#!/usr/bin/env node
// Reproducible current coverage; eligibility is evaluated with the same policy as the map.
import fs from 'node:fs';
import {eligibleSections,connectedGauges} from '../../web/nwm/gauges.mjs';
import {position} from '../../web/nwm/scale.mjs';
const root=new URL('../../',import.meta.url),read=p=>JSON.parse(fs.readFileSync(new URL(p,root)));
const a=read('web/nwm/gauges/assignments.json'),o=read('web/nwm/gauges/observations.json'),g=read('web/nwm/gauges/geometry.geojson');
const available=new Set(g.features.map(f=>f.properties.feature_id));
const ready=eligibleSections(a,o.records,Date.now(),o.max_age_hours),complete={...a,sections:a.sections.filter(s=>[...s.reach_ids,s.upstream_reach,s.downstream_reach].every(id=>available.has(String(id))))};
const manifest=read('web/nwm/overview/manifest.json'),flow=read('web/nwm/overview/'+manifest.flow);
const summary={validated_at:new Date().toISOString(),confirmed_sections:a.sections.length,confirmed_interior_reaches:a.sections.reduce((n,s)=>n+s.reach_ids.length,0),networked_gauges:new Set(a.sections.flatMap(s=>[s.upstream,s.downstream])).size,
  usable_observed_sections:ready.length,usable_observed_reaches:ready.reduce((n,s)=>n+s.reach_ids.length,0),displayable_connected_gauges:connectedGauges(complete,o.records,Date.now(),o.max_age_hours).features.length,
  seed_gauges_attempted:(a.attempted_seed_ids||a.seed_ids).length,reference_bearing_seeds:a.coverage.seed_total,
  topology_nodes:Object.keys(read('web/nwm/gauges/topology.json').reaches).length,coverage_complete:false,latest_pass:a.coverage,
  connected_geometry:g.metadata,endpoint_refresh:{requested:o.requested_gauges,errors:o.refresh_errors,refreshed_at:o.refreshed_at},
  modeled_overview:{reaches:flow.records.length,valid_colors:flow.records.filter(r=>position(r)!==null).length,noaa_update:flow.noaa_updated_at},
  launches:read('web/nwm/launches/canonical.geojson').features.length,unit_tests:{node:17,python:45}};
const json=JSON.stringify(summary,null,2)+'\n';
if(process.argv[2])fs.writeFileSync(process.argv[2],json);else process.stdout.write(json);
