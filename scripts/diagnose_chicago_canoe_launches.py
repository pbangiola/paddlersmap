#!/usr/bin/env python3
"""Small, non-destructive OSM name-query diagnostic for Chicago."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

# Chicago city limits are irregular; this rectangle is only a search envelope.
SOUTH, WEST, NORTH, EAST = 41.644, -87.941, 42.024, -87.524
SERVERS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
QUERY = (
    '[out:json][timeout:35];'
    f'nwr["name"~"canoe launch",i]({SOUTH},{WEST},{NORTH},{EAST});'
    'out center tags;'
)

def main():
    payload = urllib.parse.urlencode({"data": QUERY}).encode()
    for server in SERVERS:
        print(f"Querying {server}", flush=True)
        try:
            req = urllib.request.Request(
                server, data=payload,
                headers={"User-Agent": "PaddlersMap/1.0 (Chicago launch diagnostic)"},
            )
            with urllib.request.urlopen(req, timeout=50) as response:
                elements = json.load(response)["elements"]
            break
        except Exception as error:
            print(f"Server failed: {error}", flush=True)
    else:
        raise RuntimeError("All Overpass endpoints failed; no files changed")

    features = []
    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name", "")
        if "canoe launch" not in name.lower():
            continue
        center = element.get("center", element)
        lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        kind, osm_id = element["type"], element["id"]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                **tags, "id": f"osm-{kind}-{osm_id}",
                "osm_id": osm_id, "osm_type": kind,
                "source": "OpenStreetMap", "verification": "candidate_review",
            },
        })
    out = Path("data/diagnostics/chicago_named_canoe_launches.geojson")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "type": "FeatureCollection",
        "metadata": {
            "query": 'OSM name contains "canoe launch" (case-insensitive)',
            "search_bbox": [WEST, SOUTH, EAST, NORTH],
            "note": "Bounding rectangle, not clipped to Chicago city boundary",
            "count": len(features),
        },
        "features": features,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"SUCCESS: {len(features)} matches recorded in {out}", flush=True)
    for feature in features:
        print(f"  {feature['properties'].get('name')} | {feature['properties']['id']}", flush=True)

if __name__ == "__main__":
    main()
