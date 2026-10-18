# NWM prototype

`nwm-prototype.html` renders NOAA's real NWM river geometry with Paddler’s Map colors and the existing curated launches. The production homepage and original datasets remain separate.

```sh
.venv/bin/python -m http.server 8001 --bind 127.0.0.1
node --test web/nwm/*.test.mjs
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
.venv/bin/python scripts/nwm/connections_smoke.py
```

Open `/nwm-prototype.html`. Browser checks require Playwright, system Chromium and verified external HTTPS access. `connections_smoke.py` checks a real observed Des Plaines reach and its popup, geometry and modeled fallback. `spec_smoke.py` checks national geometry and launch rendering.

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
