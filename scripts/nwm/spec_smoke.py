#!/usr/bin/env python3
"""Real geometry/browser validation for coordinated NWM rendering; no synthetic nationwide claim."""
import asyncio,json,sys
from pathlib import Path
from playwright.async_api import async_playwright
from browser_smoke import download
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/nwm/spec-validation'
async def main():
 OUT.mkdir(parents=True,exist_ok=True);requests=[];failures=[];errors=[];warnings=[];results=[];sem=asyncio.Semaphore(6);api_sem=asyncio.Semaphore(3)
 async def transport(route):
  requests.append(route.request.url)
  try:
   async with (api_sem if route.request.method=="POST" else sem):
    if route.request.failure:return
    status,body,headers=await asyncio.to_thread(download,route.request.url,route.request.method,route.request.post_data)
   if status>=400:failures.append({'url':route.request.url,'status':status})
   await route.fulfill(status=status,body=body,headers=headers)
  except Exception as e:failures.append({'url':route.request.url,'error':str(e)});await route.abort()
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  try:
   page=await browser.new_page(viewport={'width':1000,'height':800})
   page.on('request',lambda request:requests.append(request.url));page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda msg:(warnings.append(msg.text),print('BROWSER',msg.text,flush=True)) if msg.type in ('warning','error') else None);await page.route('https://**/*',transport)
   await page.goto('http://127.0.0.1:8001/nwm-prototype.html')
   await page.wait_for_function("document.querySelector('#status').textContent.includes('canonical')",timeout=60000)
   await page.evaluate("async()=>{window.m=(await import('/web/nwm/map.mjs')).map;}")
   await page.wait_for_function("!!m.getSource('nwm-national-colors')",timeout=60000)
   canonical=json.loads((ROOT/'web/nwm/launches/canonical.geojson').read_text())['features']
   actual=await page.evaluate("m.getSource('launches').serialize().data.features.map(f=>[f.properties.id,f.geometry])")
   assert actual==[[f['properties']['id'],f['geometry']] for f in canonical]
   verified=await page.evaluate("m.getSource('launches').serialize().data.features.filter(f=>f.properties.atlas_verified).map(f=>f.properties.id)")
   registry=json.loads((ROOT/'data/verified_launches.json').read_text())['verified_ids'];assert set(verified)==set(registry)
   assert not await page.evaluate("!!m.getSource('nwm')")
   await page.locator('#launches').uncheck();await page.locator('#gauge-colors').uncheck()
   assert await page.evaluate("m.getLayoutProperty('launches','visibility')")=='none'
   for name,xy,zoom in [('national',[-96,38],4),('chicago-region',[-87.8,41.8],6),('chicago-city',[-87.65,41.87],8),('chicago-neighborhood',[-87.65,41.87],13),('other-mainland',[-122.68,45.55],9),('alaska',[-150,63],5),('hawaii',[-157.8,21.4],12)]:
    await page.evaluate('([xy,z])=>{m.jumpTo({center:xy,zoom:z});}',[xy,zoom]);await page.wait_for_timeout(6000)
    state=await page.evaluate("""async()=>{const {zoomPolicy}=await import('/web/nwm/policy.mjs');return {zoom:m.getZoom(),order:zoomPolicy(m.getZoom()).order,filters:['nwm-live','nwm-national-colors'].map(id=>m.getFilter(id)),liveCount:m.queryRenderedFeatures({layers:['nwm-live']}).length,overviewCount:m.queryRenderedFeatures({layers:['nwm-national-colors']}).length,liveStatus:document.querySelector('#live-status').textContent,activeGray:m.getStyle().layers.filter(l=>l.id.startsWith('national-')&&l.minzoom<=m.getZoom()&&l.maxzoom>m.getZoom()).map(l=>l.id)};}""")
    assert all(f[-1]==state['order'] for f in state['filters']);assert state['overviewCount']==0 or zoom<5
    if zoom<5:assert state['overviewCount']>0
    assert all(id.endswith('-'+str(state['order'])) for id in state['activeGray'])
    assert await page.evaluate("m.getLayoutProperty('launches','visibility')")=='none'
    print('Validated view',name,state['liveStatus'],flush=True);await page.screenshot(timeout=90000,path=str(OUT/(name+'.png')));results.append({'view':name,**state})
   # Let a bounded mainland view finish so numerical popup/color assertions use real NOAA data.
   await page.evaluate("()=>{m.jumpTo({center:[-87.8,41.9],zoom:10});}")
   await page.wait_for_function("m.getSource('nwm-live').serialize().data.features.some(f=>f.properties.scale_position!==null)",timeout=180000)
   await page.wait_for_function("m.queryRenderedFeatures({layers:['nwm-live']}).some(f=>f.properties.scale_position!==null)",timeout=60000)
   colored=await page.evaluate("m.getSource('nwm-live').serialize().data.features.filter(f=>f.properties.scale_position!==null).length")
   print('Real live colored reaches',colored,flush=True)
   await page.screenshot(timeout=90000,path=str(OUT/'chicago-live-colors.png'))
   pt=await page.evaluate("""()=>{const r=m.getCanvas().getBoundingClientRect();for(const f of m.queryRenderedFeatures({layers:['nwm-live']})){if(f.properties.scale_position==null)continue;const lines=f.geometry.type==='MultiLineString'?f.geometry.coordinates:[f.geometry.coordinates];for(const line of lines)for(const xy of line){const p=m.project(xy);if(p.x>20&&p.x<r.width-20&&p.y>20&&p.y<r.height-20)return {x:r.x+p.x,y:r.y+p.y};}}throw new Error('No on-screen river vertex');}""")
   await page.mouse.click(pt['x'],pt['y']);await page.wait_for_selector('.maplibregl-popup-content');text=await page.locator('.maplibregl-popup-content').inner_text()
   assert all(label in text for label in ['Color source: Modeled NWM','NWM feature ID:','Current discharge:','Low anchor:','NOAA update:']),text
   await page.locator('.maplibregl-popup-close-button').click()
   await page.locator('#noaa-comparison').check()
   assert await page.evaluate("m.getLayoutProperty('nwm-live','visibility')")=='none'
   assert await page.evaluate("m.getStyle().layers.filter(l=>l.id.startsWith('national-')).every(l=>m.getLayoutProperty(l.id,'visibility')==='none')")
   await page.locator('#noaa-comparison').uncheck();await page.locator('#gauge-colors').check();await page.locator('#launches').check()
   assert await page.evaluate("m.getLayoutProperty('launches','visibility')")=='visible'
   # Original curated marker remains clickable with available metadata.
   first=canonical[0];await page.evaluate('xy=>{m.jumpTo({center:xy,zoom:13});}',first['geometry']['coordinates']);await page.wait_for_timeout(600)
   point=await page.evaluate('xy=>{const p=m.project(xy),r=m.getCanvas().getBoundingClientRect();return {x:r.x+p.x,y:r.y+p.y};}',first['geometry']['coordinates'])
   await page.mouse.click(point['x'],point['y']);await page.wait_for_selector('.maplibregl-popup-content');assert first['properties']['name'] in await page.locator('.maplibregl-popup-content').inner_text();await page.locator('.maplibregl-popup-close-button').click()
   # Launch layer remains last even when late overview/flow responses arrive.
   assert await page.evaluate("m.getStyle().layers.at(-1).id")=='launches'
   # Failed national snapshot and absent regional assets cannot block live initialization or launches.
   await page.route('**/web/nwm/overview/manifest.json',lambda route:route.fulfill(status=503,body='Unavailable'))
   await page.route('**/web/nwm/data/**',lambda route:route.fulfill(status=404,body='Removed'))
   await page.reload();await page.wait_for_function("document.querySelector('#national-overview').textContent.includes('unavailable')&&document.querySelector('#status').textContent.includes('canonical')",timeout=60000)
   await page.evaluate("async()=>{window.m=(await import('/web/nwm/map.mjs')).map;}")
   assert await page.evaluate("!!m.getLayer('nwm-live')&&!!m.getLayer('launches')")
   await page.locator('#launches').uncheck();await page.locator('#noaa-comparison').check()
   await page.evaluate("()=>{m.jumpTo({center:[-87.7,41.8],zoom:8});}");await page.wait_for_timeout(800)
   assert await page.evaluate("m.getSource('nwm-live').serialize().data.features.length") ==0
   assert not any('/web/nwm/data/' in u for u in requests)
   assert not errors,errors
   (OUT/'results.json').write_text(json.dumps({'views':results,'real_live_colored_reaches':colored,'console_warnings':warnings,'page_errors':errors,'external_failures':failures,'launch_count':len(canonical),'verified_launch_count':len(verified),'no_regional_dependency':True,'gauge_real_data_sections':0},indent=2)+'\n')
   print(json.dumps({'views':len(results),'page_errors':errors,'external_failures':len(failures),'launch_count':len(canonical)},indent=2))
  finally:
   await browser.close()
if __name__=='__main__':asyncio.run(main())
