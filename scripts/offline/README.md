# Offline research — clone, run, inspect

These commands run **on your Mac**. They do not commit data, trigger GitHub Pages, or alter the production map.

## One-time setup

```bash
git clone https://github.com/pbangiola/paddlersmap.git
cd paddlersmap
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-offline.txt
```

For an existing clone: `git pull --ff-only` from the repository directory.

## Run jobs

From the repository root:

```bash
# Filter the existing launch inventory by launch/landing/put-in/boat ramp names
python3 scripts/offline/run.py launches

# Reconcile live NOAA gauges and graph edges against your local KML
python3 scripts/offline/run.py reconcile

# Optional: use local snapshots instead of downloading NOAA files
python3 scripts/offline/run.py reconcile --gauges data/noaa_gauges.geojson --edges /path/to/noaa_graph_edges.geojson

# Small test region: greater Chicago / southern Lake Michigan
python3 scripts/offline/run.py discover-launches --bbox -88.5 41.2 -86.5 42.5
python3 scripts/offline/run.py discover-lakes --bbox -88.5 41.2 -86.5 42.5
```

Outputs are saved to `local/output/` and should be reviewed before publication. The NOAA graph and gauges are downloaded from the `data-live` branch when local paths aren't provided. Network access is required for those downloads and OSM discovery.

## Preview the map without a Pages deployment

```bash
python3 scripts/offline/run.py serve
```

Open http://localhost:8000/ . This serves the current checkout's website immediately. **Important:** the existing web application still fetches some NOAA datasets from the live GitHub branch, and does **not automatically display** `local/output/` research files. The outputs are GeoJSON files for inspection in QGIS or another GeoJSON viewer. A local research-overlay UI remains a separate follow-up task.

## Important caveats

- The reconciliation defaults to data/river_segments_3dhp_review.geojson and uses nearest watercourse line matching, not a hydrologically proven graph. Its edge `same_path` count is deliberately conservative; connected rivers can span many KML placemarks.
- OSM lake discovery currently produces **centroid points**, not waterbody polygons. It cannot establish lake inlet/outlet connectivity. Use authoritative lake polygons plus 3DHP topology for that.
- Launch name filtering is intentionally restrictive and will exclude unnamed or generically named legitimate public access points. Keep the original inventory.
- The Overpass endpoint is a community service. Query bounded areas; nationwide collection needs a staged, resumable extraction pipeline. Google Maps scraping is not part of this setup.
- This initial offline suite does not yet produce an integrated river/lake/launch graph or a verified national launch inventory.
