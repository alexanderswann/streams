"""Attach access / sun / context attributes to reaches and drops and compute the final fish score.

fish_score (0-100) = 100 x water x (0.30 size + 0.30 thermal + 0.15 gradient + 0.25 remoteness) x burn x trout x heat
                     x channel x warm
  water      dry-season flow from the flow model (02b_download_flow.py, 05b_flow.py: TNC's natural flows in California,
             elsewhere NHDPlus's mean flow scaled by the area's gauges): 0.05 + 0.95 x the share of years since 2011 the
             reach kept >= 0.1 cfs through July-October; 0.3 in a reservoir. 05b_flow.py takes NHD's class as a floor
             where the estimate isn't about the creek's own water (inherited from another creek, or leaving out the
             water from above a dam), valued as where there's no estimate (perennial 1.0, intermittent 0.35, a line NHD
             gives no class 0.3, no NHD line 0.15, ephemeral 0.05), and lifts every creek NHD maps perennial to
             year-round (water_floor). Where the model has no estimate (no line on the creek or below it on the map):
             what the area's creeks like it read on the model's own estimates (typical_water), never below
             NHD's class. A borrowed estimate is no more evidence than none, so it never reads drier than that either
             (borrowed()), nor shows a creek NHD has no line along mostly dry: such a reach reads, as one with no
             estimate does, as NHD labels it. Where the model sees creeks dry up (TNC's natural flows), NHD's class
             alone stays the floor. Then, in order, as the user put it: "id rather rate a dry
             creek as year round than a year round creek as dry" (2026-11-20), so only (1), (2) and (4) lower, each on
             evidence:
             (1) A bare channel, decided for each creek between confluences (creeks()): a reach passes where the
             model's typical summer low is under DRY_MARGINAL_CFS (there it can't tell: 25 of 31 such gauged LA creeks
             are dry most summers), the channel shows no green in late summer (Sentinel-2, 02g_greenness.py: under
             GREEN_BARE in the median summer and GREEN_BARE_ANY_YEAR in every one, and no strip greener than the slopes
             around), NHD maps it intermittent, ephemeral or not at all, and there's no trout record, dam, tailwater,
             open water or fire since GREEN_BURN_SINCE. A creek whose reaches all pass, or are read mostly dry by the
             model already, and none of which shows water (a trout record, a dam or tailwater, NHD perennial, open
             water, a channel GREEN_WET or greener: every flowing gauged creek in the test read 0.67-0.86), reads
             "seasonal" (GREEN_SEASONAL), never lower. A creek with a stretch 05_score.py left out as buried isn't
             read bare: its channel there can't be seen (06_map.py passes those reaches, left_out). (2) A USGS gauge on the reach's own creek (5+
             summers since 2011, within flowlib.GAUGE_KM on its model line, 2/3-1.5 x its drainage; not a canal):
             0.05 + 0.95 x its share of summers flowing. It raises a reach anywhere (Piru Creek below Pyramid Dam flows
             every summer on its releases), and lowers one only at or below the gauge and where no trout are known on
             the creek it stands for. (3) A tailwater (TAILWATERS) with no gauge record on the reach: full, since its
             dam's releases keep it flowing every summer, which the natural-flow model can't see. (4) Below a gauged
             diversion (flowlib.DIVERSIONS) the model can't see the water leave in a canal: where the USGS gauge just
             below kept flowing in under half of 5+ summers since 2011, and no trout are known on the reach, the gauge's
             share replaces the model's (today only the San Jacinto River near San Jacinto). (5) A trout record (trout
             found in the last 10 years, no later survey finding none): at least "usually flows" (TROUT_WATER), since
             trout there mean water most summers; where the model can't see creeks dry up (NHDPlus's mean flow),
             a reach with trout evidence of its own (a record, or a designated trout water along it) reads
             year-round. A lake's second
             outlet (05_score.py's side_lake) takes the water term of the creek its lake's main outlet starts, and
             the evidence behind it, where that
             reads it at least as wet as its own (second_outlets); NHD's class where NHD maps the channel
             intermittent or ephemeral; and it never reads wetter than the creek it runs into below,
             unless that is its lake's own river (side_lines_below)
  size       drainage area, log scale: 1 km^2 -> 0, 50+ km^2 -> 1. The full area (05c_drainages.py, area_streams.csv):
             with what flows in from neighbouring boxes and from above reservoirs, which each box's DEM routing
             misses (a creek crossing in from the next box, or leaving a dam, started again near nothing). A side
             channel of a river (05_score.py) takes the drainage of the river reach beside it, and a lake's second
             outlet that of the creek its lake's main outlet starts.
             Wild brook trout water (brook_water) is sized for brook trout: the same curve on BROOK_SCALE x the
             drainage, so it starts at 1/BROOK_SCALE km^2 and is full from 50/BROOK_SCALE. Brook trout live in smaller
             creeks than the other trout: on all 12 maps the records of brook trout sit on creeks draining a sixth of
             what the records of other trout only do (median drainage at the nearest reach). Other water is unchanged,
             and nothing scores lower: the user's choice, 2026-11-22 ("wild brook-trout water scored on its own terms")
  thermal    0.5 water temperature + 0.35 summer shade + 0.15 mountainside northness (south-facing -0.15 ->
             north-facing +0.15). Water temperature is the reach's estimated July-August daytime water temperature
             (watertemp.py: fitted per area to measured creeks; in LA on August air + elevation; in three of the
             Adirondack maps with the share of a creek's water that comes through a lake within 650 ft upstream:
             a pond's outlet runs at the pond's surface temperature, and the warmth fades fast): full credit up to
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
  burn       fire since 2016: <=2 years ago x0.4, 3-5 x0.7, 6-9 x0.9, scaled by the fire's soil burn severity where the
             Forest Service mapped it (BAER): high 100%, moderate 75%, low 40%, very low 15%. A channel also takes the
             ash and sediment of the burned slopes above it, so the USGS post-fire debris-flow hazard sets a floor (high
             100%, moderate 75%, low 40%), and a reach below a recent burn that didn't burn itself is penalised from the
             hazard's fire year. Where neither maps the severity, the fire marks nothing down (burn_factor): a burn of
             unknown severity is no near-certain harm. On LA's burned creeks with no severity map (the 2017-2022 fires:
             the BAER layer holds only recent ones) trout were recorded after the fire on 12% of those draining 10 km2
             or more, against 9% of unburned ones (2026-11-22)
  trout      evidence of trout, x1.2: trout found in the last 10 years (a state survey or stocking, an iNaturalist
             sighting) with no later survey finding none, or a designated trout water or wild trout patch. A survey
             that found none marks nothing down (trout_factor). Capped at 100
  warm       warm-water gate (the user's choice, 2026-11-25, after the r/bluelining rules of thumb): x WARM_FACTOR
             where the reach's estimated summer water temperature (watertemp.py) is WARM_GATE_F (23.3 C) or more, unless it is a tailwater, a survey found trout on it in the last 10 years with no
             later survey finding none (11_context.py's trout_survey), or it is wild brook trout water (brook_water).
             Stocking lists, iNaturalist sightings and designations alone don't exempt it: in north Georgia half the
             best water of 2026-11-25 (2,354 mi) lay below 1,600 ft at an estimated 70-75 °F, much of it designated
             trout water the state stocks or not at all (bluelining-bands-report.md)
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
from config import has

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
                                "drive_km": th.drive_km, "th_lat": th.geometry.y.round(6), "th_lon": th.geometry.x.round(6),
                                "th_closed": th.get("closed_now")})       # 09_drive.py: today's closures on the way
        out = out.merge(th_attr, on="th_id", how="left")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def burn_factor(year, sev=None):
    """The burn term from the fire's year and its severity (0-1, BAER or the debris-flow hazard). A severity nobody
    mapped counts as none: the fire marks nothing down (module docstring)."""
    yrs = THIS_YEAR - year
    f = np.where(pd.isna(year), 1.0, np.select([yrs <= 2, yrs <= 5, yrs <= 9], [0.4, 0.7, 0.9], 1.0))
    return f if sev is None else 1 - (1 - f) * np.where(pd.isna(sev), 0.0, sev)


DEBRIS = {"high": 1.0, "moderate": 0.75, "low": 0.4}


def num(s, c):
    return pd.to_numeric(s[c], errors="coerce") if c in s else pd.Series(np.nan, index=s.index)


def low_lines(s):
    """The lines 03b_stitch.py laid lower along NHD's named and year-round lines (05_score.py's low_channel). The rules
    here that read one reach by others (a creek's reaches between confluences, the creeks a reach with no estimate is
    compared with, the line a second outlet runs into, a gauge's creek) read the other reaches without them, as before
    they were drawn; they read the 0.25 km2 network's reaches."""
    return (pd.to_numeric(s["low_channel"], errors="coerce").fillna(0).to_numpy() > 0) if "low_channel" in s \
        else np.zeros(len(s), bool)


RIDE_REMOTENESS = 2.0    # a minute ridden on the approach counts as this many minutes of remoteness (user's choice)
# Size term on wild brook trout water: the drainage counts this many times over. The median drainage at the nearest
# reach of records of other trout only (brown, rainbow, cutthroat; no brook trout), over the median at records of
# brook trout, all 12 maps, stocking and lakes left out (2026-11-23, on the reaches of the 0.1 sq mi floor): agency
# surveys 31 / 4.6 km^2 (80 and 287 records: 6.7), iNaturalist 59 / 9.8 km^2 (1,120 and 423: 6.0). The lower one
BROOK_SCALE = 6.0
HEAT_START, HEAT_FULL, HEAT_FLOOR = 29.0, 30.5, 0.2    # August mean air, C
WARM_GATE_F, WARM_FACTOR = 74, 0.5      # warm-water gate (module docstring): summer water estimate, degrees F
# Dry creeks the flow model rates flowing (water term, (1) and (2)): measured on the USGS gauges of all 12 areas,
# 2026-11-20 (MULTI_AREA_LOG.md). None of the 221 gauged creeks that flow most summers is lowered
DRY_MARGINAL_CFS = 0.45        # the model's typical summer low under this: it can't tell wet from dry there
GREEN_BARE, GREEN_BARE_ANY_YEAR = 0.45, 0.5   # channel NDVI (90th pct within 30 m): median summer, every summer
GREEN_STRIP = 0.2              # a channel this much greener than the slopes around has a riparian strip (Andreas Canyon's
                               # palms: 0.31; it flows every summer)
GREEN_BURN_SINCE = 2018        # a fire strips the riparian green for years: not read where the reach burned since
GREEN_SEASONAL = 0.35          # a bare channel's water term: "seasonal", as NHD's intermittent, never lower
GREEN_WET = 0.67               # a channel as green as this in late summer shows water: every gauged creek in the
                               # marginal zone that flows most summers read 0.67-0.86 (2026-11-20)
BARE_SHARE = 1.0               # (1) a creek between confluences reads dry most summers where this share of its length is
                               # bare or read mostly dry (all of it: lowering a stretch that fails the test is not near-certain)
CREEK_RATIO = 0.8              # reaches carrying within this ratio of each other's drainage are one creek between
                               # confluences (no tributary of a quarter or more joins): the pairs of the audit's jump test
TROUT_WATER = 0.69             # (5) a trout record's floor: "usually flows", the middle of its range (50-85 % of summers)
WATER_CUTS = [-1, 0.24, 0.525, 0.8575, 1.0]   # the water term's class limits: 0.05 + 0.95 x 20 / 50 / 85 % of summers
WATER_CLASSES = ["mostly dry", "seasonal", "usually flows", "year-round"]
SET_ASIDE = ("lake", "box", "off-map lake")   # 05b_flow.py's borrowed_via: the kinds the rules before 2026-11-22 threw
                                              # away where they read below NHD's class (score(), natural flows)
# Thermal term: estimated July-August daytime water temperature (watertemp.py), C. Trout feed and grow well up to
# about 20 C and can't hold out in water that stays at 25 C. On LA's trout records (1,566 reaches) this gives the same
# mean credit as the 700-2300 m elevation band it replaced (0.91), and none of them zero
WATER_FULL, WATER_ZERO = 20.0, 25.0
# A reach that starts just below a lake: the maps name its warm first stretch (water_outlet, outlet_m) where that
# stretch is estimated this much warmer than the reach as a whole and is at least this long
OUTLET_NOTE_C, OUTLET_NOTE_M = 1.0, 50.0
# Dams known to release cold water from the bottom of the reservoir into a trout fishery below ("tailwaters"). The
# river below the dam, down to the next reservoir, takes the elevation part of the thermal term in full:
# dam -> (river, highest elevation of the tailwater in m)
_TAILWATERS = {
    "la": {"Cogswell Reservoir": ("West Fork San Gabriel River", 715), "Pyramid Lake": ("Piru Creek", 700)},
    # Buford Dam releases from the bottom of Lake Lanier: the Chattahoochee is trout water for 48 miles below it,
    # through Bull Sluice Lake (Morgan Falls Dam, a small run-of-river pool) to Peachtree Creek in Atlanta. Blue
    # Ridge Dam does the same for the Toccoa down to the Tennessee line. Bull Sluice Lake's line sits under its own
    # water (260 m on the DEM) and over the river below Morgan Falls Dam (242 m): at 265 m a reach of the lake's stretch
    # lying outside its outline (hooch_tailwater:s1492) was named Bull Sluice Lake's tailwater, though above the dam
    "n_georgia": {"Lake Sidney Lanier": ("Chattahoochee River", 285), "Bull Sluice Lake": ("Chattahoochee River", 250),
                  "Blue Ridge Lake": ("Toccoa River", 475)},
    # Nantahala Lake's water reaches the river from the bottom of the lake: through the tunnel to the powerhouse at
    # Beechertown, where the cold tailwater starts that runs through the gorge to Fontana Lake, and as the minimum flow
    # into the bypassed reach below the dam (the river is at 848 m just below it on the 10 m DEM; the lake at 917 m)
    "smokies": {"Nantahala Lake": ("Nantahala River", 850)},
}
# Jackson: the Snake below Jackson Lake Dam and Palisades Dam (both on the map since 2026-11-19) is cold water anyway
# (13.1 C measured below Palisades at Irwin, 7 readings). Vermont, Connecticut, Lexington: none known.
TAILWATERS = _TAILWATERS.get(watertemp.AREA, {})


def dam_of(s):
    return s["below_dam"].fillna("").astype(str) if "below_dam" in s else pd.Series("", index=s.index)


SIDE_EVIDENCE = ("flow", "water", "water_class", "water_rule", "water_by_gauge", "flow_src", "dry_cfs", "dry_cfs_drought",
                 "flow_years", "below_dam", "below_div", "div_gauge", "div_share", "div_years", "div_water", "green_p90",
                 "green_p90_max", "green_sur", "green_water", "gauge_site", "gauge_name", "gauge_share", "gauge_summers",
                 "gauge_years", "gauge_area_km2", "gauge_m", "gauge_below", "tailwater", "model_class", "water_floor")


def second_outlets(s):
    """The rows of the lakes' second outlets (05_score.py's side_lake) whose lake's main outlet starts a creek in the
    table (side_sid), and that creek's row for each. A second outlet is its lake's water leaving by another channel:
    it is scored on the water of that creek, with the evidence behind it (score(), SIDE_EVIDENCE), as the maps say,
    where that reads it at least as wet as its own evidence does (one-sided: a channel's own wetter evidence stands).
    On its own evidence its few km2, its own NHD line and its own ground below a dam spoke of a brook: below Lake
    Hemet's dam it read mostly dry (fish 3) beside the South Fork San Jacinto River, year-round there (fish 64), on the
    maps of 2026-11-22. Where the main outlet runs straight into the next lake, or its creek starts in the next box, it
    keeps its own; and where either of the two lies in a lake (reservoir), as 05b_flow.py's copy for a river's side
    channels."""
    if not {"side_lake", "side_sid", "sid"} <= set(s.columns):
        return np.array([], int), np.array([], int)
    j = s["side_sid"].map(pd.Series(np.arange(len(s)), index=s["sid"].values)).to_numpy(float)
    sec = np.flatnonzero(s["side_lake"].notna().to_numpy() & ~np.isnan(j))
    of_ = j[sec].astype(int)
    wc = s["water_class"].fillna("").astype(str).to_numpy() if "water_class" in s else np.full(len(s), "")
    ok = (wc[sec] != "reservoir") & (wc[of_] != "reservoir")
    return sec[ok], of_[ok]


SIDE_NHD = "second outlet: NHD's class"          # water_rule of a second outlet NHD maps intermittent or ephemeral
SIDE_BELOW = "second outlet: the line below"      # ... and of one that reads no wetter than the line it runs into
SIDE_JOIN_M = 25.0      # a reach end this near a reach start runs into it (a cell and a half), as watertemp.LAKE_JOIN_M
SIDE_DOWN = 300         # reaches followed down from the creek a lake's main outlet starts, to find its river


def side_lines_below(s):
    """The pieces of lakes' second outlets (05_score.py's side_lake) whose line runs into another creek below, and that
    creek's row for each: the first reach not part of the second outlet that starts where its last piece ends. Not
    where that reach lies on the way down from the creek its lake's main outlet starts (side_sid; SIDE_DOWN reaches,
    through lakes): the second outlet rejoins its lake's own river there. Not where its line ends in a lake (a reach
    lying in one), a pit or at the map's edge. A second outlet never reads wetter than the line it runs into: below
    Lake Hemet's dam its spillway channel read year-round on the South Fork San Jacinto's water, above Spillway Canyon
    Creek reading mostly dry (2026-11-22)."""
    empty = np.array([], int), np.array([], int)
    if not {"side_lake", "sid"} <= set(s.columns) or not s["side_lake"].notna().any():
        return empty
    import shapely, config
    g = s.geometry if s.crs is None or s.crs == config.CRS else s.geometry.to_crs(config.CRS)
    geom = np.array(g.values, dtype=object)
    start, end = shapely.get_point(geom, 0), shapely.get_point(geom, -1)
    lk = s["side_lake"].notna().to_numpy()
    grp = (s["side_lake"].astype(str) + "|" + s["side_sid"].astype(str)).to_numpy() if "side_sid" in s else s["side_lake"].astype(str).to_numpy()
    wet = np.array(s["water_class"].eq("reservoir") if "water_class" in s else np.zeros(len(s), bool), bool)
    if "below_dam" in s:
        wet = wet | s["below_dam"].fillna("").astype(str).str.startswith("in:").to_numpy()
    big = num(s, "area_full_km2").fillna(s.area_km2).to_numpy(float)
    low = low_lines(s)
    nxt_side, nxt = np.full(len(s), -1), np.full(len(s), -1)
    i_, j_ = shapely.STRtree(start).query(end, predicate="dwithin", distance=SIDE_JOIN_M)
    for i, j in sorted(zip(i_.tolist(), j_.tolist()), key=lambda ij: -big[ij[1]]):
        if i == j:
            continue
        if lk[i] and lk[j] and grp[i] == grp[j]:
            nxt_side[i] = j if nxt_side[i] < 0 else nxt_side[i]
        elif not lk[j] and nxt[i] < 0 and not low[j]:
            nxt[i] = j                              # the biggest reach starting where this one ends
    # where only the second outlet's line made the junction, 05_score.py runs the creek's reach on through it: the
    # line the second outlet runs into passes through its last piece's end
    end_ = np.flatnonzero(lk & (nxt < 0) & (nxt_side < 0))
    if len(end_):
        tree_ = shapely.STRtree(geom)
        for i in end_:
            c_ = [j for j in tree_.query(end[i], predicate="dwithin", distance=1.0) if j != i and not lk[j] and not low[j]]
            if c_:
                nxt[i] = max(c_, key=lambda j: big[j])
    row = pd.Series(np.arange(len(s)), index=s["sid"].values)
    main = s["side_sid"].map(row).to_numpy(float) if "side_sid" in s else np.full(len(s), np.nan)
    river = {}
    rows, below = [], []
    for i in np.flatnonzero(lk & ~wet):
        k, seen = i, {i}
        while nxt_side[k] >= 0 and nxt_side[k] not in seen:     # down its own pieces to the last
            k = nxt_side[k]
            seen.add(k)
        b = nxt[k]
        if b < 0 or wet[b]:
            continue                                # into a lake, a pit or off the map: no line below
        m = main[i]
        if np.isfinite(m):
            m = int(m)
            if m not in river:
                way, c = {m}, m
                for _ in range(SIDE_DOWN):
                    c = nxt[c]
                    if c < 0 or c in way:
                        break
                    way.add(c)
                river[m] = way
            if b in river[m]:
                continue                            # it rejoins its lake's own river
        rows.append(i)
        below.append(b)
    return np.array(rows, int), np.array(below, int)


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


def brook_water(s):
    """Wild brook trout water, sized for brook trout (BROOK_SCALE): a designation of wild brook trout covers the reach
    (11_context.py's brook_water: a brook trout patch, a state's wild brook trout stream or catchment), or a survey
    found wild brook trout on the creek in the last 10 years with no later survey finding none (brook_found, matched as
    trout_found is). Not a stocking list, and not an iNaturalist sighting: neither tells wild fish from stocked."""
    found, absent = num(s, "brook_found"), num(s, "trout_absent")
    rec = (found >= THIS_YEAR - 10) & (absent.isna() | (found >= absent))
    return rec | (s["brook_water"].notna() if "brook_water" in s else False)


def warm_factor(s, wt, tw):
    """The warm-water gate (module docstring): WARM_FACTOR where the estimated summer water temperature wt (C) is
    WARM_GATE_F or more, except on a tailwater (tw, tailwater()'s names), a reach a survey found trout on in the last 10
    years with no later survey finding none, and wild brook trout water. The estimate as it is, not as the popups round
    it to whole °F: the rule the user chose on its measured effect (bluelining-bands-report.md, option 2)."""
    found, absent = num(s, "trout_survey"), num(s, "trout_absent")
    surveyed = (found >= THIS_YEAR - 10) & (absent.isna() | (found >= absent))
    warm = np.asarray(wt, float) * 9 / 5 + 32 >= WARM_GATE_F                # NaN (no estimate): never
    return np.where(warm & tw.eq("").to_numpy() & ~surveyed.to_numpy() & ~np.asarray(brook_water(s), bool), WARM_FACTOR, 1.0)


def trout_factor(s):
    """x1.2 with trout found (trout_signs) or on a designated trout water, else 1. A survey that found none marks
    nothing down: an empty sample is no near-certainty. Where a later survey sampled the same reach it found trout
    after 80% of empty samples in NE Connecticut (on 40 of 54 creeks) and 56% in the Smokies (2 of 3 creeks), and
    after two empty samples in a row 83% and 53%; in LA on one of the three creeks sampled again (2026-11-22)."""
    return np.where(trout_signs(s)[0] | s.trout_water.notna(), 1.2, 1.0)


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


def creeks(s, extra=None):
    """Each reach's creek between confluences (an id): reaches joined end to end where the smaller carries at least
    CREEK_RATIO of the larger's drainage, so no tributary of a quarter or more of it joins between them (the pairs the
    audit's test of sudden changes along a creek looks at). A reach lying in a lake joins none. The reach below
    another is the one whose first point is its last (the confluence cell belongs to the reach below); at a box edge,
    the nearest other reach within 15 m of its end that doesn't end there itself.
    `extra`: reaches the map doesn't draw (those 05_score.py left out as buried: geometry, area_km2). They join the
    creeks as they did while drawn; then (the ids, the length of them in each creek, by id)."""
    import shapely
    from config import CRS
    g = gpd.GeoSeries(s.geometry.values, crs=s.crs).to_crs(CRS).values
    km2 = num(s, "area_full_km2").fillna(s.area_km2).to_numpy(float)
    lake = (s["water_class"].astype(str).eq("reservoir") if "water_class" in s else pd.Series(False, index=s.index)).to_numpy()
    n = len(s)
    low = low_lines(s)          # a line laid lower along NHD's lines joins only such lines (low_lines)
    if extra is not None and len(extra):
        g = np.concatenate([g, gpd.GeoSeries(extra.geometry.values, crs=extra.crs).to_crs(CRS).values])
        km2 = np.concatenate([km2, num(extra, "area_full_km2").fillna(extra["area_km2"]).to_numpy(float)])
        lake = np.concatenate([lake, np.zeros(len(extra), bool)])
        low = np.concatenate([low, low_lines(extra)])
    first, last = shapely.get_point(g, 0), shapely.get_point(g, -1)
    t_first, t_line = shapely.STRtree(first), shapely.STRtree(g)
    parent = np.arange(len(g))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(g)):
        c = [j for j in t_first.query(last[i], predicate="dwithin", distance=1.0) if j != i and low[j] == low[i]]
        if not c:
            c = [j for j in t_line.query(last[i], predicate="dwithin", distance=15.0)
                 if j != i and shapely.distance(last[j], last[i]) > 1.0 and low[j] == low[i]]
            c = sorted(c, key=lambda j: shapely.distance(g[j], last[i]))[:1]
        if not c:
            continue
        j = max(c, key=lambda j_: km2[j_])
        lo, hi = sorted((km2[i], km2[j]))
        if lake[i] == lake[j] and hi > 0 and lo / hi >= CREEK_RATIO:
            a, b = root(i), root(j)
            if a != b:
                parent[a] = b
    ids = pd.Series([root(i) for i in range(n)], index=s.index)
    if len(g) == n:
        return ids
    return ids, pd.Series(shapely.length(g[n:]), index=[root(i) for i in range(n, len(g))]).groupby(level=0).sum()


TYPICAL_SIGMA = np.log(2)     # typical_water: a peer's weight falls to 0.61 at twice or half the reach's drainage
TYPICAL_GROUP = {"perennial": ["perennial"], "intermittent": ["intermittent"], "ephemeral": ["ephemeral", "intermittent"],
                 "unmapped": ["perennial", "intermittent", "ephemeral", "unmapped"], "other": ["other"]}


def typical_water(s, cls, water, which=None, group_of=None):
    """For each reach with no flow estimate (or each one in `which`): what the map's creeks of its size and NHD label
    (`group_of`'s label where given, the creeks' own sorted by s.flow either way) read where the estimate is the
    model's own (flow_src "model"): the median of their water terms, each weighted by its
    length and by how near its drainage is to the reach's (a Gaussian in log drainage, TYPICAL_SIGMA; drainage counted
    from config.STREAM_KM2, where the map's creeks start). NHD's label sorts them (TYPICAL_GROUP): a creek NHD has no
    line along is compared with creeks of every label, since the missing line says nothing of its water, and an
    ephemeral one with the intermittent ones too. 0.5 where there are none. A failed look-up is no evidence about the
    creek, nor is a borrowed estimate (borrowed()), and neither votes: until 2026-11-23 every reach with an estimate
    did, each counted once, within a factor of 2 (4, then any, under 20), and drawing 43 more pond outlets moved two
    Fivemile River pieces in NE CT from usually flows to seasonal with their own data unchanged (quinebaug:s918, fish
    27 -> 14). On the model's own estimates the value moves only where the model's lines or its data do."""
    out = pd.Series(np.nan, index=s.index)
    which = (cls.eq("no data") if which is None else which).to_numpy(bool)
    if not which.any():
        return out.fillna(0.5)
    config = __import__("config")
    km = np.log(np.clip(num(s, "area_full_km2").fillna(s.area_km2).to_numpy(float), config.STREAM_KM2, None))
    src = s["flow_src"] if "flow_src" in s else pd.Series("", index=s.index)
    own = src.eq("model").to_numpy() & cls.isin(WATER_CLASSES).to_numpy() & water.notna().to_numpy() & ~low_lines(s)
    length = gpd.GeoSeries(s.geometry.values, crs=s.crs).to_crs(config.CRS).length.to_numpy()
    lab = s.flow.fillna("unmapped").to_numpy()
    grp = lab if group_of is None else pd.Series(group_of, index=s.index).fillna("unmapped").to_numpy()
    w_ = water.to_numpy(float)
    for g in np.unique(grp[which]):
        peer = own & np.isin(lab, TYPICAL_GROUP.get(g, [g]))
        if not peer.any():
            continue
        o = np.argsort(w_[peer])
        pk, pw, pl = km[peer][o], w_[peer][o], length[peer][o]
        for i in np.flatnonzero(which & (grp == g)):
            c = np.cumsum(pl * np.exp(-0.5 * ((pk - km[i]) / TYPICAL_SIGMA) ** 2))
            if c[-1] > 0:
                out.iat[i] = float(pw[np.searchsorted(c, 0.5 * c[-1])])
    return out.fillna(0.5)


def borrowed(s, cls):
    """Reaches whose flow estimate is borrowed, not about the creek's own water: scaled from another creek (05b_flow.py's
    flow_src "scaled": the first modelled reach below, in this box or the next, down a way through a lake, or an off-map
    lake's line), or, where the flows are natural flows, below a lake or dam holding half the drainage, where the model
    counts only the creek's own ground below it (05b_flow.py's `held`; a first stretch cut below a lake as its line)."""
    src = s["flow_src"] if "flow_src" in s else pd.Series("", index=s.index)
    out = src.eq("scaled").to_numpy(dtype=bool, copy=True)
    if has("tnc_flows") and {"area_full_km2", "area_edge_km2"} <= set(s.columns):
        full, edge = num(s, "area_full_km2"), num(s, "area_edge_km2")
        held = ((full - edge) >= 0.5 * full).fillna(False).to_numpy()
        if "cut_sid" in s:
            row_ = s["cut_sid"].map(pd.Series(np.arange(len(s)), index=s["sid"].values)).fillna(-1).astype(int).to_numpy()
            held = np.where(row_ >= 0, held[np.maximum(row_, 0)], held)
        out |= held
    return pd.Series(out, index=s.index) & cls.isin(WATER_CLASSES)


def score(s, left_out=None):
    # left_out: the reaches 05_score.py left out as buried (06_map.py reads buried_reaches.gpkg), for (1)'s creeks
    nhd_water = s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05}).fillna(0.3)
    cls = s["water_class"].fillna("no data") if "water_class" in s else pd.Series("no data", index=s.index)
    water = num(s, "water")
    cls2, rule = cls.copy(), pd.Series("", index=s.index)
    # (0) 05b_flow.py's floor: an estimate inherited from another creek, or one that leaves out the water from above a
    # dam, never puts a reach below NHD's class, and NHD-perennial creeks read year-round (water_floor says why)
    fl = s["water_floor"] if "water_floor" in s else pd.Series(None, index=s.index, dtype=object)
    rule[fl.notna() & cls.ne("no data")] = "NHD class"
    # no flow estimate (the model has no line on the creek or below it on the map): the area's creeks like it, never
    # below NHD's class
    no_est = cls.eq("no data") | water.isna()
    bor = borrowed(s, cls) & ~no_est
    # a class 05_score.py read along the reach (flow_along: raised from the 3-point vote's flow_vote, where the vote
    # missed NHD's line or read the drier side of where NHD's class changes) may raise the reach's water, never lower
    # it: its typical value is the higher of its class's peers' and its 3-point class's, and every reach's peers are
    # sorted by the 3-point class, so a raised class moves no other reach. Taken as the vote's, a filled "intermittent"
    # put 5 NE CT pieces with borrowed estimates among the drier "NHD maps intermittent" peers: year-round -> usually
    # flows, fish -12 to -21, 3 on wild trout water (2026-11-24). nhd_water (above) takes the raised class, the higher
    along = s["flow_along"].fillna(False).astype(bool) if "flow_along" in s else pd.Series(False, index=s.index)
    vote_ = s["flow_vote"].fillna("unmapped") if "flow_vote" in s else pd.Series("unmapped", index=s.index)
    voted = s.assign(flow=s.flow.where(~along, vote_)) if along.any() else s
    typ = typical_water(voted, cls, water, no_est | bor)
    peers_ = voted.flow.fillna("unmapped").copy()
    if (along & (no_est | bor)).any():
        typ_a = typical_water(voted, cls, water, (no_est | bor) & along, group_of=s.flow)
        hi_ = along & (no_est | bor) & (typ_a > typ + 1e-9)
        typ, peers_ = typ.where(~hi_, typ_a), peers_.where(~hi_, s.flow)
    s["typ_peers"] = peers_            # whose typical value it took, by NHD's label (06_map.py's popup line)
    if no_est.any():
        water = water.where(~no_est, np.fmax(typ, nhd_water))
        rule[no_est] = "no estimate"
    # ... and where the flow model can't see creeks dry up, the map shows the class that value gives, as it does for a
    # borrowed estimate lifted to it, unless the value reads mostly dry (no evidence shows a creek dry): a reach the pond
    # routing left with no creek below to scale from kept its score and showed only NHD's label (SE Pennsylvania,
    # 39.83231, -75.18171, 2026-11-24); outside LA 998 of 1,001 such reaches read year-round, 3 usually flows
    if not has("tnc_flows"):
        show_ = no_est & (water > WATER_CUTS[1] + 1e-9)
        cls2[show_] = pd.cut(water[show_], WATER_CUTS, labels=WATER_CLASSES).astype(str)
        rule[show_] = "no estimate, typical"
        cls = cls.where(~show_, cls2)
    # a borrowed estimate (borrowed()) is no more evidence about the creek than none: it never reads drier than what a
    # reach with no estimate takes, and on a creek NHD has no line along it never shows it mostly dry: the reach then
    # reads as NHD labels it, as one with no estimate does, scored on the larger of the two. Floored at NHD's class
    # alone (2026-11-23), 103 drawn pieces (61 mi) read "mostly dry" where the maps had said "NHD unmapped" (the
    # Champlain lowland's champlain:s250, 10 km2 between pieces of its creek NHD maps perennial, read year-round).
    # Where the flow model sees creeks dry up (TNC's natural flows) the estimate stays on NHD's class (05b_flow.py's
    # floor): the area's typical value there mixes mountain creeks with desert washes (lifting LA's borrowed estimates
    # to it put 19 more two-class jumps along its creeks and read two dry gauged creeks wet: Temescal Wash at Corona
    # Lake, Castaic Creek below Castaic Lake), and its borrowed reads that say mostly dry are the maps' own (of 1,090
    # such pieces on LA creeks NHD doesn't map, 1,012 read so before 2026-11-22; measured 2026-11-23)
    model_class = s["model_class"].copy() if "model_class" in s else pd.Series(None, index=s.index, dtype=object)
    up = no_cls = pd.Series(False, index=s.index)
    if not has("tnc_flows"):
        floor_ = np.fmax(typ, nhd_water)
        up = bor & (water < floor_ - 1e-9)
        model_class[up & model_class.isna()] = cls[up & model_class.isna()]
        water = water.where(~up, floor_)
        cls2[up] = pd.cut(water[up], WATER_CUTS, labels=WATER_CLASSES).astype(str)
        rule[up] = "typical"
        no_cls = bor & s.flow.eq("unmapped") & (water <= WATER_CUTS[1] + 1e-9)
        model_class[no_cls & model_class.isna()] = cls[no_cls & model_class.isna()]
        cls2[no_cls], rule[no_cls] = "no data", "borrowed, no class"
        cls = cls.where(~(up | no_cls), cls2)      # the rules below read the class these give
    else:
        # ... and there an estimate the rules before 2026-11-22 threw away where it read below NHD's class (found down a
        # way through a lake, in the box the creek runs on into, or on the line of a lake draining off the map:
        # 05b_flow.py's borrowed_via, SET_ASIDE) and that NHD's floor lifts reads, as it read then, as a reach with no
        # estimate does: NHD's label, scored on what like creeks read, never below NHD's class. Kept on NHD's class, 79
        # drawn LA pieces (46 mi) on creeks NHD doesn't map read "mostly dry" where the maps had said "NHD unmapped".
        # A plain borrowed estimate (the first modelled reach below, in the reach's own box) keeps the map's read
        via = s["borrowed_via"] if "borrowed_via" in s else pd.Series(None, index=s.index, dtype=object)
        no_cls = bor & fl.eq("inherited") & via.isin(SET_ASIDE)
        model_class[no_cls & model_class.isna()] = cls[no_cls & model_class.isna()]
        water = water.where(~no_cls, np.fmax(typ, nhd_water))
        cls2[no_cls], rule[no_cls] = "no data", "borrowed, set aside"
        cls = cls.where(~no_cls, cls2)
    # creeks the model rates flowing that are dry most summers (module docstring, water (1) and (2)); 05b_flow.py
    # writes the evidence: green_* (the channel's late-summer greenness) and gauge_* (a gauge on the creek)
    pos = trout_signs(s)[0] | s.trout_water.notna()
    green, src = num(s, "green_p90"), s["flow_src"] if "flow_src" in s else pd.Series("", index=s.index)
    dam_tw = dam_of(s).ne("") | tailwater(s).ne("")
    # (1) a bare channel, decided for each creek between confluences (creeks()): a reach passes where the model's low
    # flow is marginal, the channel bare in late summer with no greener strip and no open water, NHD calls it no more
    # than intermittent, and no trout record, dam, tailwater or fire since GREEN_BURN_SINCE is there; a creek reads
    # "seasonal" where all of it passes or is read mostly dry by the model already, and none of it shows water: a trout
    # record, a dam or tailwater, NHD perennial, open water, or a channel as green as the flowing gauged creeks'
    # (GREEN_WET). Decided reach by reach (before 2026-11-22) the class flipped along one river: about twenty times on
    # the Santa Clara, 207 sudden changes over 91 mi in LA (audit). A creek that passes on only part of its length keeps
    # the model's class: a stretch with a riparian strip or a confidently flowing model reach isn't near-certainly dry
    passes = ((num(s, "dry_cfs") < DRY_MARGINAL_CFS) & (green < GREEN_BARE) & (num(s, "green_p90_max") < GREEN_BARE_ANY_YEAR)
              & (green - num(s, "green_sur") < GREEN_STRIP) & (num(s, "green_water").fillna(0) < 0.05)
              & s.flow.isin(["intermittent", "ephemeral", "unmapped"]) & ~pos & ~dam_tw
              & ~(num(s, "burn_year") >= GREEN_BURN_SINCE) & src.isin(["model", "scaled"])
              & cls.isin(["year-round", "usually flows", "seasonal"]))
    if green.notna().any():
        # the creeks join through the reaches left out as buried, as while they were drawn; their length counts and
        # never passes, so a creek with a buried stretch isn't read bare (its channel there can't be seen)
        ck, hid = creeks(s, left_out) if left_out is not None and len(left_out) else (creeks(s), None)
        creek = cls.ne("reservoir")
        L = gpd.GeoSeries(s.geometry.values, crs=s.crs).to_crs(__import__("config").CRS).length.to_numpy()
        dry_len = pd.Series(L * (passes | cls.eq("mostly dry")).to_numpy() * creek.to_numpy(), index=s.index).groupby(ck).sum()
        all_len = pd.Series(L * creek.to_numpy(), index=s.index).groupby(ck).sum()
        if hid is not None:
            all_len = all_len.add(hid.reindex(all_len.index).fillna(0.0))
        shows = (pos | dam_tw | s.flow.eq("perennial") | (num(s, "green_water").fillna(0) >= 0.05) | (green >= GREEN_WET))
        veto = (shows & creek).groupby(ck).any()
        bare = (ck.map(dry_len / all_len.where(all_len > 0)) >= BARE_SHARE - 1e-6) & ~ck.map(veto).astype(bool) & creek
        bare &= cls.isin(["year-round", "usually flows", "seasonal"]) & src.isin(["model", "scaled"]) & (water > GREEN_SEASONAL + 1e-9)
    else:
        bare = pd.Series(False, index=s.index)
    water, cls2[bare], rule[bare] = water.where(~bare, GREEN_SEASONAL), "seasonal", "bare channel"
    gsh = num(s, "gauge_share")
    gwt = 0.05 + 0.95 * gsh
    site = s["gauge_site"].astype(object) if "gauge_site" in s else pd.Series(None, index=s.index, dtype=object)
    below = s["gauge_below"].astype(object).eq(True) if "gauge_below" in s else pd.Series(False, index=s.index)
    trout_site = set(site[pos & gsh.notna() & ~low_lines(s)].dropna())  # trout anywhere on the creek a gauge stands
                                                                        # for: not lowered
    rec = gsh.notna() & (((water > gwt + 0.05) & below & ~site.isin(trout_site)) | (water < gwt - 0.05))
    water = water.where(~rec, gwt)
    cls2[rec] = pd.cut(gsh[rec], [-1, 0.2, 0.5, 0.85, 1.0], labels=["mostly dry", "seasonal", "usually flows",
                                                                     "year-round"]).astype(str)
    rule[rec] = "gauge"
    # (3) a tailwater (TAILWATERS) flows every summer on its dam's releases, which the natural-flow model can't see: it
    # scales the creek's own ground below the dam. Piru Creek below Pyramid Dam read mostly dry or seasonal on 28 of its
    # reaches, and on about 20 more once the routing stopped leaking Pyramid Lake's own shores into that ground
    # (03b_stitch.route_lake, 2026-11-21). A gauge record on the reach (2) still stands: it is measured.
    tw_up = tailwater(s).ne("") & (water < 1.0) & ~rec
    water = water.where(~tw_up, 1.0)
    cls2[tw_up], rule[tw_up] = "year-round", "tailwater releases"
    # (4) below a gauged diversion the model can't see the canal: where the gauge just below kept flowing in under half
    # its summers since 2011 (05b_flow.py's div_water) and no trout are known here, its record is the water term
    gw = num(s, "div_water")
    by_gauge = (gw < 0.5) & ~(trout_signs(s)[0] | s.trout_water.notna())
    water = water.where(~by_gauge, 0.05 + 0.95 * gw)
    # (5) a trout record: trout found since THIS_YEAR - 10 with no later survey finding none (trout_signs) means water
    # most summers, whatever the model says: at least "usually flows". In LA 81 such reaches (53 mi) read mostly dry or
    # seasonal (Arroyo Trabuco: "mostly dry, 0.0 cfs"; audit, 2026-11-22). Nothing above lowers such a reach.
    tr = trout_signs(s)[0] & cls.ne("reservoir") & (water < TROUT_WATER - 1e-9)
    water = water.where(~tr, TROUT_WATER)
    cls2[tr], rule[tr] = "usually flows", "trout record"
    # (5) and, where the flow model can't see creeks dry up (NHDPlus's mean flow), trout water is water: a reach with
    # trout evidence of its own (a record as above, or a designated trout water, wild brook trout patches included,
    # along most of it or naming its own creek: 11_context.py's trout_water_own) reads year-round. There a read below it
    # comes from a small modelled flow on a small brook, or from NHD's label, and the label is a vote at three points
    # that can flip where NHD's perennial line meets its intermittent one: re-cut by the pond routing (2026-11-24), wild
    # brook trout reaches in north-east Connecticut went from year-round to seasonal or usually flows with their own
    # data unchanged (41.57632, -71.96099: fish 73 -> 38; Mount Hope River 64 -> 43; Ruby Brook 66 -> 46). A tributary
    # that only touches a designated river's line at its mouth reads the river's designation (pos) but not as its own
    # water. Nothing above lowers trout water: (1) and (4) skip it, (2) lowers no creek with trout on it; and a gauge's
    # record on the reach still stands, as it is measured. A reach the model has no estimate for shows it too, whichever
    # rule above read it ("no estimate, trout water": the popup says there is no estimate)
    # Where the flows are natural flows (TNC: LA), which see creeks dry up, a trout record keeps "usually flows".
    if not has("tnc_flows"):
        own_tw = (s["trout_water_own"].astype(str).eq("True") if "trout_water_own" in s
                  else pd.Series(False, index=s.index))
        tw5 = ((trout_signs(s)[0] | (s.trout_water.notna() & own_tw)) & cls.ne("reservoir") & (water < 1.0 - 1e-9)
               & gsh.isna())
        water = water.where(~tw5, 1.0)
        none_ = tw5 & no_est
        cls2[tw5], rule[tw5 & ~none_], rule[none_] = "year-round", "trout water", "no estimate, trout water"
    # a lake's second outlet (second_outlets): the water term of the creek its lake's main outlet starts, where that
    # reads it at least as wet as its own evidence does and NHD doesn't map the channel itself intermittent or
    # ephemeral (by the 3-point class: one read along the channel doesn't lower it); where NHD does, NHD's class; and
    # never wetter than the line it runs into below, unless that line is the main outlet's own river
    # (side_lines_below). Neither lowers one where trout are recorded on it
    sec, of_ = second_outlets(s)
    lk_ = s["side_lake"].notna().to_numpy() if "side_lake" in s else np.zeros(len(s), bool)
    nhd_dry = lk_ & voted.flow.isin(["intermittent", "ephemeral"]).to_numpy() & cls.ne("reservoir").to_numpy()
    wet_ = (water.to_numpy()[of_] >= water.to_numpy()[sec] - 1e-9) & ~nhd_dry[sec]
    sec, of_ = sec[wet_], of_[wet_]
    water, cls2, rule, by_gauge = water.copy(), cls2.copy(), rule.copy(), by_gauge.copy()
    for x_ in (water, cls2, rule, by_gauge):
        x_.iloc[sec] = x_.to_numpy()[of_]
    nd_ = np.flatnonzero(nhd_dry & ~pos.to_numpy())
    water.iloc[nd_] = nhd_water.to_numpy()[nd_]
    cls2.iloc[nd_], rule.iloc[nd_], by_gauge.iloc[nd_] = "no data", SIDE_NHD, False
    cap_, below_ = side_lines_below(s)
    drier_ = (water.to_numpy()[below_] < water.to_numpy()[cap_] - 1e-9) & ~pos.to_numpy()[cap_]
    cap_, below_ = cap_[drier_], below_[drier_]
    for x_ in (water, cls2, by_gauge):
        x_.iloc[cap_] = x_.to_numpy()[below_]
    rule.iloc[cap_] = SIDE_BELOW
    # a side channel of a river (05_score.py's side_of) is sized as the river beside it (river_km2): D8 sends a split
    # river's water down one arm, and the other arm's own few km2 say nothing of the water in it
    big = np.fmax(num(s, "area_full_km2").fillna(s.area_km2), num(s, "river_km2").fillna(0))
    brook = brook_water(s)                   # sized for brook trout: never lower, as BROOK_SCALE > 1
    size = np.clip(np.log10(big * np.where(brook, BROOK_SCALE, 1.0)) / np.log10(50), 0, 1)
    terrain, canopy = s.shade_pct.fillna(20) / 100, np.clip(num(s, "canopy_pct").fillna(0) / 100, 0, 1)
    shade = np.clip((1 - (1 - terrain) * (1 - 0.8 * canopy)) / 0.45, 0, 1)
    north = np.clip((s.northness.fillna(0) + 0.15) / 0.30, 0, 1)
    tw = tailwater(s)
    lake, lake_top, lake_m = watertemp.lake_parts(s)
    wt = pd.Series(watertemp.estimate(num(s, "air_aug"), s.elev_m, big, lake), index=s.index)
    # a reach that starts just below a lake is scored on its estimate as a whole (the mean along it), but its first
    # stretch runs warmer: that stretch's own estimate and length, for the maps to say (no part in the score)
    top = pd.Series(watertemp.estimate(num(s, "air_aug"), s.elev_m, big, lake_top), index=s.index)
    outlet = (top - wt >= OUTLET_NOTE_C) & (lake_m >= OUTLET_NOTE_M)
    # no estimate: where the area's fit has no skill, its measured sites' mean stands for every creek (the model the
    # skill test compares with: a cold area stays cold); with no measured sites at all, neutral
    avg = watertemp.area_mean()
    no_est = float(np.clip((WATER_ZERO - avg) / (WATER_ZERO - WATER_FULL), 0, 1)) if np.isfinite(avg) else 0.5
    cool = np.clip((WATER_ZERO - wt) / (WATER_ZERO - WATER_FULL), 0, 1).fillna(no_est)
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
    warm_f = warm_factor(s, wt, tw)
    s = s.copy()
    s["model_class"] = model_class                 # the borrowed estimate's own class where the rules above lifted it
    changed = rule.ne("") & rule.ne("no estimate") & rule.ne("NHD class")
    s.loc[changed, "water_class"] = cls2[changed]
    s["water_rule"] = rule.where(rule.ne("") & ~by_gauge, None)
    s["water_by_gauge"] = by_gauge
    if by_gauge.any():
        s.loc[by_gauge, "water_class"] = np.where(gw[by_gauge] <= 0.2, "mostly dry", "seasonal")
    s["thermal"] = thermal.round(2)
    s["water_aug"] = wt.round(1)
    s["water_outlet"] = top.round(1).where(outlet)
    s["outlet_m"] = pd.Series(lake_m, index=s.index).round().where(outlet)
    s["water_term"] = water.round(2)
    s["burn_factor"] = np.round(burn, 2)
    s["trout_factor"] = trout
    s["brook_size"] = np.asarray(brook, bool)      # sized as wild brook trout water (brook_water)
    s["heat_factor"] = np.round(heat, 2)
    s["tailwater"] = tw.where(tw.ne(""), None)
    s["channel_factor"] = chan
    s["warm_factor"] = warm_f
    # a lake's second outlet on its creek's water (above), and the evidence behind it for the maps: its creek's, or the
    # line's below where that caps it
    s["on_outlet_creek"] = np.isin(np.arange(len(s)), sec) & ~np.isin(np.arange(len(s)), cap_)
    for rows_, from_ in ((sec, of_), (cap_, below_)):
        for c_ in [c_ for c_ in SIDE_EVIDENCE if c_ in s and len(rows_)]:
            s.iloc[rows_, s.columns.get_loc(c_)] = s[c_].to_numpy()[from_]
    if len(nd_) or len(cap_):
        s.iloc[nd_, s.columns.get_loc("water_rule")] = SIDE_NHD
        s.iloc[cap_, s.columns.get_loc("water_rule")] = SIDE_BELOW
    # the terms as the line below combines them, unrounded, for the popups' breakdown of each reach's score (06_map.py's
    # fs_parts, map_score.js): water, size and the drainage it reads, the water-temperature part of the thermal term
    # (in full on a tailwater), burn and heat. The pages work out the others from their inputs, as above
    s["t_water"], s["t_size"], s["t_big"] = water.to_numpy(float), np.asarray(size, float), np.asarray(big, float)
    s["t_cool"], s["t_burn"], s["t_heat"] = np.where(tw.ne(""), 1.0, cool), np.asarray(burn, float), np.asarray(heat, float)
    s["fish_score"] = np.clip(100 * water * (0.30 * size + 0.30 * thermal + 0.15 * grad + 0.25 * remote) * burn * trout
                              * heat * chan * warm_f, 0, 100).round(0)
    return s
