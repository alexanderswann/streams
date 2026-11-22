"""Before / after on one area: the reaches of build B (a scratch root) matched to build A's (the project or another root)
by place (B's reach middle within 30 m of A's reach), and how their drainage, flow class and fish score moved; the
fish-score distribution of each.  AREA=<area> python compare_roots.py <rootA|-> <rootB> [outcsv]"""
import sys, os
A = sys.argv[1] if sys.argv[1] != "-" else "/Users/mac/Fishing"
B = sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, f"{B}/scripts"); os.chdir(f"{B}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
def load(root):
    rk = pd.read_csv(f"{root}/output/{config.AREA}/stream_reaches_ranked.csv", low_memory=False)
    rk = rk[~rk.sid.astype(str).str.contains("+", regex=False)]   # 06_map's drawn-through pieces
    g = pd.concat([gpd.read_file(f"{root}/output/{config.AREA}/{r}/streams_scored.gpkg")[["sid", "geometry"]]
                   for r in config.REGIONS], ignore_index=True)
    g = gpd.GeoDataFrame(g, crs=4326).to_crs(config.CRS).merge(rk, on="sid")
    g["af"] = g.area_full_km2.fillna(g.area_km2)
    return g
a, b = load(A), load(B)
def dist(s):
    return dict(n=len(s), km=round(s.len_m.sum() / 1000), mean=round(s.fish_score.mean(), 2),
                **{f">={k}": int((s.fish_score >= k).sum()) for k in (40, 60, 80)},
                km60=round(s[s.fish_score >= 60].len_m.sum() / 1000, 1))
print(f"{config.AREA}: A {A}\n   B {B}")
print("fish scores  A:", dist(a)); print("             B:", dist(b))
mid = shapely.line_interpolate_point(b.geometry.values, 0.5, normalized=True)
tree = shapely.STRtree(a.geometry.values)
idx, d = tree.query_nearest(mid, max_distance=30, return_distance=True, all_matches=False)
m = b.iloc[idx[0]].reset_index(drop=True).add_suffix("_b").join(a.iloc[idx[1]].reset_index(drop=True).add_suffix("_a"))
print(f"B reaches matched to an A reach within 30 m: {len(m)} of {len(b)} ({len(b) - len(m)} unmatched, "
      f"{b.loc[~b.index.isin(idx[0]), 'len_m'].sum() / 1000:.1f} km); A reaches no B reach matched: "
      f"{len(a) - len(set(idx[1]))}")
r = m.af_b / m.af_a
ds = m.fish_score_b - m.fish_score_a
print(f"  drainage +20% or more: {int((r >= 1.2).sum())}, -20% or more: {int((r <= 1 / 1.2).sum())}; "
      f"x2 or more: {int((r >= 2).sum())}, /2 or less: {int((r <= 0.5).sum())}")
print(f"  flow class changed: {int((m.water_class_b.fillna('-') != m.water_class_a.fillna('-')).sum())}; "
      f"name changed: {int((m.name_b.fillna('-') != m.name_a.fillna('-')).sum())}")
print(f"  fish score up 10+: {int((ds >= 10).sum())}, down 10+: {int((ds <= -10).sum())}; any change: {int((ds != 0).sum())}; "
      f"crossing 60: up {int(((m.fish_score_a < 60) & (m.fish_score_b >= 60)).sum())}, down {int(((m.fish_score_a >= 60) & (m.fish_score_b < 60)).sum())}")
show = m.assign(ds=ds, ratio=r.round(2))
cols = ["sid_b", "name_b", "af_a", "af_b", "ratio", "water_class_a", "water_class_b", "fish_score_a", "fish_score_b", "ds"]
big = show[(show.ds.abs() >= 10) | (show.ratio >= 2) | (show.ratio <= 0.5)]
print("  biggest moves:")
print(big.reindex(big.ds.abs().sort_values(ascending=False).index)[cols].head(25).to_string(index=False))
if OUT:
    show.drop(columns=[c for c in show.columns if c.startswith("geometry")]).to_csv(OUT, index=False)
