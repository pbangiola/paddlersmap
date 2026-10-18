"""Verify the active map cannot silently restore retired or fabricated networks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nwm.connected_geometry import retrieve

ROOT = Path(__file__).resolve().parents[1]


class PrimaryEntrypoints(unittest.TestCase):
    def test_homepage_uses_only_nwm_and_legacy_pages_redirect(self):
        page = (ROOT / 'index.html').read_text()
        self.assertIn('web/nwm/map.mjs', page)
        self.assertNotIn('web/app.js', page)
        self.assertNotIn('river_segments', page)
        for name in ['gauge-connections.html', 'nwm-prototype.html']:
            page = (ROOT / name).read_text()
            self.assertIn('location.replace', page)
            self.assertNotIn('maplibre', page)
        self.assertFalse((ROOT / 'web/gauge-connections.js').exists())
        self.assertFalse((ROOT / 'web/app.js').exists())


class ExactConnectedGeometry(unittest.TestCase):
    def test_cache_and_exact_id_geometry_without_reconstruction(self):
        fixture = {'feature_id': 123, 'strm_order': 4, 'name': 'Real NOAA reach'}
        def service(url, params):
            if not url.endswith('/query'):
                return {'fields': [{'name': k} for k in fixture], 'maxRecordCount': 200}
            return {'features': [{'attributes': fixture, 'geometry': {'paths': [[[-87, 42], [-87.1, 41.9]]]}}]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('nwm.connected_geometry.get', side_effect=service):
                result = retrieve({'123'}, Path(tmp))
            self.assertEqual(result['features'][0]['geometry']['coordinates'], [[[-87, 42], [-87.1, 41.9]]])
            with patch('nwm.connected_geometry.get', side_effect=AssertionError('Do not refetch static geometry')):
                cached = retrieve({'123'}, Path(tmp))
            self.assertEqual(cached['features'], result['features'])
            self.assertEqual(result['metadata']['missing_reach_ids'], [])

    def test_truncated_or_wrong_feature_ids_are_not_accepted(self):
        meta = {'fields': [{'name': 'feature_id'}, {'name': 'strm_order'}]}
        for bad in [{'exceededTransferLimit': True, 'features': []}, {'features': [{'attributes': {'feature_id': '999'}, 'geometry': {'paths': [[[0, 0], [1, 1]]]}}]}]:
            with tempfile.TemporaryDirectory() as tmp, patch('nwm.connected_geometry.get', side_effect=[meta, bad]):
                with self.assertRaises(ValueError): retrieve({'123'}, Path(tmp))
