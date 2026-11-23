#!/usr/bin/env python3
"""Does 1 m lidar find the waterfalls the 10 m terrain misses? A test on a few maps, not a pipeline step.

For known falls placed on the fall itself (known_falls.gpkg, precise, waterfall or cascade), split by whether the
pipeline's 10 m terrain found a drop within 100 m (output/<area>/waterfall_candidates.csv, DEM artifacts and dams not
counted), and for random points on NHD-named creeks with no known fall within 500 m (how often a rule fires where
nobody has mapped a fall), all measured within 50 m of the point: the stream profile 150 m up and down the NHD line, as the lowest ground within 10 m of each
metre of line (so a line drawn a few metres off the channel still reads the channel bed), made non-increasing
downstream, from the 1 m 3DEP lidar DEM (read in place from USGS's cloud tiles with lakelidar.py) and from the 10 m
DEM the pipeline uses. Measured: the largest drop over 5, 10 and 20 m of channel, and where it is.
Network (lidar tiles, about 1 MB a point); read-only on the project; tiles and tables go to OUT.
    OUT=<folder> python audit/scripts/lidar_falls_test.py smokies:15:8:8 n_georgia ...   (area[:missed:found:random])
"""
import sys, os, glob, json, shutil, time
import numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely, shapely.ops
from rasterio.windows import from_bounds
from scipy import ndimage
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/Users/mac/Fishing/scripts")
from common import ROOT, boxes, epsg, area_box_union, nhd_lines
import lakelidar

OUT = os.environ.get("OUT", "/tmp/lidar_falls_test")   # tiles are cached there: a re-run reads them again, no download
HALF = 150.0          # m of line up and down from the point
SNAP = 10             # m: lowest ground within this of the line
STEPS = (5, 10, 20)
rng = np.random.default_rng(20261122)


def profile_from(a, T, line, snap_px):
    """Lowest ground within snap_px cells of each metre of the line, non-increasing downstream."""
    fp = np.hypot(*np.mgrid[-snap_px:snap_px + 1, -snap_px:snap_px + 1]) <= snap_px
    lo = ndimage.minimum_filter(np.where(a < -1000, np.inf, a), footprint=fp)
    d = np.arange(0, line.length, 1.0)
    pts = [line.interpolate(x) for x in d]
    rc = [rasterio.transform.rowcol(T, p.x, p.y) for p in pts]
    z = np.array([lo[r, c] if 0 <= r < lo.shape[0] and 0 <= c < lo.shape[1] else np.nan for r, c in rc], float)
    z[~np.isfinite(z)] = np.nan
    if np.isnan(z).mean() > 0.2:
        return None, d
    z = pd.Series(z).interpolate(limit_direction="both").to_numpy()
    if z[0] < z[-1]:                          # make it run downstream
        z, d = z[::-1], d[::-1]
    return np.minimum.accumulate(z), d


def drops(z, d, at, near=50.0):
    """{L: (largest drop over L m of channel within `near` m of the point, distance of that drop from the point)}:
    the same window for a known fall and for a random creek point, so the rates compare."""
    out = {}
    for L in STEPS:
        if z is None or len(z) <= L:
            out[L] = (np.nan, np.nan)
            continue
        dd = z[:-L] - z[L:]
        mid = np.abs(d[L // 2: L // 2 + len(dd)] - at)
        dd = np.where(mid <= near, dd, np.nan)
        if np.isnan(dd).all():
            out[L] = (np.nan, np.nan)
            continue
        i = int(np.nanargmax(dd))
        out[L] = (float(dd[i]), float(mid[i]))
    return out


def dem10_window(area, line):
    x0, y0, x1, y1 = line.buffer(40).bounds
    for p in sorted(glob.glob(f"{ROOT}/data/raw/{area}/*/dem_10m.tif")):
        with rasterio.open(p) as s:
            b = s.bounds
            if b.left <= x0 and b.right >= x1 and b.bottom <= y0 and b.top >= y1:
                w = from_bounds(x0, y0, x1, y1, s.transform)
                return s.read(1, window=w).astype(np.float32), s.window_transform(w)
    return None, None


def sample(area, n_miss, n_found, n_rand):
    crs = epsg(area)
    clip = area_box_union(area)
    K = gpd.read_file(f"{ROOT}/data/raw/{area}/_shared/known_falls.gpkg").to_crs(crs)
    K = K[K.precise.astype(bool) & K.kind.isin(["waterfall", "cascade"]) & K.within(clip)].reset_index(drop=True)
    w = pd.read_csv(f"{ROOT}/output/{area}/waterfall_candidates.csv", low_memory=False)
    w = w[~w.status.isin(["likely DEM artifact", "dam / weir"])]
    pts = np.concatenate([gpd.GeoSeries(gpd.points_from_xy(w.lon, w.lat), crs=4326).to_crs(crs).values,
                          gpd.GeoSeries(gpd.points_from_xy(w.pool_lon, w.pool_lat), crs=4326).to_crs(crs).values])
    found = np.zeros(len(K), bool)
    if len(pts):
        found[np.unique(shapely.STRtree(pts).query(K.geometry.values, predicate="dwithin", distance=100)[0])] = True
    K["group"] = np.where(found, "found by 10 m", "missed by 10 m")
    take = []
    for g, n in (("missed by 10 m", n_miss), ("found by 10 m", n_found)):
        s = K[K.group == g]
        take.append(s.iloc[rng.permutation(len(s))[:n]])
    # random points on NHD-named creeks, 500 m or more from any known fall
    nhd = nhd_lines(area)
    nhd = nhd[nhd.ftype.astype(str).isin(["460", "StreamRiver"]) & nhd.gnis_name.notna()].reset_index(drop=True)
    nhd = nhd[nhd.within(clip)]
    allk = gpd.read_file(f"{ROOT}/data/raw/{area}/_shared/known_falls.gpkg").to_crs(crs)
    kt = shapely.STRtree(allk.geometry.values)
    r = []
    L = nhd.length.to_numpy()
    for _ in range(n_rand * 20):
        if len(r) >= n_rand:
            break
        i = rng.choice(len(nhd), p=L / L.sum())
        g = nhd.geometry.iloc[i]
        p = g.interpolate(rng.uniform(HALF, max(HALF, g.length - HALF)))
        if not len(kt.query(p, predicate="dwithin", distance=500)):
            r.append(dict(name=nhd.gnis_name.iloc[i], kind="random creek point", geometry=p))
    R = gpd.GeoDataFrame(r, geometry="geometry", crs=crs)
    R["group"] = "random creek point"
    return pd.concat(take + [R], ignore_index=True), nhd


def run(area, n_miss, n_found, n_rand):
    crs = epsg(area)
    S, nhd = sample(area, n_miss, n_found, n_rand)
    lines = nhd_lines(area)
    lines = lines[lines.ftype.astype(str).isin(["460", "StreamRiver"])].reset_index(drop=True)
    lt = shapely.STRtree(lines.geometry.values)
    cache = f"{OUT}/cache/{area}"
    os.makedirs(cache, exist_ok=True)
    src_cat = f"{ROOT}/data/raw/{area}/_shared/cache/lidar_catalog.json"
    if os.path.exists(src_cat) and not os.path.exists(f"{cache}/lidar_catalog.json"):
        shutil.copy(src_cat, f"{cache}/lidar_catalog.json")       # read the project's copy, never write it
    W, Sx, E, N = gpd.GeoSeries([area_box_union(area)], crs=crs).to_crs(4326).total_bounds
    cat = lakelidar.catalog((W, Sx, E, N), cache)
    rows = []
    for k, q in enumerate(S.itertuples()):
        row = dict(area=area, group=q.group, name=q.name, kind=q.kind)
        ll = gpd.GeoSeries([q.geometry], crs=crs).to_crs(4326).iloc[0]
        row.update(lat=round(ll.y, 5), lon=round(ll.x, 5))
        j = lt.query(q.geometry, predicate="dwithin", distance=60)
        if not len(j):
            rows.append({**row, "note": "no NHD line within 60 m"})
            continue
        g = lines.geometry.iloc[min(j, key=lambda i: lines.geometry.iloc[i].distance(q.geometry))]
        if g.geom_type == "MultiLineString":
            g = shapely.line_merge(g)
            if g.geom_type == "MultiLineString":
                g = min(g.geoms, key=lambda x: x.distance(q.geometry))
        at = g.project(q.geometry)
        seg = shapely.ops.substring(g, max(0, at - HALF), min(g.length, at + HALF))
        at_seg = seg.project(q.geometry)
        t0 = time.time()
        try:
            got = lakelidar.window(seg.buffer(SNAP + 5), crs, cat, 5, f"{cache}/p{k}.tif")
        except Exception as ex:      # noqa: BLE001  (a dropped connection: note it, go on)
            got, row["note"] = None, f"lidar read failed: {str(ex)[:80]}"
        if got is None:
            rows.append({**row, "note": row.get("note", "no 1 m lidar covering it")})
            continue
        a1, T1, u = got
        z1, d1 = profile_from(a1, T1, seg, SNAP)
        a10, T10 = dem10_window(area, seg)
        z10, d10 = profile_from(a10, T10, seg, 1) if a10 is not None else (None, None)
        m1, m10 = drops(z1, d1, at_seg), drops(z10, d10, at_seg) if z10 is not None else {L: (np.nan, np.nan) for L in STEPS}
        for L in STEPS:
            row[f"lidar_drop_{L}m"], row[f"lidar_at_{L}m"] = round(m1[L][0], 2), (round(m1[L][1]) if m1[L][1] == m1[L][1] else None)
            row[f"dem10_drop_{L}m"] = round(m10[L][0], 2)
        row.update(survey=u["workunit"] if u is not None else None, survey_end=u["end"] if u is not None else None,
                   secs=round(time.time() - t0))
        rows.append(row)
        print(area, k, q.group, q.name, row.get("lidar_drop_10m"), row.get("dem10_drop_10m"), row.get("note", ""), flush=True)
    return rows


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    prev = f"{OUT}/lidar_falls_test.csv"
    done = [x.split(":")[0] for x in sys.argv[1:]]
    allrows = [r for r in pd.read_csv(prev).to_dict("records") if r["area"] not in done] if os.path.exists(prev) else []
    for spec in sys.argv[1:]:
        a, *n = spec.split(":")
        n = [int(x) for x in n] + [15, 8, 8][len(n):]
        allrows += run(a, *n)
        pd.DataFrame(allrows).to_csv(f"{OUT}/lidar_falls_test.csv", index=False)
    d = pd.DataFrame(allrows)
    ok = d[d.lidar_drop_10m.notna()] if "lidar_drop_10m" in d else d.iloc[0:0]
    out = []
    for (a, g), s in ok.groupby(["area", "group"]):
        r = dict(area=a, group=g, points=len(s))
        for thr, L in ((3, 10), (4, 10), (5, 10), (6, 20)):       # all within 50 m of the point
            r[f"1m: {thr} m over {L} m %"] = round(100 * (s[f"lidar_drop_{L}m"] >= thr).mean())
            r[f"10m: {thr} m over {L} m %"] = round(100 * (s[f"dem10_drop_{L}m"] >= thr).mean())
        r["median 1m drop over 10 m (m)"] = round(s.lidar_drop_10m.median(), 1)
        r["median 10m-DEM drop over 10 m (m)"] = round(s.dem10_drop_10m.median(), 1)
        out.append(r)
    t = pd.DataFrame(out)
    t.to_csv(f"{OUT}/lidar_falls_summary.csv", index=False)
    print(t.to_string(index=False))
