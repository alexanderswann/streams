"""Read-only: fish-score moves on the lines drawn by default, one version against another, matched by place
(a point every 100 m on the old line, the nearest new line within 30 m). Also the water-temperature text of each.
score_moves.py [area ...]   env OLDDIR, NOWDIR"""
import json, sys, os, re, collections
import sitefile                          # map3d_data.js plain or as the site keeps it (.gz, since 2026-11-25)
import numpy as np, shapely, geopandas as gpd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the project this is in
OLDDIR = os.environ.get("OLDDIR", f"{ROOT}/publish/streams-site/docs")
NOWDIR = os.environ.get("NOWDIR", f"{ROOT}/output")
AREAS = "la jackson n_georgia central_vt ne_ct lexington_va se_pa smokies adk_high_peaks adk_northwest adk_southwest adk_southeast".split()
areas = [a for a in sys.argv[1:] if not a.startswith("-")] or AREAS; verbose = "-v" in sys.argv
MI = 1609.344
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
def load(path, crs=None):
    F = layer(sitefile.read_text(path), "streams")
    g = gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326)
    crs = crs or g.estimate_utm_crs()
    return F, g.to_crs(crs).values, crs
def temp(q):
    m = re.search(r"summer water about (\d+)", json.dumps(q, ensure_ascii=False)); return float(m.group(1)) if m else np.nan
def lakeword(q):
    return "lake water" in json.dumps(q, ensure_ascii=False)
def num(v): return float(v) if isinstance(v, (int, float)) else np.nan
T = collections.Counter()
for a in areas:
    Fo, Go, crs = load(f"{OLDDIR}/{a}/map3d_data.js"); Fn, Gn, _ = load(f"{NOWDIR}/{a}/map3d_data.js", crs)
    L = shapely.length(Go); n = np.maximum(1, np.round(L / 100).astype(int)); idx = np.repeat(np.arange(len(Go)), n)
    first = np.cumsum(n) - n; frac = (np.arange(len(idx)) - first[idx] + 0.5) / n[idx]
    P = shapely.line_interpolate_point(Go[idx], frac * L[idx]); w = L[idx] / n[idx] / MI
    tree = shapely.STRtree(Gn); j = tree.nearest(P); ok = shapely.distance(P, Gn[j]) <= 30
    fo = np.array([num(f["properties"].get("fs")) for f in Fo])[idx]; fn = np.array([num(f["properties"].get("fs")) for f in Fn])[j]
    to = np.array([temp(f["properties"]) for f in Fo])[idx]; tn = np.array([temp(f["properties"]) for f in Fn])[j]
    lw = np.array([lakeword(f["properties"]) for f in Fn])[j]
    reso = np.array([f["properties"].get("fl") == "summer: reservoir" for f in Fo])[idx]
    ok &= ~np.isnan(fo) & ~np.isnan(fn)
    d = fn - fo
    dn = ok & (d <= -10) & ~reso; up = ok & (d >= 10)
    cross_dn = ok & (fo >= 60) & (fn < 60); cross_up = ok & (fo < 60) & (fn >= 60)
    warm = dn & (tn - to >= 2)
    print(f"{a:15s} matched {w[ok].sum():7.0f} mi | down 10+: {w[dn].sum():6.1f} mi (with a warmer water estimate {w[warm].sum():6.1f}, of that 'lake water' {w[warm & lw].sum():6.1f}) | up 10+: {w[up].sum():6.1f} mi | "
          f"60+ -> under 60: {w[cross_dn].sum():6.1f} mi | under 60 -> 60+: {w[cross_up].sum():6.1f} mi")
    if w[warm].sum() > 0:
        print(f"      where the estimate got warmer and the score fell 10+: water {np.nanmean(to[warm]):.0f} -> {np.nanmean(tn[warm]):.0f} F on average; fish {np.mean(fo[warm]):.0f} -> {np.mean(fn[warm]):.0f}; "
              f"warmest new estimates: {np.nanpercentile(tn[warm], 10):.0f} F (10th pct), {np.nanpercentile(tn[warm], 50):.0f} F (median), {np.nanpercentile(tn[warm], 90):.0f} F (90th)")
    for k, v in (("dn", w[dn].sum()), ("warm", w[warm].sum()), ("warmlake", w[warm & lw].sum()), ("up", w[up].sum()), ("cdn", w[cross_dn].sum()), ("cup", w[cross_up].sum())): T[k] += v
    if verbose:
        by = collections.defaultdict(lambda: [0.0, [], [], [], []])
        for i in np.flatnonzero(dn):
            q = Fo[idx[i]]["properties"]; key = (q.get("n") or "unnamed") + " / " + str(q.get("d"))
            by[key][0] += w[i]; by[key][1].append(fo[i]); by[key][2].append(fn[i]); by[key][3].append(to[i]); by[key][4].append(tn[i])
        for key, (mi, a1, a2, t1, t2) in sorted(by.items(), key=lambda kv: -kv[1][0])[:10]:
            print(f"        {mi:5.1f} mi  {key}: fish {np.mean(a1):.0f} -> {np.mean(a2):.0f}, water {np.nanmean(t1):.0f} -> {np.nanmean(t2):.0f} F")
print(f"ALL  down 10+: {T['dn']:.0f} mi (warmer estimate {T['warm']:.0f}, 'lake water' {T['warmlake']:.0f}) | up 10+: {T['up']:.0f} mi | 60+ -> under 60: {T['cdn']:.0f} mi | under 60 -> 60+: {T['cup']:.0f} mi")
