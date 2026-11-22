"""What is there now, for the creek lines along NHD streams that only the older build draws (summarize_drops.py's
named.csv, cause "line gone, on an NHD line"): 03b's stream links (dem_streams.gpkg) along the old line, with each
link's own drainage and the water carried to it at the cell 05_score reads (the last before its junction), and
whether the project's build draws it. A link under 1 km2 with nothing carried to it is under 05_score's floor: the
older build drew it only as part of a longer link, before a new line joined it and split it there.
AREA=<area> python why_gone.py <folder with named.csv> <root of the older build>"""
import sys, os
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
import config, crossbox
D, A = sys.argv[1], sys.argv[2]
area = config.AREA
n = pd.read_csv(f"{D}/named.csv", low_memory=False)
g = n[(n.cause == "line gone, on an NHD line") & (n.area == area)]
read = lambda root: pd.concat([gpd.read_file(f"{root}/output/{area}/{r}/streams_scored.gpkg")[["sid", "geometry"]]
                               for r in config.REGIONS]).to_crs(config.CRS)
old, new = read(A).set_index("sid"), read(P)
new_u = shapely.union_all(new.geometry.buffer(30).values)
cache, rows = {}, []
for _, r in g.iterrows():
    ln, box = old.geometry[r.sid], r.sid.split(":")[0]
    if box not in cache:
        fp = crossbox.fdir_path(box)
        with rasterio.open(fp) as src:
            tr, shp = src.transform, src.shape
        with rasterio.open(fp.replace("flowdir", "area_km2")) as src:
            ar = src.read(1)
        ds = gpd.read_file(os.path.dirname(fp) + "/dem_streams.gpkg").to_crs(config.CRS)
        cache[box] = (tr, ar, crossbox.carried_km2(box).reshape(shp), ds, shapely.STRtree(ds.geometry.values))
    tr, ar, car, ds, tree = cache[box]
    parts = []
    for i in tree.query(ln.buffer(35), predicate="intersects"):
        d = ds.geometry.values[i]
        if d.intersection(ln.buffer(35)).length < 0.5 * d.length:
            continue
        c = list(d.coords)
        col, row = ~tr * (c[-2] if len(c) >= 2 else c[0])
        parts.append((round(d.length), round(float(ar[int(row), int(col)]), 2), round(float(car[int(row), int(col)]), 2),
                      "drawn" if d.intersection(new_u).length >= 0.5 * d.length else "NOT drawn"))
    und = [p for p in parts if p[3] != "drawn"]
    rows.append(dict(area=area, sid=r.sid, name=r["name"], old_len=round(r.len_m), old_own=r.area_km2,
                     old_full=r.area_full_km2, old_fish=r.fish_score, links=len(parts), undrawn_m=sum(p[0] for p in und),
                     undrawn_own=max([p[1] for p in und], default=np.nan),
                     undrawn_carried=max([p[2] for p in und], default=np.nan),
                     links_len_own_carried=str(sorted(parts, reverse=True))[:150]))
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 150)
print(pd.DataFrame(rows).to_string(index=False))
