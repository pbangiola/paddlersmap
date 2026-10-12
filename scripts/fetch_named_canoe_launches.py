#!/usr/bin/env python3
"""Retrieve named canoe launches from OSM; only literal 'canoe launch' in name."""
import json,sys,time,urllib.parse,urllib.request
from pathlib import Path
S,N,W,E=24.516667,49.0,-123.066667,-66.95
ENDPOINTS=["https://overpass.private.coffee/api/interpreter","https://overpass.nchc.org.tw/api/interpreter","https://overpass-api.de/api/interpreter"]
def query(s,w,n,e):
 q=f'[out:json][timeout:90];nwr["name"~"canoe launch",i]({s},{w},{n},{e});out center tags;'
 payload=urllib.parse.urlencode({"data":q}).encode()
 for attempt in range(4):
  for url in ENDPOINTS:
   try:
    req=urllib.request.Request(url,data=payload,headers={"User-Agent":"PaddlersMap/1.0 named-launch-import"})
    with urllib.request.urlopen(req,timeout=45) as res:return json.load(res)["elements"]
   except Exception as exc:print(f"Overpass attempt {attempt+1}/4 {url}: {exc}",flush=True)
  time.sleep(10*(attempt+1))
 raise RuntimeError(f"All Overpass servers failed repeatedly for {s},{w},{n},{e}; existing inventory untouched")
def main():
 # Split into 2-degree cells to avoid one nationwide query overloading Overpass.
 unique={}
 for iy in range(13):
  s=S+iy*2;n=min(N,s+2)
  for ix in range(29):
   w=W+ix*2;e=min(E,w+2)
   if w>=E or s>=N:continue
   elements=query(s,w,n,e)
   for el in elements:unique[(el["type"],el["id"])]=el
   print(f"cell {iy+1}/13,{ix+1}/29: {len(elements)} returned, {len(unique)} unique",flush=True)
   time.sleep(1)
 features=[]
 for (kind,id),el in sorted(unique.items()):
  lat=el.get("lat",el.get("center",{}).get("lat"))
  lon=el.get("lon",el.get("center",{}).get("lon"))
  if lat is None or lon is None:continue
  tags=el.get("tags",{})
  if "canoe launch" not in tags.get("name","").lower():continue
  features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":{"id":f"osm-{kind}-{id}","osm_id":id,"osm_type":kind,"name":tags["name"],"source":"OpenStreetMap","verification":"candidate_review",**tags}})
 if not features:raise RuntimeError("Zero matching features; refusing to replace existing launch inventory")
 out=Path("data/putins_named_canoe_launches.geojson")
 out.parent.mkdir(exist_ok=True)
 out.write_text(json.dumps({"type":"FeatureCollection","metadata":{"source":"OpenStreetMap contributors","attribution":"© OpenStreetMap contributors","filter":"case-insensitive name contains canoe launch","bounds":[W,S,E,N],"count":len(features)},"features":features},ensure_ascii=False,separators=(",",":"))+"\n")
 print(f"Saved {len(features)} named canoe launches to {out}")
if __name__=="__main__":main()
