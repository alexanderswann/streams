"""Dry-season water for every reach and drop, from current data instead of the retired NHD label.
Run with REGION=<name> after 05_score.py (needs 02b_download_flow.py once for all regions).

Evidence per reach:
  1. Natural Flows Database (TNC): modelled monthly flow for the reach's NHDPlus V2 segment, for each of the
     last ~15 years. The reach's low flow in a year = the lowest Jul-Oct monthly mean, scaled by drainage area
     (DEM area of the reach, with what flows in from neighbouring boxes, / area of the model segment). Where that
     area would lower a reach's estimate below the one from its own box's area, the old estimate stays.
  2. Reaches the model network doesn't cover (small side creeks) take the unit-area flow of the first modelled
     segment downstream ("scaled"). Where the box has none below a creek and its way leaves the box, the search goes
     on in the box it flows into (03b_stitch.py routes an area's boxes as one surface).
  3. Reservoirs and reaches below a dam are flagged: the model is for unimpaired flow, the real flow there
     depends on releases. A reach lies in a reservoir when half its length is in the water; one lying outside it on
     a model line that runs mostly through the lake is a creek, below the dam only on the line's stretch below it.
     The water is NHD's lakes of 8 ha or more, with the shore the lakes layer draws where it drew the lake from the
     lidar, and, where NHD maps a lake as river or leaves it out, the lakes layer's (05d_lakes.py, which run_mid.sh
     runs before 05_score.py: that step cuts the stream links at the same shores, flowlib.lake_water).
  4. Reaches below a gauged diversion (flowlib.DIVERSIONS) are flagged with the record of the USGS gauge on the creek
     below it: the share of summers it kept FLOWING_CFS, since 2011 where it has 5+ of them, else over its record.
     Near the diversion (until tributaries add a quarter more drainage), a recent record is also passed on as
     div_water, which scoring.py uses as the water term where the creek is dry most summers.
  5. NHD's class is a floor: an estimate inherited from another creek (2), or one that leaves out the water from above
     a dam (3, natural flows), never puts a reach below NHD's class, and a creek NHD maps perennial reads year-round.

Writes output/<region>/flow_streams.csv and flow_drops.csv:
  comid, flow_src, dry_cfs (typical year), dry_cfs_drought (2nd-worst of the years), flow_years (share of years
  with at least FLOWING_CFS through the dry season), water (0-1 score term), water_class, below_dam,
  below_div, div_gauge, div_share, div_years, div_water, model_class and water_floor (where NHD's class lifted the
  reach (5): the model's own class, and why: perennial / inherited / dam),
  and the evidence scoring.py reads for creeks the model rates flowing that are dry most summers (2026-11-20):
  green_p90, green_p90_max, green_sur, green_water (the channel's late-summer greenness, flowlib.channel_green, where
  02g_greenness.py made rasters) and gauge_site, gauge_name, gauge_share, gauge_summers, gauge_years, gauge_area_km2,
  gauge_m, gauge_below (a USGS gauge on the reach's own creek, flowlib.gauge_record)
"""
import os, shapely, numpy as np, pandas as pd, geopandas as gpd, rasterio
from config import *
from flowpath import CODES as D8
from crossbox import dam_links
from flowlib import (FLOW, DIVERSIONS, match_points, below_dam_comids, below_diversion_comids, gauge_summers, water_term,
                     FLOWING_CFS, reservoirs, MIN_RESERVOIR_KM2, lakes_layer, layer_counted, as_drawn)
from flowlib import wet_lakes as pit_lakes

v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg")
nf = pd.read_csv(f"{FLOW}/natural_flows.csv")
nf = nf[(nf.variable == "estimated") & (nf.statistic == "mean")]
low = nf.groupby(["comid", "year"]).value.min().unstack()          # comid x year: lowest dry-season monthly mean
low = low.dropna(axis=1, thresh=int(0.9 * len(low)))                # drop a not-yet-complete current year
# (that test only catches a year most segments lack altogether: one with some of its four months still counts, on the
# months it has)
_months = nf.groupby("year").month.nunique()
_part = {int(y): int(_months[y]) for y in low.columns if _months[y] < 4}
if _part:
    print("NOTE: the flow model's dry season is incomplete for", ", ".join(f"{y} ({n} of 4 months)" for y, n in _part.items()),
          "- that year's low flow is the lowest of the months it has. Run 02b_download_flow.py with REFRESH=1 once "
          "October is published.")
v2_area = v2.set_index("comid").totdasqkm
dam = below_dam_comids(v2)
div = below_diversion_comids(v2)
div_gauge = gauge_summers([g for _, _, g in DIVERSIONS.values()]).reindex([g for _, _, g in DIVERSIONS.values()])
div_gauge.index = list(DIVERSIONS)                                   # by diversion name

s = gpd.read_file(f"{OUT}/streams_scored.gpkg").to_crs(CRS)
s = s[["sid", "area_km2", "flow", "geometry"] + [c_ for c_ in ("side_sid", "cut_sid") if c_ in s]]
# A creek cut 200 m below a lake (05_score.py cuts it for its water temperature alone; a first piece's cut_sid names
# the rest of its line) is read here whole, as it was before the cut, and both pieces take its row: its model line and
# flow, the dam above it, its greenness and its gauge record. Measured on its own, a piece matched another model line
# or none: the first 200 m, where the creek's own drainage starts again from nothing, read drier than the creek below
# it (a brook below a pond in north-east Connecticut "usually flows" -> "mostly dry"), and a short rest of a line
# below a small reservoir on the Arroyo Seco matched the model's next line, the one below the dam: "usually flows"
# where the creek reads "year-round" (2026-11-22). The rest keeps its own drainage: the line's, at its lower end.
cut_of = {}                        # first piece's sid -> its line's (the rest's)
if "cut_sid" in s and s.cut_sid.notna().any():
    first_ = s.cut_sid.notna().to_numpy()
    row_ = pd.Series(np.arange(len(s)), index=s.sid.values)
    geo_ = list(s.geometry.values)
    for i in np.flatnonzero(first_):
        r_ = row_[s.cut_sid.iat[i]]
        geo_[r_] = shapely.LineString(list(geo_[i].coords) + list(geo_[r_].coords)[1:])
        cut_of[s.sid.iat[i]] = s.sid.iat[r_]
    s = s.copy()
    s["geometry"] = gpd.GeoSeries(geo_, index=s.index, crs=s.crs)
    s = s[~first_].reset_index(drop=True)
    if "side_sid" in s:
        s["side_sid"] = s.side_sid.replace(cut_of)
    print(f"creeks cut below a lake, read whole: {len(cut_of)}")
# Drainage area with the water that flows in from neighbouring boxes (05c_drainages.py, crossbox.py): this box's DEM
# starts a creek that crosses in from the next box with no area, which scaled its modelled flow down to almost
# nothing (Lytle Creek in the San Bernardino box: 2 km2 of its 120). Water from above a dam is left out: the model
# is for natural flow, and a dam can hold it back. Used for matching the segment, scaling its flow and diversions.
area_box = s.area_km2.copy()
area_edge = area_box
if os.path.exists(f"{OUT}/area_streams.csv"):
    # (outside California the flow table is NHDPlus's gauge-adjusted mean flow, which has the dams in it, so the
    # full area, with the water from above reservoirs, is the one that matches its segments)
    col_ = "area_edge_km2" if has("tnc_flows") else "area_full_km2"
    more = s.sid.map(pd.read_csv(f"{OUT}/area_streams.csv").set_index("sid")[col_]) - area_box
    area_edge = area_box + more.where(more >= 0.01, 0.0)       # (the CSV is rounded: no inflow keeps the exact area)
mid = s.geometry.interpolate(0.5, normalized=True)

# ---- the lakes and reservoirs the model's lines are flagged against (flowlib.below_dam_comids), and for each reach
# the one holding the largest share of its length: a reach at least half inside it lies in it, as for those lines ----
# NHD stores some lakes as several pieces that touch (Palisades Reservoir as four: 5,626, 396, 376 and 49 ha), so the
# share is counted over a lake's pieces together: the Salt River's way across Palisades lies 72% in the four and under
# half in any one, and scored 80 as a river (the only such reach over the 12 areas, 2026-11-20). Whether the lake
# holds water is still read from the piece holding most of the reach (lake_of): counted over the whole lake, 7 reaches
# in the Adirondacks lying in a piece with no level water of its own would also have changed.
# A reach's length in a lake is measured against the shore the map draws: NHD's outline cut to the lidar's where the
# lakes layer drew that lake from the lidar (flowlib.as_drawn; wbd_). Against NHD's own outline a side creek at Lower
# Slide Lake's head (324 m, half inside NHD's outline, none of it in the water the lidar shows) and Emma Matilda Lake's
# outlet creek between its ponds read "reservoir" and drew as lake where the map has none: 158 reaches, 84 km, over the
# 12 maps (2026-11-21). NHD's own outlines still say which pieces are one lake, which hold a pit, and where a model
# line leaves the lake (wb_).
wb_ = reservoirs()
wb_ = wb_.assign(geometry=shapely.make_valid(wb_.geometry.values))
ll_all_ = lakes_layer()
lake_name, lake_share = pd.Series(None, index=s.index, dtype=object), pd.Series(0.0, index=s.index)
lake_of = pd.Series(-1, index=s.index)
if len(wb_):
    whole_ = gpd.GeoDataFrame(geometry=list(shapely.get_parts(shapely.union_all(wb_.geometry.buffer(1).values))),
                              crs=CRS)
    g_ = gpd.sjoin(wb_[["geometry"]], whole_, predicate="intersects")
    wb_["lake"] = g_[~g_.index.duplicated()].index_right.reindex(wb_.index).values
    wbd_ = wb_.assign(geometry=as_drawn(wb_, ll_all_).values)
    j_ = gpd.sjoin(s[["geometry"]], wbd_[["gnis_name", "lake", "geometry"]], predicate="intersects")
    if len(j_):
        share = (shapely.length(shapely.intersection(j_.geometry.values, wbd_.geometry.reindex(j_.index_right).values))
                 / j_.geometry.length.values)
        j_ = j_.assign(share=share)
        j_["whole"] = j_.groupby([j_.index, "lake"]).share.transform("sum")
        j_ = j_.sort_values(["whole", "share"], ascending=False)
        j_ = j_[~j_.index.duplicated()]
        lake_name[j_.index], lake_share[j_.index] = j_.gnis_name.fillna("unnamed reservoir").values, j_.whole.values
        lake_of[j_.index] = j_.index_right.values
in_lake = (lake_share >= 0.5).values
# Which of those lakes hold water: 03b_stitch.py ends paths at the outlet of every lake with 2+ ha of its outline at
# one level in the DEM (a pit, fdir 254); one without (a marsh or meadow NHD maps as a pond, a dry basin) has none
wet_lakes = pit_lakes(wb_, REGION)
in_wet_lake = in_lake & lake_of.isin(wet_lakes).values
# ---- and the lakes layer (05d_lakes.py: NHD, agency and OpenStreetMap outlines, checked against the lidar), where NHD
# maps a lake as river area, leaves it out, or draws it smaller than the water: the Little Tennessee inside Cheoah
# Reservoir (NHD river area; NCWRC's outline in the layer) scored 73 as a river, the reaches crossing Jenny Lake and
# Lake Lila 100. A lake counts there at 8 ha or more (the whole lake's size: one reaching far past the map is stored
# clipped), level in the lidar ("flattened" or "level, not flattened"; not "little level water", a dry, marsh or
# overgrown bed; not drawn down or drained), not intermittent, and not a lagoon (as reservoirs()); a reach at least
# half inside one lies in it. 05d_lakes.py runs before this step (run_mid.sh): it reads 05c's drainages, nothing of 05b's.
in_layer_lake, layer_name = np.zeros(len(s), dtype=bool), pd.Series(None, index=s.index, dtype=object)
if ll_all_ is not None:
    ll_ = layer_counted(ll_all_)
    j_ = gpd.sjoin(s[["geometry"]], ll_[["name", "geometry"]], predicate="intersects") if len(ll_) else []
    if len(j_):
        share = (shapely.length(shapely.intersection(j_.geometry.values, ll_.geometry.reindex(j_.index_right).values))
                 / j_.geometry.length.values)
        j_ = j_.assign(share=share).sort_values("share", ascending=False)
        j_ = j_[~j_.index.duplicated()]
        j_ = j_[j_.share >= 0.5]
        in_layer_lake = s.index.isin(j_.index)
        layer_name[j_.index] = j_["name"].fillna("unnamed lake").values
else:
    print(f"NOTE: no lakes layer at {SHARED_DERIVED}/lakes.gpkg (05d_lakes.py): only NHD's lakes are read")
v2_line = v2.drop_duplicates("comid").set_index("comid").geometry
_lake_end = {}


def below_lake(comid, pt):
    """True where pt sits on the stretch of model line `comid` (flagged "in:<lake>") below that lake: past the last
    point where the line, digitized downstream, is in the lake."""
    if comid not in _lake_end:
        line = shapely.line_merge(v2_line[comid])
        lk = wb_[wb_.gnis_name.eq(dam[comid][3:]) & wb_.intersects(line)]
        parts = shapely.get_parts(shapely.intersection(line, shapely.union_all(lk.geometry.values)))
        ends = [line.project(shapely.Point(xy)) for p in parts if p.length > 0 for xy in shapely.get_coordinates(p)[[0, -1]]]
        _lake_end[comid] = (line, max(ends, default=None))
    line, end = _lake_end[comid]
    return end is not None and line.project(pt) > end


# ---- reaches off the model network: inherit the first modelled reach downstream (D8 walk), in this box or the next.
# Each box's reaches and its walk end at its rim, though 03b_stitch.py routes an area's boxes as one surface: a creek
# whose way left the box over an edge it shares with another found no modelled reach below it and read "no data".
# On the Jackson map (2026-11-19) that was 10 % of the reaches within 1.5 km of a shared edge against 2.5 % overall:
# five unnamed creeks above Deadman's Bar went from year-round at about 0.5 cfs (fish 65) to no data (fish 9) only
# because the edge below them moved. Now, where this box has no modelled reach below a creek, its way is followed
# into the box it flows into, and on through that box's reaches as that box's own run walks them. ----
class Walk:
    """A box's reaches and the D8 walk from each one's end to the next reach downstream, one reach at a time (so a
    box that a creek only runs on into costs just the reaches it passes)."""

    def __init__(self, geoms, fdir, transform, box=None):
        self.fdir, self.T, self.inv = fdir, transform, ~transform
        H, W = fdir.shape
        # a lake's dead end and the cell below its outlet where its water goes on (crossbox.dam_links)
        self.dams = {int(o): int(r_) * W + int(c_) for o, (r_, c_) in dam_links(box).items()} if box else {}
        cells, ids = [], []
        self.end, self.last = np.zeros(len(geoms), dtype=np.int64), np.zeros((len(geoms), 2))
        for i, g in enumerate(geoms):
            xy = np.asarray(g.coords)[:, :2]
            c, r = self.inv * (xy[:, 0], xy[:, 1])
            # a vertex is the top-left corner of its cell, +-3e-10 m after the trip through EPSG:4326: rounded, not
            # truncated (truncation put about half of them one row or column off, 2026-11-20)
            idx = np.clip(np.rint(r).astype(int), 0, H - 1) * W + np.clip(np.rint(c).astype(int), 0, W - 1)
            cells.append(idx[:-1])          # the last vertex is the confluence cell: it belongs to the next reach
            ids.append(np.full(len(idx) - 1, i))
            self.end[i], self.last[i] = idx[-1], xy[-1]
        cells, ids = np.concatenate(cells)[::-1], np.concatenate(ids)[::-1]
        self.cells, first = np.unique(cells, return_index=True)      # a cell two reaches share is the later one's
        self.ids = ids[first]
        self.next_, self.own = {}, {}

    def walk(self, cell, skip=-1):
        """Down from `cell` to the first line cell of a reach other than `skip`, over up to 4 km of unmapped channel
        (drainage < 1 km2 gaps don't exist downstream): (reach, None); where the way stops first (a pit or flat, or
        the box's rim), (-1, that cell); (-1, None) past 4 km."""
        H, W = self.fdir.shape
        seen = set()
        for _ in range(400):
            k = np.searchsorted(self.cells, cell)
            if k < len(self.cells) and self.cells[k] == cell and self.ids[k] != skip:
                return int(self.ids[k]), None
            st = D8.get(int(self.fdir.flat[cell]))
            r, c = divmod(cell, W)
            if st is None and cell in self.dams and cell not in seen:     # through the lake, on below its outlet
                seen.add(cell)
                cell = self.dams[cell]
                continue
            if st is None or not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
                return -1, cell
            cell = (r + st[0]) * W + c + st[1]
        return -1, None

    def next(self, i):
        if i not in self.next_:
            self.next_[i] = self.walk(int(self.end[i]), skip=i)
        return self.next_[i]

    def onward(self, i=None, cell=None):
        """Where the way down from reach i (with no reach below it in its box), or from a cell where a walk stopped,
        goes on in the next box: (box, cell there), or None. A line that leaves its box ends on the first cell of the
        next one (03b_stitch.py), and a rim cell's direction can point into it; from a pit or flat on the rim the
        way goes straight out, as crossbox.exit_points() has it. (A line's vertex is the top-left corner of its
        cell.)"""
        H, W = self.fdir.shape
        if i is not None:
            c, r = self.inv * tuple(self.last[i])
            if not (0 <= round(r) < H and 0 <= round(c) < W):
                return enter(*self.last[i])
            cell = self.next(i)[1]
        if cell is None:
            return None
        r, c = divmod(cell, W)
        st = D8.get(int(self.fdir.flat[cell]))
        if st is None:
            st = (int(r == H - 1) - int(r == 0), int(c == W - 1) - int(c == 0))
            if st == (0, 0):
                return None             # a dead end inside the box (a lake, a sink)
        return enter(*(self.T * (c + st[1], r + st[0])))


_GRID, _WALK, STALE, ACROSS = {}, {}, set(), {}


def enter(x, y):
    """(box, flat index of its cell whose top-left corner is x, y) for the box of this area holding that cell, or
    None (off the map, or a box with no reaches yet)."""
    for b in REGIONS:
        if b not in _GRID:
            p = f"{derived_dir(b)}/flowdir.tif"
            _GRID[b] = None
            if os.path.exists(p) and os.path.exists(f"{out_dir(b)}/streams_scored.gpkg"):
                with rasterio.open(p) as src:
                    _GRID[b] = (~src.transform, src.shape)
        if _GRID[b]:
            c, r = _GRID[b][0] * (x, y)
            r, c = int(round(r)), int(round(c))
            if 0 <= r < _GRID[b][1][0] and 0 <= c < _GRID[b][1][1]:
                return b, r * _GRID[b][1][1] + c
    return None


def walk_of(b):
    """Box b's reaches, walked as its own run of this script walks them, with their midpoints and drainage areas: its
    own box's, and with the water from other boxes where its area_streams.csv was written for these reaches."""
    if b not in _WALK:
        g = gpd.read_file(f"{out_dir(b)}/streams_scored.gpkg")[["sid", "area_km2", "geometry"]].to_crs(CRS)
        with rasterio.open(f"{derived_dir(b)}/flowdir.tif") as src:
            w = Walk(g.geometry.values, src.read(1), src.transform, b)
        w.mid, w.area = g.geometry.interpolate(0.5, normalized=True), {False: g.area_km2, True: g.area_km2}
        p = f"{out_dir(b)}/area_streams.csv"
        t = pd.read_csv(p) if os.path.exists(p) else None
        if t is not None and set(t.sid) == set(g.sid):      # written for these reaches (the test scoring.attach makes)
            more = g.sid.map(t.set_index("sid")["area_edge_km2" if has("tnc_flows") else "area_full_km2"]) - g.area_km2
            w.area[True] = g.area_km2 + more.where(more >= 0.01, 0.0)
        else:
            STALE.add(b)
        _WALK[b] = w
    return _WALK[b]


def own(w, edge):
    """Each reach's own model segment in walk w's box (NaN where none), by its drainage with (edge) or without the
    water from other boxes, as segments() matches them."""
    if edge not in w.own:
        c_ = match_points(w.mid, w.area[edge], v2).values.astype(float)
        c_[~np.isin(c_, low.index)] = np.nan
        w.own[edge] = c_
    return w.own[edge]


_DONE = {}


def settle(b, j, edge, boxes):
    """(segment, box) for reach j of box b: its own segment, or that of the first modelled reach below it, up to 60
    reaches on as in this box; where its way leaves box b first, on in the box it runs into (`boxes` more boxes at
    most). (NaN, None) where there is none. Each reach is settled once (the creeks of a box share their ways down)."""
    if (b, j, edge) in _DONE:
        return _DONE[(b, j, edge)]
    w = walk_of(b)
    seg, chain, res = own(w, edge), [], (np.nan, None)
    for _ in range(61):
        chain.append(j)
        _DONE[(b, j, edge)] = (np.nan, None)        # (a way that loops back here finds nothing)
        if not np.isnan(seg[j]):
            res = (seg[j], b)
            break
        j2 = w.next(j)[0]
        if j2 < 0:
            if boxes > 0:
                res = into(w.onward(j), edge, boxes - 1)
            break
        if (b, j2, edge) in _DONE:
            res = _DONE[(b, j2, edge)]
            break
        j = j2
    for j_ in chain:
        _DONE[(b, j_, edge)] = res
    return res


def into(to, edge, boxes):
    """settle() for a way entering a box at `to` (box, cell): the first reach it meets there. A way that leaves that
    box again before it meets one (across a corner) goes on."""
    for _ in range(4):
        if to is None:
            break
        b, cell = to
        w = walk_of(b)
        j, stop = w.walk(cell)
        if j >= 0:
            return settle(b, j, edge, boxes)
        to = w.onward(cell=stop)
    return np.nan, None


def beyond(k, edge):
    """For a creek whose way leaves this box with no modelled reach below it here (reach k, the last one on it):
    (segment, box) of the first modelled reach below it in the boxes it runs on into, up to four boxes on; (NaN,
    None) where there is none."""
    return into(here.onward(k), edge, 3)


with rasterio.open(f"{DERIVED}/flowdir.tif") as src:
    here = Walk(s.geometry.values, src.read(1), src.transform, REGION)
here.mid, here.area = mid, {False: area_box, True: area_edge}
_WALK[REGION] = here
nxt = np.array([here.next(i)[0] for i in range(len(s))], dtype=np.int64)

# ---- a way that ends in a lake draining off the map ----
# 03b_stitch.py leaves no stream lines on a lake whose water leaves the map (its lakes_off_map.gpkg, 2026-11-20), so the
# search below for the first modelled reach downstream stopped at the shore, where it used to run on across the lake's
# lines to the lake's own NHDPlus line (the artificial path of the river or cove through it). 72 reaches over 7 areas
# lost their flow that way and read "no data": 15 small creeks dropped 30-60 points (9 by Lake Champlain in the
# Adirondacks, 2 by Hartwell Lake, 2 by Lake Chaubunagungamaug, 1 by Brewster Lake, 1 by Champlain off Ticonderoga), the
# Tallulah's reservoir reaches above Hartwell lost their flow figures. Now, where the way down from the last reach in this
# box runs into such a lake within 4 km (on through lakes below their outlets), the search takes that lake's NHDPlus line
# nearest the cell where the way enters the water (a line at least half inside the lake, with flows; at any distance, as
# the old search ran on across the lake's lines: off Port Kent the line Big Brook had taken is 3.5-4.1 km out), as it
# took the lake reaches' lines before (restored at the user's word, 2026-11-20). An inherited estimate like any other:
# it never puts a reach below NHD's class (below).
LAKE_LINE, LAKE_USED, wet_, lines_ = {}, set(), None, None
if os.path.exists(f"{DERIVED}/lakes_off_map.gpkg"):
    from rasterio import features as rio_features
    off_l = gpd.read_file(f"{DERIVED}/lakes_off_map.gpkg").to_crs(CRS).reset_index(drop=True)
    wet_ = rio_features.rasterize(((g, i + 1) for i, g in enumerate(off_l.geometry)), out_shape=here.fdir.shape,
                                  transform=here.T, fill=0, dtype="int32").ravel()      # the lake's number + 1
    water_ = shapely.union_all(off_l.geometry.values)
    lines_ = v2[v2.comid.isin(low.index)].drop_duplicates("comid")[["comid", "geometry"]].to_crs(CRS)
    lines_ = lines_[lines_.intersects(water_).values].reset_index(drop=True)
    share_ = np.array([[ln.intersection(lk).length / max(ln.length, 1e-9) for lk in off_l.geometry] for ln in lines_.geometry])
    lines_["lake"] = (share_.argmax(axis=1) + 1) if len(lines_) else []
    lines_ = lines_[(share_.max(axis=1) >= 0.5) if len(lines_) else []]


def lake_line(k):
    """The comid of the line of a lake draining off the map where the way down from reach k (the last reach on its way
    in this box) enters it within 4 km, or NaN."""
    if k not in LAKE_LINE:
        LAKE_LINE[k] = np.nan
        if wet_ is not None and len(lines_):
            H_, W_ = here.fdir.shape
            cell, seen = int(here.end[k]), set()
            for _ in range(400):
                if wet_[cell]:
                    r, c = divmod(cell, W_)
                    own_ = lines_[lines_.lake == wet_[cell]]
                    if len(own_):
                        d_ = own_.distance(shapely.Point(here.T * (c + 0.5, r + 0.5)))
                        LAKE_LINE[k] = float(own_.comid.iat[int(np.argmin(d_.values))])
                    break
                st = D8.get(int(here.fdir.flat[cell]))
                r, c = divmod(cell, W_)
                if st is None and cell in here.dams and cell not in seen:
                    seen.add(cell)
                    cell = here.dams[cell]
                    continue
                if st is None or not (0 <= r + st[0] < H_ and 0 <= c + st[1] < W_):
                    break
                cell = (r + st[0]) * W_ + c + st[1]
    return LAKE_LINE[k]


def in_box(area, edge):
    """Each reach's model segment in this box, given the reaches' drainage areas (edge: with the water from other
    boxes): the nearest segment of similar drainage ("model"), or off the model network that of the first modelled
    reach downstream ("scaled"); and for a reach with neither, the last reach on its way down in this box, else -1."""
    comid = match_points(mid, area, v2).values.astype(float)
    comid[~np.isin(comid, low.index)] = np.nan
    here.own[edge] = comid.copy()
    src_ = np.where(~np.isnan(comid), "model", None).astype(object)
    last = np.full(len(s), -1)
    for i in np.flatnonzero(np.isnan(comid)):
        k, j, hops = i, nxt[i], 0
        while j >= 0 and np.isnan(comid[j]) and hops < 60:
            k, j, hops = j, nxt[j], hops + 1
        if j >= 0 and not np.isnan(comid[j]):
            comid[i], src_[i] = comid[j], "scaled"
        elif j < 0:
            c_ = lake_line(k)              # the way ends in a lake draining off the map (above)
            if np.isnan(c_):
                last[i] = k
            else:
                comid[i], src_[i] = c_, "scaled"
                LAKE_USED.add(int(i))
    return comid, src_, last


# Only a creek with no segment in this box by either area goes on into the next box: one with a segment here by one of
# them keeps the result it always had, rather than the keep rule below preferring a segment far down another box.
OWN = {False: in_box(area_box, False)}
OWN[True] = in_box(area_edge, True) if (area_edge != area_box).any() else OWN[False]
if LAKE_USED:
    print(f"reaches whose way ends in a lake draining off the map ({', '.join(off_l.gnis_name.fillna('unnamed'))}), "
          f"given the lake's line: {len(LAKE_USED)}")
lost = np.isnan(OWN[False][0]) & np.isnan(OWN[True][0])


def segments(area, edge=False):
    """The reaches with their model segment (comid) and its source, given their drainage areas (edge: with the water
    from other boxes): in_box(), and for a creek with no segment in this box by either area, the segment of the first
    modelled reach below it in the box its way runs on into (beyond(); "scaled" too).
    Also each gauged diversion's drainage at the diversion point: a diversion's own V2 flowline can start above it,
    and there only reaches with at least that drainage count as below it."""
    comid, src_, last = (a_.copy() for a_ in OWN[edge])
    from_ = np.full(len(s), None, dtype=object)        # the box the segment was found in, where it's another box
    for i in np.flatnonzero(lost & (last >= 0)):
        comid[i], from_[i] = beyond(last[i], edge)
        if from_[i] is not None:
            src_[i] = "scaled"
    ACROSS[edge] = from_
    df = pd.DataFrame({"comid": comid, "flow_src": pd.Series(src_, index=s.index).fillna("none").values,
                       "area_km2": area.values, "inside": in_lake, "pt": mid.values}, index=s.index)
    div_area = {}
    for c_, name in div[div.div_first].below_div.items():
        on = df[(df.comid == c_) & (df.flow_src == "model")]
        if len(on):
            pt = gpd.GeoSeries(gpd.points_from_xy([DIVERSIONS[name][0][0]], [DIVERSIONS[name][0][1]]), crs=4326).to_crs(CRS)
            div_area[c_] = on.area_km2[s.geometry[on.index].distance(pt.iloc[0]).idxmin()]
    return df, div_area


def evidence(df, div_area):
    """df with comid, area_km2, flow_src, inside (lies in a lake), pt (the point matched) -> flow columns."""
    has = df.comid.notna()
    ratio = (df.area_km2 / df.comid.map(v2_area)).clip(upper=1.2).where(has)
    q = low.reindex(df.comid.where(has, -1).astype(int)).values * ratio.values[:, None]      # reach x year
    out = pd.DataFrame(index=df.index)
    out["comid"] = df.comid.astype("Int64")
    out["flow_src"] = df.flow_src
    out["dry_cfs"] = np.round(np.nanmedian(q, axis=1), 2)
    out["dry_cfs_drought"] = np.round(np.sort(q, axis=1)[:, 1], 2)        # second-driest year
    out["flow_years"] = np.round((q >= FLOWING_CFS).mean(axis=1), 2).astype(float)
    out.loc[~has.values, ["dry_cfs", "dry_cfs_drought", "flow_years"]] = np.nan
    d = df.comid.map(dam).where(df.flow_src == "model")
    # A model line that runs mostly through a lake is flagged "in:<lake>", and a reach matched to it read "reservoir"
    # even where it lies outside the water: NHDPlus's line can run on past the shore. Piseco Outlet, 700 m below
    # Piseco Lake, matched a 3.9 km line 73 % in the lake; as "reservoir" its estimate with its 174 km2 was lower than
    # the old one from its own box's 1.3 km2 (the outlet starts again from nothing there), which stood: 0.43 cfs,
    # scaled from the river 374 km2 downstream, where the reach below carries 75 cfs. Such a reach is a creek with the
    # line's flow: below the dam where it sits on the line's stretch below the lake (12 of the 161 reaches this
    # changed over the 12 areas, 2026-11-19), else a creek coming in or running beside the water, with no dam.
    off = d.fillna("").str.startswith("in:").values & ~df.inside.values.astype(bool)
    for i in np.flatnonzero(off):
        d.iat[i] = d.iat[i][3:] if below_lake(int(df.comid.iat[i]), df.pt.iat[i]) else None
    out["below_dam"] = d
    out["water"], out["water_class"] = water_term(out)
    # below a gauged diversion (on the model network only, as for dams): the record of the gauge below it
    key = df.comid.where(df.flow_src == "model").fillna(-1).astype("int64")
    dv = div.reindex(key.values).reset_index(drop=True)
    above = (key.map(div_area) > df.area_km2 + 0.05).values          # on the diversion's own flowline, above it
    dv.loc[above, ["below_div", "div_growth"]] = np.nan
    g = div_gauge.reindex(dv.below_div.values)
    out["below_div"] = dv.below_div.values
    out["div_gauge"] = [DIVERSIONS[n][2] if isinstance(n, str) else None for n in dv.below_div]
    out["div_share"] = g.div_share.values
    out["div_years"] = g.div_years.values
    out["div_water"] = np.where(g.div_recent.eq(True).values & (dv.div_growth <= 1.25).values, g.div_share.values, np.nan)
    return out


box_df, box_div = segments(area_box)
ev = evidence(box_df, box_div)
across = ACROSS[False]
nhd = s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05}).fillna(0.3)

# ---- NHD's class as a floor ----
# NHD's perennial and intermittent labels are about this creek. An estimate inherited from another creek (the first
# modelled reach below it, in this box or the one it runs on into, down a way through a lake, or the line of a lake
# draining off the map) isn't, and neither is one that leaves out the water from above a lake or dam holding half the
# drainage (where the flows are natural flows: the model's figure there is for the creek's own ground below the dam,
# the least that runs there; what seeps, spills or is released comes on top). So such an estimate never puts a reach
# below NHD's class, valued as the map values it where there's no estimate (`nhd`: perennial year-round, intermittent
# and a line NHD gives no class seasonal, no NHD line mostly dry), and a creek NHD maps perennial reads year-round
# whatever the model says ("never show a wet creek as dry"): outside California the model is NHDPlus's mean flow with
# no drying in it, which read 671 perennial brooks in north-east Connecticut below year-round (398 with trout found),
# and in LA the natural-flow model read 145 mi that NHD maps perennial mostly dry (audit, 2026-11-22). Only a USGS
# gauge's record (scoring.py: on the creek, or below a diversion) puts a reach below NHD's class. Before 2026-11-22 this
# was five rules, each written for one kind of inherited estimate (Ticonderoga's creeks, Smith and Skinner brooks,
# Partridge Brook, Dry Creek by the Sespe box edge, Willow Creek below Lake Arrowhead), and a plain inherited estimate
# in the box had none.
held = np.zeros(len(s), bool)                          # below a lake or dam holding half the drainage, natural flows
if has("tnc_flows") and os.path.exists(f"{OUT}/area_streams.csv"):
    t_ = pd.read_csv(f"{OUT}/area_streams.csv").set_index("sid")
    full_, edge_ = s.sid.map(t_.area_full_km2), s.sid.map(t_.area_edge_km2)
    held = ((full_ - edge_) >= 0.5 * full_).fillna(False).values
    if "cut_sid" in s:      # a creek's first stretch below a lake, cut off for its water temperature alone (cut_sid: the
        row_ = s.cut_sid.map(pd.Series(np.arange(len(s)), index=s.sid.values)).fillna(-1).astype(int).values
        held = np.where(row_ >= 0, held[np.maximum(row_, 0)], held)     # rest of its line), is held as that rest is


def floor_of(e):
    """(water term after NHD's floor, why it was lifted: 'perennial', 'inherited', 'dam', or None) for the reaches of
    flow evidence e. Only estimates are lifted: not a reach in a lake, nor one with no estimate."""
    f = nhd.values
    why = np.where(s.flow.eq("perennial").values, "perennial", np.where(e.flow_src.eq("scaled").values, "inherited",
                                                                        np.where(held, "dam", "")))
    lift = (e.water_class.isin(["mostly dry", "seasonal", "usually flows", "year-round"]).values
            & (e.water.values < f - 1e-9) & (why != ""))
    return np.where(lift, f, e.water.values), np.where(lift, why, None)


def eff(e):
    """The water term scoring.py starts from: the estimate after NHD's floor, NHD's class where there is none."""
    has_ = e.water_class.fillna("no data").ne("no data") & e.water.notna()
    return pd.Series(floor_of(e)[0], index=e.index).where(has_, nhd)


if (area_edge != area_box).any():
    # With the water from other boxes. Where that would lower a reach's water estimate, keep the old one: the drop
    # comes from the model now matching a creek it didn't before, or a side creek inheriting a different segment,
    # not from evidence that the creek dries (Dry Creek by the Sespe box edge, where trout were found: perennial on
    # NHD, 38 % of summers in the model). Possible trout water stays in until the evidence is near-certain. The two
    # are weighed after NHD's floor: before it, a low estimate from a lake's line made the other pass's estimate look
    # higher and win (four creeks off Ticonderoga, perennial on NHD, 46-59 -> 34-40, 2026-11-20).
    ev_edge = evidence(*segments(area_edge, edge=True))
    keep = (eff(ev_edge) < eff(ev) - 1e-9).values
    # ... but only an old estimate that is about this creek. Below a pond the box's own area starts again from
    # nothing, so the old estimate there is whatever small line happened to match it: the Pachaug River inside
    # Pachaug Pond (129 km2) took a 2.3 km2 brook's 0.23 cfs and stood as "usually flows", where the estimate with
    # its real drainage says reservoir. An old estimate from a line with under half the reach's drainage is
    # dropped whatever it says.
    line_km2 = ev.comid.map(v2_area).astype(float).values
    credible = line_km2 >= 0.5 * area_edge.values
    n_all = int(keep.sum())
    keep = keep & (np.isnan(line_km2) | credible)      # an old estimate with no line at all (NHD's label) still stands
    print(f"water with the area from other boxes: {int((area_edge > area_box).sum())} reaches get more area; the old "
          f"estimate is kept on {int(keep.sum())} where the new one would be lower ({n_all - int(keep.sum())} more "
          f"were not kept: the old estimate came from a line with under half the reach's drainage)")
    for c_ in ev.columns:
        ev_edge[c_] = ev_edge[c_].where(~keep, ev[c_])
    ev = ev_edge
    across = np.where(keep, ACROSS[False], ACROSS[True])
far = pd.Series(across, index=s.index).where(ev.flow_src.eq("scaled").values)
if far.notna().any():
    print(f"creeks whose way leaves this box with no modelled reach below them here, scaled from one in the box they "
          f"run on into: {int(far.notna().sum())} ({', '.join(f'{b} {n}' for b, n in far.value_counts().items())})")
for b in sorted(STALE):
    print(f"NOTE: {out_dir(b)}/area_streams.csv doesn't list {b}'s current reaches, so creeks running on into {b} were "
          f"matched there on that box's own drainage areas: run 05b_flow.py for {REGION} again after 05c_drainages.py "
          f"for {b}")
# A reach lying in a lake or reservoir that no model segment matched was scored as a stream (found 2026-11-19 on
# Fontana Lake, fish 83-85): either it read "no data" and scoring.py took NHD's "perennial" label (about 550 reaches
# over the eight areas: Jackson Lake, Palisades, Lake Champlain, Lake Elsinore, Lanier...), or it took the flow of the
# first modelled reach downstream, the river below the dam ("scaled", about 750 more). The DEM's channel through the
# water can lie far from NHDPlus's line, so no segment of its own matches it. The test the model segments get
# (flowlib.below_dam_comids: half the length inside the water) now makes such a reach "reservoir" too. A reach
# matched to a segment of its own keeps that segment's evidence.
# ... and a reach lying in a lake that holds water is a reservoir reach whatever it matched: one matched to a
# segment of its own outside the water (the creek's line above the lake) read as that creek (a reach all inside
# String Lake scored 100, Jackson Lake's 73-76; 404 such reaches over the 12 areas, 2026-11-20). One in a lake with
# no level water keeps its own evidence: water runs through it.
lk_ = (ev.flow_src.fillna("none").ne("model").values & in_lake) | in_wet_lake
if lk_.any():
    ev.loc[lk_, "below_dam"] = "in:" + lake_name[lk_]
    ev.loc[lk_, "water"], ev.loc[lk_, "water_class"] = 0.3, "reservoir"
    print(f"reaches in a lake with no model segment of their own, now reservoir: {int(lk_.sum())}")
# ... and a reach in a lake of the lakes layer (above) that isn't one yet: Cheoah Reservoir's 32 reaches; 196 over the
# 12 areas, 125 of which had scored 60 or more (2026-11-20)
lk2_ = in_layer_lake & ev.water_class.ne("reservoir").values
if lk2_.any():
    ev.loc[lk2_, "below_dam"] = "in:" + layer_name[lk2_]
    ev.loc[lk2_, "water"], ev.loc[lk2_, "water_class"] = 0.3, "reservoir"
    print(f"reaches in a lake of the lakes layer (none on NHD, or a smaller one), now reservoir: {int(lk2_.sum())}")
# A side channel of a river (05_score.py's side_of: a small reach along the river's own NHD lines, beside the reach
# that carries the river) is the river's water in another arm. On its own few km2 it matched no line of the river and
# took a brook's flow or none ("no data", "seasonal" beside a year-round river); it takes the flow evidence of the
# river reach beside it (side_sid). Not where either of the two lies in a lake.
side_row = np.full(len(s), -1)
if "side_sid" in s:
    side_row = s.side_sid.map(pd.Series(np.arange(len(s)), index=s.sid.values)).fillna(-1).astype(int).values
    take_ = (side_row >= 0) & ev.water_class.ne("reservoir").values
    take_ &= ev.water_class.values[np.maximum(side_row, 0)] != "reservoir"
    side_row = np.where(take_, side_row, -1)
    if take_.any():
        for c_ in ev.columns:
            ev.loc[take_, c_] = ev[c_].values[side_row[take_]]
    print(f"side channels given the flow evidence of the river reach beside them: {int(take_.sum())}")
on_ = ev.comid.map(dam).fillna("").str.startswith("in:").values & ev.flow_src.eq("model").values & ~in_lake & ~lk2_
if on_.any():
    print(f"reaches outside a lake on a model line that runs mostly through it, read as creeks: {int(on_.sum())} "
          f"({int(ev.below_dam[on_].notna().sum())} of them below the lake)")
# NHD's floor (above), on the evidence each reach ends with: water_floor says why a reach was lifted and model_class
# what the model said (the cfs and summers flowing stay the model's)
w_, why_ = floor_of(ev)
lift_ = pd.notna(why_)
ev["model_class"] = ev.water_class.where(lift_)
ev["water_floor"] = why_
ev["water"] = np.round(w_, 2)
ev.loc[lift_, "water_class"] = pd.cut(w_[lift_], [-1, 0.24, 0.525, 0.8575, 1.0],
                                      labels=["mostly dry", "seasonal", "usually flows", "year-round"]).astype(str)
print("reaches NHD's class lifts: " + ", ".join(f"{k} {n}" for k, n in pd.Series(why_[lift_]).value_counts().items())
      + f" (of them to a wetter class than the model's: {int((lift_ & (ev.model_class != ev.water_class)).sum())})")
# ---- evidence for creeks the model rates flowing that are dry most summers (scoring.py's water (1) and (2)) ----
# The channel's late-summer greenness (02g_greenness.py's rasters, where the area has the late_summer_green source)
# and the record of a USGS gauge on the reach's own creek (flowlib.gauge_record). scoring.py decides, one-sided: it
# lowers a creek only where the evidence agrees and no trout are known, and lets a gauge raise one (Piru Creek below
# Pyramid Dam flows every summer on its releases; the natural-flow model rated it seasonal).
from flowlib import channel_green, creek_gauges, gauge_record, gauge_reach_comids, gauge_own_lines
extra = channel_green(s.geometry.values, REGION)
extra.index = s.index
area_full_ = area_box.copy()
if os.path.exists(f"{OUT}/area_streams.csv"):
    area_full_ = s.sid.map(pd.read_csv(f"{OUT}/area_streams.csv").set_index("sid")["area_full_km2"]).fillna(area_box)
cg_ = creek_gauges(v2)
comid_ = ev.comid.astype(float).values
near_ = gauge_reach_comids(cg_, s.geometry.values, area_full_.values, comid_)
# (a side channel stands for its river: a gauge on the river is matched on the river's drainage)
area_full_ = pd.Series(np.where(side_row >= 0, area_full_.values[np.maximum(side_row, 0)], area_full_.values), index=s.index)
gr_ = gauge_record(mid.values, area_full_.values, comid_, ev.flow_src.values,
                   ev.below_dam.fillna("").astype(str).str.startswith("in:").values, cg_, near_,
                   gauge_own_lines(cg_, v2, near_))
gr_.index = s.index
extra = extra.join(gr_)
print(f"late-summer channel greenness for {int(extra.green_p90.notna().sum())} of {len(s)} reaches; the record of a gauge "
      f"on their creek for {int(extra.gauge_share.notna().sum())} ({extra.gauge_name.dropna().nunique()} gauges)")
fs_ = pd.concat([s[["sid"]], ev, extra], axis=1)
if cut_of:      # the first piece of a creek cut below a lake: its line's row (above)
    fs_ = pd.concat([fs_, fs_.set_index("sid").loc[list(cut_of.values())].reset_index().assign(sid=list(cut_of))],
                    ignore_index=True)
fs_.to_csv(f"{OUT}/flow_streams.csv", index=False)

# ---- drops take the evidence of the reach they sit on ----
kp = gpd.read_file(f"{OUT}/waterfall_candidates.gpkg")[["did", "area_km2", "geometry"]].to_crs(CRS)
near = gpd.sjoin_nearest(kp, s[["geometry"]].join(ev), max_distance=80, how="left").groupby(level=0).first()
cols = list(ev.columns)
kpe = near[cols].reindex(kp.index)
miss = kpe.flow_src.isna()
if miss.any():      # drops on channels below the 1 km2 map floor: match the model network directly
    m = kp[miss].assign(comid=match_points(kp[miss].geometry, kp[miss].area_km2, v2).values)
    m.loc[~m.comid.isin(low.index), "comid"] = np.nan
    m["flow_src"] = np.where(m.comid.notna(), "model", "none")
    m["pt"] = m.geometry.values
    m["inside"] = m.index.isin(gpd.sjoin(m[["geometry"]], wbd_[["geometry"]], predicate="within").index) if len(wb_) else False
    kpe.loc[miss, cols] = evidence(m, box_div).reindex(columns=cols).values
pd.concat([kp[["did"]], kpe], axis=1).to_csv(f"{OUT}/flow_drops.csv", index=False)

print(LABEL, "| reaches", len(s), "| source", ev.flow_src.value_counts().to_dict())
print(ev.water_class.value_counts().to_string())
print("years", list(low.columns))
if ev.below_div.notna().any():
    print("reaches below gauged diversions:", ev.below_div.value_counts().to_dict(),
          "| near enough to use the gauge:", int(ev.div_water.notna().sum()))
