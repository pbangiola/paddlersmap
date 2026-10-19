# More detail, bracketed color gaps and NOAA legend

The shared stream-order thresholds now show **6+, 5+, 4+, 3+, 2+, 1+** at zoom breaks 0, 5, 7, 9, 11, 13. This adds one tier everywhere except the closest view, which already includes every published stream order. The national snapshot uses order 6+ in 18 bounded geographic cells; each query retains the 25,000-feature guard, exact-ID joins, batch limits and separate static geometry cache. No entire national network is downloaded. If a refresh is interrupted, `overview.py --resume-minutes 30` reuses recently completed regional flows with matching service configuration and bounding boxes. NOAA’s explicit `objectIdFieldName` plus null `objectIds` means an empty cell; absent or truncated responses still fail.

`web/nwm/gaps.mjs` applies **visual inference only** after current modeled/observed colors have been calculated. It follows cached published directed reach IDs, never names or nearest geometry. Both endpoint reaches must have finite positions on the same source scale. At most 50 missing reaches are interpolated by reach count; known forks, confluences, cycles, absent geometry/topology, mixed source scales and one-sided paths stop inference. Existing actual colors remain unchanged. Cached topology is partial, so this cannot detect every uncached tributary; the method is a display estimate, not a hydrologic calculation. Missing discharge and reference fields remain missing. Popups identify inferred color, position and bracketing IDs.

Technical statuses and popup metadata start collapsed. Long method descriptions live on About. Relative-flow and inferred-color qualifications remain visible. The NOAA comparison legend uses the publisher's exact layer-0 seven-day symbols and labels (including its existing punctuation). NOAA publishes no normal-category legend entry here, so none is invented. Refresh it with:

```sh
.venv/bin/python scripts/nwm/anomaly_legend.py
```

The daily overview refresh also updates this cached legend. Its retrieval date/source are retained in `web/nwm/anomaly-legend.json`.

## OSM round

The literal primary-name `canoe launch` filter and US/territory administrative-area scope are unchanged. Timed-out cells now subdivide up to two levels, preserving every successful child checkpoint. A round defaults to at most 24 requests and 600 seconds (an in-flight request can take up to 45 additional seconds). HTTP 429 stops further requests for the round. Publication still requires complete geographic coverage and valid records; incomplete rounds never replace the canonical launch inventory. Historical US-only checkpoints can be reused for mainland/Alaska/Hawaii; territory cells require the explicit expanded area scope.

```sh
.venv/bin/python scripts/nwm/launch_inventory.py --retrieve --provider de \
  --checkpoint local/output/canonical-launches-round2 --max-requests 24 --max-seconds 600
```

The October 19 local and hosted rounds remained incomplete because the providers were unavailable/at capacity. See [OSM round reports](launch-round2/README.md); no new launches were promoted.

Only a complete source snapshot may be reconciled into the active inventory. Original curated coordinates and verification identities remain protected.

## Validation

Run `node --test web/nwm/*.test.mjs` and `.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`.

With the repository served on port 8001, `.venv/bin/python scripts/nwm/detail_smoke.py` verifies national order-6 geometry renders, original launch positions, collapsed details, NOAA's seven legend symbols, actual Chicago numerical provenance and observed/model toggling with identical geometry. Current artifacts are saved separately under `docs/nwm/detail-validation/`.
