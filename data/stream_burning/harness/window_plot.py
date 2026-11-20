"""Plot a window_test.py result: D8 channels (1+ km2) for two depths over the terrain, with NHD HR (blue) and NHDPlus V2
(labelled with comid and km2). AREA=.. REGION=.. python window_plot.py x0 y0 x1 y1 dA dB out.png [zoom x0 y0 x1 y1]"""
import sys, os, importlib
sys.path.insert(0, "/Users/mac/Fishing/scripts"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir("/Users/mac/Fishing/scripts")
import numpy as np, rasterio, rasterio.windows, geopandas as gpd, shapely
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
import config, burnlib
from flowlib import FLOW
st = importlib.import_module("03b_stitch")
x0, y0, x1, y1 = map(float, sys.argv[1:5]); dA, dB, out = sys.argv[5], sys.argv[6], sys.argv[7]
zx = list(map(float, sys.argv[8:12])) if len(sys.argv) > 8 else [x0, y0, x1, y1]
with rasterio.open(f"{config.RAW}/dem_10m.tif") as src:
    win = rasterio.windows.from_bounds(x0, y0, x1, y1, src.transform).round_offsets().round_lengths()
    z = src.read(1, window=win, masked=True).astype(np.float32).filled(np.nan)
    T = src.window_transform(win)
D = os.environ.get("OUTDIR", "/tmp")
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg").to_crs(config.CRS).cx[zx[0]:zx[2], zx[1]:zx[3]]
hr = burnlib.lines().cx[zx[0]:zx[2], zx[1]:zx[3]]
fig, axs = plt.subplots(1, 2, figsize=(22, 11), dpi=100)
ls = LightSource(315, 45)
ext = (T.c, T.c + z.shape[1] * 10, T.f - z.shape[0] * 10, T.f)
for ax, d in zip(axs, (dA, dB)):
    fd = np.load(f"{D}/fd_{d}.npy")
    acc, _ = st.accumulate(fd, st.DR, st.DC)
    a = acc * 1e-4
    ax.imshow(ls.shade(np.nan_to_num(z, nan=np.nanmin(z)), cmap=plt.cm.gist_earth, vert_exag=4, blend_mode="overlay"), extent=ext)
    ax.contour(np.linspace(ext[0], ext[1], z.shape[1]), np.linspace(ext[3], ext[2], z.shape[0]), z,
               levels=np.arange(400, 900, 5), colors="k", linewidths=0.15)
    hr.plot(ax=ax, color="blue", lw=0.8)
    v2.plot(ax=ax, color="cyan", lw=1.5, alpha=0.7)
    for g, c, t in zip(v2.geometry, v2.comid, v2.totdasqkm):
        if t >= 2:
            p = g.interpolate(0.5, normalized=True)
            ax.annotate(f"{c % 100000}:{t:.0f}", (p.x, p.y), fontsize=6, color="darkcyan")
    from scipy.ndimage import maximum_filter
    a = maximum_filter(a, size=int(os.environ.get("THICK", "5")))
    m = np.ma.masked_less(np.log10(np.maximum(a, 1e-3)), 0)
    ax.imshow(m, extent=ext, cmap="autumn_r", vmin=0, vmax=2, interpolation="nearest")
    ax.set_xlim(zx[0], zx[2]); ax.set_ylim(zx[1], zx[3]); ax.set_title(f"burn {d} m: D8 channels 1+ km2 (yellow 1 -> red 100)")
fig.savefig(out, bbox_inches="tight"); print("ok")
