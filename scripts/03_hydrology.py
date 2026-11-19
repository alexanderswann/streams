"""Standard DEM hydrology: fill -> D8 flow direction -> flow accumulation -> streams -> Strahler order.

Two things that aren't standard:
  - resolve_flats() runs with a much smaller increment than its default (FLAT_EPS). The default (1e-5 m a cell) piles
    up across a wide flat until the cells stand higher than the next step down, and the flat turns into a pit: 3DEP
    flattens the water surface of every river wide enough to map, in short level steps, so D8 paths died all along
    the big rivers (the White River at 519 km2, the Winooski at 464, the Hoback at 1,136) and each river's drainage
    started again from nothing below. LA's dry channels have no such steps, so it showed there only at reservoirs.
  - Flow paths still end at every lake and reservoir that holds water (flowlib.still_water), at the cell where the
    water leaves it. That is by design: drainages end at dams, and crossbox.py carries a reservoir's area on past
    its dam for the reaches' own areas. Before, each lake ended paths at scattered pits; now at its outlet.
    "Holds water" is read off the DEM: at least LEVEL_HA of the outline at one elevation (3DEP flattens standing
    water). The reservoirs that were drawn down when the DEM was flown, the dry flood-control basins and the debris
    basins have no such patch (San Gabriel Reservoir, Cogswell, Devil's Gate: under 1 ha, against 6 ha in Big
    Tujunga and 440 in Pyramid Lake), and water runs through them, as it did before.
"""
import numpy as np, rasterio, rasterio.features
from scipy import ndimage
if not hasattr(np, "in1d"):  # pysheds still calls np.in1d, removed in NumPy 2.4
    np.in1d = np.isin
from pysheds.grid import Grid
from config import *

grid = Grid.from_raster(f"{RAW}/dem_10m.tif")
dem = grid.read_raster(f"{RAW}/dem_10m.tif")

# 1. Condition the DEM: fill single-cell pits, fill depressions, then resolve flats
pit_filled = grid.fill_pits(dem)
flooded = grid.fill_depressions(pit_filled)
FLAT_EPS = 1e-9      # m of rise a cell across a flat; 4 km of flat is 0.4 mm, under any step in the DEM
inflated = grid.resolve_flats(flooded, eps=FLAT_EPS, max_iter=10000)

# 2. D8 flow direction (ESRI encoding: E=1 SE=2 S=4 SW=8 W=16 NW=32 N=64 NE=128)
dirmap = (64, 128, 1, 2, 4, 8, 16, 32)
fdir = grid.flowdir(inflated, dirmap=dirmap)

# 2b. End the paths at each lake's outlet: the cell inside it with the most water (accumulation routed straight
#     through first, to find it)
from flowlib import still_water
acc = grid.accumulation(fdir, dirmap=dirmap)
lakes = still_water(HU4, (XMIN, YMIN, XMAX, YMAX))
if len(lakes):
    lab = rasterio.features.rasterize(((g, i + 1) for i, g in enumerate(lakes.geometry)), out_shape=fdir.shape,
                                      transform=grid.affine, fill=0, dtype="int32")
    LEVEL_HA = 2
    z = np.asarray(dem)
    wet = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is not None:
            v = np.round(z[sl][lab[sl] == i], 2)
            if v.size and np.unique(v, return_counts=True)[1].max() * RES * RES / 1e4 >= LEVEL_HA:
                wet.append(i)
    lab[~np.isin(lab, wet)] = 0
    ids = np.unique(lab[lab > 0])
    outlets = ndimage.maximum_position(np.asarray(acc), lab, ids)
    for r_, c_ in outlets:
        if 0 < r_ < fdir.shape[0] - 1 and 0 < c_ < fdir.shape[1] - 1:     # one on the border leaves the box anyway
            fdir[r_, c_] = -2                                              # pysheds' code for a pit
    print(f"lakes and reservoirs ending flow paths at their outlet: {len(ids)} of {len(lakes)} mapped (the rest hold no "
          f"level water in the DEM)")

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
