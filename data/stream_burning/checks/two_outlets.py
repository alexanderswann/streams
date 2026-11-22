"""Lakes with two or more NHD outflow lines the terrain takes the water on from: each candidate's name, how far its
exit is from the terrain's cell, and whether the published map draws a line along its first 300 m.
On the surfaces of a build from before 2026-11-22 (every lake pitted at the terrain's cell): run for all 12 areas on
the published build d16a885 when the rule for lakes with several outlets was chosen (results/root_fix_2026-11-22/).
BEFORE=<build root> BEFORE_MAPS=<maps dir> BUILD=<new build root> AREA=<area> python two_outlets.py <out.csv>"""
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
import numpy as np, pandas as pd, geopandas as gpd, shapely, shapely.ops, rasterio, pyproj
spec = importlib.util.spec_from_file_location("stitch", STITCH); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from config import *
from flowlib import still_water
area = AREA
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
F = layer(open(f"{BEFORE_MAPS}/{area}.js").read(), "streams")
G = gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326).to_crs(CRS).values
GT = shapely.STRtree(G)
# the stream lines of the scratch build's routing (03b's dem_streams.gpkg, every link of 0.25 km2 and the ways out)
import glob
DS = np.concatenate([gpd.read_file(f).to_crs(CRS).geometry.values for f in sorted(glob.glob(f"{BUILD}/data/derived/{area}/*/dem_streams.gpkg"))])
DT = shapely.STRtree(DS)
rows = []
for box in REGIONS:
    with rasterio.open(f"{BEFORE}/data/derived/{area}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    fl = gpd.read_file(f"{raw_dir(box)}/nhd_flowlines.gpkg", columns=["ftype", "gnis_name"])
    fl = fl[fl.ftype.isin(m.LAKE_LINE_FTYPES + m.BUILT_FTYPES)].to_crs(CRS)
    fl = fl[fl.geometry.notna() & ~fl.geometry.is_empty].reset_index(drop=True)
    index = m.outflow_index(fl)
    parts, kinds, tree, begins = index[:4]
    names = []
    for g, nm in zip(shapely.force_2d(fl.geometry.values), fl.gnis_name.values):
        names += [nm if isinstance(nm, str) else ""] * len([q for q in getattr(g, "geoms", [g]) if q.geom_type == "LineString" and q.length > 1])
    assert len(names) == len(parts)
    from collections import defaultdict
    ends = defaultdict(list)
    for i_, q_ in enumerate(parts):
        ends[(round(q_.coords[-1][0]), round(q_.coords[-1][1]))].append(i_)
    wins, wet = {}, np.zeros(fd.shape, bool)
    for k, g in enumerate(lakes.geometry):
        w_ = m.lake_cells(fd, g, T)
        if w_ is not None and w_[2].any():
            wins[k] = w_
    pit = {}
    for k, (r0, c0, mask) in wins.items():
        p = np.argwhere((fd[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] == m.PIT) & mask)
        if len(p):
            pit[k] = (int(p[0][0]) + r0, int(p[0][1]) + c0)
            wet[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] |= mask
    lt = shapely.STRtree(shapely.make_valid(lakes.geometry.values))
    for k, cell in pit.items():
        geom = shapely.make_valid(lakes.geometry.iloc[k])
        cands = [q for q in m.nhd_outlets(fd, geom, T, wins[k], index, m.LAKE_LINE_FTYPES, wet) if q["cells"]]
        if len(cands) < 2:
            continue
        dem = shapely.Point(*(T * (cell[1] + 0.5, cell[0] + 0.5)))
        lk = geom.buffer(30)
        near = min(range(len(cands)), key=lambda i: cands[i]["exit"].distance(dem))
        for i, q in enumerate(cands):
            # the outflow line this exit lies on, and the lines it runs into: names and a chain for the drawn test
            js = [j for j in tree.query(q["exit"].buffer(1.5), predicate="intersects")
                  if kinds[j] in m.LAKE_LINE_FTYPES and lk.contains(shapely.Point(parts[j].coords[0])) and not lk.contains(shapely.Point(parts[j].coords[-1]))]
            nm, ftypes, chain_len, ch, fed = "", [], 0.0, None, ""
            if js:
                c0_ = parts[js[0]].coords[0]
                fed = next((names[x] for x in ends.get((round(c0_[0]), round(c0_[1])), []) if x != js[0] and names[x]), "")
                j = js[0]; cur = parts[j]; seen = {j}; cs = list(cur.coords); nms = [names[j]]; ftypes = [kinds[j]]; chain_len = cur.length
                while chain_len < 900:
                    nx = [x for x in begins.get((round(cur.coords[-1][0]), round(cur.coords[-1][1])), []) if x not in seen]
                    if not nx: break
                    cur = parts[nx[0]]; seen.add(nx[0]); cs += list(cur.coords)[1:]; nms.append(names[nx[0]]); ftypes.append(kinds[nx[0]]); chain_len += cur.length
                nm = next((x for x in nms if x), "")
                first_named = next((n_ for n_, x in enumerate(nms) if x), -1)
                ch = shapely.LineString(cs)
            cov = cov_dem = np.nan
            if ch is not None:
                t0 = ch.project(q["exit"])
                P = shapely.line_interpolate_point(ch, np.arange(t0 + 25, min(ch.length, t0 + 700) + 1, 25.0))
                if len(P):
                    inl = np.zeros(len(P), bool); inl[np.unique(lt.query(P, predicate="dwithin", distance=10.0)[0])] = True
                    P = P[~inl][:12]
                    if len(P) >= 4:
                        a_, b_ = GT.query(P, predicate="dwithin", distance=60.0)
                        cov = round(len(np.unique(a_)) / len(P), 2)
                        a_, b_ = DT.query(P, predicate="dwithin", distance=60.0)
                        cov_dem = round(len(np.unique(a_)) / len(P), 2)
            lon, lat = back.transform(q["exit"].x, q["exit"].y)
            name = lakes.gnis_name.iloc[k]
            rows.append(dict(area=area, box=box, lake=name if isinstance(name, str) else "unnamed", ha=round(geom.area / 1e4, 1), n=len(cands), cand=i,
                             cand_name=nm, own_name=(names[js[0]] if js else ""), fed_name=fed, ftype=(ftypes[0] if ftypes else 0), exit_to_dem_m=round(q["exit"].distance(dem)),
                             cells=len(q["cells"]), on_line=q["on_line"], nearest=i == near, named=bool(q.get("named")), drawn_pub=cov, routed_now=cov_dem, lat=round(lat, 5), lon=round(lon, 5)))
t = pd.DataFrame(rows)
t.to_csv(sys.argv[1], index=False)
print(area, "lakes with 2+ outlets the terrain takes on:", t.groupby(["box", "lake", "ha"]).ngroups if len(t) else 0)
