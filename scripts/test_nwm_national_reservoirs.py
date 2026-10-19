import unittest,tempfile,time,json
from pathlib import Path
from unittest.mock import patch
from nwm import national_reservoirs as n
from nwm import reservoirs as core
class NationalReservoirs(unittest.TestCase):
 def test_grid_has_unique_ownership_on_edges_and_domains_are_explicit(self):
  c=n.initial_catalog();self.assertIn('conus_-123_40',c['cells']);self.assertIn('hawaii',n.DOMAINS);self.assertIn('alaska',c['unavailable_domains'])
  self.assertFalse(n.owns([0,0,2,2],[2,1],[0,0,4,4]));self.assertTrue(n.owns([2,0,4,2],[2,1],[0,0,4,4]));self.assertTrue(n.owns([2,2,4,4],[4,4],[0,0,4,4]))
 def test_null_is_empty_only_when_arcgis_identifies_empty_ids(self):
  self.assertEqual(n.ids({'objectIdFieldName':'oid','objectIds':None},5),[])
  for d in [{},{'objectIds':None},{'objectIds':list(range(6))},{'objectIds':[],'exceededTransferLimit':True}]:
   with self.assertRaises(ValueError):n.ids(d,5)
 def test_polygon_queries_all_stream_orders_without_a_river_name_join(self):
  class Response:
   status_code=200
   def raise_for_status(self):pass
   def json(self):return {'objectIds':[1,2]}
  g={'type':'Polygon','coordinates':[[[0,0],[1,0],[1,1],[0,0]]]}
  with patch.object(n.requests,'post',return_value=Response()) as request:
   self.assertEqual(n.polygon_query('https://example.test',g),[1,2]);p=request.call_args.kwargs['data'];self.assertEqual(p['where'],'1=1');self.assertNotIn('strm_order',p['where']);self.assertEqual(p['geometryType'],'esriGeometryPolygon')
 def test_shared_routing_budget_stops_before_requests_and_keeps_cached_progress(self):
  groups=[{'properties':{'reach_ids':['11']}}];lines=[{'properties':{'feature_id':'11','order':5}}]
  with tempfile.TemporaryDirectory() as d,patch.object(core.connections,'get') as get:
   with self.assertRaisesRegex(ValueError,'budget'):core.topology_for(groups,lines,Path(d),budget={'remaining':0,'deadline':time.monotonic()+60},follow_priority_names=False)
   get.assert_not_called()
 def test_published_manifest_keeps_failures_and_geometry_gaps_distinct(self):
  c=n.initial_catalog();c['waterbodies']['bad']={'status':'unavailable-invalid-geometry'}
  with tempfile.TemporaryDirectory() as d:
   n.manifest(c,Path(d));m=json.loads((Path(d)/'manifest.json').read_text());self.assertEqual(m['shards'],[]);self.assertEqual(m['coverage']['waterbodies']['unavailable-invalid-geometry'],1)
 def test_refresh_never_stamps_a_partially_refreshed_shard_as_fresh(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);n.save(p/'s/static.json',{'context':{'features':[{'properties':{'feature_id':'1','flood':10}}]}});n.save(p/'s/flow.json',{'retrieved_at':'original','records':[]})
   c={'waterbodies':{'s':{'status':'published','domain':'conus','static':'s/static.json','flow':'s/flow.json'}},'refresh_cursor':0}
   with patch.object(core,'refresh_flows',side_effect=ValueError('unavailable')):n.refresh(c,p,p/'cache',1,time.monotonic()+60)
   self.assertEqual(n.read(p/'s/flow.json')['retrieved_at'],'original')
if __name__=='__main__':unittest.main()
