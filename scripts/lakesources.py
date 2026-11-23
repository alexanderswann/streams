"""Lake facts from national and state sources, for 05d_lakes.py (each checked against the live service on 2026-11-19).

nla_depths(bounds_ll)   EPA National Lakes Assessment, all four cycles (2007, 2012, 2017, 2022): the sonar depth at
                        each lake's index site, which for a natural lake is the deepest spot the crew found and for a
                        reservoir a mid-lake site (a lower bound). Cached in data/raw/_national/nla/.
extras(area, bounds_ll) The state's lake access and rules, as points or polygons with kind ("access", "rules",
                        "designation"), text and url:
    ne_ct         CT DEEP boat launches; lake designations of the fisheries management areas (trout management lakes
                  and the like)
    central_vt    Vermont Fish & Wildlife fishing access areas; special-regulation and restricted lakes and ponds
    lexington_va  Virginia DWR public fishing lakes (with the boat and motor rules and the agency page)
    se_pa         PFBC access points at lakes (ramps, piers, motor rules; with credit to PFBC, as its licence asks), DCNR
                  state park boat launches, PFBC lake special regulations (Big Bass, Panfish Enhancement) and boating
                  rules (no gasoline motors)
    smokies       NCWRC's Public Mountain Trout Waters impoundments: the class (Hatchery Supported, Delayed Harvest...)
agency_lakes(area, bounds_ll)  A state's own list of trout lakes as outlines, for 05d_lakes.py's step 2 (as Wyoming Game
                        & Fish's guide is used there): a listed lake is kept whatever its size, and one NHD has no lake
                        for keeps the agency's outline. Columns agency, agency_id (stable: agency and name), agency_name.
    smokies       NCWRC's Public Mountain Trout Waters impoundments (Cheoah Reservoir: NHD draws it as river; Max Patch
                  Pond, 0.5 ha)
    se_pa         PFBC's stocked trout lakes (approved trout waters)
    ne_ct         CT DEEP's stocked trout lakes (Connecticut_Stocked_Lakes; 2026-11-23: four stocked ponds under the 1 ha
                  floor were missing, Lower Storrs Pumping Station, Paine, Pasture and Mansfield Training Ponds)
Stocking and fish surveys at lakes come from 11_context.py's trout evidence (troutdata.py), read by maplakes.py.
"""
import os, re, json, time, requests, numpy as np, pandas as pd, geopandas as gpd
from config import NATIONAL, SHARED
from geomatch import esri
import netfetch

UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
NLA_DIR = f"{NATIONAL}/nla"
NLA = {  # cycle: (url, the columns that hold latitude, longitude, depth, date; how the depth was measured)
    2007: ("https://www.epa.gov/sites/default/files/2014-01/nla2007_sampledlakeinformation_20091113.csv",
           ("FLD_LAT_DD", "FLD_LON_DD", "DEPTHMAX", "DATE_COL"), "deepest depth found"),
    2012: ("https://www.epa.gov/sites/default/files/2016-12/nla2012_wide_profile_08232016.csv",
           ("INDEX_LAT_DD", "INDEX_LON_DD", "INDEX_SITE_DEPTH", "DATE_COL"), "sonar at the index site"),
    2017: ("https://www.epa.gov/sites/default/files/2021-04/nla_2017_profile-data.csv",
           ("INDEX_LAT_DD", "INDEX_LON_DD", "INDEX_SITE_DEPTH", "DATE_COL"), "sonar at the index site"),
    2022: ("https://www.epa.gov/system/files/other-files/2024-04/nla22_siteinfo.csv",
           ("INDEX_LAT_DD", "INDEX_LON_DD", "INDEX_SITE_DEPTH", "DATE_COL"), "sonar at the index site"),
}


def _fetch(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for attempt in range(4):
            try:
                r = netfetch.get(url, headers=UA, timeout=300)
                if r.ok:
                    with open(path + ".tmp", "wb") as f:
                        f.write(r.content)
                    os.replace(path + ".tmp", path)
                    break
            except requests.RequestException:
                pass
            if attempt < 3:
                netfetch.wait(10 * (attempt + 1), url)
    return path


def nla_depths(bounds_ll):
    """Points (EPSG:4326): cycle, site, date, depth_m, method; inside the lon/lat box."""
    w, s, e, n = bounds_ll
    out = []
    for cyc, (url, (la, lo, dp, dt), how) in NLA.items():
        p = _fetch(url, f"{NLA_DIR}/{url.split('/')[-1]}")
        if not os.path.exists(p):
            continue
        t = pd.read_csv(p, low_memory=False, encoding="latin-1")
        if la not in t:      # the 2007 file gives the lake's point where no field point was taken
            la, lo = "LAT_DD", "LON_DD"
        t["lat"], t["lon"] = pd.to_numeric(t[la], errors="coerce"), pd.to_numeric(t[lo], errors="coerce")
        t["depth_m"] = pd.to_numeric(t[dp], errors="coerce")
        t = t[(t.lon >= w) & (t.lon <= e) & (t.lat >= s) & (t.lat <= n) & (t.depth_m > 0)]
        if not len(t):
            continue
        t = t.groupby(["SITE_ID", "DATE_COL"]).agg(lat=("lat", "first"), lon=("lon", "first"), depth_m=("depth_m", "max")).reset_index()
        out.append(pd.DataFrame({"cycle": cyc, "site": t.SITE_ID, "date": pd.to_datetime(t.DATE_COL, errors="coerce").dt.date.astype(str),
                                 "depth_m": t.depth_m.round(1), "method": how, "lat": t.lat, "lon": t.lon}))
    if not out:
        return gpd.GeoDataFrame({"cycle": []}, geometry=[], crs=4326)
    t = pd.concat(out, ignore_index=True)
    return gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(t.lon, t.lat), crs=4326)


CT = "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services"
VT = "https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASFISHWILDLIFE_WM_NOCACHE/MapServer"
VA = "https://services.dwr.virginia.gov/arcgis/rest/services/HUB_Layers"


def _g(url, bb, fields, where="1=1"):
    try:
        g = esri(url, bb, fields, where)
    except Exception as ex:                       # a state service that is down leaves its facts out, not the lakes
        print(f"  lake source unavailable: {url.split('/services/')[-1]} ({str(ex)[:80]})")
        return None
    return gpd.GeoDataFrame(g, crs=4326) if len(g) else None


def extras(area, bounds_ll):
    parts = []
    if area == "ne_ct":
        b = _g(f"{CT}/Connecticut_DEEP_Boat_Launches/FeatureServer/0", bounds_ll, "LAUNCHNAME,LAUNCHTYPE,LINK")
        if b is not None:
            parts.append(b.assign(kind="access", text="Boat launch: " + b.LAUNCHNAME.fillna("CT DEEP") +
                                  b.LAUNCHTYPE.fillna("").map(lambda v: f" ({v.lower()})" if v else ""), url=b.LINK))
        m = _g(f"{CT}/Fisheries_management_Areas/FeatureServer/1", bounds_ll, "FISH_TYPE,MGMT_AREA,COMMENT")
        if m is not None:
            parts.append(m.assign(kind="designation", text=(m.MGMT_AREA.fillna("") + m.COMMENT.fillna("").map(
                lambda v: f" ({v})" if v else "")).str.strip() + " (CT DEEP)", url=None))
    elif area == "central_vt":
        # Vermont's map server refuses paged queries: troutdata.fetch asks for the ids first, then the features
        import troutdata
        def _vt(key, lyr, fields):
            try:
                g = troutdata.fetch(key, f"{VT}/{lyr}", fields=fields)
            except Exception as ex:
                print(f"  lake source unavailable: Vermont layer {lyr} ({str(ex)[:80]})")
                return None
            return g.to_crs(4326) if len(g) else None
        a = _vt("lake_vt_access", 2, "AccessName,WaterBody,AccessType,RampType")
        if a is not None:
            parts.append(a.assign(kind="access", text="Fishing access area: " + a.AccessName.fillna(a.WaterBody).fillna("") +
                                  a.RampType.fillna("").map(lambda v: f" ({v.lower()} ramp)" if v and v.lower() != "none" else ""),
                                  url=None))
        r = _vt("lake_vt_specialregs", 32, "*")
        if r is not None:
            parts.append(gpd.GeoDataFrame({"kind": "rules", "text": "Special fishing regulations (Vermont Fish & Wildlife)",
                                           "url": "https://vtfishandwildlife.com/fish/fishing-regulations"},
                                          index=r.index, geometry=r.geometry, crs=4326))
        x = _vt("lake_vt_restricted", 47, "Name,Type")
        if x is not None:
            parts.append(x.assign(kind="rules", text="Restricted: " + x.Type.fillna("restricted water") + " (Vermont Fish & Wildlife)", url=None))
    elif area == "lexington_va":
        p = _g(f"{VA}/DWR_Public_Fishing_Lakes/FeatureServer/0", bounds_ll, "NAME,Boat_Motor,URL")
        if p is not None:
            parts.append(p.assign(kind="designation", text="Virginia DWR public fishing lake" + p.Boat_Motor.fillna("").map(
                lambda v: f" ({v.lower()})" if v else ""), url=p.URL))
    elif area == "se_pa":
        PF = "https://fbweb.pa.gov/arcgis/rest/services/PFBC_Map_Services"
        # PFBC's access points at lakes (its own lake-access flag, or a lake for the water: the rest are on creeks and
        # rivers, and one by a riverside pond would be pinned to the pond). Used with credit to PFBC, as its licence asks
        a = _g(f"{PF}/Access/MapServer/0", bounds_ll, "ACC_NAME,WATERBODY,RAMP,PIER,DOCK,SHORE_FISH,HP_FullDesc,PALakes_Access")
        if a is not None:
            a = a[a.PALakes_Access.fillna("").eq("Y") | a.WATERBODY.fillna("").str.contains(r"(?i)\b(?:lake|pond|reservoir)\b")]
            what = lambda r: ", ".join(w for w, f in (("boat ramp", r.RAMP), ("pier", r.PIER), ("dock", r.DOCK),
                                                      ("shore fishing", r.SHORE_FISH)) if str(f).upper() == "Y")
            parts.append(a.assign(kind="access", text=[
                f"Fishing access: {r.ACC_NAME or r.WATERBODY}" + (f" ({what(r)})" if what(r) else "")
                + (f"; {r.HP_FullDesc.lower()}" if isinstance(r.HP_FullDesc, str) and r.HP_FullDesc.strip() else "") + " (PFBC)"
                for r in a.itertuples()], url=None))
        # DCNR's state park boat launches (positions only: PFBC's Scotts Run Lake point lies 1.4 km from the lake)
        d = _g("https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/boat_launch/MapServer/0", bounds_ll, "OBJECTID")
        if d is not None:
            parts.append(d.assign(kind="access", text="Boat launch (state park, DCNR)", url=None))
        # lake special regulations (Big Bass, Panfish Enhancement) and boating rules ("MT": no internal-combustion motors)
        r = _g(f"{PF}/Special_Regulations/MapServer/3", bounds_ll, "WtrName,Spec_Reg_1,Spec_Reg_2,Reg_Link_1")
        if r is not None:
            parts.append(r.assign(kind="rules", text=[" and ".join(x.strip() for x in (a_, b_) if isinstance(x, str) and x.strip())
                                                     + " (PFBC)" for a_, b_ in zip(r.Spec_Reg_1, r.Spec_Reg_2)],
                                  url=r.Reg_Link_1))
        b = _g(f"{PF}/Boating_Spec_Regs/MapServer/2", bounds_ll, "WTRNAME,SPECREG_TYPE,SPECREG_TYPE2,SPECREG_TYPE3,SPECREG_TYPE4,SPECREG_TYPE5")
        if b is not None:
            mt = b[[c for c in b.columns if c.startswith("SPECREG_TYPE")]].fillna("").eq("MT").any(axis=1)
            if mt.any():
                parts.append(b[mt].assign(kind="rules", text="No gasoline motors (PFBC boating rules)", url=None))
    elif area.startswith("adk_"):
        # DEC's lake fishing list (data.ny.gov, open terms): launch type, hike-in, bait and motor rules, its contour map
        gd = ny_guide(bounds_ll)
        if len(gd):
            lt = gd.boat_launc.fillna("").str.strip()
            a = gd[lt.ne("") & lt.str.lower().ne("none")]
            if len(a):
                parts.append(a.assign(kind="access", text="Boat launch: " + a.boat_launc.str.lower().str.replace(" - ", ", ") + " (NYSDEC)",
                                      url=a.bl_weblink if "bl_weblink" in a else None))
            cm = gd.comments.fillna("")
            h = gd[cm.str.contains("hike in", case=False)]
            if len(h):
                parts.append(h.assign(kind="access", text="Hike-in water (NYSDEC)", url=None))
            rl = cm.str.split(" - ").map(lambda v: [x.strip() for x in v if x.strip() and not re.search(
                r"(?i)hike in|accessible features|canoe portage", x)])
            r = gd[rl.map(len) > 0]
            if len(r):
                parts.append(r.assign(kind="rules", text=rl[rl.map(len) > 0].map(lambda v: "; ".join(v) + " (NYSDEC)"),
                                      url=r.spec_regs if "spec_regs" in r else None))
            for col, what in (("contourmap", "DEC contour map"), ("weblink", "DEC page")):
                if col in gd:
                    k = gd[gd[col].notna()]
                    if len(k):
                        parts.append(k.assign(kind="links", text=k[col], url=k[col]))
        # DEC's boat launches, fishing access sites and piers (data.ny.gov facility assets)
        fa = ny_facilities(bounds_ll)
        if len(fa):
            parts.append(fa.assign(kind="access", text=fa.asset.str.capitalize() + ": " + fa["name"].str.title()
                                   + " (" + fa.facility.str.title() + ", NYSDEC)", url=None))
    elif area == "smokies":
        NC_ = "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services"
        b = _g(f"{NC_}/NCWRC_Boating_Access_Areas_view/FeatureServer/0", bounds_ll,
               "BAA_Name,Water_Access,Launch_Lane_No,Fishing_Pier,Site_Status,Website")
        if b is not None:
            b = b[~b.Site_Status.fillna("").str.contains("closed", case=False)]
            parts.append(b.assign(kind="access", text="Boating access: " + b.BAA_Name.fillna(b.Water_Access).fillna("NCWRC")
                                  + b.Fishing_Pier.fillna("").map(lambda v: ", fishing pier" if str(v).lower() in ("yes", "y", "1") else "")
                                  + " (NCWRC)", url=b.Website))
        f = _g(f"{NC_}/NCWRC_Public_Fishing_Areas_view/FeatureServer/0", bounds_ll, "PFA_Name,Water_Access,Waterbody_Type,Site_Status")
        if f is not None:
            f = f[f.Waterbody_Type.fillna("").str.upper().isin(["LAKE", "POND"]) & ~f.Site_Status.fillna("").str.contains("closed", case=False)]
            parts.append(f.assign(kind="access", text="Public fishing area: " + f.PFA_Name.fillna(f.Water_Access).fillna("NCWRC") + " (NCWRC)",
                                  url=None))
        t = _g("https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services/AllAccessSites/FeatureServer/0", bounds_ll,
               "Name,Waterway,Type,Ramps,FishingPier")
        if t is not None:
            t = t[t.Type.fillna("").ne("Attention")]
            parts.append(t.assign(kind="access", text=t.Type.fillna("Access") + ": " + t.Name.fillna(t.Waterway).fillna("") + " (TWRA)",
                                  url=None))
        v = _g("https://services.arcgis.com/w8auYAijfGK1Mydj/ArcGIS/rest/services/TVA_Recreation_Layers_Hosted/FeatureServer/0",
               bounds_ll, "TRINAMETX_LAND")
        if v is not None:
            parts.append(v.assign(kind="access", text="Boat ramp: " + v.TRINAMETX_LAND.fillna("TVA").str.title() + " (TVA)", url=None))
        q = _g("https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services/TWRA_Reciprocal_Fishing_Agreement_Areas/FeatureServer/0",
               bounds_ll, "*")
        if q is not None:
            parts.append(q.assign(kind="rules", text="From a boat, a North Carolina or Tennessee fishing licence is valid "
                                  "(reciprocal agreement, TWRA)", url=None))
        k = _nc_impoundments()
        if k is not None:
            parts.append(k.assign(kind="designation", text=k.cls + " trout water" + k.cls.str.contains(
                "Hatchery Supported|Delayed Harvest", case=False).map({True: ": NCWRC stocks it each season", False: ""})
                + k.reach.map(lambda v: f" ({v})" if v and v.lower() != "entire impoundment" else "") + " (NCWRC)",
                url="https://www.ncwildlife.gov/fishing/where-fish/public-mountain-trout-waters"))
    if not parts:
        return gpd.GeoDataFrame({"kind": [], "text": [], "url": []}, geometry=[], crs=4326)
    return gpd.GeoDataFrame(pd.concat([q[["kind", "text", "url", "geometry"]] for q in parts], ignore_index=True), crs=4326)


def _nc_impoundments():
    """NCWRC's Public Mountain Trout Waters impoundments in the area (EPSG:4326): name, class, reach; or None. Not the
    game lands' blanket "Wild Trout Waters unless otherwise noted" (troutdata.py leaves it out too)."""
    import troutdata
    yr, svc = troutdata._ncwrc_newest("Impoundments")
    try:
        k = troutdata.fetch(f"nc_pmtw_lakes_{yr}", f"{troutdata.NCWRC}/{svc}/FeatureServer/0",
                            fields="WRC_Class,DISPL_NAME,Reg_Descri")
    except Exception as ex:
        print(f"  lake source unavailable: NCWRC impoundments ({str(ex)[:80]})")
        return None
    if not len(k):
        return None
    k = k[~k.Reg_Descri.fillna("").str.contains("unless otherwise noted", case=False) & k.DISPL_NAME.fillna("").str.strip().ne("")]
    if not len(k):
        return None
    return gpd.GeoDataFrame({"name": k.DISPL_NAME.str.strip(),
                             "cls": k.WRC_Class.fillna("").str.replace(r"\s*Trout Waters$", "", regex=True).str.strip(),
                             "reach": k.Reg_Descri.fillna("").str.strip()}, geometry=k.geometry, crs=k.crs).to_crs(4326)


def agency_lakes(area, bounds_ll):
    """The state's own list of trout lakes as outlines (EPSG:4326): agency, agency_id, agency_name, geometry."""
    rows = []
    if area == "smokies":
        k = _nc_impoundments()
        if k is not None:
            rows.append(gpd.GeoDataFrame({"agency": "NCWRC", "agency_id": "NCWRC:" + k["name"], "agency_name": k["name"]},
                                         geometry=k.geometry, crs=4326))
    elif area == "se_pa":
        import troutdata
        try:
            k = troutdata.fetch("pa_stocked_lakes", f"{troutdata.PFBC}/PFBC_Stocked_Trout_Waters/MapServer/5",
                                fields="WtrName,GNIS_NAME")
        except Exception as ex:
            print(f"  lake source unavailable: PFBC stocked lakes ({str(ex)[:80]})")
            k = None
        if k is not None and len(k):
            nm = k.WtrName.fillna(k.GNIS_NAME).fillna("").str.strip()
            k, nm = k[nm.ne("")], nm[nm.ne("")]
            rows.append(gpd.GeoDataFrame({"agency": "PFBC", "agency_id": "PFBC:" + nm, "agency_name": nm},
                                         geometry=k.geometry, crs=k.crs).to_crs(4326))
    elif area == "ne_ct":
        import troutdata
        try:
            k = troutdata.fetch("ct_stocked_lakes", f"{troutdata.CT}/Connecticut_Stocked_Lakes/FeatureServer/0", fields="*")
        except Exception as ex:
            print(f"  lake source unavailable: CT DEEP stocked lakes ({str(ex)[:80]})")
            k = None
        if k is not None and len(k):
            nm = k.LAKES_WATERBODY.fillna("").astype(str).str.strip()
            k, nm = k[nm.ne("")], nm[nm.ne("")]
            rows.append(gpd.GeoDataFrame({"agency": "CT DEEP", "agency_id": "CTDEEP:" + nm, "agency_name": nm},
                                         geometry=k.geometry, crs=k.crs).to_crs(4326))
    if not rows:
        return gpd.GeoDataFrame({"agency": [], "agency_id": [], "agency_name": []}, geometry=[], crs=4326)
    g = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs=4326)
    g = g[g.geometry.notna() & ~g.geometry.is_empty & g.geom_type.isin(["Polygon", "MultiPolygon"])]
    return g.drop_duplicates("agency_id").reset_index(drop=True)



# ---- New York: data.ny.gov (OPEN-NY terms: free reuse). DEC's own ArcGIS layers say "secondary distribution of the
# data is not allowed", so lake facts come from these instead ----
NYDATA = "https://data.ny.gov/resource"
TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"


def _socrata(dsid, where=None, limit=50000):
    """Rows of a data.ny.gov dataset, cached a week in the area's cache."""
    os.makedirs(f"{SHARED}/cache", exist_ok=True)
    p = f"{SHARED}/cache/ny_{dsid}.json"
    if os.path.exists(p) and os.environ.get("REFRESH") != "1" and time.time() - os.path.getmtime(p) < 7 * 86400:
        return json.load(open(p))
    def fetch():     # written only from the whole answer; a refresh that fails keeps the earlier copy
        rows, off = [], 0
        while True:
            prm = {"$limit": limit, "$offset": off}
            if where:
                prm["$where"] = where
            got = netfetch.fetch("GET", f"{NYDATA}/{dsid}.json", params=prm, headers=UA, timeout=180).json()
            rows += got
            off += limit
            if len(got) < limit:
                break
        with open(p + ".tmp", "w") as f:
            json.dump(rows, f)
        os.replace(p + ".tmp", p)
        return rows
    rows = netfetch.keep_old(p, fetch, f"data.ny.gov {dsid}")
    if rows is None:
        return json.load(open(p))
    return rows


def ny_guide(bounds_ll):
    """DEC's lake and pond fishing list (data.ny.gov mw8j-wduf): water, acres, fish species, boat launch, comments (hike
    in, bait and motor rules), links; points (EPSG:4326) inside the lon/lat box."""
    w, s, e, n = bounds_ll
    try:
        rows = _socrata("mw8j-wduf")
    except Exception as ex:
        print(f"  lake source unavailable: data.ny.gov mw8j-wduf ({str(ex)[:80]})")
        rows = []
    t = pd.DataFrame([{k: (v.get("url") if isinstance(v, dict) else v) for k, v in r.items() if not k.startswith(":")}
                      for r in rows if r.get("point_x") and r.get("point_y")])
    if not len(t):
        return gpd.GeoDataFrame({"water": []}, geometry=[], crs=4326)
    t["x"], t["y"] = pd.to_numeric(t.point_x, errors="coerce"), pd.to_numeric(t.point_y, errors="coerce")
    t = t[(t.x >= w) & (t.x <= e) & (t.y >= s) & (t.y <= n)].copy()
    for c in ("boat_launc", "comments", "fish_speci", "contourmap", "weblink", "spec_regs", "bl_weblink"):
        if c not in t:
            t[c] = None
    return gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(t.x, t.y), crs=4326).reset_index(drop=True)


def ny_facilities(bounds_ll):
    """DEC's boat launches, fishing access sites and fishing piers (data.ny.gov yvkb-z58x, DEC facility assets)."""
    w, s, e, n = bounds_ll
    try:
        rows = _socrata("yvkb-z58x", where="asset in('BOAT LAUNCH','FISHING ACCESS SITE','FISHING PIER','ACCESSIBLE FISHING PIER',"
                                           "'ACCESSIBLE HAND LAUNCH','ACCESSIBLE FISHING PLATFORM')")
    except Exception as ex:
        print(f"  lake source unavailable: data.ny.gov yvkb-z58x ({str(ex)[:80]})")
        rows = []
    t = pd.DataFrame([{k: v for k, v in r.items() if k in ("facility", "name", "asset", "latitude", "longitude")} for r in rows])
    if not len(t):
        return gpd.GeoDataFrame({"asset": []}, geometry=[], crs=4326)
    t["x"], t["y"] = pd.to_numeric(t.longitude, errors="coerce"), pd.to_numeric(t.latitude, errors="coerce")
    t = t[(t.x >= w) & (t.x <= e) & (t.y >= s) & (t.y <= n)].fillna("")
    return gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(t.x, t.y), crs=4326).reset_index(drop=True)


def ny_stocking(bounds_ll):
    """DEC's actual stocking (data.ny.gov e52k-ymww, 2011 on: year, county, waterbody, town, month, number, species,
    size), for the counties in the box, and the box's towns as polygons (Census county subdivisions, with their county's
    name): (rows, towns). Stocked waters carry no coordinates: 05d_lakes.py finds each by name in its town."""
    try:
        cty = esri(f"{TIGER}/State_County/MapServer/1", bounds_ll, "NAME,BASENAME,STATE,COUNTY")
        cty = cty[cty.STATE == "36"]
        tw = esri(f"{TIGER}/Places_CouSub_ConCity_SubMCD/MapServer/1", bounds_ll, "BASENAME,STATE,COUNTY")
        tw = gpd.GeoDataFrame(tw[tw.STATE == "36"], crs=4326)
        names = dict(zip(cty.COUNTY, cty.BASENAME))
        tw["county"] = tw.COUNTY.map(names)
        cl = ",".join("'" + n.replace("'", "''") + "'" for n in sorted(set(names.values())))
        rows = _socrata("e52k-ymww", where=f"county in({cl})")
    except Exception as ex:
        print(f"  lake source unavailable: NY stocking list or towns ({str(ex)[:80]})")
        return pd.DataFrame(), gpd.GeoDataFrame({"BASENAME": []}, geometry=[], crs=4326)
    return pd.DataFrame(rows), tw[["BASENAME", "county", "geometry"]].rename(columns={"BASENAME": "town"})
