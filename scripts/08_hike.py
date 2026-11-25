"""Approach time (bike + hike) to every stream reach and drop from the nearest open drivable road
(cost-distance on the DEM).

Walking speed is Tobler's hiking function on the local slope, averaged uphill/downhill:
  - trails, tracks, gated and closed roads, the trail layer's steps and bike paths, and the Forest Service roads OSM
    lacks (02e_access.py): grade capped at 15% (trails switchback), full Tobler speed
  - faint trails: the agencies' trails OSM lacks (02d_trails.py's "official only", drawn dotted), off any OSM way:
    FAINT_FACTOR of that speed (the user, 2026-11-25: "Walk them slower", since OSM's lack of a trail often means it is
    overgrown), between a trail and open ground below; never slower than the ground under them
  - creek bottoms (1 km^2 of drainage up to CHANNEL_MAX_KM2, 25 sq mi) off trail: 45% of Tobler (boulder-hopping,
    wading); a bigger river is walked along its bank, at the off-trail speed below
  - other off-trail terrain: 30% of Tobler (SoCal chaparral), slopes over 45 degrees nearly impassable
Bikeable (ridden wherever it beats walking):
  - roads closed to cars and every fire road: closures in force in mid-July, roads cut off by them, OSM roads tagged
    access=no / motor_vehicle=no, OSM tracks, access roads of class "bike" (02e_access.py: closed to cars, open to
    bikes) and all fire roads of the trail layer (02d_trails.py). Fire roads count even where bikes may not be
    allowed (wilderness, posted no bikes, fire closures, closed or private in OSM): the bike time stays in and the
    reach / drop gets a bike_check flag (below). Other private roads (ranch roads neither layer lists) stay out.
  - the Forest Service roads OSM lacks (02e_access.py, source "USFS records only"; the user, 2026-11-25: "Draw and ride
    them"), open or closed to cars, as dirt roads: flagged like a doubtful fire road (they may be overgrown or gated)
  - bike paths: every OSM highway=cycleway in the region, downloaded here (the trail layer, 02d_trails.py, draws them,
    and the road layer those OSM names as roads, like Old Pass Road); walked too; never ridden in wilderness
  - singletrack only where it is clearly bike-legal (trail layer bike = "yes"); never in wilderness
Cycling speed 18 km/h on the flat, slowed by grade (~10 km/h at 6%); x0.7 on dirt roads, x0.5 on singletrack. The grade
is the line's own (DEM elevation along the road or trail over 200 m, capped at 25%), not the cell's slope: a road
benched into a canyon wall climbs far less than the hillside under it (West Fork Road: 1.4% vs 30%).
bike_check names why bike access is doubtful when the fastest route rides at least CHECK_MIN minutes on such a fire
road, and bike_check_min is how long it rides on them. Reaches also get approach_med_min, the median time along the
reach, and bike_med_min, the minutes of it ridden (the fish score counts ridden minutes double, scoring.py).
Sources are cells on open public drivable roads a car can reach, minus the full closures still in force in mid-July,
the season the map scores (07_road_closures.py: a winter gate or a night's road work doesn't cut its road; 09_drive.py
names today's closures on the access line instead).
Each reach also gets the trailhead (the road cell its fastest route starts from). Run with REGION=<name>.
Last, the routes themselves, for the map pages to draw on a click: each reach's, drop's and lake's fastest route from
its trailhead to its approach point, one network of segments the routes share (approach_routes.py: hike_routes.gpkg,
hike_route_starts.csv). They are read from the traceback after everything above is written, which they don't change.
"""
import numpy as np, pandas as pd, geopandas as gpd, rasterio, os, json, time, shapely
from rasterio import features
from skimage.graph import MCP_Geometric
from scipy.ndimage import map_coordinates
from shapely.geometry import Point, MultiPoint, box
from config import *
from geomatch import overpass, wilderness_path
import roadclosures

TRAIL_MAX_GRADE = 0.15
FAINT_FACTOR = 0.6          # a faint trail (an agency's trail OSM lacks): this share of a trail's speed (open ground: 0.30)
CHANNEL_FACTOR, OFFTRAIL_FACTOR = 0.45, 0.30
# A creek bottom is walked up to this drainage; a bigger river along its bank, off trail. Since #7 a lake's outlet river
# carries the water of the lake above it, and its channel counted as a creek bottom however big: the Raquette below
# Long Lake, 171 km2, made 16,000 cells around Round Lake Outlet 3+ minutes nearer on foot (adk_northwest,
# 2026-11-24). The user: "Stop above a size", then "25 sq mi" (2026-11-24, from 10 and 25 sq mi measured on the 12
# maps: 25 slows 427 reaches' approach by 10+ min where 10 slows 998; 10 also took creeks like Raven Fork off the
# creek bottoms).
CHANNEL_MAX_KM2 = 64.7      # km2: 25 sq mi
CLIFF_SLOPE, CLIFF_KMH = 1.0, 0.05
BIKE_FLAT_KMH, BIKE_GRADE_K, DIRT_FACTOR, SINGLETRACK_FACTOR = 18.0, 12.0, 0.7, 0.5
BIKE_MAX_GRADE, GRADE_WINDOW_M = 0.25, 200.0
CHECK_MIN = 1.0       # minutes on a doubtful fire road before a route is flagged (a crossing takes a few seconds)
PAVED = {"paved", "asphalt", "concrete", "concrete:plates", "chipseal", "paving_stones", "sett", "metal", "wood"}
NO_BIKES = {"Pacific Crest Trail: no bikes", "posted no bikes", "agency: no bikes",
            "Forest Service: closed to bikes by order", "State Parks: no bikes", "NPS: hikers / horses only"}

src = rasterio.open(f"{RAW}/dem_10m.tif")
dem = src.read(1).astype("float64")
nodata = dem < -1000
area = rasterio.open(f"{DERIVED}/area_km2.tif").read(1)
H, W = dem.shape
shape, T = dem.shape, src.transform

def tobler(s):
    """km/h, symmetric (mean of walking up and down slope s)."""
    return 0.5 * (6 * np.exp(-3.5 * np.abs(s + 0.05)) + 6 * np.exp(-3.5 * np.abs(-s + 0.05)))

gy, gx = np.gradient(np.where(nodata, np.nanmean(dem[~nodata]), dem), RES)
slope = np.hypot(gx, gy)
del gy, gx

roads = gpd.read_file(f"{RAW}/osm_roads.gpkg")
trails = gpd.read_file(f"{RAW}/osm_trails.gpkg")
# the trail layer's steps and bike paths are walked too (02d_trails.py): this range's own OSM download has neither, and
# a stair down a gorge wall (Tallulah Gorge's 550 m of them) joined no path to the river. Bike paths are ridden below
_tl_all = gpd.read_file(f"{SHARED}/trails.gpkg").to_crs(CRS) if os.path.exists(f"{SHARED}/trails.gpkg") else None
if _tl_all is not None and "highway" in _tl_all:
    _tl = _tl_all[_tl_all.highway.isin(["steps", "cycleway"])].cx[XMIN - 2000:XMAX + 2000, YMIN - 2000:YMAX + 2000]
    trails = pd.concat([trails, _tl[["highway", "name", "geometry"]].to_crs(trails.crs)], ignore_index=True)
# The Forest Service roads OSM lacks (02e_access.py: source "USFS records only") are walked like the fire roads, and
# ridden below. The agencies' trails OSM lacks (02d_trails.py: "official only", drawn dotted; not the water trails it
# doesn't draw) are faint trails, walked slower (FAINT_FACTOR)
_ar = gpd.read_file(f"{SHARED}/access_roads.gpkg").to_crs(CRS).cx[XMIN - 2000:XMAX + 2000, YMIN - 2000:YMAX + 2000]
usfs_only = _ar[_ar.source.ne("OSM").values] if "source" in _ar else _ar.iloc[:0]
trails = pd.concat([trails, usfs_only[["name", "geometry"]].to_crs(trails.crs)], ignore_index=True)
faint_lines = _tl_all.iloc[:0] if _tl_all is None or "source" not in _tl_all else \
    _tl_all[_tl_all.source.eq("official only").values & ~_tl_all.get("undrawn", pd.Series(False, index=_tl_all.index))
            .fillna(False).astype(bool).values].cx[XMIN - 2000:XMAX + 2000, YMIN - 2000:YMAX + 2000]
drivable = roads[~roads.access.isin(["private", "no"]) & ~roads.motor_vehicle.isin(["no", "private"])
                 & (roads.highway != "track")]
# The times are for mid-July: a full closure cuts its road only if 07_road_closures.py counts it as still in force then
# (in_season); winter gates, short works and closures past their reopening date don't, nor one 07 could not lay on its
# road (placed: a straight line between its ends would cut whatever roads it crosses). It cuts the road it runs along,
# not the roads it meets (roadclosures.py)
closed = None
if os.path.exists(f"{MAP_OUT}/road_closures.gpkg"):
    cl = gpd.read_file(f"{MAP_OUT}/road_closures.gpkg").to_crs(CRS)
    if "in_season" not in cl:     # written before 2026-11-22
        print(f"{LABEL}: road_closures.gpkg predates the season rule (run 07_road_closures.py): today's full closures cut")
        cl["in_season"], cl["placed"] = cl.when.eq("active now"), True
    cl = cl[cl.severity.eq("full closure") & cl.in_season.astype(bool) & cl.placed.astype(bool)]
    cl = cl[cl.intersects(box(XMIN, YMIN, XMAX, YMAX).buffer(2000))]
    closed = cl.geometry.values if len(cl) else None
open_roads = drivable if closed is None else drivable.assign(geometry=roadclosures.cut(drivable.geometry.values, closed))
open_roads = open_roads[~open_roads.is_empty].explode(index_parts=False)

# Only roads a car can actually reach count as trailheads: drop pieces cut off by closures (e.g. campground
# spurs beyond a closed highway). Keep road components that touch the study-area edge (connected to the
# outside network); anything else is stranded.
import networkx as nx
G = nx.Graph()
for i, geom in enumerate(open_roads.geometry):
    cs = [(round(x), round(y)) for x, y in geom.coords]
    G.add_node(("w", i))
    for c in (cs[0], cs[-1], *cs[1:-1]):
        G.add_edge(("w", i), c)
edge = lambda x, y: min(x - XMIN, XMAX - x, y - YMIN, YMAX - y) < 300
keep = set()
for comp in nx.connected_components(G):
    if any(isinstance(n[0], (int, float)) and edge(*n) for n in comp if n[0] != "w"):
        keep |= {n[1] for n in comp if n[0] == "w"}
stranded = len(open_roads) - len(keep)
stranded_roads = open_roads.iloc[sorted(set(range(len(open_roads))) - keep)]
open_roads = open_roads.iloc[sorted(keep)]
print(f"{LABEL}: {stranded} road pieces stranded by closures or isolated")

def burn(geoms):
    geoms = [p for g in geoms if g is not None and not g.is_empty
             for p in (shapely.get_parts(g) if g.geom_type == "GeometryCollection" else [g])]
    if not geoms:
        return np.zeros(shape, bool)
    return features.rasterize(((g, 1) for g in geoms), out_shape=shape, transform=T, all_touched=True,
                              dtype="uint8").astype(bool)
on_path = burn(pd.concat([trails.geometry, roads.geometry]))   # anything with a tread is walkable at trail speed
faint = burn(faint_lines.geometry) & ~on_path                  # faint trails: where no OSM way runs
print(f"{LABEL}: faint trails (agency records only) {len(faint_lines)} lines, {int(faint.sum()):,} cells off OSM ways | "
      f"Forest Service roads OSM lacks {len(usfs_only)} pieces, {usfs_only.length.sum() / 1609.344:.0f} mi")
# A freeway is no place to leave a car: its lanes and ramps aren't trailheads (476 reaches used to start from I-5, the
# 210 and others). The exits' surface roads and the roads beside it still are; freeways stay in the network test above.
source = burn(open_roads[~open_roads.highway.isin(["motorway", "motorway_link"])].geometry)


def cycleways():
    """OSM highway=cycleway ways in the whole region (the map's layers keep fewer: 02d_trails.py), cached for a week under
    data/raw/_shared/cache (REFRESH=1 forces a new download); the old copy is used when Overpass can't be reached."""
    path = f"{SHARED}/cache/cycleways_{REGION}.json"
    have = os.path.exists(path)
    if not have or time.time() - os.path.getmtime(path) > 7 * 86400 or os.environ.get("REFRESH") == "1":
        W_, S_, E_, N_ = gpd.GeoSeries([box(XMIN, YMIN, XMAX, YMAX)], crs=CRS).to_crs(4326).total_bounds
        try:
            els = overpass(f'[out:json][timeout:300];way["highway"="cycleway"]({S_},{W_},{N_},{E_});out geom;')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(els, open(path, "w"))
        except RuntimeError:
            print(f"{LABEL}: Overpass unreachable, " + ("using the cached cycleways" if have else "no cycleways"))
            if not have:
                return gpd.GeoDataFrame({"surface": []}, geometry=[], crs=CRS)
    rows = []
    for e in json.load(open(path)):
        t = e.get("tags", {})
        if e.get("type") != "way" or len(e.get("geometry", [])) < 2 or t.get("bicycle") in ("no", "private", "dismount") \
                or (t.get("access") in ("private", "no") and t.get("bicycle") not in ("yes", "designated", "permissive")):
            continue
        rows.append(dict(surface=t.get("surface"), geometry=shapely.LineString([(p["lon"], p["lat"]) for p in e["geometry"]])))
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326).to_crs(CRS) if rows else \
        gpd.GeoDataFrame({"surface": []}, geometry=[], crs=CRS)


# ---- bikeable lines (see the docstring) ----
wild = gpd.read_file(wilderness_path()).to_crs(CRS).union_all().intersection(box(XMIN, YMIN, XMAX, YMAX).buffer(2000))
shapely.prepare(wild)
clip = lambda d: d.cx[XMIN - 2000:XMAX + 2000, YMIN - 2000:YMAX + 2000]
closed_roads = roads.iloc[:0]
if closed is not None:     # the closed stretches themselves, ridden (5 m past the cut so they join the open road)
    _rows, _parts = roadclosures.closed_parts(roads.geometry.values, closed)
    closed_roads = roads.iloc[_rows].assign(geometry=_parts)
gated = roads[(roads.access == "no") | roads.motor_vehicle.isin(["no"]) | (roads.highway == "track")]
gated = gated[gated.access != "private"]            # private roads count only where the layers below list them
ar = clip(gpd.read_file(f"{SHARED}/access_roads.gpkg").to_crs(CRS))        # 02e_access.py
usf = ar.source.ne("OSM").values if "source" in ar else np.zeros(len(ar), bool)
ab = ar[(ar.cls == "bike").values & ~usf]                                    # closed to cars, open to bikes
us = ar[usf]                                         # the Forest Service roads OSM lacks, open or closed to cars
tl = clip(gpd.read_file(f"{SHARED}/trails.gpkg").to_crs(CRS))              # 02d_trails.py
fire = tl[tl.kind == "fire road"]
single = tl[(tl.kind == "trail") & (tl.bike == "yes")]
cyc = cycleways()
paved = lambda s: s.fillna("").isin(PAVED).values
track = lambda d: d.highway.eq("track").values


def part(d, surf, kind):
    """Bike lines with a surface class (paved, dirt or single) and a kind: road (roads closed to cars and fire roads,
    ridden in wilderness too but flagged) or path (bike paths and singletrack, never in wilderness)."""
    return gpd.GeoDataFrame({"surf": np.broadcast_to(surf, len(d)), "kind": kind}, geometry=d.geometry.values, crs=CRS)


bl = pd.concat([part(closed_roads, np.where(track(closed_roads), "dirt", "paved"), "road"),
                part(stranded_roads, np.where(track(stranded_roads), "dirt", "paved"), "road"),
                part(gated, np.where(track(gated), "dirt", "paved"), "road"),
                part(ab, np.where(paved(ab.surface) | ~track(ab) & ab.surface.isna().values & ab.tracktype.isna().values,
                                  "paved", "dirt"), "road"),
                part(fire, np.where(paved(fire.surface), "paved", "dirt"), "road"),
                part(us, np.where(us.cls.eq("paved"), "paved", "dirt"), "road"),
                part(cyc, np.where(cyc.surface.isna().values | paved(cyc.surface), "paved", "dirt"), "path"),
                part(single, "single", "path")], ignore_index=True)
in_wild = bl.intersects(wild).values
cut = in_wild & bl.kind.eq("path").values
bl.loc[cut, "geometry"] = bl.geometry[cut].difference(wild)
cells = {s: burn(bl.geometry[bl.surf.eq(s).values]) for s in ("paved", "dirt", "single")}
bike = (cells["paved"] | cells["dirt"] | cells["single"]) & ~source
# where paved and dirt lines share a cell, the surface the better source knows wins (e.g. a track tagged paved)
surf_factor = np.where(cells["paved"], 1.0, np.where(cells["dirt"], DIRT_FACTOR, SINGLETRACK_FACTOR))
del cells

# fire roads where bikes may not be allowed: their bike time counts, and routes that ride them get flagged
fire_closure = fire.closed_why.fillna("").str.contains("Eaton").values
osm_closed = (fire.bike_why.eq("closed").values & ~fire_closure) | \
    (fire.access.isin(["no", "private"]).values & fire.bike_why.eq("fire road outside wilderness").values)
CHECK = {"wilderness, no bikes by law": burn(bl.geometry[in_wild & bl.kind.eq("road").values].intersection(wild)),
         "posted no bikes": burn(fire.geometry[(fire.bike.eq("no") & fire.bike_why.isin(NO_BIKES)).values]),
         "fire closure": burn(pd.concat([fire.geometry[fire_closure], ar.geometry[ar.cls.eq("closed").values]])),
         "closed or private in OpenStreetMap": burn(fire.geometry[osm_closed]),
         "a Forest Service road missing from OpenStreetMap, maybe overgrown or gated": burn(us.geometry)}
CHECK = {k: v & bike for k, v in CHECK.items()}
print(f"{LABEL}: bikeable cells {int(bike.sum()):,} ({int(bike.sum() - (surf_factor < 0.6)[bike].sum()):,} on roads), "
      f"on doubtful fire roads " + ", ".join(f"{k} {int(v.sum()):,}" for k, v in CHECK.items()) + f" | cycleways {len(cyc)}")


def line_grade(geoms, step=5.0):
    """Grade of the lines themselves on the cells they cross (NaN elsewhere): |rise| / run over GRADE_WINDOW_M of
    line, from the DEM sampled at most `step` m apart along it. Lines under 50 m long get none."""
    ln = shapely.get_parts(np.asarray(geoms, dtype=object))
    ln = ln[shapely.get_type_id(ln) == 1]                                    # LineStrings
    xy, li = shapely.get_coordinates(shapely.segmentize(ln, step), return_index=True)
    d = np.r_[0.0, np.hypot(*np.diff(xy, axis=0).T)]
    d[np.r_[True, li[1:] != li[:-1]]] = 0.0
    d = np.cumsum(d)
    first = np.r_[0, np.flatnonzero(li[1:] != li[:-1]) + 1]
    d -= np.repeat(d[first], np.diff(np.r_[first, len(li)]))                 # distance along its own line
    key = li * 1e7 + d                                                        # increasing; lines 1e7 m apart
    lo = np.searchsorted(key, key - GRADE_WINDOW_M / 2, "left")
    hi = np.searchsorted(key, key + GRADE_WINDOW_M / 2, "right") - 1
    c, r = inv * (xy[:, 0], xy[:, 1])
    z = map_coordinates(dem, [r - 0.5, c - 0.5], order=1, mode="nearest")
    run = d[hi] - d[lo]
    g = np.abs(z[hi] - z[lo]) / np.maximum(run, 1.0)
    ok = (run >= 50) & (r >= 0) & (r < H) & (c >= 0) & (c < W)
    out = np.full(H * W, np.nan, np.float32)
    out[r[ok].astype(int) * W + c[ok].astype(int)] = g[ok]
    return out.reshape(shape)


inv = ~T
lg = line_grade(bl.geometry.values)
speed = np.where(on_path, tobler(np.minimum(slope, TRAIL_MAX_GRADE)),
                 tobler(slope) * np.where((area >= 1.0) & (area < CHANNEL_MAX_KM2), CHANNEL_FACTOR, OFFTRAIL_FACTOR))
speed = np.where(~on_path & (slope > CLIFF_SLOPE), CLIFF_KMH, speed)
# faint trails: FAINT_FACTOR of a trail's speed (switchbacks too), never slower than the ground under them
speed = np.where(faint, np.maximum(speed, tobler(np.minimum(slope, TRAIL_MAX_GRADE)) * FAINT_FACTOR), speed)
grade = np.where(np.isfinite(lg), np.minimum(lg, BIKE_MAX_GRADE), np.minimum(slope, TRAIL_MAX_GRADE))
print(f"{LABEL}: bike-cell grade median {np.median(grade[bike]):.3f} along the lines "
      f"(cell slope capped at 15%: {np.median(np.minimum(slope, TRAIL_MAX_GRADE)[bike]):.3f}), "
      f"{np.isfinite(lg)[bike].mean():.0%} of bike cells have a line grade")
del lg
bike_kmh = BIKE_FLAT_KMH / (1 + BIKE_GRADE_K * grade) * surf_factor
speed = np.where(bike, np.maximum(speed, bike_kmh), speed)
del bike_kmh, grade, surf_factor
speed = np.where(nodata, 1e-3, speed)
# Lakes (05d_lakes.py, where built) can't be walked across: open water off any trail or road is as slow as a cliff.
# Before them, flat lake surfaces read as easy off-trail ground and routes crossed lakes on foot.
LAKES = gpd.read_file(f"{SHARED_DERIVED}/lakes.gpkg").to_crs(CRS) if os.path.exists(f"{SHARED_DERIVED}/lakes.gpkg") else None
if LAKES is not None:
    LAKES = LAKES[LAKES.intersects(box(XMIN, YMIN, XMAX, YMAX))].reset_index(drop=True)
    lake_cells = features.rasterize(((g, 1) for g in LAKES.geometry), out_shape=shape, transform=T, all_touched=False,
                                    dtype="uint8").astype(bool) & ~on_path
    speed = np.where(lake_cells, CLIFF_KMH, speed)
    print(f"{LABEL}: {len(LAKES)} lakes, {int(lake_cells.sum()):,} water cells off trails made impassable")
cost = 60.0 / (speed * 1000.0) * RES      # minutes to cross one cell edge-to-edge

mcp = MCP_Geometric(cost, fully_connected=True)
starts = np.argwhere(source)
cum, tb = mcp.find_costs(starts)
print(f"{LABEL}: {len(starts)} road cells; median minutes over terrain {np.nanmedian(cum[np.isfinite(cum)]):.0f}")

# origin road cell for every cell: pointer doubling on the traceback (predecessor = cell - offsets[tb])
offs = np.asarray(mcp.offsets)
rr, cc = np.indices(shape)
tbf = tb.ravel()
pr = np.where(tbf >= 0, rr.ravel() - offs[np.clip(tbf, 0, None), 0], rr.ravel())
pc = np.where(tbf >= 0, cc.ravel() - offs[np.clip(tbf, 0, None), 1], cc.ravel())
parent = (np.clip(pr, 0, H - 1) * W + np.clip(pc, 0, W - 1)).astype(np.int64)
del rr, cc, pr, pc
cumf = cum.ravel()
JUMP = None           # lake cells and the shore cells they lead to (below), for the routes (approach_routes.py)
# A point in a lake is reached at the lake's shore: every water cell takes the approach of the nearest shore cell of its
# own lake that can be reached, and leads there, with no time or distance added (its lake's quickest shore where none
# can). Without this, a reach mapped through a lake (an artificial path) cost the crossing of the impassable water: up
# to 37 hours. With the quickest shore for every cell, a creek's mouth at the far end of a long reservoir was "reached"
# at its quickest shore 20 km away (Panther Creek on Fontana Lake: 243 -> 2 min); boats aren't modelled
if LAKES is not None and lake_cells.any():
    from scipy import ndimage
    lab, nl = ndimage.label(lake_cells, structure=np.ones((3, 3), bool))
    ring = (ndimage.maximum_filter(lab, size=3) * (lab == 0)).ravel()   # a shore cell takes its neighbouring lake's label
    # A shore reached across the water (an island's) is no target: its own route runs through lake cells, which now
    # lead to shores, and a route could go round in a circle (Fontana Lake's islands, Cades Cove box). Which routes
    # cross a lake cell, by pointer doubling along them
    via = lake_cells.ravel().copy()
    par = parent.copy()
    for _ in range(48):
        via |= via[par]
        nxt = par[par]
        if np.array_equal(nxt, par):
            break
        par = nxt
    del par, nxt
    ok = (ring > 0) & np.isfinite(cumf) & ~via
    del via
    ri = np.flatnonzero(ok)
    if len(ri):
        sh = pd.DataFrame({"lab": ring[ri], "c": cumf[ri], "i": ri}).sort_values("c").drop_duplicates("lab")
        best_i = np.full(nl + 1, -1, np.int64)
        best_i[sh.lab.values] = sh.i.values
        ir, ic = ndimage.distance_transform_edt(~ok.reshape(shape), return_distances=False, return_indices=True)
        near = (ir.astype(np.int64) * W + ic).ravel()
        del ir, ic
        li = np.flatnonzero(lab.ravel() > 0)
        own = lab.ravel()[li]
        tgt = near[li]
        tgt = np.where(ring[tgt] == own, tgt, best_i[own])            # the nearest shore cell is another lake's: quickest
        li, tgt = li[tgt >= 0], tgt[tgt >= 0]
        parent[li], cumf[li], tbf[li] = tgt, cumf[tgt], -1
        JUMP = (li, tgt)
        del near
    del lab, ring
# minutes spent on bike cells, and on each kind of doubtful fire road (the last row: any of them), along each route:
# path sums by the same pointer doubling
step_min = np.where(np.isfinite(cumf), cumf - cumf[parent], 0.0)
bsum = np.where(bike.ravel(), step_min, 0.0)
LABELS = list(CHECK)
dsum = np.zeros((len(LABELS) + 1, H * W), np.float32)
for k, lab in enumerate(LABELS):
    dsum[k] = np.where(CHECK[lab].ravel(), step_min, 0.0)
dsum[-1] = np.where(np.logical_or.reduce(list(CHECK.values())).ravel(), step_min, 0.0)
del CHECK, step_min
# metres along each route (a cell's step to its predecessor is 1 or 1.41 cells), summed the same way
msum = np.where(np.isfinite(cumf) & (tbf >= 0), RES * np.hypot(*offs[np.clip(tbf, 0, None)].T), 0.0).astype(np.float32)
for _ in range(40):
    nxt = parent[parent]
    bsum = bsum + bsum[parent]
    msum = msum + msum[parent]
    dsum += dsum[:, parent]
    if np.array_equal(nxt, parent):
        break
    parent = nxt

def best(geom, step=20):
    """Along a line (or at a point): cheapest minutes, its flat index, the median minutes along it and the bike
    minutes of that median approach."""
    pts = [geom] if geom.geom_type == "Point" else list(geom.geoms) if geom.geom_type == "MultiPoint" else \
        [geom.interpolate(d) for d in np.arange(0, geom.length + step, step)]
    xs, ys = np.array([p.x for p in pts]), np.array([p.y for p in pts])
    c, r = inv * (xs, ys)
    idx = np.clip(r.astype(int), 0, H - 1) * W + np.clip(c.astype(int), 0, W - 1)
    m = cumf[idx]
    k = np.argmin(m)
    o = np.argsort(m, kind="stable")
    mid = idx[o[[(len(o) - 1) // 2, len(o) // 2]]]       # the one or two middle points np.median averages
    return m[k], idx[k], np.median(m), bsum[mid].mean()

def xy(i):
    r, c = divmod(int(i), W)
    return T * (c + 0.5, r + 0.5)

def table(gdf, key, cells=None):
    """The access columns for each row of gdf; cells (a list), if given, gets each row's approach cell (-1: none)."""
    rows = []
    for k, g in zip(gdf[key], gdf.geometry):
        mins, i, med, bmed = best(g)
        o = parent[i]
        fin = np.isfinite(mins)
        if cells is not None:
            cells.append(int(i) if fin else -1)
        why = [lab for j, lab in enumerate(LABELS) if fin and dsum[j, i] >= CHECK_MIN]
        rows.append(dict({key: k}, approach_min=round(float(mins), 0) if fin else None,
                         bike_min=round(float(bsum[i]), 0) if fin else None,
                         # the bike leg can round a hair above the whole approach: never "hike -0 min" (153 lines)
                         walk_min=max(0.0, round(float(mins - bsum[i]), 0)) if fin else None,
                         bike_check="; ".join(why) if why else None,
                         bike_check_min=round(float(dsum[-1, i]), 0) if why else None,
                         approach_med_min=round(float(med), 0) if np.isfinite(med) else None,
                         bike_med_min=round(float(bmed), 0) if np.isfinite(med) else None,
                         route_km=round(float(msum[i]) / 1000, 2) if fin else None,
                         th_x=xy(o)[0], th_y=xy(o)[1]))
    return pd.DataFrame(rows)

streams = gpd.read_file(f"{OUT}/streams_scored.gpkg").to_crs(CRS)
drops = gpd.read_file(f"{OUT}/waterfall_candidates.gpkg").to_crs(CRS)
# a drop is reachable at its top or at its pool/base: use whichever is closer
pool = gpd.GeoSeries(gpd.points_from_xy(drops.pool_lon, drops.pool_lat), crs=4326).to_crs(CRS)
drops["geometry"] = [MultiPoint([a, b]) for a, b in zip(drops.geometry, pool)]
start_cells = {"stream": [], "drop": [], "lake": []}     # approach cells, for the routes (approach_routes.py)
start_ids = {"stream": streams.sid.values, "drop": drops.did.values, "lake": []}
ts, td = table(streams, "sid", start_cells["stream"]), table(drops, "did", start_cells["drop"])
# lakes: reached at the nearest point of the shore in this box, on the land side (a line 7 m out from the water)
tl = None
if LAKES is not None and len(LAKES):
    inner = box(XMIN + 5, YMIN + 5, XMAX - 5, YMAX - 5)
    ring = [g.buffer(7).boundary.intersection(inner) for g in LAKES.geometry]
    ok = [not r_.is_empty and r_.length > 0 for r_ in ring]
    tl = table(gpd.GeoDataFrame({"lid": LAKES.lid[ok].values}, geometry=[r_ for r_, k in zip(ring, ok) if k], crs=CRS), "lid",
               start_cells["lake"])
    start_ids["lake"] = LAKES.lid[ok].values

# trailheads: snap origins to a 250 m grid so neighbouring road cells collapse into one access point
both = pd.concat([ts, td] + ([tl] if tl is not None else []), ignore_index=True)
both["th_id"] = REGION + ":t" + ((both.th_x // 250).astype(int).astype(str) + "_" + (both.th_y // 250).astype(int).astype(str))
# A trailhead stands at the middle of the start points of what it serves. Where it serves any of the 0.25 km2 network's
# reaches, a drop or a lake, those alone place it, as before 03b_stitch.py laid lines lower along NHD's lines
# (low_channel): one of those sharing its 250 m cell moved it, and with it the drive and the road named for the places
# it served before. Its count (n) is of all it serves
_lo = np.zeros(len(both), bool)
if "low_channel" in streams:
    _lo[:len(ts)] = ts.sid.map(dict(zip(streams.sid, pd.to_numeric(streams.low_channel, errors="coerce").fillna(0) > 0))
                               ).fillna(False).to_numpy(bool)
_b = both[~_lo | ~both.th_id.isin(set(both.th_id[~_lo]))]
th = _b.groupby("th_id").agg(x=("th_x", "median"), y=("th_y", "median")).reset_index()
th["n"] = th.th_id.map(both.groupby("th_id").size()).astype(int)
th = gpd.GeoDataFrame(th, geometry=gpd.points_from_xy(th.x, th.y), crs=CRS)
# a start point is never on a freeway (see `source`), so it isn't named after one that runs beside its road either
named = drivable[drivable.name.notna() & ~drivable.highway.isin(["motorway", "motorway_link"])]
th["road"] = gpd.sjoin_nearest(th[["geometry"]], named[["name", "geometry"]], how="left",
                               max_distance=300).groupby(level=0).first().name
ts = ts.merge(both[["th_x", "th_y", "th_id"]].drop_duplicates(["th_x", "th_y"]), on=["th_x", "th_y"])
td = td.merge(both[["th_x", "th_y", "th_id"]].drop_duplicates(["th_x", "th_y"]), on=["th_x", "th_y"])
ts.drop(columns=["th_x", "th_y"]).to_csv(f"{OUT}/hike_streams.csv", index=False)
td.drop(columns=["th_x", "th_y"]).to_csv(f"{OUT}/hike_drops.csv", index=False)
if tl is not None:
    tl = tl.merge(both[["th_x", "th_y", "th_id"]].drop_duplicates(["th_x", "th_y"]), on=["th_x", "th_y"])
    tl.drop(columns=["th_x", "th_y"]).to_csv(f"{OUT}/hike_lakes.csv", index=False)
    print(f"{LABEL}: lakes {len(tl)}, median approach {tl.approach_min.median():.0f} min")
th.drop(columns=["x", "y"]).to_file(f"{OUT}/trailheads.gpkg")

with rasterio.open(f"{DERIVED}/hike_minutes.tif", "w", **dict(src.profile, dtype="float32", nodata=-1,
                                                                compress="deflate")) as dst:
    dst.write(np.where(np.isfinite(cum), cum, -1).astype("float32"), 1)
assert source.ravel()[parent[np.isfinite(cumf)]].all(), "trailhead trace did not end on a road cell"
print(f"reaches: median approach along reach {ts.approach_med_min.median():.0f} min, {(ts.bike_min >= 1).mean():.0%} use a "
      f"bike leg, {ts.bike_check.notna().sum()} flagged to double-check bike access | drops: median "
      f"{td.approach_min.median():.0f} min, {(td.bike_min >= 1).mean():.0%} use a bike leg, {td.bike_check.notna().sum()} "
      f"flagged | trailheads {len(th)}")

# ---- the routes, for the map pages (approach_routes.py): each start's fastest route from its trailhead, followed back
# through the traceback (tbf; a lake cell leads to its shore, JUMP), on the lines burned in above ----
import approach_routes
approach_routes.build(
    OUT, CRS, {k: (start_ids[k], start_cells[k]) for k in start_cells},
    tbf, offs, T, bike, on_path | faint, area, bike_lines=bl.geometry.values,          # a faint trail is a trail
    path_lines=pd.concat([trails.geometry, roads.geometry, faint_lines.geometry.to_crs(trails.crs)]).values,  # on_path
    road_lines=open_roads[~open_roads.highway.isin(["motorway", "motorway_link"])].geometry.values,   # source
    jump=JUMP, creek_km2=1.0, creek_max_km2=CHANNEL_MAX_KM2,   # creek bottoms, as `speed` walks them (the cap too)
    label=LABEL)
