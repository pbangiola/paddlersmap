# National geometry validation

These results record the earlier geometry-only phase. National CONUS colors have since been added; see [color-validation.md](color-validation.md).

The full contiguous-US map renders NOAA’s actual NWM flowline geometry, not just the Chicago snapshot. Western and eastern detail views and the separate Alaska, Hawaii and Puerto Rico/USVI services also rendered nonempty river imagery. Screenshots and raw results are saved in [national/](national/).

| View | Tile responses observed | Image bytes | Nontransparent line pixels | Screenshot |
| --- | ---: | ---: | ---: | --- |
| conus | 53 | 282,001 | 183,795 | [View](national/conus.png) |
| west | 45 | 230,319 | 136,993 | [View](national/west.png) |
| east | 45 | 232,087 | 140,399 | [View](national/east.png) |
| alaska | 21 | 105,008 | 70,708 | [View](national/alaska.png) |
| hawaii | 32 | 29,890 | 588 | [View](national/hawaii.png) |
| prvi | 37 | 62,150 | 21,572 | [View](national/prvi.png) |

The test waits for map movement and tile loading to finish, checks that exported NOAA PNGs contain nontransparent pixels, captures the actual browser view, and checks the geometry visibility toggle. Tile counts cover responses observed during each transition, including requests already in flight; they are not national feature counts. No national vector dataset is downloaded.

The final run had 0 unrecovered tile errors and 2 recovered timeout requests. An earlier run encountered two unrecovered timeouts; bounded retries recovered them in the final run. NOAA imagery is a live service and can be slow: the Puerto Rico/USVI transition took 51.29 seconds including retries in this validation transport. The prototype displays a notice for failed national geometry tiles, and a plain-background fallback if the basemap is unavailable.

All 20 Python tests and 4 Node tests passed. The existing regional browser smoke check passed, verifying the original 1,553 unmoved launch records, launch/river popups and toggles, and continued launch availability when the NOAA snapshot fails. That regression run observed one timed-out optional NOAA anomaly-comparison image request; regional geometry and local flow-color checks still passed.

At broad zooms the national geometry overlay shows stream order 4 and above; at zoom 7 and above it requests all stream orders. The overlay is gray, because numerical flow colors and popups remain limited to the verified Chicago snapshot. Gray national linework must not be interpreted as a new national flow-color join.

Production datasets, homepage, app script and deployment workflow remain unchanged.
