#!/usr/bin/env python3
"""Smaller popup values against their sources, all areas:
  names      the drawn reach's name against the GNIS name of the NHD HR line under it (by length)
  elevation  popup elevation against the 10 m DEM at the reach's middle; gradient against (top - bottom) / length
  canopy     popup tree canopy against the canopy raster along the line
  sun        consistency of hours of sun and the shaded share; impossible values
  access     implied driving speed, drive miles against the straight line from home, zero and missing times
Tables: audit/tables/popup_checks_summary.csv, name_mismatches.csv, access_oddities.csv
    SITE_DIR=<published maps> python audit/scripts/popup_checks.py [area ...]
"""
import sys, os, re
import numpy as np, pandas as pd, shapely, rasterio, pyproj
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from popups import reaches

STREAMISH = {460, 558, 336}


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("saint", "st").replace(" (side channel)", "")).strip()


def sample(area, fname, x, y, root="raw"):
    out = np.full(len(x), np.nan)
    for r_, b in boxes(area).items():
        p = f"{ROOT}/data/{root}/{area}/{r_}/{fname}"
        if not os.path.exists(p):
            continue
        x0, y0, x1, y1 = b["bbox"]
        m = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
        if not m.any():
            continue
        with rasterio.open(p) as src:
            v = np.array([q[0] for q in src.sample(np.c_[x[m], y[m]])], float)
            if src.nodata is not None:
                v[v == src.nodata] = np.nan
            out[m] = v
    return out


def main(areas):
    S, NM, AO = [], [], []
    for a in areas:
        r = reaches(a, layers=("streams",)).reset_index(drop=True)
        to_ll = pyproj.Transformer.from_crs(epsg(a), 4326, always_xy=True)
        from_ll = pyproj.Transformer.from_crs(4326, epsg(a), always_xy=True)
        row = dict(area=a, reaches=len(r), miles=r.len_m.sum() / MI)

        # ---- names
        nhd = nhd_lines(a)
        nhd = nhd[nhd.ftype.isin(STREAMISH)].reset_index(drop=True)
        named = nhd[nhd.gnis_name.notna()].reset_index(drop=True)
        x, y, ln, li = seg_midpoints(r.geometry.values)
        d, j = nearest_dist(x, y, named.geometry.values, 40.0)
        nm = np.where(j >= 0, named.gnis_name.to_numpy(object)[np.maximum(j, 0)], None)
        df = pd.DataFrame(dict(i=li, ln=ln, nhd=nm))
        tot = df.groupby("i").ln.sum()
        with_name = df.dropna(subset=["nhd"]).groupby(["i", "nhd"]).ln.sum().reset_index().sort_values("ln").groupby("i").tail(1).set_index("i")
        share = (with_name.ln / tot.reindex(with_name.index)).reindex(r.index).fillna(0)
        nhd_name = with_name.nhd.reindex(r.index)
        on_nhd = share >= 0.6                                         # the reach lies along one named NHD stream
        mine = np.array([m if isinstance(m, str) and m else None for m in r.name], dtype=object)
        nhd_name = np.array([n if isinstance(n, str) and n else None for n in nhd_name], dtype=object)
        same = [norm(m) == norm(n) if m is not None and n is not None else False for m, n in zip(mine, nhd_name)]
        same = np.array(same)
        L = r.len_m.to_numpy(float)
        has = np.array([m is not None for m in mine])
        row.update(named_mi=L[has].sum() / MI,
                   on_named_nhd_mi=L[on_nhd].sum() / MI,
                   name_same_pct=100 * L[on_nhd & same].sum() / max(L[on_nhd].sum(), 1),
                   name_differs_mi=L[on_nhd & has & ~same].sum() / MI,
                   name_missing_mi=L[on_nhd & ~has].sum() / MI,
                   named_off_nhd_mi=L[has & (share < 0.2)].sum() / MI)
        for i in np.where(on_nhd & ~same)[0]:
            if L[i] >= 300:
                NM.append(dict(area=a, map_name=mine[i], nhd_name=nhd_name[i], miles=round(L[i] / MI, 2), sq_mi=round(r.km2.iat[i] / 2.58999, 2),
                               fish=r.fish.iat[i], lat=r.lat.iat[i], lon=r.lon.iat[i]))

        # ---- elevation and gradient (a sample of up to 4,000 reaches)
        rs = r.sample(min(4000, len(r)), random_state=1)
        g = rs.geometry.values
        mid = shapely.line_interpolate_point(g, 0.5, normalized=True)
        z = sample(a, "dem_10m.tif", shapely.get_x(mid), shapely.get_y(mid))
        dz = rs.elev_m.to_numpy(float) - z
        p0, p1 = shapely.get_point(g, 0), shapely.get_point(g, -1)
        ok = np.array([q is not None for q in p0])
        z0 = sample(a, "dem_10m.tif", shapely.get_x(p0[ok]), shapely.get_y(p0[ok]))
        z1 = sample(a, "dem_10m.tif", shapely.get_x(p1[ok]), shapely.get_y(p1[ok]))
        gr = 100 * np.abs(z0 - z1) / np.maximum(rs.len_m.to_numpy(float)[ok], 1)
        dg = rs.grad_pct.to_numpy(float)[ok] - gr
        row.update(elev_median_diff_ft=np.nanmedian(dz) / FT, elev_p95_abs_ft=np.nanquantile(np.abs(dz), 0.95) / FT,
                   grad_median_diff=np.nanmedian(dg), grad_p90_abs=np.nanquantile(np.abs(dg), 0.9),
                   grad_zero_pct=100 * (r.grad_pct == 0).mean())

        # ---- canopy along the line (same sample)
        cx, cy, cl, ci = seg_midpoints(g, 30.0)
        cv = sample(a, "canopy_tcc.tif", cx, cy)
        cdf = pd.DataFrame(dict(i=ci, v=cv, w=cl)).dropna()
        cm = cdf.groupby("i").apply(lambda t: np.average(t.v, weights=t.w))
        dc = rs.canopy_pct.to_numpy(float)[cm.index] - cm.to_numpy()
        row.update(canopy_median_diff=np.nanmedian(dc), canopy_p90_abs=np.nanquantile(np.abs(dc), 0.9))

        # ---- sun
        pot = r.sun_h / (1 - r.shade_pct / 100).clip(lower=0.01)
        row.update(sun_possible_h_median=pot.median(), sun_possible_h_iqr=pot.quantile(0.75) - pot.quantile(0.25),
                   shade_negative_n=int((r.shade_pct < 0).sum()),
                   sun_over_15h_n=int((r.sun_h > 15.2).sum()), shade_over_80_pct=100 * (r.shade_pct > 80).mean())

        # ---- access
        home = AREAS[a]["home"]
        hx, hy = from_ll.transform(home["lon"], home["lat"])
        mx, my = shapely.get_x(shapely.centroid(r.geometry.values)), shapely.get_y(shapely.centroid(r.geometry.values))
        straight = np.hypot(mx - hx, my - hy) / MI
        mph = 60 * r.drive_mi / r.drive_min.where(r.drive_min > 0)
        short = r.drive_mi < 0.85 * straight - 3 - (r.hike_min.fillna(0) + 3 * r.bike_min.fillna(0)) / 20.0   # miles a walk or ride could cover
        row.update(drive_missing_pct=100 * r.drive_min.isna().mean(), mph_median=mph.median(), mph_p5=mph.quantile(0.05),
                   mph_p95=mph.quantile(0.95), mph_over_70_n=int((mph > 70).sum()), mph_under_15_n=int((mph < 15).sum()),
                   drive_shorter_than_straight_n=int(short.sum()), hike_0_pct=100 * (r.hike_min.fillna(0) == 0).mean(),
                   hike_over_8h_pct=100 * (r.hike_min > 480).mean(), bike_pct=100 * r.bike_min.notna().mean(),
                   bike_check_pct=100 * r.bike_check.mean(), hike_median_min=r.hike_min.median(),
                   neg_zero_n=int(r.acc_text.str.contains("hike -0").sum()))
        odd = r[(mph > 70) | (mph < 15) | short | r.drive_min.isna()]
        for q in odd.head(400).itertuples():
            AO.append(dict(area=a, name=q.name, drive_min=q.drive_min, drive_mi=q.drive_mi, hike_min=q.hike_min, bike_min=q.bike_min,
                           park=q.park, lat=q.lat, lon=q.lon, access=q.acc_text[:140]))
        S.append(row)
        print(a, "done", flush=True)
    S = pd.DataFrame(S)
    S.insert(0, "site", site_name())
    S.round(2).to_csv(f"{TABLES}/popup_checks_summary.csv", index=False)
    pd.DataFrame(NM).sort_values("miles", ascending=False).to_csv(f"{TABLES}/name_mismatches.csv", index=False)
    pd.DataFrame(AO).to_csv(f"{TABLES}/access_oddities.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
    print(S.round(2).T.to_string())


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
