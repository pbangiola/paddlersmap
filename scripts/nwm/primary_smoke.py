#!/usr/bin/env python3
"""Validate the promoted map, absent legacy layers and connected-only gauges.

The offline-flow scenario still uses real, cached NOAA river geometry and readings.
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
    errors = []; failures = []; requests = []; sem = asyncio.Semaphore(5)
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
            page.on('request', lambda r: requests.append(r.url))
            await page.route('https://**/*', transport)
            # Fail modeled-flow requests deliberately: observed paths must not depend on them.
            await page.route('**/nwm/ana_anomaly/MapServer/0/**', lambda r: r.fulfill(status=503, body='{"error":{"message":"Deliberate outage test"}}', content_type='application/json'))
            for entry in ['nwm-prototype.html', 'gauge-connections.html']:
                await page.goto('http://127.0.0.1:8001/' + entry)
                await page.wait_for_url('http://127.0.0.1:8001/')
                await page.wait_for_function("document.querySelector('#status')?.textContent.includes('canonical')", timeout=60000)
            await page.evaluate("async()=>{window.m=(await import('/web/nwm/map.mjs')).map;}")
            await page.wait_for_function("m.getSource('connected-gauges')?.serialize().data.features.length>0", timeout=60000)
            summary = await page.evaluate("""async()=>{const [{eligibleSections,observedPosition},a,o,g]=await Promise.all([import('/web/nwm/gauges.mjs'),fetch('/web/nwm/gauges/assignments.json').then(r=>r.json()),fetch('/web/nwm/gauges/observations.json').then(r=>r.json()),fetch('/web/nwm/gauges/geometry.geojson').then(r=>r.json())]);const available=new Set(g.features.map(f=>String(f.properties.feature_id))),sections=eligibleSections(a,o.records,Date.now(),o.max_age_hours).filter(s=>s.reach_ids.every(id=>available.has(String(id)))),ids=new Set(sections.flatMap(s=>[s.upstream,s.downstream]));const fs=m.getSource('connected-gauges').serialize().data.features;return {markers:fs.length,valid:fs.every(f=>ids.has(f.properties.id)&&observedPosition(f.properties)!==null),noLegacy:m.getStyle().layers.every(l=>!['gauges','expanded-gauges','noaa-national-gauges','name-connections','river-routes','rivers'].includes(l.id)),launches:m.getSource('launches').serialize().data.features.map(f=>[f.properties.id,f.geometry])};}""")
            assert summary['markers'] > 0 and summary['valid'] and summary['noLegacy'], summary
            canonical=json.loads((ROOT/'web/nwm/launches/canonical.geojson').read_text())['features']
            assert summary['launches'] == [[f['properties']['id'], f['geometry']] for f in canonical]
            del summary['launches']
            chicago=await page.evaluate("""async()=>{const {eligibleSections}=await import('/web/nwm/gauges.mjs'),[a,o,g]=await Promise.all(['assignments.json','observations.json','geometry.geojson'].map(n=>fetch('/web/nwm/gauges/'+n).then(r=>r.json()))),ready=eligibleSections(a,o.records),s=ready.find(s=>s.upstream==='DMPI2'&&s.downstream==='RVFI2')||ready.find(s=>{const c=o.records[s.upstream].coordinates;return c&&c[0]>-90&&c[0]<-86&&c[1]>40&&c[1]<43;});if(!s)throw Error('No eligible Chicago bracket');const id=s.reach_ids[Math.floor(s.reach_ids.length/2)],f=g.features.find(f=>f.properties.feature_id===id),line=f.geometry.coordinates[0];return {id,xy:line[Math.floor(line.length/2)]};}""")
            await page.evaluate('sample=>{window.sampleId=sample.id;m.jumpTo({center:sample.xy,zoom:13});}',chicago)
            await page.wait_for_function("m.queryRenderedFeatures({layers:['nwm-live']}).some(f=>f.properties.feature_id===window.sampleId&&f.properties.color_source==='Observed gauge-to-gauge')", timeout=60000)
            summary['observed_during_flow_outage'] = chicago['id']
            assert await page.evaluate("m.getStyle().layers.at(-1).id") == 'launches'
            await page.locator('#show-gauges').uncheck()
            assert await page.evaluate("m.getLayoutProperty('connected-gauges','visibility')") == 'none'
            await page.locator('#show-gauges').check()
            await page.screenshot(path=str(OUT / 'primary-chicago.png'), timeout=90000)
            sample=await page.evaluate("""async()=>{const {eligibleSections}=await import('/web/nwm/gauges.mjs'),[a,o,g]=await Promise.all(['assignments.json','observations.json','geometry.geojson'].map(n=>fetch('/web/nwm/gauges/'+n).then(r=>r.json()))),ids=new Set(eligibleSections(a,o.records).flatMap(s=>s.reach_ids.map(String)));const f=g.features.find(f=>ids.has(f.properties.feature_id)&&f.properties.geometry_source.includes('_prvi/'));if(!f)return null;const line=f.geometry.coordinates[0];return {id:f.properties.feature_id,xy:line[Math.floor(line.length/2)]};}""")
            if sample:
                await page.evaluate('xy=>{m.jumpTo({center:xy,zoom:13});}',sample['xy'])
                await page.wait_for_function("id=>m.queryRenderedFeatures({layers:['nwm-live']}).some(f=>f.properties.feature_id===id&&f.properties.color_source==='Observed gauge-to-gauge')",arg=sample['id'],timeout=60000)
                summary['prvi_observed_during_flow_outage']=sample['id']
                await page.screenshot(path=str(OUT / 'primary-prvi.png'),timeout=90000)
            else: summary['prvi_observed_during_flow_outage']=None
            await page.locator('#noaa-comparison').check()
            assert await page.evaluate("m.getLayoutProperty('connected-gauges','visibility')") == 'none'
            assert await page.evaluate("m.getLayoutProperty('nwm-live','visibility')") == 'none'
            banned = ['web/app.js','web/gauge-connections.js','river_segments_3dhp_review','gauges_expansion.geojson','waterways_expansion.geojson','canoe_routes']
            assert not any(any(x in u for x in banned) for u in requests)
            assert not errors, errors
            summary.update({'page_errors': errors, 'external_failures': failures, 'launch_count': len(canonical), 'no_legacy_requests': True})
            (OUT / 'primary-browser.json').write_text(json.dumps(summary, indent=2)+'\n')
            print(json.dumps(summary), flush=True)
        finally:
            await browser.close()

if __name__ == '__main__': asyncio.run(main())
