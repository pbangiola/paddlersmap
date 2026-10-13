import {rivers} from './scale.mjs';
const STATIC='https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0';
const FLOW='https://maps.water.noaa.gov/server/rest/services/nwm/ana_anomaly/MapServer/0';
const EMPTY={type:'FeatureCollection',features:[]};
const memory=new Map();
let database;
async function db(){
  if(!database)database=new Promise((resolve,reject)=>{
    const request=indexedDB.open('paddlersmap-nwm-v1',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('cache');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
  return database;
}
async function cached(key){
  if(memory.has(key))return memory.get(key);
  try{const database=await db();return await new Promise(resolve=>{const request=database.transaction('cache').objectStore('cache').get(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve(null);});}catch{return null;}
}
async function save(key,value){
  memory.set(key,value);if(memory.size>80)memory.delete(memory.keys().next().value);
  try{(await db()).transaction('cache','readwrite').objectStore('cache').put(value,key);}catch{/* A full cache must not hide available NOAA data. */}
}
export function tier(zoom){return zoom<5?{order:7,z:4}:zoom<7?{order:5,z:Math.floor(zoom)}:zoom<9?{order:3,z:Math.floor(zoom)}:{order:1,z:Math.min(12,Math.floor(zoom))};}
const latitude=(y,n)=>Math.atan(Math.sinh(Math.PI*(1-2*y/n)))*180/Math.PI;
export function cellsForBounds([west,south,east,north],zoom){
  west=Math.max(-125,west);east=Math.min(-66,east);south=Math.max(24,south);north=Math.min(50,north);
  if(west>=east||south>=north)return [];
  const {z,order}=tier(zoom),n=2**z;
  const x=lon=>Math.floor((lon+180)/360*n);
  const y=lat=>Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
  const cells=[];
  for(let i=x(west);i<=x(east-1e-9);i++)for(let j=y(north);j<=y(south+1e-9);j++)
    cells.push({key:`conus:${order}:${z}:${i}:${j}`,order,z,bbox:[Math.max(-125,i/n*360-180),Math.max(24,latitude(j+1,n)),Math.min(-66,(i+1)/n*360-180),Math.min(50,latitude(j,n))]});
  if(cells.length>24)throw new Error('View exceeds the bounded color-query budget; zoom in.');
  return cells;
}
export async function arcgis(url,params,signal,fetcher=fetch){
  for(let attempt=0;attempt<3;attempt++){
    let response;
    try{response=await fetcher(url,{method:'POST',body:new URLSearchParams({f:'json',...params}),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(45000)]):AbortSignal.timeout(45000)});}
    catch(error){if(signal?.aborted||!['TimeoutError','TypeError'].includes(error.name)||attempt===2)throw error;await new Promise(resolve=>setTimeout(resolve,1000*2**attempt));continue;}
    if([429,500,502,503,504].includes(response.status)&&attempt<2){
      const retry=Number(response.headers.get('Retry-After'));
      await new Promise((resolve,reject)=>{const timer=setTimeout(resolve,Math.min(30,Number.isFinite(retry)&&retry>0?retry:2**attempt)*1000);signal?.addEventListener('abort',()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'));},{once:true});});
      continue;
    }
    if(!response.ok)throw new Error('NOAA service HTTP '+response.status);
    const data=await response.json();if(data.error)throw new Error(data.error.message||'NOAA query failed');return data;
  }
}
export function normalize(attributes){
  const a=attributes.prcntle_25,b=attributes.prcntle_75;
  return {feature_id:String(attributes.feature_id),discharge:attributes.latest_flow,low:attributes.prcntle_10,
    average:typeof a==='number'&&typeof b==='number'&&Number.isFinite(a)&&Number.isFinite(b)&&0<=a&&a<=b?(a+b)/2:null,
    p25:a,p75:b,noaa_updated_at:attributes.update_time};
}
let schema;
async function schemas(signal){
  if(!schema)schema=Promise.all([arcgis(STATIC,{},signal),arcgis(FLOW,{},signal)]).then(([s,f])=>{
    for(const [metadata,fields] of [[s,['feature_id','name','strm_order','rf_2_0_17c']],[f,['feature_id','latest_flow','prcntle_10','prcntle_25','prcntle_75','update_time']]])
      for(const name of fields){
        const field=metadata.fields.find(field=>field.name===name);if(!field)throw new Error('NOAA schema missing '+name);
        if(['rf_2_0_17c','latest_flow','prcntle_10','prcntle_25','prcntle_75'].includes(name)&&!field.alias?.toLowerCase().includes('cfs'))throw new Error('Unverified NOAA discharge units for '+name);
      }
    return {staticLimit:Math.min(1000,s.maxRecordCount||1000),flowLimit:Math.min(500,f.maxRecordCount||500)};
  }).catch(error=>{schema=null;throw error;});
  return schema;
}
export async function loadCell(cell,signal){
  const limits=await schemas(signal);
  let geometry=await cached('geometry:'+cell.key);
  if(!geometry){
    const spatial={geometry:cell.bbox.join(','),geometryType:'esriGeometryEnvelope',inSR:4326,spatialRel:'esriSpatialRelIntersects',where:'strm_order >= '+cell.order};
    const ids=(await arcgis(STATIC+'/query',{...spatial,returnIdsOnly:true},signal)).objectIds;
    if(!Array.isArray(ids)||ids.length>25000)throw new Error('NOAA cell missing IDs or exceeds the 25,000-reach bound');
    const features=[];
    for(let i=0;i<ids.length;i+=limits.staticLimit){
      const batch=ids.slice(i,i+limits.staticLimit);
      const data=await arcgis(STATIC+'/query',{objectIds:batch.join(','),outFields:'feature_id,name,strm_order,nwm_vers,rf_2_0_17c',returnGeometry:true,outSR:4326,geometryPrecision:6,maxAllowableOffset:360/(2**cell.z)/4096},signal);
      if(data.exceededTransferLimit||data.features?.length!==batch.length)throw new Error('NOAA truncated a geometry batch');
      for(const feature of data.features){
        const p=feature.attributes;if(p.feature_id==null||!feature.geometry?.paths)throw new Error('NOAA reach lacks ID or geometry');
        features.push({type:'Feature',geometry:{type:'MultiLineString',coordinates:feature.geometry.paths},properties:{feature_id:String(p.feature_id),name:p.name,order:p.strm_order,version:p.nwm_vers,flood:p.rf_2_0_17c}});
      }
    }
    geometry={type:'FeatureCollection',features};await save('geometry:'+cell.key,geometry);
  }
  let flow=await cached('flow:'+cell.key);
  if(!flow||Date.now()-flow.fetched_at>15*60*1000){
    const records=[];
    for(let i=0;i<geometry.features.length;i+=limits.flowLimit){
      const ids=geometry.features.slice(i,i+limits.flowLimit).map(f=>f.properties.feature_id);
      const where='feature_id IN ('+ids.map(id=>"'"+id.replaceAll("'","''")+"'").join(',')+')';
      const data=await arcgis(FLOW+'/query',{where,outFields:'feature_id,latest_flow,prcntle_10,prcntle_25,prcntle_75,update_time',returnGeometry:false},signal);
      if(data.exceededTransferLimit||!Array.isArray(data.features))throw new Error('NOAA truncated a flow batch');
      const expected=new Set(ids),seen=new Set();
      for(const feature of data.features){const record=normalize(feature.attributes);if(!expected.has(record.feature_id)||seen.has(record.feature_id))throw new Error('NOAA returned unexpected or duplicate feature IDs');seen.add(record.feature_id);records.push(record);}
    }
    flow={records,fetched_at:Date.now()};await save('flow:'+cell.key,flow);
  }
  const floodById=new Map(geometry.features.map(f=>[f.properties.feature_id,f.properties.flood]));
  return rivers(geometry,flow.records.map(record=>({...record,flood:floodById.get(record.feature_id)})));
}
export function attachLiveColors(map,onStatus){
  map.addSource('nwm-live',{type:'geojson',data:EMPTY});
  map.addLayer({id:'nwm-live',type:'line',source:'nwm-live',minzoom:5,paint:{'line-color':['get','color'],'line-width':['interpolate',['linear'],['zoom'],5,1.2,12,4],'line-opacity':0.95}},map.getLayer('launches')?'launches':undefined);
  let controller,sequence=0;
  async function update(){
    controller?.abort();controller=new AbortController();const signal=controller.signal,version=++sequence;
    map.getSource('nwm-live').setData(EMPTY);
    if(map.getLayoutProperty('nwm-live','visibility')==='none'){onStatus('Custom flow colors are hidden during NOAA comparison.');return;}
    if(map.getZoom()<5){onStatus('National major-river snapshot. Zoom in for more flow colors.');return;}
    const b=map.getBounds();let cells;
    try{cells=cellsForBounds([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()],map.getZoom());}catch(error){onStatus(error.message);return;}
    if(!cells.length){onStatus('NOAA percentile anchors are unavailable for this region; river geometry remains gray.');return;}
    const features=new Map(),dates=new Set();let next=0,completed=0,failed=0;
    onStatus('Loading NOAA flow colors for this view…');
    async function worker(){
      while(next<cells.length&&!signal.aborted){const cell=cells[next++];try{
        const data=await loadCell(cell,signal);if(version!==sequence)return;
        for(const feature of data.features){features.set(feature.properties.feature_id,feature);if(feature.properties.noaa_updated_at)dates.add(feature.properties.noaa_updated_at);}
        map.getSource('nwm-live').setData({type:'FeatureCollection',features:[...features.values()]});
      }catch(error){if(signal.aborted)return;failed++;console.warn('NWM flow cell unavailable',cell.key,error.message);}finally{completed++;}
      if(version===sequence){const available=[...features.values()].filter(f=>f.properties.scale_position!==null).length;onStatus(`${completed}/${cells.length} cells · ${available} colored reaches · ${failed} unavailable cells · NOAA update: ${[...dates].sort().join(', ')||'unavailable'}`);}
      }
    }
    await Promise.all([worker(),worker(),worker()]);
  }
  map.on('moveend',update);document.getElementById('noaa-comparison').addEventListener('change',update);update();
  return {update};
}
