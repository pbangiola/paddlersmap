import test from 'node:test';
import assert from 'node:assert/strict';
import {fillGaps} from './gaps.mjs';
import {color} from './scale.mjs';
const feature=(id,p=null,source='Modeled NWM')=>({type:'Feature',geometry:{type:'LineString',coordinates:[[0,0],[1,1]]},properties:{feature_id:id,scale_position:p,color:color(p),color_source:source,discharge:null}});
const graph={reaches:{a:{downstream:['b']},b:{downstream:['c']},c:{downstream:['d']},d:{downstream:[]}}};
test('bracketed gray gaps interpolate scale positions without creating flow measurements or changing geometry',()=>{
 const data={features:[feature('a',0),feature('b'),feature('c'),feature('d',1)]},before=JSON.stringify(data),out=fillGaps(data,graph);
 assert.equal(out.features[1].properties.inferred_position,1/3);assert.equal(out.features[2].properties.inferred_position,2/3);
 assert.equal(out.features[1].properties.discharge,null);assert.equal(out.features[1].properties.scale_position,null);
 assert.equal(out.features[1].geometry,data.features[1].geometry);assert.equal(JSON.stringify(data),before);
 assert.equal(out.features[1].properties.gap_upstream,'a');assert.equal(out.features[1].properties.gap_downstream,'d');
});
test('one-sided, branching, confluence, cycles, mixed scales, absent geometry and excessive gaps stay unavailable',()=>{
 const data={features:[feature('a',0),feature('b'),feature('c'),feature('d',1)]};
 const cases=[{data:{features:data.features.slice(0,3)},graph}, {data,graph:{reaches:{...graph.reaches,b:{downstream:['c','x']}}}}, {data,graph:{reaches:{...graph.reaches,x:{downstream:['c']}}}}, {data,graph:{reaches:{...graph.reaches,c:{downstream:['a']}}}}, {data:{features:[...data.features.slice(0,3),feature('d',1,'Other scale')]},graph}, {data:{features:data.features.filter(f=>f.properties.feature_id!=='c')},graph}];
 for(const c of cases)assert.ok(fillGaps(c.data,c.graph).features.every(f=>f.properties.inferred_position===undefined));
 assert.ok(fillGaps(data,graph,1).features.every(f=>f.properties.inferred_position===undefined));
 assert.ok(fillGaps(data,null).features.every(f=>f.properties.inferred_position===undefined));
});
test('zero observed positions remain valid anchors and are never replaced by modeled positions',()=>{
 const a=feature('a',1,'Observed gauge-to-gauge'),d=feature('d',1,'Observed gauge-to-gauge');a.properties.observed_position=0;d.properties.observed_position=1;
 const out=fillGaps({features:[a,feature('b'),feature('c'),d]},graph);assert.equal(out.features[1].properties.inferred_position,1/3);
});
