#!/usr/bin/env python3
"""Resumable nationwide USGS 3DHP flowline download, sharded as GeoJSON pages.

Run: python3 scripts/offline/download_national_3dhp.py
Resume by running the same command. Data is not published or committed.
"""
import argparse,json,os,time,urllib.parse,urllib.request
from pathlib import Path
URL="https://3dhp.nationalmap.gov/arcgis/rest/services/usgs_3dhp_all/FeatureServer/50/query"
FIELDS="OBJECTID,id3dhp,gnisidlabel,flowdirection,featuretypelabel,mainstemid,arbolatesum,hydrosequence"
def fetch(params,retries=5):
 encoded=urllib.parse.urlencode(params).encode()
 for attempt in range(retries):
  try:
   req=urllib.request.Request(URL,data=encoded,headers={"User-Agent":"PaddlersMapNational3DHP/1.0","Accept":"application/json"})
   with urllib.request.urlopen(req,timeout=180) as response:data=json.load(response)
   if "error" in data:raise RuntimeError(str(data["error"]))
   return data
  except (OSError,ValueError,RuntimeError) as exc:
   if attempt==retries-1:raise
   delay=min(60,2**attempt*3);print(f"Request failed: {exc}; retrying in {delay}s",flush=True);time.sleep(delay)
def atomic_json(path,data):
 tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,separators=(",",":"))+"\n");tmp.replace(path)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--output-dir",type=Path,default=Path("local/national_3dhp/flowlines"))
 p.add_argument("--page-size",type=int,default=1000)
 p.add_argument("--max-pages",type=int,default=0,help="0 means all; otherwise stop after N pages this run")
 p.add_argument("--delay",type=float,default=0.5)
 a=p.parse_args()
 if not 1<=a.page_size<=2500:p.error("--page-size must be 1..2500")
 if a.delay<0:p.error("--delay must be nonnegative")
 out=a.output_dir;out.mkdir(parents=True,exist_ok=True)
 manifest_path=out/"manifest.json"
 if manifest_path.exists():
  state=json.loads(manifest_path.read_text())
  if state.get("source")!=URL or state.get("page_size")!=a.page_size:raise SystemExit("Existing manifest has a different source or page size")
 else:
  state={"source":URL,"page_size":a.page_size,"last_objectid":0,"pages":0,"features":0,"complete":False,"parts":[]}
 if state["complete"]:
  print("Download already marked complete; remove/rename directory to start a fresh snapshot.");return
 pages_this_run=0
 while True:
  cursor=state["last_objectid"]
  result=fetch({"where":f"OBJECTID > {cursor}","outFields":FIELDS,"returnGeometry":"true","returnZ":"false","returnM":"false","orderByFields":"OBJECTID ASC","resultRecordCount":a.page_size,"f":"geojson","outSR":4326})
  batch=result.get("features",[])
  if not batch:
   if result.get("exceededTransferLimit"):raise RuntimeError("Empty truncated page; refusing completion")
   state["complete"]=True;atomic_json(manifest_path,state);print("COMPLETE",state["features"],"flowlines in",state["pages"],"pages");break
  ids=[int(f["properties"]["OBJECTID"]) for f in batch]
  if ids!=sorted(ids) or len(set(ids))!=len(ids) or ids[0]<=cursor:raise RuntimeError("Invalid/nonmonotonic OBJECTIDs; refusing to advance")
  last=ids[-1];name=f"flowlines_{cursor+1:010d}_{last:010d}.geojson"
  atomic_json(out/name,{"type":"FeatureCollection","metadata":{"source":URL,"objectid_after":cursor,"objectid_through":last},"features":batch})
  state["last_objectid"]=last;state["pages"]+=1;state["features"]+=len(batch)
  state["parts"].append({"file":name,"features":len(batch),"last_objectid":last})
  atomic_json(manifest_path,state)
  pages_this_run+=1
  print(f"Pages {state['pages']} | features {state['features']} | last OBJECTID {last}",flush=True)
  if a.max_pages and pages_this_run>=a.max_pages:break
  time.sleep(a.delay)
if __name__=="__main__":main()
