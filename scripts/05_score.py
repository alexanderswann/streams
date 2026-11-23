"""Attribute DEM streams + drop candidates (perennial, remoteness, trout-elevation) for one region,
score them, and write layers for the combined map (06_map.py). Run with REGION=<name>."""
import json, os, re, time, shapely, numpy as np, pandas as pd, geopandas as gpd, rasterio
from collections import defaultdict
from rasterio.warp import calculate_default_transform, reproject, Resampling
import matplotlib
from matplotlib import cm, colors
from PIL import Image
from rasterio import features
from config import *
import areaclip

MAP_MIN_KM2 = 1.0   # draw every channel draining >= 1 km^2 ...
NHD_MIN_KM2 = 0.25  # ... and down to this (03b_stitch.py's channel start) where NHD maps the creek year-round or names it

dem_src = rasterio.open(f"{RAW}/dem_10m.tif")
dem = dem_src.read(1)
area = rasterio.open(f"{DERIVED}/area_km2.tif").read(1)
strahler = rasterio.open(f"{DERIVED}/strahler.tif").read(1)
inv = ~dem_src.transform
def sample(arr, geoms):
    cols, rows = inv * (np.array([g.x for g in geoms]), np.array([g.y for g in geoms]))
    return arr[np.clip(rows.astype(int), 0, arr.shape[0] - 1), np.clip(cols.astype(int), 0, arr.shape[1] - 1)]

streams = gpd.read_file(f"{DERIVED}/dem_streams.gpkg")
# A river that comes in from outside the map (crossbox.py's "outside" water: over the outer edge, or through a
# reservoir the edge cuts and on below its dam) starts its line where its water goes in, not where 0.25 km2 has
# gathered inside the map: 03b_stitch.py's streams count only the map's own cells, so a river's first few hundred
# metres in the map had no link, and 06_map.py drew them through as lines with no reach of their own (65 mi at the
# edges and 5.7 mi below dams, on the 12 maps of 2026-11-22: the Little Tennessee below Chilhowee Dam, the
# Chattahoochee below Buford Dam). The D8 path from that cell to the first line is a link of its own, on cell corners
# as 03b's lines are (crossbox.lead_ins).
import crossbox
_leads = crossbox.lead_ins(REGION, streams.geometry,
                           [e for e in crossbox.inflows(REGION, through_dams=True) if e[3] == "outside"])
print(f"lines from where a river from outside the map goes in to its first link: {len(_leads)}, "
      f"{sum(g.length for g in _leads) / 1000:.1f} km")
streams = pd.concat([streams, gpd.GeoDataFrame(geometry=_leads, crs=CRS)], ignore_index=True)
nhd = gpd.read_file(f"{RAW}/nhd_flowlines.gpkg")
nhd_pts = gpd.read_file(f"{RAW}/nhd_points.gpkg")
roads = gpd.read_file(f"{RAW}/osm_roads.gpkg")
trails = gpd.read_file(f"{RAW}/osm_trails.gpkg")
kp = pd.concat([gpd.read_file(f"{DERIVED}/knickpoints.gpkg").assign(**{"pass": 1}),
                gpd.read_file(f"{DERIVED}/knickpoints_bigcreek.gpkg")], ignore_index=True)
kp = gpd.GeoDataFrame(kp, crs=CRS)
kp = kp[areaclip.inside(kp.geometry.values)]    # an area that stops at a state line: drops past it go (areaclip.py)

# Public roads a car can use (exclude gated/private service roads & fire roads marked no motor vehicles)
drivable = roads[~roads.access.isin(["private", "no"]) & ~roads.motor_vehicle.isin(["no", "private"])
                 & (roads.highway != "track")]
road_u = drivable.geometry.union_all()
trail_u = pd.concat([trails.geometry, roads[roads.highway == "track"].geometry]).union_all()

# NHD: perennial (46006) / intermittent (46003) / ephemeral (46007); keep stream/river & artificial paths
# Artificial paths (55800, the centrelines of mapped rivers and lakes) take the area's class (config.py)
nhd["flow"] = nhd.fcode.map({46006: "perennial", 46003: "intermittent", 46007: "ephemeral",
                             55800: ARTIFICIAL_PATH}).fillna("other")
# Known waterfalls: the area's list from every source, merged (02f_known_falls.py: OpenStreetMap, NHD, USGS GNIS,
# Wikidata, CDFW's barrier surveys in LA, and falls from guidebooks and state inventories in data/known_falls_curated.csv).
# This range takes those within 500 m of its box, so a drop near an edge still finds its fall, and writes out only those
# inside it, so each fall is drawn once (the lon/lat box each range used to take overlapped its neighbours').
kf_path = f"{SHARED}/known_falls.gpkg"
if not os.path.exists(kf_path):
    raise SystemExit(f"{kf_path} is missing: run AREA={AREA} 02f_known_falls.py first (run_mid.sh does)")
range_box = shapely.box(XMIN, YMIN, XMAX, YMAX)
known_falls = gpd.read_file(kf_path).to_crs(CRS)
known_falls = known_falls[known_falls.intersects(range_box.buffer(500))].reset_index(drop=True)
known_falls["precise"] = known_falls.precise.astype(bool)
print(f"known falls: {len(known_falls)} ({int(known_falls.precise.sum())} precisely placed);",
      "sources:", known_falls.src.str.split(" · ").explode().value_counts().to_dict())
dams = pd.concat([nhd_pts[nhd_pts.ftype == 343].geometry, gpd.read_file(f"{RAW}/osm_dams.gpkg").geometry])

# ---- stream links ----
# Measured on each link's own cells. A pysheds link's last vertex is the cell where it joins the next stream, so the
# drainage area there includes the other arm: every side creek used to report the trunk's area, and gullies draining
# well under 1 km2 passed the cut. Area, gradient and the downstream end now use the second-to-last vertex; order and
# elevation use the middle vertex (vertices sit on cell corners, so they always sample the channel cell itself).
# Name and NHD flow class come from the NHD lines nearest the link at its 25 %, 50 % and 75 % vertices, each kept when
# two of the three agree (on the name, or the class: NHD splits a creek into many short segments), so a short side
# creek doesn't take the name and flow of the river it runs beside. NHD has no name on many lines (e.g. San Antonio
# Creek below Mt. Baldy); those links take the name of OpenStreetMap's named rivers and streams the same way.
# Links mostly on sea-level cells are dropped (the DEM stores the sea as 0 m, and its flats trace fake channels), and
# in an area that stops at a state line (config clip_state), links whose middle lies past it (areaclip.py).
s = streams[streams.length > 0].copy()
def vert(g, f):
    c = g.coords
    return shapely.Point(c[min(len(c) - 1, max(0, int(round(f * (len(c) - 1)))))])
def vertices3(geoms, index=None):
    """Each line's 25 / 50 / 75 % vertices, as three point layers."""
    return [gpd.GeoDataFrame(geometry=[vert(g, f) for g in geoms], index=index, crs=CRS) for f in (0.25, 0.5, 0.75)]
def vote(lines, col, max_d=60, pts=None):
    """`col` of the line nearest each link's 25 / 50 / 75 % vertices (`pts`, vertices3(); the reaches' by default),
    within max_d m, kept when two agree."""
    pts = pts3 if pts is None else pts
    v = pd.concat([gpd.sjoin_nearest(p, lines[[col, "geometry"]], max_distance=max_d, how="left").groupby(level=0)[col]
                   .first().reindex(pts[0].index) for p in pts], axis=1, ignore_index=True)
    out = v[0].where(v[0].notna() & ((v[0] == v[1]) | (v[0] == v[2])))
    return out.fillna(v[1].where(v[1].notna() & (v[1] == v[2])))
own_end = gpd.GeoSeries([shapely.Point(g.coords[-2] if len(g.coords) >= 2 else g.coords[0]) for g in s.geometry],
                        index=s.index, crs=CRS)
starts = gpd.GeoSeries([shapely.Point(g.coords[0]) for g in s.geometry], index=s.index, crs=CRS)
mid = gpd.GeoSeries([vert(g, 0.5) for g in s.geometry], index=s.index, crs=CRS)
s["area_km2"] = sample(area, own_end).round(2)
# The floor counts the water that reaches a link from elsewhere, as the reaches' areas do (05c_drainages.py's
# area_full_km2, from crossbox.py): over a dam, past a pond, in from outside the map. A lake ends its D8 paths at its
# outlet (03b_stitch.py), so the creek below starts again near nothing, and on its own area alone its links stayed
# under the floor until it had gathered 1 km2 again or met a creek that had: the map had no line below the outlet.
# Where it did have one, a path had leaked across the lake and left it beside the outlet; since 2026-11-21 every lake
# cell drains to the outlet (03b_stitch.route_lake), so those stretches went too (found the same day: 1.5 km of the
# Oswegatchie, the Raquette between Raquette Lake and Forked Lake, Salmon Lake Outlet, Emma Matilda Lake's outlet).
# area_km2 stays the link's own area; 05c adds the carried water where this samples it, so the two agree.
carried_grid = crossbox.carried_km2(REGION).reshape(area.shape)
carried = sample(carried_grid, own_end)
sea = np.array([np.mean(sample(dem, shapely.points(np.asarray(g.coords))) <= 0.5) for g in s.geometry])
# Under MAP_MIN_KM2 a creek is drawn down to NHD_MIN_KM2 where NHD maps it year-round or names it (the vote below, on
# the uncut link). Where streams run at smaller sizes NHD's year-round lines start smaller (the Smokies, Vermont, North
# Georgia; hardly any in LA), and NHD's named brook-trout branches there drain 0.1-0.39 sq mi: at 1 km2 alone 12.5 % of
# NHD's named stream miles on the 12 maps were not drawn, 26 % in the Smokies (the audit of 2026-11-22; the user's
# choice the same day, of keeping 1 km2, NHD's year-round lines only, its named ones only, or both).
SIDE_RATIO, SIDE_RIVER_KM2, SIDE_NEAR_M, SIDE_ALONG, SIDE_ON_RIVER = 10.0, 50.0, 250.0, 0.6, 0.6   # side channels: below
# The vote reads the NHD line nearest the link, and a small link along a river's bank reads the river's line, its name
# and its class: that is no evidence for the link (nhd_says; on the first try about 1,600 bank links of the 12 maps
# were drawn as "side channels" of the river beside them, 156 mi, scored with the river's size).
def nhd_says(geoms, km2, lines, big_geoms, big_km2):
    """Links NHD names or maps year-round (the vote), less what a link reads off a stream SIDE_RATIO times bigger beside
    it (`big_geoms`, their drainage `big_km2`): a name it shares with one within SIDE_NEAR_M, and, with no name of its
    own, the year-round class of one of SIDE_RIVER_KM2 or more it runs along (SIDE_ON_RIVER of its length within 150 m,
    as the side channels' test below)."""
    p3 = vertices3(geoms)
    nm = vote(lines, "gnis_name", pts=p3).to_numpy(object)
    ok = pd.notna(nm) | vote(lines, "flow", pts=p3).eq("perennial").to_numpy()
    if len(big_geoms):
        bn, tree = vote(lines, "gnis_name", pts=vertices3(big_geoms)).to_numpy(object), shapely.STRtree(big_geoms)
        for n_, g in enumerate(geoms):
            if not ok[n_]:
                continue
            near = tree.query(g, predicate="dwithin", distance=SIDE_NEAR_M)
            if isinstance(nm[n_], str):
                ok[n_] = not any(bn[k] == nm[n_] and big_km2[k] >= SIDE_RATIO * km2[n_] for k in near)
            else:
                river = [k for k in near if big_km2[k] >= max(SIDE_RIVER_KM2, SIDE_RATIO * km2[n_])]
                ok[n_] = not (river and g.intersection(shapely.union_all(shapely.buffer(big_geoms[river], 150))).length
                              >= SIDE_ON_RIVER * g.length)
    return ok
# The floor reads NHD's natural channels only. Its canals and ditches (FType 336), pipelines (428) and underground
# conduits (420) are built, and so is a line named after one, as the paths and connectors NHD lays along an aqueduct
# through its reservoirs are (a name it gives a built channel of the box and no stream line, FType 460). On the first
# try 9.7 mi of LA's new lines were named after the California and Los Angeles aqueducts, the Gage and Riverside canals
# and flood-control channels (fish 0-9, 2026-11-22). A stream line NHD names after a channel (a canyon's creek above its
# flood-control channel) is still read, and so are the paths of a river through its own water.
BUILT_FTYPES = (336, 420, 428)
def floor_lines(nl):
    """The NHD lines `nl` (gnis_name, ftype, flow, geometry) the floor reads: no built channel, nor a line named after
    one."""
    built = nl.ftype.isin(BUILT_FTYPES)
    built_name = set(nl.gnis_name[built].dropna()) - set(nl.gnis_name[nl.ftype.eq(460)].dropna())
    nl = nl[~built & ~nl.gnis_name.isin(built_name)]
    return nl[["gnis_name", "flow", "geometry"]].reset_index(drop=True)
full0 = s.area_km2 + carried
base = (sea < 0.5) & areaclip.inside(s.geometry.values)
_f, _g = full0.to_numpy(float), s.geometry.values
small = ((full0 < MAP_MIN_KM2) & (full0 >= NHD_MIN_KM2) & base).to_numpy()
_big = np.flatnonzero((full0 >= MAP_MIN_KM2).to_numpy() & base)
by_nhd = np.zeros(len(s), bool)
if small.any():
    by_nhd[small] = nhd_says(_g[small], _f[small], floor_lines(nhd), _g[_big], _f[_big])
keep = ((full0 >= MAP_MIN_KM2) | by_nhd) & base
# A creek kept goes on downstream until it meets a kept line: NHD's class changes along a creek, and the vote with it, so
# a creek kept on its NHD evidence could end in the woods where NHD calls it intermittent (14 such ends in NE Connecticut
# on the first try). Across an edge two boxes share, the link that ends on it in the next box is judged here with the
# same rule, on that box's cells and NHD lines: a creek kept on one side goes on on the other.
_key = lambda c: (round(c[0], 1), round(c[1], 1))
_starts = defaultdict(list)
for i, ln in enumerate(_g):
    _starts[_key(ln.coords[0])].append(i)
_kp, _seam = keep.to_numpy().copy(), []
for nb in REGIONS:
    if nb == REGION or not shapely.box(*REGIONS[nb]["bbox"]).intersection(range_box).length:
        continue
    _ns = gpd.read_file(f"{derived_dir(nb)}/dem_streams.gpkg")
    _ns = _ns[_ns.length > 0]
    _e = np.array([ln.coords[-1][:2] for ln in _ns.geometry])
    _in = shapely.contains_xy(range_box.buffer(1), _e[:, 0], _e[:, 1])     # ends on this box's first cell
    if not _in.any():
        continue
    with rasterio.open(f"{derived_dir(nb)}/area_km2.tif") as _src:
        _a = np.array([v[0] for v in _src.sample([ln.coords[-2][:2] if len(ln.coords) >= 2 else ln.coords[0][:2]
                                                  for ln in _ns.geometry])], float)
    _nl = gpd.read_file(f"{raw_dir(nb)}/nhd_flowlines.gpkg")
    _nl["flow"] = _nl.fcode.map({46006: "perennial", 46003: "intermittent", 46007: "ephemeral",
                                 55800: ARTIFICIAL_PATH}).fillna("other")
    _sm = np.flatnonzero(_in & (_a >= NHD_MIN_KM2) & (_a < MAP_MIN_KM2))
    _ok = np.flatnonzero(_in & (_a >= MAP_MIN_KM2)).tolist()
    if len(_sm):
        _bg = np.flatnonzero(_a >= MAP_MIN_KM2)
        _ok += _sm[nhd_says(_ns.geometry.values[_sm], _a[_sm], floor_lines(_nl), _ns.geometry.values[_bg],
                            _a[_bg])].tolist()
    _seam += [j for k in _ok for j in _starts.get(_key(_ns.geometry.values[k].coords[-1]), []) if base[j] and not _kp[j]]
_n0 = int(_kp.sum())
_kp[_seam] = True
# ... and through a pond or reservoir: a creek kept into it goes on below its outlet, where crossbox.py carries the
# lake's water on (dam_links: the lake's dead end -> the cell below the outlet). On the first try Munson Pond's outflow
# in the High Peaks (drawn through on live) had no line: the creek into the pond was kept, the one out of it wasn't,
# and 06_map.py's draw-through stopped at once on the kept creek's end beside it.
with rasterio.open(crossbox.fdir_path(REGION)) as _src:
    _T, _W = _src.transform, _src.width
_past = {_key(_T * (o_ % _W, o_ // _W)): _key(_T * (c_, r_)) for o_, (r_, c_) in crossbox.dam_links(REGION).items()}
_stack = list(np.flatnonzero(_kp))
while _stack:
    i = _stack.pop()
    _e = _key(_g[i].coords[-1])
    for j in _starts.get(_e, []) + _starts.get(_past.get(_e), []):
        if not _kp[j] and base[j]:
            _kp[j] = True
            _stack.append(j)
by_down = _kp & ~keep.to_numpy()
keep = pd.Series(_kp, index=s.index)
by_carried = keep & (s.area_km2 < MAP_MIN_KM2) & (full0 >= MAP_MIN_KM2)
by_nhd &= keep.to_numpy()
print(f"links under {MAP_MIN_KM2:g} km2 of their own kept on the water that reaches them from elsewhere (below a lake's "
      f"outlet, in from outside the map): {int(by_carried.sum())}, {s.length[by_carried].sum() / 1000:.1f} km; "
      f"{NHD_MIN_KM2:g}-{MAP_MIN_KM2:g} km2 kept as NHD maps them year-round or names them: {int(by_nhd.sum())}, "
      f"{s.length[by_nhd].sum() / 1000:.1f} km; below a kept creek: {int(by_down.sum())}, "
      f"{s.length[by_down].sum() / 1000:.1f} km ({len(set(_seam))} on from a creek kept in the next box)")
s = s[keep].copy()
# A link is cut where it crosses a lake's shore. pysheds draws one line per link between confluences, so a link that
# runs from a creek into a lake, or out of one, is part creek and part lake water. 05b_flow.py reads a reach as lying
# in a lake when half its length does, and the whole link took the lake's class or the creek's: Taggart Creek's last
# 161 m above Taggart Lake scored as lake (fish 29 against 99 above), 710 m of Indian Creek above Palisades Reservoir
# too, and over the 12 maps 352 km of creek read as lake and 339 km of lake water as creek (2026-11-21). Each link is
# now cut at the shores of the lakes a reach can lie in (flowlib.lake_water: the outlines 05b_flow.py reads, from
# 05d_lakes.py, which run_mid.sh runs before this step), so every reach is creek or lake. A stretch under
# LAKE_PIECE_M on one side of a shore stays with its neighbour (a line clipping a point or a cove). A piece keeps its
# link's place on the map (the floor above is the link's), and is measured on its own cells like any link.
from flowlib import lake_water, cut_at_shores, cut_below_lakes, carried_lake_km2, lake_water_km2, LAKE_NEAR_M
_lakes = lake_water(REGION)
_pieces, _src, _wet = cut_at_shores(s.geometry.values, _lakes)
print(f"links cut at lake shores: {len(_pieces) - len(s)} cuts on {int((pd.Series(_src).value_counts() > 1).sum())} "
      f"of {len(s)} links")
# The first LAKE_NEAR_M (200 m, 650 ft) below a lake is a reach of its own (flowlib.cut_below_lakes). A lake's outlet
# runs at the temperature of its surface and the warmth fades fast below it, and a reach is scored on one water
# temperature, the mean along it: a reach that started at a pond and ran on for half a mile read as a cool creek, its
# outlet's warmth averaged away (watertemp.py; at the 19 measured outlet sites on the Adirondack maps the reach read
# 7.9 F too cool, 2026-11-22). Each creek is cut where it has run that far from the lake, along the channel the lake's
# water takes (flowlib.below_lake, as the water-temperature term finds it), where the lake term there is 0.5 or more
# (watertemp.lake_share: half the water or more through the lake, less on rivers of 50 to 500 km2, none beyond; the
# measured warmth is at outlets of mostly lake water) and neither piece would be under LAKE_PIECE_M. The cut is for the
# water temperature alone, so the pieces keep the line's gradient and NHD class (below), and 05b_flow.py gives the
# first the flow evidence of the rest of its line (cut_sid): measured on 200 m alone, a step just below the shore (a
# dam, a cascade) read as a steep creek, the vote's three points could fall on the lake's own line, and the model's
# natural flow, which leaves the lake's water out, read the first stretch drier than the creek below it (all 12 maps,
# 2026-11-22: a brook below a pond in north-east Connecticut "usually flows" -> "mostly dry", Big Tujunga Creek below
# its dam "year-round" -> "seasonal"). Everything else is measured on each piece's own cells, like any link.
from watertemp import lake_share
_shore = np.array(_pieces, dtype=object)
_own = [shapely.Point(g.coords[-2] if len(g.coords) >= 2 else g.coords[0]) for g in _shore]
_full = sample(area, _own) + sample(carried_grid, _own)
_carried_lake = sample(carried_lake_km2(REGION).reshape(area.shape), _own)
_lake_km2 = np.minimum(lake_water_km2(_shore, _carried_lake, _full - _carried_lake, _wet), _full)
def _mostly_lake(ii, pts):     # the line's lake water (it takes none on along the line) against the drainage at the mark
    full = sample(area, pts) + sample(carried_grid, pts)
    return np.nan_to_num(lake_share(full - np.minimum(_lake_km2[ii], full), full), nan=0.0) >= 0.5
_pieces, _from, _wet = cut_below_lakes(_shore, _lake_km2, _wet, _lakes, keep=_mostly_lake)
_from = np.asarray(_from, int)
_src = [_src[k] for k in _from]
_cut = pd.Series(_from).duplicated(keep=False).to_numpy()          # both pieces of a line cut below a lake
_first = pd.Series(_from).duplicated(keep="last").to_numpy()       # the upper one
s = gpd.GeoDataFrame(s.drop(columns="geometry").iloc[_src].reset_index(drop=True), geometry=_pieces, crs=CRS)
own_end = gpd.GeoSeries([shapely.Point(g.coords[-2] if len(g.coords) >= 2 else g.coords[0]) for g in s.geometry],
                        index=s.index, crs=CRS)
starts = gpd.GeoSeries([shapely.Point(g.coords[0]) for g in s.geometry], index=s.index, crs=CRS)
mid = gpd.GeoSeries([vert(g, 0.5) for g in s.geometry], index=s.index, crs=CRS)
s["area_km2"] = sample(area, own_end).round(2)
# each piece's drainage with the water that reaches it from elsewhere (the floor's `carried`, on the piece's own cells)
full_km2 = s["area_km2"].to_numpy(float) + sample(carried_grid, own_end)
in_water = np.array(_wet, bool)
s["order"] = sample(strahler, mid)
s["elev_m"] = sample(dem, mid).round(0)
s["len_m"] = s.length.round(0)
s["gradient_pct"] = ((sample(dem, starts) - sample(dem, own_end)) / s.length * 100).clip(lower=0).round(1)
if _cut.any():           # the two pieces of a line cut below a lake keep the line's gradient (above)
    _g = _shore[_from[_cut]]
    _own = s.gradient_pct.to_numpy(float)
    s.loc[_cut, "gradient_pct"] = np.clip((sample(dem, [shapely.Point(g.coords[0]) for g in _g])
                                           - sample(dem, [shapely.Point(g.coords[-2]) for g in _g]))
                                          / shapely.length(_g) * 100, 0, None).round(1)
    print(f"creek lines cut {LAKE_NEAR_M:g} m below a lake: {int(_first.sum())} ({s.length[_first].sum() / 1000:.1f} km in "
          f"the first pieces); both keep the line's gradient, where the first piece's own would be over 8 % on "
          f"{int((_own[_first] > 8).sum())} (the line's: {int((s.gradient_pct.to_numpy(float)[_first] > 8).sum())})")
else:
    print(f"creek lines cut {LAKE_NEAR_M:g} m below a lake: 0")
s["road_m"] = mid.distance(road_u).round(0)
s["trail_m"] = mid.distance(trail_u).round(0)
pts3 = vertices3(s.geometry, s.index)
nhd_k = nhd[["gnis_name", "flow", "geometry"]].reset_index(drop=True)
s["name"] = vote(nhd_k, "gnis_name")
s["flow"] = vote(nhd_k, "flow").fillna("unmapped")
if _cut.any():           # the two pieces of a line cut below a lake keep the line's NHD class (above)
    _lp = [gpd.GeoDataFrame(geometry=[vert(g, f) for g in _shore[_from[_cut]]], index=s.index[_cut], crs=CRS)
           for f in (0.25, 0.5, 0.75)]
    s.loc[_cut, "flow"] = vote(nhd_k, "flow", pts=_lp).fillna("unmapped").values
osm_wp = f"{RAW}/osm_waterways.gpkg"    # OSM named rivers and streams, cached a week
if not os.path.exists(osm_wp) or time.time() - os.path.getmtime(osm_wp) > 7 * 86400:
    from geomatch import overpass
    import netfetch      # when Overpass can't be reached, the older download stays (a dated NOTE)
    def osm_names():
        w0, s0, e0, n0 = gpd.GeoSeries([shapely.box(*REGIONS[REGION]["bbox"])], crs=CRS).to_crs(4326).total_bounds
        els = [e for e in overpass(f'[out:json][timeout:600];way["waterway"~"^(river|stream)$"]["name"]'
                                   f'({s0:.5f},{w0:.5f},{n0:.5f},{e0:.5f});out geom;') if len(e.get("geometry") or []) >= 2]
        if els:
            gpd.GeoDataFrame({"name": [e["tags"]["name"] for e in els]}, crs=4326,
                             geometry=[shapely.LineString([(q["lon"], q["lat"]) for q in e["geometry"]]) for e in els]
                             ).to_crs(CRS).to_file(osm_wp + ".tmp.gpkg", driver="GPKG")
            os.replace(osm_wp + ".tmp.gpkg", osm_wp)
    netfetch.keep_old(osm_wp, osm_names, f"OSM stream names ({REGION})")
if os.path.exists(osm_wp):
    nhd_named = s["name"].notna().sum()
    s["name"] = s["name"].fillna(vote(gpd.read_file(osm_wp).to_crs(CRS), "name"))
    print(f"names: NHD {nhd_named}, OpenStreetMap {s['name'].notna().sum() - nhd_named} more, of {len(s)} links")

# A reach between two reaches of one river (its largest upstream reach and the reach below, passing over unnamed reaches)
# is that river, if the vote gave it no name or the name of a much smaller stream: every other reach of that name within
# 3 km drains under half as much. Where a creek comes in, NHD draws the creek's line out to the river's centreline, and
# on a short reach two of the vote's three points can lie nearest it: the Snake River between Little Red Creek's and
# Station Creek's mouths took their names (3,321 and 3,242 km2), Castaic Creek's the Santa Clara River below it, and
# creek profiles read the river's drainage at the mouth. Streams of about the same size keep the vote (forks, lakes where
# two rivers meet, spelling variants). Decided once, from the vote's names, so no reach is renamed back and forth.
geoms = s.geometry.values
end_key = lambda c: (round(c[0], 1), round(c[1], 1))
ends = {}
for i, g in enumerate(geoms):
    ends.setdefault(end_key(g.coords[-1]), []).append(i)
# A lake ends its paths at its outlet (03b_stitch.py), and the creek below starts in the next cell, so its first reach
# has no reach running into it: the lake's last reach ends one cell short. For the names, that reach counts as running
# into it (a reach end within a cell and a half of the start, where no reach starts): without it the river's first
# stretch below a lake kept whatever the vote gave it, often nothing (Richland Creek's 300 m below Lake Junaluska),
# since the rule below needs a reach above and one below. Unnamed creek reaches carrying 100+ km2: 251 -> 232 over
# the 12 maps. Not where the lake's water goes on from a cell further off: below Palisades Dam crossbox puts it in at
# NHD's cell, 480 m from the lake's last reach, and the Snake's first 580 m keeps no name.
_starts = {end_key(g.coords[0]) for g in geoms}
_end_tree = shapely.STRtree(shapely.points([g.coords[-1][:2] for g in geoms]))
def donors_of(i):
    """The reaches running into reach i: those ending at its start, else a lake's last reach ending a cell short."""
    d = ends.get(end_key(geoms[i].coords[0]), [])
    if not d:
        d = [int(j) for j in _end_tree.query(shapely.Point(geoms[i].coords[0][:2]), predicate="dwithin", distance=1.5 * RES)
             if j != i and end_key(geoms[j].coords[-1]) not in _starts]
    return d
km2 = full_km2      # sizes are compared with the water carried past dams (since 2026-11-21: below a dam a river's own
                    # count starts again near nothing, and on it the main stem above a junction could be a side creek)
voted = s["name"].to_numpy(object)
main_up, down = np.full(len(s), -1), np.full(len(s), -1)
for i, g in enumerate(geoms):
    donors = donors_of(i)
    if donors:
        main_up[i] = max(donors, key=lambda j: km2[j])
    down[donors] = i
def named_along(i, ptr, steps=20):
    """The vote's name of the first named reach from reach i along ptr (upstream main stem, or downstream)."""
    for _ in range(steps):
        i = ptr[i]
        if i < 0:
            return None
        if isinstance(voted[i], str):
            return voted[i]
    return None
reach_tree, renamed = shapely.STRtree(geoms), {}
for i in range(len(s)):
    y = named_along(i, main_up) if main_up[i] >= 0 and down[i] >= 0 else None
    if y is None or y == voted[i] or y != named_along(i, down):
        continue
    if isinstance(voted[i], str):
        same = [j for j in reach_tree.query(geoms[i].buffer(3000)) if j != i and voted[j] == voted[i]]
        if same and km2[same].max() >= 0.5 * km2[i]:
            continue
    renamed[i] = y
s["name"] = [renamed.get(i, n) for i, n in enumerate(voted)]
print(f"names along rivers: {len(renamed)} reaches take the river's name "
      f"({sum(isinstance(voted[i], str) for i in renamed)} had another stream's, the rest none)")

# A small reach beside a river carries the river's name only if it is a channel of that river. The vote names a reach
# after the nearest NHD line at two of three points, and a creek's last stretch often runs along the river before it
# joins: Cottonwood Creek's last 1.4 km (203 km2) read "Snake River" beside the Snake's 4,250, and so did the ends of
# Taylor, Pritchard and Tag Alder creeks and of dozens of unnamed creeks. And D8 sends a split river's water down one
# arm, so its other arm is a reach of a few km2 with the river's name (a side creek at Lower Slide Lake's head read
# "Gros Ventre River", 2 km2). Over the 12 maps about 720 reaches (2026-11-21). A reach is looked at when reaches of its
# name that drain SIDE_RATIO times as much, and SIDE_RIVER_KM2 or more, run within SIDE_NEAR_M along SIDE_ALONG of its
# length (the river is beside it), and it isn't lake water. Then, up its main stem:
# - a reach of another name within 6 reaches, not much smaller than it: it is that creek's lower end, and takes its name;
# - else, where the stem up to its head lies along NHD's lines of the river (SIDE_ON_RIVER of its length within 150 m):
#   a side channel of the river. It keeps the name and is marked (side_of, the river reach beside it in side_sid, that
#   reach's drainage in river_km2): 05b_flow.py gives it the river's flow evidence, scoring.py the river's size, and
#   the maps call it a side channel;
# - else it is the lower end of a creek with no name, and has none.
# Decided on the names as they stand here, so nothing is renamed back and forth.
names0 = s["name"].to_numpy(object)
is_named = np.array([isinstance(n, str) for n in names0])
# From a reach of MAP_MIN_KM2 or more the stem climbs reaches of that size only: a creek drawn under it because NHD names
# it or maps it year-round can end at a side channel's head, and the stem then ran up that creek, away from the river (4
# of NE Connecticut's 13 side channels lost the river's size, flow and trout records that way, 2026-11-22).
stem_up = np.full(len(s), -1)                 # the biggest reach running in, by full drainage (main_up above)
for i, g in enumerate(geoms):
    donors = [j for j in donors_of(i) if full_km2[j] >= MAP_MIN_KM2 or full_km2[i] < MAP_MIN_KM2]
    if donors:
        stem_up[i] = max(donors, key=lambda j: full_km2[j])
big = np.flatnonzero(is_named & (full_km2 >= SIDE_RIVER_KM2) & ~in_water)
big_tree = shapely.STRtree(geoms[big]) if len(big) else None
_zone = {}
def river_zone(river):
    """150 m around NHD's lines of that name (the river's own lines, its braids included)."""
    if river not in _zone:
        ln = nhd_k.geometry[nhd_k.gnis_name.eq(river).values]
        _zone[river] = shapely.union_all(ln.values).buffer(150) if len(ln) else None
    return _zone[river]
new_name, side = {}, {}
for i in (np.flatnonzero(is_named & ~in_water) if big_tree is not None else []):
    near = big[big_tree.query(geoms[i].buffer(SIDE_NEAR_M))]
    sib = near[(names0[near] == names0[i]) & (full_km2[near] >= SIDE_RATIO * full_km2[i])]
    if not len(sib):
        continue
    beside = shapely.union_all(shapely.buffer(geoms[sib], SIDE_NEAR_M))
    if geoms[i].intersection(beside).length < SIDE_ALONG * geoms[i].length:
        continue
    j, other = stem_up[i], None
    for _ in range(6):
        if j < 0 or (names0[j] == names0[i] and full_km2[j] >= SIDE_RATIO * full_km2[i]):
            break                                 # the head, or the river itself comes in above
        if isinstance(names0[j], str) and names0[j] != names0[i]:
            other = j
            break
        j = stem_up[j]
    if other is not None and full_km2[i] <= 3 * full_km2[other]:
        new_name[i] = names0[other]
        continue
    zone, tot, inn, j = river_zone(names0[i]), 0.0, 0.0, i
    for _ in range(30):
        if j < 0:
            break
        tot += geoms[j].length
        inn += geoms[j].intersection(zone).length if zone is not None else 0.0
        j = stem_up[j]
    if inn >= SIDE_ON_RIVER * tot:
        side[i] = sib[int(np.argmax(full_km2[sib]))]
    else:
        new_name[i] = None
s["name"] = [new_name.get(i, n) for i, n in enumerate(names0)]
s["side_of"] = [names0[i] if i in side else None for i in range(len(s))]
s["side_row"] = [side.get(i, -1) for i in range(len(s))]        # the river reach beside it (its row; a sid below)
s["river_km2"] = [round(float(full_km2[side[i]]), 2) if i in side else np.nan for i in range(len(s))]
s["cut_row"] = np.where(_first, np.arange(len(s)) + 1, -1)      # a first stretch below a lake: the rest of its line
print(f"small reaches named after the river beside them: {sum(v is not None for v in new_name.values())} take the name of "
      f"the creek they end, {sum(v is None for v in new_name.values())} end an unnamed creek and lose the name, "
      f"{len(side)} are side channels of the river")

# Fishability score 0-100 (heuristic, tuned for SoCal trout water)
def band(x, lo, hi, soft):  # 1 inside [lo,hi], linear falloff over `soft`
    return np.clip(1 - np.clip(np.maximum(lo - x, x - hi), 0, None) / soft, 0, 1)
water = s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05, "other": 0.3})
size = np.clip(np.log10(s.area_km2) / np.log10(50), 0, 1)        # 1 km2 -> 0, 50+ km2 -> 1
cold = band(s.elev_m, *ELEV_BAND) if ELEV_BAND else 1.0           # trout-friendly elevation (LA; first pass only)
grad = band(s.gradient_pct, 1, 8, 10)                             # pool-riffle to step-pool
remote = np.clip(s.road_m / 2000, 0, 1)                           # 2 km+ from a public road
s["fish_score"] = (100 * water * (0.35 * size + 0.25 * cold + 0.15 * grad + 0.25 * remote)).round(0)

# ---- drop candidates ----
# A drop takes the name of the reach its top cell is on. The nearest NHD line can be the river's where a creek comes in
# (drops on Little Cottonwood and Blue Bell creeks were "Snake River", Pigpen Falls "Lick Log Creek"); on an unnamed
# reach, or a channel too small to be one, the nearest NHD line's within 80 m, as before. The junction cell at a reach's
# end belongs to the reach below (vertices sit on cell corners: rounded, as in 12_profiles.py).
reach_at = {}
for i, g in enumerate(geoms):
    v = np.asarray(g.coords)[:-1]
    vc, vr = inv * (v[:, 0], v[:, 1])
    for k in np.rint(vr).astype(int) * dem.shape[1] + np.rint(vc).astype(int):
        reach_at[int(k)] = i
reach_name = s["name"].to_numpy(object)
on_reach = [reach_name[reach_at[t]] if t in reach_at else None for t in kp.top_idx.astype(int)]
nearest_line = gpd.sjoin_nearest(kp[["geometry"]], nhd[["gnis_name", "geometry"]], max_distance=80,
                                 how="left").groupby(level=0).first().gnis_name
kp["stream"] = [o if isinstance(o, str) else n for o, n in zip(on_reach, nearest_line.reindex(kp.index))]
kp["flow"] = gpd.sjoin_nearest(kp[["geometry"]], nhd[["flow", "geometry"]], max_distance=80,
                               how="left").groupby(level=0).first().flow.fillna("unmapped")
kp["road_m"] = kp.distance(road_u).round(0)
kp["trail_m"] = kp.distance(trail_u).round(0)
kp["known_fall_m"] = kp.distance(known_falls.geometry.union_all()).round(0) if len(known_falls) else np.nan
kp["dam_m"] = kp.distance(dams.union_all()).round(0) if len(dams) else np.inf
# A drop that starts at the outlet of a dammed lake is its dam, wherever the dam's point is mapped. The drop detectors
# count the water carried past dams since 2026-11-21 (04_knickpoints.py), so they scan the river from the dam on, and
# found the dams themselves: Buford Dam as a 49.5 m "waterfall-like step" on the Chattahoochee (its mapped point is
# 506 m off), Carters Dam as a 115 m cascade, Five Falls and Hinckley dams. A dammed lake is a reservoir or a lake with
# a dam on its shore (05d_lakes.py's `regulated`); the drop is its dam where the top lies within DAM_LAKE_M of the
# lake's outline and at its level (3 m below to 6 m above: the crest) and the step ends 3 m or more below that level.
# A fall where a creek comes into a reservoir ends at the lake's level and stays a fall (the Tallulah's above
# Tallulah Falls Lake).
DAM_LAKE_M = 100
kp["dam_lake"] = False
_lakes_p = f"{SHARED_DERIVED}/lakes.gpkg"
if os.path.exists(_lakes_p) and len(kp):
    _lk = gpd.read_file(_lakes_p).to_crs(CRS)
    _lk = _lk[(_lk.regulated.fillna(False).astype(bool) | _lk.ftype.eq("reservoir")) & _lk.elev_m.notna()]
    if len(_lk):
        _j = gpd.sjoin_nearest(kp[["elev_m", "drop_m", "geometry"]], _lk[["elev_m", "geometry"]].rename(columns={"elev_m": "lake_m"}),
                               max_distance=DAM_LAKE_M, how="inner")
        _j = _j[~_j.index.duplicated()]
        _at = (_j.elev_m >= _j.lake_m - 3) & (_j.elev_m <= _j.lake_m + 6) & (_j.elev_m - _j.drop_m <= _j.lake_m - 3)
        kp.loc[_j.index[_at.values], "dam_lake"] = True
# A road fakes a drop where it crosses the channel: an embankment over a culvert, or a bridge deck the DEM kept, makes
# the lip, so the step's top sits on it. One that only runs beside the creek does not, and gorges are often walled by
# one: with a drivable road within 40 m of the top as the test, Texas Falls, Huntington Gorge and Sterling Falls Gorge
# (VT) and Amicalola Falls (GA) were all set aside as artifacts (155 drops in all). So the test is a drivable road
# crossing the DEM channel within 40 m of the top. Not along the whole step: a road bridge below a fall doesn't make
# it (testing to the pool flagged 19 more, among them a 101 m fall in the Santa Ana Mountains over a highway bridge).
step = shapely.linestrings(np.stack([np.c_[kp.geometry.x, kp.geometry.y], np.c_[kp.pool_x, kp.pool_y]], axis=1))
zone = shapely.buffer(kp.geometry.values, 40)
chan_g, road_g = streams.geometry.values, drivable.geometry.values
chan_t, road_t = shapely.STRtree(chan_g), shapely.STRtree(road_g)
def crosses(z):
    rd = road_g[road_t.query(z)]
    if not len(rd):
        return False
    ch = shapely.intersection(shapely.union_all(chan_g[chan_t.query(z)]), z)
    return not ch.is_empty and bool(shapely.intersects(rd, ch).any())
kp["road_crossing"] = [crosses(z) for z in zone]
# A mapped waterfall on the step itself (within 50 m of its top-to-pool line: room for a hand-placed point and the DEM
# channel's offset) is that drop, whatever a road or fill suggests; 14 such were labelled artifacts. The nearest
# artifact beyond that was 88 m off. Up to 200 m from the top a mapped fall still names a drop, but no longer outranks
# the artifact tests.
# Only precisely placed falls count here (02f_known_falls.py's `precise`: OSM, NHD, CDFW and guidebook
# GPS points on the fall); USGS GNIS placements and points placed from directions can be 100 m or more off.
on_fall = known_falls[known_falls.precise]
kp["fall_on_step"] = (shapely.distance(step, on_fall.geometry.union_all()) <= 50) if len(on_fall) else False
kp["status"] = np.select(
    [(kp.dam_m < 250) | kp.dam_lake, kp.fall_on_step, kp.road_crossing | kp.artifact_risk, kp.known_fall_m < 200,
     kp.kind == "waterfall-like step", kp.kind == "cascade / knickpoint",
     kp.kind == "short fall / pool (big creek)"],
    ["dam / weir", "matches mapped waterfall", "likely DEM artifact", "matches mapped waterfall",
     "unmapped waterfall-like step", "unmapped cascade", "unmapped short fall (big creek)"], "steep reach")
# the big-creek pass is meant for fishable water: keep it to NHD perennial channels
kp = kp[(kp["pass"] == 1) | (kp.flow == "perennial")]
kp = kp.sort_values("drop_m", ascending=False)

ll = lambda g: g.to_crs(4326)
os_ = OUT
s_ll, kp_ll = ll(s), ll(kp)
pool = gpd.GeoSeries(gpd.points_from_xy(kp.pool_x, kp.pool_y), crs=CRS).to_crs(4326)
kp_ll["pool_lat"], kp_ll["pool_lon"] = pool.y.values.round(6), pool.x.values.round(6)
kp_ll["lat"], kp_ll["lon"] = kp_ll.geometry.y.round(6), kp_ll.geometry.x.round(6)

cols = ["status", "kind", "pass", "stream", "flow", "drop_m", "excess_drop_m", "pool_depth_m", "run_m", "step_slope", "max_slope", "slope_above",
        "slope_below", "knick_ratio", "area_km2", "elev_m",
        "road_m", "trail_m", "known_fall_m", "lat", "lon", "pool_lat", "pool_lon"]
kp_ll.insert(0, "region", LABEL)
s_ll.insert(0, "region", LABEL)
# stable keys so later scripts (08-11) can attach attributes
s_ll.insert(0, "sid", [f"{REGION}:s{i}" for i in range(len(s_ll))])
s_ll["side_sid"] = [f"{REGION}:s{j}" if j >= 0 else None for j in s_ll.pop("side_row")]
s_ll["cut_sid"] = [f"{REGION}:s{j}" if j >= 0 else None for j in s_ll.pop("cut_row")]
kp_ll.insert(0, "did", [f"{REGION}:d{i}" for i in range(len(kp_ll))])
cols = ["did", "region"] + cols
kp_ll[cols].to_csv(f"{os_}/waterfall_candidates.csv", index=False)
s_out = s_ll.assign(lat=s_ll.geometry.interpolate(0.5, normalized=True).y.round(6),
                    lon=s_ll.geometry.interpolate(0.5, normalized=True).x.round(6))
s_out.sort_values("fish_score", ascending=False)[
    ["sid", "region", "name", "flow", "fish_score", "area_km2", "order", "elev_m", "gradient_pct", "len_m", "road_m", "trail_m", "lat", "lon"]
].to_csv(f"{os_}/stream_reaches_ranked.csv", index=False)
s_ll.to_file(f"{os_}/streams_scored.gpkg")
kp_ll.drop(columns=["top_idx", "base_idx"]).to_file(f"{os_}/waterfall_candidates.gpkg")

# light copies of trails + mapped falls for the combined map
t_ll = areaclip.cut(trails).to_crs(4326)
t_ll = t_ll[~t_ll.is_empty].assign(geometry=shapely.set_precision(t_ll.geometry.simplify(0.0001).values, 1e-5))
t_ll.assign(name=t_ll["name"].fillna("trail"))[["name", "geometry"]].to_file(f"{os_}/trails.gpkg")
known_falls[known_falls.within(range_box) & areaclip.inside(known_falls.geometry.values)].to_crs(4326).to_file(
    f"{os_}/known_falls.gpkg")

# ---- hillshade overlay (warped to web mercator) ----
def hillshade(z, az=315, alt=45):
    dy, dx = np.gradient(z, RES)
    slope = np.arctan(np.hypot(dx, dy)); aspect = np.arctan2(-dx, dy)
    a, b = np.radians(360 - az + 90), np.radians(alt)
    return np.clip(np.sin(b) * np.cos(slope) + np.cos(b) * np.sin(slope) * np.cos(a - aspect), 0, 1)
hs = hillshade(dem.astype("float64"))
dst_t, w, h = calculate_default_transform(CRS, "EPSG:3857", dem.shape[1], dem.shape[0], *dem_src.bounds,
                                          resolution=30)
hs_m = np.zeros((h, w), "float32"); dem_m = np.zeros((h, w), "float32")
reproject(hs.astype("float32"), hs_m, src_transform=dem_src.transform, src_crs=CRS, dst_transform=dst_t,
          dst_crs="EPSG:3857", resampling=Resampling.bilinear, dst_nodata=0)
reproject(dem, dem_m, src_transform=dem_src.transform, src_crs=CRS, dst_transform=dst_t,
          dst_crs="EPSG:3857", resampling=Resampling.bilinear, dst_nodata=0)
tint = matplotlib.colormaps["terrain"](colors.Normalize(200, 3100)(dem_m))[..., :3]
rgb = (tint * (0.35 + 0.65 * hs_m[..., None])) * 255
alpha = np.where(dem_m > 0, 255, 0)
if areaclip.outline() is not None:      # an area that stops at a state line: no terrain shading past it
    alpha[features.geometry_mask([areaclip.outline("EPSG:3857")], (h, w), dst_t)] = 0
Image.fromarray(np.dstack([rgb, alpha]).astype("uint8")).quantize(192, method=Image.Quantize.FASTOCTREE).save(
    f"{os_}/hillshade.png", optimize=True)
from pyproj import Transformer
tb = Transformer.from_crs(3857, 4326, always_xy=True)
west, north = tb.transform(dst_t.c, dst_t.f)
east, south = tb.transform(dst_t.c + w * dst_t.a, dst_t.f + h * dst_t.e)
json.dump(dict(south=south, west=west, north=north, east=east), open(f"{os_}/hillshade_bounds.json", "w"))

print(LABEL, "| streams", len(s), "| perennial", int((s.flow == "perennial").sum()))
print(kp.status.value_counts().to_string())
print("\nTop reaches:\n", s_out.sort_values("fish_score", ascending=False)
      .drop_duplicates("name").head(12)[["name", "flow", "fish_score", "area_km2", "elev_m", "gradient_pct", "road_m"]].to_string())
print("\nTop unmapped steps:\n", kp[kp.status == "unmapped waterfall-like step"].head(10)[
    ["stream", "flow", "drop_m", "run_m", "area_km2", "elev_m", "road_m", "trail_m"]].to_string())
