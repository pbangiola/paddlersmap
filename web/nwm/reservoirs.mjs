import {color,rivers} from './scale.mjs';
const finite=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
// Dedicated geometry and flow snapshots stay separate. Existing real values take precedence.
export function mergeReservoirContext(data,geometry,records){
 if(!geometry)return data;
 const context=rivers(geometry,records||[]),features=new Map(context.features.map(f=>[String(f.properties.feature_id),f]));
 for(const f of data.features){const old=features.get(String(f.properties.feature_id));features.set(String(f.properties.feature_id),old?{...f,geometry:old.geometry,properties:{...old.properties,...f.properties}}:f);}
 return {...data,features:[...features.values()]};
}
// Reservoir-specific visual estimates may span braided main channels and minor tributary joins.
// Only published edges at least as large as the identified mainstem are followed.
export function interpolateReservoirs(data,waterbodies,topology,maxDepth=50){
 const features=new Map(data.features.map(f=>[String(f.properties.feature_id),f])),nodes=topology?.reaches||{},estimates=new Map();
 const claims=new Map();for(const body of waterbodies?.features||[])for(const id of body.properties.reach_ids||[])claims.set(String(id),(claims.get(String(id))||0)+1);
 const bodies=(waterbodies?.features||[]).map(body=>{
  const p=body.properties,members=new Set(p.reach_ids||[]),minimum=p.order;
  if([...members].some(id=>claims.get(String(id))>1))return {...body,properties:{...p,color:color(null),available:false,color_source:'Reservoir estimate unavailable',unavailable_reason:'Ambiguous overlapping waterbody membership'}};
  const length=id=>{const n=features.get(id)?.properties.length_km;return typeof n==='number'&&Number.isFinite(n)&&n>0?n:0;};
  const value=(id,mode)=>{const a=features.get(id)?.properties;if(!a)return null;if(mode==='observed')return a.color_source==='Observed gauge-to-gauge'&&finite(a.observed_position)?a.observed_position:null;return finite(a.scale_position)?a.scale_position:null;};
  function walk(id,direction,mode,distance=0,trail=new Set()){
   if(++calls>2000)throw Error('Routing search budget exhausted');
   if(trail.has(id))throw Error('Cyclic published boundary routing at '+id);
   if(trail.size>=maxDepth)throw Error('Boundary search depth limit reached at '+id);
   if(!members.has(id)&&value(id,mode)!==null)return [{id,position:value(id,mode),distance:distance+length(id)/2}];
   const node=nodes[id];if(!node)throw Error('Published boundary routing unavailable');
   const edges=node[direction];if(!Array.isArray(edges))throw Error('Published boundary routing unavailable');
   let eligible=edges.filter(next=>{
    const order=features.get(next)?.properties.order??node[direction+'_orders']?.[next];
    if(!Number.isFinite(order))throw Error('Boundary stream order unavailable');
    return features.get(next)?.properties.priority_mainstem===true||order>=minimum;
   });
   if(!eligible.length&&direction==='upstream'&&(members.has(id)||features.get(id)?.properties.priority_mainstem)){
    const orders=edges.map(next=>features.get(next)?.properties.order??node.upstream_orders?.[next]);
    const largest=Math.max(...orders);if(Number.isFinite(largest)&&largest>0)eligible=edges.filter((next,i)=>orders[i]===largest);
   }
   if(!eligible.length)throw Error('No bracket on the main channel at '+id+' '+direction);
   const nextTrail=new Set(trail);nextTrail.add(id);
   return eligible.flatMap(next=>walk(String(next),direction,mode,distance+length(id),nextTrail));
  }
  const unique=anchors=>{const m=new Map();for(const a of anchors)if(!m.has(a.id)||m.get(a.id).distance>a.distance)m.set(a.id,a);return [...m.values()];};
  const mean=anchors=>anchors.reduce((sum,a)=>sum+a.position,0)/anchors.length;
  let calls=0;
  let chosen=null,reason='Numerical inlet/outlet references unavailable';
  for(const mode of ['observed','modeled']){
   calls=0;
   try{
    if(!members.size||!Number.isFinite(minimum))throw Error('Waterbody membership unavailable');
    const perReach=new Map(),ups=[],downs=[];
    for(const id of members){
     if(length(id)<=0)throw Error('Actual channel length unavailable');
     const up=unique(walk(id,'upstream',mode,-length(id)/2)),down=unique(walk(id,'downstream',mode,-length(id)/2));
     const du=Math.min(...up.map(a=>a.distance)),dd=Math.min(...down.map(a=>a.distance)),t=du+dd>0?du/(du+dd):.5;
     perReach.set(id,{position:mean(up)*(1-t)+mean(down)*t,up,down});ups.push(...up);downs.push(...down);
    }
    chosen={mode,perReach,up:unique(ups),down:unique(downs)};break;
   }catch(error){reason=error.message;}
  }
  if(!chosen)return {...body,properties:{...p,color:color(null),available:false,color_source:'Reservoir estimate unavailable',unavailable_reason:reason}};
  const {mode,up,down,perReach}=chosen,position=(mean(up)+mean(down))/2;
  for(const [id,a] of perReach){const f=features.get(id);if(!f)continue;
   // Preserve all real colors and all underlying discharge/reference/observation values.
   if(finite(f.properties.scale_position)||f.properties.color_source==='Observed gauge-to-gauge'&&finite(f.properties.observed_position))continue;
   if(estimates.has(id)){estimates.set(id,null);continue;} // Overlapping waterbody claims are withheld.
   estimates.set(id,{position:a.position,waterbody_id:p.waterbody_id,name:p.name,up:a.up.map(v=>v.id),down:a.down.map(v=>v.id),mode});
  }
  return {...body,properties:{...p,color:color(position),available:true,color_source:'Inferred reservoir color',inferred_position:position,anchor_mode:mode,anchor_provenance:JSON.stringify({upstream:up.map(a=>features.get(a.id).properties),downstream:down.map(a=>features.get(a.id).properties)}),upstream_anchor_ids:up.map(a=>a.id),downstream_anchor_ids:down.map(a=>a.id),upstream_position:mean(up),downstream_position:mean(down),method:'Main-channel inlet/outlet normalized-position mean; reach colors use directed distance'}};
 });
 return {waterbodies:{type:'FeatureCollection',features:bodies},estimates};
}
export function applyReservoirColors(data,estimates){
 return {...data,features:data.features.map(f=>{const e=estimates.get(String(f.properties.feature_id));if(!e)return f;
  return {...f,properties:{...f.properties,color:color(e.position),color_source:'Inferred reservoir color',inferred_position:e.position,reservoir_id:e.waterbody_id,reservoir_name:e.name,anchor_mode:e.mode,gap_upstream:e.up.join(', '),gap_downstream:e.down.join(', '),inference_method:'Directed channel-distance interpolation across NOAA waterbody'}};
 })};
}
