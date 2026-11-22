"""Each lake 03b leaves at the terrain's cell though NHD has an outflow line: what the terrain does along each of
NHD's outflow lines. Lake level = median raw-DEM height of the lake's cells; along the line (to 1.5 km): the highest
ground above that level and where the line first drops 0.5 m below the level for good; how many of the cells within
300 m lead back into the lake. The lakes come from BUILD's lake_outlets.json ("kept"), the replay runs on BEFORE's
surface. BEFORE=<build root> BUILD=<new build root> AREA=<area> python kept_explain.py"""
import sys, json, importlib.util
# Paths: BEFORE = a build root from before 2026-11-22 (its data/derived/<area>/<box>/flowdir.tif has every lake's pit at
# the cell with the most water; the candidates are replayed on that surface), BEFORE_MAPS = a folder with that build's
# <area>.js map data, BUILD = the build root to read the new routing from, STITCH = the 03b_stitch.py to replay.
import os
P = "/Users/mac/Fishing"
BEFORE = os.environ.get("BEFORE", P)
BEFORE_MAPS = os.environ.get("BEFORE_MAPS", f"{P}/output")
BUILD = os.environ.get("BUILD", P)
STITCH = os.environ.get("STITCH", f"{P}/scripts/03b_stitch.py")
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, shapely, shapely.ops, pyproj
spec = importlib.util.spec_from_file_location("stitch", STITCH); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from config import *
from flowlib import still_water
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
lo = json.load(open(f"{BUILD}/data/derived/{AREA}/_shared/lake_outlets.json"))
for box, rows in lo.get("kept", {}).items():
    if not rows:
        continue
    with rasterio.open(f"{BEFORE}/data/derived/{AREA}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    with rasterio.open(f"{raw_dir(box)}/dem_10m.tif") as src:
        z = src.read(1).astype(float)
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    index = m.outflow_index(m.nhd_lines([box], m.LAKE_LINE_FTYPES + m.BUILT_FTYPES))
    parts, kinds, tree, begins, named = index
    wet = np.zeros(fd.shape, bool)
    for g in lakes.geometry:
        w_ = m.lake_cells(fd, g, T)
        if w_ is not None and w_[2].any():
            r0, c0, mask = w_
            if ((fd[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] == m.PIT) & mask).any():
                wet[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] |= mask
    for name, ha, why, x, y in rows:
        d = lakes.distance(shapely.Point(x, y))
        k = int(np.argmin(d.values)); geom = shapely.make_valid(lakes.geometry.iloc[k])
        win = m.lake_cells(fd, geom, T); r0, c0, mask = win
        level = float(np.median(z[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]][mask]))
        lon, lat = back.transform(x, y)
        print(f"{AREA}/{box} {name} ({ha:g} ha), terrain's cell {lat:.5f},{lon:.5f}, level {level:.1f} m: {why}")
        lk = geom.buffer(30)
        for j in tree.query(lk, predicate="intersects"):
            g = parts[j]
            if kinds[j] not in m.LAKE_LINE_FTYPES + m.BUILT_FTYPES:
                continue
            if lk.contains(shapely.Point(g.coords[-1])) or not lk.contains(shapely.Point(g.coords[0])):
                continue
            ins = g.intersection(geom)
            t0 = 0.0 if ins.is_empty else max(g.project(shapely.Point(xy)) for q in getattr(ins, "geoms", [ins]) if q.geom_type in ("LineString", "Point") for xy in q.coords)
            chain, cur, seen, length = [shapely.ops.substring(g, t0, g.length)], g, {j}, g.length - t0
            while length < 1500:
                nx = [q for q in begins.get((round(cur.coords[-1][0]), round(cur.coords[-1][1])), []) if q not in seen]
                if not nx: break
                cur = parts[nx[0]]; seen.add(nx[0]); chain.append(cur); length += cur.length
            ch = shapely.LineString([c for part in chain for c in part.coords])
            ds = np.arange(0, min(ch.length, 1500), 5.0)
            hs, back_n, n300, wet_at = [], 0, 0, None
            for dd in ds:
                p = ch.interpolate(dd); cc, rr = ~T * (p.x, p.y); rc = (int(np.floor(rr)), int(np.floor(cc)))
                if not (0 <= rc[0] < z.shape[0] and 0 <= rc[1] < z.shape[1]):
                    break
                hs.append(z[rc])
                ins_ = 0 <= rc[0] - r0 < mask.shape[0] and 0 <= rc[1] - c0 < mask.shape[1] and mask[rc[0] - r0, rc[1] - c0]
                if dd <= 300 and not ins_:
                    n300 += 1
                    back_n += m.leads_back(fd, rc[0], rc[1], win)
                    if wet_at is None and wet[rc]:
                        wet_at = dd
            hs = np.array(hs)
            if not len(hs):
                ex = ch.interpolate(0); elon, elat = back.transform(ex.x, ex.y)
                print(f"   NHD outflow line (type {kinds[j]}) leaving at {elat:.5f},{elon:.5f}, {shapely.Point(x, y).distance(ex):.0f} m from the terrain's cell: "
                      f"{ch.length:.0f} m long, off this box's grid at once")
                continue
            below = np.flatnonzero(hs < level - 0.5)
            stay = next((i for i in below if (hs[i:] < level + 0.3).all()), None)
            ex = ch.interpolate(0); elon, elat = back.transform(ex.x, ex.y)
            print(f"   NHD outflow line (type {kinds[j]}{', named' if named[j] else ''}) leaving at {elat:.5f},{elon:.5f}, {shapely.Point(x, y).distance(ex):.0f} m from the terrain's cell; "
                  f"followed {len(hs) * 5} m: highest ground {hs.max() - level:+.1f} m against the lake at {int(np.argmax(hs)) * 5} m; "
                  f"{'below the lake for good from ' + str(stay * 5) + ' m' if stay is not None else 'never stays below the lake'}; "
                  f"within 300 m {back_n} of {n300} cells lead back into the lake" + (f"; another lake's water at {wet_at:.0f} m" if wet_at is not None else ""))
