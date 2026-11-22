"""The roads a closure closes (08_hike.py, 09_drive.py; 07_road_closures.py draws the closures).

A closure comes as a line drawn along its road: the feed's own line, or 07's route between its two ends. The road it
closes is the stretch of each road line that runs along it: within BUF_M of it, for as far along the closure as
ALONG_M, or as most (MOST) of the road line's own length or of the closure's (a short piece of the closed road between
two junctions, a closed bridge). "Along" is measured on the closure (the distance between where the stretch's ends fall
on it), so a road that only meets or crosses the closure stays open. Cutting BUF_M around the closure out of every road
severed the roads it met: Teton Park Road where the Jenny Lake Loop joins it, Lower Gros Ventre Road at the foot of
Mormon Row (2026-11-22).
A spot closure (07 draws a point closure as a ring SPOT_R m round it) closes every road through the ring, as before:
which road at the point is closed isn't known.
"""
import numpy as np, shapely

BUF_M, ALONG_M, MOST = 25.0, 100.0, 0.8
SPOT_MAX = 400.0      # 07's rings are 2 pi x 60 m = 377 m round; a closed loop shorter than this is a spot closure


def is_spot(g):
    """True for 07's ring round a point closure."""
    return g is not None and g.geom_type == "LineString" and g.is_ring and g.length < SPOT_MAX


def closing(lines, closures):
    """For each road line of `lines`: the indices of the `closures` (lines) that close it, by the module's rule."""
    lines = np.asarray(lines, dtype=object)
    out = [[] for _ in range(len(lines))]
    if not len(lines):
        return out
    tree = shapely.STRtree(lines)
    for j, cg in enumerate(np.asarray(closures, dtype=object)):
        if cg is None or cg.is_empty:
            continue
        if is_spot(cg):
            for i in tree.query(cg.buffer(BUF_M), predicate="intersects"):
                out[i].append(j)
            continue
        hit = {}
        for part in shapely.get_parts(cg):            # each piece of the closure measured on itself
            if part.geom_type != "LineString" or part.length == 0:
                continue
            buf = part.buffer(BUF_M)
            ii = tree.query(buf, predicate="intersects")
            for i in ii:
                ov = shapely.get_parts(lines[i].intersection(buf))
                ov = [p for p in ov if p.geom_type == "LineString" and p.length > 0]
                run = sum(abs(part.project(shapely.Point(p.coords[0])) - part.project(shapely.Point(p.coords[-1])))
                          for p in ov)
                need = min(ALONG_M, MOST * lines[i].length, MOST * part.length)
                if run >= need:
                    hit[i] = True
        for i in hit:
            out[i].append(j)
    return out


def buffers(closures):
    """The BUF_M buffer of each closure: the stretch of a road it closes is the part inside it."""
    return [g.buffer(BUF_M) if g is not None and not g.is_empty else shapely.Polygon() for g in np.asarray(closures, dtype=object)]


def cut(lines, closures):
    """The road lines with the stretches their closures close taken out (other lines unchanged)."""
    lines = np.asarray(lines, dtype=object).copy()
    bufs = buffers(closures)
    for i, js in enumerate(closing(lines, closures)):
        if js:
            lines[i] = lines[i].difference(shapely.union_all([bufs[j] for j in js]))
    return lines


def closed_parts(lines, closures, pad=5.0):
    """(row indices, the closed stretch of each of those lines, `pad` m longer at the ends)."""
    lines = np.asarray(lines, dtype=object)
    bufs = buffers(closures)
    rows, geoms = [], []
    for i, js in enumerate(closing(lines, closures)):
        if js:
            rows.append(i)
            geoms.append(lines[i].intersection(shapely.union_all([bufs[j].buffer(pad) for j in js])))
    return np.array(rows, dtype=int), geoms
