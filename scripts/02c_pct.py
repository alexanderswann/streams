"""The area's long-distance trail for the maps (config.py `long_trail`: the Pacific Crest Trail in LA, the
Appalachian Trail in North Georgia and at Lexington, the Long Trail in Vermont): the ways of its OSM hiking route
relations (LA: ref=PCT, named like "PCT - California Section D"), clipped to a box around all study areas with room
to spare, so the trail runs off the edge of the map rather than stopping short. No REGION needed.

Writes data/raw/<area>/_shared/pct.gpkg (the name is from when there was only the PCT): one line per OSM way, with
the section relation it belongs to."""
import time, requests, geopandas as gpd, shapely
from config import REGIONS, CRS, SHARED, LONG_TRAIL, AREA
if not LONG_TRAIL:
    raise SystemExit(f"{AREA}: no long-distance trail listed in config.py; nothing to do")
NAME, REF, NAME_RE = LONG_TRAIL

PAD_M = 60000
area = gpd.GeoSeries([shapely.box(*v["bbox"]) for v in REGIONS.values()], crs=CRS).union_all().envelope.buffer(PAD_M)
W, S, E, N = gpd.GeoSeries([area], crs=CRS).to_crs(4326).total_bounds

q = f"""[out:json][timeout:300];
(relation["route"="hiking"]["ref"="{REF}"]({S},{W},{N},{E});
 relation["route"="hiking"]["name"~"{NAME_RE}",i]({S},{W},{N},{E}););
rel._["route"="hiking"]->.r;
.r out body;
way(r.r)({S},{W},{N},{E});
out geom;"""
for attempt in range(6):  # public Overpass servers 502/429 under load; retry and alternate mirrors
    url = ("https://overpass.openstreetmap.fr/api/interpreter", "https://overpass-api.de/api/interpreter")[attempt % 2]   # (the kumi mirror stopped answering in Nov 2026)
    try:
        r = requests.post(url, data={"data": q}, timeout=(20, 600),
                          headers={"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"})
        if r.ok:
            break
    except requests.RequestException:
        pass
    time.sleep(20 * (attempt + 1))
r.raise_for_status()
els = r.json()["elements"]

rels = [e for e in els if e["type"] == "relation"]
section = {}
for rel in rels:   # section relations list their ways; the PCT super-relation lists the sections
    for m in rel.get("members", []):
        if m["type"] == "way":
            section.setdefault(m["ref"], rel["tags"].get("name", NAME))
feats = [{"type": "Feature", "properties": {"osm_id": e["id"], "section": section.get(e["id"]),
                                            "name": e.get("tags", {}).get("name")},
          "geometry": {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in e["geometry"]]}}
         for e in els if e["type"] == "way" and len(e.get("geometry", [])) >= 2]
pct = gpd.GeoDataFrame.from_features(feats, crs=4326)
# only the trail itself: a side trail that carries its ref (the Arkaquah Trail is tagged ref=AT) is left out
import re
pct = pct[[bool(re.search(NAME_RE, str(s_), re.I)) or s_ is None for s_ in pct.section]]
pct.to_file(f"{SHARED}/pct.gpkg")
print("relations:", sorted({(x["tags"].get("name"), x["tags"].get("ref")) for x in rels}, key=str))
print("ways", len(pct), "| km", round(pct.to_crs(CRS).length.sum() / 1000, 1))
print(pct.groupby("section", dropna=False).size().to_string())
