"""Where an area stops at a state line inside its boxes.

An area whose entry in config.AREAS has clip_state keeps and shows only what lies in that state, or in those states
when it names several. Central Vermont ("VT") reaches west into Lake Champlain, whose middle is the New York line
(user, 2026-11-20: "expand vermont all the way to its border in the middle of lake champlain"). Its boxes are
rectangles, so they take in New York's shore where the line bends east: about 300 km2 of it from Ticonderoga to
Willsboro, which is no part of the Vermont map. Southeastern Pennsylvania (("PA", "DE", "MD")) reaches east and south
to the Delaware River (user, 2026-11-23: "everything here west of the delaware river"), and its boxes take in New
Jersey across it. The hydrology runs on the whole boxes as everywhere else (that shore drains into the lake or the
river, and nothing of it reaches a creek on the map); what is kept is cut at the line:
  05_score.py       reaches and drops (by their middle point), the trails and known falls it copies, the hillshade
  05c_drainages.py  drainage outlines
  05d_lakes.py      lakes (Lake Champlain is stored to the line); lake_bathymetry.py's depth lines
  06_map.py         the other map layers: trails, access roads, parking, road closures, context layers
  creekprofiles.py  the creeks given a long profile (12_profiles.py, and 06_map.py's links to them), as reaches are
A river that is itself the state line (the Delaware between Pennsylvania and New Jersey above the tide at Trenton)
is kept whole: its line wanders either side of the line down its middle, and by its middle point alone the map would
show it in pieces. A line kept that way lies, half its length or more, in the river's own water: NHD HR's river area
(StreamRiver) within RIVER_M of the state line. TIGER's line strays up to about 250 m from NHD's centre line at Yardley,
where the river's whole line lies on the New Jersey side of it; a creek, a ditch along the shore or the canal along
the bank lies on land, not in the river (within 200 m of the line they had been kept; the line along the New Jersey
shore inside Delaware's twelve-mile circle is no river's middle). The river's own falls show with it (in_river: a known
falls in its water, or within RIVER_NEAR_M of it): Scudders Falls and the Falls of the Delaware at Trenton lie in the
Delaware on the New Jersey side of the line. Drops and water-temperature sites still go by the state alone: in the
river's water past the line lie the tidal river's sites and New Jersey creeks' mouths, no part of the map.
State outlines: US Census TIGER/Line 2024 (public domain), downloaded once to data/raw/_national."""
import os, functools, numpy as np, requests, geopandas as gpd, shapely
from config import A, CRS, NATIONAL, REGIONS

URL = "https://www2.census.gov/geo/tiger/TIGER2024/STATE/tl_2024_us_state.zip"
ZIP = f"{NATIONAL}/tl_2024_us_state.zip"
RIVER_M = 400        # NHD's river area this near the state line is the water of a river the line runs down


def states():
    """The states the area keeps (config clip_state: one name or several), as a tuple; () for an area that is just its
    boxes."""
    st = A.get("clip_state")
    return () if not st else (st,) if isinstance(st, str) else tuple(st)


@functools.lru_cache(None)
def outline(crs=CRS):
    """The state (or states) this area keeps, as one (multi)polygon in `crs`; None for an area that is just its boxes."""
    st = states()
    if not st:
        return None
    if not os.path.exists(ZIP):
        import netfetch
        r = netfetch.fetch("GET", URL, timeout=600, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
        with open(ZIP + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(ZIP + ".tmp", ZIP)
    g = gpd.read_file(f"zip://{ZIP}", where="STUSPS IN (" + ", ".join(f"'{s}'" for s in st) + ")")
    missing = set(st) - set(g.STUSPS)
    if missing:
        raise SystemExit(f"clip_state {', '.join(sorted(missing))}: no such state in {ZIP}")
    o = shapely.make_valid(g.to_crs(crs).geometry.union_all())
    shapely.prepare(o)
    return o


@functools.lru_cache(None)
def line(crs=CRS):
    """The state line inside the area's boxes (the outline's boundary there, 1 km around them): where a kept state meets
    one that isn't (New York in Lake Champlain, New Jersey in the Delaware). None for an area that is just its boxes."""
    o = outline(crs)
    if o is None:
        return None
    boxes = gpd.GeoSeries([shapely.box(*v["bbox"]) for v in REGIONS.values()], crs=CRS).to_crs(crs).union_all()
    ln = shapely.intersection(o.boundary, boxes.buffer(1000))
    shapely.prepare(ln)
    return ln


@functools.lru_cache(None)
def river(crs=CRS):
    """The water of a river the state line runs down: NHD HR's river areas (StreamRiver, from the area's HU4 downloads)
    within RIVER_M of the line. None where the line runs through none (Lake Champlain is a lake)."""
    ln = line(crs)
    if ln is None or ln.is_empty:
        return None
    import pyogrio, pandas as pd
    bb = gpd.GeoSeries([ln.buffer(RIVER_M)], crs=crs).to_crs(4269).total_bounds
    parts = []
    for hu in sorted({h for v in REGIONS.values() for h in v["hu4"]}):
        p = f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg"
        if not os.path.exists(p):
            continue
        lyr = next(l for l in pyogrio.list_layers(p)[:, 0] if l.lower() == "nhdarea")
        a = gpd.read_file(p, layer=lyr, bbox=tuple(bb), columns=["ftype"])
        a.columns = [c.lower() if c != "geometry" else c for c in a.columns]
        parts.append(a[a.ftype == 460].to_crs(crs).geometry)
    if not sum(len(x) for x in parts):
        return None
    z = shapely.intersection(shapely.make_valid(shapely.union_all(pd.concat(parts).values)), ln.buffer(RIVER_M))
    if z.is_empty:
        return None
    shapely.prepare(z)
    return z


def middle(geoms):
    """A line's halfway point, a polygon's point on its surface, a point itself."""
    geoms = np.asarray(geoms, dtype=object)
    out = shapely.point_on_surface(geoms)
    ln = np.isin(shapely.get_type_id(geoms), (1, 2))          # LineString, LinearRing
    out[ln] = shapely.line_interpolate_point(geoms[ln], 0.5, normalized=True)
    return out


def inside(geoms, crs=CRS):
    """True where a geometry's middle lies in the area's state, or where a line lies, half its length or more, in the
    water of a river the state line runs down (river(): the river that is the line); all True for an area without
    clip_state."""
    o = outline(crs)
    geoms = np.asarray(geoms, dtype=object)
    if o is None:
        return np.ones(len(geoms), bool)
    keep = np.asarray(shapely.intersects(o, middle(geoms)), bool)
    ln = ~keep & np.isin(shapely.get_type_id(geoms), (1, 2, 5))       # LineString, LinearRing, MultiLineString
    z = river(crs) if ln.any() else None
    if z is not None:
        g = geoms[ln]
        wet = shapely.length(shapely.intersection(g, z)) >= 0.5 * shapely.length(g)
        keep[np.flatnonzero(ln)[wet & (shapely.length(g) > 0)]] = True
    return keep


RIVER_NEAR_M = 25    # a point this near the river's water is in the river (a falls placed on the bank, NHD's outline)


def in_river(geoms, crs=CRS, near=RIVER_NEAR_M):
    """True where a point lies in the water of a river the state line runs down (river()), or within `near` of it: the
    river's own falls, shown as the river is. All False for an area without such a river."""
    geoms = np.asarray(geoms, dtype=object)
    z = river(crs) if len(geoms) and outline(crs) is not None else None
    if z is None:
        return np.zeros(len(geoms), bool)
    return np.asarray(shapely.dwithin(geoms, z, near), bool)


def cut(gdf):
    """gdf (any CRS) cut along the area's state line: geometries intersected with the state, features left empty
    dropped. gdf itself for an area without clip_state."""
    if gdf is None or not len(gdf) or not states():
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
