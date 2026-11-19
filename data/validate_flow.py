"""How well do the flow sources predict whether a creek actually keeps water through the dry season?

Truth: USGS daily gauge records in the study area. A gauge-year is "dry" if the creek had >= 7 zero-flow days
in Jul-Oct. Compared: (a) the retired NHD perennial/intermittent label at the gauge, (b) the Natural Flows
model's dry-season estimate for the gauge's reach in the same years.
Run from scripts/:  ../.venv/bin/python ../data/validate_flow.py
"""
import sys, os, io, time, requests, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from config import REGIONS, CRS, SHARED, ROOT, raw_dir
from flowlib import below_dam_comids, match_points

FLOW = f"{SHARED}/flow"
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg")
gs = gpd.read_file(f"{FLOW}/gauge_sites.gpkg").to_crs(CRS)
dv = pd.read_csv(f"{FLOW}/gauges_daily.csv.gz", dtype={"site_no": str}, parse_dates=["date"])
gs["area_km2"] = pd.to_numeric(gs.drain_area_va, errors="coerce") * 2.58999

# gauge -> COMID (nearest V2 flowline whose drainage area agrees)
gs["comid"] = match_points(gs.geometry, gs.area_km2, v2, max_dist=300)
dam = below_dam_comids(v2)
gs["below_dam"] = gs.comid.map(dam)
# old NHD label at the gauge
nhd = pd.concat([gpd.read_file(f"{raw_dir(r)}/nhd_flowlines.gpkg") for r in REGIONS], ignore_index=True)
nhd["nhd"] = nhd.fcode.map({46006: "perennial", 46003: "intermittent", 46007: "ephemeral"}).fillna("other")
near = gpd.sjoin_nearest(gs[["site_no", "geometry"]], nhd[["nhd", "geometry"]], max_distance=150, how="left")
gs["nhd"] = near.groupby(level=0).nhd.first()

# observed dry-season behaviour per gauge-year
d = dv[dv.date.dt.month.between(7, 10)].copy()
d["year"] = d.date.dt.year
obs = d.groupby(["site_no", "year"]).agg(days=("cfs", "size"), zero_days=("cfs", lambda x: int((x < 0.005).sum())),
                                         min_cfs=("cfs", "min"), mean_cfs=("cfs", "mean")).reset_index()
mm = d.groupby(["site_no", "year", d.date.dt.month]).cfs.mean().groupby(["site_no", "year"]).min().rename("obs_low")
obs = obs.merge(mm.reset_index(), on=["site_no", "year"])
obs = obs[obs.days >= 110]
obs["dry"] = obs.zero_days >= 7

# Natural Flows for gauge COMIDs, full history
gc = sorted(gs.comid.dropna().astype(int).unique())
f = f"{FLOW}/nf_gauges_full.csv"
if not os.path.exists(f):
    parts = []
    for i in range(0, len(gc), 20):
        r = requests.get("https://flow-api.codefornature.org/v2/stream/", timeout=300, params=dict(
            comids=",".join(map(str, gc[i:i + 20])), statistics="mean,min", variables="estimated",
            begin_month=7, end_month=10))
        r.raise_for_status()
        parts.append(pd.read_csv(io.StringIO(r.text)))
        time.sleep(0.3)
    pd.concat(parts).to_csv(f, index=False)
nf = pd.read_csv(f)
nf = nf[nf.month.between(7, 10)]
low = nf.pivot_table(index=["comid", "year"], columns="statistic", values="value", aggfunc="min").reset_index()
low = low.rename(columns={"mean": "nf_low_mean", "min": "nf_low_min"})

t = obs.merge(gs[["site_no", "station_nm", "comid", "area_km2", "below_dam", "nhd"]], on="site_no")
t = t.merge(low, on=["comid", "year"], how="left")
t.to_csv(f"{FLOW}/validation_gauge_years.csv", index=False)

site = t.groupby(["site_no", "station_nm"]).agg(
    area_km2=("area_km2", "first"), nhd=("nhd", "first"), below_dam=("below_dam", "first"), years=("year", "size"),
    first=("year", "min"), last=("year", "max"), dry_frac=("dry", "mean"), obs_low_med=("obs_low", "median"),
    nf_low_med=("nf_low_mean", "median"), nf_min_med=("nf_low_min", "median")).reset_index()
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(site.sort_values("dry_frac").round(2).to_string())
site.to_csv(f"{FLOW}/validation_sites.csv", index=False)
