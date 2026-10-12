#!/usr/bin/env python3
"""Incrementally download 3DHP tiles, match local NOAA gauges, and checkpoint progress.

Uses existing scripts/download_3dhp_flowlines.py; no GitHub Pages build.
"""
import argparse,json,math,subprocess,sys,urllib.request
from pathlib import Path
from shapely.geometry import Point,shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from download_3dhp_flowlines import download
LIVE="https://raw.githubusercontent.com/pbangiola/paddlersmap/data-live/data/noaa_gauges.geojson"
def meters(a,b):
 lat=math.radians((a[1]+b[1])/2)
 return math.hypot((a[0]-b[0])*111320*math.cos(lat),(a[1]-b[1])*111320)
def atomic_json(path,obj):
 tmp=path.with_suffix(".tmp");tmp.write_text(json.dumps(obj,separators=(",",":"))+"\n");tmp.replace(path)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--bbox",type=float,nargs=4,default=(-125,24,-66,50),metavar=("W","S","E","N"))
 p.add_argument("--cell-deg",type=float,default=1.0)
 p.add_argument("--snap-m",type=float,default=1000)
 p.add_argument("--page-size",type=int,default=1000)
 p.add_argument("--max-cells",type=int,default=0,help="0 means all cells")
 p.add_argument("--out-dir",type=Path,default=ROOT/"local"/"output"/"national_3dhp")
 p.add_argument("--gauges",type=Path,default=None)
 a=p.parse_args()
 if a.cell_deg<=0 or a.snap_m<=0:p.error("cell-deg and snap-m must be positive")
 w,s,e,n=a.bbox
 if not (-180<=w<e<=180 and -90<=s<n<=90):p.error("Invalid bbox")
 out=a.out_dir.resolve();tiles=out/"tiles";matches=out/"matches";tiles.mkdir(parents=True,exist_ok=True);matches.mkdir(parents=True,exist_ok=True)
 gaugefile=out/"noaa_gauges.geojson"
 if a.gauges:gaugefile=a.gauges.resolve()
 elif not gaugefile.exists():
  req=urllib.request.Request(LIVE,headers={"User-Agent":"PaddlersMapOffline/1.0"})
  with urllib.request.urlopen(req,timeout=120) as response:gaugefile.write_bytes(response.read())
 gauges=json.loads(gaugefile.read_text()).get("features",[])
 cells=[];x=w
 while x<e-1e-9:
  y=s
  while y<n-1e-9:
   cells.append((round(x,8),round(y,8),round(min(x+a.cell_deg,e),8),round(min(y+a.cell_deg,n),8)))
   y+=a.cell_deg
  x+=a.cell_deg
 print(f"{len(cells)} cells; {len(gauges)} NOAA gauges; output {out}",flush=True)
 completed=0
 for idx,(cw,cs,ce,cn) in enumerate(cells):
  tile=tiles/f"cell_{idx:05d}.geojson";match=matches/f"cell_{idx:05d}.geojson"
  if match.exists():continue
  if a.max_cells and completed>=a.max_cells:break
  # Download with margin to reduce artificial border mismatches. Overlapping
  # flowlines are intentionally kept in per-cell files for later deduplication.
  if not tile.exists():
   print(f"Downloading {idx+1}/{len(cells)} {cw,cs,ce,cn}",flush=True)
   result=download((max(-180,cw-.02),max(-90,cs-.02),min(180,ce+.02),min(90,cn+.02)),page_size=a.page_size)
   atomic_json(tile,result)
  data=json.loads(tile.read_text());lines=[]
  for f in data.get("features",[]):
   geom=f.get("geometry")
   if not geom:continue
   g=shape(geom)
   if g.geom_type=="LineString":lines.append((g,f.get("properties") or {}))
   elif g.geom_type=="MultiLineString":lines.extend((line,f.get("properties") or {}) for line in g.geoms)
  tree=STRtree([v[0] for v in lines]) if lines else None
  found=[]
  for f in gauges:
   geom=f.get("geometry") or {}
   if geom.get("type")!="Point":continue
   lon,lat=geom["coordinates"][:2]
   if not (cw<=lon<ce and cs<=lat<cn):continue
   props=dict(f.get("properties") or {})
   if tree is None:props.update({"match_status":"no_flowlines_in_cell","coverage_cell":idx})
   else:
    i=int(tree.nearest(Point(lon,lat)));line,lp=lines[i];near=nearest_points(Point(lon,lat),line)[1]
    dist=meters((lon,lat),(near.x,near.y))
    props.update({"match_status":"matched" if dist<=a.snap_m else "review","snap_distance_m":round(dist,1),"snapped_coordinates":[near.x,near.y],"watercourse_objectid":lp.get("OBJECTID"),"watercourse_mainstemid":lp.get("mainstemid"),"watercourse_name":lp.get("gnisidlabel"),"coverage_cell":idx})
   found.append({"type":"Feature","geometry":geom,"properties":props})
  atomic_json(match,{"type":"FeatureCollection","metadata":{"cell_bbox":[cw,cs,ce,cn],"flowline_count":len(lines),"gauge_count":len(found)},"features":found})
  completed+=1
  print(f"Completed cell {idx+1}/{len(cells)}: {len(lines)} flowlines, {len(found)} gauges",flush=True)
 # Combine completed match shards; explicitly report incomplete coverage.
 all_matches=[];done=0
 for idx in range(len(cells)):
  file=matches/f"cell_{idx:05d}.geojson"
  if file.exists():done+=1;all_matches.extend(json.loads(file.read_text()).get("features",[]))
 atomic_json(out/"gauges_reconciled.geojson",{"type":"FeatureCollection","metadata":{"completed_cells":done,"total_cells":len(cells),"complete":done==len(cells),"note":"Gauge matching per cell; no cross-cell topology or edge matching yet"},"features":all_matches})
 print(f"Checkpoint: {done}/{len(cells)} cells, {len(all_matches)} gauge matches",flush=True)
if __name__=="__main__":main()
