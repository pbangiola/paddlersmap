# Mississippi reservoir pass — October 19, 2026

**84 unit tests passed**: 28 Node and 56 Python. The final actual-browser check passed with **zero page errors and zero external request failures**.

The bounded all-order Mississippi scan selected 1,685 named mainstem reaches and inspected 442 candidate NOAA waterbody polygons. It identifies **10 valid footprints with 40 main-channel member reaches**, backed by **469 published routing/context reaches**. Existing geometry and raw routing caches were reused; the extended run stopped at 50 boundary rings and preserves its unresolved frontier in metadata.

**Five footprints have complete, numerically usable brackets; 20 channel reaches receive visual estimates.** Available footprints are Lake Pepin, Sugar Lake, Little Winnibigoshish Lake, and two unnamed NOAA waterbodies. Wolf Lake, Andrusia Lake, Lake Irving, Lake Bemidji and Buck Lake remain gray: their required brackets reach missing numerical references, a terminal main-channel boundary, or the bounded search depth. Extending known topology to 50 rings did not justify fabricating those missing inputs. Exact per-footprint results are in [summary.json](summary.json).

Two other candidate footprints are excluded because their authoritative polygons are invalid even without simplification: Pool 2 (120051919) and unnamed waterbody 13358122. NOAA's layer supplies no reservoir/natural-lake classification, and a footprint can represent only part of a named lake. This is a partial Mississippi waterbody inventory, not complete reservoir coverage.

## Lake Pepin validation

- Actual NOAA footprint **1874843** renders over the basemap, and its NWM channel geometry is retained.
- Upstream anchor **1875139**, downstream anchor **1878125**. The browser independently verifies the mean of their normalized modeled positions: **0.35070326608658114**. Their source update is **2026-10-19 00:50:14 UTC**.
- **11 formerly unavailable member reaches** show distance-based reservoir color estimates. Their modeled numerical scale positions remain unavailable, and no discharge/reference values are created.
- A clickable surface popup starts with details collapsed. Expanding it reveals the ID, bracket IDs, source values/timestamps, position and inference method.
- The reservoir/lake toggle hides estimates; NOAA comparison also hides them. Launch markers remain above all river and footprint layers.
- All **101 launch IDs and original point coordinates match the canonical inventory exactly**. Original `data/**` files and the canonical launch dataset are unchanged by this PR.

Artifacts: [Lake Pepin map](lake-pepin.png), [expanded surface popup](lake-pepin-popup.png), [browser evidence](browser.json), [current coverage summary](summary.json).

Reproduce with `scripts/nwm/reservoir_smoke.py` after serving the repository on port 8001. Recalculate the snapshot summary with `node scripts/nwm/reservoir_coverage.mjs`. Full method, retrieval limits and refresh instructions: [reservoirs.md](../reservoirs.md).
