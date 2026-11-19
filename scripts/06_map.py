"""Combine every scored region into one interactive Leaflet map plus merged CSV/GPX exports.
Hillshades stay as separate PNGs next to the map (output/<region>/hillshade.png) to keep the HTML small."""
import json, os, colorsys, shapely, numpy as np, pandas as pd, geopandas as gpd, folium
from html import escape as hesc
from branca.element import MacroElement, Template
import shapely.ops
import rasterio
from urllib.parse import quote
from pyproj import Transformer
from labelpaths import label_paths
from folium.plugins import MeasureControl, MousePosition, Fullscreen
import matplotlib
from matplotlib import colors
from config import REGIONS, MAP_OUT, HOME, SHARED, ROOT as ROOT_DIR
from scoring import attach, score
import crossbox

done = [r for r in REGIONS if os.path.exists(f"{MAP_OUT}/{r}/streams_scored.gpkg")]
read = lambda name: pd.concat([gpd.read_file(f"{MAP_OUT}/{r}/{name}") for r in done], ignore_index=True)
s_ll = gpd.GeoDataFrame(read("streams_scored.gpkg"), crs=4326)
kp_ll = gpd.GeoDataFrame(read("waterfall_candidates.gpkg"), crs=4326).sort_values("drop_m", ascending=False)
trails = gpd.GeoDataFrame(read("trails.gpkg"), crs=4326)
known_falls = gpd.GeoDataFrame(read("known_falls.gpkg"), crs=4326)
known_falls = known_falls[known_falls.geometry.notna()]
# road closures from 07_road_closures.py (optional; re-run that script to refresh)
closures = gpd.read_file(f"{MAP_OUT}/road_closures.gpkg") if os.path.exists(f"{MAP_OUT}/road_closures.gpkg") else None
gated = gpd.read_file(f"{MAP_OUT}/gated_roads.gpkg") if os.path.exists(f"{MAP_OUT}/gated_roads.gpkg") else None
if closures is not None and len(closures):
    # nearest full closure within 3 km of each drop, for the popup
    full = closures[closures.severity.str.startswith("full")].to_crs(26911).reset_index(drop=True)
    near = gpd.sjoin_nearest(kp_ll[["geometry"]].to_crs(26911), full[["road", "geometry"]], how="left",
                             max_distance=3000, distance_col="closure_m").groupby(level=0).first()
    kp_ll["closure_road"], kp_ll["closure_m"] = near.road, near.closure_m.round(-1)
print("regions:", done)

# access (08/09), sun (10) and context (11) attributes, then the final fish score (scoring.py)
dirs = [f"{MAP_OUT}/{r}" for r in done]
s_ll = score(attach(s_ll.drop(columns="fish_score"), "sid", dirs, "streams"))
# drainage / fork / channel Strahler order from 05c_drainages.py
MINOR = "Minor front-range drainages"
sd = pd.concat([pd.read_csv(f"{MAP_OUT}/{r}/stream_drainage.csv") for r in done
                if os.path.exists(f"{MAP_OUT}/{r}/stream_drainage.csv")], ignore_index=True)
s_ll = s_ll.drop(columns=[c for c in ("drainage", "fork", "strahler") if c in s_ll]).merge(sd, on="sid", how="left")
s_ll["drainage"] = s_ll.drainage.fillna(MINOR)
s_ll["fork"] = s_ll.fork.fillna(s_ll.drainage)
s_ll["strahler"] = s_ll.strahler.fillna(s_ll["order"]).clip(1, 7).astype(int)
basins = pd.concat([gpd.read_file(f"{MAP_OUT}/{r}/drainages.gpkg") for r in done
                    if os.path.exists(f"{MAP_OUT}/{r}/drainages.gpkg")], ignore_index=True)

# Basins cut by a box edge join the drainage they continue into in the neighbouring range: Sierra Pelona's
# San Francisquito and Bouquet canyons -> Santa Clara River, upper Piru Creek -> Piru Creek, North Fork Lytle ->
# Lytle Creek. 05c records where each basin leaves its box (out_x/out_y, one cell outside: on its reaches, and on the
# outline of an unnamed basin); following the neighbour's flow directions downhill from there to its first mapped
# stream gives the drainage (crossbox.py). Unnamed basins take that reach's drainage and fork; named ones keep their
# own name as a fork of it. A few passes let chains (Pelona -> San Gabriels -> Piru) settle. Unnamed outlines that
# join no named drainage are dropped.
for c_ in ("out_x", "out_y"):
    if c_ not in basins:
        basins[c_] = np.nan
basins["rkey"] = basins.region.map({cfg_["label"]: k_ for k_, cfg_ in REGIONS.items()})
if "out_x" in s_ll and s_ll.out_x.notna().any():
    s_ll["rkey"] = s_ll.sid.str.split(":").str[0]
    tree = s_ll.to_crs(26911).sindex
    # positions in the full s_ll (grouping a filtered copy would give positions within the copy)
    groups = {g: np.asarray(ix) for g, ix in s_ll.reset_index(drop=True).groupby(["rkey", "out_x", "out_y"],
                                                                                   dropna=True).indices.items()}
    outlines = {(r_, x_, y_) for r_, x_, y_ in zip(basins.rkey, basins.out_x, basins.out_y) if pd.notna(x_)}
    edges, fdirs = crossbox.shared_edges(done), {}
    def fdir_of(region):
        if region not in fdirs:
            with rasterio.open(crossbox.fdir_path(region)) as src_:
                fdirs[region] = (src_.read(1), src_.transform)
        return fdirs[region]
    target = {}
    for g in set(groups) | outlines:
        for b_, away in crossbox.neighbours(g[0], g[1], g[2], edges):
            # from the crossing, follow the neighbour's own D8 flow directions downhill (up to 6 km) to its first
            # mapped stream: the neighbour's streams start only where enough area has gathered below the edge
            for *_, x_, y_ in crossbox.crossing(b_, *fdir_of(b_), g[1], g[2], away):
                cand = [i for i in tree.query(shapely.Point(x_, y_), predicate="dwithin", distance=30)
                        if s_ll.rkey.iat[i] == b_]
                if cand:
                    target[g] = max(cand, key=lambda i: s_ll.area_km2.iat[i])
                    break
            if g in target:
                break
    d0, f0 = s_ll.drainage.to_numpy().copy(), s_ll.fork.to_numpy().copy()
    dcur, fcur = d0.copy(), f0.copy()
    for _ in range(6):
        dnew, fnew = dcur.copy(), fcur.copy()
        for g, ti in target.items():
            if g not in groups or dcur[ti] == MINOR:
                continue
            ix = groups[g]
            if d0[ix[0]] == MINOR:
                dnew[ix], fnew[ix] = dcur[ti], fcur[ti]
            else:
                dnew[ix] = dcur[ti]
        if (dnew == dcur).all() and (fnew == fcur).all():
            break
        dcur, fcur = dnew, fnew
    moved = pd.DataFrame({"r": s_ll.region.values, "a": d0, "b": dcur})
    moved = moved[moved.a != MINOR].groupby(["r", "a"]).b.agg(lambda x: x.iloc[0] if x.nunique() == 1 else None)
    relabel = {k: v for k, v in moved.items() if pd.notna(v) and v != k[1]}   # only when the whole named basin moved
    s_ll["drainage"], s_ll["fork"] = dcur, fcur
    basins["drainage"] = [relabel.get((r_, d_), d_) for r_, d_ in zip(basins.region, basins.drainage)]
    # an unnamed outline takes the drainage and fork of the reach its water continues into
    link = [target.get((r_, x_, y_)) if d_ == MINOR else None
            for r_, x_, y_, d_ in zip(basins.rkey, basins.out_x, basins.out_y, basins.drainage)]
    link = [ti if ti is not None and dcur[ti] != MINOR else None for ti in link]
    basins["drainage"] = [dcur[ti] if ti is not None else d_ for ti, d_ in zip(link, basins.drainage)]
    basins["fork"] = [fcur[ti] if ti is not None else f_ for ti, f_ in zip(link, basins.fork)]
    print("cross-range links:", len(target), "| renamed basins:", sorted(set(relabel.items()))[:12],
          f"| unnamed outlines joined: {sum(ti is not None for ti in link)} of {len(outlines)}")
basins = basins[basins.drainage != MINOR].drop(columns=["out_x", "out_y", "rkey"]).reset_index(drop=True)
kp_ll = attach(kp_ll, "did", dirs, "drops")
CTX = f"{MAP_OUT}/context"
ctx = lambda n: gpd.read_file(f"{CTX}/{n}.gpkg") if os.path.exists(f"{CTX}/{n}.gpkg") else None

def approach(r):
    """'Drive 95 min (117 km) → park at X → bike 12 min → hike 40 min' for a reach or drop row."""
    if pd.isna(getattr(r, "approach_min", np.nan)):
        return "No route from an open road"
    bits = []
    if pd.notna(r.drive_min):
        bits.append(f"Drive {r.drive_min:.0f} min ({r.drive_km:.0f} km) from {HOME['label']}")
    if isinstance(r.th_road, str):
        bits.append(f"park at {r.th_road}")
    if r.bike_min >= 1:
        chk = getattr(r, "bike_check", None)     # 08_hike.py: the ride uses a fire road bikes may not be allowed on
        bits.append(f"bike {r.bike_min:.0f} min on closed roads, fire roads or bike trails"
                    + (f" (⚠ fire road: double-check bike access, {r.bike_check_min:.0f} min of the ride: {chk})"
                       if isinstance(chk, str) else ""))
    bits.append(f"hike {r.walk_min:.0f} min")
    return " → ".join(bits)

# ---- merged exports ----
ACCESS = ["drive_min", "drive_km", "th_road", "th_lat", "th_lon", "bike_min", "bike_check", "bike_check_min", "walk_min",
          "approach_min"]
CONTEXT = ["sun_hours", "shade_pct", "northness", "canopy_pct", "air_aug", "burn_fire", "burn_year", "burn_sev", "debris_flow",
           "trout_water", "trout_found", "trout_absent", "trout_ev", "crit_habitat", "wilderness", "non_fs_land",
           "cpad_access"]
FLOWC = ["water_class", "dry_cfs", "dry_cfs_drought", "flow_years", "flow_src", "below_dam",   # 05b_flow.py
         "below_div", "div_share", "div_years", "water_by_gauge"]                                # (the last: scoring.py)
for c_ in CONTEXT + FLOWC:   # older context files may lack a column
    if c_ not in s_ll:
        s_ll[c_] = None
    if c_ not in kp_ll:
        kp_ll[c_] = None
kp_ll.drop(columns="geometry").to_csv(f"{MAP_OUT}/waterfall_candidates.csv", index=False)
mid = s_ll.geometry.interpolate(0.5, normalized=True)
s_ll.assign(lat=mid.y.round(6), lon=mid.x.round(6)).sort_values("fish_score", ascending=False)[
    ["sid", "region", "drainage", "fork", "name", "flow", *FLOWC, "water_term", "fish_score", "thermal", "tailwater", "burn_factor", "trout_factor", "heat_factor", "area_km2", "area_edge_km2", "area_full_km2", "strahler", "elev_m",
     "gradient_pct", "len_m", "approach_med_min", "bike_med_min"] + ACCESS + CONTEXT + ["lat", "lon"]
].to_csv(f"{MAP_OUT}/stream_reaches_ranked.csv", index=False)

# GPX for a GPS / phone (onX, Gaia, CalTopo all import GPX). The apps refuse a file that isn't valid XML, so text
# is escaped: region names such as "Piru Creek & Castaic" hold a bare "&"
SHOW = ["unmapped waterfall-like step", "unmapped cascade", "unmapped short fall (big creek)", "matches mapped waterfall"]
good = kp_ll[kp_ll.status.isin(SHOW)]
with open(f"{MAP_OUT}/waterfall_candidates.gpx", "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="la-stream-analysis" xmlns="http://www.topografix.com/GPX/1/1">\n')
    for i, r in enumerate(good.itertuples()):
        tag = "WF" if r.status.startswith("matches") else "SF" if r.status.endswith("(big creek)") else "DROP"
        nm = f"{tag}{i+1:03d} {r.drop_m:.0f}m"
        stream = r.stream if isinstance(r.stream, str) and r.stream else "unnamed"   # a missing name is NaN, not None
        desc = hesc(f"{r.region}; {stream}; {r.drop_m} m over {r.run_m:.0f} m; {r.flow}; {approach(r)}", quote=False)
        f.write(f'<wpt lat="{r.lat}" lon="{r.lon}"><name>{nm}</name><desc>{desc}</desc></wpt>\n')
        f.write(f'<wpt lat="{r.pool_lat}" lon="{r.pool_lon}"><name>{nm} pool</name></wpt>\n')
    f.write("</gpx>\n")

# ---- map ----
b = s_ll.total_bounds
m = folium.Map(location=[(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], zoom_start=9, tiles=None, control_scale=True,
               prefer_canvas=True)
# Default basemap is deliberately quiet (light gray + gray terrain shading + muted labels) so the analysis colors
# read clearly; the busier topo/satellite maps, which draw their own streams, are one click away.
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"
folium.TileLayer(f"{ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}", attr="Esri, HERE, Garmin",
                 name="Light gray terrain (default)", max_zoom=16).add_to(m)
folium.TileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
                 attr="USGS The National Map", name="USGS Topo (busy: its own streams)", max_zoom=16, show=False).add_to(m)
folium.TileLayer(f"{ESRI}/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",
                 attr="Esri, Maxar, Earthstar Geographics", name="Satellite (Esri)", max_zoom=19, show=False).add_to(m)
folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attr="OpenTopoMap (CC-BY-SA)",
                 name="OpenTopoMap", max_zoom=17, show=False).add_to(m)
folium.TileLayer(f"{ESRI}/Elevation/World_Hillshade/MapServer/tile/{{z}}/{{y}}/{{x}}", attr="Esri", overlay=True,
                 name="Terrain shading", opacity=0.45, max_zoom=16).add_to(m)
folium.TileLayer(f"{ESRI}/Canvas/World_Light_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}", attr="Esri",
                 overlay=True, name="Place & road labels", max_zoom=16, opacity=0.55).add_to(m)
hs_group = folium.FeatureGroup(name="DEM color relief (10 m 3DEP)", show=False)
for r in done:
    hb = json.load(open(f"{MAP_OUT}/{r}/hillshade_bounds.json"))
    ov = folium.raster_layers.ImageOverlay("https://example.invalid/x.png", opacity=0.75,
                                           bounds=[[hb["south"], hb["west"]], [hb["north"], hb["east"]]])
    ov.url = f"{r}/hillshade.png"  # relative link, not embedded
    ov.add_to(hs_group)
hs_group.add_to(m)

# ---- streams by drainage ----
# One hue per drainage (neighbouring drainages never share one), forks of a drainage are lighter/darker shades of
# it. Line width and lightness follow Strahler order, so trunks read first and headwater rills recede. Minor
# front-range drainages are a quiet slate. Styling, labels, legend and the colour-mode switch live in
# map_drainages.js (initDrainageMap), drawn on one canvas for speed.
PALETTE = ["#1864ab", "#d9480f", "#0b7285", "#2b8a3e", "#c92a2a", "#9c36b5", "#5c940d", "#1098ad", "#a05a2c",
           "#364fc7"]
MINOR_COL = "#8193a6"
bm = basins.to_crs(26911)
def fill_small_holes(g, min_m2=50000):
    """Drop pockets under 0.05 km2 (a few 50 m cells left between forks), which would draw as tiny rings."""
    parts = g.geoms if g.geom_type == "MultiPolygon" else [g]
    return shapely.MultiPolygon([shapely.Polygon(p.exterior, [h for h in p.interiors if shapely.Polygon(h).area >= min_m2])
                                 for p in parts if p.geom_type == "Polygon"])
dpoly = bm.dissolve("drainage").reset_index()
dpoly["geometry"] = [fill_small_holes(g) for g in dpoly.geometry]
dpoly["km2"] = dpoly.area / 1e6
dpoly = dpoly.sort_values("km2", ascending=False).reset_index(drop=True)
near_d = gpd.sjoin(dpoly[["drainage", "geometry"]].assign(geometry=dpoly.buffer(400)), dpoly[["drainage", "geometry"]],
                   predicate="intersects")
near_d = near_d[near_d.drainage_left != near_d.drainage_right].groupby("drainage_left").drainage_right.agg(set)
dcol, used = {}, {c: 0 for c in PALETTE}
for d in dpoly.drainage:
    banned = {dcol.get(n) for n in near_d.get(d, set())}
    c = min((c for c in PALETTE if c not in banned), key=lambda c: (used[c], PALETTE.index(c)))
    dcol[d], used[c] = c, used[c] + 1
dcol[MINOR] = MINOR_COL

def shade(hexc, dl):
    h, l, s_ = colorsys.rgb_to_hls(*colors.to_rgb(hexc))
    return colors.to_hex(colorsys.hls_to_rgb(h, min(max(l + dl, 0.18), 0.72), s_))
SHADES = [0.14, -0.11, 0.24, -0.19, 0.31, 0.07, -0.05]
fcol = {}
for d, g in bm.assign(km2=bm.area / 1e6).groupby("drainage"):
    forks = [f for f in g.sort_values("km2", ascending=False).fork if f != d]
    fcol[(d, d)] = dcol[d]
    for i, f in enumerate(forks):
        fcol[(d, f)] = shade(dcol[d], SHADES[i % len(SHADES)])

def cfs(v):
    return f"{v:.0f}" if v >= 10 else f"{v:.1f}" if v >= 1 else f"{v:.2f}"


def summer_flow(r):
    """Popup line from the flow model (05b_flow.py): class, typical / drought-year low flow, share of summers flowing.
    Below a gauged diversion, the record of the USGS gauge below it too; where the score uses it, it comes first."""
    c = r.water_class
    if not isinstance(c, str) or c == "no data":
        return ""
    dam = r.below_dam if isinstance(r.below_dam, str) else ""
    if c == "reservoir":
        return f"reservoir ({dam[3:] or 'lake'})"
    bits = []
    if pd.notna(r.dry_cfs):
        bits.append(f"low flow about {cfs(r.dry_cfs)} cfs in a typical July–October, {cfs(r.dry_cfs_drought)} cfs in a "
                    f"drought year")
    if pd.notna(r.flow_years):
        bits.append(f"kept flowing {r.flow_years:.0%} of summers since 2011")
    src = "TNC Natural Flows model" + (", scaled from the creek below" if r.flow_src == "scaled" else "")
    div = r.below_div if isinstance(r.below_div, str) else ""
    gauge = (f"below {div}: the USGS gauge there kept flowing {r.div_share:.0%} of summers in {r.div_years}"
             if div and pd.notna(r.div_share) else "")
    if gauge and r.water_by_gauge == True:
        return (f"{c} · {gauge}, which the score uses · the {src}, which can't see the diversion: " + ", ".join(bits)
                + f" · NHD: {r.flow}")
    return (" · ".join([c] + bits) + f" ({src})" + (f" · below {dam}: releases set the flow" if dam else "")
            + (f" · {gauge}" if gauge else "") + f" · NHD: {r.flow}")


def sev_label(v):
    return ("mostly high soil burn severity" if v >= 0.85 else "moderate to high soil burn severity" if v >= 0.6
            else "low to moderate soil burn severity" if v >= 0.3 else "very low soil burn severity")


# the hottest creek with a trout record (11_context.py), for the heat gate's popup line
tev = ctx("trout_evidence")
HOT = (tev[tev.trout.astype(bool) & ~tev.lake.astype(bool)].air_aug.max()
       if tev is not None and "air_aug" in tev else np.nan)


def heat_line(air, f):
    if not (pd.notna(f) and f < 1):
        return ""
    rec = f" (at most {HOT:.1f} °C)" if pd.notna(HOT) else ""
    return (f"August air averages {air:.1f} °C here (PRISM 1991–2020 normal), hotter than any creek in these ranges "
            f"where trout have been recorded{rec} · fish score × {f:.2f}")
s_show = s_ll.assign(geometry=shapely.set_precision(s_ll.geometry.simplify(0.00008).values, 1e-5))
mid_ll = s_show.geometry.interpolate(0.5, normalized=True)
nz = lambda v, nd=0: None if pd.isna(v) else round(float(v), nd) if nd else int(round(float(v)))
props = pd.DataFrame({
    "n": s_show["name"].where(s_show["name"].notna(), None),
    "d": s_show.drainage, "k": s_show.fork, "o": s_show.strahler,
    "c": [fcol.get((d, f), dcol.get(d, MINOR_COL)) for d, f in zip(s_show.drainage, s_show.fork)],
    "fs": s_show.fish_score.round(0).astype(int),
    "fl": [f"summer: {c}" if isinstance(c, str) and c != "no data" else f"NHD {f}" for c, f in zip(s_show.water_class, s_show.flow)],
    "dq": [summer_flow(r) for r in s_show.itertuples()],
    "a": s_show.area_full_km2.fillna(s_show.area_km2).astype(float).round(1), "el": [nz(v) for v in s_show.elev_m], "gr": s_show.gradient_pct.astype(float).round(1),
    "acc": [approach(r) for r in s_show.itertuples()],
    "sun": [" · ".join(x for x in (
                f"{h:.1f} h direct sun mid-July ({p:.0f}% shaded by terrain)" if pd.notna(h) else "",
                f"tree canopy {cv:.0f}%" if pd.notna(cv) else "",
                f"slope faces {'north' if n > 0.04 else 'south' if n < -0.04 else 'east/west or mixed'}" if pd.notna(n) else "",
                f"August air averages {a:.0f} °C" if pd.notna(a) else "",
                f"tailwater below {tw}: the dam releases cold water from the bottom of the reservoir" if isinstance(tw, str) else "")
                       if x)
            for h, p, n, cv, a, tw in zip(s_show.sun_hours, s_show.shade_pct, s_show.northness, pd.to_numeric(s_show.canopy_pct),
                                          pd.to_numeric(s_show.air_aug), s_show.tailwater)],
    "ht": [heat_line(a, f) for a, f in zip(pd.to_numeric(s_show.air_aug), s_show.heat_factor)],
    "burn": [" · ".join(x for x in (
                 f"{f} fire {y:.0f}" + (f" ({sev_label(sv)})" if pd.notna(sv) else "") if pd.notna(y) else "",
                 f"⚠ debris-flow hazard {dfl}" if isinstance(dfl, str) else "") if x)
             for f, y, sv, dfl in zip(s_show.burn_fire, s_show.burn_year, pd.to_numeric(s_show.burn_sev), s_show.debris_flow)],
    "tr": [" · ".join(x for x in (t if isinstance(t, str) else "", e if isinstance(e, str) else "") if x)
           for t, e in zip(s_show.trout_water, s_show.trout_ev)],
    "flags": [" · ".join(x for x in (f"⚠ critical habitat: {c}" if isinstance(c, str) else "",
                                     f"{w} (no bikes)" if isinstance(w, str) else "",
                                     f"⚠ {a}" if isinstance(a, str) else
                                     "⚠ non-Forest-Service land" if isinstance(o, str) else "") if x)
              for c, w, o, a in zip(s_show.crit_habitat, s_show.wilderness, s_show.non_fs_land, s_show.cpad_access)],
    "y": mid_ll.y.round(5), "x": mid_ll.x.round(5)})
s_feat = gpd.GeoDataFrame(props, geometry=s_show.geometry.values, crs=4326).sort_values(["o", "fs"])

# drainage / fork polygons, label points (inside the largest part) and legend entries
def label_pt(g):
    """Pole of inaccessibility of the largest part: the label sits well inside the basin."""
    g = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    return shapely.ops.polylabel(g, tolerance=200)
fpoly = bm.dissolve(["drainage", "fork"]).reset_index()
fpoly["geometry"] = [fill_small_holes(g) for g in fpoly.geometry]
fpoly["c"] = [fcol.get((d, f), dcol[d]) for d, f in zip(fpoly.drainage, fpoly.fork)]
to_ll = lambda geoms: gpd.GeoSeries(geoms, crs=26911).to_crs(4326)
fl_pts = to_ll([label_pt(g) for g in fpoly.geometry])
dl_pts = to_ll([label_pt(g) for g in dpoly.geometry])
f_json = json.loads(fpoly[["drainage", "fork", "c", "geometry"]].to_crs(4326).assign(
    geometry=lambda g: shapely.set_precision(g.geometry.simplify(0.0002).values, 1e-5)).to_json())
d_json = json.loads(dpoly[["drainage", "geometry"]].to_crs(4326).assign(
    geometry=lambda g: shapely.set_precision(g.geometry.boundary.simplify(0.0002).values, 1e-5)).to_json())
region_of = s_ll.groupby("drainage").region.agg(lambda r: r.mode().iloc[0])
dbounds = dpoly.to_crs(4326).bounds
drains = [dict(name=d, color=dcol[d], dark=shade(dcol[d], -0.12), region=region_of.get(d, ""), km2=round(k),
               lab=[round(p.y, 5), round(p.x, 5)], b=[[r.miny, r.minx], [r.maxy, r.maxx]])
          for d, k, p, r in zip(dpoly.drainage, dpoly.km2, dl_pts, dbounds.itertuples())]
for e in drains:  # forks of each drainage, biggest first
    sel = fpoly.drainage == e["name"]
    e["forks"] = sorted([dict(name=f, color=c, km2=round(a / 1e6), lab=[round(p.y, 5), round(p.x, 5)])
                         for f, c, a, p in zip(fpoly.fork[sel], fpoly.c[sel], fpoly.area[sel], fl_pts[sel])],
                        key=lambda x: -x["km2"])
drains.append(dict(name=MINOR, color=MINOR_COL, dark="#5c6b7a", region="", km2=None, lab=None, b=None, forks=[]))
def merge_lines(geoms):
    """Join touching lines into as few lines as possible (linemerge rejects a single line)."""
    u = shapely.union_all(geoms)
    u = shapely.ops.linemerge(u) if u.geom_type == "MultiLineString" else u
    return [g for g in getattr(u, "geoms", [u]) if g.geom_type == "LineString"]


# ---- Pacific Crest Trail (02c_pct.py): one line per PCT section, plus label points along the trail ----
PCT_SECTIONS = {"A": "Campo → Warner Springs", "B": "Warner Springs → San Gorgonio Pass (I-10)",
                "C": "San Gorgonio Pass (I-10) → Cajon Pass (I-15)", "D": "Cajon Pass (I-15) → Agua Dulce",
                "E": "Agua Dulce → Tehachapi Pass (Hwy 58)", "F": "Tehachapi Pass → Walker Pass"}
pct_json, pct_labels = None, []
if os.path.exists(f"{SHARED}/pct.gpkg"):
    pct = gpd.read_file(f"{SHARED}/pct.gpkg").to_crs(26911)
    pct["sec"] = pct.section.str.extract(r"Section ([A-Z])\b", expand=False).fillna("?")
    secs = pct.dissolve("sec").reset_index()
    secs["geometry"] = [shapely.ops.linemerge(g) if g.geom_type == "MultiLineString" else g for g in secs.geometry]
    secs["label"] = [f"Section {k}: {PCT_SECTIONS.get(k, '')}".rstrip(": ") for k in secs.sec]
    pct_json = json.loads(secs[["sec", "label", "geometry"]].to_crs(4326).assign(
        geometry=lambda g: shapely.set_precision(g.geometry.simplify(0.00002).values, 1e-5)).to_json(drop_id=True))
    # labels that bend along the trail, one set per zoom band (labelpaths.py); "Pacific Crest Trail" is ~112 px
    PCT_BANDS = [(11, 15, 10000, 12000, [65]), (12, 9, 5000, 6000, [32]), (13, 5, 2500, 3000, [16, 8])]
    pct_lines = merge_lines(pct.geometry.values)
    pct_labels = [lab for ln in pct_lines for lab in label_paths(ln, PCT_BANDS, 112)]
    whole = shapely.MultiLineString(pct_lines) if pct_lines else u_
    print("PCT", len(secs), "sections,", round(whole.length / 1000), "km | labels per zoom band:",
          pd.Series([l["z"] for l in pct_labels]).value_counts().sort_index().to_dict())
# ---- Trails and fire roads (02d_trails.py; older runs fall back to each range's OSM paths) ----
# Drawn by map_drainages.js / map3d.html with detail revealed by zoom: rank 1 hiking routes and named trails, 2 named
# fire roads, 3 unnamed trails, 4 unnamed fire roads. Named trails and fire roads get labels that bend along them.
SAC = {"hiking": "easy (T1)", "mountain_hiking": "mountain hiking (T2)", "demanding_mountain_hiking": "demanding (T3)",
       "alpine_hiking": "alpine (T4)", "demanding_alpine_hiking": "demanding alpine (T5)",
       "difficult_alpine_hiking": "difficult alpine (T6)"}
study = gpd.GeoSeries([shapely.box(*v["bbox"]) for v in REGIONS.values()], crs=26911).union_all().buffer(1000)
study_ll = gpd.GeoSeries([study], crs=26911).to_crs(4326).iloc[0]
if os.path.exists(f"{SHARED}/trails.gpkg"):
    tr = gpd.read_file(f"{SHARED}/trails.gpkg")
    tr = tr[tr.intersects(study_ll)]
    col_ = lambda c, d=None: tr[c] if c in tr else pd.Series(d, index=tr.index)
    def agency(s):
        s = str(s)
        for k, v in (("Forest Service", "USFS"), ("National Park", "NPS"), ("State Park", "CA State Parks"),
                     ("Los Angeles County", "LA County Parks")):
            if k.lower() in s.lower():
                return v
        return s[:40]
    unoff = col_("unofficial", False).fillna(False).astype(bool)
    tprops = pd.DataFrame({
        "cw": col_("closed_why"), "n": tr["name"], "k": tr.kind, "rk": tr["rank"].astype(int), "s": tr.sac_scale.map(SAC), "sf": tr.surface,
        "rt": tr.route, "cl": col_("closed", False).fillna(False).astype(int),
        "f": (tr.informal.eq("yes") | tr.trail_visibility.isin(["bad", "horrible", "no"]) | unoff
              | col_("source", "OSM").eq("official only")).astype(int),
        "u": unoff.astype(int), "of": col_("official").map(lambda v: agency(v) if isinstance(v, str) else None),
        "no": col_("trail_no"), "us": col_("uses"), "g": col_("gated"),
        "src": col_("source", "OSM").where(lambda x: x != "OSM"),
        "b": col_("bike", "unknown"), "bw": col_("bike_why"), "mtb": col_("mtb_scale")})
else:
    tr = trails.assign(name=trails["name"].where(trails["name"] != "trail"))
    tprops = pd.DataFrame({"n": tr["name"], "k": "trail", "rk": np.where(tr["name"].notna(), 1, 3)})
t_feat = gpd.GeoDataFrame(tprops, geometry=shapely.set_precision(tr.geometry.simplify(0.00004).values, 1e-5), crs=4326)
t_feat = t_feat[~t_feat.geometry.is_empty].sort_values("rk", ascending=False)
if os.path.exists(f"{SHARED}/access_roads.gpkg"):   # the road layers draw fire roads; keep the ones on hiking routes
    t_feat = t_feat[(t_feat.k != "fire road") | t_feat.get("rt", pd.Series(None, index=t_feat.index)).notna()]
def beside_creeks(feat, step=10.0, max_d=80.0, min_run=40.0):
    """Split trail / road lines into the runs that follow a creek of order 2+ (within max_d m and within ~50° of its
    direction), so the maps can draw those runs shifted to the creek's far side instead of on top of it. Adds sd (+1:
    the creek is on the line's left, so it's drawn shifted right; -1: the other way), so (the creek's order) and dm
    (median metres apart: the maps shift only by what the two line widths need at each zoom)."""
    feat = feat[~feat.geometry.is_empty]
    if not len(feat):
        return feat
    cr = s_ll[s_ll.strahler >= 2].to_crs(26911)
    cg, co = cr.geometry.values, cr.strahler.values.astype(int)
    ex = feat.to_crs(26911).explode(index_parts=False)
    ex = ex[ex.geom_type == "LineString"]
    lines = ex.geometry.values
    L = shapely.length(lines)
    n = np.maximum(2, (L // step).astype(int) + 1)
    first = np.r_[0, np.cumsum(n)[:-1]]
    own = np.repeat(np.arange(len(lines)), n)
    idx = np.arange(len(own))
    d = (idx - np.repeat(first, n)) / np.repeat(n - 1, n) * np.repeat(L, n)
    pts = shapely.line_interpolate_point(np.repeat(lines, n), d)
    X, Y = shapely.get_x(pts), shapely.get_y(pts)
    nx_ = np.minimum(idx + 1, len(idx) - 1)
    nx_ = np.where(own[nx_] == own, nx_, idx)
    pv_ = np.maximum(idx - 1, 0)
    pv_ = np.where(own[pv_] == own, pv_, idx)
    tx, ty = X[nx_] - X[pv_], Y[nx_] - Y[pv_]
    sd, so, dm = np.zeros(len(idx), np.int8), np.zeros(len(idx)), np.full(len(idx), np.nan)
    (pi, ci), dist = shapely.STRtree(cg).query_nearest(pts, max_distance=max_d, return_distance=True, all_matches=False)
    if len(pi):
        cl = cg[ci]
        pos = shapely.line_locate_point(cl, pts[pi])
        a, b = shapely.line_interpolate_point(cl, np.maximum(pos - 8, 0)), shapely.line_interpolate_point(cl, pos + 8)
        q = shapely.line_interpolate_point(cl, pos)
        sx, sy = shapely.get_x(b) - shapely.get_x(a), shapely.get_y(b) - shapely.get_y(a)
        ux, uy = tx[pi], ty[pi]
        par = np.abs(ux * sx + uy * sy) >= 0.64 * np.hypot(ux, uy) * np.hypot(sx, sy)
        cross = ux * (shapely.get_y(q) - Y[pi]) - uy * (shapely.get_x(q) - X[pi])
        side = np.where(dist < 2, 2, np.sign(cross)).astype(np.int8)        # 2: right on the creek, side unknown
        ok = par & (side != 0)
        sd[pi[ok]], so[pi[ok]], dm[pi[ok]] = side[ok], co[ci[ok]], dist[ok]

    def runs(v):
        b_ = np.r_[0, np.flatnonzero(np.diff(v)) + 1, len(v)]
        return [(b_[j], b_[j + 1], v[b_[j]]) for j in range(len(b_) - 1)]
    keep, pieces = [], []
    props = ex.drop(columns="geometry").reset_index(drop=True)
    for i, ln in enumerate(lines):
        s0, s1 = first[i], first[i] + n[i]
        v = sd[s0:s1].copy()
        if v.any():
            for a_, b_, val in runs((v != 0).astype(np.int8)):      # a run on the creek takes its run's side
                if val:
                    seg = v[a_:b_]
                    seg[seg == 2] = np.sign(seg[np.abs(seg) == 1].sum()) or 1
            for a_, b_, val in runs(v):                              # bridge gaps of up to 20 m on the same side
                if val == 0 and b_ - a_ <= 2 and a_ > 0 and b_ < len(v) and v[a_ - 1] == v[b_] != 0:
                    v[a_:b_] = v[b_]
            for a_, b_, val in runs(v):                              # drop runs too short to matter
                if val and (b_ - a_) * step < min_run:
                    v[a_:b_] = 0
        if not v.any():
            keep.append((i, ln, None, None, None))
            continue
        dd = d[s0:s1]
        for a_, b_, val in runs(v):
            lo = 0 if a_ == 0 else (dd[a_ - 1] + dd[a_]) / 2
            hi = L[i] if b_ == len(v) else (dd[b_ - 1] + dd[b_]) / 2
            g_ = shapely.ops.substring(ln, lo, hi)
            if g_.geom_type != "LineString" or g_.length < 1:
                continue
            on = slice(s0 + a_, s0 + b_)
            keep.append((i, g_, int(val) if val else None, int(np.median(so[on])) if val else None,
                         int(round(np.nanmedian(dm[on]))) if val else None))
    out = props.iloc[[k[0] for k in keep]].reset_index(drop=True)
    out["sd"], out["so"], out["dm"] = [k[2] for k in keep], [k[3] for k in keep], [k[4] for k in keep]
    out = gpd.GeoDataFrame(out, geometry=[k[1] for k in keep], crs=26911).to_crs(4326)
    out["geometry"] = shapely.set_precision(out.geometry.values, 1e-5)
    out = out[~out.geometry.is_empty]
    on_ = out.sd.notna()
    print(f"  beside a creek: {out[on_].to_crs(26911).length.sum() / out.to_crs(26911).length.sum():.0%} of the length, "
          f"{int(on_.sum())} of {len(out)} pieces")
    return out


TRAIL_BANDS = [(13, 5, 1500, 3000, [16]), (14, 3, 800, 1500, [8, 4, 2])]
trail_labels = []
tu = t_feat[t_feat.n.notna() & ~t_feat.n.fillna("").str.contains("Pacific Crest", case=False)].to_crs(26911)
for nm, grp in tu.groupby("n"):
    for ln in merge_lines(grp.geometry.values):
        if ln.length >= 1600:
            trail_labels += [dict(lab, t=nm) for lab in label_paths(ln, TRAIL_BANDS, len(nm) * 5.6 + 6)]
print("trails:")
t_feat = beside_creeks(t_feat)
# ---- access roads, parking and trailheads (02e_access.py) ----
roads_json, park_json = None, None
if os.path.exists(f"{SHARED}/access_roads.gpkg"):
    ar = gpd.read_file(f"{SHARED}/access_roads.gpkg")
    ar = ar[ar.intersects(study_ll)]
    getc = lambda c: ar[c] if c in ar else pd.Series(None, index=ar.index)
    r_feat = gpd.GeoDataFrame({"n": ar["name"], "c": ar.cls, "sf": getc("surface"), "tt": getc("tracktype"),
                               "sm": getc("smoothness"), "fs": getc("fs_id"), "lv": getc("fs_level"),
                               "se": getc("seasonal"), "ac": getc("access_conditional"),
                               "mv": getc("mvum"), "od": getc("open_dates"), "cw": getc("closed_why")},
                              geometry=shapely.set_precision(ar.geometry.simplify(0.00004).values, 1e-5), crs=4326)
    print("access roads:")
    roads_json = json.loads(beside_creeks(r_feat).to_json(na="drop", drop_id=True))
    # named unpaved roads get labels too (fire roads used to be labelled as trails)
    named_r = r_feat[r_feat.n.notna() & r_feat.c.ne("paved") & ~r_feat.n.isin(set(t_feat.n.dropna()))].to_crs(26911)
    for nm, grp in named_r.groupby("n"):
        for ln in merge_lines(grp.geometry.values):
            if ln.length >= 1600:
                trail_labels += [dict(lab, t=nm) for lab in label_paths(ln, TRAIL_BANDS, len(nm) * 5.6 + 6)]
    print("access roads", len(r_feat), "|", r_feat.c.value_counts().to_dict())
if os.path.exists(f"{SHARED}/parking_trailheads.gpkg"):
    pk = gpd.read_file(f"{SHARED}/parking_trailheads.gpkg")
    pk = pk[pk.intersects(study_ll)]
    park_json = json.loads(gpd.GeoDataFrame(
        {"k": pk.kind, "n": pk["name"], "u": pk.url, "no": pk.note, "fee": pk.fee, "cap": pk.capacity,
         "p": pk.parking.fillna(False).astype(int), "src": pk.source,
         "st": pk["status"] if "status" in pk else None},
        geometry=pk.geometry, crs=4326).to_json(na="null", drop_id=True))
    print("parking / trailheads", len(pk), "|", pk.kind.value_counts().to_dict())
print("trails", len(t_feat), "ways |", t_feat.groupby("rk").size().to_dict(), "| labels per zoom band:",
      pd.Series([l["z"] for l in trail_labels], dtype=int).value_counts().sort_index().to_dict())
m.get_root().header.add_child(folium.Element(
    "<script>window.STREAMS=" + s_feat.to_json(na="null", drop_id=True) + ";\nwindow.FORKS=" + json.dumps(f_json)
    + ";\nwindow.DIVIDES=" + json.dumps(d_json) + ";\nwindow.DRAINS=" + json.dumps(drains)
    + ";\nwindow.PCT=" + json.dumps(pct_json) + ";\nwindow.PCT_LABEL_LINES=" + json.dumps(pct_labels)
    + ";\nwindow.TRAILS=" + t_feat.to_json(na="drop", drop_id=True) + ";\nwindow.TRAIL_LABEL_LINES="
    + json.dumps(trail_labels) + ";\nwindow.ROADS=" + json.dumps(roads_json) + ";\nwindow.PARKING="
    + json.dumps(park_json) + ";</script>"))
m.get_root().header.add_child(folium.Element(
    "<style>" + open(os.path.join(os.path.dirname(__file__), "map_style.css")).read() + "</style>\n<script>"
    + open(os.path.join(os.path.dirname(__file__), "map_drainages.js")).read() + "</script>"))

# every layer is also exported for the 3D map (stream_map_3d.html reads map3d_data.js)
X3D = {"streams": json.loads(s_feat.to_json(na="null", drop_id=True)), "forks": f_json, "divides": d_json,
       "drains": drains, "home": HOME, "pct": pct_json, "pct_labels": pct_labels}
gj = lambda g: json.loads(g.to_json(na="null", drop_id=True))

top = s_feat[s_feat.fs >= 55][["geometry"]]
folium.GeoJson(top.to_json(), name="<span style='color:#e8590c'>━</span> Best remote trout water (score ≥ 55)",
               show=False, style_function=lambda f: {"color": "#e8590c", "weight": 6, "opacity": 0.55,
                                                     "interactive": False}).add_to(m)   # clicks reach the stream

X3D["trails"] = json.loads(t_feat.to_json(na="drop", drop_id=True))
X3D["trail_labels"] = trail_labels
X3D["roads"], X3D["parking"] = roads_json, park_json
drops3d = []

# magenta / yellow / violet: validated all-pairs for color-blind separation and kept clear of the blue-green streams;
# drops at mapped waterfalls are neutral ink (same encoding as profiles.html)
color = {"unmapped waterfall-like step": "#e87ba4", "unmapped cascade": "#eda100",
         "unmapped short fall (big creek)": "#6250d6",
         "matches mapped waterfall": "#3b3a37", "steep reach": "#adb5bd",
         "likely DEM artifact": "#868e96", "dam / weir": "#495057"}
hidden = {"steep reach", "likely DEM artifact", "dam / weir"}
groups = {k: folium.FeatureGroup(name=f"<span style='color:{color[k]}'>●</span> Drops: {k}", show=False) for k in color}
for r in kp_ll.rename(columns={"pass": "pass_n"}).itertuples():   # "pass" is a keyword: itertuples would rename it
    gm = f"https://www.google.com/maps/@?api=1&map_action=map&center={r.lat},{r.lon}&zoom=18&basemap=satellite"
    html = (f"<b>{r.stream if isinstance(r.stream, str) and r.stream else 'unnamed drainage'}</b> · {r.region}<br>{r.status}<br>"
            f"{r.kind}<br>Drop <b>{r.drop_m:.0f} m</b> over {r.run_m:.0f} m (max slope {r.max_slope:.2f})<br>"
            f"Channel slope above {r.slope_above} / below {r.slope_below} · knick ×{r.knick_ratio}<br>"
            + (f"Excess drop over creek trend <b>{r.excess_drop_m} m</b> · DEM pool depth {r.pool_depth_m} m<br>"
               if r.pass_n == 2 else "") +
            f"Drainage {r.area_km2} km² · "
            + (f"summer: {r.water_class}" + (f" (about {cfs(r.dry_cfs)} cfs typical low flow)" if pd.notna(r.dry_cfs) else "")
               if isinstance(r.water_class, str) and r.water_class != "no data" else f"NHD {r.flow}")
            + f" · elev {r.elev_m:.0f} m<br>"
            f"<b>Access:</b> {approach(r)}<br>"
            + (f"Shade: {r.sun_hours:.1f} h direct sun mid-July ({r.shade_pct:.0f}% shaded)<br>" if pd.notna(r.sun_hours) else "")
            + (f"<span style='color:#a61e4d'>Burned: {r.burn_fire} fire {r.burn_year:.0f}</span><br>" if pd.notna(r.burn_year) else "")
            + (f"<span style='color:#2b8a3e'>{r.trout_water}</span><br>" if isinstance(r.trout_water, str) else "")
            + (f"<span style='color:#c92a2a'>⚠ Critical habitat: {r.crit_habitat} (check seasonal closures)</span><br>"
               if isinstance(r.crit_habitat, str) else "")
            + (f"{r.wilderness} (no bikes)<br>" if isinstance(r.wilderness, str) else "")
            + (f"<span style='color:#c92a2a'>⚠ {r.cpad_access}</span><br>" if isinstance(r.cpad_access, str) else "")
            + (f"<i>Bike legs use closed roads, fire roads, bike paths and bike-legal trails; some closure orders ban "
               f"all entry, check first.</i><br>"
               if pd.notna(r.bike_min) and r.bike_min >= 1 else "")
            + (f"<span style='color:#c92a2a'>⚠ Road closure {r.closure_m / 1000:.1f} km away: {r.closure_road}</span><br>"
               if isinstance(r._asdict().get("closure_road"), str) else "") +
            f"Top {r.lat}, {r.lon}<br>Pool/base {r.pool_lat}, {r.pool_lon}<br>"
            f"<a href='{gm}' target='_blank'>Satellite view</a>"
            + (f" · <a href='profiles.html#q={quote(r.stream)}&lat={r.lat}&lon={r.lon}' target='_blank'>Creek profile ↗</a>"
               if isinstance(r.stream, str) else ""))
    folium.CircleMarker([r.lat, r.lon], radius=3 + min(r.drop_m, 80) / 8, color=color[r.status], weight=1.5,
                        fill=True, fill_opacity=0.7, popup=folium.Popup(html, max_width=300),
                        tooltip=f"{r.drop_m:.0f} m drop").add_to(groups[r.status])
    drops3d.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                    "properties": {"s": r.status, "c": color[r.status], "h": round(float(r.drop_m), 1), "html": html,
                                   "pool": [r.pool_lon, r.pool_lat] if r.status in SHOW else None}})
    if r.status in SHOW:
        folium.CircleMarker([r.pool_lat, r.pool_lon], radius=3, color="#0b7285", fill=True, fill_opacity=1,
                            tooltip="plunge pool / base").add_to(groups[r.status])
for g in groups.values():
    g.add_to(m)
X3D["drops"] = {"type": "FeatureCollection", "features": drops3d}
X3D["drop_colors"] = color
# Diamond and triangle symbols as small SVG icons: folium's RegularPolygonMarker (leaflet-dvf) needs the SVG renderer
# and throws on this canvas map whenever the layer is shown and the map moves
FALL_SVG = ('<svg width="16" height="16" viewBox="0 0 16 16"><rect x="4" y="4" width="8" height="8" '
            'transform="rotate(45 8 8)" fill="#74c0fc" stroke="#0b3d91" stroke-width="2"/></svg>')
GAUGE_SVG = ('<svg width="18" height="16" viewBox="0 0 18 16"><path d="M9 1.5 L17 15 L1 15 Z" fill="{c}" stroke="#212529" '
             'stroke-width="1.2"/></svg>')
svg_icon = lambda html, w, h: folium.DivIcon(html=html, icon_size=(w, h), icon_anchor=(w // 2, h // 2), class_name="svgpin")
if "note" not in known_falls:
    known_falls["note"] = None
kf = folium.FeatureGroup(name="<span style='color:#0b3d91'>◆</span> Known waterfalls (OSM + NHD + CDFW surveys)", show=False)
for r in known_falls.itertuples():
    note = r.note if isinstance(r.note, str) and r.note else ""
    nm_ = r.name if isinstance(r.name, str) and r.name else "waterfall"
    folium.Marker([r.geometry.y, r.geometry.x], icon=svg_icon(FALL_SVG, 16, 16),
                  popup=folium.Popup(f"<b>{hesc(nm_)}</b> ({r.src})" + (f"<br>{hesc(note)}" if note else ""), max_width=300),
                  tooltip=f"{nm_} ({r.src})").add_to(kf)
kf.add_to(m)
X3D["falls"] = gj(known_falls[["name", "src", "note", "geometry"]].assign(name=known_falls.name.fillna("waterfall")))

if closures is not None and len(closures):
    fetched = closures.fetched.iloc[0]
    c_show = closures.assign(**{c: closures[c].fillna("") for c in ("road", "from", "to", "reason", "start", "end", "when")})
    folium.GeoJson(c_show[["source", "road", "from", "to", "severity", "reason", "when", "start", "end", "geometry"]].to_json(),
                   name=f"<span style='color:#c92a2a'>▬</span> Road closures (fetched {fetched})", show=False,
                   style_function=lambda f: {
                       "color": "#c92a2a" if f["properties"]["severity"].startswith("full") else "#f76707",
                       "weight": 7 if f["properties"]["severity"] == "full closure" else 5, "opacity": 0.85,
                       "dashArray": None if f["properties"]["severity"].startswith("full") else "8 6"},
                   tooltip=folium.GeoJsonTooltip(["road", "severity", "when", "from", "to", "reason", "start", "end", "source"],
                                                 aliases=["Road", "Closure", "Status", "From", "To", "Reason", "Start",
                                                          "End / reopen", "Source"])).add_to(m)
    X3D["closures"] = gj(c_show[["road", "from", "to", "severity", "reason", "when", "start", "end", "source", "geometry"]])
    X3D["closures_fetched"] = str(fetched)
if gated is not None and len(gated) and roads_json is None:   # older runs: the access-road layer replaces this
    folium.GeoJson(gated.assign(geometry=shapely.set_precision(gated.geometry.simplify(0.0001).values, 1e-5)).to_json(),
                   name="Gated / no public vehicles (OSM)", show=False,
                   style_function=lambda f: {"color": "#862e9c", "weight": 2.5, "dashArray": "1 5", "opacity": 0.9},
                   tooltip=folium.GeoJsonTooltip(["name", "highway", "access", "motor_vehicle"],
                                                 aliases=["Road", "Type", "Access", "Motor vehicle"])).add_to(m)

# ---- fire closure areas (LA County's Eaton Fire closures, via 02d_trails.py) ----
if os.path.exists(f"{SHARED}/closure_areas.gpkg"):
    ca_ = gpd.read_file(f"{SHARED}/closure_areas.gpkg")
    folium.GeoJson(ca_.to_json(), name="<span style='color:#c92a2a'>▧</span> Fire closure areas (Eaton Fire)", show=True,
                   style_function=lambda f: {"color": "#c92a2a", "weight": 2, "dashArray": "6 4", "fillColor": "#c92a2a",
                                             "fillOpacity": 0.1},
                   tooltip=folium.GeoJsonTooltip(["Agency", "Closure_Date"], aliases=["Closed by", "Since"])).add_to(m)
    X3D["closure_areas"] = gj(ca_)

# ---- context layers (11_context.py) ----
fires = ctx("fires")
if fires is not None:
    if "src" not in fires:
        fires["src"] = "CAL FIRE"
    fcm = matplotlib.colormaps["YlOrRd"]
    yr0, yr1 = fires.year.min(), fires.year.max()
    folium.GeoJson(fires.assign(geometry=fires.geometry.simplify(0.0003)).to_json(), name="Fire perimeters since 2016 (CAL FIRE; this year's: WFIGS, BAER)",
                   show=False, style_function=lambda f: {
                       "color": colors.to_hex(fcm(0.3 + 0.7 * (f["properties"]["year"] - yr0) / max(yr1 - yr0, 1))),
                       "weight": 1, "fillOpacity": 0.25},
                   tooltip=folium.GeoJsonTooltip(["fire", "year", "acres", "src"], aliases=["Fire", "Year", "Acres", "Perimeter"])).add_to(m)
    X3D["fires"] = gj(fires[["fire", "year", "acres", "src", "geometry"]].assign(
        geometry=fires.geometry.simplify(0.0003),
        c=[colors.to_hex(fcm(0.3 + 0.7 * (y - yr0) / max(yr1 - yr0, 1))) for y in fires.year]))
for name, label, style, fields in [
        ("wild_trout_waters", "CDFW Wild / Heritage Trout Waters",
         {"color": "#2b8a3e", "weight": 2, "fillOpacity": 0.15}, (["Name", "Designation", "Designation_Boundary"],
                                                                    ["Water", "Designation", "Boundary"])),
        ("critical_habitat", "Critical habitat, stream species (not closure boundaries)",
         {"color": "#c92a2a", "weight": 1.6, "fillOpacity": 0.22, "dashArray": "4 3"}, (["species", "unit"], ["Species", "Unit"])),
        ("wilderness", "Wilderness (no bikes)",
         {"color": "#5c940d", "weight": 1.5, "fillOpacity": 0.06}, (["wilderness"], ["Wilderness"])),
        ("non_fs_land", "Non-Forest-Service land inside the forests",
         {"color": "#e67700", "weight": 1, "fillOpacity": 0.2}, (["ownerclassification"], ["Owner"])),
        ("cpad_restricted", "Restricted or no public access (CPAD)",
         {"color": "#d9480f", "weight": 1, "fillOpacity": 0.25, "dashArray": "2 3"},
         (["ACCESS_TYP", "UNIT_NAME", "MNG_AGNCY"], ["Access", "Unit", "Manager"]))]:
    g = ctx(name)
    if g is not None and len(g):
        g = g.assign(geometry=g.geometry.simplify(0.0002))
        folium.GeoJson(g[fields[0] + ["geometry"]].to_json(), name=label, show=False,
                       style_function=lambda f, st=style: st,
                       tooltip=folium.GeoJsonTooltip(fields[0], aliases=fields[1])).add_to(m)
        X3D[name] = gj(g.assign(tip=[" · ".join(str(v) for v in row if isinstance(v, str) and v)
                                     for row in g[fields[0]].itertuples(index=False)])[["tip", "geometry"]])
gauges = ctx("gauges")
if gauges is not None and len(gauges):
    gcol = {"much below normal": "#c92a2a", "below normal": "#f76707", "normal": "#2b8a3e", "above normal": "#1c7ed6",
            "much above normal": "#1864ab", "dry": "#c92a2a", "dry (normal for date)": "#adb5bd",
            "flowing (usually dry on this date)": "#1c7ed6", "no history": "#868e96"}
    g3 = []
    gg = folium.FeatureGroup(name=f"<span style='color:#1c7ed6'>▲</span> Stream gauges, USGS + CDEC (live, {gauges.time.max()[:10]})",
                             show=False)
    for r in gauges.itertuples():
        html = (f"<b>{r.name}</b><br>{r.cfs:g} cfs at {r.time}<br>{r.status}"
                + (f" · {r.pct_of_median:.0f}% of median for today" if pd.notna(r.pct_of_median) else "")
                + (f"<br>Median for this date {r.p50:g} cfs" if pd.notna(r.p50) else "")
                + f"<br><a href='{r.url}' target='_blank'>{'CDEC' if str(r.site).startswith('CDEC') else 'USGS'} station page</a>")
        folium.Marker([r.geometry.y, r.geometry.x], icon=svg_icon(GAUGE_SVG.format(c=gcol.get(r.status, "#868e96")), 18, 16),
                      popup=folium.Popup(html, max_width=280), tooltip=f"{r.name}: {r.cfs:g} cfs ({r.status})").add_to(gg)
        g3.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.geometry.x, r.geometry.y]},
                   "properties": {"c": gcol.get(r.status, "#868e96"), "html": html,
                                  "tip": f"{r.name}: {r.cfs:g} cfs ({r.status})"}})
    X3D["gauges"] = {"type": "FeatureCollection", "features": g3}
    gg.add_to(m)

# trout evidence and springs (11_context.py)
tev = ctx("trout_evidence")
if tev is not None and len(tev):
    TCOL = {"CDFW survey": "#2b8a3e", "CDFW stocking": "#1c7ed6", "iNaturalist": "#82c91e"}
    tgrp, t3 = folium.FeatureGroup(name="<span style='color:#2b8a3e'>●</span> Trout evidence: CDFW surveys (red = none "
                                        "found), stocking, iNaturalist", show=False), []
    for r in tev.sort_values("kind", ascending=False).itertuples():
        col = TCOL.get(r.kind, "#2b8a3e") if r.trout else "#e03131"
        head = r.water if isinstance(r.water, str) and r.water else r.kind
        lab = r.label + (" (at a lake: likely stocked)" if r.lake and r.kind == "iNaturalist" else "")
        html_ = (f"<b>{hesc(head)}</b><br>{hesc(lab)}"
                 + (f"<br><a href='{hesc(r.url)}' target='_blank'>iNaturalist record ↗</a>" if isinstance(r.url, str) and r.url else ""))
        folium.CircleMarker([r.geometry.y, r.geometry.x], radius=4.5 if r.kind == "iNaturalist" else 7, color="#ffffff",
                            weight=1.2, fill=True, fill_color=col, fill_opacity=0.95, popup=folium.Popup(html_, max_width=300),
                            tooltip=f"{head}: {lab}").add_to(tgrp)
        t3.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(r.geometry.x, 5), round(r.geometry.y, 5)]},
                   "properties": {"c": col, "r": 4.5 if r.kind == "iNaturalist" else 7, "html": html_, "tip": f"{head}: {lab}"}})
    tgrp.add_to(m)
    X3D["trout"] = {"type": "FeatureCollection", "features": t3}
spr = ctx("springs")
if spr is not None and len(spr):
    sgrp = folium.FeatureGroup(name="<span style='color:#1098ad'>●</span> Springs and seeps (NHD)", show=False)
    tips = [f"{n} (spring, NHD)" if isinstance(n, str) and n else "Spring or seep (NHD)" for n in spr.gnis_name]
    for g_, t_ in zip(spr.geometry, tips):
        folium.CircleMarker([g_.y, g_.x], radius=3.5, color="#0b7285", weight=1, fill=True, fill_color="#66d9e8",
                            fill_opacity=1, tooltip=t_).add_to(sgrp)
    sgrp.add_to(m)
    X3D["springs"] = gj(spr.assign(tip=tips, geometry=shapely.set_precision(spr.geometry.values, 1e-5))[["tip", "geometry"]])

# trailheads used by good water or shown drops, with drive time from HOME
used = pd.concat([s_ll.loc[s_ll.fish_score >= 50, ["th_id", "th_road", "th_lat", "th_lon", "drive_min", "drive_km"]],
                  kp_ll.loc[kp_ll.status.isin(SHOW), ["th_id", "th_road", "th_lat", "th_lon", "drive_min", "drive_km"]]])
used = used.dropna(subset=["th_lat"]).drop_duplicates("th_id")
tg = folium.FeatureGroup(name=f"<span style='color:#e0a800'>●</span> Approach start points (computed; drive from {HOME['label']})",
                         show=False)
for r in used.itertuples():
    folium.CircleMarker([r.th_lat, r.th_lon], radius=4, color="#212529", weight=1, fill=True, fill_color="#ffd43b",
                        fill_opacity=1, tooltip=f"P · {r.th_road if isinstance(r.th_road, str) else 'road end'} · "
                        + (f"{r.drive_min:.0f} min / {r.drive_km:.0f} km drive" if pd.notna(r.drive_min) else "no drive route")
                        ).add_to(tg)
tg.add_to(m)
X3D["trailheads"] = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.th_lon, r.th_lat]},
     "properties": {"tip": f"P · {r.th_road if isinstance(r.th_road, str) else 'road end'} · "
                           + (f"{r.drive_min:.0f} min / {r.drive_km:.0f} km drive" if pd.notna(r.drive_min) else "no drive route")}}
    for r in used.itertuples()]}
folium.Marker([HOME["lat"], HOME["lon"]], tooltip=f"Start: {HOME['label']}",
              icon=folium.Icon(color="darkblue", icon="home")).add_to(m)

# Legend, drainage list, colour-mode switch, labels and #lat,lon,zoom links (from the profile viewer) are built by
# initDrainageMap in map_drainages.js, which runs once the map and layer control exist.
lc = folium.LayerControl(collapsed=True, position="topright")
lc.add_to(m)
MeasureControl(primary_length_unit="meters", position="bottomright").add_to(m)
Fullscreen(position="topleft").add_to(m)

class InitDrainages(MacroElement):
    _template = Template("""{% macro script(this, kwargs) %}
initDrainageMap({{ this._parent.get_name() }}, {{ this.ctrl }});
{% endmacro %}""")
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
m.add_child(InitDrainages(lc.get_name()))
m.save(f"{MAP_OUT}/stream_map.html")
# 3D map: static page + data file (a <script>, so it also works opened straight from disk)
with open(f"{MAP_OUT}/map3d_data.js", "w") as f:
    f.write("window.MAP3D=" + json.dumps(X3D, separators=(",", ":"), default=str) + ";\n")
import shutil
shutil.copy(os.path.join(os.path.dirname(__file__), "map3d.html"), f"{MAP_OUT}/stream_map_3d.html")

print("streams", len(s_ll), "| drops", len(kp_ll))
print(kp_ll.groupby(["region", "status"]).size().unstack(fill_value=0).to_string())
