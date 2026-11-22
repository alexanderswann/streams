"""One place on two sets of maps: the drawn stream lines within a radius (name, drainage, ends), the lakes, NHD's
detailed lines with their direction and NHDPlus's lines; and a picture, the two maps side by side.
OLD_MAPS and NEW_MAPS are folders with <area>/map3d_data.js (or <area>.js); the defaults are the published copy in
the site clone and the project's output folder.
[OLD_MAPS=<dir>] [NEW_MAPS=<dir>] AREA=<area> python place.py <lat> <lon> [radius m] [out.png]"""
import sys, os, json
P = "/Users/mac/Fishing"
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyproj
import config
from flowlib import reservoirs, FLOW
lat, lon = float(sys.argv[1]), float(sys.argv[2])
rad = float(sys.argv[3]) if len(sys.argv) > 3 else 600
png = sys.argv[4] if len(sys.argv) > 4 else None
fwd = pyproj.Transformer.from_crs(4326, config.CRS, always_xy=True)
back = pyproj.Transformer.from_crs(config.CRS, 4326, always_xy=True)
ll = lambda x, y: "%.5f,%.5f" % back.transform(x, y)[::-1]
p = shapely.Point(*fwd.transform(lon, lat)); win = p.buffer(rad)
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
drawn = {}
OLD = os.environ.get("OLD_MAPS", f"{P}/publish/alexanderswann.github.io/streams")
NEW = os.environ.get("NEW_MAPS", f"{P}/output")
js = lambda d: next(f for f in (f"{d}/{config.AREA}/map3d_data.js", f"{d}/{config.AREA}.js") if os.path.exists(f))
for tag, f in (("published", js(OLD)), ("new", js(NEW))):
    F = layer(open(f).read(), "streams")
    G = gpd.GeoSeries([shapely.LineString([c[:2] for c in q["geometry"]["coordinates"]]) for q in F], crs=4326).to_crs(config.CRS).values
    T = shapely.STRtree(G)
    rows = []
    for k in T.query(win, predicate="intersects"):
        q = F[k]["properties"]; g = G[k]
        rows.append(dict(name=q.get("n") or "-", km2=q.get("a"), fish=q.get("f"), cls=q.get("fc", q.get("c")), len_m=round(g.length), dist_m=round(g.distance(p)),
                         start=ll(*g.coords[0]), end=ll(*g.coords[-1])))
    drawn[tag] = [G[k] for k in T.query(win, predicate="intersects")]
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(f"== {tag}: {len(t)} drawn lines within {rad:.0f} m")
    if len(t):
        print(t.sort_values("dist_m").to_string(index=False))
    if tag == "published" and F:
        print("   (property keys: " + ",".join(sorted(F[0]["properties"].keys())) + ")")
lakes = reservoirs()
lg = shapely.make_valid(lakes.geometry.values)
near = [i for i in shapely.STRtree(lg).query(win, predicate="intersects")]
print("== lakes:", "; ".join(f"{lakes.gnis_name.iloc[i] if isinstance(lakes.gnis_name.iloc[i], str) else 'unnamed'} {lg[i].area / 1e4:.1f} ha" for i in near))
hr = []
for box in config.REGIONS:
    if not shapely.box(*config.REGIONS[box]["bbox"]).intersects(p):
        continue
    fl = gpd.read_file(f"{config.raw_dir(box)}/nhd_flowlines.gpkg").to_crs(config.CRS)
    fl = fl[fl.geometry.notna() & fl.intersects(win)]
    for g, nm, ft in zip(shapely.force_2d(fl.geometry.values), fl.gnis_name.values, fl.ftype.values):
        for x in getattr(g, "geoms", [g]):
            if x.geom_type == "LineString":
                hr.append((x, nm if isinstance(nm, str) else "-", int(ft)))
    print(f"== NHD detailed lines [{box}]:")
    for x, nm, ft in hr:
        print(f"   {ft} {nm:28s} {x.length:6.0f} m  {ll(*x.coords[0])} -> {ll(*x.coords[-1])}")
    break
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg", columns=["comid", "totdasqkm", "gnis_name"]).to_crs(config.CRS)
v2 = v2[v2.intersects(win)]
print("== NHDPlus lines:")
for _, f in v2.iterrows():
    g = shapely.line_merge(f.geometry); parts = list(getattr(g, "geoms", [g]))
    print(f"   {f.gnis_name if isinstance(f.gnis_name, str) else '-':28s} {f.totdasqkm:8.2f} km2  {ll(*parts[0].coords[0])} -> {ll(*parts[-1].coords[-1])}")
if png:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(17, 9))
    for ax, tag in zip(axs, ("published", "new")):
        for i in near:
            for poly in getattr(lg[i], "geoms", [lg[i]]):
                if poly.geom_type == "Polygon":
                    ax.fill(*poly.exterior.xy, color="#cfe6ff", zorder=1)
            c = lg[i].representative_point()
            if win.contains(c):
                ax.annotate(f"{lakes.gnis_name.iloc[i] if isinstance(lakes.gnis_name.iloc[i], str) else 'unnamed'}\n{lg[i].area / 1e4:.1f} ha", (c.x, c.y), fontsize=8, ha="center", color="#225")
        for x, nm, ft in hr:
            xs, ys = x.xy
            ax.plot(xs, ys, color="#888" if ft in (460, 558, 334) else "#c8a", lw=1, ls="--", zorder=2)
            m = x.interpolate(0.5, normalized=True); m2 = x.interpolate(min(x.length, x.length * 0.5 + 15))
            ax.annotate("", xy=(m2.x, m2.y), xytext=(m.x, m.y), arrowprops=dict(arrowstyle="->", color="#666", lw=1), zorder=2)
        for _, f in v2.iterrows():
            for part in getattr(f.geometry, "geoms", [f.geometry]):
                ax.plot(*part.xy, color="#2a2", lw=1, ls=":", zorder=2)
        for g in drawn[tag]:
            ax.plot(*g.xy, color="#06c" if tag == "published" else "#d30", lw=2.2, zorder=3)
            ax.plot(*g.coords[0], "o", color="k", ms=3, zorder=4)
        ax.plot(p.x, p.y, "*", color="gold", mec="k", ms=16, zorder=5)
        ax.set_xlim(p.x - rad, p.x + rad); ax.set_ylim(p.y - rad, p.y + rad); ax.set_aspect("equal"); ax.set_title(f"{tag}  ({config.AREA} {lat},{lon}; {rad:.0f} m)")
        ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(png, dpi=70)
    print("picture:", png)
