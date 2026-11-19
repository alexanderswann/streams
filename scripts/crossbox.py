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
goes on, found on the NHDPlus flowlines leaving the lake. Drainages still end at dams; only areas use this.
"""
import json, os
from collections import defaultdict
import numpy as np, pandas as pd, geopandas as gpd, rasterio, rasterio.windows, shapely, shapely.ops
from config import REGIONS, ROOT, RES, CRS

D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
CACHE = f"{ROOT}/data/derived/_shared/inflows.json"
VERSION = 5
MIN_KM2 = 0.1    # smaller basins draining off an edge or into a lake add nothing worth carrying


def fdir_path(region):
    return f"{ROOT}/data/derived/{region}/flowdir.tif"


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


def crossing(region, fd, T, x, y, away, radius=10):
    """Cells (row, col, x, y) along a creek entering `region`'s grid at (x, y): downhill() from there; or, where the
    box's own border handling ends the creek in a pit on the edge (a road fill or a low bump just inside leaves the
    border cell lowest: Bouquet Canyon entering the Piru box), from the lowest cell within `radius` cells inside the
    box whose path heads away from the edge."""
    path = downhill(fd, T, x, y, away)
    hit = next(path, None)
    if hit is None:
        c, r = ~T * (x, y)
        r, c = int(np.floor(r)), int(np.floor(c))
        r0, c0 = max(r - radius, 0), max(c - radius, 0)
        r1, c1 = min(r + radius + 1, fd.shape[0]), min(c + radius + 1, fd.shape[1])
        if r0 >= r1 or c0 >= c1:
            return
        with rasterio.open(f"{ROOT}/data/derived/{region}/dem_filled.tif") as src:
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
    files = [fdir_path(r) for r in regions] + [f"{FLOW}/reservoirs.gpkg", f"{FLOW}/nhdplus_v2.gpkg"]
    return {"version": VERSION, **{f: [os.path.getmtime(f), os.path.getsize(f)] for f in files if os.path.exists(f)}}


def _dam_links(fd, T, sinks, lakes, v2, by_seq):
    """{sink outlet: (row, col)} for dead ends inside a reservoir: the cell below its dam where the water goes on.
    NHDPlus says whether the lake has an outflow and where: its outlet flowline (the most drainage inside the lake)
    and the flowlines below it. Walk down them from where the outlet flowline leaves the lake, 50 m at a time for up to
    3 km, to the first cell whose D8 path doesn't lead back into the lake's dead ends. A dead end counts for a lake
    within 400 m (Lake Mathews' is 338 m outside its outline). Lakes with no outflow (Baldwin Lake) and dead ends
    away from lakes (desert fans, gravel pits, the sea) stay closed."""
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
        ins = v2[v2.intersects(lake)]
        ins = ins[ins.geometry.intersection(lake).length >= 0.25 * ins.length]   # silted-up Matilija: 49 %
        if not len(ins):
            continue
        fl = ins.loc[ins.totdasqkm.idxmax()]
        g = shapely.line_merge(fl.geometry)
        if g.geom_type != "LineString":                 # NHDPlus stores flowlines as (usually one-part) multilines
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
        dead = set(grp.o)
        entry, done = None, False
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
        if entry:
            out.update({o: entry for o in dead})
    return out


def _build(regions):
    from flowlib import FLOW, reservoirs
    from config import SHARED
    # the reservoir list leaves out lagoons (it's for coastal ones), but Castaic's water ends in Castaic Lagoon, the
    # afterbay below the dam; a coastal lagoon has no flowline below it, so it stays closed anyway
    lag = [gpd.read_file(g, layer="NHDWaterbody", where="gnis_name LIKE '%Lagoon%' AND ftype IN (390, 436)")
           for g in sorted({f"{SHARED}/NHD_H_{h}_HU4_GPKG.gpkg" for v in REGIONS.values() for h in v["hu4"]})]
    lag = [l.to_crs(CRS)[["gnis_name", "geometry"]] for l in lag if len(l)]
    lakes = pd.concat([reservoirs()[["gnis_name", "geometry"]], *lag], ignore_index=True)
    lakes = gpd.GeoDataFrame(lakes, geometry=lakes.geometry.force_2d(), crs=CRS)
    v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg", columns=["comid", "hydroseq", "dnhydroseq", "totdasqkm"]).to_crs(CRS)
    by_seq = v2.drop_duplicates("hydroseq").set_index("hydroseq")
    edges = shared_edges(regions)
    fds, exits, own, links = {}, {}, {}, []      # own: (region, outlet) -> its basin km2; links: (src, region, row, col, kind)
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
        exit_ = ~np.isnan(ox) & (km2 >= MIN_KM2)
        sink = ((orow > 0) & (orow < H - 1) & (ocol > 0) & (ocol < W - 1) & ~np.isin(fd[orow, ocol], list(D8))
                & (km2 >= MIN_KM2))
        exits[r] = {int(o): (float(x), float(y)) for o, x, y in zip(uo[exit_], ox[exit_], oy[exit_])}
        own.update({(r, int(o)): float(a) for o, a in zip(uo[exit_ | sink], km2[exit_ | sink])})
        sinks = {int(o): T * (c + 0.5, rr + 0.5) for o, rr, c in zip(uo[sink], orow[sink], ocol[sink])}
        for o, (row, col) in _dam_links(fd, T, sinks, lakes, v2, by_seq).items():
            links.append(((r, o), r, row, col, "dam"))
    # each exit -> the cell in the neighbouring box where its creek heads away from the edge
    for r in regions:
        for o, (x, y) in exits[r].items():
            for b, away in neighbours(r, x, y, edges):
                hit = next(crossing(b, *fds[b], x, y, away), None)
                if hit:
                    links.append(((r, o), b, hit[0], hit[1], "edge"))
                    break
    out = {}
    for variant in ("edge", "full"):
        use = [l for l in links if variant == "full" or l[4] == "edge"]
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
    dams = [l for l in links if l[4] == "dam"]
    print(f"crossbox: {sum(l[4] == 'edge' for l in links)} edge links, {len(dams)} reservoir dead ends carried past "
          f"their dams")
    return out


def inflows(region, through_dams=False):
    """[(row, col, km2, from_region, kind)]: where water from elsewhere enters `region`'s grid and how much drainage
    area it brings: from neighbouring boxes ("edge"), and with through_dams also from above a reservoir ("dam").
    The edge-only totals leave out any water that came over a dam. Built for every box at once and cached until a
    flowdir.tif, the reservoir list or the NHDPlus network changes."""
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
    return [tuple(e) for e in data["full" if through_dams else "edge"].get(region, [])]
