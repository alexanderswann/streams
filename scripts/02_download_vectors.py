"""Download NHD flowlines/points (USGS) and OSM roads, trails, waterfalls for the study area."""
import json, time, requests, pandas as pd, geopandas as gpd
from pyproj import Transformer
from config import *

t = Transformer.from_crs(CRS, 4326, always_xy=True)
W, S = t.transform(XMIN, YMIN)
E, N = t.transform(XMAX, YMAX)
print("bbox lon/lat", W, S, E, N)

# NHD comes from the USGS staged bulk GeoPackages (the NHD MapServer query endpoint times out).
# HU4 1807 = Southern California coastal (south slope); 1809 = Northern Mojave (north slope).
import os, zipfile, pyogrio
NHD_DIR = SHARED

def hu4_gpkg(hu):
    z = f"{NHD_DIR}/NHD_H_{hu}_HU4_GPKG.zip"
    if not os.path.exists(z):
        url = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_{hu}_HU4_GPKG.zip"
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(z, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    with zipfile.ZipFile(z) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".gpkg"))
        out = f"{NHD_DIR}/{os.path.basename(name)}"
        if not os.path.exists(out):
            with zf.open(name) as a, open(out, "wb") as b:
                b.write(a.read())
    return out

def nhd_layer(layer):
    parts = []
    for hu in HU4:
        g = hu4_gpkg(hu)
        lyr = next(l for l in pyogrio.list_layers(g)[:, 0] if l.lower() == layer.lower())
        d = gpd.read_file(g, layer=lyr, bbox=(W, S, E, N))
        d.columns = [c.lower() if c != "geometry" else c for c in d.columns]
        parts.append(d.to_crs(CRS))
    out = pd.concat(parts, ignore_index=True)
    out = out.drop_duplicates("permanent_identifier") if "permanent_identifier" in out else out
    return gpd.GeoDataFrame(out, crs=CRS)

fl = nhd_layer("NHDFlowline")[["gnis_name", "ftype", "fcode", "lengthkm", "geometry"]]
fl["geometry"] = fl.geometry.force_2d()
fl.to_file(f"{RAW}/nhd_flowlines.gpkg")
print("flowlines", len(fl), fl.fcode.value_counts().head(8).to_dict())

pts = nhd_layer("NHDPoint")[["gnis_name", "ftype", "fcode", "geometry"]]
pts["geometry"] = pts.geometry.force_2d()
pts.to_file(f"{RAW}/nhd_points.gpkg")
print("nhd points", len(pts), pts.ftype.value_counts().to_dict())

q = f"""[out:json][timeout:300];
(way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|track"]({S},{W},{N},{E});
 way["highway"~"path|footway|bridleway"]({S},{W},{N},{E});
 node["waterway"="waterfall"]({S},{W},{N},{E});
 node["natural"="waterfall"]({S},{W},{N},{E});
 node["waterway"~"dam|weir"]({S},{W},{N},{E}); way["waterway"~"dam|weir"]({S},{W},{N},{E}););
out geom;"""
for attempt in range(6):  # public Overpass servers 502/429 under load; retry and alternate mirrors
    url = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")[attempt % 2]
    try:
        r = requests.post(url, data={"data": q}, timeout=600,
                          headers={"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"})
        if r.ok:
            break
    except requests.RequestException:
        pass
    time.sleep(20 * (attempt + 1))
r.raise_for_status()
roads, trails, falls, dams = [], [], [], []
for el in r.json()["elements"]:
    tags = el.get("tags", {})
    if tags.get("waterway") in ("dam", "weir"):
        lon, lat = (el["lon"], el["lat"]) if el["type"] == "node" else (el["geometry"][0]["lon"], el["geometry"][0]["lat"])
        dams.append({"type": "Feature", "properties": {"name": tags.get("name")},
                     "geometry": {"type": "Point", "coordinates": [lon, lat]}})
        continue
    if el["type"] == "node":
        falls.append({"type": "Feature", "properties": {"name": tags.get("name")},
                      "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]}})
        continue
    hw = tags.get("highway", "")
    f = {"type": "Feature", "properties": {"highway": hw, "name": tags.get("name"),
         "access": tags.get("access"), "motor_vehicle": tags.get("motor_vehicle")},
         "geometry": {"type": "LineString", "coordinates": [[g["lon"], g["lat"]] for g in el["geometry"]]}}
    (trails if hw in ("path", "footway", "bridleway") else roads).append(f)
for name, feats in [("osm_roads", roads), ("osm_trails", trails), ("osm_waterfalls", falls), ("osm_dams", dams)]:
    g = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(CRS)
    g.to_file(f"{RAW}/{name}.gpkg")
    print(name, len(g))
