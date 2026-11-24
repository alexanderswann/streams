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
"""
import areaclip
import networkx as nx
import numpy as np
import shapely
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union

MIN_KM = 2.0          # skip shorter creeks
SNAP_FALL = 150       # a known fall within this of a profile is drawn on it (m)
FLOWLINE_FTYPES = {460, 558}   # StreamRiver, ArtificialPath (through ponds / reservoirs)


def main_stems(lines):
    """Longest path through each connected piece of a creek's merged NHD lines."""
    u = unary_union(list(lines))
    merged = u if u.geom_type == "LineString" else linemerge(u)
    parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
    G = nx.Graph()
    key = lambda c: (round(c[0], 1), round(c[1], 1))
    for i, ln in enumerate(parts):
        a, b = key(ln.coords[0]), key(ln.coords[-1])
        G.add_edge(a, b, w=ln.length, i=i) if a != b else None
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
        coords = []
        for u, v in zip(nodes[:-1], nodes[1:]):
            seg = list(parts[sub[u][v]["i"]].coords)
            if key(seg[0]) != u:
                seg = seg[::-1]
            coords += seg if not coords else seg[1:]
        if len(coords) >= 2:
            out.append(LineString(coords))
    return out


def profile_stems(lines):
    """The main stems of one creek's lines in one range (in the area's CRS) that get a profile: MIN_KM or more, inside
    the area's state line where it has one."""
    st = [s for s in main_stems(lines) if s.length >= MIN_KM * 1000]
    return [s for s, k in zip(st, areaclip.inside(st)) if k] if st else []


class ProfileLines:
    """The profiles' main stems in a map, by creek name: built from each range's NHD flowlines on their own (as
    12_profiles.py builds them), only for the names asked about. `nhd` holds the named flowlines in the area's CRS
    (config.CRS: the state line is tested there), with the range in column "range"."""

    def __init__(self, nhd):
        nhd = nhd[nhd.gnis_name.notna() & nhd.ftype.isin(FLOWLINE_FTYPES)]
        self._by_name = {n: g for n, g in nhd.groupby("gnis_name")}
        self._stems = {}

    def stems(self, name):
        if name not in self._stems:
            g = self._by_name.get(name)
            self._stems[name] = [] if g is None else [s for _, gr in g.groupby("range") for s in profile_stems(gr.geometry)]
        return self._stems[name]

    def passes(self, name, pt, within=SNAP_FALL):
        """True where a profile of the creek `name` passes within `within` metres of the point `pt` (same CRS)."""
        st = self.stems(name) if isinstance(name, str) and name else []
        return bool(st) and float(np.min(shapely.distance(pt, np.asarray(st, dtype=object)))) <= within
