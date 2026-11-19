"""Attach access / sun / context attributes to reaches and drops and compute the final fish score.

fish_score (0-100) = 100 x water x (0.30 size + 0.30 thermal + 0.15 gradient + 0.25 remoteness) x burn x trout x heat
                     x channel
  water      dry-season flow from the TNC Natural Flows model (02b_download_flow.py, 05b_flow.py): 0.05 + 0.95 x the
             share of years since 2011 the reach kept >= 0.1 cfs through July-October; 0.3 in a reservoir. Where the
             model has no data, the NHD flow class: perennial 1.0, intermittent 0.35, unmapped 0.15, ephemeral 0.05.
             Below a gauged diversion (flowlib.DIVERSIONS) the model can't see the water leave in a canal. Where the
             USGS gauge just below kept flowing in under half of 5+ summers since 2011, and no trout are known on the
             reach, the gauge's share replaces the model's (today only the San Jacinto River near San Jacinto)
  size       drainage area, log scale: 1 km^2 -> 0, 50+ km^2 -> 1. The full area (05c_drainages.py, area_streams.csv):
             with what flows in from neighbouring boxes and from above reservoirs, which each box's DEM routing
             misses (a creek crossing in from the next box, or leaving a dam, started again near nothing)
  thermal    0.5 water temperature + 0.35 summer shade + 0.15 mountainside northness (south-facing -0.15 ->
             north-facing +0.15). Water temperature is the reach's estimated July-August daytime water temperature
             (watertemp.py: fitted per area to measured creeks; in LA on August air + elevation): full credit up to
             WATER_FULL, none from WATER_ZERO, the same cutoffs in every area because a trout's limits are water
             temperatures. No penalty for cold. Where there's no estimate the term is neutral (0.5). Shade combines
             the terrain's shade (share of mid-July daylight) with the tree canopy along the reach (USFS canopy
             cover, latest year): 1 - (1 - terrain) x (1 - 0.8 canopy); 45%+ is full credit.
             A tailwater below a dam that releases cold water from the reservoir's bottom (TAILWATERS: the West Fork
             San Gabriel below Cogswell, Piru Creek below Pyramid) gets the water-temperature part in full: the
             estimate knows nothing of the dam
  gradient   1-8% best (pool-riffle to step-pool), falling off over 10%
  remoteness typical bike+hike approach along the reach, 0 -> 120+ minutes, each minute ridden counted RIDE_REMOTENESS
             times: most anglers walk in, so a road closed to cars keeps most of them out
  burn       fire since 2016: <=2 years ago x0.4, 3-5 x0.7, 6-9 x0.9. Where the Forest Service mapped the fire's
             soil burn severity (BAER), the penalty is scaled by it: high 100%, moderate 75%, low 40%, very low 15%.
             A channel also takes the ash and sediment of the burned slopes above it, so the USGS post-fire debris-flow
             hazard sets a floor (high 100%, moderate 75%, low 40%), and a reach below a recent burn that didn't burn
             itself is penalised from the hazard's fire year
  trout      evidence of trout, x1.2: trout found in the last 10 years (CDFW survey, CDFW stocking, iNaturalist
             sighting) with no later survey finding none, or a CDFW Wild / Heritage Trout Water; x0.5 when the latest
             CDFW survey (last 10 years) found no trout. Capped at 100
  heat       desert heat gate, only where the water is near-certainly too warm (when unsure, a possible trout
             stream stays in): 1 up to an August mean air temperature (PRISM 1991-2020 normal, 800 m) of HEAT_START,
             falling to HEAT_FLOOR at HEAT_FULL and above. No creek in these ranges with a trout record is above
             26.7 C (lower Piru Creek, cooled by Pyramid Dam's releases); the gate starts 2 C higher, which leaves only
             the low desert canyons and fans below the San Jacinto and San Gorgonio escarpments (the Whitewater River
             at White Water read 24-27 C on April afternoons; the Indian Canyons 17-22 C on March-April mornings).
             Never applied to a reach with trout evidence or below a dam. Air temperature, not a stream-temperature
             model: NorWeST and EPA StreamCat both missed measured summer water temperatures here by 4-6 C (README)
  channel    x0.2 on a channel that is near-certainly a built conveyance: its name says so (aqueduct, canal, flood
             control channel, diversion, ditch, flume...) and has no natural word in it (creek, river, wash, brook,
             branch, fork, run: "Ditch Creek" is a creek), and no trout are recorded there. Channels with natural
             names stay as they are, concrete or not (the Los Angeles River, Tujunga Wash)
Critical habitat, wilderness and non-Forest-Service land are flags, not score terms.
"""
import datetime as dt, os, numpy as np, pandas as pd, geopandas as gpd
import watertemp

THIS_YEAR = dt.date.today().year


def band(x, lo, hi, soft):
    return np.clip(1 - np.clip(np.maximum(lo - x, x - hi), 0, None) / soft, 0, 1)


# per-range tables attach() merges on the reach / drop key, and the script that writes each
WRITERS = {"hike": "08_hike.py", "sun": "10_sun.py", "context": "11_context.py", "flow": "05b_flow.py",
           "area": "05c_drainages.py"}


def attach(gdf, key, region_dirs, kind):
    """Merge hike_/sun_/context_/flow_/area_ CSVs (kind = 'streams' or 'drops') and trailhead drive times onto gdf."""
    parts = {}
    src = "streams_scored.gpkg" if kind == "streams" else "waterfall_candidates.gpkg"
    for name, script in WRITERS.items():
        frames = []
        for d in region_dirs:
            p = f"{d}/{name}_{kind}.csv"
            if not os.path.exists(p):
                continue
            t = pd.read_csv(p)
            # The keys are row numbers 05_score.py gives the reaches and drops of a range. A table written for an
            # earlier set of them would attach its values to the wrong ones, so the two must list the same keys.
            mine = gdf[key][gdf[key].str.startswith(os.path.basename(d) + ":")]
            if t[key].duplicated().any() or set(t[key]) != set(mine):
                raise SystemExit(f"{p} doesn't list the same {kind} as {d}/{src} ({len(t)} rows against {len(mine)}): "
                                 f"run {script} again for this range (after 05_score.py, before 06_map.py)")
            if os.path.getmtime(p) < os.path.getmtime(f"{d}/{src}"):   # same keys, but they may have been renumbered
                print(f"NOTE: {p} is older than {src}; if 05_score.py changed the {kind} since, run {script} again")
            frames.append(t)
        if frames:
            parts[name] = pd.concat(frames, ignore_index=True)
    out = gdf
    for t in parts.values():
        out = out.merge(t, on=key, how="left")
    ths = [gpd.read_file(f"{d}/trailheads.gpkg") for d in region_dirs if os.path.exists(f"{d}/trailheads.gpkg")]
    if ths and "th_id" in out:
        th = pd.concat(ths, ignore_index=True)
        th = gpd.GeoDataFrame(th, crs=ths[0].crs).to_crs(4326)
        th_attr = pd.DataFrame({"th_id": th.th_id, "th_road": th.road, "drive_min": th.drive_min,
                                "drive_km": th.drive_km, "th_lat": th.geometry.y.round(6), "th_lon": th.geometry.x.round(6)})
        out = out.merge(th_attr, on="th_id", how="left")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def burn_factor(year, sev=None):
    yrs = THIS_YEAR - year
    f = np.where(pd.isna(year), 1.0, np.select([yrs <= 2, yrs <= 5, yrs <= 9], [0.4, 0.7, 0.9], 1.0))
    return f if sev is None else 1 - (1 - f) * np.where(pd.isna(sev), 1.0, sev)


DEBRIS = {"high": 1.0, "moderate": 0.75, "low": 0.4}


def num(s, c):
    return pd.to_numeric(s[c], errors="coerce") if c in s else pd.Series(np.nan, index=s.index)


RIDE_REMOTENESS = 2.0    # a minute ridden on the approach counts as this many minutes of remoteness (user's choice)
HEAT_START, HEAT_FULL, HEAT_FLOOR = 29.0, 30.5, 0.2    # August mean air, C
# Thermal term: estimated July-August daytime water temperature (watertemp.py), C. Trout feed and grow well up to
# about 20 C and can't hold out in water that stays at 25 C. On LA's trout records (1,566 reaches) this gives the same
# mean credit as the 700-2300 m elevation band it replaced (0.91), and none of them zero
WATER_FULL, WATER_ZERO = 20.0, 25.0
# Dams known to release cold water from the bottom of the reservoir into a trout fishery below ("tailwaters"). The
# river below the dam, down to the next reservoir, takes the elevation part of the thermal term in full:
# dam -> (river, highest elevation of the tailwater in m)
_TAILWATERS = {
    "la": {"Cogswell Reservoir": ("West Fork San Gabriel River", 715), "Pyramid Lake": ("Piru Creek", 700)},
    # Buford Dam releases from the bottom of Lake Lanier: the Chattahoochee is trout water for 48 miles below it,
    # through Bull Sluice Lake (Morgan Falls Dam, a small run-of-river pool) to Peachtree Creek in Atlanta. Blue
    # Ridge Dam does the same for the Toccoa down to the Tennessee line.
    "n_georgia": {"Lake Sidney Lanier": ("Chattahoochee River", 285), "Bull Sluice Lake": ("Chattahoochee River", 265),
                  "Blue Ridge Lake": ("Toccoa River", 475)},
}
# Jackson: Jackson Lake Dam is just north of the area's boxes, and the Snake below it is cold water all the way
# anyway. Vermont, Connecticut, Lexington: none known.
TAILWATERS = _TAILWATERS.get(watertemp.AREA, {})


def dam_of(s):
    return s["below_dam"].fillna("").astype(str) if "below_dam" in s else pd.Series("", index=s.index)


def tailwater(s):
    """The dam's name where a reach is a cold tailwater below it (TAILWATERS), else ''. Below the flow model's
    below-dam flag, the river's main stem (20+ km2) by name, down to the next reservoir."""
    dam, out = dam_of(s), pd.Series("", index=s.index)
    # the main stem by its full drainage: the box's own routing starts the river again below the dam (the Toccoa
    # below Blue Ridge Dam showed 3-7 km2 of its 490)
    big = num(s, "area_full_km2").fillna(s.area_km2) if "area_full_km2" in s else s.area_km2
    for d, (river, top) in TAILWATERS.items():
        on = dam.eq(d) | (s["name"].fillna("").eq(river) & (s.elev_m <= top) & (big >= 20) & dam.eq(""))
        out = out.where(~on, d)
    return out


def trout_signs(s):
    """(found, none): trout found in the last 10 years with no later survey finding none; the latest survey in the
    last 10 years found none."""
    found, absent = num(s, "trout_found"), num(s, "trout_absent")
    pos = (found >= THIS_YEAR - 10) & (absent.isna() | (found >= absent))
    return pos, (absent >= THIS_YEAR - 10) & ~pos


def trout_factor(s):
    pos, neg = trout_signs(s)
    return np.select([pos, neg, s.trout_water.notna()], [1.2, 0.5, 1.2], 1.0)


ARTIFICIAL = (r"(?i)\b(channel|canal|aqueduct|diversion|ditch|flume|drain|conduit|penstock|spillway|outfall|"
              r"storm ?drain|flood control|tailrace|headrace|millrace|raceway)\b")
NATURAL = r"(?i)\b(creek|river|brook|branch|fork|run|wash|stream|bayou|slough|kill)\b"


def channel_factor(s):
    """0.2 on a built conveyance by name (see the module docstring), never where trout are recorded."""
    name = s["name"].fillna("").astype(str)
    built = name.str.contains(ARTIFICIAL) & ~name.str.contains(NATURAL)
    return np.where(built & ~(trout_signs(s)[0] | s.trout_water.notna()), 0.2, 1.0)


def heat_factor(s):
    """1 up to HEAT_START C of August air, linear to HEAT_FLOOR at HEAT_FULL. Never where trout are known, or below a
    dam (its releases may run cold)."""
    air, dam = num(s, "air_aug"), dam_of(s)
    f = np.clip(1 - (air - HEAT_START) / (HEAT_FULL - HEAT_START) * (1 - HEAT_FLOOR), HEAT_FLOOR, 1.0)
    below = (dam.ne("") & ~dam.str.startswith("in:")) | tailwater(s).ne("")
    return np.where(trout_signs(s)[0] | s.trout_water.notna() | below | air.isna(), 1.0, f)


def score(s):
    nhd_water = s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05}).fillna(0.3)
    cls = s["water_class"].fillna("no data") if "water_class" in s else pd.Series("no data", index=s.index)
    water = num(s, "water").where(cls.ne("no data"), nhd_water)      # the flow model, else the NHD class
    # below a gauged diversion the model can't see the canal: where the gauge just below kept flowing in under half
    # its summers since 2011 (05b_flow.py's div_water) and no trout are known here, its record is the water term
    gw = num(s, "div_water")
    by_gauge = (gw < 0.5) & ~(trout_signs(s)[0] | s.trout_water.notna())
    water = water.where(~by_gauge, 0.05 + 0.95 * gw)
    size = np.clip(np.log10(num(s, "area_full_km2").fillna(s.area_km2)) / np.log10(50), 0, 1)
    terrain, canopy = s.shade_pct.fillna(20) / 100, np.clip(num(s, "canopy_pct").fillna(0) / 100, 0, 1)
    shade = np.clip((1 - (1 - terrain) * (1 - 0.8 * canopy)) / 0.45, 0, 1)
    north = np.clip((s.northness.fillna(0) + 0.15) / 0.30, 0, 1)
    tw = tailwater(s)
    wt = pd.Series(watertemp.estimate(num(s, "air_aug"), s.elev_m, num(s, "area_full_km2").fillna(s.area_km2)), index=s.index)
    cool = np.clip((WATER_ZERO - wt) / (WATER_ZERO - WATER_FULL), 0, 1).fillna(0.5)   # no estimate: neutral
    thermal = 0.5 * np.where(tw.ne(""), 1.0, cool) + 0.35 * shade + 0.15 * north
    grad = band(s.gradient_pct, 1, 8, 10)
    ridden = num(s, "bike_med_min").fillna(0)          # 08_hike.py: the minutes of the typical approach ridden
    remote = np.clip((s.approach_med_min.fillna(0) + (RIDE_REMOTENESS - 1) * ridden) / 120, 0, 1)
    dfl = s["debris_flow"].fillna("").astype(str) if "debris_flow" in s else pd.Series("", index=s.index)
    d_sev = dfl.str.split(" ").str[0].map(DEBRIS)
    d_year = pd.to_numeric(dfl.str.extract(r"((?:19|20)\d\d)")[0], errors="coerce")
    sev = pd.Series(np.fmax(num(s, "burn_sev").values, d_sev.values), index=s.index)
    year = num(s, "burn_year").fillna(d_year)
    sev = sev.where(num(s, "burn_year").notna() | d_year.isna(), d_sev)   # below a burn: the hazard is the severity
    burn = burn_factor(year, sev)
    trout, heat, chan = trout_factor(s), heat_factor(s), channel_factor(s)
    s = s.copy()
    s["water_by_gauge"] = by_gauge
    if by_gauge.any():
        s.loc[by_gauge, "water_class"] = np.where(gw[by_gauge] <= 0.2, "mostly dry", "seasonal")
    s["thermal"] = thermal.round(2)
    s["water_aug"] = wt.round(1)
    s["water_term"] = water.round(2)
    s["burn_factor"] = np.round(burn, 2)
    s["trout_factor"] = trout
    s["heat_factor"] = np.round(heat, 2)
    s["tailwater"] = tw.where(tw.ne(""), None)
    s["channel_factor"] = chan
    s["fish_score"] = np.clip(100 * water * (0.30 * size + 0.30 * thermal + 0.15 * grad + 0.25 * remote) * burn * trout
                              * heat * chan, 0, 100).round(0)
    return s
