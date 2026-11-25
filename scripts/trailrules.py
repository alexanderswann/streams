"""Which OpenStreetMap ways the trail and road layers keep on flat ground, and the bike-path download they share
(02d_trails.py, 02e_access.py).

Mountain terrain (the area's MIN_RELIEF_M of relief within 1 km) keeps every trail, track and dirt road, as before.
Flat ground is where the towns are; there the layers used to keep only a path named like a trail, on a hiking route or
on an agency's trail list, and no dirt road at all, so a paved greenway along a creek through a suburb (the Rottenwood
Creek Trail, Chattahoochee tailwater, mapped in OSM as bike paths named "Bob Callan Trail"), the river paths of the
Chattahoochee River NRA and the farm and forest tracks down to Piedmont creeks were left off the maps. On flat ground a
way is now kept when an angler can use it to reach water:
  - it has a name, is on a hiking route or follows an agency's trail record (any name: "West Palisades", "Blue Loop"),
  - or it runs along the water: half its length within WATER_M of a reach the map draws or of a lake,
and it is not a sidepath: an unnamed footway, path or bike path that runs within SIDE_M of a car road for SIDE_SHARE
of its length is that road's sidewalk or side path (OSM often leaves it untagged), and the basemap draws the road.
Measured on the 12 maps (2026-11-25, trails-and-roads session); the numbers are in its notes.
"""
import os, json, time, numpy as np, pandas as pd, geopandas as gpd, shapely, shapely.ops
from config import REGIONS, CRS, SHARED, SHARED_DERIVED, raw_dir, out_dir

SIDE_M, SIDE_SHARE = 20.0, 0.6      # a sidepath: this share of an unnamed way within SIDE_M of a car road
WATER_M, WATER_SHARE = 150.0, 0.5   # along the water: this share of a way within WATER_M of a drawn reach or a lake
STEP_M = 25.0                       # the shares are read at points this far apart along each way
CAR = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
       "tertiary", "tertiary_link", "unclassified", "residential", "living_street"}
# a bike path OSM names as a road (Old Pass Road, Mount Hollywood Drive) is a road closed to cars: the road layer
# draws it, as class "bike"; every other bike path is a trail
ROAD_NAME = r"\b(?:road|rd|drive|dr|street|st|avenue|ave|lane|ln|highway|hwy|boulevard|blvd)\.?$"


def cycleway_elements(key, bbox):
    """OSM highway=cycleway ways in one range's lon/lat box (W, S, E, N): one download, kept a week (REFRESH=1 to
    force a new one), shared by 02d_trails.py and 02e_access.py in data/raw/<area>/_shared/cache/
    access_osm_cycleway_<range>.json; when Overpass can't be reached the older copy stays (netfetch.keep_old)."""
    import netfetch
    W, S, E, N = bbox
    path = f"{SHARED}/cache/access_osm_cycleway_{key}.json"
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400 and os.environ.get("REFRESH") != "1":
        return json.load(open(path))

    def dl():
        els = netfetch.overpass(f'[out:json][timeout:300];way["highway"="cycleway"]({S},{W},{N},{E});out geom;')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(els, open(path + ".tmp", "w"))
        os.replace(path + ".tmp", path)
        return els
    els = netfetch.keep_old(path, dl, f"OSM cycleways ({key})")
    return json.load(open(path)) if els is None else els


def share_near(lines, targets, dist, step=STEP_M):
    """For each projected line, the share of points `step` m apart along it (both ends included) that lie within
    `dist` m of any of the target geometries."""
    lines = np.asarray(lines, dtype=object)
    out = np.zeros(len(lines))
    targets = np.asarray([t for t in targets if t is not None and not t.is_empty], dtype=object)
    if not len(lines) or not len(targets):
        return out
    tree = shapely.STRtree(targets)
    L = shapely.length(lines)
    n = np.maximum(2, (L // step).astype(int) + 1)
    own = np.repeat(np.arange(len(lines)), n)
    k = np.arange(len(own)) - np.repeat(np.cumsum(n) - n, n)
    pts = shapely.line_interpolate_point(lines[own], k / np.repeat(n - 1, n) * np.repeat(L, n))
    hit = np.zeros(len(pts), bool)
    for a in range(0, len(pts), 1_000_000):
        i = tree.query_nearest(pts[a:a + 1_000_000], max_distance=dist, all_matches=False)[0]
        hit[a + np.unique(i)] = True
    return np.bincount(own, weights=hit, minlength=len(lines)) / n


def car_roads():
    """Every range's car roads (02_download_vectors.py's osm_roads.gpkg), projected."""
    parts = []
    for r in REGIONS:
        p = f"{raw_dir(r)}/osm_roads.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p)
            parts.append(g[g.highway.isin(CAR)].to_crs(CRS).geometry)
    return pd.concat(parts).values if parts else np.array([], dtype=object)


def water():
    """The water the map will draw: every range's reaches (05_score.py's streams_scored.gpkg, written before the trail
    and road steps run) and the lakes (05d_lakes.py), projected. Empty before 05_score.py's first run."""
    parts = []
    for r in REGIONS:
        p = f"{out_dir(r)}/streams_scored.gpkg"
        if os.path.exists(p):
            parts.append(gpd.read_file(p).to_crs(CRS).geometry)
    lp = f"{SHARED_DERIVED}/lakes.gpkg"
    if os.path.exists(lp):
        parts.append(gpd.read_file(lp).to_crs(CRS).geometry)
    return pd.concat(parts).values if parts else np.array([], dtype=object)


def along_water(lines, wet=None):
    """True for each projected line with WATER_SHARE of it within WATER_M of the water (water())."""
    return share_near(lines, water() if wet is None else wet, WATER_M) >= WATER_SHARE


def beside_road(lines, roads=None):
    """True for each projected line with SIDE_SHARE of it within SIDE_M of a car road (car_roads())."""
    return share_near(lines, car_roads() if roads is None else roads, SIDE_M) >= SIDE_SHARE


# ---- Forest Service roads OpenStreetMap lacks (the user, 2026-11-25: "Draw and ride them") ----
# A USFS road line (EDW RoadBasic, open or closed to the public) is cut USFS_CUT_M around every OSM way; a piece of
# USFS_MIN_M or more is a road OSM lacks, unless it is an offset copy of a way the maps have (map_ways(): OSM's, and the
# agencies' trails the trail layer draws): the median distance of its points (USFS_STEP_M apart) to the nearest way under
# COPY_M, or under COPY_PAR_M with PAR_SHARE of its points beside a way that runs within PAR_DEG of the piece's own
# direction. A USFS line drawn off the road OSM has runs alongside it; a road OSM lacks leaves the ways it starts from.
USFS_CUT_M, USFS_MIN_M, USFS_STEP_M = 40.0, 200.0, 50.0
COPY_M, COPY_PAR_M, PAR_SHARE, PAR_DEG = 100.0, 300.0, 0.6, 30.0


def map_ways(extra=()):
    """Every way the maps have, projected LineStrings: each range's OSM roads and paths (02_download_vectors.py), the
    trail layer's lines (02d_trails.py: its OSM tracks, steps and bike paths, and the agencies' trails OSM lacks, but not
    the water trails it doesn't draw) and `extra` (02e_access.py's own download)."""
    parts = [np.asarray(list(extra), dtype=object)]
    for r in REGIONS:
        for f in ("osm_roads", "osm_trails"):
            p = f"{raw_dir(r)}/{f}.gpkg"
            if os.path.exists(p):
                parts.append(gpd.read_file(p, columns=[]).to_crs(CRS).geometry.values)
    p = f"{SHARED}/trails.gpkg"
    if os.path.exists(p):
        t = gpd.read_file(p)
        drawn = ~t.undrawn.fillna(False).astype(bool) if "undrawn" in t else pd.Series(True, index=t.index)
        parts.append(t[t.osm_id.notna() | drawn].to_crs(CRS).geometry.values)
    g = shapely.get_parts(np.concatenate([np.asarray(x, dtype=object) for x in parts]))
    return g[shapely.get_type_id(g) == 1]


def _heading(lines, d):
    """Each line's direction (degrees, 0-180) at d m along it, over 20 m."""
    a = shapely.line_interpolate_point(lines, np.maximum(d - 10.0, 0.0))
    b = shapely.line_interpolate_point(lines, np.minimum(d + 10.0, shapely.length(lines)))
    return np.degrees(np.arctan2(shapely.get_y(b) - shapely.get_y(a), shapely.get_x(b) - shapely.get_x(a))) % 180


def usfs_only(lines, ways):
    """The pieces of USFS road lines (projected) no way covers (ways: map_ways()). A DataFrame: line (the index
    into `lines`), geometry (the piece, lengthened by USFS_CUT_M along its own line at each cut end so it meets the
    way it was cut from), len_m (before that), median_m (to the nearest OSM way), parallel (the share of its points
    beside a way running its way) and offset_copy (a copy of an OSM way drawn off it, by the rule above)."""
    ways = np.asarray(ways, dtype=object)
    tree = shapely.STRtree(ways) if len(ways) else None
    rows = []
    for i, ln in enumerate(lines):
        if ln is None or ln.is_empty:
            continue
        for part in shapely.get_parts(ln):
            if part.geom_type != "LineString" or part.length < USFS_MIN_M:
                continue
            near = tree.query(part, predicate="dwithin", distance=USFS_CUT_M) if tree is not None else []
            rest = part.difference(shapely.union_all(shapely.buffer(ways[near], USFS_CUT_M))) if len(near) else part
            for piece in shapely.get_parts(shapely.line_merge(rest) if rest.geom_type == "MultiLineString" else rest):
                if piece.geom_type != "LineString" or piece.length < USFS_MIN_M:
                    continue
                d = np.linspace(0.0, piece.length, max(3, int(piece.length // USFS_STEP_M)))
                pts = shapely.line_interpolate_point(piece, d)
                med, par = np.inf, 0.0
                if tree is not None:
                    (pi, wi), dist = tree.query_nearest(pts, return_distance=True, all_matches=False)
                    med = float(np.median(dist))
                    turn = np.abs(_heading(np.full(len(pi), piece, dtype=object), d[pi])
                                  - _heading(ways[wi], shapely.line_locate_point(ways[wi], pts[pi]))) % 180
                    par = float(np.mean(np.minimum(turn, 180 - turn) < PAR_DEG))
                s, e = sorted((part.project(shapely.Point(piece.coords[0])), part.project(shapely.Point(piece.coords[-1]))))
                geom = shapely.ops.substring(part, max(s - USFS_CUT_M, 0.0), min(e + USFS_CUT_M, part.length))
                if geom.geom_type != "LineString" or geom.length > piece.length + 2 * USFS_CUT_M + 1:
                    geom = piece                       # a line that loops back on itself: the piece as cut
                rows.append(dict(line=i, geometry=geom, len_m=piece.length, median_m=med, parallel=par,
                                 offset_copy=med < COPY_M or (med < COPY_PAR_M and par >= PAR_SHARE)))
    return pd.DataFrame(rows, columns=["line", "geometry", "len_m", "median_m", "parallel", "offset_copy"])
