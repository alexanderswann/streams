#!/usr/bin/env python3
"""Downloads for completeness.py that the pipeline does not make: reference copies in audit/reference/<area>/.
Network only; nothing in data/ or output/ is touched. A copy is written only when every request for it succeeded
(a timed-out or partial answer is never kept); an old copy stays until a complete new one replaces it.

  osm_swim.json        OSM swimming spots, named or not: leisure=swimming_area / bathing_place, sport=swimming (not
                       pools, gyms or water parks), water=stream_pool, natural=water + swimming=yes
  osm_waterways.gpkg   OSM waterway=river / stream lines, named or not, with their NHD import tags (an OSM line imported
                       from NHD is not an independent witness; the table says how much of OSM that is)
  3dhp_status.json     USGS 3DHP: how many elevation-derived (EDH) work units cover the map. 3DHP lines that came over
                       from NHD (workunitid 'NHD') say nothing NHD doesn't; 3dhp_flowlines.gpkg is fetched only where
                       EDH work units exist.
    python audit/scripts/completeness_fetch.py [--only swim|waterways|3dhp] [area ...]
"""
import sys, os, json, time, requests, numpy as np, geopandas as gpd, shapely, pyproj
sys.path.insert(0, os.path.dirname(__file__))
from common import AREAS, NAMES, ROOT, boxes, epsg

REF = f"{ROOT}/audit/reference"
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
MIRRORS = ("https://overpass-api.de/api/interpreter", "https://overpass.openstreetmap.fr/api/interpreter")
HYDRO = "https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/MapServer"


def lonlat_box(area, pad=0.01):
    t = pyproj.Transformer.from_crs(epsg(area), 4326, always_xy=True)
    xs, ys = [], []
    for b in boxes(area).values():
        x0, y0, x1, y1 = b["bbox"]
        for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            lo, la = t.transform(x, y)
            xs.append(lo)
            ys.append(la)
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def overpass(q, tries=8):
    for i in range(tries):
        try:
            r = requests.post(MIRRORS[i % 2], data={"data": q}, timeout=(20, 400), headers=UA)
            if r.ok:
                j = r.json()
                if "elements" in j and not j.get("remark", "").lower().startswith(("runtime error", "runtime remark: timeout")):
                    return j["elements"]
        except (requests.RequestException, ValueError):
            pass
        time.sleep(min(20 * (i + 1), 120))
    raise RuntimeError("Overpass: no complete answer")


def tiles(area, step):
    w, s, e, n = lonlat_box(area)
    nx, ny = max(1, int(np.ceil((e - w) / step))), max(1, int(np.ceil((n - s) / step)))
    for i in range(nx):
        for j in range(ny):
            yield (s + (n - s) * j / ny, w + (e - w) * i / nx, s + (n - s) * (j + 1) / ny, w + (e - w) * (i + 1) / nx)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


def swim(area):
    els = {}
    for s, w, n, e in tiles(area, 0.5):
        bb = f"({s:.5f},{w:.5f},{n:.5f},{e:.5f})"
        q = f"""[out:json][timeout:300];
(nwr["leisure"~"^(swimming_area|bathing_place)$"]{bb};
 nwr["sport"="swimming"]["leisure"!~"^(sports_centre|swimming_pool|fitness_centre|sports_hall|water_park|pitch)$"]["amenity"!="swimming_pool"]{bb};
 nwr["water"="stream_pool"]{bb}; nwr["natural"="water"]["swimming"="yes"]{bb}; nwr["swimming"="yes"]["natural"!="water"]["leisure"!="swimming_pool"]{bb};);
out tags center;"""
        for el in overpass(q):
            els[(el["type"], el["id"])] = el
    save_json(f"{REF}/{area}/osm_swim.json", list(els.values()))
    return len(els)


def waterways(area):
    feats = {}
    for s, w, n, e in tiles(area, 0.25):
        q = f'[out:json][timeout:300];way["waterway"~"^(river|stream)$"]({s:.5f},{w:.5f},{n:.5f},{e:.5f});out tags geom;'
        for el in overpass(q):
            g = el.get("geometry") or []
            if len(g) >= 2:
                feats[el["id"]] = el
    t = [f.get("tags", {}) for f in feats.values()]
    g = gpd.GeoDataFrame(
        {"osm_id": list(feats), "name": [x.get("name") for x in t], "waterway": [x.get("waterway") for x in t],
         "intermittent": [x.get("intermittent") for x in t],
         "nhd_import": [any(k.lower().startswith(("nhd:", "nhd_", "nhdplus")) for k in x) for x in t]},
        geometry=[shapely.LineString([(p["lon"], p["lat"]) for p in f["geometry"]]) for f in feats.values()], crs=4326)
    os.makedirs(f"{REF}/{area}", exist_ok=True)
    p = f"{REF}/{area}/osm_waterways.gpkg"
    g.to_file(p + ".tmp.gpkg", driver="GPKG")
    os.replace(p + ".tmp.gpkg", p)
    return len(g), int(g.nhd_import.sum())


def dhp(area):
    w, s, e, n = lonlat_box(area)
    out = {}
    for lyr, key in ((92, "edh_workunits"), (94, "elevation_workunits")):
        r = requests.get(f"{HYDRO}/{lyr}/query", params=dict(where="1=1", geometry=f"{w},{s},{e},{n}", geometryType="esriGeometryEnvelope",
                         inSR=4326, spatialRel="esriSpatialRelIntersects", returnCountOnly="true", f="json"), headers=UA, timeout=90)
        r.raise_for_status()
        out[key] = r.json()["count"]
    out["checked"] = time.strftime("%Y-%m-%d")
    save_json(f"{REF}/{area}/3dhp_status.json", out)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    only = None
    if args[:1] == ["--only"]:
        only, args = args[1], args[2:]
    # every map's lon/lat box, for completeness_overture.py (which runs where duckdb is, without the project's libraries)
    save_json(f"{REF}/area_bbox.json", {a: lonlat_box(a, 0.0) for a in NAMES})
    if only == "bbox":
        raise SystemExit(0)
    for a in args or NAMES:
        for name, fn in (("swim", swim), ("3dhp", dhp), ("waterways", waterways)):
            if only and only != name:
                continue
            t0 = time.time()
            try:
                print(f"{a} {name}: {fn(a)} ({time.time() - t0:.0f} s)", flush=True)
            except Exception as ex:          # noqa: BLE001  (keep the old copy, go on with the next)
                print(f"{a} {name}: FAILED ({str(ex)[:120]}); old copy kept", flush=True)
