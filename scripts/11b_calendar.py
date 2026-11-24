"""The trout calendar's inputs for this area (troutcal.py says what the calendar is): after 10_sun.py, 11_context.py
and watertemp.py, before 06_map.py.

  output/<area>/calendar.json               the area's tables, which the map pages read (06_map.py: LBL["cal"]):
                                            the water temperature's year (the Water Quality Portal readings watertemp.py
                                            cached), each USGS gauge's year of flow (02b's daily records) and of ice, the
                                            area's year of turbidity, oxygen saturation and hatches, and the limits
  output/<area>/<range>/calendar_streams.csv  per reach: cz (the horizon at troutcal.AZ, one character a bearing, then
                                            the time zone where it isn't the area's), st (its state), for the checks
Downloads (netfetch.py: time limits, the last good copy when one fails), each kept 30 days:
  - the Water Quality Portal's stream turbidity and dissolved oxygen readings, and the oxygen sites, box by box
    (_shared/cache/wqp_{result,station}_{turbidity,oxygen}_<range>.csv, beside watertemp.py's temperature files)
  - the USGS Water Data API's daily discharge flags (estimated, ice) since 2000-10-01 at 02b's gauges
    (_shared/calendar/flags_<site>.csv), several gauges to a request
  - iNaturalist's verifiable records by week of the year in the area's boxes, all and mayflies and caddisflies
    (netcache: calendar-inat-*)
  AREA=ne_ct ../.venv/bin/python 11b_calendar.py
"""
import os, json, time, numpy as np, pandas as pd, geopandas as gpd, rasterio
from shapely.geometry import box
from config import REGIONS, CRS, SHARED, MAP_OUT, NATIONAL, raw_dir, out_dir
import netfetch
import troutcal as tc

PTS = 4                                          # points per reach, as 10_sun.py
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
CACHE, CAL = f"{SHARED}/cache", f"{SHARED}/calendar"
os.makedirs(CAL, exist_ok=True)
DAYS30 = 30 * 86400
fresh = lambda p: os.path.exists(p) and time.time() - os.path.getmtime(p) < DAYS30 and os.environ.get("REFRESH") != "1"
area = gpd.GeoSeries([box(*v["bbox"]).buffer(3000) for v in REGIONS.values()], crs=CRS)
W_, S_, E_, N_ = area.to_crs(4326).total_bounds


def wqp(kind, char, tag):
    """The Water Quality Portal's stream rows for one characteristic, one request for each of the area's boxes (as
    watertemp.py fetches its temperatures, but box by box: the whole of LA in one request for turbidity was cut off by
    the server twice, 2026-11-24), each kept 30 days; rows two boxes share once."""
    out = []
    for r, v in REGIONS.items():
        W, S, E, N = gpd.GeoSeries([box(*v["bbox"]).buffer(3000)], crs=CRS).to_crs(4326).total_bounds
        p = f"{CACHE}/wqp_{kind.lower()}_{tag}_{r}.csv"
        if not fresh(p):
            def refresh(p=p, W=W, S=S, E=E, N=N):
                q = netfetch.fetch("GET", f"https://www.waterqualitydata.us/data/{kind}/search", tries=3, timeout=900,
                                   params=dict(bBox=f"{W:.3f},{S:.3f},{E:.3f},{N:.3f}", characteristicName=char,
                                               siteType="Stream", startDateLo="01-01-1995", mimeType="csv",
                                               **({"dataProfile": "narrowResult"} if kind == "Result" else {})), headers=UA)
                open(p + ".tmp", "wb").write(q.content)
                os.replace(p + ".tmp", p)
            try:
                netfetch.keep_old(p, refresh, f"Water Quality Portal ({char}, {r})")
            except Exception as e:     # noqa: BLE001 (no answer and no earlier copy: this box goes without)
                print(f"NOTE: Water Quality Portal ({char}, {r}) not fetched and no earlier copy ({e}); left out")
                continue
        try:
            out.append(pd.read_csv(p, low_memory=False))
        except pd.errors.EmptyDataError:
            pass
    if not out:
        return pd.DataFrame()
    t = pd.concat(out, ignore_index=True)
    key = "ResultIdentifier" if "ResultIdentifier" in t else "MonitoringLocationIdentifier" if "MonitoringLocationIdentifier" in t else None
    return t.drop_duplicates(key) if key else t


# ---- the area's tables ----
st = pd.read_csv(f"{CACHE}/wqp_station_temp.csv", low_memory=False).set_index("MonitoringLocationIdentifier")
st = st[~st.index.duplicated()]
temp = pd.read_csv(f"{CACHE}/wqp_result_temp.csv", low_memory=False)
water = tc.water_season(temp, st)
print(f"water temperature's year from {max(water['n'])} sites at most a half-month (fewest {min(water['n'])}); "
      f"Jul-Aug mean {water['S']:.1f} C; Jan 1-15 a site at that mean reads {water['S'] + water['d'][0]:.1f} C, "
      f"May 1-15 {water['S'] + water['d'][8]:.1f} C, Oct 1-15 {water['S'] + water['d'][18]:.1f} C")
flow = f"{SHARED}/flow"
daily = pd.read_csv(f"{flow}/gauges_daily.csv.gz", dtype={"site_no": str})
sites = gpd.read_file(f"{flow}/gauge_sites.gpkg").to_crs(4326)
gauges = tc.flow_shapes(daily, sites)
print(f"flow's year from {len(gauges)} of {len(sites)} gauges")

# ice: the gauges' daily flags (02b keeps the values only), several gauges to a request, as 02b fetches the values,
# with the USGS key when there is one (USGS_API_KEY, or the private file ~/.config/usgs/api_key; netfetch.usgs_key)
WD = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items"


def flag_pages(ids):
    params = dict(f="json", monitoring_location_id=",".join(f"USGS-{s}" for s in ids), parameter_code="00060",
                  statistic_id="00003", time=f"{tc.ICE_FROM}/{pd.Timestamp.now():%Y-%m-%d}", properties="monitoring_location_id,time,qualifier,time_series_id",
                  skipGeometry="true", limit=50000)
    js, feats = netfetch.fetch("GET", WD, headers={**UA, **netfetch.usgs_key(WD)}, timeout=300,
                               params=params).json(), []
    while True:
        feats += js["features"]
        nxt = next((l["href"] for l in js.get("links", []) if l.get("rel") == "next"), None)
        if nxt is None or not js["features"]:
            return pd.DataFrame([f["properties"] for f in feats],
                                columns=["monitoring_location_id", "time", "qualifier", "time_series_id"])
        js = netfetch.fetch("GET", nxt, headers={**UA, **netfetch.usgs_key(nxt)}, timeout=300).json()


need = [g[4] for g in gauges if not fresh(f"{CAL}/flags_{g[4]}.csv")]
n_days = (pd.Timestamp.now() - pd.Timestamp(tc.ICE_FROM)).days + 1
per = max(1, 49000 // n_days)
for i in range(0, len(need), per):
    b = need[i:i + per]

    def get(b=b):          # (written only when the whole batch came: a failed one keeps the earlier flags)
        t = flag_pages(b)
        for s in b:
            u = t[t.monitoring_location_id == f"USGS-{s}"]
            if len(u):                                 # a gauge with two series: the one with more days, as 02b keeps
                u = u[u.time_series_id == u.time_series_id.value_counts().idxmax()]
            q = u.qualifier.astype(str)
            pd.DataFrame({"date": u.time.str[:10], "est": q.str.contains("ESTIMATED|ICE").astype(int)}).sort_values(
                "date").to_csv(f"{CAL}/flags_{s}.csv.tmp", index=False)
            os.replace(f"{CAL}/flags_{s}.csv.tmp", f"{CAL}/flags_{s}.csv")
    try:
        netfetch.keep_old([f"{CAL}/flags_{s}.csv" for s in b], get, "USGS daily discharge flags")
    except Exception as e:             # noqa: BLE001 (no answer and no earlier flags: these gauges read no ice)
        print(f"NOTE: USGS flags of {', '.join(b)} not fetched and no earlier copy ({e}): no ice from them")
est = {g[4]: (pd.read_csv(f"{CAL}/flags_{g[4]}.csv") if os.path.exists(f"{CAL}/flags_{g[4]}.csv") else None)
       for g in gauges}
ice = tc.ice_shapes(est, water)
iced = [s for s, v in ice.items() if v is not None and max(v) > 0]
print(f"ice from {sum(v is not None for v in ice.values())} gauges' flags; {len(iced)} with ice-affected days"
      + (f", most in a half-month {max(max(ice[s]) for s in iced):.0%}" if iced else ""))

clarity = tc.clarity_season(wqp("Result", "Turbidity", "turbidity"))
print(f"clarity: turbidity at {max(clarity['n'])} sites at most a half-month; typical NTU by half-month "
      f"{clarity['ntu']}")
do_res, do_st = wqp("Result", "Dissolved oxygen (DO)", "oxygen"), wqp("Station", "Dissolved oxygen (DO)", "oxygen")
elev = {}
if len(do_st):
    import watertemp
    pts = gpd.GeoDataFrame(do_st[["MonitoringLocationIdentifier"]], crs=4326, geometry=gpd.points_from_xy(
        pd.to_numeric(do_st.LongitudeMeasure, errors="coerce"), pd.to_numeric(do_st.LatitudeMeasure, errors="coerce"))).to_crs(CRS)
    elev = dict(zip(pts.MonitoringLocationIdentifier, watertemp.elev_at(pts)))
    elev = {k: v for k, v in elev.items() if np.isfinite(v)}
oxygen = tc.oxygen_season(do_res, temp, elev)
print(f"oxygen: saturation at {max(oxygen['n'])} sites at most a half-month; by half-month {oxygen['sat']}")


def inat(taxa):
    def get():
        p = dict(swlat=S_ - tc.HATCH_PAD, swlng=W_ - tc.HATCH_PAD, nelat=N_ + tc.HATCH_PAD, nelng=E_ + tc.HATCH_PAD,
                 interval="week_of_year", verifiable="true", **({"taxon_id": taxa} if taxa else {}))
        r = netfetch.fetch("GET", "https://api.inaturalist.org/v1/observations/histogram", headers=UA, timeout=120, params=p)
        return r.json()["results"]["week_of_year"]
    name = f"calendar-inat-{netfetch.key(taxa or 'all', round(W_, 2), round(S_, 2), round(E_, 2), round(N_, 2))}"
    return netfetch.last_good(name, get, "iNaturalist records by week")


try:
    hatch = tc.hatch_curve(inat(tc.HATCH_TAXA), inat(None))
except Exception as e:                 # noqa: BLE001 (no answer and no earlier copy: the part reads neutral)
    print(f"NOTE: iNaturalist not fetched and no earlier copy ({e}); the calendar goes without hatches")
    hatch = dict(rel=[None] * tc.HALF, n=[0] * tc.HALF)
print(f"hatches: {sum(hatch['n']):,} mayfly and caddisfly records; relative to the year's share by half-month {hatch['rel']}")

# ---- per reach: the horizon, the state and its time zone ----
states = gpd.read_file(f"zip://{NATIONAL}/tl_2024_us_state.zip", columns=["STUSPS"]).to_crs(4326)
rows = {}
for r in REGIONS:
    if not os.path.exists(f"{out_dir(r)}/streams_scored.gpkg"):
        continue
    s = gpd.read_file(f"{out_dir(r)}/streams_scored.gpkg", columns=["sid"]).to_crs(CRS)
    fr = (np.arange(PTS) + 0.5) / PTS
    pts = [g.interpolate(f, normalized=True) for g in s.geometry for f in fr]
    with rasterio.open(f"{raw_dir(r)}/dem_10m.tif") as src:
        z = src.read(1).astype("float32")
        z[z < -1000] = np.nan
        T = src.transform
    step = 4000 * PTS
    hz = np.vstack([tc.horizon_codes(z, T, [p.x for p in pts[i:i + step]], [p.y for p in pts[i:i + step]])
                    for i in range(0, len(pts), step)])
    del z
    mid = gpd.GeoSeries(s.geometry.interpolate(0.5, normalized=True), crs=CRS).to_crs(4326)
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=mid.values, crs=4326), states, how="left", predicate="within")
    stv = j.groupby(level=0).STUSPS.first().reindex(range(len(s))).fillna("").values
    rows[r] = pd.DataFrame({"sid": s.sid, "hz": [tc.pack_horizon(hz[i * PTS:(i + 1) * PTS]) for i in range(len(s))],
                            "st": stv, "tz": [tc.tz_of(a, p.x, p.y) for a, p in zip(stv, mid)]})

allr = pd.concat(rows.values(), ignore_index=True)
tz0, dst0 = allr.tz.mode().iloc[0]
for r, t in rows.items():
    t.assign(cz=[tc.pack(h, z[0], tz0) for h, z in zip(t.hz, t.tz)])[["sid", "cz", "st"]].to_csv(
        f"{out_dir(r)}/calendar_streams.csv", index=False)
    print(f"{r}: {len(t)} reaches | states {t.st.value_counts().to_dict()} | horizon due south median "
          f"{np.median([tc.CHARS.index(c[6]) for c in t.hz]):.0f} deg")
other = allr.tz.map(lambda z: z[0] != tz0).sum()
print(f"time zone UTC{tz0:+d}{' with daylight saving time' if dst0 else ''}" + (f"; {other} reaches in another" if other else ""))

json.dump(tc.table(water, gauges, ice, clarity, oxygen, hatch, int(tz0), bool(dst0)), open(f"{MAP_OUT}/calendar.json", "w"),
          separators=(",", ":"))
print(f"calendar.json: {os.path.getsize(f'{MAP_OUT}/calendar.json'):,} bytes")
