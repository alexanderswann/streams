"""Read-only. For one area's build (ROOT: the project or a scratch root): each reach's length inside the lakes the
Lakes layer draws, inside the layer's lakes 05b counts (8 ha+, level in lidar), and inside NHD's lakes (reservoirs()),
with 05b's flag. Totals: creek scored as lake (flagged "in:", outside every drawn lake) and lake scored as creek.
AREA=<area> lake_shares.py <root> <out.csv>"""
import os, sys
ROOT, OUTCSV = sys.argv[1], sys.argv[2]
sys.path.insert(0, "/Users/mac/Fishing/scripts")
import warnings; warnings.filterwarnings("ignore")
import shapely, numpy as np, pandas as pd, geopandas as gpd
import config
from config import REGIONS, EPSG, AREA
import flowlib
rows = []
for r in REGIONS:
    d = f"{ROOT}/output/{AREA}/{r}"
    s = gpd.read_file(f"{d}/streams_scored.gpkg").to_crs(EPSG)
    fl = pd.read_csv(f"{d}/flow_streams.csv", low_memory=False).set_index("sid")
    ar = pd.read_csv(f"{d}/area_streams.csv").set_index("sid")
    s["below_dam"] = s.sid.map(fl.below_dam)
    s["water_class"] = s.sid.map(fl.water_class)
    s["flow_src"] = s.sid.map(fl.flow_src)
    s["af"] = s.sid.map(ar.area_full_km2).fillna(s.area_km2)
    rows.append(s[["sid", "name", "area_km2", "af", "order", "flow", "below_dam", "water_class", "flow_src", "geometry"]])
s = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs=EPSG)
lk = gpd.read_file(f"{ROOT}/data/derived/{AREA}/_shared/lakes.gpkg").to_crs(EPSG)
lk["geometry"] = shapely.make_valid(lk.geometry.values)
note = lk.water_note.fillna("").astype(str).str.strip().str.lower()
big = (lk.lidar_kind.isin(["flattened", "level, not flattened"]) & ~note.str.startswith("little level water")
       & ~note.str.contains("drawn down|drained") & ~lk.intermittent.fillna(False).astype(bool)
       & ~lk["name"].fillna("").str.contains("Lagoon") & (lk.ha.fillna(lk.geometry.area / 1e4) >= 8))
wb = flowlib.reservoirs().to_crs(EPSG)
wb["geometry"] = shapely.make_valid(wb.geometry.values)
def inside(lines, polys):
    """Length of each line inside the union of polys."""
    out = np.zeros(len(lines))
    if not len(polys):
        return out
    tree = shapely.STRtree(polys)
    li, pi = tree.query(lines, predicate="intersects")
    if len(li):
        U = pd.Series(list(polys[pi])).groupby(li).agg(lambda x: shapely.union_all(list(x)))
        out[U.index.values] = shapely.length(shapely.intersection(lines[U.index.values], U.values))
    return out
g = s.geometry.values
s["len_m"] = shapely.length(g)
s["in_drawn"] = inside(g, lk.geometry.values)
s["in_big"] = inside(g, lk.geometry.values[big.values])
s["in_nhd"] = inside(g, wb.geometry.values)
s["flag"] = s.below_dam.fillna("").astype(str).str.startswith("in:")
s.drop(columns="geometry").to_csv(OUTCSV, index=False)
f = s[s.flag]; n = s[~s.flag]
out_m = f.len_m - f.in_drawn
print(f"{AREA:15s} reaches {len(s):6d} | flagged in-lake {len(f):5d} ({f.len_m.sum()/1000:7.1f} km), outside every drawn lake "
      f"{out_m.sum()/1000:6.1f} km: {int((out_m >= 100).sum()):4d} reaches with 100+ m outside ({out_m[out_m >= 100].sum()/1000:6.1f} km), "
      f"{int((f.in_drawn < 1).sum()):3d} untouched by a drawn lake | not flagged: {n.in_big.sum()/1000:6.1f} km inside counted lakes "
      f"({int((n.in_big >= 100).sum())} reaches with 100+ m), {n.in_drawn.sum()/1000:6.1f} km inside any drawn lake")
