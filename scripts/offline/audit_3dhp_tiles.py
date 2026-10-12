#!/usr/bin/env python3
"""Read-only audit of existing 3DHP tile shards; standard library only.

Usage: python3 scripts/offline/audit_3dhp_tiles.py --tiles local/output/national_3dhp/tiles
"""
import argparse
import collections
import json
from pathlib import Path


def audit(directory):
    files = sorted(directory.glob("cell_*.geojson"))
    totals = collections.Counter()
    seen = {}
    examples = []
    errors = []
    for path in files:
        try:
            data = json.loads(path.read_text())
            features = data["features"]
            if data.get("type") != "FeatureCollection" or not isinstance(features, list):
                raise ValueError("not a GeoJSON FeatureCollection")
            totals["tiles"] += 1
            if not features:
                totals["empty_tiles"] += 1
            totals["raw_features"] += len(features)
            local_ids = set()
            for feature in features:
                props = feature.get("properties") or {}
                oid = props.get("OBJECTID")
                if oid is None:
                    totals["missing_objectid"] += 1
                else:
                    oid = str(oid)
                    if oid in local_ids:
                        totals["duplicate_ids_within_tile"] += 1
                    local_ids.add(oid)
                    if oid in seen:
                        totals["overlapping_ids_across_tiles"] += 1
                        if len(examples) < 10:
                            examples.append({"objectid": oid, "first_tile": seen[oid], "other_tile": path.name})
                    else:
                        seen[oid] = path.name
                geometry = feature.get("geometry")
                if not geometry or geometry.get("type") not in ("LineString", "MultiLineString"):
                    totals["missing_or_unexpected_geometry"] += 1
                totals["type:" + str(props.get("featuretypelabel"))] += 1
                totals["flowdirection:" + str(props.get("flowdirection"))] += 1
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"tile": path.name, "error": str(exc)})
    totals["unique_objectids"] = len(seen)
    totals["unreadable_tiles"] = len(errors)
    return {"directory": str(directory), "summary": dict(totals), "overlap_examples": examples, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tiles", type=Path, default=Path("local/output/national_3dhp/tiles"))
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    if not args.tiles.is_dir():
        parser.error("Tile directory does not exist: " + str(args.tiles))
    result = audit(args.tiles)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
