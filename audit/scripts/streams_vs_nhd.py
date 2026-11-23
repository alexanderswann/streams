#!/usr/bin/env python3
"""Is the creek there, and is it where NHD says? Drawn stream lines of the published maps against NHD HR flowlines.

Read-only. For each area:
  omission    NHD HR stream lines (named streams first) with no drawn line within 50 m / 150 m. A stretch with nothing
              drawn within 150 m is split by the pipeline's own drainage raster at that spot: under the 1 km2 size
              floor (a headwater the map leaves out by design) or 1 km2+ (routed there, not drawn).
  commission  drawn line (the default layer, outside lakes) with no NHD line of any kind within 50 m / 150 m.
  course      distance from drawn line to the nearest NHD line where one lies within 150 m (median, 90th percentile).
Tables: audit/tables/streams_vs_nhd.csv, streams_vs_nhd_missing.csv (named NHD streams not drawn, worst first),
streams_vs_nhd_extra.csv (drawn fish-60+ reaches with no NHD line near, longest first).
    SITE_DIR=<folder of published maps> python audit/scripts/streams_vs_nhd.py [area ...]
"""
import sys, os, csv
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import *
import shapely, rasterio, pyproj

STREAM_FT = {460, "460", "StreamRiver"}
PATH_FT = {558, "558", "ArtificialPath"}
PEREN, INTER, EPHEM = {46006, "46006"}, {46003, "46003"}, {46007, "46007"}


def d8_area_near(area, x, y, win=6):
    """Largest drainage area (km2) of the pipeline's raster within win cells (60 m) of each point; nan off the boxes."""
    out = np.full(len(x), np.nan)
    for r, b in boxes(area).items():
        p = f"{ROOT}/data/derived/{area}/{r}/area_km2.tif"
        if not os.path.exists(p):
            continue
        x0, y0, x1, y1 = b["bbox"]
        m = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
        if not m.any():
            continue
        with rasterio.open(p) as src:
            a = src.read(1)
            rows, cols = rasterio.transform.rowcol(src.transform, x[m], y[m])
            rows, cols = np.asarray(rows), np.asarray(cols)
            best = np.full(m.sum(), np.nan)
            for dr in range(-win, win + 1):
                for dc in range(-win, win + 1):
                    rr, cc = rows + dr, cols + dc
                    ok = (rr >= 0) & (rr < a.shape[0]) & (cc >= 0) & (cc < a.shape[1])
                    v = np.full(m.sum(), np.nan)
                    v[ok] = a[rr[ok], cc[ok]]
                    best = np.fmax(best, v)
            out[m] = best
    return out


def runs(idx_line, flag, ln, x, y):
    """Longest run of flagged pieces per line: {line: (metres flagged in all, x, y of the middle of the longest run)}."""
    out = {}
    order = np.arange(len(flag))
    cur, best = {}, {}
    start = 0
    n = len(flag)
    i = 0
    while i < n:
        if not flag[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flag[j + 1] and idx_line[j + 1] == idx_line[i]:
            j += 1
        L = ln[i:j + 1].sum()
        k = idx_line[i]
        tot, bl, bx, by = out.get(k, (0.0, 0.0, None, None))
        mid = (i + j) // 2
        if L > bl:
            bl, bx, by = L, x[mid], y[mid]
        out[k] = (tot + L, bl, bx, by)
        i = j + 1
    return out


def main(areas):
    rows, missing, extra = [], [], []
    for a in areas:
        to_ll = pyproj.Transformer.from_crs(epsg(a), 4326, always_xy=True)
        nhd = nhd_lines(a)
        clip = area_box_union(a)
        nhd = nhd[nhd.intersects(clip)].reset_index(drop=True)
        ft, fc = nhd["ftype"].tolist(), nhd["fcode"].tolist()
        is_stream = np.array([f in STREAM_FT for f in ft])
        is_path = np.array([f in PATH_FT for f in ft])
        named = nhd["gnis_name"].notna().to_numpy() & (nhd["gnis_name"].astype(str).str.len() > 0).to_numpy()
        peren = np.array([c in PEREN for c in fc])
        inter = np.array([c in INTER or c in EPHEM for c in fc])

        drawn = streams_gdf(a, "streams")
        lake = streams_gdf(a, "streams_lake")
        any_drawn = np.concatenate([drawn.geometry.values, lake.geometry.values])

        # ---- omission: NHD pieces against any drawn line
        nx, ny, nl, ni = seg_midpoints(nhd.geometry.values)
        inside = shapely.contains_xy(clip, nx, ny)
        nx, ny, nl, ni = nx[inside], ny[inside], nl[inside], ni[inside]
        d, _ = nearest_dist(nx, ny, any_drawn, 400)
        far = d > 150
        d8 = np.full(len(nx), np.nan)
        d8[far] = d8_area_near(a, nx[far], ny[far])
        below = far & (d8 < 1.0)                       # nothing drawn and the terrain routing has under 1 km2 there
        notdrawn = far & ~(d8 < 1.0)

        def om(mask_lines, label):
            m = mask_lines[ni]
            tot = nl[m].sum()
            if tot == 0:
                return
            rows.append(dict(area=a, side="NHD not drawn", cls=label, total_mi=tot / MI,
                             within50_pct=100 * nl[m & (d <= 50)].sum() / tot,
                             within150_pct=100 * nl[m & (d <= 150)].sum() / tot,
                             absent_below_floor_pct=100 * nl[m & below].sum() / tot,
                             absent_1km2_plus_pct=100 * nl[m & notdrawn].sum() / tot,
                             absent_1km2_plus_mi=nl[m & notdrawn].sum() / MI))
        om(is_stream & named, "named stream lines")
        om(is_stream & named & peren, "named perennial stream lines")
        om(is_path & named, "named river/lake centrelines")
        om(is_stream & ~named & peren, "unnamed perennial stream lines")
        om(is_stream & ~named & inter, "unnamed intermittent/ephemeral lines")

        # worst named streams: by name, the length with nothing drawn within 150 m where 1 km2+ is routed
        m = (is_stream | is_path)[ni] & named[ni]
        rr = runs(ni[m], notdrawn[m], nl[m], nx[m], ny[m])
        by_name = {}
        for k, (tot, bl, bx, by) in rr.items():
            nm = nhd["gnis_name"].iat[k]
            t = by_name.setdefault(nm, [0.0, 0.0, None, None])
            t[0] += tot
            if bl > t[1]:
                t[1], t[2], t[3] = bl, bx, by
        for nm, (tot, bl, bx, by) in by_name.items():
            if tot >= 300:
                lon, lat = to_ll.transform(bx, by)
                missing.append(dict(area=a, nhd_name=nm, not_drawn_mi=round(tot / MI, 2), longest_gap_mi=round(bl / MI, 2),
                                    lat=round(lat, 5), lon=round(lon, 5)))

        # ---- commission and course: drawn default-layer pieces against any NHD line
        dx, dy, dl, di = seg_midpoints(drawn.geometry.values)
        dd, _ = nearest_dist(dx, dy, nhd.geometry.values, 400)
        fs = drawn["fs"].to_numpy(float)[di]
        o = drawn["o"].to_numpy(float)[di]
        fl = drawn["fl"].astype(str).to_numpy()[di]

        def com(mask, label):
            tot = dl[mask].sum()
            if tot == 0:
                return
            near = mask & (dd <= 150)
            rows.append(dict(area=a, side="drawn, no NHD line", cls=label, total_mi=tot / MI,
                             within50_pct=100 * dl[mask & (dd <= 50)].sum() / tot,
                             within150_pct=100 * dl[near].sum() / tot,
                             absent_1km2_plus_pct=100 * dl[mask & (dd > 150)].sum() / tot,
                             absent_1km2_plus_mi=dl[mask & (dd > 150)].sum() / MI,
                             offset_median_ft=float(np.median(np.repeat(dd[near], np.maximum(1, (dl[near] // 5).astype(int)))) / FT) if near.any() else np.nan,
                             offset_p90_ft=float(np.quantile(dd[near], 0.9) / FT) if near.any() else np.nan))
        allm = np.ones(len(dl), bool)
        com(allm, "all drawn (default layer)")
        com(fs >= 60, "drawn, fish 60+")
        com(o >= 3, "drawn, order 3+")
        com((fs >= 60) & (o >= 3), "drawn, fish 60+ and order 3+")
        com(np.char.find(fl.astype(str), "unmapped") >= 0, "drawn, flagged 'NHD unmapped'")

        # worst extras: fish-60+ reaches with over half their length more than 150 m from any NHD line
        far_len = np.bincount(di, weights=dl * (dd > 150), minlength=len(drawn))
        tot_len = np.bincount(di, weights=dl, minlength=len(drawn))
        for i in np.where((far_len > 0.5 * tot_len) & (drawn["fs"].to_numpy(float) >= 60) & (tot_len >= 400))[0]:
            p = drawn.iloc[i]
            extra.append(dict(area=a, name=p["n"], drainage=p["d"], order=p["o"], fish=p["fs"], flow=p["fl"],
                              sq_mi=round(float(p["a"]) / 2.58999, 2), drawn_mi=round(tot_len[i] / MI, 2),
                              lat=p["y"], lon=p["x"]))
        print(a, "done", flush=True)

    df = pd.DataFrame(rows)
    df.insert(0, "site", site_name())
    df.round(2).to_csv(f"{TABLES}/streams_vs_nhd.csv", index=False)
    pd.DataFrame(missing, columns=["area", "nhd_name", "not_drawn_mi", "longest_gap_mi", "lat", "lon"]).sort_values(
        "not_drawn_mi", ascending=False).to_csv(f"{TABLES}/streams_vs_nhd_missing.csv", index=False)
    pd.DataFrame(extra, columns=["area", "name", "drainage", "order", "fish", "flow", "sq_mi", "drawn_mi", "lat", "lon"]).sort_values(
        "drawn_mi", ascending=False).to_csv(f"{TABLES}/streams_vs_nhd_extra.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    print(df.round(1).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
