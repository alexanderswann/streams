"""Every area's settings worked out from its outline (derive.py) against the values typed in by hand (B1 of the
new-area plan, 2026-11-23). Read-only: it writes nothing of the project's but the WBD answers it keeps in
data/raw/_national/wbd/ (00_area.py keeps the same ones).

    python derive_check.py [area ...] > derive_check.md

For each area: the UTM zone, each box's HU4 units, the states, the area-specific sources, the lake depth surveys,
the state lake lists, the states GNIS falls come from, and the typed-in lake depths and surveys (lakedata.py) that
lie in the area against those listed under its name. Hand values are what the maps use; a difference is the agenda
of B2 (sources, lake lists, surveys) or a note (zone, HU4).
"""
import os, sys
os.environ.setdefault("AREA", "la")
import geopandas as gpd, shapely
from shapely.geometry import box as sbox
import config, derive, sources, lakedata

areas = sys.argv[1:] or list(config.AREAS)
same, rows = [], []
print("| area | item | by hand | worked out |\n|---|---|---|---|")
for a in areas:
    e = config.AREAS[a]
    got = derive.settings(a, e)
    got["lake_states"] = tuple(s for s in got["states"] if s in sources.LAKE_LISTS)
    diffs = []
    if e.get("crs") != got["crs_derived"]:
        diffs.append(("zone", f"EPSG {e.get('crs')}", f"EPSG {got['crs_derived']}"))
    for k, r in e["ranges"].items():
        if set(r["hu4"]) != set(got["ranges"][k]["hu4"]):
            diffs.append((f"hu4 {k}", ", ".join(r["hu4"]), ", ".join(got["ranges"][k]["hu4"])))
    if set(e.get("sources", ())) != set(got["sources"]):
        add = sorted(set(got["sources"]) - set(e.get("sources", ())))
        gone = sorted(set(e.get("sources", ())) - set(got["sources"]))
        diffs.append(("sources", "", f"+ {', '.join(add) or 'none'}; - {', '.join(gone) or 'none'}"))
    for kind, mine in (("gnis_states", got["states"]), ("bathymetry", got["bathymetry"]), ("lake_states", got["lake_states"])):
        if set(sources.HAND[kind][a]) != set(mine):
            diffs.append((kind, ", ".join(sources.HAND[kind][a]) or "none", ", ".join(mine) or "none"))
    # typed-in lake records: by location (05d_lakes.py since B1) against by name of the map
    bx = gpd.GeoSeries([sbox(*r["bbox"]) for r in e["ranges"].values()], crs=e["crs"]).buffer(3000).union_all()
    def here(d):
        x, y = d["at"]
        return bx.contains(gpd.GeoSeries([shapely.Point(x, y)], crs=d.get("crs", 4326)).to_crs(e["crs"]).iloc[0])
    for name, table in (("lake depths", lakedata.DEPTHS), ("lake surveys", lakedata.SURVEYS)):
        keyed = [id(d) for d in table.get(a, [])]
        located = [id(d) for d in lakedata.inside(table, here)]
        if keyed != located:
            diffs.append((name, f"{len(keyed)} listed for {a}", f"{len(located)} lie in it"
                          + ("" if set(keyed) != set(located) else " (same records, another order)")))
    for item, h, w in diffs:
        print(f"| {a} | {item} | {h} | {w} |")
    if not diffs:
        same.append(a)
    sys.stdout.flush()
print(f"\nThe same in every item: {', '.join(same) or 'none'}")
