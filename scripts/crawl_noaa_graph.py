#!/usr/bin/env python3
"""Resumable NWPS upstream/downstream crawler. Publishes each successful batch separately."""
import argparse
import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

API = "https://api.water.noaa.gov/nwps/v1/gauges"
DATA = Path("data")
STATE = DATA / "noaa_graph_state.json"
GAUGES = DATA / "noaa_gauges.geojson"
EDGES = DATA / "noaa_graph_edges.geojson"
AGENT = "PaddlersMap/1.0 (public NOAA NWPS API; github.com/pbangiola/paddlersmap)"


def read(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, separators=(",", ":")))
    temp.replace(path)


def get(path, attempts=5):
    url = API + "/" + path
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404, 410):
                return None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            wait = exc.headers.get("Retry-After")
            try:
                delay = min(120, float(wait)) if wait else min(60, 2 ** attempt + random.random())
            except ValueError:
                delay = min(60, 2 ** attempt + random.random())
            time.sleep(delay)
        except (TimeoutError, OSError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(60, 2 ** attempt + random.random()))


def lid(item):
    if isinstance(item, str):
        return item.strip().upper()
    if isinstance(item, dict):
        for key in ("lid", "identifier", "noaa_lid", "nwsLid", "nws_lid"):
            if item.get(key):
                return str(item[key]).strip().upper()
        for key in ("gauge", "station"):
            if isinstance(item.get(key), dict):
                return lid(item[key])
    return ""


def neighbors(data):
    """Only trust explicitly named upstream/downstream collections; never infer edges."""
    pairs = set()
    if not isinstance(data, dict):
        return pairs
    containers = [data]
    for key in ("stream", "riverflow", "riverFlow", "data"):
        if isinstance(data.get(key), dict):
            containers.append(data[key])
    for container in containers:
        for key, direction in (("upstream", "upstream"), ("upstreamGauges", "upstream"),
                               ("downstream", "downstream"), ("downstreamGauges", "downstream")):
            value = container.get(key, [])
            if isinstance(value, dict):
                value = value.get("gauges", value.get("locations", []))
            if not isinstance(value, list):
                continue
            for entry in value:
                found = lid(entry)
                if found:
                    pairs.add((found, direction))
    return pairs


def feature(meta, previous=None):
    previous = previous or {}
    if not isinstance(meta, dict):
        return previous or None
    point = meta.get("geometry")
    if isinstance(point, dict) and point.get("type") == "Point":
        xy = point.get("coordinates")
    else:
        lat = meta.get("latitude", meta.get("lat"))
        lon = meta.get("longitude", meta.get("lon"))
        if isinstance(meta.get("location"), dict):
            loc = meta["location"]
            lat = lat if lat is not None else loc.get("latitude", loc.get("lat"))
            lon = lon if lon is not None else loc.get("longitude", loc.get("lon"))
        xy = [lon, lat]
    try:
        xy = [float(xy[0]), float(xy[1])]
        if not (-180 <= xy[0] <= 180 and -90 <= xy[1] <= 90):
            raise ValueError()
    except (TypeError, ValueError, IndexError):
        return previous or None
    p = dict(previous.get("properties", {}))
    p.update({k: v for k, v in {
        "noaa_lid": lid(meta), "name": meta.get("name"), "usgs_id": meta.get("usgsId"),
        "reach_id": meta.get("reachId"), "source": "NOAA NWPS",
    }.items() if v is not None and v != ""})
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": xy}, "properties": p}


def commit(paths):
    subprocess.run(["git", "add", *map(str, paths)], check=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0
    if changed:
        subprocess.run(["git", "commit", "-m", "Checkpoint incremental NOAA gauge graph"], check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "data-live"], check=True)
        subprocess.run(["git", "push", "origin", "HEAD:data-live"], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    original = read(GAUGES, {"type": "FeatureCollection", "features": []})
    existing = {lid(f.get("properties", {})): f for f in original.get("features", [])
                if lid(f.get("properties", {}))}
    graph = read(EDGES, {"type": "FeatureCollection", "features": []})
    state = read(STATE, {})
    pending = deque(state.get("pending") or sorted(existing))
    visited = set(state.get("visited", []))
    seen = set(pending) | visited
    links = set(tuple(e["properties"][k] for k in ("upstream", "downstream"))
                for e in graph.get("features", []) if all(k in e.get("properties", {}) for k in ("upstream", "downstream")))
    processed = 0
    while pending and processed < args.batch:
        current = pending.popleft()
        if current in visited:
            continue
        try:
            metadata = get(urllib.parse.quote(current, safe=""))
            time.sleep(args.delay)
            relationship = get(urllib.parse.quote(current, safe="") + "/riverflow")
            time.sleep(args.delay)
        except (OSError, ValueError) as exc:
            print("Transient error:", current, exc, flush=True)
            pending.appendleft(current)
            break
        record = feature(metadata, existing.get(current))
        if record:
            existing[current] = record
        for other, direction in neighbors(relationship):
            if other == current:
                continue
            a, b = (other, current) if direction == "upstream" else (current, other)
            links.add((a, b))
            if other not in seen:
                pending.append(other)
                seen.add(other)
        visited.add(current)
        processed += 1
        # Persist after each station; workflow publishes after a bounded batch.
        save(STATE, {"pending": list(pending), "visited": sorted(visited)})
        save(GAUGES, {"type": "FeatureCollection", "features": list(existing.values())})
        lines = []
        for a, b in sorted(links):
            fa, fb = existing.get(a), existing.get(b)
            if not fa or not fb:
                continue
            lines.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                fa["geometry"]["coordinates"], fb["geometry"]["coordinates"]]},
                "properties": {"upstream": a, "downstream": b, "source": "NOAA NWPS riverflow"}})
        save(EDGES, {"type": "FeatureCollection", "features": lines})
        print(f"Gauge {current}: {processed}/{args.batch} processed, {len(existing)} gauges, {len(links)} relationships, {len(pending)} queued", flush=True)
    if args.publish:
        commit([STATE, GAUGES, EDGES])
    print(f"Batch finished: processed={processed}, queued={len(pending)}")


if __name__ == "__main__":
    main()
