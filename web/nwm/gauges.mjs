import {color} from './scale.mjs';
export const MAX_AGE_HOURS=36; // Existing atlas report freshness policy.
const numeric=v=>typeof v==='number'&&Number.isFinite(v);
export function observedPosition(gauge,now=Date.now(),maxAgeHours=MAX_AGE_HOURS){
  if(!gauge||gauge.units!=='ft'||!gauge.reference_source)return null;
  const {stage,low,flood,timestamp}=gauge;
  const time=Date.parse(timestamp),age=now-time;
  if(!numeric(stage)||!numeric(low)||!numeric(flood)||flood<=0||flood<=low||!Number.isFinite(time)||age<0||age>maxAgeHours*3600000)return null;
  return Math.max(0,Math.min(1,(stage-low)/(flood-low)));
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
