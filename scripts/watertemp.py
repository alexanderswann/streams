"""Estimated typical summer water temperature of each reach, for the thermal term of the fish score (scoring.py).

Target, the same in every area: the July-August daytime water temperature at a site, as the median of the readings in
the Water Quality Portal (USGS, state agencies, tribes, the Forest Service; 07:00-18:00, since 2000 or the cache's
start). A trout's limits are water temperatures, so the score's cutoffs (scoring.WATER_FULL / WATER_ZERO) carry from
one area to the next; an elevation band or an air-temperature cutoff doesn't, because how far a creek runs below its
air depends on the climate and the geology.

Estimate, per area: a least-squares fit of the measured sites on the best of a few predictor sets (SETS), chosen by
leave-one-out error among the sets whose coefficients have the physical sign:
  air       PRISM August mean air temperature (1991-2020 normal, 800 m)
  elev_km   elevation
  log_area  drainage area (NHDPlus V2): in the East a small brook stays near groundwater temperature and a river
            warms in the sun and the mill ponds, whatever the air does
  lake      the share of the creek's drainage that reaches it through a lake (05c_drainages.py: the water carried
            past dams and ponds over the reach's full drainage), where the lake lies within LAKE_NEAR_M up the
            channel (lake_term(); a measured site takes the reach it sits on, lake_at()), counted in full on creeks
            up to LAKE_FULL_KM2 and fading to nothing at LAKE_NONE_KM2 (lake_share()). A lake's outlet runs at the
            temperature of its surface: in the Adirondacks, where most creeks leave a pond, the creek just below
            one runs about 7 C warmer than one with none, and without this term three of the four Adirondack maps
            had no fit with skill (2026-11-21).
            Why only just below the lake (2026-11-22): the warmth is measured at the outlets and fades fast. The
            mostly-lake-water sites of the three maps that use the term read 74.9 F within 650 ft of the lake (19
            sites, 16 of them 73 F or more, none 68 F or less), 68.4 F from there to 0.6 mi (8 sites), 65.5 F from
            0.6 to 1.9 mi (7), 66.3 F further down (11), against 63.0 F at the 231 sites with under half lake
            water. The first version (the plain share, however far down) read every lake-fed reach as warm as an
            outlet: 3.0 F too cool at the outlets, 1.4 to 5.0 F too warm below, and it took 10+ points from 444
            reaches (173 mi), 401 of them recorded trout water, on evidence that holds for the outlets only (the
            audit's test of the published maps). Past LAKE_NEAR_M a reach now reads as a creek with no lake: 3 to
            6 F too cool at those 26 sites, on the side that costs no creek its credit (the score marks water down
            only where it is near-certain). A reach takes the term for the part of its length within LAKE_NEAR_M.
            How far below a lake a reach lies comes from the reaches themselves (below_lake()): up the reaches that
            bring the lake water to the reach lying in the lake, or to where the lake's water is put in beside its
            outline.
            Why it fades on rivers: a pond spills warm surface water, but a big dam may release cold water from the
            depths (a tailwater), and on a big river nearly all the water has been through some lake far upstream,
            so the share says less. The measured sites on lake-fed rivers of 200+ km2 are mixed. With the plain
            share the Adirondack ones read 0.7 C below the fit on average (11 sites: the Sacandaga below Great
            Sacandaga Lake's dam 2.9 C below, the Black River below Kayuta Lake 1.0 and 2.7 C below, Lake George's
            outlet 0.9 C above), Jackson's 1.4 C below (11 sites, the Snake below its dams among them). A river
            below a dam isn't marked down for warmth on that (the score marks water down only where it is
            near-certain; a cold tailwater is the standing example). The cost: with the fade those 12 sites read 2.2 C above the
            estimate on average, and warm lake-outlet rivers keep the credit they had (leave-one-out error 3.13 C
            against 3.04 C with the plain share).
            The term enters a fit only where LAKE_MIN_SITES measured sites have a term of 0.5 or more (mostly lake
            water, just below the lake): the High Peaks map has 6, the south-west map 15, the four Adirondack maps
            together 28. Jackson has 9 and no fit there is better for the term (its dams release cold water); the
            other areas have none or one. So every other area's fit stays as it was
In the LA ranges air + elevation wins (the mountains span 2,000 m); in northeastern Connecticut, where the air only
spans 2 C, it is drainage area.
Sites are weighted by how well their median is known (since 2026-11-20): a site's median of n readings misses its
typical temperature by about sigma_w^2 / n (sigma_w: the spread of single readings around their site's median, robust,
over sites with 3+ readings, 1.3-3.9 C by area), and the predictors miss even a well-measured site by tau^2 (the first,
unweighted fit's residual variance less the mean of those sampling variances). Weight 1 / (tau^2 + sigma_w^2 / n): a
single grab sample counts for less than a logger's summer of readings. The skill test and the area mean are weighted the
same way. It gave Jackson's fit its skill (leave-one-out 0.887 of the spread, 0.906 unweighted). A fit that can't beat "every creek is the average" by 10 % is not used
for single reaches (SKILL); every creek then takes that average, the measured sites' mean (area_mean(), used by
scoring.py), so a cold area stays cold rather than unknown. (Jackson since its 2026-11-19 expansion: 145 sites, mean
13.4 C, the fit 3.37 C off against a 3.72 C spread.)
An area whose own sites give no fit with skill may take its region's: config.py's water_temp_group names areas that are
one region cut into several maps (the four Adirondack maps). Each map's run writes its measured sites to
<area>/_shared/water_temp_sites.csv; a map with no fit of its own fits the sites of all the group's maps and uses
that fit if it misses the map's own sites by no more than SKILL x their own spread (_group_fit). Each map's own fit
comes first: one fit for all four Adirondack maps missed the south-east map's sites by 3.10 C, more than their own
spread (2.99 C) and than that map's own fit (2.50 C). On 2026-11-21 three of the four have a fit of their own, and
the north-west map (no skill on its 63 sites) takes the region's.
Left out of a fit: sites with a median above GEOTHERMAL_C (hot-spring creeks: Warm Creek in San Bernardino reads
32-37 C), and sites far off the first fit (OUTLIER_MADS; e.g. two Connecticut logger records reading 9-10 C in
midsummer on lowland rivers).

  ../.venv/bin/python watertemp.py        fit this AREA, print the check, write <area>/_shared/water_temp_fit.json
  watertemp.estimate(air, elev, area)     the fitted estimate (NaN where an input is missing or the fit has no skill)
The Water Quality Portal downloads are cached for 30 days in <area>/_shared/cache (the same files
data/validate_heat.py uses).
"""
import os, json, time, datetime as dt, requests, rasterio, numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
from config import REGIONS, CRS, SHARED, NATIONAL, AREA, AREAS, A, RAW_ROOT, raw_dir, out_dir

FIT = f"{SHARED}/water_temp_fit.json"
SITES = f"{SHARED}/water_temp_sites.csv"     # this area's measured sites, for the fits of the maps it shares one with
GROUP = [a for a in AREAS if A.get("water_temp_group") and AREAS[a].get("water_temp_group") == A["water_temp_group"]] or [AREA]
CACHE = f"{SHARED}/cache"
GEOTHERMAL_C = 30.0     # site medians above this are hot springs, not climate
MIN_SITES = 25          # fewer measured sites than this: no fit (the score falls back to the air temperature alone)


def _cached(name, fetch):
    """A download kept 30 days; when it can't be refreshed, the earlier one stays (netfetch.py: a dated NOTE)."""
    import netfetch
    os.makedirs(CACHE, exist_ok=True)
    p = f"{CACHE}/{name}"
    if not (os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400):
        def refresh():
            fetch(p + ".tmp")
            os.replace(p + ".tmp", p)
        netfetch.keep_old(p, refresh, f"Water Quality Portal ({name})")
    return p


def _wqp(kind, bounds):
    W, S, E, N = bounds
    def fetch(p):
        import netfetch
        r = netfetch.fetch("GET", f"https://www.waterqualitydata.us/data/{kind}/search", tries=2, timeout=900, params=dict(
            bBox=f"{W:.3f},{S:.3f},{E:.3f},{N:.3f}", characteristicName="Temperature, water", siteType="Stream",
            startDateLo="01-01-1995", mimeType="csv", **({"dataProfile": "narrowResult"} if kind == "Result" else {})),
            headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
        open(p, "wb").write(r.content)
    return pd.read_csv(_cached(f"wqp_{kind.lower()}_temp.csv", fetch), low_memory=False)


PRISM = "ftp://prism.oregonstate.edu/normals/us/800m/tmean/monthly/prism_tmean_us_30s_202008_avg_30y"
def air_tif():
    """The PRISM August mean air temperature normal (1991-2020, 800 m) clipped to this area's ranges, in
    <area>/_shared. The national file (~58 MB, kept in _national for the other areas) is downloaded when missing;
    the clip is redone when ranges are added."""
    import urllib.request
    from rasterio.windows import from_bounds
    W, S, E, N = gpd.GeoSeries([box(*v["bbox"]).buffer(3000) for v in REGIONS.values()], crs=CRS).to_crs(4326).total_bounds
    p_ = f"{SHARED}/prism_tmean_aug.tif"
    if os.path.exists(p_):
        with rasterio.open(p_) as src:
            b = src.bounds
        if b.left <= W and b.bottom <= S and b.right >= E and b.top >= N:
            return p_
    z = f"{NATIONAL}/prism_tmean_aug_us.zip"       # GDAL's /vsizip/ wants the .zip extension
    if not os.path.exists(z):
        import netfetch
        netfetch.urlretrieve(PRISM + ".zip", z + ".part")
        os.replace(z + ".part", z)
    with rasterio.open(f"/vsizip/{z}/{os.path.basename(PRISM)}.tif") as src:
        win = from_bounds(W - 0.05, S - 0.05, E + 0.05, N + 0.05, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win)
        prof = dict(driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=a.dtype, crs=src.crs,
                    transform=src.window_transform(win), nodata=src.nodata, compress="deflate")
    with rasterio.open(p_ + ".tmp", "w", **prof) as dst:
        dst.write(a, 1)
    os.replace(p_ + ".tmp", p_)
    return p_


def air_at(pts):
    """PRISM August mean air temperature at points (any CRS)."""
    with rasterio.open(air_tif()) as src:
        ll = pts.to_crs(src.crs)
        v = np.array([x[0] for x in src.sample(zip(ll.geometry.x, ll.geometry.y))], float)
    return np.where(v < -100, np.nan, v)


def elev_at(pts):
    """10 m DEM elevation at points in the area's CRS, from whichever range's DEM covers each."""
    z = np.full(len(pts), np.nan)
    x, y = pts.geometry.x.values, pts.geometry.y.values
    for r in REGIONS:
        p = f"{raw_dir(r)}/dem_10m.tif"
        if not os.path.exists(p):
            continue
        with rasterio.open(p) as src:
            b = src.bounds
            m = np.isnan(z) & (x >= b.left) & (x < b.right) & (y > b.bottom) & (y <= b.top)
            if m.any():
                v = np.array([s[0] for s in src.sample(zip(x[m], y[m]))], float)
                z[m] = np.where(v < -100, np.nan, v)
    return z


def measured_sites():
    """Stream sites in the area with July-August daytime water temperature readings: median `w`, count `n`, PRISM
    August air `air`, DEM elevation `elev`. Co-located station ids (same 3-decimal lat/lon) are one site."""
    area = gpd.GeoSeries([box(*v["bbox"]).buffer(3000) for v in REGIONS.values()], crs=CRS)
    bounds = area.to_crs(4326).total_bounds
    res, st = _wqp("Result", bounds), _wqp("Station", bounds).set_index("MonitoringLocationIdentifier")
    res["v"] = pd.to_numeric(res.ResultMeasureValue, errors="coerce")
    res.loc[res["ResultMeasure/MeasureUnitCode"] == "deg F", "v"] = (res.v - 32) * 5 / 9
    res["date"] = pd.to_datetime(res.ActivityStartDate, errors="coerce")
    res["hour"] = pd.to_numeric(res["ActivityStartTime/Time"].astype(str).str[:2], errors="coerce")
    res = res[res.v.between(0, 40)].join(st[["MonitoringLocationName", "LatitudeMeasure", "LongitudeMeasure"]],
                                         on="MonitoringLocationIdentifier")
    res["key"] = res.LatitudeMeasure.round(3).astype(str) + "," + res.LongitudeMeasure.round(3).astype(str)
    summer = res[res.date.dt.month.isin([7, 8]) & (res.hour.between(7, 18) | res.hour.isna())]
    site = summer.groupby("key").agg(w=("v", "median"), n=("v", "size"), name=("MonitoringLocationName", "first"),
                                     lat=("LatitudeMeasure", "first"), lon=("LongitudeMeasure", "first"))
    pts = gpd.GeoDataFrame(site, geometry=gpd.points_from_xy(site.lon, site.lat), crs=4326).to_crs(CRS)
    pts = pts[pts.intersects(area.union_all())].copy()
    pts["air"], pts["elev"] = air_at(pts), elev_at(pts)
    # the spread of single readings around their site's median (robust, sites with 3+ readings): fit()'s weights
    global SIGMA_W2
    dev = summer.v - summer.groupby("key").v.transform("median")
    many = summer.groupby("key").v.transform("size") >= 3
    SIGMA_W2 = float((1.4826 * np.median(np.abs(dev[many]))) ** 2) if many.any() else float("nan")
    return pts


SIGMA_W2 = float("nan")


# predictors a fit may use, with the sign physics allows: warmer air -> warmer water, higher -> cooler,
# a bigger stream -> warmer (small brooks stay near groundwater temperature; rivers take the sun and the ponds)
# and one fed through a lake -> warmer (a lake's outlet runs at its surface temperature)
TERMS = {"air": +1, "elev_km": -1, "log_area": +1, "lake": +1}
LAKE_FULL_KM2, LAKE_NONE_KM2 = 50.0, 500.0   # the lake term: a creek up to this size takes its lake share in full, a
                                             # river from this size on none of it (between: by log drainage)
LAKE_MIN_SITES = 5      # the lake term needs this many measured sites with a lake term of 0.5 or more (10 until the
                        # term counted only just below a lake: sites at lake outlets are fewer than lake-fed sites)
# how far below a lake the term counts (LAKE_NEAR_M, 200 m: 650 ft), and how that distance is found (below_lake()):
# in flowlib.py, since 05_score.py cuts each creek there too, so the first stretch below a lake is a reach of its own
from flowlib import below_lake, lake_water_km2, LAKE_NEAR_M, LAKE_JOIN_M, LAKE_AT_M
_BASE = [("air", "elev_km"), ("air",), ("elev_km",), ("log_area",), ("air", "log_area"), ("elev_km", "log_area"),
         ("air", "elev_km", "log_area")]
SETS = _BASE + [("lake",)] + [s + ("lake",) for s in _BASE]
SKILL = 0.9             # a fit must beat "every creek is the average" by 10 % (leave-one-out RMSE <= 0.9 x the spread)
OUTLIER_MADS = 3.0      # sites this far off the first fit (in robust standard deviations) are left out of the second


def area_at(pts):
    """Drainage area (km2) of the NHDPlus V2 flowline within 200 m of each point (02b_download_flow.py's network)."""
    path = f"{SHARED}/flow/nhdplus_v2.gpkg"
    if not os.path.exists(path):
        return np.full(len(pts), np.nan)
    v2 = gpd.read_file(path)
    v2 = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"])]
    return gpd.sjoin_nearest(pts[["geometry"]], v2[["totdasqkm", "geometry"]], max_distance=200, how="left") \
        .groupby(level=0).totdasqkm.first().reindex(pts.index).values


def lake_share(area_edge, area_full):
    """The share of a reach's drainage that reaches it through a lake upstream (what crossbox.py carries past dams and
    ponds, area_full_km2 less area_edge_km2 of 05c_drainages.py, over the full drainage), in full where the reach
    drains LAKE_FULL_KM2 or less, fading with the log of its drainage to nothing at LAKE_NONE_KM2."""
    full = np.asarray(area_full, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.clip(1 - np.asarray(area_edge, float) / full, 0, 1)
        fade = np.clip((np.log10(LAKE_NONE_KM2) - np.log10(np.clip(full, 1e-3, None)))
                       / (np.log10(LAKE_NONE_KM2) - np.log10(LAKE_FULL_KM2)), 0, 1)
    return share * fade


_lakes = None


def _lake_outlines():
    """The area's lake outlines (flowlib.lake_water: what 05_score.py cuts the reaches at), read once."""
    global _lakes
    if _lakes is None:
        import flowlib
        _lakes = flowlib.lake_water(None)
    return _lakes


def _lake_frame(s):
    """(lines in the area's CRS, lake_share, lies in a lake, metres below the lake at the start) of the reaches s."""
    g = s.geometry if s.crs is None or s.crs == CRS else s.geometry.to_crs(CRS)
    geom = np.array(g.values, dtype=object)
    full = pd.to_numeric(s["area_full_km2"], errors="coerce").to_numpy(float)
    edge = pd.to_numeric(s["area_edge_km2"], errors="coerce").to_numpy(float)
    in_lake = s["below_dam"].fillna("").astype(str).str.startswith("in:").to_numpy() if "below_dam" in s else np.zeros(len(s), bool)
    lake = np.minimum(lake_water_km2(geom, full - edge, edge, in_lake), np.nan_to_num(full, nan=0.0))
    share = np.nan_to_num(lake_share(full - lake, full), nan=0.0)
    fade = np.nan_to_num(lake_share(np.zeros(len(s)), full), nan=0.0)       # all of a lake reach's water is lake water
    share = np.where(in_lake, fade, share)
    return geom, share, in_lake, below_lake(geom, lake, in_lake, _lake_outlines())


def lake_parts(s):
    """(the lake term, the term at the reach's upper end, metres of the reach within LAKE_NEAR_M below a lake) of each
    reach of s (a GeoDataFrame of an area's reaches with area_edge_km2, area_full_km2 and below_dam, as
    scoring.attach gives them). Zeros where the columns aren't there (a box scored before its drainages are made).
    The term is lake_share x the part of the reach's length that lies within LAKE_NEAR_M below a lake; a reach lying
    in a lake takes its lake_share in full. Why only just below the lake: the module's header.
    A reach's term is the mean over its length, as a site's is the value at its spot: a reach that starts at a pond
    and runs on for half a mile is mostly past the warmth, and reads cool as a whole. Its first stretch still runs at
    the term of its upper end (the reach's lake_share): the maps say so beside the reach's own estimate
    (scoring.py's water_outlet). At the 19 measured sites within LAKE_NEAR_M of a lake the reach is a median 764 m
    long and reads 4.4 C (7.9 F) below the site; the value at the site's spot reads 0.6 C below."""
    import shapely
    n = len(s)
    if not n or "area_edge_km2" not in s or "area_full_km2" not in s or "geometry" not in s:
        return np.zeros(n), np.zeros(n), np.zeros(n)
    geom, share, in_lake, d0 = _lake_frame(s)
    length = np.maximum(shapely.length(geom), 1e-6)
    with np.errstate(invalid="ignore"):
        near = np.clip((LAKE_NEAR_M - d0) / length, 0, 1)
    near = np.where(in_lake, 1.0, np.where(np.isfinite(d0), near, 0.0))
    return share * near, share * (near > 0), near * length


def lake_term(s):
    """The lake term of each reach of s: lake_parts()'s first value."""
    return lake_parts(s)[0]


def lake_at(pts):
    """The lake term at measured sites (the area's CRS): the lake_share of the reach each sits on (within 150 m; among
    several, the one nearest the site's NHDPlus drainage, da_km2, then the nearest; the first 200 m below a lake that
    05_score.py cuts off its line counts with the line's drainage, so that NHDPlus's figure, a flowline's at its lower
    end, doesn't send a site at the outlet to the rest of the line: the Limekiln Lake outlet's, 17.2 km2 on NHDPlus,
    went 59 m off to the reach with 15.5 km2, past the outlet's own 70 m with 13.7 km2, 5 m off) where the site lies within
    LAKE_NEAR_M below a lake along that reach, else 0. A site on a reach lying in a lake reads lake water, except at
    the reach's upper end where no lake reach runs in: there it reads the creek coming in (Archer Creek above Arbutus
    Pond, 63.9 F, against 73.5 F at the pond's outlet), and takes that creek's term. NaN where no reach is within
    150 m, or the area's reaches aren't built yet."""
    import shapely
    parts = []
    for r in REGIONS:
        d = out_dir(r)
        if all(os.path.exists(f"{d}/{f_}") for f_ in ("streams_scored.gpkg", "area_streams.csv", "flow_streams.csv")):
            s = gpd.read_file(f"{d}/streams_scored.gpkg")
            s = s[["sid", "geometry"] + [c_ for c_ in ("cut_sid",) if c_ in s]].to_crs(CRS)
            s = s.merge(pd.read_csv(f"{d}/area_streams.csv"), on="sid")
            parts.append(s.merge(pd.read_csv(f"{d}/flow_streams.csv", low_memory=False)[["sid", "below_dam"]], on="sid", how="left"))
    out = np.full(len(pts), np.nan)
    if not parts:
        return out
    s = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    geom, share, in_lake, d0 = _lake_frame(s)
    full, length = s.area_full_km2.to_numpy(float), shapely.length(geom)
    line_km2 = full.copy()                   # a first stretch below a lake: its line's drainage (the rest of the line's)
    if "cut_sid" in s:
        rest = s.cut_sid.map(pd.Series(np.arange(len(s)), index=s.sid.values)).fillna(-1).astype(int).to_numpy()
        line_km2 = np.where(rest >= 0, full[np.maximum(rest, 0)], full)
    tree, ends = shapely.STRtree(geom), shapely.STRtree(shapely.get_point(geom, -1))
    da = pts.da_km2.to_numpy(float) if "da_km2" in pts else np.full(len(pts), np.nan)

    def term(j, along):            # the lake term at `along` metres down reach j
        return share[j] if in_lake[j] or d0[j] + along <= LAKE_NEAR_M else 0.0

    for i, p in enumerate(pts.geometry.values):
        k = tree.query(p, predicate="dwithin", distance=150)
        if len(k):
            dist = shapely.distance(geom[k], p)
            rank = dist if not np.isfinite(da[i]) else \
                np.round(np.abs(np.log(np.clip(line_km2[k], 0.1, None) / max(da[i], 0.1))), 1) * 1000 + dist
            j = k[int(np.argmin(rank))]
            along = float(shapely.line_locate_point(geom[j], p))
            if in_lake[j] and along <= LAKE_JOIN_M:
                up = [q for q in ends.query(shapely.get_point(geom[j], 0), predicate="dwithin", distance=LAKE_JOIN_M) if q != j]
                if not any(in_lake[q] for q in up):       # the site is where a creek comes into the lake
                    q = max(up, key=lambda q_: full[q_], default=None)
                    out[i] = 0.0 if q is None else term(q, length[q])
                    continue
            out[i] = term(j, along)
    return out


def _cols(air, elev, area, lake=None):
    return {"air": np.asarray(air, float), "elev_km": np.asarray(elev, float) / 1000,
            "log_area": np.log10(np.clip(np.asarray(area, float), 0.5, None)),
            "lake": np.full(len(np.asarray(air)), np.nan) if lake is None else np.asarray(lake, float)}


def wls(X, y, w):
    """Weighted least squares."""
    s_ = np.sqrt(w)
    return np.linalg.lstsq(X * s_[:, None], y * s_, rcond=None)[0]


def loo_rmse(X, y, w=None):
    w = np.ones(len(y)) if w is None else w
    err = np.array([y[i] - X[i] @ wls(np.delete(X, i, 0), np.delete(y, i), np.delete(w, i)) for i in range(len(y))])
    return float(np.sqrt(np.sum(w * err * err) / np.sum(w)))


def _best(d):
    """The predictor set with the lowest leave-one-out RMSE among those whose coefficients have the physical sign
    (a simpler set within 0.05 C of the best wins). -> (terms, coef, rmse) or None."""
    # sets are compared on the sites that have every input (a few sites sit on no NHDPlus flowline, some on no
    # reach); the winner is fitted again on all the sites that have the inputs it uses
    full = d
    for c_ in ("da_km2", "lake"):
        if full[c_].notna().mean() >= 0.8:
            full = full[full[c_].notna()]
    got = _pick(full)
    if got is not None and len(full) < len(d):
        need = [c_ for c_, t_ in (("da_km2", "log_area"), ("lake", "lake")) if t_ in got[0]]
        got = _pick(d.dropna(subset=need), sets=[got[0]]) or got
    return got


def _pick(d, sets=None):
    c = _cols(d.air, d.elev, d.da_km2, d.lake)
    y, out = d.w.values, []
    w = d.wt.values if "wt" in d else np.ones(len(d))
    for terms in sets or SETS:
        if any(np.isnan(c[t]).any() for t in terms):
            continue
        if "lake" in terms and int((c["lake"] >= 0.5).sum()) < LAKE_MIN_SITES:
            continue                   # too few lake-fed creeks measured to fit the lake term on
        X = np.c_[np.ones(len(d))] if not terms else np.c_[np.ones(len(d)), np.column_stack([c[t] for t in terms])]
        coef = wls(X, y, w)
        if all(np.sign(coef[i + 1]) == TERMS[t] for i, t in enumerate(terms)):
            out.append((terms, coef, loo_rmse(X, y, w)))
    if not out:
        return None
    low = min(o[2] for o in out)
    return min((o for o in out if o[2] <= low + 0.05), key=lambda o: (len(o[0]), o[2]))


def _resid(dd, terms, coef):
    c = _cols(dd.air, dd.elev, dd.da_km2, dd.lake)
    return dd.w.values - (coef[0] + sum(coef[i + 1] * c[t] for i, t in enumerate(terms)))


def _fit_sites(d):
    """The fit on one table of measured sites: weights, one pass of outlier removal, the best of SETS.
    -> (record, sites used with their weights, sites left out)."""
    sig2 = d.sigma_w2.to_numpy(float)
    hot = d[d.w > GEOTHERMAL_C]
    d = d[d.w <= GEOTHERMAL_C]

    def having(dd, terms):         # the sites with the inputs a set uses
        need = [c_ for c_, t_ in (("da_km2", "log_area"), ("lake", "lake")) if t_ in terms]
        return dd.dropna(subset=need) if need else dd

    # weights: tau^2 from the unweighted first fit, then each site 1 / (tau^2 + sigma_w^2 / n)
    d = d.assign(wt=1.0)
    first, tau2 = _best(d), 0.1
    if first is not None and np.isfinite(d.sigma_w2).all():
        terms, coef, _ = first
        dd = having(d, terms)
        tau2 = max(float(np.var(_resid(dd, terms, coef))) - float(np.mean(dd.sigma_w2.values / dd.n.values)), 0.1)
        d["wt"] = 1 / (tau2 + d.sigma_w2.values / d.n.values.astype(float))
    first = _best(d)
    out = d.iloc[:0]
    if first is not None:          # one pass of outlier removal: a site far off the first fit is a bad record
        terms, coef, _ = first     # (a logger left in a spring, a mislabelled unit), not a creek to learn from
        dd = having(d, terms)      # (judged on the sites that have this fit's inputs; the others stay in)
        res = _resid(dd, terms, coef)
        sig = 1.4826 * np.median(np.abs(res - np.median(res)))
        far = dd.index[np.abs(res - np.median(res)) > OUTLIER_MADS * sig]
        out, d = d.loc[far], d.drop(index=far)
    best = _best(d)
    if best is not None:
        d = having(d, best[0])
    w = d.wt.values
    mu = float(np.sum(w * d.w.values) / np.sum(w))
    sd = float(np.sqrt(np.sum(w * (d.w.values - mu) ** 2) / np.sum(w) * len(d) / (len(d) - 1)))
    sw = float(np.nanmedian(sig2)) if len(sig2) else float("nan")
    rec = dict(area=AREA, sites=int(len(d)), sd_sites=round(sd, 2), mean_sites=round(mu, 2),
               left_out_over_30c=int(len(hot)),
               left_out_outliers=int(len(out)), fitted=dt.date.today().isoformat(), ok=False,
               weights=dict(sigma_w=round(sw ** 0.5, 2) if np.isfinite(sw) else None, tau=round(tau2 ** 0.5, 2)))
    if best is not None:
        terms, coef, rmse = best
        c = _cols(d.air, d.elev, d.da_km2, d.lake)
        rec.update(terms=list(terms), intercept=round(float(coef[0]), 3),
                   coef={t: round(float(coef[i + 1]), 3) for i, t in enumerate(terms)}, rmse_loo=round(rmse, 2),
                   ranges={t: [round(float(np.nanmin(c[t])), 3), round(float(np.nanmax(c[t])), 3)] for t in terms},
                   ok=bool(rmse <= SKILL * sd))
    return rec, d, pd.concat([hot, out])


def _group_fit(d, own):
    """For an area whose own sites give no fit with skill (`own`, its record): the fit on the sites of every map of its
    group (config.py's water_temp_group: one region cut into several maps), as their last runs wrote them, if that fit
    has skill and misses this area's own sites by no more than SKILL x their own spread. -> (record, sites, left out)
    or None. The record's rmse_loo is the error on this area's own sites; rmse_group the fit's own."""
    path = lambda a: f"{os.path.dirname(RAW_ROOT)}/{a}/_shared/{os.path.basename(SITES)}"
    others = [a for a in GROUP if a != AREA and os.path.exists(path(a))]
    if not others:
        return None
    # one site in two maps' margins counts once: the copy with the most readings
    g = pd.concat([d] + [pd.read_csv(path(a), index_col=0)[list(d.columns)] for a in others])
    g = g.sort_values("n", ascending=False)
    g = g[~g.index.duplicated()]
    rec, used, left = _fit_sites(g)
    mine = used[used["area"] == AREA]
    if not rec["ok"] or len(mine) < MIN_SITES:
        return None
    res, w = _resid(mine, rec["terms"], [rec["intercept"]] + [rec["coef"][t] for t in rec["terms"]]), mine.wt.values
    rmse_own = float(np.sqrt(np.sum(w * res * res) / np.sum(w)))
    if rmse_own > SKILL * own["sd_sites"]:
        return None
    rec.update(group=A["water_temp_group"], sites_by_area={a: int(n) for a, n in used["area"].value_counts().items()},
               rmse_group=rec["rmse_loo"], sd_group=rec["sd_sites"], rmse_loo=round(rmse_own, 2), sd_sites=own["sd_sites"],
               mean_sites=own["mean_sites"], own_sites=int(len(mine)))
    return rec, used, left


def fit(write=True):
    """Fit the area's measured sites on the best of SETS; returns (record, sites used, sites left out). The record's
    `ok` is False when no set has skill (SKILL): then nothing is estimated and every reach takes the sites' mean.
    Before that fallback, an area in a group (config.py's water_temp_group) tries the fit on the whole group's sites
    (_group_fit). Its own sites are written to SITES for the other maps of the group."""
    pts = measured_sites()
    pts["da_km2"] = area_at(pts)
    pts["lake"] = lake_at(pts)
    pts["sigma_w2"] = SIGMA_W2
    pts["area"] = AREA
    d = pts.dropna(subset=["w", "air", "elev"])
    d = d[["w", "n", "name", "lat", "lon", "air", "elev", "da_km2", "lake", "sigma_w2", "area"]]
    if write and len(GROUP) > 1:
        d.to_csv(SITES + ".tmp")
        os.replace(SITES + ".tmp", SITES)
    if int((d.w <= GEOTHERMAL_C).sum()) < MIN_SITES:
        raise SystemExit(f"{AREA}: only {int((d.w <= GEOTHERMAL_C).sum())} measured sites (need {MIN_SITES}); no water-temperature fit written")
    rec, used, left = _fit_sites(d)
    if not rec["ok"] and len(GROUP) > 1:
        rec, used, left = _group_fit(d, rec) or (rec, used, left)
    if write:
        with open(FIT, "w") as f:
            json.dump(rec, f, indent=1)
    return rec, used, left


def area_mean():
    """The measured sites' mean July-August water temperature (C) where the area's fit has no skill, else NaN: no
    better than "every creek is the average", so that average stands for every creek."""
    rec = fit_record()
    if rec is None or rec.get("ok") or "mean_sites" not in rec:
        return float("nan")
    return float(rec["mean_sites"])


_fit = None
def fit_record():
    """The area's stored fit, or None if there is none yet."""
    global _fit
    if _fit is None and os.path.exists(FIT):
        with open(FIT) as f:
            _fit = json.load(f)
    return _fit


def estimate(air_aug, elev_m, area_km2=None, lake=None):
    """Estimated July-August daytime water temperature (C); NaN where an input the fit uses is missing, or the area
    has no fit with skill. Inputs outside the fitted sites' range are held at its edge: a straight line carried
    far past the measured sites isn't evidence. `lake`: lake_term() of each reach."""
    rec = fit_record()
    n = len(np.asarray(air_aug))
    if rec is None or not rec.get("ok"):
        return np.full(n, np.nan)
    c = _cols(air_aug, elev_m, np.full(n, np.nan) if area_km2 is None else area_km2, lake)
    return rec["intercept"] + sum(k * np.clip(c[t], *rec["ranges"][t]) for t, k in rec["coef"].items())


NAMES = {"air": "August air (C)", "elev_km": "elevation (km)", "log_area": "log10 drainage area (km2)",
         "lake": "share of the drainage that comes through a lake within 200 m upstream (fading out on rivers of 50 to 500 km2)"}


if __name__ == "__main__":
    rec, d, left = fit()
    if "terms" in rec:
        print(f"{AREA}: water = {rec['intercept']:.2f} " + " ".join(f"{k:+.2f} x {NAMES[t]}" for t, k in rec["coef"].items()))
        if "group" in rec:
            print(f"  no fit with skill on this map's own sites: this is the fit on the {rec['group']} maps' {rec['sites']} sites "
                  f"({rec['sites_by_area']}; leave-one-out RMSE {rec['rmse_group']} C, spread {rec['sd_group']} C)")
            print(f"  on this map's own {rec['own_sites']} sites it is off by {rec['rmse_loo']} C (their spread {rec['sd_sites']} C)")
        else:
            print(f"  {rec['sites']} sites (spread {rec['sd_sites']} C); leave-one-out RMSE {rec['rmse_loo']} C"
                  + ("" if rec["ok"] else f" -- NO SKILL (needs <= {SKILL} x the spread): no estimate, every reach takes the sites' mean"))
        print("  fitted over " + "; ".join(f"{NAMES[t]} {a}..{b}" for t, (a, b) in rec["ranges"].items()))
    else:
        print(f"{AREA}: no predictor set with physically sensible signs; no estimate")
    print("  left out (over 30 C, or far off the first fit):", ", ".join(f"{n} ({w:.1f} C)" for n, w in zip(left.name, left.w)) or "none")
    print(f"  written to {FIT}")
