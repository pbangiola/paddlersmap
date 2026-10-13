import json,tempfile,unittest
from pathlib import Path
from nwm.gauge_assignments import assignments
from nwm.launch_inventory import reconcile,publish,feature

def point(id,name,xy):return {'type':'Feature','geometry':{'type':'Point','coordinates':xy},'properties':{'id':id,'name':name}}
class GaugePaths(unittest.TestCase):
 def setUp(self):
  self.top={'source':'Authoritative test fixture','method':'published-directed-nwm','reaches':{'1':{'downstream':['2']},'2':{'downstream':['3']},'3':{'downstream':['4']},'4':{'downstream':[]},'branch':{'downstream':['2']}}}
  self.gauges=[{'id':x,'reach_id':r,'match_method':'published-reach-id','match_source':'NOAA explicit reachId'} for x,r in [('up','1'),('down','4')]]
 def test_connected_path_excludes_endpoints_and_tributary(self):
  sections=assignments(self.top,self.gauges)['sections'];self.assertEqual(sections[0]['reach_ids'],['2','3'])
 def test_branches_cycles_wrong_rivers_and_candidates_fail(self):
  for edges in [['3','branch'],['1'],['missing']]:
   top=json.loads(json.dumps(self.top));top['reaches']['2']['downstream']=edges;self.assertFalse(assignments(top,self.gauges)['sections'])
  self.gauges[1]['reach_id']='branch';self.assertFalse(assignments(self.top,self.gauges)['sections'])
  self.gauges[1]['reach_id']='4';self.gauges[0]['match_method']='nearest';self.assertFalse(assignments(self.top,self.gauges)['sections'])
 def test_successive_gauges_and_same_reach_ambiguity(self):
  self.gauges.append({**self.gauges[0],'id':'middle','reach_id':'3'})
  sections=assignments(self.top,self.gauges)['sections'];self.assertEqual(len(sections),1);self.assertEqual(sections[0]['reach_ids'],['2'])
  self.gauges.append({**self.gauges[0],'id':'duplicate'});self.assertFalse(assignments(self.top,self.gauges)['sections'])
class LaunchInventory(unittest.TestCase):
 def test_literal_selection_and_original_osm_geometry(self):
  e={'type':'way','id':1,'center':{'lon':-87,'lat':42},'geometry':[{'lon':-87,'lat':42}],'tags':{'name':'Park CANOE LAUNCH'}}
  f=feature(e,'now');self.assertEqual(f['properties']['original_osm_element'],e)
  e['tags']['name']='Kayak ramp';self.assertIsNone(feature(e,'now'))
 def test_conservative_dedup_preserves_curated_and_nearby_distinct(self):
  c=point('owner','Example Park Canoe Launch',[-87,42]);osm=point('osm-node-1','Example Park Canoe Launch',[-87.0001,42]);near=point('osm-node-2','Other Park Canoe Launch',[-87,42])
  fs,r=reconcile([osm,osm,near],[c]);self.assertEqual(len(fs),2);self.assertEqual(fs[0]['geometry'],c['geometry']);self.assertEqual(fs[0]['properties']['alternate_ids'],['osm-node-1']);self.assertTrue(r['ambiguous_groups'])
  fs,_=reconcile([osm],[c],['osm-node-1']);self.assertEqual(len(fs),2)
  fs,_=reconcile([point('b','Canoe Launch',[-87,42])],[point('a','Canoe Launch',[-87,42])]);self.assertEqual(len(fs),2)
 def test_partial_refresh_keeps_active_bytes(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'active.geojson';out.write_text('original')
   with self.assertRaises(ValueError):publish({'metadata':{'complete':False},'features':[]},[],out,Path(tmp)/'report.json',10)
   self.assertEqual(out.read_text(),'original');self.assertFalse((Path(tmp)/'report.json').exists())
if __name__=='__main__':unittest.main()

class LaunchProtection(unittest.TestCase):
 def test_distance_threshold_and_separate_entrances(self):
  c=point('owner','Example Park Canoe Launch',[-87,42]);f=point('osm-node-1','Example Park Canoe Launch',[-87.0003,42])
  self.assertEqual(len(reconcile([f],[c],max_m=10)[0]),2)
  self.assertEqual(len(reconcile([f],[c],max_m=40)[0]),1)
 def test_empty_and_broad_source_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'active';out.write_text('prior complete')
   for fs in [[],[point('osm-node-1','Boat Ramp',[-87,42])]]:
    with self.assertRaises(ValueError):publish({'metadata':{'complete':True},'features':fs},[],out,Path(tmp)/'report',1)
    self.assertEqual(out.read_text(),'prior complete')

class OsmGeometry(unittest.TestCase):
 def test_geometry_output_bounds_are_valid_representative_centers(self):
  e={'type':'way','id':808598909,'bounds':{'minlon':-122.7407709,'maxlon':-122.7406597,'minlat':45.3846876,'maxlat':45.3848592},'geometry':[{'lat':45.3848592,'lon':-122.7406597},{'lat':45.3846876,'lon':-122.7407709}],'tags':{'name':'Browns Ferry Park Kayak and Canoe Launch'}}
  f=feature(e,'now');self.assertAlmostEqual(f['geometry']['coordinates'][0],-122.7407153);self.assertEqual(f['properties']['original_osm_element'],e)
  e['type']='relation';self.assertIsNotNone(feature(e,'now'))
  e.pop('bounds');self.assertRaises(ValueError,feature,e,'now')
