import {TIERS,NOAA_LINE_POINTS,NOAA_EXPORT_DPI} from './policy.mjs';
// NOAA renders its own geographic flowlines; no national GeoJSON download.
export const NATIONAL_BOUNDS=[[-125,24],[-66,50]];
export const DOMAINS=[
  {id:'conus',service:'static_nwm_flowlines',bounds:NATIONAL_BOUNDS},
  {id:'alaska',service:'static_nwm_flowlines_ak',bounds:[[-180,50],[-129,72]]},
  {id:'hawaii',service:'static_nwm_flowlines_hi',bounds:[[-160.5,18.8],[-154.5,22.5]]},
  {id:'prvi',service:'static_nwm_flowlines_prvi',bounds:[[-68.1,17.6],[-64.4,18.6]]}
];
export function geometryTileUrl(domain,order=7){
  const layer={id:0,source:{type:'mapLayer',mapLayerId:0},minScale:0,maxScale:0,
    definitionExpression:'strm_order >= '+order,
    drawingInfo:{renderer:{type:'simple',symbol:{type:'esriSLS',style:'esriSLSSolid',color:[136,146,155,255],width:NOAA_LINE_POINTS}}}};
  return 'https://maps.water.noaa.gov/server/rest/services/reference/'+domain.service+'/MapServer/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&dpi='+NOAA_EXPORT_DPI+'&format=png32&transparent=true&f=image&dynamicLayers='+encodeURIComponent(JSON.stringify([layer]));
}
export function addNationalGeometry(map,before){
  const ids=[];
  for(const domain of DOMAINS)for(const tier of TIERS){
    const id='national-'+domain.id+'-'+tier.order;ids.push(id);
    map.addSource(id,{type:'raster',tileSize:256,bounds:domain.bounds.flat(),tiles:[geometryTileUrl(domain,tier.order)]});
    map.addLayer({id,type:'raster',source:id,minzoom:tier.min,maxzoom:tier.max,paint:{'raster-fade-duration':0}},before);
  }
  return ids;
}
