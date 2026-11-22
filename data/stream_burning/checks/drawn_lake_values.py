"""What the map draws with a lake's values outside the lakes it draws, in two versions of an area's map data
(map3d_data.js: `streams` is drawn with Lakes on, `streams_lake` only with Lakes off). A line in `streams` reading
"summer: reservoir" is stream line shown as lake water: the measure of creek water marked down by the in-lake rule.
Each such piece with 100+ m outside the drawn lakes is looked up in the other version (the line drawn within 30 m of
its middle): `other_fl` / `other_fs` say what that version shows there. A new piece the old map showed as a creek is
creek line newly marked down; an old piece the new map shows as a creek is one put right.
AREA=<area> python drawn_lake_values.py <old map3d_data.js> <new map3d_data.js> [outcsv]"""
import sys, os, json
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
from flowlib import reservoirs
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
lp = f"{P}/data/derived/{config.AREA}/_shared/lakes.gpkg"
layer = gpd.read_file(lp).to_crs(config.CRS)
layer_u = shapely.union_all(shapely.make_valid(layer.geometry.values))
nhd_u = shapely.union_all(list(shapely.make_valid(reservoirs().geometry.values)))


def load(path):
    t = open(path).read()
    d = json.loads(t[t.index("{"):t.rindex("}") + 1])
    out = {}
    for k in ("streams", "streams_lake"):
        g = gpd.GeoDataFrame.from_features(d[k]["features"], crs=4326).to_crs(config.CRS)
        g["m"] = g.geometry.length
        out[k] = g
    return out


km = lambda s: round(float(s.sum()) / 1000, 1)
rows = []
both = {"old": load(sys.argv[1]), "new": load(sys.argv[2])}
for label in ("old", "new"):
    d = both[label]
    s = d["streams"]
    o = both["new" if label == "old" else "old"]["streams"]
    to = shapely.STRtree(o.geometry.values)
    lk = s[s.fl.fillna("").str.contains("reservoir")].copy()
    lk["out_m"] = shapely.length(shapely.difference(lk.geometry.values, layer_u))
    lk["out_all_m"] = shapely.length(shapely.difference(lk.geometry.values, shapely.union_all([layer_u, nhd_u])))
    c = lk.geometry.to_crs(4326).interpolate(0.5, normalized=True)
    lk["lat"], lk["lon"] = c.y.round(5), c.x.round(5)
    print(f"{config.AREA} {label}: lines drawn with Lakes on {len(s)}, {km(s.m)} km; reading reservoir {len(lk)}, "
          f"{km(lk.m)} km, of that outside the lakes the map draws {km(lk.out_m)} km "
          f"(outside NHD's outlines too: {km(lk.out_all_m)} km); pieces with 100+ m outside the drawn lakes: "
          f"{int((lk.out_m >= 100).sum())}, {km(lk.out_m[lk.out_m >= 100])} km | Lakes-off layer: "
          f"{len(d['streams_lake'])} lines, {km(d['streams_lake'].m)} km")
    lk["other_fl"], lk["other_fs"], lk["other_a"] = None, np.nan, np.nan
    mids = shapely.line_interpolate_point(lk.geometry.values, 0.5, normalized=True)
    q, k = to.query_nearest(mids, max_distance=30, all_matches=False)
    lk.iloc[q, lk.columns.get_loc("other_fl")] = o.fl.values[k]
    lk.iloc[q, lk.columns.get_loc("other_fs")] = o.fs.values[k]
    lk.iloc[q, lk.columns.get_loc("other_a")] = o.a.values[k]
    lk["other_fl"] = lk.other_fl.fillna("no line").str.replace("summer: ", "")
    rows.append(lk.assign(which=label))
    big = lk[lk.out_m >= 100].sort_values("out_m", ascending=False)
    creek = big[~big.other_fl.isin(["reservoir", "no line"])]
    word = "now drawn as a creek (put right)" if label == "old" else "the old map drew as a creek (newly marked down)"
    print(f"   of the 100+ m pieces, {word}: {len(creek)}, {km(creek.out_m)} km; of those with the other "
          f"version's fish score 40+: {int((creek.other_fs >= 40).sum())}, {km(creek.out_m[creek.other_fs >= 40])} km")
    print(big[["n", "d", "a", "o", "fs", "m", "out_m", "out_all_m", "other_fl", "other_fs", "other_a", "lat", "lon"]]
          .head(40).round(1).to_string(index=False) if len(big) else "  none")
if len(sys.argv) > 3:
    pd.concat(rows).drop(columns="geometry")[["which", "n", "d", "a", "o", "fs", "fl", "m", "out_m", "out_all_m",
                                              "other_fl", "other_fs", "other_a", "lat", "lon"]].to_csv(sys.argv[3],
                                                                                                       index=False)
