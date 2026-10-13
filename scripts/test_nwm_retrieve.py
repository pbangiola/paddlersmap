"""Bounded retrieval contracts, using synthetic service responses only."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('nwm_retrieve', Path(__file__).parent / 'nwm/retrieve.py')
nwm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nwm)


class NwmRetrievalTests(unittest.TestCase):
    def test_batches_use_ids_and_honor_service_limit(self):
        calls = []
        def get(url, params):
            calls.append(params)
            if params.get('returnIdsOnly'):
                return {'objectIds': [8, 2, 19]}
            if url.endswith('/query'):
                return {'features': [{'attributes': {'feature_id': int(x)}} for x in params['objectIds'].split(',')]}
            return {'fields': [{'name': 'feature_id'}], 'maxRecordCount': 2}
        with patch.object(nwm, 'get', side_effect=get), patch.object(nwm.time, 'sleep'):
            result = nwm.query('https://example.test/0', [-88, 41, -87, 42], ['feature_id'], True)
        self.assertEqual(len(result), 3)
        batches = [p for p in calls if 'objectIds' in p]
        self.assertEqual([p['objectIds'] for p in batches], ['8,2', '19'])
        self.assertTrue(all(p['outSR'] == 4326 for p in batches))

    def test_truncated_results_are_not_accepted(self):
        responses = [{'objectIds': [1, 2]}, {'fields': [{'name': 'id'}]}, {'features': [{'attributes': {'id': 1}}], 'exceededTransferLimit': True}]
        with patch.object(nwm, 'get', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, 'Truncated'):
                nwm.query('https://example.test/0', [-88, 41, -87, 42], ['id'], False)

    def test_unverified_fields_rejected(self):
        with patch.object(nwm, 'get', return_value={'fields': [{'name': 'id'}]}):
            with self.assertRaisesRegex(ValueError, 'missing fields'):
                nwm.validate_schema('https://example.test/0', ['id', 'fabricated_threshold'])

    def test_rate_limit_retries_preserve_request(self):
        from unittest.mock import Mock
        limited = Mock(status_code=429, headers={'Retry-After': '3'})
        good = Mock(status_code=200, headers={})
        good.json.return_value = {'features': []}
        with patch.object(nwm.requests, 'get', side_effect=[limited, good]) as request, patch.object(nwm.time, 'sleep') as sleep:
            self.assertEqual(nwm.get('https://example.test/0', {'where': '1=1'}), {'features': []})
        sleep.assert_called_once_with(3)
        self.assertEqual(request.call_args_list[0], request.call_args_list[1])
