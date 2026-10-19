"""Bounded OSM query subdivision preserves complete-only publication."""
import tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from nwm import launch_inventory as m
class LaunchRound(unittest.TestCase):
 def test_http_error_keeps_status_and_public_service_diagnostic(self):
  import io
  error=urllib.error.HTTPError('test',500,'Internal Server Error',{},io.BytesIO(b'<p>Service dispatcher unavailable</p>'))
  with patch.object(m.urllib.request,'urlopen',side_effect=error):
   with self.assertRaises(urllib.error.HTTPError) as caught:m.fetch_cell([0,0,1,1],attempts=1)
  self.assertEqual(caught.exception.code,500);self.assertIn('dispatcher unavailable',str(caught.exception))
 def test_split_deduplicate_and_reuse(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cell.json';calls=[]
   def fetch(b,*args,**kw):
    calls.append(b)
    if b==[0,0,4,4]:raise TimeoutError('timeout')
    return {'elements':[{'type':'node','id':1}], '_area_scope':'US|PR|VI|GU|MP|AS'}
   with patch.object(m,'fetch_cell',side_effect=fetch):
    data=m.retrieve_cell([0,0,4,4],p,'test');self.assertEqual(len(data['elements']),1);self.assertEqual(len(calls),5)
    m.retrieve_cell([0,0,4,4],p,'test');self.assertEqual(len(calls),5)
 def test_rate_limit_does_not_multiply_requests(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'fetch_cell',side_effect=urllib.error.HTTPError('test',429,'rate limit',{},None)) as f:
   with self.assertRaises(urllib.error.HTTPError):m.retrieve_cell([0,0,4,4],Path(d)/'cell.json','test')
   self.assertEqual(f.call_count,1)
 def test_budget_preserves_partial_children_without_publishing_parent(self):
  import time
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cell.json'
   def fetch(b,*args,**kw):
    if b==[0,0,4,4]:raise TimeoutError('timeout')
    return {'elements':[], '_area_scope':'US|PR|VI|GU|MP|AS'}
   with patch.object(m,'fetch_cell',side_effect=fetch):
    with self.assertRaisesRegex(ValueError,'budget'):m.retrieve_cell([0,0,4,4],p,'test',budget={'remaining':2,'deadline':time.monotonic()+60})
   self.assertFalse(p.exists());self.assertTrue((Path(d)/'cell-0.json').exists())
if __name__=='__main__':unittest.main()
