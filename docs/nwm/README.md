# NWM prototype

`index.html` now renders NOAA's real NWM river geometry with Paddler’s Map colors and the existing curated launches. The older regional renderer and name-based connections page have been retired. Their URLs lead to the NWM homepage; original source datasets are preserved.

```sh
.venv/bin/python -m http.server 8001 --bind 127.0.0.1
node --test web/nwm/*.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
.venv/bin/python scripts/nwm/connections_smoke.py
```

Open `/`. The former `/nwm-prototype.html` and `/gauge-connections.html` URLs redirect here. Browser checks require Playwright, system Chromium and verified external HTTPS access. `connections_smoke.py` checks a real observed Des Plaines reach and its popup, geometry and modeled fallback. `spec_smoke.py` checks national geometry and launch rendering.

## Colors and sources

NOAA's static flowline service supplies feature IDs, geometry and two-year recurrence discharge. `nwm/ana_anomaly` supplies latest discharge and seasonal percentiles in cfs. Modeled colors interpolate through brown/blue/yellow/red using the 10th-percentile low, provisional midpoint of 25th/75th percentiles, and two-year recurrence upper. Invalid references stay gray. The major-river overview refreshes daily at 05:20 UTC; detailed geographic requests cache static geometry separately and expire flow values after 15 minutes. Modeled anomaly anchors remain unavailable for Alaska/Hawaii/PRVI.

**Observed connections now use NOAA's published routing:** `/nwps/v1/reaches/{reachId}.route.downstream[].reachId`, joined to explicit NWPS gauge `reachId` values. No nearest-neighbor or name matching is used. Routing is checkpointed and bounded; repeat a command to resume and extend the verified topology. Existing verified paths are retained and recomputed on expansion. Ambiguous paths, cycles, conflicting brackets and missing topology are withheld. Only complete interior reaches between successive gauges receive observed colors; endpoint reaches and unbracketed tributaries retain model colors.

Each endpoint uses its own `(stage-low)/(flood-low)`, clamped to [0,1]. The section color uses the arithmetic mean of these two positions, not raw stages or RGB colors. Low is NOAA's explicitly unit-qualified `lowThreshold`, or an adequate-coverage annual USGS stage minimum joined by `usgsId`. Flood is NOAA's minor flood stage with explicit stage units. Stage units come from `status.observed.primaryUnit`. Missing references, incompatible units, sentinels, future/stale readings, or a changed gauge-to-reach ID prevent observed coloring. Freshness is 36 hours; observations refresh every three hours (plus the existing gauge refresh) without rebuilding topology. The browser reloads them every 15 minutes and checks freshness every minute. Click rivers to inspect inputs, endpoint times, references and path evidence. These colors describe relative conditions, not navigability.

## Refresh and expand

```sh
# Chicago validation; no national geometry download:
python scripts/nwm/connections.py --bbox -89 41 -87 43 --seed-limit 45 --max-requests 700
# National expansion, interleaving seeds across states; resume with the same command:
python scripts/nwm/connections.py --seed-limit 180 --max-requests 1500 --max-depth 100
# Only current readings for endpoints of confirmed paths:
python scripts/nwm/connections.py --observations-only
# Major rivers only; static geometry cached separately:
.venv/bin/python scripts/nwm/overview.py
```

The routing cache is `local/output/nwm-connections/reaches/`; remove it deliberately to requery static routing. Defaults are 80 seeds, 1,000 new reach lookups, depth 100 and 600 seconds (checked between frontiers; in-flight bounded retries may finish later). Each lookup retries at most three times, using three workers. Endpoint refresh defaults to at most 500 gauges; explicitly increase `--max-gauges` (up to 5,000) when expanding beyond that coverage. Long NOAA Retry-After responses pause further requests for the run. `--states IL WI` or `--bbox west south east north` restricts seed selection. No full network is downloaded. Commands update only prototype files. Review and commit them on a feature branch; routing does not auto-publish. The observation and overview workflows update only their prototype outputs once merged, then explicitly dispatch GitHub Pages deployment (automatic token pushes do not trigger push workflows).

See [current validation and remaining gaps](connection-validation/README.md), [original implementation](spec-implementation.md), and [NOAA field metadata](service-fields.json). Coverage is explicitly partial: confirmed paths do not imply that every river has an eligible gauge bracket. National OSM launch collection also remains incomplete; the 101 curated launch positions and all verified identities are unchanged.

## Primary map and continued expansion

The active site imports only `web/nwm/map.mjs`. The old `web/app.js` and name-matched straight-line renderer were removed. No legacy Chicago courses or unqualified gauge inventory loads on the public map.

Only current, unit-compatible endpoints of confirmed paths with complete cached NWM geometry become gauge markers. Markers follow the same stream-order density policy as river lines; the gauge control hides them independently of observed river colors. Dataless, stale and isolated gauges are withheld, not assigned invented readings. Original curated launch coordinates and verification records remain intact.

`connected_geometry.py` fetches actual NOAA flowlines only for confirmed reach IDs, including neutral endpoint reaches, across CONUS/AK/HI/PRVI, and caches each reach separately. Those features merge by exact ID into the existing overview/live sources, with live modeled attributes taking priority. This enables observed paths even during an anomaly-service outage or in domains without modeled anchors, without a second duplicate line layer.

```sh
# Expand successive windows of eligible reference-bearing seed gauges:
python scripts/nwm/connections.py --seed-offset 0 --seed-limit 500 --max-requests 5000 --max-depth 300 --max-seconds 1200 --skip-observations
python scripts/nwm/connections.py --seed-offset 500 --seed-limit 500 --max-requests 5000 --max-depth 300 --max-seconds 1200 --skip-observations
python scripts/nwm/connections.py --seed-offset 1000 --seed-limit 500 --max-requests 5000 --max-depth 300 --max-seconds 1200 --skip-observations
python scripts/nwm/connections.py --observations-only --max-gauges 5000
.venv/bin/python scripts/nwm/connected_geometry.py
.venv/bin/python scripts/nwm/primary_smoke.py
```

The daily `nwm-expand.yml` job rotates across all available seed windows, allowing 2,000 new lookups per run, reusing committed topology and cached source responses. It refreshes observations and actual geometry, commits only NWM outputs, and explicitly dispatches Pages. Missing references, unknown direction and incomplete paths retain modeled fallback. This is a continuing bounded crawl, not a claim that national observed coverage is complete. See [primary-map validation](primary-validation/README.md).

During consecutive expansion passes, `--observation-cache-minutes 15` can reuse recent raw endpoint responses while preserving both their original capture time and their observation time. The default remains fresh requests.
