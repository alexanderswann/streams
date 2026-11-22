"""Read-only: reaches that carry a big river's name beside it, split into (a) the lower end of a tributary (a reach of
another name leads into it along its main stem), (b) side channels (no other name above; the river's own NHD line under
them), (c) lake reaches. AREA=<area> find.py <root> <out csv> [-v]"""
import sys, os
ROOT, OUT = sys.argv[1], sys.argv[2]; V = "-v" in sys.argv
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
RATIO, RIVER_KM2, NEAR_M, ALONG = 10.0, 50.0, 250.0, 0.6
rows = []
parts = []
for b in config.REGIONS:
    d = config.out_dir(b)
    s = gpd.read_file(f"{d}/streams_scored.gpkg")[["sid", "name", "area_km2", "len_m", "geometry"]].to_crs(config.CRS)
    a = pd.read_csv(f"{d}/area_streams.csv").set_index("sid")
    f = pd.read_csv(f"{d}/flow_streams.csv", low_memory=False).set_index("sid")
    s["full"] = s.sid.map(a.area_full_km2); s["cls"] = s.sid.map(f.water_class); s["box"] = b
    parts.append(s)
s = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=config.CRS)
rk = pd.read_csv(f"{config.MAP_OUT}/stream_reaches_ranked.csv", low_memory=False).set_index("sid")
s["fish"] = s.sid.map(rk.fish_score)
geom, name, full = s.geometry.values, s["name"].to_numpy(object), s.full.to_numpy(float)
k = lambda c: (round(c[0], 1), round(c[1], 1))
ends = {}
for i, g in enumerate(geom):
    ends.setdefault(k(g.coords[-1]), []).append(i)
main_up = np.full(len(s), -1)
for i, g in enumerate(geom):
    donors = ends.get(k(g.coords[0]), [])
    if donors:
        main_up[i] = max(donors, key=lambda j: full[j])
# NHD's lines by name (the river's own lines, braids included)
nhd = []
for b in config.REGIONS:
    f_ = f"{config.raw_dir(b)}/nhd_flowlines.gpkg"
    if os.path.exists(f_):
        n_ = gpd.read_file(f_, columns=["gnis_name"]).to_crs(config.CRS)
        nhd.append(n_[n_.gnis_name.notna()])
nhd = pd.concat(nhd, ignore_index=True)
nhd_by = {n: shapely.union_all(g.geometry.values) for n, g in nhd.groupby("gnis_name")}
def on_river(i, river):
    """Share of the main stem from reach i up to its head (30 reaches at most) lying within 150 m of NHD lines named
    `river`, and that stem's length."""
    line = nhd_by.get(river)
    if line is None:
        return 0.0, 0.0
    zone = line.buffer(150)
    tot = inn = 0.0
    j, n_ = i, 0
    while j >= 0 and n_ < 30:
        tot += geom[j].length; inn += geom[j].intersection(zone).length
        j = main_up[j]; n_ += 1
    return inn / max(tot, 1), tot
big = np.flatnonzero(np.array([isinstance(n, str) for n in name]) & (full >= RIVER_KM2))
tree = shapely.STRtree(geom[big])
for i in range(len(s)):
    if not isinstance(name[i], str):
        continue
    near = big[tree.query(geom[i].buffer(NEAR_M))]
    sib = near[(name[near] == name[i]) & (full[near] >= RATIO * full[i])]
    if not len(sib):
        continue
    along = geom[i].intersection(shapely.union_all(shapely.buffer(geom[sib], NEAR_M))).length / max(geom[i].length, 1)
    if along < ALONG:
        continue
    # the first other name up the main stem, within 6 reaches, and how far up
    j, other, steps, up_km2 = main_up[i], None, 0, np.nan
    while j >= 0 and steps < 6:
        steps += 1
        if isinstance(name[j], str) and name[j] != name[i]:
            other, up_km2 = name[j], full[j]; break
        if isinstance(name[j], str) and name[j] == name[i] and full[j] >= RATIO * full[i]:
            break                                  # the river itself comes in above (a reach cut off it)
        j = main_up[j]
    share, stem = on_river(i, name[i])
    kind = ("c lake" if s.cls.iat[i] == "reservoir" else "a tributary end" if other is not None and full[i] <= 3 * up_km2
            else "b side channel" if share >= 0.6 else "d unnamed tributary end")
    ll = gpd.GeoSeries([geom[i].interpolate(0.5, normalized=True)], crs=config.CRS).to_crs(4326).iloc[0]
    rows.append(dict(area=config.AREA, sid=s.sid.iat[i], name=name[i], kind=kind, other=other, km2=round(full[i], 2), river_km2=round(float(full[sib].max()), 1),
                     len_m=round(geom[i].length), along=round(along, 2), fish=s.fish.iat[i], cls=s.cls.iat[i], on_river=round(share, 2), stem_m=round(stem), head=bool(main_up[i] < 0), lat=round(ll.y, 5), lon=round(ll.x, 5)))
t = pd.DataFrame(rows)
t.to_csv(OUT, index=False)
if len(t):
    g = t.groupby("kind").agg(n=("sid", "size"), km=("len_m", lambda x: round(x.sum() / 1000, 1)), med_km2=("km2", "median"), med_fish=("fish", "median"), ge60=("fish", lambda x: int((x >= 60).sum())))
    print(config.AREA, len(t), "candidates"); print(g.to_string())
    if V:
        pd.set_option("display.width", 220); pd.set_option("display.max_rows", 80)
        for kd in ("d unnamed tributary end", "b side channel"):
            print(t[t.kind == kd].sort_values("river_km2", ascending=False).head(14).to_string(index=False))
