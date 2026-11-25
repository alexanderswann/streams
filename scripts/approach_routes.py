"""Approach routes: the fastest route from a reach's trailhead to its approach point, drawn on the map pages when the
reach is clicked (the user, 2026-11-24: "when i click on a section of stream draw a line that is the hiking/biking to
the computed approach point, highlight the trails if they exist or just draw the calculated line if there are no
trails").

build() (08_hike.py, per range). 08_hike.py's cost-distance keeps, for every cell, the step to the cell before it on its
fastest route from an open road (skimage's traceback; a lake's water cells lead to their shore). build() follows those
steps from each reach's approach point (the cell best() picks: the cheapest along the reach; a drop's or a lake's the
same way) back to the road cell the route starts from: the trailhead of the access line. The routes share their trunks,
so they are kept once, as a network: their cells form a forest rooted at the trailheads, cut into segments at every
junction, at every route's start and wherever the kind of ground changes; each segment points to the one it runs on
into (its parent), and a route is its first segment and the parents after it. The kinds, from 08_hike.py's own speed
rules on the cells a run crosses:
  0 bike   a bikeable line (closed or gated road, fire road, bike path, bike-legal singletrack)
  1 trail  on foot on a trail or road (anything with a tread)
  2 off    on foot off trail
  3 creek  on foot off trail in a creek bottom (1 km2 or more drains there)
A run shorter than MERGE_M between two runs of one other kind takes their kind (a walk across a fire road "rides" its
width), MERGE_OFF_M between off trail and creek bottom (a creek-bottom route steps on and off the channel's cells every
few cells), as does a route's first run off trail or up a creek bottom before a run of the other of those two. A run on
a bike line or a trail or road is drawn as that line's own vector geometry, not as the cells' staircase: each
cell takes the line passing within SNAP_M of it (every line burned into a cell passes that near its centre), keeping the
line of the cell before while that one stays as near, and the run follows that line between the points nearest its
first and last cells. Off-trail runs are the cells' centres. Douglas-Peucker then thins each segment (THIN_M). Written
per range: hike_routes.gpkg (seg, parent, kind; LineStrings in the area's CRS, each from its start toward the
trailhead, its last point the first point of its parent) and hike_route_starts.csv (what: stream / drop / lake, id,
seg: the route's first segment, -1 for one that starts on the road itself; then the metres of each kind along it).
08_hike.py's own outputs and times do not change: this reads its traceback after them.

pack() (06_map.py): routes_data.js for an area's two map pages, which load it on the first click on a reach
(map_routes.js). Only the segments the drawn reaches' routes use; coordinates as encoded polylines (Google's
algorithm, 1e-5 degrees), each segment from its far end, starting from its parent's first point, so a segment stores
only small steps; the route line of the popup is made here, in imperial units (units.py).
"""
import itertools, json, os, time
import numpy as np, pandas as pd, geopandas as gpd, shapely

KINDS = ("bike", "trail", "off", "creek")
SNAP_M = 7.5            # half a 10 m cell's diagonal is 7.07 m: a line burned into a cell (all_touched) passes this near
JUMP_M = 40.0           # two cells in a row more than this apart along one line: another leg of it (a switchback)
THIN_M = (2.5, 2.5, 5.0, 5.0)   # Douglas-Peucker per kind: lines keep their bends, the cells' staircase is smoothed
NEAR_M = 80.0           # under ~0.05 mi a part of the route isn't named in the popup line ("0.0 mi")
MERGE_M = 30.0          # a run of one kind shorter than this between two of another takes their kind (build())
MERGE_OFF_M = 60.0      # the same between off trail and creek bottom, which differ only in the dashes (the popup's
                        # miles count both as off trail): creek-bottom walks cut the channel's bends over 3-5 cells
GAP_CELLS = 2           # a run on a line goes on along it over this many cells near no line (cells of a joined run)


def explode(geoms):
    """The LineStrings in a set of geometries (multi-parts and collections taken apart; points and empties left out)."""
    g = np.asarray([x for x in geoms if x is not None], dtype=object)
    for _ in range(3):
        g = shapely.get_parts(g)
        if not np.isin(shapely.get_type_id(g), (4, 5, 6, 7)).any():
            break
    return g[np.isin(shapely.get_type_id(g), (1, 2)) & ~shapely.is_empty(g)]


class _Lines:
    """A set of lines, for snapping cells to them and following them between two points."""
    def __init__(self, geoms):
        self.g = explode(geoms)
        self.tree = shapely.STRtree(self.g)
        xy, ix = shapely.get_coordinates(self.g, return_index=True)
        self.xy = xy
        self.off = np.r_[0, np.cumsum(np.bincount(ix, minlength=len(self.g)))]
        d = np.r_[0.0, np.hypot(*np.diff(xy, axis=0).T)]
        d[self.off[:-1]] = 0.0
        d = np.cumsum(d)
        self.cum = d - np.repeat(d[self.off[:-1]], np.diff(self.off))      # metres along its own line

    def snap(self, pts, runs):
        """For each point: the line it is on (-1: none within SNAP_M) and the metres along it. A run (points in a row)
        keeps the line it is on while that line is within SNAP_M, else takes the nearest."""
        if not len(self.g):
            return np.full(len(pts), -1), np.full(len(pts), np.nan)
        pi, li = self.tree.query(pts, predicate="dwithin", distance=SNAP_M)
        d = shapely.distance(pts[pi], self.g[li])
        o = np.lexsort((li, d, pi))
        pi, li = pi[o], li[o]
        k = np.arange(len(pts))
        lo, hi = np.searchsorted(pi, k).tolist(), np.searchsorted(pi, k, "right").tolist()
        li = li.tolist()
        A = [-1] * len(pts)
        for a, b in runs:
            cur = -1
            for j in range(a, b):
                cand = li[lo[j]:hi[j]]
                if not cand:
                    cur = -1
                elif cur not in cand:
                    cur = cand[0]
                A[j] = cur
        A = np.asarray(A, np.int64)
        D = np.full(len(pts), np.nan)
        ok = A >= 0
        D[ok] = shapely.line_locate_point(self.g[A[ok]], pts[ok])
        return A, D

    def piece(self, L, d0, d1):
        """Line L from d0 to d1 metres along it (backwards where d1 < d0), with its own vertices between."""
        a, b = self.off[L], self.off[L + 1]
        cd, P = self.cum[a:b], self.xy[a:b]
        lo, hi = (d0, d1) if d0 <= d1 else (d1, d0)

        def at(d):
            k = min(max(int(np.searchsorted(cd, d)), 1), len(cd) - 1)
            t = 0.0 if cd[k] == cd[k - 1] else min(max((d - cd[k - 1]) / (cd[k] - cd[k - 1]), 0.0), 1.0)
            return P[k - 1] + (P[k] - P[k - 1]) * t
        k0, k1 = np.searchsorted(cd, lo, "right"), np.searchsorted(cd, hi, "left")
        out = [tuple(at(lo))] + [tuple(p) for p in P[k0:k1]] + ([tuple(at(hi))] if hi > lo else [])
        return out if d0 <= d1 else out[::-1]


def build(out_dir, crs, starts, tbf, offs, transform, bike, on_path, area, bike_lines, path_lines, road_lines,
          jump=None, creek_km2=1.0, creek_max_km2=None, label=""):
    """Each start's route from its trailhead, as a shared network (see the module's docstring). starts: {what: (ids,
    flat cells)} with -1 where there is no route; tbf: 08_hike.py's flat traceback (-1 at road cells and at lake cells,
    which lead to their shore: jump = (lake cells, shore cells)); offs: its offsets; bike, on_path, area: its rasters;
    the lines: those 08_hike.py burned in (bike lines, trails and roads, the open roads the routes start from);
    creek_km2 up to creek_max_km2 (None: no cap): the drainages its speed rule walks as a creek bottom."""
    t0 = time.time()
    H, W = bike.shape
    offs = np.asarray(offs, np.int64)
    if jump is not None and len(jump[0]):
        o = np.argsort(jump[0])
        jsrc, jdst = np.asarray(jump[0], np.int64)[o], np.asarray(jump[1], np.int64)[o]
    else:
        jsrc = jdst = None

    def lake(c):
        if jsrc is None:
            return np.zeros(len(c), bool), c
        k = np.minimum(np.searchsorted(jsrc, c), len(jsrc) - 1)
        return jsrc[k] == c, jdst[k]

    def step(c):
        """The cell before each cell on its fastest route (itself at a road cell)."""
        t = tbf[c].astype(np.int64)
        r, q = np.divmod(c, W)
        o = offs[np.clip(t, 0, None)]
        p = np.where(t >= 0, (r - o[:, 0]) * W + (q - o[:, 1]), c)
        hit, dst = lake(c)
        return np.where(hit & (t < 0), dst, p)

    ids, S = [], []
    for what, (keys, cells) in starts.items():
        ids += [(what, k) for k in keys]
        S.append(np.asarray(cells, np.int64))
    S = np.concatenate(S) if S else np.zeros(0, np.int64)
    has = S >= 0
    hit, dst = lake(np.where(has, S, 0))
    S = np.where(has & hit, dst, S)          # a start in a lake: the route ends at the shore it leads to
    # every cell on a route, and the cell before it
    seen = np.zeros(H * W, bool)
    front, parts = np.unique(S[has]), []
    while front.size:
        seen[front] = True
        parts.append(front)
        nxt = step(front)
        nxt = nxt[nxt != front]
        front = np.unique(nxt[~seen[nxt]])
    del seen
    R = np.sort(np.concatenate(parts)) if parts else np.zeros(0, np.int64)
    n = len(R)
    Pl = np.searchsorted(R, step(R))
    root = Pl == np.arange(n)
    a = area.ravel()[R]
    creek = (a >= creek_km2) & (a < (creek_max_km2 or np.inf))
    kind = np.where(bike.ravel()[R], 0, np.where(on_path.ravel()[R], 1, np.where(creek, 3, 2))).astype(np.int8)
    del a
    # nodes: starts, trailheads, junctions, changes of kind; a segment runs from a node to the next one down
    sl = np.searchsorted(R, S[has])
    fixed = root.copy()
    fixed[sl] = True
    fixed |= np.bincount(Pl[~root], minlength=n) >= 2
    rr, qq = np.divmod(R, W)
    X, Y = transform.c + (qq + 0.5) * transform.a, transform.f + (rr + 0.5) * transform.e
    down_m = np.hypot(X - X[Pl], Y - Y[Pl])          # from each cell to the next one down its route
    Pll = Pl.tolist()

    def cut(kind):
        """The segments: from each node (a start, a junction, a change of kind) down to the next node."""
        node = fixed.copy()
        node[Pl[~root & (kind != kind[Pl])]] = True
        heads = np.flatnonzero(node & ~root)
        nodel, cells, end = node.tolist(), [], []
        for x in heads.tolist():
            cs, y = [x], Pll[x]
            while not nodel[y]:
                cs.append(y)
                y = Pll[y]
            cells.append(cs)
            end.append(y)
        seg_of = np.full(n, -1, np.int64)
        seg_of[heads] = np.arange(len(heads))
        return heads, cells, np.asarray(end, np.int64), seg_of

    # A run shorter than MERGE_M between two runs of one other kind takes their kind (MERGE_OFF_M where both are off
    # trail or creek bottom); so does a route's first run, off trail or up a creek bottom, before a run of the other of
    # those two. Along a creek bottom the route steps on and off the cells that drain 1 km2 or more every few cells (a
    # dotted line broken by dashes every 20-40 m), and a walk across a fire road "rode" its few metres. The shortest runs
    # first, never two neighbours in one round; each change joins runs, so the rounds end. Drawing only: the approach
    # times are 08_hike.py's, and the popup's miles move by metres (not at all between off trail and creek bottom).
    merged = 0.0
    for _ in range(100):
        heads, seg_cells, seg_end, seg_of = cut(kind)
        m = len(heads)
        parent = seg_of[seg_end]
        skind = kind[heads]
        if not m:
            break
        sc = np.repeat(np.arange(m), [len(c) for c in seg_cells])
        slen = np.bincount(sc, weights=down_m[np.fromiter(itertools.chain.from_iterable(seg_cells), np.int64)],
                           minlength=m)
        up = parent >= 0
        pk = np.where(up, skind[np.maximum(parent, 0)], -1)
        nk = np.bincount(parent[up], minlength=m)
        kid = np.full(m, -1, np.int64)
        kid[parent[up]] = np.flatnonzero(up)                 # a child (the only one where nk == 1)
        ck = np.where(nk == 1, skind[np.maximum(kid, 0)], -1)
        off = (skind >= 2) & (pk >= 2)
        cand = up & (slen < np.where(off, MERGE_OFF_M, MERGE_M)) & (pk != skind) & (((nk == 1) & (ck == pk)) |
                                                                                  ((nk == 0) & off))
        if not cand.any():
            break
        taken = np.zeros(m, bool)
        for s in np.flatnonzero(cand)[np.argsort(slen[cand], kind="stable")].tolist():
            if taken[parent[s]] or (nk[s] == 1 and taken[kid[s]]):
                continue
            taken[s] = True
            kind[seg_cells[s]] = pk[s]
            merged += slen[s]
    else:
        heads, seg_cells, seg_end, seg_of = cut(kind)
        m = len(heads)
        parent = seg_of[seg_end]
        skind = kind[heads]
    assert sum(map(len, seg_cells)) == n - int(root.sum()), "a route cell is in no segment or in two"
    # numbered parents first (depth-first from the trailheads, a child right after its parent where it can be)
    kids, tops = [[] for _ in range(m)], []
    for s, p in enumerate(parent.tolist()):
        (tops if p < 0 else kids[p]).append(s)
    order, stack = [], tops[::-1]
    while stack:
        s = stack.pop()
        order.append(s)
        stack.extend(kids[s][::-1])
    assert len(order) == m, "the routes' segments do not form a forest"
    order = np.asarray(order, np.int64)
    new = np.empty(m, np.int64)
    new[order] = np.arange(m)
    # geometry: cell centres, or the line a run is on
    coords = [None] * m
    unsnapped = 0
    for k, lines in ((0, _Lines(bike_lines)), (1, _Lines(path_lines))):
        segs = np.flatnonzero(skind == k).tolist()
        if not segs:
            continue
        C = np.fromiter(itertools.chain.from_iterable(seg_cells[s] for s in segs), np.int64)
        bnd = np.r_[0, np.cumsum([len(seg_cells[s]) for s in segs])].tolist()
        A, D = lines.snap(shapely.points(X[C], Y[C]), list(zip(bnd[:-1], bnd[1:])))
        unsnapped += int((A < 0).sum())
        Al, Dl = A.tolist(), D.tolist()
        for i, s in enumerate(segs):
            out, j, b = [], bnd[i], bnd[i + 1]
            while j < b:
                L = Al[j]
                if L < 0:
                    out.append((X[C[j]], Y[C[j]]))
                    j += 1
                    continue
                g0 = j
                while True:          # on along L, over at most GAP_CELLS cells near no line (a run joined above)
                    nx = j + 1
                    while nx < b and Al[nx] < 0 and nx - j <= GAP_CELLS:
                        nx += 1
                    if nx < b and Al[nx] == L and abs(Dl[nx] - Dl[j]) <= JUMP_M:
                        j = nx
                    else:
                        break
                out.extend(lines.piece(L, Dl[g0], Dl[j]))
                j += 1
            coords[s] = out
    for s in np.flatnonzero(skind >= 2).tolist():
        c = seg_cells[s]
        coords[s] = list(zip(X[c], Y[c]))
    # the trailheads: on the open road the route starts from
    rl = np.flatnonzero(root)
    roads = _Lines(road_lines)
    A, D = roads.snap(shapely.points(X[rl], Y[rl]), [(i, i + 1) for i in range(len(rl))])
    root_xy = {int(x): (roads.piece(L, d, d)[0] if L >= 0 else (X[x], Y[x]))
               for x, L, d in zip(rl.tolist(), A.tolist(), D.tolist())}
    geoms = np.empty(m, dtype=object)
    for s in range(m):
        end = coords[parent[s]][0] if parent[s] >= 0 else root_xy[seg_end[s]]
        pts = coords[s] + [end]
        geoms[s] = shapely.LineString(pts if len(pts) > 1 else pts * 2)
    for k in range(4):
        ks = np.flatnonzero(skind == k)
        thin = shapely.simplify(geoms[ks], THIN_M[k], preserve_topology=False)
        # (Douglas-Peucker keeps both ends, where the segments meet; a line it would empty stays as it was)
        good = ~shapely.is_empty(thin) & (shapely.get_num_coordinates(thin) >= 2)
        geoms[ks[good]] = thin[good]
    seg_len = shapely.length(geoms)
    # metres of each kind along each route: summed from the trailhead down
    acc = np.zeros((m, 4))
    for s in order.tolist():
        if parent[s] >= 0:
            acc[s] = acc[parent[s]]
        acc[s, skind[s]] += seg_len[s]
    gdf = gpd.GeoDataFrame({"seg": np.arange(m), "parent": np.where(parent[order] >= 0, new[parent[order]], -1),
                            "kind": skind[order]}, geometry=geoms[order], crs=crs)
    gdf.to_file(f"{out_dir}/hike_routes.gpkg", layer="routes")
    first = np.full(len(S), -1, np.int64)
    first[has] = seg_of[sl]                                  # -1 also where the route starts on the road itself
    rows = pd.DataFrame({"what": [w for w, _ in ids], "id": [k for _, k in ids],
                         "seg": np.where(first >= 0, new[np.maximum(first, 0)], -1)})
    for k, name in enumerate(KINDS):
        rows[f"{name}_m"] = np.where(first >= 0, np.round(acc[np.maximum(first, 0), k]), 0).astype(int)
    rows[has].to_csv(f"{out_dir}/hike_route_starts.csv", index=False)
    km = {name: shapely.length(geoms[skind == k]).sum() / 1000 for k, name in enumerate(KINDS)}
    wet = int(lake(R)[0].sum())    # a route that crossed a lake: its water cell leads straight to the shore (08_hike.py)
    print(f"{label}: approach routes for {int(has.sum())} starts: {m:,} segments over {n:,} cells from {len(rl)} "
          f"trailheads; network km " + ", ".join(f"{k} {v:,.1f}" for k, v in km.items())
          + f"; short runs joined to their neighbours' kind {merged / 1000:,.1f} km; {unsnapped} bike / "
          f"trail cells with no line within {SNAP_M} m; {wet} lake cells on routes; {time.time() - t0:.0f} s")
    return gdf, rows[has]


# ---- for the map pages (06_map.py) ----
def _enc(v):
    """One value of Google's encoded polyline algorithm."""
    v = ~(v << 1) if v < 0 else v << 1
    out = []
    while v >= 0x20:
        out.append(chr((0x20 | (v & 0x1f)) + 63))
        v >>= 5
    out.append(chr(v + 63))
    return "".join(out)


def encode(deltas):
    return "".join(_enc(int(a)) + _enc(int(b)) for a, b in deltas)


def route_text(b, t, o, c, mi):
    """The popup's route line from the metres of each kind (bike, trail or road, off trail, creek bottom), in miles
    (mi: units.mi, which takes km): 'bike 3.1 mi · hike 1.2 mi, 0.9 mi of it on trails or roads'. Roads: about half
    of what is walked on a mapped line in NE Connecticut is a private road or driveway, not a trail. Where the part on
    them rounds to the whole walk though some of it is off trail ("hike 0.3 mi, 0.3 mi of it ..."), it says "mostly"."""
    hike = t + o + c
    if b + hike < NEAR_M:
        return "starts right by the road"
    out = [f"bike {mi(b / 1000)}"] if b >= NEAR_M else []
    if hike >= NEAR_M or not out:
        on = ("all on trails or roads" if o + c < NEAR_M else "off trail" if t < NEAR_M else
              "mostly on trails or roads" if mi(t / 1000) == mi(hike / 1000) else f"{mi(t / 1000)} of it on trails or roads")
        out.append(f"hike {mi(hike / 1000)}, {on}")
    return " · ".join(out)


def pack(map_out, ranges, epsg, stream_sids, lake_sids, mi):
    """routes_data.js's contents (or None where no range has routes): the segments the drawn reaches' routes use and,
    for each drawn reach in the order of the pages' streams and streams_lake layers, its route. stream_sids, lake_sids:
    each drawn feature's reach (a piece drawn for another reach, "<sid>+<n>", takes that reach's)."""
    from pyproj import Transformer
    segs, starts, base = [], [], 0
    for r in ranges:
        g, c = f"{map_out}/{r}/hike_routes.gpkg", f"{map_out}/{r}/hike_route_starts.csv"
        if not (os.path.exists(g) and os.path.exists(c)):
            continue
        sg = gpd.read_file(g).sort_values("seg").reset_index(drop=True)
        st = pd.read_csv(c)
        st = st[st.what.eq("stream")]
        sg["parent"] = np.where(sg.parent >= 0, sg.parent + base, -1)
        segs.append(sg)
        starts.append(st.assign(seg=np.where(st.seg >= 0, st.seg + base, -1)))
        base += len(sg)
    if not segs:
        return None
    sg = gpd.GeoDataFrame(pd.concat(segs, ignore_index=True), crs=segs[0].crs)
    st = pd.concat(starts, ignore_index=True).drop_duplicates("id")
    keys = set(pd.Series(list(stream_sids) + list(lake_sids), dtype=object).dropna().astype(str)
               .str.split("+").str[0])
    st = st[st.id.astype(str).isin(keys)].reset_index(drop=True)
    par = sg.parent.to_numpy()
    used = np.zeros(len(sg), bool)
    for s in st.seg[st.seg >= 0].tolist():
        while s >= 0 and not used[s]:
            used[s] = True
            s = par[s]
    keep = np.flatnonzero(used)
    renum = np.full(len(sg), -1, np.int64)
    renum[keep] = np.arange(len(keep))
    sg = sg.iloc[keep].reset_index(drop=True)
    par = np.where(sg.parent >= 0, renum[np.maximum(sg.parent.to_numpy(), 0)], -1)
    assert (par < np.arange(len(sg))).all(), "a segment comes before its parent"
    xy, ix = shapely.get_coordinates(sg.geometry.values, return_index=True)
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(xy[:, 0], xy[:, 1])
    E = np.column_stack([np.round(np.asarray(lat) * 1e5), np.round(np.asarray(lon) * 1e5)]).astype(np.int64)
    off = np.r_[0, np.cumsum(np.bincount(ix, minlength=len(sg)))]
    g = []
    for s in range(len(sg)):
        P = E[off[s]:off[s + 1]][::-1]                       # from the far end (the parent's first point) back
        if par[s] >= 0:
            b = E[off[par[s]]]
            assert (P[0] == b).all(), "a segment does not end where its parent starts"
            P = P[1:]
        else:
            b = np.zeros(2, np.int64)
        g.append(encode(np.diff(np.vstack([b, P]), axis=0)))
    texts = [route_text(*v, mi) for v in st[[f"{k}_m" for k in KINDS]].to_numpy(float).tolist()]
    tx = sorted(set(texts))
    ti = {t: i for i, t in enumerate(tx)}
    ri = {k: i for i, k in enumerate(st.id.astype(str))}
    look = lambda sids: [ri.get(str(s).split("+")[0], -1) if isinstance(s, str) else -1 for s in sids]
    return {"v": 1, "k": "".join(map(str, sg.kind.astype(int))),
            "p": (np.arange(len(sg)) - np.where(par >= 0, par, np.arange(len(sg)))).tolist(),
            "g": g, "t": tx,
            "r": [[int(renum[s]) if s >= 0 else -1, ti[t]] for s, t in zip(st.seg.tolist(), texts)],
            "s": look(stream_sids), "l": look(lake_sids)}


def write(path, data):
    """routes_data.js: a plain script, so the pages work opened from disk too."""
    with open(path, "w") as f:
        f.write("window.ROUTES=" + json.dumps(data, separators=(",", ":")) + ";\n")
