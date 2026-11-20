"""Late-summer greenness for every range box of an area: Sentinel-2 NDVI, one raster per box and summer.

What it's for: the flow model rates many LA creeks "year-round" that USGS gauges show dry most summers (2026-11-20:
31 of the 53 gauged LA creeks dry most summers; almost all where the model's typical summer low is 0.1-0.45 cfs). In
that range nothing in the catchment tells the wet creeks from the dry ones, but the channel does: in late summer every
gauged creek there that flows has a green strip of riparian trees and shrubs (75th-90th percentile NDVI 0.67-0.86),
and the driest are bare. 05b_flow.py reads these rasters for each reach; scoring.py lowers a creek only where the
channel is bare and the other evidence agrees.

For each box and summer (GREEN_YEARS), every Sentinel-2 tile over the box: its scenes between Aug 15 and Sep 30 with
under 10 % cloud, best coverage then least cloud first, up to four per tile, each filling what the ones before left
empty. NDVI x 10000 as int16 on the tile grid (10 m, the CRS of the tile covering most of the box), with clouds, cloud
shadow, snow (scene classes 3, 8, 9, 10, 11) and no-data at -32768; open water (class 6) is kept (NDVI < 0 there).
Written to data/raw/<area>/<range>/late_summer_ndvi_<year>.tif, with the scenes used in a .json beside it.
Only for areas with the late_summer_green source (config.py); elsewhere it says so and stops. Kept once made
(delete a file to fetch it again). From Earth Search (Element 84's STAC API over the AWS open-data copy of Sentinel-2
L2A): no key, nothing sent but the box and dates. LA's eight boxes take about 15 minutes and 0.7 GB.
Run: AREA=<area> ../.venv/bin/python 02g_greenness.py [range ...]
"""
import os, sys, time, json, numpy as np, requests, rasterio, rasterio.warp, shapely
from rasterio.windows import Window
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from config import AREA, REGIONS, CRS, raw_dir, has
from flowlib import GREEN_YEARS, green_path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
STAC = "https://earth-search.aws.element84.com/v1/search"
NODATA = -32768


def search(bbox_ll, year):
    body = {"collections": ["sentinel-2-l2a"], "bbox": list(bbox_ll), "limit": 200,
            "datetime": f"{year}-08-15T00:00:00Z/{year}-09-30T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 10}}}
    for k in range(5):
        try:
            r = requests.post(STAC, json=body, timeout=90)
            r.raise_for_status()
            return r.json()["features"]
        except Exception:
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"Earth Search: no answer for {bbox_ll} {year}")


_OFF = {}


def offset(f):
    """The +1000 that processing baseline 04.00 and later adds to every value, where the scene still has it.
    Earth Search's earthsearch:boa_offset_applied flag is wrong on some scenes (S2B_11SLU_20220930 says False, yet its
    red values go down to 234; 16 of the scenes over LA and Jackson, found 2026-11-20), so it's read from the data:
    with the offset in, no valid red value is under 1000 (that would be negative reflectance); without it, dark
    vegetation, shadow and water read 0-600. The 0.5th percentile of the scene's red band (a 1/16 overview) under 900
    means the offset is already out. A scene with no dark pixel at all would read as offset-in, which only makes its
    channels greener: the safe way to be wrong here."""
    if f["id"] in _OFF:
        return _OFF[f["id"]]
    off = 0
    if float(f["properties"].get("s2:processing_baseline", "0") or 0) >= 4.0:
        with rasterio.open(f["assets"]["red"]["href"]) as s:
            a = s.read(1, out_shape=(max(1, s.height // 16), max(1, s.width // 16)))
        a = a[a > 0]
        off = 1000 if (len(a) and np.percentile(a, 0.5) >= 900) else 0
    _OFF[f["id"]] = off
    return off


def box_year(name, bounds, year):
    out = green_path(name, year)
    if os.path.exists(out):
        return out, "kept"
    ll = rasterio.warp.transform_bounds(CRS, "EPSG:4326", *bounds)
    by_tile = {}
    for f in search(ll, year):
        by_tile.setdefault(f["properties"].get("s2:mgrs_tile") or f["id"].split("_")[1], []).append(f)
    if not by_tile:
        return None, "no scenes"
    key = lambda f: (round(float(f["properties"].get("s2:nodata_pixel_percentage", 0) or 0) / 5),
                     f["properties"]["eo:cloud_cover"])
    ranked = {t: sorted(v, key=key)[:4] for t, v in by_tile.items()}
    best = {t: v[0] for t, v in ranked.items()}
    box_ll = shapely.box(*ll)
    main = max(best.values(), key=lambda f: shapely.box(*f["bbox"]).intersection(box_ll).area)
    main_tile = next(t for t, f in best.items() if f is main)
    with rasterio.open(main["assets"]["red"]["href"]) as src:
        ocrs = src.crs
    b = rasterio.warp.transform_bounds(CRS, ocrs, *bounds)
    x0, y1 = np.floor(b[0] / 10) * 10, np.ceil(b[3] / 10) * 10
    W, H = int(np.ceil((b[2] - x0) / 10)), int(np.ceil((y1 - b[1]) / 10))
    otr = from_origin(x0, y1, 10, 10)
    prof = dict(driver="GTiff", width=W, height=H, count=1, dtype="int16", crs=ocrs, transform=otr, nodata=NODATA,
                tiled=True, blockxsize=512, blockysize=512, compress="deflate", predictor=2)
    used = []
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with rasterio.open(out + ".tmp.tif", "w+", **prof) as dst:
        # the main tile's best scene first, then the other tiles' best, then each tile's next scenes; each only where
        # the output is still empty (a tile in another UTM zone is warped onto the grid, nearest neighbour)
        order = [f for k in range(4) for t in sorted(ranked, key=lambda t: t != main_tile) for f in ranked[t][k:k + 1]]
        for f in order:
            fb = rasterio.warp.transform_bounds("EPSG:4326", ocrs, *f["bbox"])
            if fb[2] <= x0 or fb[0] >= x0 + W * 10 or fb[3] <= y1 - H * 10 or fb[1] >= y1:
                continue
            off = offset(f)
            srcs = [rasterio.open(f["assets"][k]["href"]) for k in ("red", "nir", "scl")]
            vrts = [WarpedVRT(x, crs=ocrs, transform=otr, width=W, height=H, resampling=Resampling.nearest,
                              src_nodata=0, nodata=0) for x in srcs]
            ra, rb = max(0, int((y1 - fb[3]) / 10) - 2), min(H, int((y1 - fb[1]) / 10) + 2)
            ca, cb = max(0, int((fb[0] - x0) / 10) - 2), min(W, int((fb[2] - x0) / 10) + 2)
            for k in range(ra, rb, 1024):
                w = Window(ca, k, cb - ca, min(1024, rb - k))
                cur = dst.read(1, window=w)
                if not (cur == NODATA).any():
                    continue
                red, nir, scl = (v.read(1, window=w) for v in vrts)
                red, nir = red.astype("float32"), nir.astype("float32")
                bad = (red == 0) | (nir == 0) | np.isin(scl, [0, 1, 3, 8, 9, 10, 11])
                red, nir = np.clip(red - off, 1, None), np.clip(nir - off, 1, None)
                v_ = np.round((nir - red) / (nir + red) * 10000).astype("int16")
                v_[bad] = NODATA
                dst.write(np.where(cur != NODATA, cur, v_), 1, window=w)
            for x in vrts + srcs:
                x.close()
            used.append(f"{f['id']} ({f['properties']['eo:cloud_cover']:.1f}% cloud)")
    os.replace(out + ".tmp.tif", out)
    json.dump(used, open(out + ".json", "w"))
    return out, "; ".join(used)


if not has("late_summer_green"):
    sys.exit(print(f"{AREA}: no late_summer_green source in config.py (only where summer drought browns the slopes); "
                   f"nothing to do") or 0)
for name in sys.argv[1:] or list(REGIONS):
    for y in GREEN_YEARS:
        t0 = time.time()
        p, info = box_year(name, REGIONS[name]["bbox"], y)
        print(f"{AREA}/{name} {y}: {info} [{time.time() - t0:.0f} s]", flush=True)
