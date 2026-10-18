# Primary NWM map rollout — October 18, 2026

The main site now serves the NWM map. `nwm-prototype.html` and `gauge-connections.html` redirect to it. The old regional renderer (`web/app.js`) and name-based straight-line renderer were removed. Original production/source datasets and all 101 curated launch records remain unchanged.

## Expanded actual coverage

| Measurement | This rollout |
| --- | ---: |
| Confirmed directed gauge sections | 475 |
| Connected gauges in those sections | 844 |
| Whole interior NWM reaches | 4,481 |
| Cached actual channel geometries, including neutral endpoints | 5,325 |
| Current usable observed sections | 202 |
| Interior reaches eligible for observed colors | 1,854 |
| Eligible connected gauge markers | 346 |
| Reference-bearing starting gauges attempted | 1,436 / 1,436 |
| Published topology nodes retained | 18,451 |

These are real NOAA NWPS links and exact feature IDs. At the previous deployment there were 105 confirmed sections / 1,193 interior reaches; 41 sections / 383 reaches were eligible at its recorded validation. Observed eligibility varies with current readings and references, so it is not a permanent coverage guarantee.

The three state-interleaved windows used offsets 0, 500 and 1,000, each allowing at most 5,000 new reach lookups. Earlier verified topology and raw checkpoints were reused. All **844 endpoint refreshes succeeded**. All **5,325 requested geometries were found** in NOAA’s CONUS/AK/HI/PRVI feature services, with no reconstructed channels.

The national modeled snapshot uses **2026-10-18 00:50:11 UTC** NOAA data: **32,209** major-river reaches, **22,762** with valid numerical colors. Static overview geometry is unchanged. Detailed model requests remain geographically bounded and separately cached.

## What changed on the map

- No older Chicago courses, regional approximate stream associations, same-name straight lines, or broad dataless gauge inventory is loaded.
- Markers require fresh, unit-compatible readings and real references at both ends of a verified section, with actual path geometry available. Dataless, stale, inactive and isolated gauges are withheld. Markers follow the shared river density policy.
- Actual cached connected geometry merges by feature ID into the existing overview/live sources. Live modeled attributes take priority; there is no second duplicate colored river network.
- Observed paths can render while the modeled-flow service is unavailable and in domains without modeled anomaly references. Endpoint channels remain modeled or neutral gray; observed colors are never extended beyond their valid bracket.
- Original curated launch positions and verification identities are preserved, above river/gauge layers.

## Validation

**62 unit tests passed: 17 Node + 45 Python.** Added coverage includes retired entry points, exact-ID geometry/cache reuse, truncation rejection, connected-only markers, missing/stale references, neutral endpoint channels, modeled attribute priority, and explicit observation-cache reuse preserving source timestamps.

[Primary browser validation](primary-browser.json) opens both former pages and verifies their redirects, absence of legacy requests/layers, all original launch coordinates, connected-only eligible markers, gauge/comparison controls and actual observed geometry during a deliberately unavailable modeled-flow service. A real Puerto Rico reach is also checked when eligible endpoint readings exist. See [Chicago](primary-chicago.png) and [Puerto Rico](primary-prvi.png).

[Real numeric popup validation](browser.json) checks an eligible Des Plaines reach between DMPI2 and RVFI2 and its actual inputs, normalized mean, popup provenance, unchanged live geometry and modeled fallback. [Screenshot](chicago-connected.png).

[Machine-readable coverage report](summary.json) records current eligibility, update times, geometry coverage and unfinished lookups. Regenerate it with:

```sh
node scripts/nwm/coverage.mjs docs/nwm/primary-validation/summary.json
```

## Continuing limits and refresh

This is not complete national observed coverage. The final window stopped 124 frontiers at its lookup budget; earlier windows also had bounded stops. Gauges without compatible readings and real low/flood references cannot provide observed colors. These gaps use modeled fallback, or explicit gray where model references are unavailable.

The daily expansion workflow rotates across the available reference-bearing seed windows, allowing 2,000 new lookups per run. It reuses committed topology and static caches, refreshes endpoint observations, retrieves newly needed geometry and dispatches Pages after committing only NWM outputs. Scheduled endpoint readings refresh every three hours; the major-river model snapshot refreshes daily.

An explicit `--observation-cache-minutes 15` option avoids duplicate endpoint downloads during consecutive expansion passes. It retains original source capture and observation timestamps; cached old readings never become fresh merely because they were reread. Routine scheduled observation refresh defaults to fresh requests.

National launch retrieval remains incomplete and is outside this rollout. Colors indicate relative flow conditions, not paddling suitability or guaranteed navigability.

The expanded topology revealed overlapping claims on the earlier DSPI2/DMPI2 demonstration reach 14784631. That bracket and other overlapping claims are withheld; the validation now selects a currently unambiguous Chicago-area bracket. Expanding the graph can expose ambiguity, so a previously colored section may correctly return to modeled fallback.
