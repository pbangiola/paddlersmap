#!/usr/bin/env python3
"""Optional real-browser checks; requires Playwright and system Chromium.

External assets use urllib's existing verified HTTPS transport because the cloud
proxy CA is not available in Chromium's trust store. TLS verification stays on.
"""
import argparse
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def transport(route):
    request = urllib.request.Request(route.request.url, headers={"User-Agent": "PaddlersMapPrototypeValidation/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            headers = {key: response.headers[key] for key in ("content-type", "access-control-allow-origin") if key in response.headers}
            route.fulfill(status=response.status, body=response.read(), headers=headers)
    except Exception as error:
        print("External asset unavailable:", route.request.url, error, flush=True)
        route.abort()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000/nwm-prototype.html')
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--screenshot', default='/tmp/nwm-prototype.png')
    args = parser.parse_args()
    launches = json.loads((ROOT / 'data/putins_consolidated.geojson').read_text())
    with sync_playwright() as runner:
        browser = runner.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1400, 'height': 950})
        page.route('https://**/*', transport)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.wait_for_function("document.querySelector('#status').textContent.includes('NOAA reaches')", timeout=60000)
        page.wait_for_function("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.queryRenderedFeatures({layers:['nwm']}).length>0;}")
        result = page.evaluate("""async()=>{const {map}=await import('/web/nwm/map.mjs');
            return {lines:map.queryRenderedFeatures({layers:['nwm']}).length,
                    launches:map.queryRenderedFeatures({layers:['launches']}).length,
                    records:map.getSource('launches').serialize().data.features.map(f=>[f.properties.id,f.geometry]),
                    layers:map.getStyle().layers.map(l=>l.id)};}""")
        assert result['lines'] > 0 and result['launches'] > 0
        assert result['records'] == [[f['properties']['id'], f['geometry']] for f in launches['features']]
        assert result['layers'].index('nwm') < result['layers'].index('launches')
        page.screenshot(path=args.screenshot)
        page.locator('#launches').uncheck()
        assert page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getLayoutProperty('launches','visibility');}") == 'none'
        # Click an actual rendered river, then verify the numerical popup.
        point = page.evaluate("""async()=>{const {map}=await import('/web/nwm/map.mjs');
            const feature=map.queryRenderedFeatures({layers:['nwm']}).find(f=>f.properties.scale_position!==null);
            const coordinates=feature.geometry.type==='MultiLineString'?feature.geometry.coordinates[0]:feature.geometry.coordinates;
            const xy=coordinates[Math.floor(coordinates.length/2)];map.setCenter(xy);map.setZoom(12);
            const rect=map.getCanvas().getBoundingClientRect();const pixel=map.project(xy);
            return {x:rect.x+pixel.x,y:rect.y+pixel.y};}""")
        page.wait_for_timeout(400)
        page.mouse.click(point['x'], point['y'])
        page.wait_for_selector('.maplibregl-popup-content')
        text = page.locator('.maplibregl-popup-content').inner_text()
        for label in ['NWM feature ID:', 'Current discharge:', 'Low anchor:', 'Central anchor:', 'Upper anchor:', 'Scale position:']:
            assert label in text, text
        page.locator('.maplibregl-popup-close-button').click()
        page.locator('#launches').check()
        feature = launches['features'][0]
        point = page.evaluate("""async xy=>{const {map}=await import('/web/nwm/map.mjs');map.setCenter(xy);map.setZoom(12);
            const rect=map.getCanvas().getBoundingClientRect(),pixel=map.project(xy);return {x:rect.x+pixel.x,y:rect.y+pixel.y};}""", feature['geometry']['coordinates'])
        page.wait_for_timeout(400)
        page.mouse.click(point['x'], point['y'])
        page.wait_for_selector('.maplibregl-popup-content')
        assert feature['properties']['name'] in page.locator('.maplibregl-popup-content').inner_text()
        page.locator('.maplibregl-popup-close-button').click()
        page.locator('#noaa-comparison').check()
        assert page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getLayoutProperty('noaa-comparison','visibility');}") == 'visible'
        page.wait_for_function("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.isSourceLoaded('noaa-comparison');}", timeout=60000)
        page.screenshot(path=str(Path(args.screenshot).with_name('nwm-noaa-comparison.png')))
        # A NOAA snapshot failure must not remove the independent launch overlay.
        page.route('**/web/nwm/data/manifest.json', lambda route: route.fulfill(status=503, body='Unavailable'))
        page.goto(args.url)
        page.wait_for_function("document.querySelector('#status').textContent.includes('NOAA data unavailable')", timeout=60000)
        assert page.evaluate("async()=>{const {map}=await import('/web/nwm/map.mjs');return map.getSource('launches').serialize().data.features.length;}") == len(launches['features'])
        assert not errors, errors
        print(f"PASS: {result['lines']} rendered river features, {len(launches['features'])} unmoved launch records, river/launch popups and toggles", flush=True)
        browser.close()


if __name__ == '__main__':
    main()
