# Mississippi reservoirs and connected lakes

This pass prioritizes the **Mississippi River mainstem** within `[-96,28,-88,49]`, selecting all stream orders. It is an initial waterbody inventory, not a national dam/reservoir inventory. Existing launch datasets and all original `data/**` files remain unchanged.

## Identification and source limits

NOAA's [`reference/static_nwm_waterbodies/MapServer/0`](https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_waterbodies/MapServer/0) publishes polygon geometry, `feature_id` and `gnis_name`. It supplies **no reservoir/natural-lake classification, operating state, storage, level or release metadata**. Those values are not invented. Its footprints can cover only part of a larger named lake; the estimated area follows the published polygon, not the entire basemap lake.

The mainstem selection uses NOAA's exact `name = 'Mississippi River'` attribute to prioritize retrieval. Names never create connections. Full NOAA flowline geometries are joined by exact `feature_id`; actual line/polygon overlap discovers footprints. Majority-interior overlap identifies member reaches. Published NWPS `route.upstream/downstream.reachId` edges connect them and supply boundary context, including unnamed channel reaches. Minor tributaries remain excluded from main-channel estimates. The cached geometry retains NOAA coordinates (generalization offset 0.0001 degrees); no straight lines are drawn across missing channel geometry, and launches are never snapped.

Two candidate footprints are invalid even when fetched without simplification: **Pool 2 (120051919)** and **unnamed waterbody 13358122**. They are excluded and recorded in dataset metadata, rather than repairing or inventing their boundaries. NOAA's waterbody service does not identify every Mississippi navigation pool or reservoir; further coverage needs suitable authoritative footprints and confirmed routing.

## Color interpolation

`web/nwm/reservoirs.mjs` performs **visual interpolation only**, after valid modeled and observed colors have been calculated:

1. Follow published edges along the identified mainstem and channels of at least its order. At upstream headwater order changes, the largest published inflow branches can be considered; ties retain all equally dominant branches. Named priority reaches are allowed through order changes only when the published topology connects them. Actual geometry's stream order takes precedence over NWPS edge metadata (a downstream edge's order can describe the originating channel).
2. Find valid upstream and downstream references outside the footprint's member reach set. All required main-channel branches must resolve. Each endpoint retains its own normalized relative-flow position. Observed positions are used only when the whole bracket has eligible observations; otherwise modeled positions are used consistently. Mixed stage/discharge anchors are never averaged together.
3. The surface tint is the midpoint of the mean upstream and mean downstream normalized positions. It is uniform across that NOAA footprint, with a translucent fill and dashed outline.
4. A missing channel color uses upstream/downstream positions interpolated by approximate great-circle channel distance between reach midpoints. Existing real modeled and observed colors are preserved. Duplicate paths to an anchor deduplicate by exact ID, using their shortest distance.
5. Numerical discharge, low/central/flood references, stage and geometry remain unchanged. No reservoir discharge is calculated. Popups retain endpoint records, timestamps, scale type and method. The entire polygon is marked as an estimate.

Missing brackets, incomplete routing, unknown stream orders, cycles, invalid lengths, overlapping memberships and exceeded search limits leave estimates explicitly unavailable (gray). Each browser search is bounded to 50 edges and 2,000 recursive visits per waterbody/scale attempt. Minor tributaries, reservoir storage and dam releases can affect actual conditions; this color estimate is not a hydrologic mass-balance calculation or navigability rating.

## Retrieval, refresh and local execution

```sh
# Uses existing requests + Shapely dependencies, no new service:
.venv/bin/python scripts/nwm/reservoirs.py --max-requests 800 --max-depth 50
# Refresh values only; never redownload polygons or routing:
.venv/bin/python scripts/nwm/reservoirs.py --flow-only
# Serve the existing site:
.venv/bin/python -m http.server 8001 --bind 127.0.0.1
# Browser validation with Playwright and system Chromium:
.venv/bin/python scripts/nwm/reservoir_smoke.py
```

The identification script caps the mainstem selection at 3,000 reaches, uses geographic latitude bands, checks waterbody fields, and limits polygon query regions to 5,000 IDs with 200-record geometry batches. It validates returned batches and exact IDs. Routing uses at most three workers, at most 1,000 new requests per run (400 by default), and at most 50 boundary rings (24 by default). Successful raw responses are checkpointed under ignored `local/output/nwm-reservoirs/`. Repeating a command resumes static caches. Cache bounding boxes must match their queries.

Published `waterbodies.geojson`, `context.geojson` and `topology.json` are static. Frequently changing values live separately in `flow.json`, queried in 100-ID batches against the already-verified cfs anomaly service. Missing individual records remain missing; truncated, foreign or entirely empty responses retain the prior snapshot. The existing daily overview workflow refreshes this bounded context independently, retaining its cache if the service fails. The browser checks the flow snapshot every 15 minutes, and current visible exact-ID flow values take precedence when available. Gauge eligibility and freshness still use the existing observed-data policy.

Use the **Mississippi: Lake Pepin** button to open the priority view. **Reservoir/lake estimates** independently hides the tints and reservoir interpolation. NOAA's seven-day comparison hides these custom estimates, and launch markers stay above all river and reservoir layers. Technical details start collapsed.

Current test evidence and coverage counts are in [reservoir validation](reservoir-validation/README.md).
