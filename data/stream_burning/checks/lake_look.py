"""One lake: NHD HR's lines leaving it (names down the chain), NHDPlus V2's flowlines in it, the published and the
new outlet and put-in (putin.py's tables: the 12 maps of 2026-11-21 in results/installed_2026-11-21, and the one
NEW_PUTINS names, e.g. results/root_fix_2026-11-22/putin_12_maps.csv).
NEW_PUTINS=<csv> AREA=<area> python lake_look.py "<lake name>" [ha]"""
import sys, os, json
P = "/Users/mac/Fishing"
NEW_PUTINS = os.environ.get("NEW_PUTINS", f"{P}/data/stream_burning/results/root_fix_2026-11-22/putin_12_maps.csv")
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, shapely.ops, pyproj
from config import *
from flowlib import reservoirs, FLOW
name, ha = sys.argv[1], (float(sys.argv[2]) if len(sys.argv) > 2 else None)
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
ll = lambda p: "%.5f,%.5f" % back.transform(p.x, p.y)[::-1]
lakes = reservoirs()
c = lakes[lakes.gnis_name == name] if name != "unnamed" else lakes[lakes.gnis_name.isna()]
if ha: c = c[(c.area / 1e4 - ha).abs() < 0.2]
for _, lk in c.iterrows():
    g = shapely.make_valid(lk.geometry); buf = g.buffer(30)
    print(f"{name} ({g.area / 1e4:.1f} ha), centre {ll(g.representative_point())}")
    for tag, f in (("published", "/Users/mac/Fishing/data/stream_burning/results/installed_2026-11-21/putin_12_maps.csv"), ("new", NEW_PUTINS)):
        t = pd.read_csv(f); t = t[(t.area == AREA) & (t.lake == name) & ((t.ha - g.area / 1e4).abs() < 0.2)]
        for _, r in t.iterrows():
            print(f"  {tag}: pit {r.pit_lat:.5f},{r.pit_lon:.5f} -> put-in {r.putin_lat:.5f},{r.putin_lon:.5f} ({r.pit_to_putin_m} m), {r.km2} km2 carried, kind {r.kind}, {r.misses}")
    for box in REGIONS:
        if not shapely.box(*REGIONS[box]["bbox"]).intersects(g):
            continue
        fl = gpd.read_file(f"{raw_dir(box)}/nhd_flowlines.gpkg").to_crs(CRS)
        fl = fl[fl.geometry.notna()]
        parts, meta = [], []
        for q, nm, ft in zip(shapely.force_2d(fl.geometry.values), fl.gnis_name.values, fl.ftype.values):
            for x in getattr(q, "geoms", [q]):
                if x.geom_type == "LineString" and x.length > 1:
                    parts.append(x); meta.append((nm if isinstance(nm, str) else "", int(ft)))
        tree = shapely.STRtree(parts)
        begins = {}
        for i, q in enumerate(parts):
            begins.setdefault((round(q.coords[0][0]), round(q.coords[0][1])), []).append(i)
        for j in tree.query(buf, predicate="intersects"):
            q = parts[j]
            s_in, e_in = buf.contains(shapely.Point(q.coords[0])), buf.contains(shapely.Point(q.coords[-1]))
            if s_in and not e_in:
                cur, seen, names, length = q, {j}, [f"{meta[j][1]}:{meta[j][0] or '-'}:{q.length:.0f}"], q.length
                while length < 4000:
                    nx = [k for k in begins.get((round(cur.coords[-1][0]), round(cur.coords[-1][1])), []) if k not in seen]
                    if not nx: break
                    nx.sort(key=lambda k: meta[k][1] not in (460, 558, 334))
                    cur = parts[nx[0]]; seen.add(nx[0]); names.append(f"{meta[nx[0]][1]}:{meta[nx[0]][0] or '-'}:{cur.length:.0f}"); length += cur.length
                ins = q.intersection(g)
                t0 = 0.0 if ins.is_empty else max(q.project(shapely.Point(xy)) for x in getattr(ins, "geoms", [ins]) if x.geom_type in ("LineString", "Point") for xy in x.coords)
                print(f"  [{box}] HR OUTFLOW leaving at {ll(q.interpolate(t0))}: " + " > ".join(names[:9]) + f"; ends {ll(shapely.Point(cur.coords[-1]))}")
            elif e_in and not s_in:
                print(f"  [{box}] HR inflow {meta[j][1]}:{meta[j][0] or '-'}:{q.length:.0f} entering at {ll(shapely.Point(q.coords[-1]))}")
        break
    v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg", columns=["comid", "hydroseq", "dnhydroseq", "totdasqkm", "gnis_name"]).to_crs(CRS)
    ins = v2[v2.intersects(g)]
    by = v2.drop_duplicates("hydroseq").set_index("hydroseq")
    for _, f in ins.sort_values("totdasqkm").iterrows():
        seq, chain = f.dnhydroseq, []
        for _ in range(4):
            if seq not in by.index: break
            b = by.loc[seq]; chain.append(f"{b.gnis_name if isinstance(b.gnis_name, str) else '-'} {b.totdasqkm:.1f}"); seq = b.dnhydroseq
        gg = shapely.line_merge(f.geometry)
        end = shapely.Point(list(getattr(gg, "geoms", [gg]))[-1].coords[-1])
        print(f"  NHDPlus V2 line in the lake: {f.gnis_name if isinstance(f.gnis_name, str) else '-'} {f.totdasqkm:.1f} km2, ends {ll(end)} ({'inside' if g.buffer(30).contains(end) else 'outside'} the lake); then " + " > ".join(chain))
