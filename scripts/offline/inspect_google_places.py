#!/usr/bin/env python3
"""Inspect Google Place IDs using Places API (New) Details.

Displays live names and coordinates in the terminal. Does not persist Google
location/name data or publish it to the MapLibre atlas. Place IDs are reusable.
Check Google Maps Platform terms before using Places content in another map.
"""
import argparse,json,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--input",required=True,help="ID-only GeoJSON from discovery")
 p.add_argument("--offset",type=int,default=0,help="Start index in sorted Place ID list")
 p.add_argument("--max-requests",type=int,default=25,help="Maximum billable Place Details calls in this invocation")
 a=p.parse_args()
 if a.offset<0 or a.max_requests<=0:p.error("offset must be nonnegative and max-requests positive")
 key=os.environ.get("GOOGLE_MAPS_API_KEY")
 if not key:p.error("Set GOOGLE_MAPS_API_KEY")
 data=json.loads(Path(a.input).read_text())
 ids=sorted({str(f.get("properties",{}).get("google_place_id","")).strip() for f in data["features"]})
 ids=[x for x in ids if x]
 print(f"Resolving IDs {a.offset+1} through {min(len(ids),a.offset+a.max_requests)} of {len(ids)}",flush=True)
 print("index\tplace_id\tlatitude\tlongitude\tname\tGoogle Maps URL",flush=True)
 for i in range(a.offset,min(len(ids),a.offset+a.max_requests)):
  pid=ids[i]
  url="https://places.googleapis.com/v1/places/"+urllib.parse.quote(pid,safe="")
  req=urllib.request.Request(url,headers={"X-Goog-Api-Key":key,"X-Goog-FieldMask":"id,displayName,location,googleMapsUri"})
  for attempt in range(4):
   try:
    with urllib.request.urlopen(req,timeout=40) as response:obj=json.load(response)
    break
   except urllib.error.HTTPError as exc:
    msg=exc.read().decode(errors="replace")
    if exc.code not in (429,500,502,503,504) or attempt==3:
     print(f"ERROR at index {i}: HTTP {exc.code}: {msg}",flush=True);raise
   except (TimeoutError,urllib.error.URLError):
    if attempt==3:raise
   time.sleep(2**attempt)
  loc=obj.get("location",{})
  name=obj.get("displayName",{}).get("text","").replace("\t"," ").replace("\n"," ")
  print(f"{i}\t{pid}\t{loc.get('latitude','')}\t{loc.get('longitude','')}\t{name}\t{obj.get('googleMapsUri','')}",flush=True)
  time.sleep(.15)
 print("Done. Output was not written to disk; Google-provided coordinates must not be silently published to a non-Google map.",flush=True)
if __name__=="__main__":main()
