#!/usr/bin/env python3
"""Publish a small ordered NOAA riverflow pilot from LYNI2; preserve all other data."""
import json
import urllib.request
from pathlib import Path

BASE="https://api.water.noaa.gov/nwps/v1/gauges/"
DATA=Path("data")
HEAD={"User-Agent":"PaddlersMap/1.0 (LYNI2 pilot)"}
def get(lid):
    with urllib.request.urlopen(urllib.request.Request(BASE+lid,headers=HEAD),timeout=30) as r:return json.load(r)
def read(p):
    try:return json.loads(p.read_text())
    except (OSError,ValueError):return {"type":"FeatureCollection","features":[]}
def lid(x):return str(x.get("LID") or x.get("lid") or "").upper()
def number(x):
    try:
        n=float(x)
        return n if -100<n<10000 else None
    except (ValueError,TypeError):return None
def main():
    with urllib.request.urlopen(urllib.request.Request(BASE+"LYNI2/riverflow",headers=HEAD),timeout=30) as r:flow=json.load(r)
    up=[lid(x) for x in flow.get("upstream",[])]
    down=[lid(x) for x in flow.get("downstream",[])]
    chain=list(dict.fromkeys(up+["LYNI2"]+down))
    if len(chain)<5:raise RuntimeError("NOAA riverflow ordering missing; refusing to publish")
    gauges=read(DATA/"noaa_gauges.geojson")
    byid={str(f.get("properties",{}).get("noaa_lid","")).upper():f for f in gauges["features"]}
    for station in chain:
        meta=get(station)
        lat,lon=number(meta.get("latitude")),number(meta.get("longitude"))
        if lat is None or lon is None:raise RuntimeError("Missing coordinates for "+station)
        p=dict(byid.get(station,{}).get("properties",{}))
        observed=meta.get("status",{}).get("observed",{})
        flood=number(meta.get("flood",{}).get("categories",{}).get("minor",{}).get("stage"))
        stage=number(observed.get("primary")) if observed.get("primaryUnit")=="ft" else None
        p.update({"noaa_lid":station,"name":meta.get("name"),"source":"NOAA NWPS",
                  "stage":stage,"stage_observed_at":observed.get("validTime"),
                  "flood_stage_ft":flood,"low_water_stage_ft":3.0,
                  "low_water_method":"provisional 3 ft display baseline, not measured low-water threshold"})
        byid[station]={"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":p}
    gauges["features"]=list(byid.values())
    (DATA/"noaa_gauges.geojson").write_text(json.dumps(gauges,separators=(",",":")))
    graph=read(DATA/"noaa_graph_edges.geojson")
    graph["features"]=[f for f in graph["features"] if f.get("properties",{}).get("pilot")!="LYNI2"]
    def blend(a,b,t):
        return "#"+"".join(f"{round(int(a[i:i+2],16)*(1-t)+int(b[i:i+2],16)*t):02x}" for i in (1,3,5))
    def color(p):
        h=number(p.get("stage"));f=number(p.get("flood_stage_ft"))
        if h is None or f is None or f<=3:return "#88929b"
        t=max(0,min(1,(h-3)/(f-3)))
        if t<=.25:return blend("#85512c","#0867d9",t/.25)
        if t<=.625:return blend("#0867d9","#f0cf31",(t-.25)/.375)
        return blend("#f0cf31","#cf2929",(t-.625)/.375)
    for a,b in zip(chain,chain[1:]):
        pa,pb=byid[a]["properties"],byid[b]["properties"]
        ca,cb=color(pa),color(pb)
        c=blend(ca,cb,.5) if ca!="#88929b" and cb!="#88929b" else ca if cb=="#88929b" else cb
        graph["features"].append({"type":"Feature","geometry":{"type":"LineString","coordinates":[byid[a]["geometry"]["coordinates"],byid[b]["geometry"]["coordinates"]]},
         "properties":{"upstream":a,"downstream":b,"stage_color":c,"pilot":"LYNI2","source":"NOAA NWPS ordered riverflow","geometry_note":"straight gauge-to-gauge chord; not traced waterway"}})
    (DATA/"noaa_graph_edges.geojson").write_text(json.dumps(graph,separators=(",",":")))
    print("Published",len(chain),"gauges and",len(chain)-1,"consecutive pilot segments")
if __name__=="__main__":main()
