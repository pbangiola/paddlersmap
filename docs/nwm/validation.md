# Chicago NOAA comparisons

Three reaches were independently queried from NOAA after retrieval. Their exact flowline paths match the cached geometry, and discharge / percentile / recurrence fields match the snapshot numerically. NOAA’s own anomaly comparison layer uses 7-day average categories, while our prototype uses latest published discharge and a different continuous palette. The colors are therefore not expected to match NOAA’s categorical colors.

| NWM ID | Waterway | Latest cfs | Low cfs | Central cfs | Upper cfs | NOAA 7-day category |
| --- | --- | --- | --- | --- | --- | --- |
| 14784419 | Des Plaines River | 143.378 | 1.947 | 3.0155 | 253.910 | Above Normal (76th - 90th) |
| 14787573 | Des Plaines River | 911.826 | 47.576 | 79.7905 | 14371.790 | Above Normal (76th - 90th) |
| 14787663 | Chicago Sanitary and Ship Canal | 750.084 | 24.572 | 40.8380 | 6279.450 | Above Normal (76th - 90th) |

NOAA source update: `2026-10-12 00:51:39 UTC`. All values use NOAA’s published cfs aliases. The anomaly’s moving-average category is retained only for comparison, never used to infer current flow colors.

The browser smoke test renders real NOAA linework, checks all 1,553 original launch geometries, verifies layer order, clicks a river and a launch, and exercises visibility switches. It uses the OS-verified HTTPS transport for external assets because Chromium lacks the cloud proxy CA; it does not disable TLS checks.

Browser screenshots:

- [Prototype with NOAA geometry and existing launches](prototype.png)
- [NOAA’s own anomaly comparison layer](noaa-comparison.png)
