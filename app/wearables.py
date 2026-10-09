"""Provider envelopes to one DailyMetrics document.

Each parser takes a delivery's `data` object and returns the three metrics,
null where the provider did not report one. Missing means null, never zero,
and the provider, not the magnitude, decides whether a figure is a fraction or
a percentage.
"""

from collections.abc import Callable

from .models import DailyMetrics, WearableBody


def _terra_shape(data: dict) -> dict:
    """oura, garmin and fitbit: efficiency in percent, steps in 96 buckets."""
    heart = data.get("heart_rate_data") or {}
    sleep = data.get("sleep_data") or {}
    steps = (data.get("activity_data") or {}).get("steps_samples")
    return {
        "resting_hr_bpm": heart.get("resting_hr_bpm"),
        "steps": sum(s["value"] or 0 for s in steps) if steps else None,
        "sleep_efficiency_pct": sleep.get("efficiency_pct"),
    }


def _whoop(data: dict) -> dict:
    """whoop: efficiency as a fraction of one, no steps at all."""
    resting = (data.get("heart_rate") or {}).get("resting") or {}
    fraction = (data.get("sleep") or {}).get("efficiency")
    return {
        "resting_hr_bpm": resting.get("bpm"),
        "steps": None,
        "sleep_efficiency_pct": None if fraction is None else round(fraction * 100, 1),
    }


PARSERS: dict[str, Callable[[dict], dict]] = {
    "oura": _terra_shape,
    "garmin": _terra_shape,
    "fitbit": _terra_shape,
    "whoop": _whoop,
}


def daily_metrics(body: WearableBody) -> DailyMetrics:
    """The day document for a delivery. An unknown provider gives null metrics."""
    parse = PARSERS.get(body.provider)
    return DailyMetrics(
        date=body.data.calendar_date,
        provider=body.provider,
        upload_id=body.data.upload_id,
        **(parse(body.data.model_dump()) if parse else {}),
    )
