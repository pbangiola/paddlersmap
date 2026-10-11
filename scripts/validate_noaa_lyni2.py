#!/usr/bin/env python3
"""Small, read-only NOAA NWPS graph diagnostic starting at LYNI2.

Runs automatically in Actions when this diagnostic is updated.

Walk both directions for a bounded number of hops; save raw responses so we can
identify actual relationship fields before changing the production crawler.
"""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

BASE = "https://api.water.noaa.gov/nwps/v1/gauges/"
HEADERS = {"User-Agent": "PaddlersMap/1.0 (NOAA graph validation)", "Accept": "application/json"}


def fetch(lid, suffix=""):
    url = BASE + urllib.parse.quote(lid, safe="") + suffix
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=25) as response:
            return {"status": response.status, "url": url, "data": json.load(response)}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "url": url, "error": exc.read(1500).decode("utf-8", "replace")}
    except (OSError, ValueError) as exc:
        return {"status": None, "url": url, "error": str(exc)}


def station_id(item):
    if isinstance(item, str):
        return item.strip().upper()
    if isinstance(item, dict):
        for key in ("lid", "identifier", "noaa_lid", "nwsLid", "nws_lid"):
            if item.get(key):
                return str(item[key]).strip().upper()
        for key in ("gauge", "station"):
            if isinstance(item.get(key), dict):
                return station_id(item[key])
    return ""


def existing_parser(data):
    found = []
    if not isinstance(data, dict):
        return found
    containers = [data] + [data[k] for k in ("stream", "riverflow", "riverFlow", "data") if isinstance(data.get(k), dict)]
    for container in containers:
        for key, direction in (("upstream", "upstream"), ("upstreamGauges", "upstream"),
                               ("downstream", "downstream"), ("downstreamGauges", "downstream")):
            values = container.get(key, [])
            if isinstance(values, dict):
                values = values.get("gauges", values.get("locations", []))
            if isinstance(values, list):
                for item in values:
                    other = station_id(item)
                    if other:
                        found.append({"id": other, "direction": direction, "field": key})
    return found


def structure(value, prefix="", depth=0):
    """Compact key/type inventory; raw responses are saved separately."""
    if depth > 5:
        return []
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            path = prefix + "." + key if prefix else key
            rows.append({"path": path, "type": type(item).__name__, "length": len(item) if isinstance(item, (list, dict)) else None})
            if isinstance(item, dict):
                rows.extend(structure(item, path, depth + 1))
            elif isinstance(item, list) and item and isinstance(item[0], dict):
                rows.extend(structure(item[0], path + "[0]", depth + 1))
        return rows
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="LYNI2")
    ap.add_argument("--hops", type=int, default=6)
    ap.add_argument("--max-stations", type=int, default=30)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--output", default="noaa_lyni2_validation")
    args = ap.parse_args()
    if not (0 <= args.hops <= 20 and 1 <= args.max_stations <= 200):
        ap.error("hops must be 0..20 and max-stations 1..200")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    queue = deque([(args.seed.upper(), 0)])
    seen = {args.seed.upper()}
    stations, edges = [], set()
    while queue and len(stations) < args.max_stations:
        lid, depth = queue.popleft()
        meta = fetch(lid)
        time.sleep(args.delay)
        river = fetch(lid, "/riverflow")
        time.sleep(args.delay)
        (root / (lid + ".json")).write_text(json.dumps({"metadata": meta, "riverflow": river}, indent=2))
        parsed = existing_parser(river.get("data"))
        stations.append({"id": lid, "hop": depth, "metadata_status": meta["status"],
                         "riverflow_status": river["status"], "parser_neighbors": parsed,
                         "riverflow_structure": structure(river.get("data"))})
        print(f"{lid}: metadata={meta['status']} riverflow={river['status']} neighbors={len(parsed)}", flush=True)
        for item in parsed:
            other, direction = item["id"], item["direction"]
            if other == lid:
                continue
            edges.add((other, lid) if direction == "upstream" else (lid, other))
            if depth < args.hops and other not in seen:
                seen.add(other)
                queue.append((other, depth + 1))
    report = {"seed": args.seed.upper(), "visited": len(stations), "queued": len(queue),
              "edges": [{"upstream": a, "downstream": b} for a, b in sorted(edges)],
              "stations": stations}
    (root / "report.json").write_text(json.dumps(report, indent=2))
    print(f"Saved {root}/report.json and raw API responses; stations={len(stations)} edges={len(edges)}")
    if not edges:
        print("No explicit links found. Inspect raw riverflow JSON and report field inventory; do not assume no hydrologic connectivity.")


if __name__ == "__main__":
    main()
