// One density policy for raster geometry and every custom vector renderer.
export const TIERS=[{min:0,max:5,order:7,width:2},{min:5,max:7,order:6,width:2.5},{min:7,max:9,order:5,width:3},{min:9,max:11,order:4,width:3.5},{min:11,max:13,order:3,width:4},{min:13,max:24,order:1,width:4.5}];
export function zoomPolicy(zoom){return TIERS.find(t=>zoom<t.max)||TIERS.at(-1);}
export const WIDTH=['interpolate',['linear'],['zoom'],4,2,5,2.5,7,3,9,3.5,11,4,13,4.5];
export const ORDER_FILTER=['>=',['to-number',['get','order'],0],7];
export function lineLayer(id,source,extra={}){return {id,type:'line',source,layout:{'line-cap':'round','line-join':'round'},filter:ORDER_FILTER,paint:{'line-color':['get','color'],'line-width':WIDTH},...extra};}
