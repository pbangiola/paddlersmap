#!/usr/bin/env python3
"""Bounded OpenStreetMap Overpass candidate discovery. Lake outputs are points, not shorelines."""
import argparse,json,urllib.parse,urllib.request
from pathlib import Path
API="https://overpass.kumi.systems/api/interpreter"
def main():
 p=argparse.ArgumentParser();p.add_argument("--bbox",nargs=4,type=float,required=True,metavar=("WEST","SOUTH","EAST","NORTH"));p.add_argument("--kind",choices=("launches","lakes"),required=True);p.add_argument("--out",required=True);p.add_argument("--endpoint",default=API);a=p.parse_args()
 w,s,e,n=a.bbox
 if not (-180<=w<e<=180 and -90<=s<n<=90):p.error("Invalid bbox")
 if (e-w)*(n-s)>5:p.error("Area too large; query smaller regions")
 bbox=f"({s},{w},{n},{e})"
 selectors=(['nwr["leisure"="slipway"]','nwr["waterway"="access_point"]','nwr["name"~"(canoe|kayak|boat).*(launch|landing|ramp)|put[ -]?in",i]'] if a.kind=="launches" else ['nwr["natural"="water"]["water"~"^(lake|pond|reservoir)$"]','nwr["landuse"="reservoir"]','nwr["name"~"(lake|pond)",i]["natural"="water"]'])
 query="[out:json][timeout:120];("+"".join(v+bbox+";" for v in selectors)+");out center tags;"
 req=urllib.request.Request(a.endpoint,data=urllib.parse.urlencode({"data":query}).encode(),headers={"User-Agent":"PaddlersMapOfflineResearch/1.0"})
 with urllib.request.urlopen(req,timeout=150) as response:obj=json.load(response)
 features=[];seen=set()
 for item in obj.get("elements",[]):
  key=(item["type"],item["id"]);xy=item.get("center",item)
  if key in seen or "lon" not in xy or "lat" not in xy:continue
  seen.add(key);tags=item.get("tags") or {}
  features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[xy["lon"],xy["lat"]]},"properties":{"name":tags.get("name",""),"source":"OpenStreetMap","osm_type":item["type"],"osm_id":item["id"],"source_url":f'https://www.openstreetmap.org/{item["type"]}/{item["id"]}',"water":tags.get("water"),"access":tags.get("access"),"leisure":tags.get("leisure"),"verification":"candidate_review"}})
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps({"type":"FeatureCollection","metadata":{"kind":a.kind,"bbox":a.bbox,"warning":"Candidate points only; not complete, verified, or connected waterbody polygons"},"features":features},indent=2)+"\n")
 print(f"{len(features)} candidates -> {out}")
if __name__=="__main__":main()
