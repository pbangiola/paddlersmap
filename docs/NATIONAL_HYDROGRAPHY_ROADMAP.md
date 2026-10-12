# National Hydrography Engine and Paddler's Map: delivery plan

Status: planning baseline (2026-10-12). Branch: `feature/national-hydrography-roadmap`.

## Product contract
- Preserve national source hydrography; **never filter acquisition by paddling suitability**.
- Distinguish source coverage from successful processing; distinguish geographic proximity from hydrologic connectivity.
- Default map: verified/documented recreational waterways. Explore mode: all available hydrography, with an explicit *not verified navigable* label.
- Full source dataset lives outside Pages and Git history; publish derived static vector tiles and compact indexes.
- Local-first: commands work on macOS and support partial rebuilds without waiting for Pages.

## Architecture
1. **Source layer:** immutable 3DHP GeoJSON cell shards + source URL, query, retrieval time, count, pagination, status; NWPS and USGS gauges; launch candidates and verified accesses; elevation, waterbodies, WBD when available.
2. **Normalized layer:** SQLite/GeoPackage feature catalog keyed by `(source, source_version, feature_id)`; geometry, identifiers, name, type, direction, mainstem, source cell(s), provenance. Deduplicate overlap without discarding source tile provenance.
3. **Network layer:** explicit directed edges/nodes with validated endpoint connectivity and cross-cell joins. Do not assume `hydrosequence` alone proves connectivity. Track uncertain topology and waterbody connectors.
4. **Enrichment layer:** gauge/launch crosswalks with distance, name agreement, candidate alternatives, review status, observation timestamps and units.
5. **Publishing layer:** generalization by zoom and hydrologic importance plus independently documented paddling priority. Vector tiles / PMTiles and small API-free static manifests.
6. **Applications:** Paddler's Map; watershed tracing; data QA; research exports; education; later routing and conditions.

## Work breakdown and acceptance criteria

### P0 — Preserve and audit current national acquisition
- [ ] Capture run configuration, source endpoint, server version/date, field definitions, and bounding regions in manifest.
- [ ] Add independent `returnCountOnly` verification for each tile (compare count with returned distinct OBJECTIDs; log mismatch and retry).
- [ ] Audit `flowdirection IN (1,2)` against full feature-type/value distribution; define intentional exclusions; no silent omissions.
- [ ] Verify `resultOffset` pagination behavior under large cells; if inconsistent, use OBJECTID-keyset or ID-batch retrieval.
- [ ] Add atomic per-cell completion metadata, errors and retry log; never mark failed/partial cell complete.
- [ ] Add a non-invasive validator for already-downloaded tiles; do not force redownload or rewrite source shards.
- [ ] Add separate Alaska, Hawaii, territories geographic jobs; define ocean/land empty-cell expectations.
- [ ] Add `status` command summarizing attempted, complete, empty, failed, counts, gauge coverage and disk usage.
**Gate:** every requested cell complete/empty/failed explicitly; no silent truncation; restarts preserve previous completed cells.

### P1 — Build national feature store
- [ ] Ingest existing `local/output/national_3dhp/tiles/cell_*.geojson` incrementally.
- [ ] Normalize stable source IDs, geometries, CRS, attributes, source version and per-cell provenance.
- [ ] Deduplicate by source feature ID; detect conflicting geometries/attributes and quarantine for review.
- [ ] Maintain spatial index; streaming/batched writes to bound RAM.
- [ ] Export reproducible regional GeoJSON/GeoPackage and stats.
- [ ] Add tests: overlap dedup, empty cell, malformed feature, conflicting duplicate, restart/idempotence.
**Gate:** ingest rerun does not change feature count; all source features traceable to original tile.

### P2 — Network reconstruction
- [ ] Confirm documented 3DHP flow-network derivatives exist and evaluate using them instead of reinventing topology.
- [ ] Establish network nodes/edges, orientation and source identifier crosswalks.
- [ ] Join across cell boundaries and handle waterbody/canal/surface connectors.
- [ ] Trace upstream/downstream with cycle detection and incomplete-coverage flags.
- [ ] Validate on known rivers across multiple tiles; publish disconnected components and dangling ends report.
- [ ] Evaluate `arbolatesum`, `mainstemid`, `hydrosequence` definitions, units, and missingness.
**Gate:** tested river traces across cell boundaries; unknown connectivity is never presented as confirmed.

### P3 — Gauge and access reconciliation
- [ ] Retain NOAA NWPS and USGS identifiers, original point, timestamp, datum and provenance.
- [ ] Match within locally completed coverage only; statuses `awaiting_geometry`, `candidate`, `matched`, `review`, `unmatched`.
- [ ] Record distance and alternative candidate flowlines; score name agreement separately from proximity.
- [ ] Associate gauges with directed network; reject kilometer-scale snaps.
- [ ] Reconcile launch candidates; separately verify public access, parking, restrictions, legal status and launch type.
- [ ] Evaluate whether Google Places IDs can be lawfully used with non-Google map displays; don't publish Google-derived geometry without licensing review.
**Gate:** reproducible sample audit; no inferred navigability from a flowline alone.

### P4 — Display/publishing
- [ ] Define zoom-dependent classes from network significance, not individual segment length.
- [ ] Add independently sourced `documented_paddling` designation with provenance and review date.
- [ ] Implement default Paddling mode and opt-in Explore All Waterways mode.
- [ ] Prototype vector tiles / PMTiles; measure payload, render time, memory and tile counts.
- [ ] Click river to highlight connected named/mainstem portions; show gauge/access and uncertainty.
- [ ] Local preview command; build static artifacts without Pages.
- [ ] Accessible legends and disclaimer: mapped water does not establish navigability, safety or legal access.
**Gate:** mobile/desktop performance budget measured on representative dense/sparse areas; no whole-country GeoJSON in browser.

### P5 — Research products and advanced applications
- [ ] Watershed upstream/downstream explorer; export subgraph and provenance.
- [ ] Launch-to-launch distance routing after connectivity/access QA.
- [ ] Gauge-to-network interpolation experiment with calibration, uncertainty and hydrologic limitations.
- [ ] Gradient/flow/obstruction evidence pipeline; never auto-label a route safe.
- [ ] Access-gap inventory and water-trail directory.
- [ ] Public reproducible QA report and feedback mechanism for agency users.
**Gate:** research outputs have documented assumptions, data lineage and validation cases.

## Proposed CLI contract
```bash
python3 scripts/offline/download_match_3dhp.py --max-cells 10
python3 scripts/offline/audit_3dhp_tiles.py --tiles local/output/national_3dhp/tiles
# Future:
python3 scripts/offline/run.py hydro-status
python3 scripts/offline/run.py hydro-ingest --source local/output/national_3dhp/tiles
python3 scripts/offline/run.py hydro-validate
python3 scripts/offline/run.py hydro-export --bbox -125 40 -123 42
python3 scripts/offline/run.py hydro-preview --bbox -125 40 -123 42
```
Never overwrite raw tiles on a schema upgrade; output schema version and migration path.

## Data-quality measurements
- Source coverage by geographic region and source version.
- Requested/complete/failed/empty cell counts; independent server counts.
- Unique vs raw features; conflicting duplicates.
- Geometry invalidity, missing identifiers, dangling network endpoints, cycles.
- Gauges by status and snap-distance distribution; audited false-match rate.
- Verified vs candidate access points.
- Map tile sizes and interactive performance.

## Sequencing and release criteria
- **Release 0 — Audit:** source tile audit and manifests, no UI change.
- **Release 1 — Network prototype:** one multi-cell river trace, reproducible feature store.
- **Release 2 — Public map:** static regional tiles, paddling/explore toggle, provenance and caveats.
- **Release 3 — National map:** all supported regions, scalable tiles, QA dashboards.
- **Release 4 — Route intelligence:** validated access and connectivity; conservative condition display.

## Agency outreach / questions
USGS 3DHP support: 3DHP@usgs.gov; Steve Aichele (Hydrography Management and Planning Lead): saichele@usgs.gov; Susan Buto (Hydrography Data Acquisition Lead): sbuto@usgs.gov. Ask about recommended bulk download, national network derivatives, source completeness, identifier stability, field definitions and public QA contributions.
NOAA Office of Water Prediction / National Water Center: ask for the appropriate NWPS/National Water Model technical liaison, gauge-to-reach crosswalks, flow predictions and use restrictions. Do not assume an individual contact or partnership.
USGS Water Data for the Nation support: https://waterdata.usgs.gov/questions-comments/; ask about monitoring-site crosswalks, streamflow APIs and datum interpretation.

References:
- https://www.usgs.gov/3d-hydrography-program/connect
- https://www.usgs.gov/media/videos/april-2026-usgs-hydrography-community-call
- https://water.noaa.gov/about/owp
- https://water.noaa.gov/about/nwc
- https://waterdata.usgs.gov/questions-comments/

## Out of scope until validated
Real-time paddling safety ratings, automatic legal access determinations, universal depth prediction, and guaranteed passable routing.
