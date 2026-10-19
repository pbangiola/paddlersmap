// One density policy for raster geometry and every custom vector renderer.
// NOAA ArcGIS line symbols use points; 96 DPI exports convert 1 pt to 4/3 CSS pixels.
export const NOAA_LINE_POINTS=1;
export const NOAA_EXPORT_DPI=96;
export const WIDTH=NOAA_LINE_POINTS*NOAA_EXPORT_DPI/72;
export const TIERS=[{min:0,max:5,order:6,width:WIDTH},{min:5,max:7,order:5,width:WIDTH},{min:7,max:9,order:4,width:WIDTH},{min:9,max:11,order:3,width:WIDTH},{min:11,max:13,order:2,width:WIDTH},{min:13,max:24,order:1,width:WIDTH}];
export function zoomPolicy(zoom){return TIERS.find(t=>zoom<t.max)||TIERS.at(-1);}
export const ORDER_FILTER=['>=',['to-number',['get','order'],0],6];
export function lineLayer(id,source,extra={}){return {id,type:'line',source,layout:{'line-cap':'round','line-join':'round'},filter:ORDER_FILTER,paint:{'line-color':['get','color'],'line-width':WIDTH},...extra};}
