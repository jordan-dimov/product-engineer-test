from datetime import date
from typing import TypeVar

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- envelope


T = TypeVar("T")


class Envelope[T](BaseModel):
    """Every endpoint returns {"data": ..., "meta": ...}."""

    data: T
    meta: dict = Field(default_factory=dict)


# ------------------------------------------------------- stored documents


class Member(BaseModel):
    """pk="user", sk=id"""

    id: str
    email: str
    name: str
    sex: str
    birth_date: str
    created_at: str


class EmailPointer(BaseModel):
    """pk="email", sk=email: a pointer partition."""

    user_id: str


class Band(BaseModel):
    min: float
    max: float


class Ranges(BaseModel):
    optimal: Band
    good: Band
    improve: Band


class BiomarkerDefinition(BaseModel):
    """pk="biomarker", sk=biomarker_id"""

    id: str
    name: str
    category: str
    unit: str
    description: str
    direction: str
    ranges: Ranges


class BiomarkerResult(BaseModel):
    biomarker_id: str
    value: float
    unit: str
    status: str
    ranges: Ranges
    source: str | None = None


class ResultsDocument(BaseModel):
    """pk=f"results:{id}", sk=tested_at"""

    user_id: str
    tested_at: str
    results: list[BiomarkerResult]


class DailyMetrics(BaseModel):
    """pk=f"wearable_day:{user_id}", sk=date: one day's metrics, null if unreported."""

    date: date
    provider: str
    upload_id: str | None
    resting_hr_bpm: float | None = None
    steps: int | None = None
    sleep_efficiency_pct: float | None = None


# -------------------------------------------------------- response & resquest models


class MemberView(BaseModel):
    id: str
    email: str
    name: str
    sex: str
    birth_date: str


class BiomarkerView(BaseModel):
    biomarker_id: str
    name: str
    category: str
    description: str
    direction: str
    value: float
    unit: str
    tested_at: str
    status: str
    ranges: Ranges


class MemberPayload(BaseModel):
    user: MemberView


class BiomarkerListPayload(BaseModel):
    results: list[BiomarkerView]


class OkPayload(BaseModel):
    ok: bool


class HistoryPoint(BaseModel):
    """One draw's reading of a marker, with the status and ranges recorded then."""

    tested_at: str
    value: float
    status: str
    ranges: Ranges


class WearablesPayload(BaseModel):
    """Thirty days ending on the latest delivery; days without one carry nulls."""

    provider: str
    days: list[DailyMetrics]


class HomePayload(BaseModel):
    results: list[BiomarkerView]
    history: dict[str, list[HistoryPoint]]
    wearables: WearablesPayload | None


class ReadingBody(BaseModel):
    biomarker_id: str
    value: float
    unit: str
    tested_at: str


class ReadingPayload(BaseModel):
    biomarker_id: str
    tested_at: str
    status: str
    created_draw: bool


class DrawReading(BaseModel):
    biomarker_id: str
    value: float
    unit: str


class DrawBody(BaseModel):
    tested_at: str
    results: list[DrawReading]


class DrawResultPayload(BaseModel):
    biomarker_id: str
    status: str


class DrawPayload(BaseModel):
    tested_at: str
    created_draw: bool
    accepted: list[DrawResultPayload]
    results_in_draw: int


class WearableMember(BaseModel):
    reference_id: str
    email: str


class WearableDay(BaseModel):
    model_config = {"extra": "allow"}

    calendar_date: date
    upload_id: str


class WearableBody(BaseModel):
    provider: str
    member: WearableMember
    data: WearableDay


class WearablePayload(BaseModel):
    stored: bool
    calendar_date: date
    upload_id: str
    replaced_upload_id: str | None
