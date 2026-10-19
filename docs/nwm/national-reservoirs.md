# National all-flow reservoir expansion through Actions

The Mississippi baseline is preserved. The new pipeline identifies NOAA waterbody footprints in geographic cells and queries **every stream order, named or unnamed**, actually intersecting each footprint. Neither discovery nor channel selection has a river-name filter. Only exact NWM IDs and published NWPS routing create connections. Surface and channel interpolation retain the [same visual-only methodology](reservoirs.md); no numerical discharge, stage or reservoir operating data is invented.

## GitHub Actions

**Expand and refresh national NWM waterbodies** (`.github/workflows/nwm-reservoirs-national.yml`) runs:

- **Hourly at :45 UTC:** discover up to two cells, process up to 32 waterbodies, and perform at most 800 new routing lookups, with a 20-minute work deadline.
- **Daily at 06:05 UTC:** refresh already-published numerical values without downloading geometry or routing. Exact context IDs are deduplicated; up to 50 batches of 5,000 cached IDs rotate through a durable cursor. A footprint's snapshot is published only when every required ID's batch succeeded; old snapshots retain their original retrieval time on failure.
- **Manual dispatch:** choose `expand` or `refresh`, optionally select a cell, and set waterbody/routing limits. `publish=false` creates a review artifact without committing; automatic publication is main-branch-only. `publish=true` commits map outputs and explicitly dispatches GitHub Pages.

Only `web/nwm/reservoirs/national/**` can be committed by this workflow. It never changes original `data/**`, launch coordinates/identities, or the Mississippi baseline. A shared concurrency group prevents the expansion and daily refresh jobs racing one another. Failed cells/footprints retain diagnostics, pause for two hours, and do not block other regions. Source caches persist through Actions cache; committed progress survives cache eviction. Review artifacts are retained for seven days.

## Durable coverage and source gaps

The initial grid has **404 cells**: CONUS, Hawaii and Puerto Rico/USVI. Each footprint belongs to one cell by its bounding-box center, so crossing cell borders cannot duplicate it. Cell discovery is independent of individual footprint processing, allowing a dense cell to finish across multiple runs.

NOAA's reference catalog has no Alaska NWM waterbody layer; Alaska footprint identification is explicitly unavailable. Hawaii and PR/USVI have waterbody/flowline geometry but lack the modeled anomaly anchors in the CONUS service. Those snapshots contain no fabricated modeled values; verified observed brackets may still supply estimates when available. This is incremental coverage, not a claim that every US reservoir is already mapped or colored.

`progress.json` records cells, queued/retry/published/unavailable footprints, source failures and the flow-refresh cursor. `manifest.json` exposes published footprints and coverage counts. Each footprint has separate `static.json` (actual geometry and published routing) and `flow.json` (changing values). The footprint ID is kept distinct from its member reach IDs.

## Bounded retrieval

- Waterbody discovery queries are geographic, capped at 5,000 IDs per cell, with batches no larger than 200 or the advertised service limit.
- Flowline discovery uses the actual polygon in a POST query, including correctly oriented holes, avoiding URL-length truncation. It selects `where=1=1`, all stream orders, capped at 5,000 intersecting flowlines per footprint.
- Routing uses three workers, a shared lookup/time budget, and at most 50 boundary rings. All geographic IDs are validated before joins. Domain-specific geometry retrieval prevents accidentally resolving a regional ID against another domain.
- Invalid footprints, oversized selections, missing geometry and unavailable numerical references stay unavailable/retryable. Successful cached responses resume a later run. Failed rebuilds retain an existing published snapshot.
- Source metadata and raw routing caches remain in ignored `local/output/nwm-national-reservoirs/`; no complete national flowline network is downloaded.

## Browser loading and width

The map loads only the published footprints intersecting the current viewport and shared stream-order tier, up to 24 at once. Three workers fetch static geometry once and cache changing flow values for 15 minutes. Moving away discards those footprints from the active dataset; returning reuses their cached files. National snapshots older than 36 hours cannot silently act as fresh numerical anchors. Conflicting cached routing is withheld. The Mississippi baseline remains available independently.

NOAA's reference flowline and seven-day anomaly renderers both publish a **1-point** line symbol. Our vectors and reservoir outlines now use **96/72 = 1.333333 CSS pixels**, independent of zoom; the national raster uses the same 1-point symbol at explicit 96 DPI. The comparison export also specifies 96 DPI. The stream-order density tiers remain 6+/5+/4+/3+/2+/1+.

## Local commands

```sh
# Bounded expansion, all flows through owned footprints:
.venv/bin/python scripts/nwm/national_reservoirs.py \
  --max-cells 2 --max-waterbodies 32 --routing-budget 800 --max-depth 50 --seconds 1200
# Review a specific cell without losing existing progress:
.venv/bin/python scripts/nwm/national_reservoirs.py --cell conus_-123_40 --max-waterbodies 1
# Resume/enlarge a known footprint's boundary context explicitly:
.venv/bin/python scripts/nwm/national_reservoirs.py --rebuild-body conus-2781987 --max-depth 50
# Flow-only refresh of published cached IDs:
.venv/bin/python scripts/nwm/national_reservoirs.py --mode refresh
# Browser check (serve the repository on port 8001):
.venv/bin/python scripts/nwm/national_reservoir_smoke.py
```

Validation and source evidence: [national validation](national-validation/README.md).
