"""Context layers for all study areas, plus per-reach / per-drop attributes:
  - Fire perimeters since FIRE_SINCE (burn scars degrade trout habitat for years): CAL FIRE's historic perimeters
    (published once a year), this year's interagency perimeters (WFIGS), and for a fire in neither the outline of its
    Forest Service BAER soil burn severity map
  - Soil burn severity (BAER) of a reach's latest fire, and the USGS post-fire debris-flow hazard below recent burns
  - USFS tree canopy cover (NLCD TCC, latest year, so it reflects recent fires) along each reach: riparian shade
  - USGS real-time streamflow gauges vs. the daily percentiles for today's date (USGS Water Data APIs), plus CDEC's
    two Piru Creek gauges (above Pyramid Lake, and the dam's release to lower Piru Creek)
  - Trout evidence: CDFW Heritage & Wild Trout Program surveys (trout found or not), CDFW trout stocking in the last
    12 months, and iNaturalist research-grade rainbow / brown trout sightings with an exact location
  - Springs and seeps (NHD)
  - August mean air temperature along each reach (PRISM 1991-2020 normal, 800 m) for the desert heat gate in
    scoring.py, and at each trout record (the gate starts above the hottest one)
  - Land status: USFS wilderness (no bikes), non-Forest-Service land inside the forests (private inholdings),
    CPAD (California Protected Areas Database) holdings with restricted or no public access
  - Critical habitat for stream species (USFWS) and southern steelhead (NMFS), clipped to the study areas.
    Designated habitat, not closure boundaries: Forest Service closures are usually smaller
  - CDFW Heritage and Wild Trout Waters (special regulations, strong sign of wild trout)
  - Wild brook trout water (outside California, troutdata.py's wild_brook): brook_water, a designation of wild brook
    trout covering the reach (any of them, where trout_water names only the first), and brook_found, the latest year a
    survey found wild brook trout on the creek. scoring.py sizes that water for brook trout
Writes output/context/*.gpkg and output/<region>/context_streams.csv, context_drops.csv.
A download that fails (no network, a server that doesn't answer) is read from its last good copy (netfetch.py), with a
dated NOTE in the log and "(as of <date>)" in the source wording the map shows: the fire perimeters' source, the trout
records' labels, the trout waters' designation, critical habitat's unit, the land layers' unit or owner, the debris-flow
hazard. The gauges' readings carry their own times. Only a source with no copy at all stops the step.
"""
import os, re, glob, time, difflib, urllib.request, datetime as dt, requests, shapely, rasterio, numpy as np, pandas as pd, geopandas as gpd
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from scipy.ndimage import uniform_filter
from shapely.geometry import box
from config import REGIONS, CRS, EPSG, MAP_OUT, SHARED, NATIONAL, ROOT, raw_dir, has
from scoring import HEAT_START
from geomatch import wilderness_path
import troutdata
import netfetch     # every download: timeouts, a breaker, and the last good copy when one fails (2026-11-22)

FIRE_SINCE = 2016
# USFWS critical habitat kept as "stream species": LA's by name; elsewhere any fish, mussel or stream amphibian
AQUATIC = ["Arroyo (=arroyo southwestern) toad", "Santa Ana sucker", "Mountain yellow-legged frog",
           "California red-legged frog", "tidewater goby"]
AQUATIC_RE = (r"(?i)\b(trout|salmon|sturgeon|darter|shiner|chub|dace|sucker|madtom|logperch|minnow|sculpin|"
              r"mussel|pearlymussel|pigtoe|mucket|elktoe|kidneyshell|rabbitsfoot|combshell|riffleshell|bean|"
              r"hellbender|waterdog|crayfish|frog|toad)\b")
CTX = f"{MAP_OUT}/context"
os.makedirs(CTX, exist_ok=True)
UA = {"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"}

area = gpd.GeoSeries([box(*v["bbox"]).buffer(3000) for v in REGIONS.values()], crs=CRS)
area_u = area.union_all()
W, S, E, N = area.to_crs(4326).total_bounds

ESRI_BUDGET = 20 * 60      # s for one layer, all its pages and tries: then its last good copy


def esri(url, where="1=1", fields="*", page=1000, what=None):
    """Every feature of an ArcGIS layer in the study area. A server that can't answer a full page (the Forest
    Service ownership layer over the Chattahoochee: a thousand detailed parcels at once) is asked for smaller ones,
    and for bigger ones again after each page it answers: after a network drop on 2026-11-22 LA's CPAD went on one
    feature at a time. A layer that can't be read (12 tries of a page, ESRI_BUDGET s, or the host out: netfetch.py)
    is its last good copy, `what` in the log and in netfetch.asof()."""
    what = what or re.sub(r".*/services/|/(?:Feature|Map)Server", "", url)
    def fetch():
        feats, off, size, t0 = [], 0, page, time.time()
        while True:
            js, served = None, 0                    # failures in a row where the server was reached
            for attempt in range(12):
                try:
                    r = netfetch.get(f"{url}/query", headers=UA, timeout=300, params=dict(
                        where=where, geometry=f"{W},{S},{E},{N}", geometryType="esriGeometryEnvelope", inSR=4326,
                        spatialRel="esriSpatialRelIntersects", outFields=fields, outSR=EPSG, f="geojson",
                        resultOffset=off, resultRecordCount=size))
                    if r.ok and "features" in r.json():
                        js = r.json()
                        break
                    served += 1
                except requests.ConnectionError:    # no connection (a drop): says nothing about the page's size
                    served = 0
                except (requests.RequestException, ValueError):
                    served += 1
                if time.time() - t0 > ESRI_BUDGET:
                    break
                if served >= 2 and size > 1:        # two failures at this size: a quarter of the page, down to one
                    size = max(1, size // 4)        # feature (ten whole-forest parcel maps are too much for one answer)
                netfetch.wait(5 * min(attempt + 1, 4), url)
            if js is None:
                raise RuntimeError(f"no usable answer from {url}")
            batch = js["features"]
            feats += batch
            if len(batch) < size or not js.get("properties", {}).get("exceededTransferLimit", len(batch) == size):
                break
            off += len(batch)
            size = min(page, size * 4)
        return feats
    feats = netfetch.last_good(f"esri-{netfetch.key(url, where, fields, W, S, E, N, EPSG)}", fetch, what)
    g = gpd.GeoDataFrame.from_features(feats, crs=CRS) if feats else gpd.GeoDataFrame(geometry=[], crs=CRS)
    return g[g.intersects(area_u)] if len(g) else g

# ---- fires ----
if has("cal_fire"):
    fires = esri("https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Historic_Fire_Perimeters/"
                 "FeatureServer/0", where=f"YEAR_ >= {FIRE_SINCE}", fields="YEAR_,FIRE_NAME,GIS_ACRES,ALARM_DATE",
                 what="CAL FIRE perimeters")
    fires = fires.rename(columns={"YEAR_": "year", "FIRE_NAME": "fire", "GIS_ACRES": "acres"})
    HIST = "CAL FIRE"
else:   # outside California: the interagency fire perimeter history (NIFC), every agency's perimeters in one layer
    fires = esri("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
                 "InterAgencyFirePerimeterHistory_All_Years_View/FeatureServer/0",
                 where=f"FIRE_YEAR_INT >= {FIRE_SINCE}", fields="FIRE_YEAR_INT,INCIDENT,GIS_ACRES", what="NIFC perimeters")
    fires = fires.rename(columns={"FIRE_YEAR_INT": "year", "INCIDENT": "fire", "GIS_ACRES": "acres"})
    HIST = "NIFC"
    if len(fires):   # this layer has unnamed and self-crossing perimeters
        fires = fires[fires.fire.notna() & fires.year.notna()].copy()
        fires["fire"] = fires.fire.str.strip()
        fires["geometry"] = fires.geometry.buffer(0)
if len(fires):
    fires["year"] = fires.year.astype(int)
    fires["fire"] = fires.fire.str.title()
    fires = fires.dissolve(by=["fire", "year"], as_index=False, aggfunc={"acres": "sum"}).assign(
        src=HIST + netfetch.asof(f"{HIST} perimeters"))
else:
    fires = gpd.GeoDataFrame({"fire": pd.Series(dtype=str), "year": pd.Series(dtype=int), "acres": pd.Series(dtype=float),
                              "src": pd.Series(dtype=str)}, geometry=[], crs=CRS)
# CAL FIRE publishes once a year: this year's fires come from the interagency year-to-date perimeters (WFIGS), and a
# fire in neither from the outline of its Forest Service BAER soil burn severity map (e.g. the 2026 Bouquet Fire)
SEV = {"Very Low or Unburned": 0.15, "Low": 0.4, "Moderate": 0.75, "High": 1.0}   # share of the full burn penalty
known = set(zip(fires.fire.str.lower(), fires.year))
wf = esri("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_YearToDate/"
          "FeatureServer/0", where="attr_IncidentTypeCategory = 'WF'",
          fields="poly_IncidentName,poly_GISAcres,attr_FireDiscoveryDateTime", what="WFIGS perimeters")
if len(wf):
    wf = wf.assign(fire=wf.poly_IncidentName.str.strip().str.title(), acres=wf.poly_GISAcres.astype(float),
                   year=pd.to_datetime(wf.attr_FireDiscoveryDateTime, unit="ms").dt.year)
    wf = wf[(wf.acres >= 10).values & np.array([(f.lower(), y) not in known for f, y in zip(wf.fire, wf.year)], bool)]
    wf = wf.dissolve(by=["fire", "year"], as_index=False, aggfunc={"acres": "max"}).assign(
        src="WFIGS" + netfetch.asof("WFIGS perimeters"))
    known |= set(zip(wf.fire.str.lower(), wf.year))
baer = esri("https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_BurnedAreaEmergencyResponse_01/MapServer/1",
            fields="baer_name,soil_burn_severity,est_containment_date,created_date", what="BAER burn severity")
if len(baer):
    nm = baer.baer_name.fillna("")
    when = pd.to_datetime(baer.est_containment_date.fillna(baer.created_date), unit="ms", errors="coerce")
    baer["year"] = pd.to_numeric(nm.str.extract(r"((?:19|20)\d\d)")[0], errors="coerce").fillna(when.dt.year)
    baer = baer[baer.year.notna()].assign(year=lambda d: d.year.astype(int))
    baer["fire"] = (baer.baer_name.str.replace(r"\b(?:BAER|Fire|(?:19|20)\d\d)\b", " ", regex=True)
                    .str.split().str.join(" ").str.title())
    baer["sev"] = baer.soil_burn_severity.map(SEV)
    baer["geometry"] = baer.geometry.buffer(0)
    new = baer[np.array([(f.lower(), y) not in known for f, y in zip(baer.fire, baer.year)], bool)]
    if len(new):
        bo = new.dissolve(by=["fire", "year"], as_index=False)
        bo = bo.assign(acres=bo.area / 4046.86, src="BAER" + netfetch.asof("BAER burn severity"))
        wf = pd.concat([wf, bo[bo.acres >= 10][["fire", "year", "acres", "src", "geometry"]]], ignore_index=True)
    baer = baer[baer.sev.notna()][["fire", "year", "sev", "geometry"]]
if len(wf):
    fires = gpd.GeoDataFrame(pd.concat([fires, wf[["fire", "year", "acres", "src", "geometry"]]], ignore_index=True), crs=CRS)
fires["year"] = fires.year.astype(int)
fires.to_crs(4326).to_file(f"{CTX}/fires.gpkg")
print("fires", len(fires), fires.src.value_counts().to_dict(), "| big:",
      sorted(fires[fires.acres > 5000].apply(lambda r: f"{r.fire} {r.year}", axis=1)),
      "| added this year:", sorted(f"{r.fire} {r.year} ({r.acres:.0f} ac)" for r in fires[~fires.src.str.startswith(HIST)].itertuples()
                                   if r.acres >= 100))
print("BAER burn severity polygons", len(baer), sorted(set(baer.fire + " " + baer.year.astype(str))) if len(baer) else [])
# USGS post-fire debris-flow hazard (combined likelihood and volume class) for channels below burns of the last 4
# years; the hazard fades as the slopes revegetate
dfh = esri("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/USGS_Post_Fire_Hazard_Assessment_Data/"
           "FeatureServer/5", fields="SCH_Legend,fire_id", what="USGS debris-flow hazard")
if len(dfh):
    dfh["hz"] = dfh.SCH_Legend.map({"Low": 1, "Moderate": 2, "High": 3})
    dfh["year"] = pd.to_numeric(dfh.fire_id.str.extract(r"((?:19|20)\d\d)")[0], errors="coerce")
    dfh = dfh[dfh.hz.notna() & (dfh.year >= dt.date.today().year - 4)][["hz", "year", "geometry"]]
print("debris-flow hazard segments", len(dfh))

# ---- springs and seeps (NHD points, FType 458) from every range's NHD download ----
sp_ = [gpd.read_file(p_).to_crs(CRS) for p_ in (f"{raw_dir(r)}/nhd_points.gpkg" for r in REGIONS) if os.path.exists(p_)]
springs = gpd.GeoDataFrame(pd.concat([q[q.ftype == 458][["gnis_name", "geometry"]] for q in sp_], ignore_index=True), crs=CRS)
springs = springs[~springs.geometry.to_wkb().duplicated()]
springs.to_crs(4326).to_file(f"{CTX}/springs.gpkg")
print("springs and seeps", len(springs))

# ---- land status ----
wild = gpd.read_file(wilderness_path())
wild = wild.rename(columns={c: "wilderness" for c in wild.columns if c.lower() == "wildernessname"})
if "wilderness" not in wild:   # no wilderness in the area
    wild["wilderness"] = pd.Series(dtype=str)
wild.to_crs(4326).to_file(f"{CTX}/wilderness.gpkg")
own = esri("https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_BasicOwnership_02/MapServer/0",
           fields="ownerclassification,forestname", what="Forest Service ownership")
if not len(own):   # no national forest in the area (northeastern Connecticut)
    own = gpd.GeoDataFrame({"ownerclassification": pd.Series(dtype=str), "forestname": pd.Series(dtype=str)}, geometry=[], crs=CRS)
nonfs = own[~own.ownerclassification.str.contains("USDA FOREST SERVICE", case=False, na=False)]
nonfs = nonfs[nonfs.area > 2000]  # skip slivers
nonfs = netfetch.tag(nonfs, "ownerclassification", "Forest Service ownership")
nonfs.to_crs(4326).to_file(f"{CTX}/non_fs_land.gpkg")
# California Protected Areas Database (CPAD 2026a): parks and open space with their public access. Only restricted
# and no-public-access holdings are kept; land outside CPAD and outside the national forests is private.
if has("cpad"):
    cpad = esri("https://gis.cnra.ca.gov/arcgis/rest/services/Boundaries/CPAD_AccessType/MapServer/0",
                where="ACCESS_TYP <> 'Open Access'", fields="ACCESS_TYP,UNIT_NAME,MNG_AGNCY", what="CPAD")
else:   # outside California: PAD-US (USGS), holdings recorded as restricted (RA) or closed (XA) to the public.
    #     Most eastern holdings are "unknown" (UK) there: those aren't flagged
    cpad = esri("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS_Public_Access/FeatureServer/0",
                where="Pub_Access IN ('RA','XA')", fields="Pub_Access,Unit_Nm,MngNm_Desc", what="PAD-US")
    if len(cpad):
        # PAD-US files federal wilderness, forest and park units as "restricted" (rules on use, not on entry):
        # they are open on foot, so they aren't flagged
        open_fed = cpad.Pub_Access.eq("RA") & (
            cpad.Unit_Nm.fillna("").str.contains(r"(?i)wilderness|national forest|national park|parkway|national recreation")
            | cpad.MngNm_Desc.fillna("").str.contains(r"(?i)forest service|national park service"))
        cpad = cpad[~open_fed]
    if len(cpad):
        cpad = cpad.assign(ACCESS_TYP=cpad.Pub_Access.map({"RA": "Restricted Access", "XA": "No Public Access"}),
                           UNIT_NAME=cpad.Unit_Nm, MNG_AGNCY=cpad.MngNm_Desc, geometry=cpad.geometry.buffer(0))
        cpad = cpad[["ACCESS_TYP", "UNIT_NAME", "MNG_AGNCY", "geometry"]]
cpad = cpad[cpad.area > 2000] if len(cpad) else cpad
cpad = netfetch.tag(cpad, "UNIT_NAME", "CPAD", "PAD-US")
cpad.to_crs(4326).to_file(f"{CTX}/cpad_restricted.gpkg")
print("restricted / no public access holdings (CPAD in California, PAD-US elsewhere):", len(cpad), cpad.ACCESS_TYP.value_counts().to_dict() if len(cpad) else {})
print("wilderness", list(wild.wilderness), "| non-FS parcels in forests", len(nonfs),
      nonfs.ownerclassification.value_counts().to_dict())

# ---- critical habitat ----
fws = esri("https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer/0",
           fields="comname,unitname,effectdate", what="USFWS critical habitat")
CA = has("cdfw_trout")
if len(fws):
    fws = fws[fws.comname.isin(AQUATIC) if CA else fws.comname.fillna("").str.contains(AQUATIC_RE)]
fws = fws.rename(columns={"comname": "species", "unitname": "unit"}) if len(fws) else fws.assign(species=None, unit=None)
fws = netfetch.tag(fws, "unit", "USFWS critical habitat")
nmfs = esri("https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NMFS_ESA_Critical_Habitat_gdb/FeatureServer/0",
            where="COMNAME LIKE '%teelhead%'", fields="COMNAME,LISTENTITY", what="NMFS critical habitat") \
    if CA else gpd.GeoDataFrame(geometry=[], crs=CRS)
nmfs = netfetch.tag(nmfs.assign(species="Southern California steelhead", unit=nmfs.get("LISTENTITY")), "unit",
                    "NMFS critical habitat")
habitat = pd.concat([fws[["species", "unit", "geometry"]],
                     nmfs[["species", "unit", "geometry"]].assign(geometry=nmfs.buffer(30))], ignore_index=True)
habitat = gpd.GeoDataFrame(habitat, crs=CRS)
habitat["species"] = habitat.species.replace({"Arroyo (=arroyo southwestern) toad": "Arroyo toad"})
# The service returns each species' whole range-wide multipolygon; keep only the part inside the study areas
# (otherwise the arroyo toad's ~400 km² across SoCal, and the red-legged frog's ~6,700 km², get drawn)
habitat["geometry"] = shapely.make_valid(habitat.geometry.values)
habitat["geometry"] = habitat.geometry.intersection(area_u)
habitat = habitat[~habitat.is_empty & (habitat.area > 1000)]
habitat.to_crs(4326).to_file(f"{CTX}/critical_habitat.gpkg")
print("critical habitat", habitat.species.value_counts().to_dict())

# ---- wild trout waters ----
trout = netfetch.tag(esri("https://services2.arcgis.com/Uq9r85Potqm3MfRV/arcgis/rest/services/biosds1356_fpu/FeatureServer/0",
                          fields="Name,Designation,Designation_Boundary", what="CDFW Wild Trout Waters"),
                     "Designation", "CDFW Wild Trout Waters") if CA else []
if not len(trout):   # outside California: each state's trout waters and the brook trout patches (troutdata.py)
    trout = troutdata.waters()
if "broad" not in trout:
    trout["broad"] = False
if "wild_brook" not in trout:   # CDFW's waters are for rainbow and golden trout: no brook trout in the LA ranges
    trout["wild_brook"] = False
trout.to_crs(4326).to_file(f"{CTX}/wild_trout_waters.gpkg")
print("wild trout waters", list(trout.Name))

# ---- August mean air temperature (PRISM 1991-2020 normal, 800 m) ----
from watertemp import air_tif     # the PRISM normal clipped to this area (downloaded when missing)

def air_at(pts):
    """August mean air temperature (C) at each point of a GeoSeries."""
    with rasterio.open(air_tif()) as src:
        ll = pts.to_crs(src.crs)
        v = np.array([x[0] for x in src.sample(zip(ll.x, ll.y))], float)
        nd = src.nodata
    return np.where((v == nd) | (v < -100), np.nan, v) if nd is not None else v

def air_along(gdf):
    """Mean August air temperature along each reach, sampled every 200 m."""
    pts, owner = [], []
    for i, ln in enumerate(gdf.geometry.values):
        n = max(2, int(ln.length // 200) + 1)
        pts.append(shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n)))
        owner.append(np.full(n, i))
    v = air_at(gpd.GeoSeries(np.concatenate(pts), crs=CRS))
    return pd.Series(v).groupby(np.concatenate(owner)).mean().reindex(range(len(gdf))).round(1).values

# ---- trout evidence ----
BIOS = "https://services2.arcgis.com/Uq9r85Potqm3MfRV/arcgis/rest/services"
LAKE = r"(?i)\b(?:lakes?|ponds?|reservoir)\b"
ev = []
hwt = esri(f"{BIOS}/HWT_Project_Map_WFL1/FeatureServer/14", fields="ProjectYear,WaterName,SpeciesPresent",
           what="CDFW surveys") if CA else []
if len(hwt):   # CDFW Heritage & Wild Trout Program: electrofishing / snorkel surveys and what they found
    spp = hwt.SpeciesPresent.fillna("").str.strip()
    found = spp.str.contains("trout", case=False)
    yr_ = pd.to_numeric(hwt.ProjectYear, errors="coerce")
    ev.append(hwt.assign(kind="CDFW survey", water=hwt.WaterName.str.strip(), year=yr_, trout=found, lake=False, url=None,
                         label=[f"CDFW survey {y:.0f}: " + (sp if t else "no trout found"
                                                            + (f" (found {sp})" if sp and sp.lower() != "none" else ""))
                                + netfetch.asof("CDFW surveys") for y, sp, t in zip(yr_, spp, found)]))
plant = esri(f"{BIOS}/biosds2897_fmu/FeatureServer/0", fields="WaterName,WeekOfPlantStart,FishType",
             what="CDFW stocking") if CA else []
if len(plant):   # CDFW trout stocking (planting) locations
    plant["when"] = pd.to_datetime(plant.WeekOfPlantStart, errors="coerce")
    plant = plant[plant.FishType.str.contains("trout", case=False, na=False).values
                  & (plant.when >= pd.Timestamp(dt.date.today()) - pd.Timedelta(days=365)).values]
    if len(plant):
        pg = plant.groupby(plant.WaterName.str.strip()).agg(n=("when", "size"), last=("when", "max"),
                                                             geometry=("geometry", "first"))
        pg = gpd.GeoDataFrame(pg.reset_index(), geometry="geometry", crs=CRS)
        ev.append(pg.assign(kind="CDFW stocking", water=pg.WaterName, year=pg["last"].dt.year, trout=True,
                            lake=pg.WaterName.str.contains(LAKE), url=None,
                            label=[f"stocked with trout {n}x in the last 12 months, last the week of {d:%b %-d, %Y}"
                                   + netfetch.asof("CDFW stocking") for n, d in zip(pg.n, pg["last"])]))
ev += troutdata.evidence()     # the other states' surveys and stocking (none in California)
def inat(taxon):
    """Research-grade iNaturalist sightings of a taxon in the study box with an exact (not obscured) location: the
    fields used below. When iNaturalist can't be read, its last good copy (netfetch.py)."""
    def fetch():
        rows, above = [], 0
        for _ in range(50):
            res = None
            for attempt in range(3):
                try:
                    r = netfetch.get("https://api.inaturalist.org/v1/observations", headers=UA, timeout=120, params=dict(
                        taxon_name=taxon, quality_grade="research", swlat=S, swlng=W, nelat=N, nelng=E, per_page=200,
                        order_by="id", order="asc", id_above=above))
                    res = r.json()["results"]
                    break
                except (requests.RequestException, ValueError, KeyError):
                    if attempt < 2:
                        netfetch.wait(10 * (attempt + 1), "https://api.inaturalist.org")
            if res is None:
                raise RuntimeError("iNaturalist failed")
            rows += [{k: o.get(k) for k in ("observed_on", "uri", "location")} | {"taxon": {
                         k: (o.get("taxon") or {}).get(k) for k in ("preferred_common_name", "name")}}
                     for o in res if o.get("location") and not o.get("obscured")
                     and (o.get("positional_accuracy") or 0) <= 500]
            if len(res) < 200:
                return rows
            above = res[-1]["id"]
            time.sleep(1.1)   # iNaturalist asks API users for about one request a second
        return rows
    return netfetch.last_good(f"inat-{netfetch.key(taxon, W, S, E, N)}", fetch, "iNaturalist")
# rainbow and brown trout everywhere; brook trout and cutthroat where they live (none of either in the LA ranges)
obs = inat("Oncorhynchus mykiss") + inat("Salmo trutta")
if not CA:
    obs += inat("Salvelinus fontinalis") + inat("Oncorhynchus clarkii")
if obs:
    tx = [o.get("taxon") or {} for o in obs]
    nat = gpd.GeoDataFrame(dict(
        kind="iNaturalist", water=None, trout=True, url=[o.get("uri") for o in obs],
        year=[int(o["observed_on"][:4]) if o.get("observed_on") else np.nan for o in obs],
        lake=False,
        label=[f"iNaturalist {o.get('observed_on') or ''}: {(t.get('preferred_common_name') or t.get('name') or 'trout').lower()}"
               + netfetch.asof("iNaturalist") for o, t in zip(obs, tx)]),
        geometry=gpd.points_from_xy([float(o["location"].split(",")[1]) for o in obs],
                                    [float(o["location"].split(",")[0]) for o in obs]), crs=4326).to_crs(CRS)
    ev.append(nat[nat.intersects(area_u)])
trout_ev = gpd.GeoDataFrame(pd.concat(ev, ignore_index=True), crs=CRS) if ev else None
if trout_ev is not None:
    # trout at a lake or reservoir are stocked fish: sightings within 100 m of an NHD lake / reservoir of 2 ha or more,
    # or within 400 m of a stocked lake, don't count for the creeks
    wb = [gpd.read_file(p_, layer="NHDWaterbody", bbox=(W, S, E, N)) for p_ in sorted([f"{NATIONAL}/NHD_H_{h}_HU4_GPKG.gpkg" for h in sorted({h for v in REGIONS.values() for h in v["hu4"]})])]
    wb = [w_[w_.ftype.isin([390, 436]) & (w_.areasqkm >= 0.02)].to_crs(CRS) for w_ in wb if len(w_)]
    lakes_ = pd.concat([w_.geometry for w_ in wb] + [trout_ev[trout_ev.kind.str.endswith("stocking") & trout_ev.lake]
                                                      .geometry.buffer(300)], ignore_index=True)
    if len(lakes_):
        trout_ev.loc[(trout_ev.kind == "iNaturalist") & (trout_ev.distance(lakes_.union_all()) < 100), "lake"] = True
    trout_ev["air_aug"] = air_at(trout_ev.geometry).round(1)
    # wild brook trout found (troutdata.py's surveys). Not CDFW's (no brook trout in the LA ranges), and not a sighting:
    # iNaturalist can't tell a wild brook trout from a stocked one
    trout_ev["wild_brook"] = (trout_ev["wild_brook"] if "wild_brook" in trout_ev else pd.Series(False, index=trout_ev.index)
                              ).fillna(False).astype(bool)
    trout_ev = trout_ev[["kind", "water", "year", "trout", "lake", "label", "url", "air_aug", "wild_brook", "geometry"]]
    trout_ev.to_crs(4326).to_file(f"{CTX}/trout_evidence.gpkg")
    print("trout evidence", trout_ev.groupby(["kind", "trout", "lake"]).size().to_dict())
    creek = trout_ev[trout_ev.trout & ~trout_ev.lake]
    hot = creek.loc[creek.air_aug.idxmax()] if creek.air_aug.notna().any() else None
    if hot is not None:
        print(f"hottest creek with a trout record: August air {hot.air_aug:.1f} C ({hot.label}); heat gate starts at "
              f"{HEAT_START} C" + (" -- WARNING: trout recorded above the gate's start, revisit HEAT_START in scoring.py"
                                    if hot.air_aug > HEAT_START else ""))

GENERIC = {"creek", "canyon", "wash", "river", "ck", "cyn"}
def norm(n):
    return " ".join(sorted(re.sub(r"[^a-z ]", " ", str(n).lower()).replace("secco", "seco").split()))

def cut_lines(s):
    """The line each reach is part of. 05_score.py cuts a creek 200 m below a lake for its water temperature alone (a
    first piece's cut_sid names the rest of its line), so the two pieces are one creek for what this step reads off
    other layers along it: trout records, trout water, fires and critical habitat are the whole line's for each, as
    the uncut line had them. Measured on its own, a first piece below a pond often missed a designated trout water or
    brook trout patch that starts lower down, and a record goes to the nearest reach: one piece. A reach that isn't
    cut is its own line. (Land and wilderness, read at a reach's middle, canopy and air stay each piece's own.)"""
    line = pd.Series(s.sid.values, index=s.index)
    return line.where(s.cut_sid.isna(), s.cut_sid) if "cut_sid" in s else line

CREEK_SHARE = 0.25      # of a link's creek a designation must cover to be read on every creek piece of the link
NAME_NEAR_M = 90.0      # a designation naming the reach's own creek is read this far: 05_score.py's name vote (60 m) + 30 m
OWN_SHARE = 0.5         # of a reach's own line designated waters must lie along to be its own (attrs: trout_water_own)
def creek_lines(s):
    """The creek each reach is part of for the designated trout waters it reads (attrs). 05_score.py cuts a link where
    it crosses the shore of a lake the map draws, at the outlet of a lake that passes its water on, and 200 m below a
    lake, and every creek piece of one link (link_id) reads the designated trout waters and brook trout patches on the
    whole link, as the uncut link did: measured on its own, a short piece where a creek runs through a pond or across a
    delta to a lake fell outside the 30 m a designation is read within (Big Elk Creek's last 48 m above Palisades
    Reservoir, Canada Creek's 51 m; on the 12 maps of 2026-11-23 about 1.9 mi lost its designation and 10+ of its fish
    score). A piece lying in a lake keeps its own, and a link never takes another's (a tributary's mouth is a link of
    its own); a designation read on the whole link counts only where it covers CREEK_SHARE of the link's creek (attrs):
    the last 11 m of an unnamed tributary in the Hoback box, past a pond, touch Bailey Creek's line, and on that touch
    its whole 2.6 km read as Bailey Creek's trout water. Records keep cut_lines (they go by the creek's name, so a named
    creek's pieces on both sides of a pond share them already), and so do fires and critical habitat."""
    line = cut_lines(s)
    if "link_id" not in s or "in_lake" not in s:
        return line
    lid = s.link_id.where(~s.in_lake.fillna(False).astype(bool))
    many = lid.notna() & lid.duplicated(keep=False)
    return line.where(~many, lid)

KIND_WORDS = {"creek", "ck", "cr", "river", "r", "brook", "bk", "branch", "br", "run", "stream", "kill", "canyon", "cyn",
              "wash", "the", "of", "to"}
SHORT = {"n": "north", "s": "south", "e": "east", "w": "west", "m": "middle", "nb": "north", "sb": "south", "eb": "east",
         "wb": "west", "mb": "middle", "nf": "north fork", "sf": "south fork", "ef": "east fork", "wf": "west fork",
         "mf": "middle fork", "trib": "tributary", "unt": "tributary", "mt": "mount", "mtn": "mountain"}
def water_words(n):
    """A stream name's own words: not the ones that say what kind of stream it is, a state's site codes ("Guys Run,
    10GUY-01T") or notes in brackets ("(rm 13.86 - modena)"); short forms written out ("Simpson Creek, NB")."""
    n = re.sub(r"\(.*?\)|\[.*?\]", " ", ("" if pd.isna(n) else str(n)).lower().replace("'", ""))
    n = " ".join(w for w in n.split() if not re.search(r"\d", w))
    return sorted(set(" ".join(SHORT.get(w, w) for w in re.sub(r"[^a-z ]", " ", n).split()).split()) - KIND_WORDS)

def same_water(a, b):
    """True when two names are one stream's: the same own words in any order ("Bitch Creek, South" is South Bitch
    Creek), or nearly the same letters ("Suga Creek"). "Camp Creek Trib" is not Camp Creek, nor "Little Toccoa Creek"
    Toccoa Creek. False when either has no name."""
    x, y = water_words(a), water_words(b)
    return bool(x) and bool(y) and (x == y or difflib.SequenceMatcher(None, " ".join(x), " ".join(y)).ratio() >= 0.85)

def trout_attrs(s):
    """Per reach: latest year trout were found (CDFW survey, stocking, iNaturalist), latest CDFW survey year that
    found none, latest year a survey found wild brook trout (brook_found), and a summary. Surveys and stocking count
    for the creek of the same name within 5 km of the point
    (else the nearest reach within 300 m and the same creek within 1.5 km); a sighting for its reach (within 150 m)
    and the same creek within 1.5 km.
    Lakes are left out: their trout are stocked."""
    out = pd.DataFrame({"sid": s.sid.values})
    if trout_ev is None:
        return out
    s = s.reset_index(drop=True)
    named = s["name"].fillna("").map(norm)
    hits = []
    for e in trout_ev[~trout_ev.lake & trout_ev.geometry.notna()].itertuples():
        d = s.distance(e.geometry)
        if not len(d) or d.min() > 5000:
            continue
        j = d.idxmin()
        if e.kind == "iNaturalist":
            if d[j] > 150:
                continue
            sel = (d <= 1500) & (named == named[j]) if named[j] else (d.index == j)
        else:   # same name, or the reach's name inside the survey's (NHD calls the East Fork "San Gabriel River")
            # A no-trout sample outside California speaks for the creek within 1.5 km of its site only: the states
            # there sample warm lower reaches of creeks whose headwaters hold trout (CDFW's surveys keep 5 km)
            reach_m = 5000 if (e.trout or CA) else 1500
            want, wcore, close = norm(e.water), set(norm(e.water).split()) - GENERIC, (d <= reach_m) & (named != "")
            ok = {n: difflib.SequenceMatcher(None, n, want).ratio() >= 0.85
                     or (len(c := set(n.split()) - GENERIC) >= 2 and c <= wcore) for n in set(named[close])}
            sel = close & named.map(lambda n: ok.get(n, False))
            if not sel.any() and d[j] <= 300:   # else the nearest reach and the same creek within 1.5 km
                sel = (d <= 1500) & (named == named[j]) if named[j] else (d.index == j)
        hits += [(sid, e.Index, e.kind, e.year, e.trout, e.label, e.wild_brook) for sid in s.sid[sel]]
    if not hits:
        return out
    h = pd.DataFrame(hits, columns=["sid", "e", "kind", "year", "trout", "label", "brook"])
    line = pd.DataFrame({"sid": s.sid.values, "line": cut_lines(s).values})   # a cut line's pieces: the whole line's
    h = (h.merge(line, on="sid").drop(columns="sid").drop_duplicates(["line", "e"]).merge(line, on="line")
         .drop(columns=["line", "e"]))
    pos, neg = h[h.trout], h[~h.trout & h.kind.str.endswith("survey")]
    out["trout_found"] = out.sid.map(pos.groupby("sid").year.max())
    out["trout_absent"] = out.sid.map(neg.groupby("sid").year.max())
    out["brook_found"] = out.sid.map(h[h.brook].groupby("sid").year.max())
    def summary(g):
        recs = g[g.kind != "iNaturalist"].sort_values("year", ascending=False)
        parts = list(dict.fromkeys(recs.label))[:3]
        if recs.brook.any() and recs[recs.brook].label.iat[0] not in parts:   # the brook trout find scoring.py sizes on
            parts.append(recs[recs.brook].label.iat[0])
        nat_ = g[g.kind == "iNaturalist"]
        if len(nat_):
            parts.append(f"iNaturalist: {len(nat_)} trout sighting{'s' if len(nat_) > 1 else ''} on this creek nearby, "
                         f"latest {nat_.year.max():.0f}")
        return " · ".join(parts)
    out["trout_ev"] = out.sid.map({k: summary(g) for k, g in h.groupby("sid")})
    return out

# ---- USFS tree canopy cover (NLCD TCC), latest year, 30 m ----
TCC = "https://imagery.geoplatform.gov/iipp/rest/services/Vegetation/USFS_EDW_NLCD_TCC_CONUS/ImageServer"
def canopy_tif(r, tile=1500):
    """The region's canopy cover raster (% , 255 = no data), downloaded in tiles and cached for 90 days."""
    p_ = f"{raw_dir(r)}/canopy_tcc.tif"
    if os.path.exists(p_) and time.time() - os.path.getmtime(p_) < 90 * 86400:
        return p_
    def fetch():     # (an older raster stays when the download fails: netfetch.keep_old)
        t1 = netfetch.fetch("GET", TCC, params={"f": "json"}, headers=UA, timeout=120).json()["timeInfo"]["timeExtent"][1]
        x0, y0, x1, y1 = REGIONS[r]["bbox"]
        w_, h_ = int(np.ceil((x1 - x0) / 30)), int(np.ceil((y1 - y0) / 30))
        arr = np.full((h_, w_), 255, np.uint8)
        for ty in range(0, h_, tile):
            for tx in range(0, w_, tile):
                w, h = min(tile, w_ - tx), min(tile, h_ - ty)
                bb = (x0 + tx * 30, y1 - (ty + h) * 30, x0 + (tx + w) * 30, y1 - ty * 30)
                for attempt in range(4):
                    try:
                        rr = netfetch.get(f"{TCC}/exportImage", headers=UA, timeout=300, params=dict(
                            bbox=",".join(map(str, bb)), bboxSR=EPSG, imageSR=EPSG, size=f"{w},{h}", format="tiff",
                            pixelType="U8", interpolation="RSP_NearestNeighbor", time=t1, f="image"))
                        with rasterio.MemoryFile(rr.content) as mf, mf.open() as src:
                            a = src.read(1)
                        break
                    except Exception:
                        if attempt < 3:
                            netfetch.wait(15 * (attempt + 1), TCC)
                else:
                    raise RuntimeError("canopy cover download failed")
                arr[ty:ty + min(h, a.shape[0]), tx:tx + min(w, a.shape[1])] = a[:h, :w]
        with rasterio.open(p_ + ".tmp", "w", driver="GTiff", height=h_, width=w_, count=1, dtype="uint8", crs=CRS,
                           transform=from_origin(x0, y1, 30, 30), nodata=255, compress="deflate") as dst:
            dst.write(arr, 1)
        os.replace(p_ + ".tmp", p_)
    netfetch.keep_old(p_, fetch, f"tree canopy cover ({r})")
    return p_

def canopy_pct(gdf, r):
    """Mean canopy cover within ~45 m of the channel: 3 x 3 cell means at points every 30 m along each reach."""
    with rasterio.open(canopy_tif(r)) as src:
        a, T = src.read(1).astype("float32"), src.transform
    ok = a <= 100
    a[~ok] = 0
    num, den = uniform_filter(a, 3), uniform_filter(ok.astype("float32"), 3)
    m = np.where(den > 0.3, num / np.maximum(den, 1e-6), np.nan)
    pts, owner = [], []
    for i, ln in enumerate(gdf.geometry.values):
        n = max(2, int(ln.length // 30) + 1)
        pts.append(shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n)))
        owner.append(np.full(n, i))
    pts, owner = np.concatenate(pts), np.concatenate(owner)
    cols, rows = ~T * (shapely.get_x(pts), shapely.get_y(pts))
    rows, cols = np.floor(rows).astype(int), np.floor(cols).astype(int)
    inside = (rows >= 0) & (rows < m.shape[0]) & (cols >= 0) & (cols < m.shape[1])
    v = np.full(len(pts), np.nan)
    v[inside] = m[rows[inside], cols[inside]]
    return pd.Series(v).groupby(owner).mean().reindex(range(len(gdf))).round(0).values

# ---- USGS gauges: latest discharge vs daily percentiles for today ----
# From the USGS Water Data APIs (api.waterdata.usgs.gov), which replace WaterServices (shut down on 2027-02-22): the
# latest discharge from the OGC API, the percentiles for today's date from the Statistics API (beta). It allows a set
# number of requests an hour (1,000 without a key, shared with the connection); a free key from
# https://api.waterdata.usgs.gov/signup/ (USGS_API_KEY, or the private file ~/.config/usgs/api_key) gets 1,000 an hour
# of its own, and netfetch.usgs_key sends it only to this API.
WDAPI = "https://api.waterdata.usgs.gov"
def get(url, tries=4, **params):
    """GET with retries: the USGS and CDEC servers drop connections now and then. A server over its request limit
    (HTTP 429) is waited out as long as it asks, twice at most. None when the server answers with errors only;
    netfetch.NetworkDown when it doesn't answer at all (then the gauges are their last good snapshot)."""
    hdr, waits = {**UA, **netfetch.usgs_key(url)}, 0
    for attempt in range(tries):
        try:
            r = netfetch.get(url, headers=hdr, timeout=300, params=params)
            if r.ok:
                return r
            if r.status_code == 429 and waits < 2:
                s = r.headers.get("Retry-After", "")
                s = int(s) if s.isdigit() else 600
                netfetch.rate_wait(s + 5, url)     # (or the last good copy, when the wait is long)
                waits += 1
                continue
        except requests.RequestException:
            pass
        netfetch.wait(10 * (attempt + 1) if attempt < tries - 1 else 0, url)
    return None
def chunks(xs, n):
    """Site ids go in the URL, and long URLs are refused (83 ids in one statistics request got a 403)."""
    return [xs[i:i + n] for i in range(0, len(xs), n)]
def answer(r, what):
    if r is None:
        raise RuntimeError(f"no answer from USGS for {what}")
    return r.json()
# Latest discharge of each gauge in the box that reported in the last 183 days: the API also keeps long-retired gauges
# with their last reading (WaterServices' siteStatus=active left those out). Times come in UTC.
def latest(lc):
    rows = []
    for ft in lc["features"]:
        pr, (lon, lat) = ft["properties"], ft["geometry"]["coordinates"][:2]
        rows.append(dict(site=pr["monitoring_location_id"].removeprefix("USGS-"), name="",
                         cfs=pd.to_numeric(pr["value"], errors="coerce"),
                         time=pd.Timestamp(pr["time"]).tz_convert("America/Los_Angeles").strftime("%Y-%m-%d %H:%M"),
                         lon=lon, lat=lat))
    g = gpd.GeoDataFrame(rows, geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]), crs=4326)
    g = g[g.to_crs(CRS).intersects(area_u)].sort_values("site").drop_duplicates("site")
    return g[g.cfs >= 0]
def named(g, names):    # (the latest values don't carry the station name)
    g = g.assign(name=g.site.map(names).fillna("").str.title())
    # diversions, flumes, spillways and tunnels measure plumbing, not the creek
    return g[~g.name.str.contains(r"\b(?:Div|Diversion|Spill|Spillway|Forebay|Flume|Tunnel|Supp)\b", case=False)]
today = dt.date.today()
missed = []      # statistics requests the server refused (their gauges show "no history")
def day_stats(sites):
    """Percentiles of the daily mean flow on today's month/day over each gauge's approved record, 20 gauges a request.
    Where the flow on this date was 0 in every year the API gives "nan" percentiles, so the maximum comes too: a
    maximum of 0 makes them all 0."""
    st, md = {}, f"{today:%m-%d}"
    for ids in chunks(["USGS-" + s for s in sites], 20):
        tok = None
        while True:
            r = get(f"{WDAPI}/statistics/v0/observationNormals", tries=3, monitoring_location_id=ids,
                    parameter_code="00060", normal_type="DOY", start_date=md, end_date=md,
                    computation_type=["percentile", "maximum"], page_size=1000, next_token=tok)
            if r is None:
                print("USGS statistics request failed for", ", ".join(ids))
                missed.extend(ids)
                break
            js = r.json()
            for ft in js.get("features", []):
                site = ft["properties"]["monitoring_location_id"].removeprefix("USGS-")
                for d_ in ft["properties"].get("data", []):
                    v = {x.get("computation"): x for x in d_.get("values", []) if x.get("time_of_year") == md}
                    if "percentile" not in v:
                        continue
                    s_ = dict(zip(("p" + q for q in v["percentile"]["percentiles"]),
                                  pd.to_numeric(v["percentile"]["values"], errors="coerce")))
                    if pd.to_numeric(v.get("maximum", {}).get("value"), errors="coerce") == 0:
                        s_ = dict.fromkeys(s_, 0.0)
                    s_["years"] = v["percentile"].get("sample_count") or 0
                    if s_["years"] > st.get(site, {}).get("years", -1):   # several discharge records: the longest
                        st[site] = s_
            tok = js.get("next")
            if not tok:
                break
    return st
def snapshot():
    """The latest discharge, the station names and today's percentiles: one snapshot, kept as the last good copy
    unless a statistics request was refused (used then, but not kept)."""
    lc = answer(get(f"{WDAPI}/ogcapi/v1/collections/latest-continuous/items", f="json",
                    bbox=f"{W:.4f},{S:.4f},{E:.4f},{N:.4f}", parameter_code="00060", time="P183D",
                    properties="monitoring_location_id,time,value", limit=10000), "the latest discharge")
    g, names = latest(lc), {}
    for ids in chunks(list("USGS-" + g.site), 40):
        ml = answer(get(f"{WDAPI}/ogcapi/v1/collections/monitoring-locations/items", f="json", id=",".join(ids),
                        properties="monitoring_location_name", skipGeometry="true", limit=1000), "station names")
        names.update({ft["id"].removeprefix("USGS-"): ft["properties"]["monitoring_location_name"] for ft in ml["features"]})
    snap = dict(lc=lc, names=names, st=day_stats(list(named(g, names).site)))
    return netfetch.Partial(snap, f"no percentiles for {len(missed)} gauges") if missed else snap
snap = netfetch.last_good(f"usgs-gauges-{netfetch.key(W, S, E, N)}", snapshot, "USGS gauges")
gauges, st = named(latest(snap["lc"]), snap["names"]), snap["st"]
for p in ("p10", "p25", "p50", "p75", "p90"):
    gauges[p] = [st.get(x, {}).get(p, np.nan) for x in gauges.site]
gauges["years"] = [st.get(x, {}).get("years") for x in gauges.site]
def rel(r):
    """Today's flow against the daily percentiles for this date (missing high percentiles are skipped)."""
    if pd.isna(r.get("p50")):
        return "no history"
    if r.cfs <= 0:
        return "dry" if r.p50 > 0 else "dry (normal for date)"
    if r.p50 == 0:
        return "flowing (usually dry on this date)"
    for p, lab in (("p10", "much below normal"), ("p25", "below normal"), ("p75", "normal"), ("p90", "above normal")):
        if pd.notna(r.get(p)) and r.cfs < r[p]:
            return lab
    return "much above normal" if pd.notna(r.get("p90")) else "above normal"
gauges["status"] = gauges.apply(rel, axis=1)
gauges["pct_of_median"] = np.where(gauges.get("p50", 0) > 0, (100 * gauges.cfs / gauges.get("p50", np.nan)).round(0), np.nan)
gauges["url"] = "https://waterdata.usgs.gov/monitoring-location/" + gauges.site
# CDEC (California DWR): Piru Creek above Pyramid Lake, and Pyramid Dam's release to lower Piru Creek (live, hourly;
# no percentile history)
CDEC = [("PIR", 20, "Piru Creek above Pyramid Lake (CDEC)", 34.665, -118.823),
        ("PYM", 23, "Pyramid Dam release to lower Piru Creek (CDEC)", 34.644153, -118.764528)]
if not has("cdec"):
    CDEC = []
try:     # (its readings carry their times: a last good copy shows its own)
    js = [] if not CDEC else netfetch.last_good("cdec-piru", lambda: answer(get(
        "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet", Stations=",".join(c[0] for c in CDEC),
        SensorNums=",".join(str(c[1]) for c in CDEC), dur_code="H", Start=(today - dt.timedelta(days=3)).isoformat(),
        End=(today + dt.timedelta(days=1)).isoformat()), "CDEC"), "CDEC gauges")
except (AttributeError, ValueError, RuntimeError):
    js = []
crow = []
for st_id, sens, name, lat, lon in CDEC:
    v = [x for x in js if x.get("stationId") == st_id and x.get("SENSOR_NUM") == sens
         and x.get("value") is not None and x["value"] > -9000]
    if v:
        crow.append(dict(site=f"CDEC {st_id}", name=name, cfs=float(v[-1]["value"]), time=v[-1]["date"][:16],
                         status="no history", url=f"https://cdec.water.ca.gov/dynamicapp/staMeta?station_id={st_id}",
                         geometry=shapely.Point(lon, lat)))
if crow:
    gauges = gpd.GeoDataFrame(pd.concat([gauges, gpd.GeoDataFrame(crow, crs=4326)], ignore_index=True), crs=4326)
# " (as of Nov 23)" where the snapshot is a saved copy (netfetch.py), "" where it is live: the map's gauge layer says
# so instead of "live" (06_map.py, 2026-11-24)
gauges["asof"] = [netfetch.asof("CDEC gauges" if str(s_).startswith("CDEC") else "USGS gauges") for s_ in gauges.site]
gauges.to_file(f"{CTX}/gauges.gpkg")
print("gauges", len(gauges), gauges.status.value_counts().to_dict())

# ---- per-reach / per-drop attributes ----
fire_s = fires.sort_values("year", ascending=False)
def attrs(gdf, key, buf):
    g = gdf[[key, "geometry"]].copy()
    g["geometry"] = g.buffer(buf)
    if key == "sid":    # the two pieces of a line cut below a lake: each the whole line's buffer (cut_lines)
        line = cut_lines(gdf)
        two = line.duplicated(keep=False).to_numpy()
        if two.any():
            whole = g[two].assign(_line=line[two].values).dissolve("_line").geometry
            g.loc[two, "geometry"] = whole.reindex(line[two].values).values
    out = pd.DataFrame({key: gdf[key]})
    j = gpd.sjoin(g, fire_s[["fire", "year", "geometry"]], predicate="intersects").sort_values("year", ascending=False)
    first = j.groupby(key).first()
    out["burn_year"] = out[key].map(first.year)
    out["burn_fire"] = out[key].map(first.fire)
    out["burn_count"] = out[key].map(j.groupby(key).size()).fillna(0).astype(int)
    mid = gdf[[key]].assign(geometry=gdf.geometry.representative_point())
    mid = gpd.GeoDataFrame(mid, crs=CRS)
    out["wilderness"] = out[key].map(gpd.sjoin(mid, wild[["wilderness", "geometry"]]).groupby(key).wilderness.first())
    out["non_fs_land"] = out[key].map(gpd.sjoin(mid, nonfs[["ownerclassification", "geometry"]])
                                      .groupby(key).ownerclassification.first())
    if len(cpad):
        cj = gpd.sjoin(mid, cpad[["ACCESS_TYP", "UNIT_NAME", "geometry"]]).groupby(key).first()
        out["cpad_access"] = out[key].map(cj.ACCESS_TYP + ": " + cj.UNIT_NAME.fillna(""))
    h = gpd.sjoin(g, habitat[["species", "geometry"]], predicate="intersects")
    out["crit_habitat"] = out[key].map(h.groupby(key).species.agg(lambda s: ", ".join(sorted(set(s)))))
    gt = g              # the designated trout waters: every creek piece of a link reads them on the whole link (creek_lines)
    if key == "sid":
        cl = creek_lines(gdf)
        many = cl.duplicated(keep=False).to_numpy()
        if many.any():
            gt = g.copy()
            whole = g[many].assign(_line=cl[many].values).dissolve("_line").geometry
            gt.loc[many, "geometry"] = whole.reindex(cl[many].values).values
    t = gpd.sjoin(gt, trout[["Name", "Designation", "broad", "wild_brook", "geometry"]], predicate="intersects")
    t["label"] = (t.Designation + ": " + t.Name).str.replace(r": $", "", regex=True)
    # one label per reach: a mapped stream's designation before a catchment-wide one, then the reach's own stream's by
    # name (same_water), then the one that covers most of the reach. Only which label shows, here and in brook_water
    # below: a reach keeps every water its buffer touches, so the score is the same. At a confluence the neighbouring
    # stream's line clips the reach too, and a river's own line can come in short segments that each cover less of it
    # than a tributary's or a misnamed one's (the Little River in the Smokies showed Brier Branch): 881 popups on the
    # 12 maps named another stream (2026-11-22)
    t["cover"] = shapely.area(shapely.intersection(t.geometry.values, trout.geometry.reindex(t.index_right).values))
    if gt is not g:     # read on the whole link: only a designation covering CREEK_SHARE of it, or one the piece touches
        own_ = gpd.sjoin(g, trout[["geometry"]], predicate="intersects")
        own_ = set(zip(own_[key], own_.index_right))
        t = t[(t.cover >= CREEK_SHARE * shapely.area(t.geometry.values))
              | np.array([(k_, j_) in own_ for k_, j_ in zip(t[key], t.index_right)], dtype=bool)]
    names = gdf["name"] if key == "sid" and "name" in gdf else pd.Series(None, index=gdf.index, dtype=object)
    # ... and a creek reach reads a designation that names its own creek (same_water) within NAME_NEAR_M, where its line
    # strays from the designated one: a braided river's routed channel lies up to 60 m off NHD's line and still carries
    # its name (05_score.py's name vote), and the designation is read 30 m from it. A reach got its creek's designation
    # only where its 30 m reached the designated line, so where the routing cut a creek again, the piece lying off the
    # line lost it: Buffalo Fork's 348 m and Pacific Creek's 549 m in Jackson, 86 m from their Wyoming trout-stream lines,
    # with pond routing v2 (2026-11-24). A tributary (another name, or none) reads only what its own 30 m touches.
    if key == "sid" and names.notna().any():
        cr_ = names.notna().to_numpy() & ~(gdf["in_lake"].fillna(False).astype(bool).to_numpy() if "in_lake" in gdf
                                           else np.zeros(len(gdf), bool))
        nb_ = gpd.sjoin(gdf.loc[cr_, [key, "geometry"]].assign(geometry=gdf.geometry[cr_].buffer(NAME_NEAR_M)),
                        trout[["Name", "Designation", "broad", "wild_brook", "geometry"]], predicate="intersects")
        nb_ = nb_[np.array([same_water(a, b) for a, b in zip(names.reindex(nb_.index), nb_.Name)], dtype=bool)]
        have_ = set(zip(t[key], t.index_right))
        nb_ = nb_[np.array([(k_, j_) not in have_ for k_, j_ in zip(nb_[key], nb_.index_right)], dtype=bool)]
        if len(nb_):
            nb_ = nb_.assign(geometry=g.geometry.reindex(nb_.index).values, cover=0.0,
                             label=(nb_.Designation + ": " + nb_.Name).str.replace(r": $", "", regex=True))
            t = pd.concat([t, nb_])
    t["own"] = [same_water(a, b) for a, b in zip(names.reindex(t.index), t.Name)]
    t = t.sort_values(["broad", "own", "cover"], ascending=[True, False, False])
    out["trout_water"] = out[key].map(t.groupby(key).label.first())
    # wild brook trout water, from any designation that covers the reach: a state's line (NY's class T, Georgia's
    # designated streams) is the label above and would hide the brook trout patch under it
    out["brook_water"] = out[key].map(t[t.wild_brook.astype(bool)].groupby(key).label.first())
    # the reach's own trout water, which scoring.py's water (5) takes for water every summer: designated waters along
    # OWN_SHARE of the reach's own line (within buf of them, together: a river's line can come in short segments, a
    # patch is an area), or one naming its own creek. A tributary's 30 m touches the river's line at its mouth and
    # reads the river's designation, which says nothing of the tributary's water: unnamed creeks in Teton Valley read
    # Bitch Creek's or the Teton River's along a third of their length or less, and as trout water would have gone
    # from mostly dry to year-round (teton_valley:s244, 1 %: fish 6 -> 54; 2026-11-24)
    if key == "sid":
        own_ = pd.Series(False, index=out.index)
        if len(t):
            zone_, line_ = trout.geometry.buffer(buf), gdf.set_index(key).geometry
            along_ = {k_: (line_[k_].intersection(shapely.union_all(zone_.loc[j_.unique()].values)).length
                           / max(line_[k_].length, 1e-9)) for k_, j_ in t.groupby(key).index_right}
            own_ = (out[key].map(pd.Series(along_, dtype=float)).ge(OWN_SHARE - 1e-9)
                    | out[key].map(t.groupby(key).own.any()).eq(True))
        out["trout_water_own"] = own_.to_numpy(bool)
    if len(baer):   # area-weighted soil burn severity of the reach's latest fire, where BAER mapped it (>= 30 % cover)
        x = gpd.overlay(g, baer, how="intersection", keep_geom_type=True)
        if len(x):
            x["a"] = x.area
            x["w"] = x.sev * x.a
            agg = x.groupby([key, "fire", "year"])[["w", "a"]].sum()
            agg = agg[agg.a.values / g.set_index(key).area.reindex(agg.index.get_level_values(0)).values >= 0.3]
            lk = {(k_, f.lower(), int(y)): round(w / a, 2) for (k_, f, y), w, a in zip(agg.index, agg.w, agg.a)}
            out["burn_sev"] = [lk.get((k_, str(f).lower(), int(y)), np.nan) if pd.notna(y) else np.nan
                               for k_, f, y in zip(out[key], out.burn_fire, out.burn_year)]
    if len(dfh):    # highest post-fire debris-flow hazard on the channel
        dj = gpd.sjoin(g, dfh, predicate="intersects")
        if len(dj):
            top = dj.sort_values(["hz", "year"]).groupby(key).last()
            w_ = netfetch.when("USGS debris-flow hazard")    # (scoring.py reads the class and the year from it)
            out["debris_flow"] = out[key].map(top.hz.map({1: "low", 2: "moderate", 3: "high"})
                                              + " (" + top.year.astype(int).astype(str) + " fire"
                                              + (f"; hazard map as of {w_}" if w_ else "") + ")")
    return out

for r in REGIONS:
    s = gpd.read_file(f"{MAP_OUT}/{r}/streams_scored.gpkg").to_crs(CRS)
    d = gpd.read_file(f"{MAP_OUT}/{r}/waterfall_candidates.gpkg").to_crs(CRS)
    cs, cd = attrs(s, "sid", 30), attrs(d, "did", 60)
    cs["canopy_pct"] = canopy_pct(s, r)
    cs["air_aug"] = air_along(s)
    cs = cs.merge(trout_attrs(s), on="sid", how="left")
    cs.to_csv(f"{MAP_OUT}/{r}/context_streams.csv", index=False)
    cd.to_csv(f"{MAP_OUT}/{r}/context_drops.csv", index=False)
    print(f"{REGIONS[r]['label']}: reaches burned since {FIRE_SINCE}: {cs.burn_year.notna().mean():.0%} | wilderness "
          f"{cs.wilderness.notna().mean():.0%} | non-FS land {cs.non_fs_land.notna().mean():.0%} | crit. habitat "
          f"{cs.crit_habitat.notna().mean():.0%} | wild trout {cs.trout_water.notna().sum()} (brook trout "
          f"{cs.brook_water.notna().sum()}, found {cs.get('brook_found', pd.Series(dtype=float)).notna().sum()}) | trout found "
          f"{cs.get('trout_found', pd.Series(dtype=float)).notna().sum()}, none found "
          f"{cs.get('trout_absent', pd.Series(dtype=float)).notna().sum()} | burn severity "
          f"{cs.get('burn_sev', pd.Series(dtype=float)).notna().sum()} | debris-flow "
          f"{cs.get('debris_flow', pd.Series(dtype=object)).notna().sum()} | canopy median {np.nanmedian(cs.canopy_pct):.0f}% | "
          f"August air {np.nanmin(cs.air_aug):.1f}-{np.nanmax(cs.air_aug):.1f} C, above the heat gate "
          f"{int((cs.air_aug > HEAT_START).sum())}")
