import {color} from './scale.mjs';
// Visual inference only. Never synthesize discharge, reference values or observations.
export function fillGaps(data,topology,maxGap=50){
  const nodes=topology?.reaches||{},features=new Map(data.features.map(f=>[String(f.properties.feature_id),f]));
  const incoming=new Map();
  for(const [id,node] of Object.entries(nodes))for(const next of node.downstream||[]){const key=String(next);if(!incoming.has(key))incoming.set(key,[]);incoming.get(key).push(id);}
  const value=f=>{const p=f?.properties;if(!p||p.inferred_position!==undefined)return null;const v=p.color_source==='Observed gauge-to-gauge'?p.observed_position:p.scale_position;return typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1?v:null;};
  const inferred=new Map();
  for(const [start,feature] of features){
    const a=value(feature);if(a===null)continue;
    let current=start;const gap=[],seen=new Set([start]);
    for(let step=0;step<=maxGap;step++){
      const next=nodes[current]?.downstream;if(next?.length!==1)break;
      const id=String(next[0]);if(seen.has(id)||incoming.get(id)?.length!==1)break;
      seen.add(id);const f=features.get(id);if(!f)break;
      const b=value(f);
      if(b!==null){
        if(gap.length&&feature.properties.color_source===f.properties.color_source)gap.forEach((reach,i)=>inferred.set(reach,{position:a+(b-a)*(i+1)/(gap.length+1),upstream:start,downstream:id}));
        break;
      }
      if(gap.length===maxGap)break;
      gap.push(id);current=id;
    }
  }
  return {...data,features:data.features.map(f=>{const p=inferred.get(String(f.properties.feature_id));return p?{...f,properties:{...f.properties,color:color(p.position),color_source:'Inferred between connected reaches',inferred_position:p.position,gap_upstream:p.upstream,gap_downstream:p.downstream}}:f;})};
}
