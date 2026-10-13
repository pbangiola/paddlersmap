import test from 'node:test';
import assert from 'node:assert/strict';
import {position,color,COLORS,rivers} from './scale.mjs';
const record = {discharge:10,low:0,average:10,flood:30};
test('anchors, continuous interpolation and clamping', () => {
  for (const [q,p,c] of [[0,0,COLORS.low],[10,0.25,COLORS.average],[20,0.625,COLORS.elevated],[30,1,COLORS.flood],[50,1,COLORS.flood]]) {
    assert.equal(position({...record,discharge:q}),p); assert.equal(color(p),c);
  }
  assert.equal(position({...record,discharge:5}),0.125);
  assert.notEqual(color(0.125),COLORS.low);
});
test('zero flow is valid; missing, negative, equal and unordered anchors are unavailable', () => {
  assert.equal(position({...record,discharge:0}),0);
  for (const field of ['discharge','low','average','flood']) for (const value of [null,undefined,'','   ',NaN,-1,true]) assert.equal(position({...record,[field]:value}),null);
  assert.equal(position({...record,average:0}),null);
  assert.equal(position({...record,flood:5}),null);
  assert.equal(color(null),COLORS.unavailable);
});
test('join by exact feature ID without moving or mutating geometry', () => {
  const geometry={type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'LineString',coordinates:[[1,2],[3,4]]},properties:{feature_id:'123'}},{type:'Feature',geometry:null,properties:{feature_id:'456'}}]};
  const copy=JSON.stringify(geometry), result=rivers(geometry,[{...record,feature_id:123}]);
  assert.equal(result.features[0].properties.color,COLORS.average);
  assert.equal(result.features[1].properties.color,COLORS.unavailable);
  assert.deepEqual(result.features[0].geometry,geometry.features[0].geometry);
  assert.equal(JSON.stringify(geometry),copy);
});
