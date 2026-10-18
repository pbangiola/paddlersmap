# Paddler’s Map

[Open the map](https://pbangiola.github.io/paddlersmap/) — NOAA’s actual National Water Model river network with relative flow colors, verified gauge connections and existing curated canoe/kayak launches.

The homepage now uses the NWM renderer. The older Chicago-area courses and name-based straight-line connections have been retired. Existing links to `nwm-prototype.html` and `gauge-connections.html` redirect to the homepage. Original source datasets are preserved for reproducibility; they are not loaded as legacy overlays.

## Run locally

```sh
python -m http.server 8001 --bind 127.0.0.1
# Open http://127.0.0.1:8001/
node --test web/nwm/*.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
```

Install Python pipeline dependencies into a virtual environment (`requests` is required for NOAA geometry/overview retrieval). Optional browser checks use Playwright and Chromium:

```sh
.venv/bin/python scripts/nwm/primary_smoke.py
.venv/bin/python scripts/nwm/connections_smoke.py
```

## What the colors mean

Modeled colors use NOAA’s latest discharge and published numerical references: 10th percentile, provisional midpoint of the 25th/75th percentiles, and a provisional two-year recurrence upper anchor. Colors interpolate continuously through brown, blue, yellow and red. Missing or invalid numerical references remain gray.

Observed colors take priority only along verified directed NWM paths with two current, compatible gauge readings and real low/flood references. Each endpoint uses its own normalized stage; the section uses their mean. Only complete interior reaches are colored. Endpoint reaches, ambiguous routing, stale observations and missing references retain modeled fallback. Colors describe relative conditions, not paddling suitability or guaranteed navigability.

Gauge markers show only usable endpoints of verified sections whose actual geometry is available. They obey the river density policy and can be toggled independently. Dataless and isolated gauges are hidden. Launches retain their original curated coordinates and verification identities; national launch coverage remains incomplete.

## Refresh and expansion

- Endpoint observations: every three hours; the browser checks freshness each minute.
- National major-river modeled snapshot: daily; visible detail flows use a 15-minute cache.
- Verified routing: bounded daily expansion across rotating seed windows, reusing committed topology and raw checkpoints.
- Static connected geometry: cached separately from changing flow values; only confirmed reach IDs are retrieved.

Automated jobs change NWM outputs only and dispatch GitHub Pages deployment explicitly. They do not replace the original production/source datasets. No national whole-network geometry download is required.

See [NWM execution and source documentation](docs/nwm/README.md), [primary-map validation](docs/nwm/primary-validation/README.md), and [original launch reconciliation](docs/nwm/launch-reconciliation.json). The scripts record incomplete coverage and source gaps rather than inventing measurements or connections.

## Credits

River geometry, modeled flow, gauge observations and routing: NOAA NWM/NWPS. Annual stage references: USGS. Launch records include owner-curated sources and OpenStreetMap contributors. Basemap: OpenFreeMap/OpenMapTiles; renderer: MapLibre. The project’s original inspiration was [Flow — Bellingham streamflow cartography](https://flows.bellingham.dev/about.html).
