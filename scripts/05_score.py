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
                    # ... and down to STREAM_KM2 (config.py: 03b_stitch.py's channel start) where NHD maps the creek
                    # year-round or names it
OUTFLOW_MIN_KM2 = 0.25   # ... and a lake's outflow down to the first creek it meets, from this much water through the lake

dem_src = rasterio.open(f"{RAW}/dem_10m.tif")
dem = dem_src.read(1)
area = rasterio.open(f"{DERIVED}/area_km2.tif").read(1)
# The water behind lakes' outlets (03b_stitch.py, since 2026-11-22 it runs on at the outlet: area_km2.tif counts it).
# A reach's area_km2 stays its own ground below the lakes, as before; its full drainage counts the lakes' water too
# (05c_drainages.py's area_full_km2), and the size floor below goes by that.
held = (rasterio.open(f"{DERIVED}/held_km2.tif").read(1) if os.path.exists(f"{DERIVED}/held_km2.tif")
        else np.zeros_like(area))
area_own = area - held
strahler = rasterio.open(f"{DERIVED}/strahler.tif").read(1)
inv = ~dem_src.transform
def sample(arr, geoms):
    cols, rows = inv * (np.array([g.x for g in geoms]), np.array([g.y for g in geoms]))
    return arr[np.clip(rows.astype(int), 0, arr.shape[0] - 1), np.clip(cols.astype(int), 0, arr.shape[1] - 1)]

streams = gpd.read_file(f"{DERIVED}/dem_streams.gpkg")
# low_channel: a line 03b_stitch.py laid along an NHD named or year-round line from where that line starts, upstream of
# its channel start at STREAM_KM2 (low_channels); it ends on the stream it runs into, which isn't cut there (none in a
# routing made before 2026-11-24)
streams["low_channel"] = streams["low_channel"].fillna(0).astype(int) if "low_channel" in streams else 0
# A river that comes in from outside the map (crossbox.py's "outside" water: over the outer edge, or through a
# reservoir the edge cuts and on below its dam) starts its line where its water goes in, not where 0.25 km2 has
# gathered inside the map: 03b_stitch.py's streams count only the map's own cells, so a river's first few hundred
# metres in the map had no link, and 06_map.py drew them through as lines with no reach of their own (65 mi at the
# edges and 5.7 mi below dams, on the 12 maps of 2026-11-22: the Little Tennessee below Chilhowee Dam, the
# Chattahoochee below Buford Dam). The D8 path from that cell to the first line is a link of its own, on cell corners
# as 03b's lines are (crossbox.lead_ins).
# So is water carried across an edge two boxes share (crossbox.py's "edge" links, STREAM_KM2 or more) where this box's
# routing has no line at the cell it comes in at: a creek's own water runs on across the edge on 03b's lines, but water
# carried in from outside the map or past a dam isn't in the next box's area, so its line started again only where
# 0.25 km2 of that box's own had gathered (2026-11-23: a lead-in from outside ran to its box's rim and stopped, Still
# Brook in central Vermont and a creek into the Smokies' le_conte box; 5 such crossings on the 12 maps, 3 of them in
# Lake Champlain, where a lead-in stops).
# So is the way on from a lake that still ends its water in a pit at its outlet (03b_stitch.py: no outflow line in
# NHD, one the terrain refuses, a way out leading back), where crossbox.py puts the lake's water in below it ("dam", and
# "pond" for a pond NHDPlus has no line for): 06_map.py drew those through too.
import crossbox
# The lead-ins run to the first line of the STREAM_KM2 network, as without the lines laid lower along NHD's named or
# year-round lines (low_channel); such a line that runs onto a lead-in's way ends where it meets it, as on a stream.
# Run to the first line of either, a pond's way out in NE Connecticut stopped on a new line 14 m below the pond, and
# Bucks Horn Brook's 591 m reach below it went with that line (first try, 2026-11-25)
_reg = streams.low_channel.to_numpy() == 0
_leads = crossbox.lead_ins(REGION, streams.geometry.values[_reg],
                           [e for e in crossbox.inflows(REGION, through_dams=True)
                            if e[3] == "outside" or (e[4] == "edge" and e[2] >= STREAM_KM2) or e[4] in ("dam", "pond")])
print(f"lines from where a river from outside the map, water carried across a box edge or a lake's pit goes in to its "
      f"first link: {len(_leads)}, {sum(g.length for g in _leads) / 1000:.1f} km")
if len(_leads) and not _reg.all():
    _on_lead = {(round(x, 1), round(y, 1)) for g in _leads for x, y, *_ in g.coords}
    _gl, _keep_l, _n_met = list(streams.geometry.values), np.ones(len(streams), bool), 0
    for i in np.flatnonzero(~_reg):
        _cs = list(_gl[i].coords)
        k = next((k for k, c in enumerate(_cs) if (round(c[0], 1), round(c[1], 1)) in _on_lead), None)
        if k is not None:
            _n_met += 1
            if k >= 1:
                _gl[i] = shapely.LineString(_cs[:k + 1])
            else:
                _keep_l[i] = False      # it starts on a lead-in's way: no line of its own
    streams = gpd.GeoDataFrame(streams.drop(columns="geometry"), geometry=_gl, crs=CRS)[_keep_l].reset_index(drop=True)
    print(f"lines laid lower along NHD's lines that run onto a lead-in's way, ended where they meet it: {_n_met} "
          f"({int((~_keep_l).sum())} starting on one, left out)")
streams = pd.concat([streams, gpd.GeoDataFrame(geometry=_leads, crs=CRS)], ignore_index=True)
streams["low_channel"] = streams.low_channel.fillna(0).astype(int)
# A lake that passes its water on at its outlet (03b_stitch.py's "wet" outlets, since 2026-11-23) used to end its links
# there in a pit; a link now runs on through it. Each link is cut at the outlet's corner, so every rule below judges the
# links as the pits ended them: the size floor on the water at a link's end, the sea test on its own share of sea-level
# cells (run on from the Tinicum impoundment's outlet into the Delaware's tidal flats, a link was 68 % sea and was dropped
# whole, with the 515 m of creek above the outlet), the names, and the drainages, which 05c_drainages.py still ends at the
# outlets (run on past Upper Ausable Lake's outlet, 600 m past its drawn shore, the link's last 612 m went with the
# creek below, and the lake's basin took its name from Stillwater Inlet). The piece above an outlet takes the cell
# before it as its own, as the link did.
_lo_w = f"{SHARED_DERIVED}/lake_outlets.json"
_wet_o = ({(int(q[0]), int(q[1])) for q in json.load(open(_lo_w)).get("wet", {}).get(REGION, [])}
          if os.path.exists(_lo_w) else set())
if _wet_o:
    _lines, _low, _n_out = [], [], 0
    for g_, lw_ in zip(streams.geometry.values, streams.low_channel.values):
        v_ = np.asarray(g_.coords)[:, :2]
        cc_, rr_ = inv * (v_[:, 0], v_[:, 1])
        at_ = [i for i in range(1, len(v_) - 1) if (int(np.rint(rr_[i])), int(np.rint(cc_[i]))) in _wet_o]
        last_ = 0
        for i in at_:
            _lines.append(shapely.LineString(v_[last_:i + 1]))
            last_ = i
            _n_out += 1
        _lines.append(shapely.LineString(v_[last_:]) if at_ else g_)
        _low += [lw_] * (len(at_) + 1)
    streams = gpd.GeoDataFrame({"low_channel": _low}, geometry=_lines, crs=CRS)
    print(f"links cut at the outlets of lakes that pass their water on: {_n_out}")
nhd = gpd.read_file(f"{RAW}/nhd_flowlines.gpkg")
nhd_pts = gpd.read_file(f"{RAW}/nhd_points.gpkg")
roads = gpd.read_file(f"{RAW}/osm_roads.gpkg")
trails = gpd.read_file(f"{RAW}/osm_trails.gpkg")
kp = pd.concat([gpd.read_file(f"{DERIVED}/knickpoints.gpkg").assign(**{"pass": 1}),
                gpd.read_file(f"{DERIVED}/knickpoints_bigcreek.gpkg")], ignore_index=True)
kp = gpd.GeoDataFrame(kp, crs=CRS)
kp = kp[areaclip.inside(kp.geometry.values)]    # an area that stops at a state line: drops past it go (areaclip.py)
kp = kp[crossbox.owns(REGION, kp.geometry.x.values, kp.geometry.y.values)]   # where a later box overlaps, it has them

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
# inside it, so each fall is drawn once (the lon/lat box each range used to take overlapped its neighbours'), and
# those just past the map's edge that another source puts inside it (02f_known_falls.py: home_lon, home_lat).
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
s["area_km2"] = sample(area_own, own_end).round(2)
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
# Under MAP_MIN_KM2 a creek is drawn down to STREAM_KM2 where NHD maps it year-round or names it (the vote below, on
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
# through its reservoirs are: a name it gives a built channel of the box, where its stream lines (FType 460) carry under
# BUILT_STREAM_SHARE of its length. On the first try 9.7 mi of LA's new lines were named after the California and Los
# Angeles aqueducts, the Gage and Riverside canals and flood-control channels (fish 0-9, 2026-11-22); NHD files 3 m of
# the West Branch California Aqueduct's 41 km as a stream line, which let 0.5 mi of it in while the test was "no stream
# line at all" (2026-11-23; the next name down on the 12 maps, Kimball Canal, has 12 % on stream lines, and real creeks
# with a channelized stretch 20 % and more). A stream line NHD names after a channel (a canyon's creek above its
# flood-control channel) is still read, and so are the paths of a river through its own water.
BUILT_FTYPES, BUILT_STREAM_SHARE = (336, 420, 428), 0.1
# A name whose generic term is an artificial channel's reads as a canal's too, whatever NHD's code for the line: NHD
# files old ditches as stream lines (The Zanja, Redlands' irrigation ditch; Magazine Ditch by Wilmington; Main Ditch at
# Tinicum: 2.0 mi drawn as floor creeks, fish 3-11, on 2026-11-23's maps). The generic term is the name's last word, or its first
# after "The" in Spanish names (Zanja Madre); Ditch Creek is a creek.
CHANNEL_WORDS = {"ditch", "canal", "zanja", "acequia", "flume", "aqueduct", "lateral"}
def channel_word(names):
    """Names whose generic term is an artificial channel's: the last word (Main Ditch, Kimball Canal), or the first
    after "The" (The Zanja, Acequia Madre)."""
    def is_ch(n):
        if not isinstance(n, str):
            return False
        w = [x for x in n.replace("-", " ").split() if x.lower() != "the"]
        return bool(w) and (w[-1].lower() in CHANNEL_WORDS or w[0].lower() in {"zanja", "acequia"})
    return names.map(is_ch).astype(bool)
def floor_lines(nl):
    """The NHD lines `nl` (gnis_name, ftype, flow, geometry, in metres) the floor reads: no built channel, nor a line
    named after one."""
    built = nl.ftype.isin(BUILT_FTYPES)
    length = nl.geometry.length
    share = length.where(nl.ftype.eq(460), 0.0).groupby(nl.gnis_name).sum() / length.groupby(nl.gnis_name).sum()
    built_name = {n for n in set(nl.gnis_name[built].dropna()) if share.get(n, 0.0) < BUILT_STREAM_SHARE}
    nl = nl[~built & ~nl.gnis_name.isin(built_name) & ~channel_word(nl.gnis_name)]
    return nl[["gnis_name", "flow", "fcode", "geometry"]].reset_index(drop=True)
# A link running out of a lake starts along NHD's artificial path through it (FCode 55800, which reads as the area's
# class: perennial outside LA). Where the routing splits the link inside the lake, that stretch is a link of its own,
# kept on that vote, and the creek below runs on from it (the continuation below), or the creek below is a link of its
# own, kept on its own NHD line; where it doesn't, the outflow link starts in the lake, and its 25/50/75 % vertices
# land part on the lake's path, part on the creek: neither vote holds. Since 03_hydrology.py routes a flat along NHD's
# lines (2026-11-23) a pond's water runs to its outlet in one link, and small lake outlets live had drawn went (Dunham
# Pond Brook in NE Connecticut, Howard Pond and a 4.7 acre pond in the High Peaks, a pond on Dime Creek in Jackson). So
# a link that starts in a lake of the map's lakes layer (05d_lakes.py's, any size) and isn't kept whole votes again on
# each part, whichever way the routing splits it: its first stretch along an artificial path through the lake (not one
# NHD maps as intermittent), and the creek from where it leaves the lake. Through a swamp or along a river's own water
# the first doesn't count: on the first try that kept 5 times as many links, 33 mi in NE Connecticut. Nor does it where
# NHD maps no creek below the lake (POND_ON_NHD of the rest of the link within 60 m of an NHD line): where the terrain
# leaves a pond away from NHD's outlet, the kept link and the creeks below it ran on where NHD has nothing (on the
# second try 7.7 of the 25.7 mi added, chains of up to 1.3 mi 4-16 % on NHD). (The outlines the reaches are cut at
# below, flowlib.lake_water, start at 8 ha: these ponds are 1.5-4 ha.)
POND_NEAR_M, POND_IN_LAKE, POND_ON_NHD = 20.0, 0.5, 0.5
def pond_stretches(geoms, ap, lakes, lines):
    """For each line, its first stretch from its upstream end with every vertex within POND_NEAR_M of a line of `ap`
    (3 vertices or more) and POND_IN_LAKE of its length in `lakes` (polygons), where POND_ON_NHD of the rest of the
    line (if 50 m or more) lies within 60 m of a line of `lines`; or None."""
    tree = shapely.STRtree(ap.geometry.values) if len(ap) else None
    lt = shapely.STRtree(lakes) if len(lakes) else None
    nt = shapely.STRtree(lines.geometry.values) if len(lines) else None
    out = []
    for g in geoms:
        c = np.asarray(g.coords)[:, :2]
        if tree is None or lt is None or len(c) < 3:
            out.append(None)
            continue
        near = np.zeros(len(c), bool)
        near[np.unique(tree.query(shapely.points(c), predicate="dwithin", distance=POND_NEAR_M)[0])] = True
        k = len(c) if near.all() else int(np.argmin(near))
        st = shapely.LineString(c[:k]) if k >= 3 else None
        if st is not None:
            lk = lt.query(st, predicate="intersects")
            if not len(lk) or st.intersection(shapely.union_all(lakes[lk])).length < POND_IN_LAKE * st.length:
                st = None
        if st is not None and k < len(c):
            rest = shapely.LineString(c[k - 1:])
            if rest.length >= 50:
                pts = shapely.line_interpolate_point(rest, np.arange(0.0, rest.length, 25.0))
                on = len(np.unique(nt.query(pts, predicate="dwithin", distance=60)[0])) / len(pts) if nt is not None else 0.0
                if on < POND_ON_NHD:
                    st = None
        out.append(st)
    return out
def creek_parts(geoms, lakes):
    """For each line that starts inside one of `lakes` (polygons) and leaves it: the line from the vertex before the
    first one outside (3 vertices or more), or None."""
    lt = shapely.STRtree(lakes) if len(lakes) else None
    out = []
    for g in geoms:
        c = np.asarray(g.coords)[:, :2]
        lk = lt.query(g, predicate="intersects") if lt is not None and len(c) >= 4 else []
        if not len(lk):
            out.append(None)
            continue
        inside = shapely.contains_xy(shapely.union_all(lakes[lk]), c[:, 0], c[:, 1])
        k = int(np.argmin(inside))
        out.append(shapely.LineString(c[k - 1:]) if inside[0] and not inside.all() and len(c) - k >= 2 else None)
    return out
# The vote reads a name at 3 vertices, and a creek whose terrain path wanders from NHD's line misses it: below Dunham
# Pond in NE Connecticut the path runs up to 85 m off Dunham Pond Brook, and the link's 25/50/75 % vertices read
# nothing, Dunham Pond Brook and an unnamed line (since 2026-11-23's routing; live's link, split higher, read the name
# at 2). So a link the vote doesn't keep reads its name along its length too: the NHD name within NAME_NEAR_M of
# NAME_SHARE of its points (every 25 m), less a name it shares with a stream
# SIDE_RATIO times bigger beside it (as nhd_says), and not where half the link runs within BESIDE_M of a line already
# kept: there the name is that line's, and the link a side-by-side piece of it (on the first try 59 of 292 links). The
# last NAME_END_M, where a link nears the stream it joins, doesn't count, and what's left must be NAME_MIN_M or more: on
# the second try short tributaries took the name of the creek they join. Read on a link's creek below a lake alone,
# names went to whole links from a short tail (Carson Brook, 6 % of its length), to braids of the Snake and the
# Independence River, to an irrigation ditch: Bautista Creek below Hog Lake in LA, whose link starts on an unmapped
# creek above the lake, isn't read so.
NAME_SHARE, NAME_NEAR_M, BESIDE_M, NAME_END_M, NAME_MIN_M = 0.5, 60.0, 30.0, 100.0, 200.0
PERENNIAL_SHARE = 1 / 3      # NHD perennial along this share of a piece's points raises it to perennial (never lowers)
# NHD's classes, driest first; "other" (a line NHD gives no flow class) ranks as "unmapped"
CLASS_RANK = {"unmapped": 0, "other": 0, "ephemeral": 1, "intermittent": 2, "perennial": 3}
MAIN_NEAR_M, MAIN_SHARE = 150.0, 0.6     # an unnamed piece takes its main stem's name where NHD's line of it runs so near
def beside(geoms, drawn):
    """For each line, whether half its points (every 25 m) or more lie within BESIDE_M of a line of `drawn`."""
    tree = shapely.STRtree(drawn) if len(drawn) else None
    out = np.zeros(len(geoms), bool)
    for n_, g in enumerate(geoms):
        if tree is None:
            break
        pts = shapely.line_interpolate_point(g, np.arange(0.0, g.length + 1e-6, 25.0))
        hit = tree.query(pts, predicate="dwithin", distance=BESIDE_M)
        out[n_] = len(np.unique(hit[0])) >= 0.5 * len(pts)
    return out
def name_by_share(geoms, lines, end_m=NAME_END_M, min_m=NAME_MIN_M, near_m=NAME_NEAR_M, col="gnis_name",
                  min_share=NAME_SHARE):
    """For each line (or None), the NHD name (or other `col` of `lines`) whose lines lie within `near_m` of `min_share`
    (NAME_SHARE) or more of its points (every 25 m) short of its last `end_m` (where it nears the stream it joins), on
    `min_m` or more; or None."""
    named = lines[lines[col].notna()]
    tree = shapely.STRtree(named.geometry.values) if len(named) else None
    nm = named[col].to_numpy(object)
    out = []
    for g in geoms:
        if g is None or tree is None or g.length - end_m < min_m or g.length == 0:
            out.append(None)
            continue
        pts = shapely.line_interpolate_point(g, np.arange(0.0, g.length - end_m + 1e-6, 25.0))
        pi, li = tree.query(pts, predicate="dwithin", distance=near_m)
        if not len(pi):
            out.append(None)
            continue
        share = pd.DataFrame({"p": pi, "n": nm[li]}).drop_duplicates().groupby("n").p.size() / len(pts)
        out.append(share.idxmax() if share.max() >= min_share else None)
    return out
def name_keeps(geoms, km2, lines, big_geoms, big_km2):
    """Links whose name read along their length (name_by_share) isn't one they share with a stream SIDE_RATIO times
    bigger within SIDE_NEAR_M (`big_geoms`, their drainage `big_km2`), its name read at its 3 vertices or along it
    within SIDE_NEAR_M: a big river's own vote can miss its name too (East Creek's 74 km2 beside a 0.5 km2 link on the
    first try; a braid of the Snake River, whose main channel runs over 60 m from NHD's line)."""
    nm = name_by_share(geoms, lines)
    ok = np.array([n is not None for n in nm])
    if ok.any() and len(big_geoms):
        bn, tree = vote(lines, "gnis_name", pts=vertices3(big_geoms)).to_numpy(object), shapely.STRtree(big_geoms)
        bs = {}
        for n_ in np.flatnonzero(ok):
            big = [k for k in tree.query(geoms[n_], predicate="dwithin", distance=SIDE_NEAR_M)
                   if big_km2[k] >= SIDE_RATIO * km2[n_]]
            for k in big:
                if k not in bs:
                    bs[k] = name_by_share(np.array([big_geoms[k]], dtype=object), lines, 0.0, 0.0, SIDE_NEAR_M)[0]
            ok[n_] = not any(bn[k] == nm[n_] or bs[k] == nm[n_] for k in big)
    return ok
def nhd_keeps(geoms, km2, lines, big_geoms, big_km2, lakes):
    """nhd_says, and for a link it doesn't keep that starts in a lake, the same vote on its first stretch along an
    artificial path through the lake and on its creek below the lake; then, for one still not kept, a name read along
    its length (name_keeps) where no kept line runs beside it. lakes: (the lakes layer's outlines, which of them NHD
    maps as intermittent)."""
    ok = nhd_says(geoms, km2, lines, big_geoms, big_km2)
    outl, dry = lakes
    for part in (pond_stretches(geoms, lines[lines.fcode.eq(55800)], outl[~dry], lines), creek_parts(geoms, outl)):
        j = np.array([i for i in range(len(geoms)) if not ok[i] and part[i] is not None], dtype=int)
        if len(j):
            ok[j] = nhd_says(np.array([part[i] for i in j], dtype=object), np.asarray(km2)[j], lines, big_geoms,
                             big_km2)
    j = np.flatnonzero(~ok)          # a name read along the link
    if len(j):
        j = j[name_keeps(np.asarray(geoms, dtype=object)[j], np.asarray(km2)[j], lines, big_geoms, big_km2)]
        if len(j):                   # not where a kept line already runs beside it: the name is that line's
            drawn = np.array(list(big_geoms) + [geoms[i] for i in np.flatnonzero(ok)], dtype=object)
            ok[j] = ~beside(np.asarray(geoms, dtype=object)[j], drawn)
    return ok
from flowlib import lakes_layer
_ll = lakes_layer()
_floor_lakes = ((np.array([], dtype=object), np.array([], dtype=bool)) if _ll is None else
                (np.array(_ll.geometry.values, dtype=object), _ll.intermittent.fillna(False).astype(bool).values))
# A link's water is all that reaches it: its own ground, the water behind lakes' outlets (03b_stitch.py: since
# 2026-11-23 a lake taken to NHD's outlet passes its water on there, area_km2.tif counts it and held_km2.tif marks it),
# and what crossbox.py carries from elsewhere. A lake's outflow is drawn down to the first creek it meets once
# OUTFLOW_MIN_KM2 or more comes through the lake (or from elsewhere), as 06_map.py's draw_through drew it from 2026-11-19
# (below 77 ponds and dams on the 12 maps, 23 mi, a pond's 0.5 km2 outlet creek drawn with the values of the creek it
# joins: Beaver Brook below Beaver Brook Pond as a 10.6 km2 creek, fish 76); now as reaches with their own values.
full0 = pd.Series(sample(area, own_end).round(2), index=s.index) + carried
through_ = sample(held, own_end) + carried
base = (sea < 0.5) & areaclip.inside(s.geometry.values)
_f, _g = full0.to_numpy(float), s.geometry.values
_lowc = s.low_channel.to_numpy(bool)       # 03b's lines laid along NHD's named or year-round lines (below)
small = ((full0 < MAP_MIN_KM2) & (full0 >= STREAM_KM2) & base).to_numpy() & ~_lowc
_big = np.flatnonzero((full0 >= MAP_MIN_KM2).to_numpy() & base & ~_lowc)
by_nhd = np.zeros(len(s), bool)
if small.any():
    by_nhd[small] = nhd_keeps(_g[small], _f[small], floor_lines(nhd), _g[_big], _f[_big], _floor_lakes)
# Under STREAM_KM2 a creek has a line only where 03b_stitch.py laid one along NHD's named or year-round lines, from
# where NHD's line starts (low_channel): it is drawn on the floor's own vote (a named or year-round NHD line, no canal
# or ditch, read at its 25/50/75 % points, through a lake, or along its length), less the test against a bigger stream
# beside it, as it runs down NHD's own line from where NHD starts it; and the creek it runs into goes on with it to a
# kept line (below).
by_low = np.zeros(len(s), bool)
if (_lowc & base).any():
    _j = np.flatnonzero(_lowc & base)
    by_low[_j] = nhd_keeps(_g[_j], _f[_j], floor_lines(nhd), np.array([], dtype=object), np.array([]), _floor_lakes)
keep = ((full0 >= MAP_MIN_KM2) | by_nhd | by_low | (through_ >= OUTFLOW_MIN_KM2)) & base
by_outflow = (keep & (full0 < MAP_MIN_KM2)).to_numpy() & ~by_nhd & ~by_low
# A creek kept goes on downstream until it meets a kept line: NHD's class changes along a creek, and the vote with it, so
# a creek kept on its NHD evidence could end in the woods where NHD calls it intermittent (14 such ends in NE Connecticut
# on the first try). Across an edge two boxes share, the link that ends on it in the next box is judged here with the
# same rule, on that box's cells and NHD lines: a creek kept on one side goes on on the other.
_key = lambda c: (round(c[0], 1), round(c[1], 1))
_starts = defaultdict(list)
for i, ln in enumerate(_g):
    _starts[_key(ln.coords[0])].append(i)
_kp, _seam, _seam_low = keep.to_numpy().copy(), [], []
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
    _sm = np.flatnonzero(_in & (_a >= STREAM_KM2) & (_a < MAP_MIN_KM2))
    _ok = np.flatnonzero(_in & (_a >= MAP_MIN_KM2)).tolist()
    if len(_sm):
        _bg = np.flatnonzero(_a >= MAP_MIN_KM2)
        _ok += _sm[nhd_keeps(_ns.geometry.values[_sm], _a[_sm], floor_lines(_nl), _ns.geometry.values[_bg],
                            _a[_bg], _floor_lakes)].tolist()
    _seam += [j for k in _ok for j in _starts.get(_key(_ns.geometry.values[k].coords[-1]), []) if base[j] and not _kp[j]]
    _lw = np.flatnonzero(_in & _ns.low_channel.fillna(0).to_numpy(bool)) if "low_channel" in _ns else []
    if len(_lw):                   # a line laid lower along NHD's named or year-round lines, as here
        _okl = _lw[nhd_keeps(_ns.geometry.values[_lw], _a[_lw], floor_lines(_nl), np.array([], dtype=object),
                             np.array([]), _floor_lakes)]
        _seam_low += [j for k in _okl for j in _starts.get(_key(_ns.geometry.values[k].coords[-1]), [])
                      if base[j] and not _kp[j]]
_n0 = int(_kp.sum())
_kp0 = _kp & ~_lowc                 # the links kept as without the lines laid lower along NHD's lines (below)
_kp0[_seam] = True
_kp[_seam] = True
_kp[_seam_low] = True
# ... and through a pond or reservoir: a creek kept into it goes on below its outlet, where crossbox.py carries the
# lake's water on (dam_links: the lake's dead end -> the cell below the outlet). On the first try Munson Pond's outflow
# in the High Peaks (drawn through on live) had no line: the creek into the pond was kept, the one out of it wasn't,
# and 06_map.py's draw-through stopped at once on the kept creek's end beside it.
with rasterio.open(crossbox.fdir_path(REGION)) as _src:
    _T, _W = _src.transform, _src.width
_past = {_key(_T * (o_ % _W, o_ // _W)): _key(_T * (c_, r_)) for o_, (r_, c_) in crossbox.dam_links(REGION).items()}
# A line laid lower along NHD's named or year-round lines (low_channel) ends on the stream it runs into, which isn't
# cut there: where no link starts at its end, the link it ends on goes on with it.
_lowt = None
def _down(kp):
    """kp with every link below a kept one kept, down to a kept line."""
    global _lowt
    kp, stack = kp.copy(), list(np.flatnonzero(kp))
    while stack:
        i = stack.pop()
        e = _key(_g[i].coords[-1])
        nx = _starts.get(e, []) + _starts.get(_past.get(e), [])
        if not nx and _lowc[i]:
            _lowt = shapely.STRtree(_g) if _lowt is None else _lowt
            nx = [j for j in _lowt.query(shapely.Point(_g[i].coords[-1]), predicate="dwithin", distance=0.5)
                  if j != i and not _lowc[j] and e in {_key(c) for c in _g[j].coords[1:-1]}]
        for j in nx:
            if not kp[j] and base[j]:
                kp[j] = True
                stack.append(j)
    return kp
# Run twice: as without the lines laid lower (_kp0), and with them. A 0.25-1 km2 link drawn only because such a line
# runs into it (or into the creek above it) is marked as they are (low_channel 2, below): the rules that read one reach
# by others leave both out for the rest, which read as without them
_kp0, _kp = _down(_kp0), _down(_kp)
by_down = _kp & ~keep.to_numpy()
keep = pd.Series(_kp, index=s.index)
by_carried = keep & (s.area_km2 < MAP_MIN_KM2) & (full0 >= MAP_MIN_KM2)
by_nhd &= keep.to_numpy()
# A lake that passes its water on at its outlet (03b_stitch.py, since 2026-11-23) sends it on from the outlet cell, and
# where the creek passes right below that cell the outlet drains straight into it: a junction the creek didn't have
# while the outlet was a pit (the line laid below an outlet, outflow_streams, starts at that cell and so added none),
# so the creek's link above it can end under the floor though the creek was drawn before (645 m of a 0.57 km2 creek
# beside a pond in the Buffalo Fork box). A link that runs into such a junction (it and a lake's way whose last cell
# before it is the outlet, nothing else) is kept with the link it continues there, as the floor had the two as one link.
# Where the way out runs on for a cell or more first, the line below the outlet met the creek before too, and nothing
# changes (counting those too kept 41 mi of creek no map drew, in the first try).
_lo_ = f"{SHARED_DERIVED}/lake_outlets.json"
_wet = ({(int(q[0]), int(q[1])) for q in json.load(open(_lo_)).get("wet", {}).get(REGION, [])}
        if os.path.exists(_lo_) else set())
by_joint = np.zeros(len(s), bool)
if _wet:
    _ends = defaultdict(list)
    for i, ln in enumerate(_g):
        if not _lowc[i]:                 # not a line laid lower along NHD's lines (low_channel): it takes no part
            _ends[_key(ln.coords[-1])].append(i)
    def _through_outlet(i):
        v = np.asarray(_g[i].coords)[:, :2]
        if len(v) < 2:
            return False
        cc_, rr_ = inv * (v[-2, 0], v[-2, 1])
        return (int(np.rint(rr_)), int(np.rint(cc_))) in _wet
    def _joint(kp, flag):
        for _ in range(5):
            more = 0
            for J, ins in _ends.items():
                nxt = _starts.get(J, [])
                if len(ins) != 2 or len(nxt) != 1 or not kp[nxt[0]]:
                    continue
                for i, j in (ins, ins[::-1]):
                    if not kp[i] and base[i] and _through_outlet(j):
                        kp[i] = flag[i] = True
                        more += 1
            if not more:
                break
    _kp = keep.to_numpy().copy()
    _joint(_kp, by_joint)
    _joint(_kp0, np.zeros(len(s), bool))
    keep = pd.Series(_kp, index=s.index)
_new2 = keep.to_numpy() & ~_kp0 & ~_lowc        # drawn only because a line laid lower runs into it (above)
s["low_channel"] = np.where(_new2, 2, s["low_channel"].to_numpy())
print(f"links kept with the creek they continue, at a junction a lake's way out makes beside them: {int(by_joint.sum())}, "
      f"{s.length[by_joint].sum() / 1000:.1f} km")
print(f"links under {MAP_MIN_KM2:g} km2 of their own kept on the water that reaches them from elsewhere (below a lake's "
      f"outlet, in from outside the map): {int(by_carried.sum())}, {s.length[by_carried].sum() / 1000:.1f} km; "
      f"{STREAM_KM2:g}-{MAP_MIN_KM2:g} km2 kept as NHD maps them year-round or names them: {int(by_nhd.sum())}, "
      f"{s.length[by_nhd].sum() / 1000:.1f} km; below a kept creek: {int(by_down.sum())}, "
      f"{s.length[by_down].sum() / 1000:.1f} km ({len(set(_seam))} on from a creek kept in the next box); "
      f"lake outflows on {OUTFLOW_MIN_KM2:g} km2 or more through the lake: {int(by_outflow.sum())}, "
      f"{s.length[by_outflow].sum() / 1000:.1f} km; lines started under {STREAM_KM2:g} km2 along NHD's named or "
      f"year-round lines (03b_stitch.py's low_channels): {int((by_low & keep.to_numpy()).sum())} of "
      f"{int(_lowc.sum())}, "
      f"{s.length[by_low & keep.to_numpy()].sum() / 1000:.1f} km, and {int(_new2.sum())} links of {STREAM_KM2:g}-"
      f"{MAP_MIN_KM2:g} km2 below them drawn only because they run into them, {s.length[_new2].sum() / 1000:.1f} km")
# A lake's second outlets (03b_stitch.py's "sides" in lake_outlets.json: the lake's other NHD outflow lines the terrain
# takes the water on down, by the outlet's own test). D8 sends the lake's water down its outlet, so the cells below a
# second outlet gather only their own few: its links stayed under the floor and the maps had no line there, or drew
# one only where crossbox.py happened to put the lake's water in (13 such lines at 9 lakes until 2026-11-22: Round
# Lake's, Marsh Creek Reservoir's side arms). Each is kept from the cell where the terrain takes the water on, down
# its D8 path to the outlet's creek where the two meet again (whatever that creek drains), the first link kept on its
# own (another creek), a lake, a pit or the box's edge, and is a side channel of the creek the lake's outlet starts
# (below). Nothing is added to the drainage of any line: NHD gives no split of a lake's water, so it is not counted
# twice anywhere.
SIDE_MAX_M = 5000          # a second outlet whose way meets no creek the map keeps within this far isn't drawn (printed)
_lo = f"{SHARED_DERIVED}/lake_outlets.json"
sides = json.load(open(_lo)).get("sides", {}).get(REGION, []) if os.path.exists(_lo) else []
s["side_n"] = -1
s["order_cap"] = np.nan     # a creek's order above a junction only a second outlet's line makes, it runs on through (below)
if sides:
    fdir = rasterio.open(f"{DERIVED}/flowdir.tif").read(1)
    D8_ = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
    own_keep = keep.to_numpy(bool) & (s["low_channel"].to_numpy() == 0)     # as without the new lines (low_channel)
    # On a second outlet's way only a link's own ground makes it a creek of its own (1 km2, with the water carried to
    # it), not the floor's rules under 1 km2: NHD's vote there reads the outflow line itself, which NHD maps because the
    # lake's water leaves by it, and a creek the floor runs on below carries the lake's water too (as nhd_says says of
    # a bank link reading its river's line). Kept on those rules, 12 of the 51 second outlets became small creeks of
    # their own from the lake on, and the lower links of 4 more, and read up to 32 points lower than as side channels
    # (Woodhull Lake's, 0.14 sq mi, 100 -> 81; Marsh Creek Reservoir's lower 2,499 ft, 72 -> 45; 2026-11-23)
    own_ground = own_keep & (full0 >= MAP_MIN_KM2).to_numpy()
    ok_ = (sea < 0.5) & np.asarray(areaclip.inside(s.geometry.values), bool)
    cell_link, head, tail = {}, {}, {}  # each link's cells, from its vertices (cell corners; its last is the junction,
    for i, g in enumerate(s.geometry.values):           # the next link's), its first, and the junction it ends at
        if _lowc[i]:    # not a line 03b laid lower along NHD's lines (low_channel): it ends on a stream whose link isn't
            continue    # cut there, so a second outlet's way and its junctions read the 0.25 km2 network as without them
        v = np.asarray(g.coords)
        vc, vr = inv * (v[:, 0], v[:, 1])
        cells_ = np.rint(vr).astype(int) * fdir.shape[1] + np.rint(vc).astype(int)
        for kk in cells_[:-1]:
            cell_link.setdefault(int(kk), i)
        if len(cells_) > 1:
            head[i], tail[i] = int(cells_[0]), int(cells_[-1])
    def main_way(e):
        """The links the lake's main outlet's own way runs through, down D8 from the first cell below the outlet, twice
        as far as a second outlet's way is followed: where the second outlet's way comes to one of them, the two meet
        again. None where the outlet's creek starts in the next box."""
        if e.get("main_box", REGION) != REGION:
            return set()
        (r_, c_), way = e["main"], set()
        for _ in range(int(2 * SIDE_MAX_M / RES)):
            i = cell_link.get(r_ * fdir.shape[1] + c_)
            if i is not None:
                way.add(i)
            d_ = D8_.get(int(fdir[r_, c_]))
            if d_ is None or not (0 <= r_ + d_[0] < fdir.shape[0] and 0 <= c_ + d_[1] < fdir.shape[1]):
                break
            r_, c_ = r_ + d_[0], c_ + d_[1]
        return way
    into = {}                           # each junction: the links that end there
    for i, t_ in tail.items():
        into.setdefault(t_, []).append(i)
    side_n, long_, own_, stops, meet_ = s["side_n"].to_numpy(int).copy(), [], [], [], []
    for n_, e in enumerate(sides):
        r_, c_, marked, way_ = *e["top"], False, main_way(e)
        for _ in range(int(SIDE_MAX_M / RES)):
            k_ = r_ * fdir.shape[1] + c_
            i = cell_link.get(k_)
            if i is not None and side_n[i] != n_ and head.get(i) != k_:
                if not marked:
                    own_.append(e["lake"] + " (a creek passing its exit)")
                break           # a creek the way runs into from the side (one that passes the lake's exit)
            own_i = i is not None and bool(own_ground[i])
            if i is not None and (own_i or not ok_[i] or (side_n[i] >= 0 and side_n[i] != n_)):
                if not marked and own_i:        # its first link gathers a creek's ground of its own: that creek,
                    own_.append(e["lake"])      # drawn from the lake on
                elif marked and own_i:
                    stops.append((n_, k_))
                break           # a link kept on its own (or the sea, the state line, another second outlet's way)
            # A creek comes in at this junction (any link not of a second outlet's way: each ends on STREAM_KM2 or more
            # of its own ground), or the link below lies on the lake's own outlet creek (its main outlet's D8 way: the
            # two outlets meet again), and the floor keeps the link below: the second outlet ends here, whatever the
            # link below drains, and the link is that creek's, as below a creek of its own. A pond's outlet creek often
            # drains under 1 km2, and the way ran on down it: the creek's own reach was marked the pond's side channel,
            # its popup saying its own drainage was small (43 links, 10.7 mi on the 12 maps of 2026-11-24). A link
            # below the floor doesn't end it: the way runs on as before, so a second outlet never ends on a line the
            # map doesn't draw
            if i is not None and side_n[i] != n_ and own_keep[i]:
                if i in way_ or any(side_n[u] < 0 for u in into.get(k_, [])):
                    if marked:
                        stops.append((n_, k_))
                        meet_.append(e["lake"])
                    else:
                        own_.append(e["lake"] + " (a creek passing its exit)")
                    break
            if i is not None:
                if marked and side_n[i] != n_ and own_keep[i]:   # on into a link the floor keeps under 1 km2: the
                    stops.append((n_, k_))                        # creek above its junction is judged as at a stop
                side_n[i], marked = n_, True
            d_ = D8_.get(int(fdir[r_, c_]))
            if d_ is None:
                break           # a pit: a lake's outlet, or a dead end
            if not (0 <= r_ + d_[0] < fdir.shape[0] and 0 <= c_ + d_[1] < fdir.shape[1]):
                long_.append(e["lake"] + " (leaves the box first)")
                side_n[side_n == n_] = -1   # it would end dead on the box's edge: the next box keeps no line for it
                break
            r_, c_ = r_ + d_[0], c_ + d_[1]
        else:
            long_.append(e["lake"] + f" ({SIDE_MAX_M} m on)")
            side_n[side_n == n_] = -1       # a channel lost in flat ground: no line that stops short of a creek
    # Where the second outlet's way joins a creek, its new line split that creek's link, and the creek's reach ended at
    # the junction. A junction only the new line makes (the creek and the second outlet run into it, nothing else, and
    # the second outlet's last cell above it gathers under STREAM_KM2, so it had no stream line of its own there before
    # 03b_stitch.py's side_streams) is no junction for the creek: a side channel carries no water of its own (nothing
    # is added to any line's drainage), so the creek's reach runs on through it, its links above and below one link
    # again as before the second outlet's line was laid. On the 12 maps of 2026-11-24 such junctions ended 104.7 mi of
    # creek reaches: Fender Brook's at the rejoin of its pond's parallel channel (fish 59 -> 48), Ledford Creek's lower
    # end moved off the brook trout patch it touched (85 -> 57), and an Adirondack pond's outlet creek read its steep
    # lower 761 m on their own gradient (96 -> 84). This replaces 6e0898c's junction rule, which kept the creek above
    # drawn but still ended its reach there. The order 03b counted below such a junction (the second outlet's line
    # coming in) is the creek's above it again (order_cap: 05c_drainages.py reads the order at a reach's end). Where the
    # way had already become a stream above the junction (west of Crooked Lake: 0.41 km2), the junction was there
    # before, and the creek's reach ends there as at any creek's
    out_of = {h_: i for i, h_ in head.items()}
    run_on = {}
    for n_, j_ in stops:
        up_ = into.get(j_, [])
        mine_ = [u for u in up_ if side_n[u] == n_]
        other_ = [u for u in up_ if side_n[u] < 0]
        d_ = out_of.get(j_)
        if (mine_ and len(other_) == 1 and len(up_) == 2 and ok_[other_[0]] and d_ is not None and side_n[d_] < 0
                and own_keep[d_] and s.area_km2.values[mine_[0]] < STREAM_KM2):
            run_on[other_[0]] = d_              # the creek's reach runs on through
    geoms_, gone_, cap_ = s.geometry.values.copy(), [], s["order_cap"].to_numpy(float).copy()
    for u in [u for u in run_on if u not in set(run_on.values())]:     # the top of each creek run on through
        run_ = [u]
        while run_[-1] in run_on:
            run_.append(run_on[run_[-1]])
        xy = list(geoms_[run_[0]].coords)
        for k in run_[1:]:
            xy += list(geoms_[k].coords)[1:]
        geoms_[run_[-1]] = shapely.LineString(xy)
        gone_ += run_[:-1]
        top_ = geoms_[run_[0]].coords
        cap_[run_[-1]] = float(sample(strahler, [shapely.Point(top_[-2] if len(top_) >= 2 else top_[0])])[0])
    gone_km = s.length.values[gone_].sum() / 1000 if gone_ else 0.0
    if gone_:
        s[s.geometry.name] = gpd.GeoSeries(geoms_, index=s.index, crs=s.crs)
        s["order_cap"] = cap_
    keep = ((keep | pd.Series(side_n >= 0, index=s.index))
            & ~pd.Series(np.isin(np.arange(len(s)), gone_), index=s.index))
    s["side_n"] = side_n
    print(f"second outlets of lakes: {len(sides)} ({', '.join(e['lake'] for e in sides)}); kept below the floor: "
          f"{int((side_n >= 0).sum())} links, {s.length[side_n >= 0].sum() / 1000:.1f} km"
          + (f"; a creek of its own from the lake on: {', '.join(own_)}" if own_ else "")
          + (f"; not drawn, no creek the map keeps reached within the box: {', '.join(long_)}" if long_ else ""))
    print(f"second outlets ending where a creek the map draws comes in (their lake's outlet creek or another), under "
          f"1 km2: {len(meet_)}" + (f" ({', '.join(meet_)})" if meet_ else "")
          + f"; creek reaches run on through a junction only a second outlet's line makes: {len(gone_)} "
          f"({gone_km:.2f} km of creek above them joined to the link below)")
s = s[keep].copy()
# A link is cut where it crosses a lake's shore. pysheds draws one line per link between confluences, so a link that
# runs from a creek into a lake, or out of one, is part creek and part lake water. 05b_flow.py reads a reach as lying
# in a lake when half its length does, and the whole link took the lake's class or the creek's: Taggart Creek's last
# 161 m above Taggart Lake scored as lake (fish 29 against 99 above), 710 m of Indian Creek above Palisades Reservoir
# too, and over the 12 maps 352 km of creek read as lake and 339 km of lake water as creek (2026-11-21). Each link is
# now cut at the shores of the lakes the map draws (flowlib.drawn_water: 05d_lakes.py's lakes layer, which run_mid.sh
# runs before this step) where they are the lakes a reach can lie in (flowlib.lake_water: the outlines 05b_flow.py
# reads), exactly where the line crosses the shore, so every reach is creek or lake and the map draws each reach as it
# is: one lying in a lake (in_lake) with the lake, the others as streams. The outlines 05b reads that no drawn lake
# covers cut the links too (an NHD lake of 8 ha or more the lakes layer leaves out or draws smaller, from a source
# other than the lidar): cut only at the drawn shores, a link lying half in one read "reservoir" whole (a Mettawee
# River tributary's 0.3 mi above an unnamed 30 ha NHD pond, fish 58 -> 20) and one under half in it read creek whole
# (2026-11-23). A reach lying in such a lake is drawn as a stream, as the map draws no lake there (_in_drawn below).
# Until 2026-11-23 the cut was at lake_water's
# outlines, at the nearest vertex and with a 50 m tolerance, and 06_map.py clipped every line again at the lakes it
# draws, from 1.2 acres: 470 mi of creek lay in drawn ponds the cut didn't see, 6,290 reaches were drawn shorter than
# their table, 1,133 pieces took another reach's values. A stretch out of the water that hugs the shore of the lake it
# leaves and comes back to (the routing's straight path over flat water clipping a shore or a headland), or one under
# 20 m between two stretches in the water, stays with the lake (flowlib.cut_exact). A piece keeps its link's place on
# the map (the floor above is the link's), and is measured on its own cells like any link.
from flowlib import (drawn_water, counted_water, cut_exact, lake_water, cut_below_lakes, carried_lake_km2,
                     lake_water_km2, LAKE_NEAR_M)
_lakes = lake_water(REGION)
_drawn = drawn_water()
_counted = counted_water(_drawn, REGION)
_links_geom = s.geometry.values          # the links as kept, for the NHD vote of a piece whose own vote fails (below)
_pieces, _src, _wet, _own_xy = cut_exact(s.geometry.values, np.concatenate([_counted, _lakes]))
_in_drawn = np.zeros(len(_pieces), bool)  # a piece in the water lying half or more in a lake the map draws
if len(_counted):
    _ct = shapely.STRtree(_counted)
    for i in np.flatnonzero(np.asarray(_wet, bool)):
        c_ = _ct.query(_pieces[i], predicate="intersects")
        _in_drawn[i] = bool(len(c_)) and (shapely.union_all(_counted[c_]).intersection(_pieces[i]).length
                                          >= 0.5 * _pieces[i].length)
# ... and such a piece whose end runs on through an outline 05b_flow.py reads where the map draws no lake (NHD's
# outline reaching past the drawn shore) ends at the drawn shore: the stretch past it, SLIVER_M or longer, is a piece of
# its own, lying in that water and drawn as a stream, as a reach lying wholly in such an outline is. Drawn with its
# lake, the last 306 m of a reach in an unnamed 11.6 ha lake (adk_southeast 43.476,-73.303; NHD's outline there is
# 30 ha) left a gap where the map shows no lake, and the lake's outlet undrawn (2026-11-23).
from flowlib import SLIVER_M, before_vertex
_ends = []
if _in_drawn.any():
    _P, _S, _W, _O, _D = [], [], [], [], []
    for i, g in enumerate(_pieces):
        lead_ = tail_ = 0.0
        if _in_drawn[i]:
            sub_, _, sw_, _ = cut_exact([g], _counted[_ct.query(g, predicate="intersects")])
            if len(sub_) > 1:
                lead_ = sub_[0].length if not sw_[0] and sub_[0].length >= SLIVER_M else 0.0
                tail_ = sub_[-1].length if not sw_[-1] and sub_[-1].length >= SLIVER_M else 0.0
        if not (lead_ or tail_):
            _P.append(g); _S.append(_src[i]); _W.append(_wet[i]); _O.append(_own_xy[i]); _D.append(_in_drawn[i])
            continue
        L_ = g.length
        for a_, b_, lake_ in ((0.0, lead_, False), (lead_, L_ - tail_, True), (L_ - tail_, L_, False)):
            if b_ - a_ <= 0:
                continue
            _P.append(shapely.ops.substring(g, a_, b_)); _S.append(_src[i]); _W.append(True)
            _O.append(_own_xy[i] if b_ >= L_ else before_vertex(g, b_)); _D.append(lake_)
            if not lake_:
                _ends.append(b_ - a_)
    _pieces, _src, _wet, _own_xy, _in_drawn = _P, _S, _W, _O, np.array(_D, bool)
print(f"links cut at lake shores: {len(_pieces) - len(s)} cuts on {int((pd.Series(_src).value_counts() > 1).sum())} "
      f"of {len(s)} links; of them at the drawn shore where a lake's piece runs on through water the map draws no lake "
      f"in: {len(_ends)} ({sum(_ends) / 1000:.2f} km, drawn as streams)")
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
_own = [shapely.Point(q) for q in _own_xy]      # each piece's own cell (cut_exact: a piece cut at a shore can end off the grid)
_full = sample(area, _own) + sample(carried_grid, _own)
_carried_lake = sample(carried_lake_km2(REGION).reshape(area.shape), _own)
_low_sh = s["low_channel"].to_numpy(bool)[np.asarray(_src, int)]     # 03b's lines laid lower (low_channel): no donors
_lake_km2 = np.minimum(lake_water_km2(_shore, _carried_lake, _full - _carried_lake, _wet, low=_low_sh), _full)
# A lake's second outlet (side_n, above) is the lake's water leaving by another channel. NHD gives no split of a
# lake's water, so the routing sends it all down the main outlet and the second outlet's line carries none of it;
# but what runs there is lake water, as warm as the main outlet's. So the whole of its drainage counts as the
# lake's here, and the cut finds it where it finds a main outlet: its first 200 m are a reach of their own
# (watertemp.py gives the rest its distance below the lake). Woodhull Lake's 811 m second outlet read 66 F as one
# reach and 76 F over its first 650 ft in the popup (2026-11-22).
_sd = s["side_n"].to_numpy()[np.asarray(_src, int)] >= 0
_lake_km2 = np.where(_sd & ~np.asarray(_wet, bool), _full, _lake_km2)
def _mostly_lake(ii, pts):     # the line's lake water (it takes none on along the line) against the drainage at the mark
    full = sample(area, pts) + sample(carried_grid, pts)
    return np.nan_to_num(lake_share(full - np.minimum(_lake_km2[ii], full), full), nan=0.0) >= 0.5
_pieces, _from, _wet = cut_below_lakes(_shore, _lake_km2, _wet, _lakes, keep=_mostly_lake, low=_low_sh)
_from = np.asarray(_from, int)
_in_drawn = _in_drawn[_from]
_src = [_src[k] for k in _from]
_cut = pd.Series(_from).duplicated(keep=False).to_numpy()          # both pieces of a line cut below a lake
_first = pd.Series(_from).duplicated(keep="last").to_numpy()       # the upper one
# each piece's own cell, where its drainage is read: the lower piece of a line cut below a lake ends where the line did,
# the upper one at a vertex of the line, its own cell the vertex before it
_own_xy = [tuple(g.coords[-2][:2]) if f_ else tuple(_own_xy[k]) for k, f_, g in zip(_from, _first, _pieces)]
s = gpd.GeoDataFrame(s.drop(columns="geometry").iloc[_src].reset_index(drop=True), geometry=_pieces, crs=CRS)
# the link each piece was cut from (at the shores of the lakes the map draws, at opened outlets, 200 m below a lake):
# 11_context.py reads the designated trout waters on all of a creek's pieces at once (creek_lines), as on the link
s["link_id"] = [f"{REGION}:k{int(k)}" for k in _src]
own_end = gpd.GeoSeries([shapely.Point(q) for q in _own_xy], index=s.index, crs=CRS)
s["own_x"], s["own_y"] = np.round([q[0] for q in _own_xy], 2), np.round([q[1] for q in _own_xy], 2)   # for 05c_drainages.py
starts = gpd.GeoSeries([shapely.Point(g.coords[0]) for g in s.geometry], index=s.index, crs=CRS)
mid = gpd.GeoSeries([vert(g, 0.5) for g in s.geometry], index=s.index, crs=CRS)
s["area_km2"] = sample(area_own, own_end).round(2)
# each piece's drainage with the water that reaches it from elsewhere (the floor's `carried`, on the piece's own cells)
full_km2 = sample(area, own_end).astype(float) + sample(carried_grid, own_end)
in_water = np.array(_wet, bool)
s["in_lake"] = in_water
# The pieces the map draws: each reach cut again at the shores of every lake the map draws, ponds under 8 ha too. A
# creek runs through such a pond as one reach, with its own values; the stretch in the pond is drawn with the lake
# (shown while the Lakes layer is off), as the stretches of a reach lying in a lake are; a reach lying in a lake the
# map doesn't draw is drawn as a stream. 06_map.py draws these pieces and nothing else: len_drawn_m is how much of
# the reach it draws while Lakes is on.
_dpieces, _dsrc, _dwet, _ = cut_exact(s.geometry.values, _drawn)
_dwet = np.array(_dwet, bool) | _in_drawn[np.asarray(_dsrc, int)]
s["len_drawn_m"] = (pd.Series([0.0 if w_ else g_.length for g_, w_ in zip(_dpieces, _dwet)]).groupby(np.asarray(_dsrc)).sum()
                    .reindex(range(len(s))).fillna(0.0).round(0).values)
_o = sample(strahler, mid)
s["order"] = np.where(np.isfinite(s["order_cap"].to_numpy(float)),
                      np.minimum(_o, s["order_cap"].to_numpy(float)), _o).astype(_o.dtype)
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
# ... and a creek piece cut from a link at the shores of the lakes the map draws, or at an opened outlet, whose own vote
# fails (no two of its 25/50/75 % vertices agree) takes its link's: in the Stowe box a 0.4 km2 brook's first 25 m were cut
# off at a pond's drawn shore, the 679 m creek piece's vote failed where the link's held ("perennial"), and it read
# "usually flows" for "year-round". Only a failed vote is filled, so no piece reads wetter, or takes another name, than
# NHD's lines along its link give.
_need = ~s["in_lake"].astype(bool).to_numpy() & (s["flow"].eq("unmapped").to_numpy() | s["name"].isna().to_numpy())
if _need.any():
    _lpts = vertices3([_links_geom[k] for k in np.asarray(_src)[_need]], s.index[_need])
    _lf, _ln = vote(nhd_k, "flow", pts=_lpts), vote(nhd_k, "gnis_name", pts=_lpts)
    _ff = s.loc[_need, "flow"].eq("unmapped") & _lf.notna()
    _fn = s.loc[_need, "name"].isna() & _ln.notna()
    s.loc[_ff[_ff].index, "flow"] = _lf[_ff]
    s.loc[_fn[_fn].index, "name"] = _ln[_fn]
    print(f"creek pieces whose own NHD vote failed, given their link's: class {int(_ff.sum())}, name {int(_fn.sum())}")
# A piece the map draws as a stream (len_drawn_m: a creek piece, or one in a lake the map doesn't draw) still unnamed
# reads its NHD name along its length, by the size floor's rules (name_by_share, on the lines the floor reads: no canal,
# nor a name that is a ditch's or a canal's). It doesn't take a name it shares with a reach SIDE_RATIO times bigger
# within SIDE_NEAR_M (that reach's name read at its 3 vertices or along it within SIDE_NEAR_M) or with a reach beside it
# (half its points within BESIDE_M), nor one other than its main stem's above (the reach of most water ending at its
# start, named by the vote or along it): Mill Creek's last reach, beside the Santa Ana River in its wash (137 km2
# against the river's 500), read the river's name. Dunham Pond Brook below Dunham Pond in NE Connecticut, whose terrain
# path runs up to 85 m off NHD's line, lost its name when 2026-11-23's routing moved its link's vertices into the pond.
# Such a piece still "unmapped" reads NHD's class along it the same way, perennial or intermittent only (no reach reads
# drier than "unmapped" for it), less where it runs along a river of SIDE_RIVER_KM2 or more, SIDE_RATIO times its size
# (SIDE_ON_RIVER of it within 150 m, as the floor's side channels).
_fl = floor_lines(nhd)
_G, _tree = s.geometry.values, shapely.STRtree(s.geometry.values)
_creek = s["len_drawn_m"].to_numpy(float) > 0           # the pieces the map draws as streams, in part or whole
_unn = np.flatnonzero(s["name"].isna().to_numpy() & _creek)
_vn, _bs, _got, _held = s["name"].to_numpy(object).copy(), {}, [], [0, 0, 0]
_ends = defaultdict(list)
_lowp = s["low_channel"].to_numpy(bool)    # 03b's lines laid lower along NHD's lines: no stem above, nor a reach beside,
for k, g in enumerate(_G):                 # for the other pieces (whose names read here as without them)
    if not _lowp[k]:
        _ends[(round(g.coords[-1][0], 1), round(g.coords[-1][1], 1))].append(k)
def _up_name(i):
    """The name of reach i's main stem above it (the reach of most water ending at its start): its vote's, else
    read along it."""
    ups = _ends.get((round(_G[i].coords[0][0], 1), round(_G[i].coords[0][1], 1)), [])
    if not ups:
        return None
    m = max(ups, key=lambda k: full_km2[k])
    return _vn[m] if isinstance(_vn[m], str) else name_by_share(np.array([_G[m]], dtype=object), _fl, 0.0, 0.0)[0]
for _i, _n in zip(_unn, name_by_share(_G[_unn], _fl)):
    if _n is None:
        continue
    _un = _up_name(_i)
    if isinstance(_un, str) and _un != _n:     # a creek's last reach beside the river it joins
        _held[2] += 1
        continue
    _big = [k for k in _tree.query(_G[_i], predicate="dwithin", distance=SIDE_NEAR_M)
            if full_km2[k] >= SIDE_RATIO * full_km2[_i] and (_lowp[_i] or not _lowp[k])]
    for k in _big:
        if k not in _bs:
            _bs[k] = name_by_share(np.array([_G[k]], dtype=object), _fl, 0.0, 0.0, SIDE_NEAR_M)[0]
    if any(_vn[k] == _n or _bs[k] == _n for k in _big):
        _held[0] += 1
        continue
    _same = np.flatnonzero((_vn == _n) & (_lowp[_i] | ~_lowp))
    if len(_same) and beside(np.array([_G[_i]], dtype=object), _G[_same])[0]:
        _held[1] += 1
        continue
    _got.append((_i, _n))
for _i, _n in _got:
    s.iat[_i, s.columns.get_loc("name")] = _n
# A piece still unnamed that carries its named main stem on (the reach of most water ending at its start, named by the
# vote or read along it) takes that name where NHD's lines of that name lie within MAIN_NEAR_M of MAIN_SHARE of its
# points (every 25 m, as the floor reads them). The terrain's path can stray further from the creek's line than the
# 60 m the vote and name_by_share read, and still carry the creek's water: in the Cohutta (north Georgia) the pond
# routing cut Rock Creek's 2.6 km reach in two, and the lower 1 km, all of Rock Creek's water a median 79 m off NHD's
# Rock Creek line (within 60 m at 25 % of its points, within 150 m at 96 %), was drawn unnamed; so were 2.1 mi of the
# Independence River (ADK) and 0.8 mi of the Hudson. The guards above hold: not a name it shares with a stream
# SIDE_RATIO times bigger beside it, nor one on a reach running beside it (the main stem above it and the reaches it
# runs into excepted, which touch its ends). Down the stem in turn, so unnamed pieces one below another carry the name
# on as far as NHD's line of it runs along them.
_nm, _main = s["name"].to_numpy(object).copy(), []
_flt, _fln = shapely.STRtree(_fl.geometry.values), _fl["gnis_name"].to_numpy(object)
# A point counts only where NHD's line of the name goes on past it. A tributary's line ends where it joins, and at a
# confluence it lies within MAIN_NEAR_M of the piece below, though the piece runs on another line: near Manker Flat
# (LA) the 111 m below San Antonio Creek's junction with Big Butch Wash, nearest NHD's unnamed perennial main channel
# at every point, took "Big Butch Wash" (the routing's bigger donor there, 5.0 km2 to 2.9), whose NHD line ends 10 m
# from it. (OSM, which names the main channel San Antonio Creek, fills names only after this.) Whether the line goes on
# is read on all of NHD's lines of that name, canals, connectors and artificial paths included: NHD draws Horno Creek
# (LA) as a stream, a ditch and a connector by turns, and on the floor's lines alone it seemed to end at every ditch.
_merged = {}
_nht, _nhn = shapely.STRtree(nhd.geometry.values), nhd["gnis_name"].to_numpy(object)
def _along_main(geom, pts, n):
    """How many of the points lie within MAIN_NEAR_M of NHD's lines of name n where the nearest place on those lines
    is not where they end: all of NHD's lines of that name within 4 MAIN_NEAR_M of the piece, merged into continuous
    lines (drawn downstream), so a line that goes on further off than MAIN_NEAR_M, or as a ditch, still goes on."""
    pi, li = _flt.query(pts, predicate="dwithin", distance=MAIN_NEAR_M)
    pi = np.unique(pi[_fln[li] == n])
    if not len(pi):
        return 0
    lj = _nht.query(geom, predicate="dwithin", distance=4 * MAIN_NEAR_M)
    key = (n, tuple(np.sort(lj[_nhn[lj] == n]).tolist()))
    if key not in _merged:
        m = shapely.line_merge(shapely.union_all(nhd.geometry.values[list(key[1])]), directed=True)
        _merged[key] = [g for g in getattr(m, "geoms", [m]) if g.geom_type == "LineString"]
    ok = 0
    for k in pi:
        L = min(_merged[key], key=lambda g: g.distance(pts[k]))
        ok += bool(L.project(pts[k]) < L.length - 1.0)
    return ok
_starts_at = defaultdict(list)
for k, g in enumerate(_G):
    _starts_at[(round(g.coords[0][0], 1), round(g.coords[0][1], 1))].append(k)
_todo = set(np.flatnonzero(pd.isna(_nm) & _creek).tolist())
_held_main = [0, 0, 0, 0]    # NHD's line of the name not along it, a bigger stream's name, a reach so named beside it,
                             # NHD's line of the name ending at it (a tributary at its confluence)
while _todo:
    _step, _done = [], []
    for _i in sorted(_todo):
        _ups = _ends.get((round(_G[_i].coords[0][0], 1), round(_G[_i].coords[0][1], 1)), [])
        _m = max(_ups, key=lambda k: full_km2[k]) if _ups else -1
        _n = _nm[_m] if _m >= 0 else None
        if not isinstance(_n, str):       # no main stem, or one still unnamed (it may be named on a later turn)
            if _m < 0 or _m not in _todo:
                _done.append(_i)
            continue
        _done.append(_i)                  # its main stem's name is settled: decided now, once
        _pts = shapely.line_interpolate_point(_G[_i], np.arange(0.0, _G[_i].length + 1e-6, 25.0))
        _pi, _li = _flt.query(_pts, predicate="dwithin", distance=MAIN_NEAR_M)
        if len(np.unique(_pi[_fln[_li] == _n])) < MAIN_SHARE * len(_pts):
            _held_main[0] += 1
            continue
        if _along_main(_G[_i], _pts, _n) < MAIN_SHARE * len(_pts):
            _held_main[3] += 1
            continue
        _big = [k for k in _tree.query(_G[_i], predicate="dwithin", distance=SIDE_NEAR_M)
                if full_km2[k] >= SIDE_RATIO * full_km2[_i] and (_lowp[_i] or not _lowp[k])]
        for k in _big:
            if k not in _bs:
                _bs[k] = name_by_share(np.array([_G[k]], dtype=object), _fl, 0.0, 0.0, SIDE_NEAR_M)[0]
        if any(_nm[k] == _n or _bs[k] == _n for k in _big):
            _held_main[1] += 1
            continue
        _touch = set(_ups) | set(_starts_at.get((round(_G[_i].coords[-1][0], 1), round(_G[_i].coords[-1][1], 1)), []))
        _same = np.array([k for k in np.flatnonzero((_nm == _n) & (_lowp[_i] | ~_lowp)) if k not in _touch and k != _i],
                         dtype=int)     # (not a line laid lower along NHD's lines, for a reach of the network: _lowp)
        if len(_same) and beside(np.array([_G[_i]], dtype=object), _G[_same])[0]:
            _held_main[2] += 1
            continue
        _step.append((_i, _n))
    _todo.difference_update(_done)
    for _i, _n in _step:
        _nm[_i] = _n
    _main += _step
    if not _step:
        break
for _i, _n in _main:
    s.iat[_i, s.columns.get_loc("name")] = _n
# NHD's class read along the piece the same way can raise the 3-point vote's class, never lower it: perennial where
# NHD's perennial lines lie along PERENNIAL_SHARE or more of its points, and on a piece the vote leaves "unmapped" or
# "ephemeral", the class on half of them. A piece that straddles the point where NHD's line turns from intermittent to
# perennial took whichever class two of its three vertices read, so a re-cut that moved its ends flipped it: Palmer
# Brook in NE Connecticut read perennial, then intermittent when the pond routing cut its reach 34 m shorter (year-round
# -> usually flows, fish 43 -> 31). Not where it runs along a river of SIDE_RIVER_KM2 or more, SIDE_RATIO times its
# size (SIDE_ON_RIVER of it within 150 m, as the floor's side channels).
_vote_cls = s["flow"].to_numpy(object).copy()             # the 3-point class (with the cut pieces' link vote)
# "Other" too, as "unmapped": the vote's line has no flow class (a connector, a stream line NHD leaves unclassified, in
# LA an artificial path), unless it is a built channel's (a canal, ditch, pipeline or conduit, or a line named after
# one: floor_lines()), which stays as voted. Hooks Creek above Lake Arrowhead (LA) lies on NHD's Hooks Creek all
# along, its perennial line at 40 % of its points and its connector and artificial path at the rest; re-cut, its
# vertices read the connector, "other", and it showed seasonal for year-round (fish 44 -> 13).
_oth = np.flatnonzero(_creek & (_vote_cls == "other"))
_built_v = (vote(nhd.assign(built=nhd.ftype.isin(BUILT_FTYPES) | channel_word(nhd.gnis_name))[["built", "geometry"]]
                 .reset_index(drop=True), "built", pts=vertices3(_G[_oth], s.index[_oth])).eq(True).to_numpy()
            if len(_oth) else np.zeros(0, bool))
_cand = np.flatnonzero(_creek & np.isin(_vote_cls, ["unmapped", "other", "ephemeral", "intermittent"]))
_cand = np.setdiff1d(_cand, _oth[_built_v])
_cls = _fl[_fl.fcode.isin([46006, 46003])]
_per = name_by_share(_G[_cand], _cls[_cls.fcode.eq(46006)], col="flow", min_share=PERENNIAL_SHARE)
_most = name_by_share(_G[_cand], _cls, col="flow")
_fill, _held_cls = [], 0
for _i, _p, _m in zip(_cand, _per, _most):
    _c = _p or (_m if _vote_cls[_i] in ("unmapped", "other", "ephemeral") else None)
    if _c is None or CLASS_RANK[_c] <= CLASS_RANK[_vote_cls[_i]]:
        continue
    _big = [k for k in _tree.query(_G[_i], predicate="dwithin", distance=150)
            if full_km2[k] >= max(SIDE_RIVER_KM2, SIDE_RATIO * full_km2[_i]) and (_lowp[_i] or not _lowp[k])]
    _along = _G[_i].intersection(shapely.union_all(shapely.buffer(_G[_big], 150))).length if _big else 0.0
    if _along >= SIDE_ON_RIVER * _G[_i].length and _big:
        _held_cls += 1
        continue
    _fill.append((_i, _c))
# flow_vote keeps the 3-point class and flow_along marks a class raised from it: scoring.score() lets such a class
# raise a reach's water, never lower it (the area's typical value for it is the higher of its class's peers' and its
# 3-point class's), and sorts every reach's peers by the 3-point class. Taken as the vote's, a filled "intermittent"
# put 5 NE CT pieces with borrowed estimates among the drier "NHD maps intermittent" peers: year-round -> usually
# flows, fish -12 to -21, 3 on wild trout water
_along_cls = np.zeros(len(s), bool)
for _i, _c in _fill:
    s.iat[_i, s.columns.get_loc("flow")] = _c
    _along_cls[_i] = True
s["flow_vote"], s["flow_along"] = _vote_cls, _along_cls
_moves = pd.Series([f"{_vote_cls[_i]} -> {_c}" for _i, _c in _fill]).value_counts()
print(f"read along the reach: names {len(_got)} of {len(_unn)} unnamed (held: {_held[0]} a bigger stream's, {_held[1]} "
      f"beside a reach so named, {_held[2]} not its main stem's above); NHD classes raised {len(_fill)} of {len(_cand)} "
      f"below perennial ({', '.join(f'{k} {v}' for k, v in _moves.items()) or 'none'}; held along a big river: "
      f"{_held_cls}; 'other' on a built channel, not read: {int(_built_v.sum())})")
print(f"main stem's name carried on: {len(_main)} pieces, {sum(_G[i].length for i, _ in _main) / 1000:.1f} km (held: "
      f"{_held_main[0]} NHD's line of it not along them, {_held_main[1]} a bigger stream's, {_held_main[2]} beside a "
      f"reach so named, {_held_main[3]} NHD's line of it ending at them)")
osm_wp = f"{RAW}/osm_waterways.gpkg"    # OSM named rivers and streams, cached a week
if not os.path.exists(osm_wp) or time.time() - os.path.getmtime(osm_wp) > 7 * 86400:
    from geomatch import overpass
    import netfetch      # when Overpass can't be reached, the older download stays (a dated NOTE)
    def osm_names():
        w0, s0, e0, n0 = gpd.GeoSeries([shapely.box(*REGIONS[REGION]["bbox"])], crs=CRS).to_crs(4326).total_bounds
        els = [e for e in overpass(f'[out:json][timeout:600];way["waterway"~"^(river|stream)$"]["name"]'
                                   f'({s0:.5f},{w0:.5f},{n0:.5f},{e0:.5f});out geom;') if len(e.get("geometry") or []) >= 2]
        # kept when empty too (a box with no named stream in OSM): it is the last good copy the step runs on offline
        gpd.GeoDataFrame({"name": [e["tags"]["name"] for e in els]}, crs=4326,
                         geometry=[shapely.LineString([(q["lon"], q["lat"]) for q in e["geometry"]]) for e in els]
                         ).to_crs(CRS).to_file(osm_wp + ".tmp.gpkg", driver="GPKG")
        os.replace(osm_wp + ".tmp.gpkg", osm_wp)
    netfetch.keep_old(osm_wp, osm_names, f"OSM stream names ({REGION})")
osm_vote = np.full(len(s), None, dtype=object)    # OSM's name at each reach (the vote), whatever names it on the map
if os.path.exists(osm_wp):
    nhd_named = s["name"].notna().sum()
    _ov = vote(gpd.read_file(osm_wp).to_crs(CRS), "name").reindex(s.index)
    osm_vote = _ov.to_numpy(object)
    s["name"] = s["name"].fillna(_ov)
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
_low_r = s["low_channel"].to_numpy(bool)     # 03b's lines laid lower along NHD's lines (low_channel): no donor of another
def donors_of(i):                            # reach, which reads its stem as without them
    """The reaches running into reach i: those ending at its start, else a lake's last reach ending a cell short."""
    d = [j for j in ends.get(end_key(geoms[i].coords[0]), []) if _low_r[i] or not _low_r[j]]
    if not d:
        d = [int(j) for j in _end_tree.query(shapely.Point(geoms[i].coords[0][:2]), predicate="dwithin", distance=1.5 * RES)
             if j != i and end_key(geoms[j].coords[-1]) not in _starts and (_low_r[i] or not _low_r[j])]
    return d
km2 = full_km2      # sizes are compared with the water carried past dams (since 2026-11-21: below a dam a river's own
                    # count starts again near nothing, and on it the main stem above a junction could be a side creek)
voted = s["name"].to_numpy(object)
main_up, down = np.full(len(s), -1), np.full(len(s), -1)
for i, g in enumerate(geoms):
    donors = donors_of(i)
    if donors:
        main_up[i] = max(donors, key=lambda j: km2[j])
    down[[j for j in donors if _low_r[j] or not _low_r[i]]] = i     # no other reach's reach below is a low_channel one
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
# - else, where its own line lies on NHD's lines of the river (SIDE_ON_RIVER of its length within SIDE_ON_M): NHD maps
#   the channel itself as the river, and it is a side channel whatever drains into its head. Its D8 drainage says
#   nothing of the water in it (above), so the stem below can't decide it: the pond routing of 2026-11-24 took the
#   Winooski's 370 m side channel in the stowe_lamoille box under 1 km2, where the stem climbs any reach (71 % of it on
#   NHD's Winooski lines), and it climbed an unnamed 0.39 km2 creek joining at its head; Otter Creek's 279 m at
#   44.198 N 73.315 W (85-100 %) climbed a pond the routing now sends through it. Both lost the river's size and flow;
# - else, where the stem up to its head lies along NHD's lines of the river (SIDE_ON_RIVER of its length within 150 m):
#   a side channel of the river. It keeps the name and is marked (side_of, the river reach beside it in side_sid, that
#   reach's drainage in river_km2): 05b_flow.py gives it the river's flow evidence, scoring.py the river's size, and
#   the maps call it a side channel;
# - else it is the lower end of a creek with no name, and has none.
# The river is found by the name OSM gives it as well: a reach named after a stream SIDE_RATIO times bigger beside it,
# whose own reaches NHD names another way, where OSM's name for those reaches (its vote there) is this reach's name.
# Big Tujunga Creek in NHD is "Big Tujunga River" in OSM, and a 0.8 km2 creek end beside it took OSM's name once the
# river's reach had NHD's (2026-11-25). Such a reach is judged as one of the river's, by the river's name, and a side
# channel takes that name. Not where NHD itself gives a line near the reach its name: that is the creek's own name
# (Peachtree Creek in the Smokies lies on NHD's Peachtree Creek all along, beside a river reach OSM's vote calls
# Peachtree Creek too). And found this way, it is a side channel only where it lies on NHD's lines of the river
# (SIDE_ON_RIVER of it within SIDE_ON_M), not where only its stem runs within 150 m of them: a 2 km2 creek end in Big
# Tujunga Creek's wash read the river's size and flow, mostly dry at fish 2 -> year-round at 79.
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
def river_zone(river, d=150.0):
    """d m around NHD's lines of that name (the river's own lines, its braids included)."""
    if (river, d) not in _zone:
        ln = nhd_k.geometry[nhd_k.gnis_name.eq(river).values]
        _zone[river, d] = shapely.union_all(ln.values).buffer(d) if len(ln) else None
    return _zone[river, d]
SIDE_ON_M = 30.0        # a reach this near NHD's lines of a river lies on the river's own channel (11_context.py reads
                        # a designated stream's line within 30 m of a reach, too)
new_name, side, by_line, side_name, by_osm, osm_lost = {}, {}, [], {}, [], {}
_nk_tree, _nk_name = shapely.STRtree(nhd_k.geometry.values), nhd_k.gnis_name.to_numpy(object)
def _nhd_named_near(n, g):
    """Whether NHD gives a line within SIDE_NEAR_M of g the name n."""
    k_ = _nk_tree.query(g, predicate="dwithin", distance=SIDE_NEAR_M)
    return bool((_nk_name[k_] == n).any())
for i in (np.flatnonzero(is_named & ~in_water) if big_tree is not None else []):
    near = big[big_tree.query(geoms[i].buffer(SIDE_NEAR_M))]
    ni = names0[i]                                        # the river's name, as its own reaches carry it
    sib = near[(names0[near] == ni) & (full_km2[near] >= SIDE_RATIO * full_km2[i])]
    if not len(sib):                                      # ... or OSM's spelling of it (above)
        if _nhd_named_near(ni, geoms[i]):                 # a name NHD gives a line near it is the creek's own
            continue
        alt = near[(osm_vote[near] == ni) & (names0[near] != ni) & (full_km2[near] >= SIDE_RATIO * full_km2[i])]
        if not len(alt):
            continue
        ni = names0[alt[int(np.argmax(full_km2[alt]))]]
        sib = alt[names0[alt] == ni]
    beside = shapely.union_all(shapely.buffer(geoms[sib], SIDE_NEAR_M))
    if geoms[i].intersection(beside).length < SIDE_ALONG * geoms[i].length:
        continue
    osm_i = ni != names0[i]
    if osm_i:
        by_osm.append(i)
    j, other = stem_up[i], None
    for _ in range(6):
        if j < 0 or (names0[j] in (ni, names0[i]) and full_km2[j] >= SIDE_RATIO * full_km2[i]):
            break                                 # the head, or the river itself comes in above
        if isinstance(names0[j], str) and names0[j] not in (ni, names0[i]):
            other = j
            break
        j = stem_up[j]
    if other is not None and full_km2[i] <= 3 * full_km2[other]:
        new_name[i] = names0[other]
        continue
    zone, tot, inn, j = river_zone(ni), 0.0, 0.0, i
    for _ in range(30):
        if j < 0:
            break
        tot += geoms[j].length
        inn += geoms[j].intersection(zone).length if zone is not None else 0.0
        j = stem_up[j]
    on = river_zone(ni, SIDE_ON_M)                        # NHD maps this channel itself as the river
    on_line = on is not None and geoms[i].intersection(on).length >= SIDE_ON_RIVER * geoms[i].length
    if on_line or (inn >= SIDE_ON_RIVER * tot and not osm_i):     # by OSM's spelling: on the river's own line only
        side[i], side_name[i] = sib[int(np.argmax(full_km2[sib]))], ni
        if ni != names0[i]:
            new_name[i] = ni                              # a side channel takes the river's own name
        if inn < SIDE_ON_RIVER * tot:
            by_line.append(i)
    else:
        new_name[i] = None
        if osm_i:
            osm_lost[i] = ni                              # a lake's second outlet may take it back (below)
s["name"] = [new_name.get(i, n) for i, n in enumerate(names0)]
s["side_of"] = [side_name[i] if i in side else None for i in range(len(s))]
s["side_row"] = [side.get(i, -1) for i in range(len(s))]        # the river reach beside it (its row; a sid below)
s["river_km2"] = [round(float(full_km2[side[i]]), 2) if i in side else np.nan for i in range(len(s))]
s["cut_row"] = np.where(_first, np.arange(len(s)) + 1, -1)      # a first stretch below a lake: the rest of its line
print(f"small reaches named after the river beside them: "
      f"{sum(v is not None and i not in side for i, v in new_name.items())} take the name of "
      f"the creek they end, {sum(v is None for v in new_name.values())} end an unnamed creek and lose the name, "
      f"{len(side)} are side channels of the river ({len(by_line)} on NHD's own lines of the river though the stem up "
      f"leaves it, {sum(geoms[i].length for i in by_line) / 1000:.2f} km); {len(by_osm)} by OSM's name for the river")
# A lake's second outlet (kept above: side_n) is a side channel of the creek its lake's outlet starts, the first creek
# piece on the D8 way from the first cell below the outlet ("main"): like a river's side channel it takes that reach's
# flow evidence (05b_flow.py) and size (scoring.py, river_km2), and its lake share for the water temperature
# (watertemp.py). side_lake names the lake for the maps. A piece of its way lying in a lake is lake water.
# A second outlet that OSM names after that creek in its own spelling (osm_lost above: the river-beside rule found the
# creek by OSM's name and, the piece lying off the creek's own line, took the name away) is the creek's side channel
# and takes the creek's NHD name, as a river's side channel does: Ballouville Pond's second outlet beside the
# Fivemile River, "Five Mile River" in OSM, lost the name and with it the river's stocking and survey records, fish
# 82 -> 69 (2026-11-25).
side_lake = np.full(len(s), None, object)
if sides:
    cell_piece = {}
    for i, g in enumerate(geoms):
        if _low_r[i]:       # not a line laid lower along NHD's lines, nor a link drawn only for one (low_channel): the
            continue        # outlet's creek is found as without them (first try: two NE Connecticut side channels
                            # took a new line's 0.03 and 0.08 sq mi for their creek's, Stickney Hill Brook's 69 -> 53)
        v = np.asarray(g.coords)[:-1]
        vc, vr = inv * (v[:, 0], v[:, 1])
        for kk in np.rint(vr).astype(int) * fdir.shape[1] + np.rint(vc).astype(int):
            cell_piece.setdefault(int(kk), i)
    sn_ = s["side_n"].to_numpy(int)
    side_of_, side_row_ = s["side_of"].to_numpy(object).copy(), s["side_row"].to_numpy(int).copy()
    river_ = s["river_km2"].to_numpy(float).copy()
    nm2_ = s["name"].to_numpy(object).copy()
    told = []
    for n_, e in enumerate(sides):
        rows = np.flatnonzero((sn_ == n_) & ~in_water)
        if not len(rows):
            continue
        main, other = -1, np.nan
        if e.get("main_box", REGION) == REGION:
            r_, c_ = e["main"]
            for _ in range(1000):
                j = cell_piece.get(r_ * fdir.shape[1] + c_)
                if j is not None and not in_water[j] and sn_[j] < 0:
                    main = j
                    break
                d_ = D8_.get(int(fdir[r_, c_]))
                if d_ is None or not (0 <= r_ + d_[0] < fdir.shape[0] and 0 <= c_ + d_[1] < fdir.shape[1]):
                    break
                r_, c_ = r_ + d_[0], c_ + d_[1]
            if main < 0:    # the outlet's way runs straight into the next lake: the water the lake passes on there
                other = float(area[e["main"][0], e["main"][1]]) + float(carried_grid[e["main"][0], e["main"][1]])
        else:           # the outlet's creek starts in the next box: sized on the water the lake passes on there
            with rasterio.open(f"{derived_dir(e['main_box'])}/area_km2.tif") as src_:
                r_, c_ = e["main"]
                other = float(src_.read(1, window=rasterio.windows.Window(c_, r_, 1, 1))[0, 0])
                other += float(crossbox.carried_km2(e["main_box"])[r_ * src_.width + c_])
        side_lake[rows], side_of_[rows], side_row_[rows] = e["lake"], None, main
        if main >= 0:
            for r_ in rows:
                if osm_lost.get(r_) is not None and osm_lost[r_] == nm2_[main]:
                    nm2_[r_] = nm2_[main]
        river_[rows] = round(float(full_km2[main]), 2) if main >= 0 else round(other, 2)
        told.append(f"{e['lake']} ({s.length.values[rows].sum():.0f} m, beside "
                    + (f"{full_km2[main]:.1f} km2" if main >= 0 else f"{other:.1f} km2 in {e.get('main_box')}") + ")")
    s["side_of"], s["side_row"], s["river_km2"], s["name"] = side_of_, side_row_, river_, nm2_
    print(f"second outlets drawn as side channels of their lake's outlet creek: {len(told)}: " + ", ".join(told))
s["side_lake"] = side_lake
s = s.drop(columns="side_n")

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
chan_g, road_g = streams.geometry.values[streams.low_channel.to_numpy() == 0], drivable.geometry.values   # the
# drop's own channel: not a line 03b laid lower along NHD's lines (low_channel), which drops (1 km2 or more) never lie on
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

# A reach a city has buried isn't drawn (buried.py; the user's choice, "Option A", 2026-11-24): no name and no NHD class
# once the reaches are named, a city's impervious cover and no open water in OpenStreetMap along it, no NHD line along
# half of it, and no trout water or trout record near it. On the 12 maps of 2026-11-24, 568 mi of lines down streets
# where the creek runs in a sewer, or never had a channel (LA's urban fans: 477). Decided here, on the names the map
# shows (a creek named only by the rules above, like a piece of Tacony Creek off NHD's line, stays), so the floor and
# the naming run as before, and the routing still carries the water. A drop candidate whose top lies on such a reach
# goes with it; the rows the reaches and pieces point to are renumbered.
import buried
_lowb = s["low_channel"].to_numpy(bool)      # 03b's lines laid lower along NHD's lines (low_channel 1 and 2): they read
_bur, _bur_trout = buried.reaches(s.geometry.values, s["name"].to_numpy(object), s["flow"].to_numpy(object),   # the
                                  s["in_lake"].to_numpy(bool), nhd, low=_lowb)       # network's reaches, not it them
print(f"reaches a city has buried (buried.py), not drawn: {int(_bur.sum())}, {s.length.values[_bur].sum() / 1000:.1f} km; "
      f"kept for a trout water or record nearby: {int(_bur_trout.sum())}, {s.length.values[_bur_trout].sum() / 1000:.1f} km")
_bur_keep, _bur_why = buried.keep(s.geometry.values, _bur, s["area_km2"].to_numpy(float), nhd, low=_lowb)   # its two
                                                                                                          # exceptions
print(f"of those drawn after all: {int((_bur_why == 'outlet').sum())} carrying a lake's outlet NHD maps, "
      f"{int((_bur_why == 'short gap').sum())} in short stretches drawn above and below, "
      f"{s.length.values[_bur_keep].sum() / 1000:.1f} km")
_bur &= ~_bur_keep
# The reaches left out, with their rows among the reaches before they were left out, for the steps after this one that
# follow the water down the reaches (buried_reaches.gpkg; no file where there are none): 05b_flow.py reads them back for
# the way down to the first modelled reach and the segment one matches, and 06_map.py doesn't draw a path below a dam
# that runs into one. Without them (the 12 maps' test, 2026-11-24) creeks above a buried one lost the estimate they
# take from below (65 mi of LA's lines fell back to NHD's class, 6 mi of them 10+ lower in fish score), and paths below
# dams ran on down the buried lines to the next drawn reach (1.6 mi drawn again on 4 paths).
_bp = f"{OUT}/buried_reaches.gpkg"
if _bur.any():
    s.loc[_bur, ["area_km2"] + [c_ for c_ in ("own_x", "own_y", "low_channel") if c_ in s] + ["geometry"]].assign(
        row=np.flatnonzero(_bur)).to_crs(4326).to_file(_bp)
elif os.path.exists(_bp):
    os.remove(_bp)
if _bur.any():
    _pos = np.full(len(s), -1)
    _pos[~_bur] = np.arange(int((~_bur).sum()))
    _on = np.array([reach_at.get(int(t), -1) for t in kp.top_idx.astype(int)], int)
    kp = kp[~((_on >= 0) & _bur[np.maximum(_on, 0)])]
    _dk = [j for j, r_ in enumerate(np.asarray(_dsrc, int)) if not _bur[r_]]
    _dpieces, _dwet, _dsrc = [_dpieces[j] for j in _dk], np.asarray(_dwet, bool)[_dk], _pos[np.asarray(_dsrc, int)[_dk]]
    s = s[~_bur].copy()
    s["side_row"] = [int(_pos[j]) if j >= 0 else -1 for j in s["side_row"]]
    s["cut_row"] = [int(_pos[j]) if j >= 0 else -1 for j in s["cut_row"]]

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
gpd.GeoDataFrame({"sid": s_ll.sid.values[np.asarray(_dsrc, int)], "wet": _dwet}, geometry=list(_dpieces), crs=CRS).to_crs(4326) \
    .to_file(f"{os_}/drawn_pieces.gpkg")
kp_ll.drop(columns=["top_idx", "base_idx"]).to_file(f"{os_}/waterfall_candidates.gpkg")

# light copies of trails + mapped falls for the combined map
t_ll = areaclip.cut(trails).to_crs(4326)
t_ll = t_ll[~t_ll.is_empty].assign(geometry=shapely.set_precision(t_ll.geometry.simplify(0.0001).values, 1e-5))
t_ll.assign(name=t_ll["name"].fillna("trail"))[["name", "geometry"]].to_file(f"{os_}/trails.gpkg")
# each range draws the falls whose point lies in it (and the falls of a river that is the state line, as the river:
# areaclip.in_river; Scudders Falls in the Delaware), and those drawn just past the map's edge whose other source on
# the map lies in it (02f_known_falls.py's home_lon/home_lat)
_kh = np.array(known_falls.geometry.values, dtype=object)
if "home_lon" in known_falls:
    _hm = known_falls.home_lon.notna().to_numpy()
    if _hm.any():
        _kh[_hm] = np.array(gpd.GeoSeries(gpd.points_from_xy(known_falls.home_lon[_hm], known_falls.home_lat[_hm]),
                                          crs=4326).to_crs(CRS).values, dtype=object)
known_falls[shapely.within(_kh, range_box) & crossbox.owns(REGION, shapely.get_x(_kh), shapely.get_y(_kh))
            & (areaclip.inside(_kh) | areaclip.in_river(_kh))] \
    .drop(columns=["home_lon", "home_lat"], errors="ignore").to_crs(4326).to_file(f"{os_}/known_falls.gpkg")

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
