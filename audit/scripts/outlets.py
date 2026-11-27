"""Read-only: for every lake's outlet stream that NHD maps (NHD lines that begin in or at a lake and leave it, followed
downstream), is a creek line drawn along its first 300 m outside the lakes (Lakes on)? Last night's maps against the
live ones. outlets.py [area ...]   -> outlets.csv"""
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # the project this is in
OLDDIR = _os.environ.get("OLDDIR")      # e.g. the published copy, to check new local builds before a publish
NOWDIR = _os.environ.get("NOWDIR", f"{ROOT}/publish/streams-site/docs")

import json, sys, os, glob, collections
import sitefile                          # map3d_data.js plain or as the site keeps it (.gz, since 2026-11-25)
import numpy as np, shapely, shapely.ops, geopandas as gpd, pandas as pd
S = os.path.dirname(os.path.abspath(__file__))
AREAS = "la jackson n_georgia central_vt ne_ct lexington_va se_pa smokies adk_high_peaks adk_northwest adk_southwest adk_southeast".split()
areas = sys.argv[1:] or AREAS
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
def load(t, crs):
    F = layer(t, "streams")
    G = gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326).to_crs(crs).values
    return F, G, shapely.STRtree(G)
ROWS = []; TOT = collections.Counter()
def data_root(a):
    """The lakes and NHD lines of the project this is in (the live build's); a copy of the checker with no data (a
    scratch clone of the code alone) reads the build's own, the folder NOWDIR is in."""
    for r in (ROOT, os.path.dirname(os.path.abspath(NOWDIR))):
        if os.path.exists(f"{r}/data/derived/{a}/_shared/lakes.gpkg"):
            return r
    sys.exit(f"{a}: no lakes.gpkg in {ROOT}/data or beside {NOWDIR}")
for a in areas:
    D = data_root(a)
    lk = gpd.read_file(f"{D}/data/derived/{a}/_shared/lakes.gpkg", columns=["lid", "name", "ha"]); crs = lk.crs
    lk = lk[lk.ha >= 1].reset_index(drop=True)
    parts = [gpd.read_file(p).to_crs(crs) for p in glob.glob(f"{D}/data/raw/{a}/*/nhd_flowlines.gpkg")]
    N = pd.concat(parts, ignore_index=True); N = N[N.geometry.notna() & N.ftype.isin([460, 334, 558, 336])]
    N = N.loc[~pd.Series(shapely.to_wkb(N.geometry.values), index=N.index).duplicated()].reset_index(drop=True)
    NG = np.array([g if g.geom_type == "LineString" else shapely.ops.linemerge(g) for g in N.geometry.values], dtype=object)
    ok = shapely.get_type_id(NG) == 1
    N, NG = N[ok].reset_index(drop=True), NG[ok]
    st, en = shapely.get_point(NG, 0), shapely.get_point(NG, -1)
    key = lambda p: (round(p.x), round(p.y))
    starts = collections.defaultdict(list)
    for i, p in enumerate(st): starts[key(p)].append(i)
    Fo, Go, To = load(sitefile.read_text(f"{OLDDIR}/{a}/map3d_data.js" if OLDDIR else f"{S}/old/{a}.js"), crs); Fn, Gn, Tn = load(sitefile.read_text(f"{NOWDIR}/{a}/map3d_data.js"), crs)
    LG = lk.geometry.values; lt = shapely.STRtree(LG)
    ni, li = lt.query(st, predicate="dwithin", distance=20.0)        # the NHD line begins in or at this lake
    cnt = collections.Counter(); seen_out = set()
    for n, l in zip(ni, li):
        cs = list(NG[n].coords); L = NG[n].length; cur = n; used = {n}; names = [N.gnis_name.iat[n]]; fcodes = [int(N.fcode.iat[n])]
        while L < 700:
            nxt = [m for m in starts.get(key(en[cur]), []) if m not in used]
            if not nxt: break
            cur = max(nxt, key=lambda m: NG[m].length); used.add(cur); cs += list(NG[cur].coords)[1:]; L += NG[cur].length
            names.append(N.gnis_name.iat[cur]); fcodes.append(int(N.fcode.iat[cur]))
        ch = shapely.LineString(cs)
        P = shapely.line_interpolate_point(ch, np.arange(25, min(ch.length, 700) + 1, 25.0))
        if not len(P): continue
        inl = np.zeros(len(P), bool); inl[np.unique(lt.query(P, predicate="dwithin", distance=10.0)[0])] = True
        if inl.all() or not inl[0] and shapely.distance(st[n], LG[l]) > 0 and False: continue
        first = int(np.argmax(~inl))                        # first point outside every lake
        P = P[first:][~inl[first:]][:12]
        if len(P) < 4: continue
        k0 = (round(P[0].x / 60), round(P[0].y / 60))
        if k0 in seen_out: continue
        seen_out.add(k0)
        def cov(T, G, F):
            a_, b_ = T.query(P, predicate="dwithin", distance=60.0)
            return len(np.unique(a_)) / len(P), (F[np.bincount(b_).argmax()]["properties"] if len(b_) else {})
        co, qo = cov(To, Go, Fo); cn, qn = cov(Tn, Gn, Fn)
        k = "both" if co >= 0.6 and cn >= 0.6 else "lost" if co >= 0.6 else "gained" if cn >= 0.6 else "neither"
        cnt[k] += 1
        if k in ("lost", "gained"):
            q = qo if k == "lost" else qn
            ll = gpd.GeoSeries([P[min(3, len(P) - 1)]], crs=crs).to_crs(4326).iloc[0]
            nm = next((x for x in names if isinstance(x, str)), "")
            ROWS.append((a, k, lk.name.iat[l] or "unnamed lake", round(float(lk.ha.iat[l]) * 2.47105, 1), nm, max(fcodes, key=fcodes.count),
                         q.get("n") or "unnamed", round(float(q.get("a") or 0) / 2.58999, 2), q.get("fl"), q.get("fs"), f"{ll.y:.5f},{ll.x:.5f}", round(co, 2), round(cn, 2)))
    TOT.update(cnt)
    print(f"{a:15s} NHD-mapped lake outlets: drawn both nights {cnt['both']:4d} | drawn last night, not now {cnt['lost']:3d} | not last night, drawn now {cnt['gained']:3d} | neither {cnt['neither']:4d}"); sys.stdout.flush()
print(f"ALL             both {TOT['both']} | lost {TOT['lost']} | gained {TOT['gained']} | neither {TOT['neither']}")
D = pd.DataFrame(ROWS, columns="area change lake acres nhd_name fcode line sqmi flow fish at cov_old cov_new".split())
D.to_csv(os.path.join(os.environ.get("OUTDIR", os.getcwd()), "outlets.csv"), index=False)  # caller's folder, not tools/
print(D.groupby("change").agg(n=("sqmi", "size"), over_0_8_sqmi=("sqmi", lambda s: int((s >= 0.8).sum())), fish60=("fish", lambda s: int((pd.to_numeric(s, errors="coerce") >= 60).sum()))))
