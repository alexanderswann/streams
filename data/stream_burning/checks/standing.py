"""Standing routing checks on a build (the project or a scratch root): per box, the lowest drainage cell (no negative
drainage), reach ends dead on an edge shared with another box (a reach whose last vertex lies on the edge and on no reach
line of another box within 15 m), and order-3+ stream cells (strahler.tif) more than one cell from any
reach (km). AREA=<area> python standing.py [root|-]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else "/Users/mac/Fishing"
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, geopandas as gpd, pandas as pd, rasterio, rasterio.features, shapely
from scipy.ndimage import binary_dilation
import config
from crossbox import shared_edges
edges = shared_edges(list(config.REGIONS))
seam = shapely.union_all(list(edges.values())) if edges else shapely.LineString()
reaches = {r: gpd.read_file(f"{config.out_dir(r)}/streams_scored.gpkg")[["sid", "area_km2", "geometry"]].to_crs(config.CRS)
           for r in config.REGIONS}
allg = [(r, g) for r in reaches for g in reaches[r].geometry]
tree = shapely.STRtree([g for _, g in allg])
owner = np.array([r for r, _ in allg])
rows, dead_list = [], []
for r, g in reaches.items():
    with rasterio.open(f"{config.derived_dir(r)}/area_km2.tif") as src:
        amin = float(src.read(1).min()); T = src.transform; shape = (src.height, src.width)
    ends = shapely.points([ln.coords[-1] for ln in g.geometry])
    on = shapely.dwithin(ends, seam, 1.0) if edges else np.zeros(len(g), bool)
    # dead: on no reach line of another box (its start or its middle), and no other reach of its own box starts there
    # (a junction can fall on the edge: the reach below it then starts in the same box)
    own_starts = shapely.STRtree(shapely.points([ln.coords[0] for ln in g.geometry]))
    dead = [i for i in np.flatnonzero(on)
            if not (owner[tree.query(ends[i], predicate="dwithin", distance=15)] != r).any()
            and not any(j != i for j in own_starts.query(ends[i], predicate="dwithin", distance=15))]
    dead_list += [(r, g.sid.iat[i], round(float(g.area_km2.iat[i]), 1)) for i in dead]
    with rasterio.open(f"{config.derived_dir(r)}/strahler.tif") as src:
        so = src.read(1)
    drawn = rasterio.features.rasterize(((ln, 1) for ln in g.geometry), out_shape=shape, transform=T, fill=0,
                                        dtype="uint8", all_touched=True).astype(bool)
    drawn = binary_dilation(drawn, iterations=1)
    lost = (so >= 3) & ~drawn
    rows.append(dict(box=r, reaches=len(g), min_area_km2=round(amin, 3), ends_on_shared_edge=int(on.sum()),
                     dead_on_edge=len(dead), order3_cells_no_reach_km=round(lost.sum() * config.RES / 1000, 2),
                     order3_km=round((so >= 3).sum() * config.RES / 1000, 1)))
t = pd.DataFrame(rows)
print(f"{config.AREA} ({ROOT})")
print(t.to_string(index=False))
if dead_list:
    print("dead ends:", dead_list[:20])
