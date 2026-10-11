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
        for key in ("lid", "LID", "identifier", "noaa_lid", "nwsLid", "nws_lid"):
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
    # Refresh both live worklists from the same checkpointed state.
    subprocess.run(["python", "app-code/scripts/national_endpoint_lists.py"], check=True)
    paths = list(paths) + [DATA / "network_audit"]
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
    parser.add_argument("--max-seconds", type=int, default=18000)
    args = parser.parse_args()
    original = read(GAUGES, {"type": "FeatureCollection", "features": []})
    existing = {lid(f.get("properties", {})): f for f in original.get("features", [])
                if lid(f.get("properties", {}))}
    graph = read(EDGES, {"type": "FeatureCollection", "features": []})
    state = read(STATE, {})
    # Earlier crawler versions could mark stations visited while discarding the
    # NOAA ordered riverflow lists. Recheck once with the proven ordered parser.
    if not state.get("ordered_riverflow_v1"):
        state["visited"] = []
        state["pending"] = []
        state["ordered_riverflow_v1"] = True
    visited = {str(x).upper() for x in state.get("visited", [])}
    # Process single-partner loose ends first, then every unchecked national gauge.
    # Keep previously queued stations first so interrupted runs resume reliably.
    partner_counts = {}
    for edge in graph.get("features", []):
        p = edge.get("properties", {})
        a, b = p.get("upstream"), p.get("downstream")
        if a and b and a != b:
            partner_counts.setdefault(a, set()).add(b)
            partner_counts.setdefault(b, set()).add(a)
    single = sorted(k for k, v in partner_counts.items() if len(v) == 1 and k not in visited)
    national = sorted((set(existing) | set(partner_counts)) - visited)
    seed = list(state.get("pending", [])) + single + national
    pending = deque(dict.fromkeys(str(x).upper() for x in seed if x and str(x).upper() not in visited))
    seen = set(pending) | visited
    links = set(tuple(e["properties"][k] for k in ("upstream", "downstream"))
                for e in graph.get("features", []) if all(k in e.get("properties", {}) for k in ("upstream", "downstream")))
    if not graph.get('features') and visited and not state.get('lid_parser_v2'):
        print('Revisiting gauges after uppercase LID parser fix', flush=True)
        pending = deque(sorted(set(existing) | set(pending) | visited))
        visited = set()
        seen = set(pending)
    processed = 0
    start = time.monotonic()
    while pending and time.monotonic() - start < args.max_seconds:
        if processed and processed % args.batch == 0 and args.publish:
            commit([STATE, GAUGES, EDGES])
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
        if not isinstance(metadata, dict) or not isinstance(relationship, dict):
            print("Unavailable station metadata/riverflow; leave for later:", current, flush=True)
            pending.append(current)
            continue
        record = feature(metadata, existing.get(current))
        if record:
            existing[current] = record
        flow = relationship if isinstance(relationship, dict) else {}
        up = [lid(v) for v in flow.get("upstream", []) if lid(v)]
        down = [lid(v) for v in flow.get("downstream", []) if lid(v)]
        for chain in (up + [current], [current] + down):
            chain = list(dict.fromkeys(chain))
            for a, b in zip(chain, chain[1:]):
                if a != b:
                    links.add((a, b))
        for other in list(reversed(up)) + down:
            if other != current and other not in seen:
                pending.append(other)
                seen.add(other)
        visited.add(current)
        processed += 1
        # Persist after each station; workflow publishes after a bounded batch.
        save(STATE, {"pending": list(pending), "visited": sorted(visited), "lid_parser_v2": True, "ordered_riverflow_v1": True})
        save(GAUGES, {"type": "FeatureCollection", "features": list(existing.values())})
        old_edges = {(f.get("properties", {}).get("upstream"), f.get("properties", {}).get("downstream")): f
                     for f in graph.get("features", [])}
        lines = []
        for a, b in sorted(links):
            fa, fb = existing.get(a), existing.get(b)
            if not fa or not fb:
                continue
            prior = old_edges.get((a, b), {})
            props = dict(prior.get("properties", {}))
            props.update({"upstream": a, "downstream": b})
            props.setdefault("segment_id", a + "_" + b)
            props.setdefault("source", "NOAA NWPS riverflow")
            lines.append({"type": "Feature", "geometry": prior.get("geometry") or {"type": "LineString", "coordinates": [
                fa["geometry"]["coordinates"], fb["geometry"]["coordinates"]]},
                "properties": props})
        save(EDGES, {"type": "FeatureCollection", "features": lines})
        print(f"Gauge {current}: {processed} processed, {len(existing)} gauges, {len(links)} relationships, {len(pending)} queued", flush=True)
    if args.publish:
        commit([STATE, GAUGES, EDGES])
    print(f"Crawl stopped: processed={processed}, queued={len(pending)}, complete={not pending}")


if __name__ == "__main__":
    main()
