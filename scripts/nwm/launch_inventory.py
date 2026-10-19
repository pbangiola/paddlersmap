#!/usr/bin/env python3
"""Canonical launch inventory, exact-name OSM retrieval, resumable complete-only publication."""
import argparse,copy,json,math,re,time,urllib.request,urllib.parse,urllib.error
from datetime import datetime,timezone
from pathlib import Path
# US-area intersection excludes foreign points; AK west/east boxes include Aleutians.
DOMAINS={'conus':[-125,24,-66,50],'alaska-west':[-180,50,-129,72],'alaska-east':[172,50,180,72],
         'hawaii':[-179,18,-154,29],'puerto-rico-usvi':[-68.1,17.6,-64.4,18.6],
         'guam-cnmi':[144,13,146.5,21],'american-samoa':[-172,-15,-168,-10]}
PROVIDERS={'de':'https://overpass-api.de/api/interpreter','coffee':'https://overpass.private.coffee/api/interpreter'}
ENDPOINT=PROVIDERS['de']
def norm(name):return ' '.join(re.findall(r'\w+',str(name).casefold()))
def distance(a,b):return math.hypot((a[0]-b[0])*111320*math.cos(math.radians((a[1]+b[1])/2)),(a[1]-b[1])*111320)
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n');tmp.replace(path)
def feature(el,retrieved):
    tags=el.get('tags',{});name=tags.get('name','')
    if 'canoe launch' not in name.casefold():return None
    if el['type']=='node':xy=[el.get('lon'),el.get('lat')]
    else:
        center=el.get('center') or {};bounds=el.get('bounds') or {}
        if center:xy=[center.get('lon'),center.get('lat')]
        elif all(k in bounds for k in ['minlon','minlat','maxlon','maxlat']):xy=[(bounds['minlon']+bounds['maxlon'])/2,(bounds['minlat']+bounds['maxlat'])/2]
        else:xy=[None,None]
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in xy) or not (-180<=xy[0]<=180 and -90<=xy[1]<=90):raise ValueError('Matching OSM record has no representative coordinates')
    return {'type':'Feature','geometry':{'type':'Point','coordinates':xy},'properties':{'name':name,'id':f"osm-{el['type']}-{el['id']}",
        'source':'OpenStreetMap','osm_type':el['type'],'osm_id':el['id'],'tags':tags,'retrieved_at':retrieved,
        'point_method':'original node' if el['type']=='node' else 'Overpass bounding-box center',
        'original_osm_element':el,'verification':'unverified'}}
def reconcile(osm,curated,verified=(),max_m=40):
    unique={};groups=[];ambiguous=[];coordinate_changes=[]
    for f in curated+osm:
        sid=f['properties']['id']
        if sid in unique:
            unique[sid]['properties'].setdefault('stable_id_versions',[]).append(copy.deepcopy(f))
            if unique[sid]['geometry']!=f['geometry']:
                coordinate_changes.append({'id':sid,'kept_geometry':unique[sid]['geometry'],'alternate_geometry':f['geometry'],'decision':'Retain original primary coordinates; review source update'})
                unique[sid]['properties']['source_coordinate_review_required']=True
            continue
        unique[sid]=copy.deepcopy(f)
    curated_ids={f['properties']['id'] for f in curated};result=[unique[sid] for sid in unique if sid in curated_ids]
    verified=set(verified)
    for f in result:f['properties']['source_records']=[copy.deepcopy(f)]
    for sid,f in unique.items():
        if sid in curated_ids:continue
        name=norm(f['properties'].get('name',''));near=[];matches=[]
        for c in result:
            if distance(c['geometry']['coordinates'],f['geometry']['coordinates'])<=max_m:
                near.append(c)
                # Generic 'Canoe Launch' names are not enough to merge physical entrances.
                if name==norm(c['properties'].get('name','')) and name not in ('canoe launch','boat launch') and len(name)>12:matches.append(c)
        if len(matches)==1:
            c=matches[0]
            # Retain both verified identities if only the nonprimary source is verified.
            if sid in verified and c['properties']['id'] not in verified:
                ambiguous.append({'ids':[c['properties']['id'],sid],'reason':'Verified alternate identity requires explicit review'});result.append(f);continue
            c['properties'].setdefault('source_records',[copy.deepcopy(c)]).append(f)
            c['properties'].setdefault('alternate_ids',[]).append(sid);c['properties'].setdefault('alternate_names',[]).append(f['properties']['name'])
            groups.append({'primary':c['properties']['id'],'alternate':sid})
        else:
            if near:ambiguous.append({'ids':[sid]+[c['properties']['id'] for c in near],'reason':'Proximity or ambiguous name is insufficient'})
            result.append(f)
    return result,{'osm_input':len(osm),'curated_input':len(curated),'stable_unique':len(unique),'output':len(result),
        'duplicate_groups':groups,'ambiguous_groups':ambiguous,'stable_id_coordinate_changes':coordinate_changes,'preserved_curated_ids':sorted(curated_ids),'distance_threshold_m':max_m}
def publish(source,curated,output,report,legacy_count,verified=(),max_m=40,legacy_ids=None):
    if source.get('metadata',{}).get('complete') is not True:raise ValueError('Incomplete retrieval; active dataset untouched')
    coverage=source['metadata'].get('coverage',{})
    if any(not isinstance(cell,dict) or cell.get('complete') is not True for cell in coverage.values()):raise ValueError('Incomplete coverage; active dataset untouched')
    if not source.get('features'):raise ValueError('Empty national OSM inventory; active dataset untouched')
    if any('canoe launch' not in f.get('properties',{}).get('name','').casefold() for f in source['features']):raise ValueError('OSM source contains out-of-scope records')
    fs,r=reconcile(source['features'],curated,verified,max_m);r.update({'coverage':source['metadata'],'legacy_records_removed':len(set(legacy_ids)-{f['properties']['id'] for f in fs}) if legacy_ids is not None else legacy_count,
        'note':'Source coverage is not completeness of real-world launches; historic broad OSM candidates are excluded.'})
    atomic(report,r);atomic(output,{'type':'FeatureCollection','metadata':source['metadata'],'features':fs})
    return r

def fetch_cell(bbox,endpoint=ENDPOINT,attempts=3):
    w,s,e,n=bbox
    query=f'[out:json][timeout:30];area["ISO3166-1"~"^(US|PR|VI|GU|MP|AS)$"]["boundary"="administrative"]->.us;nwr["name"~"canoe launch",i](area.us)({s},{w},{n},{e});out body center geom;'
    for attempt in range(attempts):
        try:
            req=urllib.request.Request(endpoint,data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'PaddlersMap/1.0 canonical-launch-import'})
            with urllib.request.urlopen(req,timeout=45) as response:data=json.load(response)
            if data.get('remark') or not isinstance(data.get('elements'),list):raise ValueError('Partial or invalid Overpass response')
            data['_area_scope']='US|PR|VI|GU|MP|AS';data['_retrieved_at']=datetime.now(timezone.utc).isoformat();time.sleep(1);return data
        except Exception as error:
            if isinstance(error,urllib.error.HTTPError) and error.code not in (429,500,502,503,504):raise
            if attempt==attempts-1:raise
            retry=error.headers.get('Retry-After') if isinstance(error,urllib.error.HTTPError) else None
            try:delay=float(retry) if retry is not None else 2**attempt*2
            except ValueError:delay=2**attempt*2
            time.sleep(max(0,min(60,delay)))
def retrieve_cell(bbox,path,endpoint,depth=0,budget=None,accept_legacy=False):
    """Reuse valid checkpoints; subdivide timed-out geographic queries, never partial data."""
    if path.exists():
        data=json.loads(path.read_text())
        if not data.get('remark') and isinstance(data.get('elements'),list) and (data.get('_area_scope')=='US|PR|VI|GU|MP|AS' or accept_legacy and data.get('_retrieved_at') and data.get('osm3s')):return data
    if budget is not None:
        if budget['remaining']<=0 or time.monotonic()>budget['deadline']:raise ValueError('Round request/time budget exhausted; resume checkpoints later')
        budget['remaining']-=1
    try:
        data=fetch_cell(bbox,endpoint,attempts=1)
    except Exception as error:
        if isinstance(error,urllib.error.HTTPError) and error.code==429 and budget is not None:budget['remaining']=0
        # Rate limiting is not a reason to multiply requests. Resume a later round.
        if depth>=2 or isinstance(error,urllib.error.HTTPError) and error.code==429:raise
        if not (isinstance(error,TimeoutError) or isinstance(error,urllib.error.HTTPError) and error.code==504 or 'timed out' in str(error).lower()):raise
        print(path.stem, 'timed out; subdividing',bbox,flush=True)
        w,s,e,n=bbox;x=(w+e)/2;y=(s+n)/2
        children=[]
        for i,box in enumerate([[w,s,x,y],[x,s,e,y],[w,y,x,n],[x,y,e,n]]):
            children.append(retrieve_cell(box,path.with_name(path.stem+f'-{i}.json'),endpoint,depth+1,budget,accept_legacy))
        elements={(el['type'],el['id']):el for child in children for el in child['elements']}
        data={'elements':list(elements.values()),'_area_scope':'US|PR|VI|GU|MP|AS','_retrieved_at':datetime.now(timezone.utc).isoformat(),
              '_subdivision_sources':[{'retrieved_at':c.get('_retrieved_at'),'osm3s':c.get('osm3s'),'children':c.get('_subdivision_sources')} for c in children]}
    atomic(path,data)
    return data

def curated_inputs(root=Path('.')):
    curated=[]
    for name in ['regional_launches.geojson','putins.geojson']:
        curated+=json.loads((root/'data'/name).read_text())['features']
    verified=set(json.loads((root/'data/verified_launches.json').read_text()).get('verified_ids',[]))
    present={f['properties']['id'] for f in curated}
    for original in json.loads((root/'data/putins_osm_candidates.geojson').read_text())['features']:
        if original['properties']['id'] in verified and original['properties']['id'] not in present:
            f=copy.deepcopy(original);f['properties']['curation_source']='Explicit reviewed ID in data/verified_launches.json';curated.append(f);present.add(f['properties']['id'])
    return curated,sorted(verified-present)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--max-requests',type=int,default=24);p.add_argument('--max-seconds',type=int,default=600);p.add_argument('--source',type=Path);p.add_argument('--retrieve',action='store_true');p.add_argument('--provider',choices=PROVIDERS,default='de');p.add_argument('--checkpoint',type=Path,default=Path('local/output/canonical-launches'));p.add_argument('--output',type=Path,default=Path('web/nwm/launches/canonical.geojson'));p.add_argument('--report',type=Path,default=Path('docs/nwm/launch-reconciliation.json'));p.add_argument('--max-m',type=float,default=40);a=p.parse_args()
    curated,missing_verified=curated_inputs()
    if missing_verified:raise SystemExit('Reviewed identities lack original coordinates: '+', '.join(missing_verified))
    registry=json.loads(Path('data/verified_launches.json').read_text()).get('verified_ids',[])
    legacy_features=json.loads(Path('data/putins_consolidated.geojson').read_text())['features'];legacy=len(legacy_features)
    if a.retrieve:
        budget={'remaining':max(1,min(a.max_requests,200)), 'deadline':time.monotonic()+max(1,min(a.max_seconds,3600))};coverage={};elements={};failures=0;started=datetime.now(timezone.utc).isoformat()
        for domain,bbox in DOMAINS.items():
            # Subdivide large boxes into 10-degree cells; persisted raw response supports resume.
            for x in range(math.ceil((bbox[2]-bbox[0])/10)):
                for y in range(math.ceil((bbox[3]-bbox[1])/10)):
                    key=f'{domain}-{x}-{y}';path=a.checkpoint/(key+'.json')
                    b=[bbox[0]+10*x,bbox[1]+10*y,min(bbox[2],bbox[0]+10*(x+1)),min(bbox[3],bbox[1]+10*(y+1))]
                    try:
                        if failures>=2 and not path.exists():raise ValueError('Deferred after two source failures; resume later')
                        data=retrieve_cell(b,path,PROVIDERS[a.provider],budget=budget,accept_legacy=domain in ['conus','alaska-west','alaska-east','hawaii'])
                        if domain in ['puerto-rico-usvi','guam-cnmi','american-samoa'] and data.get('_area_scope')!='US|PR|VI|GU|MP|AS':data=fetch_cell(b,PROVIDERS[a.provider])
                        if data.get('remark') or not isinstance(data.get('elements'),list):raise ValueError('Incomplete checkpoint')
                        atomic(path,data);print(key, 'complete:',len(data['elements']),'source records',flush=True);coverage[key]={'complete':True,'osm_timestamp':data.get('osm3s',{}).get('timestamp_osm_base'),'retrieved_at':data.get('_retrieved_at')}
                        for el in data['elements']:elements[(el['type'],el['id'])]=(el,data.get('_retrieved_at',started))
                    except Exception as e:
                        failures+=1;print(key, 'incomplete:',str(e),flush=True);coverage[key]={'complete':False,'error':str(e)}
        complete=all(v['complete'] for v in coverage.values())
        features=[];invalid=[]
        for el,retrieved in elements.values():
            try:
                f=feature(el,retrieved)
                if f:features.append(f)
            except ValueError as error:invalid.append({'id':f"{el['type']}/{el['id']}",'reason':str(error)})
        complete=complete and not invalid
        raw={'type':'FeatureCollection','metadata':{'complete':complete,'invalid_records':invalid,'coverage':coverage,'domains':DOMAINS,'retrieved_at':started,'filter':'primary name case-insensitive literal canoe launch','attribution':'© OpenStreetMap contributors','area_scope':'US|PR|VI|GU|MP|AS administrative-area union','minor_outlying_islands':'Not comprehensively covered; records inside listed bounding boxes may be included'},'features':features}
        atomic(a.checkpoint/'source.geojson',raw)
        if not complete:
            atomic(a.checkpoint/'incomplete-report.json',raw['metadata']);raise SystemExit('Incomplete national retrieval; active inventory untouched. See checkpoint report.')
    elif a.source:raw=json.loads(a.source.read_text())
    else:raise SystemExit('Supply --retrieve or --source with a complete source snapshot')
    print(json.dumps(publish(raw,curated,a.output,a.report,legacy,registry,a.max_m,[f['properties']['id'] for f in legacy_features]),indent=2))
if __name__=='__main__':main()
