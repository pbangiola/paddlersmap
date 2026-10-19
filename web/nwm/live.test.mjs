import test from 'node:test';
import assert from 'node:assert/strict';
import {tier,cellsForBounds,normalize,loadCell,arcgis} from './live.mjs';
import {position} from './scale.mjs';

test('national tiers and bounded geographic cells avoid unsupported domains',()=>{
  assert.equal(tier(4).order,6);assert.equal(tier(6).order,5);assert.equal(tier(8).order,4);assert.equal(tier(10).order,3);
  for(const bbox of [[-170,60,-140,70],[-160,19,-155,22],[-68,17,-64,19]])assert.deepEqual(cellsForBounds(bbox,7),[]);
  const cells=cellsForBounds([-123,44,-121,46],7);
  assert.ok(cells.length>0&&cells.length<=24);
  for(const c of cells)assert.ok(c.bbox[0]<c.bbox[2]&&c.bbox[1]<c.bbox[3]);
});
test('NOAA normalization preserves zero and refuses invented central references',()=>{
  const r=normalize({feature_id:'1',latest_flow:0,prcntle_10:0,prcntle_25:5,prcntle_75:15});
  assert.equal(r.average,10);assert.equal(position({...r,flood:100}),0);
  for(const [a,b] of [[null,10],[10,5],[-1,10],[NaN,10]])assert.equal(normalize({prcntle_25:a,prcntle_75:b}).average,null);
});
test('HTTP service errors and truncated geometry remain failures',async()=>{
  await assert.rejects(arcgis('https://example.test',{},undefined,async()=>({ok:false,status:403})),/HTTP 403/);
});
test('live cells join exact IDs and reuse separately cached geometry and flow',async()=>{
  const original=globalThis.fetch,calls=[];
  const fields=['feature_id','name','strm_order','rf_2_0_17c','latest_flow','prcntle_10','prcntle_25','prcntle_75','update_time'].map(name=>({name,alias:name+' (cfs)'}));
  globalThis.fetch=async(url,options)=>{
    const params=options.body;calls.push([url,params]);let data;
    if(!url.endsWith('/query'))data={fields,maxRecordCount:2000};
    else if(params.get('returnIdsOnly'))data={objectIds:[1,2]};
    else if(params.get('objectIds'))data={features:[1,2].map(i=>({attributes:{feature_id:String(i),name:'River '+i,strm_order:5,rf_2_0_17c:100},geometry:{paths:[[[i,1],[i,2]]]}}))};
    else data={features:[{attributes:{feature_id:'1',latest_flow:0,prcntle_10:0,prcntle_25:5,prcntle_75:15,update_time:'2026-10-13 00:00:00 UTC'}}]};
    return {ok:true,status:200,json:async()=>data};
  };
  try{
    const cell={key:'test-cache',bbox:[-123,44,-122,45],order:5,z:6};
    const result=await loadCell(cell);
    assert.equal(result.features[0].properties.scale_position,0);
    assert.equal(result.features[1].properties.scale_position,null);
    assert.deepEqual(result.features[0].geometry.coordinates,[[[1,1],[1,2]]]);
    const count=calls.length;await loadCell(cell);assert.equal(calls.length,count);
    const cacheFetcher=globalThis.fetch;
    globalThis.fetch=async()=>({ok:true,status:200,json:async()=>({objectIdFieldName:'oid',objectIds:null})});
    assert.equal((await loadCell({...cell,key:'test-empty'})).features.length,0);globalThis.fetch=cacheFetcher;
    const now=Date.now,initial=now();
    try{Date.now=()=>initial+16*60*1000;await loadCell(cell);}finally{Date.now=now;}
    assert.equal(calls.length,count+1);
    assert.ok(calls.at(-1)[0].includes('ana_anomaly'));
    globalThis.fetch=async(url,options)=>({ok:true,status:200,json:async()=>options.body.get('returnIdsOnly')?{objectIds:[1]}:{exceededTransferLimit:true,features:[]}});
    await assert.rejects(loadCell({...cell,key:'test-truncated'}),/truncated/);
  }finally{globalThis.fetch=original;}
});

test('transient network errors retry without substituting data',async()=>{
  let calls=0;
  const data=await arcgis('https://example.test',{},undefined,async()=>{
    if(++calls===1)throw new TypeError('Failed to fetch');
    return {ok:true,status:200,json:async()=>({features:[]})};
  });
  assert.equal(calls,2);assert.deepEqual(data,{features:[]});
});

import {attachLiveColors} from './live.mjs';
function fakeMap(){
 const sources=new Map(),layers=new Map(),events={};
 return {events,addSource:(id,s)=>sources.set(id,{data:s.data,setData(data){this.data=data;}}),getSource:id=>sources.get(id),
 addLayer:l=>layers.set(l.id,{...l,visibility:'visible'}),getLayer:id=>layers.get(id),getLayoutProperty:id=>layers.get(id).visibility,
 on:(name,fn)=>events[name]=fn,getZoom:()=>9,getBounds:()=>({getWest:()=>-87.8,getSouth:()=>41.8,getEast:()=>-87.79,getNorth:()=>41.81}),layers};
}
test('late request cannot resurrect comparison-hidden colors',async()=>{
 const original=globalThis.document,listeners={};globalThis.document={getElementById:()=>({addEventListener:(name,fn)=>listeners[name]=fn})};
 try{
  const map=fakeMap(),pending=[];
  attachLiveColors(map,()=>{},()=>{},()=>new Promise(resolve=>pending.push(resolve)));
  assert.equal(pending.length,1);map.layers.get('nwm-live').visibility='none';await listeners.change();
  pending[0]({type:'FeatureCollection',features:[{properties:{feature_id:'old',scale_position:.5}}]});
  await new Promise(resolve=>setImmediate(resolve));assert.equal(map.getSource('nwm-live').data.features.length,0);
 }finally{globalThis.document=original;}
});
test('obsolete viewport response cannot overwrite current view',async()=>{
 const original=globalThis.document;globalThis.document={getElementById:()=>({addEventListener(){}})};
 try{
  const map=fakeMap(),pending=[];const live=attachLiveColors(map,()=>{},()=>{},()=>new Promise(resolve=>pending.push(resolve)));
  map.events.movestart();const current=live.update();assert.equal(pending.length,2);
  pending[1]({type:'FeatureCollection',features:[{properties:{feature_id:'current',scale_position:.5}}]});await current;
  pending[0]({type:'FeatureCollection',features:[{properties:{feature_id:'old',scale_position:.5}}]});await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(map.getSource('nwm-live').data.features.map(f=>f.properties.feature_id),['current']);
 }finally{globalThis.document=original;}
});
