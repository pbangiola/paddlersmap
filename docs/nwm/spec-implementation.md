# Prototype revision: coordinated rendering, observed sections, canonical launches

This branch implements rendering and reproducible data pipelines for the supplied specification without merging or deploying it. Real observed routing and complete national OSM coverage remain subject to the source gaps below. The production homepage, broad legacy datasets, and verification registry remain unchanged. `nwm-prototype.html` now loads only its canonical launch dataset.

## Rendering

`web/nwm/policy.mjs` defines one policy used by vector filters, live query thresholds and NOAA raster definitions. Zoom tiers are <5: order7+, 5–7:6+, 7–9:5+, 9–11:4+, 11–13:3+, 13+:1+. Target line widths are 2/2.5/3/3.5/4/4.5 pixels, with smooth width interpolation and rounded vector caps/joins. Gray geometry obeys the same discrete tiers. Basemap waterway line layers are removed so they cannot contribute an unfiltered second river mesh; lake/coast polygons remain. NOAA raster widths remain 0.9 ArcGIS points: gray serves as a subdued missing-data background, with colored vectors carrying the requested weight.

The Chicago fallback is no longer fetched or rendered; its files remain for reference. Overview renders only below zoom5, live vectors only at zoom5+, and observed colors modify those same features rather than drawing another overlapping layer. Launches, comparison, geometry, observations and live loading initialize independently of overview success. Comparison hides both observed and modeled colors and the gray geometry. Visibility is read from controls after every asynchronous update. View movement aborts requests and clears obsolete live features; sequence checks reject late results. Existing bounded/paginated requests, separate static/flow caching, 15-minute flow TTL, service-schema checks and retries remain.

## Observed sections and real-data limitations

`python3 scripts/nwm/gauge_assignments.py --topology /path/to/verified-topology.json` rebuilds static assignments. Expected input:

```json
{"method":"published-directed-nwm","source":"authoritative URL/version and field documentation","reaches":{"123":{"downstream":["124"]},"124":{"downstream":[]}}}
```

Keys are actual NWM feature IDs, with documented downstream edges. This is an input contract, not a supplied national topology. Existing NWPS `reachId` records supply explicit candidate gauge IDs. Nearest-line and same-name graphs are not accepted. The builder validates IDs, follows a unique directed path to the next gauge, rejects cycles/divergences/missing topology, and withholds conflicting assignments. It excludes both endpoint reaches because the exact along-reach gauge locations are unknown: only whole reaches strictly between gauges receive observed colors. Tributaries are not expanded.

The NOAA static service inspected on October 13, 2026 provides geometry and feature IDs but **no directed connectivity fields**. The repository's existing gauge graph and nearest-watercourse reconciliation do not establish NWM topology. The committed assignments contain zero confirmed sections and identify 10,147 explicit-ID candidates; this is not observed national coverage. No real same-river pair is claimed validated.

The existing atlas stage scale is reused: `(stage - low) / (flood - low)`, clamped to [0,1], with the same scalar-to-color function as NWM. Each endpoint uses its own stage references; a section uses the arithmetic mean of normalized positions. NWM percentile discharge references are never used as gauge stage anchors. Stage readings and anchors must be finite and compatible in feet, with an identified reference source. Low stage may be negative; upper must be positive and exceed low, matching the existing atlas stage policy. The freshness default is 36 hours, matching the existing atlas report policy, with future timestamps rejected; callers can configure the pure normalization function and the browser consumes `max_age_hours` from the observation manifest. NOAA NWPS import currently omits primary observation units; these records remain ineligible. USGS measurements use the repository's documented NWIS gauge-height parameter 00065 in feet, with adequate-coverage annual minima and official flood stages.

`python3 scripts/nwm/gauge_assignments.py --observations-only` refreshes readings independently of topology. This command is included in the existing three-hour USGS refresh workflow. Browser observations reload every 15 minutes and eligibility is checked each minute. Missing, stale, incompatible or ambiguous endpoints restore original NWM colors; disabling the default-on gauge toggle does the same. Popups for eligible sections include endpoint readings, names/IDs, timestamps, references, normalized positions, method, confidence and covered reach IDs alongside underlying NWM inputs.

## Launch coverage and migration

The latest repository national named-launch jobs failed/cancelled, and `data/putins_named_canoe_launches.geojson` does not exist on main. A hosted, resumed Overpass run retrieved 21 real matching records in 9 of 48 cells before two HTTP504 failures stopped publication. These partial records were not promoted. A subsequent alternate-provider run also stopped with 9/48 complete cells and 21 records, after repeatable timeouts in `conus-2-1` and `conus-3-1`. Both reports and raw checkpoints are preserved in review artifacts. Direct national and Chicago Overpass probes failed (timeouts, HTTP504/406, and a proxy-denied endpoint). Therefore **national matching OSM records have not been retrieved or claimed complete**. No older regional name-filtered list was substituted.

The initial prototype canonical inventory contains only the 75 explicit regional CSV records, 14 coordinate-resolved Google catalogue records, and 12 explicitly reviewed OSM records: 101 records with original coordinates. The remaining 36 Google catalogue entries lack resolved coordinates; they are retained in the original catalogue and listed in the review report, not placed at invented positions. The historical consolidated inventory is not treated as owner-curated. Generic historical OSM candidates are no longer loaded. All 14 registry-verified identities remain present and green; reviewed OSM IDs are explicit curated exceptions, with review provenance retained. Verification is never transferred to nearby points. The production registry and original input files are preserved.

See `launch-reconciliation.json` for counts, preserved IDs, ambiguities, source gaps and excluded verification identities. Until a complete source is available the UI explicitly labels national coverage incomplete.

```sh
python3 scripts/nwm/launch_inventory.py --retrieve
# Or use a complete, provenance-bearing source FeatureCollection:
python3 scripts/nwm/launch_inventory.py --source /path/to/source.geojson
```

Retrieval intersects the US/PR/VI/GU/MP/AS administrative-area union with bounded cells across CONUS, Alaska (including both sides of the dateline), Hawaii, Puerto Rico/USVI, Guam/CNMI and American Samoa. US Minor Outlying Islands are not comprehensively covered; records falling inside the declared bounding boxes may be included. Primary names must contain literal `canoe launch`, case-insensitively; arbitrary ramps/tags are not included. Nodes use original coordinates; ways/relations use Overpass bounding-box centers, retaining original elements/geometry. Raw responses, retrieval/OSM timestamps and progress are checkpointed under ignored `local/output/canonical-launches/`. Retry attempts are bounded, and two failing cells suspend remaining network work for a resumable later run. Any failed/unattempted cell prevents publication and leaves the previous complete active dataset untouched.

Stable source IDs deduplicate first; source-coordinate changes retain the original curated point and updated raw geometry and require review. Cross-source reconciliation requires exact normalized names and <=40m distance (configurable `--max-m`); generic names and proximity alone cannot merge records. Curated coordinates/IDs win, alternate identities/names and raw records are retained, and an alternate verified identity is withheld for explicit review rather than silently transferring status. Ambiguous neighboring accesses remain separate. The existing named-launch workflow is now manual and uploads review artifacts; it never commits or deploys output. Checkpoint caches and the optional `resume_run` input (a prior review-artifact run ID) support resuming even after failures. Remove the checkpoint directory to request a wholly fresh OSM snapshot.

## Local execution and verification

```sh
.venv/bin/python -m http.server 8001 --bind 127.0.0.1
node --test web/nwm/*.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/nwm/spec_smoke.py
```

Open `nwm-prototype.html` from the local server. Browser validation uses real NOAA services and verified HTTPS, system Chromium and Playwright. `spec-validation/` contains screenshots and results; synthetic path tests verify algorithms only and do not establish real-data completeness. `browser_smoke.py` delegates to these current checks; use `spec_smoke.py` for this revision.

## Validation findings

46 local unit tests passed (14 Node, 32 Python). The final real NOAA browser check passed seven representative views: national, Chicago regional/city/neighborhood, Portland, Alaska and Hawaii. The final Chicago sample had five live-colored reaches after three cells exhausted bounded timeout retries; an earlier run verified 64 live-colored reaches. Clicking a rendered reach displayed actual discharge, reference inputs and source time. All 101 canonical launch IDs/geometries matched the input snapshot, and all 14 registry-verified IDs remained green. Launch popups, launch/gauge/comparison controls, render order, absent Chicago assets and failed national snapshot behavior passed. Five actual navigation buttons were tested separately, including Puerto Rico/USVI. No JavaScript page errors occurred. Screenshot capture uses a larger timeout for software WebGL in the cloud runner; the test avoids serializing the Map object.

The final browser run recorded three external transport failures plus three timed-out live cells; see `spec-validation/results.json` for exact requests. Some OpenFreeMap expressions logged null-value warnings and a missing interstate shield. These are recorded, not classified as a clean console/network run. Available NOAA data remained usable; unavailable cells remained gray. Screenshots show heavier modeled Des Plaines lines, sparse Portland gray geometry while detail loads, and honest gray Hawaii geometry. These checks do not establish observed national coverage or complete national launch retrieval.
