# Notes

## Assumptions

- Each draw stores the status and ranges as recorded at the time of the draw. The history shows those recorded ranges and never recomputes them against the current definitions, so a range that changed between draws appears as a step in the chart.
- The stored status is displayed as is, even where it disagrees with its own stored ranges. Changing what a member was told at the time is a product decision, not a display fix.
- History is served on `GET /api/home` keyed by biomarker id, chronological, with one point per draw that measured the marker. Partial panels simply have fewer points.
- The wearable window is the 30 calendar days ending on the member's latest delivery, not today, so a member whose device stopped syncing still sees their last month rather than an empty chart.
- Wearable charts leave a day without a value as a gap in the line rather than bridging it, so a missing delivery, a null field and a corrected day all read truthfully. A metric that is null on every day of the window is a line of text instead of an empty chart: "Not reported by {provider}" when deliveries exist (whoop steps), "No data in this period" otherwise.
- The history chart is opened per marker on demand, so the page does not build thirty charts up front. The optimal and good bands are drawn from the ranges recorded at each draw and held until the next draw, so a changed range shows as a step at the draw that introduced it. A marker with one draw shows a single point; its bands are already on the scale above the chart.

## Storage layout

- Wearables use two partitions per member. `wearable_day:{user_id}` holds one small `DailyMetrics` document per calendar date (provider, upload id, resting heart rate, steps, sleep efficiency, each nullable), so a 30 day window is one range query. `wearable_upload:{user_id}` holds every envelope exactly as received, keyed `{date}#{upload_id}`, so corrections are kept alongside the original. Both are written in one transaction. The home screen never reads the upload partition; a raw day is 70 to 86 KB and would blow the budget.
- A repeated delivery for the same day replaces the day document, because the later file carries the corrected value and the earlier envelope is still on record. Replaying a file is idempotent. The response reports the upload id that was replaced.
- The day is taken from `calendar_date` in the envelope, never derived from a sample timestamp (whoop timestamps are +01:00).
- A missing or null field is stored as null, never zero. Whoop reports sleep efficiency as a fraction of one and is multiplied by 100; the provider decides that, not the magnitude of the value. Whoop reports no steps, so steps are null for that member.
- `GET /api/home` makes five store reads: the session's member, the member's draws, the biomarker definitions, the keys of the member's wearable days (the last key is the latest date, nothing decoded) and one range query for the 30 days ending there. Missing days are filled server-side with null metrics so the client draws a plain calendar. A test pins the count.
- Benchmarks after importing all four members' fixtures, serial p95 for `GET /api/home` against a 35 ms budget: James Chen 2.7 ms, Priya Raman 2.0 ms, Tom Okafor 2.4 ms, Sofia Marek 2.0 ms.
- An unknown provider is still stored: the envelope is kept and the day document has null metrics, so nothing is lost and the charts show gaps until a parser exists.
- Biomarkers keep the existing layout: `results:{user_id}` with the ISO draw timestamp as sort key, one document per draw. The home screen reads the whole partition with one `query` and pivots it into latest values plus per-marker history in code. That is cheap while a member has a handful of draws; one marker's history still decodes every draw.

## What was left out and what comes next

## How AI tools were used
