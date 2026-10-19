import {zoomPolicy} from './policy.mjs';
const overlap=(a,b)=>a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];
export function selectShards(manifest,bounds,zoom,limit=24){
 const order=zoomPolicy(zoom).order,cx=(bounds[0]+bounds[2])/2,cy=(bounds[1]+bounds[3])/2;
 return (manifest.shards||[]).filter(s=>s.order>=order&&overlap(s.bbox,bounds)).sort((a,b)=>{
  const area=s=>(s.bbox[2]-s.bbox[0])*(s.bbox[3]-s.bbox[1]);
  const distance=s=>((s.bbox[0]+s.bbox[2])/2-cx)**2+((s.bbox[1]+s.bbox[3])/2-cy)**2;
  return (zoom<6?area(b)-area(a):distance(a)-distance(b))||a.key.localeCompare(b.key);
 }).slice(0,limit);
}
export function combineReservoirData(parts){
 const bodies=new Map(),features=new Map(),nodes={},conflicts=new Set(),records=new Map(),times=new Map();
 for(const part of parts.filter(Boolean)){
  for(const f of part.waterbodies?.features||[])bodies.set((f.properties.domain||'conus')+':'+f.properties.waterbody_id,f);
  for(const f of part.geometry?.features||[])features.set(String(f.properties.feature_id),f);
  for(const [id,node] of Object.entries(part.topology?.reaches||{})){
   if(nodes[id]&&['upstream','downstream'].some(direction=>Array.isArray(nodes[id][direction])&&Array.isArray(node[direction])&&JSON.stringify([...nodes[id][direction]].sort())!==JSON.stringify([...node[direction]].sort())))conflicts.add(id);
   else nodes[id]={...nodes[id],...node};
  }
  const date=Date.parse(part.flow?.retrieved_at)||0;
  for(const r of part.flow?.records||[]){const id=String(r.feature_id);if(date>=(times.get(id)||0)){records.set(id,r);times.set(id,date);}}
 }
 for(const id of conflicts)delete nodes[id];
 return {waterbodies:{type:'FeatureCollection',features:[...bodies.values()]},geometry:{type:'FeatureCollection',features:[...features.values()]},topology:{reaches:nodes},flow:{records:[...records.values()]}};
}
export function freshFlow(flow,now=Date.now()){
 const age=now-Date.parse(flow?.retrieved_at);
 // Stale national snapshots cannot silently become fresh offscreen anchors.
 return Number.isFinite(age)&&age>=0&&age<=36*3600000?flow:{...flow,records:[],unavailable_reason:'National cached flow snapshot is unavailable or older than 36 hours'};
}
export function attachNationalReservoirs(map,onData,onStatus,fetcher=fetch){
 const root='web/nwm/reservoirs/national/',staticCache=new Map(),flowCache=new Map();
 let manifest=null,manifestAt=0,generation=0,timer;
 async function get(path){const r=await fetcher(root+path);if(!r.ok)throw Error('Reservoir data HTTP '+r.status);return r.json();}
 async function update(){
  const own=++generation;
  try{
   if(!manifest||Date.now()-manifestAt>3600000){manifest=await get('manifest.json');manifestAt=Date.now();}
   const b=map.getBounds(),bounds=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()],shards=selectShards(manifest,bounds,map.getZoom());
   const parts=[];let next=0,failed=0;
   async function worker(){while(next<shards.length){const s=shards[next++];try{
    const staticKey=s.static+'?v='+encodeURIComponent(s.updated_at);
    if(!staticCache.has(staticKey))staticCache.set(staticKey,await get(staticKey));
    if(!flowCache.has(s.flow)||Date.now()-flowCache.get(s.flow).at>15*60000)flowCache.set(s.flow,{at:Date.now(),data:await get(s.flow)});
    const data=staticCache.get(staticKey);parts.push({waterbodies:data.waterbodies,geometry:data.context,topology:data.topology,flow:freshFlow(flowCache.get(s.flow).data)});
   }catch{failed++;}}}
   await Promise.all([worker(),worker(),worker()]);
   if(own!==generation)return;
   onData(combineReservoirData(parts));
   onStatus(shards.length+' national footprints selected for this view · '+(manifest.shards||[]).length+' published · '+failed+' unavailable. Zoom in to inspect smaller footprints.');
   const keep=new Set(shards.flatMap(s=>[s.static+'?v='+encodeURIComponent(s.updated_at),s.flow]));
   if(staticCache.size>48)for(const key of staticCache.keys())if(!keep.has(key))staticCache.delete(key);
   if(flowCache.size>48)for(const key of flowCache.keys())if(!keep.has(key))flowCache.delete(key);
  }catch{if(own===generation)onStatus('National reservoir expansion data unavailable; existing Mississippi coverage retained.');}
 }
 const schedule=()=>{clearTimeout(timer);timer=setTimeout(update,300);};
 map.on('moveend',schedule);const interval=setInterval(update,15*60000);update();
 map.on('remove',()=>{clearTimeout(timer);clearInterval(interval);generation++;});
 return {update};
}
