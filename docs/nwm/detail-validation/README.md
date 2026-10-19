# October 19 detail round validation

All **70 local unit tests passed** (20 Node, 50 Python). The final browser run (`scripts/nwm/detail_smoke.py`) passed with **zero JavaScript errors and zero external request failures**. Earlier smoke attempts caught a render-worker timing race in the test and an application popup-anchor issue when details expanded; the final run waits for rendering and confirms that expanded details and the close button remain usable.

- Snapshot: **80,718** actual NWM flowlines, including **48,509 order-6 reaches**; **55,890** have valid modeled positions. NOAA update: **2026-10-19 00:50:14 UTC**.
- Combined overview/eligible observed geometry: 82,499 features. At the tested national viewport, 6,024 rendered feature fragments included 3,091 order-6 fragments. Rendered fragments can repeat across tiles and are not unique reach counts.
- **147** previously gray reaches receive explicitly inferred colors from bracketing compatible colors on cached directed topology. Missing numerical values and actual flowline coordinates are preserved.
- All **101 launch IDs and geometries match the canonical inventory exactly**.
- Page technical statuses and river popup details start closed and can be expanded.
- NOAA comparison raster rendered with the **seven original publisher legend symbols**; custom lines/gauges hide during comparison and launches stay above rivers.
- Chicago reach **14786171**, bracketed by **DMPI2 / RVFI2**, shows observed position **0.22711538461538466**, independently calculated from its endpoint measurements. Turning observed colors off restores modeled colors with identical geometry. The popup shows the underlying numbers after expansion.

Artifacts: [national map](national.png), [NOAA comparison and legend](noaa-legend.png), [Chicago expanded popup](chicago-connected.png), [browser evidence](browser.json), [snapshot summary](summary.json).

The original `data/**` files and canonical launch inventory are unchanged. OSM provider capacity prevented new source retrieval; see [attempt reports](../launch-round2/README.md). Topology remains partial: unknown, one-sided and ambiguous gaps stay gray. These are relative-condition display colors, not a navigability assessment.
