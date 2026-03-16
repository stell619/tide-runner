#!/usr/bin/env python3
"""
Tide Runner — Tide Data Fetcher
Fetches 7 days of tide predictions from WorldTides API.
Run twice weekly via cron (Mon & Thu midnight).

Usage:
    python3 fetch_tides.py

Requires WORLDTIDES_API_KEY in .env file.
Caches to ./cache/tides.json (relative to this script).
"""

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Load .env ────────────────────────────────────────────
_env = Path(__file__).parent / ".env"
if _env.exists():
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# ── CONFIG ───────────────────────────────────────────────
API_KEY    = os.environ.get("WORLDTIDES_API_KEY", "")
LAT        = float(os.environ.get("LATITUDE",  "-33.9558"))
LON        = float(os.environ.get("LONGITUDE", "151.0617"))
LOCATION   = os.environ.get("LOCATION_NAME", "Port Hacking, NSW")
DAYS       = 7
CACHE_DIR  = Path(__file__).parent / "cache"
CACHE_FILE = CACHE_DIR / "tides.json"


def fetch():
    if not API_KEY:
        raise ValueError(
            "WORLDTIDES_API_KEY not set. "
            "Add it to your .env file."
        )

    CACHE_DIR.mkdir(exist_ok=True)

    url = (
        f"https://www.worldtides.info/api/v3"
        f"?extremes&heights"
        f"&date=today"
        f"&lat={LAT}&lon={LON}"
        f"&days={DAYS}"
        f"&datum=CD"
        f"&localtime"
        f"&timezone"
        f"&step=900"
        f"&key={API_KEY}"
    )

    print(f"🌊 Fetching {DAYS}-day tide data...")
    print(f"   Location: {LOCATION} ({LAT}, {LON})")

    req = urllib.request.Request(
        url, headers={"User-Agent": "TideRunner/2.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())

    if data.get("status") != 200:
        raise Exception(f"API error: {data.get('error', 'unknown')}")

    data["_fetched_at"] = datetime.now().isoformat()
    data["_fetch_date"] = datetime.now().strftime("%Y-%m-%d")
    data["_location"]   = LOCATION
    data["_lat"]        = LAT
    data["_lon"]        = LON

    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Cached to {CACHE_FILE}")
    print(f"   Extremes : {len(data.get('extremes', []))} tide events")
    print(f"   Heights  : {len(data.get('heights', []))} data points")
    print(f"   Credits  : {data.get('callCount', '?')} used this call")
    print(f"   Station  : {data.get('station', 'background data')}")


if __name__ == "__main__":
    try:
        fetch()
    except Exception as e:
        print(f"❌ Tide fetch failed: {e}")
        raise SystemExit(1)
