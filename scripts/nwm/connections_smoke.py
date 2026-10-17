#!/usr/bin/env python3
"""Render actual connected Chicago reaches, inspect popup evidence and model fallback.

Serve the repository on port 8001 first. External HTTPS uses the verified cloud CA.
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_smoke import download

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/nwm/connection-validation'


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    errors = []; failures = []; sem = asyncio.Semaphore(5)
    async def transport(route):
        try:
            async with sem:
                if route.request.failure: return
                status, body, headers = await asyncio.to_thread(download, route.request.url, route.request.method, route.request.post_data)
            if status >= 400: failures.append({'url': route.request.url, 'status': status})
            await route.fulfill(status=status, body=body, headers=headers)
        except Exception as exc:
            failures.append({'url': route.request.url, 'error': str(exc)})
            await route.abort()
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            page = await browser.new_page(viewport={'width': 1200, 'height': 950})
            page.on('pageerror', lambda e: errors.append(str(e)))
            await page.route('https://**/*', transport)
            await page.goto('http://127.0.0.1:8001/nwm-prototype.html')
            await page.wait_for_function("document.querySelector('#status').textContent.includes('canonical')", timeout=60000)
            await page.evaluate("async()=>{window.m=(await import('/web/nwm/map.mjs')).map;}")
            await page.evaluate("()=>{m.jumpTo({center:[-87.885,42.055],zoom:11});}")
            await page.wait_for_function("m.getSource('nwm-live')?.serialize().data.features.some(f=>f.properties.feature_id==='14784631'&&f.properties.color_source==='Observed gauge-to-gauge')", timeout=180000)
            actual = await page.evaluate("m.getSource('nwm-live').serialize().data.features.find(f=>f.properties.feature_id==='14784631')")
            props = actual['properties']; evidence = json.loads(props['gauge_provenance'])
            positions = [(evidence[k]['stage'] - evidence[k]['low']) / (evidence[k]['flood'] - evidence[k]['low']) for k in ['upstream_observation', 'downstream_observation']]
            expected = sum(max(0, min(1, v)) for v in positions) / 2
            assert abs(props['observed_position'] - expected) < 1e-10
            assert evidence['upstream'] == 'DSPI2' and evidence['downstream'] == 'DMPI2'
            point = await page.evaluate("""()=>{const f=m.getSource('nwm-live').serialize().data.features.find(f=>f.properties.feature_id==='14784631'),r=m.getCanvas().getBoundingClientRect();const lines=f.geometry.type==='MultiLineString'?f.geometry.coordinates:[f.geometry.coordinates];for(const line of lines)for(const xy of line){const p=m.project(xy);if(p.x>25&&p.y>25&&p.x<r.width-25&&p.y<r.height-25)return {x:r.x+p.x,y:r.y+p.y};}throw Error('No visible vertex');}""")
            await page.wait_for_timeout(1500)
            await page.mouse.click(point['x'], point['y'])
            await page.wait_for_selector('.maplibregl-popup-content')
            popup = await page.locator('.maplibregl-popup-content').inner_text()
            assert all(s in popup for s in ['Observed gauge-to-gauge', '14784631', 'DSPI2', 'DMPI2', 'Observed section position:', 'Current discharge:']), popup
            await page.screenshot(path=str(OUT / 'chicago-connected.png'), timeout=90000)
            await page.locator('.maplibregl-popup-close-button').click()
            await page.locator('#gauge-colors').uncheck()
            fallback = await page.evaluate("m.getSource('nwm-live').serialize().data.features.find(f=>f.properties.feature_id==='14784631')")
            assert fallback['properties']['color_source'] == 'Modeled NWM'
            assert fallback['geometry'] == actual['geometry']
            await page.locator('#gauge-colors').check()
            await page.locator('#noaa-comparison').check()
            assert await page.evaluate("m.getLayoutProperty('nwm-live','visibility')") == 'none'
            await page.locator('#noaa-comparison').uncheck()
            assert await page.evaluate("m.getStyle().layers.at(-1).id") == 'launches'
            assert not errors, errors
            (OUT / 'browser.json').write_text(json.dumps({'feature': actual, 'expected_position': expected, 'fallback': fallback['properties'], 'popup': popup, 'page_errors': errors, 'external_failures': failures, 'checks': ['Actual NOAA geometry rendered', 'Mean of independently normalized endpoint stages', 'Clickable observed provenance', 'Toggle restores modeled colors with unchanged geometry', 'NOAA comparison hides custom lines', 'Launches above rivers']}, indent=2) + '\n')
            print(json.dumps({'observed_feature_id': props['feature_id'], 'position': expected, 'page_errors': errors, 'external_failures': len(failures)}), flush=True)
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
