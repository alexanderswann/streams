"""For every lake (flowlib.reservoirs) with an NHDPlus outlet line: NHDPlus's drainage where the line leaves the lake,
against the full drainage (area_streams.csv) of the reach carrying the most water below the lake: within 150 m of
that spot outside the lake, or of the cell where the build puts the lake's water back in (the link cache's dam
links). NHDPlus's 1:100,000 line can leave the outline hundreds of metres from the outlet (1 km at Spy Lake), and
since 2026-11-22 the water goes on from NHD's detailed outlet, so the first spot alone read a side creek there.
ROOT=<build root, default the project> AREA=adk_northwest python lake_outlets.py <area tables dir or 'project'>"""
import sys, os, json
ROOT = os.environ.get("ROOT", "/Users/mac/Fishing"); sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
import config
from flowlib import reservoirs, FLOW

src = sys.argv[1] if len(sys.argv) > 1 else "project"
wb = reservoirs()
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg").to_crs(config.CRS)
v2 = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"])]
parts = []
for r in config.REGIONS:
    g = gpd.read_file(f"{config.out_dir(r)}/streams_scored.gpkg")[["sid", "name", "geometry"]].to_crs(config.CRS)
    p = f"{config.out_dir(r)}/area_streams.csv" if src == "project" else f"{src}/{r}/area_streams.csv"
    parts.append(g.merge(pd.read_csv(p), on="sid"))
st = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=config.CRS)
tree = shapely.STRtree(st.geometry.values)
# where the build puts each lake's water back in: (the lake's dead end, the cell the water goes on from)
pits, tops = [], []
cache = f"{config.SHARED_DERIVED}/inflows.json"
if os.path.exists(cache):
    for box, dams in json.load(open(cache)).get("dams", {}).items():
        with rasterio.open(f"{config.derived_dir(box)}/flowdir.tif") as s_:
            T_, W_ = s_.transform, s_.width
        for o, row, col in dams:
            pr, pc = divmod(int(o), W_)
            pits.append(shapely.Point(*(T_ * (pc + 0.5, pr + 0.5))))
            tops.append(shapely.Point(*(T_ * (col + 0.5, row + 0.5))))
pit_tree = shapely.STRtree(pits) if pits else None
rows = []
for _, lk in wb.iterrows():
    lake = shapely.make_valid(lk.geometry)
    ins = v2[v2.intersects(lake)]
    if not len(ins):
        continue
    ins = ins[ins.geometry.intersection(lake).length >= 0.25 * ins.length]
    if not len(ins):
        continue
    fl = ins.loc[ins.totdasqkm.idxmax()]
    g = shapely.line_merge(fl.geometry)
    if g.geom_type != "LineString":
        g = shapely.LineString([c for p in g.geoms for c in p.coords])
    inside = g.intersection(lake)
    t_end = max(g.project(shapely.Point(c)) for p in getattr(inside, "geoms", [inside]) for c in p.coords)
    if t_end >= g.length - 1:                       # the line ends at the shore: 100 m down the next line
        by = v2.drop_duplicates("hydroseq").set_index("hydroseq")
        if fl.dnhydroseq not in by.index:
            continue
        g2 = shapely.line_merge(by.loc[fl.dnhydroseq].geometry)
        if g2.geom_type != "LineString":
            g2 = shapely.LineString([c for p in g2.geoms for c in p.coords])
        pt = g2.interpolate(min(100, g2.length))
    else:
        pt = g.interpolate(min(t_end + 100, g.length))
    cand = [i for i in tree.query(pt, predicate="dwithin", distance=150)]
    if pit_tree is not None:
        for k in pit_tree.query(lake.buffer(20), predicate="intersects"):
            cand += [i for i in tree.query(tops[k], predicate="dwithin", distance=150)]
    cand = [i for i in cand if st.geometry.values[i].intersection(lake).length < 0.5 * st.geometry.values[i].length]
    if not cand:
        rows.append(dict(lake=lk.gnis_name, ha=round(lake.area / 1e4, 1), nhd_km2=round(fl.totdasqkm, 1), ours=np.nan, sid=None))
        continue
    # the reach carrying the most water there: the river below the outlet, not a side creek that happens to pass
    # nearer NHDPlus's (1:100,000) line
    i = max(cand, key=lambda i: st.area_full_km2.iat[i])
    rows.append(dict(lake=lk.gnis_name, ha=round(lake.area / 1e4, 1), nhd_km2=round(fl.totdasqkm, 1),
                     ours=st.area_full_km2.iat[i], sid=st.sid.iat[i], reach_name=st.name.iat[i]))
t = pd.DataFrame(rows)
t["ratio"] = (t.ours / t.nhd_km2).round(2)
low = t[((t.ratio < 0.5) & (t.nhd_km2 >= 1)) | t.lake.isin(os.environ.get("SHOW", "").split(","))]
print(f"{config.AREA} ({src}): lakes with an outlet line {len(t)}; below them under half of NHDPlus: {len(low)}")
print(low.sort_values("nhd_km2", ascending=False).to_string(index=False))
