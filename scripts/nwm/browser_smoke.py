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
    # The regional nwm overlay was deliberately removed. Use the current real-data checks.
    from spec_smoke import main as validate
    await validate()

if __name__ == '__main__':
    asyncio.run(main())
