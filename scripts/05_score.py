"""Attribute DEM streams + drop candidates (perennial, remoteness, trout-elevation) for one region,
score them, and write layers for the combined map (06_map.py). Run with REGION=<name>."""
import json, os, re, time, shapely, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import matplotlib
from matplotlib import cm, colors
from PIL import Image
from rasterio import features
from config import *
import areaclip

MAP_MIN_KM2 = 1.0  # only draw channels draining >= 1 km^2

dem_src = rasterio.open(f"{RAW}/dem_10m.tif")
dem = dem_src.read(1)
area = rasterio.open(f"{DERIVED}/area_km2.tif").read(1)
strahler = rasterio.open(f"{DERIVED}/strahler.tif").read(1)
inv = ~dem_src.transform
def sample(arr, geoms):
    cols, rows = inv * (np.array([g.x for g in geoms]), np.array([g.y for g in geoms]))
    return arr[np.clip(rows.astype(int), 0, arr.shape[0] - 1), np.clip(cols.astype(int), 0, arr.shape[1] - 1)]

streams = gpd.read_file(f"{DERIVED}/dem_streams.gpkg")
nhd = gpd.read_file(f"{RAW}/nhd_flowlines.gpkg")
nhd_pts = gpd.read_file(f"{RAW}/nhd_points.gpkg")
roads = gpd.read_file(f"{RAW}/osm_roads.gpkg")
trails = gpd.read_file(f"{RAW}/osm_trails.gpkg")
kp = pd.concat([gpd.read_file(f"{DERIVED}/knickpoints.gpkg").assign(**{"pass": 1}),
                gpd.read_file(f"{DERIVED}/knickpoints_bigcreek.gpkg")], ignore_index=True)
kp = gpd.GeoDataFrame(kp, crs=CRS)
kp = kp[areaclip.inside(kp.geometry.values)]    # an area that stops at a state line: drops past it go (areaclip.py)

# Public roads a car can use (exclude gated/private service roads & fire roads marked no motor vehicles)
drivable = roads[~roads.access.isin(["private", "no"]) & ~roads.motor_vehicle.isin(["no", "private"])
                 & (roads.highway != "track")]
road_u = drivable.geometry.union_all()
trail_u = pd.concat([trails.geometry, roads[roads.highway == "track"].geometry]).union_all()

# NHD: perennial (46006) / intermittent (46003) / ephemeral (46007); keep stream/river & artificial paths
# Artificial paths (55800, the centrelines of mapped rivers and lakes) take the area's class (config.py)
nhd["flow"] = nhd.fcode.map({46006: "perennial", 46003: "intermittent", 46007: "ephemeral",
                             55800: ARTIFICIAL_PATH}).fillna("other")
# Known waterfalls: the area's list from every source, merged (02f_known_falls.py: OpenStreetMap, NHD, USGS GNIS,
# Wikidata, CDFW's barrier surveys in LA, and falls from guidebooks and state inventories in data/known_falls_curated.csv).
# This range takes those within 500 m of its box, so a drop near an edge still finds its fall, and writes out only those
# inside it, so each fall is drawn once (the lon/lat box each range used to take overlapped its neighbours').
kf_path = f"{SHARED}/known_falls.gpkg"
if not os.path.exists(kf_path):
    raise SystemExit(f"{kf_path} is missing: run AREA={AREA} 02f_known_falls.py first (run_mid.sh does)")
range_box = shapely.box(XMIN, YMIN, XMAX, YMAX)
known_falls = gpd.read_file(kf_path).to_crs(CRS)
known_falls = known_falls[known_falls.intersects(range_box.buffer(500))].reset_index(drop=True)
known_falls["precise"] = known_falls.precise.astype(bool)
print(f"known falls: {len(known_falls)} ({int(known_falls.precise.sum())} precisely placed);",
      "sources:", known_falls.src.str.split(" · ").explode().value_counts().to_dict())
dams = pd.concat([nhd_pts[nhd_pts.ftype == 343].geometry, gpd.read_file(f"{RAW}/osm_dams.gpkg").geometry])

# ---- stream links ----
# Measured on each link's own cells. A pysheds link's last vertex is the cell where it joins the next stream, so the
# drainage area there includes the other arm: every side creek used to report the trunk's area, and gullies draining
# well under 1 km2 passed the cut. Area, gradient and the downstream end now use the second-to-last vertex; order and
# elevation use the middle vertex (vertices sit on cell corners, so they always sample the channel cell itself).
# Name and NHD flow class come from the NHD lines nearest the link at its 25 %, 50 % and 75 % vertices, each kept when
# two of the three agree (on the name, or the class: NHD splits a creek into many short segments), so a short side
# creek doesn't take the name and flow of the river it runs beside. NHD has no name on many lines (e.g. San Antonio
# Creek below Mt. Baldy); those links take the name of OpenStreetMap's named rivers and streams the same way.
# Links mostly on sea-level cells are dropped (the DEM stores the sea as 0 m, and its flats trace fake channels), and
# in an area that stops at a state line (config clip_state), links whose middle lies past it (areaclip.py).
s = streams[streams.length > 0].copy()
def vert(g, f):
    c = g.coords
    return shapely.Point(c[min(len(c) - 1, max(0, int(round(f * (len(c) - 1)))))])
own_end = gpd.GeoSeries([shapely.Point(g.coords[-2] if len(g.coords) >= 2 else g.coords[0]) for g in s.geometry],
                        index=s.index, crs=CRS)
starts = gpd.GeoSeries([shapely.Point(g.coords[0]) for g in s.geometry], index=s.index, crs=CRS)
mid = gpd.GeoSeries([vert(g, 0.5) for g in s.geometry], index=s.index, crs=CRS)
s["area_km2"] = sample(area, own_end).round(2)
sea = np.array([np.mean(sample(dem, shapely.points(np.asarray(g.coords))) <= 0.5) for g in s.geometry])
s = s[(s.area_km2 >= MAP_MIN_KM2) & (sea < 0.5) & areaclip.inside(s.geometry.values)].copy()
mid, own_end, starts = mid[s.index], own_end[s.index], starts[s.index]
s["order"] = sample(strahler, mid)
s["elev_m"] = sample(dem, mid).round(0)
s["len_m"] = s.length.round(0)
s["gradient_pct"] = ((sample(dem, starts) - sample(dem, own_end)) / s.length * 100).clip(lower=0).round(1)
s["road_m"] = mid.distance(road_u).round(0)
s["trail_m"] = mid.distance(trail_u).round(0)
pts3 = [gpd.GeoDataFrame(geometry=[vert(g, f) for g in s.geometry], index=s.index, crs=CRS) for f in (0.25, 0.5, 0.75)]
def vote(lines, col, max_d=60):
    """`col` of the line nearest each of the link's 25 / 50 / 75 % vertices (within max_d m), kept when two agree."""
    v = pd.concat([gpd.sjoin_nearest(p, lines[[col, "geometry"]], max_distance=max_d, how="left").groupby(level=0)[col]
                   .first().reindex(s.index) for p in pts3], axis=1, ignore_index=True)
    out = v[0].where(v[0].notna() & ((v[0] == v[1]) | (v[0] == v[2])))
    return out.fillna(v[1].where(v[1].notna() & (v[1] == v[2])))
nhd_k = nhd[["gnis_name", "flow", "geometry"]].reset_index(drop=True)
s["name"] = vote(nhd_k, "gnis_name")
s["flow"] = vote(nhd_k, "flow").fillna("unmapped")
osm_wp = f"{RAW}/osm_waterways.gpkg"    # OSM named rivers and streams, cached a week
if not os.path.exists(osm_wp) or time.time() - os.path.getmtime(osm_wp) > 7 * 86400:
    from geomatch import overpass
    w0, s0, e0, n0 = gpd.GeoSeries([shapely.box(*REGIONS[REGION]["bbox"])], crs=CRS).to_crs(4326).total_bounds
    els = [e for e in overpass(f'[out:json][timeout:600];way["waterway"~"^(river|stream)$"]["name"]'
                               f'({s0:.5f},{w0:.5f},{n0:.5f},{e0:.5f});out geom;') if len(e.get("geometry") or []) >= 2]
    if els:
        gpd.GeoDataFrame({"name": [e["tags"]["name"] for e in els]}, crs=4326,
                         geometry=[shapely.LineString([(q["lon"], q["lat"]) for q in e["geometry"]]) for e in els]
                         ).to_crs(CRS).to_file(osm_wp + ".tmp.gpkg", driver="GPKG")
        os.replace(osm_wp + ".tmp.gpkg", osm_wp)
if os.path.exists(osm_wp):
    nhd_named = s["name"].notna().sum()
    s["name"] = s["name"].fillna(vote(gpd.read_file(osm_wp).to_crs(CRS), "name"))
    print(f"names: NHD {nhd_named}, OpenStreetMap {s['name'].notna().sum() - nhd_named} more, of {len(s)} links")

# A reach between two reaches of one river (its largest upstream reach and the reach below, passing over unnamed reaches)
# is that river, if the vote gave it no name or the name of a much smaller stream: every other reach of that name within
# 3 km drains under half as much. Where a creek comes in, NHD draws the creek's line out to the river's centreline, and
# on a short reach two of the vote's three points can lie nearest it: the Snake River between Little Red Creek's and
# Station Creek's mouths took their names (3,321 and 3,242 km2), Castaic Creek's the Santa Clara River below it, and
# creek profiles read the river's drainage at the mouth. Streams of about the same size keep the vote (forks, lakes where
# two rivers meet, spelling variants). Decided once, from the vote's names, so no reach is renamed back and forth.
geoms = s.geometry.values
end_key = lambda c: (round(c[0], 1), round(c[1], 1))
ends = {}
for i, g in enumerate(geoms):
    ends.setdefault(end_key(g.coords[-1]), []).append(i)
km2 = s["area_km2"].to_numpy(float)
voted = s["name"].to_numpy(object)
main_up, down = np.full(len(s), -1), np.full(len(s), -1)
for i, g in enumerate(geoms):
    donors = ends.get(end_key(g.coords[0]), [])
    if donors:
        main_up[i] = max(donors, key=lambda j: km2[j])
    down[donors] = i
def named_along(i, ptr, steps=20):
    """The vote's name of the first named reach from reach i along ptr (upstream main stem, or downstream)."""
    for _ in range(steps):
        i = ptr[i]
        if i < 0:
            return None
        if isinstance(voted[i], str):
            return voted[i]
    return None
reach_tree, renamed = shapely.STRtree(geoms), {}
for i in range(len(s)):
    y = named_along(i, main_up) if main_up[i] >= 0 and down[i] >= 0 else None
    if y is None or y == voted[i] or y != named_along(i, down):
        continue
    if isinstance(voted[i], str):
        same = [j for j in reach_tree.query(geoms[i].buffer(3000)) if j != i and voted[j] == voted[i]]
        if same and km2[same].max() >= 0.5 * km2[i]:
            continue
    renamed[i] = y
s["name"] = [renamed.get(i, n) for i, n in enumerate(voted)]
print(f"names along rivers: {len(renamed)} reaches take the river's name "
      f"({sum(isinstance(voted[i], str) for i in renamed)} had another stream's, the rest none)")

# Fishability score 0-100 (heuristic, tuned for SoCal trout water)
def band(x, lo, hi, soft):  # 1 inside [lo,hi], linear falloff over `soft`
    return np.clip(1 - np.clip(np.maximum(lo - x, x - hi), 0, None) / soft, 0, 1)
water = s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05, "other": 0.3})
size = np.clip(np.log10(s.area_km2) / np.log10(50), 0, 1)        # 1 km2 -> 0, 50+ km2 -> 1
cold = band(s.elev_m, *ELEV_BAND) if ELEV_BAND else 1.0           # trout-friendly elevation (LA; first pass only)
grad = band(s.gradient_pct, 1, 8, 10)                             # pool-riffle to step-pool
remote = np.clip(s.road_m / 2000, 0, 1)                           # 2 km+ from a public road
s["fish_score"] = (100 * water * (0.35 * size + 0.25 * cold + 0.15 * grad + 0.25 * remote)).round(0)

# ---- drop candidates ----
# A drop takes the name of the reach its top cell is on. The nearest NHD line can be the river's where a creek comes in
# (drops on Little Cottonwood and Blue Bell creeks were "Snake River", Pigpen Falls "Lick Log Creek"); on an unnamed
# reach, or a channel too small to be one, the nearest NHD line's within 80 m, as before. The junction cell at a reach's
# end belongs to the reach below (vertices sit on cell corners: rounded, as in 12_profiles.py).
reach_at = {}
for i, g in enumerate(geoms):
    v = np.asarray(g.coords)[:-1]
    vc, vr = inv * (v[:, 0], v[:, 1])
    for k in np.rint(vr).astype(int) * dem.shape[1] + np.rint(vc).astype(int):
        reach_at[int(k)] = i
reach_name = s["name"].to_numpy(object)
on_reach = [reach_name[reach_at[t]] if t in reach_at else None for t in kp.top_idx.astype(int)]
nearest_line = gpd.sjoin_nearest(kp[["geometry"]], nhd[["gnis_name", "geometry"]], max_distance=80,
                                 how="left").groupby(level=0).first().gnis_name
kp["stream"] = [o if isinstance(o, str) else n for o, n in zip(on_reach, nearest_line.reindex(kp.index))]
kp["flow"] = gpd.sjoin_nearest(kp[["geometry"]], nhd[["flow", "geometry"]], max_distance=80,
                               how="left").groupby(level=0).first().flow.fillna("unmapped")
kp["road_m"] = kp.distance(road_u).round(0)
kp["trail_m"] = kp.distance(trail_u).round(0)
kp["known_fall_m"] = kp.distance(known_falls.geometry.union_all()).round(0) if len(known_falls) else np.nan
kp["dam_m"] = kp.distance(dams.union_all()).round(0) if len(dams) else np.inf
# A road fakes a drop where it crosses the channel: an embankment over a culvert, or a bridge deck the DEM kept, makes
# the lip, so the step's top sits on it. One that only runs beside the creek does not, and gorges are often walled by
# one: with a drivable road within 40 m of the top as the test, Texas Falls, Huntington Gorge and Sterling Falls Gorge
# (VT) and Amicalola Falls (GA) were all set aside as artifacts (155 drops in all). So the test is a drivable road
# crossing the DEM channel within 40 m of the top. Not along the whole step: a road bridge below a fall doesn't make
# it (testing to the pool flagged 19 more, among them a 101 m fall in the Santa Ana Mountains over a highway bridge).
step = shapely.linestrings(np.stack([np.c_[kp.geometry.x, kp.geometry.y], np.c_[kp.pool_x, kp.pool_y]], axis=1))
zone = shapely.buffer(kp.geometry.values, 40)
chan_g, road_g = streams.geometry.values, drivable.geometry.values
chan_t, road_t = shapely.STRtree(chan_g), shapely.STRtree(road_g)
def crosses(z):
    rd = road_g[road_t.query(z)]
    if not len(rd):
        return False
    ch = shapely.intersection(shapely.union_all(chan_g[chan_t.query(z)]), z)
    return not ch.is_empty and bool(shapely.intersects(rd, ch).any())
kp["road_crossing"] = [crosses(z) for z in zone]
# A mapped waterfall on the step itself (within 50 m of its top-to-pool line: room for a hand-placed point and the DEM
# channel's offset) is that drop, whatever a road or fill suggests; 14 such were labelled artifacts. The nearest
# artifact beyond that was 88 m off. Up to 200 m from the top a mapped fall still names a drop, but no longer outranks
# the artifact tests.
# Only precisely placed falls count here (02f_known_falls.py's `precise`: OSM, NHD, CDFW and guidebook
# GPS points on the fall); USGS GNIS placements and points placed from directions can be 100 m or more off.
on_fall = known_falls[known_falls.precise]
kp["fall_on_step"] = (shapely.distance(step, on_fall.geometry.union_all()) <= 50) if len(on_fall) else False
kp["status"] = np.select(
    [kp.dam_m < 250, kp.fall_on_step, kp.road_crossing | kp.artifact_risk, kp.known_fall_m < 200,
     kp.kind == "waterfall-like step", kp.kind == "cascade / knickpoint",
     kp.kind == "short fall / pool (big creek)"],
    ["dam / weir", "matches mapped waterfall", "likely DEM artifact", "matches mapped waterfall",
     "unmapped waterfall-like step", "unmapped cascade", "unmapped short fall (big creek)"], "steep reach")
# the big-creek pass is meant for fishable water: keep it to NHD perennial channels
kp = kp[(kp["pass"] == 1) | (kp.flow == "perennial")]
kp = kp.sort_values("drop_m", ascending=False)

ll = lambda g: g.to_crs(4326)
os_ = OUT
s_ll, kp_ll = ll(s), ll(kp)
pool = gpd.GeoSeries(gpd.points_from_xy(kp.pool_x, kp.pool_y), crs=CRS).to_crs(4326)
kp_ll["pool_lat"], kp_ll["pool_lon"] = pool.y.values.round(6), pool.x.values.round(6)
kp_ll["lat"], kp_ll["lon"] = kp_ll.geometry.y.round(6), kp_ll.geometry.x.round(6)

cols = ["status", "kind", "pass", "stream", "flow", "drop_m", "excess_drop_m", "pool_depth_m", "run_m", "step_slope", "max_slope", "slope_above",
        "slope_below", "knick_ratio", "area_km2", "elev_m",
        "road_m", "trail_m", "known_fall_m", "lat", "lon", "pool_lat", "pool_lon"]
kp_ll.insert(0, "region", LABEL)
s_ll.insert(0, "region", LABEL)
# stable keys so later scripts (08-11) can attach attributes
s_ll.insert(0, "sid", [f"{REGION}:s{i}" for i in range(len(s_ll))])
kp_ll.insert(0, "did", [f"{REGION}:d{i}" for i in range(len(kp_ll))])
cols = ["did", "region"] + cols
kp_ll[cols].to_csv(f"{os_}/waterfall_candidates.csv", index=False)
s_out = s_ll.assign(lat=s_ll.geometry.interpolate(0.5, normalized=True).y.round(6),
                    lon=s_ll.geometry.interpolate(0.5, normalized=True).x.round(6))
s_out.sort_values("fish_score", ascending=False)[
    ["sid", "region", "name", "flow", "fish_score", "area_km2", "order", "elev_m", "gradient_pct", "len_m", "road_m", "trail_m", "lat", "lon"]
].to_csv(f"{os_}/stream_reaches_ranked.csv", index=False)
s_ll.to_file(f"{os_}/streams_scored.gpkg")
kp_ll.drop(columns=["top_idx", "base_idx"]).to_file(f"{os_}/waterfall_candidates.gpkg")

# light copies of trails + mapped falls for the combined map
t_ll = areaclip.cut(trails).to_crs(4326)
t_ll = t_ll[~t_ll.is_empty].assign(geometry=shapely.set_precision(t_ll.geometry.simplify(0.0001).values, 1e-5))
t_ll.assign(name=t_ll["name"].fillna("trail"))[["name", "geometry"]].to_file(f"{os_}/trails.gpkg")
known_falls[known_falls.within(range_box) & areaclip.inside(known_falls.geometry.values)].to_crs(4326).to_file(
    f"{os_}/known_falls.gpkg")

# ---- hillshade overlay (warped to web mercator) ----
def hillshade(z, az=315, alt=45):
    dy, dx = np.gradient(z, RES)
    slope = np.arctan(np.hypot(dx, dy)); aspect = np.arctan2(-dx, dy)
    a, b = np.radians(360 - az + 90), np.radians(alt)
    return np.clip(np.sin(b) * np.cos(slope) + np.cos(b) * np.sin(slope) * np.cos(a - aspect), 0, 1)
hs = hillshade(dem.astype("float64"))
dst_t, w, h = calculate_default_transform(CRS, "EPSG:3857", dem.shape[1], dem.shape[0], *dem_src.bounds,
                                          resolution=30)
hs_m = np.zeros((h, w), "float32"); dem_m = np.zeros((h, w), "float32")
reproject(hs.astype("float32"), hs_m, src_transform=dem_src.transform, src_crs=CRS, dst_transform=dst_t,
          dst_crs="EPSG:3857", resampling=Resampling.bilinear, dst_nodata=0)
reproject(dem, dem_m, src_transform=dem_src.transform, src_crs=CRS, dst_transform=dst_t,
          dst_crs="EPSG:3857", resampling=Resampling.bilinear, dst_nodata=0)
tint = matplotlib.colormaps["terrain"](colors.Normalize(200, 3100)(dem_m))[..., :3]
rgb = (tint * (0.35 + 0.65 * hs_m[..., None])) * 255
alpha = np.where(dem_m > 0, 255, 0)
if areaclip.outline() is not None:      # an area that stops at a state line: no terrain shading past it
    alpha[features.geometry_mask([areaclip.outline("EPSG:3857")], (h, w), dst_t)] = 0
Image.fromarray(np.dstack([rgb, alpha]).astype("uint8")).quantize(192, method=Image.Quantize.FASTOCTREE).save(
    f"{os_}/hillshade.png", optimize=True)
from pyproj import Transformer
tb = Transformer.from_crs(3857, 4326, always_xy=True)
west, north = tb.transform(dst_t.c, dst_t.f)
east, south = tb.transform(dst_t.c + w * dst_t.a, dst_t.f + h * dst_t.e)
json.dump(dict(south=south, west=west, north=north, east=east), open(f"{os_}/hillshade_bounds.json", "w"))

print(LABEL, "| streams", len(s), "| perennial", int((s.flow == "perennial").sum()))
print(kp.status.value_counts().to_string())
print("\nTop reaches:\n", s_out.sort_values("fish_score", ascending=False)
      .drop_duplicates("name").head(12)[["name", "flow", "fish_score", "area_km2", "elev_m", "gradient_pct", "road_m"]].to_string())
print("\nTop unmapped steps:\n", kp[kp.status == "unmapped waterfall-like step"].head(10)[
    ["stream", "flow", "drop_m", "run_m", "area_km2", "elev_m", "road_m", "trail_m"]].to_string())
