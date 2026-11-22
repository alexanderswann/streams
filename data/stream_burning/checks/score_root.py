"""Fish scores for a scratch build, as 06_map.py would give them, without rerunning the late steps: each new reach takes
the access (08), sun (10) and context (11) values of the project's reach it lies on (the one nearest its middle, within
30 m; else within 200 m), and its own area (05c), flow (05b) and reach attributes (05_score). Those late values are
properties of the place, not of the routing. Writes the root's output/<area>/stream_reaches_ranked.csv (06_map's
columns) and prints how the reaches were matched.  AREA=<area> python score_root.py <root>"""
import sys, os, shutil
ROOT = sys.argv[1]
P = os.environ.get("LATE_ROOT", "/Users/mac/Fishing")      # where the late values (08, 10, 11) are taken from, by place
import os.path as _op
if _op.realpath(ROOT) == _op.realpath(P):
    raise SystemExit("score_root.py writes tables into the root's output/: never on the project")
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
from scoring import attach, score
regions = list(config.REGIONS)
new = pd.concat([gpd.read_file(f"{config.out_dir(r)}/streams_scored.gpkg") for r in regions], ignore_index=True)
new = gpd.GeoDataFrame(new, crs=4326)
pout = lambda r: f"{P}/output/{config.AREA}/{r}"
old = gpd.GeoDataFrame(pd.concat([gpd.read_file(f"{pout(r)}/streams_scored.gpkg")[["sid", "geometry"]] for r in regions],
                                 ignore_index=True), crs=4326)
late = {k: pd.concat([pd.read_csv(f"{pout(r)}/{k}_streams.csv") for r in regions], ignore_index=True)
        for k in ("hike", "sun", "context")}
n_p, o_p = new.to_crs(config.CRS), old.to_crs(config.CRS)
same = len(new) == len(old) and (new.sid.values == old.sid.values).all() and \
       bool(shapely.equals_exact(n_p.geometry.values, o_p.geometry.values, 0.01).all())
if same:
    match = pd.DataFrame({"sid": new.sid, "old": old.sid, "d": 0.0})
    print("reaches identical to the project's: values taken by sid")
else:
    mid = shapely.line_interpolate_point(n_p.geometry.values, 0.5, normalized=True)
    tree = shapely.STRtree(o_p.geometry.values)
    idx, dist = tree.query_nearest(mid, max_distance=200, return_distance=True, all_matches=False)
    k = np.full(len(new), -1); d = np.full(len(new), np.inf)
    k[idx[0]] = idx[1]; d[idx[0]] = dist
    match = pd.DataFrame({"sid": new.sid, "old": np.where(k >= 0, old.sid.values[np.maximum(k, 0)], None), "d": d})
    print(f"reaches {len(new)} (project {len(old)}); matched within 30 m {int((d <= 30).sum())}, "
          f"30-200 m {int(((d > 30) & (d <= 200)).sum())}, none within 200 m {int(np.isinf(d).sum())}")
for r in regions:
    mine = match[match.sid.str.startswith(r + ":")]
    for k_, t in late.items():
        m = mine[["sid", "old"]].merge(t.rename(columns={"sid": "old"}), on="old", how="left").drop(columns="old")
        m.to_csv(f"{config.out_dir(r)}/{k_}_streams.csv", index=False)
    if os.path.exists(f"{pout(r)}/trailheads.gpkg") and os.path.abspath(pout(r)) != os.path.abspath(config.out_dir(r)):
        shutil.copy(f"{pout(r)}/trailheads.gpkg", f"{config.out_dir(r)}/trailheads.gpkg")
dirs = [config.out_dir(r) for r in regions]
s = score(attach(new.drop(columns="fish_score"), "sid", dirs, "streams"))
s["area_rank_pct"] = ((s.fish_score.rank(method="min") - 1) / max(len(s) - 1, 1) * 100).round(0)
sd = pd.concat([pd.read_csv(f"{d}/stream_drainage.csv") for d in dirs], ignore_index=True)
s = s.drop(columns=[c for c in ("drainage", "fork", "strahler") if c in s]).merge(sd, on="sid", how="left")
s["drainage"] = s.drainage.fillna(config.MINOR); s["fork"] = s.fork.fillna(s.drainage)
s["strahler"] = s.strahler.fillna(s["order"]).clip(1, 7).astype(int)
mid = s.geometry.interpolate(0.5, normalized=True)
s = s.assign(lat=mid.y.round(6), lon=mid.x.round(6), match_old=match.set_index("sid").old.reindex(s.sid).values,
             match_m=match.set_index("sid").d.reindex(s.sid).values)
cols = ["sid", "region", "drainage", "fork", "name", "flow", "water_class", "dry_cfs", "dry_cfs_drought", "flow_years",
        "flow_src", "below_dam", "below_div", "div_share", "div_years", "water_by_gauge", "water_term", "fish_score",
        "thermal", "water_aug", "tailwater", "burn_factor", "trout_factor", "heat_factor", "channel_factor",
        "area_rank_pct", "area_km2", "area_edge_km2", "area_full_km2", "strahler", "elev_m", "gradient_pct", "len_m",
        "approach_med_min", "bike_med_min", "lat", "lon", "match_old", "match_m", "water_rule", "gauge_name", "gauge_share",
        "green_p90", "trout_water", "trout_found"]
s.sort_values("fish_score", ascending=False)[[c for c in cols if c in s]].to_csv(f"{config.MAP_OUT}/stream_reaches_ranked.csv", index=False)
print("wrote", f"{config.MAP_OUT}/stream_reaches_ranked.csv", len(s))
