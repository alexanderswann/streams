"""Download a 10 m USGS 3DEP DEM for the study area, tiled, and mosaic it."""
import os, time, requests, numpy as np, rasterio
from rasterio.merge import merge
from config import *

URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
os.makedirs(f"{RAW}/dem_tiles", exist_ok=True)
step = TILE * RES
paths = []
for x0 in range(XMIN, XMAX, step):
    for y0 in range(YMIN, YMAX, step):
        x1, y1 = min(x0 + step, XMAX), min(y0 + step, YMAX)
        w, h = (x1 - x0) // RES, (y1 - y0) // RES
        p = f"{RAW}/dem_tiles/dem_{x0}_{y0}.tif"
        paths.append(p)
        if os.path.exists(p):
            # A tile on the box's top or right edge was cut there, and keeps its full-size name. When the box grows,
            # that short tile would be reused and leave a strip with no terrain, so it is fetched again.
            with rasterio.open(p) as t:
                if (round(t.bounds.right), round(t.bounds.top)) == (x1, y1):
                    continue
            print("again:", p, "was cut at an earlier box edge")
        params = dict(bbox=f"{x0},{y0},{x1},{y1}", bboxSR=EPSG, imageSR=EPSG,
                      size=f"{w},{h}", format="tiff", pixelType="F32",
                      interpolation="RSP_BilinearInterpolation", noData=-9999, f="image")
        for attempt in range(6):   # the 3DEP server answers 502 / 504 now and then; tiles already on disk are kept
            try:
                r = requests.get(URL, params=params, timeout=600)
                if r.ok and r.content[:2] in (b"II", b"MM"):   # a TIFF, not an error page
                    break
            except requests.RequestException:
                pass
            time.sleep(20 * (attempt + 1))
        else:
            raise SystemExit(f"3DEP download failed for tile {x0},{y0} after 6 tries; run again to resume")
        open(p + ".tmp", "wb").write(r.content)
        os.replace(p + ".tmp", p)
        print("got", p, len(r.content) // 1e6, "MB")

mosaic, transform = merge(paths)
with rasterio.open(paths[0]) as src:
    prof = src.profile
prof.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=transform,
            crs=CRS, nodata=-9999, compress="deflate", tiled=True)
with rasterio.open(f"{RAW}/dem_10m.tif", "w", **prof) as dst:
    dst.write(mosaic)
print("mosaic", mosaic.shape, np.nanmin(mosaic), np.nanmax(mosaic))
