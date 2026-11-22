"""Patch a copy of scripts/03b_stitch.py with lake routing along NHD's lines: every cell of a lake that holds water
drains to the lake's outlet cell, along NHD HR's lines through the lake where they run (route_lake). Until now only
the path that gathered the most water ended at the outlet; the flat water's own directions let any other path leave
the lake on its own (Pilgrim Creek crossed Jackson Lake to the dam beside the Snake's outlet cell, so the line below
the dam was Pilgrim Creek's channel). python patch_lakes.py <scripts dir>"""
import sys

d = sys.argv[1]
p = f"{d}/03b_stitch.py"
s = open(p).read()


def sub(old, new):
    global s
    assert s.count(old) == 1, f"anchor not found once: {old[:70]!r}"
    s = s.replace(old, new)


sub("""  - A lake that holds water still ends the paths that enter it, at the cell where its water leaves (flowlib.
    still_water; "holds water" read off the DEM, at least LEVEL_HA of the outline at one elevation). A lake lying
    across a shared edge now has one outlet, not one in each box. crossbox.py carries the area on past the dam.
""", """  - A lake that holds water still ends the paths that enter it, at the cell where its water leaves (flowlib.
    still_water; "holds water" read off the DEM, at least LEVEL_HA of the outline at one elevation). A lake lying
    across a shared edge now has one outlet, not one in each box. crossbox.py carries the area on past the dam.
    Every cell of such a lake drains to that outlet, along NHD's lines through the lake where they run (route_lake):
    the flat water's own directions let a path other than the biggest leave the lake on its own. Below the outlet the
    way the water takes is a stream line down to the first stream it meets (outflow_streams), so that the lake's water,
    which crossbox.py puts back in there, lands on the river below the junction, not on a side creek's line.
""")

sub("""LEVEL_HA = 2
""", """LEVEL_HA = 2
LINE_PULL = 5.0      # route_lake: a step through a lake off NHD's lines costs this many steps along them
LAKE_LINE_FTYPES = (460, 558, 334)   # NHD HR StreamRiver, ArtificialPath (lake and river centrelines), Connector
""")

sub('''def groups():
''', '''CODE_OF = np.zeros(9, np.uint8)                         # the code for a step (dr, dc), at (dr + 1) * 3 + dc + 1
for code, (dr, dc) in zip(CODES, OFFS):
    CODE_OF[(dr + 1) * 3 + dc + 1] = code


def nhd_lines(group):
    """NHD HR stream lines of the group's boxes (each box's nhd_flowlines.gpkg reaches past its box): StreamRiver,
    ArtificialPath and Connector, not canals, pipelines or coastline."""
    import pandas as pd
    parts = []
    for r in group:
        p = f"{raw_dir(r)}/nhd_flowlines.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p, columns=["ftype"])
            parts.append(g[g.ftype.isin(LAKE_LINE_FTYPES)].to_crs(CRS))
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    return g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)


def route_lake(fd, geom, outlet, T, lines):
    """Send every cell of a lake that holds water to its outlet cell (row, col of the group's grid), along NHD's lines
    through the lake where they run: a least-cost path over the lake's cells (8 neighbours), a step off the lines
    costing LINE_PULL steps along them. Before, only the path that gathered the most water ended at the outlet; the
    flat water's own directions (resolve_flats) let any other path leave the lake on its own, beside the outlet:
    Pilgrim Creek crossed Jackson Lake to the dam next to the Snake's outlet cell, so the line below the dam was
    Pilgrim Creek's and the map named the river there after it. Cells not joined to the outlet through the lake keep
    their directions. Changes fd in place; returns the number of cells re-routed."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    H, W = fd.shape
    gx0, gy0, gx1, gy1 = geom.bounds
    ca, ra = ~T * (gx0, gy1)
    cb, rb = ~T * (gx1, gy0)
    r0, c0 = max(int(np.floor(ra)) - 1, 0), max(int(np.floor(ca)) - 1, 0)
    r1, c1 = min(int(np.ceil(rb)) + 1, H), min(int(np.ceil(cb)) + 1, W)
    ro, co = outlet[0] - r0, outlet[1] - c0
    if r1 <= r0 or c1 <= c0 or not (0 <= ro < r1 - r0 and 0 <= co < c1 - c0):
        return 0
    shape = (r1 - r0, c1 - c0)
    Tw = T * rasterio.Affine.translation(c0, r0)
    view = fd[r0:r1, c0:c1]
    lake = rasterio.features.geometry_mask([geom], shape, Tw, invert=True) & (view > 0)
    lake[ro, co] = True
    on = np.zeros(shape, bool)
    if len(lines):
        near = lines.geometry.values[lines.sindex.query(geom, predicate="intersects")]
        if len(near):
            on = rasterio.features.rasterize(((g, 1) for g in near), out_shape=shape, transform=Tw, fill=0,
                                             dtype="uint8").astype(bool) & lake
    cells = np.flatnonzero(lake)
    n = len(cells)
    if n < 2:
        return 0
    idx = np.full(shape[0] * shape[1], -1, np.int64)
    idx[cells] = np.arange(n)
    cost = np.where(on.ravel()[cells], 1.0, LINE_PULL)
    rr, cc = np.divmod(cells, shape[1])
    src, dst, wt = [], [], []
    for dr, dc in ((0, 1), (1, 1), (1, 0), (1, -1)):        # each pair of neighbours once
        r2, c2 = rr + dr, cc + dc
        ok = (r2 < shape[0]) & (c2 >= 0) & (c2 < shape[1])
        j = np.full(n, -1, np.int64)
        j[ok] = idx[r2[ok] * shape[1] + c2[ok]]
        a_ = np.flatnonzero(j >= 0)
        b_ = j[a_]
        src.append(a_)
        dst.append(b_)
        wt.append((cost[a_] + cost[b_]) / 2 * (np.sqrt(2.0) if dr and dc else 1.0))
    g = coo_matrix((np.concatenate(wt), (np.concatenate(src), np.concatenate(dst))), shape=(n, n)).tocsr()
    _, pred = dijkstra(g, directed=False, indices=int(idx[ro * shape[1] + co]), return_predecessors=True)
    k = np.flatnonzero(pred >= 0)                         # every cell reached; the outlet itself has none
    if not len(k):
        return 0
    p = pred[k]
    view[rr[k], cc[k]] = CODE_OF[(rr[p] - rr[k] + 1) * 3 + (cc[p] - cc[k] + 1)]
    return len(k)


def outflow_streams(fd, stream, outflow, max_cells=3000):
    """Make the way a pitted lake's water takes below its outlet a stream line, down to the first stream cell it meets.
    The cells below a dam gather little ground of their own, so the river had no line there: the lake's water, which
    crossbox.py puts back in below the outlet, ran down to the first line it met and was counted on that whole link,
    a side creek's included (Lower Slide Lake's 1,500 km2 on a 2.7 km creek beside the Gros Ventre). With a line of
    its own the outflow meets that creek at a junction, and the water lands on the river below it. Changes stream in
    place; returns km of line added."""
    H, W = fd.shape
    added = 0
    for r_, c_, code in outflow:
        if code not in CODE_SET:
            continue
        r, c = r_ + int(DR[code]), c_ + int(DC[code])
        for _ in range(max_cells):
            if not (0 <= r < H and 0 <= c < W) or stream[r, c]:
                break
            k = int(fd[r, c])
            if k not in CODE_SET:
                break
            stream[r, c] = True
            added += 1
            r, c = r + int(DR[k]), c + int(DC[k])
    return round(added * RES / 1000, 1)


def groups():
''')

sub("""        most = {}
        for (i, v), k in level.items():
            most[i] = max(most.get(i, 0), k)
        for i, (a, r_, c_) in best.items():""", """        most = {}
        for (i, v), k in level.items():
            most[i] = max(most.get(i, 0), k)
        lines = nhd_lines(group)
        for i, (a, r_, c_) in best.items():""")

sub("""            if not (0 < r_ < H - 1 and 0 < c_ < W - 1 and (ring > 0).all()):
                off_map.append(i)
                continue
""", """            if not (0 < r_ < H - 1 and 0 < c_ < W - 1 and (ring > 0).all()):
                off_map.append(i)
                continue
            # every cell of the lake drains to its outlet, along NHD's lines through it where they run
            n_routed += route_lake(fd, lakes.geometry.iloc[i - 1], (r_, c_), T, lines) > 0
""")

sub("""    n_wet = n_through = 0
""", """    n_wet = n_through = n_routed = 0
    outflow = []                                        # (row, col, direction) of each pitted lake's outlet
""")

sub("""            fd[r_, c_] = PIT
            n_wet += 1
        acc, _ = accumulate(fd, DR, DC)
""", """            outflow.append((r_, c_, int(fd[r_, c_])))     # the way its water takes out of the lake, before the pit
            fd[r_, c_] = PIT
            n_wet += 1
        acc, more = accumulate(fd, DR, DC)
        if more:                                        # a flowing-on lake's outlet pointing back into the lake
            fd[acc < 0] = PIT
            acc, _ = accumulate(fd, DR, DC)
            loops += more
""")

sub("""    stream = acc >= int(round(STREAM_KM2 * 1e6 / (RES * RES)))      # in cells: no float copy of a 250-million-cell grid
""", """    stream = acc >= int(round(STREAM_KM2 * 1e6 / (RES * RES)))      # in cells: no float copy of a 250-million-cell grid
    n_out = outflow_streams(fd, stream, outflow)
""")

sub("""          f"{n_wet} of {len(lakes)} lakes end paths at their outlet"
""", """          f"{n_wet} of {len(lakes)} lakes end paths at their outlet ({n_routed} routed to it along NHD's lines; "
          f"{n_out} km of stream line added below outlets)"
""")

open(p, "w").write(s)
print("patched lake routing into", p)
