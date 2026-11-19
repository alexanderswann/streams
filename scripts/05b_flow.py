"""Dry-season water for every reach and drop, from current data instead of the retired NHD label.
Run with REGION=<name> after 05_score.py (needs 02b_download_flow.py once for all regions).

Evidence per reach:
  1. Natural Flows Database (TNC): modelled monthly flow for the reach's NHDPlus V2 segment, for each of the
     last ~15 years. The reach's low flow in a year = the lowest Jul-Oct monthly mean, scaled by drainage area
     (DEM area of the reach, with what flows in from neighbouring boxes, / area of the model segment). Where that
     area would lower a reach's estimate below the one from its own box's area, the old estimate stays.
  2. Reaches the model network doesn't cover (small side creeks) take the unit-area flow of the first modelled
     segment downstream ("scaled").
  3. Reservoirs and reaches below a dam are flagged: the model is for unimpaired flow, the real flow there
     depends on releases.
  4. Reaches below a gauged diversion (flowlib.DIVERSIONS) are flagged with the record of the USGS gauge on the creek
     below it: the share of summers it kept FLOWING_CFS, since 2011 where it has 5+ of them, else over its record.
     Near the diversion (until tributaries add a quarter more drainage), a recent record is also passed on as
     div_water, which scoring.py uses as the water term where the creek is dry most summers.

Writes output/<region>/flow_streams.csv and flow_drops.csv:
  comid, flow_src, dry_cfs (typical year), dry_cfs_drought (2nd-worst of the years), flow_years (share of years
  with at least FLOWING_CFS through the dry season), water (0-1 score term), water_class, below_dam,
  below_div, div_gauge, div_share, div_years, div_water
"""
import os, numpy as np, pandas as pd, geopandas as gpd, rasterio
from config import *
from flowpath import pointers
from flowlib import (FLOW, DIVERSIONS, match_points, below_dam_comids, below_diversion_comids, gauge_summers, water_term,
                     FLOWING_CFS)

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

s = gpd.read_file(f"{OUT}/streams_scored.gpkg")[["sid", "area_km2", "flow", "geometry"]].to_crs(CRS)
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

# ---- reaches off the model network: inherit the first modelled reach downstream (D8 walk) ----
with rasterio.open(f"{DERIVED}/flowdir.tif") as src:
    fdir, inv = src.read(1), ~src.transform
area_r = rasterio.open(f"{DERIVED}/area_km2.tif").read(1)
H, W = fdir.shape
down, _, _ = pointers(fdir, area_r.ravel(), 0.25)
cell_reach = np.full(H * W, -1, dtype=np.int64)
end_cell = np.zeros(len(s), dtype=np.int64)
for i, g in enumerate(s.geometry.values):
    xy = np.asarray(g.coords)
    c, r = inv * (xy[:, 0], xy[:, 1])
    idx = np.clip(r.astype(int), 0, H - 1) * W + np.clip(c.astype(int), 0, W - 1)
    cell_reach[idx[:-1]] = i            # the last vertex is the confluence cell: it belongs to the next reach
    end_cell[i] = idx[-1]
nxt = np.full(len(s), -1)
for i in range(len(s)):
    cur = end_cell[i]
    for _ in range(400):                # up to 4 km of unmapped channel (drainage < 1 km2 gaps don't exist downstream)
        j = cell_reach[cur]
        if j >= 0 and j != i:
            nxt[i] = j
            break
        if down[cur] == cur:
            break
        cur = down[cur]


def segments(area):
    """The reaches with their model segment (comid) and its source, given their drainage areas: the nearest segment
    of similar drainage ("model"), or off the model network the first modelled reach downstream ("scaled").
    Also each gauged diversion's drainage at the diversion point: a diversion's own V2 flowline can start above it,
    and there only reaches with at least that drainage count as below it."""
    comid = match_points(mid, area, v2).values.astype(float)
    comid[~np.isin(comid, low.index)] = np.nan
    src_ = np.where(~np.isnan(comid), "model", None).astype(object)
    for i in np.flatnonzero(np.isnan(comid)):
        j, hops = nxt[i], 0
        while j >= 0 and np.isnan(comid[j]) and hops < 60:
            j, hops = nxt[j], hops + 1
        if j >= 0 and not np.isnan(comid[j]):
            comid[i], src_[i] = comid[j], "scaled"
    df = pd.DataFrame({"comid": comid, "flow_src": pd.Series(src_, index=s.index).fillna("none").values,
                       "area_km2": area.values}, index=s.index)
    div_area = {}
    for c_, name in div[div.div_first].below_div.items():
        on = df[(df.comid == c_) & (df.flow_src == "model")]
        if len(on):
            pt = gpd.GeoSeries(gpd.points_from_xy([DIVERSIONS[name][0][0]], [DIVERSIONS[name][0][1]]), crs=4326).to_crs(CRS)
            div_area[c_] = on.area_km2[s.geometry[on.index].distance(pt.iloc[0]).idxmin()]
    return df, div_area


def evidence(df, div_area):
    """df with comid, area_km2, flow_src -> flow columns."""
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
if (area_edge != area_box).any():
    # With the water from other boxes. Where that would lower a reach's water estimate, keep the old one: the drop
    # comes from the model now matching a creek it didn't before, or a side creek inheriting a different segment,
    # not from evidence that the creek dries (Dry Creek by the Sespe box edge, where trout were found: perennial on
    # NHD, 38 % of summers in the model). Possible trout water stays in until the evidence is near-certain.
    ev_edge = evidence(*segments(area_edge))
    nhd = s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05}).fillna(0.3)
    eff = lambda e: e.water.where(e.water_class.fillna("no data").ne("no data") & e.water.notna(), nhd)  # as scoring.py
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
pd.concat([s[["sid"]], ev], axis=1).to_csv(f"{OUT}/flow_streams.csv", index=False)

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
    kpe.loc[miss, cols] = evidence(m, box_div)[cols].values
pd.concat([kp[["did"]], kpe], axis=1).to_csv(f"{OUT}/flow_drops.csv", index=False)

print(LABEL, "| reaches", len(s), "| source", ev.flow_src.value_counts().to_dict())
print(ev.water_class.value_counts().to_string())
print("years", list(low.columns))
if ev.below_div.notna().any():
    print("reaches below gauged diversions:", ev.below_div.value_counts().to_dict(),
          "| near enough to use the gauge:", int(ev.div_water.notna().sum()))
