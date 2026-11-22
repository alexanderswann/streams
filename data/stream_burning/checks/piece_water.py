"""Read-only: in a build with links cut at lake shores, the pieces that end above the point where water carried from
elsewhere (past a dam, a pond) joins their link: consecutive pieces of one link where the lower one's carried water
(area_full - area) is 1+ km2 more than the upper one's. AREA=<area> piece_water.py <root> [-v]"""
import sys, os
ROOT = sys.argv[1]; V = "-v" in sys.argv
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
rows = []
for b in config.REGIONS:
    d = config.out_dir(b)
    s = gpd.read_file(f"{d}/streams_scored.gpkg").to_crs(config.CRS)
    a = pd.read_csv(f"{d}/area_streams.csv").set_index("sid")
    f = pd.read_csv(f"{d}/flow_streams.csv", low_memory=False).set_index("sid")
    s["full"] = s.sid.map(a.area_full_km2); s["cls"] = s.sid.map(f.water_class)
    s["car"] = s.full - s.area_km2
    k = lambda c: (round(c[0], 1), round(c[1], 1))
    start = {}
    for i, g in enumerate(s.geometry):
        start.setdefault(k(g.coords[0]), []).append(i)
    ends_at = {}
    for i, g in enumerate(s.geometry):
        ends_at.setdefault(k(g.coords[-1]), []).append(i)
    for i, g in enumerate(s.geometry):
        e = k(g.coords[-1])
        nxt = start.get(e, [])
        # a cut, not a confluence: exactly one reach ends here and one starts
        if len(nxt) == 1 and len(ends_at.get(e, [])) == 1:
            j = nxt[0]
            if s.car.iat[j] - s.car.iat[i] >= 1.0:
                ll = gpd.GeoSeries([shapely.Point(g.coords[-1][:2])], crs=config.CRS).to_crs(4326).iloc[0]
                rows.append(dict(sid=s.sid.iat[i], name=s["name"].iat[i], len_m=round(g.length), own=s.area_km2.iat[i], full=s.full.iat[i], cls=s.cls.iat[i],
                                 below=s.sid.iat[j], below_full=s.full.iat[j], below_cls=s.cls.iat[j], lat=round(ll.y, 5), lon=round(ll.x, 5)))
t = pd.DataFrame(rows)
if not len(t):
    print(f"{config.AREA:15s} none"); sys.exit()
creek = t[t.cls != "reservoir"]
print(f"{config.AREA:15s} pieces ending above where carried water joins their link: {len(t)} ({t.len_m.sum()/1000:.1f} km); creek pieces {len(creek)} ({creek.len_m.sum()/1000:.1f} km), "
      f"of them with 10x more water below {int((creek.below_full >= 10 * creek.full).sum())}")
if V:
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
    print(t.sort_values("below_full", ascending=False).head(40).to_string(index=False))
