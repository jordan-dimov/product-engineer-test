"""Task 2 tests: ingest through HTTP, checked against the store and the home screen."""

import json
import logging
from pathlib import Path

import pytest

from app.models import DailyMetrics

WEARABLES = Path(__file__).resolve().parents[1] / "data" / "wearables"

EMAILS = {
    "user-1": "james.chen@example.com",
    "user-2": "priya.raman@example.com",
    "user-3": "tom.okafor@example.com",
    "user-4": "sofia.marek@example.com",
}


def delivery(user_id, name):
    """One fixture file, e.g. delivery("user-3", "2026-07-17_r2")."""
    return json.loads((WEARABLES / user_id / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def no_wearables(store):
    """dev.db may already hold the imported fixtures; every test starts from none."""
    for user_id in EMAILS:
        for partition in (f"wearable_day:{user_id}", f"wearable_upload:{user_id}"):
            for key in list(store.keys(partition)):
                store.delete(partition, key)


def sign_in(client, user_id):
    response = client.post("/api/auth/login", json={"email": EMAILS[user_id]})
    assert response.status_code == 200
    return client


def test_ingest_stores_a_delivery(client, store):
    response = client.post(
        "/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31")
    )
    assert response.status_code == 200
    assert response.json()["data"] == {
        "stored": True,
        "calendar_date": "2026-08-31",
        "upload_id": "ou_20260831",
        "replaced_upload_id": None,
    }
    day = store.get("wearable_day:user-1", "2026-08-31", DailyMetrics)
    assert day == DailyMetrics(
        date="2026-08-31",
        provider="oura",
        upload_id="ou_20260831",
        resting_hr_bpm=64,
        steps=17925,
        sleep_efficiency_pct=89.0,
    )


def test_whoop_efficiency_is_a_fraction_and_steps_are_not_reported(client, store):
    client.post("/api/users/user-2/wearables", json=delivery("user-2", "2026-08-31"))
    day = store.get("wearable_day:user-2", "2026-08-31", DailyMetrics)
    assert day is not None
    assert (day.resting_hr_bpm, day.steps, day.sleep_efficiency_pct) == (63, None, 80.9)


def test_fitbit_null_sleep_gives_null_efficiency(client, store):
    client.post("/api/users/user-4/wearables", json=delivery("user-4", "2026-07-22"))
    day = store.get("wearable_day:user-4", "2026-07-22", DailyMetrics)
    assert day is not None
    assert (day.resting_hr_bpm, day.sleep_efficiency_pct) == (58, None)


def test_later_delivery_replaces_the_day_and_keeps_both_envelopes(client, store):
    client.post("/api/users/user-3/wearables", json=delivery("user-3", "2026-07-17"))
    response = client.post(
        "/api/users/user-3/wearables", json=delivery("user-3", "2026-07-17_r2")
    )
    assert response.json()["data"]["replaced_upload_id"] == "ga_20260717"
    day = store.get("wearable_day:user-3", "2026-07-17", DailyMetrics)
    assert day is not None
    assert (day.upload_id, day.resting_hr_bpm) == ("ga_20260717_r2", 67)
    assert list(store.keys("wearable_upload:user-3")) == [
        "2026-07-17#ga_20260717",
        "2026-07-17#ga_20260717_r2",
    ]


def test_replaying_a_delivery_is_idempotent(client, store):
    for _ in range(2):
        client.post(
            "/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31")
        )
    assert list(store.keys("wearable_day:user-1")) == ["2026-08-31"]
    assert list(store.keys("wearable_upload:user-1")) == ["2026-08-31#ou_20260831"]


def test_home_fills_30_days_ending_on_the_latest_delivery(client):
    for name in ("2026-08-01", "2026-08-02", "2026-08-31"):
        client.post("/api/users/user-1/wearables", json=delivery("user-1", name))

    wearables = sign_in(client, "user-1").get("/api/home").json()["data"]["wearables"]
    assert wearables["provider"] == "oura"
    days = wearables["days"]
    assert len(days) == 30
    assert [d["date"] for d in days][::29] == ["2026-08-02", "2026-08-31"]
    assert days[0]["upload_id"] == "ou_20260802"
    assert days[1] == {
        "date": "2026-08-03",
        "provider": "oura",
        "upload_id": None,
        "resting_hr_bpm": None,
        "steps": None,
        "sleep_efficiency_pct": None,
    }


def test_home_only_returns_the_signed_in_members_wearables(client):
    client.post("/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31"))
    home = sign_in(client, "user-2").get("/api/home").json()["data"]
    assert home["wearables"] is None


def test_home_makes_five_store_reads(client, caplog):
    client.post("/api/users/user-1/wearables", json=delivery("user-1", "2026-08-31"))
    sign_in(client, "user-1")
    caplog.set_level(logging.INFO)
    caplog.clear()

    assert client.get("/api/home").status_code == 200
    # get user (session), query results, query biomarker definitions,
    # keys wearable_day (latest date), query wearable_day (the 30 day window).
    assert sum(r.getMessage().startswith("store:") for r in caplog.records) == 5
