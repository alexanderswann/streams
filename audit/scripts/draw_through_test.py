#!/usr/bin/env python3
"""What does 06_map.py's draw_through still add, now that 03b draws a line below each lake outlet and 05_score keeps
it on the water it carries?

draw_through (06_map.py:106-283) follows the routing from every place crossbox.py puts water back in (below a dam or
pond, or where a river enters the map) to the first drawn reach, and draws that path: either as a new piece (written
with a "+N" id) or by lengthening the reach it meets at its head. streams_drawn.gpkg is the lines right after that
step, streams_scored.gpkg the reaches before it. Read-only, from one build's files:

  new pieces      rows of streams_drawn.gpkg with "+" in the id: how many, how long, and how much of each already lies
                  along a reach (within 26 ft): a second line beside one that is there
  longer heads    reaches drawn longer than they were scored, and by how much
  by kind         each addition matched to the crossbox link it starts from (inflows.json): dam, pond or outside river
    SNAP=<folder with <area>/streams_drawn.gpkg, <area>/<box>/streams_scored.gpkg, <area>/inflows.json> \
    AUDIT_TABLES=<out> python audit/scripts/draw_through_test.py
Tables: draw_through_actions.csv (one row per addition), draw_through_summary.csv
"""
import sys, os, json, glob
import numpy as np, pandas as pd, geopandas as gpd, shapely
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(__file__))
from common import *

SNAP = os.environ["SNAP"]
NEAR = 8.0            # m: "along an existing reach"


def share_along(geoms, others_tree, others, skip):
    """For each line: the share of its length within NEAR of a reach other than skip[i]."""
    out = np.zeros(len(geoms))
    for n, g in enumerate(geoms):
        if g is None or g.is_empty or g.length == 0:
            continue
        x, y, ln, _ = seg_midpoints([g], 5.0)
        pts = shapely.points(x, y)
        hit = np.zeros(len(pts), bool)
        for k, p in enumerate(pts):
            c = others_tree.query(p, predicate="dwithin", distance=NEAR)
            hit[k] = any(j != skip[n] for j in c)
        out[n] = ln[hit].sum() / ln.sum()
    return out


def main(areas):
    rows = []
    for a in areas:
        d = gpd.read_file(f"{SNAP}/{a}/streams_drawn.gpkg").to_crs(epsg(a))
        sc = pd.concat([gpd.read_file(p, columns=["sid"]).to_crs(epsg(a)) for p in sorted(glob.glob(f"{SNAP}/{a}/*/streams_scored.gpkg"))],
                       ignore_index=True)
        sidx = {s: i for i, s in enumerate(sc.sid)}
        tree = shapely.STRtree(sc.geometry.values)
        extra = d[d.sid.str.contains(r"\+")].reset_index(drop=True)
        same = d[~d.sid.str.contains(r"\+")].reset_index(drop=True)
        ls = np.array([sc.geometry.values[sidx[s]].length if s in sidx else np.nan for s in same.sid])
        grow = same.length.to_numpy() - ls
        longer = same[grow > 0.5].reset_index(drop=True)
        gl = grow[grow > 0.5]
        heads = [shapely.ops.substring(g, 0, min(m, g.length)) for g, m in zip(longer.geometry.values, gl)]
        # the links the additions start from
        links = json.load(open(f"{SNAP}/{a}/inflows.json"))["cross"]
        lx, ly, lkind, lkm2 = [], [], [], []
        for frm, x, y, into, row, col, km2, kind in links:
            if kind == "edge" or into not in boxes(a):
                continue
            x0, y0, x1, y1 = boxes(a)[into]["bbox"]
            lx.append(x0 + (col + 0.5) * 10); ly.append(y1 - (row + 0.5) * 10); lkind.append(kind); lkm2.append(km2)
        ltree = cKDTree(np.c_[lx, ly]) if lx else None

        def kind_of(g):
            if ltree is None or g is None or g.is_empty:
                return "?", np.nan
            dd, j = ltree.query(g.coords[0][:2], distance_upper_bound=25.0)
            return (lkind[j], lkm2[j]) if np.isfinite(dd) else ("?", np.nan)

        sh_e = share_along(list(extra.geometry.values), tree, sc, [-1] * len(extra))
        sh_h = share_along(heads, tree, sc, [sidx.get(s, -1) for s in longer.sid])
        to_ll = __import__("pyproj").Transformer.from_crs(epsg(a), 4326, always_xy=True)
        for g, s, sh in zip(extra.geometry.values, extra.sid, sh_e):
            k, km2 = kind_of(g)
            lon, lat = to_ll.transform(*g.coords[0][:2])
            rows.append(dict(area=a, how="new piece", sid=s, link=k, link_sq_mi=None if np.isnan(km2) else round(km2 / 2.58999, 2), ft=g.length / FT,
                             share_along_existing=round(sh, 2), lat=round(lat, 5), lon=round(lon, 5)))
        for g, s, sh in zip(heads, longer.sid, sh_h):
            k, km2 = kind_of(g)
            lon, lat = to_ll.transform(*g.coords[0][:2])
            rows.append(dict(area=a, how="longer head", sid=s, link=k, link_sq_mi=None if np.isnan(km2) else round(km2 / 2.58999, 2), ft=g.length / FT,
                             share_along_existing=round(sh, 2), lat=round(lat, 5), lon=round(lon, 5)))
        print(a, "new pieces", len(extra), "longer heads", len(longer), "links (not edge)", len(lx), flush=True)
    D = pd.DataFrame(rows)
    D["redraws_existing"] = D.share_along_existing >= 0.8
    D["under_50_ft"] = D.ft < 50
    D.round(2).to_csv(f"{TABLES}/draw_through_actions.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    mi = lambda s: round(s.sum() / 5280, 1)
    real = D[~D.redraws_existing & ~D.under_50_ft]
    S = D.groupby("area", sort=False).apply(lambda t: pd.Series(dict(
        additions=len(t), miles=mi(t.ft), new_pieces=int((t.how == "new piece").sum()), longer_heads=int((t.how == "longer head").sum()),
        redraw_an_existing_reach=int(t.redraws_existing.sum()), under_50_ft=int((t.under_50_ft & ~t.redraws_existing).sum()),
        real_additions=int((~t.redraws_existing & ~t.under_50_ft).sum()), real_miles=mi(t.ft[~t.redraws_existing & ~t.under_50_ft]),
        real_from_outside_rivers_mi=mi(t.ft[~t.redraws_existing & ~t.under_50_ft & (t.link == "outside")]),
        real_below_dams_mi=mi(t.ft[~t.redraws_existing & ~t.under_50_ft & (t.link == "dam")]),
        real_below_ponds_mi=mi(t.ft[~t.redraws_existing & ~t.under_50_ft & (t.link == "pond")]),
        real_unmatched_mi=mi(t.ft[~t.redraws_existing & ~t.under_50_ft & (t.link == "?")]))))
    S.loc["all 12"] = S.sum(numeric_only=True).round(1)
    S.to_csv(f"{TABLES}/draw_through_summary.csv")
    print(S.to_string())
    print("\nreal additions by kind of link:"); print(real.groupby("link").agg(n=("ft", "size"), miles=("ft", mi), median_ft=("ft", "median"), longest_mi=("ft", lambda s: round(s.max() / 5280, 2))).to_string())
    print("\nlongest real additions:"); print(real.sort_values("ft", ascending=False).head(15).assign(mi=lambda t: (t.ft / 5280).round(2))[["area", "how", "sid", "link", "link_sq_mi", "mi", "share_along_existing", "lat", "lon"]].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
