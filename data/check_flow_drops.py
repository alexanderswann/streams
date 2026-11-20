"""Standing check: sudden flow drops. A reach whose dry-season flow per km2 is under a quarter of both the reach above
it and the reach below it on the same creek, where both of those keep flowing (FLOWING_CFS), is likely a matching
error in 05b_flow.py (a side arm's trickle, a stale estimate below a pond, a model line that runs through a lake:
Guys Run, the Pachaug River, Piseco Outlet in 2026-11-19's builds).

The check the sessions ran before this one (scratch scripts, 2026-11-19) misread two things:
- It divided by area_full_km2. LA's flows are natural flows scaled on the area without the water from above dams
  (area_edge_km2, has("tnc_flows")). A reach's flow is now divided by the area 05b scales with: area_edge_km2 in
  LA, area_full_km2 elsewhere.
- At a confluence it paired a side creek with the main stem (Jackson's Teton Valley: small creeks that sink into
  the valley fill beside the spring-fed Teton River). Now "above" is the reach running into this one with the most
  drainage, and counts only where it has at least half of this reach's drainage (this reach continues its creek);
  "below" counts only where this reach brings at least half the drainage of the reach below.
The reaches come from the D8 walk 05b_flow.py does: each reach's last vertex is the confluence cell, from which the
D8 path runs to the first line cell of another reach; where the way leaves the box, it goes on in the box it runs
into (03b_stitch.py routes an area's boxes as one surface), so creeks at an edge between boxes are checked too.
Reaches of 1+ km2 with a flow figure; reaches in a lake ("reservoir") are left out on every side; headwater reaches
(nothing above) and reaches whose way leaves the map can't be checked.

Run from scripts/:  AREA=<area> ../.venv/bin/python ../data/check_flow_drops.py [--list]
"""
import sys, os, numpy as np, pandas as pd, geopandas as gpd, rasterio
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from config import AREA, REGIONS, CRS, has, out_dir, derived_dir
from flowpath import CODES as D8
from flowlib import FLOWING_CFS

RATIO = 0.25           # under this share of both neighbours' flow per km2
SAME_CREEK = 0.5       # a neighbour counts where the smaller of the two has at least this share of the larger's area
AREA_COL = "area_edge_km2" if has("tnc_flows") else "area_full_km2"


class Box:
    """A box's reaches (with their flow and areas) and the D8 walk between them, as 05b_flow.py's Walk. Vertices are
    cell corners (the top-left of their cell), so they are rounded to their cell."""

    def __init__(self, b):
        s = gpd.read_file(f"{out_dir(b)}/streams_scored.gpkg")[["sid", "name", "area_km2", "geometry"]].to_crs(CRS)
        fl = pd.read_csv(f"{out_dir(b)}/flow_streams.csv")[["sid", "dry_cfs", "water_class", "flow_src"]]
        ar = pd.read_csv(f"{out_dir(b)}/area_streams.csv")[["sid", "area_edge_km2", "area_full_km2"]]
        self.s = s.merge(fl, on="sid", how="left").merge(ar, on="sid", how="left")
        with rasterio.open(f"{derived_dir(b)}/flowdir.tif") as src:
            self.fdir, self.T = src.read(1), src.transform
        self.inv = ~self.T
        H, W = self.fdir.shape
        cells, ids = [], []
        self.end, self.last = np.zeros(len(s), dtype=np.int64), np.zeros((len(s), 2))
        for i, g in enumerate(self.s.geometry.values):
            xy = np.asarray(g.coords)[:, :2]
            c, r = self.inv * (xy[:, 0], xy[:, 1])
            idx = np.clip(np.rint(r).astype(int), 0, H - 1) * W + np.clip(np.rint(c).astype(int), 0, W - 1)
            cells.append(idx[:-1])
            ids.append(np.full(len(idx) - 1, i))
            self.end[i], self.last[i] = idx[-1], xy[-1]
        cells, ids = np.concatenate(cells)[::-1], np.concatenate(ids)[::-1]
        self.cells, first = np.unique(cells, return_index=True)
        self.ids = ids[first]

    def walk(self, cell, skip=-1):
        """(reach, None) for the first line cell of a reach other than `skip` down from `cell` (up to 4 km); (-1, the
        cell where the way stops: a pit, a flat or the rim) or (-1, None) past 4 km."""
        H, W = self.fdir.shape
        for _ in range(400):
            k = np.searchsorted(self.cells, cell)
            if k < len(self.cells) and self.cells[k] == cell and self.ids[k] != skip:
                return int(self.ids[k]), None
            st = D8.get(int(self.fdir.flat[cell]))
            r, c = divmod(cell, W)
            if st is None or not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
                return -1, cell
            cell = (r + st[0]) * W + c + st[1]
        return -1, None

    def onward(self, i=None, cell=None):
        """(x, y) of the first cell in the next box where the way down from reach i (or from the cell where a walk
        stopped) goes on, or None: a line that leaves its box ends on the first cell of the next one; a rim cell's
        direction points into it; from a pit or flat on the rim the way goes straight out."""
        H, W = self.fdir.shape
        if i is not None:
            c, r = self.inv * tuple(self.last[i])
            if not (0 <= round(r) < H and 0 <= round(c) < W):
                return tuple(self.last[i])
            cell = self.walk(int(self.end[i]), skip=i)[1]
        if cell is None:
            return None
        r, c = divmod(cell, W)
        st = D8.get(int(self.fdir.flat[cell]))
        if st is None:
            st = (int(r == H - 1) - int(r == 0), int(c == W - 1) - int(c == 0))
            if st == (0, 0):
                return None
        return self.T * (c + st[1], r + st[0])


def load():
    return {b: Box(b) for b in REGIONS
            if os.path.exists(f"{out_dir(b)}/streams_scored.gpkg") and os.path.exists(f"{out_dir(b)}/flow_streams.csv")}


def enter(boxes, xy):
    """(box, flat cell index) of the box holding the cell whose top-left corner is xy, or None."""
    if xy is None:
        return None
    for b, w in boxes.items():
        c, r = w.inv * xy
        r, c = int(round(r)), int(round(c))
        if 0 <= r < w.fdir.shape[0] and 0 <= c < w.fdir.shape[1]:
            return b, r * w.fdir.shape[1] + c
    return None


def downstream(boxes):
    """{(box, reach): (box, reach)} for every reach with a reach below it, in its box or the ones it runs on into."""
    out = {}
    for b, w in boxes.items():
        for i in range(len(w.s)):
            j, stop = w.walk(int(w.end[i]), skip=i)
            if j >= 0:
                out[(b, i)] = (b, j)
                continue
            to = enter(boxes, w.onward(i))
            for _ in range(4):
                if to is None:
                    break
                b2, cell = to
                j2, stop2 = boxes[b2].walk(cell)
                if j2 >= 0:
                    out[(b, i)] = (b2, j2)
                    break
                to = enter(boxes, boxes[b2].onward(cell=stop2))
    return out


def drops(boxes=None):
    boxes = boxes or load()
    nxt = downstream(boxes)
    val = {}
    for b, w in boxes.items():
        a = w.s[AREA_COL].fillna(w.s.area_km2).astype(float).values
        q = w.s.dry_cfs.astype(float).values
        ok = (a >= 1) & np.isfinite(q) & w.s.water_class.ne("reservoir").values
        for i in range(len(w.s)):
            val[(b, i)] = (a[i], q[i], q[i] / a[i], ok[i])
    up = {}
    for k, d in sorted(nxt.items(), key=lambda kv: val[kv[0]][0]):     # larger areas last, so they win
        up[d] = k
    rows = []
    for k, (a, q, u, ok) in val.items():
        if not ok or k not in up or k not in nxt:
            continue
        ka, kb = up[k], nxt[k]
        (aa, qa, ua, oka), (ab, qb, ub, okb) = val[ka], val[kb]
        if not (oka and okb) or qa < FLOWING_CFS or qb < FLOWING_CFS:
            continue
        if aa < SAME_CREEK * a or a < SAME_CREEK * ab:
            continue                            # a side creek above, or this one a side creek of the one below
        if u < RATIO * ua and u < RATIO * ub:
            s = boxes[k[0]].s
            mid = s.geometry.iloc[k[1]].interpolate(0.5, normalized=True)
            rows.append(dict(sid=s.sid.iat[k[1]], name=s.name.iat[k[1]], km2=round(a, 2), cfs=q,
                             src=s.flow_src.iat[k[1]], above=boxes[ka[0]].s.sid.iat[ka[1]], cfs_above=qa,
                             km2_above=round(aa, 2), below=boxes[kb[0]].s.sid.iat[kb[1]], cfs_below=qb,
                             km2_below=round(ab, 2), x=round(mid.x), y=round(mid.y)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    d = drops()
    print(f"{AREA}: sudden flow drops (flow per km2 of {AREA_COL} under {RATIO:.0%} of both neighbours on the same "
          f"creek, both flowing): {len(d)}")
    if len(d) and "--list" in sys.argv:
        pd.set_option("display.width", 250)
        print(d.to_string(index=False))
