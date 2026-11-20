"""Shared helpers for the map layer downloads (02e_access.py; 02d_trails.py has its own copies): Overpass and ArcGIS
queries, a relief test, and matching OSM lines to official lines."""
import os, re, time, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from scipy.ndimage import maximum_filter, minimum_filter
from config import EPSG, raw_dir

UA = {"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"}


def overpass(q):
    for attempt in range(14):  # public Overpass servers 502/429 under load (and allow about two queries at once
        # per address, so several ranges running side by side queue up); retry for ~25 min and alternate mirrors
        url = ("https://overpass.openstreetmap.fr/api/interpreter", "https://overpass-api.de/api/interpreter")[attempt % 2]   # (the kumi mirror stopped answering in Nov 2026)
        try:
            # 20 s to connect (a dead mirror), and the query's own time limit plus a minute to answer
            wait = int(m.group(1)) + 60 if (m := re.search(r"\[timeout:(\d+)\]", q)) else 900
            r = requests.post(url, data={"data": q}, timeout=(20, wait), headers=UA)
            if r.ok and "elements" in r.json():
                return r.json()["elements"]
        except (requests.RequestException, ValueError):
            pass
        time.sleep(min(30 * (attempt + 1), 120))
    raise RuntimeError("Overpass failed")


def esri(url, bbox, fields, where="1=1"):
    """All features of an ArcGIS layer in a lon/lat box (EPSG:4326 out), paging through the server's record limit."""
    feats, off = [], 0
    while True:
        js = {}
        for attempt in range(4):
            try:
                r = requests.get(f"{url}/query", headers=UA, timeout=300, params=dict(
                    where=where, geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope", inSR=4326,
                    spatialRel="esriSpatialRelIntersects", outFields=fields, outSR=4326, f="geojson",
                    resultOffset=off, resultRecordCount=1000))
                js = r.json()
                if "features" in js:
                    break
            except (requests.RequestException, ValueError):
                js = {}
            time.sleep(10 * (attempt + 1))
        if "features" not in js:    # a server that is down is not a layer with nothing in the box: stop, don't return less
            raise RuntimeError(f"{url}: no usable answer after 4 tries ({str(js)[:200]})")
        batch = js["features"]
        feats += [f for f in batch if f.get("geometry")]
        if len(batch) < 1000 and not js.get("properties", {}).get("exceededTransferLimit"):
            break
        off += len(batch)
    return gpd.GeoDataFrame.from_features(feats, crs=4326) if feats else gpd.GeoDataFrame(geometry=[], crs=4326)


def wilderness_path():
    """The Forest Service's wilderness areas over all study areas (data/raw/<area>/_shared/wilderness.gpkg, the area's UTM CRS),
    downloaded when missing or when the study areas have outgrown the box it was downloaded for. Shared by
    02d_trails.py, 02e_access.py, 08_hike.py and 11_context.py, so whichever runs first fetches it.
    In the Adirondacks (source nys_forest_preserve) the state's Forest Preserve units classed Wilderness, Primitive or
    Canoe Area are added (NYSDEC's lands layer): the State Land Master Plan keeps bicycles out of them as out of a
    federal wilderness, which is what the layer stands for in these scripts."""
    import json
    from config import REGIONS, CRS, SHARED, has
    path = f"{SHARED}/wilderness.gpkg"
    b = np.array([v["bbox"] for v in REGIONS.values()])
    env = gpd.GeoSeries([shapely.box(b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max())],
                        crs=CRS).to_crs(4326).total_bounds
    ext_path = path + ".extent.json"   # the box it was downloaded for
    ext = json.load(open(ext_path)) if os.path.exists(ext_path) else None
    if not os.path.exists(path) or ext is None or not (ext[0] <= env[0] and ext[1] <= env[1] and ext[2] >= env[2]
                                                      and ext[3] >= env[3]):
        js = requests.get("https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_Wilderness_01/MapServer/0/query",
                          headers=UA, timeout=300, params=dict(
                              where="1=1", geometry=",".join(map(str, env)), geometryType="esriGeometryEnvelope",
                              inSR=4326, outSR=EPSG, outFields="WILDERNESSNAME", f="geojson")).json()
        w = gpd.GeoDataFrame.from_features(js["features"], crs=CRS)
        if has("nys_forest_preserve"):
            ny = esri("https://services6.arcgis.com/DZHaqZm9cxOD4CWM/ArcGIS/rest/services/NYS_DEC_Lands/FeatureServer/0",
                      env, "FACILITY,CLASS", where="CLASS IN ('WILDERNESS','PRIMITIVE','CANOE AREA')")
            if len(ny):
                ny = ny.to_crs(CRS)
                ny["geometry"] = shapely.make_valid(ny.geometry.values)
                ny = ny.dissolve(by="FACILITY", as_index=False)
                ny = gpd.GeoDataFrame(dict(WILDERNESSNAME=ny.FACILITY.str.replace("Primtive", "Primitive")),
                                      geometry=ny.geometry.values, crs=CRS)
                w = gpd.GeoDataFrame(pd.concat([w, ny], ignore_index=True), crs=CRS)
        w.to_file(path + ".tmp.gpkg", driver="GPKG")
        os.replace(path + ".tmp.gpkg", path)
        json.dump([float(v) for v in env], open(ext_path, "w"))
    return path


def relief_at(points_utm, regions, root, radius_cells=10, block=5):
    """Relief (max - min elevation) within ~1 km of each point, from 50 m blocks of every region's DEM; NaN outside."""
    out = np.full(len(points_utm), np.nan)
    x, y = points_utm.x.values, points_utm.y.values
    for key in regions:
        p = f"{raw_dir(key)}/dem_10m.tif"
        if not os.path.exists(p):
            continue
        with rasterio.open(p) as src:
            z, T = src.read(1).astype("float32"), src.transform
        z[z < -100] = np.nan
        h, w = z.shape[0] // block * block, z.shape[1] // block * block
        blk = z[:h, :w].reshape(h // block, block, w // block, block)
        hi = maximum_filter(np.nan_to_num(np.nanmax(blk, axis=(1, 3)), nan=-1e4), size=2 * radius_cells + 1)
        lo = minimum_filter(np.nan_to_num(np.nanmin(blk, axis=(1, 3)), nan=1e4), size=2 * radius_cells + 1)
        rel = hi - lo
        cols, rows = ~T * (x, y)
        rows, cols = (rows // block).astype(int), (cols // block).astype(int)
        inside = (rows >= 0) & (rows < rel.shape[0]) & (cols >= 0) & (cols < rel.shape[1]) & np.isnan(out)
        out[inside] = rel[rows[inside], cols[inside]]
    return out


def follow(lines, ref, match_m=25, share_min=0.6, step=25):
    """For each line (projected), the index of the ref line it mostly follows (within match_m over share_min of its
    length), else -1. Uses points every `step` m along each line."""
    if not len(ref) or not len(lines):
        return np.full(len(lines), -1)
    tree = shapely.STRtree(ref.geometry.values)
    pts, owner = [], []
    for i, ln in enumerate(lines.geometry.values):
        n = max(2, int(ln.length // step) + 1)
        pts.append(shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n)))
        owner.append(np.full(n, i))
    pts, owner = np.concatenate(pts), np.concatenate(owner)
    hit_pt, hit_ref = tree.query_nearest(pts, max_distance=match_m, all_matches=False)
    share = np.bincount(owner[hit_pt], minlength=len(lines)) / np.bincount(owner, minlength=len(lines))
    best = np.full(len(lines), -1)
    if len(hit_pt):
        pairs = pd.DataFrame({"line": owner[hit_pt], "ref": hit_ref})
        top = pairs.groupby(["line", "ref"]).size().reset_index().sort_values(0).drop_duplicates("line", keep="last")
        best[top.line.values] = top.ref.values
    best[share < share_min] = -1
    return best
