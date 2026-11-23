"""Where an area stops at a state line inside its boxes.

An area whose entry in config.AREAS has clip_state keeps and shows only what lies in that state. Central Vermont
("VT") reaches west into Lake Champlain, whose middle is the New York line (user, 2026-11-20: "expand vermont all the
way to its border in the middle of lake champlain"). Its boxes are rectangles, so they take in New York's shore where
the line bends east: about 300 km2 of it from Ticonderoga to Willsboro, which is no part of the Vermont map. The
hydrology runs on the whole boxes as everywhere else (that shore drains into the lake, and nothing of it reaches a
Vermont creek); what is kept is cut at the line:
  05_score.py       reaches and drops (by their middle point), the trails and known falls it copies, the hillshade
  05c_drainages.py  drainage outlines
  05d_lakes.py      lakes (Lake Champlain is stored to the line); lake_bathymetry.py's depth lines
  06_map.py         the other map layers: trails, access roads, parking, road closures, context layers
State outlines: US Census TIGER/Line 2024 (public domain), downloaded once to data/raw/_national."""
import os, functools, numpy as np, requests, geopandas as gpd, shapely
from config import A, CRS, NATIONAL

URL = "https://www2.census.gov/geo/tiger/TIGER2024/STATE/tl_2024_us_state.zip"
ZIP = f"{NATIONAL}/tl_2024_us_state.zip"


@functools.lru_cache(None)
def outline(crs=CRS):
    """The state this area stops at, as one (multi)polygon in `crs`; None for an area that is just its boxes."""
    st = A.get("clip_state")
    if not st:
        return None
    if not os.path.exists(ZIP):
        import netfetch
        r = netfetch.fetch("GET", URL, timeout=600, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
        with open(ZIP + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(ZIP + ".tmp", ZIP)
    g = gpd.read_file(f"zip://{ZIP}", where=f"STUSPS = '{st}'")
    if not len(g):
        raise SystemExit(f"clip_state {st!r}: no such state in {ZIP}")
    o = shapely.make_valid(g.to_crs(crs).geometry.union_all())
    shapely.prepare(o)
    return o


def middle(geoms):
    """A line's halfway point, a polygon's point on its surface, a point itself."""
    geoms = np.asarray(geoms, dtype=object)
    out = shapely.point_on_surface(geoms)
    ln = np.isin(shapely.get_type_id(geoms), (1, 2))          # LineString, LinearRing
    out[ln] = shapely.line_interpolate_point(geoms[ln], 0.5, normalized=True)
    return out


def inside(geoms, crs=CRS):
    """True where a geometry's middle lies in the area's state; all True for an area without clip_state."""
    o = outline(crs)
    geoms = np.asarray(geoms, dtype=object)
    if o is None:
        return np.ones(len(geoms), bool)
    return shapely.intersects(o, middle(geoms))


def cut(gdf):
    """gdf (any CRS) cut along the area's state line: geometries intersected with the state, features left empty
    dropped. gdf itself for an area without clip_state."""
    if gdf is None or not len(gdf) or A.get("clip_state") is None:
        return gdf
    o = outline(gdf.crs.to_string())
    keep = shapely.intersects(gdf.geometry.values, o)
    g = gdf[keep].copy()
    g["geometry"] = shapely.make_valid(shapely.intersection(g.geometry.values, o))
    # keep each feature's own kind of geometry (a lake stays polygons, a trail lines): an intersection can add stray
    # points or lines where an outline only touches the line
    dim = shapely.get_dimensions(gdf.geometry.values[keep])
    g["geometry"] = [_parts(x, d) for x, d in zip(g.geometry.values, dim)]
    return g[~shapely.is_empty(g.geometry.values)]


def _parts(x, dim):
    """The parts of x of dimension dim (0 points, 1 lines, 2 polygons), as one geometry."""
    if shapely.get_dimensions(x) == dim and x.geom_type != "GeometryCollection":
        return x
    parts = [p for p in shapely.get_parts(x) if shapely.get_dimensions(p) == dim]
    parts = [q for p in parts for q in shapely.get_parts(p)]
    if not parts:
        return shapely.GeometryCollection()
    return shapely.union_all(parts) if dim == 2 else (shapely.MultiLineString(parts) if dim == 1 else shapely.MultiPoint(parts))
