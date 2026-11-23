#!/usr/bin/env python3
"""Drainage area the popups state, against two independent references:
  1. USGS gauges: the drainage area in each gauge's site record (data/raw/<area>/_shared/flow/gauge_sites.gpkg).
  2. NHDPlus V2: totdasqkm of every flowline of 10 km2 or more (main paths only), taken 100 m above its lower end.
For each reference point the nearest drawn stream line is read ("nearest"), and of every drawn line within reach the
one closest in size ("best": tells a real mismatch from a gauge sitting at a confluence or beside a side channel).
Within reach = 100 m for a creek under 100 km2, 250 m to 1,000 km2, 500 m for a bigger river (a wide river's routed
line wanders from bank to bank over the flat water surface, and gauges stand on the bank).
Tables: audit/tables/area_vs_gauges.csv, area_vs_nhdplus.csv (per point), area_vs_reference_summary.csv.
"""
import sys, os
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyproj
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from popups import reaches

SQMI = 2.58999


def match(pts, ref_km2, r):
    """For each point: (km2 of the nearest line within 100 m, its distance, km2 of the best-fitting line within 100 m)."""
    tree = shapely.STRtree(r.geometry.values)
    near = np.full(len(pts), np.nan); dist = np.full(len(pts), np.nan); best = np.full(len(pts), np.nan)
    idx = np.full(len(pts), -1)
    km2 = r.km2.to_numpy(float)
    for i, p in enumerate(pts):
        c = tree.query(p, predicate="dwithin", distance=100.0 if ref_km2[i] < 100 else 250.0 if ref_km2[i] < 1000 else 500.0)
        if not len(c):
            continue
        d = shapely.distance(r.geometry.values[c], p)
        j = c[np.argmin(d)]
        near[i], dist[i], idx[i] = km2[j], d.min(), j
        best[i] = km2[c[np.argmin(np.abs(np.log(np.maximum(km2[c], 1e-3) / max(ref_km2[i], 1e-3))))]]
    return near, dist, best, idx


def summarize(df, ref, area, label):
    d = df[df.map_km2.notna()]
    if not len(d):
        return dict(area=area, ref=label, n=len(df), matched=0)
    q = d.map_km2 / d[ref]
    qb = d.best_km2 / d[ref]
    return dict(area=area, ref=label, n=len(df), matched=len(d), median_ratio=q.median(),
                within10_pct=100 * ((q > 0.9) & (q < 1.1)).mean(), within25_pct=100 * ((q > 0.75) & (q < 1.25)).mean(),
                under_half_pct=100 * (q < 0.5).mean(), over_1_5_pct=100 * (q > 1.5).mean(),
                under_half_n=int((q < 0.5).sum()), over_1_5_n=int((q > 1.5).sum()),
                best_within25_pct=100 * ((qb > 0.75) & (qb < 1.25)).mean(), best_under_half_n=int((qb < 0.5).sum()))


def main(areas):
    G, N, S = [], [], []
    for a in areas:
        r = reaches(a)
        to_ll = pyproj.Transformer.from_crs(epsg(a), 4326, always_xy=True)
        clip = area_box_union(a)
        # ---- gauges
        g = gpd.read_file(f"{ROOT}/data/raw/{a}/_shared/flow/gauge_sites.gpkg").to_crs(epsg(a))
        g = g[g.drain_area_va.notna() & shapely.contains(clip, g.geometry.values)].reset_index(drop=True)
        ref = g.drain_area_va.to_numpy(float) * SQMI
        near, dist, best, idx = match(g.geometry.values, ref, r)
        gg = pd.DataFrame(dict(area=a, site_no=g.site_no, station=g.station_nm, gauge_km2=ref, map_km2=near, best_km2=best,
                               dist_m=dist, lat=g.geometry.to_crs(4326).y.round(5), lon=g.geometry.to_crs(4326).x.round(5),
                               reach_name=[r.name.iat[j] if j >= 0 else None for j in idx],
                               end_date=g.end_date))
        G.append(gg); S.append(summarize(gg, "gauge_km2", a, "USGS gauges"))
        # ---- NHDPlus V2 lines of 10 km2+, main paths, 100 m above the lower end
        n = gpd.read_file(f"{ROOT}/data/raw/{a}/_shared/flow/nhdplus_v2.gpkg").to_crs(epsg(a))
        n = n[(n.totdasqkm >= 10) & (n.divergence != 2) & (n.streamcalc != 0)].reset_index(drop=True)
        geoms = np.array([shapely.line_merge(x) if x.geom_type == "MultiLineString" else x for x in n.geometry.values], dtype=object)
        ok = np.array([x.geom_type == "LineString" and x.length > 250 for x in geoms])
        n, geoms = n[ok].reset_index(drop=True), geoms[ok]
        pts = shapely.line_interpolate_point(geoms, np.maximum(shapely.length(geoms) - 100.0, 0))
        inside = shapely.contains(clip, pts)
        n, pts = n[inside].reset_index(drop=True), pts[inside]
        ref = n.totdasqkm.to_numpy(float)
        near, dist, best, idx = match(pts, ref, r)
        lon, lat = to_ll.transform(shapely.get_x(pts), shapely.get_y(pts))
        nn = pd.DataFrame(dict(area=a, comid=n.comid, nhd_name=n.gnis_name, nhdplus_km2=ref, map_km2=near, best_km2=best,
                               dist_m=dist, lat=np.round(lat, 5), lon=np.round(lon, 5),
                               reach_name=[r.name.iat[j] if j >= 0 else None for j in idx],
                               reach_flow=[r.flow_shown.iat[j] if j >= 0 else None for j in idx],
                               layer=[r.layer.iat[j] if j >= 0 else None for j in idx]))
        N.append(nn)
        S.append(summarize(nn, "nhdplus_km2", a, "NHDPlus 10+ km2"))
        S.append(summarize(nn[nn.nhdplus_km2 >= 100], "nhdplus_km2", a, "NHDPlus 100+ km2"))
        print(a, "done", flush=True)
    G, N, S = pd.concat(G), pd.concat(N), pd.DataFrame(S)
    G["ratio"] = (G.map_km2 / G.gauge_km2).round(3)
    N["ratio"] = (N.map_km2 / N.nhdplus_km2).round(3)
    G.round(3).to_csv(f"{TABLES}/area_vs_gauges.csv", index=False)
    N.round(3).to_csv(f"{TABLES}/area_vs_nhdplus.csv", index=False)
    S.insert(0, "site", site_name())
    S.round(2).to_csv(f"{TABLES}/area_vs_reference_summary.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(S.round(2).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
