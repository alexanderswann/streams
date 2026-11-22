"""Read-only: where crossbox puts a lake's water back in (the cell below the dam, found along NHDPlus's or NHD's
outlet line) against the routing's own way out of the lake (the outlet pit's steepest-descent neighbour on the
conditioned DEM, the start of 03b's outflow stream line): how far down the outflow line the carried water first
appears. AREA=<area> landing.py <root> [-v]"""
import sys, os, json
ROOT = sys.argv[1]; V = "-v" in sys.argv
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, rasterio, geopandas as gpd, shapely
import config, crossbox
CODES = (64, 128, 1, 2, 4, 8, 16, 32); OFFS = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
D8 = crossbox.D8
data = json.load(open(crossbox.CACHE))
rows = []
for b in config.REGIONS:
    dams = data.get("dams", {}).get(b, [])
    if not dams:
        continue
    with rasterio.open(crossbox.fdir_path(b)) as src:
        fd = src.read(1); T = src.transform
    with rasterio.open(f"{config.derived_dir(b)}/dem_cond.tif") as src:
        z = src.read(1)
    with rasterio.open(f"{config.derived_dir(b)}/area_km2.tif") as src:
        area = src.read(1)
    H, W = fd.shape
    full = {}
    for row, col, km2, *_ in data["full"].get(b, []):
        full[(row, col)] = full.get((row, col), 0) + km2
    def path(r, c, n=600):
        out = []
        for _ in range(n):
            out.append((r, c))
            d = D8.get(int(fd[r, c]))
            if d is None or not (0 <= r + d[0] < H and 0 <= c + d[1] < W):
                break
            r, c = r + d[0], c + d[1]
        return out
    # one lake's dead ends share a landing cell: its outlet is the dead end holding the most water
    grp = {}
    for o, lr, lc in dams:
        grp.setdefault((lr, lc), []).append(int(o))
    main = {(lr, lc): max(os_, key=lambda o: float(area.flat[o])) for (lr, lc), os_ in grp.items()}
    deadset = {(lr, lc): set(os_) for (lr, lc), os_ in grp.items()}
    for (lr, lc), o in main.items():
        pr, pc = divmod(int(o), W)
        if int(fd[pr, pc]) != 254 or not (0 < pr < H - 1 and 0 < pc < W - 1):
            continue                                    # a flat or a rim cell, not a lake's outlet pit
        best, nb = -np.inf, None
        for (dr, dc) in OFFS:
            s = (z[pr, pc] - z[pr + dr, pc + dc]) / (config.RES * (2 ** 0.5 if dr and dc else 1))
            if s > best:
                best, nb = s, (pr + dr, pc + dc)
        if nb is None or best <= 0:
            rows.append(dict(box=b, o=int(o), km2=full.get((lr, lc), np.nan), kind="no way out on the DEM", m=np.nan)); continue
        out_path = path(*nb, n=3000)
        end = out_path[-1][0] * W + out_path[-1][1]
        if end in deadset[(lr, lc)]:
            rows.append(dict(box=b, o=int(o), km2=round(full.get((lr, lc), np.nan), 1), kind="the routed way out leads back into the lake", m=np.nan)); continue
        out_path = out_path[:600]
        land_path = path(lr, lc)
        pos = {rc: i for i, rc in enumerate(out_path)}
        j = next((pos[rc] for rc in land_path if rc in pos), None)
        x, y = T * (pc + 0.5, pr + 0.5)
        ll = gpd.GeoSeries([shapely.Point(x, y)], crs=config.CRS).to_crs(4326).iloc[0]
        if j is None:
            kind, m = ("the landing's path never meets the outflow line (600 cells)", np.nan)
        else:
            m = j * config.RES
            kind = "on the outflow line" if (lr, lc) in pos else "joins the outflow line"
        op = np.array(out_path)
        side = float(np.hypot(op[:, 0] - lr, op[:, 1] - lc).min() * config.RES)        # the landing cell's distance from the outflow line
        rows.append(dict(box=b, o=int(o), km2=round(full.get((lr, lc), np.nan), 1), kind=kind, m=m, lat=round(ll.y, 5), lon=round(ll.x, 5),
                         land_m=round(np.hypot(lr - pr, lc - pc) * config.RES), side_m=round(side)))
t = pd.DataFrame(rows)
if not len(t):
    print(config.AREA, "no dam links"); sys.exit()
big = t[t.km2 >= 1]
q = big.m.dropna()
print(f"{config.AREA:15s} lake outlets with a link {len(t):4d} (1+ km2: {len(big)}) | water first on the outflow line: at its start to 50 m {int((q <= 50).sum())}, "
      f"50-100 m {int(((q > 50) & (q <= 100)).sum())}, 100-300 m {int(((q > 100) & (q <= 300)).sum())}, 300+ m {int((q > 300).sum())}, never {int(big.m.isna().sum())} "
      f"| median {q.median():.0f} m, p90 {q.quantile(0.9):.0f} m")
mv = big[big.m.notna() & (big.side_m <= 100) & (big.m > 20)]
far = big[big.m.notna() & (big.side_m > 100)]
print(f"   landing on or within 100 m of the outflow line and joining it: {int((big.m.notna() & (big.side_m <= 100)).sum())} (water would move up {mv.m.sum()/1000:.1f} km in all at {len(mv)} outlets; "
      f"100+ m up at {int((mv.m >= 100).sum())}); landing over 100 m from it: {len(far)} joining, {int(big.m.isna().sum())} never meeting or leading back (kept as they are)")
if V:
    pd.set_option("display.width", 220)
    print(big[(big.m > 300) | big.m.isna()].sort_values("km2", ascending=False).head(40).to_string(index=False))
