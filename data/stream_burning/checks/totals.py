"""Reaches, km of stream line, km of fish 60+ and km of lake ("reservoir") reaches per area, for any number of builds.
python totals.py <label>=<root|-> [<label>=<root> ...]     e.g. totals.py before=/tmp/before now=-"""
import sys, os
import pandas as pd
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts")
import config
roots = [(a.split("=")[0], P if a.split("=")[1] == "-" else a.split("=")[1]) for a in sys.argv[1:]]
rows = []
for a in config.AREAS:
    r = dict(area=a)
    for k, root in roots:
        f = f"{root}/output/{a}/stream_reaches_ranked.csv"
        if not os.path.exists(f):
            continue
        d = pd.read_csv(f, low_memory=False)
        d = d[~d.sid.astype(str).str.contains("+", regex=False)]          # not 06_map's drawn-through pieces
        r[f"n_{k}"], r[f"km_{k}"] = len(d), round(d.len_m.sum() / 1000, 1)
        r[f"f60_{k}"] = round(d.len_m[d.fish_score >= 60].sum() / 1000, 1)
        r[f"lake_{k}"] = round(d.len_m[d.water_class == "reservoir"].sum() / 1000, 1)
    rows.append(r)
t = pd.DataFrame(rows)
t = pd.concat([t, pd.DataFrame([{"area": "ALL", **t.drop(columns="area").sum().round(1).to_dict()}])])
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
print(t.to_string(index=False))
