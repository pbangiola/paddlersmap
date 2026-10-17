import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nwm.connections import parse_reach, parse_gauge, fetch_observations
from nwm.gauge_assignments import observations


class PublishedRouting(unittest.TestCase):
    def test_exact_ids_and_published_direction(self):
        d = {'reachId': '14784677', 'route': {'upstream': [{'reachId': '111'}], 'downstream': [{'reachId': '14784631'}]}}
        self.assertEqual(parse_reach(d, '14784677')['downstream'], ['14784631'])
        for invalid in [{**d, 'reachId': 'other'}, {'reachId': '14784677'}, {**d, 'route': {'downstream': [{'reachId': 'not-an-id'}]}}, {**d, 'route': {'downstream': None}}]:
            with self.assertRaises(ValueError): parse_reach(invalid, '14784677')
        self.assertEqual(parse_reach({**d, 'route': {'downstream': []}}, '14784677')['downstream'], [])
        self.assertEqual(parse_reach({**d, 'route': {'downstream': [{'reachId': '0'}]}}, '14784677')['downstream'], [])


class QualifiedObservations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root / 'data').mkdir()
        (self.root / 'data/stage_minima.json').write_text(json.dumps({'stations': {'05529000': {'minimum_ft': 7, 'daily_adequate_75pct_distributed': True}}}))
        self.detail = {'lid': 'DSPI2', 'usgsId': '05529000', 'reachId': '14784677', 'status': {'observed': {'primary': 0, 'primaryUnit': 'ft', 'validTime': '2026-10-17T12:00:00Z'}}, 'lowThreshold': {'value': 7.5, 'units': 'ft'}, 'flood': {'stageUnits': 'ft', 'categories': {'minor': {'stage': 15}}}}

    def test_published_units_zero_and_sentinels(self):
        r = parse_gauge(self.detail, 'DSPI2', self.root)
        self.assertEqual((r['stage'], r['low'], r['flood'], r['units']), (0, 7.5, 15, 'ft'))
        self.detail['status']['observed']['primary'] = -999
        self.assertIsNone(parse_gauge(self.detail, 'DSPI2', self.root)['stage'])
        self.detail['flood']['stageUnits'] = 'm'
        self.assertIsNone(parse_gauge(self.detail, 'DSPI2', self.root)['flood'])
        self.detail['status']['observed'].pop('primaryUnit')
        self.assertIsNone(parse_gauge(self.detail, 'DSPI2', self.root)['units'])

    def test_low_uses_usgs_identity_and_adequate_coverage(self):
        self.detail['lowThreshold'] = {'value': 1, 'units': 'm'}
        r = parse_gauge(self.detail, 'DSPI2', self.root)
        self.assertEqual(r['low'], 7)
        self.assertIn('05529000', r['reference_source'])
        (self.root / 'data/stage_minima.json').write_text('{"stations":{}}')
        self.assertIsNone(parse_gauge(self.detail, 'DSPI2', self.root)['low'])

    def test_changed_reach_invalidates_previous_reading(self):
        out = self.root / 'out'; out.mkdir()
        (out / 'assignments.json').write_text(json.dumps({'sections': [{'upstream': 'DSPI2', 'downstream': 'DSPI2', 'upstream_reach': 'other', 'downstream_reach': 'other'}]}))
        (out / 'observations.json').write_text(json.dumps({'records': {'DSPI2': {'stage': 10}}}))
        with patch('nwm.connections.get', return_value=self.detail):
            with self.assertRaises(RuntimeError): fetch_observations(out, self.root, self.root / 'cache')
        self.assertNotIn('DSPI2', json.loads((out / 'observations.json').read_text())['records'])

    def test_transport_failure_keeps_original_timestamp(self):
        out = self.root / 'out'; out.mkdir()
        (out / 'assignments.json').write_text(json.dumps({'sections': [{'upstream': 'DSPI2', 'downstream': 'DSPI2', 'upstream_reach': '14784677', 'downstream_reach': '14784677'}]}))
        prior = {'stage': 10, 'timestamp': '2026-10-10T12:00:00Z'}
        (out / 'observations.json').write_text(json.dumps({'records': {'DSPI2': prior}}))
        with patch('nwm.connections.get', side_effect=OSError('unavailable')):
            with self.assertRaises(RuntimeError): fetch_observations(out, self.root, self.root / 'cache')
        self.assertEqual(json.loads((out / 'observations.json').read_text())['records']['DSPI2'], prior)

    def test_repository_annual_minimum_joins_usgs_not_noaa_id(self):
        (self.root / 'data/flood_stages_il.json').write_text('{"stations":{}}')
        (self.root / 'data/gauges.geojson').write_text('{"features":[]}')
        (self.root / 'data/noaa_gauges.geojson').write_text(json.dumps({'features': [{'properties': {'noaa_lid': 'DSPI2', 'site': '05529000', 'flood_stage_ft': 15}}]}))
        obs, _ = observations(self.root)
        self.assertEqual(obs['records']['DSPI2']['low'], 7)


class BoundedExpansion(unittest.TestCase):
    def test_checkpoint_resume_and_unbracketed_refresh_protection(self):
        from argparse import Namespace
        from nwm.connections import build
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'data').mkdir(); out = root / 'out'
            for name in ['stage_minima.json', 'flood_stages_il.json']:
                (root / 'data' / name).write_text('{"stations":{}}')
            features = [{'geometry': {'coordinates': [-88, 42]}, 'properties': {'noaa_lid': gid, 'site': gid, 'reach_id': rid, 'state': 'IL', 'low_water_stage_ft': 1, 'flood_stage_ft': 10}} for gid, rid in [('UP', '1'), ('DOWN', '4')]]
            (root / 'data/noaa_gauges.geojson').write_text(json.dumps({'features': features}))
            (root / 'data/gauges.geojson').write_text('{"features":[]}')
            args = Namespace(root=root, output=out, cache=root / 'cache', states=None, bbox=None, seed_limit=10, max_requests=10, max_depth=10, max_seconds=60)
            def api(path):
                rid = path.split('/')[-1]
                return {'reachId': rid, 'route': {'downstream': [{'reachId': str(int(rid) + 1)}] if rid != '4' else []}}
            with patch('nwm.connections.get', side_effect=api) as network, patch('nwm.connections.fetch_observations'), patch('nwm.connections.time.sleep'):
                build(args)
                self.assertEqual(network.call_count, 4)
            self.assertEqual(json.loads((out / 'assignments.json').read_text())['sections'][0]['reach_ids'], ['2', '3'])
            with patch('nwm.connections.get', side_effect=AssertionError('Cached topology must not refetch')), patch('nwm.connections.fetch_observations'):
                build(args)
            protected = (out / 'assignments.json').read_bytes()
            # Different, truncated traversal cannot replace a valid active result.
            args.cache = root / 'empty-cache'; args.max_depth = 1
            (out / 'topology.json').unlink()
            with patch('nwm.connections.get', side_effect=api), patch('nwm.connections.time.sleep'):
                with self.assertRaises(ValueError): build(args)
            self.assertEqual((out / 'assignments.json').read_bytes(), protected)


class RateLimits(unittest.TestCase):
    def test_long_retry_after_pauses_all_further_requests(self):
        import urllib.error
        from nwm.connections import get, RATE_PAUSED
        RATE_PAUSED.clear(); self.addCleanup(RATE_PAUSED.clear)
        error = urllib.error.HTTPError('https://api.water.noaa.gov', 429, 'Too Many Requests', {'Retry-After': '60'}, None)
        with patch('nwm.connections.urllib.request.urlopen', side_effect=error) as network:
            with self.assertRaises(OSError): get('/reaches/1')
            with self.assertRaises(OSError): get('/reaches/2')
            self.assertEqual(network.call_count, 1)


class LegacyRebuildProtection(unittest.TestCase):
    def test_missing_topology_cannot_erase_confirmed_paths(self):
        from nwm.gauge_assignments import main
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); path = out / 'assignments.json'
            path.write_text('{"sections":[{"upstream":"UP","downstream":"DOWN"}]}')
            previous = path.read_bytes()
            with patch('sys.argv', ['gauge_assignments.py', '--output', str(out)]):
                with self.assertRaises(ValueError): main()
            self.assertEqual(path.read_bytes(), previous)
