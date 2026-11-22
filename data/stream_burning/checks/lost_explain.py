"""Each lake outlet the overview's outlets.py flags as no longer drawn, with what the new map has there:
the nearest drawn line (how far, its name and drainage), and whether the flagged NHD line is a second outlet of a lake
with several (two_outlets.py's table) that the lake's water no longer leaves by. The outlet a lake's water leaves by
is the candidate nearest the build's dead end for that lake (putin.py's table), not a guess from the drawn lines.
A flagged outlet whose nearest new line carries the old line's drainage is the same creek with its start moved.
python lost_explain.py <acc dir with outlets_<area>.csv> <two-outlet dir> <new maps dir> <putin dir> [areas]"""
import sys, os, json, glob
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyproj
ACC, TWO, NEW, PUT = sys.argv[1:5]
areas = sys.argv[5:] or sorted(os.path.basename(f)[8:-4] for f in glob.glob(f"{ACC}/outlets_*.csv") if "explained" not in f)
pd.set_option("display.width", 280); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
out = []
for a in areas:
    f = f"{ACC}/outlets_{a}.csv"
    if not os.path.exists(f) or os.path.getsize(f) < 5:
        continue
    o = pd.read_csv(f)
    if "change" not in o:
        continue
    o = o[(o.area == a) & (o.change == "lost")]
    if not len(o):
        continue
    crs = gpd.read_file(f"/Users/mac/Fishing/data/derived/{a}/_shared/lakes.gpkg", rows=1).crs
    tr = pyproj.Transformer.from_crs(4326, crs, always_xy=True)
    F = layer(open(f"{NEW}/{a}/map3d_data.js").read(), "streams")
    G = gpd.GeoSeries([shapely.LineString([c[:2] for c in q["geometry"]["coordinates"]]) for q in F], crs=4326).to_crs(crs).values
    T = shapely.STRtree(G)
    two = pd.read_csv(f"{TWO}/{a}.csv") if os.path.exists(f"{TWO}/{a}.csv") and os.path.getsize(f"{TWO}/{a}.csv") > 5 else pd.DataFrame()
    if len(two):
        two["key"] = two.box + "|" + two.lake + "|" + two.ha.astype(str)
        two["pick"] = False         # the outlet the build's routing runs down: the candidate nearest the lake's dead end
        ex = [shapely.Point(*tr.transform(lon, lat)) for lat, lon in zip(two.lat, two.lon)]
        pt = pd.read_csv(f"{PUT}/{a}.csv")
        for k, g in two.groupby("key"):
            m = pt[(pt.box == g.box.iloc[0]) & (pt.lake == g.lake.iloc[0]) & ((pt.ha - g.ha.iloc[0]).abs() < 0.2)]
            if len(m):
                pit = shapely.Point(*tr.transform(m.pit_lon.iloc[0], m.pit_lat.iloc[0]))
                two.loc[min(g.index, key=lambda i: ex[two.index.get_loc(i)].distance(pit)), "pick"] = True
            else:
                two.loc[g.assign(r=g.routed_now.fillna(0.5)).sort_values(["r", "named"], ascending=[False, False]).index[0], "pick"] = True
    for _, r in o.iterrows():
        lat, lon = map(float, r["at"].split(","))
        p = shapely.Point(*tr.transform(lon, lat))
        k = T.nearest(p); q = F[k]["properties"]
        why = ""
        if len(two):
            d = np.array([p.distance(e) for e in ex])
            i = int(np.argmin(d))
            c = two.iloc[i]
            if d[i] <= 450 and (c.lake == r.lake or d[i] <= 120):
                pk = two[(two.key == c.key) & two.pick].iloc[0]
                if not c.pick:
                    how = ("the one NHD names" + (f" ({pk.own_name})" if isinstance(pk.own_name, str) and pk.own_name else "")) if pk.named else "another of them"
                    why = (f"second outlet of {c.lake} ({int(two[two.key == c.key].shape[0])} NHD outlets): the water leaves by {how}, "
                           f"{round(ex[i].distance(ex[pk.name]) * 3.28084, -1):,.0f} ft away")
                else:
                    why = f"the picked outlet of {c.lake}: LOOK"
        new_sqmi = round(float(q.get("a") or 0) / 2.58999, 2)
        if (not why or why.endswith("LOOK")) and abs(new_sqmi - r.sqmi) <= 0.02 * max(r.sqmi, 0.1):
            why = f"the same creek (the same drainage), drawn from {round(float(G[k].distance(p)) * 3.28084, -1):,.0f} ft further on"
        out.append(dict(area=a, lake=r.lake, acres=r.acres, nhd_name=r.nhd_name, old_line=r.line, old_sqmi=r.sqmi, old_fish=r.fish, at=r["at"],
                        cov_old=r.cov_old, cov_new=r.cov_new, nearest_new_ft=round(float(G[k].distance(p)) * 3.28084),
                        new_name=q.get("n") or "unnamed", new_sqmi=round(float(q.get("a") or 0) / 2.58999, 2), why=why or "LOOK"))
t = pd.DataFrame(out)
print(t.to_string(index=False) if len(t) else "no lost outlets")
t.to_csv(f"{ACC}/lost_outlets_explained.csv", index=False)
