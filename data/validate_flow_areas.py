"""Outside California: how well does the flow table (NHDPlus EROM monthly mean x the area's yearly gauge index,
02b_download_flow.py) match the summer low flows the USGS gauges recorded?

Per gauge and summer since 2011: observed low = the lowest July-October monthly mean; modelled low = the same from
natural_flows.csv for the gauge's NHDPlus segment. Gauges below a reservoir are left out (releases set their flow).
Reported per area and by drainage size: the median of modelled / observed, the share of gauge-summers within a
factor of two, and how often the model says "flowing" (>= 0.1 cfs) when the gauge fell below that.
The yearly index is the median over these same gauges, so this checks EROM's spread along the network and the
one-index-per-area shortcut, not the index itself.
Run from scripts/:  AREA=<area> ../.venv/bin/python ../data/validate_flow_areas.py
"""
import sys, os, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from config import CRS, SHARED, AREA
from flowlib import below_dam_comids, match_points, FLOWING_CFS

FLOW = f"{SHARED}/flow"
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg")
gs = gpd.read_file(f"{FLOW}/gauge_sites.gpkg").to_crs(CRS)
dv = pd.read_csv(f"{FLOW}/gauges_daily.csv.gz", dtype={"site_no": str}, parse_dates=["date"])
nf = pd.read_csv(f"{FLOW}/natural_flows.csv")
nf = nf[(nf.variable == "estimated") & (nf.statistic == "mean")]
gs["area_km2"] = pd.to_numeric(gs.drain_area_va, errors="coerce") * 2.58999
gs["comid"] = match_points(gs.geometry, gs.area_km2, v2, max_dist=300)
dam = below_dam_comids(v2)
gs = gs[gs.comid.notna()].copy()
gs = gs[~gs.comid.astype(int).isin(set(dam))]
d = dv[dv.site_no.isin(gs.site_no) & dv.date.dt.month.between(7, 10) & (dv.date.dt.year >= 2011)]
m = d.groupby(["site_no", d.date.dt.year.rename("year"), d.date.dt.month.rename("month")]).cfs.agg(["mean", "size"])
obs = m[m["size"] >= 25].groupby(level=["site_no", "year"])["mean"].agg(["min", "size"])
obs = obs[obs["size"] == 4]["min"].rename("obs").reset_index()
mod = nf.groupby(["comid", "year"]).value.min().rename("mod").reset_index()
t = obs.merge(gs[["site_no", "comid", "area_km2", "station_nm"]], on="site_no").merge(mod, on=["comid", "year"])
t["ratio"] = (t["mod"] + 0.01) / (t.obs + 0.01)
t["size"] = pd.cut(t.area_km2, [0, 25, 100, 500, 1e6], labels=["< 25 km2", "25-100", "100-500", "> 500"])
def line(g):
    return (f"gauges {g.site_no.nunique():3d} | summers {len(g):4d} | median modelled/observed {g.ratio.median():.2f} | within x2 "
            f"{((g.ratio > 0.5) & (g.ratio < 2)).mean():.0%} | observed < {FLOWING_CFS} cfs: {int((g.obs < FLOWING_CFS).sum())} summers, "
            f"of which the model says flowing: {int(((g.obs < FLOWING_CFS) & (g['mod'] >= FLOWING_CFS)).sum())}")
print(f"{AREA}: all   ", line(t))
for k, g in t.groupby("size", observed=True):
    print(f"  {k:9s}", line(g))
small = t[t.area_km2 < 100].groupby("station_nm").agg(km2=("area_km2", "first"), summers=("obs", "size"),
                                                         obs_low=("obs", "median"), mod_low=("mod", "median")).round(2)
if len(small):
    print("  small gauges (median summer low, cfs):"); print(small.sort_values("km2").head(12).to_string())
