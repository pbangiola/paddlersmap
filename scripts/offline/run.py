#!/usr/bin/env python3
"""One-command local research runner; never publishes results to the website."""
import argparse,json,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"local"/"output"
LIVE="https://raw.githubusercontent.com/pbangiola/paddlersmap/data-live/data/"
def run(script,*args):
 subprocess.run([sys.executable,str(ROOT/"scripts"/"offline"/script),*map(str,args)],check=True,cwd=ROOT)
def download(filename):
 dest=OUT/filename
 req=urllib.request.Request(LIVE+filename,headers={"User-Agent":"PaddlersMapLocalResearch/1.0"})
 with urllib.request.urlopen(req,timeout=90) as response:dest.write_bytes(response.read())
 print("Downloaded",filename)
 return dest
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("task",choices=("launches","reconcile","discover-launches","discover-lakes","serve"))
 p.add_argument("--kml",help="Optional KML watercourses file")
 p.add_argument("--watercourses",help="Optional watercourse GeoJSON; defaults to data/river_segments_3dhp_review.geojson")
 p.add_argument("--gauges",help="Optional local NOAA gauges GeoJSON")
 p.add_argument("--edges",help="Optional local NOAA graph GeoJSON")
 p.add_argument("--bbox",nargs=4,type=float,metavar=("WEST","SOUTH","EAST","NORTH"))
 p.add_argument("--snap-m",type=float,default=1000)
 p.add_argument("--port",type=int,default=8000)
 p.add_argument("--source",choices=("osm","google"),default="osm",help="Discovery provider")
 p.add_argument("--step",type=float,default=0.2,help="Discovery grid spacing in degrees; use 0.5 for a cheaper national first pass")
 p.add_argument("--max-requests",type=int,default=100,help="Maximum Google Places API searches this invocation (billing applies); raise for unattended completion")
 a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 if a.task=="serve":
  print(f"Open http://localhost:{a.port}/ in your browser; Ctrl+C stops the server",flush=True)
  subprocess.run([sys.executable,"-m","http.server",str(a.port),"--bind","127.0.0.1","--directory",str(ROOT)],check=True);return
 if a.task=="launches":
  run("filter_launches.py","--input",ROOT/"data"/"putins_consolidated.geojson","--output",OUT/"putins_named_launches.geojson")
 elif a.task=="reconcile":
  watercourses=Path(a.watercourses).expanduser().resolve() if a.watercourses else ROOT/"data"/"river_segments_3dhp_review.geojson"
  if not a.kml and not watercourses.exists():p.error(f"Missing watercourse GeoJSON: {watercourses}")
  gauges=Path(a.gauges) if a.gauges else download("noaa_gauges.geojson")
  edges=Path(a.edges) if a.edges else download("noaa_graph_edges.geojson")
  run("reconcile_gauges_watersheds.py","--gauges",gauges,"--edges",edges,* (["--kml",str(Path(a.kml).expanduser().resolve())] if a.kml else ["--watercourses",str(watercourses)]),"--out",OUT/"reconciled.geojson","--snap-m",a.snap_m)
 else:
  if not a.bbox:p.error("discovery requires --bbox WEST SOUTH EAST NORTH")
  kind="launches" if a.task=="discover-launches" else "lakes"
  run("discover_google_places.py" if a.source=="google" else "discover_osm_features.py","--bbox",*a.bbox,"--kind",kind,"--step",a.step,"--out",OUT/(kind+"_google_place_ids.geojson" if a.source=="google" else kind+"_candidates.geojson"),*(["--max-requests",a.max_requests] if a.source=="google" else []))
if __name__=="__main__":main()
