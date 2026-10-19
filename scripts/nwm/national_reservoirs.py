#!/usr/bin/env python3
"""Resumable all-order NOAA waterbody discovery, interpolation inputs and flow refresh."""
import argparse,json,math,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
import requests
try:
 from . import reservoirs as core,connected_geometry,connections
 from .retrieve import get,validate_schema
except ImportError:
 import reservoirs as core,connected_geometry,connections
 from retrieve import get,validate_schema
BASE='https://maps.water.noaa.gov/server/rest/services/reference/'
DOMAINS={
 'conus':{'bbox':[-125,24,-66,50],'flow':'static_nwm_flowlines','water':'static_nwm_waterbodies','modeled':True},
 'hawaii':{'bbox':[-161,18,-154,23],'flow':'static_nwm_flowlines_hi','water':'static_nwm_waterbodies_hi','modeled':False},
 'prvi':{'bbox':[-68.1,17.6,-64.4,18.6],'flow':'static_nwm_flowlines_prvi','water':'static_nwm_waterbodies_prvi','modeled':False}}
UNAVAILABLE={'alaska':'NOAA reference catalog publishes Alaska flowlines but no Alaska NWM waterbody layer; footprint identification is unavailable.'}
ROOT=Path(__file__).resolve().parents[2]
def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(path.read_text())
def save(path,data):connections.write(path,data)
def intersects(a,b):return a[0]<=b[2] and a[2]>=b[0] and a[1]<=b[3] and a[3]>=b[1]
def owns(bbox,point,outer):
 x,y=point;w,s,e,n=bbox
 return w<=x and s<=y and (x<e or e==outer[2] and x<=e) and (y<n or n==outer[3] and y<=n)
def initial_catalog():
 cells={}
 for domain,d in DOMAINS.items():
  w,s,e,n=d['bbox']
  for i in range(math.ceil((e-w)/2)):
   for j in range(math.ceil((n-s)/2)):
    box=[w+2*i,s+2*j,min(e,w+2*i+2),min(n,s+2*j+2)];key=f'{domain}_{box[0]:g}_{box[1]:g}'
    cells[key]={'domain':domain,'bbox':box,'status':'pending'}
 return {'version':1,'cells':cells,'waterbodies':{},'unavailable_domains':UNAVAILABLE,'updated_at':now(),'refresh_cursor':0}
def ids(data,limit):
 values=data.get('objectIds')
 if values is None and 'objectIds' in data and data.get('objectIdFieldName') and not data.get('exceededTransferLimit'):values=[]
 if not isinstance(values,list) or len(values)>limit or data.get('exceededTransferLimit'):raise ValueError('Missing, truncated or oversized ID response')
 return values

def polygons(domain,bbox,cache):
 d=DOMAINS[domain];url=BASE+d['water']+'/MapServer/0';meta=validate_schema(url,['feature_id','gnis_name'])
 path=cache/(domain+'-'+str(bbox)+'.json')
 if path.exists():return read(path)['features']
 spatial={'geometry':','.join(map(str,bbox)),'geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects','where':'1=1'}
 keys=ids(get(url+'/query',{**spatial,'returnIdsOnly':'true'}),5000);features=[]
 size=min(200,meta.get('maxRecordCount',200))
 for start in range(0,len(keys),size):
  batch=keys[start:start+size];data=get(url+'/query',{'f':'geojson','objectIds':','.join(map(str,batch)),'outFields':'feature_id,gnis_name','returnGeometry':'true','outSR':4326,'geometryPrecision':6,'maxAllowableOffset':.0001})
  if data.get('exceededTransferLimit') or len(data.get('features',[]))!=len(batch):raise ValueError('Truncated waterbody polygons')
  features+=data['features']
 save(path,{'features':features,'retrieved_at':now()});return features

def discover(catalog,key,cache):
 from shapely.geometry import shape
 cell=catalog['cells'][key];domain=cell['domain'];d=DOMAINS[domain];features=polygons(domain,cell['bbox'],cache/'polygons')
 seed_ids={str(f['properties']['waterbody_id']) for f in read(ROOT/'web/nwm/reservoirs/waterbodies.geojson')['features']} if domain=='conus' else set()
 for f in features:
  p=f['properties'];wid=str(int(p['feature_id']));box=list(shape(f['geometry']).bounds);center=[(box[0]+box[2])/2,(box[1]+box[3])/2]
  if not owns(cell['bbox'],center,d['bbox']) or wid in seed_ids:continue
  body_key=domain+'-'+wid
  if body_key not in catalog['waterbodies']:catalog['waterbodies'][body_key]={'domain':domain,'id':wid,'name':p.get('gnis_name') or 'Unnamed NOAA waterbody','bbox':box,'status':'pending','cell':key}
  save(cache/'polygons-by-id'/(body_key+'.json'),f)
 cell.update(status='discovered',candidate_count=len(features),updated_at=now());print('Discovered',key,len(features),'candidate footprints',flush=True)

def polygon_query(url,geometry):
 # POST carries authoritative polygon rings without URL-length truncation.
 from shapely.geometry import shape
 from shapely.geometry.polygon import orient
 polygon=shape(geometry);parts=[polygon] if polygon.geom_type=='Polygon' else list(polygon.geoms);rings=[]
 for part in parts:
  part=orient(part,sign=-1);rings.append(list(part.exterior.coords));rings.extend(list(r.coords) for r in part.interiors)
 params={'f':'json','geometry':json.dumps({'rings':rings,'spatialReference':{'wkid':4326}},separators=(',',':')),'geometryType':'esriGeometryPolygon','inSR':4326,'spatialRel':'esriSpatialRelIntersects','where':'1=1','returnIdsOnly':'true'}
 for attempt in range(3):
  try:
   r=requests.post(url+'/query',data=params,timeout=45)
   if r.status_code in (429,500,502,503,504) and attempt<2:
    retry=r.headers.get('Retry-After','');delay=int(retry) if retry.isdigit() else 2**attempt
    if delay>30:raise ValueError('NOAA requested a long retry delay; resume later')
    time.sleep(delay);continue
   r.raise_for_status();data=r.json()
   if 'error' in data:raise ValueError(str(data['error']))
   return ids(data,5000)
  except requests.Timeout:
   if attempt==2:raise
   time.sleep(2**attempt)

def footprint_lines(domain,body,cache):
 url=BASE+DOMAINS[domain]['flow']+'/FeatureServer/0';key=body['properties']['waterbody_id'];path=cache/'selections'/(domain+'-'+key+'.json')
 if path.exists():return read(path)['features']
 meta=validate_schema(url,['feature_id','strm_order']);available={f['name'] for f in meta['fields']};fields=[f for f in ['feature_id','name','strm_order','nwm_vers','rf_2_0_17c'] if f in available]
 object_ids=polygon_query(url,body['geometry']);features=[]
 size=min(200,meta.get('maxRecordCount',200))
 for start in range(0,len(object_ids),size):
  batch=object_ids[start:start+size];data=get(url+'/query',{'objectIds':','.join(map(str,batch)),'outFields':','.join(fields),'returnGeometry':'true','outSR':4326,'geometryPrecision':6,'maxAllowableOffset':.0001})
  if data.get('exceededTransferLimit') or len(data.get('features',[]))!=len(batch):raise ValueError('Truncated flowline geometry')
  for row in data['features']:
   a=row['attributes'];rid=str(a['feature_id']);paths=row.get('geometry',{}).get('paths')
   if not rid.isdigit() or not paths:raise ValueError('Invalid flowline identity/geometry')
   features.append({'type':'Feature','geometry':{'type':'MultiLineString','coordinates':paths},'properties':{'feature_id':rid,'order':a['strm_order'],'name':a.get('name'),'flood':a.get('rf_2_0_17c'),'version':a.get('nwm_vers'),'geometry_source':url}})
 save(path,{'features':features});return features

def build(catalog,key,cache,output,budget,depth):
 from shapely.geometry import shape
 item=catalog['waterbodies'][key];domain=item['domain'];d=DOMAINS[domain];url=BASE+d['water']+'/MapServer/0'
 p=cache/'polygons-by-id'/(key+'.json')
 if p.exists():raw=read(p)
 else:
  data=get(url+'/query',{'f':'geojson','where':'feature_id = '+item['id'],'outFields':'feature_id,gnis_name','returnGeometry':'true','outSR':4326})
  if len(data.get('features',[]))!=1:raise ValueError('Waterbody identity unavailable')
  raw=data['features'][0];save(p,raw)
 if str(int(raw['properties']['feature_id']))!=item['id']:raise ValueError('Waterbody identity changed')
 if shape(raw['geometry']).is_empty or not shape(raw['geometry']).is_valid:
  data=get(url+'/query',{'f':'geojson','where':'feature_id = '+item['id'],'outFields':'feature_id,gnis_name','returnGeometry':'true','outSR':4326})
  if len(data.get('features',[]))!=1 or shape(data['features'][0]['geometry']).is_empty or not shape(data['features'][0]['geometry']).is_valid:
   item.update(status='unavailable-invalid-geometry',updated_at=now());return
  raw=data['features'][0]
 body={'type':'Feature','geometry':raw['geometry'],'properties':{'waterbody_id':item['id'],'name':item['name'],'domain':domain,'geometry_source':url,'classification':'NOAA waterbody; reservoir/natural-lake type unavailable'}}
 lines=footprint_lines(domain,body,cache);groups=core.membership([body],lines);nodes={};errors={};frontier=[]
 if groups:
  order=max(f['properties']['order'] for f in lines if f['properties']['feature_id'] in groups[0]['properties']['reach_ids'])
  groups[0]['properties']['reach_ids']=[r for r in groups[0]['properties']['reach_ids'] if next(f['properties']['order'] for f in lines if f['properties']['feature_id']==r)==order]
  nodes,errors,frontier=core.topology_for(groups,lines,cache/domain,max_requests=1000,max_depth=depth,follow_priority_names=False,budget=budget)
  seed_ids={r for group in groups for r in group['properties']['reach_ids']}
  context=connected_geometry.retrieve(set(nodes)|seed_ids,cache/domain/'flowlines',{'features':lines},services=[d['flow']])
  for f in context['features']:f['properties'].update(length_km=core.length_km(f['geometry']),priority_mainstem=False)
  groups=core.membership([body],context['features'])
 else:context={'type':'FeatureCollection','features':[]}
 if groups:
  body=groups[0];by_id={f['properties']['feature_id']:f for f in context['features']};order=max(by_id[r]['properties']['order'] for r in body['properties']['reach_ids'])
  body['properties']['excluded_tributary_reach_ids']=[r for r in body['properties']['reach_ids'] if by_id[r]['properties']['order']<order]
  body['properties']['reach_ids']=[r for r in body['properties']['reach_ids'] if by_id[r]['properties']['order']>=order]
 else:order=max([f['properties']['order'] for f in lines],default=1);body['properties']['reach_ids']=[]
 body['properties']['order']=order
 staging=cache/'products'/key;save(staging/'context.geojson',context)
 if d['modeled'] and context['features']:
  try:core.refresh_flows(staging);flow=read(staging/'flow.json')
  except Exception as error:
   flow=read(staging/'flow.json') if (staging/'flow.json').exists() else {'records':[],'retrieved_at':now(),'noaa_updated_at':None}
   flow['unavailable_reason']=str(error)
 else:flow={'records':[],'retrieved_at':now(),'noaa_updated_at':None,'unavailable_reason':'Modeled anomaly references unavailable in this domain' if not d['modeled'] else 'No actual interior flowlines retrieved'}
 static={'waterbodies':{'type':'FeatureCollection','features':[body]},'context':context,'topology':{'reaches':nodes},'metadata':{'built_at':now(),'domain':domain,'all_stream_orders':True,'river_name_filter':None,'routing_errors':errors,'unresolved_priority_frontier':frontier}}
 target=output/'shards'/key;save(target/'static.json',static);save(target/'flow.json',flow)
 item.update(status='published',pending_rebuild=False,order=order,static='shards/'+key+'/static.json',flow='shards/'+key+'/flow.json',updated_at=now(),flow_retrieved_at=flow['retrieved_at'],member_reaches=len(body['properties']['reach_ids']),context_reaches=len(context['features']))
 print('Published',key,item['name'],item['member_reaches'],'member reaches',flush=True)

def refresh(catalog,output,cache,max_batches,deadline):
 # Deduplicate already-cached IDs, refresh values only, and publish a shard only if all IDs succeeded.
 published=[(k,v) for k,v in catalog['waterbodies'].items() if v['status']=='published' and DOMAINS[v['domain']]['modeled']]
 features={};shard_ids={}
 for key,item in published:
  fs=read(output/item['static'])['context']['features'];shard_ids[key]={f['properties']['feature_id'] for f in fs}
  features.update({f['properties']['feature_id']:{'properties':{'feature_id':f['properties']['feature_id'],'flood':f['properties'].get('flood')}} for f in fs})
 keys=sorted(features);updates={};failures=0
 if not keys:return
 start=catalog.get('refresh_cursor',0)%len(keys);ordered=keys[start:]+keys[:start];processed=0
 for offset in range(0,min(len(ordered),max_batches*5000),5000):
  if time.monotonic()>deadline:break
  batch=ordered[offset:offset+5000];staging=cache/'refresh';save(staging/'context.geojson',{'features':[features[r] for r in batch]})
  try:core.refresh_flows(staging);updates.update({r['feature_id']:r for r in read(staging/'flow.json')['records']})
  except Exception as error:
   failures+=1;print('Flow batch unavailable:',str(error),flush=True)
   if failures>=2:break
  processed+=len(batch)
 catalog['refresh_cursor']=(start+processed)%len(keys)
 for key,item in published:
  wanted=shard_ids[key]
  if not wanted or not wanted<=updates.keys():continue
  records=[updates[r] for r in sorted(wanted)];dates=sorted({r['noaa_updated_at'] for r in records if r.get('noaa_updated_at')})
  save(output/item['flow'],{'records':records,'units':'ft³/s','retrieved_at':now(),'noaa_updated_at':dates[0] if len(dates)==1 else None,'noaa_update_values':dates,'source':'NOAA NWM anomaly service exact-ID joins'})
  item['flow_retrieved_at']=now()
 print('Refreshed',len(updates),'distinct cached context IDs',flush=True)

def manifest(catalog,output):
 published=[{'key':k,**{name:item[name] for name in ['domain','bbox','name','order','static','flow','updated_at','flow_retrieved_at']}} for k,item in catalog['waterbodies'].items() if item['status']=='published']
 counts={}
 for item in catalog['waterbodies'].values():counts[item['status']]=counts.get(item['status'],0)+1
 save(output/'manifest.json',{'version':1,'updated_at':now(),'shards':published,'coverage':{'cells_total':len(catalog['cells']),'cells_discovered':sum(c['status']=='discovered' for c in catalog['cells'].values()),'waterbodies':counts,'unavailable_domains':UNAVAILABLE,'modeled_reference_unavailable_domains':[key for key,value in DOMAINS.items() if not value['modeled']]},'limits':'Incremental all-order coverage; missing footprints/references/routing remain unavailable. Shards load by viewport.'})

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'web/nwm/reservoirs/national');p.add_argument('--cache',type=Path,default=ROOT/'local/output/nwm-national-reservoirs');p.add_argument('--mode',choices=['expand','refresh'],default='expand');p.add_argument('--cell');p.add_argument('--rebuild-body',help='Explicit existing body key to resume or rebuild static context');p.add_argument('--max-cells',type=int,default=2);p.add_argument('--max-waterbodies',type=int,default=32);p.add_argument('--routing-budget',type=int,default=800);p.add_argument('--max-depth',type=int,default=50);p.add_argument('--seconds',type=int,default=1200);p.add_argument('--refresh-batches',type=int,default=50);a=p.parse_args()
 for value,cap in [(a.max_cells,8),(a.max_waterbodies,100),(a.routing_budget,1000),(a.max_depth,50),(a.seconds,2400),(a.refresh_batches,100)]:
  if not 1<=value<=cap:raise ValueError('Invalid bounded run parameter')
 path=a.output/'progress.json';catalog=read(path) if path.exists() else initial_catalog();budget={'remaining':a.routing_budget,'deadline':time.monotonic()+a.seconds}
 try:
  if a.mode=='refresh':refresh(catalog,a.output,a.cache,a.refresh_batches,budget['deadline'])
  else:
   if a.rebuild_body:
    if a.rebuild_body not in catalog['waterbodies']:raise ValueError('Unknown waterbody key')
    catalog['waterbodies'][a.rebuild_body]['pending_rebuild']=True;catalog['waterbodies'][a.rebuild_body].pop('retry_after',None)
   if a.cell and a.cell not in catalog['cells']:raise ValueError('Unknown cell key')
   pending=[k for k,v in catalog['cells'].items() if (v['status'] in ['pending','retry'] or v.get('pending_rebuild')) and (not v.get('retry_after') or datetime.fromisoformat(v['retry_after'])<=datetime.now(timezone.utc))]
   priority=['conus_-123_40','conus_-93_44','hawaii_-157_20','prvi_-68.1_17.6']
   pending=([a.cell] if a.cell else sorted(pending,key=lambda k:(priority.index(k) if k in priority else len(priority),k)))[:a.max_cells]
   for key in pending:
    if time.monotonic()>budget['deadline']:break
    try:discover(catalog,key,a.cache)
    except Exception as error:
     catalog['cells'][key].update(status='retry',last_error=str(error),updated_at=now(),retry_after=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat());print(key,str(error),flush=True)
     if isinstance(error,requests.HTTPError) and error.response.status_code==429:budget['remaining']=0;break
   tasks=[(k,v) for k,v in catalog['waterbodies'].items() if (v['status'] in ['pending','retry'] or v.get('pending_rebuild')) and (not v.get('retry_after') or datetime.fromisoformat(v['retry_after'])<=datetime.now(timezone.utc))]
   tasks.sort(key=lambda pair:((0 if pair[0]==a.rebuild_body else 1),(0 if a.cell and pair[1]['cell']==a.cell else 1),-(pair[1]['bbox'][2]-pair[1]['bbox'][0])*(pair[1]['bbox'][3]-pair[1]['bbox'][1]),pair[0]))
   for key,item in tasks[:a.max_waterbodies]:
    if time.monotonic()>budget['deadline'] or budget['remaining']<=0:break
    try:build(catalog,key,a.cache,a.output,budget,a.max_depth)
    except Exception as error:
     item.update(status='published' if item.get('static') and (a.output/item['static']).exists() else 'retry',last_error=str(error),updated_at=now(),retry_after=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat());print(key,'deferred:',str(error),flush=True)
     if 'budget' in str(error).lower() or isinstance(error,requests.HTTPError) and error.response.status_code==429:break
 finally:
  catalog['updated_at']=now();save(path,catalog);manifest(catalog,a.output)
if __name__=='__main__':main()
