"""One table per question over the areas drops.py, drawn_lake_values.py and outlet_gaps.py were run for (their CSVs in
one folder: moves_<area>.csv, gone_<area>.csv, new_<area>.csv, drawn_<area>.csv, gaps_<area>.csv), and the reaches
to look at by name.  python summarize_drops.py <folder> [area ...]"""
import sys, os, glob
import numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 500)
D = sys.argv[1]
areas = sys.argv[2:] or sorted(os.path.basename(f)[6:-4] for f in glob.glob(f"{D}/moves_*.csv"))
km = lambda s: round(float(s.sum()) / 1000, 1)
DOWN, UP = ["lake", "carried", "drainage", "flow", "other"], ["left lake", "gained", "drainage+", "flow+", "other+"]
t1, t2, t3, names = [], [], [], []
for a in areas:
    m = pd.read_csv(f"{D}/moves_{a}.csv", low_memory=False)
    dn, up = m[m.ds <= -10], m[m.ds >= 10]
    row = dict(area=a, down=len(dn), **{c: int((dn.cause == c).sum()) for c in DOWN}, up=len(up),
               **{c: int((up.cause == c).sum()) for c in UP})
    row["lake_out200"] = int(((dn.cause == "lake") & (dn.out_m >= 200)).sum())
    t1.append(row)
    for c in ("flow", "other", "drainage"):
        names.append(dn[dn.cause == c].assign(area=a))
    if os.path.exists(f"{D}/drawn_{a}.csv"):
        d = pd.read_csv(f"{D}/drawn_{a}.csv")
        o, n = d[d.which == "old"], d[d.which == "new"]
        creek = lambda x: x[(x.out_m >= 100) & ~x.other_fl.isin(["reservoir", "no line"])]
        t2.append(dict(area=a, old_km=km(o.out_m), new_km=km(n.out_m), old_pieces=int((o.out_m >= 100).sum()),
                       new_pieces=int((n.out_m >= 100).sum()), put_right=len(creek(o)), put_right_km=km(creek(o).out_m),
                       newly_marked=len(creek(n)), newly_marked_km=km(creek(n).out_m),
                       newly_marked_fish40=int((creek(n).other_fs >= 40).sum())))
        names.append(creek(n).assign(area=a, cause="drawn as lake, was creek"))
    g, w = pd.read_csv(f"{D}/gone_{a}.csv", low_memory=False), pd.read_csv(f"{D}/new_{a}.csv", low_memory=False)
    cg, cw = g[~g.lake & (g.out_m >= 200)], w[~w.lake & (w.out_m >= 200)]
    real = cg[(cg.nhd >= 0.5) & cg.moved_m.isna()] if "nhd" in cg else cg.iloc[:0]
    row = dict(area=a, gone=len(cg), gone_km=km(cg.len_m), gone_on_nhd=len(real), gone_on_nhd_km=km(real.len_m),
               gone_on_nhd_60_km=km(real.len_m[real.fish_score >= 60]), new=len(cw), new_km=km(cw.len_m),
               new_60_km=km(cw.len_m[cw.fish_score >= 60]))
    if os.path.exists(f"{D}/gaps_{a}.csv"):
        q = pd.read_csv(f"{D}/gaps_{a}.csv")
        u = q[q.drawn < 0.5]
        row.update(outlet_links=len(q), outlet_km=km(q.len_m), undrawn=len(u), undrawn_km=km(u.len_m))
    t3.append(row)
    names.append(real.assign(area=a, cause="line gone, on an NHD line"))
tot = lambda rows: pd.concat([pd.DataFrame(rows), pd.DataFrame([{"area": "ALL", **pd.DataFrame(rows).drop(columns="area").sum().round(1).to_dict()}])])
print("== 10+ point fish-score moves of matched reaches, by cause (lake_out200: lake-group reaches with 200+ m outside every lake outline)")
print(tot(t1).to_string(index=False))
if t2:
    print("\n== stream line the map draws with a lake's values outside the lakes it draws (km), and the 100+ m pieces")
    print(tot(t2).to_string(index=False))
print("\n== creek lines only one build has (not lake reaches, 200+ m outside every lake outline); stream links below outlets")
print(tot(t3).to_string(index=False))
n = pd.concat(names, ignore_index=True)
if len(n):
    n.to_csv(f"{D}/named.csv", index=False)
    print(f"\nnamed cases written to {D}/named.csv: " + ", ".join(f"{k} {v}" for k, v in n.cause.value_counts().items()))
