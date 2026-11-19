"""Drainage basins for the map. Every DEM cell is traced down the D8 flow directions to where it leaves the study area
(or ends in a sink such as a dam), so each stream reach gets the drainage it belongs to. Drainages big enough get a
name and are split into their major forks; the rest are grouped as minor front-range drainages. Creeks that flow in
from a neighbouring box bring their drainage area with them (crossbox.py), so the trunk and forks are picked as if
the boxes were one map; 06_map.py then joins the basins an edge cuts to the drainage they continue into.

Writes output/<region>/drainages.gpkg (fork polygons with drainage + fork names, plus the unnamed basins that drain
off an edge, for 06_map.py to join) and output/<region>/stream_drainage.csv (sid -> drainage, fork). Run after
05_score.py, with REGION set."""
import re, numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from rasterio import features
from config import *
from crossbox import graph, jump, exit_points, inflows

MAJOR_KM2 = 25   # outlet basins at least this big are named drainages
FORK_KM2 = 35    # a tributary this big joining a drainage's trunk becomes its own fork...
SPLIT_KM2 = 120  # ...in drainages at least this big
MINOR = "Minor front-range drainages"
# canals and flood-control channels catch DEM flow on the valley floor; never name a drainage after them
ARTIFICIAL = re.compile(r"aqueduct|canal|ditch|diversion|drain\b|conduit|spreading|feeder", re.I)
# drainages whose lower reaches have no NHD name, so the trunk rule lands on a tributary
NAME_FIX = {("santa_monica", "Garapito Creek"): "Topanga Creek",
            # the Santa Clara River valley stretch of the Piru box; a short wash near the outlet won the name vote
            ("piru", "Real Wash"): "Santa Clara River",
            # the box reaches the desert floor, where the creek is mapped as a wash
            ("san_gabriel", "Big Rock Wash"): "Big Rock Creek",
            # Bouquet Canyon's stretch through the box's north-west corner, on its way from the Sierra Pelona to the
            # Santa Clara; its channel has no NHD name, so the tributary Texas Canyon won the vote
            ("san_gabriel", "Texas Canyon"): "Bouquet Canyon"}
# forks NHD names oddly: the East Fork is just "San Gabriel River"; the Mojave trunk here is Deep Creek's canyon
FORK_FIX = {("san_gabriel", "San Gabriel River", "Iron Fork"): "East Fork San Gabriel River",
            # lower Bouquet Canyon (with Haskell Canyon), from where it enters the Piru box to the Santa Clara at
            # Saugus; its channel has no NHD name. Joins the stretch upstream in the San Gabriel box (NAME_FIX)
            ("piru", "Santa Clara River", "Santa Clara River, unnamed fork"): "Bouquet Canyon",
            ("san_bernardino", "Mojave River", "Mojave River"): "Deep Creek",
            ("san_bernardino", "Mojave River", "Deep Creek"): "Upper Deep Creek"}
def tidy(n):
    """'San Antonio Creek Channel' -> 'San Antonio Creek', 'Lytle Creek Wash' -> 'Lytle Creek'."""
    return re.sub(r"((?:Creek|River)) (?:Channel|Wash)$", r"\1", n) if n else n

with rasterio.open(f"{DERIVED}/flowdir.tif") as src:
    fdir, T = src.read(1), src.transform
with rasterio.open(f"{DERIVED}/area_km2.tif") as src:
    a = src.read(1).ravel()
H, W = fdir.shape
N = H * W
idx = np.arange(N, dtype=np.int32)
nxt, outlet = graph(fdir)   # downstream neighbour and outlet of every cell (flat index)
basin_km2 = pd.Series(np.bincount(outlet, minlength=N)[np.unique(outlet)] * RES * RES / 1e6, index=np.unique(outlet))

def along(entries):
    """Drainage area that reaches each cell from elsewhere: every entry's area, added all the way down its D8 path."""
    ex = np.zeros(N, np.float32)
    for row, col, km2, *_ in entries:
        i = row * W + col
        while True:
            ex[i] += km2
            if nxt[i] == i:
                break
            i = nxt[i]
    return ex

# Water from neighbouring boxes: this box's hydrology starts a creek that crosses in from the next box with no area,
# so add the area it brings all the way down its path. Without it the Santa Clara River entered the Piru & Castaic
# box with none, Piru Creek won the trunk and the river's own valley was labelled as a fork. Drainages still end at
# dams, so this leaves out water that came over one.
inflow = inflows(REGION)
extra_edge = along(inflow)
for row, col, km2, *_ in inflow:
    basin_km2.loc[int(outlet[row * W + col])] += km2
a += extra_edge
# The same plus the area above any reservoir upstream, carried past its dam: the routing ends every path in a big
# flat lake, so the creek below a dam started again near nothing. For the reaches' areas (area_streams.csv) only.
extra_full = along(inflows(REGION, through_dams=True))
if inflow:
    print(f"inflow from neighbouring boxes: {len(inflow)} creeks, {sum(e[2] for e in inflow):.0f} km2")
major = basin_km2[basin_km2 >= MAJOR_KM2]

# ---- forks ----
# A branch ends where it is the smaller arm at a confluence (the downstream cell gets more area from elsewhere).
# Branch mouths with >= FORK_KM2, inside drainages >= SPLIT_KM2, are fork candidates; a cell's fork is the outermost
# candidate on its way down (the one that joins the trunk), so nested forks stay with their parent fork.
ends = (a[nxt] - a) > a
big_basins = major.index[major >= SPLIT_KM2].values
cand = np.flatnonzero(ends & (a >= FORK_KM2) & np.isin(outlet, big_basins))
stop = np.zeros(N, bool)
stop[cand] = True
stop |= nxt == idx
first = jump(np.where(stop, idx, nxt).astype(np.int32))      # first candidate (or outlet) downstream of each cell
fork_of = {}
for s in cand:
    m = int(s)
    while True:
        p = int(first[nxt[m]])
        if p == outlet[m]:
            break
        m = p
    fork_of[int(s)] = m
unit = first.copy()                                            # fork mouth, or the outlet for trunk cells
for s, m in fork_of.items():
    if s != m:
        unit[unit == s] = m                                    # nested fork -> outermost fork
del first, stop

# ---- stream reaches -> unit, by the biggest-area cell within 2 cells of each reach's middle vertex ----
streams = gpd.read_file(f"{OUT}/streams_scored.gpkg").to_crs(CRS)
A2 = a.reshape(H, W)
def reach_cell(g):
    xy = np.asarray(g.coords if g.geom_type == "LineString" else max(g.geoms, key=lambda p: p.length).coords)
    c, r = ~T * tuple(xy[len(xy) // 2])
    r, c = int(np.clip(r, 0, H - 1)), int(np.clip(c, 0, W - 1))
    r0, c0 = max(r - 2, 0), max(c - 2, 0)
    win = A2[r0:r + 3, c0:c + 3]
    i, j = np.unravel_index(np.argmax(win), win.shape)
    return (r0 + i) * W + c0 + j
cells = np.array([reach_cell(g) for g in streams.geometry])
streams["outlet"], streams["unit"] = outlet[cells], unit[cells]
# Strahler order on the channel cell itself (05_score samples the middle vertex, which can sit beside the channel)
with rasterio.open(f"{DERIVED}/strahler.tif") as src:
    streams["strahler"] = src.read(1).ravel()[cells]

def candidates(sub, share=0.5):
    """Names for a drainage/fork, best first: natural named reaches near its bottom (>= share of the biggest named
    area), most channel length first; then every other name by its biggest area. Length-weighting at the bottom
    avoids a side creek whose last reach straddles the confluence and so carries the trunk's area."""
    named = sub[sub["name"].notna() & ~sub["name"].fillna("").str.contains(ARTIFICIAL)]
    if not len(named):
        return []
    low = named[named.area_km2 >= share * named.area_km2.max()]
    first = list(low.groupby("name").len_m.sum().sort_values(ascending=False).index)
    rest = [n for n in named.groupby("name").area_km2.max().sort_values(ascending=False).index if n not in first]
    return first + rest

dname = {}
for o in major.index:
    c = candidates(streams[streams.outlet == o], 0.8)
    n = tidy(c[0]) if c else None
    dname[int(o)] = NAME_FIX.get((REGION, n), n)
# basins split by a dam / sink share a name; unnamed ones fall in with the minor drainages
streams["drainage"] = [dname.get(int(o)) or MINOR for o in streams.outlet]
uname = {}
for o, sub in streams[streams.drainage != MINOR].groupby("outlet"):
    used = {dname[int(o)]}
    uname[int(o)] = dname[int(o)]
    forks = sub[sub.unit != o]
    for u in forks.groupby("unit").size().sort_values(ascending=False).index:   # bigger forks pick first
        nm = next((tidy(n) for n in candidates(forks[forks.unit == u]) if tidy(n) not in used), None)
        nm = nm or f"{dname[int(o)]}, unnamed fork"
        used.add(nm)
        uname[int(u)] = nm
uname = {u: FORK_FIX.get((REGION, dname[int(outlet[u])], n), n) for u, n in uname.items()}
streams["fork"] = [uname.get(int(u), d) for u, d in zip(streams.unit, streams.drainage)]
streams.loc[streams.drainage == MINOR, "fork"] = MINOR
# Where each reach's basin leaves the study area: the centre of the first cell outside the box, if it drains off an
# edge (sinks such as dams and lakes have none). 06_map.py uses it to join basins cut by a box edge to the
# drainage they continue into in the neighbouring range.
o = streams.outlet.values.astype(np.int64)
streams["out_x"], streams["out_y"] = exit_points(fdir, T, o)
streams["basin_km2"] = basin_km2.reindex(o).values.round(2)
streams[["sid", "drainage", "fork", "strahler", "out_x", "out_y", "basin_km2"]].to_csv(f"{OUT}/stream_drainage.csv",
                                                                                     index=False)

# Each reach's drainage area with the water that reaches it from neighbouring boxes (edge: 05b_flow.py scales the
# modelled flow with it) and also over dams (full: the fish score's creek size), added where 05_score.py measured
# area_km2: the link's second-to-last vertex, a cell corner (snapped back to the 10 m grid after the lat/lon trip).
end = np.array([g.coords[-2] if len(g.coords) >= 2 else g.coords[0] for g in streams.geometry])
cc, rr = ~T * tuple(np.round(end / RES).T * RES)
own = np.clip(np.rint(rr).astype(int), 0, H - 1) * W + np.clip(np.rint(cc).astype(int), 0, W - 1)
same = np.isclose((a - extra_edge)[own], streams.area_km2, atol=0.02).mean()
streams["area_edge_km2"] = (streams.area_km2 + extra_edge[own]).round(2)
streams["area_full_km2"] = (streams.area_km2 + extra_full[own]).round(2)
streams[["sid", "area_edge_km2", "area_full_km2"]].to_csv(f"{OUT}/area_streams.csv", index=False)
print(f"reach areas: {same:.1%} sampled on 05_score's cell; {(streams.area_edge_km2 > streams.area_km2).sum()} reaches get "
      f"water from other boxes, {(streams.area_full_km2 > streams.area_km2).sum()} counting dams too")

# ---- polygons per fork / trunk (50 m cells) for named drainages, plus the unnamed basins that drain off a box
# edge: 06_map.py joins those to the drainage they continue into in the neighbouring box (upper San Francisquito
# Canyon -> Santa Clara River) and drops the rest ----
k = 5
small = unit.reshape(H, W)[::k, ::k].astype(np.int32)
named_outlets = {o for o, n in dname.items() if n}
uo = basin_km2.index.values
ex_x, ex_y = exit_points(fdir, T, uo)
exit_of = {int(o): (x, y) for o, x, y in zip(uo, ex_x, ex_y)}
edge_minor = uo[~np.isnan(ex_x) & (basin_km2.values >= 0.5) & ~np.isin(uo, list(named_outlets))]
keep = np.isin(outlet.reshape(H, W)[::k, ::k], list(named_outlets) + edge_minor.tolist())
rows = []
for g, v in features.shapes(small, mask=keep, transform=T * rasterio.Affine.scale(k)):
    rows.append(dict(unit=int(v), geometry=shapely.geometry.shape(g)))
poly = gpd.GeoDataFrame(rows, crs=CRS).dissolve("unit").reset_index()
poly["outlet"] = outlet[poly.unit.values]
poly["drainage"] = [dname.get(int(o)) or MINOR for o in poly.outlet]
poly["fork"] = [uname.get(int(u), d) for u, d in zip(poly.unit, poly.drainage)]
# dam-split basins of one river merge; an unnamed basin keeps its own outline, keyed by where it leaves the box
poly["out_x"] = [exit_of[int(o)][0] if d == MINOR else np.nan for o, d in zip(poly.outlet, poly.drainage)]
poly["out_y"] = [exit_of[int(o)][1] if d == MINOR else np.nan for o, d in zip(poly.outlet, poly.drainage)]
poly["exit"] = ["" if np.isnan(x) else f"{x:.0f},{y:.0f}" for x, y in zip(poly.out_x, poly.out_y)]
poly = poly.dissolve(["drainage", "fork", "exit"]).reset_index()
poly["region"] = LABEL
poly["area_km2"] = (poly.area / 1e6).round(1)
poly = poly[poly.area_km2 >= np.where(poly.drainage == MINOR, 0.5, 2)].reset_index(drop=True)   # edge slivers
# Simplify the fork polygons together as one coverage, so neighbours keep exactly shared edges (simplifying each on
# its own left gaps and overlaps between forks, which the maps drew as little triangles along the divides). The
# polygons are first rebuilt from their noded boundaries: built cell by cell, one polygon's edge can run straight
# past a point where its neighbours have a vertex (where three forks meet), which the coverage tools reject.
# 60 m also smooths most of the 50 m raster stair-steps.
geoms = shapely.make_valid(poly.geometry.values)
faces = np.asarray(shapely.get_parts(shapely.polygonize(shapely.get_parts(
    shapely.node(shapely.union_all(shapely.boundary(geoms)))))))
inp, owner = shapely.STRtree(geoms).query(shapely.point_on_surface(faces), predicate="within")
faces, owner = faces[inp], owner
simp = gpd.GeoDataFrame({"i": owner}, geometry=shapely.coverage_simplify(faces, 60), crs=CRS).dissolve("i")
poly.loc[simp.index, "geometry"] = simp.geometry.values
poly[["region", "drainage", "fork", "area_km2", "out_x", "out_y", "geometry"]].to_crs(4326).to_file(f"{OUT}/drainages.gpkg")

print(f"{len(basin_km2)} outlets, {len(major)} >= {MAJOR_KM2} km2; {(poly.drainage == MINOR).sum()} unnamed basins "
      f"drain off an edge ({poly[poly.drainage == MINOR].area_km2.sum():.0f} km2)")
print(poly[poly.drainage != MINOR].groupby(["drainage", "fork"]).area_km2.sum().to_string())
print(streams.groupby("drainage").size().sort_values().to_string())
