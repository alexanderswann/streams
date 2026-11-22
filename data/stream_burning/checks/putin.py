"""Where crossbox puts each pitted lake's water back in, against the lake's own way out and NHD's outlet.

03b_stitch.py ends a wet lake's paths at one outlet cell (a pit) and makes the D8 path below it a stream line
(outflow_streams): the lake's routed way out. crossbox.py finds where the lake's water goes on separately, by walking
NHDPlus V2's 1:100,000 outlet line from the lake's edge to the first cell whose D8 path doesn't lead back to the pit
(_dam_links), and puts the water in there. Where the two differ, the top of the outlet channel carries none of the
lake's water (under 05_score's floor it isn't drawn) and the water runs down another line: Seventh Lake's 43.5 km2 went
in 555 m from its outlet, in the woods, on 2026-11-21.

For every dam / pond link of the area's link cache (<root>/data/derived/<area>/_shared/inflows.json, read only; it was
written for crossbox VERSION 16's cache):
  pit_to_putin_m        from the pit to the put-in cell
  on_way                the put-in cell lies on the routed way out
  joins_after_m         how far down its own D8 path the put-in's water reaches the way out (empty: not in 30 km)
  down_the_way_m        how much of the way out lies above that point: outlet channel without the lake's water
  putin_to_way_m        from the put-in cell to the nearest cell of the way out's first 6 km (crossbox's _at_outflow
                        moves a put-in to the top of the way out where this is 100 m or less and its path joins it)
  pit_to_hr_outlet_m    from the pit to where a detailed NHD (HR) stream line leaves the lake (a line that starts in
                        the lake and ends outside it); a pit at NHD's outlet says 03b's outlet is right and the put-in
                        is what is off, a pit far from it says 03b's outlet (the lake cell with the most water) is not
                        the lake's outlet: Raquette Lake's sat 9.1 km away, where South Inlet enters
  putin_to_hr_outlet_m  the same for the put-in cell
A put-in under 100 m from the pit that "never joins" is usually this check picking another stream link that starts by
the pit: look before counting it.
AREA=<area> python putin.py <root|-> [out.csv]"""
import sys, os, json
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
import config
from flowlib import reservoirs
ROOT = P if sys.argv[1] == "-" else sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
area = config.AREA
Q = f"{ROOT}/data/derived/{area}"
D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
cache = json.load(open(f"{Q}/_shared/inflows.json"))
lakes = reservoirs()
lg = shapely.make_valid(lakes.geometry.values)
lt = shapely.STRtree(lg)
rows = []
for box, dams in cache["dams"].items():
    with rasterio.open(f"{Q}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    H, W = fd.shape
    km = {(r_, c_): (k, kind) for r_, c_, k, _, kind in cache["full"].get(box, []) if kind in ("dam", "pond")}
    ds = gpd.read_file(f"{Q}/{box}/dem_streams.gpkg").to_crs(config.CRS)
    st = shapely.STRtree(shapely.points([g.coords[0][:2] for g in ds.geometry.values]))
    fl = gpd.read_file(f"{config.raw_dir(box)}/nhd_flowlines.gpkg").to_crs(config.CRS)
    fl = fl[fl.ftype.isin([460, 558, 334]) & fl.geometry.notna()]
    hr = []
    for g in fl.geometry.force_2d().values:
        hr += [x for x in getattr(g, "geoms", [g]) if x.geom_type == "LineString" and x.length > 1]
    ht = shapely.STRtree(hr)

    def path(r, c, n=3000):
        out = []
        for _ in range(n):
            if not (0 <= r < H and 0 <= c < W):
                break
            out.append((r, c))
            d = D8.get(int(fd[r, c]))
            if d is None:
                break
            r, c = r + d[0], c + d[1]
        return out

    done = set()
    for o, row, col in dams:
        pr, pc = divmod(int(o), W)
        if int(fd[pr, pc]) in D8 or (pr, pc) in done:
            continue
        done.add((pr, pc))
        px, py = T * (pc + 0.5, pr + 0.5)
        ex, ey = T * (col + 0.5, row + 0.5)
        k, kind = km.get((row, col), (np.nan, "?"))
        # the routed way out: the stream link that starts beside the pit
        wayset = {}
        n_way = 0
        for i in st.query(shapely.Point(px, py), predicate="dwithin", distance=22):
            c0, r0 = ~T * ds.geometry.values[i].coords[0][:2]
            n_way += 1
            for n_, cell in enumerate(path(int(np.floor(r0)), int(np.floor(c0)))):
                wayset.setdefault(cell, n_)
        own = path(row, col)
        join = next(((n_, wayset[cell]) for n_, cell in enumerate(own) if cell in wayset), None)
        near = [c_ for c_, n_ in wayset.items() if n_ < 600]
        to_way = round(float(np.hypot(*(np.array(near) - (row, col)).T).min() * 10)) if near else np.nan
        # NHD's outlet: where a detailed line that starts in the lake and ends outside it leaves the water
        li = lt.query_nearest(shapely.Point(px, py), max_distance=400)
        name, ha, outs = None, np.nan, []
        if len(li):
            name, core = lakes.gnis_name.iloc[li[0]], lg[li[0]]
            ha, lk = round(core.area / 1e4, 1), core.buffer(30)
            for j in ht.query(lk, predicate="intersects"):
                g = hr[j]
                if lk.contains(shapely.Point(g.coords[-1])) or not lk.contains(shapely.Point(g.coords[0])):
                    continue
                ins = g.intersection(core)
                if ins.is_empty:
                    outs.append(shapely.Point(g.coords[0]))
                else:
                    outs.append(g.interpolate(max(g.project(shapely.Point(c)) for part in getattr(ins, "geoms", [ins])
                                                  if part.geom_type in ("LineString", "Point") for c in part.coords)))
        d_hr = lambda x, y: round(min(shapely.Point(x, y).distance(s) for s in outs)) if outs else np.nan
        rows.append(dict(area=area, box=box, lake=name if isinstance(name, str) else "unnamed", ha=ha, kind=kind, km2=k,
                         pit_to_putin_m=round(float(np.hypot(ex - px, ey - py))), way_out=n_way,
                         on_way=bool(join and join[0] == 0), joins_after_m=(join[0] * 10 if join else np.nan),
                         down_the_way_m=(join[1] * 10 if join else np.nan), putin_to_way_m=to_way, hr_outlets=len(outs),
                         pit_to_hr_outlet_m=d_hr(px, py), putin_to_hr_outlet_m=d_hr(ex, ey),
                         pit_x=px, pit_y=py, putin_x=ex, putin_y=ey))
t = pd.DataFrame(rows)
for k_ in ("pit", "putin"):
    ll = gpd.GeoSeries(gpd.points_from_xy(t[f"{k_}_x"], t[f"{k_}_y"]), crs=config.CRS).to_crs(4326)
    t[f"{k_}_lat"], t[f"{k_}_lon"] = ll.y.round(5).values, ll.x.round(5).values
t = t.drop(columns=["pit_x", "pit_y", "putin_x", "putin_y"])
d = t.down_the_way_m
t["misses"] = np.select([t.on_way, d < 100, d < 200, d.notna()], ["on the way out", "under 100 m", "100-199 m", "200+ m"],
                        "never joins")
t["pit_at"] = np.select([t.pit_to_hr_outlet_m <= 100, t.pit_to_hr_outlet_m.notna()],
                        ["NHD's outlet", "100+ m from it"], "no NHD outlet line")
if OUT:
    t.to_csv(OUT, index=False)
print(f"{area} ({ROOT}): lakes with a link {len(t)}")
print(pd.crosstab(t.misses, t.pit_at, margins=True).to_string())
bad = t[t.misses.isin(["200+ m", "never joins"]) & (t.pit_at == "NHD's outlet") & (t.pit_to_putin_m >= 200)]
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
print(f"\npit at NHD's outlet, put-in 200+ m from it and missing 200+ m of the way out: {len(bad)} ({bad.km2.sum():.0f} km2 carried)")
print(bad.sort_values("km2", ascending=False)[["box", "lake", "ha", "km2", "pit_to_putin_m", "down_the_way_m", "pit_to_hr_outlet_m",
                                               "putin_to_hr_outlet_m", "pit_lat", "pit_lon"]].head(30).to_string(index=False))
far = t[t.pit_to_hr_outlet_m > 300]
print(f"\npit 300+ m from NHD's outlet: {len(far)} ({far.ha.sum():.0f} ha of lake)")
print(far.sort_values("ha", ascending=False)[["box", "lake", "ha", "km2", "pit_to_hr_outlet_m", "putin_to_hr_outlet_m", "pit_lat",
                                              "pit_lon"]].head(20).to_string(index=False))
