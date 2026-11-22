"""Links where the D8 paths stop short: at the edges between study boxes, and in reservoirs.

Each range's hydrology (03_hydrology.py) sees only its own box, so a creek that crosses into the next box starts
there again with no drainage area. In the Piru & Castaic box the Santa Clara River arrived from the San Gabriel box
with none, so Piru Creek won the trunk and the river's own valley was labelled as a fork. inflows() follows every
basin that drains off an edge two boxes share into the neighbouring box and carries its area across (with whatever
flowed into it from a third box), so 05c_drainages.py can add it along the creek there. 06_map.py uses the same edge
and downhill helpers to give a basin cut by an edge the drainage it continues into.

pysheds can't route water across a big flat lake surface either, so every large reservoir ends its D8 paths in pits
and the creek below the dam starts again near nothing (San Gabriel Reservoir, Castaic, Pyramid, Big Tujunga, Lake
Hemet...). With through_dams, inflows() also carries a reservoir's area to the cell below its dam where the water
goes on, found on the NHDPlus flowlines leaving the lake, or for a pond NHDPlus has no flowline for, on the detailed
NHD stream line leaving it. Drainages still end at dams; only areas use this.

A river that enters from outside every box (the Maury above Goshen Pass, Otter Creek, the Chattahoochee below Lake
Lanier, the Snake) started with nothing too. Where an NHDPlus V2 river crosses the outer boundary flowing in, its
drainage there (the flowline's total, less what the box's own routing already has at that spot, so a river that
only brushes the boundary adds nothing) is carried in the same way ("outside"), in both variants.
"""
import json, os
from collections import defaultdict
import numpy as np, pandas as pd, geopandas as gpd, rasterio, rasterio.windows, shapely, shapely.ops
from config import REGIONS, ROOT, RES, CRS, SHARED_DERIVED, NATIONAL, derived_dir, raw_dir

D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
CACHE = f"{SHARED_DERIVED}/inflows.json"
VERSION = 16
MIN_KM2 = 0.1    # smaller basins draining off an edge or into a lake add nothing worth carrying
OUTSIDE_MIN_KM2 = 10   # a river entering from outside every box brings at least this much, or it isn't carried


def fdir_path(region):
    return f"{derived_dir(region)}/flowdir.tif"


def jump(ptr):
    """Pointer jumping: follow ptr to its fixed point (each round doubles the distance covered)."""
    for _ in range(40):
        pp = ptr[ptr]
        if np.array_equal(pp, ptr):
            return pp
        ptr = pp
    return ptr


def graph(fdir):
    """Downstream neighbour of every cell (flat index) and the outlet cell it drains to. Off-grid cells, sinks and
    flats point at themselves."""
    H, W = fdir.shape
    idx = np.arange(H * W, dtype=np.int32)
    rr, cc = np.divmod(idx, W)
    f = fdir.ravel()
    for code, (dr, dc) in D8.items():
        k = f == code
        rr[k] += dr
        cc[k] += dc
    off = (rr < 0) | (rr >= H) | (cc < 0) | (cc >= W)
    nxt = np.where(off, idx, rr * W + cc).astype(np.int32)
    del idx, rr, cc, off
    return nxt, jump(nxt)


def exit_points(fdir, T, outlets):
    """Where the basins with these outlet cells leave the box: the centre of the first cell outside it (x, y arrays),
    NaN for sinks such as dams and lakes. pysheds keeps flow inside the grid: a stream leaving the box runs along the
    border to a low point and ends in a pit cell there, so outlets on the border also leave the box; step one cell
    straight out from that border."""
    H, W = fdir.shape
    orow, ocol = np.divmod(np.asarray(outlets, dtype=np.int64), W)
    codes = fdir[orow, ocol]
    dd = np.array([D8.get(int(k), (0, 0)) for k in codes], dtype=np.int64).reshape(-1, 2)
    trow, tcol = orow + dd[:, 0], ocol + dd[:, 1]
    off = np.isin(codes, list(D8)) & ((trow < 0) | (trow >= H) | (tcol < 0) | (tcol >= W))
    on_edge = (orow == 0) | (orow == H - 1) | (ocol == 0) | (ocol == W - 1)
    trow = np.where(off, trow, np.where(orow == 0, -1, np.where(orow == H - 1, H, orow)))
    tcol = np.where(off, tcol, np.where(ocol == 0, -1, np.where(ocol == W - 1, W, ocol)))
    leaves = off | on_edge
    ox, oy = T * (tcol + 0.5, trow + 0.5)
    return np.where(leaves, np.round(ox), np.nan), np.where(leaves, np.round(oy), np.nan)


def shared_edges(regions):
    """Edges two boxes share (boxes meet edge to edge), at least 1 km long: {(a, b): MultiLineString}. A basin links
    only across such an edge: streams leaving along a border run to its lowest point, which can be a corner that
    merely overlaps another box (the San Gabriels' south-west corner sits inside the Santa Monica box)."""
    out = {}
    for a in regions:
        for b in regions:
            if a != b:
                seg = shapely.box(*REGIONS[a]["bbox"]).boundary.intersection(shapely.box(*REGIONS[b]["bbox"]).boundary)
                lines = [g for g in getattr(seg, "geoms", [seg]) if g.geom_type == "LineString" and g.length >= 1000]
                if lines:
                    out[(a, b)] = shapely.MultiLineString(lines)
    return out


def neighbours(region, x, y, edges):
    """(neighbour, outward (dx, dy)) for each box whose shared edge with `region` passes within 60 m of (x, y)."""
    pt = shapely.Point(x, y)
    for (a, b), seg in edges.items():
        if a == region and seg.distance(pt) <= 60:
            ca, cb = shapely.box(*REGIONS[a]["bbox"]).centroid, shapely.box(*REGIONS[b]["bbox"]).centroid
            vertical = abs(seg.bounds[2] - seg.bounds[0]) < 1
            yield b, ((np.sign(cb.x - ca.x), 0) if vertical else (0, np.sign(cb.y - ca.y)))


def downhill(fd, T, x, y, away, steps=600):
    """Cells (row, col, x, y) downhill from (x, y) on a neighbour's grid, once the path has moved more than 25 m away
    from the shared edge (`away` = outward (dx, dy)); nothing if it hasn't within 100 cells. Edge cells first run
    along the border; where a creek really enters the source box from the neighbour, the source's edge cells still
    "exit" there, but the neighbour's water stays on the border instead of heading away."""
    c, r = ~T * (x, y)
    r, c = int(np.floor(r)), int(np.floor(c))
    left = False
    for k in range(steps):
        if not (0 <= r < fd.shape[0] and 0 <= c < fd.shape[1]):
            return
        px, py = T * (c + 0.5, r + 0.5)
        left = left or (px - x) * away[0] + (py - y) * away[1] > 25
        if left:
            yield r, c, px, py
        elif k >= 100:
            return
        st = D8.get(int(fd[r, c]))
        if st is None:
            return
        r, c = r + st[0], c + st[1]


_STITCHED = None
def stitched():
    """The boxes whose flow directions 03b_stitch.py worked out together with their neighbours: a cell on an edge
    they share drains straight into the next box, so a crossing there is exact."""
    global _STITCHED
    if _STITCHED is None:
        p = f"{SHARED_DERIVED}/stitched.json"
        _STITCHED = set(json.load(open(p))) if os.path.exists(p) else set()
    return _STITCHED


def crossing(region, fd, T, x, y, away, radius=10):
    """Cells (row, col, x, y) along a creek entering `region`'s grid at (x, y).
    Across an edge shared by two boxes that 03b_stitch.py routed together: simply the D8 path from that cell (the
    box it leaves points exactly at it).
    Elsewhere (in from outside the map, or boxes still routed alone): downhill() from there; or, where the box's
    own border handling ends the creek in a pit on the edge (a road fill or a low bump just inside leaves the
    border cell lowest: Bouquet Canyon entering the Piru box), from the lowest cell within `radius` cells inside the
    box whose path heads away from the edge."""
    if region in stitched():
        back = shapely.Point(x - away[0] * RES, y - away[1] * RES)
        if any(r != region and shapely.box(*REGIONS[r]["bbox"]).contains(back) for r in stitched()):
            c, r = ~T * (x, y)
            r, c = int(np.floor(r)), int(np.floor(c))
            for _ in range(600):
                if not (0 <= r < fd.shape[0] and 0 <= c < fd.shape[1]):
                    return
                yield (r, c, *(T * (c + 0.5, r + 0.5)))
                st = D8.get(int(fd[r, c]))
                if st is None:
                    return
                r, c = r + st[0], c + st[1]
            return
    path = downhill(fd, T, x, y, away)
    hit = next(path, None)
    if hit is None:
        c, r = ~T * (x, y)
        r, c = int(np.floor(r)), int(np.floor(c))
        r0, c0 = max(r - radius, 0), max(c - radius, 0)
        r1, c1 = min(r + radius + 1, fd.shape[0]), min(c + radius + 1, fd.shape[1])
        if r0 >= r1 or c0 >= c1:
            return
        with rasterio.open(f"{derived_dir(region)}/dem_filled.tif") as src:
            z = src.read(1, window=rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0), masked=True).astype(float)
        for k in np.argsort(z.filled(np.inf), axis=None):
            rr, cc = np.unravel_index(k, z.shape)
            if np.ma.is_masked(z[rr, cc]):
                break
            px, py = T * (c0 + cc + 0.5, r0 + rr + 0.5)
            if (px - x) * away[0] + (py - y) * away[1] <= 0:    # on the edge itself
                continue
            path = downhill(fd, T, px, py, away)
            hit = next(path, None)
            if hit is not None:
                break
    if hit is not None:
        yield hit
        yield from path


def walk(fd, r, c):
    """Flat index of the cell where the D8 path from (r, c) ends (the outlet graph() gives that cell)."""
    H, W = fd.shape
    for _ in range(10 ** 6):
        st = D8.get(int(fd[r, c]))
        if st is None or not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
            break
        r, c = r + st[0], c + st[1]
    return r * W + c


def _key(regions):
    from flowlib import FLOW
    files = [fdir_path(r) for r in regions] + [f"{raw_dir(r)}/nhd_flowlines.gpkg" for r in regions] + [
        f"{FLOW}/reservoirs.gpkg", f"{FLOW}/nhdplus_v2.gpkg", f"{SHARED_DERIVED}/stitched.json"]
    return {"version": VERSION, **{f: [os.path.getmtime(f), os.path.getsize(f)] for f in files if os.path.exists(f)}}


def _outflow_lines(region):
    """The box's detailed NHD stream lines (NHD High Resolution, 1:24,000 or better; 02_download_vectors.py), merged
    into single lines, with an index and the lines starting at each point: (lines, tree, begins), or None. Pipelines,
    tunnels, canals and ditches don't count."""
    p = f"{raw_dir(region)}/nhd_flowlines.gpkg"
    if not os.path.exists(p):
        return None
    fl = gpd.read_file(p).to_crs(CRS)
    fl = fl[fl.ftype.isin([460, 558, 334]) & fl.geometry.notna()]
    lines = []
    for g in shapely.line_merge(fl.geometry.force_2d().values):
        lines += [q for q in getattr(g, "geoms", [g]) if q.geom_type == "LineString" and q.length > 1]
    if not lines:
        return None
    begins = defaultdict(list)
    for i, g in enumerate(lines):
        begins[(round(g.coords[0][0]), round(g.coords[0][1]))].append(i)
    return lines, shapely.STRtree(lines), begins


def _pond_outflow(fd, T, lake, dead, detailed):
    """(row, col) where the water of a lake NHDPlus has no flowline for goes on, from the detailed NHD stream lines:
    a line that starts in the lake and ends outside it is its outflow (they are drawn downstream). Walk down it and the
    lines it runs into, 25 m at a time for up to 3 km, to the first cell whose D8 path doesn't lead back into the
    lake's dead ends; None where no line leaves the lake, or each one leaves the box first."""
    lines, tree, begins = detailed
    H, W = fd.shape
    lk = lake.buffer(30)
    for i in tree.query(lk, predicate="intersects"):
        g = lines[i]
        if not lk.contains(shapely.Point(g.coords[0])) or lk.contains(shapely.Point(g.coords[-1])):
            continue
        length, seen = 0.0, {i}
        while g is not None and length < 3000:
            for d in np.arange(0, g.length, 25.0):
                p = g.interpolate(d)
                if lk.contains(p):
                    continue
                c, r = ~T * (p.x, p.y)
                r, c = int(np.floor(r)), int(np.floor(c))
                if not (0 <= r < H and 0 <= c < W):
                    length = 1e9                    # this brook leaves the box first
                    break
                if walk(fd, r, c) not in dead:
                    return r, c
            length += g.length
            nx = [j for j in begins.get((round(g.coords[-1][0]), round(g.coords[-1][1])), []) if j not in seen]
            g = lines[nx[0]] if nx else None
            seen.update(nx[:1])
    return None


def _dam_links(fd, T, sinks, lakes, v2, by_seq, detailed=None, ponds=None, pond_dead=None):
    """{sink outlet: (row, col)} for dead ends inside a reservoir: the cell below its dam where the water goes on.
    NHDPlus says whether the lake has an outflow and where: its outlet flowline (the most drainage inside the lake)
    and the flowlines below it. Walk down them from where the outlet flowline leaves the lake, 50 m at a time for up to
    3 km, to the first cell whose D8 path doesn't lead back into the lake's dead ends. A dead end counts for a lake
    within 400 m (Lake Mathews' is 338 m outside its outline). Lakes with no outflow (Baldwin Lake) and dead ends
    away from lakes (desert fans, gravel pits, the sea) stay closed.
    NHDPlus (1:100,000) doesn't have the brooks most small ponds sit on, and below such a pond the brook's drainage
    started again from nothing (66 ponds over six areas on 2026-11-19, 35 of them in north-east Connecticut), so its
    size and flow were low for a stretch. Where NHDPlus has no flowline in the lake, or its lines find no way on, the
    box's detailed NHD stream lines (`detailed`, from _outflow_lines) give it: _pond_outflow(). A lake whose NHDPlus
    outflow leaves the box first stays closed. 05c_drainages.py used these lines for the drainage names only."""
    if not sinks:
        return {}
    pts = gpd.GeoDataFrame({"o": list(sinks)}, geometry=gpd.points_from_xy(*zip(*sinks.values())), crs=CRS)
    # each dead end belongs to its nearest lake (the bigger one where it lies in two), so a pond beside a reservoir
    # can't claim the reservoir's dead ends
    hit = gpd.sjoin_nearest(pts, gpd.GeoDataFrame({"km2": lakes.area}, geometry=lakes.geometry, crs=CRS),
                            max_distance=400, distance_col="dist")
    hit = hit.sort_values(["dist", "km2"], ascending=[True, False]).drop_duplicates("o")
    H, W = fd.shape
    out = {}
    for li, grp in hit.groupby("index_right"):
        lake = lakes.geometry.iloc[li]
        dead = set(grp.o)
        entry, done = None, False
        ins = v2[v2.intersects(lake)]
        ins = ins[ins.geometry.intersection(lake).length >= 0.25 * ins.length]   # silted-up Matilija: 49 %
        lines = []
        if len(ins):
            fl = ins.loc[ins.totdasqkm.idxmax()]
            g = shapely.line_merge(fl.geometry)
            if g.geom_type != "LineString":             # NHDPlus stores flowlines as (usually one-part) multilines
                g = shapely.LineString([c for part in g.geoms for c in part.coords])
            inside = g.intersection(lake)
            t_end = max(g.project(shapely.Point(c)) for p in getattr(inside, "geoms", [inside]) for c in p.coords)
            lines = [shapely.ops.substring(g, t_end, g.length)]
            seq, length = fl.dnhydroseq, 0.0
            while seq in by_seq.index and length < 3000:
                below = by_seq.loc[seq]
                lines.append(below.geometry)
                length += below.geometry.length
                seq = below.dnhydroseq
        for ln in lines:
            for part in getattr(ln, "geoms", [ln]):
                if part.is_empty or part.geom_type != "LineString":
                    continue
                for d in np.arange(0, part.length, 50.0):
                    p = part.interpolate(d)
                    if lake.contains(p):
                        continue
                    c, r = ~T * (p.x, p.y)
                    r, c = int(np.floor(r)), int(np.floor(c))
                    if not (0 <= r < H and 0 <= c < W):
                        done = True                     # the creek leaves the box first: leave it closed
                        break
                    if walk(fd, r, c) not in dead:
                        entry, done = (r, c), True
                        break
                if done:
                    break
            if done:
                break
        if entry is None and not done and detailed is not None:    # no NHDPlus way on, and none that leaves the box
            entry = _pond_outflow(fd, T, lake, dead, detailed)
            if entry and ponds is not None:
                ponds.append(entry)
                pond_dead.update(dead)
        if entry:
            out.update({o: entry for o in dead})
    return out


def _build(regions):
    from flowlib import FLOW, reservoirs
    from config import SHARED
    # the reservoir list leaves out lagoons (it's for coastal ones), but Castaic's water ends in Castaic Lagoon, the
    # afterbay below the dam; a coastal lagoon has no flowline below it, so it stays closed anyway
    lag = [gpd.read_file(g, layer="NHDWaterbody", where="gnis_name LIKE '%Lagoon%' AND ftype IN (390, 436)")
           for g in sorted({f"{NATIONAL}/NHD_H_{h}_HU4_GPKG.gpkg" for v in REGIONS.values() for h in v["hu4"]})]
    lag = [l.to_crs(CRS)[["gnis_name", "geometry"]] for l in lag if len(l)]
    lakes = pd.concat([reservoirs()[["gnis_name", "geometry"]], *lag], ignore_index=True)
    lakes = gpd.GeoDataFrame(lakes, geometry=lakes.geometry.force_2d(), crs=CRS)
    v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg", columns=["comid", "hydroseq", "dnhydroseq", "totdasqkm", "ftype", "gnis_name"]).to_crs(CRS)
    by_seq = v2.drop_duplicates("hydroseq").set_index("hydroseq")
    edges = shared_edges(regions)
    fds, exits, own, links = {}, {}, {}, []      # own: (region, outlet) -> its basin km2; links: (src, region, row, col, kind)
    ponds, pond_dead = [], set()                  # the cells below the ponds whose way on comes from the detailed lines
    for r in regions:
        with rasterio.open(fdir_path(r)) as src:
            fds[r] = (src.read(1), src.transform)
        fd, T = fds[r]
        H, W = fd.shape
        _, outlet = graph(fd)
        uo, n = np.unique(outlet, return_counts=True)
        del outlet
        km2 = n * RES * RES / 1e6
        ox, oy = exit_points(fd, T, uo)
        orow, ocol = np.divmod(uo, W)
        if r in stitched():
            # Routed together with its neighbours (03b_stitch.py): area_km2.tif already counts the cells upstream in
            # the other boxes. So a basin that leaves over an edge hands on nothing of its own (the next box has it),
            # only what came into it from outside the map or over a dam; and a lake's dead end holds everything the
            # raster has there, wherever it fell.
            with rasterio.open(f"{derived_dir(r)}/area_km2.tif") as src:
                km2 = np.maximum(km2, src.read(1).ravel()[uo].astype(float))
        exit_ = ~np.isnan(ox) & (km2 >= MIN_KM2)
        sink = ((orow > 0) & (orow < H - 1) & (ocol > 0) & (ocol < W - 1) & ~np.isin(fd[orow, ocol], list(D8))
                & (km2 >= MIN_KM2))
        exits[r] = {int(o): (float(x), float(y)) for o, x, y in zip(uo[exit_], ox[exit_], oy[exit_])}
        own.update({(r, int(o)): float(a) for o, a in zip(uo[sink], km2[sink])})
        own.update({(r, int(o)): (0.0 if r in stitched() else float(a)) for o, a in zip(uo[exit_ & ~sink], km2[exit_ & ~sink])})
        sinks = {int(o): T * (c + 0.5, rr + 0.5) for o, rr, c in zip(uo[sink], orow[sink], ocol[sink])}
        for o, (row, col) in _dam_links(fd, T, sinks, lakes, v2, by_seq, _outflow_lines(r), ponds, pond_dead).items():
            links.append(((r, o), r, row, col, "pond" if o in pond_dead else "dam"))
    # each exit -> the cell in the neighbouring box where its creek heads away from the edge
    for r in regions:
        for o, (x, y) in exits[r].items():
            for b, away in neighbours(r, x, y, edges):
                hit = next(crossing(b, *fds[b], x, y, away), None)
                if hit:
                    links.append(((r, o), b, hit[0], hit[1], "edge"))
                    break
    # rivers entering from outside every box: NHDPlus rivers that cross the outer boundary flowing in
    boxes = {r: shapely.box(*REGIONS[r]["bbox"]) for r in regions}
    union = shapely.unary_union(list(boxes.values()))
    riv = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"]) & (v2.totdasqkm >= OUTSIDE_MIN_KM2)]
    riv = riv[riv.intersects(union.boundary)]
    found, traces = [], []
    # what the edge links already bring in, per link: a river weaving along the boxes' edges (the Santa Clara at
    # Fillmore) comes in from the neighbouring box and from outside within a few km, and must count once
    edge_links = [l for l in links if l[4] == "edge"]
    into_e, tot_e = defaultdict(list), {}
    for src, b_, row_, col_, _ in edge_links:
        into_e[(b_, walk(fds[b_][0], row_, col_))].append(src)
    def carried(key, path=frozenset()):
        if key not in tot_e:
            tot_e[key] = own.get(key, 0.0) + sum(carried(s_, path | {key}) for s_ in into_e.get(key, [])
                                                 if s_ not in path and s_ != key)
        return tot_e[key]
    for f in riv.sort_values("totdasqkm", ascending=False).itertuples():
        g = f.geometry if f.geometry.geom_type == "LineString" else max(f.geometry.geoms, key=lambda q: q.length)
        g = shapely.LineString([c[:2] for c in g.coords])
        last = shapely.Point(g.coords[-1])                       # flowlines are digitised downstream
        if not union.contains(last):
            continue
        cut = g.intersection(union.boundary)
        pts = [q for q in getattr(cut, "geoms", [cut]) if q.geom_type == "Point"]
        if not pts:
            continue
        # its last crossing, if that one comes in from outside: the flowline may start outside, or start inside,
        # leave and come back (the Snake below Jackson Lake weaves across the north edge at Moran)
        t = max(g.project(q) for q in pts)
        pt = g.interpolate(t)
        if union.contains(g.interpolate(max(t - 15, 0))) or t < 15:
            continue
        b = next((r for r in regions if boxes[r].buffer(1).contains(last)), None)
        if b is None:
            continue
        x0, y0, x1, y1 = REGIONS[b]["bbox"]
        away = min(((abs(pt.x - x0), (1, 0)), (abs(pt.x - x1), (-1, 0)), (abs(pt.y - y0), (0, 1)), (abs(pt.y - y1), (0, -1))))[1]
        fd_b, T_b = fds[b]
        kind = "outside"
        lake = lakes[lakes.distance(pt) <= 150]
        hit = None
        if len(lake):        # the river comes in through a reservoir (the Chattahoochee in Lake Lanier): its water
            lk = lake.geometry.union_all()                   # goes on below the dam. Follow the mapped river down
            lines, seq, length = [shapely.ops.substring(g, t, g.length)], f.dnhydroseq, g.length - t   # to the first
            while seq in by_seq.index and length < 25000:    # cell outside the lake (up to 25 km)
                nx_ = by_seq.loc[seq]
                lines.append(nx_.geometry)
                length += nx_.geometry.length
                seq = nx_.dnhydroseq
            kind, gone = "dam", 0.0
            for ln in lines:
                for part in getattr(ln, "geoms", [ln]):
                    if part.is_empty or part.geom_type != "LineString":
                        continue
                    for d_ in np.arange(50.0, part.length, 50.0):
                        q = part.interpolate(d_)
                        c_, r_ = ~T_b * (q.x, q.y)
                        r_, c_ = int(np.floor(r_)), int(np.floor(c_))
                        if not (0 <= r_ < fd_b.shape[0] and 0 <= c_ < fd_b.shape[1]):
                            gone = 1e9                       # it leaves the box before the dam: not carried
                            break
                        if lk.distance(q) > 60:
                            hit = (r_, c_)
                            break
                    gone += part.length
                    if hit is not None or gone > 25000:
                        break
                if hit is not None or gone > 25000:
                    break
            if hit is None:
                continue
        if hit is None:
            hit = next(crossing(b, fd_b, T_b, pt.x, pt.y, away), None)
        if hit is None:
            continue
        if kind == "outside":
            # A flat river surface cut by the box edge drains back out through the edge (the edge is the lowest way
            # out the routing can see): the Snake's 2,112 km2 came in at Moran and left again 1 km on. Where the
            # path from the entry ends back on the border within 3 km, hand the water over further down the
            # mapped river instead: the first point, 50 m at a time for up to 6 km, whose path ends elsewhere.
            Hh, Ww = fd_b.shape
            e0 = walk(fd_b, hit[0], hit[1])
            er, ec = divmod(int(e0), Ww)
            ex, ey = T_b * (ec + 0.5, er + 0.5)
            if (er in (0, Hh - 1) or ec in (0, Ww - 1)) and np.hypot(ex - pt.x, ey - pt.y) < 3000:
                lines, seq, length = [shapely.ops.substring(g, t, g.length)], f.dnhydroseq, g.length - t
                while seq in by_seq.index and length < 6000:
                    nx_ = by_seq.loc[seq]
                    lines.append(nx_.geometry)
                    length += nx_.geometry.length
                    seq = nx_.dnhydroseq
                hit, gone = None, 0.0
                for ln in lines:
                    for part in getattr(ln, "geoms", [ln]):
                        if part.is_empty or part.geom_type != "LineString":
                            continue
                        for d_ in np.arange(50.0, part.length, 50.0):
                            q = part.interpolate(d_)
                            c_, r_ = ~T_b * (q.x, q.y)
                            r_, c_ = int(np.floor(r_)), int(np.floor(c_))
                            if gone + d_ > 6000 or not (0 <= r_ < Hh and 0 <= c_ < Ww):
                                break
                            if walk(fd_b, r_, c_) != e0:
                                hit = (r_, c_)
                                break
                        gone += part.length
                        if hit is not None or gone > 6000:
                            break
                    if hit is not None or gone > 6000:
                        break
                if hit is None:
                    continue                       # the river only brushes the box
        with rasterio.open(f"{derived_dir(b)}/area_km2.tif") as src:
            have = float(src.read(1, window=rasterio.windows.Window(int(hit[1]), int(hit[0]), 1, 1))[0, 0])
        have += sum(carried(src_) for src_, b_, row_, col_, _ in edge_links
                    if b_ == b and np.hypot(row_ - hit[0], col_ - hit[1]) * RES < 3000)
        # ... and what an earlier entry of the same river already brought down to here (the Santa Ana clips a
        # corner of the Santa Ana Mountains box twice)
        i_, mine = hit[0] * fd_b.shape[1] + hit[1], []
        for _ in range(200000):
            mine.append(i_)
            st_ = D8.get(int(fd_b.flat[i_]))
            if st_ is None:
                break
            r2, c2 = i_ // fd_b.shape[1] + st_[0], i_ % fd_b.shape[1] + st_[1]
            if not (0 <= r2 < fd_b.shape[0] and 0 <= c2 < fd_b.shape[1]):
                break
            i_ = r2 * fd_b.shape[1] + c2
        # (also what makes a side channel of a river already taken add nothing). Only where that entry's water
        # passes this spot, within 1.5 km: a tributary that joins the river further down is its own water
        # (Buffalo Fork and Pacific Creek join the Snake 2 km below where each comes in)
        # A twin channel of a river already taken (NHDPlus maps both arms of a split with nearly the same
        # drainage: the Santa Ana's 2,502 and 2,500 km2) is the same water where the two paths meet within 6 km.
        have += sum(a_ for b_, tr_, a_, q_, tot_ in traces if b_ == b and (
            not tr_.isdisjoint(mine[:150])
            or (abs(tot_ - float(f.totdasqkm)) <= 0.02 * tot_ and q_.distance(pt) < 3000 and not tr_.isdisjoint(mine[:600]))))
        more = float(f.totdasqkm) - have
        if more < max(OUTSIDE_MIN_KM2, 0.25 * float(f.totdasqkm)):   # the box's routing already carries the river
            continue
        key = ("outside", int(f.comid))
        own[key] = more
        links.append((key, b, int(hit[0]), int(hit[1]), kind))     # "dam": only in the through-dams totals
        traces.append((b, set(mine), more, pt, float(f.totdasqkm)))
        found.append((pt, (f.gnis_name if isinstance(f.gnis_name, str) else "unnamed river", b, round(more))))
    if found:
        print("crossbox: rivers entering from outside the boxes (km2 carried in):",
              ", ".join(f"{n} -> {b} {a}" for _, (n, b, a) in found[:14]) + (f" ... {len(found)} in all" if len(found) > 14 else ""))
    out = {}
    # edge: across edges and in from outside; full: also past dams and ponds; full_dams: past dams but not the ponds
    # NHDPlus has no flowline for (05c_drainages.py picks forks and drainage names on it, as before those were carried)
    for variant in ("edge", "full", "full_dams"):
        use = [l for l in links if variant == "full" or (variant == "full_dams" and l[4] != "pond")
               or l[4] in ("edge", "outside")]
        into = defaultdict(list)
        for src, b, row, col, _ in use:
            into[(b, walk(fds[b][0], row, col))].append(src)
        total = {}
        def tot(key, path=frozenset()):
            """A basin's own area plus everything flowing into it (a loop along a border counts once)."""
            if key not in total:
                total[key] = own.get(key, 0.0) + sum(tot(s, path | {key}) for s in into.get(key, [])
                                                     if s not in path and s != key)
            return total[key]
        ent = defaultdict(list)
        for src, b, row, col, kind in use:
            ent[b].append([int(row), int(col), round(tot(src), 3), src[0], kind])
        out[variant] = {r: ent.get(r, []) for r in regions}
        if variant == "full":
            # every place a creek's line breaks, for crossings(): where it leaves its box (edge links only), the
            # cell it goes on from in the next one (or below the dam, or inside the outer boundary) and what it carries
            out["cross"] = [[src[0], *(exits.get(src[0], {}).get(src[1], (None, None)) if kind == "edge" else (None, None)),
                             b, int(row), int(col), round(tot(src), 3), kind] for src, b, row, col, kind in use]
    dams = [l for l in links if l[4] in ("dam", "pond")]
    print(f"crossbox: {sum(l[4] == 'edge' for l in links)} edge links, {len(dams)} reservoir dead ends carried past "
          f"their dams ({len(ponds)} ponds NHDPlus has no flowline for, by the detailed NHD stream line leaving them)")
    # the dead ends themselves, for dam_links(): {region: [[dead-end cell, row, col of the cell below the dam]]}
    out["dams"] = {r: [[int(src[1]), int(row), int(col)] for src, b, row, col, kind in dams
                       if b == r and src[0] == r] for r in regions}
    return out


def inflows(region, through_dams=False, ponds=True):
    """[(row, col, km2, from_region, kind)]: where water from elsewhere enters `region`'s grid and how much drainage
    area it brings: from neighbouring boxes ("edge"), and with through_dams also from above a reservoir ("dam").
    The edge-only totals leave out any water that came over a dam; ponds=False leaves out what came past a pond NHDPlus
    has no flowline for (the detailed NHD stream line's way on). Built for every box at once and cached until a
    flowdir.tif, the reservoir list, the NHDPlus network or a box's NHD stream lines change."""
    key = "edge" if not through_dams else "full" if ponds else "full_dams"
    return [tuple(e) for e in _data()[key].get(region, [])]


def carried_km2(region):
    """Drainage area (km2) that reaches each cell of `region`'s grid from elsewhere, as a flat array: every
    inflows(region, through_dams=True) entry's area, added all the way down its D8 path (over a dam, past a pond,
    across a box edge, in from outside the map). 05c_drainages.py adds the same to each reach's own area
    (area_full_km2); 05_score.py's 1 km2 floor counts it, so the creek below a lake's outlet is drawn from the outlet."""
    with rasterio.open(fdir_path(region)) as src:
        fd = src.read(1)
    W = fd.shape[1]
    nxt, _ = graph(fd)
    ex = np.zeros(fd.size, np.float32)
    for row, col, km2, *_ in inflows(region, through_dams=True):
        i = row * W + col
        while True:
            ex[i] += km2
            if nxt[i] == i:
                break
            i = nxt[i]
    return ex


def dam_links(region):
    """{dead-end cell (flat index): (row, col)}: for every dead end in a lake or reservoir of `region` whose water
    goes on, the cell below the dam where it does (in the same box). 05c_drainages.py uses it to give a pond's
    basin the drainage its outflow joins. From the same cache as inflows()."""
    return {int(o): (int(r), int(c)) for o, r, c in _data().get("dams", {}).get(region, [])}


def crossings():
    """[(from box, exit x, exit y, into box, row, col, km2, kind)]: every link where a creek's D8 path stops and goes
    on elsewhere: across an edge two boxes share ("edge": the exit is the centre of the first cell outside the box
    it leaves), below a dam ("dam") or in from outside every box ("outside"); the last two have no exit. km2 is
    the drainage it carries, with everything upstream. 06_map.py draws the creek through with it."""
    return [tuple(e) for e in _data().get("cross", [])]


def _data():
    regions = [r for r in REGIONS if os.path.exists(fdir_path(r))]
    key = _key(regions)
    data = None
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            data = json.load(f)
        if data.get("key") != key:
            data = None
    if data is None:
        data = {"key": key, **_build(regions)}
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, CACHE)
    return data
