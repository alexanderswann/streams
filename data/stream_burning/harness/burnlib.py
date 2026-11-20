"""Stream burning for the routing surface only: NHD HR stream lines lowered into the DEM before it is conditioned.

The burned surface decides flow directions (03b's D8); the elevations that drops, gradients and profiles are measured on
(dem_filled.tif, fill_depth.tif, dem_10m.tif) stay unburned.

Lines: every box's nhd_flowlines.gpkg of the area (each box's file reaches 0.5-3.7 km past its box, so together they
cover any box's halo), StreamRiver (460), ArtificialPath (558, through lakes and wide rivers) and Connector (334);
not CanalDitch (336), Pipeline (428), Underground conduit (420) or Coastline (566).
BURN_M: depth in m (0: no burn). BURN_SLOPE: burn only where the ground's slope, averaged over 50 m, is under this
(0: everywhere).
"""
import os, functools
import numpy as np, geopandas as gpd, pandas as pd, rasterio.features, shapely
from config import REGIONS, raw_dir, CRS

BURN_FTYPES = (460, 558, 334)
DEPTH = float(os.environ.get("BURN_M", "0"))
SLOPE_MAX = float(os.environ.get("BURN_SLOPE", "0"))
EDGE_M = float(os.environ.get("BURN_EDGE_M", "0"))   # no burn this close to the area's outer edge (no halo there)


@functools.lru_cache(1)
def lines():
    parts = []
    for r in REGIONS:
        p = f"{raw_dir(r)}/nhd_flowlines.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p, columns=["ftype"])
            parts.append(g[g.ftype.isin(BURN_FTYPES)].to_crs(CRS))
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    wkb = g.geometry.normalize().to_wkb()
    return g[~pd.Series(wkb).duplicated().values].reset_index(drop=True)


@functools.lru_cache(1)
def inner():
    """The area's boxes less EDGE_M along its outer edge (edges shared between boxes are inside)."""
    u = shapely.union_all([shapely.box(*v["bbox"]) for v in REGIONS.values()])
    return u.buffer(-EDGE_M) if EDGE_M > 0 else u


def mask(shape, transform):
    """Cells of a grid (shape, affine) on a burn line: one cell wide, 8-connected; none within EDGE_M of the area's
    outer edge, where a burned line running along or out over the edge would lead the water off the map early."""
    H, W = shape
    x0, y1 = transform.c, transform.f
    x1, y0 = x0 + W * transform.a, y1 + H * transform.e
    g = lines()
    g = g[g.intersects(shapely.box(x0, y0, x1, y1))]
    if not len(g):
        return np.zeros(shape, bool)
    m = rasterio.features.rasterize(((geom, 1) for geom in g.geometry), out_shape=shape, transform=transform,
                                    fill=0, dtype="uint8", all_touched=False).astype(bool)
    if EDGE_M > 0:
        m &= rasterio.features.rasterize([(inner(), 1)], out_shape=shape, transform=transform, fill=0,
                                         dtype="uint8").astype(bool)
    return m


def flat(z, slope_max):
    """Cells where the ground's slope, averaged over 50 m (5 x 5 cells), is under slope_max."""
    from scipy.ndimage import uniform_filter
    good = np.isfinite(z) & (z > -1000)
    zz = np.where(good, z, np.nan).astype(np.float32)
    fillv = float(np.nanmean(zz)) if good.any() else 0.0
    gy, gx = np.gradient(np.where(good, zz, fillv), 10.0)
    del zz
    g = np.hypot(gx, gy).astype(np.float32)
    del gx, gy
    g[~good] = 1e3        # no ground: never flat (finite: uniform_filter's running sum turns an inf row into NaN)
    return (uniform_filter(g, size=5) < slope_max) & good


def burn(z, transform, depth=None, slope_max=None):
    """z (float; NaN or nodata where there is no ground, left as is) with the burn lines lowered by depth m, only where
    the ground is flatter than slope_max if that is > 0."""
    d = DEPTH if depth is None else depth
    sm = SLOPE_MAX if slope_max is None else slope_max
    if d <= 0:
        return z
    ok = mask(z.shape, transform) & np.isfinite(z) & (z > -1000)
    if sm > 0:
        ok &= flat(z, sm)
    out = z.copy()
    out[ok] = z[ok] - d
    return out
