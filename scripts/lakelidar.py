"""1 m lidar (USGS 3DEP) around lakes: the newest survey's bare-earth DEM, read in place from USGS's cloud-optimized
tiles, and the water level and shoreline it shows.

Lidar DEMs are hydro-flattened: inside the breakline a survey draws around a lake (required from 2 acres, by the USGS
lidar base specification) the water is set to one elevation. So the cells at exactly that elevation are the lake as it
was on the survey date, to the metre: a newer and sharper shoreline than NHD's, and a measured water level.

catalog(bounds, cache)          1 m DEM tiles over a lon/lat box (TNM Access API) and each survey's work units with
                                flight dates and quality level (3DEP index); cached 30 days
window(geom, crs, cat, pad, path)  the newest survey that fully covers a lake and a margin of `pad` m around it:
                                (array, transform, work unit); cached as a GeoTIFF at `path`
water(a, T, lake, others)       the water level, the share of the lake's outline at it, the flattened shoreline and
                                whether it runs off the window
Checked on 2026-11-19: Bradley Lake reads one level (2,139.500 m) on 99% of its NHD outline, Holly Lake 97%. The
USGS seamless elevation service serves the 2014 Grand Teton survey there, not the 2022-23 one, so the tiles are read
directly.
"""
import os, json, time, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from rasterio import features
from rasterio.merge import merge
from rasterio.enums import Resampling
from scipy import ndimage
from shapely.geometry import box, shape

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "4")
TNM = "https://tnmaccess.nationalmap.gov/api/v1/products"
WU = "https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer/24/query"
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
FLAT_TOL = 0.005      # m: a hydro-flattened surface is one value; this only absorbs float rounding
MIN_PART_M2 = 25      # flattened specks and pinholes smaller than this are dropped (a few lidar cells)
MIN_STEP_M2 = 200     # a flat patch at another level this big (1 m cells), mostly inside the outline, is the same lake
NODATA = -9999.0


def _get(url, **params):
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=180)
            if r.ok:
                return r.json()
        except (requests.RequestException, ValueError):
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"no answer from {url}")


class Catalog:
    def __init__(self, tiles, units):
        self.tiles, self.units = tiles, units


def catalog(bounds_ll, cache):
    """The 1 m DEM tiles and lidar work units over a lon/lat box."""
    p = f"{cache}/lidar_catalog.json"
    if os.path.exists(p) and os.environ.get("REFRESH") != "1" and time.time() - os.path.getmtime(p) < 30 * 86400:
        js = json.load(open(p))
    else:
        w, s, e, n = bounds_ll
        items, off = [], 0
        while True:
            d = _get(TNM, datasets="Digital Elevation Model (DEM) 1 meter", bbox=f"{w},{s},{e},{n}", max=500,
                     offset=off, outputFormat="JSON")
            items += d.get("items", [])
            off += 500
            if off >= d.get("total", 0):
                break
        wu = _get(WU, where="1=1", geometryType="esriGeometryEnvelope", spatialRel="esriSpatialRelIntersects",
                  geometry=json.dumps(dict(xmin=w, ymin=s, xmax=e, ymax=n, spatialReference={"wkid": 4326})),
                  outFields="workunit,project,collect_start,collect_end,ql", returnGeometry="true", outSR=4326,
                  maxAllowableOffset=0.0005, f="geojson")
        js = dict(tiles=[dict(title=x["title"], url=x["downloadURL"], bbox=x["boundingBox"], pub=x.get("publicationDate"))
                         for x in items if x.get("downloadURL", "").endswith(".tif")],
                  units=wu)
        with open(p + ".tmp", "w") as f:
            json.dump(js, f)
        os.replace(p + ".tmp", p)
    t = pd.DataFrame(js["tiles"])
    t["project"] = t.url.str.extract(r"/1m/Projects/([^/]+)/")[0]
    tiles = gpd.GeoDataFrame(t, geometry=[box(b["minX"], b["minY"], b["maxX"], b["maxY"]) for b in t.bbox], crs=4326)
    u = gpd.GeoDataFrame.from_features(js["units"]["features"], crs=4326)
    u["start"] = pd.to_datetime(u.collect_start, unit="ms").dt.date.astype(str)
    u["end"] = pd.to_datetime(u.collect_end, unit="ms").dt.date.astype(str)
    # a tile's project is named after either the work unit or the project (WY_GrandTetonElkRefuge_2014 is a work unit
    # of WY_Grand_Teton_and_National_Elk_Refuge_LiDAR_15; WY_GrandTetonNP_D22 a project)
    have = set(tiles["project"])                   # (u.project would be GeoDataFrame.project, a method)
    u["tiles_as"] = [wk if wk in have else pr for wk, pr in zip(u["workunit"], u["project"])]
    return Catalog(tiles, u.sort_values("collect_end", ascending=False).reset_index(drop=True))


def window(geom, crs, cat, pad, path=None):
    """(array, transform, work unit row) from the newest survey whose tiles fully cover geom.buffer(pad), or None."""
    g = geom.buffer(pad)
    x0, y0, x1, y1 = np.floor(g.bounds[0]), np.floor(g.bounds[1]), np.ceil(g.bounds[2]), np.ceil(g.bounds[3])
    gl = gpd.GeoSeries([box(x0, y0, x1, y1)], crs=crs).to_crs(4326).iloc[0]
    if path and os.path.exists(path):
        with rasterio.open(path) as s:
            wk = s.tags().get("workunit")
            hit = cat.units[cat.units.workunit == wk]
            return s.read(1), s.transform, (hit.iloc[0] if len(hit) else None)
    inside = geom.representative_point()
    pl = gpd.GeoSeries([inside], crs=crs).to_crs(4326).iloc[0]
    for _, u in cat.units[cat.units.intersects(pl)].iterrows():        # newest first
        t = cat.tiles[(cat.tiles["project"] == u["tiles_as"]) & cat.tiles.intersects(gl)]
        if not len(t) or not shapely.union_all(t.geometry.values).buffer(1e-6).contains(gl):
            continue
        srcs = [rasterio.open("/vsicurl/" + url) for url in t.url]
        try:
            # Tiles come in their survey's UTM zone (zone 19 for the Massachusetts surveys along NE Connecticut's
            # edge, where the area's maps are in zone 18). Tiles of one zone are merged in it and the window is
            # reprojected to the area's 1 m grid by nearest neighbour, which keeps flattened water at one value.
            by = {}
            for s in srcs:
                by.setdefault(s.crs.to_string(), []).append(s)
            dst_crs = rasterio.crs.CRS.from_user_input(crs)
            same = [v for k, v in by.items() if rasterio.crs.CRS.from_string(k) == dst_crs]
            if same:
                a, T = merge(same[0], bounds=(x0, y0, x1, y1), res=1.0, nodata=NODATA, resampling=Resampling.nearest)
                a = a[0].astype(np.float32)
                a[a < -1000] = NODATA                  # the tiles' own nodata is -999999
            else:
                from rasterio.warp import reproject
                from rasterio.transform import from_origin
                zone = max(by.values(), key=len)       # the zone with the most tiles here
                bs = gpd.GeoSeries([box(x0, y0, x1, y1)], crs=crs).to_crs(zone[0].crs).buffer(5).total_bounds
                a_s, T_s = merge(zone, bounds=tuple(bs), res=1.0, nodata=NODATA, resampling=Resampling.nearest)
                a_s = a_s[0].astype(np.float32)
                a_s[a_s < -1000] = NODATA
                T = from_origin(x0, y1, 1.0, 1.0)
                a = np.full((int(y1 - y0), int(x1 - x0)), NODATA, np.float32)
                reproject(a_s, a, src_transform=T_s, src_crs=zone[0].crs, dst_transform=T, dst_crs=dst_crs,
                          resampling=Resampling.nearest, src_nodata=NODATA, dst_nodata=NODATA)
        finally:
            for s in srcs:
                s.close()
        m = features.geometry_mask([geom], out_shape=a.shape, transform=T, invert=True)
        if m.any() and (a[m] == NODATA).mean() > 0.02:  # a gap in this survey: try the next one
            continue
        if path:
            prof = dict(driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype="float32", crs=crs,
                        transform=T, nodata=NODATA, compress="deflate", predictor=3, tiled=True)
            with rasterio.open(path + ".tmp.tif", "w", **prof) as d:
                d.write(a, 1)
                d.update_tags(workunit=u.workunit)
            os.replace(path + ".tmp.tif", path)
        return a, T, u
    return None


def _clean(poly):
    """Drop specks and pinholes under MIN_PART_M2, and the stair-steps of the 1 m grid."""
    parts = []
    for p in getattr(poly, "geoms", [poly]):
        if p.geom_type != "Polygon" or p.area < MIN_PART_M2:
            continue
        parts.append(shapely.Polygon(p.exterior, [h for h in p.interiors if shapely.Polygon(h).area >= MIN_PART_M2]))
    if not parts:
        return None
    out = shapely.make_valid(shapely.simplify(shapely.MultiPolygon(parts), 0.7, preserve_topology=True))
    out = shapely.MultiPolygon([q for q in getattr(out, "geoms", [out]) if q.geom_type == "Polygon" and q.area >= MIN_PART_M2])
    return out if not out.is_empty else None


def water(a, T, lake, others=()):
    """(level, share, shoreline polygon or None, runs off the window, other levels) from a hydro-flattened DEM window.
    Other levels: [(level, m2)] of the flat patches at other levels taken into the shoreline (see below)."""
    valid = a != NODATA
    core = lake.buffer(-3)
    core = core if not core.is_empty and core.area >= 0.3 * lake.area else lake
    inner = features.geometry_mask([core], out_shape=a.shape, transform=T, invert=True)
    v = a[inner & valid]
    if len(v) < 20:
        return np.nan, np.nan, None, False, []
    vals, cnt = np.unique(np.round(v, 3), return_counts=True)
    level, share = float(vals[np.argmax(cnt)]), float(cnt.max() / len(v))
    if share < 0.5:
        # Not flattened inside the outline. A small pond's mapped outline can sit off its water: look 30 m around it
        # for a flattened surface (200 m2 or more at one value) that overlaps the outline by 30% of the smaller one
        zone = features.geometry_mask([lake.buffer(30)], out_shape=a.shape, transform=T, invert=True)
        zv, zc = np.unique(np.round(a[zone & valid], 3), return_counts=True)
        if not len(zc) or zc.max() < 200:
            return np.nan, share, None, False, []
        lev2 = float(zv[np.argmax(zc)])
        flat2 = valid & (np.abs(a - lev2) <= FLAT_TOL)
        lab2, _ = ndimage.label(flat2, structure=np.ones((3, 3), bool))
        # flattened water is one patch of 200 m2 or more; a level surface the survey didn't flatten has its commonest
        # value in scattered cells (a 2.7 ha Adirondack pond's specks made a 0.08 ha "shoreline")
        ids2 = np.unique(lab2[zone & flat2])
        ids2 = ids2[ids2 > 0]
        ids2 = ids2[np.bincount(lab2.ravel())[ids2] >= MIN_STEP_M2]
        reg2 = np.isin(lab2, ids2)
        me = features.geometry_mask([lake], out_shape=a.shape, transform=T, invert=True)
        ov = int((reg2 & me).sum())
        if ov < 0.3 * min(me.sum(), reg2.sum()) or reg2.sum() < 0.3 * me.sum():
            return np.nan, share, None, False, []  # no flattened water here: no measured level or shoreline
        level, share, inner = lev2, ov / max(int(me.sum()), 1), zone
    flat = valid & (np.abs(a - level) <= FLAT_TOL)
    lab, _ = ndimage.label(flat, structure=np.ones((3, 3), bool))
    ids = np.unique(lab[inner & flat])
    reg = np.isin(lab, ids[ids > 0])
    # A lake flown on more than one day, or flattened in steps as a river is, lies flat at more than one level: Tugaloo
    # Lake at 271.20 and 269.96 m, Seed Lake at 533.33 and 533.53 m, Toccoa Reservoir at 372.80 and 376.23 m (a straight
    # edge across the water). With only the commonest level, half of each was left out. Flat patches at the other levels
    # (200 m2 or more, at least half inside the outline) are the same water
    me = features.geometry_mask([lake], out_shape=a.shape, transform=T, invert=True)
    steps, seen = [], [level]
    rest = a[me & valid & ~reg]
    if len(rest):
        lv_, c_ = np.unique(np.round(rest, 3), return_counts=True)
        for k in np.argsort(-c_)[:20]:
            if c_[k] < MIN_STEP_M2:
                break
            lv = float(lv_[k])
            if any(abs(lv - x) <= FLAT_TOL for x in seen):
                continue
            seen.append(lv)
            f2 = valid & (np.abs(a - lv) <= FLAT_TOL) & ~reg
            l2, n2 = ndimage.label(f2, structure=np.ones((3, 3), bool))
            if not n2:
                continue
            size = np.bincount(l2.ravel(), minlength=n2 + 1)
            inside = np.bincount(l2[me].ravel(), minlength=n2 + 1)
            take = np.flatnonzero((size >= MIN_STEP_M2) & (inside >= 0.5 * size))
            take = take[take > 0]
            if len(take):
                add = np.isin(l2, take)
                reg |= add
                steps.append((round(lv, 2), int(add.sum())))
    if steps:   # where two levels meet along a tile's edge, a seam a cell or two wide (Unicoi Lake) is water too; a
        # causeway between two pools (Toccoa Reservoir's, 13 m) is not
        reg |= ndimage.binary_closing(reg, structure=np.ones((3, 3), bool)) & me
    if len(others):   # another mapped lake joined to this one at the same level (String and Leigh): nearer outline
        ot = features.geometry_mask(list(others), out_shape=a.shape, transform=T, invert=True)
        if ot.any() and (reg & ot).any():
            reg &= ndimage.distance_transform_edt(~me) <= ndimage.distance_transform_edt(~ot)
    edge = bool(reg[0].any() or reg[-1].any() or reg[:, 0].any() or reg[:, -1].any())
    polys = [shape(s) for s, val in features.shapes(reg.astype(np.uint8), mask=reg, transform=T, connectivity=8) if val == 1]
    return level, share, (_clean(shapely.union_all(polys)) if polys else None), edge, steps


def surface_stats(a, T, lake):
    """(median, share within 15 cm of it, interquartile range) of the DEM 3 m in from a lake's outline: how level the
    surface is where the survey didn't flatten it; and the median along the outline itself, its shore."""
    core = lake.buffer(-3)
    core = core if not core.is_empty and core.area >= 0.3 * lake.area else lake
    m = features.geometry_mask([core], out_shape=a.shape, transform=T, invert=True) & (a != NODATA)
    v = a[m]
    s = a[features.geometry_mask([lake.boundary.buffer(1.5)], out_shape=a.shape, transform=T, invert=True) & (a != NODATA)]
    shore = float(np.median(s)) if len(s) >= 20 else np.nan
    if len(v) < 20:
        return np.nan, np.nan, np.nan, shore
    med = float(np.median(v))
    return med, float(np.mean(np.abs(v - med) <= 0.15)), float(np.subtract(*np.percentile(v, [75, 25]))), shore
