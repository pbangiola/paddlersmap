import unittest
from nwm.reservoirs import membership,length_km,parse_routing
class Reservoirs(unittest.TestCase):
 def test_membership_uses_actual_overlap_not_names_or_touching_alone(self):
  body={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[0,0],[2,0],[2,2],[0,2],[0,0]]]},'properties':{'waterbody_id':'123','name':'Pool'}}
  def line(rid,coordinates):return {'type':'Feature','geometry':{'type':'LineString','coordinates':coordinates},'properties':{'feature_id':rid,'name':'Same misleading river name'}}
  lines=[line('inside',[[0,1],[2,1]]),line('outside',[[3,1],[4,1]]),line('touch',[[2,2],[3,3]])]
  result=membership([body],lines);self.assertEqual(result[0]['properties']['reach_ids'],['inside']);self.assertEqual(lines[0]['geometry']['coordinates'],[[0,1],[2,1]])
 def test_invalid_polygon_is_reported_without_repairing_its_coordinates(self):
  body={'geometry':{'type':'Polygon','coordinates':[[[0,0],[2,2],[0,2],[2,0],[0,0]]]},'properties':{'waterbody_id':'bad','name':'Invalid'}}
  line={'geometry':{'type':'LineString','coordinates':[[0,1],[2,1]]},'properties':{'feature_id':'1'}}
  invalid={};self.assertEqual(membership([body],[line],invalid),[]);self.assertEqual(invalid,{'bad':'Invalid'})
 def test_length_in_km_and_zero_length(self):
  self.assertAlmostEqual(length_km({'type':'LineString','coordinates':[[0,0],[0,1]]}),111.1949,places=3)
  self.assertEqual(length_km({'type':'MultiLineString','coordinates':[[[0,0],[0,0]]]}),0)
 def test_published_routing_id_validation_and_orders(self):
  d={'reachId':'12','route':{'upstream':[{'reachId':'11','streamOrder':'5'}],'downstream':[{'reachId':'13','streamOrder':'5'}]}}
  node=parse_routing(d,'12');self.assertEqual(node['upstream'],['11']);self.assertEqual(node['upstream_orders'],{'11':5})
  with self.assertRaises(ValueError):parse_routing(d,'99')
  d['route']['upstream']=[{'reachId':'x'}]
  with self.assertRaises(ValueError):parse_routing(d,'12')

class ReservoirFlow(unittest.TestCase):
 def context(self,tmp):
  import json
  from pathlib import Path
  p=Path(tmp);(p/'context.geojson').write_text(json.dumps({'features':[{'properties':{'feature_id':'11','flood':100}}]}));(p/'flow.json').write_text('previous snapshot');return p
 def test_exact_id_flow_join_quotes_service_string_ids_and_preserves_zero(self):
  import tempfile,json
  from unittest.mock import patch
  from nwm import reservoirs as m
  with tempfile.TemporaryDirectory() as d:
   p=self.context(d)
   response={'features':[{'attributes':{'feature_id':'11','latest_flow':0,'prcntle_10':0,'prcntle_25':5,'prcntle_75':15,'update_time':'2026-10-19 00:50:14 UTC'}}]}
   with patch.object(m,'validate_schema'),patch.object(m,'get',return_value=response) as fetch:m.refresh_flows(p)
   self.assertEqual(fetch.call_args.args[1]['where'],"feature_id IN ('11')")
   record=json.loads((p/'flow.json').read_text())['records'][0];self.assertEqual(record['discharge'],0);self.assertEqual(record['average'],10)
 def test_missing_truncated_or_foreign_flow_records_retain_previous_snapshot(self):
  import tempfile
  from unittest.mock import patch
  from nwm import reservoirs as m
  for response in [{'features':[]},{'features':[],'exceededTransferLimit':True},{'features':[{'attributes':{'feature_id':'wrong'}}]}]:
   with tempfile.TemporaryDirectory() as d:
    p=self.context(d)
    with patch.object(m,'validate_schema'),patch.object(m,'get',return_value=response):
     with self.assertRaises(ValueError):m.refresh_flows(p)
    self.assertEqual((p/'flow.json').read_text(),'previous snapshot')

if __name__=='__main__':unittest.main()
