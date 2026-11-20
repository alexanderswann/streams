"""Does the D8 routing take each NHD HR line's water where NHD HR does?  (library + command line)

HR lines (StreamRiver 460, Connector 334, ArtificialPath 558) are drawn in their flow direction and split at
confluences, so the network is their end points: a line flows into the lines that start where it ends. For every line
of 150 m+ wholly inside the grid (and not in a lake that ends paths), from the channel cell nearest its middle (most
drainage within 30 m) the D8 path is followed; the line agrees when the path comes within 60 m of its own end or of a
line downstream of it (2 km of NHD's way on). Each line also carries its NHD upstream length (km of HR line upstream
of its end, itself included), a stand-in for its size that doesn't depend on the DEM.
AREA=<area> python hragree.py [root|-] [outcsv]"""
import sys, os, importlib
import numpy as np, pandas as pd, geopandas as gpd, shapely

TOL, SNAP, DOWN_M = 60.0, 3, 2000.0


def network(hr):
    """successors (list of index lists) and upstream length (km) for HR lines (LineStrings in flow direction)."""
    key = lambda p: (round(p[0], 1), round(p[1], 1))
    starts = {}
    for i, g in enumerate(hr.geometry):
        starts.setdefault(key(g.coords[0]), []).append(i)
    succ = [[j for j in starts.get(key(g.coords[-1]), []) if j != i] for i, g in enumerate(hr.geometry)]
    n = len(succ)
    indeg = np.zeros(n, int)
    for s in succ:
        for j in s:
            indeg[j] += 1
    length = hr.length.values / 1000
    up = length.copy()
    todo = [i for i in range(n) if indeg[i] == 0]
    while todo:
        i = todo.pop()
        for j in succ[i]:
            up[j] += up[i]
            indeg[j] -= 1
            if indeg[j] == 0:
                todo.append(j)
    return succ, up


def downstream(i, succ, length_m):
    out, frontier, seen = [], [(i, 0.0)], {i}
    while frontier:
        k, d = frontier.pop()
        for j in succ[k]:
            if j not in seen and d < DOWN_M:
                seen.add(j); out.append(j); frontier.append((j, d + length_m[j]))
    return out


def check(fd, acc, T, hr, inside, lake_u, CODE_SET, DR, DC, res=10):
    """hr: GeoDataFrame of LineStrings in flow direction (all lines, for the network); returns a table per checked line."""
    succ, up = network(hr)
    geoms = hr.geometry.values
    length_m = hr.length.values
    end = shapely.points([g.coords[-1] for g in geoms])
    mid = shapely.line_interpolate_point(geoms, 0.5, normalized=True)
    shapely.prepare(lake_u); shapely.prepare(inside)
    sel = np.flatnonzero((length_m >= 150) & shapely.contains(inside, geoms) & ~shapely.contains(lake_u, mid)
                         & ~shapely.contains(lake_u, end))
    H, W = fd.shape
    inv = ~T
    rows = []
    for i in sel:
        c, r = inv * (mid[i].x, mid[i].y)
        r, c = int(r), int(c)
        w = acc[max(r - SNAP, 0):r + SNAP + 1, max(c - SNAP, 0):c + SNAP + 1]
        k = np.unravel_index(np.argmax(w), w.shape)
        r, c = max(r - SNAP, 0) + k[0], max(c - SNAP, 0) + k[1]
        a_mid = float(acc[r, c]) * res * res / 1e6
        target = shapely.union_all([end[i]] + [geoms[j] for j in downstream(i, succ, length_m)])
        budget = int(3 * length_m[i] / res) + 100
        pts = []
        for _ in range(budget):
            pts.append((c, r))
            kk = int(fd[r, c])
            if kk not in CODE_SET:
                break
            r2, c2 = r + int(DR[kk]), c + int(DC[kk])
            if not (0 <= r2 < H and 0 <= c2 < W) or fd[r2, c2] == 0:
                break
            r, c = r2, c2
        pc = np.array(pts, float)
        xs, ys = T * (pc[:, 0] + 0.5, pc[:, 1] + 0.5)
        dist = shapely.distance(shapely.points(xs, ys), target)
        ok = bool((dist <= TOL).any())
        rows.append(dict(i=int(i), name=hr.gnis_name.iat[i], ftype=int(hr.ftype.iat[i]), len_m=round(length_m[i]),
                         up_km=round(float(up[i]), 1), a_mid=round(a_mid, 2), miss_m=round(float(dist.min())), ok=ok,
                         x=round(mid[i].x), y=round(mid[i].y)))
    t = pd.DataFrame(rows)
    t["size"] = pd.cut(t.up_km, [-1, 2, 10, 50, 1e9], labels=["<2 km", "2-10", "10-50", "50+ km"])
    return t


def summary(t, label):
    s = t.groupby("size", observed=False).agg(lines=("ok", "size"), miss=("ok", lambda x: int((~x).sum())))
    s["miss_pct"] = (100 * s.miss / s.lines).round(1)
    return f"{label}: HR lines checked {len(t)}, D8 misses {int((~t.ok).sum())} ({100 * (~t.ok).mean():.1f} %)\n" + s.T.to_string()


def hr_lines(config):
    parts = []
    for r in config.REGIONS:
        g = gpd.read_file(f"{config.raw_dir(r)}/nhd_flowlines.gpkg")
        parts.append(g[g.ftype.isin([460, 558, 334])].to_crs(config.CRS))
    hr = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=config.CRS)
    hr = hr[~pd.Series(hr.geometry.normalize().to_wkb()).duplicated().values].reset_index(drop=True)
    hr["geometry"] = [shapely.line_merge(shapely.force_2d(g)) for g in hr.geometry]
    return hr[hr.geometry.geom_type == "LineString"].reset_index(drop=True)


if __name__ == "__main__":
    ROOT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else "/Users/mac/Fishing"
    OUT = sys.argv[2] if len(sys.argv) > 2 else None
    sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
    import rasterio, config
    from flowlib import still_water
    st = importlib.import_module("03b_stitch")
    boxes = {r: v["bbox"] for r, v in config.REGIONS.items()}
    x0, y0 = min(b[0] for b in boxes.values()), min(b[1] for b in boxes.values())
    x1, y1 = max(b[2] for b in boxes.values()), max(b[3] for b in boxes.values())
    RES = config.RES
    H, W = int(round((y1 - y0) / RES)), int(round((x1 - x0) / RES))
    T = rasterio.Affine(RES, 0, x0, 0, -RES, y1)
    fd = np.zeros((H, W), np.uint8)
    for r, b in boxes.items():
        r0, c0 = int(round((y1 - b[3]) / RES)), int(round((b[0] - x0) / RES))
        with rasterio.open(f"{config.derived_dir(r)}/flowdir.tif") as src:
            d = src.read(1)
        fd[r0:r0 + d.shape[0], c0:c0 + d.shape[1]] = d
    acc, _ = st.accumulate(fd, st.DR, st.DC)
    inside = shapely.union_all([shapely.box(*b) for b in boxes.values()]).buffer(-100)
    lakes = still_water(tuple(sorted({h for v in config.REGIONS.values() for h in v["hu4"]})), (x0, y0, x1, y1))
    lake_u = shapely.union_all(lakes.geometry.values) if len(lakes) else shapely.Polygon()
    t = check(fd, acc, T, hr_lines(config), inside, lake_u, st.CODE_SET, st.DR, st.DC, RES)
    print(summary(t, f"{config.AREA} ({ROOT})"))
    if OUT:
        t.to_csv(OUT, index=False)
