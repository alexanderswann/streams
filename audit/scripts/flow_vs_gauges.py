#!/usr/bin/env python3
"""Summer flow the popups state, against the USGS gauge records in the project.

For every gauge inside an area with 5+ complete dry seasons (July-October) since 2011:
  gauge_typ   median over those years of the year's lowest July-October monthly mean (the popups' "typical" figure)
  gauge_share share of those years whose lowest monthly mean was 0.1 cfs or more (the popups' "kept flowing")
  gauge_class the map's own class limits on that share (<=20 % mostly dry, <=50 % seasonal, <=85 % usually flows)
The drawn reach is the one within reach of the gauge whose drainage area fits the gauge's best (area within 0.8-1.25,
else the gauge is left out as not on a drawn line of its size).
Outside LA the estimate is NHDPlus's mean monthly flow times an index made from the same gauges, so agreement at a
gauge is partly built in there; in LA (TNC's natural-flow model) the gauges are independent.
Tables: audit/tables/flow_vs_gauges.csv (per gauge), flow_vs_gauges_summary.csv; flow_class_vs_nhd.csv (how the
map's class and NHD's own perennial / intermittent label agree, by length).
"""
import sys, os
import numpy as np, pandas as pd, geopandas as gpd, shapely
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from popups import reaches

SQMI = 2.58999
ORDER = ["mostly dry", "seasonal", "usually flows", "year-round"]


def cls(share):
    return ORDER[int(np.searchsorted([0.2, 0.5, 0.85], share, side="left"))]


def gauge_stats(area):
    p = f"{ROOT}/data/raw/{area}/_shared/flow/gauges_daily.csv.gz"
    d = pd.read_csv(p, dtype={"site_no": str}, parse_dates=["date"])
    d = d[(d.date.dt.year >= 2011) & d.date.dt.month.isin([7, 8, 9, 10])].dropna(subset=["cfs"])
    d["year"], d["month"] = d.date.dt.year, d.date.dt.month
    mm = d.groupby(["site_no", "year", "month"]).cfs.agg(["mean", "size"]).reset_index()
    mm = mm[mm["size"] >= 25]                                      # a month needs 25+ days
    yr = mm.groupby(["site_no", "year"]).agg(low=("mean", "min"), months=("month", "nunique")).reset_index()
    yr = yr[yr.months == 4]
    g = yr.groupby("site_no").agg(gauge_typ=("low", "median"), gauge_share=("low", lambda s: float((s >= 0.1).mean())),
                                  summers=("low", "size"), gauge_drought=("low", lambda s: float(np.sort(s)[1]) if len(s) > 1 else np.nan))
    return g[g.summers >= 5]


def main(areas):
    rows, cross = [], []
    for a in areas:
        r = reaches(a)
        sites = gpd.read_file(f"{ROOT}/data/raw/{a}/_shared/flow/gauge_sites.gpkg").to_crs(epsg(a))
        sites["site_no"] = sites.site_no.astype(str).str.zfill(8)
        st = gauge_stats(a)
        st.index = st.index.astype(str).str.zfill(8)
        sites = sites[sites.site_no.isin(st.index) & sites.drain_area_va.notna()
                      & shapely.contains(area_box_union(a), sites.geometry.values)].reset_index(drop=True)
        tree = shapely.STRtree(r.geometry.values)
        km2 = r.km2.to_numpy(float)
        for s in sites.itertuples():
            ref = s.drain_area_va * SQMI
            c = tree.query(s.geometry, predicate="dwithin", distance=100.0 if ref < 100 else 250.0 if ref < 1000 else 500.0)
            if not len(c):
                continue
            j = c[np.argmin(np.abs(np.log(np.maximum(km2[c], 1e-3) / ref)))]
            if not 0.8 <= km2[j] / ref <= 1.25:
                continue
            q, g = r.iloc[j], st.loc[s.site_no]
            ll = gpd.GeoSeries([s.geometry], crs=epsg(a)).to_crs(4326).iloc[0]
            rows.append(dict(area=a, site_no=s.site_no, station=s.station_nm, sq_mi=round(s.drain_area_va, 1), summers=int(g.summers),
                             gauge_typ_cfs=round(g.gauge_typ, 3), map_typ_cfs=q.typ_cfs, gauge_drought_cfs=round(g.gauge_drought, 3),
                             map_drought_cfs=q.drought_cfs, gauge_share=round(g.gauge_share, 2),
                             map_share=None if pd.isna(q.pct_flowing) else q.pct_flowing / 100,
                             gauge_class=cls(g.gauge_share), map_class=q.flow_class, map_shown=q.flow_shown, rule=q.rule,
                             flow_src=q.flow_src, scaled=q.scaled, fish=q.fish, lat=round(ll.y, 5), lon=round(ll.x, 5)))
        # the map's class against NHD's label, by drawn length (default layer)
        d = r[r.layer == "streams"]
        t = d.groupby([d.flow_class.fillna("(NHD's label shown)"), d.nhd_class.fillna("none")]).len_m.sum().div(MI).round(1)
        for (fc, nc), mi in t.items():
            cross.append(dict(area=a, map_class=fc, nhd_class=nc, miles=mi))
        print(a, "done", flush=True)
    G = pd.DataFrame(rows)
    G["typ_ratio"] = (G.map_typ_cfs / G.gauge_typ_cfs.where(G.gauge_typ_cfs >= 0.05)).round(2)
    G["class_steps"] = [ORDER.index(m) - ORDER.index(g) if m in ORDER else np.nan for m, g in zip(G.map_class, G.gauge_class)]
    G.to_csv(f"{TABLES}/flow_vs_gauges.csv", index=False)
    X = pd.DataFrame(cross)
    X.to_csv(f"{TABLES}/flow_class_vs_nhd.csv", index=False)
    S = []
    for a, d in G.groupby("area", sort=False):
        k = d[d.map_class.isin(ORDER)]
        nat = k[k.rule == ""]
        lr = np.log10(k.typ_ratio.dropna())
        wet_g = k[k.gauge_class.isin(["usually flows", "year-round"])]
        dry_g = k[k.gauge_class.isin(["mostly dry", "seasonal"])]
        S.append(dict(area=a, gauges=len(d), with_class=len(k), same_class_pct=100 * (k.class_steps == 0).mean(),
                      map_wetter_n=int((k.class_steps > 0).sum()), map_drier_n=int((k.class_steps < 0).sum()),
                      wet_gauges=len(wet_g), wet_shown_dry_n=int(wet_g.map_class.isin(["mostly dry", "seasonal"]).sum()),
                      dry_gauges=len(dry_g), dry_shown_wet_n=int(dry_g.map_class.isin(["usually flows", "year-round"]).sum()),
                      typ_median_ratio=k.typ_ratio.median(), typ_within_2x_pct=100 * (lr.abs() <= np.log10(2)).mean() if len(lr) else np.nan,
                      typ_n=len(lr)))
    S = pd.DataFrame(S)
    S.insert(0, "site", site_name())
    S.round(2).to_csv(f"{TABLES}/flow_vs_gauges_summary.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    print(S.round(2).to_string(index=False))
    # NHD disagreement: map says usually flows / year-round where NHD says intermittent, ephemeral or has no line
    W = X.pivot_table(index=["area", "map_class"], columns="nhd_class", values="miles", aggfunc="sum", fill_value=0)
    print(W.round(0).to_string())


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
