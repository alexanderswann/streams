"""Patch a scratch copy of scripts/ for the burn (burnlib.py, BURN_M / BURN_SLOPE): 03_hydrology.py keeps its unburned
fill for dem_filled / fill_depth and conditions the burned DEM for dem_cond; 03b_stitch.py's condition() (the seam
mends) burns its piece of raw DEM the same way. With BURN_M=0 both run exactly as before."""
import sys
d = sys.argv[1]
p = f"{d}/03_hydrology.py"
s = open(p).read()
old = """grid = Grid.from_raster(tmp)
dem = grid.read_raster(tmp)
pit_filled = grid.fill_pits(dem)
flooded = grid.fill_depressions(pit_filled)
inflated = grid.resolve_flats(flooded, eps=FLAT_EPS, max_iter=10000)
"""
new = """grid = Grid.from_raster(tmp)
dem = grid.read_raster(tmp)
pit_filled = grid.fill_pits(dem)
flooded = grid.fill_depressions(pit_filled)
import burnlib
if burnlib.DEPTH > 0:   # the routing surface from the burned DEM; dem_filled / fill_depth stay unburned
    from pysheds.sview import Raster
    del pit_filled
    zb = Raster(burnlib.burn(np.asarray(dem, np.float32), T), viewfinder=dem.viewfinder)
    inflated = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(zb)), eps=FLAT_EPS, max_iter=10000)
    del zb
else:
    inflated = grid.resolve_flats(flooded, eps=FLAT_EPS, max_iter=10000)
"""
assert s.count(old) == 1, "03 anchor"
s = s.replace(old, new)
open(p, "w").write(s)
p = f"{d}/03b_stitch.py"
s = open(p).read()
old = """    nod = np.float32(-99999.0)
    vf = ViewFinder(affine=Tw, shape=z.shape, crs=CRS, nodata=nod)
"""
new = """    import burnlib
    z = burnlib.burn(z, Tw)           # the same burn as 03_hydrology.py's (BURN_M=0: none)
    nod = np.float32(-99999.0)
    vf = ViewFinder(affine=Tw, shape=z.shape, crs=CRS, nodata=nod)
"""
assert s.count(old) == 1, "03b anchor"
s = s.replace(old, new)
open(p, "w").write(s)
print("patched 03_hydrology.py and 03b_stitch.py in", d)
