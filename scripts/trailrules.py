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
import os, json, time, numpy as np, pandas as pd, geopandas as gpd, shapely
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
