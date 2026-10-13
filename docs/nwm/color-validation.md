# National flow-color validation

The national overview contains 32,209 actual NWM reaches and 22,400 usable color records, using NOAA source update `2026-10-13 00:50:51 UTC`. The overview was retrieved in two bounded geographic partitions. Geometry and flow files are stored separately.

| View | Rendered colored features | Result | Screenshot |
| --- | ---: | --- | --- |
| national | 3,930 | 32209 national major-river reaches · 22400 colored · NOAA update: 2026-10-13 00:50:51 UTC | [View](colors/national.png) |
| west | 5,716 | 6/6 cells · 10373 colored reaches · 0 unavailable cells · NOAA update: 2026-10-13 00:50:51 UTC | [View](colors/west.png) |
| east | 5,884 | 6/6 cells · 12149 colored reaches · 0 unavailable cells · NOAA update: 2026-10-13 00:50:51 UTC | [View](colors/east.png) |

Rendered-feature counts include MapLibre tile fragments and are not unique source-reach counts. The browser checked real NOAA geometry and numerical records, not synthetic data. Both detail views completed with zero unavailable cells. A cached western revisit made no additional feature requests. Clicking a live river displayed the feature ID, discharge, all anchors, scale position and source update.

Captured numerical popup:

```text
NWM feature ID: 23832751
Current discharge: 55.79722475 ft³/s
Low anchor: 0.289 ft³/s
Central anchor: 0.779 ft³/s
Upper anchor: 6888.68 ft³/s
Scale position: 0.2559907464643438
NOAA update: 2026-10-13 00:50:51 UTC
```

The test observed 168 successful feature/metadata responses and 6 timed-out feature requests; bounded retries recovered those requests. Cold detail loading was slow, taking minutes in this validation transport. The immediate national overview and subsequent cache reuse mitigate that delay, but live NOAA service latency remains a prototype limitation.

All 20 Python tests and 9 Node tests passed. The regional browser regression also passed for 1,553 unchanged launch geometries, a single numerical popup, launch controls and independent launch loading. Its optional NOAA anomaly-comparison raster had three timed-out image requests; custom flow-color and launch checks passed.

Alaska, Hawaii and Puerto Rico/USVI remain gray: bounded queries to the available anomaly service returned zero records for their extents, and its required low / central percentile anchors are not available there.
