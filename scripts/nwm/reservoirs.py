#!/usr/bin/env python3
"""Identify Mississippi NWM waterbodies and cache published routing; bounded and resumable."""
import argparse,concurrent.futures,json,math,time
from pathlib import Path
from datetime import datetime,timezone
try:
 from . import connected_geometry,connections
 from .retrieve import get,query,validate_schema
except ImportError:
 import connected_geometry,connections
 from retrieve import get,query,validate_schema
ROOT=Path(__file__).resolve().parents[2]
WATER='https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_waterbodies/MapServer/0'

def length_km(geometry):
 paths=geometry['coordinates'] if geometry['type']=='MultiLineString' else [geometry['coordinates']]
 total=0
 for path in paths:
  for a,b in zip(path,path[1:]):
   lat1,lat2=map(math.radians,[a[1],b[1]]);dl=math.radians(b[0]-a[0]);dp=lat2-lat1
   total+=6371*2*math.asin(min(1,math.sqrt(math.sin(dp/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2)))
 return total

def membership(waterbodies,lines,invalid=None,threshold=.5):
 """Actual line/polygon overlap identifies membership, never names or nearest distance."""
 from shapely.geometry import shape
 from shapely.strtree import STRtree
 shapes=[shape(f['geometry']) for f in lines];tree=STRtree(shapes);groups=[]
 for f in waterbodies:
  polygon=shape(f['geometry'])
  if not len(tree.query(polygon)):continue
  if not polygon.is_valid:
   if invalid is not None:invalid[f['properties']['waterbody_id']]=f['properties'].get('name')
   continue
  members=[];overlaps={}
  for idx in tree.query(polygon,predicate='intersects'):
   line=shapes[idx];fraction=line.intersection(polygon).length/line.length if line.length else 0
   if fraction>threshold:
    rid=str(lines[idx]['properties']['feature_id']);members.append(rid);overlaps[rid]=round(fraction,6)
  if members:groups.append({**f,'properties':{**f['properties'],'reach_ids':sorted(members),'overlap_fraction':overlaps}})
 return groups

def identify(cache):
 from shapely.geometry import shape
 # Name selects the priority river only. Connections always use published feature-ID topology.
 selection=cache/'mississippi-selection.json'
 if selection.exists():ids=set(json.loads(selection.read_text())['reach_ids'])
 else:
  rows=query(connected_geometry.BASE+'static_nwm_flowlines/FeatureServer/0',[-96,28,-88,49],['feature_id'],False,where="name = 'Mississippi River'",batch=200)
  ids={str(row['attributes']['feature_id']) for row in rows};connections.write(selection,{'reach_ids':sorted(ids),'source':connected_geometry.BASE+'static_nwm_flowlines/FeatureServer/0','where':"name = 'Mississippi River'",'bbox':[-96,28,-88,49]})
 if not ids or len(ids)>3000 or any(not rid.isdigit() for rid in ids):raise ValueError('Expected a bounded Mississippi mainstem selection')
 lines=connected_geometry.retrieve(ids,cache/'flowlines')['features']
 regions={}
 for f in lines:
  box=shape(f['geometry']).bounds
  for band in range(math.floor(box[1]),math.floor(box[3])+1):
   r=regions.setdefault(band,[box[0],band,box[2],band+1]);r[0]=min(r[0],box[0]);r[2]=max(r[2],box[2])
 meta=get(WATER,{})
 if not {'feature_id','gnis_name'}<={f['name'] for f in meta.get('fields',[])}:raise ValueError('NOAA waterbody schema changed')
 bodies={}
 for band,bbox in sorted(regions.items(),reverse=True):
  path=cache/f'waterbodies-{band}.json'
  if path.exists() and json.loads(path.read_text()).get('bbox')==bbox:part=json.loads(path.read_text())
  else:
   spatial={'geometry':','.join(map(str,bbox)),'geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects','where':'1=1'}
   result=get(WATER+'/query',{**spatial,'returnIdsOnly':'true'})
   object_ids=result.get('objectIds')
   if object_ids is None and result.get('objectIdFieldName') and 'objectIds' in result:object_ids=[]
   if not isinstance(object_ids,list) or len(object_ids)>5000:raise ValueError('Unbounded or invalid waterbody query')
   fs=[]
   for start in range(0,len(object_ids),200):
    batch=object_ids[start:start+200]
    data=get(WATER+'/query',{'f':'geojson','objectIds':','.join(map(str,batch)),'outFields':'feature_id,gnis_name','returnGeometry':'true','outSR':4326,'geometryPrecision':6,'maxAllowableOffset':.0001})
    if data.get('exceededTransferLimit') or len(data.get('features',[]))!=len(batch):raise ValueError('Truncated NOAA polygon batch')
    fs+=data['features'];time.sleep(.2)
   part={'bbox':bbox,'features':fs,'retrieved_at':datetime.now(timezone.utc).isoformat()};connections.write(path,part)
  for f in part['features']:
   p=f['properties'];wid=str(int(p['feature_id']));bodies[wid]={'type':'Feature','geometry':f['geometry'],'properties':{'waterbody_id':wid,'name':p.get('gnis_name') or 'Unnamed NOAA waterbody','geometry_source':WATER,'classification':'NOAA waterbody; reservoir/natural-lake type unavailable'}}
  print('Waterbody region',band,len(part['features']),'candidates',flush=True)
 invalid={}
 groups=membership(list(bodies.values()),lines,invalid,threshold=1e-8)
 # Simplification can invalidate thin navigation pools; retry the original polygon once.
 for wid in list(invalid):
  path=cache/('waterbody-full-'+wid+'.json')
  if path.exists():data=json.loads(path.read_text())
  else:
   data=get(WATER+'/query',{'f':'geojson','where':'feature_id = '+wid,'outFields':'feature_id,gnis_name','returnGeometry':'true','outSR':4326});connections.write(path,data)
  fs=data.get('features',[])
  if len(fs)==1 and str(int(fs[0]['properties']['feature_id']))==wid:
   candidate={**bodies[wid],'geometry':fs[0]['geometry']}
   if shape(candidate['geometry']).is_valid:bodies[wid]=candidate
 invalid={}
 groups=membership(list(bodies.values()),lines,invalid,threshold=1e-8)
 return lines,groups,len(bodies),invalid

def topology_for(groups,lines,cache,max_requests=400,max_depth=24):
 errors={};count=0
 orders={str(f['properties']['feature_id']):f['properties'].get('order',0) for f in lines}
 priorities={}
 for g in groups:
  order=max(orders[r] for r in g['properties']['reach_ids'])
  for rid in g['properties']['reach_ids']:priorities[rid]=min(priorities.get(rid,order),order)
 members=set(priorities);frontier=members;nodes={}
 # Bounded boundary rings supply published routing outside polygons; no inferred links.
 for depth in range(max_depth):
  todo=[]
  for rid in sorted(frontier-nodes.keys()):
   path=cache/'routing'/(rid+'.json')
   if path.exists():detail=json.loads(path.read_text());nodes[rid]=parse_routing(detail,rid)
   else:todo.append(rid)
  if count+len(todo)>max_requests:raise ValueError('Routing budget exceeded; cached checkpoints retained')
  def fetch(rid):
   try:
    detail=connections.get('/reaches/'+rid);node=parse_routing(detail,rid);connections.write(cache/'routing'/(rid+'.json'),detail);return rid,node,detail,None
   except Exception as e:return rid,None,None,str(e)
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   for rid,node,detail,error in pool.map(fetch,todo):
    count+=1
    if error:errors[rid]=error
    else:nodes[rid]=node
  next_frontier=set()
  for rid in frontier:
   if rid not in nodes:continue
   for direction in ['upstream','downstream']:
    edges=nodes[rid][direction]
    eligible=[nxt for nxt in edges if nxt in orders or nodes[rid][direction+'_orders'].get(nxt,0)>=priorities[rid]]
    if not eligible and direction=='upstream' and (rid in orders or rid in members):
     largest=max([nodes[rid][direction+'_orders'].get(nxt,0) for nxt in edges],default=0)
     eligible=[nxt for nxt in edges if largest>0 and nodes[rid][direction+'_orders'].get(nxt,0)==largest]
    for nxt in eligible:
     priorities[nxt]=min(priorities.get(nxt,priorities[rid]),priorities[rid]);next_frontier.add(nxt)
  frontier=next_frontier
  if not frontier-nodes.keys():break
  print('Reservoir routing frontier',depth,'nodes',len(nodes),'requests',count,'errors',len(errors),flush=True)
 return nodes,errors,sorted(frontier-nodes.keys())

def parse_routing(detail,rid):
 node=connections.parse_reach(detail,rid)
 up=detail.get('route',{}).get('upstream')
 if not isinstance(up,list):raise ValueError('Published upstream routing unavailable')
 ids=[str(v.get('reachId')) for v in up if str(v.get('reachId'))!='0']
 if any(not v.isdigit() or int(v)<=0 for v in ids) or len(ids)!=len(set(ids)):raise ValueError('Invalid upstream IDs')
 return {**node,'upstream':ids,**{direction+'_orders':{str(v['reachId']):int(v.get('streamOrder') or 0) for v in detail['route'][direction] if str(v.get('reachId'))!='0'} for direction in ['upstream','downstream']}}

def refresh_flows(output):
 context=json.loads((output/'context.geojson').read_text())
 config=json.loads((ROOT/'web/nwm/services.json').read_text());url=config['flow']['url']
 if url!=config['reference']['url'] or config['units']!='ft³/s':raise ValueError('Unverified flow/reference service configuration')
 fields=['feature_id','latest_flow','prcntle_10','prcntle_25','prcntle_75','update_time']
 validate_schema(url,fields)
 records={str(f['properties']['feature_id']):{'feature_id':str(f['properties']['feature_id']),'flood':f['properties'].get('flood')} for f in context['features']}
 if not records or len(records)>5000 or any(not rid.isdigit() for rid in records):raise ValueError('Expected 1–5,000 numerical reservoir context IDs')
 ids=sorted(records);updates=set();matched=0
 for start in range(0,len(ids),100):
  batch=ids[start:start+100]
  data=get(url+'/query',{'where':'feature_id IN ('+','.join("'"+rid+"'" for rid in batch)+')','outFields':','.join(fields),'returnGeometry':'false'})
  if data.get('exceededTransferLimit') or not isinstance(data.get('features'),list):raise ValueError('Truncated flow batch; previous snapshot retained')
  seen=set()
  for row in data['features']:
   a=row['attributes'];rid=str(a['feature_id'])
   if rid not in batch or rid in seen:raise ValueError('Invalid or duplicate exact-ID flow join')
   seen.add(rid);matched+=1;p25,p75=a.get('prcntle_25'),a.get('prcntle_75')
   average=(p25+p75)/2 if all(type(v) in (int,float) and math.isfinite(v) for v in [p25,p75]) and 0<=p25<=p75 else None
   updated=a.get('update_time')
   if isinstance(updated,(int,float)):updated=datetime.fromtimestamp(updated/1000,timezone.utc).isoformat()
   if updated is not None:updates.add(str(updated))
   records[rid].update({'discharge':a.get('latest_flow'),'low':a.get('prcntle_10'),'average':average,'noaa_updated_at':updated})
 if not matched:raise ValueError('NOAA returned no context flow records; previous snapshot retained')
 connections.write(output/'flow.json',{'records':list(records.values()),'units':'ft³/s','source':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'noaa_updated_at':next(iter(updates)) if len(updates)==1 else None,'noaa_update_values':sorted(updates)})
 print('Refreshed',len(records),'bounded reservoir context flows',flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--flow-only',action='store_true');p.add_argument('--cache',type=Path,default=ROOT/'local/output/nwm-reservoirs');p.add_argument('--output',type=Path,default=ROOT/'web/nwm/reservoirs');p.add_argument('--max-requests',type=int,default=400);p.add_argument('--max-depth',type=int,default=24);a=p.parse_args()
 if a.flow_only:refresh_flows(a.output);return
 if not 1<=a.max_depth<=50:raise ValueError('Routing depth must be 1–50')
 if not 1<=a.max_requests<=1000:raise ValueError('Routing budget must be 1–1,000 requests')
 lines,groups,candidates,invalid=identify(a.cache)
 print('Identified',len(groups),'Mississippi waterbodies;',sum(len(g['properties']['reach_ids']) for g in groups),'member reaches',flush=True)
 nodes,errors,unresolved=topology_for(groups,lines,a.cache,a.max_requests,a.max_depth)
 context_ids=set(nodes)|{rid for group in groups for rid in group['properties']['reach_ids']};known={str(f['properties']['feature_id']):f for f in lines}
 context=connected_geometry.retrieve(context_ids,a.cache/'flowlines',{'features':list(known.values())})
 for f in context['features']:
  f['properties']['length_km']=length_km(f['geometry']);f['properties']['priority_mainstem']=str(f['properties']['feature_id']) in known
 groups=membership(groups,context['features'])
 for group in groups:
  orders={str(f['properties']['feature_id']):f['properties']['order'] for f in context['features']}
  order=max(orders[r] for r in group['properties']['reach_ids'])
  group['properties']['order']=order
  group['properties']['excluded_tributary_reach_ids']=[r for r in group['properties']['reach_ids'] if orders[r]<order and r not in known]
  group['properties']['reach_ids']=[r for r in group['properties']['reach_ids'] if orders[r]>=order or r in known]
 metadata={'priority':'Mississippi River mainstem, all stream orders within [-96,28,-88,49]','built_at':datetime.now(timezone.utc).isoformat(),'waterbody_source':WATER,'routing_source':connections.BASE+'/reaches/{reachId}','candidate_polygons':candidates,'invalid_candidate_geometries':invalid,'identified_waterbodies':len(groups),'member_reaches':len({r for g in groups for r in g['properties']['reach_ids']}),'routing_nodes':len(nodes),'routing_depth_limit':a.max_depth,'routing_new_request_limit':a.max_requests,'unresolved_priority_frontier':unresolved,'routing_errors':errors,'limitations':'Waterbody is not a reservoir classification. Partial boundary topology and missing numerical anchors are explicit; no discharge is inferred. No nearest/name network joins.'}
 connections.write(a.output/'waterbodies.geojson',{'type':'FeatureCollection','metadata':metadata,'features':groups})
 connections.write(a.output/'context.geojson',context)
 connections.write(a.output/'topology.json',{'reaches':nodes,'metadata':metadata})
 refresh_flows(a.output)
 print(json.dumps(metadata),flush=True)
if __name__=='__main__':main()
