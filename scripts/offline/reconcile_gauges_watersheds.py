#!/usr/bin/env python3
"""Nearest-watercourse audit for NOAA gauges and graph edges (Shapely >=2)."""
import argparse,json,math,xml.etree.ElementTree as ET
from pathlib import Path
from shapely.geometry import LineString,Point
from shapely.ops import nearest_points
from shapely.strtree import STRtree
def read_kml(path):
 root=ET.parse(path).getroot();paths=[]
 for pm in root.iter():
  if pm.tag.split("}")[-1]!="Placemark":continue
  name=next((e.text for e in pm if e.tag.split("}")[-1]=="name"),"")
  for el in pm.iter():
   if el.tag.split("}")[-1]!="LineString":continue
   raw=next((e.text for e in el.iter() if e.tag.split("}")[-1]=="coordinates"),"") or ""
   coords=[]
   for token in raw.split():
    try:coords.append(tuple(map(float,token.split(",")[:2])))
    except ValueError:pass
   if len(coords)>1:paths.append((name,LineString(coords)))
 return paths
def meters(a,b):
 lat=math.radians((a[1]+b[1])/2)
 return math.hypot((a[0]-b[0])*111320*math.cos(lat),(a[1]-b[1])*111320)
def main():
 p=argparse.ArgumentParser();p.add_argument("--gauges",required=True);p.add_argument("--edges",required=True);p.add_argument("--kml",required=True);p.add_argument("--out",default="local/output/reconciled.geojson");p.add_argument("--snap-m",type=float,default=1000);a=p.parse_args()
 paths=read_kml(a.kml)
 if not paths:raise SystemExit("No KML LineStrings found")
 lines=[v[1] for v in paths];tree=STRtree(lines)
 def snap(xy):
  i=int(tree.nearest(Point(xy)));nearest=nearest_points(Point(xy),lines[i])[1];d=meters(xy,(nearest.x,nearest.y))
  return {"watercourse_index":i,"watercourse_name":paths[i][0],"snap_distance_m":round(d,1),"snapped_coordinates":[nearest.x,nearest.y],"match_status":"matched" if d<=a.snap_m else "review"}
 gauges=json.loads(Path(a.gauges).read_text());edges=json.loads(Path(a.edges).read_text());features=[];summary={"gauges":0,"gauges_matched":0,"edges":0,"edges_both_ends_matched":0,"edges_same_path":0}
 for f in gauges.get("features",[]):
  geom=f.get("geometry") or {}
  if geom.get("type")!="Point":continue
  r=snap(geom["coordinates"][:2]);summary["gauges"]+=1;summary["gauges_matched"]+=r["match_status"]=="matched"
  features.append({"type":"Feature","geometry":geom,"properties":{**(f.get("properties") or {}),**r,"record_type":"gauge"}})
 for f in edges.get("features",[]):
  geom=f.get("geometry") or {};coords=geom.get("coordinates") or []
  if geom.get("type")!="LineString" or len(coords)<2:continue
  start,end=snap(coords[0][:2]),snap(coords[-1][:2]);summary["edges"]+=1
  both=start["match_status"]==end["match_status"]=="matched";same=both and start["watercourse_index"]==end["watercourse_index"]
  summary["edges_both_ends_matched"]+=both;summary["edges_same_path"]+=same
  features.append({"type":"Feature","geometry":geom,"properties":{**(f.get("properties") or {}),"record_type":"gauge_edge","start_watercourse":start["watercourse_name"],"end_watercourse":end["watercourse_name"],"start_snap_m":start["snap_distance_m"],"end_snap_m":end["snap_distance_m"],"match_status":"same_path" if same else "review"}})
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps({"type":"FeatureCollection","metadata":{"summary":summary,"warning":"Nearest KML line is only a candidate; not verified hydrologic connectivity"},"features":features},indent=2)+"\n")
 print(json.dumps(summary,indent=2));print("Output:",out)
if __name__=="__main__":main()
