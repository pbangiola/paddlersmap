#!/usr/bin/env python3
"""Resolve Google Place IDs and match to independently mapped OSM launches.

Google coordinates/names are used transiently for matching, never written.
Only OSM coordinates and OSM attribution are saved. Unmatched IDs remain null.
Re-run periodically; completed IDs are refreshed after --refresh-days.
Requires GOOGLE_MAPS_API_KEY. OSM Overpass is a shared service: be courteous.
"""
import argparse,datetime,json,math,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

DETAILS="https://places.googleapis.com/v1/places/"
OVERPASS_SERVERS=["https://overpass.private.coffee/api/interpreter","https://overpass-api.de/api/interpreter"]
def get_json(req,tries=2,timeout=15):
 for attempt in range(tries):
  try:
   with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
  except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
   if isinstance(e,urllib.error.HTTPError) and e.code not in (429,500,502,503,504):raise
   if attempt==tries-1:raise
   time.sleep(2**attempt)
def meters(a,b,c,d):
 r=6371000;p1,p2=math.radians(a),math.radians(c)
 x=math.radians(d-b)*math.cos((p1+p2)/2);y=p2-p1
 return r*math.hypot(x,y)
def osm_near(lat,lon,radius):
 # Search only mapped water-access features; avoid treating arbitrary nearby
 # parks, roads, or marinas as confirmed launches.
 q=f"""[out:json][timeout:25];(nwr(around:{radius},{lat},{lon})["leisure"="slipway"];nwr(around:{radius},{lat},{lon})["waterway"="access_point"];nwr(around:{radius},{lat},{lon})["canoe"="put_in"];nwr(around:{radius},{lat},{lon})["sport"~"canoe|kayak"];);out center tags;"""
 data=urllib.parse.urlencode({"data":q}).encode()
 errors=[]
 for server in OVERPASS_SERVERS:
  print(f"  OSM: querying {server}",flush=True)
  try:
   req=urllib.request.Request(server,data=data,headers={"User-Agent":"PaddlersMapResearch/1.0 (OSM matching)"})
   return get_json(req,tries=1,timeout=15).get("elements",[])
  except Exception as exc:
   errors.append(f"{server}: {exc}")
 raise RuntimeError("Overpass unavailable: "+"; ".join(errors))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--input",required=True)
 p.add_argument("--out",default="local/output/google_osm_launch_matches.geojson")
 p.add_argument("--max-requests",type=int,default=None,help="Optional maximum Google details lookups per run")
 p.add_argument("--refresh-days",type=int,default=30)
 p.add_argument("--radius-m",type=int,default=250)
 p.add_argument("--pause",type=float,default=2.0,help="Seconds between Overpass requests")
 a=p.parse_args()
 if a.max_requests is not None and a.max_requests<1:p.error("max-requests must be positive")
 key=os.getenv("GOOGLE_MAPS_API_KEY")
 if not key:p.error("Set GOOGLE_MAPS_API_KEY")
 ids=sorted({f.get("properties",{}).get("google_place_id") for f in json.loads(Path(a.input).read_text())["features"]}-{None,""})
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 cache=out.with_suffix(".progress.json")
 records=json.loads(cache.read_text()) if cache.exists() else {}
 now=datetime.datetime.now(datetime.timezone.utc)
 n=0
 for i,pid in enumerate(ids):
  prior=records.get(pid,{})
  if prior.get("checked_at"):
   age=now-datetime.datetime.fromisoformat(prior["checked_at"])
   if age.total_seconds()<a.refresh_days*86400:continue
  if a.max_requests is not None and n>=a.max_requests:break
  print(f"[{i+1}/{len(ids)}] Resolving Google Place ID {pid}",flush=True)
  req=urllib.request.Request(DETAILS+urllib.parse.quote(pid,safe=""),headers={"X-Goog-Api-Key":key,"X-Goog-FieldMask":"id,location"})
  try:
   place=get_json(req);point=place.get("location",{})
   lat,lon=point["latitude"],point["longitude"]
   print("  Google: location resolved; looking for nearby OSM launch",flush=True)
   candidates=osm_near(lat,lon,a.radius_m)
   scored=[]
   for el in candidates:
    elat=el.get("lat",el.get("center",{}).get("lat"))
    elon=el.get("lon",el.get("center",{}).get("lon"))
    if elat is None or elon is None:continue
    dist=meters(lat,lon,elat,elon)
    if dist<=a.radius_m:scored.append((dist,el,elat,elon))
   scored.sort(key=lambda x:x[0])
   # A nearby OSM feature is only a possible match, not proof of identity.
   if scored:
    dist,el,elat,elon=scored[0]
    record={"checked_at":now.isoformat(),"status":"osm_candidate_review","osm_type":el["type"],"osm_id":el["id"],"osm_lat":elat,"osm_lon":elon,"distance_m":round(dist,1),"osm_name":el.get("tags",{}).get("name"),"osm_tags":el.get("tags",{})}
   else:record={"checked_at":now.isoformat(),"status":"no_osm_match"}
  except KeyboardInterrupt:
   print("Interrupted; previous results remain checkpointed.",flush=True)
   raise
  except Exception as exc:
   print(f"ERROR {i+1}/{len(ids)} {pid}: {exc}",flush=True)
   record={"checked_at":now.isoformat(),"status":"lookup_error","error":str(exc)[:200]}
  records[pid]=record;cache.write_text(json.dumps(records,indent=2)+"\n")
  features=[]
  for place_id,item in sorted(records.items()):
   valid=item.get("status")=="osm_candidate_review"
   geometry={"type":"Point","coordinates":[item["osm_lon"],item["osm_lat"]]} if valid else None
   props={"google_place_id":place_id,"verification":item.get("status"),"osm_type":item.get("osm_type"),"osm_id":item.get("osm_id"),"osm_name":item.get("osm_name"),"distance_m":item.get("distance_m"),"checked_at":item.get("checked_at")}
   features.append({"type":"Feature","geometry":geometry,"properties":props})
  out.write_text(json.dumps({"type":"FeatureCollection","metadata":{"source":"OpenStreetMap contributors","attribution":"© OpenStreetMap contributors","note":"Proximity-only OSM candidates; review before publishing. No Google coordinates retained."},"features":features},indent=2)+"\n")
  n+=1
  print(f"{i+1}/{len(ids)} {pid}: {record['status']}",flush=True)
  time.sleep(a.pause)
 print(f"Processed {n} IDs; OSM candidate file: {out}",flush=True)
if __name__=="__main__":main()
