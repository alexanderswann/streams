#!/usr/bin/env python3
"""The popup's "summer water about X F" against measured July-August water temperatures.

The measured side is rebuilt here from the Water Quality Portal downloads in each area's cache
(data/raw/<area>/_shared/cache/wqp_station_temp.csv, wqp_result_temp.csv), not taken from watertemp.py: stream sites,
July and August, 2000 on, readings between 09:00 and 18:00 where a time is given, the site's median. The map side is
the popup of the nearest drawn stream line within 60 m. The fits were made on these sites, so this is not an
independent test of the model; it shows what the popups say at the places where the answer is known, and whether the
"+- N F" they state covers it.
Tables: audit/tables/<label>/watertemp_vs_sites.csv (per site), watertemp_summary.csv
"""
import sys, os
import numpy as np, pandas as pd, geopandas as gpd, shapely
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from popups import reaches


def sites(area):
    c = f"{ROOT}/data/raw/{area}/_shared/cache"
    st = pd.read_csv(f"{c}/wqp_station_temp.csv", low_memory=False)
    rs = pd.read_csv(f"{c}/wqp_result_temp.csv", low_memory=False)
    st = st[st.MonitoringLocationTypeName.astype(str).str.contains("Stream|River", case=False)]
    rs = rs[rs.CharacteristicName.astype(str).str.lower().eq("temperature, water")]
    v = pd.to_numeric(rs.ResultMeasureValue, errors="coerce")
    unit = rs["ResultMeasure/MeasureUnitCode"].astype(str).str.lower()
    v = np.where(unit.str.contains("f"), (v - 32) * 5 / 9, v)
    d = pd.to_datetime(rs.ActivityStartDate, errors="coerce")
    hh = pd.to_numeric(rs["ActivityStartTime/Time"].astype(str).str.slice(0, 2), errors="coerce")
    ok = d.dt.month.isin([7, 8]) & (d.dt.year >= 2000) & (v > 0) & (v < 40) & (hh.isna() | ((hh >= 9) & (hh < 18)))
    r = pd.DataFrame(dict(site=rs.MonitoringLocationIdentifier, c=v))[ok.to_numpy()]
    g = r.groupby("site").c.agg(["median", "size"]).rename(columns={"median": "measured_c", "size": "readings"})
    st = st.drop_duplicates("MonitoringLocationIdentifier").set_index("MonitoringLocationIdentifier")
    g = g.join(st[["MonitoringLocationName", "LatitudeMeasure", "LongitudeMeasure"]], how="inner").dropna()
    return gpd.GeoDataFrame(g.reset_index(names="site"), geometry=gpd.points_from_xy(g.LongitudeMeasure, g.LatitudeMeasure), crs=4326)


def main(areas):
    rows, S = [], []
    for a in areas:
        try:
            s = sites(a).to_crs(epsg(a))
        except FileNotFoundError:
            continue
        r = reaches(a, layers=("streams",)).reset_index(drop=True)
        tree = shapely.STRtree(r.geometry.values)
        idx, dist = [], []
        for g in s.geometry.values:
            j = tree.nearest(g)
            idx.append(j); dist.append(shapely.distance(r.geometry.values[j], g))
        s["dist_m"] = dist
        q = r.iloc[idx].reset_index(drop=True)
        s = s.reset_index(drop=True)
        s["map_f"], s["pm_f"], s["tailwater"], s["sq_mi"], s["name"] = q.water_f, q.water_pm_f, q.tailwater, (q.km2 / 2.58999).round(1), q.name
        s["measured_f"] = s.measured_c * 9 / 5 + 32
        s = s[(s.dist_m <= 60)]
        s.insert(0, "area", a)
        rows.append(pd.DataFrame(s.drop(columns="geometry")))
        k = s[s.map_f.notna() & (s.readings >= 3)]
        if len(k) < 5:
            S.append(dict(area=a, sites_on_a_drawn_line=len(s), with_estimate_3plus_readings=len(k)))
            continue
        e = k.map_f - k.measured_f
        cold = k[k.measured_f <= 68]; warm = k[k.measured_f >= 72]
        S.append(dict(area=a, sites_on_a_drawn_line=len(s), with_estimate_3plus_readings=len(k), stated_pm_f=float(k.pm_f.median()),
                      bias_f=e.mean(), rmse_f=float(np.sqrt((e ** 2).mean())), within_stated_pct=100 * (e.abs() <= k.pm_f).mean(),
                      spread_of_sites_f=k.measured_f.std(), map_range_f=f"{k.map_f.min():.0f}-{k.map_f.max():.0f}",
                      measured_range_f=f"{k.measured_f.min():.0f}-{k.measured_f.max():.0f}",
                      cold_sites_bias_f=(cold.map_f - cold.measured_f).mean() if len(cold) else np.nan, cold_sites=len(cold),
                      warm_sites_bias_f=(warm.map_f - warm.measured_f).mean() if len(warm) else np.nan, warm_sites=len(warm),
                      # the score's cut: full credit to 68 F, none from 77 F. Sites measured 72 F+ that the map puts under 68 F, and the reverse
                      warm_read_as_full_credit=int(((k.measured_f >= 72) & (k.map_f <= 68)).sum()),
                      cool_read_as_warm=int(((k.measured_f <= 64) & (k.map_f >= 72)).sum())))
        print(a, "done", flush=True)
    D = pd.concat(rows)
    D.round(2).to_csv(f"{TABLES}/watertemp_vs_sites.csv", index=False)
    S = pd.DataFrame(S)
    S.round(1).to_csv(f"{TABLES}/watertemp_summary.csv", index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
    print(S.round(1).to_string(index=False))
    D["err"] = D.map_f - D.measured_f
    w = D[(D.readings >= 5) & D.map_f.notna()].sort_values("err")
    cols = ["area", "MonitoringLocationName", "readings", "measured_f", "map_f", "pm_f", "sq_mi", "tailwater", "LatitudeMeasure", "LongitudeMeasure"]
    print("map reads coldest against measured:"); print(w.head(12)[cols].round(1).to_string(index=False))
    print("map reads warmest against measured:"); print(w.tail(12)[cols].round(1).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
