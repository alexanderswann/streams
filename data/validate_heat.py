"""How well can anything predict summer water temperature here, and is the heat gate (scoring.py) safe?

Truth: July-August water temperature readings at stream sites in the study areas from the Water Quality Portal
(USGS, Forest Service, EPA, and the Morongo, Soboba and Agua Caliente tribes), as the median per site.
Compared, by leave-one-out RMSE of a linear fit to the readings:
  (a) PRISM August mean air temperature (1991-2020 normal, the heat gate's input; clipped by 11_context.py)
  (b) NorWeST modelled August mean stream temperature (USFS, 1993-2011 scenario)
  (c) EPA StreamCat predicted July-August stream temperature (Hill et al. 2013, mean of 2008/09/13/14)
Then: the hottest creek with a trout record against the gate's start, and the readings inside the gated zone.
Downloads are cached for 30 days in data/raw/<area>/_shared/cache/.
Run from scripts/:  ../.venv/bin/python ../data/validate_heat.py
"""
import sys, os, io, time, requests, rasterio, numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from config import REGIONS, CRS, EPSG, SHARED, NATIONAL, MAP_OUT
from scoring import HEAT_START, HEAT_FULL

CACHE = f"{SHARED}/cache"
os.makedirs(CACHE, exist_ok=True)
area = gpd.GeoSeries([box(*v["bbox"]).buffer(3000) for v in REGIONS.values()], crs=CRS)
W, S, E, N = area.to_crs(4326).total_bounds


def cached(name, fetch):
    p = f"{CACHE}/{name}"
    if not (os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400):
        fetch(p + ".tmp")
        os.replace(p + ".tmp", p)
    return p


def wqp(kind):
    def fetch(p):
        r = requests.get(f"https://www.waterqualitydata.us/data/{kind}/search", timeout=600, params=dict(
            bBox=f"{W:.3f},{S:.3f},{E:.3f},{N:.3f}", characteristicName="Temperature, water", siteType="Stream",
            startDateLo="01-01-1995", mimeType="csv", **({"dataProfile": "narrowResult"} if kind == "Result" else {})))
        r.raise_for_status()
        open(p, "wb").write(r.content)
    return pd.read_csv(cached(f"wqp_{kind.lower()}_temp.csv", fetch), low_memory=False)


def norwest(p):
    url = "https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_NorWeST_StreamTemperatures_01/MapServer/2/query"
    feats = []
    for b in area.to_crs(4326).bounds.itertuples():
        off = 0
        while True:
            js = requests.get(url, timeout=300, params=dict(
                where="1=1", geometry=f"{b.minx},{b.miny},{b.maxx},{b.maxy}", geometryType="esriGeometryEnvelope",
                inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="s1_93_11,comid", outSR=EPSG,
                f="geojson", resultOffset=off, resultRecordCount=2000, orderByFields="objectid")).json()
            feats += js["features"]
            if len(js["features"]) < 2000:
                break
            off += 2000
    gpd.GeoDataFrame.from_features(feats, crs=CRS).to_file(p, driver="GPKG")


def streamcat(p):
    ids = sorted(gpd.read_file(f"{SHARED}/flow/nhdplus_v2.gpkg", ignore_geometry=True).comid.astype(int).unique())
    rows = []
    for i in range(0, len(ids), 400):
        rows += requests.post("https://api.epa.gov/StreamCat/streams/metrics", timeout=300, data=dict(
            name="msst2008,msst2009,msst2013,msst2014", aoi="other", comid=",".join(map(str, ids[i:i + 400])))).json()["items"]
    pd.DataFrame(rows).to_csv(p, index=False)


# ---- measured July-August water temperature per site ----
res, st = wqp("Result"), wqp("Station").set_index("MonitoringLocationIdentifier")
res["v"] = pd.to_numeric(res.ResultMeasureValue, errors="coerce")
res.loc[res["ResultMeasure/MeasureUnitCode"] == "deg F", "v"] = (res.v - 32) * 5 / 9
res["date"] = pd.to_datetime(res.ActivityStartDate, errors="coerce")
res["hour"] = pd.to_numeric(res["ActivityStartTime/Time"].astype(str).str[:2], errors="coerce")
res = res[res.v.between(0, 40)].join(st[["MonitoringLocationName", "LatitudeMeasure", "LongitudeMeasure"]],
                                     on="MonitoringLocationIdentifier")
res["key"] = res.LatitudeMeasure.round(3).astype(str) + "," + res.LongitudeMeasure.round(3).astype(str)  # co-located ids
summer = res[res.date.dt.month.isin([7, 8]) & (res.hour.between(7, 18) | res.hour.isna())]
site = summer.groupby("key").agg(w=("v", "median"), n=("v", "size"), name=("MonitoringLocationName", "first"),
                                 lat=("LatitudeMeasure", "first"), lon=("LongitudeMeasure", "first"))
pts = gpd.GeoDataFrame(site, geometry=gpd.points_from_xy(site.lon, site.lat), crs=4326).to_crs(CRS)
pts = pts[pts.intersects(area.union_all())]


def air_at(g):
    with rasterio.open(f"{NATIONAL}/prism_tmean_aug.tif") as src:
        ll = g.to_crs(src.crs)
        v = np.array([x[0] for x in src.sample(zip(ll.geometry.x, ll.geometry.y))], float)
    return np.where(v < -100, np.nan, v)


pts["air"] = air_at(pts)
nw = gpd.read_file(cached("norwest.gpkg", norwest))
pts["nw"] = gpd.sjoin_nearest(pts[["geometry"]], nw, max_distance=300, how="left").groupby(level=0).s1_93_11.first()
sc = pd.read_csv(cached("streamcat_temp.csv", streamcat))
sc["msst"] = sc.filter(like="msst").mean(axis=1)
v2 = gpd.read_file(f"{SHARED}/flow/nhdplus_v2.gpkg").merge(sc[["comid", "msst"]], on="comid", how="left")
v2 = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"])]
pts["sc"] = gpd.sjoin_nearest(pts[["geometry"]], v2[["msst", "geometry"]], max_distance=300, how="left").groupby(level=0).msst.first()


def loo_rmse(x, y):
    X = np.c_[np.ones(len(x)), x]
    err = [y[i] - X[i] @ np.linalg.lstsq(np.delete(X, i, 0), np.delete(y, i), rcond=None)[0] for i in range(len(y))]
    return np.sqrt(np.mean(np.square(err)))


print(f"sites with July-August readings: {len(pts)}")
for col, label in (("air", "PRISM August air"), ("nw", "NorWeST August mean"), ("sc", "StreamCat Jul-Aug mean")):
    d = pts[[col, "w"]].dropna()
    print(f"  {label:24s} n={len(d):3d}  LOO RMSE {loo_rmse(d[col].values, d.w.values):.2f} C  (sd of readings {d.w.std():.2f})")

# ---- the gate against the trout records and the readings ----
tev = gpd.read_file(f"{MAP_OUT}/context/trout_evidence.gpkg")
creek = tev[tev.trout.astype(bool) & ~tev.lake.astype(bool)]
print(f"\ncreek trout records: {len(creek)}; hottest August air {creek.air_aug.max():.1f} C; above the gate's start "
      f"({HEAT_START} C): {int((creek.air_aug > HEAT_START).sum())}")
print(creek.nlargest(5, "air_aug")[["kind", "air_aug", "label"]].to_string(index=False))
allp = res.drop_duplicates("key").copy()
allp = gpd.GeoDataFrame(allp, geometry=gpd.points_from_xy(allp.LongitudeMeasure, allp.LatitudeMeasure), crs=4326)
allp["air"] = air_at(allp)
hotkeys = set(allp[allp.air > HEAT_START].key)
inz = res[res.key.isin(hotkeys) & res.date.dt.month.between(3, 9)].merge(allp[["key", "air"]], on="key")
print(f"\nMarch-September readings at sites inside the gate (August air > {HEAT_START} C; full penalty at {HEAT_FULL} C):")
print(inz.sort_values(["air", "date"])[["MonitoringLocationName", "air", "date", "ActivityStartTime/Time", "v"]]
      .assign(date=lambda d: d.date.dt.date, v=lambda d: d.v.round(1), air=lambda d: d.air.round(1))
      .to_string(index=False, header=["site", "air C", "date", "time", "water C"]))
