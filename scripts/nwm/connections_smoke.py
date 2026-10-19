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
OUT = ROOT / 'docs/nwm/primary-validation'


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
            sample=await page.evaluate("""async()=>{const {eligibleSections}=await import('/web/nwm/gauges.mjs'),[a,o,g]=await Promise.all(['assignments.json','observations.json','geometry.geojson'].map(n=>fetch('/web/nwm/gauges/'+n).then(r=>r.json())));const ready=eligibleSections(a,o.records),s=ready.find(s=>s.upstream==='DMPI2'&&s.downstream==='RVFI2')||ready.find(s=>{const c=o.records[s.upstream].coordinates;return c&&c[0]>-90&&c[0]<-86&&c[1]>40&&c[1]<43;});if(!s)throw Error('No eligible Chicago bracket');const id=s.reach_ids[Math.floor(s.reach_ids.length/2)],f=g.features.find(f=>f.properties.feature_id===id),line=f.geometry.coordinates[0];return {id,up:s.upstream,down:s.downstream,xy:line[Math.floor(line.length/2)]};}""")
            await page.evaluate('sample=>{window.sampleId=sample.id;m.jumpTo({center:sample.xy,zoom:13});}',sample)
            await page.wait_for_function("m.getSource('nwm-live')?.serialize().data.features.some(f=>f.properties.feature_id===window.sampleId&&f.properties.color_source==='Observed gauge-to-gauge')", timeout=180000)
            # Let live geometry replace the generalized static cache before comparing toggle geometry.
            await page.wait_for_function("m.getSource('nwm-live')?.serialize().data.features.some(f=>f.properties.feature_id===window.sampleId&&!f.properties.geometry_source)", timeout=180000)
            await page.wait_for_function("m.queryRenderedFeatures({layers:['nwm-live']}).some(f=>f.properties.feature_id===window.sampleId)", timeout=60000)
            actual = await page.evaluate("m.getSource('nwm-live').serialize().data.features.find(f=>f.properties.feature_id===window.sampleId)")
            props = actual['properties']; evidence = json.loads(props['gauge_provenance'])
            positions = [(evidence[k]['stage'] - evidence[k]['low']) / (evidence[k]['flood'] - evidence[k]['low']) for k in ['upstream_observation', 'downstream_observation']]
            expected = sum(max(0, min(1, v)) for v in positions) / 2
            assert abs(props['observed_position'] - expected) < 1e-10
            assert evidence['upstream'] == sample['up'] and evidence['downstream'] == sample['down']
            point = await page.evaluate("""()=>{const f=m.getSource('nwm-live').serialize().data.features.find(f=>f.properties.feature_id===window.sampleId),r=m.getCanvas().getBoundingClientRect();const lines=f.geometry.type==='MultiLineString'?f.geometry.coordinates:[f.geometry.coordinates];for(const line of lines){const i=Math.floor((line.length-1)/2),xy=[(line[i][0]+line[i+1][0])/2,(line[i][1]+line[i+1][1])/2];const p=m.project(xy);if(p.x>25&&p.y>25&&p.x<r.width-25&&p.y<r.height-25)return {x:r.x+p.x,y:r.y+p.y};}throw Error('No visible vertex');}""")
            await page.wait_for_timeout(1500)
            await page.mouse.click(point['x'], point['y'])
            await page.wait_for_selector('.maplibregl-popup-content')
            await page.locator('.maplibregl-popup-content summary').click()
            popup = await page.locator('.maplibregl-popup-content').inner_text()
            assert all(s in popup for s in ['Observed gauge-to-gauge', sample['id'], sample['up'], sample['down'], 'Observed section position:', 'Current discharge:']), popup
            await page.screenshot(path=str(OUT / 'chicago-connected.png'), timeout=90000)
            await page.locator('.maplibregl-popup-close-button').click()
            await page.locator('#gauge-colors').uncheck()
            await page.wait_for_function("m.getSource('nwm-live').serialize().data.features.some(f=>f.properties.feature_id===window.sampleId)", timeout=180000)
            fallback = await page.evaluate("m.getSource('nwm-live').serialize().data.features.find(f=>f.properties.feature_id===window.sampleId)")
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
