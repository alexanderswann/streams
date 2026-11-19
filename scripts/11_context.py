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
Writes output/context/*.gpkg and output/<region>/context_streams.csv, context_drops.csv.
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

def esri(url, where="1=1", fields="*", page=1000):
    """Every feature of an ArcGIS layer in the study area. A server that can't answer a full page (the Forest
    Service ownership layer over the Chattahoochee: a thousand detailed parcels at once) is asked for smaller ones."""
    feats, off = [], 0
    while True:
        js = None
        for attempt in range(12):
            try:
                r = requests.get(f"{url}/query", headers=UA, timeout=300, params=dict(
                    where=where, geometry=f"{W},{S},{E},{N}", geometryType="esriGeometryEnvelope", inSR=4326,
                    spatialRel="esriSpatialRelIntersects", outFields=fields, outSR=EPSG, f="geojson",
                    resultOffset=off, resultRecordCount=page))
                if r.ok and "features" in r.json():
                    js = r.json()
                    break
            except (requests.RequestException, ValueError):
                pass
            if attempt >= 1 and page > 1:       # two failures at this size: a quarter of the page, down to one
                page = max(1, page // 4)        # feature (ten whole-forest parcel maps are too much for one answer)
            time.sleep(5 * min(attempt + 1, 4))
        if js is None:
            raise RuntimeError(f"no usable answer from {url}")
        batch = js["features"]
        feats += batch
        if len(batch) < page or not js.get("properties", {}).get("exceededTransferLimit", len(batch) == page):
            break
        off += len(batch)
    g = gpd.GeoDataFrame.from_features(feats, crs=CRS) if feats else gpd.GeoDataFrame(geometry=[], crs=CRS)
    return g[g.intersects(area_u)] if len(g) else g

# ---- fires ----
if has("cal_fire"):
    fires = esri("https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Historic_Fire_Perimeters/"
                 "FeatureServer/0", where=f"YEAR_ >= {FIRE_SINCE}", fields="YEAR_,FIRE_NAME,GIS_ACRES,ALARM_DATE")
    fires = fires.rename(columns={"YEAR_": "year", "FIRE_NAME": "fire", "GIS_ACRES": "acres"})
    HIST = "CAL FIRE"
else:   # outside California: the interagency fire perimeter history (NIFC), every agency's perimeters in one layer
    fires = esri("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
                 "InterAgencyFirePerimeterHistory_All_Years_View/FeatureServer/0",
                 where=f"FIRE_YEAR_INT >= {FIRE_SINCE}", fields="FIRE_YEAR_INT,INCIDENT,GIS_ACRES")
    fires = fires.rename(columns={"FIRE_YEAR_INT": "year", "INCIDENT": "fire", "GIS_ACRES": "acres"})
    HIST = "NIFC"
    if len(fires):   # this layer has unnamed and self-crossing perimeters
        fires = fires[fires.fire.notna() & fires.year.notna()].copy()
        fires["fire"] = fires.fire.str.strip()
        fires["geometry"] = fires.geometry.buffer(0)
if len(fires):
    fires["year"] = fires.year.astype(int)
    fires["fire"] = fires.fire.str.title()
    fires = fires.dissolve(by=["fire", "year"], as_index=False, aggfunc={"acres": "sum"}).assign(src=HIST)
else:
    fires = gpd.GeoDataFrame({"fire": pd.Series(dtype=str), "year": pd.Series(dtype=int), "acres": pd.Series(dtype=float),
                              "src": pd.Series(dtype=str)}, geometry=[], crs=CRS)
# CAL FIRE publishes once a year: this year's fires come from the interagency year-to-date perimeters (WFIGS), and a
# fire in neither from the outline of its Forest Service BAER soil burn severity map (e.g. the 2026 Bouquet Fire)
SEV = {"Very Low or Unburned": 0.15, "Low": 0.4, "Moderate": 0.75, "High": 1.0}   # share of the full burn penalty
known = set(zip(fires.fire.str.lower(), fires.year))
wf = esri("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_YearToDate/"
          "FeatureServer/0", where="attr_IncidentTypeCategory = 'WF'",
          fields="poly_IncidentName,poly_GISAcres,attr_FireDiscoveryDateTime")
if len(wf):
    wf = wf.assign(fire=wf.poly_IncidentName.str.strip().str.title(), acres=wf.poly_GISAcres.astype(float),
                   year=pd.to_datetime(wf.attr_FireDiscoveryDateTime, unit="ms").dt.year)
    wf = wf[(wf.acres >= 10).values & np.array([(f.lower(), y) not in known for f, y in zip(wf.fire, wf.year)], bool)]
    wf = wf.dissolve(by=["fire", "year"], as_index=False, aggfunc={"acres": "max"}).assign(src="WFIGS")
    known |= set(zip(wf.fire.str.lower(), wf.year))
baer = esri("https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_BurnedAreaEmergencyResponse_01/MapServer/1",
            fields="baer_name,soil_burn_severity,est_containment_date,created_date")
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
        bo = bo.assign(acres=bo.area / 4046.86, src="BAER")
        wf = pd.concat([wf, bo[bo.acres >= 10][["fire", "year", "acres", "src", "geometry"]]], ignore_index=True)
    baer = baer[baer.sev.notna()][["fire", "year", "sev", "geometry"]]
if len(wf):
    fires = gpd.GeoDataFrame(pd.concat([fires, wf[["fire", "year", "acres", "src", "geometry"]]], ignore_index=True), crs=CRS)
fires["year"] = fires.year.astype(int)
fires.to_crs(4326).to_file(f"{CTX}/fires.gpkg")
print("fires", len(fires), fires.src.value_counts().to_dict(), "| big:",
      sorted(fires[fires.acres > 5000].apply(lambda r: f"{r.fire} {r.year}", axis=1)),
      "| added this year:", sorted(f"{r.fire} {r.year} ({r.acres:.0f} ac)" for r in fires[fires.src != HIST].itertuples()
                                   if r.acres >= 100))
print("BAER burn severity polygons", len(baer), sorted(set(baer.fire + " " + baer.year.astype(str))) if len(baer) else [])
# USGS post-fire debris-flow hazard (combined likelihood and volume class) for channels below burns of the last 4
# years; the hazard fades as the slopes revegetate
dfh = esri("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/USGS_Post_Fire_Hazard_Assessment_Data/"
           "FeatureServer/5", fields="SCH_Legend,fire_id")
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
           fields="ownerclassification,forestname")
if not len(own):   # no national forest in the area (northeastern Connecticut)
    own = gpd.GeoDataFrame({"ownerclassification": pd.Series(dtype=str), "forestname": pd.Series(dtype=str)}, geometry=[], crs=CRS)
nonfs = own[~own.ownerclassification.str.contains("USDA FOREST SERVICE", case=False, na=False)]
nonfs = nonfs[nonfs.area > 2000]  # skip slivers
nonfs.to_crs(4326).to_file(f"{CTX}/non_fs_land.gpkg")
# California Protected Areas Database (CPAD 2026a): parks and open space with their public access. Only restricted
# and no-public-access holdings are kept; land outside CPAD and outside the national forests is private.
if has("cpad"):
    cpad = esri("https://gis.cnra.ca.gov/arcgis/rest/services/Boundaries/CPAD_AccessType/MapServer/0",
                where="ACCESS_TYP <> 'Open Access'", fields="ACCESS_TYP,UNIT_NAME,MNG_AGNCY")
else:   # outside California: PAD-US (USGS), holdings recorded as restricted (RA) or closed (XA) to the public.
    #     Most eastern holdings are "unknown" (UK) there: those aren't flagged
    cpad = esri("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS_Public_Access/FeatureServer/0",
                where="Pub_Access IN ('RA','XA')", fields="Pub_Access,Unit_Nm,MngNm_Desc")
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
cpad.to_crs(4326).to_file(f"{CTX}/cpad_restricted.gpkg")
print("restricted / no public access holdings (CPAD in California, PAD-US elsewhere):", len(cpad), cpad.ACCESS_TYP.value_counts().to_dict() if len(cpad) else {})
print("wilderness", list(wild.wilderness), "| non-FS parcels in forests", len(nonfs),
      nonfs.ownerclassification.value_counts().to_dict())

# ---- critical habitat ----
fws = esri("https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer/0",
           fields="comname,unitname,effectdate")
CA = has("cdfw_trout")
if len(fws):
    fws = fws[fws.comname.isin(AQUATIC) if CA else fws.comname.fillna("").str.contains(AQUATIC_RE)]
fws = fws.rename(columns={"comname": "species", "unitname": "unit"}) if len(fws) else fws.assign(species=None, unit=None)
nmfs = esri("https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/NMFS_ESA_Critical_Habitat_gdb/FeatureServer/0",
            where="COMNAME LIKE '%teelhead%'", fields="COMNAME,LISTENTITY") if CA else gpd.GeoDataFrame(geometry=[], crs=CRS)
nmfs = nmfs.assign(species="Southern California steelhead", unit=nmfs.get("LISTENTITY"))
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
trout = esri("https://services2.arcgis.com/Uq9r85Potqm3MfRV/arcgis/rest/services/biosds1356_fpu/FeatureServer/0",
             fields="Name,Designation,Designation_Boundary") if CA else []
if not len(trout):   # outside California: each state's trout waters and the brook trout patches (troutdata.py)
    trout = troutdata.waters()
if "broad" not in trout:
    trout["broad"] = False
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
hwt = esri(f"{BIOS}/HWT_Project_Map_WFL1/FeatureServer/14", fields="ProjectYear,WaterName,SpeciesPresent") if CA else []
if len(hwt):   # CDFW Heritage & Wild Trout Program: electrofishing / snorkel surveys and what they found
    spp = hwt.SpeciesPresent.fillna("").str.strip()
    found = spp.str.contains("trout", case=False)
    yr_ = pd.to_numeric(hwt.ProjectYear, errors="coerce")
    ev.append(hwt.assign(kind="CDFW survey", water=hwt.WaterName.str.strip(), year=yr_, trout=found, lake=False, url=None,
                         label=[f"CDFW survey {y:.0f}: " + (sp if t else "no trout found"
                                                            + (f" (found {sp})" if sp and sp.lower() != "none" else ""))
                                for y, sp, t in zip(yr_, spp, found)]))
plant = esri(f"{BIOS}/biosds2897_fmu/FeatureServer/0", fields="WaterName,WeekOfPlantStart,FishType") if CA else []
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
                                   for n, d in zip(pg.n, pg["last"])]))
ev += troutdata.evidence()     # the other states' surveys and stocking (none in California)
def inat(taxon):
    """Research-grade iNaturalist sightings of a taxon in the study box with an exact (not obscured) location."""
    rows, above = [], 0
    for _ in range(50):
        res = None
        for attempt in range(3):
            try:
                r = requests.get("https://api.inaturalist.org/v1/observations", headers=UA, timeout=120, params=dict(
                    taxon_name=taxon, quality_grade="research", swlat=S, swlng=W, nelat=N, nelng=E, per_page=200,
                    order_by="id", order="asc", id_above=above))
                res = r.json()["results"]
                break
            except (requests.RequestException, ValueError, KeyError):
                time.sleep(10 * (attempt + 1))
        if res is None:
            raise RuntimeError("iNaturalist failed")
        rows += [o for o in res if o.get("location") and not o.get("obscured")
                 and (o.get("positional_accuracy") or 0) <= 500]
        if len(res) < 200:
            return rows
        above = res[-1]["id"]
        time.sleep(1.1)   # iNaturalist asks API users for about one request a second
    return rows
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
               for o, t in zip(obs, tx)]),
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
    trout_ev = trout_ev[["kind", "water", "year", "trout", "lake", "label", "url", "air_aug", "geometry"]]
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

def trout_attrs(s):
    """Per reach: latest year trout were found (CDFW survey, stocking, iNaturalist), latest CDFW survey year that
    found none, and a summary. Surveys and stocking count for the creek of the same name within 5 km of the point
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
        hits += [(sid, e.kind, e.year, e.trout, e.label) for sid in s.sid[sel]]
    if not hits:
        return out
    h = pd.DataFrame(hits, columns=["sid", "kind", "year", "trout", "label"])
    pos, neg = h[h.trout], h[~h.trout & h.kind.str.endswith("survey")]
    out["trout_found"] = out.sid.map(pos.groupby("sid").year.max())
    out["trout_absent"] = out.sid.map(neg.groupby("sid").year.max())
    def summary(g):
        parts = list(dict.fromkeys(g[g.kind != "iNaturalist"].sort_values("year", ascending=False).label))[:3]
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
    t1 = requests.get(TCC, params={"f": "json"}, headers=UA, timeout=120).json()["timeInfo"]["timeExtent"][1]
    x0, y0, x1, y1 = REGIONS[r]["bbox"]
    w_, h_ = int(np.ceil((x1 - x0) / 30)), int(np.ceil((y1 - y0) / 30))
    arr = np.full((h_, w_), 255, np.uint8)
    for ty in range(0, h_, tile):
        for tx in range(0, w_, tile):
            w, h = min(tile, w_ - tx), min(tile, h_ - ty)
            bb = (x0 + tx * 30, y1 - (ty + h) * 30, x0 + (tx + w) * 30, y1 - ty * 30)
            for attempt in range(4):
                try:
                    rr = requests.get(f"{TCC}/exportImage", headers=UA, timeout=300, params=dict(
                        bbox=",".join(map(str, bb)), bboxSR=EPSG, imageSR=EPSG, size=f"{w},{h}", format="tiff",
                        pixelType="U8", interpolation="RSP_NearestNeighbor", time=t1, f="image"))
                    with rasterio.MemoryFile(rr.content) as mf, mf.open() as src:
                        a = src.read(1)
                    break
                except Exception:
                    time.sleep(15 * (attempt + 1))
            else:
                raise RuntimeError("canopy cover download failed")
            arr[ty:ty + min(h, a.shape[0]), tx:tx + min(w, a.shape[1])] = a[:h, :w]
    with rasterio.open(p_ + ".tmp", "w", driver="GTiff", height=h_, width=w_, count=1, dtype="uint8", crs=CRS,
                       transform=from_origin(x0, y1, 30, 30), nodata=255, compress="deflate") as dst:
        dst.write(arr, 1)
    os.replace(p_ + ".tmp", p_)
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
# number of requests an hour (1,000 without a key); a free key from https://api.waterdata.usgs.gov/signup/ in
# USGS_API_KEY raises that, and is sent only to this API.
WDAPI = "https://api.waterdata.usgs.gov"
def get(url, tries=4, **params):
    """GET with retries: the USGS and CDEC servers drop connections now and then. A server over its request limit
    (HTTP 429) is waited out as long as it asks, twice at most."""
    key = os.environ.get("USGS_API_KEY") if url.startswith(WDAPI) else None
    hdr, waits = {**UA, **({"X-Api-Key": key} if key else {})}, 0
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=hdr, timeout=300, params=params)
            if r.ok:
                return r
            if r.status_code == 429 and waits < 2:
                s = r.headers.get("Retry-After", "")
                s = int(s) if s.isdigit() else 600
                print(f"{url.split('/')[2]} is rate limiting: waiting {s // 60 + 1} min", flush=True)
                time.sleep(s + 5)
                waits += 1
                continue
        except requests.RequestException:
            pass
        time.sleep(10 * (attempt + 1))
    return None
def chunks(xs, n):
    """Site ids go in the URL, and long URLs are refused (83 ids in one statistics request got a 403)."""
    return [xs[i:i + n] for i in range(0, len(xs), n)]
# Latest discharge of each gauge in the box that reported in the last 183 days: the API also keeps long-retired gauges
# with their last reading (WaterServices' siteStatus=active left those out). Times come in UTC.
lc = get(f"{WDAPI}/ogcapi/v1/collections/latest-continuous/items", f="json", bbox=f"{W:.4f},{S:.4f},{E:.4f},{N:.4f}",
         parameter_code="00060", time="P183D", properties="monitoring_location_id,time,value", limit=10000).json()
rows = []
for ft in lc["features"]:
    pr, (lon, lat) = ft["properties"], ft["geometry"]["coordinates"][:2]
    rows.append(dict(site=pr["monitoring_location_id"].removeprefix("USGS-"), name="",
                     cfs=pd.to_numeric(pr["value"], errors="coerce"),
                     time=pd.Timestamp(pr["time"]).tz_convert("America/Los_Angeles").strftime("%Y-%m-%d %H:%M"),
                     lon=lon, lat=lat))
gauges = gpd.GeoDataFrame(rows, geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]), crs=4326)
gauges = gauges[gauges.to_crs(CRS).intersects(area_u)].sort_values("site").drop_duplicates("site")
gauges = gauges[gauges.cfs >= 0]
names = {}   # the latest values don't carry the station name
for ids in chunks(list("USGS-" + gauges.site), 40):
    ml = get(f"{WDAPI}/ogcapi/v1/collections/monitoring-locations/items", f="json", id=",".join(ids),
             properties="monitoring_location_name", skipGeometry="true", limit=1000).json()
    names.update({ft["id"].removeprefix("USGS-"): ft["properties"]["monitoring_location_name"] for ft in ml["features"]})
gauges["name"] = gauges.site.map(names).fillna("").str.title()
# diversions, flumes, spillways and tunnels measure plumbing, not the creek
gauges = gauges[~gauges.name.str.contains(r"\b(?:Div|Diversion|Spill|Spillway|Forebay|Flume|Tunnel|Supp)\b", case=False)]
today = dt.date.today()
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
st = day_stats(list(gauges.site))
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
try:
    js = [] if not CDEC else get("https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet", Stations=",".join(c[0] for c in CDEC),
             SensorNums=",".join(str(c[1]) for c in CDEC), dur_code="H", Start=(today - dt.timedelta(days=3)).isoformat(),
             End=(today + dt.timedelta(days=1)).isoformat()).json()
except (AttributeError, ValueError):
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
gauges.to_file(f"{CTX}/gauges.gpkg")
print("gauges", len(gauges), gauges.status.value_counts().to_dict())

# ---- per-reach / per-drop attributes ----
fire_s = fires.sort_values("year", ascending=False)
def attrs(gdf, key, buf):
    g = gdf[[key, "geometry"]].copy()
    g["geometry"] = g.buffer(buf)
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
    t = gpd.sjoin(g, trout[["Name", "Designation", "broad", "geometry"]], predicate="intersects")
    t["label"] = (t.Designation + ": " + t.Name).str.replace(r": $", "", regex=True)
    # one label per reach: a mapped stream's designation before a catchment-wide one, and of those the one that
    # covers most of the reach (at a confluence the neighbouring river's line clips the reach too)
    t["cover"] = shapely.area(shapely.intersection(t.geometry.values, trout.geometry.reindex(t.index_right).values))
    t = t.sort_values(["broad", "cover"], ascending=[True, False])
    out["trout_water"] = out[key].map(t.groupby(key).label.first())
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
            out["debris_flow"] = out[key].map(top.hz.map({1: "low", 2: "moderate", 3: "high"})
                                              + " (" + top.year.astype(int).astype(str) + " fire)")
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
          f"{cs.crit_habitat.notna().mean():.0%} | wild trout {cs.trout_water.notna().sum()} | trout found "
          f"{cs.get('trout_found', pd.Series(dtype=float)).notna().sum()}, none found "
          f"{cs.get('trout_absent', pd.Series(dtype=float)).notna().sum()} | burn severity "
          f"{cs.get('burn_sev', pd.Series(dtype=float)).notna().sum()} | debris-flow "
          f"{cs.get('debris_flow', pd.Series(dtype=object)).notna().sum()} | canopy median {np.nanmedian(cs.canopy_pct):.0f}% | "
          f"August air {np.nanmin(cs.air_aug):.1f}-{np.nanmax(cs.air_aug):.1f} C, above the heat gate "
          f"{int((cs.air_aug > HEAT_START).sum())}")
