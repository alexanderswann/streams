"""For every lake whose put-in is the first cell of 03b's way out (at_top) but which putin.py doesn't find on the way
out (no stream link starts by the pit): is a line drawn at the put-in, and what does it carry?
python top_drawn.py <putin dir> <maps dir> [areas]"""
import sys, os, json, glob, math
import pandas as pd
PUT, NEW = sys.argv[1], sys.argv[2]
areas = sys.argv[3:] or sorted(os.path.basename(f)[:-4] for f in glob.glob(f"{PUT}/*.csv"))
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
def layer(t, key):
    i = t.find(f'"{key}"'); j = t.find('{', i); d = 0
    for k in range(j, len(t)):
        if t[k] == '{': d += 1
        elif t[k] == '}':
            d -= 1
            if d == 0: return json.loads(t[j:k+1])["features"]
rows = []
for a in areas:
    t = pd.read_csv(f"{PUT}/{a}.csv")
    t = t[(t.misses != "on the way out")]
    if not len(t):
        continue
    F = layer(open(f"{NEW}/{a}/map3d_data.js").read(), "streams")
    for _, r in t.iterrows():
        kx = 111320 * math.cos(math.radians(r.putin_lat)); best = (1e9, None)
        for f in F:
            for x, y, *_ in f["geometry"]["coordinates"]:
                d = math.hypot((x - r.putin_lon) * kx, (y - r.putin_lat) * 110574)
                if d < best[0]:
                    best = (d, f["properties"])
        q = best[1] or {}
        rows.append(dict(area=a, lake=r.lake, ha=r.ha, km2=r.km2, misses=r.misses, at_top=bool(r.get("at_top", False)), putin_in=r.get("putin_in", ""),
                         kept_why=str(r.get("kept_why", ""))[:40], line_at_putin_m=round(best[0]), line_name=q.get("n") or "unnamed", line_km2=q.get("a"),
                         lake_piece=bool(q.get("lk")), putin=f"{r.putin_lat:.5f},{r.putin_lon:.5f}"))
out = pd.DataFrame(rows)
print(out.to_string(index=False) if len(out) else "every put-in is on the way out")
