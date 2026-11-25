"""An area's settings worked out from its outline (the new-area plan's B1, 2026-11-23).

00_area.py calls these for one area and writes the result to data/derived/<area>/_shared/area.json; derive_check.py
calls them for every area and compares them with the values config.py and the per-area tables give by hand.

  outline_ll(entry)        the area's outline in lon/lat: its boxes' union, or the outline its config entry gives
                           (a lon/lat rectangle (w, s, e, n), or a polygon file any GDAL format holds)
  utm_epsg(outline)        NAD83 / UTM zone (EPSG 269zz) holding most of the outline
  one_box(outline, epsg)   an area given only an outline: one box around it, in its zone's metres, outward to the km;
                           more than MAX_BOX_KM2 stops (several boxes are the layout step's work, B8)
  states(outline, clip)    the states the outline reaches into (TIGER/Line 2024; any piece of 0.1 km2 or more), or
                           just clip_state's (one state or several)
  hu4(bbox, epsg)          the NHD 4-digit units whose WBD outlines meet a box as 02_download_vectors.py reads it
                           (the box's lon/lat bounds), from the USGS WBD service, kept by extent in
                           data/raw/_national/wbd/
  sources / bathymetry     the coverage tests of sources.py
"""
import hashlib, json, math, os
import geopandas as gpd, shapely
from shapely.geometry import box as sbox
import netfetch, sources

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIONAL = f"{ROOT}/data/raw/_national"
STATES_ZIP = f"{NATIONAL}/tl_2024_us_state.zip"
STATES_URL = "https://www2.census.gov/geo/tiger/TIGER2024/STATE/tl_2024_us_state.zip"
WBD = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/2/query"     # layer 2: 4-digit HU
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
EQUAL_AREA = 5070            # NAD83 / Conus Albers, for areas
MIN_STATE_KM2 = 0.1          # a state the outline only touches along its line doesn't count
MAX_BOX_KM2 = 3800           # the largest box built so far (n_georgia's blue_ridge, about 3,800 km2)
LOWER_48 = (-125.0, 24.0, -66.5, 49.5)


def outline_ll(entry):
    """The area's outline as one lon/lat (EPSG:4326) polygon."""
    if "ranges" in entry and "crs" in entry:
        g = gpd.GeoSeries([sbox(*r["bbox"]).segmentize(1000) for r in entry["ranges"].values()], crs=entry["crs"])
        return shapely.make_valid(g.to_crs(4326).union_all())
    o = entry.get("outline")
    if o is None:
        raise SystemExit("no outline: give the area an outline (lon/lat rectangle or a polygon file), or ranges and crs")
    if isinstance(o, (tuple, list)) and len(o) == 4:
        w, s, e, n = map(float, o)
        if not (w < e and s < n):
            raise SystemExit(f"outline {o}: not (west, south, east, north) in degrees")
        geom = sbox(w, s, e, n)
    else:
        path = o if os.path.isabs(o) else os.path.join(ROOT, o)
        geom = shapely.make_valid(gpd.read_file(path).to_crs(4326).union_all())
    lw, ls, le, ln = LOWER_48
    if not geom.within(sbox(lw, ls, le, ln)):
        raise SystemExit("the outline reaches outside the lower 48: Alaska and Hawaii need their own elevation, flow "
                         "and climate sources (not built yet)")
    return geom


def utm_epsg(outline):
    """The NAD83 / UTM zone that holds most of the outline (EPSG 26901-26923)."""
    w, s, e, n = outline.bounds
    best, zone = -1.0, None
    for z in range(int((w + 180) // 6) + 1, int((e + 180) // 6) + 2):
        strip = sbox(-180 + 6 * (z - 1), -90, -180 + 6 * z, 90)
        part = outline.intersection(strip)
        if part.is_empty:
            continue
        a = gpd.GeoSeries([part], crs=4326).to_crs(EQUAL_AREA).area.iloc[0]
        if a > best:
            best, zone = a, z
    return 26900 + zone


def one_box(outline, epsg):
    """One box (xmin, ymin, xmax, ymax) in the zone's metres around the outline, outward to the km."""
    g = gpd.GeoSeries([outline.segmentize(0.01)], crs=4326).to_crs(epsg)
    x0, y0, x1, y1 = g.total_bounds
    b = (math.floor(x0 / 1000) * 1000, math.floor(y0 / 1000) * 1000, math.ceil(x1 / 1000) * 1000, math.ceil(y1 / 1000) * 1000)
    km2 = (b[2] - b[0]) * (b[3] - b[1]) / 1e6
    if km2 > MAX_BOX_KM2:
        raise SystemExit(f"the outline needs a box of {km2:,.0f} km2, more than one box holds ({MAX_BOX_KM2:,} km2): "
                         f"split it into ranges, or wait for the layout step (B8)")
    return tuple(int(v) for v in b)


def _state_outlines():
    if not os.path.exists(STATES_ZIP):
        os.makedirs(NATIONAL, exist_ok=True)
        r = netfetch.fetch("GET", STATES_URL, timeout=600, headers=UA)
        with open(STATES_ZIP + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(STATES_ZIP + ".tmp", STATES_ZIP)
    return gpd.read_file(f"zip://{STATES_ZIP}", columns=["STUSPS"]).to_crs(EQUAL_AREA)


_STATES = None


def states(outline, clip_state=None):
    """(state codes in descending order of the outline's area in them, {code: km2}); for an area that stops at a
    state line, clip_state's: one code or several (southeastern Pennsylvania keeps PA, DE and MD), as areaclip.py
    reads it."""
    global _STATES
    if clip_state:
        return ((clip_state,) if isinstance(clip_state, str) else tuple(clip_state)), {}
    if _STATES is None:
        _STATES = _state_outlines()
    o = gpd.GeoSeries([outline.segmentize(0.01)], crs=4326).to_crs(EQUAL_AREA).iloc[0]
    hit = _STATES[_STATES.intersects(o)]
    km2 = {r.STUSPS: shapely.intersection(r.geometry, o).area / 1e6 for r in hit.itertuples()}
    km2 = {k: round(v, 1) for k, v in sorted(km2.items(), key=lambda kv: -kv[1]) if v >= MIN_STATE_KM2}
    return tuple(km2), km2


def _bounds_ll(bbox, epsg):
    """A box's lon/lat bounds as 02_download_vectors.py takes them (edges cut every km before reprojecting)."""
    return tuple(gpd.GeoSeries([sbox(*bbox).segmentize(1000)], crs=epsg).to_crs(4326).total_bounds)


def hu4(bbox, epsg):
    """The 4-digit hydrologic units whose WBD outlines meet the box, sorted. The box goes to the service as a polygon
    (its edges cut every km, in lon/lat), not as its lon/lat bounds: a unit that only meets the corners those bounds
    add holds nothing 02_download_vectors.py keeps."""
    ring = gpd.GeoSeries([sbox(*bbox).segmentize(1000)], crs=epsg).to_crs(4326).iloc[0].exterior.coords
    ring = [[round(x, 5), round(y, 5)] for x, y in ring]
    key = hashlib.sha1(json.dumps(["hu4 polygon", ring]).encode()).hexdigest()[:16]
    path = f"{NATIONAL}/wbd/hu4_{key}.json"
    if os.path.exists(path):
        with open(path) as f:
            return tuple(json.load(f)["hu4"])
    w, s, e, n = (round(v, 4) for v in _bounds_ll(bbox, epsg))
    r = netfetch.fetch("POST", WBD, timeout=60, headers=UA, ok=lambda r: r.ok and "features" in r.json(),
                       data=dict(geometry=json.dumps({"rings": [ring], "spatialReference": {"wkid": 4326}}),
                                 geometryType="esriGeometryPolygon", inSR=4326, spatialRel="esriSpatialRelIntersects",
                                 outFields="huc4", returnGeometry="false", f="json"))
    codes = sorted({f["attributes"]["huc4"] for f in r.json()["features"]})
    if not codes:
        raise SystemExit(f"WBD has no 4-digit unit at {w},{s},{e},{n}: is the box in the lower 48?")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(dict(bounds=[w, s, e, n], hu4=codes, source=WBD), f)
    os.replace(path + ".tmp", path)
    return tuple(codes)


def _boxes_hit(outline):
    return lambda boxes: any(outline.intersects(sbox(*b)) for b in boxes)


def area_sources(outline, st):
    return sources.covering(sources.SOURCES, st, _boxes_hit(outline))


def bathymetry(outline, st):
    return sources.covering(sources.BATHYMETRY, st, _boxes_hit(outline))


def settings(area, entry, need_hu4=True):
    """Everything worked out for one area: the dict 00_area.py writes to area.json."""
    o = outline_ll(entry)
    epsg = utm_epsg(o)
    crs = entry.get("crs", epsg)            # the boxes below are in the zone the area is built in
    if "ranges" in entry:
        ranges = {k: dict(label=r["label"], bbox=tuple(r["bbox"])) for k, r in entry["ranges"].items()}
    else:
        ranges = {area: dict(label=entry["label"], bbox=one_box(o, crs))}
    if need_hu4:
        for r in ranges.values():
            r["hu4"] = hu4(r["bbox"], crs)
    st, km2 = states(o, entry.get("clip_state"))
    w, s, e, n = o.bounds
    # crs: the zone the ranges' boxes are in (config's, where it gives one); crs_derived: the zone holding most of
    # the outline, which a new area is built in
    return dict(area=area, crs=crs, crs_derived=epsg, outline_ll=[round(v, 5) for v in (w, s, e, n)], ranges=ranges,
                states=st, states_km2=km2, sources=area_sources(o, st), bathymetry=bathymetry(o, st))
