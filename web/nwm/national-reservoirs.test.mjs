import test from 'node:test';import assert from 'node:assert/strict';
import {selectShards,combineReservoirData,freshFlow} from './national-reservoirs.mjs';
import {WIDTH,NOAA_LINE_POINTS,NOAA_EXPORT_DPI,lineLayer,TIERS} from './policy.mjs';
import {geometryTileUrl,DOMAINS} from './national.mjs';
test('our colored lines match the verified NOAA 1-point symbol at explicit 96 DPI at every tier',()=>{
 assert.equal(NOAA_LINE_POINTS,1);assert.equal(NOAA_EXPORT_DPI,96);assert.equal(WIDTH,4/3);assert.equal(lineLayer('test','source').paint['line-width'],4/3);assert.ok(TIERS.every(t=>t.width===4/3));
 const u=new URL(geometryTileUrl(DOMAINS[0],6));assert.equal(u.searchParams.get('dpi'),'96');assert.equal(JSON.parse(u.searchParams.get('dynamicLayers'))[0].drawingInfo.renderer.symbol.width,1);
});
test('viewport queries honor the same order policy, bounds and batch limit',()=>{
 const m={shards:[{key:'big',bbox:[0,0,2,2],order:8},{key:'small',bbox:[0,0,1,1],order:2},{key:'far',bbox:[20,20,21,21],order:8}]};
 assert.deepEqual(selectShards(m,[0,0,3,3],4).map(s=>s.key),['big']);assert.equal(selectShards(m,[0,0,3,3],13).length,2);assert.equal(selectShards(m,[0,0,3,3],13,1).length,1);
});
test('old or future flow snapshots cannot become invented fresh anchors',()=>{
 const now=Date.parse('2026-10-19T12:00:00Z'),f={records:[{feature_id:'1'}],retrieved_at:'2026-10-19T11:00:00Z'};assert.equal(freshFlow(f,now),f);
 for(const retrieved_at of ['2026-10-15T00:00:00Z','2026-10-20T00:00:00Z',undefined])assert.deepEqual(freshFlow({...f,retrieved_at},now).records,[]);
});
test('datasets merge without mutation, retain the newest actual values and withhold conflicting topology',()=>{
 const seed={waterbodies:{features:[{properties:{waterbody_id:'lake'}}]},geometry:{features:[{properties:{feature_id:'1'}}]},topology:{reaches:{'1':{downstream:['2']}}},flow:{records:[{feature_id:'1',discharge:0}],retrieved_at:'2026-10-19T10:00:00Z'}},before=JSON.stringify(seed);
 const other={...seed,topology:{reaches:{'1':{downstream:['3']}}},flow:{records:[{feature_id:'1',discharge:5}],retrieved_at:'2026-10-19T11:00:00Z'}};
 const r=combineReservoirData([seed,other]);assert.equal(r.waterbodies.features.length,1);assert.equal(r.geometry.features.length,1);assert.equal(r.flow.records[0].discharge,5);assert.equal(r.topology.reaches['1'],undefined);assert.equal(JSON.stringify(seed),before);
});
test('viewport loader reuses static geometry and flow caches across moves and drops offscreen shards',async()=>{
 const {attachNationalReservoirs}=await import('./national-reservoirs.mjs');
 const originalSet=globalThis.setInterval,originalClear=globalThis.clearInterval;globalThis.setInterval=()=>0;globalThis.clearInterval=()=>{};
 const events={},calls=[],outputs=[];let box=[0,0,2,2];const map={on:(event,fn)=>events[event]=fn,getZoom:()=>8,getBounds:()=>({getWest:()=>box[0],getSouth:()=>box[1],getEast:()=>box[2],getNorth:()=>box[3]})};
 const manifest={shards:[{key:'s',bbox:[0,0,1,1],order:8,updated_at:'version',static:'shards/s/static.json',flow:'shards/s/flow.json'}]};
 const fetcher=async path=>{calls.push(path);const data=path.endsWith('manifest.json')?manifest:path.includes('static.json')?{waterbodies:{features:[{properties:{waterbody_id:'x'}}]},context:{features:[]},topology:{reaches:{}}}:{records:[],retrieved_at:new Date().toISOString()};return {ok:true,json:async()=>data};};
 try{
  const loader=attachNationalReservoirs(map,data=>outputs.push(data),()=>{},fetcher);await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(outputs.at(-1).waterbodies.features.length,1);const count=calls.length;
  box=[10,10,11,11];await loader.update();assert.equal(outputs.at(-1).waterbodies.features.length,0);
  box=[0,0,2,2];await loader.update();assert.equal(calls.length,count);assert.equal(outputs.at(-1).waterbodies.features.length,1);events.remove();
 }finally{globalThis.setInterval=originalSet;globalThis.clearInterval=originalClear;}
});
