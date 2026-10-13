#!/usr/bin/env python3
"""Test national NOAA raster geometry without downloading the national network."""
import argparse
import asyncio
import io
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000/nwm-prototype.html')
    parser.add_argument('--output',type=Path,default=Path('/tmp/nwm-national'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    tiles=[]
    failures=[]
    optional_failures=[]
    retries=[]
    semaphore=asyncio.Semaphore(4)
    def download(url,method="GET",payload=None):
        request=urllib.request.Request(url,data=payload.encode() if payload else None,method=method,headers={'User-Agent':'PaddlersMapPrototypeValidation/1.0',**({'Content-Type':'application/x-www-form-urlencoded'} if payload else {})})
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request,timeout=45) as response:
                    return response.status,response.read(),{key:response.headers[key] for key in ('content-type','access-control-allow-origin') if key in response.headers}
            except (TimeoutError,urllib.error.URLError) as error:
                retryable=not isinstance(error,urllib.error.HTTPError) or error.code in (429,500,502,503,504)
                if attempt or not retryable:
                    raise
                retries.append({'url':url,'reason':str(error)})
                time.sleep(2)
    async def transport(route):
        url=route.request.url
        try:
            async with semaphore:
                status,body,headers=await asyncio.to_thread(download,url,route.request.method,route.request.post_data)
            if '/reference/static_nwm_flowlines' in url and '/export?' in url:
                image=Image.open(io.BytesIO(body)).convert('RGBA')
                pixels=sum(image.getchannel('A').histogram()[1:])
                tiles.append({'service':url.split('/reference/')[1].split('/')[0],
                              'bbox':urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['bbox'][0],
                              'bytes':len(body),'line_pixels':pixels})
            await route.fulfill(status=status,body=body,headers=headers)
        except Exception as error:
            result={'url':url,'error':str(error)}
            (optional_failures if 'tiles.openfreemap.org' in url else failures).append(result)
            print('ASSET ERROR',url,str(error),flush=True)
            await route.abort()
    results=[]
    async with async_playwright() as runner:
        browser=await runner.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1400,'height':1050})
        await page.route('https://**/*',transport)
        page.on('pageerror',lambda error:(failures.append({'script_error':str(error)}),print('PAGE ERROR',str(error),flush=True)))
        await page.goto(args.url)
        print('Loaded prototype page',flush=True)
        await page.wait_for_function("document.querySelector('#status').textContent.includes('NOAA reaches')",timeout=60000)
        await page.evaluate("async()=>{window.__nwmMap=(await import('/web/nwm/map.mjs')).map;}")
        # Broad extent plus distant detail views distinguish national coverage
        # from the original Chicago-only snapshot.
        cases=[('conus',None,None),('west',[-121.5,45.5],7.5),('east',[-75.5,40.5],7.5),
               ('alaska',None,None),('hawaii',None,None),('prvi',None,None)]
        for name,center,zoom in cases:
            start=len(tiles)
            started=time.monotonic()
            if center:
                await page.evaluate("async ([center,zoom])=>{const {map}=await import('/web/nwm/map.mjs');map.jumpTo({center,zoom});}",[center,zoom])
                domain='conus'
            else:
                await page.locator('#'+name).click()
                domain=name
            await page.wait_for_timeout(350)
            await page.wait_for_function("""domain=>{const map=window.__nwmMap;
                const detail=map.getZoom()>=7?'-detail':'';
                return !map.isMoving()&&map.areTilesLoaded()&&map.isSourceLoaded('national-'+domain+detail);}""",arg=domain,timeout=120000)
            relevant=tiles[start:]
            # A previously cached overview may need no new downloads; for each
            # new region, however, require visible line pixels in returned tiles.
            assert relevant and sum(tile['line_pixels'] for tile in relevant)>0,(name,relevant,failures)
            await page.screenshot(path=str(args.output/(name+'.png')))
            result={'view':name,'seconds':round(time.monotonic()-started,2),'tiles':len(relevant),
                    'bytes':sum(tile['bytes'] for tile in relevant),'line_pixels':sum(tile['line_pixels'] for tile in relevant)}
            results.append(result)
            print(json.dumps(result),flush=True)
        await page.locator('#national-geometry').uncheck()
        assert await page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getLayoutProperty('national-conus','visibility');}")=='none'
        (args.output/'results.json').write_text(json.dumps({'views':results,'tiles':tiles,'failures':failures,'optional_basemap_failures':optional_failures,'retries':retries},indent=2)+'\n')
        assert not failures,failures
        await browser.close()
    (args.output/'results.json').write_text(json.dumps({'views':results,'tiles':tiles,'failures':failures,'optional_basemap_failures':optional_failures,'retries':retries},indent=2)+'\n')
    print('PASS: national overview, west/east detail, Alaska, Hawaii and Puerto Rico/USVI geometry',flush=True)


if __name__=='__main__':
    asyncio.run(main())
