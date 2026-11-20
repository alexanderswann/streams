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
from config import REGIONS, CRS, SHARED, NATIONAL, AREA, raw_dir

FIT = f"{SHARED}/water_temp_fit.json"
CACHE = f"{SHARED}/cache"
GEOTHERMAL_C = 30.0     # site medians above this are hot springs, not climate
MIN_SITES = 25          # fewer measured sites than this: no fit (the score falls back to the air temperature alone)


def _cached(name, fetch):
    os.makedirs(CACHE, exist_ok=True)
    p = f"{CACHE}/{name}"
    if not (os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400):
        fetch(p + ".tmp")
        os.replace(p + ".tmp", p)
    return p


def _wqp(kind, bounds):
    W, S, E, N = bounds
    def fetch(p):
        r = requests.get(f"https://www.waterqualitydata.us/data/{kind}/search", timeout=900, params=dict(
            bBox=f"{W:.3f},{S:.3f},{E:.3f},{N:.3f}", characteristicName="Temperature, water", siteType="Stream",
            startDateLo="01-01-1995", mimeType="csv", **({"dataProfile": "narrowResult"} if kind == "Result" else {})),
            headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
        r.raise_for_status()
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
        urllib.request.urlretrieve(PRISM + ".zip", z + ".part")
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
TERMS = {"air": +1, "elev_km": -1, "log_area": +1}
SETS = [("air", "elev_km"), ("air",), ("elev_km",), ("log_area",), ("air", "log_area"), ("elev_km", "log_area"),
        ("air", "elev_km", "log_area")]
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


def _cols(air, elev, area):
    return {"air": np.asarray(air, float), "elev_km": np.asarray(elev, float) / 1000,
            "log_area": np.log10(np.clip(np.asarray(area, float), 0.5, None))}


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
    # sets are compared on the sites that have every input (a few sites sit on no NHDPlus flowline); if the winner
    # doesn't use the drainage area, it is fitted again on all of them
    full = d[d.da_km2.notna()] if d.da_km2.notna().mean() >= 0.8 else d
    got = _pick(full)
    if got is not None and "log_area" not in got[0] and len(full) < len(d):
        got = _pick(d, sets=[got[0]]) or got
    return got


def _pick(d, sets=None):
    c = _cols(d.air, d.elev, d.da_km2)
    y, out = d.w.values, []
    w = d.wt.values if "wt" in d else np.ones(len(d))
    for terms in sets or SETS:
        if any(np.isnan(c[t]).any() for t in terms):
            continue
        X = np.c_[np.ones(len(d))] if not terms else np.c_[np.ones(len(d)), np.column_stack([c[t] for t in terms])]
        coef = wls(X, y, w)
        if all(np.sign(coef[i + 1]) == TERMS[t] for i, t in enumerate(terms)):
            out.append((terms, coef, loo_rmse(X, y, w)))
    if not out:
        return None
    low = min(o[2] for o in out)
    return min((o for o in out if o[2] <= low + 0.05), key=lambda o: (len(o[0]), o[2]))


def fit(write=True):
    """Fit the area's measured sites on the best of SETS; returns (record, sites used, sites left out). The record's
    `ok` is False when no set has skill (SKILL): then nothing is estimated and the thermal term stays neutral."""
    pts = measured_sites()
    pts["da_km2"] = area_at(pts)
    d = pts.dropna(subset=["w", "air", "elev"])
    hot = d[d.w > GEOTHERMAL_C]
    d = d[d.w <= GEOTHERMAL_C]
    if len(d) < MIN_SITES:
        raise SystemExit(f"{AREA}: only {len(d)} measured sites (need {MIN_SITES}); no water-temperature fit written")
    # weights: tau^2 from the unweighted first fit, then each site 1 / (tau^2 + sigma_w^2 / n)
    d = d.assign(wt=1.0)
    first, tau2 = _best(d), 0.1
    if first is not None and np.isfinite(SIGMA_W2):
        terms, coef, _ = first
        dd = d[d.da_km2.notna()] if "log_area" in terms else d
        c = _cols(dd.air, dd.elev, dd.da_km2)
        r = dd.w.values - (coef[0] + sum(coef[i + 1] * c[t] for i, t in enumerate(terms)))
        tau2 = max(float(np.var(r)) - float(np.mean(SIGMA_W2 / dd.n.values)), 0.1)
        d["wt"] = 1 / (tau2 + SIGMA_W2 / d.n.values.astype(float))
    first = _best(d)
    out = d.iloc[:0]
    if first is not None:          # one pass of outlier removal: a site far off the first fit is a bad record
        terms, coef, _ = first     # (a logger left in a spring, a mislabelled unit), not a creek to learn from
        if "log_area" in terms:
            d = d[d.da_km2.notna()]
        c = _cols(d.air, d.elev, d.da_km2)
        res = d.w.values - (coef[0] + sum(coef[i + 1] * c[t] for i, t in enumerate(terms)))
        sig = 1.4826 * np.median(np.abs(res - np.median(res)))
        far = np.abs(res - np.median(res)) > OUTLIER_MADS * sig
        out, d = d[far], d[~far]
    best = _best(d)
    if best is not None and "log_area" in best[0]:
        d = d[d.da_km2.notna()]
    w = d.wt.values
    mu = float(np.sum(w * d.w.values) / np.sum(w))
    sd = float(np.sqrt(np.sum(w * (d.w.values - mu) ** 2) / np.sum(w) * len(d) / (len(d) - 1)))
    rec = dict(area=AREA, sites=int(len(d)), sd_sites=round(sd, 2), mean_sites=round(mu, 2),
               left_out_over_30c=int(len(hot)),
               left_out_outliers=int(len(out)), fitted=dt.date.today().isoformat(), ok=False,
               weights=dict(sigma_w=round(SIGMA_W2 ** 0.5, 2) if np.isfinite(SIGMA_W2) else None, tau=round(tau2 ** 0.5, 2)))
    if best is not None:
        terms, coef, rmse = best
        c = _cols(d.air, d.elev, d.da_km2)
        rec.update(terms=list(terms), intercept=round(float(coef[0]), 3),
                   coef={t: round(float(coef[i + 1]), 3) for i, t in enumerate(terms)}, rmse_loo=round(rmse, 2),
                   ranges={t: [round(float(np.nanmin(c[t])), 3), round(float(np.nanmax(c[t])), 3)] for t in terms},
                   ok=bool(rmse <= SKILL * sd))
    if write:
        with open(FIT, "w") as f:
            json.dump(rec, f, indent=1)
    return rec, d, pd.concat([hot, out])


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


def estimate(air_aug, elev_m, area_km2=None):
    """Estimated July-August daytime water temperature (C); NaN where an input the fit uses is missing, or the area
    has no fit with skill. Inputs outside the fitted sites' range are held at its edge: a straight line carried
    far past the measured sites isn't evidence."""
    rec = fit_record()
    n = len(np.asarray(air_aug))
    if rec is None or not rec.get("ok"):
        return np.full(n, np.nan)
    c = _cols(air_aug, elev_m, np.full(n, np.nan) if area_km2 is None else area_km2)
    return rec["intercept"] + sum(k * np.clip(c[t], *rec["ranges"][t]) for t, k in rec["coef"].items())


NAMES = {"air": "August air (C)", "elev_km": "elevation (km)", "log_area": "log10 drainage area (km2)"}


if __name__ == "__main__":
    rec, d, left = fit()
    if "terms" in rec:
        print(f"{AREA}: water = {rec['intercept']:.2f} " + " ".join(f"{k:+.2f} x {NAMES[t]}" for t, k in rec["coef"].items()))
        print(f"  {rec['sites']} sites (spread {rec['sd_sites']} C); leave-one-out RMSE {rec['rmse_loo']} C"
              + ("" if rec["ok"] else f" -- NO SKILL (needs <= {SKILL} x the spread): no estimate, the thermal term stays neutral"))
        print("  fitted over " + "; ".join(f"{NAMES[t]} {a}..{b}" for t, (a, b) in rec["ranges"].items()))
    else:
        print(f"{AREA}: no predictor set with physically sensible signs; no estimate")
    print("  left out (over 30 C, or far off the first fit):", ", ".join(f"{n} ({w:.1f} C)" for n, w in zip(left.name, left.w)) or "none")
    print(f"  written to {FIT}")
