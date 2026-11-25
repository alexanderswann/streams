"""Read-only: drainage area at NHDPlus points (39+ sq mi), one audit label against another.
nhdplus_area_cmp.py <label old> <label new>"""
import sys, numpy as np, pandas as pd
import os as _os
T = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "audit", "tables")
o = pd.read_csv(f"{T}/{sys.argv[1]}/area_vs_nhdplus.csv"); n = pd.read_csv(f"{T}/{sys.argv[2]}/area_vs_nhdplus.csv")
m = o.merge(n, on=["area", "comid"], suffixes=("_old", "_new"))
m["e_old"] = np.abs(np.log(m.ratio_old.clip(1e-3))); m["e_new"] = np.abs(np.log(m.ratio_new.clip(1e-3)))
m["sq_mi"] = (m.nhdplus_km2_old / 2.58999).round(0)
moved = m[np.abs(np.log(m.ratio_new.clip(1e-3) / m.ratio_old.clip(1e-3))) >= np.log(1.1)]
worse, better = moved[moved.e_new > moved.e_old + 0.02], moved[moved.e_new < moved.e_old - 0.02]
print(f"points {len(m)}; ratio moved by 10 %+: {len(moved)}; better {len(better)}, worse {len(worse)}")
g = pd.DataFrame({"better": better.groupby("area").size(), "worse": worse.groupby("area").size()}).fillna(0).astype(int)
print(g.to_string())
for lbl, lim in (("within 10 %", np.log(1.1)), ("within 25 %", np.log(1.25)), ("under half", np.log(2))):
    if lbl == "under half": print(lbl, "old", int((m.ratio_old < 0.5).sum()), "new", int((m.ratio_new < 0.5).sum()))
    else: print(lbl, "old", int((m.e_old <= lim).sum()), "new", int((m.e_new <= lim).sum()), "of", len(m))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
# one line per stream: the largest point of each worse run
w = worse.sort_values("sq_mi", ascending=False).drop_duplicates(["area", "nhd_name_old"]).head(25)
print("\nworse, largest point per named stream:"); print(w[["area", "nhd_name_old", "sq_mi", "ratio_old", "ratio_new", "lat_old", "lon_old", "reach_name_new"]].round(3).to_string(index=False))
b = better.sort_values("sq_mi", ascending=False).drop_duplicates(["area", "nhd_name_old"]).head(15)
print("\nbetter, largest point per named stream:"); print(b[["area", "nhd_name_old", "sq_mi", "ratio_old", "ratio_new", "lat_old", "lon_old", "reach_name_new"]].round(3).to_string(index=False))
