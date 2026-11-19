"""Standard DEM hydrology: fill -> D8 flow direction -> flow accumulation -> streams -> Strahler order."""
import numpy as np, rasterio
if not hasattr(np, "in1d"):  # pysheds still calls np.in1d, removed in NumPy 2.4
    np.in1d = np.isin
from pysheds.grid import Grid
from config import *

grid = Grid.from_raster(f"{RAW}/dem_10m.tif")
dem = grid.read_raster(f"{RAW}/dem_10m.tif")

# 1. Condition the DEM: fill single-cell pits, fill depressions, then resolve flats
pit_filled = grid.fill_pits(dem)
flooded = grid.fill_depressions(pit_filled)
inflated = grid.resolve_flats(flooded)

# 2. D8 flow direction (ESRI encoding: E=1 SE=2 S=4 SW=8 W=16 NW=32 N=64 NE=128)
dirmap = (64, 128, 1, 2, 4, 8, 16, 32)
fdir = grid.flowdir(inflated, dirmap=dirmap)

# 3. Flow accumulation (cells) -> drainage area km^2
acc = grid.accumulation(fdir, dirmap=dirmap)
area_km2 = acc * (RES * RES) / 1e6

# 4. Stream network: channel initiation at 0.25 km^2 (2,500 cells @ 10 m)
STREAM_KM2 = 0.25
streams = area_km2 >= STREAM_KM2

# 5. Strahler order
order = grid.stream_order(fdir, streams, dirmap=dirmap)

fill_depth = np.asarray(flooded) - np.asarray(dem)
prof = rasterio.open(f"{RAW}/dem_10m.tif").profile
prof.update(compress="deflate", tiled=True, nodata=None)
def save(name, arr, dtype):
    p = dict(prof, dtype=dtype)
    with rasterio.open(f"{DERIVED}/{name}.tif", "w", **p) as dst:
        dst.write(np.asarray(arr).astype(dtype), 1)
save("dem_filled", flooded, "float32")
save("fill_depth", fill_depth, "float32")
save("flowdir", fdir, "uint8")
save("area_km2", area_km2, "float32")
save("strahler", np.where(streams, order, 0), "uint8")

# Vector stream network (one line per link between confluences)
branches = grid.extract_river_network(fdir, streams, dirmap=dirmap)
import geopandas as gpd
g = gpd.GeoDataFrame.from_features(branches["features"], crs=CRS)
g.to_file(f"{DERIVED}/dem_streams.gpkg")
print("stream cells", int(streams.sum()), "links", len(g), "max order", int(np.max(order)))
