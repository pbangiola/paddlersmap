# Verified NWM connections — October 17, 2026

The NOAA NWPS reach API resolves the earlier connectivity blocker. The current prototype contains **105 confirmed directed sections and 1,193 complete interior reaches**, derived from 3,257 published topology nodes. Their endpoints span 36 states and Puerto Rico. These are actual NWM IDs and downstream edges, not geographic/name guesses.

At validation, **41 sections / 383 reaches** had two eligible, current observations and stage references. All **201 endpoint gauge requests succeeded**, but a successful response does not guarantee a usable stage, low reference, flood stage or compatible units. The remaining confirmed paths fall back to modeled colors. Eligibility changes as readings refresh; no values were invented to fill coverage.

The national modeled overview now uses NOAA's **2026-10-17 00:50:22 UTC** update: 32,209 major-river reaches, with 22,703 valid modeled colors. Its static geometry is unchanged. Detail colors still load through bounded geographic cells; Alaska/Hawaii/PRVI do not have the required modeled anomaly anchors. Observed colors can appear there only where a verified path joins actual rendered feature IDs and has eligible endpoint data.

## Evidence

- [Browser evidence and actual reach inputs](browser.json): Des Plaines reach **14784631**, between **DSPI2** and **DMPI2**. Normalized endpoint positions averaged to **0.30033333333333334**, independently checked against the rendered color input. Clicking the river displayed both gauges, references and timestamps. Gauge-off restored original modeled values and exactly the same geometry. NOAA comparison hid custom lines; launches stayed above rivers. No JavaScript errors or external failures in this check.
- [Rendered observed reach and popup](chicago-connected.png).
- [Seven-view national browser validation](national-browser.json): national, Chicago at three scales, Portland, Alaska and Hawaii; 101 unchanged launch geometries and all 14 verified identities. No JavaScript errors or external transport failures; basemap null-expression and missing-shield warnings remain recorded.
- [Coverage and current eligibility](summary.json), including uncompleted reach lookups and explicit `national_complete: false`.
- 56 unit tests: 15 Node and 41 Python, including actual captured NOAA inputs, exact routing IDs/direction, ambiguous/cyclic paths, unit/sentinel handling, correct USGS minimum join, checkpoint resume, protection of active assignments on an unbracketed refresh, changed gauge reach IDs, stale fallback and rate-limit pause.

## Remaining limits

This is expanded national sampling, not complete national observed coverage. Three bounded passes used 45 Chicago-area seeds, then 90 and 180 seeds interleaved across states. The final pass allowed 1,500 new reach lookups, retained earlier confirmed paths and resumed cached routing. 58 paths/frontiers stopped at that request budget; they did not become fabricated connections. Repeat the documented command to continue, or select a state/bounding box for focused validation. Additional gauges without real low and flood stage references still cannot supply observed colors.

Endpoint reaches are deliberately excluded because gauge locations within those reaches are not known. Multiple gauges on one reach, routing divergences, loops, incomplete paths and conflicting brackets remain uncolored by observations. Stage references must come from the same identified station and compatible units; modeled percentile discharge anchors are never used to normalize observed stage. Observations expire after 36 hours even if a refresh fails.

Launch inventory expansion is outside this update. All 101 curated launch records, all verified identities, original coordinates, production datasets and homepage remain unchanged. Changes are reviewable on a feature branch; this validation is not evidence of a production deployment.
