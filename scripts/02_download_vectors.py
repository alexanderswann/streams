"""Download NHD flowlines/points (USGS) and OSM roads, trails, waterfalls for the study area."""
import json, re, time, requests, shapely, pandas as pd, geopandas as gpd
from config import *
from geomatch import overpass

# The lon/lat box around the whole UTM box. The UTM grid is turned against lon/lat (1.4 degrees in the Sespe range), so
# a box from just the south-west and north-east corners left slivers along the edges with no NHD or OSM data: up to
# 1.5 km wide, 1,370 NHD flowlines in all (parts of Pole, Redrock, Agua Blanca, Tar and Piru creeks)
W, S, E, N = gpd.GeoSeries([shapely.box(XMIN, YMIN, XMAX, YMAX).segmentize(1000)], crs=CRS).to_crs(4326).total_bounds
print("bbox lon/lat", W, S, E, N)

# NHD comes from the USGS staged bulk GeoPackages (the NHD MapServer query endpoint times out).
# HU4 1807 = Southern California coastal (south slope); 1809 = Northern Mojave (north slope).
import os, zipfile, pyogrio
NHD_DIR = NATIONAL   # HU4 GeoPackages are reused by every area

def hu4_gpkg(hu):
    z = f"{NHD_DIR}/NHD_H_{hu}_HU4_GPKG.zip"
    if not os.path.exists(z):
        url = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_{hu}_HU4_GPKG.zip"
        import netfetch
        with netfetch.get(url, stream=True, timeout=600) as r:
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
(way["highway"~"^((motorway|trunk|primary|secondary|tertiary)(_link)?|unclassified|residential|service|track)$"]({S},{W},{N},{E});
 way["highway"~"^(path|footway|bridleway)$"]({S},{W},{N},{E});
 node["waterway"="waterfall"]({S},{W},{N},{E});
 node["natural"="waterfall"]({S},{W},{N},{E});
 node["waterway"~"dam|weir"]({S},{W},{N},{E}); way["waterway"~"dam|weir"]({S},{W},{N},{E}););
out geom;"""
# The public Overpass servers are sometimes down for hours. A range that already has its OSM files keeps them then
# (they are a day to a few weeks old; run this again later to refresh them); OSM=keep skips the download outright.
osm_files = ["osm_roads", "osm_trails", "osm_waterfalls", "osm_dams"]
have = all(os.path.exists(f"{RAW}/{n}.gpkg") for n in osm_files)
if os.environ.get("OSM") == "keep" and have:
    print("OSM=keep: this range's OSM roads, trails, waterfalls and dams stay as last downloaded")
    raise SystemExit(0)
try:
    elements = overpass(q)   # retries and alternates mirrors
except RuntimeError:
    if not have:
        raise
    print("NOTE: Overpass can't be reached. This range's OSM roads, trails, waterfalls and dams stay as last "
          "downloaded; run 02_download_vectors.py again later to refresh them.")
    raise SystemExit(0)
roads, trails, falls, dams = [], [], [], []
for el in elements:
    tags = el.get("tags", {})
    # any value the query's dam|weir matches (also "check_dam", "dam;weir"): those used to fall through to the roads
    if re.search("dam|weir", tags.get("waterway", "")):
        lon, lat = (el["lon"], el["lat"]) if el["type"] == "node" else (el["geometry"][0]["lon"], el["geometry"][0]["lat"])
        dams.append({"type": "Feature", "properties": {"name": tags.get("name")},
                     "geometry": {"type": "Point", "coordinates": [lon, lat]}})
        continue
    if el["type"] == "node":
        falls.append({"type": "Feature", "properties": {"name": tags.get("name")},
                      "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]}})
        continue
    hw = tags.get("highway", "")
    if not hw or len(el.get("geometry") or []) < 2:
        continue
    f = {"type": "Feature", "properties": {"highway": hw, "name": tags.get("name"),
         "access": tags.get("access"), "motor_vehicle": tags.get("motor_vehicle")},
         "geometry": {"type": "LineString", "coordinates": [[g["lon"], g["lat"]] for g in el["geometry"]]}}
    (trails if hw in ("path", "footway", "bridleway") else roads).append(f)
for name, feats in [("osm_roads", roads), ("osm_trails", trails), ("osm_waterfalls", falls), ("osm_dams", dams)]:
    g = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(CRS)
    g.to_file(f"{RAW}/{name}.gpkg")
    print(name, len(g))
