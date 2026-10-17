#!/usr/bin/env python3
"""Build static assignments from explicit gauge IDs and documented directed NWM topology.

No spatial/name inference. Geometry is rendered separately from the NWM sources.
"""
import argparse,json,math
from pathlib import Path
from datetime import datetime,timezone

def assignments(topology,gauges,max_reaches=10000):
    if topology.get('method')!='published-directed-nwm' or not topology.get('source'):
        raise ValueError('Documented published directed NWM topology is required')
    reaches=topology['reaches'];by_reach={};rejected=[];sections=[]
    identities={}
    for gauge in gauges:identities.setdefault(gauge['id'],set()).add(str(gauge.get('reach_id','')))
    ambiguous={gid for gid,rids in identities.items() if len(rids)!=1}
    for gauge in gauges:
        rid=str(gauge.get('reach_id',''))
        if gauge['id'] in ambiguous:
            rejected.append({'gauge':gauge['id'],'reason':'Gauge identity maps to multiple NWM reaches'});continue
        if gauge.get('match_method')!='published-reach-id' or rid not in reaches:
            rejected.append({'gauge':gauge['id'],'reason':'No validated explicit NWM reach ID'});continue
        by_reach.setdefault(rid,[]).append(gauge)
    for start,gs in by_reach.items():
        if len(gs)!=1:
            rejected.append({'reach':start,'reason':'Multiple gauges on one reach; within-reach order unknown'});continue
        path=[];seen={start};current=start;reason='No downstream bracketing gauge within available topology'
        for _ in range(max_reaches):
            edges=reaches[current].get('downstream')
            if not isinstance(edges,list) or len(edges)!=1:
                reason='Missing or ambiguous downstream direction';break
            nxt=str(edges[0])
            if nxt in seen or nxt not in reaches:
                reason='Cycle or incomplete topology';break
            seen.add(nxt);current=nxt
            if current in by_reach:
                endpoints=by_reach[current]
                if len(endpoints)!=1:reason='Ambiguous downstream gauges';break
                # Exclude both endpoint reaches: exact gauge location within them is unknown.
                if not path:reason='No complete reach lies between endpoint gauges';break
                sections.append({'upstream':gs[0]['id'],'downstream':endpoints[0]['id'],'reach_ids':path,
                    'confidence':'confirmed','method':'explicit-id-directed-topology','topology_source':topology['source'],
                    'upstream_reach':start,'downstream_reach':current,
                    'match_evidence':[gs[0]['match_source'],endpoints[0]['match_source']]});reason=None;break
            path.append(current)
        else:reason='Routing bound exceeded'
        if reason:rejected.append({'gauge':gs[0]['id'],'reason':reason})
    # Conflicting bracket claims cannot color a reach.
    counts={}
    for s in sections:
        for rid in s['reach_ids']:counts[rid]=counts.get(rid,0)+1
    safe=[]
    for s in sections:
        if any(counts[r]>1 for r in s['reach_ids']):rejected.append({'section':[s['upstream'],s['downstream']],'reason':'Overlapping bracket assignments'})
        else:safe.append(s)
    return {'sections':safe,'rejected':rejected,'topology_source':topology['source']}

def observations(root):
    # Existing NOAA import labels primary observations as stage without retaining units.
    # Do not infer feet from an unsuffixed reading. Only explicitly unit-qualified records pass.
    records={};candidates=[]
    minima=json.loads((root/'data/stage_minima.json').read_text()).get('stations',{})
    flood=json.loads((root/'data/flood_stages_il.json').read_text()).get('stations',{})
    for filename in ['noaa_gauges.geojson','gauges.geojson']:
        for f in json.loads((root/'data'/filename).read_text())['features']:
            p=f['properties'];gid=str(p.get('noaa_lid') or p.get('site'))
            lo=p.get('low_water_stage_ft');ref='NOAA NWPS published low-water and flood-stage thresholds'
            if lo is None:rec=minima.get(str(p.get('site') or gid),{});lo=rec.get('minimum_ft') if rec.get('observed_adequate_75pct_distributed') or rec.get('daily_adequate_75pct_distributed') else None;ref='Repository stage_minima atlas and official flood stage'
            records[gid]={'id':gid,'name':p.get('name'),'stage':p.get('stage'),'timestamp':p.get('stage_time'),
                'low':lo,'flood':p.get('flood_stage_ft') or flood.get(gid,{}).get('flood_stage_ft'),
                'units':'ft' if filename=='gauges.geojson' else p.get('stage_units'),'reference_source':ref}
            if p.get('reach_id') is not None:candidates.append({'id':gid,'reach_id':str(p['reach_id']),
                'match_method':'published-reach-id','match_source':'NOAA NWPS reachId in data/'+filename})
    return {'records':records,'max_age_hours':36},candidates

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--topology',type=Path);p.add_argument('--observations-only',action='store_true');p.add_argument('--output',type=Path,default=Path('web/nwm/gauges'));a=p.parse_args()
    active=a.output/'assignments.json'
    if not a.topology and active.exists() and json.loads(active.read_text()).get('sections'):
        if a.observations_only:
            try:from .connections import fetch_observations
            except ImportError:from connections import fetch_observations
            fetch_observations(a.output,Path('.'),Path('local/output/nwm-connections'));return
        raise ValueError('Confirmed paths already exist; use connections.py to expand them, not an empty topology rebuild')
    obs,candidates=observations(Path('.'));a.output.mkdir(parents=True,exist_ok=True)
    if a.observations_only:
        atomic_obs=a.output/'observations.json';temp=atomic_obs.with_suffix('.tmp');temp.write_text(json.dumps(obs,separators=(',',':'))+'\n');temp.replace(atomic_obs);return
    if a.topology:result=assignments(json.loads(a.topology.read_text()),candidates)
    else:result={'sections':[],'rejected':[], 'limitation':'Observed routing unavailable: NOAA static flowline service has no directed connectivity fields. Existing gauge graph is not verified NWM topology. Existing NWPS import omits primary units. Modeled NWM fallback remains active.'}
    result['candidate_count']=len(candidates);result['built_at']=datetime.now(timezone.utc).isoformat()
    for name,data in [('assignments.json',result),('observations.json',obs)]:
        target=a.output/name;temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data,separators=(',',':'))+'\n');temp.replace(target)
    print(len(result['sections']),'confirmed sections;',len(candidates),'explicit-ID candidates')
if __name__=='__main__':main()
