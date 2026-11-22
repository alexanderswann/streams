"""Every drawn line whose drainage fell (or rose) between two sets of maps, whatever its fish score did: the default
layer "streams" of map3d_data.js, each new piece against the old piece drawn at the same place (its middle within
30 m), kept where the drainage changed by 1 km2 or more and by 30 % or more. With NHDPlus V2's drainage on the
nearest flowline within 60 m, to tell a correction (the new value is nearer NHDPlus's) from a loss (further from it).

Written 2026-11-22: the review of a routing change had read the reaches that scored 10+ lower, and a creek that lost
its headwater scored 9 lower and was not on any list (a Grass River tributary, adk_northwest).
[OLD_MAPS=<dir>] [NEW_MAPS=<dir>] python drainage_moves.py <out.csv> [area ...]
OLD_MAPS and NEW_MAPS hold <area>/map3d_data.js or <area>.js (defaults: the site clone, the project's output)."""
import sys, os, json, math
P = "/Users/mac/Fishing"
import numpy as np, pandas as pd, geopandas as gpd, shapely
OLD = os.environ.get("OLD_MAPS", f"{P}/publish/alexanderswann.github.io/streams")
NEW = os.environ.get("NEW_MAPS", f"{P}/output")
OUT = sys.argv[1]
areas = sys.argv[2:] or "jackson ne_ct lexington_va se_pa central_vt smokies n_georgia la adk_southwest adk_northwest adk_high_peaks adk_southeast".split()
def js(d, a): return next(f for f in (f"{d}/{a}/map3d_data.js", f"{d}/{a}.js") if os.path.exists(f))
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
num = lambda v: float(v) if v not in (None, "") else np.nan
rows = []
for a in areas:
    A = layer(open(js(OLD, a)).read(), "streams"); B = layer(open(js(NEW, a)).read(), "streams")
    crs = gpd.read_file(f"{P}/data/derived/{a}/_shared/lakes.gpkg", rows=1).crs
    def geoms(F): return gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326).to_crs(crs).values
    GA, GB = geoms(A), geoms(B)
    T = shapely.STRtree(GA)
    v2 = gpd.read_file(f"{P}/data/raw/{a}/_shared/flow/nhdplus_v2.gpkg", columns=["totdasqkm", "gnis_name"]).to_crs(crs)
    V = shapely.STRtree(v2.geometry.values)
    for f, g in zip(B, GB):
        p = f["properties"]; an = num(p.get("a"))
        m = g.interpolate(0.5, normalized=True)
        k = T.query_nearest(m, max_distance=30)
        if not len(k) or np.isnan(an): continue
        q = A[int(k[0])]["properties"]; ao = num(q.get("a"))
        if np.isnan(ao) or abs(ao - an) < 1.0 or min(ao, an) > 0.7 * max(ao, an): continue
        j = V.query_nearest(m, max_distance=60)
        vk = float(v2.totdasqkm.iloc[int(j[0])]) if len(j) else np.nan
        vn = v2.gnis_name.iloc[int(j[0])] if len(j) else None
        verdict = "no NHDPlus line" if not (vk > 0) else ("towards NHDPlus" if abs(math.log(max(an, 0.01) / vk)) < abs(math.log(max(ao, 0.01) / vk)) - 0.05 else "AWAY from NHDPlus")
        c = f["geometry"]["coordinates"][len(f["geometry"]["coordinates"]) // 2]
        rows.append(dict(area=a, name=p.get("n") or "", ft=round(g.length * 3.28084), old_km2=ao, new_km2=an, nhdplus_km2=round(vk, 2) if vk == vk else np.nan,
                         nhdplus_name=vn if isinstance(vn, str) else "", change="lost" if an < ao else "gained", verdict=verdict,
                         old_fish=num(q.get("fs")), new_fish=num(p.get("fs")), flow=p.get("fl"), lat=round(c[1], 5), lon=round(c[0], 5)))
t = pd.DataFrame(rows)
t.to_csv(OUT, index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
t["mi"] = t.ft / 5280
print(t.groupby(["change", "verdict"]).agg(pieces=("mi", "size"), mi=("mi", "sum")).round(1).to_string())
