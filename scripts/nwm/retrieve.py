#!/usr/bin/env python3
"""Bounded ArcGIS NWM retrieval. Field mappings must come from inspected NOAA metadata."""
import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

DEFAULT_BBOX = [-88.5, 41.2, -87.0, 42.5]


def get(url, params, attempts=4):
    for attempt in range(attempts):
        try:
            response = requests.get(url, params={"f": "json", **params}, timeout=45)
        except requests.Timeout:
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)
            continue
        if response.status_code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
            retry = response.headers.get("Retry-After", "")
            time.sleep(min(60, int(retry)) if retry.isdigit() else 2 ** attempt)
            continue
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"ArcGIS {url}: {data['error']}")
        return data
    raise RuntimeError("Service retries exhausted")


def validate_schema(service, fields):
    metadata = get(service, {})
    available = {field["name"] for field in metadata.get("fields", [])}
    missing = set(fields) - available
    if missing:
        raise ValueError(f"Unverified/missing fields on {service}: {sorted(missing)}")
    return metadata


def query(service, bbox, fields, geometry, where="1=1", offset=None, batch=200):
    spatial = {"geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope",
               "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "where": where}
    ids_response = get(service + "/query", {**spatial, "returnIdsOnly": "true"})
    ids = ids_response.get("objectIds")
    if ids is None and "objectIds" in ids_response and ids_response.get("objectIdFieldName") and not ids_response.get("exceededTransferLimit"):
        ids = []  # ArcGIS explicitly identifies an empty geographic result.
    if ids is None:
        raise RuntimeError("Service did not return object IDs; refusing an incomplete download")
    if len(ids) > 25000:
        raise ValueError("Region exceeds 25,000 reaches; use a smaller bbox")
    features = []
    # ID batches avoid offset pagination races and honor the layer record limit.
    metadata = validate_schema(service, fields)
    batch_size = min(batch, metadata.get("maxRecordCount", 2000))
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        result = get(service + "/query", {"objectIds": ",".join(map(str, batch)), "outFields": ",".join(fields),
                     "returnGeometry": str(geometry).lower(), "outSR": 4326, **({"maxAllowableOffset": offset, "geometryPrecision": 5} if offset else {})})
        if result.get("exceededTransferLimit") or len(result.get("features", [])) != len(batch):
            raise RuntimeError("Truncated ArcGIS batch; refusing to publish a partial snapshot")
        features.extend(result["features"])
        time.sleep(0.2)
    return features


def write(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, separators=(",", ":")))
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", help="NOAA ArcGIS catalog or layer URL: print metadata only")
    parser.add_argument("--config", type=Path, help="Verified service/field/unit mapping JSON")
    parser.add_argument("--min-order", type=int, default=1)
    parser.add_argument("--geometry-offset", type=float, default=0)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX)
    parser.add_argument("--output", type=Path, default=Path("web/nwm/data"))
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(get(args.inspect, {}), indent=2))
        return
    if not args.config:
        parser.error("--config is required; no unverified service field names are assumed")
    if not (1 <= args.min_order <= 12 and 1 <= args.batch_size <= 2000 and args.geometry_offset >= 0):
        parser.error("Invalid stream order, batch size, or geometry offset")
    config = json.loads(args.config.read_text())
    if not (-180 <= args.bbox[0] < args.bbox[2] <= 180 and -90 <= args.bbox[1] < args.bbox[3] <= 90):
        parser.error("Invalid bbox")
    if config["units"] not in ("m³/s", "ft³/s"):
        parser.error("Units must be verified as m³/s or ft³/s; values are not silently converted")
    args.output.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(json.dumps([config["geometry"], args.bbox, args.min_order, args.geometry_offset], sort_keys=True).encode()).hexdigest()[:16]
    geometry_file = "geometry-" + signature + ".geojson"
    g = config["geometry"]
    if not (args.output / geometry_file).exists():
        geometry_fields = [g["id"]] + [g[k] for k in ("flood", "name", "version", "order") if g.get(k)]
        features = query(g["url"], args.bbox, geometry_fields, True, where=f"strm_order >= {args.min_order}", offset=args.geometry_offset, batch=args.batch_size)
        converted = []
        for feature in features:
            paths = feature.get("geometry", {}).get("paths")
            fid = feature["attributes"].get(g["id"])
            if not paths or fid is None:
                raise ValueError("Missing NWM feature ID or flowline geometry")
            converted.append({"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": paths},
                              "properties": {"feature_id": str(fid), **{k: feature["attributes"].get(g[k]) for k in ("flood", "name", "version", "order") if g.get(k)}}})
        write(args.output / geometry_file, {"type": "FeatureCollection", "features": converted})
    geometry = json.loads((args.output / geometry_file).read_text())
    records = {f["properties"]["feature_id"]: {"feature_id": f["properties"]["feature_id"], "flood": f["properties"].get("flood")} for f in geometry["features"]}
    updates = set()
    query_cache = {}
    for section, names in [("reference", ["low", "p25", "p75", "flood"]), ("flow", ["discharge"])]:
        mapping = config[section]
        fields = [mapping["id"]] + [mapping[k] for k in names if mapping.get(k)]
        if mapping.get("updated_at"):
            fields.append(mapping["updated_at"])
        # Fetch shared anomaly fields once for percentile references and latest flow.
        other_fields = []
        for related in (config["reference"], config["flow"]):
            if related["url"] == mapping["url"]:
                other_fields.extend(value for key, value in related.items() if key != "url" and value)
        cache_key = mapping["url"]
        if cache_key not in query_cache:
            query_cache[cache_key] = query(mapping["url"], args.bbox, list(dict.fromkeys(fields + other_fields)), False, where=f"strm_order >= {args.min_order}", batch=args.batch_size)
        for feature in query_cache[cache_key]:
            attrs = feature["attributes"]
            record = records.get(str(attrs.get(mapping["id"])))
            if record is None:
                continue
            for key in names:
                if mapping.get(key):
                    record[key] = attrs.get(mapping[key])
            if mapping.get("updated_at") and attrs.get(mapping["updated_at"]) is not None:
                value = attrs[mapping["updated_at"]]
                # ArcGIS date fields are milliseconds since the Unix epoch.
                record["noaa_updated_at"] = datetime.fromtimestamp(value / 1000, timezone.utc).isoformat() if isinstance(value, (int, float)) else str(value)
                updates.add(record["noaa_updated_at"])
    for record in records.values():
        a, b = record.get("p25"), record.get("p75")
        record["average"] = (a+b)/2 if type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and 0 <= a <= b else None
    now = datetime.now(timezone.utc).isoformat()
    flow_file = "flow-" + hashlib.sha256(now.encode()).hexdigest()[:16] + ".json"
    # Multiple cycles are explicitly marked; retrieval time is never presented as NOAA time.
    write(args.output / flow_file, {"records": list(records.values()), "noaa_updated_at": next(iter(updates)) if len(updates) == 1 else None,
                                   "noaa_update_values": sorted(updates), "retrieved_at": now})
    write(args.output / "manifest.json", {"geometry": geometry_file, "flow": flow_file, "bbox": args.bbox,
                                         "units": config["units"], "sources": config, "min_order": args.min_order, "geometry_offset": args.geometry_offset})
    print(f"Saved {len(records)} regional NWM reaches to {args.output}")


if __name__ == "__main__":
    main()
