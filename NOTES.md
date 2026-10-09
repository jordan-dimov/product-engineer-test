# Notes

## Assumptions

- Each draw stores the status and ranges as recorded at the time of the draw. The history shows those recorded ranges and never recomputes them against the current definitions, so a range that changed between draws appears as a step in the chart.
- The stored status is displayed as is, even where it disagrees with its own stored ranges. Changing what a member was told at the time is a product decision, not a display fix.
- History is served on `GET /api/home` keyed by biomarker id, chronological, with one point per draw that measured the marker. Partial panels simply have fewer points.

## Storage layout

- Biomarkers keep the existing layout: `results:{user_id}` with the ISO draw timestamp as sort key, one document per draw. The home screen reads the whole partition with one `query` and pivots it into latest values plus per-marker history in code. That is cheap while a member has a handful of draws; one marker's history still decodes every draw.

## What was left out and what comes next

## How AI tools were used
