import {attachLiveColors} from './live.mjs';
import {rivers} from './scale.mjs';
import {addNationalGeometry,DOMAINS} from './national.mjs';
const bounds=[[-88.5,41.2],[-87.0,42.5]];
let basemapAvailable=true;
const basemap=await fetch('https://tiles.openfreemap.org/styles/liberty',{signal:AbortSignal.timeout(15000)}).then(response=>{
  if(!response.ok)throw new Error('Basemap unavailable');return response.json();
}).catch(()=>{basemapAvailable=false;return {version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#f4f5f1'}}]};});
export const map=new maplibregl.Map({container:'map',style:basemap,bounds,fitBoundsOptions:{padding:25}});
if(!basemapAvailable)document.getElementById('basemap-note').hidden=false;
map.addControl(new maplibregl.NavigationControl());
map.on('error',event=>{if(event.sourceId?.startsWith('national-'))document.getElementById('national-error').hidden=false;});
document.getElementById('chicago').onclick=()=>map.fitBounds(bounds,{padding:25});
for(const domain of DOMAINS)document.getElementById(domain.id).onclick=()=>map.fitBounds(domain.bounds,{padding:25});
const status=document.getElementById('status');
async function get(path){const r=await fetch(path);if(!r.ok)throw new Error(path+' HTTP '+r.status);return r.json();}
function popup(lines,xy){const node=document.createElement('div');node.textContent=lines.join('\n');new maplibregl.Popup().setLngLat(xy).setDOMContent(node).addTo(map);}
map.on('load',async()=>{
  addNationalGeometry(map);
  document.getElementById('national-geometry').onchange=e=>{for(const domain of DOMAINS)for(const suffix of ['', '-detail'])map.setLayoutProperty('national-'+domain.id+suffix,'visibility',e.target.checked?'visible':'none');};
  // Launch loading is independent of NOAA service availability.
  let launchCount=0,launchError=null;
  try{
    const data=await get('data/putins_consolidated.geojson');
    const registry=await get('data/verified_launches.json').catch(()=>({verified_ids:[]}));
    const verified=new Set(registry.verified_ids||[]);
    for(const feature of data.features)feature.properties={...feature.properties,atlas_verified:verified.has(String(feature.properties?.id||''))};
    // Preserve the complete source inventory; do not filter or move coordinates.
    map.addSource('launches',{type:'geojson',data});
    map.addLayer({id:'launches',type:'circle',source:'launches',paint:{'circle-radius':5,'circle-color':['case',['get','atlas_verified'],'#168447','#e0ad24'],'circle-stroke-color':'#fff','circle-stroke-width':1.5}});
    launchCount=data.features.length;
    map.on('click','launches',e=>{const f=e.features[0];popup(Object.entries(f.properties).map(([k,v])=>k+': '+v),f.geometry.coordinates);});
    document.getElementById('launches').onchange=e=>map.setLayoutProperty('launches','visibility',e.target.checked?'visible':'none');
  }catch(e){launchError=e;status.textContent='Launch locations unavailable: '+e.message;}
  try{
    const manifest=await get('web/nwm/data/manifest.json');
    const [geometry,flow]=await Promise.all([get('web/nwm/data/'+manifest.geometry),get('web/nwm/data/'+manifest.flow)]);
    const data=rivers(geometry,flow.records);
    map.addSource('nwm',{type:'geojson',data});
    map.addLayer({id:'nwm',type:'line',source:'nwm',paint:{'line-color':['get','color'],'line-width':['interpolate',['linear'],['zoom'],5,1.5,12,4],'line-opacity':0.95}},map.getLayer('launches')?'launches':undefined);
    map.on('click',event=>{
      if(map.getLayer('launches')&&map.queryRenderedFeatures(event.point,{layers:['launches']}).length)return;
      for(const id of ['nwm-live','nwm-national-colors','nwm']){
        if(!map.getLayer(id))continue;
        const feature=map.queryRenderedFeatures(event.point,{layers:[id]})[0];if(!feature)continue;
        const p=feature.properties;
        popup(['NWM feature ID: '+p.feature_id,...[['Current discharge','discharge'],['Low anchor','low'],['Central anchor','average'],['Upper anchor','flood']].map(([label,key])=>label+': '+(p[key]??'unavailable')+(p[key]==null?'':' ft³/s')),'Scale position: '+(p.scale_position??'unavailable'),'NOAA update: '+(p.noaa_updated_at??(id==='nwm'?flow.noaa_updated_at:null)??'unavailable')],event.lngLat);
        break;
      }
    });
    const anomaly='https://maps.water.noaa.gov/server/rest/services/nwm/ana_anomaly/MapServer';
    map.addSource('noaa-comparison',{type:'raster',tileSize:256,tiles:[anomaly+'/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&layers=show:0&format=png32&transparent=true&f=image']});
    map.addLayer({id:'noaa-comparison',type:'raster',source:'noaa-comparison',layout:{visibility:'none'}},map.getLayer('launches')?'launches':undefined);
    document.getElementById('noaa-comparison').onchange=e=>{
      map.setLayoutProperty('noaa-comparison','visibility',e.target.checked?'visible':'none');
      for(const id of ['nwm','nwm-national-colors','nwm-live'])if(map.getLayer(id))map.setLayoutProperty(id,'visibility',e.target.checked?'none':'visible');
      document.getElementById('legend').style.display=e.target.checked?'none':'flex';
      document.getElementById('comparison-note').hidden=!e.target.checked;
    };
    const available=data.features.filter(f=>f.properties.scale_position!==null).length;
    status.textContent=data.features.length+' NOAA reaches · '+available+' with calibrated colors · '+(launchError?'launch locations unavailable':launchCount+' launch records')+'. Coverage: '+manifest.bbox.join(', ');
    document.getElementById('updated').textContent='Chicago fallback update: '+(flow.noaa_updated_at??'unavailable')+' · Retrieved: '+flow.retrieved_at;
    try{
      const national=await get('web/nwm/overview/manifest.json');
      const [nationalGeometry,nationalFlow]=await Promise.all([get('web/nwm/overview/'+national.geometry),get('web/nwm/overview/'+national.flow)]);
      const nationalData=rivers(nationalGeometry,nationalFlow.records);
      map.addSource('nwm-national-colors',{type:'geojson',data:nationalData});
      map.addLayer({id:'nwm-national-colors',type:'line',source:'nwm-national-colors',maxzoom:5,paint:{'line-color':['get','color'],'line-width':1.8,'line-opacity':0.95}},map.getLayer('launches')?'launches':undefined);
      const colored=nationalData.features.filter(f=>f.properties.scale_position!==null).length;
      document.getElementById('national-overview').textContent=nationalData.features.length+' national major-river reaches · '+colored+' colored · NOAA update: '+(nationalFlow.noaa_updated_at??'unavailable');
      attachLiveColors(map,text=>document.getElementById('live-status').textContent=text);
      for(const id of ['nwm-national-colors','nwm-live']){
        map.setLayoutProperty(id,'visibility',document.getElementById('noaa-comparison').checked?'none':'visible');

      }
    }catch(error){document.getElementById('national-overview').textContent='National flow snapshot unavailable; geometry remains visible.';console.warn(error);}

  }catch(e){status.textContent='NOAA data unavailable. '+(launchError?'Launch locations are also unavailable.':'Launch locations remain available.')+' Try again later.';}
});
