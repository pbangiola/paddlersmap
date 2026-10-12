#!/usr/bin/env python3
"""Google Places (New) discovery: persist Place IDs only, not Google coordinates/content."""
import argparse,json,math,os,time,urllib.request,urllib.error
from pathlib import Path

URL="https://places.googleapis.com/v1/places:searchText"
TERMS={"launches":["boat launch","canoe launch","kayak launch","public boat ramp","paddling access"],"lakes":["lake","reservoir"]}
def request(key,query,lat,lon,radius):
 payload={"textQuery":query,"locationBias":{"circle":{"center":{"latitude":lat,"longitude":lon},"radius":radius}},"pageSize":20}
 req=urllib.request.Request(URL,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","X-Goog-Api-Key":key,"X-Goog-FieldMask":"places.id,nextPageToken"},method="POST")
 for attempt in range(4):
  try:
   with urllib.request.urlopen(req,timeout=40) as response:return json.load(response)
  except urllib.error.HTTPError as exc:
   body=exc.read().decode(errors="replace")
   if exc.code not in (429,500,502,503,504):raise RuntimeError(f"Google Places HTTP {exc.code}: {body}") from exc
   print(f"Google HTTP {exc.code}, retry {attempt+1}/4",flush=True)
  except (TimeoutError,urllib.error.URLError):
   if attempt==3:raise
  time.sleep(2**attempt)
 raise RuntimeError("Google Places retries exhausted")
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--bbox",nargs=4,type=float,required=True,metavar=("WEST","SOUTH","EAST","NORTH"))
 p.add_argument("--kind",choices=TERMS,required=True)
 p.add_argument("--out",required=True)
 p.add_argument("--step",type=float,default=.2,help="Grid spacing in degrees")
 p.add_argument("--max-requests",type=int,default=100,help="Maximum API requests per run; increase for unattended operation (billing applies)")
 a=p.parse_args()
 key=os.environ.get("GOOGLE_MAPS_API_KEY")
 if not key:p.error("Set GOOGLE_MAPS_API_KEY (Google Cloud project with billing and Places API (New) enabled)")
 w,s,e,n=a.bbox
 if not (-180<=w<e<=180 and -90<=s<n<=90 and 0<a.step<=1 and a.max_requests>0):p.error("Invalid bounds, step, or max requests")
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 checkpoint=out.with_suffix(".progress.json")
 state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {"bbox":a.bbox,"kind":a.kind,"step":a.step,"completed":[],"ids":[]}
 if state["bbox"]!=a.bbox or state["kind"]!=a.kind or state["step"]!=a.step:p.error("Existing checkpoint is for a different search; move it before restarting")
 completed=set(state["completed"]);ids=set(state["ids"]);count=0
 nx=math.ceil((e-w)/a.step);ny=math.ceil((n-s)/a.step)
 for iy in range(ny):
  for ix in range(nx):
   west=w+ix*a.step;east=min(e,west+a.step);south=s+iy*a.step;north=min(n,south+a.step)
   lat=(south+north)/2;lon=(west+east)/2
   radius=min(50000,max(1000,math.hypot((north-south)*111000,(east-west)*111000*math.cos(math.radians(lat)))/2))
   for term in TERMS[a.kind]:
    task=f"{ix}:{iy}:{term}"
    if task in completed:continue
    if count>=a.max_requests:
     remaining=nx*ny*len(TERMS[a.kind])-len(completed)
     print(f"Reached request cap ({count}); {remaining} searches remain. Rerun to resume, or use --max-requests to raise the per-run limit.",flush=True);return
    obj=request(key,term,lat,lon,radius)
    ids.update(x["id"] for x in obj.get("places",[]) if x.get("id"))
    completed.add(task);state["completed"]=sorted(completed);state["ids"]=sorted(ids)
    checkpoint.write_text(json.dumps(state,indent=2)+"\n")
    out.write_text(json.dumps({"type":"FeatureCollection","metadata":{"source":"Google Places API (New)","note":"Place IDs only; no Google place content persisted. IDs are not verified launches.","completed_requests":len(completed)},"features":[{"type":"Feature","geometry":None,"properties":{"google_place_id":pid,"verification":"candidate_review"}} for pid in sorted(ids)]},indent=2)+"\n")
    count+=1
    print(f"{len(completed)} searches complete; {len(ids)} unique Place IDs ({term})",flush=True)
    time.sleep(.15)
 print(f"Done: {len(ids)} Place IDs -> {out}")
if __name__=="__main__":main()
