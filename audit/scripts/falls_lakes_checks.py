#!/usr/bin/env python3
"""Drops against the known-falls lists, and the lakes layer against NHD's waterbodies.

Falls: for every known waterfall of an area (data/raw/<area>/_shared/known_falls.gpkg, kind 'waterfall', inside the
boxes) the nearest drop the pipeline found (output/<area>/waterfall_candidates.csv, or a snapshot folder): is there
one within 100 m / 250 m, and what does the map call it. Split by whether the list's point is 'precise'.
Lakes: the lakes layer (data/derived/<area>/_shared/lakes.gpkg) against NHD HR lakes and reservoirs of the national
download: lakes NHD has that the layer lacks (at or above the layer's own smallest size), acreage against NHD's,
how many lakes carry a measured depth, fish records, an outlet name.
    TABLES_DIR=<folder with <area>/waterfall_candidates.csv> python audit/scripts/falls_lakes_checks.py [area ...]
Tables: audit/tables/falls_recall.csv, falls_missed.csv, lakes_summary.csv, lakes_missing.csv, lakes_area_off.csv
"""
import sys, os
import numpy as np, pandas as pd, geopandas as gpd, shapely
sys.path.insert(0, os.path.dirname(__file__))
from common import *

SNAP = os.environ.get("TABLES_DIR", "")


def table(area, name):
    for base in ([SNAP] if SNAP else []) + [f"{ROOT}/output"]:
        p = f"{base}/{area}/{name}"
        if os.path.exists(p):
            return p
    return None


def falls(a):
    kp = f"{ROOT}/data/raw/{a}/_shared/known_falls.gpkg"
    wp = table(a, "waterfall_candidates.csv")
    if not os.path.exists(kp) or wp is None:
        return None, None
    k = gpd.read_file(kp).to_crs(epsg(a))
    k = k[shapely.contains(area_box_union(a), k.geometry.values)].reset_index(drop=True)
    w = pd.read_csv(wp, low_memory=False)
    wg = gpd.GeoDataFrame(w, geometry=gpd.points_from_xy(w.lon, w.lat), crs=4326).to_crs(epsg(a))
    pool = gpd.GeoSeries(gpd.points_from_xy(w.pool_lon, w.pool_lat), crs=4326).to_crs(epsg(a))
    tree, tree2 = shapely.STRtree(wg.geometry.values), shapely.STRtree(pool.values)
    rows = []
    for q in k.itertuples():
        best, bj = np.inf, -1
        for t in (tree, tree2):
            j = t.nearest(q.geometry)
            d = shapely.distance(t.geometries[j], q.geometry)
            if d < best:
                best, bj = d, j
        ll = gpd.GeoSeries([q.geometry], crs=epsg(a)).to_crs(4326).iloc[0]
        rows.append(dict(area=a, name=q.name, kind=q.kind, precise=bool(q.precise), src=q.src, nearest_m=round(best),
                         status=w.status.iat[bj], drop_kind=w.kind.iat[bj], drop_ft=round(w.drop_m.iat[bj] / FT),
                         lat=round(ll.y, 5), lon=round(ll.x, 5)))
    return pd.DataFrame(rows), w


def lakes(a):
    p = f"{ROOT}/data/derived/{a}/_shared/lakes.gpkg"
    if not os.path.exists(p):
        return None, None, None
    L = gpd.read_file(p).to_crs(epsg(a))
    clip = area_box_union(a)
    hu4 = sorted({h for b in boxes(a).values() for h in b["hu4"]})
    parts = []
    for h in hu4:
        g = f"{ROOT}/data/raw/_national/NHD_H_{h}_HU4_GPKG.gpkg"
        if os.path.exists(g):
            x0, y0, x1, y1 = gpd.GeoSeries([clip], crs=epsg(a)).to_crs(4269).total_bounds
            w = gpd.read_file(g, layer="NHDWaterbody", bbox=(x0, y0, x1, y1), columns=["gnis_name", "ftype", "fcode", "areasqkm"])
            parts.append(w.to_crs(epsg(a)))
    N = pd.concat(parts, ignore_index=True)
    N = N[N.ftype.isin([390, 436])]
    N = N[shapely.contains(clip, shapely.point_on_surface(N.geometry.values))].reset_index(drop=True)
    N["ha"] = N.geometry.area / 1e4
    N = N.drop_duplicates(subset=["gnis_name", "ha"]).reset_index(drop=True)
    return L, N, clip


def main(areas):
    FR, FM, LS, LM, LA_ = [], [], [], [], []
    for a in areas:
        f, w = falls(a)
        if f is not None and len(f):
            wf = f[f.kind == "waterfall"]
            for lab, d in (("precise points", wf[wf.precise]), ("imprecise points", wf[~wf.precise]), ("cascades, rapids", f[f.kind != "waterfall"])):
                if not len(d):
                    continue
                real = ~d.status.eq("likely DEM artifact")
                FR.append(dict(area=a, known=lab, n=len(d), drop_within_100m_pct=100 * ((d.nearest_m <= 100) & real).mean(),
                               drop_within_250m_pct=100 * ((d.nearest_m <= 250) & real).mean(),
                               nearest_is_artifact_n=int(((d.nearest_m <= 100) & ~real).sum()),
                               none_within_250m_n=int((d.nearest_m > 250).sum())))
            miss = wf[wf.precise & (wf.nearest_m > 250)]
            FM.append(miss)
        L, N, clip = lakes(a)
        if L is not None:
            min_ha = float(L.ha.min())
            tree = shapely.STRtree(L.geometry.values)
            big = N[N.ha >= max(min_ha, 1.0)].reset_index(drop=True)
            hit = np.array([len(tree.query(g_, predicate="intersects")) > 0 for g_ in big.geometry.values])
            miss = big[~hit]
            for q in miss.sort_values("ha", ascending=False).head(60).itertuples():
                ll = gpd.GeoSeries([shapely.point_on_surface(q.geometry)], crs=epsg(a)).to_crs(4326).iloc[0]
                LM.append(dict(area=a, nhd_name=q.gnis_name, acres=round(q.ha * 2.47105), fcode=q.fcode, lat=round(ll.y, 5), lon=round(ll.x, 5)))
            ratio = (L.ha / L.nhd_ha).replace([np.inf, -np.inf], np.nan)
            has_nhd = L.nhd_ha.notna() & (L.nhd_ha > 0)
            dep = L.depth_max_m.notna()
            LS.append(dict(area=a, lakes=len(L), smallest_acres=round(min_ha * 2.47105, 1), acres_total=round(L.ha.sum() * 2.47105),
                           nhd_lakes_1ha_plus=len(big), nhd_lakes_missing=int((~hit).sum()), nhd_missing_acres=round(miss.ha.sum() * 2.47105),
                           outline_from=L.src_outline.value_counts().to_dict(),
                           area_within10_of_nhd_pct=round(100 * ((ratio[has_nhd] > 0.9) & (ratio[has_nhd] < 1.1)).mean(), 1),
                           area_off_25_n=int(((ratio[has_nhd] < 0.75) | (ratio[has_nhd] > 1.25)).sum()),
                           with_depth_n=int(dep.sum()), with_depth_pct=round(100 * dep.mean(), 1),
                           depth_acres_pct=round(100 * L.ha[dep].sum() / L.ha.sum(), 1),
                           depth_sources=L.depth_src[dep].astype(str).str.slice(0, 40).value_counts().head(4).to_dict(),
                           named_pct=round(100 * L.name.notna().mean(), 1), with_fish_records_pct=round(100 * (L.n_records.fillna(0) > 0).mean(), 1),
                           outlet_named_pct=round(100 * L.outlet_name.notna().mean(), 1),
                           no_inlet_no_outlet_pct=round(100 * L.connection.astype(str).str.contains("none|closed|no ").mean(), 1)))
            off = L[has_nhd & ((ratio < 0.75) | (ratio > 1.25)) & (L.ha >= 4)]
            for q in off.sort_values("ha", ascending=False).head(40).itertuples():
                ll = gpd.GeoSeries([shapely.point_on_surface(q.geometry)], crs=epsg(a)).to_crs(4326).iloc[0]
                LA_.append(dict(area=a, name=q.name, acres=round(q.ha * 2.47105), nhd_acres=round(q.nhd_ha * 2.47105), ratio=round(q.ha / q.nhd_ha, 2),
                                outline=q.src_outline, note=str(q.water_note)[:80], lat=round(ll.y, 5), lon=round(ll.x, 5)))
        print(a, "done", flush=True)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 90)
    FR = pd.DataFrame(FR); FR.round(1).to_csv(f"{TABLES}/falls_recall.csv", index=False); print(FR.round(1).to_string(index=False))
    if FM:
        pd.concat(FM).to_csv(f"{TABLES}/falls_missed.csv", index=False)
    LS = pd.DataFrame(LS); LS.to_csv(f"{TABLES}/lakes_summary.csv", index=False); print(LS.T.to_string())
    pd.DataFrame(LM).to_csv(f"{TABLES}/lakes_missing.csv", index=False)
    pd.DataFrame(LA_).to_csv(f"{TABLES}/lakes_area_off.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
