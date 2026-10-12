#!/usr/bin/env python3
"""Download USGS 3DHP flowlines from its public ArcGIS FeatureServer.

Pagination uses OBJECTID order and checks transfer-limit flags. The source's
flowdirection=1/2 attribute is retained for downstream orientation. This is
an *unclipped* bounding-box query; expand bounds to avoid artificial outlets.
"""
import argparse
import json
import time
import random
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL='https://3dhp.nationalmap.gov/arcgis/rest/services/usgs_3dhp_all/FeatureServer/50/query'
FIELDS='OBJECTID,id3dhp,gnisidlabel,flowdirection,featuretypelabel,mainstemid,arbolatesum,hydrosequence'


def request(params, retries=10):
    """Retry transient service failures without silently accepting truncated pages."""
    query = urllib.parse.urlencode(params)
    url = URL + '?' + query
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                result = json.load(response)
            if 'error' in result:
                error = result['error']
                code = error.get('code') if isinstance(error, dict) else None
                if code in (408, 429, 500, 502, 503, 504):
                    raise urllib.error.HTTPError(url, code, str(error), None, None)
                raise RuntimeError(f'USGS service error: {error}')
            return result
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt == retries - 1:
                raise
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            try:
                delay = min(120.0, float(retry_after)) if retry_after else None
            except (TypeError, ValueError):
                delay = None
            if delay is None:
                delay = min(120.0, 2.0 ** min(attempt + 1, 7)) + random.uniform(0, 1)
            print(f'USGS HTTP {exc.code}; retry {attempt + 1}/{retries - 1} in {delay:.1f}s', flush=True)
            time.sleep(delay)
        except (OSError, ValueError) as exc:
            if attempt == retries - 1:
                raise
            delay = min(120.0, 2.0 ** min(attempt + 1, 7)) + random.uniform(0, 1)
            print(f'USGS request failed ({type(exc).__name__}); retry {attempt + 1}/{retries - 1} in {delay:.1f}s', flush=True)
            time.sleep(delay)
    raise RuntimeError('unreachable')

def download(bounds, page_size=1000, max_features=None):
    if len(bounds)!=4 or bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:
        raise ValueError('Bounds must be west,south,east,north')
    common={
        'where':'flowdirection IN (1,2)',
        'geometry':','.join(map(str,bounds)),
        'geometryType':'esriGeometryEnvelope',
        'inSR':4326,'outSR':4326,
        'spatialRel':'esriSpatialRelIntersects',
        'outFields':FIELDS,'returnGeometry':'true',
        'returnZ':'false','returnM':'false',
        'orderByFields':'OBJECTID ASC','f':'geojson'
    }
    features=[]
    offset=0
    while True:
        result=request({**common,'resultOffset':offset,'resultRecordCount':page_size})
        batch=result.get('features',[])
        if not batch:
            if result.get('exceededTransferLimit'):
                raise RuntimeError('USGS returned empty truncated page; refusing incomplete download')
            break
        features.extend(batch)
        offset+=len(batch)
        print(f'Downloaded {offset} flowlines',flush=True)
        if max_features is not None and offset>=max_features:
            raise RuntimeError('Safety feature limit reached; output not complete')
        if len(batch)<page_size and not result.get('exceededTransferLimit'):
            break
    ids=[f.get('properties',{}).get('OBJECTID') for f in features]
    if len(ids)!=len(set(ids)):
        raise RuntimeError('Duplicate OBJECTIDs across pages; refusing incomplete dataset')
    return {'type':'FeatureCollection','metadata':{
        'source':URL,'bbox':list(bounds),
        'source_filter':'flowdirection IN (1,2)',
        'note':'Spatial bbox may clip basin connectivity; inspect before publication'
    },'features':features}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bbox',type=float,nargs=4,metavar=('W','S','E','N'),
                   default=(-91.6,36.9,-87.0,42.6))
    p.add_argument('--output',type=Path,default=Path('local/usgs_3dhp_flowlines.geojson'))
    p.add_argument('--page-size',type=int,default=1000)
    p.add_argument('--max-features',type=int,default=None)
    args=p.parse_args()
    if not 1<=args.page_size<=2500:p.error('Page size must be 1..2500')
    data=download(args.bbox,args.page_size,args.max_features)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,separators=(',',':')))
    print(f'Wrote {len(data["features"])} USGS flowlines to {args.output}')


if __name__=='__main__':
    main()
