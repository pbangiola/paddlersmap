# National worker and NOAA-width validation — October 19, 2026

**95 unit tests passed** (33 Node + 62 Python), including empty/paginated responses, exact IDs, polygon ownership, routing budgets, failed-refresh retention, viewport caching, stale references, conflicting topology, and NOAA point/pixel width conversion.

The local all-order worker discovered one of 404 national cells, queued 25 owned waterbodies and published **Shasta Lake (2781987)**. Its static shard contains **224 actual context/routing reaches**, with **21 member reaches**. Extending its boundary context to 50 rings produced a valid modeled bracket:

- Upstream reach **7950896**.
- Downstream reach **2782765**.
- Estimated normalized position **0.44731386138897145**.
- All 21 unavailable member reach colors receive directed-distance visual estimates; underlying numerical reference fields remain unchanged.

A separate real flow-only refresh updated 224 distinct cached context IDs without requesting geometry or routing.

The browser verified Shasta's footprint and colors outside the Mississippi region, then returned to Lake Pepin and checked its existing numerical provenance, toggles, collapsed details and original launch positions. **Zero JavaScript errors; zero external request failures.** Screenshots wait for full viewport tiles to finish, avoiding an intermediate overzoomed coarse tile during the jump.

The browser asserts that both overview and live colored river layers use **4/3 CSS pixels**. NOAA's reference and seven-day anomaly source renderers were inspected and both use **1-point** symbols. Our background renderer uses the same point width and explicit 96 DPI; unit tests verify this shared mapping at every density tier.

Artifacts: [Shasta](shasta.png), [Lake Pepin](lake-pepin.png), [popup](lake-pepin-popup.png), [browser evidence](browser.json), [NOAA renderer widths](noaa-widths.json).

This is an initial national pilot, not completed coverage. Subsequent Actions runs advance committed progress and load additional footprints by viewport. Alaska lacks NOAA waterbody geometry; Hawaii and PR/USVI lack modeled anomaly references. Unsupported data remains unavailable.
