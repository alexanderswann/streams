"""Shared helpers for the audit scripts. Read-only on the project: nothing here writes outside audit/ or a scratchpad.

Sides to measure are picked by environment variables:
    SITE_DIR      folder holding <area>/map3d_data.js as published (default: the site clone's docs/ folder, the gh-pages
                  branch of github.com/alexanderswann/streams; before 2026-11-23 the maps were in the personal site's streams/)
    SITE_NAME     a label for the tables (default: the site clone's gh-pages commit)
    AUDIT_TABLES  folder the tables are written to (default: audit/tables)
    TABLES_DIR    (fish_score_audit.py, falls_lakes_checks.py) folder with <area>/stream_reaches_ranked.csv etc.,
                  tried before output/<area>/
config.py is not imported (it creates folders): its AREAS table is read from the source text.
"""
import ast, json, os, pickle, hashlib, subprocess, warnings
import numpy as np

warnings.filterwarnings("ignore")
# the project this folder is in (a scratch copy's own, when run from one: the new-area test)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCR = f"{ROOT}/scripts"
CLONE = f"{ROOT}/publish/streams-site"
SITE_DIR = os.environ.get("SITE_DIR", f"{CLONE}/docs")
TABLES = os.environ.get("AUDIT_TABLES", f"{ROOT}/audit/tables")
CACHE = os.environ.get("AUDIT_CACHE", "/private/tmp/claude-501/-Users-mac-Fishing/b1190042-de6e-4861-932a-f7b59d4a72e3/scratchpad/cache")
os.makedirs(TABLES, exist_ok=True)
os.makedirs(CACHE, exist_ok=True)


def site_name():
    if os.environ.get("SITE_NAME"):
        return os.environ["SITE_NAME"]
    if SITE_DIR.startswith(CLONE):
        return subprocess.run(["git", "-C", CLONE, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    return os.path.basename(SITE_DIR.rstrip("/"))


def _areas():
    tree = ast.parse(open(f"{SCR}/config.py").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "AREAS":
            ns = {}
            exec(compile(ast.Module([node], []), "config_AREAS", "exec"), {"dict": dict}, ns)
            if os.environ.get("AREAS_FILE"):          # the new-area test's places (config.py reads them the same way)
                with open(os.environ["AREAS_FILE"]) as f:
                    for k, v in json.load(f).items():
                        ns["AREAS"].setdefault(k, v)
            return ns["AREAS"]
    raise SystemExit("AREAS not found in config.py")


AREAS = _areas()
NAMES = list(AREAS)


def epsg(area):
    return AREAS[area]["crs"]


def boxes(area):
    return AREAS[area]["ranges"]


def load_map(area, site_dir=None):
    """The MAP3D object of an area's published map3d_data.js (cached as a pickle keyed by the file's hash)."""
    path = f"{site_dir or SITE_DIR}/{area}/map3d_data.js"
    raw = open(path, "rb").read()
    key = hashlib.sha1(raw).hexdigest()[:16]
    pk = f"{CACHE}/map_{area}_{key}.pkl"
    if os.path.exists(pk):
        return pickle.load(open(pk, "rb"))
    s = raw.decode("utf-8")
    d = json.loads(s[s.index("{"):s.rindex("}") + 1])
    pickle.dump(d, open(pk, "wb"))
    return d


def streams_gdf(area, layer="streams", site_dir=None, project=True):
    """A layer of the published map as a GeoDataFrame in the area's UTM zone (or lon/lat)."""
    import geopandas as gpd, shapely
    d = load_map(area, site_dir)
    feats = d[layer]["features"]
    props = [f["properties"] for f in feats]
    geoms = []
    for f in feats:
        g = f["geometry"]
        if g["type"] == "LineString":
            geoms.append(shapely.LineString(g["coordinates"]))
        elif g["type"] == "MultiLineString":
            geoms.append(shapely.MultiLineString(g["coordinates"]))
        else:
            geoms.append(shapely.geometry.shape(g))
    gdf = gpd.GeoDataFrame(props, geometry=geoms, crs=4326)
    return gdf.to_crs(epsg(area)) if project else gdf


def seg_midpoints(geoms, step=25.0):
    """Cut every line into pieces of at most `step` metres: (x, y, length, index of the line) per piece."""
    import shapely
    g = shapely.segmentize(np.asarray(geoms, dtype=object), step)
    parts, pidx = shapely.get_parts(g, return_index=True)
    xy, idx = shapely.get_coordinates(parts, return_index=True)
    same = idx[1:] == idx[:-1]
    a, b = xy[:-1][same], xy[1:][same]
    ln = np.hypot(*(b - a).T)
    mid = (a + b) / 2
    return mid[:, 0], mid[:, 1], ln, pidx[idx[:-1][same]]


def nearest_dist(px, py, tree_geoms, maxd=500.0):
    """Distance from each point to the nearest of tree_geoms (inf beyond maxd), and that geometry's index (-1)."""
    import shapely
    tree = shapely.STRtree(np.asarray(tree_geoms, dtype=object))
    pts = shapely.points(px, py)
    (pi, ti), dist = tree.query_nearest(pts, max_distance=maxd, return_distance=True, all_matches=False)
    d = np.full(len(pts), np.inf)
    j = np.full(len(pts), -1)
    d[pi] = dist
    j[pi] = ti
    return d, j


def nhd_lines(area):
    """NHD HR flowlines of every box of an area, in the area's UTM zone, duplicates across boxes dropped."""
    import geopandas as gpd, pandas as pd
    out = []
    for r in boxes(area):
        p = f"{ROOT}/data/raw/{area}/{r}/nhd_flowlines.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p)
            g["box"] = r
            out.append(g.to_crs(epsg(area)))
    g = pd.concat(out, ignore_index=True)
    g["wkb"] = g.geometry.to_wkb()
    g = g.drop_duplicates("wkb").drop(columns="wkb").reset_index(drop=True)
    return gpd.GeoDataFrame(g, geometry="geometry", crs=epsg(area))


def area_box_union(area):
    import shapely
    return shapely.union_all([shapely.box(*b["bbox"]) for b in boxes(area).values()])


MI = 1609.344
FT = 0.3048
