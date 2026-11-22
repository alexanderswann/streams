"""Each drawn line whose drainage changed (drainage_moves.py's table), with the lake whose water it lost or gained:
the lake of the same map whose carried drainage equals the change (within 4 % or 0.15 km2) and whose put-in moved,
the nearest such lake's old (for a loss) or new (for a gain) put-in. With how the lake's outlet was decided
(rule_tally.py's table) and how far the put-in moved.
python attribute_moves.py <drainage_moves.csv> <published putin csv> <new putin dir> <rule tally all.csv> <out.csv>"""
import sys, os
import numpy as np, pandas as pd
mv, pub, newdir, tally, out = sys.argv[1:6]
t = pd.read_csv(mv); P = pd.read_csv(pub); T = pd.read_csv(tally)
rows = []
for a, g in t.groupby("area"):
    p = P[P.area == a].copy(); n = pd.read_csv(f"{newdir}/{a}.csv")
    key = lambda d: d.box + "|" + d.lake.astype(str) + "|" + d.ha.round(1).astype(str)
    p["key"], n["key"] = key(p), key(n)
    m = p.merge(n, on="key", how="outer", suffixes=("_o", "_n"))
    lat0 = g.lat.mean(); kx, ky = 111.32 * np.cos(np.radians(lat0)), 110.574
    m["moved_m"] = 1000 * np.hypot((m.putin_lat_o - m.putin_lat_n) * ky, (m.putin_lon_o - m.putin_lon_n) * kx)
    tt = T[T.area == a].assign(key=lambda d: d.box + "|" + d.lake.astype(str) + "|" + d.ha.round(1).astype(str)).drop_duplicates("key").set_index("key")
    for r in g.itertuples():
        d = abs(r.old_km2 - r.new_km2)
        best = None
        for q in m.itertuples():
            k_o, k_n = q.km2_o, q.km2_n
            k = k_o if r.change == "lost" else k_n
            if not (k == k) or abs(k - d) > max(0.04 * d, 0.15):
                continue
            if q.moved_m == q.moved_m and q.moved_m < 30:
                continue                                   # its put-in didn't move: not this lake
            la, lo = (q.putin_lat_o, q.putin_lon_o) if r.change == "lost" else (q.putin_lat_n, q.putin_lon_n)
            if not (la == la):
                continue
            dist = 1000 * np.hypot((la - r.lat) * ky, (lo - r.lon) * kx)
            if best is None or dist < best[0]:
                best = (dist, q)
        row = dict(area=a, name=r.name if isinstance(r.name, str) else "", ft=r.ft, change=r.change, old_km2=r.old_km2, new_km2=r.new_km2, nhdplus_km2=r.nhdplus_km2,
                   verdict=r.verdict, old_fish=r.old_fish, new_fish=r.new_fish, lat=r.lat, lon=r.lon)
        if best is not None and best[0] < 8000:
            q = best[1]; kk = q.key
            lake = q.lake_o if isinstance(q.lake_o, str) else q.lake_n
            ha = q.ha_o if q.ha_o == q.ha_o else q.ha_n
            row.update(lake=f"{lake} ({ha:g} ha)", lake_km2=round(q.km2_o if r.change == "lost" else q.km2_n, 2), putin_m=round(best[0]), putin_moved_m=round(q.moved_m) if q.moved_m == q.moved_m else None,
                       decided=(tt.step.get(kk) if kk in tt.index else ""), nhd_outlets=q.hr_outlets_n if q.hr_outlets_n == q.hr_outlets_n else q.hr_outlets_o)
        rows.append(row)
o = pd.DataFrame(rows)
o.to_csv(out, index=False)
pd.set_option("display.width", 280); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 60)
print(f"{len(o)} pieces; with a lake found: {int(o.lake.notna().sum())}")
print(o[o.lake.isna()].sort_values(["change", "area", "ft"], ascending=[True, True, False])[["area", "name", "ft", "change", "old_km2", "new_km2", "nhdplus_km2", "verdict", "old_fish", "new_fish", "lat", "lon"]].to_string(index=False))
