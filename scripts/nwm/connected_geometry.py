#!/usr/bin/env python3
"""Cache actual NOAA flowlines for confirmed paths, independently of live flow cells."""
import argparse
import concurrent.futures
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connections import write
from retrieve import get

SERVICES = ['static_nwm_flowlines', 'static_nwm_flowlines_ak', 'static_nwm_flowlines_hi', 'static_nwm_flowlines_prvi']
BASE = 'https://maps.water.noaa.gov/server/rest/services/reference/'


def retrieve(ids, cache, previous=None, services=None):
    found = {str(f['properties']['feature_id']): f for f in (previous or {}).get('features', []) if str(f['properties']['feature_id']) in ids}
    for rid in ids - found.keys():
        p = cache / (rid + '.json')
        if p.exists(): found[rid] = json.loads(p.read_text())
    missing = sorted(ids - found.keys())
    for name in (SERVICES if services is None else services):
        if not missing: break
        url = BASE + name + '/FeatureServer/0'
        meta = get(url, {})
        available = {f['name'] for f in meta.get('fields', [])}
        if not {'feature_id', 'strm_order'} <= available:
            raise ValueError('Unexpected NOAA geometry schema: ' + url)
        fields = [f for f in ['feature_id', 'name', 'strm_order', 'nwm_vers', 'rf_2_0_17c'] if f in available]
        size = min(200, meta.get('maxRecordCount', 200))
        batches = [missing[i:i+size] for i in range(0, len(missing), size)]
        def fetch(batch):
            result = get(url + '/query', {'where': 'feature_id IN (' + ','.join("'"+r+"'" for r in batch) + ')',
                'outFields': ','.join(fields), 'returnGeometry': 'true', 'outSR': 4326,
                'geometryPrecision': 6, 'maxAllowableOffset': .0001})
            if result.get('exceededTransferLimit') or not isinstance(result.get('features'), list):
                raise ValueError('Truncated or invalid NOAA geometry response')
            output = []; seen = set()
            for row in result['features']:
                a = row['attributes']; rid = str(a['feature_id']); paths = row.get('geometry', {}).get('paths')
                if rid in seen or rid not in batch or not paths: raise ValueError('Unexpected geometry ID or missing paths')
                seen.add(rid)
                output.append({'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': paths},
                    'properties': {'feature_id': rid, 'name': a.get('name'), 'order': a.get('strm_order'),
                        'version': a.get('nwm_vers'), 'flood': a.get('rf_2_0_17c'), 'geometry_source': url}})
            return output
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for rows in pool.map(fetch, batches):
                for f in rows:
                    rid = f['properties']['feature_id']; found[rid] = f; write(cache / (rid + '.json'), f)
        missing = sorted(ids - found.keys())
        print(name, len(found), 'exact-ID geometries;', len(missing), 'remaining', flush=True)
    return {'type': 'FeatureCollection', 'metadata': {'requested_reaches': len(ids), 'mapped_reaches': len(found),
        'missing_reach_ids': missing, 'built_at': datetime.now(timezone.utc).isoformat(), 'geometry_offset_degrees': .0001,
        'note': 'Actual NOAA flowlines for confirmed paths and their uncolored endpoint reaches; missing geometry is never reconstructed.'},
        'features': [found[rid] for rid in sorted(found)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assignments', type=Path, default=Path('web/nwm/gauges/assignments.json'))
    p.add_argument('--output', type=Path, default=Path('web/nwm/gauges/geometry.geojson'))
    p.add_argument('--cache', type=Path, default=Path('local/output/nwm-connected-geometry'))
    a = p.parse_args(); sections = json.loads(a.assignments.read_text())['sections']
    ids = {str(r) for s in sections for r in [*s['reach_ids'],s.get('upstream_reach'),s.get('downstream_reach')] if r is not None}
    if not ids or len(ids) > 50000 or not all(r.isdigit() for r in ids):
        raise ValueError('Expected 1–50,000 numerical NWM reach IDs')
    previous = json.loads(a.output.read_text()) if a.output.exists() else None
    data = retrieve(ids, a.cache, previous)
    if not data['features']: raise ValueError('No geometry retrieved; keeping active file')
    write(a.output, data)
    print('Saved', len(data['features']), 'connected flowlines;', len(data['metadata']['missing_reach_ids']), 'unavailable', flush=True)

if __name__ == '__main__': main()
