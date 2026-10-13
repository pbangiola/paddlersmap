import {attachLiveColors} from './live.mjs';
import {lineLayer,zoomPolicy} from './policy.mjs';
import {applyObserved,observedPosition} from './gauges.mjs';
import {rivers} from './scale.mjs';
import {addNationalGeometry,DOMAINS,NATIONAL_BOUNDS} from './national.mjs';
const bounds=[[-88.5,41.2],[-87.0,42.5]];
let basemapAvailable=true;
const basemap=await fetch('https://tiles.openfreemap.org/styles/liberty',{signal:AbortSignal.timeout(15000)}).then(response=>{
  if(!response.ok)throw new Error('Basemap unavailable');return response.json();
}).catch(()=>{basemapAvailable=false;return {version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#f4f5f1'}}]};});
// The basemap must not add a second, unfiltered river-line mesh. Keep lakes/coast polygons and labels.
basemap.layers=basemap.layers.filter(layer=>!(layer.type==='line'&&layer['source-layer']==='waterway'));
export const map=new maplibregl.Map({container:'map',style:basemap,bounds:NATIONAL_BOUNDS,fitBoundsOptions:{padding:25}});
if(!basemapAvailable)document.getElementById('basemap-note').hidden=false;
map.addControl(new maplibregl.NavigationControl());
map.on('error',event=>{if(event.sourceId?.startsWith('national-'))document.getElementById('national-error').hidden=false;});
document.getElementById('chicago').onclick=()=>map.fitBounds(bounds,{padding:25});
for(const domain of DOMAINS)document.getElementById(domain.id).onclick=()=>map.fitBounds(domain.bounds,{padding:25});
const status=document.getElementById('status');
async function get(path){const r=await fetch(path);if(!r.ok)throw new Error(path+' HTTP '+r.status);return r.json();}
function popup(lines,xy){const node=document.createElement('div');node.textContent=lines.join('\n');new maplibregl.Popup().setLngLat(xy).setDOMContent(node).addTo(map);}
map.once('style.load',async()=>{
  const nationalIds=addNationalGeometry(map);
  let overview=null,live=null,assignments={sections:[]},observations={},freshnessHours=36;
  const modeled=new Map();
  function sync(){
    const comparing=document.getElementById('noaa-comparison').checked;
    const order=zoomPolicy(map.getZoom()).order;
    const usable=(assignments.sections||[]).filter(s=>[s.upstream,s.downstream].every(id=>observedPosition(observations[id],Date.now(),freshnessHours)!==null)).length;
    document.getElementById('gauge-status').textContent=usable+' usable observed sections / '+(assignments.sections||[]).length+' confirmed paths. Missing, stale or incompatible endpoints use modeled colors. '+(assignments.limitation||'');
    for(const id of nationalIds)map.setLayoutProperty(id,'visibility',!comparing&&document.getElementById('national-geometry').checked?'visible':'none');
    for(const [id,data] of modeled){
      if(!map.getLayer(id))continue;
      map.setFilter(id,['>=',['to-number',['get','order'],0],order]);
      map.setLayoutProperty(id,'visibility',comparing?'none':'visible');
      map.getSource(id).setData(applyObserved(data,assignments,observations,document.getElementById('gauge-colors').checked,Date.now(),freshnessHours));
    }
    if(map.getLayer('noaa-comparison'))map.setLayoutProperty('noaa-comparison','visibility',comparing?'visible':'none');
    if(map.getLayer('launches'))map.moveLayer('launches');
    if(map.getLayer('launches'))map.setLayoutProperty('launches','visibility',document.getElementById('launches').checked?'visible':'none');
    document.getElementById('legend').style.display=comparing?'none':'flex';
    document.getElementById('comparison-note').hidden=!comparing;
  }
  for(const id of ['national-geometry','gauge-colors','noaa-comparison','launches'])document.getElementById(id).addEventListener('change',sync);
  map.on('zoom',()=>{for(const id of modeled.keys())if(map.getLayer(id))map.setFilter(id,['>=',['to-number',['get','order'],0],zoomPolicy(map.getZoom()).order]);});
  // Stage observations refresh without reconstructing topology. Recheck freshness each minute.
  const gaugeReady=Promise.all([get('web/nwm/gauges/assignments.json'),get('web/nwm/gauges/observations.json')]).then(([a,o])=>{
    assignments=a;observations=o.records||{};freshnessHours=Number.isFinite(o.max_age_hours)&&o.max_age_hours>0?o.max_age_hours:36;
    document.getElementById('gauge-status').textContent=(a.sections||[]).length+' confirmed gauge sections. '+(a.limitation||'');sync();
  }).catch(error=>{document.getElementById('gauge-status').textContent='Observed assignments unavailable; modeled colors retained.';});
  setInterval(sync,60000);
  setInterval(()=>get('web/nwm/gauges/observations.json?time='+Date.now()).then(o=>{observations=o.records||{};freshnessHours=Number.isFinite(o.max_age_hours)&&o.max_age_hours>0?o.max_age_hours:36;sync();}).catch(()=>{}),15*60000);
  map.on('click',event=>{
    if(map.getLayer('launches')&&map.queryRenderedFeatures(event.point,{layers:['launches']}).length)return;
    for(const id of ['nwm-live','nwm-national-colors']){
      if(!map.getLayer(id))continue;
      const feature=map.queryRenderedFeatures(event.point,{layers:[id]})[0];if(!feature)continue;
      const p=feature.properties,lines=['Color source: '+p.color_source,'NWM feature ID: '+p.feature_id];
      if(p.gauge_provenance){const g=JSON.parse(p.gauge_provenance);lines.push('Observed section position: '+p.observed_position,'Path confidence: '+g.confidence,'Method: '+g.method,'Covered reach IDs: '+g.reach_ids.join(', '));
        for(const key of ['upstream_observation','downstream_observation']){const o=g[key];lines.push(o.name+' ('+o.id+'): '+o.stage+' ft · low '+o.low+' ft · flood '+o.flood+' ft · position '+o.position+' · '+o.timestamp+' · '+o.reference_source);}}
      lines.push(...[['Current discharge','discharge'],['Low anchor','low'],['Central anchor','average'],['Upper anchor','flood']].map(([label,key])=>label+': '+(p[key]??'unavailable')+(p[key]==null?'':' ft³/s')),'Modeled scale position: '+(p.scale_position??'unavailable'),'NOAA update: '+(p.noaa_updated_at??'unavailable'));
      popup(lines,event.lngLat);break;
    }
  });
  const anomaly='https://maps.water.noaa.gov/server/rest/services/nwm/ana_anomaly/MapServer';
  map.addSource('noaa-comparison',{type:'raster',tileSize:256,tiles:[anomaly+'/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&layers=show:0&format=png32&transparent=true&f=image']});
  map.addLayer({id:'noaa-comparison',type:'raster',source:'noaa-comparison',layout:{visibility:'none'}});
  // Each resource can fail without blocking any of the others.
  const launchesReady=(async()=>{
    try{
      const data=await get('web/nwm/launches/canonical.geojson');
      const registry=await get('data/verified_launches.json').catch(()=>({verified_ids:[]}));
      const verified=new Set(registry.verified_ids||[]);
      for(const f of data.features)f.properties={...f.properties,atlas_verified:verified.has(String(f.properties.id))};
      map.addSource('launches',{type:'geojson',data});
      map.addLayer({id:'launches',type:'circle',source:'launches',paint:{'circle-radius':5,'circle-color':['case',['get','atlas_verified'],'#168447','#e0ad24'],'circle-stroke-color':'#fff','circle-stroke-width':1.5}});
      map.on('click','launches',e=>{const f=e.features[0];popup(Object.entries(f.properties).map(([k,v])=>k+': '+(v&&typeof v==='object'?JSON.stringify(v,null,2):v)),f.geometry.coordinates);});
      status.textContent=data.features.length+' canonical launch records · '+(data.metadata.complete?'Complete source retrieval':'Incomplete national OSM coverage — curated locations retained');sync();
    }catch(error){status.textContent='Launch inventory unavailable: '+error.message;}
  })();
  // Attach live requests before (and independently of) loading the overview.
  live=attachLiveColors(map,text=>document.getElementById('live-status').textContent=text,data=>{modeled.set('nwm-live',data);sync();});
  sync();
  try{
    const manifest=await get('web/nwm/overview/manifest.json');
    const [geometry,flow]=await Promise.all([get('web/nwm/overview/'+manifest.geometry),get('web/nwm/overview/'+manifest.flow)]);
    overview=rivers(geometry,flow.records);modeled.set('nwm-national-colors',overview);
    map.addSource('nwm-national-colors',{type:'geojson',data:overview});
    map.addLayer(lineLayer('nwm-national-colors','nwm-national-colors',{maxzoom:5}),map.getLayer('launches')?'launches':undefined);
    document.getElementById('national-overview').textContent=overview.features.length+' national major-river reaches';
    document.getElementById('updated').textContent='NOAA overview update: '+(flow.noaa_updated_at??'unavailable');sync();
  }catch(error){document.getElementById('national-overview').textContent='National snapshot unavailable; independent live colors and geometry remain available.';}
});
