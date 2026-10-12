#!/usr/bin/env python3
"""Budgeted, resumable Google Places discovery across US regions.

Runs the existing ID-only discoverer in 5-degree geographic chunks.
Each chunk has its own checkpoint, so stopping and restarting is safe.
This is a discovery pass, NOT a verified or complete national inventory.
"""
import argparse, json, math, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DISCOVER=Path(__file__).with_name("discover_google_places.py")
REGIONS={
 "lower48":(-125,24,-66,50),
 "alaska":(-170,51,-129,72),
 "hawaii":(-161,18,-154,23),
}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--regions",nargs="+",choices=REGIONS,default=["lower48","alaska","hawaii"])
 p.add_argument("--step",type=float,default=.5,help="Grid step in degrees (0.5 recommended for first pass)")
 p.add_argument("--chunk-degrees",type=float,default=5)
 p.add_argument("--max-requests",type=int,default=None,help="Optional cap on search tasks for this invocation; omit to finish all regions")
 p.add_argument("--out-dir",default=str(ROOT/"local/output/google_national"))
 a=p.parse_args()
 if (a.max_requests is not None and a.max_requests<=0) or not 0<a.step<=1 or a.chunk_degrees<=0:p.error("Invalid budget, step, or chunk size")
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 budget=a.max_requests
 for region in a.regions:
  w,s,e,n=REGIONS[region]
  nx=math.ceil((e-w)/a.chunk_degrees);ny=math.ceil((n-s)/a.chunk_degrees)
  for iy in range(ny):
   for ix in range(nx):
    if budget is not None and budget<=0:
     print("API budget exhausted. Rerun the same command to resume.",flush=True);return
    box=[round(w+ix*a.chunk_degrees,7),round(s+iy*a.chunk_degrees,7),round(min(e,w+(ix+1)*a.chunk_degrees),7),round(min(n,s+(iy+1)*a.chunk_degrees),7)]
    target=out/f"{region}_{ix:02d}_{iy:02d}_place_ids.geojson"
    checkpoint=target.with_suffix(".progress.json")
    total=math.ceil((box[2]-box[0])/a.step)*math.ceil((box[3]-box[1])/a.step)*5
    done=0
    if checkpoint.exists():
     state=json.loads(checkpoint.read_text())
     if state.get("bbox")!=box or state.get("step")!=a.step:
      p.error(f"Checkpoint configuration mismatch: {checkpoint}")
     done=len(state.get("completed",[]))
    remaining=max(0,total-done)
    if not remaining:continue
    allowance=min(budget,remaining) if budget is not None else remaining+1000
    print(f"{region} tile {ix},{iy}: {remaining} searches remaining, allowing {allowance}",flush=True)
    subprocess.run([sys.executable,str(DISCOVER),"--bbox",*map(str,box),"--kind","launches","--step",str(a.step),"--out",str(target),"--max-requests",str(allowance)],check=True)
    updated=json.loads(checkpoint.read_text())
    used=len(updated.get("completed",[]))-done
    if used<0 or used>allowance:raise RuntimeError("Unexpected checkpoint request count")
    if budget is not None:budget-=used
 # Merge the ID-only chunks into a single national index (no Google coordinates stored).
 ids=set()
 for file in sorted(out.glob("*_place_ids.geojson")):
  obj=json.loads(file.read_text())
  ids.update(f.get("properties",{}).get("google_place_id") for f in obj.get("features",[]))
 ids.discard(None)
 merged=out/"national_google_place_ids.geojson"
 merged.write_text(json.dumps({"type":"FeatureCollection","metadata":{"source":"Google Places API (New)","note":"Unique IDs only; unverified candidates, not exhaustive national coverage"},"features":[{"type":"Feature","geometry":None,"properties":{"google_place_id":pid,"verification":"candidate_review"}} for pid in sorted(ids)]},indent=2)+"\\n")
 print(f"Finished requested regions; {len(ids)} unique IDs -> {merged}",flush=True)
if __name__=="__main__":main()
