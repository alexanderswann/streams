"""For the lakes whose outlet NHD's name decides: does NHDPlus's line leave by the same outflow line, by another, or
has NHDPlus no line leaving the lake? Replayed on a build from before 2026-11-22, like rule_tally.py.
BEFORE=<build root> STITCH=<03b_stitch.py> python name_vs_v.py <rule_tally all.csv>"""
import sys, os, importlib.util, subprocess, json
P = "/Users/mac/Fishing"
import pandas as pd
t = pd.read_csv(sys.argv[1])
t = t[(t.step == "NHD's name") & t.in_build.astype(bool)]
code = r'''
import sys, os, importlib.util, json
P = "/Users/mac/Fishing"
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, shapely
spec = importlib.util.spec_from_file_location("stitch_nv", os.environ["STITCH"]); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
from config import *
from flowlib import still_water
want = json.loads(sys.argv[1])
out = []
for box in REGIONS:
    w = [x for x in want if x[0] == box]
    if not w: continue
    with rasterio.open(f"{os.environ['BEFORE']}/data/derived/{AREA}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    index = M.outflow_index(M.nhd_lines([box], M.LAKE_LINE_FTYPES + M.BUILT_FTYPES))
    v2 = M.nhdplus([box])
    wet, wins = np.zeros(fd.shape, bool), {}
    for k, g in enumerate(lakes.geometry):
        w_ = M.lake_cells(fd, g, T)
        if w_ is not None and w_[2].any():
            r0, c0, mask = w_
            if ((fd[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] == M.PIT) & mask).any():
                wins[k] = w_; wet[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] |= mask
    for k, w_ in wins.items():
        geom = shapely.make_valid(lakes.geometry.iloc[k]); name = lakes.gnis_name.iloc[k]; name = name if isinstance(name, str) else "unnamed"
        if not any(x[1] == name and abs(x[2] - geom.area / 1e4) < 0.2 for x in w): continue
        cands = [q for q in M.nhd_outlets(fd, geom, T, w_, index, M.LAKE_LINE_FTYPES, wet) if q["cells"]]
        v = M.nhdplus_exit(geom, v2)
        named = [q for q in cands if q["named"]]; other = [q for q in cands if not q["named"]]
        if v is None: verdict = "NHDPlus has no line leaving the lake"
        elif any(q["exit"].distance(v) <= M.WAY_MAX for q in named): verdict = "NHDPlus leaves by the named line too"
        elif any(q["exit"].distance(v) <= M.WAY_MAX for q in other): verdict = "NHDPlus leaves by another line"
        else: verdict = "NHDPlus leaves the lake away from every outflow line"
        dmin = lambda qs: round(min(q["exit"].distance(v) for q in qs)) if v is not None and qs else None
        out.append(dict(area=AREA, box=box, lake=name, ha=round(geom.area / 1e4, 1), lines=len(cands), named=len(named), verdict=verdict, v_to_named_m=dmin(named), v_to_other_m=dmin(other)))
print(json.dumps(out))
'''
rows = []
for a, g in t.groupby("area"):
    want = json.dumps([[r.box, r.lake, float(r.ha)] for r in g.itertuples()])
    r = subprocess.run([f"{P}/.venv/bin/python", "-W", "ignore", "-c", code, want], capture_output=True, text=True, env={**os.environ, "AREA": a})
    if r.returncode != 0:
        print("FAILED", a, r.stderr[-400:]); continue
    rows += json.loads(r.stdout.strip().splitlines()[-1])
d = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
print(d.to_string(index=False)); print(); print(d.groupby("verdict").size().to_string())
d.to_csv(os.path.join(os.path.dirname(sys.argv[1]), "name_vs_nhdplus.csv"), index=False)
