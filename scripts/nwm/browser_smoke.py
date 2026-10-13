#!/usr/bin/env python3
"""Optional real-browser checks; requires Playwright and system Chromium.

External assets use urllib's existing verified HTTPS transport because the cloud
proxy CA is not available in Chromium's trust store. TLS verification stays on.
"""
import argparse
import asyncio
import json
import urllib.request
import urllib.error
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]


def download(url,method="GET",payload=None):
    request=urllib.request.Request(url,data=payload.encode() if payload else None,method=method,headers={"User-Agent":"PaddlersMapPrototypeValidation/1.0",**({"Content-Type":"application/x-www-form-urlencoded"} if payload else {})})
    try:
        response=urllib.request.urlopen(request,timeout=45)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        headers={key:response.headers[key] for key in ("content-type","access-control-allow-origin") if key in response.headers}
        return response.status,response.read(),headers


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000/nwm-prototype.html')
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--screenshot', default='/tmp/nwm-prototype.png')
    args = parser.parse_args()
    launches = json.loads((ROOT / 'data/putins_consolidated.geojson').read_text())
    semaphore=asyncio.Semaphore(4)
    async def transport(route):
        try:
            async with semaphore:
                status,body,headers=await asyncio.to_thread(download,route.request.url,route.request.method,route.request.post_data)
            await route.fulfill(status=status,body=body,headers=headers)
        except Exception as error:
            print("External asset unavailable:",route.request.url,error,flush=True)
            await route.abort()
    async with async_playwright() as runner:
        browser = await runner.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1400, 'height': 950})
        await page.route('https://**/*', transport)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto(args.url)
        await page.wait_for_function("document.querySelector('#status').textContent.includes('NOAA reaches')", timeout=60000)
        await page.evaluate("async()=>{window.__nwmMap=(await import('/web/nwm/map.mjs')).map;}")
        await page.wait_for_function("()=>{const map=window.__nwmMap;return map.queryRenderedFeatures({layers:['nwm']}).length>0;}")
        result = await page.evaluate("""async()=>{const {map}=await import('/web/nwm/map.mjs');
            return {lines:map.queryRenderedFeatures({layers:['nwm']}).length,
                    launches:map.queryRenderedFeatures({layers:['launches']}).length,
                    records:map.getSource('launches').serialize().data.features.map(f=>[f.properties.id,f.geometry]),
                    layers:map.getStyle().layers.map(l=>l.id)};}""")
        assert result['lines'] > 0 and result['launches'] > 0
        assert result['records'] == [[f['properties']['id'], f['geometry']] for f in launches['features']]
        assert result['layers'].index('nwm') < result['layers'].index('launches')
        await page.screenshot(path=args.screenshot)
        await page.locator('#launches').uncheck()
        assert await page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getLayoutProperty('launches','visibility');}") == 'none'
        # Click an actual rendered river, then verify the numerical popup.
        point = await page.evaluate("""async()=>{const {map}=await import('/web/nwm/map.mjs');
            const feature=map.queryRenderedFeatures({layers:['nwm']}).find(f=>f.properties.scale_position!==null);
            const coordinates=feature.geometry.type==='MultiLineString'?feature.geometry.coordinates[0]:feature.geometry.coordinates;
            const xy=coordinates[Math.floor(coordinates.length/2)];map.setCenter(xy);map.setZoom(12);
            const rect=map.getCanvas().getBoundingClientRect();const pixel=map.project(xy);
            return {x:rect.x+pixel.x,y:rect.y+pixel.y};}""")
        await page.wait_for_timeout(400)
        await page.mouse.click(point['x'], point['y'])
        await page.wait_for_selector('.maplibregl-popup-content')
        text = await page.locator('.maplibregl-popup-content').inner_text()
        for label in ['NWM feature ID:', 'Current discharge:', 'Low anchor:', 'Central anchor:', 'Upper anchor:', 'Scale position:']:
            assert label in text, text
        await page.locator('.maplibregl-popup-close-button').click()
        await page.locator('#launches').check()
        feature = launches['features'][0]
        point = await page.evaluate("""async xy=>{const {map}=await import('/web/nwm/map.mjs');map.setCenter(xy);map.setZoom(12);
            const rect=map.getCanvas().getBoundingClientRect(),pixel=map.project(xy);return {x:rect.x+pixel.x,y:rect.y+pixel.y};}""", feature['geometry']['coordinates'])
        await page.wait_for_timeout(400)
        await page.mouse.click(point['x'], point['y'])
        await page.wait_for_selector('.maplibregl-popup-content')
        assert feature['properties']['name'] in await page.locator('.maplibregl-popup-content').inner_text()
        await page.locator('.maplibregl-popup-close-button').click()
        await page.locator('#noaa-comparison').check()
        assert await page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getLayoutProperty('noaa-comparison','visibility');}") == 'visible'
        await page.wait_for_function("()=>{const map=window.__nwmMap;return map.isSourceLoaded('noaa-comparison');}", timeout=60000)
        await page.screenshot(path=str(Path(args.screenshot).with_name('nwm-noaa-comparison.png')))
        # A NOAA snapshot failure must not remove the independent launch overlay.
        await page.route('**/web/nwm/data/manifest.json', lambda route: route.fulfill(status=503, body='Unavailable'))
        await page.goto(args.url)
        await page.wait_for_function("document.querySelector('#status').textContent.includes('NOAA data unavailable')", timeout=60000)
        assert await page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getSource('launches').serialize().data.features.length;}") == len(launches['features'])
        assert not errors, errors
        print(f"PASS: {result['lines']} rendered river features, {len(launches['features'])} unmoved launch records, river/launch popups and toggles", flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
