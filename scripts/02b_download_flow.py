"""Current flow evidence for all regions (replaces the retired NHD perennial/intermittent label in the score).

  nhdplus_v2.gpkg       NHDPlus V2 flowlines (COMID network the flow model is keyed to)
  natural_flows.csv     California Natural Flows Database (The Nature Conservancy): modelled unimpaired monthly
                        flow per COMID, 1950 -> last month. We keep the dry season (Jul-Oct) of recent years.
  gauges_daily.csv.gz   USGS daily discharge since 1950 at every stream gauge in the study area with 5+ years of
                        daily values (ground truth for validation), from the USGS Water Data API
  gauge_sites.gpkg      gauge locations, drainage area, and the span and count of their daily values

No REGION needed. Re-run to refresh; downloads are cached per COMID batch / site for CACHE_DAYS (REFRESH=1 forces).
"""
import os, time, json, requests, numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
from config import REGIONS, CRS, SHARED

FLOW = f"{SHARED}/flow"
os.makedirs(f"{FLOW}/nf_batches", exist_ok=True)
UA = {"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"}
FIRST_YEAR = 2011          # recent climate incl. the 2012-16 and 2020-22 droughts
DRY_MONTHS = (7, 10)       # July..October
# Natural Flows gains a month at a time and the gauges a day at a time, so a cached download is used for CACHE_DAYS and
# then fetched again (REFRESH=1 forces it now). Kept for good, the 2026 dry season stayed at July-September: October
# wasn't out yet when the batches were first downloaded.
CACHE_DAYS = 30


def fresh(path):
    return (os.path.exists(path) and os.environ.get("REFRESH") != "1"
            and time.time() - os.path.getmtime(path) < CACHE_DAYS * 86400)

area = gpd.GeoSeries([box(*v["bbox"]).buffer(2000) for v in REGIONS.values()], crs=CRS)
boxes = area.to_crs(4326).bounds.values


def get(url, headers=None, **kw):
    """GET with retries. A server over its request limit (HTTP 429) is waited out as long as it asks, 3 times at most."""
    r, waits = None, 0
    for attempt in range(5):
        try:
            r = requests.get(url, headers={**UA, **(headers or {})}, timeout=300, **kw)
            if r.ok:
                return r
            if r.status_code == 429 and waits < 3:
                s = r.headers.get("Retry-After", "")
                s = int(s) if s.isdigit() else 600
                print(f"{url.split('/')[2]} is rate limiting: waiting {s // 60 + 1} min", flush=True)
                time.sleep(s + 5)
                waits += 1
                continue
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    if r is None:
        raise requests.ConnectionError(f"no response from {url}")
    r.raise_for_status()


# ---- NHDPlus V2 flowlines ----
v2_path = f"{FLOW}/nhdplus_v2.gpkg"
v2_meta = v2_path + ".regions.json"     # the ranges the cached download covers: re-download when ranges are added
if not os.path.exists(v2_path) or not os.path.exists(v2_meta) or set(json.load(open(v2_meta))) != set(REGIONS):
    parts = []
    for w, s, e, n in boxes:
        r = get("https://api.water.usgs.gov/geoserver/wmadata/ows", params=dict(
            service="WFS", version="1.0.0", request="GetFeature", typeName="wmadata:nhdflowline_network",
            outputFormat="application/json", srsName="EPSG:4326", bbox=f"{w},{s},{e},{n},EPSG:4326",
            propertyName="comid,gnis_name,totdasqkm,fcode,ftype,streamorde,qe_ma,lengthkm,hydroseq,dnhydroseq,the_geom"))
        parts.append(gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326))
    v2 = pd.concat(parts, ignore_index=True).drop_duplicates("comid")
    v2 = gpd.GeoDataFrame(v2, crs=4326).to_crs(CRS)
    v2["geometry"] = v2.geometry.force_2d()
    v2["gnis_name"] = v2.gnis_name.str.strip().replace("", None)
    v2.to_file(v2_path + ".tmp.gpkg", driver="GPKG")
    os.replace(v2_path + ".tmp.gpkg", v2_path)
    json.dump(sorted(REGIONS), open(v2_meta, "w"))
v2 = gpd.read_file(v2_path)
print("NHDPlus V2 flowlines", len(v2))

# ---- Natural Flows (TNC) ----
comids = sorted(v2.comid.astype(int))
B = 40
files = []
for i in range(0, len(comids), B):
    chunk = comids[i:i + B]
    f = f"{FLOW}/nf_batches/{chunk[0]}_{chunk[-1]}_{len(chunk)}.csv"   # named by content, so a changed network
    files.append(f)                                                    # never reuses a batch of other COMIDs
    if fresh(f):
        continue
    r = get("https://flow-api.codefornature.org/v2/stream/", params=dict(
        comids=",".join(map(str, chunk)), statistics="mean,min", variables="estimated,p10,p90",
        begin_year=FIRST_YEAR, begin_month=DRY_MONTHS[0], end_month=DRY_MONTHS[1]))
    open(f + ".tmp", "w").write(r.text)
    os.replace(f + ".tmp", f)
    if len(files) % 25 == 0:
        print(f"natural flows: {len(files)} of {-(-len(comids) // B)} batches", flush=True)
    time.sleep(0.3)
nf = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
nf = nf[nf.month.between(*DRY_MONTHS) & (nf.year >= FIRST_YEAR)]
nf.to_csv(f"{FLOW}/natural_flows.csv.tmp", index=False)
os.replace(f"{FLOW}/natural_flows.csv.tmp", f"{FLOW}/natural_flows.csv")
print("natural flows rows", len(nf), "| comids", nf.comid.nunique(), "| years", nf.year.min(), "-", nf.year.max())

# ---- USGS gauges: every stream gauge in the area with 5+ years of daily discharge ----
# From the USGS Water Data OGC API (api.waterdata.usgs.gov), which replaces WaterServices (shut down on 2027-02-22).
# It allows a set number of requests an hour (1,000 without a key). A free key from
# https://api.waterdata.usgs.gov/signup/ in USGS_API_KEY raises that; it is sent only to this API.
WD = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
WD_KEY = {"X-Api-Key": os.environ["USGS_API_KEY"]} if os.environ.get("USGS_API_KEY") else {}


def items(coll, **params):
    """Every feature a query matches, following the "next" links (daily values come at most 50,000 to a page)."""
    js, feats = get(f"{WD}/{coll}/items", headers=WD_KEY, params=dict(f="json", **params)).json(), []
    while True:
        feats += js["features"]
        nxt = next((l["href"] for l in js.get("links", []) if l.get("rel") == "next"), None)
        if nxt is None or not js["features"]:
            return feats
        js = get(nxt, headers=WD_KEY).json()


# daily-mean discharge series (statistic 00003) in each box. A series spanning under 5 years can't have 5 years of
# values, so it's dropped before downloading; a missing begin or end keeps it.
ts = pd.DataFrame([f["properties"] for w, s, e, n in boxes for f in items(
    "time-series-metadata", bbox=f"{w:.4f},{s:.4f},{e:.4f},{n:.4f}", parameter_code="00060", statistic_id="00003",
    skipGeometry="true", limit=10000)])
span = pd.to_datetime(ts.end, utc=True) - pd.to_datetime(ts.begin, utc=True)
ids = sorted(set(ts.monitoring_location_id[~(span < pd.Timedelta(days=5 * 365 - 2))]))
# name, site type and drainage area (sq mi); 40 sites a request, since long URLs are refused
ml = [f for i in range(0, len(ids), 40) for f in items(
    "monitoring-locations", id=",".join(ids[i:i + 40]), limit=1000,
    properties="monitoring_location_name,site_type_code,drainage_area")]
gs = gpd.GeoDataFrame.from_features(ml, crs=4326)
gs["site_no"] = [f["id"].removeprefix("USGS-") for f in ml]
# streams and their canal and ditch subtypes, as WaterServices' siteType=ST gave
gs = gs[gs.site_type_code.str.startswith("ST", na=False) & gs.to_crs(CRS).intersects(area.union_all())]
gs = gs.sort_values("site_no")


def record(t):
    """One gauge's daily-mean rows as (date, cfs), sorted (they come unsorted). A gauge with two series measures two
    things (the aqueduct at the Warne powerplant: generation, and generation + bypass), so only the one with more
    days is kept, as WaterServices' first series was."""
    t = t.assign(cfs=pd.to_numeric(t.value, errors="coerce")).dropna(subset=["cfs"])
    if len(t):
        t = t[t.time_series_id == t.groupby("time_series_id").size().idxmax()]
    return t.rename(columns={"time": "date"}).sort_values("date")[["date", "cfs"]]


# whole daily-mean records, cached per site. Gauges go several to a request, as many as the spans of their series
# say fit in one page (one value a day), to keep to the hourly request limit.
est = ts.assign(days=(span.dt.days + 1).fillna(49000)).groupby("monitoring_location_id").days.sum()
batches = []
for s in gs.site_no:
    if fresh(f"{FLOW}/daily_{s}.csv"):
        continue
    d = est.get(f"USGS-{s}", 49000)
    if not batches or batches[-1][1] + d > 49000 or len(batches[-1][0]) == 40:
        batches.append(([], 0))
    batches[-1] = (batches[-1][0] + [s], batches[-1][1] + d)
for i, (b, _) in enumerate(batches, 1):
    t = pd.DataFrame([x["properties"] for x in items(
        "daily", monitoring_location_id=",".join(f"USGS-{s}" for s in b), parameter_code="00060", statistic_id="00003",
        properties="monitoring_location_id,time,value,time_series_id", skipGeometry="true", limit=50000)],
        columns=["monitoring_location_id", "time", "value", "time_series_id"])
    for s in b:
        f = f"{FLOW}/daily_{s}.csv"
        record(t[t.monitoring_location_id == f"USGS-{s}"]).to_csv(f + ".tmp", index=False)
        os.replace(f + ".tmp", f)
    if i % 10 == 0 or i == len(batches):
        print(f"gauge daily records: {i} of {len(batches)} requests", flush=True)
    time.sleep(0.3)
dv = {s: pd.read_csv(f"{FLOW}/daily_{s}.csv", parse_dates=["date"]) for s in gs.site_no}
gs["count_nu"] = [len(dv[s]) for s in gs.site_no]
gs = gs[gs.count_nu >= 5 * 365].copy()
gs["begin_date"] = [f"{dv[s].date.min():%Y-%m-%d}" for s in gs.site_no]
gs["end_date"] = [f"{dv[s].date.max():%Y-%m-%d}" for s in gs.site_no]
gs = gs.rename(columns={"monitoring_location_name": "station_nm", "drainage_area": "drain_area_va"})
gs[["site_no", "station_nm", "drain_area_va", "begin_date", "end_date", "count_nu", "geometry"]].to_file(
    f"{FLOW}/gauge_sites.gpkg")
# the daily values since 1950, when the Natural Flows model starts
dv = pd.concat([dv[s].assign(site_no=s) for s in gs.site_no], ignore_index=True)
dv = dv[dv.date >= "1950-01-01"][["site_no", "date", "cfs"]]
dv.to_csv(f"{FLOW}/gauges_daily.csv.gz", index=False)
print("gauges", gs.site_no.nunique(), "| daily rows", len(dv))
