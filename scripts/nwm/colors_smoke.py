#!/usr/bin/env python3
"""Validate real national colors, viewport retrieval, popups and static-cache reuse."""
import argparse
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_smoke import download


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000/nwm-prototype.html')
    parser.add_argument('--output',type=Path,default=Path('/tmp/nwm-colors'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    semaphore=asyncio.Semaphore(4);api_semaphore=asyncio.Semaphore(3);requests=[];failures=[]
    async def transport(route):
        request=route.request
        try:
            async with (api_semaphore if request.method=="POST" else semaphore):status,body,headers=await asyncio.to_thread(download,request.url,request.method,request.post_data)
            if request.method=='POST':requests.append({'url':request.url,'body':request.post_data,'bytes':len(body)})
            await route.fulfill(status=status,body=body,headers=headers)
        except Exception as error:
            failures.append({'url':request.url,'error':str(error)});await route.abort()
    results=[]
    async with async_playwright() as runner:
        browser=await runner.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1400,'height':1080})
        await page.route('https://**/*',transport)
        page.on('console',lambda message:print('BROWSER',message.text,flush=True) if message.type in ('warning','error') else None)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto(args.url)
        await page.wait_for_function("document.querySelector('#national-overview').textContent.includes('national major-river reaches')",timeout=90000)
        await page.evaluate("async()=>{window.__nwmMap=(await import('/web/nwm/map.mjs')).map;}")
        await page.locator('#conus').click()
        await page.wait_for_function("!window.__nwmMap.isMoving()&&window.__nwmMap.areTilesLoaded()",timeout=120000)
        await page.wait_for_function("window.__nwmMap.queryRenderedFeatures({layers:['nwm-national-colors']}).some(f=>f.properties.scale_position!==null)")
        count=await page.evaluate("window.__nwmMap.queryRenderedFeatures({layers:['nwm-national-colors']}).filter(f=>f.properties.scale_position!==null).length")
        assert count>1000,count
        results.append({'view':'national','colored_rendered_features':count,'status':await page.locator('#national-overview').inner_text()})
        print("National colored features:",count,flush=True)
        await page.screenshot(path=str(args.output/'national.png'))
        for name,center in [('west',[-122.6,45.5]),('east',[-75.2,40.5])]:
            await page.evaluate("center=>window.__nwmMap.jumpTo({center,zoom:7.5})",center)
            await page.wait_for_function("document.querySelector('#live-status').textContent.match(/(\\d+)\\/(\\d+) cells/)?.slice(1).every((v,i,a)=>v===a[0])",timeout=240000)
            text=await page.locator('#live-status').inner_text()
            print(name,text,flush=True)
            if '0 unavailable cells' not in text:print('Asset failures:',json.dumps(failures),flush=True)
            assert '0 unavailable cells' in text,text
            await page.wait_for_function("window.__nwmMap.queryRenderedFeatures({layers:['nwm-live']}).some(f=>f.properties.scale_position!==null)",timeout=90000)
            count=await page.evaluate("window.__nwmMap.queryRenderedFeatures({layers:['nwm-live']}).filter(f=>f.properties.scale_position!==null).length")
            assert count>0
            results.append({'view':name,'colored_rendered_features':count,'status':text})
            await page.screenshot(path=str(args.output/(name+'.png')))
        # No further API reads are needed to revisit a cached viewport.
        before=len(requests)
        await page.evaluate("window.__nwmMap.jumpTo({center:[-122.6,45.5],zoom:7.5})")
        await page.wait_for_function("document.querySelector('#live-status').textContent.match(/(\\d+)\\/(\\d+) cells/)?.slice(1).every((v,i,a)=>v===a[0])",timeout=240000)
        assert len(requests)==before,(before,len(requests))
        point=await page.evaluate("""()=>{const map=window.__nwmMap,f=map.queryRenderedFeatures({layers:['nwm-live']}).find(f=>f.properties.scale_position!==null);
            const coords=f.geometry.type==='MultiLineString'?f.geometry.coordinates[0]:f.geometry.coordinates;
            const xy=coords[Math.floor(coords.length/2)],p=map.project(xy),r=map.getCanvas().getBoundingClientRect();return {x:p.x+r.x,y:p.y+r.y};}""")
        await page.mouse.click(point['x'],point['y'])
        await page.wait_for_selector('.maplibregl-popup-content')
        popup=await page.locator('.maplibregl-popup-content').inner_text()
        for label in ['NWM feature ID:','Current discharge:','Low anchor:','Central anchor:','Upper anchor:','Scale position:']:
            assert label in popup,popup
        assert not errors,errors
        await browser.close()
    (args.output/'results.json').write_text(json.dumps({'views':results,'query_count':len(requests),'asset_failures':failures,'popup':popup},indent=2)+'\n')
    print(json.dumps(results),flush=True)
    print('PASS: national and west/east viewport colors, cached revisit and numerical popup',flush=True)


if __name__=='__main__':
    asyncio.run(main())
