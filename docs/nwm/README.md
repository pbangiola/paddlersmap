# NWM flow prototype

Open `nwm-prototype.html`, linked from About. The prototype now colors major rivers across the contiguous US and retrieves finer flow colors for the visible area as you zoom in. Production homepage, app scripts, datasets, and deployment remain unchanged.

## Run locally

From the checkout root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m http.server 8000 --bind 127.0.0.1
```

Open the standalone page on that server. The page opens at the contiguous-US color overview; zoom into an area for finer flow colors. Region buttons return to CONUS, Chicago, Alaska, Hawaii, or Puerto Rico/USVI. The bundled overview contains 32,209 actual NWM reaches of stream order 7+, with 22,400 usable color records. NOAA source update: `2026-10-13 00:50:51 UTC`. The remaining overview reaches lack a retrieved matching anomaly record or have invalid anchors and remain gray.

All 1,553 existing launch records retain their original coordinates and metadata. Green/yellow markers use the existing verification registry. No launch discovery, fuzzy matching, snapping or verification writes occur.

## Data sources and joins

| Purpose | NOAA ArcGIS layer | Field | Published units |
| --- | --- | --- | --- |
| Actual geometry / ID | `reference/static_nwm_flowlines/FeatureServer/0` | `feature_id`, polyline paths | WGS84 output coordinates |
| Low | `nwm/ana_anomaly/MapServer/0` | `prcntle_10` | cfs |
| Provisional central flow | Same anomaly layer | `(prcntle_25 + prcntle_75) / 2` | cfs |
| Latest published discharge | Same anomaly layer | `latest_flow` | cfs |
| Provisional upper anchor | Static flowline reference | `rf_2_0_17c` (50% annual exceedance / two-year recurrence) | cfs |
| Source update | Anomaly layer | `update_time` | UTC string |

Services are under `https://maps.water.noaa.gov/server/rest/services/`. Inspect [service-fields.json](service-fields.json) and [services.json](../../web/nwm/services.json) for the verified mappings. The browser validates field availability and published cfs aliases before querying. Values use those published units without inferred conversions. The static reference reports NWM 3.0; current anomaly records report 3.1. Joins use exact string feature IDs, with no name matching, nearest neighbors, or reconstructed geometry.

The anomaly service describes daily updates, seasonal percentile references, and 7-day-average anomaly categories. This prototype colors its latest published discharge, not its 7-day average. NOAA's comparison toggle shows the original 7-day anomaly raster and its different category colors.

**Availability:** the catalog lists only the CONUS `ana_anomaly` service; bounded queries returned zero records for Alaska, Hawaii and Puerto Rico/USVI. Their actual geometry remains visible, but the required percentile anchors are unavailable. No substitute anchors or national colors are fabricated for those domains.

## Color scale

Reuse brown `#85512c`, blue `#0867d9`, yellow `#f0cf31`, and red `#cf2929`. Low maps to 0, central to 0.25 and upper to 1. Discharge is normalized piecewise linearly on either side of central; RGB colors interpolate continuously through yellow at 0.625. Values outside the anchor range are clamped. Zero flow is valid. Missing, negative, nonnumeric, equal or unordered anchors produce gray `#88929b`.

Colors represent relative modeled flow, not paddling suitability. The central and two-year recurrence anchors are provisional. Click a river to inspect its ID, discharge, anchors, normalized position and source time. Live colors take precedence over the overview and Chicago fallback; a single popup is selected even where layers overlap. Launch markers remain above river lines.

## National overview and refresh

```sh
.venv/bin/python scripts/nwm/overview.py
```

The refresh queries west/east geographic partitions with stream order 7+, each below the 25,000-reach guard. Static geometry / recurrence references are cached under ignored `local/output/nwm-overview/`; refreshed flow values are stored separately. NOAA applies 0.02-degree cartographic generalization at nationwide scale; feature IDs are preserved. The resulting overview assets are under `web/nwm/overview/`, not production `data/`. No full 2.7-million-reach network download occurs.

Refresh after NOAA's daily cycle. Flow filenames are versioned; the manifest is replaced last. Superseded assets may be removed only after confirming no manifest references them. To refresh the original Chicago fallback, use `.venv/bin/python scripts/nwm/retrieve.py --config web/nwm/services.json`. CLI options include bounded `--bbox`, `--min-order`, `--geometry-offset`, `--batch-size`, and `--output`.

## Viewport detail and caching

At zooms below 5, the national snapshot renders immediately. At zooms 5–7 the live loader requests order 5+, at 7–9 order 3+, and at 9+ all stream orders. It partitions only the visible CONUS bounds into geographic cells, caps each view at 24 cells and each cell at 25,000 reaches, and processes three cells concurrently.

Static geometry / recurrence references and flow values use separate browser memory and IndexedDB caches. Flow values expire after 15 minutes. A fresh cached revisit requires no further feature queries; when flow expires, geometry is reused. Static geometry is generalized by NOAA appropriately for the cell's zoom, preserving IDs and geographic paths. Clear the prototype IndexedDB cache if NOAA replaces its static model/reference version.

Queries honor service record limits, reject truncated batches, validate exact flow-ID membership, and retry transient HTTP/network failures with bounded backoff. Panning aborts obsolete requests. Comparison mode stops hidden custom-color retrieval. Status reports cell progress, colored reaches, unavailable cells and actual NOAA update times. Unavailable cells retain gray geometry. A failed basemap falls back to a plain background; failed national raster tiles show a partial-coverage notice.

Live NOAA requests can be slow, especially on a first uncached detail view. The bundled overview avoids waiting for national live queries. Validation encountered six timed-out feature requests that recovered; both detail views eventually completed with zero unavailable cells. This remains a prototype, with source-service latency a material limitation.

## Validation

```sh
node --test web/nwm/*.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/nwm/colors_smoke.py
python3 scripts/nwm/browser_smoke.py
```

Optional browser checks require Playwright and system Chromium; geometry image validation also requires Pillow. These are available in the cloud environment. HTTPS validation uses the existing OS trust, with TLS verification enabled.

All 29 unit tests passed. Real browser checks passed for national colors, western/eastern detail, cached revisits without additional feature reads, numerical popups, all unchanged launch coordinates, visibility controls, and continued launches when the Chicago snapshot fails. See [color-validation.md](color-validation.md), [original Chicago comparisons](validation.md), and [national geometry checks](national-validation.md). Production datasets and deployment have not been changed or published.
