"""What the default map draws (the Lakes-on layer "streams" of map3d_data.js), an older version against a newer one, by
line length in miles: total, fish 60+, line only one version draws (nothing of the other within 40 m), and for line
both draw, how its fish score moved.

Written 2026-11-21 after the reach tables had been taken for the map: 05_score's floor change made 1,610 stream links
below lake outlets reaches of their own (1,092 km), and that was reported as new line. 06_map.py had drawn 927 km of
it before, through from the dam to the next reach with that reach's values (draw_through), so the map gained 131 mi
and lost 149. Reach tables say what a reach is; only the drawn layer says what the map shows.

Each version is a folder holding <area>.js, or a commit of the site copy (publish/alexanderswann.github.io), read with
git show.   python drawn_cmp.py <old dir | site commit> <new dir | site commit> [out.csv] [area ...]"""
import sys, json, math, os
import numpy as np, shapely
import subprocess
SITE = "/Users/mac/Fishing/publish/alexanderswann.github.io"
OLD, NEW = sys.argv[1], sys.argv[2]
rest = sys.argv[3:]
OUT = rest.pop(0) if rest and rest[0].endswith(".csv") else None
areas = rest or "jackson ne_ct lexington_va se_pa central_vt smokies n_georgia la adk_southwest adk_northwest adk_high_peaks adk_southeast".split()
MI = 1609.344
def load(src, a):
    if os.path.isdir(src):
        t = open(f"{src}/{a}.js").read()
    else:
        t = subprocess.run(["git", "-C", SITE, "show", f"{src}:streams/{a}/map3d_data.js"], capture_output=True, text=True,
                           check=True).stdout
    return json.loads(t[t.index("{"):t.rindex("}") + 1])
def lines(feats, lat0):
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    g, fs, fl, nm = [], [], [], []
    for f in feats:
        gm = f["geometry"]
        parts = [gm["coordinates"]] if gm["type"] == "LineString" else gm["coordinates"]
        for c in parts:
            if len(c) < 2:
                continue
            a = np.asarray(c, float)[:, :2]
            g.append(shapely.LineString(np.column_stack([a[:, 0] * kx, a[:, 1] * ky])))
            q = f["properties"]
            v = q.get("fs")
            fs.append(float(v) if isinstance(v, (int, float)) else np.nan)
            fl.append(str(q.get("fl", "")))
            nm.append(q.get("n"))
    return np.array(g, dtype=object), np.array(fs), np.array(fl), np.array(nm, dtype=object)
def sample(g, step=25.0):
    L = shapely.length(g)
    n = np.maximum(1, np.round(L / step).astype(int))
    idx = np.repeat(np.arange(len(g)), n)
    # midpoints of n equal pieces
    k = np.concatenate([np.arange(m) for m in n])
    frac = (k + 0.5) / n[idx]
    pts = shapely.line_interpolate_point(g[idx], frac, normalized=True)
    w = (L / n)[idx]                                  # metres each point stands for
    return pts, idx, w
rows = []
for a in areas:
    do, dn = load(OLD, a), load(NEW, a)
    fo, fn = do["streams"]["features"], dn["streams"]["features"]
    lat0 = fo[0]["properties"].get("y", fo[0]["geometry"]["coordinates"][0][1])
    go, so, flo, no = lines(fo, lat0)
    gn, sn, fln, nn = lines(fn, lat0)
    lo, ln_ = lines(do.get("streams_lake", {"features": []})["features"], lat0)[0], lines(dn.get("streams_lake", {"features": []})["features"], lat0)[0]
    to, tn = shapely.STRtree(go), shapely.STRtree(gn)
    tlo = shapely.STRtree(lo) if len(lo) else None
    r = dict(area=a, old_mi=shapely.length(go).sum() / MI, new_mi=shapely.length(gn).sum() / MI,
             old60=shapely.length(go)[so >= 60].sum() / MI, new60=shapely.length(gn)[sn >= 60].sum() / MI)
    # new side
    pts, idx, w = sample(gn)
    q, k = to.query_nearest(pts, max_distance=40, all_matches=False)
    hit = np.zeros(len(pts), bool); hit[q] = True
    oldfs = np.full(len(pts), np.nan); oldfs[q] = so[k]
    newfs = sn[idx]
    r["new_line_mi"] = w[~hit].sum() / MI
    r["new_line60_mi"] = w[~hit & (newfs >= 60)].sum() / MI
    if tlo is not None:
        ql, _ = tlo.query_nearest(pts[~hit], max_distance=40, all_matches=False)
        r["new_line_was_lakes_off_mi"] = w[~hit][np.unique(ql)].sum() / MI
    both = hit & np.isfinite(oldfs) & np.isfinite(newfs)
    d = newfs - oldfs
    r["both_mi"] = w[both].sum() / MI
    r["down10_mi"] = w[both & (d <= -10)].sum() / MI
    r["up10_mi"] = w[both & (d >= 10)].sum() / MI
    r["60_to_under_mi"] = w[both & (oldfs >= 60) & (newfs < 60)].sum() / MI
    r["under_to_60_mi"] = w[both & (oldfs < 60) & (newfs >= 60)].sum() / MI
    # old side
    pts, idx, w = sample(go)
    q, k = tn.query_nearest(pts, max_distance=40, all_matches=False)
    hit = np.zeros(len(pts), bool); hit[q] = True
    r["gone_line_mi"] = w[~hit].sum() / MI
    r["gone_line60_mi"] = w[~hit & (so[idx] >= 60)].sum() / MI
    if len(ln_):
        tl = shapely.STRtree(ln_)
        ql, _ = tl.query_nearest(pts[~hit], max_distance=40, all_matches=False)
        r["gone_now_lakes_off_mi"] = w[~hit][np.unique(ql)].sum() / MI
    rows.append(r)
    print(a, "done", flush=True)
import pandas as pd
t = pd.DataFrame(rows)
t = pd.concat([t, pd.DataFrame([{"area": "ALL", **t.drop(columns="area").sum().to_dict()}])])
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
print(t.round(1).to_string(index=False))
if OUT:
    t.round(2).to_csv(OUT, index=False)
