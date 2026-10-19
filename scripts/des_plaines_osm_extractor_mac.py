#!/usr/bin/env python3
"""Extract OSM map tiles within 500 m of local Des Plaines NWM GeoJSON.

Run from the repository root:
    python3 scripts/des_plaines_osm_extractor_mac.py --nwm path/to/flowlines.geojson
Optional: --max-requests 5
No retries: first error stops requests, then stitches successful CSVs.
"""
import argparse
import csv
import json
import math
import sys
import traceback
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

P = argparse.ArgumentParser()
P.add_argument("--repo", type=Path, default=Path.cwd())
P.add_argument("--nwm", type=Path)
P.add_argument("--max-requests", type=int)
P.add_argument("--buffer-m", type=float, default=500)
P.add_argument("--tile-m", type=float, default=500)
P.add_argument("--timeout", type=int, default=30)
args = P.parse_args()
repo = args.repo.expanduser().resolve()
if not (repo / ".git").exists():
    P.error("Run from the root of the cloned paddlersmap repository, or supply --repo.")
out = repo / "paddlersmap_osm" / "des_plaines_run"
raw = out / "raw_osm"
parts = out / "tile_csv"
for folder in (raw, parts):
    folder.mkdir(parents=True, exist_ok=True)
logfile = out / "osm_messages.txt"
columns = ["osm_type", "osm_id", "lat", "lon", "tags_json", "tile"]
summary = {"status": "failed", "planned_tiles": 0, "attempted_tiles": 0,
           "completed_tiles": 0, "unique_objects": 0, "canoe_tagged_objects": 0}

def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with logfile.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def fetch(url):
    log("GET " + url)
    request = urllib.request.Request(url, headers={"User-Agent": "PaddlersMap-Research/0.1 (OSM corridor research)", "Accept": "application/xml"})
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            log(f"HTTP {response.status} {response.reason}")
            for k, v in response.headers.items():
                log(f"HEADER {k}: {v}")
            data = response.read()
            log(f"BODY bytes: {len(data)}")
            return data
    except urllib.error.HTTPError as exc:
        log(f"HTTP ERROR {exc.code}: {exc.reason}")
        for k, v in exc.headers.items():
            log(f"ERROR HEADER {k}: {v}")
        body = exc.read()
        log("ERROR BODY: " + body.decode("utf-8", errors="replace")[:20000])
        raise

def load_lines():
    if args.nwm:
        path = args.nwm if args.nwm.is_absolute() else repo / args.nwm
        candidates = [path]
    else:
        candidates = sorted(repo.rglob("*.geojson"))
        candidates = [p for p in candidates if "nwm" in str(p).lower() or "flowline" in str(p).lower()]
    for path in candidates:
        if "paddlersmap_osm" in path.parts or ".git" in path.parts:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            features = data.get("features", [])
            segments = []
            for f in features:
                props = f.get("properties") or {}
                name = next((str(v) for k,v in props.items() if k.lower() in ("gnis_name", "name", "river_name", "river")), "")
                if name.strip().casefold() != "des plaines river":
                    continue
                g = f.get("geometry") or {}
                lines = [g["coordinates"]] if g.get("type") == "LineString" else g.get("coordinates", []) if g.get("type") == "MultiLineString" else []
                for line in lines:
                    segments.extend(zip(line, line[1:]))
            if segments:
                log(f"NWM: {path} — {len(segments)} segments")
                return segments
            if args.nwm:
                raise ValueError(f"No named Des Plaines River LineStrings in {path}")
        except Exception as exc:
            if args.nwm:
                raise
            log(f"SKIP {path}: {exc}")
    raise FileNotFoundError("No suitable named NWM GeoJSON found. Pass --nwm relative/path.geojson. Vector tiles are not GeoJSON.")

def point_segment_m(p, a, b):
    lat = math.radians(p[1])
    sx = 111320 * math.cos(lat)
    sy = 111320
    px,py = p[0]*sx,p[1]*sy
    ax,ay = a[0]*sx,a[1]*sy
    bx,by = b[0]*sx,b[1]*sy
    dx,dy = bx-ax,by-ay
    t = max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
    return math.hypot(px-ax-t*dx,py-ay-t*dy)

def plan_tiles(segments):
    coords = [p for ab in segments for p in ab]
    lowlat,highlat = min(p[1] for p in coords),max(p[1] for p in coords)
    lowlon,highlon = min(p[0] for p in coords),max(p[0] for p in coords)
    latstep = args.tile_m / 111320
    lonstep = args.tile_m / (111320*math.cos(math.radians((lowlat+highlat)/2)))
    latpad = args.buffer_m / 111320
    lonpad = args.buffer_m / (111320*math.cos(math.radians((lowlat+highlat)/2)))
    tiles=[]
    i=0
    while lowlat-latpad+i*latstep < highlat+latpad:
        s=lowlat-latpad+i*latstep
        j=0
        while lowlon-lonpad+j*lonstep < highlon+lonpad:
            w=lowlon-lonpad+j*lonstep
            center=(w+lonstep/2,s+latstep/2)
            if min(point_segment_m(center,a,b) for a,b in segments) <= args.buffer_m + args.tile_m/math.sqrt(2):
                tiles.append((w,s,w+lonstep,s+latstep))
            j+=1
        i+=1
    return tiles

def stitch():
    seen={}
    files=sorted(parts.glob("tile_*.csv"))
    for file in files:
        with file.open(newline="",encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen[(row["osm_type"],row["osm_id"])]=row
    allfile=out/"des_plaines_all_objects.csv"
    canoefile=out/"des_plaines_canoe_tagged.csv"
    with allfile.open("w",newline="",encoding="utf-8") as f1, canoefile.open("w",newline="",encoding="utf-8") as f2:
        allwriter=csv.DictWriter(f1,fieldnames=columns)
        canoewriter=csv.DictWriter(f2,fieldnames=columns)
        allwriter.writeheader()
        canoewriter.writeheader()
        count=0
        for row in seen.values():
            allwriter.writerow(row)
            if "canoe" in json.loads(row["tags_json"]):
                canoewriter.writerow(row)
                count+=1
    summary["unique_objects"]=len(seen)
    summary["canoe_tagged_objects"]=count
    log(f"STITCH: {len(files)} CSVs, {len(seen)} objects, {count} canoe-tagged")
    return files

def main():
    if list(parts.glob("tile_*.csv")):
        raise RuntimeError("Existing tile CSVs found; move or rename des_plaines_run before a new extraction.")
    segments=load_lines()
    tiles=plan_tiles(segments)
    summary["planned_tiles"]=len(tiles)
    if args.max_requests is not None:
        tiles=tiles[:args.max_requests]
    log(f"PLAN: {summary['planned_tiles']} corridor tiles; this run {len(tiles)}")
    for index,(w,s,e,n) in enumerate(tiles,1):
        summary["attempted_tiles"]=index
        url=f"https://api.openstreetmap.org/api/0.6/map?bbox={w:.8f},{s:.8f},{e:.8f},{n:.8f}"
        data=fetch(url)
        root=ET.fromstring(data)
        if root.tag != "osm":
            raise ValueError("OSM response did not contain <osm> root")
        rows=[]
        for el in root:
            if el.tag not in ("node","way","relation"):
                continue
            tags={t.get("k"):t.get("v") for t in el.findall("tag")}
            rows.append({"osm_type":el.tag,"osm_id":el.get("id",""),
                         "lat":el.get("lat",""),"lon":el.get("lon",""),
                         "tags_json":json.dumps(tags,ensure_ascii=False),"tile":index})
        xmlpath=raw/f"tile_{index:05d}.osm"
        csvpath=parts/f"tile_{index:05d}.csv"
        xmlpath.write_bytes(data)
        with csvpath.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        summary["completed_tiles"]=index
        log(f"TILE {index}/{len(tiles)}: {len(rows)} objects; saved {xmlpath.name} and {csvpath.name}")
    summary["status"]="complete"

log("=== START NEW EXTRACTION RUN ===")
failure=None
try:
    main()
except Exception as exc:
    failure=exc
    summary["error"]=f"{type(exc).__name__}: {exc}"
    log("STOPPING ON FIRST FAILURE: "+summary["error"])
    log(traceback.format_exc())
finally:
    try:
        stitch()
    except Exception as exc:
        log(f"STITCH ERROR: {type(exc).__name__}: {exc}")
        if failure is None:
            failure=exc
            summary["status"]="failed"
    summary["timestamp_utc"]=datetime.now(timezone.utc).isoformat()
    (out/"run_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    log("RUN SUMMARY "+json.dumps(summary))
if failure:
    raise SystemExit(1)
