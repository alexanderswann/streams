"""The largest drainage (area_km2.tif, own cells only) within 25 m of points along a line between two lat,lon points,
in a build: AREA=<area> python line_area.py <root> <box> <lat1> <lon1> <lat2> <lon2>"""
import sys, os
P = "/Users/mac/Fishing"
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, pyproj, shapely
import config
root, box = sys.argv[1], sys.argv[2]
a = list(map(float, sys.argv[3:7]))
fwd = pyproj.Transformer.from_crs(4326, config.CRS, always_xy=True)
p1, p2 = fwd.transform(a[1], a[0]), fwd.transform(a[3], a[2])
with rasterio.open(f"{root}/data/derived/{config.AREA}/{box}/area_km2.tif") as src:
    A, T = src.read(1), src.transform
n = max(2, int(np.hypot(p2[0] - p1[0], p2[1] - p1[1]) // 25) + 1)
out = []
for t in np.linspace(0, 1, n):
    x, y = p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])
    c, r = ~T * (x, y); r, c = int(r), int(c)
    w = A[max(0, r - 3):r + 4, max(0, c - 3):c + 4]
    out.append(round(float(np.nanmax(w)), 2))
print(f"{box}: largest own drainage within 30 m, every ~25 m from the first point to the second: {out}")
