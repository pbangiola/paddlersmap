#!/usr/bin/env python3
"""Bounded, checkpointed NOAA NWPS reach routing and unit-qualified observations.

Only /reaches/{id}.route.downstream supplies edges; no geographic/name matching.
Raw routing caches are static and independent of current gauge detail responses.
"""
import argparse
import concurrent.futures
import json
import math
import time
import threading
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from .gauge_assignments import assignments, observations
except ImportError:  # Direct script execution.
    from gauge_assignments import assignments, observations

BASE = 'https://api.water.noaa.gov/nwps/v1'
DOCS = BASE + '/docs/'
ROOT = Path(__file__).resolve().parents[2]
SENTINELS = {-999, -9999, -99999, -999999}
RATE_PAUSED = threading.Event()


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) and n not in SENTINELS else None
    except (ValueError, TypeError):
        return None


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n')
    tmp.replace(path)


def get(path):
    # Sequential attempts per worker; at most three workers, bounded timeout/backoff.
    for attempt in range(3):
        if RATE_PAUSED.is_set():
            raise OSError('NOAA requested a long retry delay; resume the checkpoint in a later run')
        try:
            req = urllib.request.Request(BASE + path, headers={'User-Agent': 'PaddlersMap-NWM-prototype/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.load(response)
        except (OSError, ValueError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            retry = exc.headers.get('Retry-After') if isinstance(exc, urllib.error.HTTPError) else None
            delay = 0
            if retry:
                try:
                    delay = int(retry) if retry.isdigit() else max(0, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError):
                    pass
            if delay > 30:
                RATE_PAUSED.set()
                raise
            time.sleep(max(2 ** attempt, delay))


def parse_reach(detail, rid):
    if str(detail.get('reachId')) != rid:
        raise ValueError('NOAA returned a different reach ID')
    edges = detail.get('route', {}).get('downstream')
    if not isinstance(edges, list):
        raise ValueError('NOAA downstream routing is unavailable')
    if len(edges) == 1 and str(edges[0].get('reachId')) == '0':
        return {'downstream': [], 'terminal_noaa_zero': True, 'name': detail.get('name'), 'source_url': BASE + '/reaches/' + rid}
    downstream = []
    for edge in edges:
        nxt = str(edge.get('reachId', ''))
        if not nxt.isdigit() or int(nxt) <= 0:
            raise ValueError('Invalid downstream reach ID')
        downstream.append(nxt)
    if len(set(downstream)) != len(downstream):
        raise ValueError('Duplicate downstream edges')
    return {'downstream': downstream, 'name': detail.get('name'), 'source_url': BASE + '/reaches/' + rid}


def parse_gauge(detail, expected_id, root=ROOT):
    if str(detail.get('lid', '')).upper() != expected_id.upper():
        raise ValueError('NOAA returned a different gauge identity')
    status = detail.get('status', {}).get('observed') or {}
    flood = detail.get('flood') or {}
    low = detail.get('lowThreshold') or {}
    lo = number(low.get('value')) if isinstance(low, dict) and low.get('units') == 'ft' else None
    low_source = BASE + '/gauges/' + expected_id + '#lowThreshold' if lo is not None else None
    site = str(detail.get('usgsId') or '')
    if lo is None and site:
        minima = json.loads((root / 'data/stage_minima.json').read_text()).get('stations', {}).get(site, {})
        if minima.get('observed_adequate_75pct_distributed') or minima.get('daily_adequate_75pct_distributed'):
            lo = number(minima.get('minimum_ft'))
            low_source = 'data/stage_minima.json USGS ' + site + ' (adequate annual coverage)'
    minor = flood.get('categories', {}).get('minor') or {}
    upper = number(minor.get('stage')) if flood.get('stageUnits') == 'ft' else None
    # Explicit unit metadata for both stage and thresholds; never infer primaryUnit.
    in_service = (detail.get('inService') or {}).get('enabled') is not False
    return {'id': expected_id, 'name': detail.get('name'), 'stage': number(status.get('primary')) if in_service else None,
            'in_service': in_service,
            'timestamp': status.get('validTime'), 'units': status.get('primaryUnit'),
            'low': lo, 'flood': upper, 'reference_source': low_source,
            'low_source': low_source, 'flood_source': BASE + '/gauges/' + expected_id + '#flood.categories.minor',
            'low_units': 'ft' if lo is not None else None, 'flood_units': flood.get('stageUnits'),
            'coordinates': [number(detail.get('longitude')), number(detail.get('latitude'))],
            'source_url': BASE + '/gauges/' + expected_id, 'usgs_id': site,
            'reach_id': str(detail.get('reachId') or ''), 'retrieved_at': datetime.now(timezone.utc).isoformat()}


def fetch_observations(out, root, cache, max_gauges=500, cache_minutes=0):
    a = json.loads((out / 'assignments.json').read_text())
    ids = sorted({s[k] for s in a['sections'] for k in ('upstream', 'downstream')})
    if len(ids) > max_gauges:
        raise ValueError(f'Observation refresh exceeds {max_gauges}-gauge bound; explicitly increase --max-gauges for expanded coverage')
    existing = json.loads((out / 'observations.json').read_text()) if (out / 'observations.json').exists() else {'records': {}, 'max_age_hours': 36}
    existing['records'] = {gid: existing['records'][gid] for gid in ids if gid in existing['records']}
    errors = []; completed = 0
    def fetch(gid):
        checkpoint = cache / 'gauges' / (gid + '.json')
        reuse = cache_minutes > 0 and checkpoint.exists() and 0 <= time.time()-checkpoint.stat().st_mtime < cache_minutes*60
        d = json.loads(checkpoint.read_text()) if reuse else get('/gauges/' + gid)
        record = parse_gauge(d, gid, root)
        if reuse:
            record['retrieved_at'] = datetime.fromtimestamp(checkpoint.stat().st_mtime,timezone.utc).isoformat()
        else:
            write(checkpoint, d)
        return gid, record
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch, gid): gid for gid in ids}
        for future in concurrent.futures.as_completed(futures):
            gid = futures[future]
            try:
                _, record = future.result()
                # Current published gauge-to-reach identity must still match this path.
                expected = {s[k + '_reach'] for s in a['sections'] for k in ('upstream', 'downstream') if s[k] == gid}
                if expected != {record['reach_id']}:
                    existing['records'].pop(gid, None)
                    raise ValueError('Published gauge reach ID changed; rebuild routing')
                existing['records'][gid] = record
            except (OSError, ValueError, KeyError) as exc:
                errors.append({'gauge': gid, 'error': str(exc)})
            completed += 1
            if completed % 100 == 0:print('Endpoint observations', completed, '/', len(ids), 'errors', len(errors), flush=True)
    # Retain prior successful readings on errors; their own timestamps still expire.
    existing.update({'refreshed_at': datetime.now(timezone.utc).isoformat(), 'refresh_errors': errors, 'requested_gauges': len(ids)})
    write(out / 'observations.json', existing)
    print('Refreshed', len(ids) - len(errors), '/', len(ids), 'endpoint gauges;', len(errors), 'errors', flush=True)
    if ids and len(errors) == len(ids):
        raise RuntimeError('All observation requests failed; previous timestamps retained')


def build(args):
    obs, candidates = observations(args.root)
    features = json.loads((args.root / 'data/noaa_gauges.geojson').read_text())['features']
    by_id = {f['properties']['noaa_lid']: f for f in features}
    seeds = []
    for g in candidates:
        f = by_id.get(g['id'])
        if not f:
            continue
        p = f['properties']; r = obs['records'].get(g['id'], {})
        if args.states and p.get('state') not in args.states:
            continue
        if args.bbox:
            x, y = f['geometry']['coordinates']; west, south, east, north = args.bbox
            if not (west <= x <= east and south <= y <= north):
                continue
        if r.get('low') is not None and r.get('flood') is not None and r['flood'] > max(0, r['low']):
            seeds.append(g)
    # Interleave states so a bounded national run isn't consumed by alphabetic IDs.
    seeds.sort(key=lambda g: g['id'])
    groups = {}
    for g in seeds:
        groups.setdefault(by_id[g['id']]['properties'].get('state') or '', []).append(g)
    all_seeds = [g for i in range(max(map(len, groups.values()), default=0)) for state in sorted(groups) for g in groups[state][i:i+1]]
    seeds = all_seeds[getattr(args,'seed_offset',0):getattr(args,'seed_offset',0)+args.seed_limit]
    if not seeds:
        raise ValueError('No gauge seeds with real reference anchors in selection')
    gauge_reaches = {g['reach_id'] for g in candidates}
    reaches = {}; errors = []; requests = 0; pending = {g['reach_id'] for g in seeds}; seen = set()
    cache = args.cache / 'reaches'
    previous = args.output / 'topology.json'
    prior_nodes = {}
    source = BASE + '/reaches/{reachId} route.downstream.reachId; ' + DOCS
    if previous.exists():
        prior = json.loads(previous.read_text())
        if prior.get('source') != source or prior.get('method') != 'published-directed-nwm':
            raise ValueError('Cannot combine topology from different sources')
        prior_nodes = {rid: node for rid,node in prior['reaches'].items() if not node.get('endpoint_only')}
    def fetch(rid):
        if rid in prior_nodes:
            return rid, prior_nodes[rid]
        path = cache / (rid + '.json')
        if path.exists():
            raw = json.loads(path.read_text())
        else:
            raw = get('/reaches/' + rid)
            parse_reach(raw, rid)  # Validate before checkpointing.
            write(path, raw)
            time.sleep(.1)
        return rid, parse_reach(raw, rid)
    # Breadth-first frontiers let independent gauge paths progress in parallel.
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for depth in range(args.max_depth):
            if time.monotonic() - started >= args.max_seconds:
                errors.append({'reason': 'Elapsed-time budget exhausted; resume from checkpoints'})
                break
            batch = sorted(pending - seen)
            if not batch:
                break
            pending = set()
            available = []
            for rid in batch:
                if rid not in prior_nodes and not (cache / (rid + '.json')).exists():
                    if requests >= args.max_requests:
                        errors.append({'reach': rid, 'reason': 'Request budget exhausted'}); continue
                    requests += 1
                available.append(rid); seen.add(rid)
            futures = {pool.submit(fetch, rid): rid for rid in available}
            for future in concurrent.futures.as_completed(futures):
                rid = futures[future]
                try:
                    _, node = future.result(); reaches[rid] = node
                    edges = node['downstream']
                    if len(edges) == 1:
                        nxt = edges[0]
                        if nxt in gauge_reaches:
                            # Endpoint membership is known; no downstream extrapolation.
                            reaches.setdefault(nxt, {'downstream': [], 'endpoint_only': True})
                        else:
                            pending.add(nxt)
                except (OSError, ValueError) as exc:
                    errors.append({'reach': rid, 'reason': str(exc)})
            print('Routing depth', depth + 1, 'reaches', len(reaches), 'new requests', requests, flush=True)
    topology = {'method': 'published-directed-nwm', 'source': BASE + '/reaches/{reachId} route.downstream.reachId; ' + DOCS,
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'reaches': reaches}
    # Expansion retains earlier verified paths; never ingest unrelated cached nodes.
    previous = args.output / 'topology.json'
    if previous.exists():
        prior = json.loads(previous.read_text())
        if prior.get('source') != topology['source'] or prior.get('method') != topology['method']:
            raise ValueError('Cannot combine topology from different sources')
        combined = dict(prior['reaches'])
        for rid, node in reaches.items():
            if not node.get('endpoint_only') or rid not in combined:
                combined[rid] = node
        topology['reaches'] = combined
    previous_assignments = args.output / 'assignments.json'
    previous_result = json.loads(previous_assignments.read_text()) if previous_assignments.exists() else {}
    attempted = set(previous_result.get('attempted_seed_ids', previous_result.get('seed_ids', []))) | {g['id'] for g in seeds}
    result = assignments(topology, candidates)
    result.update({'built_at': topology['retrieved_at'], 'candidate_count': len(candidates), 'attempted_seed_ids': sorted(attempted), 'seed_ids': [g['id'] for g in seeds],
                   'coverage': {'national_complete': False, 'states': args.states, 'bbox': args.bbox,
                                'reaches_retrieved': len(reaches), 'total_verified_nodes': len(topology['reaches']), 'new_requests': requests, 'seed_total': len(all_seeds), 'seed_offset': getattr(args,'seed_offset',0), 'max_depth': args.max_depth, 'errors': errors},
                   'limitation': 'Bounded verified NWPS paths only. Endpoint reaches, unbracketed tributaries, ambiguous paths and unavailable readings retain modeled colors.'})
    if not result['sections']:
        write(args.cache / 'last-routing-report.json', result)
        raise ValueError('No confirmed sections; keeping previous active assignments')
    write(args.output / 'topology.json', topology)
    write(args.output / 'assignments.json', result)
    if not (args.output / 'observations.json').exists():
        write(args.output / 'observations.json', obs)
    print('Confirmed', len(result['sections']), 'sections;', sum(len(s['reach_ids']) for s in result['sections']), 'interior reaches', flush=True)
    if not getattr(args, 'skip_observations', False):
        fetch_observations(args.output, args.root, args.cache, getattr(args, 'max_gauges', 500), getattr(args, 'observation_cache_minutes', 0))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--output', type=Path, default=ROOT / 'web/nwm/gauges')
    p.add_argument('--cache', type=Path, default=ROOT / 'local/output/nwm-connections')
    p.add_argument('--states', nargs='+')
    p.add_argument('--bbox', nargs=4, type=float)
    p.add_argument('--seed-offset', type=int, default=0)
    p.add_argument('--skip-observations', action='store_true')
    p.add_argument('--seed-limit', type=int, default=80)
    p.add_argument('--max-requests', type=int, default=1000)
    p.add_argument('--max-depth', type=int, default=100)
    p.add_argument('--observation-cache-minutes', type=int, default=0)
    p.add_argument('--max-gauges', type=int, default=500)
    p.add_argument('--max-seconds', type=int, default=600)
    p.add_argument('--observations-only', action='store_true')
    args = p.parse_args()
    if not 0 <= args.observation_cache_minutes <= 60:
        p.error('Observation cache age must be 0–60 minutes')
    if args.seed_offset < 0:
        p.error('Seed offset must be nonnegative')
    if not 1 <= args.seed_limit <= 500 or not 1 <= args.max_requests <= 5000 or not 1 <= args.max_depth <= 500:
        p.error('Bounds: seeds 1–500, requests 1–5000, depth 1–500')
    if not 1 <= args.max_gauges <= 5000:
        p.error('Observation refresh bound must be 1–5000 gauges')
    if not 1 <= args.max_seconds <= 1800:
        p.error('Elapsed-time bound must be 1–1800 seconds')
    if args.bbox and not (-180 <= args.bbox[0] < args.bbox[2] <= 180 and -90 <= args.bbox[1] < args.bbox[3] <= 90):
        p.error('Invalid bbox')
    if args.observations_only:
        fetch_observations(args.output, args.root, args.cache, getattr(args, 'max_gauges', 500), getattr(args, 'observation_cache_minutes', 0))
    else:
        build(args)

if __name__ == '__main__':
    main()
