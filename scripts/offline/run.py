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
 p.add_argument("--kml",help="KML of watercourses (required for reconcile)")
 p.add_argument("--gauges",help="Optional local NOAA gauges GeoJSON")
 p.add_argument("--edges",help="Optional local NOAA graph GeoJSON")
 p.add_argument("--bbox",nargs=4,type=float,metavar=("WEST","SOUTH","EAST","NORTH"))
 p.add_argument("--snap-m",type=float,default=1000)
 p.add_argument("--port",type=int,default=8000)
 a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 if a.task=="serve":
  print(f"Open http://localhost:{a.port}/ in your browser; Ctrl+C stops the server",flush=True)
  subprocess.run([sys.executable,"-m","http.server",str(a.port),"--bind","127.0.0.1","--directory",str(ROOT)],check=True);return
 if a.task=="launches":
  run("filter_launches.py","--input",ROOT/"data"/"putins_consolidated.geojson","--output",OUT/"putins_named_launches.geojson")
 elif a.task=="reconcile":
  if not a.kml:p.error("reconcile needs --kml /path/to/watercourses.kml")
  gauges=Path(a.gauges) if a.gauges else download("noaa_gauges.geojson")
  edges=Path(a.edges) if a.edges else download("noaa_graph_edges.geojson")
  run("reconcile_gauges_watersheds.py","--gauges",gauges,"--edges",edges,"--kml",Path(a.kml).expanduser().resolve(),"--out",OUT/"reconciled.geojson","--snap-m",a.snap_m)
 else:
  if not a.bbox:p.error("discovery requires --bbox WEST SOUTH EAST NORTH")
  kind="launches" if a.task=="discover-launches" else "lakes"
  run("discover_osm_features.py","--bbox",*a.bbox,"--kind",kind,"--out",OUT/(kind+"_candidates.geojson"))
if __name__=="__main__":main()
