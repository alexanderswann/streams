"""Which fish-score inputs moved for the 10+ point moves drops.py put in the given groups: one line per reach, the
terms that differ between the two builds' ranked tables, and whether the reach was cut differently (its length
changed by 10%+: a new stream line joining it splits it, and each piece is then scored on its own trout record,
gradient and shade).
python why_moved.py <folder with drops.py's moves_<area>.csv> <rootA|-> <rootB|-> <cause[,cause]> [area ...]
  e.g. why_moved.py /tmp/drops /tmp/before - other,drainage,flow"""
import sys, os, glob
import pandas as pd
P = "/Users/mac/Fishing"
D, A, B = sys.argv[1], *[P if x == "-" else x for x in sys.argv[2:4]]
causes = sys.argv[4].split(",")
areas = sys.argv[5:] or sorted(os.path.basename(f)[6:-4] for f in glob.glob(f"{D}/moves_*.csv"))
NUM = (("water_term", 0.03), ("thermal", 0.03), ("trout_factor", 0.01), ("heat_factor", 0.01), ("burn_factor", 0.01),
       ("channel_factor", 0.01), ("gradient_pct", 0.3), ("approach_med_min", 5), ("bike_med_min", 5), ("area_full_km2", None),
       ("shade_pct", 5), ("canopy_pct", 5), ("northness", 0.05), ("elev_m", 15), ("air_aug", 0.3), ("water_aug", 0.3))
TXT = ("trout_water", "trout_found", "trout_absent", "water_class", "water_rule", "below_dam", "tailwater", "gauge_name",
       "flow_src", "flow")
rows = []
for a in areas:
    m = pd.read_csv(f"{D}/moves_{a}.csv", low_memory=False)
    m = m[m.cause.isin(causes)]
    if not len(m):
        continue
    ta = pd.read_csv(f"{A}/output/{a}/stream_reaches_ranked.csv", low_memory=False).set_index("sid")
    tb = pd.read_csv(f"{B}/output/{a}/stream_reaches_ranked.csv", low_memory=False).set_index("sid")
    for _, r in m.iterrows():
        x, y = ta.loc[r.sid_a], tb.loc[r.sid_b]
        ch = []
        for c, tol in NUM:
            if c not in x or c not in y:
                continue
            u, v = pd.to_numeric(x[c], errors="coerce"), pd.to_numeric(y[c], errors="coerce")
            if pd.isna(u) and pd.isna(v):
                continue
            if c == "area_full_km2":
                if not 0.8 <= (v / u if u else 9) <= 1.25:
                    ch.append(f"{c} {u:.1f}>{v:.1f}")
            elif pd.isna(u) != pd.isna(v) or abs(u - v) > tol:
                ch.append(f"{c} {u:.2f}>{v:.2f}")
        ch += [f"{c} {str(x[c])[:26]}>{str(y[c])[:26]}" for c in TXT if c in x and c in y and str(x[c]) != str(y[c])]
        rows.append(dict(area=a, sid_b=r.sid_b, name=str(y.get("name"))[:22], fish=f"{x.fish_score:.0f}>{y.fish_score:.0f}",
                         cause=r.cause, len_m=f"{x.len_m:.0f}>{y.len_m:.0f}", recut=not 0.9 <= y.len_m / x.len_m <= 1.1,
                         changed="; ".join(ch)))
t = pd.DataFrame(rows)
pd.set_option("display.width", 330); pd.set_option("display.max_rows", 500); pd.set_option("display.max_colwidth", 230)
print(t.to_string(index=False))
print(f"\ncut differently (length changed 10%+): {int(t.recut.sum())} of {len(t)}")
