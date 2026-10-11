#!/usr/bin/env python3
"""Audit and deduplicate live NOAA gauges and directed segments without deleting unique records."""
import json
from pathlib import Path

DATA=Path("data")
def load(path):
    obj=json.loads(path.read_text())
    if obj.get("type")!="FeatureCollection" or not isinstance(obj.get("features"),list):
        raise ValueError(f"Invalid GeoJSON: {path}")
    return obj
def key(f,kind):
    p=f.get("properties") or {}
    if kind=="gauges":return str(p.get("noaa_lid") or "").strip().upper()
    a=str(p.get("upstream") or "").strip().upper()
    b=str(p.get("downstream") or "").strip().upper()
    return (a,b) if a and b else None
def merge(old,new):
    """Retain all nonempty properties, prefer newer observation timestamp when present."""
    po,pn=old.get("properties") or {},new.get("properties") or {}
    to=str(po.get("stage_observed_at") or "")
    tn=str(pn.get("stage_observed_at") or "")
    preferred=new if tn>=to else old
    other=old if preferred is new else new
    props=dict(other.get("properties") or {})
    props.update({k:v for k,v in (preferred.get("properties") or {}).items() if v is not None and v!=""})
    merged=dict(preferred)
    merged["properties"]=props
    if not merged.get("geometry"):merged["geometry"]=other.get("geometry")
    return merged
def run(kind,filename):
    path=DATA/filename
    obj=load(path)
    indexed={}
    order=[]
    anonymous=[]
    duplicates=0
    for f in obj["features"]:
        k=key(f,kind)
        if not k:
            anonymous.append(f)
            continue
        if k not in indexed:
            indexed[k]=f;order.append(k)
        else:
            duplicates+=1
            indexed[k]=merge(indexed[k],f)
    result=[indexed[k] for k in order]+anonymous
    if kind=="edges":
        for f in result:
            p=f.get("properties") or {}
            k=key(f,kind)
            if k:p.setdefault("segment_id",k[0]+"_"+k[1])
    print(f"{kind}: original={len(obj['features'])} unique={len(result)} duplicates={duplicates} unkeyed_preserved={len(anonymous)}",flush=True)
    if duplicates or (kind=="edges" and any(key(f,kind) and not (f.get("properties") or {}).get("segment_id") for f in obj["features"])):
        obj["features"]=result
        path.write_text(json.dumps(obj,separators=(",",":")))
    return duplicates
if __name__=="__main__":
    run("gauges","noaa_gauges.geojson")
    run("edges","noaa_graph_edges.geojson")
