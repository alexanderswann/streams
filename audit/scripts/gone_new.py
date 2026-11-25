"""Read-only: stream line drawn by default (Lakes on) on an older version with nothing drawn within 40 m now, and
the other way round. gone_new.py <old_site_commit | -> [-v] [area ...]   (lengths in miles)
Old maps: OLDDIR (a folder with <area>/map3d_data.js, e.g. publish/streams-site/docs) when set, else the old site
commit in the personal site repo's streams/ (before the 2026-11-22 move). New maps: NOWDIR (default: the live copy)."""
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # the project this is in
NOWDIR = _os.environ.get("NOWDIR", f"{ROOT}/publish/streams-site/docs")
OLDDIR = _os.environ.get("OLDDIR")

import json, subprocess, sys, collections
import numpy as np, shapely, geopandas as gpd
SITE = f"{ROOT}/publish/alexanderswann.github.io"
AREAS = "la jackson n_georgia central_vt ne_ct lexington_va se_pa smokies adk_high_peaks adk_northwest adk_southwest adk_southeast".split()
args = [a for a in sys.argv[1:] if a != "-v"]; verbose = "-v" in sys.argv
old_c = args[0]; areas = args[1:] or AREAS
STEP, NEAR, MI = 50.0, 40.0, 1609.344
def layer(t, key):
    i = t.find(f'"{key}"')
    if i < 0: return []
    j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
def load(t, crs=None):
    F = layer(t, "streams")
    g = gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326)
    crs = crs or g.estimate_utm_crs()
    return F, g, g.to_crs(crs).values, crs
def missing(Fa, ga, Ga, Gb):
    """for each line of a: metres of it with no b line within NEAR m; the runs of 300+ m"""
    tree = shapely.STRtree(Gb)
    L = shapely.length(Ga); n = np.maximum(1, np.ceil(L / STEP).astype(int))
    idx = np.repeat(np.arange(len(Ga)), n)
    first = np.cumsum(n) - n
    frac = (np.arange(len(idx)) - first[idx] + 0.5) / n[idx]
    P = shapely.line_interpolate_point(Ga[idx], frac * L[idx])
    hit = np.zeros(len(P), bool)
    hit[np.unique(tree.query(P, predicate="dwithin", distance=NEAR)[0])] = True
    seg = L[idx] / n[idx]
    gone_m = np.bincount(idx, weights=np.where(hit, 0, seg), minlength=len(Ga))
    rows = []
    for i in np.flatnonzero(gone_m >= 300):
        q = Fa[i]["properties"]; pts = P[idx == i][~hit[idx == i]]
        mid = gpd.GeoSeries([pts[len(pts) // 2]], crs=CRS).to_crs(4326).iloc[0]
        rows.append((gone_m[i] / MI, q.get("n") or "unnamed", q.get("d"), q.get("a"), q.get("o"), q.get("fl"), q.get("fs"), f"{mid.y:.5f},{mid.x:.5f}"))
    return gone_m, sorted(rows, reverse=True)
def f60(F, m):
    fs = np.array([f["properties"].get("fs") if isinstance(f["properties"].get("fs"), (int, float)) else -1 for f in F])
    return m[fs >= 60].sum() / MI
T = collections.Counter()
for a in areas:
    new = open(f"{NOWDIR}/{a}/map3d_data.js").read()
    old = (open(f"{OLDDIR}/{a}/map3d_data.js").read() if OLDDIR else
           subprocess.run(["git", "-C", SITE, "show", f"{old_c}:streams/{a}/map3d_data.js"], capture_output=True, text=True).stdout)
    Fn, gn, Gn, CRS = load(new); Fo, go, Go, _ = load(old, CRS)
    gm, grow = missing(Fo, go, Go, Gn); nm, nrow = missing(Fn, gn, Gn, Go)
    print(f"{a:15s} gone {gm.sum()/MI:6.1f} mi (fish 60+ {f60(Fo, gm):5.1f}) in {len(grow):3d} stretches of 0.2+ mi | new {nm.sum()/MI:6.1f} mi (fish 60+ {f60(Fn, nm):5.1f}) in {len(nrow):3d} stretches")
    for k, v in (("g", gm.sum()/MI), ("g60", f60(Fo, gm)), ("n", nm.sum()/MI), ("n60", f60(Fn, nm)), ("gs", len(grow)), ("ns", len(nrow))): T[k] += v
    for tag, rows in (("gone", grow), ("new ", nrow)):
        for r in rows[:(40 if verbose else 6)]:
            print(f"    {tag} {r[0]:4.1f} mi  {r[1]} / {r[2]} | {r[3]} km2 order {r[4]} {r[5]} fish {r[6]} | {r[7]}")
print(f"ALL  gone {T['g']:.0f} mi (fish 60+ {T['g60']:.0f}) in {T['gs']} stretches | new {T['n']:.0f} mi (fish 60+ {T['n60']:.0f}) in {T['ns']} stretches")
