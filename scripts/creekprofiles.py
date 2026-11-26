"""Which creeks get a long profile, and where: the rule 12_profiles.py draws them by, shared with 06_map.py, whose drop and
known-falls popups link to a creek's profile only where that profile passes (2026-11-23).

A profile is drawn for each named creek in the USGS hydrography: the creek's NHD flowlines (stream / river lines and
the artificial paths through ponds) are merged by name in each range, split into connected pieces, and the longest path
through each piece of MIN_KM or more is its main stem. In an area that stops at a state line (config clip_state) a main
stem past the line gets none, as the map draws no creek there (areaclip.inside: by its middle point, or the water of
the river that is the line, so the Delaware's profile stays): New Jersey's creeks inside southeastern Pennsylvania's
boxes (66 profiles, 2026-11-24) and New York's inside central Vermont's (22) had been listed on the profiles page.
profiles.html opens a creek's profile from a map link by the creek's name and a point (#q=name&lat=&lon=): the profile
of that name passing closest to the point.
Since 2026-11-25 a creek's main stems come from the whole map, not range by range: each range's NHD download reaches
past its box, so a creek near a box edge was profiled once per range, the copies sampling the edge cells of their own
box past it (Little River in northeastern Connecticut read 87 and 111 km2 for one line; Naaman Creek was cut in two at
the claymont box). The lines of all ranges are taken once each and the stems are cut to the map's boxes.
A creek is also the name the map gives its reaches where NHD has none (fill_names, 2026-11-25): the map names a reach
from OpenStreetMap where NHD's line is unnamed (05_score.py), and those creeks had no profile (1,661 reaches, 829 mi
on the 12 maps: Death Canyon Creek, Devils Canyon, Topanga Creek). NHD's unnamed line along such reaches takes their
name, and a short unnamed line between two lines of one name (a culvert, a pond's path, a stretch NHD left unnamed)
takes the creek's; NHD's named Connectors count as the creek's own lines. Creeks NHD names in pieces under MIN_KM
each had no profile either (1,752 reaches, 790 mi: Shook Branch is 5.3 km in three pieces).
"""
import functools, os
import areaclip
import rasterio
import networkx as nx
import numpy as np
import pandas as pd
import shapely
import shapely.ops
from shapely.geometry import LineString
from shapely.ops import linemerge, nearest_points, unary_union
import geopandas as gpd
from config import REGIONS, CRS, MAP_OUT, derived_dir

MIN_KM = 2.0          # skip shorter creeks
FORKS = True          # each fork of a creek MIN_KM or longer gets a profile of its own, not only its longest path
IN_MAP_KM = 0.5       # ... and the piece of a creek the map's boxes cut that is shorter than this
SEA_M = 0.5           # m: tidewater, where a profile ends (05c_drainages.SEA_M ends a drainage there; 05_score.py
                      # draws no reach on it)
SNAP_FALL = 150       # a known fall within this of a profile is drawn on it (m)
BRAID_KM2 = 100.0     # a reach's link to its creek's profile reaches SNAP_FALL x (drainage / this) ** 0.25 on a river
FLOWLINE_FTYPES = {460, 558, 334}   # StreamRiver, ArtificialPath (through ponds / reservoirs), Connector
STREAM_FTYPES = (460, 558, 334)
GAP_FTYPES = (460, 558, 334, 336, 420, 428)   # ... and CanalDitch, UnderGroundConduit, Pipeline: a culvert
NAME_M, NAME_SHARE = 30.0, 0.6   # an unnamed NHD line takes the name of the map's reaches within this of it, along this
                                 # share of it ...
NAME_NHD_M = 60.0                # ... where no NHD line of that name runs this near its middle (NHD maps the creek
                                 # there already: a ditch beside it stays unnamed)
GAP_M = 1000.0        # an unnamed line (or a run of them, or the creek's own ditch or pipe piece) this short between two
                      # lines of one name is the creek's


def main_stems(lines):
    """Longest path through each connected piece of a creek's merged NHD lines, and with FORKS each fork of it MIN_KM or
    longer: the longest path from where the fork leaves the stems already taken to its head (a piece of the rest that
    meets them at one point only; one that meets them at two is an arm of a split, left out), longest first."""
    u = unary_union(list(lines))
    merged = u if u.geom_type == "LineString" else linemerge(u)
    parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
    G = nx.Graph()
    key = lambda c: (round(c[0], 1), round(c[1], 1))
    for i, ln in enumerate(parts):
        a, b = key(ln.coords[0]), key(ln.coords[-1])
        G.add_edge(a, b, w=ln.length, i=i) if a != b else None

    def line(sub, nodes):
        coords = []
        for u, v in zip(nodes[:-1], nodes[1:]):
            seg = list(parts[sub[u][v]["i"]].coords)
            if key(seg[0]) != u:
                seg = seg[::-1]
            coords += seg if not coords else seg[1:]
        return LineString(coords) if len(coords) >= 2 else None
    out = []
    for comp in nx.connected_components(G):
        sub = G.subgraph(comp)
        # tree diameter by two weighted sweeps (good enough for creek networks)
        start = next(iter(comp))
        d1 = nx.single_source_dijkstra_path_length(sub, start, weight="w")
        far = max(d1, key=d1.get)
        d2, paths = nx.single_source_dijkstra(sub, far, weight="w")
        end = max(d2, key=d2.get)
        nodes = paths[end]
        ln = line(sub, nodes)
        if ln is not None:
            out.append(ln)
        if not FORKS:
            continue
        used_n, used_e = set(nodes), {frozenset(e) for e in zip(nodes[:-1], nodes[1:])}
        while True:
            rest = sub.edge_subgraph([e for e in sub.edges if frozenset(e) not in used_e])
            best = None
            for c in nx.connected_components(rest):
                at = [n for n in c if n in used_n]
                if len(at) != 1:
                    continue
                dd, pp = nx.single_source_dijkstra(rest.subgraph(c), at[0], weight="w")
                f = max(dd, key=dd.get)
                if dd[f] >= MIN_KM * 1000 and (best is None or dd[f] > best[0]):
                    best = (dd[f], pp[f])
            if best is None:
                break
            fork = best[1][::-1]                        # head -> where it joins
            ln = line(sub, fork)
            if ln is not None:
                out.append(ln)
            used_n |= set(fork)
            used_e |= {frozenset(e) for e in zip(fork[:-1], fork[1:])}
    return out


def link_m(km2):
    """How far a reach's own line may lie from its creek's profile and still link it (06_map.py): SNAP_FALL, and more
    on a river, growing as the fourth root of its drainage past BRAID_KM2: a braided river's channels lie hundreds of
    metres from NHD's line (the Snake in Jackson Hole 170-380 m, 418 m allowed at 6,000 km2)."""
    return SNAP_FALL * max(1.0, (km2 / BRAID_KM2) ** 0.25) if km2 and km2 > 0 else SNAP_FALL


@functools.lru_cache(1)
def boxes():
    """The map's boxes, as one polygon (config.CRS)."""
    b = shapely.union_all([shapely.box(*v["bbox"]) for v in REGIONS.values()])
    shapely.prepare(b)
    return b


def all_lines(nhd):
    """All a map's ranges' flowlines, each line once (a range's download reaches past its box, so the same line comes
    in two or three downloads), single lines only."""
    nhd = nhd[nhd.geometry.notna() & ~nhd.geometry.is_empty].copy()
    nhd["geometry"] = [shapely.line_merge(shapely.force_2d(g)) if g.geom_type == "MultiLineString" else shapely.force_2d(g)
                       for g in nhd.geometry]
    nhd = nhd[nhd.geometry.geom_type == "LineString"]
    wkb = shapely.to_wkb(shapely.normalize(np.asarray(nhd.geometry.values, dtype=object)))
    return nhd[~pd.Series(wkb).duplicated().values].reset_index(drop=True)


def reach_lines(names):
    """The map's reaches (each range's streams_scored.gpkg, in config.CRS) named as `names` (by sid: the map's final
    names) has them, side channels (named after the river beside them) left out."""
    parts = []
    for r in REGIONS:
        p = f"{MAP_OUT}/{r}/streams_scored.gpkg"
        if os.path.exists(p):
            parts.append(gpd.read_file(p, columns=["sid", "side_of", "side_lake"]).to_crs(CRS))
    if not parts:
        return gpd.GeoDataFrame(columns=["name", "geometry"], geometry=[], crs=CRS)
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    g["name"] = g.sid.map(names)
    side = g.side_of.notna() | g.side_lake.notna() if "side_lake" in g else g.side_of.notna()
    g = g[g.name.notna() & (g.name != "") & ~side]
    return g[["name", "geometry"]].reset_index(drop=True)


def fill_names(nhd, reaches=None):
    """nhd (all_lines) with names where NHD has none: an unnamed stream line along the map's reaches of one name (NAME_M,
    NAME_SHARE; not where an NHD line of that name runs within NAME_NHD_M of its middle), then a short run of unnamed
    lines (GAP_M, GAP_FTYPES) from the end of a line of one name, where no line of that name goes on, to the start of
    another of the same name (not a side arm of a braided river, which leaves beside the named line). Column "gap":
    named by the second rule."""
    nhd = nhd.copy()
    nhd["gap"] = False
    name = nhd.gnis_name.to_numpy(object).copy()
    geoms = nhd.geometry.values
    ft = nhd.ftype.to_numpy()
    if reaches is not None and len(reaches):
        rsi = reaches.sindex
        named = nhd[nhd.gnis_name.notna()]
        nsi = named.sindex
        for i in np.flatnonzero(pd.isna(name) & np.isin(ft, STREAM_FTYPES)):
            g = geoms[i]
            p = shapely.line_interpolate_point(g, np.r_[np.arange(10.0, g.length, 20.0), g.length / 2])
            ip, ir = rsi.nearest(p, max_distance=NAME_M, return_all=False)
            if not len(ir):
                continue
            nm = pd.Series(reaches.name.values[ir]).value_counts()
            if nm.iloc[0] < NAME_SHARE * len(p):
                continue
            x = nm.index[0]
            mid = shapely.line_interpolate_point(g, 0.5, normalized=True)
            cand = named.iloc[nsi.query(mid.buffer(NAME_NHD_M))]
            if (cand.gnis_name == x).any() and float(cand[cand.gnis_name == x].distance(mid).min()) <= NAME_NHD_M:
                continue
            name[i] = x
    # short unnamed runs between two lines of one name
    key = lambda c: (round(c[0], 1), round(c[1], 1))
    starts = {}
    for i, g in enumerate(geoms):
        starts.setdefault(key(g.coords[0]), []).append(i)
    gap = np.zeros(len(nhd), bool)
    stream = np.isin(ft, STREAM_FTYPES)
    for i in np.flatnonzero(pd.notna(name) & stream):
        x = name[i]
        if any(name[j] == x and stream[j] for j in starts.get(key(geoms[i].coords[-1]), [])):
            continue        # the creek's lines go on here: an unnamed line leaving beside it is a side arm, not a gap
        # a line the run may cross: unnamed, or the creek's own ditch, conduit or pipe piece (Horno Creek's named
        # CanalDitch stretches cut its stream lines in eight pieces, none under its lake's outlet of 2 km)
        walk = lambda k: ft[k] in GAP_FTYPES and (pd.isna(name[k]) or (name[k] == x and not stream[k]))
        stack = [(j, geoms[j].length, (j,)) for j in starts.get(key(geoms[i].coords[-1]), [])
                 if walk(j) and geoms[j].length <= GAP_M]
        while stack:
            j, d, path = stack.pop()
            for k in starts.get(key(geoms[j].coords[-1]), []):
                if name[k] == x and stream[k]:
                    gap[list(path)] = True
                elif walk(k) and d + geoms[k].length <= GAP_M and k not in path:
                    stack.append((k, d + geoms[k].length, path + (k,)))
        for q in np.flatnonzero(gap & pd.isna(name)):
            name[q] = x
    nhd["gnis_name"] = name
    nhd["gap"] = gap
    return nhd


def unique_lines(nhd, reaches=None):
    """The creeks' lines of all a map's ranges (all_lines, named by fill_names): NHD's named stream lines, the ones
    named after the map's reaches, and the short runs between two lines of one name."""
    nhd = fill_names(all_lines(nhd), reaches)
    return nhd[nhd.gnis_name.notna() & (nhd.ftype.isin(FLOWLINE_FTYPES) | nhd.gap)]


@functools.lru_cache(1)
def _dems():
    return {r: rasterio.open(f"{derived_dir(r)}/dem_filled.tif") for r in REGIONS
            if os.path.exists(f"{derived_dir(r)}/dem_filled.tif")}


def _ground(xs, ys):
    """dem_filled.tif at the points, from the range each lies in (NaN outside them)."""
    z = np.full(len(xs), np.nan)
    for r, ds in _dems().items():
        cc, rr = ~ds.transform * (xs, ys)
        rr, cc = np.floor(rr), np.floor(cc)
        # inside the raster itself (a point on a box's lower edge lies a row past it: sampled there, it read 0 m)
        m = (rr >= 0) & (rr < ds.height) & (cc >= 0) & (cc < ds.width) & np.isnan(z)
        if m.any():
            v = np.array([q[0] for q in ds.sample(zip(xs[m], ys[m]))], float)
            z[m] = np.where(v < -1000, np.nan, v)
    return z


def above_tide(stem):
    """The longest stretch of the stem above tidewater (ground at or below SEA_M), or None where it has no point above
    it: the tidal Delaware below Trenton had two profiles of 0 m, reading the flats' own trickle for the river's 21,000
    km2."""
    d = np.r_[np.arange(0, stem.length, 40.0), stem.length]
    p = shapely.line_interpolate_point(stem, d)
    z = _ground(shapely.get_x(p), shapely.get_y(p))
    sea = np.isfinite(z) & (z <= SEA_M)
    if not sea.any():
        return stem
    best, run = None, None                           # (first, last) index of the longest run of points above tide
    for i in range(len(d)):
        if sea[i]:
            run = None
            continue
        run = (run[0], i) if run else (i, i)
        if best is None or d[run[1]] - d[run[0]] > d[best[1]] - d[best[0]]:
            best = run
    if best is None or d[best[1]] - d[best[0]] < 1:
        return None
    return shapely.ops.substring(stem, float(d[best[0]]), float(d[best[1]]))


def profile_stems(lines):
    """The main stems of one creek's lines in the map (in the area's CRS, each line once) that get a profile: those of
    MIN_KM or more, cut to the map's boxes and at tidewater (a piece of IN_MAP_KM or more), inside the area's state
    line where it has one."""
    st = []
    for s in main_stems(lines):
        if s.length < MIN_KM * 1000:
            continue
        cut = s.intersection(boxes())
        for g in getattr(cut, "geoms", [cut]):
            if g.geom_type == "LineString" and g.length >= IN_MAP_KM * 1000:
                g = above_tide(g)
                if g is not None and g.length >= IN_MAP_KM * 1000:
                    st.append(g)
    return [s for s, k in zip(st, areaclip.inside(st)) if k] if st else []


class ProfileLines:
    """The profiles' main stems in a map, by creek name: built from all the ranges' NHD flowlines, each line once, named
    by fill_names from the map's reaches (reach_lines) as 12_profiles.py builds them, only for the names asked about.
    `nhd` holds the flowlines in the area's CRS (config.CRS: the state line is tested there)."""

    def __init__(self, nhd, reaches=None):
        nhd = unique_lines(nhd, reaches)
        self._by_name = {n: g for n, g in nhd.groupby("gnis_name")}
        self._stems, self._joined = {}, {}

    def stems(self, name):
        if name not in self._stems:
            g = self._by_name.get(name)
            self._stems[name] = [] if g is None else profile_stems(g.geometry)
        return self._stems[name]

    def passes(self, name, pt, within=SNAP_FALL):
        """True where a profile of the creek `name` passes within `within` metres of the point `pt` (same CRS)."""
        st = self.stems(name) if isinstance(name, str) and name else []
        return bool(st) and float(np.min(shapely.distance(pt, np.asarray(st, dtype=object)))) <= within

    def down_to(self, name, pt, on=30.0, within=SNAP_FALL):
        """Where a creek `name` that starts at `pt` (a lake's outlet) reaches a profile of its own name below: the
        profile's point nearest `pt`, where the creek's NHD lines through `pt` (the piece of them joined end to end, as
        main_stems joins them, with a line within `on` metres of `pt`) come within `within` metres of that profile;
        else None. NHD can leave the first stretch below a lake unjoined to the rest of its creek, a piece under MIN_KM
        with no profile of its own: Tooley Pond Outlet's first 1.8 km end 4 m short of the creek's profile, Cook Pond
        Outlet's 0.5 km 44 m short (2026-11-24). A creek of the same name elsewhere is never reached this way."""
        st = self.stems(name) if isinstance(name, str) and name else []
        g = self._by_name.get(name)
        if not st or g is None:
            return None
        if name not in self._joined:
            u = unary_union(list(g.geometry))
            merged = u if u.geom_type == "LineString" else linemerge(u)
            parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
            key = lambda c: (round(c[0], 1), round(c[1], 1))
            G = nx.Graph()
            for i, ln in enumerate(parts):
                G.add_edge(("p", i), key(ln.coords[0]))
                G.add_edge(("p", i), key(ln.coords[-1]))
            self._joined[name] = parts, G
        parts, G = self._joined[name]
        d = shapely.distance(pt, np.asarray(parts, dtype=object))
        if float(d.min()) > on:
            return None
        piece = unary_union([parts[n[1]] for n in nx.node_connected_component(G, ("p", int(np.argmin(d))))
                             if n[0] == "p"])
        ds = shapely.distance(piece, np.asarray(st, dtype=object))
        k = int(np.argmin(ds))
        return nearest_points(st[k], pt)[0] if float(ds[k]) <= within else None
