#!/usr/bin/env python3
"""Validate Mississippi reservoir surfaces, numerical provenance and unchanged launches."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_smoke import download
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/nwm/reservoir-validation'
async def main():
 OUT.mkdir(parents=True,exist_ok=True);errors=[];failures=[];sem=asyncio.Semaphore(5)
 async def transport(route):
  try:
   async with sem:status,body,headers=await asyncio.to_thread(download,route.request.url,route.request.method,route.request.post_data)
   if status>=400:failures.append({'url':route.request.url,'status':status})
   await route.fulfill(status=status,body=body,headers=headers)
  except Exception as e:failures.append({'url':route.request.url,'error':str(e)});await route.abort()
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  try:
   page=await browser.new_page(viewport={'width':1300,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)))
   await page.route('https://**/*',transport);await page.goto('http://127.0.0.1:8001/')
   await page.wait_for_function("document.querySelector('#status').textContent.includes('canonical')",timeout=60000)
   await page.evaluate("async()=>{window.m=(await import('/web/nwm/map.mjs')).map;}")
   await page.wait_for_function("m.getSource('reservoirs')?.serialize().data.features.some(f=>f.properties.waterbody_id==='1874843'&&f.properties.available)",timeout=60000)
   await page.locator('#pepin').click()
   await page.wait_for_function("m.queryRenderedFeatures({layers:['reservoir-fills']}).some(f=>f.properties.waterbody_id==='1874843')",timeout=60000)
   await page.wait_for_function("document.querySelector('#live-status').textContent.includes('0 unavailable cells')",timeout=180000)
   proof=await page.evaluate("""()=>{const body=m.getSource('reservoirs').serialize().data.features.find(f=>f.properties.waterbody_id==='1874843'),data=m.getSource('nwm-live').serialize().data.features,byId=new Map(data.map(f=>[f.properties.feature_id,f]));const p=body.properties,key=p.anchor_mode==='observed'?'observed_position':'scale_position',mean=ids=>ids.reduce((s,id)=>s+byId.get(id).properties[key],0)/ids.length;const expected=(mean(p.upstream_anchor_ids)+mean(p.downstream_anchor_ids))/2;return {body,expected,inferred:data.filter(f=>f.properties.reservoir_id==='1874843'),all_estimates:m.getSource('reservoirs').serialize().data.features.map(f=>({id:f.properties.waterbody_id,name:f.properties.name,available:f.properties.available,reason:f.properties.unavailable_reason,position:f.properties.inferred_position})),launches:m.getSource('launches').serialize().data.features.map(f=>[f.properties.id,f.geometry])};}""")
   assert abs(proof['expected']-proof['body']['properties']['inferred_position'])<1e-12
   assert proof['inferred'] and all(f['properties']['scale_position'] is None for f in proof['inferred'])
   canonical=json.loads((ROOT/'web/nwm/launches/canonical.geojson').read_text())['features'];assert proof.pop('launches')==[[f['properties']['id'],f['geometry']] for f in canonical]
   assert await page.evaluate("m.getStyle().layers.at(-1).id")=='launches'
   await page.screenshot(path=str(OUT/'lake-pepin.png'),timeout=90000)
   point=await page.evaluate("""()=>{const r=m.getCanvas().getBoundingClientRect();for(let y=30;y<r.height-30;y+=15)for(let x=30;x<r.width-30;x+=15){const hit=m.queryRenderedFeatures([x,y],{layers:['reservoir-fills']}).some(f=>f.properties.waterbody_id==='1874843');if(hit&&!m.queryRenderedFeatures([x,y],{layers:['nwm-live','nwm-national-colors','connected-gauges','launches']}).length)return {x:r.x+x,y:r.y+y};}throw Error('No clear reservoir surface pixel');}""")
   await page.mouse.click(point['x'],point['y']);await page.wait_for_selector('.maplibregl-popup-content')
   assert not await page.locator('.maplibregl-popup-content details').evaluate('(e)=>e.open')
   await page.locator('.maplibregl-popup-content summary').click();text=await page.locator('.maplibregl-popup-content').inner_text()
   assert all(v in text for v in ['1874843','1875139','1878125','visual estimate','Estimated scale position']),text
   await page.screenshot(path=str(OUT/'lake-pepin-popup.png'),timeout=90000);await page.locator('.maplibregl-popup-close-button').click()
   await page.locator('#reservoirs').uncheck();assert await page.evaluate("m.getLayoutProperty('reservoir-fills','visibility')")=='none'
   assert await page.evaluate("m.getSource('nwm-live').serialize().data.features.every(f=>f.properties.color_source!=='Inferred reservoir color')")
   await page.locator('#reservoirs').check();await page.locator('#noaa-comparison').check();assert await page.evaluate("m.getLayoutProperty('reservoir-fills','visibility')")=='none'
   await page.locator('#noaa-comparison').uncheck();assert await page.evaluate("m.getLayoutProperty('reservoir-fills','visibility')")=='visible'
   assert not errors,errors
   proof.update({'page_errors':errors,'external_failures':failures,'launch_count':len(canonical),'popup':text,'checks':['Actual NOAA polygon rendered','Lake Pepin bracket mean independently verified','Missing reach colors interpolated without numerical flow values','Reservoir details collapsed by default','Toggle and NOAA comparison hide estimates','All launch coordinates preserved']})
   (OUT/'browser.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'pepin_position':proof['expected'],'pepin_inferred_reaches':len(proof['inferred']),'errors':errors,'external_failures':len(failures)}),flush=True)
  finally:await browser.close()
if __name__=='__main__':asyncio.run(main())
