"""For each reach that lost carried water (drops' moves table), the lake whose carried drainage matches the loss and
whose put-in moved: old and new put-in. python lost_water_lakes.py <drops dir> <putin dir> [areas]"""
import sys, os, glob, math
import numpy as np, pandas as pd
D, PUT = sys.argv[1], sys.argv[2]
areas = sys.argv[3:] or sorted(os.path.basename(f)[6:-4] for f in glob.glob(f"{D}/moves_*.csv"))
old_all = pd.read_csv("/Users/mac/Fishing/data/stream_burning/results/installed_2026-11-21/putin_12_maps.csv")
pd.set_option("display.width", 280); pd.set_option("display.max_columns", 50); pd.set_option("display.max_rows", 400)
def dist(a, b, c, d):
    return math.hypot((d - b) * 111320 * math.cos(math.radians(a)), (c - a) * 110574)
rows = []
for a in areas:
    f = f"{D}/moves_{a}.csv"
    if not os.path.exists(f) or os.path.getsize(f) < 10: continue
    t = pd.read_csv(f); t = t[(t.ds <= -10) & (t.cause == "carried")]
    new = pd.read_csv(f"{PUT}/{a}.csv"); old = old_all[old_all.area == a]
    for _, r in t.iterrows():
        lost = r.af_a - r.af_b
        c = old[(old.km2 - lost).abs() <= max(0.06 * lost, 0.08)].copy()
        c["d"] = [dist(r.lat_b, r.lon_b, x, y) for x, y in zip(c.putin_lat, c.putin_lon)]
        c = c[c.d < 8000].sort_values("d")
        if not len(c):
            rows.append(dict(area=a, sid=r.sid_b, name=r.name_b, mi=round(r.len_m_b / 1609.344, 2), lost_km2=round(lost, 2), v2=r.v2_km2, fish=f"{r.fish_score_a:.0f}->{r.fish_score_b:.0f}", lake="?")); continue
        q = c.iloc[0]
        n = new[(new.box == q.box) & (new.lake == q.lake) & ((new.ha - q.ha).abs() < 0.05)]
        n = n.iloc[int(np.argmin([dist(q.pit_lat, q.pit_lon, x, y) for x, y in zip(n.pit_lat, n.pit_lon)]))] if len(n) else None
        rows.append(dict(area=a, sid=r.sid_b, name=r.name_b, mi=round(r.len_m_b / 1609.344, 2), lost_km2=round(lost, 2), v2=r.v2_km2, fish=f"{r.fish_score_a:.0f}->{r.fish_score_b:.0f}",
                         lake=f"{q.lake} ({q.ha:g} ha)", old_putin_off_m=q.pit_to_putin_m, old_miss=q.misses, old_pit_at=q.pit_at, hr_outlets=q.hr_outlets,
                         pit_moved_m=(round(dist(q.pit_lat, q.pit_lon, n.pit_lat, n.pit_lon)) if n is not None else None),
                         putin_moved_m=(round(dist(q.putin_lat, q.putin_lon, n.putin_lat, n.putin_lon)) if n is not None else None),
                         new_pit=(f"{n.pit_lat:.5f},{n.pit_lon:.5f}" if n is not None else "no link now")))
t = pd.DataFrame(rows)
if not len(t):
    print('no reach lost carried water'); sys.exit()
g = t.groupby(["area", "lake"], dropna=False).agg(reaches=("mi", "size"), mi=("mi", "sum"), lost_km2=("lost_km2", "max"), v2_max=("v2", "max"), fish=("fish", lambda s: "; ".join(s.head(4))),
                                                 old_putin_off_m=("old_putin_off_m", "first"), old_miss=("old_miss", "first"), hr_outlets=("hr_outlets", "first"),
                                                 pit_moved_m=("pit_moved_m", "first"), putin_moved_m=("putin_moved_m", "first"), new_pit=("new_pit", "first"))
print(g.round(2).to_string())
