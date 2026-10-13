// NOAA renders its own geographic flowlines; no national GeoJSON download.
export const NATIONAL_BOUNDS=[[-125,24],[-66,50]];
export const DOMAINS=[
  {id:'conus',service:'static_nwm_flowlines',bounds:NATIONAL_BOUNDS},
  {id:'alaska',service:'static_nwm_flowlines_ak',bounds:[[-180,50],[-129,72]]},
  {id:'hawaii',service:'static_nwm_flowlines_hi',bounds:[[-160.5,18.8],[-154.5,22.5]]},
  {id:'prvi',service:'static_nwm_flowlines_prvi',bounds:[[-68.1,17.6],[-64.4,18.6]]}
];
export function geometryTileUrl(domain,detail=false){
  // NOAA's default minimum scale suppresses lines at a nationwide tile zoom.
  // A dynamic layer removes that cutoff. Broad zooms show major waterways;
  // detail zooms request all stream orders. NOAA still serves bounded tiles.
  const layer={id:0,source:{type:'mapLayer',mapLayerId:0},minScale:0,maxScale:0,
    definitionExpression:detail?'1=1':'strm_order >= 4',
    drawingInfo:{renderer:{type:'simple',symbol:{type:'esriSLS',style:'esriSLSSolid',color:[136,146,155,255],width:detail?0.7:0.9}}}};
  return 'https://maps.water.noaa.gov/server/rest/services/reference/'+domain.service+'/MapServer/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256&format=png32&transparent=true&f=image&dynamicLayers='+encodeURIComponent(JSON.stringify([layer]));
}
export function addNationalGeometry(map,before){
  for(const domain of DOMAINS)for(const detail of [false,true]){
    const id='national-'+domain.id+(detail?'-detail':'');
    map.addSource(id,{type:'raster',tileSize:256,bounds:domain.bounds.flat(),tiles:[geometryTileUrl(domain,detail)]});
    map.addLayer({id,type:'raster',source:id,minzoom:detail?7:0,maxzoom:detail?24:7,paint:{'raster-fade-duration':0}},before);
  }
}
