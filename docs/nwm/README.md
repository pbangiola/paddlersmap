# NWM flow prototype

Standalone page: `nwm-prototype.html`, linked from the existing About page. The production homepage, app scripts and datasets are unchanged. GitHub Pages serves the entire checkout, but the production workflow does not publish feature branches.

## Local execution

From `/workspace/paddlersmap` (or your clone's root):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m http.server 8000 --bind 127.0.0.1
```

Open `nwm-prototype.html` on that server. A real, bounded NOAA snapshot is included; no refresh is necessary to try the page. The launch layer contains all 1,553 existing records, unchanged coordinates and original metadata from `data/putins_consolidated.geojson`. Green/yellow markers reuse the existing verification registry. Nothing retrieves new launches or snaps their locations.

Refresh the regional snapshot explicitly:

```sh
.venv/bin/python scripts/nwm/retrieve.py --config web/nwm/services.json
node --test web/nwm/scale.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
```

## Verified NOAA sources

Inspected ArcGIS layer schemas are recorded in [service-fields.json](service-fields.json); the exact field mapping is [services.json](../../web/nwm/services.json).

| Purpose | NOAA layer | Field | Published units |
| --- | --- | --- | --- |
| Actual flowline geometry / ID | `reference/static_nwm_flowlines/FeatureServer/0` | `feature_id`, polyline geometry | WGS84 output coordinates |
| Low flow | `nwm/ana_anomaly/MapServer/0` | `prcntle_10` | cfs |
| Provisional central flow | Same anomaly layer | `(prcntle_25 + prcntle_75) / 2` | cfs |
| Latest published modeled discharge | Same anomaly layer | `latest_flow` | cfs |
| Provisional upper anchor | Static flowline reference | `rf_2_0_17c` (50% annual exceedance, 2-year recurrence) | cfs |
| Source update | Anomaly layer | `update_time` | UTC string |

All numerical units above are NOAA's published field aliases. No unit conversions or inferred substitutes are applied. The anomaly service publishes seasonal percentile references and 7-day-average anomaly categories and describes a **daily** update cadence. The page uses its `latest_flow`, not its 7-day average, as discharge. This is the latest published daily service snapshot, not a continuously refreshed instantaneous observation.

Service URLs:

- https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0
- https://maps.water.noaa.gov/server/rest/services/nwm/ana_anomaly/MapServer/0
- NOAA documentation and visualization: https://www.weather.gov/owp/operations

The static reference reports NWM 3.0; the current anomaly records report 3.1. Joins use exact string `feature_id` only. No name matching, nearest-neighbor attribution or reconstructed river paths are used. The Chicago snapshot contains 3,433 static reaches, of which 1,661 have usable discharge and strictly ordered anchors. There are 1,415 unmatched reaches and 357 matched reaches with equal or unordered anchors; both remain gray. The two-year recurrence anchor is an experimental relative-flow upper reference, not a claim that flooding occurs at that value.

## Color scale

Reuse brown `#85512c`, blue `#0867d9`, yellow `#f0cf31`, red `#cf2929` from the existing atlas. Low maps to 0, provisional central flow to 0.25, and upper flow to 1. Normalize discharge with piecewise linear interpolation on either side of central; then interpolate RGB continuously through yellow at 0.625. Values beyond the anchors are clamped. Zero discharge is valid. Missing, negative, nonnumeric, equal or unordered anchors produce gray `#88929b`; no replacement thresholds are fabricated. These colors describe relative modeled flow, not paddling suitability.

Click a custom-colored river for its exact ID, discharge, all anchors, normalized position and NOAA update time. Launch popups retain available metadata. The NOAA comparison toggle switches to NOAA's own 7-day anomaly raster visualization, using its own category colors. Its categories are based on 7-day averages and are intentionally different from our latest-discharge scale; switch it off to inspect our numbers.

## Retrieval, caching and expansion

Default Chicago-region bbox: `[-88.5,41.2,-87.0,42.5]`. Expand with bounded `--bbox WEST SOUTH EAST NORTH` requests. Use `--output` to keep exploratory regions separate. No full-network national vector downloads are run. The national geometry overlay uses NOAA-rendered bounded raster tiles.

Static geometry and recurrence references are cached separately by service configuration and bbox. Refreshes reuse that cache and fetch the anomaly fields once per refresh. Object-ID batches honor the smaller of 200 and the service limit; missing IDs or truncated batches fail rather than silently publishing partial results. Requests are serial, paced, capped at 25,000 regional reaches and retry HTTP 429 / transient server failures with bounded backoff and Retry-After. Snapshot flow files are versioned and the manifest is replaced last; browsers never redownload the national network. Superseded prototype flow files may be removed after confirming the manifest no longer references them.

Refresh after NOAA's daily cycle when needed. Source update and local retrieval timestamps are displayed separately. Missing or mixed timestamps are explicitly unavailable. The bundled snapshot has NOAA update `2026-10-12 00:51:39 UTC`; it will age until refreshed.

## Validation and limitations

Tests cover all color anchors, interpolation, clamping, zero/missing/invalid inputs, exact feature-ID joins, source immutability, ArcGIS batch limits, truncation rejection, schema validation and rate-limit retries. Live regional retrieval was executed twice and reused identical static geometry on refresh. Chromium rendering and launch toggling/popups are checked against the actual included snapshot. See [validation.md](validation.md) for representative Chicago reach comparisons. Optional browser check: `python3 scripts/nwm/browser_smoke.py` (requires Playwright and system Chromium; the cloud environment already provides both).

Some static reaches are absent from the current anomaly service, and some have incomplete or unordered anchors. They are explicitly gray. NWM version differences are retained as a limitation rather than repaired through guessed IDs. Custom flow colors and numerical popups are bounded to Chicago. Geometry is available through NOAA’s tiled rendering across CONUS, Alaska, Hawaii, and Puerto Rico/USVI. No production deployment, merge, replacement of production datasets or live launch verification writes are performed.


## National geometry test

Use the Contiguous US, Alaska, Hawaii, and Puerto Rico / USVI buttons on the prototype. National geometry is enabled by default beneath the Chicago color layer. It displays NOAA's actual static NWM flowline geometry in gray, without downloading or reconstructing the national vector network. The National geometry toggle switches this overlay off independently.

NOAA's default layer scale cutoff suppresses broad-zoom tiles. The dynamic export requests explicitly remove that cutoff and apply a stream-order filter: order 4 and above at zooms below 7, all stream orders at zoom 7 and above. This keeps the full-map network legible while providing smaller waterways when zoomed in. NOAA renders the gray unavailable-data style; custom numerical flow colors have not been extended nationally.

A basemap fetch failure falls back to a plain background and a visible notice, so it does not prevent NOAA geometry or launch data from loading.

Run `python3 scripts/nwm/national_smoke.py` (Playwright, Pillow, and system Chromium required). The test renders the contiguous-US overview, western and eastern detail views, Alaska, Hawaii, and Puerto Rico/USVI. It checks that NOAA returned actual nontransparent geometry pixels, captures each map, and checks the geometry toggle. External HTTPS assets use the existing OS certificate trust with at most four concurrent downloads; TLS verification remains enabled. Results and screenshots are saved under `/tmp/nwm-national` by default. See [national-validation.md](national-validation.md) for measured results.
