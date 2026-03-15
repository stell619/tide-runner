#!/usr/bin/env python3
"""
TIDE RUNNER — Personal Fishing Tool
Backend API server — port 3004
"""

import json, os, re, math, subprocess
import urllib.request
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT      = 3004
HOST      = "0.0.0.0"
CACHE_DIR = os.path.expanduser("~/.openclaw/cache")
TIDE_CACHE = os.path.join(CACHE_DIR, "tides.json")
CATCH_LOG  = os.path.join(CACHE_DIR, "catches.json")

# ── HELPERS ──────────────────────────────────────────────

def jresp(data):
    return json.dumps(data, default=str)

def fetch_url(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "TideRunner/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def moon_phase(dt=None):
    if dt is None: dt = datetime.now()
    known_new = datetime(2000, 1, 6, 18, 14)
    cycle = 29.53058867
    delta = (dt - known_new).total_seconds() / 86400
    phase = (delta % cycle) / cycle
    phases = [
        (0.03,  "New Moon",        "🌑", 100),
        (0.22,  "Waxing Crescent", "🌒", 65),
        (0.28,  "First Quarter",   "🌓", 70),
        (0.47,  "Waxing Gibbous",  "🌔", 75),
        (0.53,  "Full Moon",       "🌕", 95),
        (0.72,  "Waning Gibbous",  "🌖", 75),
        (0.78,  "Last Quarter",    "🌗", 70),
        (1.01,  "Waning Crescent", "🌘", 65),
    ]
    for threshold, name, emoji, score in phases:
        if phase < threshold:
            return {"phase": round(phase,4), "pct": round(phase*100), "name": name, "emoji": emoji, "score": score}
    return {"phase": round(phase,4), "pct": round(phase*100), "name": "Waning Crescent", "emoji": "🌘", "score": 65}

def solunar_times(dt=None):
    """Calculate major/minor solunar feeding times based on moon position"""
    if dt is None: dt = datetime.now()
    known_new = datetime(2000, 1, 6, 18, 14)
    cycle = 29.53058867
    delta = (dt - known_new).total_seconds() / 86400
    phase = (delta % cycle) / cycle
    # Moon transit approximation
    moon_transit_hour = (phase * 24) % 24
    moon_opposite = (moon_transit_hour + 12) % 24
    # Minor periods are 90 degrees off (6 hrs)
    minor1 = (moon_transit_hour + 6) % 24
    minor2 = (moon_transit_hour + 18) % 24

    def fmt(h):
        return f"{int(h):02d}:{int((h % 1) * 60):02d}"

    return {
        "major": [
            {"time": fmt(moon_transit_hour), "label": "Major", "duration": "2h", "rating": "PRIME"},
            {"time": fmt(moon_opposite),     "label": "Major", "duration": "2h", "rating": "PRIME"},
        ],
        "minor": [
            {"time": fmt(minor1), "label": "Minor", "duration": "1h", "rating": "GOOD"},
            {"time": fmt(minor2), "label": "Minor", "duration": "1h", "rating": "GOOD"},
        ]
    }

def fishing_score(tide_range=0, moon_score=70, pressure_trend="stable",
                  wind_speed=0, hour=None, swell=0):
    if hour is None: hour = datetime.now().hour
    # Time score
    if 4 <= hour <= 7 or 17 <= hour <= 20:   time_s = 100
    elif 7 <= hour <= 9 or 15 <= hour <= 17:  time_s = 80
    elif 9 <= hour <= 11 or 13 <= hour <= 15: time_s = 55
    elif 11 <= hour <= 13:                     time_s = 30
    else:                                       time_s = 60  # night
    # Pressure
    pressure_s = {"rising": 85, "stable": 70, "falling": 40}.get(pressure_trend, 70)
    # Wind (lighter = better for most species)
    if wind_speed < 10:   wind_s = 100
    elif wind_speed < 20: wind_s = 75
    elif wind_speed < 30: wind_s = 45
    else:                  wind_s = 20
    # Tide range
    tide_s = min(100, int(tide_range * 55))
    # Swell
    if swell < 0.5:    swell_s = 90
    elif swell < 1.0:  swell_s = 75
    elif swell < 1.5:  swell_s = 55
    else:               swell_s = 30

    score = round(time_s*0.25 + moon_score*0.20 + pressure_s*0.20 + wind_s*0.15 + tide_s*0.15 + swell_s*0.05)
    if score >= 85:   label, stars = "PRIME",   5
    elif score >= 70: label, stars = "GREAT",   4
    elif score >= 55: label, stars = "GOOD",    3
    elif score >= 40: label, stars = "AVERAGE", 2
    else:             label, stars = "POOR",    1
    return {"score": score, "label": label, "stars": stars}

# ── SPECIES DATABASE ──────────────────────────────────────

SPECIES = {
    "bream": {
        "name": "Bream",
        "emoji": "🐟",
        "icon": "#4fc3f7",
        "desc": "Year-round estuary staple. Loves structure and dirty water.",
        "best_season": ["Mar","Apr","May","Jun","Jul","Aug","Sep","Oct"],
        "best_tide": "Incoming tide, 1-2hrs before high",
        "best_time": "Dawn and dusk",
        "best_bait": ["Prawns", "Worms", "Yabbies", "Soft plastics"],
        "best_spots": ["Georges River", "Port Hacking", "Botany Bay"],
        "pressure": "Stable or rising",
        "moon": "New moon and full moon",
        "min_size": 25,
        "bag_limit": 20,
        "conditions": {"wind_max": 20, "tide_pref": "incoming", "moon_pref": [0, 0.5]},
        "tips": "Fish around structure — pontoons, rocks, oyster leases. Use light gear 2-4kg."
    },
    "flathead": {
        "name": "Flathead",
        "emoji": "🐠",
        "icon": "#ff8a65",
        "desc": "Ambush predator. Loves sandy bottoms and drop-offs.",
        "best_season": ["Oct","Nov","Dec","Jan","Feb","Mar"],
        "best_tide": "Outgoing tide, last 2hrs of run",
        "best_time": "Dawn, dusk, and night",
        "best_bait": ["Soft plastics", "Live poddy mullet", "Prawns"],
        "best_spots": ["Georges River", "Port Hacking", "Botany Bay"],
        "pressure": "Stable",
        "moon": "New moon",
        "min_size": 30,
        "bag_limit": 10,
        "conditions": {"wind_max": 25, "tide_pref": "outgoing", "moon_pref": [0, 0.15]},
        "tips": "Work soft plastics along the bottom with a slow lift-drop retrieve. Jighead 1/4-3/8oz."
    },
    "whiting": {
        "name": "Whiting",
        "emoji": "🐡",
        "icon": "#fff176",
        "desc": "Fast, finicky, and delicious. Sandy flats specialist.",
        "best_season": ["Nov","Dec","Jan","Feb","Mar","Apr"],
        "best_tide": "Low to mid incoming tide on sand flats",
        "best_time": "Morning and late afternoon",
        "best_bait": ["Pippies", "Beach worms", "Nippers", "Yabbies"],
        "best_spots": ["Botany Bay", "Port Hacking"],
        "pressure": "Rising",
        "moon": "New and full moon",
        "min_size": 27,
        "bag_limit": 20,
        "conditions": {"wind_max": 15, "tide_pref": "incoming", "moon_pref": [0, 0.1]},
        "tips": "Fish the run-out channels on sand flats. Berley with sand and pippies. Ultra-light gear."
    },
    "kingfish": {
        "name": "Kingfish",
        "emoji": "🐋",
        "icon": "#ab47bc",
        "desc": "Powerful pelagic. Hard fighting, ocean and harbour raider.",
        "best_season": ["Oct","Nov","Dec","Jan","Feb","Mar","Apr"],
        "best_tide": "Strong tidal run, any direction",
        "best_time": "Dawn patrol and last light",
        "best_bait": ["Live yakkas", "Slimies", "Poppers", "Jigs"],
        "best_spots": ["Sydney Harbour", "Port Hacking"],
        "pressure": "Stable or slight drop",
        "moon": "Full moon",
        "min_size": 65,
        "bag_limit": 5,
        "conditions": {"wind_max": 20, "tide_pref": "any", "moon_pref": [0.45, 0.55]},
        "tips": "Find bait schools on the sounder. Live bait on a running sinker rig or surface poppers at dawn."
    },
    "snapper": {
        "name": "Snapper",
        "emoji": "🐸",
        "icon": "#ef5350",
        "desc": "The ultimate Sydney prize. Reef and offshore species.",
        "best_season": ["Aug","Sep","Oct","Nov","Dec","Jan"],
        "best_tide": "Change of tide, slack water",
        "best_time": "Night and early morning",
        "best_bait": ["Whole squid", "Pilchards", "Soft plastics", "Knife jigs"],
        "best_spots": ["Sydney Harbour", "Botany Bay", "Port Hacking offshore"],
        "pressure": "Rising after low",
        "moon": "New moon",
        "min_size": 30,
        "bag_limit": 10,
        "conditions": {"wind_max": 15, "tide_pref": "slack", "moon_pref": [0, 0.1]},
        "tips": "Target reef structure at depth 15-40m. Berley trail of pilchards. Paternoster rig with whole squid."
    },
    "jewfish": {
        "name": "Jewfish / Mulloway",
        "emoji": "🦈",
        "icon": "#26c6da",
        "desc": "The holy grail of Sydney estuary fishing. Nocturnal apex predator.",
        "best_season": ["Apr","May","Jun","Jul","Aug","Sep","Oct"],
        "best_tide": "Bottom of tide, first of the run-in",
        "best_time": "Night — 10pm to 3am prime",
        "best_bait": ["Live mullet", "Live tailor", "Fresh squid", "Large soft plastics"],
        "best_spots": ["Georges River", "Port Hacking", "Botany Bay"],
        "pressure": "Dropping — storm approach",
        "moon": "New moon (dark nights)",
        "min_size": 45,
        "bag_limit": 2,
        "conditions": {"wind_max": 30, "tide_pref": "incoming", "moon_pref": [0, 0.08]},
        "tips": "Fish deep holes and channel edges at night. New moon = dark water = Jew active. Patience is everything."
    }
}

SPOTS = [
    {"id": "georges_river_lugarno", "name": "Lugarno Point", "area": "Georges River",
     "lat": -33.9897, "lon": 151.0631, "depth": "2-8m",
     "species": ["bream","flathead","jewfish"], "type": "Estuary",
     "tips": "Fish the rock wall on incoming tide. Great bream and Jew spot at night.",
     "rating": 5},
    {"id": "georges_river_alfords", "name": "Alfords Point Bridge", "area": "Georges River",
     "lat": -33.9922, "lon": 151.0200, "depth": "3-12m",
     "species": ["jewfish","bream","flathead"], "type": "Bridge",
     "tips": "Night fishing under lights on new moon. Jewfish congregate in the channel.",
     "rating": 5},
    {"id": "georges_river_como", "name": "Como Bridge", "area": "Georges River",
     "lat": -34.0180, "lon": 151.0536, "depth": "4-15m",
     "species": ["jewfish","bream","snapper"], "type": "Bridge",
     "tips": "Deep channel under bridge. Fish the bottom on the run-in tide after dark.",
     "rating": 4},
    {"id": "port_hacking_burraneer", "name": "Burraneer Bay", "area": "Port Hacking",
     "lat": -34.0560, "lon": 151.1020, "depth": "1-5m",
     "species": ["bream","whiting","flathead"], "type": "Bay",
     "tips": "Shallow sand flats for whiting on low tide. Bream around moorings.",
     "rating": 4},
    {"id": "port_hacking_deeban", "name": "Deeban Spit", "area": "Port Hacking",
     "lat": -34.0760, "lon": 151.1080, "depth": "1-4m",
     "species": ["whiting","flathead","bream"], "type": "Sand Flat",
     "tips": "Classic whiting spot on the sand flat. Fish pippies on running sinker rig.",
     "rating": 5},
    {"id": "port_hacking_marley", "name": "Marley Beach", "area": "Port Hacking",
     "lat": -34.1150, "lon": 151.1220, "depth": "5-20m",
     "species": ["kingfish","snapper","flathead"], "type": "Coastal",
     "tips": "Rock fishing for kingies and snapper. Accessible from RNP. Bring live bait.",
     "rating": 4},
    {"id": "botany_bay_towra", "name": "Towra Point", "area": "Botany Bay",
     "lat": -34.0050, "lon": 151.1550, "depth": "2-6m",
     "species": ["bream","flathead","whiting"], "type": "Reserve",
     "tips": "Protected waters. Great for flathead on soft plastics. No fishing in reserve zones.",
     "rating": 3},
    {"id": "botany_bay_brighton", "name": "Brighton Le Sands", "area": "Botany Bay",
     "lat": -33.9640, "lon": 151.1560, "depth": "2-8m",
     "species": ["bream","snapper","kingfish"], "type": "Bay",
     "tips": "Fish the deep channel near the airport. Snapper active at night.",
     "rating": 4},
    {"id": "botany_bay_kurnell", "name": "Kurnell Flats", "area": "Botany Bay",
     "lat": -34.0210, "lon": 151.1990, "depth": "1-5m",
     "species": ["flathead","whiting","bream"], "type": "Sand Flat",
     "tips": "Massive sand flat ideal for wading and light gear. Best on low incoming tide.",
     "rating": 5},
    {"id": "sydney_harbour_spit", "name": "The Spit Bridge", "area": "Sydney Harbour",
     "lat": -33.7985, "lon": 151.2280, "depth": "5-20m",
     "species": ["kingfish","bream","jewfish"], "type": "Bridge",
     "tips": "Strong current under bridge holds kingfish and Jew. Fish the change of tide.",
     "rating": 5},
    {"id": "sydney_harbour_heads", "name": "Harbour Heads", "area": "Sydney Harbour",
     "lat": -33.8335, "lon": 151.2880, "depth": "10-30m",
     "species": ["kingfish","snapper"], "type": "Offshore",
     "tips": "Troll minnows or jig for kingfish around the heads on the run-out tide.",
     "rating": 5},
    {"id": "sydney_harbour_middle", "name": "Middle Harbour", "area": "Sydney Harbour",
     "lat": -33.7920, "lon": 151.2050, "depth": "3-15m",
     "species": ["bream","flathead","jewfish"], "type": "Estuary",
     "tips": "Deep holes hold quality Jew. Bream around yacht moorings. Night is best.",
     "rating": 4},
]

# ── API HANDLERS ──────────────────────────────────────────

def api_conditions():
    now = datetime.now()
    moon = moon_phase(now)
    sol  = solunar_times(now)

    # Weather + marine from Open-Meteo (free, no key)
    weather = {}
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=temperature_2m,apparent_temperature,weathercode,"
               "windspeed_10m,winddirection_10m,surface_pressure,precipitation"
               "&daily=sunrise,sunset,uv_index_max,precipitation_probability_max,"
               "windspeed_10m_max,temperature_2m_max,temperature_2m_min"
               "&hourly=surface_pressure"
               "&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        c = data["current"]
        d = data["daily"]

        # Pressure trend (compare last 3hrs)
        pressures = data.get("hourly", {}).get("surface_pressure", [])
        if len(pressures) >= 4:
            recent = pressures[now.hour] if now.hour < len(pressures) else pressures[-1]
            earlier = pressures[max(0, now.hour-3)]
            diff = recent - earlier
            if diff > 1:    pressure_trend = "rising"
            elif diff < -1: pressure_trend = "falling"
            else:           pressure_trend = "stable"
        else:
            pressure_trend = "stable"
            recent = 1013

        # Wind direction
        def wdir(deg):
            dirs = ["N","NE","E","SE","S","SW","W","NW"]
            return dirs[round(deg/45) % 8]

        WMO = {0:"Clear",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
               51:"Light drizzle",61:"Light rain",63:"Rain",65:"Heavy rain",
               80:"Showers",95:"Thunderstorm"}

        weather = {
            "temp": c["temperature_2m"],
            "feels_like": c["apparent_temperature"],
            "condition": WMO.get(c["weathercode"], "Mixed"),
            "wind_speed": c["windspeed_10m"],
            "wind_dir": wdir(c["winddirection_10m"]),
            "pressure": round(recent, 1),
            "pressure_trend": pressure_trend,
            "sunrise": d["sunrise"][0].split("T")[1],
            "sunset": d["sunset"][0].split("T")[1],
            "uv_max": d["uv_index_max"][0],
            "rain_chance": d["precipitation_probability_max"][0],
            "temp_max": d["temperature_2m_max"][0],
            "temp_min": d["temperature_2m_min"][0],
        }
    except Exception as e:
        weather = {"error": str(e), "pressure_trend": "stable", "wind_speed": 10}

    # Marine data (wave height, water temp)
    marine = {}
    try:
        url = ("https://marine-api.open-meteo.com/v1/marine"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=wave_height,wave_period,wave_direction,ocean_current_speed"
               "&daily=wave_height_max"
               "&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        c = data.get("current", {})
        marine = {
            "wave_height": c.get("wave_height", 0),
            "wave_period": c.get("wave_period", 0),
            "wave_dir": c.get("wave_direction", 0),
            "current_speed": c.get("ocean_current_speed", 0),
        }
    except:
        marine = {"wave_height": 0.5, "wave_period": 8}

    # Load today's tides from cache
    tides_today = []
    tide_range = 1.0
    try:
        with open(TIDE_CACHE) as f:
            cache = json.load(f)
        today_str = now.strftime("%Y-%m-%d")
        for e in cache.get("extremes", []):
            dt_str = e.get("date", "")
            if dt_str[:10] == today_str:
                tides_today.append({
                    "time": dt_str[11:16],
                    "height": round(e["height"], 2),
                    "type": e["type"].upper()
                })
        if len(tides_today) >= 2:
            heights = [t["height"] for t in tides_today]
            tide_range = max(heights) - min(heights)
    except:
        pass

    # Overall score
    score = fishing_score(
        tide_range=tide_range,
        moon_score=moon["score"],
        pressure_trend=weather.get("pressure_trend", "stable"),
        wind_speed=weather.get("wind_speed", 10),
        hour=now.hour,
        swell=marine.get("wave_height", 0)
    )

    # Next tide
    next_tide = None
    for t in tides_today:
        th, tm = map(int, t["time"].split(":"))
        t_mins = th * 60 + tm
        now_mins = now.hour * 60 + now.minute
        if t_mins > now_mins:
            diff = t_mins - now_mins
            next_tide = {**t, "in_mins": diff,
                         "in_str": f"{diff//60}h {diff%60}m" if diff >= 60 else f"{diff}m"}
            break

    # What's biting now
    biting = []
    hour = now.hour
    month = now.strftime("%b")
    for key, sp in SPECIES.items():
        score_sp = 0
        if month in sp["best_season"]: score_sp += 40
        cond = sp["conditions"]
        if weather.get("wind_speed", 10) <= cond["wind_max"]: score_sp += 20
        mp = moon["phase"]
        mp_range = cond["moon_pref"]
        if mp_range[0] <= mp <= mp_range[1] or (1 - mp) <= mp_range[1]: score_sp += 25
        if score_sp >= 50:
            biting.append({"key": key, "name": sp["name"], "emoji": sp["emoji"],
                           "color": sp["icon"], "score": score_sp,
                           "tip": sp["tips"][:80]})
    biting.sort(key=lambda x: -x["score"])

    return jresp({
        "time": now.strftime("%H:%M"),
        "date": now.strftime("%A %d %B"),
        "moon": moon,
        "solunar": sol,
        "weather": weather,
        "marine": marine,
        "tides": tides_today,
        "next_tide": next_tide,
        "score": score,
        "biting": biting[:4],
    })


def api_forecast():
    now = datetime.now()
    days = []

    # Get 7-day weather forecast
    weather_7d = []
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=-33.9558&longitude=151.0617"
               "&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min,"
               "windspeed_10m_max,precipitation_probability_max,uv_index_max,"
               "weathercode"
               "&timezone=Australia/Sydney&forecast_days=7")
        data = fetch_url(url)
        d = data["daily"]
        for i in range(7):
            weather_7d.append({
                "date": d["time"][i],
                "sunrise": d["sunrise"][i].split("T")[1],
                "sunset": d["sunset"][i].split("T")[1],
                "temp_max": d["temperature_2m_max"][i],
                "temp_min": d["temperature_2m_min"][i],
                "wind_max": d["windspeed_10m_max"][i],
                "rain_chance": d["precipitation_probability_max"][i],
                "uv": d["uv_index_max"][i],
            })
    except:
        for i in range(7):
            weather_7d.append({"date": (now + timedelta(days=i)).strftime("%Y-%m-%d"),
                               "wind_max": 15, "rain_chance": 20, "temp_max": 24, "temp_min": 18,
                               "sunrise": "06:15", "sunset": "19:30", "uv": 5})

    # Load tide data from cache
    from collections import defaultdict
    extremes_by_date = defaultdict(list)
    heights_by_date  = defaultdict(list)
    try:
        with open(TIDE_CACHE) as f:
            cache = json.load(f)
        for e in cache.get("extremes", []):
            dt_str = e.get("date","")
            date_part = dt_str[:10]
            time_part = dt_str[11:16]
            extremes_by_date[date_part].append({
                "time": time_part, "height": round(e["height"],2), "type": e["type"].upper()
            })
        for h in cache.get("heights", []):
            dt_str = h.get("date","")
            heights_by_date[dt_str[:10]].append({
                "time": dt_str[11:16], "height": round(h["height"],3)
            })
    except:
        pass

    for i in range(7):
        day_dt  = now + timedelta(days=i)
        day_str = day_dt.strftime("%Y-%m-%d")
        w       = weather_7d[i] if i < len(weather_7d) else {}
        extremes = extremes_by_date.get(day_str, [])
        heights  = heights_by_date.get(day_str, [])
        moon     = moon_phase(day_dt)
        sol      = solunar_times(day_dt)

        tide_range = 0
        if len(extremes) >= 2:
            hs = [e["height"] for e in extremes]
            tide_range = max(hs) - min(hs)

        score = fishing_score(
            tide_range=tide_range,
            moon_score=moon["score"],
            pressure_trend="stable",
            wind_speed=w.get("wind_max", 15),
            hour=6,  # score for dawn fishing
            swell=0.5
        )

        windows = []
        for e in extremes:
            try:
                th, tm = map(int, e["time"].split(":"))
                windows.append(f"{(th-1)%24:02d}:{tm:02d}–{(th+1)%24:02d}:{tm:02d}")
            except:
                pass

        days.append({
            "date":       day_str,
            "label":      "Today" if i==0 else ("Tomorrow" if i==1 else day_dt.strftime("%a %d")),
            "day_full":   day_dt.strftime("%A"),
            "moon":       moon,
            "solunar":    sol,
            "weather":    w,
            "extremes":   extremes,
            "heights":    heights,
            "tide_range": round(tide_range, 2),
            "windows":    windows[:4],
            "score":      score,
        })

    best_day = max(days, key=lambda d: d["score"]["score"]) if days else None
    return jresp({"days": days, "best_day": best_day["label"] if best_day else "Unknown"})


def api_spots():
    now = datetime.now()
    moon = moon_phase(now)
    w_speed = 10
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=windspeed_10m&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        w_speed = data["current"]["windspeed_10m"]
    except:
        pass

    month = now.strftime("%b")
    spots_out = []
    for sp in SPOTS:
        sp_species = []
        for key in sp["species"]:
            if key in SPECIES:
                s = SPECIES[key]
                active = month in s["best_season"]
                sp_species.append({
                    "key": key,
                    "name": s["name"],
                    "emoji": s["emoji"],
                    "color": s["icon"],
                    "active": active
                })
        score_val = sp["rating"] * 18 + (5 if moon["score"] > 80 else 0)
        spots_out.append({**sp, "species_data": sp_species,
                          "score": min(100, score_val)})

    return jresp({"spots": spots_out, "wind": w_speed, "moon": moon})


def api_species():
    now = datetime.now()
    moon = moon_phase(now)
    month = now.strftime("%b")
    w_speed = 10
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=windspeed_10m,surface_pressure"
               "&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        w_speed = data["current"]["windspeed_10m"]
    except:
        pass

    out = []
    for key, sp in SPECIES.items():
        in_season = month in sp["best_season"]
        moon_good = False
        mp = moon["phase"]
        mr = sp["conditions"]["moon_pref"]
        if mr[0] <= mp <= mr[1] or mp > (1 - mr[1]):
            moon_good = True
        wind_ok = w_speed <= sp["conditions"]["wind_max"]

        score = 0
        if in_season: score += 40
        if moon_good:  score += 30
        if wind_ok:    score += 20
        score += 10  # base

        out.append({**sp, "key": key, "in_season": in_season,
                    "moon_good": moon_good, "wind_ok": wind_ok,
                    "current_score": score})

    out.sort(key=lambda x: -x["current_score"])
    return jresp({"species": out, "moon": moon, "month": month, "wind": w_speed})


def api_solunar():
    days_out = []
    now = datetime.now()
    for i in range(7):
        dt = now + timedelta(days=i)
        sol = solunar_times(dt)
        moon = moon_phase(dt)
        days_out.append({
            "date": dt.strftime("%Y-%m-%d"),
            "label": "Today" if i==0 else ("Tomorrow" if i==1 else dt.strftime("%a %d")),
            "moon": moon,
            "solunar": sol,
            "best": moon["score"] >= 85
        })
    return jresp({"days": days_out})


def api_catches(method="GET", body=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    catches = []
    try:
        with open(CATCH_LOG) as f:
            catches = json.load(f)
    except:
        pass

    if method == "POST" and body:
        try:
            new_catch = json.loads(body)
            new_catch["id"] = int(datetime.now().timestamp())
            new_catch["logged_at"] = datetime.now().isoformat()
            catches.insert(0, new_catch)
            with open(CATCH_LOG, "w") as f:
                json.dump(catches, f, indent=2)
            return jresp({"ok": True, "catch": new_catch})
        except Exception as e:
            return jresp({"ok": False, "error": str(e)})

    if method == "DELETE" and body:
        try:
            data = json.loads(body)
            cid = data.get("id")
            catches = [c for c in catches if c.get("id") != cid]
            with open(CATCH_LOG, "w") as f:
                json.dump(catches, f, indent=2)
            return jresp({"ok": True})
        except Exception as e:
            return jresp({"ok": False, "error": str(e)})

    # Stats
    total = len(catches)
    by_species = {}
    by_spot    = {}
    best_catch = None
    for c in catches:
        sp = c.get("species","unknown")
        by_species[sp] = by_species.get(sp, 0) + 1
        loc = c.get("location","unknown")
        by_spot[loc] = by_spot.get(loc, 0) + 1
        if c.get("weight") and (not best_catch or c["weight"] > best_catch.get("weight",0)):
            best_catch = c

    return jresp({
        "catches": catches,
        "total": total,
        "by_species": by_species,
        "by_spot": by_spot,
        "best_catch": best_catch,
    })


# ── HTTP SERVER ───────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        path = urlparse(self.path).path
        routes = {
            "/api/conditions": lambda: api_conditions(),
            "/api/forecast":   lambda: api_forecast(),
            "/api/spots":      lambda: api_spots(),
            "/api/species":    lambda: api_species(),
            "/api/solunar":    lambda: api_solunar(),
            "/api/catches":    lambda: api_catches("GET"),
        }
        if path in routes:
            try:
                body = routes[path]()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body.encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif path in ("/", "/index.html"):
            try:
                sd = os.path.dirname(os.path.abspath(__file__))
                with open(os.path.join(sd, "index.html"), "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(content)
            except:
                self.send_response(404); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else None
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if path == "/api/catches":
            self.wfile.write(api_catches("POST", body).encode())
        else:
            self.wfile.write(json.dumps({"error": "not found"}).encode())

    def do_DELETE(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else None
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if path == "/api/catches":
            self.wfile.write(api_catches("DELETE", body).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"🎣 TIDE RUNNER running at http://0.0.0.0:{PORT}")
    print(f"   Local:     http://localhost:{PORT}")
    print(f"   Tailscale: http://100.123.216.110:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
