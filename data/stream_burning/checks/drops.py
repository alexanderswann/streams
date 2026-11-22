"""The 10+ point fish-score moves between two builds of one area, by cause, and the lines one build has that the
other doesn't. Written for the question the lake routing (03b_stitch.route_lake, 2026-11-21) raised against the
user's rule "keep possible trout water: mark a stream down only when near-certain": which reaches went down, and why.

B's reaches are matched to A's by place, as compare_roots.py does (B's reach middle within 30 m of an A reach).
A down-move (fish score 10+ lower in B) is put in the first group that fits:
  lake      B's reach reads "reservoir" (05b: half its length or more in a lake) and A's didn't. `out_m` is the
            length of it outside every lake outline (the lakes layer's and NHD's): creek water inside a lake reach
  carried   B's drainage is half of A's or less, and A's came from crossbox's dam / pond links (its full drainage 2x
            its own D8 area or more): a lake's water had landed on this line. `v2_km2` is NHDPlus V2's drainage on
            its line within 60 m of the reach's middle, where there is one: the independent figure
  drainage  B's drainage is half of A's or less for another reason (the D8 paths themselves moved)
  flow      the flow class is drier (not a lake reach), with the drainage not halved
  other     none of these
Up-moves mirror them (left a lake, gained a lake's water, drainage, flow, other).
Lines only one build has: a reach under half of whose length (sampled every 25 m) lies within 30 m of any reach of
the other build. Those that aren't lake reaches and run 200+ m outside every lake outline are listed with `nhd`, the
share of their length within 40 m of an NHD HR stream line (does NHD map a stream there?), and `moved_m`, the distance
from their middle to the nearest reach of the other build with half their drainage or more (the same creek, drawn
somewhere else).
AREA=<area> python drops.py <rootA|-> <rootB|-> [outdir]"""
import sys, os
P = "/Users/mac/Fishing"
A = sys.argv[1] if sys.argv[1] != "-" else P
B = sys.argv[2] if sys.argv[2] != "-" else P
OUT = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
from flowlib import FLOW, reservoirs
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
KEEP = ["sid", "name", "water_class", "water_rule", "water_term", "below_dam", "fish_score", "thermal", "gradient_pct",
        "area_km2", "area_edge_km2", "area_full_km2", "strahler", "len_m", "heat_factor", "channel_factor",
        "trout_factor", "burn_factor", "dry_cfs", "flow_src", "gauge_name", "tailwater", "lat", "lon"]


def load(root):
    rk = pd.read_csv(f"{root}/output/{config.AREA}/stream_reaches_ranked.csv", low_memory=False)
    rk = rk[~rk.sid.astype(str).str.contains("+", regex=False)].reindex(columns=KEEP)   # not 06_map's drawn-through pieces
    g = pd.concat([gpd.read_file(f"{root}/output/{config.AREA}/{r}/streams_scored.gpkg")[["sid", "geometry"]]
                   for r in config.REGIONS], ignore_index=True)
    g = gpd.GeoDataFrame(g, crs=4326).to_crs(config.CRS).merge(rk, on="sid")
    g["af"] = g.area_full_km2.fillna(g.area_km2)
    g["lake"] = g.water_class.eq("reservoir")
    return g.reset_index(drop=True)


a, b = load(A), load(B)
# ---- lake outlines: the lakes layer (what the map draws) and NHD's (what 05b also counts) ----
polys = list(shapely.make_valid(reservoirs().geometry.values))
lp = f"{P}/data/derived/{config.AREA}/_shared/lakes.gpkg"
layer = gpd.read_file(lp).to_crs(config.CRS) if os.path.exists(lp) else None
layer_u = shapely.union_all(shapely.make_valid(layer.geometry.values)) if layer is not None and len(layer) else shapely.Polygon()
water_u = shapely.union_all(polys + [layer_u])
shapely.prepare(water_u); shapely.prepare(layer_u)


def outside(geoms, u):
    return shapely.length(shapely.difference(geoms, u))


# ---- matched pairs ----
mid = shapely.line_interpolate_point(b.geometry.values, 0.5, normalized=True)
tree_a = shapely.STRtree(a.geometry.values)
ib, ia = tree_a.query_nearest(mid, max_distance=30, all_matches=False)
m = b.iloc[ib].reset_index(drop=True).add_suffix("_b").join(a.iloc[ia].reset_index(drop=True).add_suffix("_a"))
m["ds"] = m.fish_score_b - m.fish_score_a
m["ratio"] = m.af_b / m.af_a
order = ["mostly dry", "seasonal", "usually flows", "year-round"]
rank = lambda s: s.map({k: i for i, k in enumerate(order)})
drier = rank(m.water_class_b) < rank(m.water_class_a)
wetter = rank(m.water_class_b) > rank(m.water_class_a)
carried_a = (m.af_a >= 2 * m.area_km2_a) & (m.af_a - m.area_km2_a >= 2)
carried_b = (m.af_b >= 2 * m.area_km2_b) & (m.af_b - m.area_km2_b >= 2)
m["cause"] = ""
dn, up = m.ds <= -10, m.ds >= 10
m.loc[dn, "cause"] = np.select(
    [(m.lake_b & ~m.lake_a)[dn], ((m.ratio <= 0.5) & carried_a)[dn], (m.ratio <= 0.5)[dn], drier[dn]],
    ["lake", "carried", "drainage", "flow"], "other")
m.loc[up, "cause"] = np.select(
    [(m.lake_a & ~m.lake_b)[up], ((m.ratio >= 2) & carried_b)[up], (m.ratio >= 2)[up], wetter[up]],
    ["left lake", "gained", "drainage+", "flow+"], "other+")
mv = m[dn | up].copy()
gb = gpd.GeoSeries(mv.geometry_b.values, crs=config.CRS)
mv["out_m"] = outside(gb.values, water_u).round(0)            # outside every lake outline
mv["out_layer_m"] = outside(gb.values, layer_u).round(0)      # outside the lakes the map draws
# NHDPlus V2's drainage on its line by the reach's middle
v2p = f"{FLOW}/nhdplus_v2.gpkg"
mv["v2_km2"] = np.nan
if os.path.exists(v2p):
    v2 = gpd.read_file(v2p).to_crs(config.CRS).drop_duplicates("comid")
    v2 = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"]) & (v2.divergence != 2)].reset_index(drop=True)
    if len(v2):
        t2 = shapely.STRtree(v2.geometry.values)
        mids = shapely.line_interpolate_point(gb.values, 0.5, normalized=True)
        q, k = t2.query_nearest(mids, max_distance=60, all_matches=False)
        mv.iloc[q, mv.columns.get_loc("v2_km2")] = v2.totdasqkm.values[k]


# ---- lines only one build has ----
def only(x, y):
    """rows of x under half of whose length lies within 30 m of any reach of y"""
    ty = shapely.STRtree(y.geometry.values)
    share = np.zeros(len(x))
    for i, ln in enumerate(x.geometry.values):
        n = max(2, int(ln.length // 25) + 1)
        pts = shapely.line_interpolate_point(ln, np.linspace(0, 1, n), normalized=True)
        hit = ty.query(pts, predicate="dwithin", distance=30)
        share[i] = len(set(hit[0])) / n
    o = x[share < 0.5].copy()
    o["out_m"] = outside(o.geometry.values, water_u).round(0)
    return o


gone, new = only(a, b), only(b, a)
# NHD HR stream lines (as 03b_stitch.nhd_lines): does NHD map a stream along a line only one build has?
hr = [gpd.read_file(f"{config.raw_dir(r)}/nhd_flowlines.gpkg", columns=["ftype"]) for r in config.REGIONS
      if os.path.exists(f"{config.raw_dir(r)}/nhd_flowlines.gpkg")]
hr = pd.concat([h[h.ftype.isin([460, 558, 334])].to_crs(config.CRS) for h in hr], ignore_index=True) if hr else None
t_hr = shapely.STRtree(hr.geometry.values) if hr is not None and len(hr) else None


def describe(o, other):
    """nhd share and moved_m for the listed rows"""
    o = o.copy()
    o["nhd"], o["moved_m"] = np.nan, np.nan
    to = shapely.STRtree(other.geometry.values)
    for i in o.index:
        ln = o.geometry[i]
        n = max(2, int(ln.length // 25) + 1)
        pts = shapely.line_interpolate_point(ln, np.linspace(0, 1, n), normalized=True)
        if t_hr is not None:
            o.loc[i, "nhd"] = round(len(set(t_hr.query(pts, predicate="dwithin", distance=40)[0])) / n, 2)
        c = shapely.line_interpolate_point(ln, 0.5, normalized=True)
        k = to.query(c, predicate="dwithin", distance=300)
        k = k[other.af.values[k] >= 0.5 * o.af[i]]
        if len(k):
            o.loc[i, "moved_m"] = round(float(shapely.distance(other.geometry.values[k], c).min()), 0)
    return o
km = lambda s: round(float(s.sum()) / 1000, 1)
print(f"#### {config.AREA}: A {A} ({len(a)} reaches, {km(a.len_m)} km) | B {B} ({len(b)} reaches, {km(b.len_m)} km)")
print(f"fish 60+ km: A {km(a.len_m[a.fish_score >= 60])} -> B {km(b.len_m[b.fish_score >= 60])} | "
      f"reservoir-class km: A {km(a.len_m[a.lake])} -> B {km(b.len_m[b.lake])}")
print(f"matched {len(m)} of {len(b)} B reaches; down 10+: {int(dn.sum())}, up 10+: {int(up.sum())}")
for label, sel, names in (("down", dn, ["lake", "carried", "drainage", "flow", "other"]),
                          ("up", up, ["left lake", "gained", "drainage+", "flow+", "other+"])):
    s = mv[mv.cause.isin(names)]
    t = s.groupby("cause").agg(reaches=("ds", "size"), km=("len_m_b", lambda x: km(x)),
                               was60=("fish_score_a", lambda x: int((x >= 60).sum())),
                               now60=("fish_score_b", lambda x: int((x >= 60).sum()))).reindex(names).fillna(0)
    print(f"-- {label}-moves by cause\n{t.to_string()}")
lk = mv[mv.cause == "lake"]
print(f"-- lake group: {len(lk)} reaches, {km(lk.len_m_b)} km; of that outside every lake outline {km(lk.out_m)} km "
      f"(outside the lakes the map draws: {km(lk.out_layer_m)} km); reaches with 200+ m outside every outline: "
      f"{int((lk.out_m >= 200).sum())}")
ll = mv[mv.cause == "left lake"]
print(f"-- left-lake group: {len(ll)} reaches, {km(ll.len_m_b)} km")
cols = ["sid_b", "name_b", "name_a", "len_m_b", "out_m", "area_km2_a", "af_a", "area_km2_b", "af_b", "v2_km2",
        "water_class_a", "water_class_b", "fish_score_a", "fish_score_b", "ds", "lat_b", "lon_b"]
fcols = ["sid_b", "name_b", "len_m_b", "af_a", "af_b", "area_edge_km2_a", "area_edge_km2_b", "flow_src_a", "flow_src_b",
         "dry_cfs_a", "dry_cfs_b", "water_rule_a", "water_rule_b", "gauge_name_a", "gauge_name_b", "water_class_a",
         "water_class_b", "thermal_a", "thermal_b", "gradient_pct_a", "gradient_pct_b", "fish_score_a", "fish_score_b",
         "ds", "lat_b", "lon_b"]
show = lambda d, n=60, c=cols: print(d.sort_values("ds")[c].head(n).round(2).to_string(index=False) if len(d) else "  none")
print("-- lake reaches with 200+ m outside every lake outline:"); show(lk[lk.out_m >= 200])
for c in ("carried", "drainage"):
    print(f"-- down: {c}"); show(mv[mv.cause == c])
for c in ("flow", "other"):
    print(f"-- down: {c}"); show(mv[mv.cause == c], c=fcols)
print("-- up: other+ / flow+ / drainage+"); show(mv[mv.cause.isin(["other+", "flow+", "drainage+"])], 30)
for label, o in (("A has, B doesn't (gone)", gone), ("B has, A doesn't (new)", new)):
    c = o[~o.lake]
    print(f"-- lines {label}: {len(o)} reaches, {km(o.len_m)} km; not lake reaches: {len(c)}, {km(c.len_m)} km, "
          f"fish 60+ {km(c.len_m[c.fish_score >= 60])} km; of those outside every lake outline by 200+ m: "
          f"{int((c.out_m >= 200).sum())} reaches, {km(c.out_m[c.out_m >= 200])} km")
    c2 = describe(c[c.out_m >= 200], b if o is gone else a).sort_values("len_m", ascending=False)
    if len(c2):
        real = c2[(c2.nhd >= 0.5) & c2.moved_m.isna()]
        print(f"   of those, along an NHD stream line (half their length or more) with no reach of the other build "
              f"carrying half their drainage within 300 m: {len(real)} reaches, {km(real.len_m)} km, fish 60+ "
              f"{km(real.len_m[real.fish_score >= 60])} km")
    print(c2[["sid", "name", "len_m", "out_m", "area_km2", "af", "water_class", "fish_score", "nhd", "moved_m", "lat",
              "lon"]].head(60).round(2).to_string(index=False) if len(c2) else "  none")
    if o is gone: gone = gone.join(c2[["nhd", "moved_m"]])
    else: new = new.join(c2[["nhd", "moved_m"]])
if OUT:
    os.makedirs(OUT, exist_ok=True)
    mv.drop(columns=["geometry_a", "geometry_b"]).to_csv(f"{OUT}/moves_{config.AREA}.csv", index=False)
    gone.drop(columns="geometry").assign(which="gone").to_csv(f"{OUT}/gone_{config.AREA}.csv", index=False)
    new.drop(columns="geometry").assign(which="new").to_csv(f"{OUT}/new_{config.AREA}.csv", index=False)
