#!/usr/bin/env python3
"""Sudden changes along a drawn creek: two drawn stream pieces that meet end to end, carry about the same drainage
(within 20 %, so no tributary of any size joins between them) and yet differ by two or more flow classes or by 30+
fish-score points. Works on what the map draws (map3d_data.js), so it also sees the pieces 06_map.py adds below dams
and at lake outlets, which the reach tables and data/check_flow_drops.py never see.

    SITE_DIR=<published maps> python audit/scripts/drawn_jumps.py [area ...]
Tables: audit/tables/drawn_jumps.csv (every pair), drawn_jumps_summary.csv.
"""
import sys, os
from collections import defaultdict
import numpy as np, pandas as pd, shapely, pyproj
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from popups import reaches

ORDER = ["mostly dry", "seasonal", "usually flows", "year-round"]


def main(areas):
    rows, S = [], []
    for a in areas:
        r = reaches(a, layers=("streams",)).reset_index(drop=True)
        to_ll = pyproj.Transformer.from_crs(epsg(a), 4326, always_xy=True)
        g = r.geometry.values
        ends = defaultdict(list)
        for i, geom in enumerate(g):
            parts = getattr(geom, "geoms", [geom])
            for p in parts:
                c = p.coords
                for xy in (c[0], c[-1]):
                    ends[(round(xy[0]), round(xy[1]))].append(i)
        km2, fish = r.km2.to_numpy(float), r.fish.to_numpy(float)
        cls = [ORDER.index(c) if c in ORDER else None for c in r.flow_class]
        seen = set()
        for node, ids in ends.items():
            ids = sorted(set(ids))
            for x in range(len(ids)):
                for y in range(x + 1, len(ids)):
                    i, j = ids[x], ids[y]
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    lo, hi = sorted((km2[i], km2[j]))
                    if hi <= 0 or lo / hi < 0.8 or hi < 2.0:
                        continue
                    steps = abs(cls[i] - cls[j]) if cls[i] is not None and cls[j] is not None else 0
                    df = abs(fish[i] - fish[j])
                    if steps < 2 and df < 30:
                        continue
                    low, high = (i, j) if fish[i] <= fish[j] else (j, i)
                    lon, lat = to_ll.transform(*node)
                    rows.append(dict(area=a, lat=round(lat, 5), lon=round(lon, 5), km2=round(hi, 1), class_steps=steps,
                                     fish_diff=int(df), low_name=r.name.iat[low], low_fish=int(fish[low]), low_flow=r.flow_shown.iat[low],
                                     low_len_mi=round(r.len_m.iat[low] / MI, 2), low_rule=r.rule.iat[low],
                                     high_name=r.name.iat[high], high_fish=int(fish[high]), high_flow=r.flow_shown.iat[high],
                                     low_trout=bool(r.trout.iat[low]), high_trout=bool(r.trout.iat[high]),
                                     low_heat=r.heat_factor.iat[low], high_heat=r.heat_factor.iat[high]))
        d = pd.DataFrame(rows)
        d = d[d.area == a] if len(d) else d
        S.append(dict(area=a, pairs=len(d), flow_2_steps=int((d.class_steps >= 2).sum()) if len(d) else 0,
                      fish_30=int((d.fish_diff >= 30).sum()) if len(d) else 0,
                      reservoir_side=int(d.low_flow.str.contains("reservoir").sum()) if len(d) else 0,
                      low_side_mi=round(d.drop_duplicates(["low_name", "low_len_mi", "low_fish"]).low_len_mi.sum(), 1) if len(d) else 0))
        print(a, "done", flush=True)
    D = pd.DataFrame(rows).sort_values(["area", "km2"], ascending=[True, False])
    D.to_csv(f"{TABLES}/drawn_jumps.csv", index=False)
    S = pd.DataFrame(S)
    S.insert(0, "site", site_name())
    S.to_csv(f"{TABLES}/drawn_jumps_summary.csv", index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 30)
    print(S.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:] or NAMES)
