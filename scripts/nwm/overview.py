#!/usr/bin/env python3
"""Refresh a bounded, generalized national major-river overview; cache static parts."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from retrieve import write

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'web/nwm/overview')
    parser.add_argument('--cache',type=Path,default=ROOT/'local/output/nwm-overview')
    args=parser.parse_args()
    previous_manifest=args.output/'manifest.json'
    previous_flow=json.loads(previous_manifest.read_text()).get('flow') if previous_manifest.exists() else None
    geometries={}
    records={}
    updates=set()
    # Bounded regional cells keep the extra stream-order tier below the 25,000-reach guard.
    for west in range(-125,-66,10):
      for south in range(24,50,10):
        name=f'order6-{west}-{south}';bbox=[west,south,min(west+10,-66),min(south+10,50)]
        part=args.cache/name
        subprocess.run([sys.executable,str(ROOT/'scripts/nwm/retrieve.py'),'--config',str(ROOT/'web/nwm/services.json'),
                        '--bbox',*map(str,bbox),'--min-order','6','--geometry-offset','0.02',
                        '--batch-size','500','--output',str(part)],check=True,cwd=ROOT)
        manifest=json.loads((part/'manifest.json').read_text())
        geometry=json.loads((part/manifest['geometry']).read_text())
        flow=json.loads((part/manifest['flow']).read_text())
        for feature in geometry['features']:
            geometries[feature['properties']['feature_id']]=feature
        for record in flow['records']:
            records[record['feature_id']]=record
        updates.update(flow['noaa_update_values'])
    args.output.mkdir(parents=True,exist_ok=True)
    geometry={'type':'FeatureCollection','features':list(geometries.values())}
    geometry_name='geometry-'+hashlib.sha256(json.dumps(geometry,separators=(',',':')).encode()).hexdigest()[:16]+'.geojson'
    if not (args.output/geometry_name).exists():
        write(args.output/geometry_name,geometry)
    now=datetime.now(timezone.utc).isoformat()
    flow_name='flow-'+hashlib.sha256(now.encode()).hexdigest()[:16]+'.json'
    write(args.output/flow_name,{'records':list(records.values()),'noaa_updated_at':next(iter(updates)) if len(updates)==1 else None,
                               'noaa_update_values':sorted(updates),'retrieved_at':now})
    write(args.output/'manifest.json',{'geometry':geometry_name,'flow':flow_name,'bbox':[-125,24,-66,50],
                                     'units':'ft³/s','min_order':6,'geometry_offset':0.02,
                                     'sources':json.loads((ROOT/'web/nwm/services.json').read_text())})
    # Keep one prior snapshot for clients that fetched the old manifest during publication.
    for old in args.output.glob('flow-*.json'):
        if old.name not in {flow_name,previous_flow}:old.unlink()
    print(f'National overview: {len(geometries)} actual NWM reaches; no full-network download',flush=True)


if __name__=='__main__':
    main()
