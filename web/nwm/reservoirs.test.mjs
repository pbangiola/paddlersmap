import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeReservoirContext,interpolateReservoirs,applyReservoirColors} from './reservoirs.mjs';
const f=(id,position=null,length=2,order=5)=>({type:'Feature',geometry:{type:'LineString',coordinates:[[0,0],[1,1]]},properties:{feature_id:id,order,length_km:length,scale_position:position,color_source:'Modeled NWM',discharge:null}});
const graph=()=>({reaches:{a:{upstream:[],downstream:['b']},b:{upstream:['a'],downstream:['c']},c:{upstream:['b'],downstream:['z']},z:{upstream:['c'],downstream:[]}}});
const bodies=()=>({type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0]]]},properties:{waterbody_id:'lake',name:'Example',order:5,reach_ids:['b','c']}}]});
const data=()=>({features:[f('a',0),f('b'),f('c',null,6),f('z',1)]});
test('reservoir gray reaches interpolate directed distances; surface is endpoint mean; no flow values or geometry invented',()=>{
 const input=data(),before=JSON.stringify(input),result=interpolateReservoirs(input,bodies(),graph()),out=applyReservoirColors(input,result.estimates);
 assert.equal(result.waterbodies.features[0].properties.inferred_position,.5);
 assert.equal(out.features[1].properties.inferred_position,.2);assert.equal(out.features[2].properties.inferred_position,.6);
 assert.equal(out.features[1].properties.discharge,null);assert.equal(out.features[1].properties.scale_position,null);
 assert.equal(out.features[1].geometry,input.features[1].geometry);assert.equal(JSON.stringify(input),before);
 assert.deepEqual(result.waterbodies.features[0].properties.upstream_anchor_ids,['a']);
});
test('mainstem reservoir estimate excludes minor tributary anchors and preserves existing real colors',()=>{
 const input=data(),t=graph();input.features.push(f('tributary',1,2,1));t.reaches.b.upstream.push('tributary');
 input.features[2].properties.scale_position=.7;
 const result=interpolateReservoirs(input,bodies(),t),out=applyReservoirColors(input,result.estimates);
 assert.equal(result.waterbodies.features[0].properties.available,true);assert.equal(out.features[2],input.features[2]);
 assert.equal(out.features.at(-1),input.features.at(-1));assert.equal(result.estimates.has('tributary'),false);
});
test('missing boundaries, cycles, unknown stream order and mixed incompatible anchors stay explicitly unavailable',()=>{
 for(const mutate of [(d,t)=>{d.features[0].properties.scale_position=null;},(d,t)=>{t.reaches.b.upstream=['c'];},(d,t)=>{delete t.reaches.b;},(d,t)=>{d.features[0].properties.order=undefined;},(d,t)=>{d.features[0].properties.scale_position=null;d.features[0].properties.color_source='Observed gauge-to-gauge';d.features[0].properties.observed_position=0;}]){
  const d=data(),t=graph();mutate(d,t);const result=interpolateReservoirs(d,bodies(),t);
  assert.equal(result.waterbodies.features[0].properties.available,false);assert.equal(result.estimates.size,0);
 }
});
test('equal zero anchors are valid, observed anchors stay separate from modeled values',()=>{
 const d=data();d.features[0].properties.color_source=d.features[3].properties.color_source='Observed gauge-to-gauge';d.features[0].properties.observed_position=d.features[3].properties.observed_position=0;
 const r=interpolateReservoirs(d,bodies(),graph());assert.equal(r.waterbodies.features[0].properties.inferred_position,0);assert.equal(r.waterbodies.features[0].properties.anchor_mode,'observed');
});
test('overlapping waterbody memberships are withheld',()=>{
 const b=bodies();b.features.push({...b.features[0],properties:{...b.features[0].properties,waterbody_id:'other'}});
 const r=interpolateReservoirs(data(),b,graph());assert.equal(r.estimates.size,0);assert.ok(r.waterbodies.features.every(f=>!f.properties.available));
});
test('static reservoir context joins exact flow IDs while preserving original source features',()=>{
 const geometry={features:[f('b'),f('c')]},source={features:[f('b',.25)]},before=JSON.stringify(source);
 const result=mergeReservoirContext(source,geometry,[{feature_id:'c',discharge:10,low:0,average:10,flood:100}]);
 assert.equal(result.features.find(f=>f.properties.feature_id==='c').properties.scale_position,.25);assert.equal(result.features.find(f=>f.properties.feature_id==='b').properties.scale_position,.25);assert.equal(JSON.stringify(source),before);
});
test('upstream order changes follow published dominant inflows instead of silently inventing a same-order connection',()=>{
 const d=data();d.features[0].properties.order=4;
 const r=interpolateReservoirs(d,bodies(),graph());assert.equal(r.waterbodies.features[0].properties.available,true);assert.equal(r.waterbodies.features[0].properties.inferred_position,.5);
});
test('braided main channels can reconverge at a shared real bracket, but missing length/depth stay unavailable',()=>{
 const d=data(),t=graph(),b=bodies();d.features.push(f('branch'));t.reaches.b.downstream=['c','branch'];t.reaches.branch={upstream:['b'],downstream:['z']};t.reaches.z.upstream.push('branch');b.features[0].properties.reach_ids.push('branch');
 assert.equal(interpolateReservoirs(d,b,t).waterbodies.features[0].properties.available,true);
 delete d.features[1].properties.length_km;assert.equal(interpolateReservoirs(d,b,t).waterbodies.features[0].properties.available,false);
 assert.equal(interpolateReservoirs(data(),bodies(),graph(),0).waterbodies.features[0].properties.available,false);
});
