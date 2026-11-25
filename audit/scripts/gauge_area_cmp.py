"""Read-only: drainage area at USGS gauges and NHDPlus points, one audit label against another.
gauge_area_cmp.py <label old> <label new>"""
import sys, numpy as np, pandas as pd
import os as _os
T = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "audit", "tables")
o = pd.read_csv(f"{T}/{sys.argv[1]}/area_vs_gauges.csv", dtype={"site_no": str}); n = pd.read_csv(f"{T}/{sys.argv[2]}/area_vs_gauges.csv", dtype={"site_no": str})
m = o.merge(n, on=["area", "site_no"], how="outer", suffixes=("_old", "_new"), indicator=True)
print("gauges: old", len(o), "new", len(n), "| only old", int((m._merge == "left_only").sum()), "only new", int((m._merge == "right_only").sum()))
print(m[m._merge != "both"][["area", "site_no", "station_old", "station_new", "gauge_km2_old", "map_km2_old", "gauge_km2_new", "map_km2_new"]].to_string(index=False))
b = m[m._merge == "both"].copy()
b["e_old"] = (b.ratio_old - 1).abs(); b["e_new"] = (b.ratio_new - 1).abs()
ch = b[(b.ratio_old - b.ratio_new).abs() >= 0.02].copy()
ch["sq_mi"] = (ch.gauge_km2_old / 2.58999).round(1)
ch["verdict"] = np.where(ch.e_new < ch.e_old - 0.01, "better", np.where(ch.e_new > ch.e_old + 0.01, "WORSE", "same"))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(f"\ngauges whose map/gauge area ratio moved by 0.02+: {len(ch)} (better {int((ch.verdict=='better').sum())}, worse {int((ch.verdict=='WORSE').sum())})")
print(ch.sort_values(["verdict", "area"])[["area", "site_no", "station_old", "sq_mi", "ratio_old", "ratio_new", "dist_m_old", "dist_m_new", "reach_name_old", "reach_name_new", "lat_old", "lon_old", "verdict"]].round(3).to_string(index=False))
for lbl, lim in (("within 10 %", 0.10), ("within 25 %", 0.25)):
    print(lbl, "old", int((b.e_old <= lim).sum()), "new", int((b.e_new <= lim).sum()), "of", len(b))
