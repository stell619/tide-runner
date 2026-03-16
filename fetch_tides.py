#!/usr/bin/env python3
"""
Orion Tide Fetcher
Fetches 7 days of tide data from WorldTides API
Run twice a week via cron (Mon & Thu midnight)
Caches to ~/.openclaw/cache/tides.json
"""

import urllib.request
import json
import os
from datetime import datetime

# ── CONFIG ───────────────────────────────────────────────
API_KEY = os.environ.get("WORLDTIDES_API_KEY", "")
LAT       = -33.9558   # Peakhurst / Port Hacking, Sydney
LON       = 151.0617
DAYS      = 7
CACHE_DIR = os.path.expanduser("~/.openclaw/cache")
CACHE_FILE = os.path.join(CACHE_DIR, "tides.json")

def fetch():
    os.makedirs(CACHE_DIR, exist_ok=True)

    url = (
        f"https://www.worldtides.info/api/v3"
        f"?extremes&heights"
        f"&date=today"
        f"&lat={LAT}&lon={LON}"
        f"&days={DAYS}"
        f"&datum=CD"
        f"&localtime"
        f"&timezone"
        f"&step=900"   # 15 min intervals for smooth graph
        f"&key={API_KEY}"
    )

    print(f"Fetching tides from WorldTides API...")
    print(f"URL: {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "OrionDashboard/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())

    if data.get("status") != 200:
        raise Exception(f"API error: {data.get('error', 'unknown')}")

    # Add fetch metadata
    data["_fetched_at"] = datetime.now().isoformat()
    data["_fetch_date"] = datetime.now().strftime("%Y-%m-%d")
    data["_location"]   = "Port Hacking, NSW"
    data["_lat"]        = LAT
    data["_lon"]        = LON

    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    extremes_count = len(data.get("extremes", []))
    heights_count  = len(data.get("heights", []))
    credits_used   = data.get("callCount", "?")

    print(f"✅ Tides cached to {CACHE_FILE}")
    print(f"   Extremes: {extremes_count} tide events")
    print(f"   Heights:  {heights_count} data points")
    print(f"   Credits used: {credits_used}")
    print(f"   Station: {data.get('station', 'background data')}")
    print(f"   Copyright: {data.get('copyright', '')}")

if __name__ == "__main__":
    try:
        fetch()
    except Exception as e:
        print(f"❌ Tide fetch failed: {e}")
        # Send Telegram alert via Orion
        os.system(f'openclaw message --agent main "⚠️ Tide fetch failed: {e}" 2>/dev/null')
        exit(1)
