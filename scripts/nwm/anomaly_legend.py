#!/usr/bin/env python3
"""Cache the exact NOAA seven-day anomaly legend (no invented normal category)."""
from datetime import datetime,timezone
from pathlib import Path
from retrieve import get,write
URL='https://maps.water.noaa.gov/server/rest/services/nwm/ana_anomaly/MapServer/legend'
if __name__=='__main__':
    layer=next(layer for layer in get(URL,{}).get('layers',[]) if layer['layerId']==0)
    if not layer.get('legend') or any(item.get('contentType')!='image/png' or not item.get('imageData') or not item.get('label') for item in layer['legend']):
        raise ValueError('NOAA legend is unavailable or its symbol format changed; previous cache retained')
    write(Path(__file__).resolve().parents[2]/'web/nwm/anomaly-legend.json',{'source':URL+'?f=pjson','retrieved_at':datetime.now(timezone.utc).isoformat(),'layer':layer})
