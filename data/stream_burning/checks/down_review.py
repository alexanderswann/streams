"""All areas: the reaches both builds have that score 10+ lower in the new one (drops.py's moves_<area>.csv), with
NHDPlus's drainage there: a reach whose full drainage moved TOWARDS NHDPlus's is a correction, one that moved away
lost water it should carry. python down_review.py <drops dir> [areas]"""
import sys, os, glob
import numpy as np, pandas as pd
D = sys.argv[1]
areas = sys.argv[2:] or sorted(os.path.basename(f)[6:-4] for f in glob.glob(f"{D}/moves_*.csv"))
pd.set_option("display.width", 280); pd.set_option("display.max_columns", 50); pd.set_option("display.max_rows", 400)
rows = []
for a in areas:
    f = f"{D}/moves_{a}.csv"
    if not os.path.exists(f) or os.path.getsize(f) < 10:
        continue
    t = pd.read_csv(f)
    t["area"] = a
    rows.append(t)
t = pd.concat(rows, ignore_index=True)
print(list(t.columns))
t = t[t.ds <= -10].copy()
for c_ in ("v2_km2", "af_a", "af_b"):
    t[c_] = pd.to_numeric(t[c_], errors="coerce").astype(float)
v = t.v2_km2.where(t.v2_km2 > 0)
t["toward_nhdplus"] = np.where(v.isna(), "no NHDPlus line", np.where((np.log(t.af_b.clip(lower=0.01) / v)).abs() < (np.log(t.af_a.clip(lower=0.01) / v)).abs() - 0.05,
                                                                 "towards", np.where(t.af_b.round(2) == t.af_a.round(2), "same drainage", "AWAY")))
t["mi"] = t.len_m_b / 1609.344
print("\n== reaches scoring 10+ lower, by cause and by whether their drainage moved towards NHDPlus's")
print(t.groupby(["area", "cause", "toward_nhdplus"]).agg(reaches=("mi", "size"), mi=("mi", "sum"), was60=("fish_score_a", lambda s: int((s >= 60).sum())),
                                                         now60=("fish_score_b", lambda s: int((s >= 60).sum()))).round(2).to_string())
look = t[(t.toward_nhdplus == "AWAY") | ((t.cause == "carried") & (t.toward_nhdplus != "towards"))]
print(f"\n== to look at: drainage moved away from NHDPlus's, or carried water lost with no NHDPlus line to judge by: {len(look)} reaches, {look.mi.sum():.1f} mi")
print(look.sort_values(["area", "lat_b", "lon_b"])[["area", "sid_b", "name_b", "len_m_b", "area_km2_b", "af_a", "af_b", "v2_km2", "water_class_a", "water_class_b", "fish_score_a", "fish_score_b", "cause", "lat_b", "lon_b"]].round(3).to_string(index=False))
