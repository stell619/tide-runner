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
    """Calculate major/minor solunar feeding times based on moon position."""
    if dt is None: dt = datetime.now()
    known_new = datetime(2000, 1, 6, 18, 14)
    cycle = 29.53058867
    delta = (dt - known_new).total_seconds() / 86400
    phase = (delta % cycle) / cycle
    moon_transit_hour = (phase * 24) % 24
    moon_opposite = (moon_transit_hour + 12) % 24
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
                  wind_speed=0, hour=None, swell=0, water_temp=None):
    """
    Composite fishing score 0-100.

    Weights:
      Time of day    20%  — dawn/dusk windows are peak feeding times
      Moon phase     20%  — new/full moon drives tidal variance & fish activity
      Pressure trend 20%  — rising pressure = fish feed actively
      Wind speed     15%  — lighter wind = better presentation & calmer water
      Tide range     15%  — moderate range (0.8-1.8m) is ideal; extremes reduce it
      Water temp     10%  — species-specific optimal ranges (new)
      Swell height    5%  — low swell = accessible spots & cleaner water
    """
    if hour is None: hour = datetime.now().hour

    # ── Time of day (20%) ────────────────────────────────
    # Dawn (4-8am) and dusk (5-8pm) are peak feeding windows
    if 4 <= hour <= 7 or 17 <= hour <= 20:    time_s = 100
    elif 7 <= hour <= 9 or 15 <= hour <= 17:   time_s = 80
    elif 9 <= hour <= 11 or 13 <= hour <= 15:  time_s = 55
    elif 11 <= hour <= 13:                      time_s = 30
    else:                                        time_s = 65  # night — Jew/Snapper active

    # ── Pressure trend (20%) ─────────────────────────────
    # Rising = fish feed aggressively. Falling = slowdown. Rapid drop before storm = brief flurry.
    pressure_s = {"rising": 90, "stable": 70, "falling": 40}.get(pressure_trend, 70)

    # ── Wind speed (15%) ─────────────────────────────────
    # Under 10km/h is ideal. Over 30km/h = most spots unfishable.
    if wind_speed < 10:    wind_s = 100
    elif wind_speed < 20:  wind_s = 75
    elif wind_speed < 30:  wind_s = 45
    else:                   wind_s = 15

    # ── Tide range (15%) ─────────────────────────────────
    # Sweet spot is 0.8-1.8m. Too small = no water movement. Too large = dangerous current.
    # Uses a curve rather than linear scaling.
    if tide_range < 0.3:     tide_s = 20
    elif tide_range < 0.8:   tide_s = int(20 + (tide_range - 0.3) / 0.5 * 80)   # ramp up 20→100
    elif tide_range <= 1.8:  tide_s = 100                                          # sweet spot
    else:                     tide_s = max(50, int(100 - (tide_range - 1.8) * 40)) # taper off

    # ── Water temperature (10%) ──────────────────────────
    # Sydney average: 17°C winter, 23°C summer. Most species active 18-24°C.
    # If no SST available, neutral score.
    if water_temp is None:
        temp_s = 70
    elif 18 <= water_temp <= 24:  temp_s = 100  # ideal for most Sydney species
    elif 15 <= water_temp < 18:   temp_s = 65   # cool — Bream/Flathead ok, Kingfish slow
    elif 24 < water_temp <= 27:   temp_s = 80   # warm — Kingfish/Whiting love it
    elif water_temp < 15:          temp_s = 35   # cold — most species sluggish
    else:                           temp_s = 50   # very warm

    # ── Swell height (5%) ────────────────────────────────
    # Low swell = accessible spots, cleaner water. Mainly affects coastal/offshore spots.
    if swell < 0.5:    swell_s = 95
    elif swell < 1.0:  swell_s = 75
    elif swell < 1.5:  swell_s = 50
    else:               swell_s = 25

    score = round(
        time_s   * 0.20 +
        moon_score * 0.20 +
        pressure_s * 0.20 +
        wind_s   * 0.15 +
        tide_s   * 0.15 +
        temp_s   * 0.10 +
        swell_s  * 0.05
    )

    if score >= 85:   label, stars = "PRIME",   5
    elif score >= 70: label, stars = "GREAT",   4
    elif score >= 55: label, stars = "GOOD",    3
    elif score >= 40: label, stars = "AVERAGE", 2
    else:             label, stars = "POOR",    1

    return {
        "score": score, "label": label, "stars": stars,
        "breakdown": {
            "time":     round(time_s   * 0.20, 1),
            "moon":     round(moon_score * 0.20, 1),
            "pressure": round(pressure_s * 0.20, 1),
            "wind":     round(wind_s   * 0.15, 1),
            "tide":     round(tide_s   * 0.15, 1),
            "temp":     round(temp_s   * 0.10, 1),
            "swell":    round(swell_s  * 0.05, 1),
        }
    }


# ── SPECIES DATABASE ──────────────────────────────────────
# Data sourced from NSW DPI fishing guides, Fishraider forums,
# and established Australian recreational fishing literature.
# temp_range: [min_active, optimal_low, optimal_high, max_active] in °C

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
        "temp_range": [12, 18, 24, 28],
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
        "temp_range": [14, 18, 25, 28],
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
        "temp_range": [16, 20, 26, 30],
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
        "temp_range": [18, 20, 26, 29],
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
        "temp_range": [14, 17, 23, 26],
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
        "temp_range": [14, 17, 22, 26],
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


# ── WHAT'S BITING SCORING ─────────────────────────────────

def score_species_conditions(sp_key, sp, moon, weather, water_temp, hour, month):
    """
    Score a species 0-100 based on current conditions.
    Returns score + list of reasons (for transparency).

    Factors:
      Season      35pts — is this month in the species' peak season?
      Moon        25pts — is the moon phase in the species' preferred range?
      Wind        15pts — is wind under the species' comfort threshold?
      Time        15pts — is it currently a good feeding time for this species?
      Water temp  10pts — is sea surface temperature in range?
    """
    score = 0
    reasons = []
    penalties = []

    # ── Season (35pts) ───────────────────────────────────
    if month in sp["best_season"]:
        score += 35
        reasons.append("In peak season")
    else:
        score += 10  # still catchable out of season
        penalties.append("Out of peak season")

    # ── Moon phase (25pts) ───────────────────────────────
    mp = moon["phase"]
    mr = sp["conditions"]["moon_pref"]
    # Check both ends of cycle (e.g. jewfish likes 0-0.08 which also includes ~0.92-1.0)
    moon_ok = mr[0] <= mp <= mr[1] or (1 - mp) <= mr[1]
    if moon_ok:
        score += 25
        reasons.append(f"Moon phase favourable ({moon['name']})")
    else:
        score += 8
        penalties.append(f"Moon not ideal ({moon['name']})")

    # ── Wind (15pts) ─────────────────────────────────────
    wind_speed = weather.get("wind_speed", 10)
    wind_max = sp["conditions"]["wind_max"]
    if wind_speed <= wind_max * 0.5:
        score += 15
        reasons.append(f"Calm wind ({wind_speed:.0f} km/h)")
    elif wind_speed <= wind_max:
        score += 10
        reasons.append(f"Wind ok ({wind_speed:.0f} km/h)")
    else:
        score += 0
        penalties.append(f"Too windy ({wind_speed:.0f} km/h, max {wind_max})")

    # ── Time of day (15pts) ──────────────────────────────
    best_time = sp.get("best_time", "")
    time_ok = False
    if "dawn" in best_time.lower() and 4 <= hour <= 8:
        time_ok = True
    elif "dusk" in best_time.lower() and 17 <= hour <= 20:
        time_ok = True
    elif "night" in best_time.lower() and (hour >= 21 or hour <= 4):
        time_ok = True
    elif "morning" in best_time.lower() and 6 <= hour <= 11:
        time_ok = True
    elif "afternoon" in best_time.lower() and 13 <= hour <= 18:
        time_ok = True

    if time_ok:
        score += 15
        reasons.append(f"Good time of day")
    else:
        score += 5

    # ── Water temperature (10pts) ────────────────────────
    temp_range = sp.get("temp_range")
    if water_temp and temp_range:
        t_min, t_opt_low, t_opt_high, t_max = temp_range
        if t_opt_low <= water_temp <= t_opt_high:
            score += 10
            reasons.append(f"Water temp ideal ({water_temp:.1f}°C)")
        elif t_min <= water_temp <= t_max:
            score += 5
            reasons.append(f"Water temp ok ({water_temp:.1f}°C)")
        else:
            score += 0
            penalties.append(f"Water temp outside range ({water_temp:.1f}°C)")
    else:
        score += 5  # neutral if no SST data

    return score, reasons, penalties


# ── API HANDLERS ──────────────────────────────────────────

def api_conditions():
    now = datetime.now()
    moon = moon_phase(now)
    sol  = solunar_times(now)

    # Weather from Open-Meteo (free, no key)
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
            recent  = pressures[now.hour] if now.hour < len(pressures) else pressures[-1]
            earlier = pressures[max(0, now.hour - 3)]
            diff = recent - earlier
            if diff > 1:    pressure_trend = "rising"
            elif diff < -1: pressure_trend = "falling"
            else:           pressure_trend = "stable"
        else:
            pressure_trend = "stable"
            recent = 1013

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

    # Marine data — wave height + sea surface temperature
    marine = {}
    water_temp = None
    try:
        url = ("https://marine-api.open-meteo.com/v1/marine"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=wave_height,wave_period,sea_surface_temperature"
               "&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        c = data.get("current", {})
        water_temp = c.get("sea_surface_temperature")
        marine = {
            "wave_height": c.get("wave_height", 0),
            "wave_period": c.get("wave_period", 0),
            "water_temp":  round(water_temp, 1) if water_temp else None,
        }
    except:
        marine = {"wave_height": 0.5, "wave_period": 8, "water_temp": None}

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
                    "time":   dt_str[11:16],
                    "height": round(e["height"], 2),
                    "type":   e["type"].upper()
                })
        if len(tides_today) >= 2:
            heights = [t["height"] for t in tides_today]
            tide_range = max(heights) - min(heights)
    except:
        pass

    # Overall fishing score
    score = fishing_score(
        tide_range=tide_range,
        moon_score=moon["score"],
        pressure_trend=weather.get("pressure_trend", "stable"),
        wind_speed=weather.get("wind_speed", 10),
        hour=now.hour,
        swell=marine.get("wave_height", 0),
        water_temp=water_temp,
    )

    # Next tide
    next_tide = None
    for t in tides_today:
        th, tm = map(int, t["time"].split(":"))
        t_mins   = th * 60 + tm
        now_mins = now.hour * 60 + now.minute
        if t_mins > now_mins:
            diff = t_mins - now_mins
            next_tide = {
                **t,
                "in_mins": diff,
                "in_str": f"{diff//60}h {diff%60}m" if diff >= 60 else f"{diff}m"
            }
            break

    # What's biting — scored with full reasoning
    biting = []
    hour  = now.hour
    month = now.strftime("%b")
    for key, sp in SPECIES.items():
        sp_score, reasons, penalties = score_species_conditions(
            key, sp, moon, weather, water_temp, hour, month
        )
        if sp_score >= 50:
            biting.append({
                "key":      key,
                "name":     sp["name"],
                "emoji":    sp["emoji"],
                "color":    sp["icon"],
                "score":    sp_score,
                "tip":      sp["tips"][:80],
                "reasons":  reasons,
                "penalties": penalties,
            })
    biting.sort(key=lambda x: -x["score"])

    return jresp({
        "time":       now.strftime("%H:%M"),
        "date":       now.strftime("%A %d %B"),
        "moon":       moon,
        "solunar":    sol,
        "weather":    weather,
        "marine":     marine,
        "tides":      tides_today,
        "next_tide":  next_tide,
        "score":      score,
        "biting":     biting[:4],
        "water_temp": round(water_temp, 1) if water_temp else None,
    })


def api_forecast():
    now = datetime.now()
    days = []

    # 7-day weather forecast
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
                "date":       d["time"][i],
                "sunrise":    d["sunrise"][i].split("T")[1],
                "sunset":     d["sunset"][i].split("T")[1],
                "temp_max":   d["temperature_2m_max"][i],
                "temp_min":   d["temperature_2m_min"][i],
                "wind_max":   d["windspeed_10m_max"][i],
                "rain_chance":d["precipitation_probability_max"][i],
                "uv":         d["uv_index_max"][i],
            })
    except:
        for i in range(7):
            weather_7d.append({
                "date": (now + timedelta(days=i)).strftime("%Y-%m-%d"),
                "wind_max": 15, "rain_chance": 20, "temp_max": 24, "temp_min": 18,
                "sunrise": "06:15", "sunset": "19:30", "uv": 5
            })

    # Load tide data from cache
    from collections import defaultdict
    extremes_by_date = defaultdict(list)
    heights_by_date  = defaultdict(list)
    try:
        with open(TIDE_CACHE) as f:
            cache = json.load(f)
        for e in cache.get("extremes", []):
            dt_str    = e.get("date","")
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
        day_dt   = now + timedelta(days=i)
        day_str  = day_dt.strftime("%Y-%m-%d")
        w        = weather_7d[i] if i < len(weather_7d) else {}
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
            hour=6,
            swell=0.5,
            water_temp=None,
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
                    "key":    key,
                    "name":   s["name"],
                    "emoji":  s["emoji"],
                    "color":  s["icon"],
                    "active": active
                })
        score_val = sp["rating"] * 18 + (5 if moon["score"] > 80 else 0)
        spots_out.append({**sp, "species_data": sp_species, "score": min(100, score_val)})

    return jresp({"spots": spots_out, "wind": w_speed, "moon": moon})


def api_species():
    now = datetime.now()
    moon  = moon_phase(now)
    month = now.strftime("%b")
    w_speed = 10
    water_temp = None
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=windspeed_10m,surface_pressure"
               "&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        w_speed = data["current"]["windspeed_10m"]
    except:
        pass

    try:
        url = ("https://marine-api.open-meteo.com/v1/marine"
               "?latitude=-33.9558&longitude=151.0617"
               "&current=sea_surface_temperature"
               "&timezone=Australia/Sydney&forecast_days=1")
        data = fetch_url(url)
        water_temp = data.get("current", {}).get("sea_surface_temperature")
    except:
        pass

    weather = {"wind_speed": w_speed}
    out = []
    for key, sp in SPECIES.items():
        in_season = month in sp["best_season"]
        mp = moon["phase"]
        mr = sp["conditions"]["moon_pref"]
        moon_good = mr[0] <= mp <= mr[1] or (1 - mp) <= mr[1]
        wind_ok   = w_speed <= sp["conditions"]["wind_max"]

        sp_score, reasons, penalties = score_species_conditions(
            key, sp, moon, weather, water_temp, now.hour, month
        )

        out.append({
            **sp,
            "key":           key,
            "in_season":     in_season,
            "moon_good":     moon_good,
            "wind_ok":       wind_ok,
            "current_score": sp_score,
            "reasons":       reasons,
            "penalties":     penalties,
            "water_temp":    round(water_temp, 1) if water_temp else None,
        })

    out.sort(key=lambda x: -x["current_score"])
    return jresp({"species": out, "moon": moon, "month": month, "wind": w_speed,
                  "water_temp": round(water_temp, 1) if water_temp else None})


def api_solunar():
    days_out = []
    now = datetime.now()
    for i in range(7):
        dt   = now + timedelta(days=i)
        sol  = solunar_times(dt)
        moon = moon_phase(dt)
        days_out.append({
            "date":  dt.strftime("%Y-%m-%d"),
            "label": "Today" if i==0 else ("Tomorrow" if i==1 else dt.strftime("%a %d")),
            "moon":  moon,
            "solunar": sol,
            "best":  moon["score"] >= 85
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
            cid  = data.get("id")
            catches = [c for c in catches if c.get("id") != cid]
            with open(CATCH_LOG, "w") as f:
                json.dump(catches, f, indent=2)
            return jresp({"ok": True})
        except Exception as e:
            return jresp({"ok": False, "error": str(e)})

    total      = len(catches)
    by_species = {}
    by_spot    = {}
    best_catch = None
    for c in catches:
        sp  = c.get("species","unknown")
        loc = c.get("location","unknown")
        by_species[sp]  = by_species.get(sp, 0) + 1
        by_spot[loc]    = by_spot.get(loc, 0) + 1
        if c.get("weight") and (not best_catch or c["weight"] > best_catch.get("weight",0)):
            best_catch = c

    return jresp({
        "catches":    catches,
        "total":      total,
        "by_species": by_species,
        "by_spot":    by_spot,
        "best_catch": best_catch,
    })


def api_methodology():
    """
    Returns the full scoring methodology for display on the Info page.
    This makes the algorithm completely transparent to the user.
    """
    return jresp({
        "overall_score": {
            "description": "The overall fishing score (0-100) is a weighted composite of 7 environmental factors. Each factor is scored 0-100, multiplied by its weight, and summed.",
            "formula": "Score = (Time×0.20) + (Moon×0.20) + (Pressure×0.20) + (Wind×0.15) + (Tide×0.15) + (Temp×0.10) + (Swell×0.05)",
            "factors": [
                {
                    "name": "Time of Day",
                    "weight": "20%",
                    "source": "System clock",
                    "logic": "Dawn (4–8am) and dusk (5–8pm) score 100 — these are peak feeding windows when light change triggers predator activity. Mid-morning and afternoon score 55–80. Midday scores 30 (hottest, brightest, fish go deep). Night scores 65 — Jewfish and Snapper are actively nocturnal.",
                    "scores": {"Dawn/Dusk": 100, "Morning/Afternoon": 80, "Mid-morning/mid-afternoon": 55, "Midday": 30, "Night": 65}
                },
                {
                    "name": "Moon Phase",
                    "weight": "20%",
                    "source": "Astronomical calculation (synodic cycle from known new moon Jan 6, 2000)",
                    "logic": "New moon and full moon create the largest tidal variation (spring tides), which drives the most water movement and fish feeding activity. This is well-documented in recreational fishing literature and NSW DPI guides.",
                    "scores": {"New Moon": 100, "Full Moon": 95, "Gibbous phases": 75, "Quarter moons": 70, "Crescent phases": 65}
                },
                {
                    "name": "Barometric Pressure Trend",
                    "weight": "20%",
                    "source": "Open-Meteo weather API — comparing current pressure to 3hrs ago",
                    "logic": "Rising pressure means improving weather — fish feed aggressively as conditions stabilise. Stable pressure means consistent behaviour. Falling pressure (approaching front/storm) causes a brief feeding spike then a shutdown as fish sense the change.",
                    "scores": {"Rising": 90, "Stable": 70, "Falling": 40}
                },
                {
                    "name": "Wind Speed",
                    "weight": "15%",
                    "source": "Open-Meteo weather API",
                    "logic": "Lighter wind means easier casting, better lure presentation, less surface disturbance, and more accessible fishing spots. Under 10 km/h is ideal for most techniques. Above 30 km/h most spots are unfishable or unsafe.",
                    "scores": {"Under 10 km/h": 100, "10–20 km/h": 75, "20–30 km/h": 45, "Over 30 km/h": 15}
                },
                {
                    "name": "Tidal Range",
                    "weight": "15%",
                    "source": "WorldTides API (fetched twice weekly, cached locally)",
                    "logic": "Tidal range is the difference between high and low tide on a given day. A moderate range (0.8–1.8m) creates the best water movement — enough current to activate feeding, but not so much that it's unfishable. Very small ranges mean stagnant water. Very large ranges (>1.8m) create ripping current.",
                    "scores": {"Under 0.3m": 20, "0.3–0.8m": "20–100 (ramp)", "0.8–1.8m (sweet spot)": 100, "Over 1.8m": "50–100 (taper)"}
                },
                {
                    "name": "Sea Surface Temperature",
                    "weight": "10%",
                    "source": "Open-Meteo Marine API",
                    "logic": "Water temperature directly affects fish metabolism and feeding behaviour. Each species has an optimal temperature range based on their physiology. Sydney water averages 17°C in winter and 23°C in summer. The score reflects how close the current SST is to each species' ideal range.",
                    "scores": {"18–24°C (ideal for most species)": 100, "24–27°C (warm — Kingfish/Whiting active)": 80, "15–18°C (cool — Bream/Flathead ok)": 65, "Under 15°C": 35}
                },
                {
                    "name": "Swell Height",
                    "weight": "5%",
                    "source": "Open-Meteo Marine API",
                    "logic": "Low swell means accessible spots (especially rock platforms and coastal areas), cleaner water, and better visibility for fish. This factor has lower weight because most Sydney estuary spots are sheltered from ocean swell.",
                    "scores": {"Under 0.5m": 95, "0.5–1.0m": 75, "1.0–1.5m": 50, "Over 1.5m": 25}
                }
            ],
            "ratings": {"PRIME": "85–100", "GREAT": "70–84", "GOOD": "55–69", "AVERAGE": "40–54", "POOR": "0–39"}
        },
        "whats_biting": {
            "description": "Each species is scored 0-100 based on how well current conditions match their known preferences. Species scoring 50+ are shown as active.",
            "factors": [
                {"name": "Season", "weight": "35pts", "logic": "Based on NSW DPI seasonal fishing guides and established local knowledge. Peak season months are when each species is most abundant and actively feeding in Sydney waters."},
                {"name": "Moon Phase", "weight": "25pts", "logic": "Each species has a preferred moon phase range derived from fishing literature. New moon favours nocturnal species (Jewfish, Snapper). Full moon favours pelagics (Kingfish). Bream and Flathead are active across most of the cycle."},
                {"name": "Wind", "weight": "15pts", "logic": "Each species has a wind tolerance threshold. Delicate species like Whiting (max 15 km/h) are far more affected by wind chop than robust species like Jewfish (max 30 km/h)."},
                {"name": "Time of Day", "weight": "15pts", "logic": "Each species has documented peak feeding times. Dawn and dusk species (Bream, Flathead, Kingfish) score full points during those windows. Nocturnal species (Jewfish) score full points at night."},
                {"name": "Water Temperature", "weight": "10pts", "logic": "Sea surface temperature from Open-Meteo Marine API is compared against each species' optimal temperature range. Each species has a [min, optimal_low, optimal_high, max] range based on their physiology and known Sydney behaviour."}
            ]
        },
        "solunar": {
            "description": "Solunar theory was developed by John Alden Knight in 1926. It predicts fish feeding activity based on the moon's position relative to the fishing location.",
            "major_periods": "Major periods (2 hours) occur when the moon is directly overhead or directly underfoot (opposite side of Earth). These are the strongest feeding triggers.",
            "minor_periods": "Minor periods (1 hour) occur when the moon is at 90° to the location — i.e., rising or setting.",
            "calculation": "Tide Runner calculates solunar times using the moon's synodic cycle position (29.53 days) relative to a known new moon reference point. No external API is used — all calculations are local.",
            "note": "Solunar tables are most effective when combined with tidal changes and dawn/dusk windows. A major solunar period coinciding with an incoming tide at dawn is considered a prime fishing window."
        },
        "data_sources": [
            {"name": "WorldTides API", "url": "https://www.worldtides.info", "data": "Tide predictions (high/low times and heights)", "cost": "~2 credits/week from free tier", "fetch": "Twice weekly via cron (Mon & Thu midnight), cached locally"},
            {"name": "Open-Meteo Weather", "url": "https://api.open-meteo.com", "data": "Air temperature, wind speed/direction, barometric pressure, UV index, rain probability", "cost": "Free, no API key", "fetch": "Live on each page load"},
            {"name": "Open-Meteo Marine", "url": "https://marine-api.open-meteo.com", "data": "Wave height, wave period, sea surface temperature, ocean current speed", "cost": "Free, no API key", "fetch": "Live on each page load"},
            {"name": "Astronomical calculation", "url": None, "data": "Moon phase, solunar feeding times", "cost": "Free — calculated locally", "fetch": "Calculated on each request, no external API"},
        ],
        "species_data_sources": "Species seasonal data, legal sizes, bag limits, and habitat information sourced from NSW DPI Recreational Fishing Guides (dpi.nsw.gov.au), Fishraider Australian Fishing Forums, and established Australian recreational fishing literature. Temperature ranges derived from published research on Australian estuarine and coastal fish physiology.",
        "disclaimer": "Tide Runner provides fishing intelligence based on environmental data and established fishing theory. Scores and recommendations are guidance only — fish don't read algorithms. Always check current NSW DPI regulations at dpi.nsw.gov.au before fishing. Never rely solely on this tool for navigational or safety decisions on the water."
    })


# ── HTTP SERVER ───────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        path = urlparse(self.path).path
        routes = {
            "/api/conditions":   lambda: api_conditions(),
            "/api/forecast":     lambda: api_forecast(),
            "/api/spots":        lambda: api_spots(),
            "/api/species":      lambda: api_species(),
            "/api/solunar":      lambda: api_solunar(),
            "/api/catches":      lambda: api_catches("GET"),
            "/api/methodology":  lambda: api_methodology(),
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
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode() if length else None
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if path == "/api/catches":
            self.wfile.write(api_catches("POST", body).encode())
        else:
            self.wfile.write(json.dumps({"error": "not found"}).encode())

    def do_DELETE(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode() if length else None
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
    print(f"   Tailscale: http://YOUR_TAILSCALE_IP:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
