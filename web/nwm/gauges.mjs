import {color} from './scale.mjs';
export const MAX_AGE_HOURS=36; // Existing atlas report freshness policy.
const numeric=v=>typeof v==='number'&&Number.isFinite(v);
export function observedPosition(gauge,now=Date.now(),maxAgeHours=MAX_AGE_HOURS){
  if(!gauge||gauge.units!=='ft'||!gauge.reference_source)return null;
  if((gauge.low_units!==undefined&&gauge.low_units!=='ft')||(gauge.flood_units!==undefined&&gauge.flood_units!=='ft'))return null;
  const {stage,low,flood,timestamp}=gauge;
  const time=Date.parse(timestamp),age=now-time;
  if(!numeric(stage)||!numeric(low)||!numeric(flood)||flood<=0||flood<=low||!Number.isFinite(time)||age<0||age>maxAgeHours*3600000)return null;
  return Math.max(0,Math.min(1,(stage-low)/(flood-low)));
}
export function eligibleSections(assignments,observations,now=Date.now(),maxAgeHours=MAX_AGE_HOURS){
  const ready=(assignments.sections||[]).filter(s=>s.confidence==='confirmed'&&s.method==='explicit-id-directed-topology'&&s.reach_ids?.length&&[s.upstream,s.downstream].every(id=>observedPosition(observations[id],now,maxAgeHours)!==null));
  const counts=new Map();for(const s of ready)for(const id of s.reach_ids)counts.set(String(id),(counts.get(String(id))||0)+1);
  return ready.filter(s=>s.reach_ids.every(id=>counts.get(String(id))===1));
}
export function connectedGauges(assignments,observations,now=Date.now(),maxAgeHours=MAX_AGE_HOURS){
  const gauges=new Map();
  for(const section of eligibleSections(assignments,observations,now,maxAgeHours))for(const id of [section.upstream,section.downstream]){
    const o=observations[id],xy=o.coordinates;
    if(!Array.isArray(xy)||xy.length!==2||!xy.every(numeric)||Math.abs(xy[0])>180||Math.abs(xy[1])>90)continue;
    const old=gauges.get(id),links=old?.properties.sections||[];
    gauges.set(id,{type:'Feature',geometry:{type:'Point',coordinates:[...xy]},properties:{...o,position:observedPosition(o,now,maxAgeHours),color:color(observedPosition(o,now,maxAgeHours)),sections:[...links,section.upstream+' → '+section.downstream]}});
  }
  return {type:'FeatureCollection',features:[...gauges.values()]};
}
// Merge only eligible observed reaches into the existing sources, using modeled attributes when present.
export function mergeConnected(data,geometry,assignments,observations,enabled=true,now=Date.now(),maxAgeHours=MAX_AGE_HOURS){
  if(!enabled||!geometry)return data;
  const ids=new Set(eligibleSections(assignments,observations,now,maxAgeHours).flatMap(s=>[...s.reach_ids,s.upstream_reach,s.downstream_reach].filter(id=>id!==undefined&&id!==null).map(String)));
  const features=new Map((geometry.features||[]).filter(f=>ids.has(String(f.properties.feature_id))).map(f=>[String(f.properties.feature_id),{...f,properties:{...f.properties,scale_position:null,color:'#88929b'}}]));
  for(const f of data.features)features.set(String(f.properties.feature_id),f);
  return {...data,features:[...features.values()]};
}
export function applyObserved(data,assignments,observations,enabled=true,now=Date.now(),maxAgeHours=MAX_AGE_HOURS){
  const byReach=new Map(),conflicts=new Set();
  if(enabled)for(const section of assignments.sections||[]){
    if(section.confidence!=='confirmed'||section.method!=='explicit-id-directed-topology')continue;
    const a=observations[section.upstream],b=observations[section.downstream];
    const up=observedPosition(a,now,maxAgeHours),down=observedPosition(b,now,maxAgeHours);
    if(up===null||down===null)continue;
    for(const id of section.reach_ids){if(byReach.has(String(id)))conflicts.add(String(id));else byReach.set(String(id),{section,a,b,up,down});}
  }
  return {...data,features:data.features.map(f=>{
    const id=String(f.properties.feature_id),match=conflicts.has(id)?null:byReach.get(id);
    if(!match)return {...f,properties:{...f.properties,color_source:'Modeled NWM'}};
    const {section,a,b,up,down}=match,p=(up+down)/2;
    return {...f,properties:{...f.properties,color:color(p),color_source:'Observed gauge-to-gauge',observed_position:p,
      gauge_provenance:JSON.stringify({...section,upstream_observation:{...a,position:up},downstream_observation:{...b,position:down}})}};
  })};
}
