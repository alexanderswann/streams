"""The trout calendar: when in the year a reach fishes best, by half-month (the 1st-15th and the 16th-end of each month).
Separate from the fish score, which stays as it is (scoring.py, map_score.js): the score says where, the calendar when.
Fishing conditions only: no legal seasons (the user's choice, 2026-11-24); the popup says to check the state's rules.

For each half-month h (0 = Jan 1-15 ... 23 = Dec 16-31) a reach gets
    100 x water temperature x flow x light x ice x clarity x oxygen x hatches
each part 0-1, the lowest named as the reason (the popup's words). The user chose the parts (2026-11-24): water
temperature, flow (runoff), sun and shade, and from their own list ice, water clarity, water quality (as dissolved
oxygen) and bugs (as hatches). Each comes from data the area has, the same way in every area:
  water   the half-month's water temperature against the trout's limits (THERMAL): the reach's Jul-Aug estimate
          (watertemp.py, the one the fish score uses, fx's third number) moved by the area's seasonal curve, fitted
          on the Water Quality Portal's dated readings (water_season()): T(h) = max(0.5, S + d[h] + k[h] (T_aug - S)),
          where S is the measured sites' mean Jul-Aug temperature, d[h] how far a site at S runs below its summer in
          half-month h, and k[h] how much of a site's summer warmth or coolness it keeps then. Checked on all 12 maps
          (2026-11-24, leave-one-out over the sites, every half-month): 1.8-3.0 C off, against 2.6-5.5 C for "all water
          alike" (k = 0) and 2.4-3.3 C for "a site keeps its summer difference all year" (k = 1); a k below 0 in winter
          (spring-fed water warmer then) was no better on any map. Wild brook trout water (fx flag b) is judged on
          brook trout's limits, other water on brown and rainbow trout's. A tailwater (fx flag w: a dam releasing from
          the bottom of its lake, scoring.TAILWATERS) is held within TAILWATER_C.
  flow    runoff and low water: the half-month's typical day against the reach's typical day of the year
          (flow_shapes(): each of the area's USGS gauges' median daily flow in that half-month over its median day,
          blended over the gauges by likeness of drainage area and distance). Runoff, snowmelt and spring rain over
          twice the typical day, scores less (FLOW); low water only where extreme, and never on a creek that flows
          every summer by its own evidence (the fish score's water term, fx's first number, at year-round), since the
          gauges' small creeks dry where it doesn't: a creek that may run dry is marked down by that same evidence in
          July-October (multiplied by its water term over the year-round value). A tailwater's flow is the dam's
          releases: no flow mark (the West Fork San Gabriel below Cogswell Dam read 0.04x, "very low water", from the
          area's drying creeks while it flows every summer).
  light   direct sun on the water (the terrain's horizon at 13 bearings, traced from the 10 m DEM as 10_sun.py does,
          and the tree canopy): in warm water a stream in full sun scores up to 0.30 less (bright, warming, fish hold
          deep); in cold water one with no sun up to 0.15 less (no midday warming). The same sun path gives the clock
          times of sun on the water, for the popup's time-of-day line.
  ice     the share of days the nearby USGS gauges record their flow as ice-affected (ice_shapes(): days flagged
          estimated or ice in the half-month, less the gauge's share in the months without ice, in the half-months
          whose typical water is ICE_C or colder), blended as the flow is. Every day iced over: x (1 - ICE_K). At
          8 C the southern Appalachians' ice counts: their typical January water is 5-8 C, but the high creeks ice
          over in the coldest weeks (the Smokies: 7 of 18 gauges, up to 22 % of days; Lexington 8 of 10, up to 24 %);
          LA's January water reads 11.5 C, and its gauges show no winter excess of flagged days.
  clarity the area's stream turbidity in the half-month (clarity_season(): the Water Quality Portal's dated readings,
          each site's median then, the median over the sites), against CLARITY. Snowmelt runoff around Jackson reads
          19-23 NTU in May and early June; north-eastern Connecticut's creeks read 1-2.4 NTU all year.
  oxygen  dissolved oxygen: the oxygen water holds at the reach's temperature and elevation (do_sat()) times the
          area's typical saturation in the half-month (oxygen_season(): the Water Quality Portal's readings paired with
          the temperature read at the same sampling), against OXY (trout need about 6 mg/L).
  hatches the share of the area's iNaturalist records that are mayflies and caddisflies in the half-month, over the
          year's share (hatch_curve(); against all records, so that people's own seasons cancel): at or above the
          year's share x 1, none x HATCH_LO. Around north-eastern Connecticut mayflies read 1.6-2.4x the year's share
          from mid-May into July, caddisflies 1.3-1.8x from June to September. Stoneflies are left out: their records
          peak at 3-6x in February and March (small winter stoneflies on the snow, when little else is out to be
          recorded), which says little about trout feeding. An area with few records reads near 1 all year.
The page works all of it out from a few numbers per reach (map_calendar.js: cz, the horizon and, where it isn't the
map's, the time zone; with fx, a, el, x, y) and the area's tables (LBL["cal"]), as map_score.js works out the fish
score's breakdown; calendar() below is the same sum in Python, for the checks.
"""
import os, re, json, math, datetime as dt
import numpy as np, pandas as pd

HALF = 24
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"     # one character = 0..63
AZ = list(range(60, 301, 20))                    # the bearings the horizon is kept at: the sun's path at 25-50 N
YEAR = 2027                                      # the year the half-months' dates are worked on

# ---- thermal limits (deg C -> 0..1), piecewise linear. From the U.S. Fish and Wildlife Service's habitat suitability
# index models (public domain): brook trout (Raleigh 1982, FWS/OBS-82/10.24) best at 11-16 C; brown trout (Raleigh et
# al. 1986, Biol. Rep. 82(10.124)) at 12-19 C; rainbow trout (Raleigh et al. 1984, FWS/OBS-82/10.60) at 12-18 C. The
# upper end follows the anglers' rule the agencies and Trout Unlimited give, to stop fishing for trout at 68 F (20 C):
# brook trout read poor there, brown and rainbow fair; the lower end, trout that barely feed in near-freezing water.
THERMAL = {"brook": [(0.5, 0.05), (4, 0.25), (7, 0.6), (10, 1.0), (16, 1.0), (18, 0.6), (20, 0.25), (21, 0.1), (22, 0.0)],
           "trout": [(0.5, 0.05), (4, 0.25), (7, 0.6), (10, 1.0), (18, 1.0), (20, 0.5), (21.5, 0.25), (23, 0.05), (24, 0.0)]}
# A tailwater's water: the Chattahoochee 12 mi below Buford Dam (GA EPD, McGinnis Ferry Road, 582 readings) reads
# monthly medians of 8.3-13.1 C all year, against 7-24 C at Belton Bridge above Lake Lanier
TAILWATER_C = (8.0, 13.0)
# ---- flow: log10(typical day in the half-month / the reach's typical day of the year) -> 0..1. Full from 0.25x to
# 2x: late-summer low water in the East (0.2-0.5x the median day: 02b's gauges, 2026-11-24) is the usual state of a
# creek then, and a creek that may run dry is marked down by its own evidence (DRY); a snowmelt river runs about 2x its
# median day through July (Jackson's gauges: 2.3x in the second half of July) in its usual summer water. Runoff is
# marked down from there: 0.6 at 3.5x, 0.3 at 5x, 0.15 at 10x (Jackson's June peak, 5-6.5x)
FLOW = [(-2.0, 0.6), (-1.3, 0.85), (-0.6, 1.0), (0.3, 1.0), (0.544, 0.6), (0.7, 0.3), (1.0, 0.15)]
DRY = range(12, 20)                              # Jul 1 - Oct 31: 05b's dry season, the one the water term is measured in
YEAR_ROUND = 0.8575                              # flowlib.water_term's value from which a creek reads "year-round"
FLOW_SIG_LOG, FLOW_SIG_KM = 0.5, 60.0            # how gauges are blended: drainage likeness (log10) and distance
# ---- light: e = share of the day the water is in direct sun x (1 - 0.8 tree canopy), as the fish score's shade
WARM_C, COLD_C = 16.0, 8.0                       # from WARM_C up: 1 - 0.30 e; to COLD_C: 0.85 + 0.15 e; between, mixed
STEP_MIN = 10                                    # the day is walked in 10-minute steps, as 10_sun.py does
# ---- ice, clarity, oxygen, hatches
ICE_C = 8.0                                      # ice counts in half-months whose typical water (S + d) is this cold
ICE_K = 0.85                                     # iced every day: x 0.15
ICE_FROM = "2000-10-01"                          # the gauge records read for ice: water years 2001 on
CLARITY = [(5, 1.0), (10, 0.92), (25, 0.75), (50, 0.55), (100, 0.35)]   # turbidity, NTU -> 0..1
OXY = [(3.0, 0.0), (4.0, 0.2), (5.0, 0.5), (6.0, 0.85), (7.0, 1.0)]       # dissolved oxygen, mg/L -> 0..1
HATCH_LO = 0.85                                  # no aquatic insects about: x 0.85; the year's share or more: x 1
HATCH_TAXA = "48011,62164"                       # iNaturalist: Ephemeroptera, Trichoptera (hatch_curve())
HATCH_PAD = 0.5                                  # deg around the area for the iNaturalist counts (more records)
MIN_SITES = 4                                    # a WQP half-month with fewer sites takes its neighbours' values

# ---- time zones, for the clock times only: each state's standard offset (h) and daylight saving time; states the
# zone line crosses by a rough line (a reach near it may read an hour off)
STATE_TZ = {**{s: -5 for s in "CT DE DC GA ME MD MA NH NJ NY NC OH PA RI SC VT VA WV".split()},
            **{s: -6 for s in "AL AR IL IA LA MN MS MO OK WI".split()},
            **{s: -7 for s in "CO MT NM UT WY".split()}, **{s: -8 for s in "CA NV WA".split()},
            "AK": -9, "HI": -10, "AZ": -7, "ID": -7, "TN": -5, "KY": -5, "IN": -5, "FL": -5, "MI": -5,
            "ND": -6, "SD": -6, "NE": -6, "KS": -6, "TX": -6, "OR": -8}
NO_DST = {"AZ", "HI"}


def tz_of(st, lon, lat):
    """(standard UTC offset, observes daylight saving time) at a place in state st."""
    off = STATE_TZ.get(st, round(lon / 15))
    off = {"ID": -8 if lat > 45.6 else off, "TN": -6 if lon < -85.2 else off, "KY": -6 if lon < -85.6 else off,
           "IN": -6 if lon < -86.8 and (lat > 41.0 or lat < 38.3) else off, "FL": -6 if lon < -85.0 else off,
           "MI": -6 if lon < -87.6 and lat > 45.0 else off, "ND": -7 if lon < -101.3 and lat < 47.0 else off,
           "SD": -7 if lon < -100.5 else off, "NE": -7 if lon < -101.3 else off, "KS": -7 if lon < -101.5 else off,
           "TX": -7 if lon < -104.9 else off, "OR": -7 if lon > -117.7 and lat < 44.5 else off}.get(st, off)
    return off, st not in NO_DST


def mid_date(h, year=YEAR):
    return dt.date(year, h // 2 + 1, 8 if h % 2 == 0 else 23)


def half_of(dates):
    """The half-month (0..23) of each date (a pandas datetime Series)."""
    return (dates.dt.month - 1) * 2 + (dates.dt.day > 15).astype(int)


def _fill_smooth(vals, n, min_n, log=False):
    """24 values: those with fewer than min_n behind them take their neighbours' (round the year), then one pass of a
    1-2-1 smoothing round the year; in logs where log."""
    a = np.array(vals, float)
    a[np.asarray(n) < min_n] = np.nan
    if np.isnan(a).all():
        return [None] * HALF
    if log:
        a = np.log(np.clip(a, 1e-3, None))
    idx = np.flatnonzero(~np.isnan(a))
    a = np.interp(np.arange(HALF), np.r_[idx - HALF, idx, idx + HALF], np.r_[a[idx], a[idx], a[idx]])
    a = (np.roll(a, 1) + 2 * a + np.roll(a, -1)) / 4
    return list(np.exp(a) if log else a)


def _wqp(res, units=None, lo=None, hi=None):
    """WQP narrowResult rows with value v, date, half-month h and site key (co-located stations one site, as
    watertemp.measured_sites() reads them); units: the unit codes kept (lower case)."""
    r = res.copy()
    r["v"] = pd.to_numeric(r.ResultMeasureValue, errors="coerce")
    r["date"] = pd.to_datetime(r.ActivityStartDate, errors="coerce")
    u = r["ResultMeasure/MeasureUnitCode"].astype(str).str.strip().str.lower()
    if units is not None:
        r = r[u.isin(units)]
    r = r[r.date.notna() & r.v.notna()]
    if lo is not None:
        r = r[r.v.between(lo, hi)]
    r["h"] = half_of(r.date)
    return r


# ---- the water temperature's year: the area's curve from the Water Quality Portal's dated readings ----
def water_season(res, st, summer_months=(7, 8), min_pairs=6):
    """{S, d[24], k[24], n[24]}: from the readings (WQP narrowResult rows) of sites with a Jul-Aug median, as
    watertemp.measured_sites() reads them (07:00-18:00, co-located stations one site). For each half-month, over the
    sites read then too: (the site's median then - its Jul-Aug median) = d + (k - 1) (its Jul-Aug median - S), least
    squares; k kept to 0..1. Half-months with fewer than min_pairs such sites take their neighbours' values; then
    one pass of a 1-2-1 smoothing round the year."""
    r = res.copy()
    r["v"] = pd.to_numeric(r.ResultMeasureValue, errors="coerce")
    r.loc[r["ResultMeasure/MeasureUnitCode"] == "deg F", "v"] = (r.v - 32) * 5 / 9
    r["date"] = pd.to_datetime(r.ActivityStartDate, errors="coerce")
    r["hour"] = pd.to_numeric(r["ActivityStartTime/Time"].astype(str).str[:2], errors="coerce")
    r = r[r.v.between(0, 40) & r.date.notna() & (r.hour.between(7, 18) | r.hour.isna())]
    r = r.join(st[["LatitudeMeasure", "LongitudeMeasure"]], on="MonitoringLocationIdentifier")
    r["key"] = r.LatitudeMeasure.round(3).astype(str) + "," + r.LongitudeMeasure.round(3).astype(str)
    r["h"] = half_of(r.date)
    med = r.groupby(["key", "h"]).v.median().unstack()
    summer = r[r.date.dt.month.isin(summer_months)].groupby("key").v.median()
    S_all = summer.reindex(med.index)
    S = float(summer.mean())
    d, k, n = np.full(HALF, np.nan), np.full(HALF, np.nan), np.zeros(HALF, int)
    for h in range(HALF):
        if h not in med:
            continue
        ok = med[h].notna() & S_all.notna()
        n[h] = int(ok.sum())
        if n[h] < min_pairs:
            continue
        x, y = (S_all[ok] - S).to_numpy(float), (med[h][ok] - S_all[ok]).to_numpy(float)
        A = np.c_[np.ones_like(x), x]
        (d_, e_), *_ = np.linalg.lstsq(A, y, rcond=None)
        d[h], k[h] = d_, min(max(1 + e_, 0.0), 1.0)
    for arr in (d, k):                           # gaps: from the nearest half-months on either side, round the year
        if np.isnan(arr).all():
            continue
        idx = np.flatnonzero(~np.isnan(arr))
        xs = np.r_[idx - HALF, idx, idx + HALF]
        arr[:] = np.interp(np.arange(HALF), xs, np.r_[arr[idx], arr[idx], arr[idx]])
    sm = lambda a: (np.roll(a, 1) + 2 * a + np.roll(a, -1)) / 4
    return dict(S=round(S, 2), d=[round(float(v), 2) for v in sm(d)], k=[round(float(v), 3) for v in sm(k)],
                n=[int(v) for v in n])


# ---- the flow's year and its ice: each USGS gauge's typical day by half-month ----
def flow_shapes(daily, sites, first_year=1991, min_years=10):
    """[[log10 km2, lat, lon, [24 ratios], site_no], ...]: per gauge with min_years+ of daily values (since first_year
    where it has that many there, else its whole record), the median day of each half-month over the median day of
    the year (the mean day where the median day is 0)."""
    daily = daily.assign(date=pd.to_datetime(daily.date))
    out = []
    for g in sites.itertuples():
        t = daily[daily.site_no.astype(str) == str(g.site_no)]
        rec = t[t.date.dt.year >= first_year]
        if rec.date.dt.year.nunique() < min_years:
            rec = t
        if rec.date.dt.year.nunique() < min_years or not np.isfinite(g.drain_area_va) or g.drain_area_va <= 0:
            continue
        h = half_of(rec.date)
        by = rec.groupby(h).cfs.median().reindex(range(HALF))
        base = rec.cfs.median()
        base = base if base > 0 else rec.cfs.mean()
        if not base > 0 or by.isna().any():
            continue
        out.append([round(math.log10(g.drain_area_va * 2.589988), 3), round(g.geometry.y, 4), round(g.geometry.x, 4),
                    [round(float(v), 3) for v in (by / base).clip(lower=0.001)], str(g.site_no)])
    return out


def ice_shapes(est, water, min_years=5):
    """Per gauge (est: {site_no: DataFrame of date, est (1 where the day's flow is flagged estimated or ice)}), the
    share of days ice-affected in each half-month: its flagged share then less its share in the half-months without
    ice (equipment, revisions), in the half-months whose typical water (water_season's S + d) is ICE_C or colder; 0 in
    the others. None for a gauge with fewer than min_years of flags. USGS marks a day estimated when ice spoils the
    stage-discharge relation, the usual case in winter: Vermont's Mad River near Moretown reads 81-94 % of its
    January and February days so, 3 % in summer; the Arroyo Seco above Pasadena shows no winter excess."""
    cold = [water["S"] + water["d"][h] <= ICE_C for h in range(HALF)]
    out = {}
    for site, t in est.items():
        if t is None or t.empty or pd.to_datetime(t.date).dt.year.nunique() < min_years:
            out[site] = None
            continue
        d = pd.to_datetime(t.date)
        share = t.est.groupby(half_of(d)).mean().reindex(range(HALF))
        warm = share[[not c for c in cold]].dropna()
        base = float(warm.mean()) if len(warm) else 0.0
        out[site] = [round(float(min(max(v - base, 0.0), 1.0)), 2) if c and pd.notna(v) else 0.0
                     for v, c in zip(share.values, cold)]
    return out


# ---- clarity, oxygen and hatches: the area's year from dated records ----
def clarity_season(res):
    """{ntu[24], n[24]}: the area's stream turbidity by half-month: each site's median in the half-month (NTU and the
    like; JTU, an old candle scale, left out), the median over the sites (MIN_SITES or more, else the neighbours')."""
    if res is None or "ResultMeasureValue" not in res:
        return dict(ntu=[None] * HALF, n=[0] * HALF)
    r = _wqp(res, units={"ntu", "fnu", "ntru", "ftu", "fnru", "fbu", "fbru"}, lo=0, hi=5000)
    if r.empty:
        return dict(ntu=[None] * HALF, n=[0] * HALF)
    sm = r.groupby(["MonitoringLocationIdentifier", "h"]).v.median().reset_index()
    by = sm.groupby("h").v
    n = by.size().reindex(range(HALF)).fillna(0).astype(int).tolist()
    ntu = _fill_smooth(by.median().reindex(range(HALF)).values, n, MIN_SITES, log=True)
    return dict(ntu=[None if v is None else round(float(v), 1) for v in ntu], n=n)


def do_sat(T, el):
    """Dissolved oxygen at saturation (mg/L) in fresh water at T C and el m: Benson and Krause's equation (APHA
    Standard Methods 4500-O) at 1 atm, times the air pressure at that height (barometric, scale height 8,434 m)."""
    K = T + 273.15
    ln = -139.34411 + 1.575701e5 / K - 6.642308e7 / K ** 2 + 1.2438e10 / K ** 3 - 8.621949e11 / K ** 4
    return math.exp(ln) * math.exp(-max(el, 0.0) / 8434.0)


def oxygen_season(do_res, temp_res, elev):
    """{sat[24], n[24]}: the area's typical oxygen saturation by half-month: each dissolved-oxygen reading (mg/L) over
    do_sat() at the water temperature read at the same sampling (ActivityIdentifier) and the site's elevation
    (elev: {MonitoringLocationIdentifier: m}); each site's median in the half-month, the median over the sites."""
    if do_res is None or "ResultMeasureValue" not in do_res or "ActivityIdentifier" not in temp_res:
        return dict(sat=[None] * HALF, n=[0] * HALF)
    d = _wqp(do_res, units={"mg/l"}, lo=0, hi=25)
    t = _wqp(temp_res, lo=-5, hi=100)
    if d.empty or t.empty:
        return dict(sat=[None] * HALF, n=[0] * HALF)
    t.loc[t["ResultMeasure/MeasureUnitCode"] == "deg F", "v"] = (t.v - 32) * 5 / 9
    t = t[t.v.between(0, 35)].groupby("ActivityIdentifier").v.median()
    d = d.assign(T=d.ActivityIdentifier.map(t), el=d.MonitoringLocationIdentifier.map(elev).fillna(0.0)).dropna(subset=["T"])
    if d.empty:
        return dict(sat=[None] * HALF, n=[0] * HALF)
    d["sat"] = [v / do_sat(T, e) for v, T, e in zip(d.v, d["T"], d.el)]
    d = d[d.sat.between(0.05, 2.0)]                                    # (a reading in % or a unit slip)
    sm = d.groupby(["MonitoringLocationIdentifier", "h"]).sat.median().reset_index()
    by = sm.groupby("h").sat
    n = by.size().reindex(range(HALF)).fillna(0).astype(int).tolist()
    sat = _fill_smooth(by.median().reindex(range(HALF)).values, n, MIN_SITES)
    return dict(sat=[None if v is None else round(float(v), 3) for v in sat], n=n)


def hatch_curve(aq, allobs, year=YEAR):
    """{rel[24], n[24]}: iNaturalist's records by week of the year (aq: mayflies and caddisflies, HATCH_TAXA; allobs: all
    verifiable records, the same box) put in half-months by each week's middle day; rel = the half-month's share of
    aquatic insects over the year's share, with 10 records' worth of the year's share added (a half-month with few
    records reads near the year's), then one pass of a 1-2-1 smoothing round the year."""
    h = [min(HALF - 1, (lambda d_: (d_.month - 1) * 2 + (d_.day > 15))(dt.date(year, 1, 1) + dt.timedelta(days=7 * w + 3)))
         for w in range(53)]
    A = np.bincount(h, [float(aq.get(str(w + 1), 0)) for w in range(53)], HALF)
    L = np.bincount(h, [float(allobs.get(str(w + 1), 0)) for w in range(53)], HALF)
    if A.sum() == 0 or L.sum() == 0:
        return dict(rel=[None] * HALF, n=[int(v) for v in A])
    rbar = A.sum() / L.sum()
    rel = (A + 10) / (rbar * L + 10)
    rel = (np.roll(rel, 1) + 2 * rel + np.roll(rel, -1)) / 4
    return dict(rel=[round(float(v), 3) for v in rel], n=[int(v) for v in A])


# ---- the horizon along each reach ----
def horizon_codes(z, transform, xs, ys, n_az=36, ray_m=3000, ray_step=30, res=10.0, eye=1.0):
    """For points (xs, ys, in the DEM's CRS; each reach's PTS points one after another, see 11b_calendar.py) the
    horizon's elevation angle (deg) in n_az bearings, as 10_sun.horizon() traces it."""
    inv = ~transform
    c, r = inv * (np.asarray(xs), np.asarray(ys))
    H, W = z.shape
    r0, c0 = np.clip(r.astype(int), 0, H - 1), np.clip(c.astype(int), 0, W - 1)
    z0 = z[r0, c0] + eye
    d = np.arange(ray_step, ray_m + 1, ray_step, dtype="float32")
    out = np.zeros((len(r0), n_az), "float32")
    for k, a in enumerate(np.radians(np.arange(0, 360, 360 / n_az))):
        rr = np.rint(r0[:, None] - np.cos(a) * d / res).astype(int)
        cc = np.rint(c0[:, None] + np.sin(a) * d / res).astype(int)
        ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        zz = np.where(ok, z[np.clip(rr, 0, H - 1), np.clip(cc, 0, W - 1)], np.nan)
        ang = np.arctan((zz - z0[:, None]) / d)
        out[:, k] = np.nan_to_num(np.nanmax(np.where(np.isnan(ang), -np.pi / 2, ang), axis=1), nan=0)
    return np.degrees(out)


def pack_horizon(hz):
    """A reach's horizon (its points x 36 bearings, deg) as len(AZ) characters: the mean over its points, at each bearing
    of AZ as 1/4, 1/2, 1/4 of the bearings 10 deg to either side and itself, whole degrees 0..63."""
    m = hz.mean(axis=0)
    out = []
    for a in AZ:
        i = a // 10
        v = 0.25 * m[(i - 1) % 36] + 0.5 * m[i % 36] + 0.25 * m[(i + 1) % 36]
        out.append(CHARS[int(min(max(round(v), 0), 63))])
    return "".join(out)


def pack(horizon, tz, tz0):
    """A reach's cz: its horizon's characters, then its time zone's offset (CHARS[offset + 12]) where it isn't the
    map's (tz0)."""
    return horizon + ("" if tz == tz0 else CHARS[tz + 12])


# ---- the sum, as map_calendar.js works it out ----
def _lin(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def _dst(d):
    """US daylight saving time on day d: from the 2nd Sunday in March to the 1st Sunday in November."""
    a = dt.date(d.year, 3, 1)
    a += dt.timedelta(days=(6 - a.weekday()) % 7 + 7)
    b = dt.date(d.year, 11, 1)
    b += dt.timedelta(days=(6 - b.weekday()) % 7)
    return a <= d < b


_PATHS = {}


def sun_path(h, lat, year=YEAR):
    """The sun on half-month h's middle day at latitude lat, rounded to 0.1 deg (so a map's reaches share a few paths):
    (steps above the horizon as (minute of solar time, altitude, azimuth), the number of them, the equation of time
    in minutes, daylight saving time). NOAA's solar position formulas (the fractional year's Fourier series)."""
    la = math.floor(lat * 10 + 0.5) / 10
    key = (h, la, year)
    if key in _PATHS:
        return _PATHS[key]
    d = mid_date(h, year)
    n = d.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                    - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
           + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    phi = math.radians(la)
    steps = []
    for i in range(0, 24 * 60, STEP_MIN):
        t = i / 60 + STEP_MIN / 120                # the middle of the step, solar time
        ha = math.radians((t - 12) * 15)
        alt = math.degrees(math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(ha)))
        if alt <= 0:
            continue
        az = (math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(phi) - math.tan(dec) * math.cos(phi))) + 180) % 360
        steps.append((i + STEP_MIN / 2, alt, az))
    _PATHS[key] = (steps, len(steps), eot, _dst(d))
    return _PATHS[key]


def sun_day(h, lat, lon, hz, tz, dst=True, year=YEAR):
    """(hours of direct sun on the water, first and last minute of it in local clock time or None, day length in
    hours) on half-month h's middle day; hz = the horizon at AZ (deg), tz the standard UTC offset."""
    steps, up, eot, dst_ = sun_path(h, lat, year)
    pts = list(zip(AZ, hz))
    lit, first, last = 0, None, None
    for m, alt, az in steps:
        hzv = hz[0] if az <= AZ[0] else hz[-1] if az >= AZ[-1] else _lin(pts, az)
        if alt > hzv:
            lit += 1
            first = m if first is None else first
            last = m
    to_clock = lambda m: None if m is None else m - eot - 4 * (lon - 15 * tz) + (60 if dst and dst_ else 0)
    return lit * STEP_MIN / 60, to_clock(first), to_clock(last), up * STEP_MIN / 60


def prep(p, tab):
    """What calendar() reads off a reach (p as the page has it: fx, a, el, x, y, cz) and the area's tables; None for a
    reach the calendar can't be worked out for (no horizon, no fx, or neither a water temperature nor a tailwater)."""
    n = len(tab["az"])
    cz = p.get("cz")
    if not isinstance(cz, str) or len(cz) < n:
        return None
    t = (p.get("fx") or "").split(" ")
    if len(t) < 8:
        return None
    num = lambda v: None if v in (None, "", "-") else float(v)
    flags = t[8:]
    W, wt, cp, tw = num(t[0]), num(t[2]), num(t[3]), "w" in flags
    if wt is None and not tw:
        return None
    tz = CHARS.index(cz[n]) - 12 if len(cz) > n else tab["tz"]
    la = math.log10(max(p["a"], 0.01))
    wsum, acc, isum, iacc = 0.0, [0.0] * HALF, 0.0, [0.0] * HALF
    for g in tab["gauges"]:
        dkm = 111.2 * math.hypot(p["y"] - g[1], (p["x"] - g[2]) * math.cos(math.radians(p["y"])))
        w = math.exp(-0.5 * ((la - g[0]) / tab["sig"][0]) ** 2 - 0.5 * (dkm / tab["sig"][1]) ** 2)
        wsum += w
        for h in range(HALF):
            acc[h] += w * math.log10(g[3][h])
        if g[5] is not None:
            isum += w
            for h in range(HALF):
                iacc[h] += w * g[5][h]
    return dict(W=W, wt=wt, cp=cp, tw=tw, brook="b" in flags, canopy=min(max((cp or 0.0) / 100, 0.0), 1.0),
                hz=[CHARS.index(ch) for ch in cz[:n]], tz=tz, el=p.get("el") or 0.0,
                lr=[a / wsum if wsum > 0 else 0.0 for a in acc], ice=[a / isum if isum > 0 else 0.0 for a in iacc])


def half(P, p, tab, h):
    """One half-month of a reach (P = prep(p, tab)): its score 0..100 and its parts."""
    ws = tab["water"]
    base = ws["S"] if P["wt"] is None else P["wt"]
    T = max(0.5, ws["S"] + ws["d"][h] + ws["k"][h] * (base - ws["S"]))
    if P["tw"]:
        T = min(max(T, tab["tail"][0]), tab["tail"][1])
    sT = _lin(tab["thermal"]["brook" if P["brook"] else "trout"], T)
    lr = P["lr"][h]
    yr = P["W"] is not None and P["W"] >= tab["year_round"]
    # a tailwater's flow is the dam's releases, not the area's natural year; a creek that flows every summer by its
    # own evidence (the fish score's water term) takes no low-water mark from the gauges' smaller, drier creeks
    sQ = 1.0 if P["tw"] or (lr < 0 and yr) else _lin(tab["flow"], lr)
    dry = min(1.0, P["W"] / tab["year_round"]) if (P["W"] is not None and tab["dry"][0] <= h < tab["dry"][1]) else 1.0
    sun, first, last, day = sun_day(h, p["y"], p["x"], P["hz"], P["tz"], tab["dst"])
    e = (sun / day if day > 0 else 0.0) * (1 - 0.8 * P["canopy"])
    warm, cold = 1 - 0.30 * e, 0.85 + 0.15 * e
    f = min(max((T - tab["light"][1]) / (tab["light"][0] - tab["light"][1]), 0.0), 1.0)
    sL = cold + (warm - cold) * f
    ice = P["ice"][h]
    sI = 1 - tab["ice_k"] * ice
    ntu = tab["clarity"]["ntu"][h]
    sC = 1.0 if ntu is None else _lin(tab["clar"], ntu)
    sat = tab["oxygen"]["sat"][h]
    do = None if sat is None else do_sat(T, P["el"]) * sat
    sO = 1.0 if do is None else _lin(tab["oxy"], do)
    rel = tab["hatch"]["rel"][h]
    sB = 1.0 if rel is None else tab["hatch_lo"] + (1 - tab["hatch_lo"]) * min(max(rel, 0.0), 1.0)
    x = 100 * sT * sQ * dry * sL * sI * sC * sO * sB
    return dict(h=h, T=T, sT=sT, ratio=10 ** lr, sQ=sQ, dry=dry, yr=yr, sun=sun, first=first, last=last, day=day, e=e, sL=sL,
                ice=ice, sI=sI, ntu=ntu, sC=sC, do=do, sO=sO, rel=rel, sB=sB, score=int(math.floor(x + 0.5)))


def calendar(p, tab):
    """The 24 half-months of one reach (p as the page has it), tab = LBL["cal"]; None where prep() gives none."""
    P = prep(p, tab)
    return None if P is None else [half(P, p, tab, h) for h in range(HALF)]


def table(water, gauges, ice, clarity, oxygen, hatch, tz, dst):
    """LBL["cal"]: the area's tables, as map_calendar.js reads them. gauges: flow_shapes()'s, each with its ice
    shares (ice_shapes(), by site) appended."""
    return dict(water=water, gauges=[g + [ice.get(g[4])] for g in gauges], clarity=clarity, oxygen=oxygen, hatch=hatch,
                tz=tz, dst=dst, thermal=THERMAL, flow=FLOW, dry=[DRY.start, DRY.stop], year_round=YEAR_ROUND,
                tail=list(TAILWATER_C), sig=[FLOW_SIG_LOG, FLOW_SIG_KM], light=[WARM_C, COLD_C], ice_k=ICE_K,
                clar=CLARITY, oxy=OXY, hatch_lo=HATCH_LO, az=AZ, year=YEAR, step=STEP_MIN)


# ---- the map step (06_map.py) ----
def page_props(sids, regions, map_out):
    """(cz for each drawn reach, the area's tables for LBL["cal"]) from 11b_calendar.py's files; a piece 06_map.py adds
    for drawing ("<sid>+<n>") takes its reach's. (Nones, None) where 11b_calendar.py hasn't run."""
    p = f"{map_out}/calendar.json"
    if not os.path.exists(p):
        return [None] * len(sids), None
    cz = {}
    for r in regions:
        f = f"{map_out}/{r}/calendar_streams.csv"
        if os.path.exists(f):
            t = pd.read_csv(f, dtype=str, keep_default_na=False)
            cz.update(zip(t.sid, t.cz))
    return [cz.get(str(s).split("+")[0]) for s in sids], json.load(open(p))


def add_to_pages(map_out):
    """map_calendar.js at the end of both map pages (stream_map.html, stream_map_3d.html), after map_score.js, whose
    fish score line in the stream popups it adds the calendar to."""
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_calendar.js")).read()
    assert "</script" not in js.lower(), "map_calendar.js must not close its <script>"
    for f in ("stream_map.html", "stream_map_3d.html"):
        path = f"{map_out}/{f}"
        if not os.path.exists(path):
            continue
        h = open(path).read()
        i = h.rfind("</body>")
        assert i > 0, f"{f}: no </body>"
        with open(path, "w") as out:
            out.write(h[:i] + "<script>" + js + "</script>\n" + h[i:])
