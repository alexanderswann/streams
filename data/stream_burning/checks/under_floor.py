"""Read-only: in a build with links cut at lake shores, the creek pieces under the map's 1 km2 floor (own + carried
drainage at their lower end) and whether a reach runs into them. AREA=<area> toppieces.py <root>"""
import sys, os
ROOT = sys.argv[1]
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd
import config
tot = dict(n=0, km=0.0, head=0, head_km=0.0, lake=0)
ex = []
for b in config.REGIONS:
    d = config.out_dir(b)
    s = gpd.read_file(f"{d}/streams_scored.gpkg")[["sid", "name", "area_km2", "geometry"]].to_crs(config.CRS)
    a = pd.read_csv(f"{d}/area_streams.csv").set_index("sid").area_full_km2
    f = pd.read_csv(f"{d}/flow_streams.csv", low_memory=False).set_index("sid").water_class
    s["full"] = s.sid.map(a); s["cls"] = s.sid.map(f)
    k = lambda c: (round(c[0], 1), round(c[1], 1))
    ends = set(k(g.coords[-1]) for g in s.geometry)
    low = s[s.full < 1.0]
    head = np.array([k(g.coords[0]) not in ends for g in low.geometry], bool) if len(low) else np.zeros(0, bool)
    creek = (low.cls != "reservoir").values
    tot["n"] += int(creek.sum()); tot["km"] += low.geometry.length[creek].sum() / 1000
    tot["head"] += int((creek & head).sum()); tot["head_km"] += low.geometry.length[creek & head].sum() / 1000
    tot["lake"] += int((~creek).sum())
print(f"{config.AREA:15s} reaches under 1 km2 (own + carried): creek {tot['n']} ({tot['km']:.1f} km), of them with no reach above {tot['head']} ({tot['head_km']:.1f} km); lake pieces {tot['lake']}")
