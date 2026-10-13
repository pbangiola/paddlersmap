# NWM prototype

The standalone `nwm-prototype.html` uses actual NOAA NWM geometry, the project's flow colors and a separate canonical launch inventory. The production homepage and original datasets are unchanged.

```sh
.venv/bin/python -m http.server 8001 --bind 127.0.0.1
node --test web/nwm/*.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/nwm/spec_smoke.py
```

Open the prototype from the local server. Browser checks require Playwright, system Chromium and verified external HTTPS access.

NOAA's static flowline service supplies geometry, exact feature IDs and two-year recurrence anchors; `nwm/ana_anomaly` supplies latest discharge and seasonal percentiles in cfs. Modeled colors use the 10th percentile, provisional midpoint of 25th/75th percentiles, and two-year recurrence flow, clamped and interpolated through brown/blue/yellow/red. Missing or invalid references remain gray. The national overview refreshes manually after NOAA's daily cycle; bounded detail requests cache static geometry separately and expire flow values after 15 minutes. Alaska/Hawaii/PRVI have geometry but unavailable anomaly anchors.

```sh
.venv/bin/python scripts/nwm/overview.py
python3 scripts/nwm/gauge_assignments.py --topology /path/to/documented-directed-nwm.json
python3 scripts/nwm/gauge_assignments.py --observations-only
python3 scripts/nwm/launch_inventory.py --retrieve
```

Observed sections use the arithmetic mean of each endpoint's normalized stage position, on whole connected reaches strictly between the gauges. Endpoints must have compatible references, units and observations within the configurable 36-hour freshness limit. Gauge-off restores modeled colors; NOAA comparison hides all custom colors. Observations refresh independently of static assignments in the existing three-hour USGS workflow.

**Current gaps:** the repository has no verified directed NWM topology, and its NWPS import omits primary observation units. There are zero confirmed observed sections. National Overpass retrieval failed and no complete snapshot exists on main. The canonical inventory currently preserves 101 explicit curated locations with incomplete OSM coverage clearly indicated; 36 unresolved catalogue entries remain documented without invented coordinates. A failed refresh never replaces the active dataset. The manual launch workflow uploads review artifacts without committing/deploying them.

See [implementation and input contracts](spec-implementation.md), [launch reconciliation report](launch-reconciliation.json), [NOAA field metadata](service-fields.json), and [browser validation](spec-validation/results.json). Colors describe relative conditions, not navigability or safety.
