"""Read-only: the 10+ point moves of an evaluation (evaluate.sh), by what the reach is in the new build.
moves2.py <eval dir> <B root name, e.g. rB>"""
import sys, os, pandas as pd, numpy as np
E, BN = sys.argv[1], sys.argv[2]
ORDER = ["la", "jackson", "n_georgia", "central_vt", "ne_ct", "lexington_va", "se_pa", "smokies", "adk_high_peaks", "adk_northwest", "adk_southwest", "adk_southeast"]
tot = {}
keep = []
for a in ORDER:
    if not os.path.exists(f"{E}/compare_{a}.csv"):
        continue
    m = pd.read_csv(f"{E}/compare_{a}.csv", low_memory=False)
    st = pd.read_csv(f"{E}/straddle_{BN}_{a}.csv", low_memory=False).set_index("sid")
    m = m.join(st[["len_m", "in_drawn", "flag"]].add_prefix("st_"), on="sid_b")
    m["share"] = m.st_in_drawn / m.st_len_m
    m["out_m"] = m.st_len_m - m.st_in_drawn
    ca = m.water_class_a.fillna("-"); cb = m.water_class_b.fillna("-")
    def cause(r):
        ra, rb = (r.water_class_a if isinstance(r.water_class_a, str) else "-"), (r.water_class_b if isinstance(r.water_class_b, str) else "-")
        if r.ds <= -10:
            if rb == "reservoir" and ra != "reservoir":
                return "D1 lake water: now lake, 90%+ inside a drawn lake" if r.share >= 0.9 else ("D2 now lake, 50-90% inside a drawn lake" if r.share >= 0.5 else "D3 now lake, under half inside a drawn lake")
            if r.ratio <= 0.8: return "D4 less drainage"
            if ra != rb: return "D5 flow class fell"
            return "D6 other"
        if r.ds >= 10:
            if ra == "reservoir" and rb != "reservoir":
                return "U1 creek: was lake, now creek, under 10% inside a drawn lake" if r.share <= 0.1 else "U2 was lake, now creek, 10%+ inside a drawn lake"
            if r.ratio >= 1.2: return "U3 more drainage"
            if ra != rb: return "U4 flow class rose"
            return "U5 other"
        return None
    m["cause"] = [cause(r) for r in m.itertuples()]
    mv = m[m.cause.notna()].copy(); mv.insert(0, "area", a); keep.append(mv)
    tot[a] = mv.cause.value_counts()
t = pd.DataFrame(tot).fillna(0).astype(int).sort_index(); t["all"] = t.sum(axis=1)
pd.set_option("display.width", 260)
print(t.to_string())
al = pd.concat(keep, ignore_index=True)
for c in sorted(al.cause.unique()):
    d = al[al.cause == c]
    print(f"{c}: {len(d)} reaches, {d.len_m_b.sum()/1000:.1f} km; of that inside drawn lakes {d.st_in_drawn.sum()/1000:.1f} km, outside {d.out_m.sum()/1000:.1f} km")
al.to_csv(f"{E}/moves_all.csv", index=False)
