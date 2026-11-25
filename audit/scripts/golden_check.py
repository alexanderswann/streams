#!/usr/bin/env python3
"""The golden places: problems that were fixed, checked again on every build (the new-area plan's B14, 2026-11-23).

audit/golden_places.csv has one row per fixed problem: the map, where (a point on the reach and the reach's name), what
was wrong, what must hold now, and the value frozen from the published fix with its tolerance. This script reads the
drawn map (<maps folder>/<area>/map3d_data.js, as published) at each row and says, for each, holds / BROKEN / not
found. audit/scripts/run_all.sh runs it and puts the broken rows in run_all_status.json, and the publish gate
(scripts/build_stamp.py) refuses a map with a broken row. The rule from 2026-11-23: every fix adds its row in the same
commit, frozen from the build that publishes it.

    python audit/scripts/golden_check.py [area ...]                 every row (of those areas), on SITE_DIR's maps
    python audit/scripts/golden_check.py --freeze [area ...]        the values the maps show now, to freeze a row
    python audit/scripts/golden_check.py --find <area> <regex> [lon lat]   reaches whose name or drainage matches
Writes <AUDIT_TABLES>/golden_check.json and .csv (one line a row). Exit status 1 when a row broke or was not found.

Row columns:
  id, area     a short name; the map
  lon, lat     a point on the reach: the drawn line nearest to it within near_m (default 150 m) whose name (or, when
               it has none, its drainage) matches `name` (a regex; empty: any line)
  check        what is measured there:
                 drawn         a line is drawn there                                   (value 1)
                 area_sqmi     the reach's drainage, square miles                      (value, tol: relative)
                 flow_min      the summer class is at least the value: year-round > usually flows > seasonal > mostly dry
                 name_is       the reach's name matches the value (a regex)
                 drainage_is   the drainage it is drawn in matches the value (a regex)
                 text_has      field=regex present in the popup's field (n d k fl dq acc sun ht burn tr flags)
                 text_lacks    field=regex absent
                 fish_min      every reach matching `name` within near_m scores at least the value
                 area_max_sqmi no reach matching `name` within near_m drains more than the value (square miles)
                 cfs_min       the nearest one's typical July-October low flow is at least the value (cfs)
                 layer_lacks   regex absent from every property of every feature of a layer: layer=regex (value)
  value, tol   the frozen value; tol for numbers (0.10 = 10 %)
  was, must    what was wrong; what must hold now
  since        the change that fixed it
"""
import csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *          # SITE_DIR, TABLES, epsg, load_map, NAMES

ROWS = os.environ.get("GOLDEN_ROWS", f"{ROOT}/audit/golden_places.csv")
SQMI = 2.58999
CLASS = {"year-round": 4, "usually flows": 3, "seasonal": 2, "mostly dry": 1}
FIELDS = ("n", "d", "k", "fl", "dq", "acc", "sun", "ht", "burn", "tr", "flags")


def lines(area):
    """The drawn stream lines (both layers) as a GeoDataFrame in the area's UTM zone, with their popup fields."""
    import geopandas as gpd, shapely
    d = load_map(area)
    feats = d["streams"]["features"] + d.get("streams_lake", {}).get("features", [])
    props = [f["properties"] for f in feats]
    geoms = [shapely.geometry.shape(f["geometry"]) for f in feats]
    g = gpd.GeoDataFrame(props, geometry=geoms, crs=4326).to_crs(epsg(area))
    g["label"] = [p.get("n") or p.get("d") or "" for p in props]
    return g, d


def _point(area, lon, lat):
    import geopandas as gpd, shapely
    return gpd.GeoSeries([shapely.Point(float(lon), float(lat))], crs=4326).to_crs(epsg(area)).iloc[0]


def near(g, area, row):
    """The lines within near_m of the row's point whose label matches its name, nearest first."""
    p = _point(area, row["lon"], row["lat"])
    r = float(row.get("near_m") or 150)
    idx = g.sindex.query(p.buffer(r), predicate="intersects")
    c = g.iloc[idx]
    if row.get("name"):
        c = c[c.label.str.contains(row["name"], case=False, regex=True, na=False)]
    return c.assign(dist=c.distance(p)).sort_values("dist")


def measure(g, d, area, row):
    """(the value the map shows, the line found or None)."""
    chk = row["check"]
    if chk == "layer_lacks":
        layer, rx = row["value"].split("=", 1)
        hits = [f["properties"] for f in d.get(layer, {}).get("features", [])
                if any(isinstance(v, str) and re.search(rx, v) for v in f["properties"].values())]
        return len(hits), None
    c = near(g, area, row)
    if not len(c):
        return None, None
    top = c.iloc[0]
    if chk == "drawn":
        return 1, top
    if chk == "area_sqmi":
        return round(float(top["a"]) / SQMI, 2), top
    if chk == "flow_min":
        fl = str(top.get("fl") or "")
        return (fl[8:] if fl.startswith("summer: ") else fl), top
    if chk == "name_is":
        return top.get("n") or "", top
    if chk == "drainage_is":
        return top.get("d") or "", top
    if chk in ("text_has", "text_lacks"):
        field = row["value"].split("=", 1)[0]
        return str(top.get(field) or ""), top
    if chk == "fish_min":
        return int(c["fs"].min()), top
    if chk == "area_max_sqmi":
        return round(float(c["a"].astype(float).max()) / SQMI, 2), top
    if chk == "cfs_min":
        m = re.search(r"low flow about ([\d.,]+) cfs in a typical", str(top.get("dq") or ""))
        return (float(m.group(1).replace(",", "")) if m else -1.0), top
    raise SystemExit(f"row {row['id']}: unknown check {chk}")


def holds(row, got):
    chk, v = row["check"], row["value"]
    if got is None:
        return False
    if chk == "drawn":
        return got == 1
    if chk == "area_sqmi":
        return abs(got - float(v)) <= float(row.get("tol") or 0.05) * float(v)
    if chk == "flow_min":
        return CLASS.get(got, 0) >= CLASS[v]
    if chk in ("name_is", "drainage_is"):
        return bool(re.search(v, got))
    if chk == "text_has":
        return bool(re.search(v.split("=", 1)[1], got))
    if chk == "text_lacks":
        return not re.search(v.split("=", 1)[1], got)
    if chk in ("fish_min", "cfs_min"):
        return got >= float(v)
    if chk == "area_max_sqmi":
        return got <= float(v)
    if chk == "layer_lacks":
        return got == 0
    return False


def read_rows(areas):
    with open(ROWS, newline="") as f:
        return [r for r in csv.DictReader(f, skipinitialspace=True)
                if not r["id"].startswith("#") and (not areas or r["area"] in areas)]


def main(args):
    if args[:1] == ["--find"]:
        area, rx = args[1], args[2]
        g, _ = lines(area)
        c = g[g.label.str.contains(rx, case=False, regex=True, na=False) |
              g.d.astype(str).str.contains(rx, case=False, regex=True, na=False)]
        if len(args) >= 5:
            c = c.assign(dist=c.distance(_point(area, args[3], args[4]))).sort_values("dist")
        for _, t in c.head(40).iterrows():
            print(f"{t.get('n')!s:32.32} | {t.get('d')!s:24.24} | {float(t['a']) / SQMI:8.2f} sq mi | {t.get('fl')!s:22.22} "
                  f"| fish {t.get('fs')} | {t['y']}, {t['x']}" + (f" | {t['dist']:.0f} m" if "dist" in c else ""))
        return 0
    freeze = args[:1] == ["--freeze"]
    areas = [a for a in args if not a.startswith("--")]
    rows = read_rows(areas)
    out, bad = [], 0
    for area in sorted({r["area"] for r in rows}, key=lambda a: NAMES.index(a) if a in NAMES else 99):
        if not os.path.exists(f"{SITE_DIR}/{area}/map3d_data.js"):
            for r in (r for r in rows if r["area"] == area):
                out.append(dict(row=r["id"], area=area, status="no map", got=None))
            continue
        g, d = lines(area)
        for r in (r for r in rows if r["area"] == area):
            got, top = measure(g, d, area, r)
            st = "not found" if got is None else ("holds" if holds(r, got) else "broken")
            where = (f"{top['y']}, {top['x']} {top.get('n') or top.get('d')}" if top is not None else "")
            out.append(dict(row=r["id"], area=area, check=r["check"], expected=r["value"], got=got, status=st, at=where))
            if freeze:
                print(f"{r['id']},{area},{r['check']}: shows {got!r} at {where}")
            else:
                print(f"{st.upper() if st != 'holds' else 'holds':9s} {r['id']:28s} {area:15s} {r['check']:11s} "
                      f"expected {r['value']!s:18.18} got {got!s:18.18} {where}")
            bad += st != "holds"
        del g, d
    if not freeze:
        os.makedirs(TABLES, exist_ok=True)
        with open(f"{TABLES}/golden_check.json", "w") as f:
            json.dump(dict(maps=SITE_DIR, rows=out), f, indent=1, default=str)
        with open(f"{TABLES}/golden_check.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["row", "area", "check", "expected", "got", "status", "at"])
            w.writeheader()
            w.writerows(out)
        print(f"golden places: {len(out) - bad} of {len(out)} hold" + (f"; {bad} broken or not found" if bad else ""))
    return 1 if bad and not freeze else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
