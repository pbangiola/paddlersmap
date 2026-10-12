#!/usr/bin/env python3
"""Filter an existing GeoJSON launch inventory by its *name*; retain original separately."""
import argparse,json,re
from pathlib import Path
PAT=re.compile(r"\b(?:launch(?:es)?|landing(?:s)?|put[ -]?in(?:s)?|boat\s+ramp(?:s)?)\b",re.I)
def main():
 p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 data=json.loads(Path(a.input).read_text());features=data.get("features",[])
 selected=[f for f in features if PAT.search(str((f.get("properties") or {}).get("name") or ""))]
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps({"type":"FeatureCollection","metadata":{"filter":"Name contains launch, landing, put-in, or boat ramp","input_count":len(features),"selected_count":len(selected),"warning":"A name filter excludes valid unnamed/tagged launches"},"features":selected},indent=2)+"\n")
 print(f"{len(selected)} of {len(features)} launches retained -> {out}")
if __name__=="__main__":main()
