#!/usr/bin/env node
import fs from 'node:fs';
import {mergeReservoirContext,interpolateReservoirs} from '../../web/nwm/reservoirs.mjs';
const read=name=>JSON.parse(fs.readFileSync(new URL('../../web/nwm/reservoirs/'+name,import.meta.url)));
const bodies=read('waterbodies.geojson'),topology=read('topology.json'),flow=read('flow.json');
const data=mergeReservoirContext({features:[]},read('context.geojson'),flow.records);
const result=interpolateReservoirs(data,bodies,topology);
const summary={identified_waterbodies:bodies.features.length,ready:result.waterbodies.features.filter(f=>f.properties.available).length,inferred_channel_reaches:[...result.estimates.values()].filter(Boolean).length,context_reaches:data.features.length,routing_nodes:Object.keys(topology.reaches).length,noaa_updated_at:flow.noaa_updated_at,waterbodies:result.waterbodies.features.map(f=>({id:f.properties.waterbody_id,name:f.properties.name,available:f.properties.available,position:f.properties.inferred_position,reason:f.properties.unavailable_reason,upstream:f.properties.upstream_anchor_ids,downstream:f.properties.downstream_anchor_ids})),invalid_footprints:bodies.metadata.invalid_candidate_geometries};
fs.writeFileSync(process.argv[2]||new URL('../../docs/nwm/reservoir-validation/summary.json',import.meta.url),JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify({identified:summary.identified_waterbodies,ready:summary.ready,inferred_reaches:summary.inferred_channel_reaches,routing_nodes:summary.routing_nodes}));
