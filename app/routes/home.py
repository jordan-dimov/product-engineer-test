from fastapi import APIRouter, Depends

from ..auth import current_user
from ..models import (
    BiomarkerDefinition,
    BiomarkerListPayload,
    BiomarkerView,
    Envelope,
    HistoryPoint,
    HomePayload,
    Member,
    ResultsDocument,
)
from ..store import Store, get_store

router = APIRouter(prefix="/api")


DEFINITIONS = "biomarker"


def definitions(store: Store) -> dict[str, BiomarkerDefinition]:
    return {
        marker_id: definition
        for marker_id, definition in store.query(DEFINITIONS, BiomarkerDefinition)
    }


def member_results(
    store: Store, user_id: str
) -> tuple[list[BiomarkerView], dict[str, list[HistoryPoint]], str | None]:
    """Latest values and per-marker history from one query over a member's draws.

    One partition per member, one document per draw, sorted by ISO timestamp. So
    the query yields draws chronologically and the last one is the latest. Each
    history point carries the status and ranges recorded at its draw; nothing is
    recomputed against current definitions.
    """
    draws = [draw for _sk, draw in store.query(f"results:{user_id}", ResultsDocument)]
    if not draws:
        return [], {}, None

    history: dict[str, list[HistoryPoint]] = {}
    for draw in draws:
        for result in draw.results:
            history.setdefault(result.biomarker_id, []).append(
                HistoryPoint(
                    tested_at=draw.tested_at,
                    value=result.value,
                    status=result.status,
                    ranges=result.ranges,
                )
            )

    draw = draws[-1]
    defs = definitions(store)

    views = []
    for result in draw.results:
        definition = defs.get(result.biomarker_id)
        views.append(
            BiomarkerView(
                biomarker_id=result.biomarker_id,
                name=definition.name if definition else result.biomarker_id,
                category=definition.category if definition else "other",
                description=definition.description if definition else "",
                direction=definition.direction if definition else "in_range",
                value=result.value,
                unit=result.unit,
                tested_at=draw.tested_at,
                status=result.status,
                ranges=result.ranges,
            )
        )

    views.sort(key=lambda v: (v.category, v.name))
    return views, history, draw.tested_at


@router.get("/biomarkers", response_model=Envelope[BiomarkerListPayload])
def list_biomarkers(
    member: Member = Depends(current_user), store: Store = Depends(get_store)
):
    results, _history, _tested_at = member_results(store, member.id)
    return Envelope(
        data=BiomarkerListPayload(results=results),
        meta={
            "count": len(results),
            "categories": sorted({r.category for r in results}),
        },
    )


@router.get("/home", response_model=Envelope[HomePayload])
def home(member: Member = Depends(current_user), store: Store = Depends(get_store)):
    """Everything the member's home screen needs, in one request.

    Budget: defined and measured by scripts/bench.py.
    Whatever you add to this screen, it has to still pass when you are done.
    """
    results, history, tested_at = member_results(store, member.id)

    return Envelope(
        data=HomePayload(results=results, history=history),
        meta={
            "count": len(results),
            "categories": sorted({r.category for r in results}),
            "tested_at": tested_at,
        },
    )
