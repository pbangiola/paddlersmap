#!/usr/bin/env python3
"""Produce two national NOAA network worklists from persisted crawl state and graph."""
import csv
import json
from collections import defaultdict
from pathlib import Path

data=Path("data")
out=data/"network_audit"
out.mkdir(parents=True,exist_ok=True)
def read(name):
    return json.loads((data/name).read_text())
gauges=read("noaa_gauges.geojson")["features"]
edges=read("noaa_graph_edges.geojson")["features"]
state=read("noaa_graph_state.json")
known={str(f.get("properties",{}).get("noaa_lid") or "").upper():f.get("properties",{}) for f in gauges}
visited={str(x).upper() for x in state.get("visited",[])}
pending={str(x).upper() for x in state.get("pending",[])}
partners=defaultdict(set)
for f in edges:
    p=f.get("properties",{})
    a,b=(str(p.get(k) or "").strip().upper() for k in ("upstream","downstream"))
    if a and b and a!=b:
        partners[a].add(b)
        partners[b].add(a)
# "Unchecked" means not in the persistent visited set; an existing gauge
# point alone is not evidence its riverflow endpoint was checked.
unchecked=(pending|set(partners)|set(known))-visited
single={x for x,v in partners.items() if len(v)==1 and x not in visited}
def rows(ids):
    return [{"noaa_lid":x,"name":known.get(x,{}).get("name") or "",
             "partner_count":len(partners[x]),"partner_ids":";".join(sorted(partners[x])),
             "in_pending_queue":x in pending,"checked":x in visited}
            for x in sorted(ids)]
for filename,items in [("unchecked_endpoints.csv",rows(unchecked)),("single_partner_endpoints.csv",rows(single))]:
    with (out/filename).open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(items[0]) if items else ["noaa_lid","name","partner_count","partner_ids","in_pending_queue","checked"])
        writer.writeheader()
        writer.writerows(items)
summary={"gauges":len(known),"checked":len(visited),"pending":len(pending),
         "distinct_connected_endpoints":len(partners),
         "unchecked_endpoints":len(unchecked),"single_partner_endpoints":len(single),
         "definitions":{"unchecked":"not in noaa_graph_state.json visited, including queued and known gauge points",
                        "single_partner":"exactly one distinct neighbor in current directed-edge GeoJSON, ignoring direction"}}
(out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))
