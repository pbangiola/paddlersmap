import test from 'node:test';
import assert from 'node:assert/strict';
import {observedPosition,applyObserved} from './gauges.mjs';
import {zoomPolicy,TIERS} from './policy.mjs';
import {color} from './scale.mjs';
const now=Date.parse('2026-10-13T12:00:00Z');
const gauge={id:'up',name:'Upstream',stage:2,low:0,flood:10,units:'ft',timestamp:'2026-10-13T11:00:00Z',reference_source:'Published stage thresholds'};
test('shared density tier boundaries and width targets',()=>{
 for(const [i,t] of TIERS.entries()){
  assert.equal(zoomPolicy(t.min).order,t.order);assert.equal(zoomPolicy(t.max-.001).order,t.order);
  if(i)assert.equal(zoomPolicy(t.min-.001).order,TIERS[i-1].order);
 }
 assert.deepEqual(TIERS.map(t=>t.width),[2,2.5,3,3.5,4,4.5]);
});
test('observed stage policy validates units, actual anchors and freshness',()=>{
 assert.equal(observedPosition(gauge,now),.2);
 for(const override of [{units:'m'},{low:null},{flood:0},{stage:NaN},{reference_source:null},{timestamp:'invalid'},{timestamp:'2026-10-10T12:00:00Z'},{timestamp:'2026-10-14T12:00:00Z'}])assert.equal(observedPosition({...gauge,...override},now),null);
 assert.equal(observedPosition({...gauge,stage:0},now),0);
});
test('average normalized endpoints on matched actual reaches; toggles and invalid endpoint restore modeled colors',()=>{
 const section={upstream:'up',downstream:'down',reach_ids:['2'],confidence:'confirmed',method:'explicit-id-directed-topology'};
 const obs={up:gauge,down:{...gauge,id:'down',stage:80,low:0,flood:100}};
 const data={type:'FeatureCollection',features:['1','2','3'].map(id=>({type:'Feature',geometry:{type:'LineString',coordinates:[[1,2],[3,4]]},properties:{feature_id:id,color:'#123456'}}))};
 const result=applyObserved(data,{sections:[section]},obs,true,now);
 assert.equal(result.features[1].properties.observed_position,.5);assert.equal(result.features[1].properties.color,color(.5));
 assert.equal(result.features[0].properties.color,'#123456');assert.equal(result.features[2].properties.color,'#123456');
 assert.deepEqual(result.features[1].geometry,data.features[1].geometry);
 for(const [assignments,readings,enabled] of [[{sections:[section]},obs,false],[{sections:[section]},{...obs,down:{...obs.down,units:'cfs'}},true],[{sections:[{...section,confidence:'candidate'}]},obs,true],[{sections:[section,section]},obs,true]]){
  assert.equal(applyObserved(data,assignments,readings,enabled,now).features[1].properties.color,'#123456');
 }
});
