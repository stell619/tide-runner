# Tide Runner — Scoring Algorithm: Scientific Basis & Methodology

*Version 2.1 | March 2026 | Port Hacking, Sydney NSW*

---

## Overview

Most fishing forecast tools weight their algorithms around solunar theory — a framework developed by John Alden Knight in 1926. Peer-reviewed research consistently shows this approach has **weak predictive value** for the estuarine and coastal species found in Sydney waters.

Tide Runner's scoring algorithm is built on fisheries science, not folklore. Every factor and its weight is derived from published research or established field knowledge specific to Australian coastal species. This document explains what the science says, what we use, and why.

---

## The Evidence Hierarchy

The five factors with the strongest scientific support for predicting fish feeding activity in Sydney estuaries and coastal waters, ranked by evidence strength:

| Rank | Factor | Evidence Rating | Key Source |
|------|--------|----------------|------------|
| 1 | Water temperature & trend | ★★★★★ | Stoner 2004, PMC 2020 |
| 2 | Tidal flow direction | ★★★★★ | Multiple; Fisheries Research Institute 2020 |
| 3 | Time of day | ★★★★★ | Hobson et al. 1981, Myers et al. 2016 |
| 4 | Wind speed | ★★★★ | Agmour et al. 2020 |
| 5 | Weather front proximity | ★★★★ | University of Nebraska thesis |
| — | Tidal range | ★★★★ | General tidal science |
| — | Moon phase | ★★★☆ (marine only) | Lowry et al. 2007 (NSW) |
| — | Barometric pressure (direct) | ★☆☆☆ | Ross/WHOI; Bulmer 2019 |
| — | Solunar tables | ★☆☆☆ | Quigley et al. 2023 |

---

## Factor-by-Factor Analysis

### 1. Time of Day (20%)

**Evidence rating: ★★★★★ — strongest and most consistent predictor**

Hobson, Chess & McFarland (1981, *US Fishery Bulletin*) established that predatory fish vision is specifically adapted for twilight conditions, giving them a hunting advantage precisely when prey species' visual acuity is compromised. Myers et al. (2016, *Marine Ecology*) confirmed this using unbaited underwater video — diurnal surveys recorded **16× more individuals** than nocturnal surveys, with peak activity during short crepuscular changeover periods.

Walleye telemetry data (Kelso, 1978) showed consistent peaks at 0500 and 2100 hours. The mechanism is clear: predators exploit the visual disadvantage of prey during light transitions, dissolved oxygen peaks in early morning from overnight photosynthesis, and insect activity at dusk triggers surface feeding chains.

**Scoring logic:**
- Dawn 04:00–08:00 & Dusk 17:00–20:00 → **100**
- Morning 08:00–10:00 & Afternoon 15:00–17:00 → **80**
- Mid-morning/afternoon → **55**
- Midday 11:00–14:00 → **30** *(fish go deep to escape heat and light)*
- Night → **65** *(active for Jewfish, Snapper — nocturnal predators)*

---

### 2. Moon Phase (10%)

**Evidence rating: ★★★☆ (marine species) / ★☆☆☆ (freshwater)**

The most rigorous recent test — Quigley, Gonzalez Murcia & Kauwe (2023, *Discover Applied Sciences*) — found **"no significant relationship between CPUE and any of the solunar values tested, lunar phase, or lunar illumination"** for freshwater trout across multiple solunar table services. Hanson et al. (2008) used whole-lake 3D acoustic telemetry on 20 largemouth bass across 6 lunar cycles and found zero lunar effect.

However, **marine species show a different pattern**. Lowry, Williams & Metti (2007, *Fisheries Research*) analysed 145 offshore game fishing tournaments off NSW — 14,319 fish over 9 years — and found significant lunar correlations for 5 of 8 species. Andrzejaczek et al. (2024, *Reviews in Fish Biology and Fisheries*) reviewed 190 studies and found 51% showed fish swimming deeper as lunar illumination increased.

The moon phase effect for Sydney estuarine species (bream, flathead, whiting, mulloway) is real but **secondary** — primarily operating through its influence on tidal amplitude rather than any direct gravitational or illumination effect. New and full moons create spring tides (larger ranges, more water movement) which drives feeding activity. The moon phase score in Tide Runner is best understood as a tidal amplification proxy.

**Scoring logic:**
- New Moon → **100** *(spring tides + dark nights for Jewfish)*
- Full Moon → **95** *(spring tides + surface feeding for pelagics)*
- Gibbous phases → **75**
- Quarter moons → **70**
- Crescent phases → **65**

---

### 3. Barometric Pressure Trend (10%)

**Evidence rating: ★☆☆☆ for direct effect — but valid as a weather proxy**

This is the most counterintuitive finding. Dr. David Ross (Woods Hole Oceanographic Institution) demonstrated that a fish moving just **1 metre vertically** experiences a pressure change exceeding any weather-related barometric fluctuation. A typical cold front produces ~0.06 atmospheres of change; a fish descending 2 metres experiences ~0.18 atmospheres — three times more.

Alan Bulmer (Active Angling NZ) tested Ronald Reinhold's barometric prediction model over 12 months and found **"no statistically significant difference between catch rates in optimal and sub-optimal periods."** VanderWeyst (2014, Bemidji State) found R² = 0.38, P = 0.55. Tom Manns' 40,000+ bass catch analysis concluded scientific studies cannot demonstrate the relationship exists.

**However**, the pressure trend signal remains valuable as a **proxy for approaching weather systems** — the real effect is pre-frontal. A University of Nebraska thesis documented active pre-frontal feeding with "seemingly non-existent" post-frontal activity. The zooplankton cascade model provides a mechanism: a 1-2 millibar pre-frontal pressure drop disrupts zooplankton buoyancy, triggering a food chain cascade lasting 4-6 hours.

Tide Runner uses pressure trend to detect **front proximity** rather than as a direct physiological predictor:

**Scoring logic:**
- Rapid fall >2 hPa/3hrs → **85** *(pre-frontal feeding spike — act now)*
- Slow fall 0.5–2 hPa/3hrs → **65** *(front approaching, feeding picking up)*
- Stable → **70**
- Rising after fall → **80** *(post-front recovery, stable conditions returning)*
- Rapid rise → **55** *(immediate post-frontal — fish shut down)*

---

### 4. Wind Speed (18%)

**Evidence rating: ★★★★ — stronger predictor than barometric pressure**

Agmour et al. (2020, *Modeling Earth Systems and Environment*) demonstrated wind speed as **"the most important parameter involved in fishing activity"** in their quantitative analysis. Josh Alwine's 40,000+ bass catch analysis found catch rates more than doubled in 10–20 km/h winds. Gulf Coast field data showed 31% more hookups in moderate wind versus calm conditions.

Wind has clear, well-understood mechanistic pathways:
- Wave action increases dissolved oxygen at the surface
- Wind concentrates prey species in windward areas and current lines
- Light scatter conceals predators from above
- Surface disturbance masks angler presence and vibration
- Terrestrial insects and food blown into the water trigger surface feeding

Note: moderate wind (10–20 km/h) is often *better* than calm for surface species. Extreme wind (>30 km/h) renders most Sydney estuary spots unfishable or unsafe.

**Scoring logic:**
- <10 km/h → **100** *(ideal for lure presentation)*
- 10–20 km/h → **85** *(often increases activity, good for most techniques)*
- 20–30 km/h → **45** *(limits accessible spots, reduces presentation quality)*
- >30 km/h → **15** *(most spots unfishable)*

---

### 5. Tidal Range (10%)

**Evidence rating: ★★★★★ — core predictor for estuary species**

Tidal range (difference between high and low tide height on a given day) determines the volume of water moving through an estuary system. More water movement means more baitfish swept through channels, more turbulence that disorients prey, and more feeding opportunities for predators positioned at structure.

The optimal range for Sydney estuaries is **0.8–1.8 metres**. Below 0.3m the water is essentially stagnant. Above 1.8m the current becomes too strong for most fishing techniques and fish can feed without effort at any time.

Tide Runner uses a **curve rather than linear scaling** — the relationship between tidal range and fishing quality is not proportional:

**Scoring logic:**
- <0.3m → **20** *(stagnant water, very poor)*
- 0.3–0.8m → ramp 20→100 *(improving)*
- 0.8–1.8m → **100** *(sweet spot)*
- >1.8m → taper from 100 downward *(diminishing returns, strong current)*

---

### 6. Tidal Direction (8%) — *NEW in v2.1*

**Evidence rating: ★★★★★ — highest-priority addition based on research**

While tidal range measures *how much* water moves, tidal direction measures *which way* it's moving right now. This distinction is critically important and consistently cited as the primary factor by experienced Sydney anglers.

A Fisheries Research Institute study (2020) reported higher catch rates during incoming tides due to aggressive feeding behaviour. Fish possess internal circadian rhythms synchronised to 12.4-hour tidal cycles that persist even in lab conditions without tidal cues. The first 1–2 hours of both flood and ebb tide are consistently the most productive windows; slack water (within 30 minutes of a high or low) is universally the poorest.

Species-specific tide preferences in Sydney waters (from NSW DPI guides and field research):
- **Flathead**: falling tide on channel edges; rising tide in shallows
- **Whiting**: rising tide on sand flats (prey swept onto flats)
- **Bream**: incoming tide pushing prawns and crabs onto structure
- **Kingfish**: incoming tide around headlands and structure
- **Mulloway**: the tide *change* itself — slowing current, not slack water

**Scoring logic:**
- First 2hrs incoming (rising) → **90**
- Mid-incoming → **80**
- Last 2hrs before high → **75**
- Slack water (±30min of extreme) → **20**
- First 2hrs outgoing (falling) → **80**
- Mid-outgoing → **70**
- Last 2hrs before low → **65**

---

### 7. Sea Surface Temperature — Absolute (12%)

**Evidence rating: ★★★★★ — strongest single variable in fisheries science**

Stoner (2004, *Journal of Fish Biology*) — a comprehensive NOAA review — identifies water temperature as the **primary environmental driver** of fish feeding motivation and catchability. Bass metabolic rates decline approximately one-third per 10°C drop, directly controlling digestion speed, hunger cycles, and activity levels.

Sydney water temperature ranges from approximately 17°C in winter to 23°C in summer. Most estuarine species are active across this range but have distinct optimal windows:

| Species | Min active | Optimal range | Max active |
|---------|-----------|--------------|------------|
| Bream | 12°C | 18–24°C | 28°C |
| Flathead | 14°C | 18–25°C | 28°C |
| Whiting | 16°C | 20–26°C | 30°C |
| Kingfish | 18°C | 20–26°C | 29°C |
| Snapper | 14°C | 17–23°C | 26°C |
| Jewfish/Mulloway | 14°C | 17–22°C | 26°C |

*Data: NSW DPI species profiles, Pirozzi & Booth 2009 (Kingfish), field research*

**Overall scoring logic** (composite across species):
- 18–24°C → **100** *(ideal for most Sydney species)*
- 24–27°C → **80** *(warm — Kingfish and Whiting active, others ok)*
- 15–18°C → **65** *(cool — Bream and Flathead active, Kingfish slow)*
- <15°C → **35** *(cold — most species sluggish)*
- >27°C → **50** *(very warm — some stress responses)*

---

### 8. Sea Surface Temperature — Trend (5%) — *NEW in v2.1*

**Evidence rating: ★★★★ — direction of change matters as much as absolute value**

Quigley et al. (2023) found ambient temperature trend was a more effective predictor of fishing success than any solunar table tested. Research in PMC (2020) notes that acute short-term temperature fluctuations have "drastic, often detrimental effects on fish physiology," while gradual warming toward optimal temperatures can "turn good fishing into great fishing."

A 2-day temperature trajectory is computed from cached SST readings:

**Scoring logic:**
- Warming >1°C over 2 days (spring warm-up) → **100**
- Warming 0.5–1°C → **85** *(fish becoming more active)*
- Stable (±0.5°C) → **70**
- Cooling 0.5–1°C → **45** *(activity decreasing)*
- Rapid cooling >1°C → **20** *(cold snap — feeding shutdown)*

---

### 9. Swell Height (3%)

**Evidence rating: ★★★ — significant for coastal spots, minor for estuaries**

Swell height primarily affects accessibility and water clarity at coastal and rock platform spots (Marley Beach, Harbour Heads). Most of Tide Runner's target spots are estuarine and sheltered — Georges River, Port Hacking bay, Botany Bay — where ocean swell has minimal impact. The low weight reflects this reality.

**Scoring logic:**
- <0.5m → **95** *(all spots accessible)*
- 0.5–1.0m → **75**
- 1.0–1.5m → **50** *(coastal spots difficult)*
- >1.5m → **25** *(rock platforms dangerous, coastal spots closed)*

---

## What We Don't Use (and Why)

### Solunar tables as a primary factor

John Alden Knight's 1926 solunar theory predicts feeding based on moon transit and rise/set times. Quigley et al. (2023) is the most rigorous recent test — comparing 5 popular solunar table services against actual catch data — and found **no statistically significant relationship** for the species types most similar to Sydney estuary fishing.

Tide Runner displays solunar times as a secondary reference because anglers find them useful as *planning windows* — but they do not contribute to the primary fishing score. The moon's influence on fishing is captured through the moon phase factor (which reflects tidal amplitude effects) and the time of day factor (which reflects light conditions).

### Raw barometric pressure (absolute value)

A barometer reading of 1013 hPa vs 1009 hPa has no proven direct effect on fish physiology. What matters is the **rate and direction of change** as a weather front proxy, which is what the pressure trend factor captures.

### Water clarity/turbidity

Highly relevant scientifically — Newport et al. (2021) showed high turbidity significantly decreased foraging efficiency in reef fish — but not yet implemented due to API complexity. Copernicus Marine Service provides free daily satellite-derived turbidity data at 4km resolution. **Planned for v3.0.**

---

## Comparison with Commercial Tools

| Tool | Algorithm basis | Catch data trained | Species-specific | Transparent |
|------|----------------|-------------------|-----------------|-------------|
| **Tide Runner** | Fisheries science + field research | No (yet) | Yes (6 Sydney species) | ✅ Fully |
| Fishbrain BiteTime | ML on 2.5M catches | Yes | Yes | Partial |
| Fishing Points | Solunar + pressure | No | No | No |
| Fish Ranger (AU) | Solunar (Knight 1936) | No | No | No |
| BassForecast | Solunar + AccuWeather | No | Bass only | No |

Fishbrain's machine learning approach (trained on 2.5 million annotated catches via Modulai AB) is the gold standard. The long-term roadmap for Tide Runner includes catch data integration — every logged catch contributes to a locally-trained model that improves predictions over time.

---

### Score Modifiers

After the weighted sum is calculated, two environmental modifiers are applied based on research showing rain and cloud cover have non-linear effects on fish behaviour.

#### Rain Chance

**Evidence rating: ★★★★ — effect is real but direction depends on intensity**

The relationship between rain and fishing is counterintuitive. Moderate rain is actually positive for fishing: dissolved oxygen increases 15-30% from mechanical aeration (Journal of Fisheries Research), light penetration drops 40-60% making predatory fish more aggressive, surface disturbance reduces fish wariness, and terrestrial insects and worms wash into the water triggering feeding responses (WindRider 2025; MeatEater Fishing 2020).

Only heavy rain (>60% chance) becomes a penalty — extreme runoff causes dangerous turbidity, salinity changes in estuaries, and unsafe conditions (SCCF Weather Factors; Guidesly 2026).

Modifier applied to final score:
  <20% rain chance:   ×1.03  (light rain likely — bonus)
  20–40%:             ×1.00  (neutral)
  40–60%:             ×0.95  (moderate penalty)
  60–80%:             ×0.85  (significant penalty)
  >80%:               ×0.72  (heavy rain — unsafe, dirty water)

#### Cloud Cover

**Evidence rating: ★★★★ — overcast is better than sunny**

Overcast conditions are consistently better for fishing than clear sunny days. Cloud cover lowers light penetration, allowing fish to move freely and feed throughout the day rather than only during low-light crepuscular windows (Guidesly 2026). High pressure clear-sky systems cause fish to go deep and become less active; low pressure overcast conditions increase surface feeding activity (Captain Troy Wetzel 2025).

Modifier applied to final score:
  25–75% cloud cover: ×1.02  (ideal overcast — bonus)
  >75% cloud cover:   ×1.00  (heavy cloud — neutral)
  <25% cloud cover:   ×0.96  (very sunny — fish go deep)
  No data:            ×1.00  (neutral)

---

## Score Calculation

```
Final Score (0-100) =
  (time_of_day     × 0.20) +
  (moon_phase      × 0.10) +
  (pressure_trend  × 0.10) +
  (wind_speed      × 0.18) +
  (tidal_range     × 0.10) +
  (tidal_direction × 0.08) +
  (water_temp_abs  × 0.12) +
  (water_temp_trend× 0.05) +
  (swell_height    × 0.03) +
  (front_proximity × 0.04)
```

| Rating | Score range |
|--------|-------------|
| PRIME | 85–100 |
| GREAT | 70–84 |
| GOOD | 55–69 |
| AVERAGE | 40–54 |
| POOR | 0–39 |

---

## Data Sources

| Data | Source | Cost | Refresh |
|------|--------|------|---------|
| Tide predictions | WorldTides API | ~2 credits/week | Mon & Thu midnight |
| Weather + pressure | Open-Meteo | Free | Every 60 seconds |
| Sea surface temperature | Open-Meteo Marine API | Free | Every 60 seconds |
| Wave height / swell | Open-Meteo Marine API | Free | Every 60 seconds |
| Moon phase | Local astronomical calculation | Free | Per request |
| Solunar times | Local astronomical calculation | Free | Per request |
| Sunrise / Sunset | Open-Meteo | Free | Daily |

---

## References

- Agmour, I. et al. (2020). Impact of wind speed on fishing effort. *Modeling Earth Systems and Environment.*
- Andrzejaczek, S. et al. (2024). Lunar cycles and fish behaviour. *Reviews in Fish Biology and Fisheries.*
- Hanson, K.C. et al. (2008). Effects of lunar cycles on largemouth bass. *Fisheries Management and Ecology.*
- Hobson, E.S., Chess, J.R. & McFarland, W.N. (1981). Crepuscular and nocturnal activities of California nearshore fishes. *US Fishery Bulletin.*
- Kelso, J.R.M. (1978). Diel rhythm in activity of walleye. *Canadian Journal of Zoology.*
- Lowry, M., Williams, D. & Metti, Y. (2007). Lunar landings — lunar phase and catch rates for an Australian gamefish-tournament fishery. *Fisheries Research.*
- Myers, E.M.V. et al. (2016). Fine-scale patterns in the day, night and crepuscular composition of a temperate reef fish assemblage. *Marine Ecology.*
- Pirozzi, I. & Booth, M.A. (2009). Temperature preferences of yellowtail kingfish. Published research, AIMS/CSIRO.
- PMC (2020). Effects of temperature on feeding and digestive processes in fish. *PubMed Central.*
- Quigley, D., Gonzalez Murcia, S. & Kauwe, A. (2023). Popular solunar tables fail to predict fishing success in North American recreational freshwater trout fisheries. *Discover Applied Sciences.*
- Ross, D. (Woods Hole Oceanographic Institution). Barometric pressure and fish physiology. Referenced in Active Angling NZ.
- Stoner, A.W. (2004). Effects of environmental variables on fish feeding ecology. *Journal of Fish Biology.*
- NSW DPI Recreational Fishing Guides (2024). dpi.nsw.gov.au
- VanderWeyst, D. (2014). The effect of barometric pressure on feeding activity of yellow perch. Bemidji State University thesis.

---

*Tide Runner is open source — github.com/stell619/tide-runner*
*All scoring logic is visible in server.py*
