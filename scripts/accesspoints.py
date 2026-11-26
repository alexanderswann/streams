"""Official public fishing access sites and boat ramps, for 02e_access.py (the user, 2026-11-25: "official fishing
access points and boat ramps", where the states publish them). One table of points from the agencies that publish
them, each with a name, its type, the water, the source, a link and whether it has parking.

atype   "boat ramp"       a launch a trailered boat can use
        "hand launch"     a car-top, canoe or kayak launch (no trailer ramp)
        "walk-in access"  a shore or stream fishing access site, walked in from its parking
        "fishing pier"    a pier or platform to fish from
        "parking"         a parking area the agency keeps for anglers
parking True where the source says the site has a lot (or a car-top launch has its own spaces), False where it says
        there is none, None where it doesn't say. 08_hike.py starts approach routes at sites with parking.
status  the source's own word when the site is closed or limited ("closed", "seasonal"); None when it says nothing.

Sources, by the states an area's boxes reach into (sources.pick("gnis_states")), each credited in credits.py with its
terms; a source whose terms forbid reuse, or ask to be contacted first, is left out (New York DEC's ArcGIS layers:
data.ny.gov's copies are used; MassWildlife's own access layer; West Virginia DNR's, which forbids passing on its data;
Maryland DNR's public water access has no site in any map's boxes and is left out until one does):
    all     USFS recreation sites (fishing and boating sites), the National Park Service's points of interest (boat
            launches, canoe and kayak access, water access), TVA's boat ramps
    CA      CDFW's fishing guide: the public boat launches (California's Division of Boating and Waterways survey)
    WY      WGFD's fishing guide boat ramps, its Public Access Areas and their ramps and parking, its river access points
    ID      IDFG's fishing and boating access sites
    GA      Georgia DNR's water access points (boat ramps, bank fishing, canoe access)
    SC      SCDNR's public water access
    NC      NCWRC's boating access areas and public fishing areas
    TN      TWRA's access sites (boat launches and fishing sites)
    VA      Virginia DWR's boating access locations
    PA      PFBC's fishing and boating access areas (credit PFBC; the data are reduced to these fields)
    DE      DNREC's fishing access (FirstMap)
    CT      CT DEEP's boat launches
    MA      the Office of Fishing and Boating Access sites (MassGIS)
    RI      RIDEM's fishing and boating access (RIGIS)
    VT      Vermont Fish & Wildlife's fishing access areas (CC BY-SA 4.0: these points are shared under it too)
    NY      DEC's boat launches, fishing access sites and piers, its boat launch list and its Public Fishing Rights
            parking areas (data.ny.gov, Open NY terms)
A source that can't be read is left out with a note (as lakesources.py does), not the step.
"""
import os, re, json, time, numpy as np, pandas as pd, geopandas as gpd, shapely

EDW = "https://apps.fs.usda.gov/arcx/rest/services/EDW"
NPS_POI = "https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0"
TVA = "https://services.arcgis.com/w8auYAijfGK1Mydj/ArcGIS/rest/services/TVA_Recreation_Layers_Hosted/FeatureServer/0"
PFBC = "https://fbweb.pa.gov/arcgis/rest/services/PFBC_Map_Services/Access/MapServer/0"
CDFW = "https://services2.arcgis.com/Uq9r85Potqm3MfRV/arcgis/rest/services/FishingGuide/FeatureServer/0"
WGFD = "https://services6.arcgis.com/cWzdqIyxbijuhPLw/arcgis/rest/services"
IDFG = "https://gisportal-idfg.idaho.gov/hosting/rest/services/Access/IDFG_Fishing_and_Boating_Access_Sites_Public/FeatureServer/0"
GADNR = "https://services6.arcgis.com/9QlSLDqa0P1cHLhu/arcgis/rest/services/WRD_Water_Access_Points/FeatureServer/0"
SCDNR = ("https://services.arcgis.com/acgZYxoN5Oj8pDLa/arcgis/rest/services/"
         "South_Carolina_Public_Water_Access_PUBLIC_VIEW/FeatureServer/0")
NCWRC = "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services"
TWRA = "https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services/AllAccessSites/FeatureServer/0"
VADWR = "https://services.dwr.virginia.gov/arcgis/rest/services/HUB_Layers/DWR_Boating_Access_Locations/FeatureServer/0"
CTDEEP = "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Connecticut_DEEP_Boat_Launches/FeatureServer/0"
MAOFBA = "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/Office_of_Fishing_and_Boating_Access_Sites/FeatureServer/0"
RIGIS = "https://services2.arcgis.com/S8zZg9pg23JUEexQ/arcgis/rest/services/HYDRO_Fishing_Boating_Access_2024_spf/FeatureServer/0"
DNREC = "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Society/DE_Fishing_Access/FeatureServer/0"
COLS = ["name", "atype", "water", "source", "url", "parking", "status", "note", "geometry"]
TYPES = ("boat ramp", "hand launch", "walk-in access", "fishing pier", "parking")
yes = lambda v: str(v).strip().upper() in ("Y", "YES", "TRUE", "1")
clean = lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) and v.strip() else None


def _g(url, bb, fields, where="1=1"):
    from geomatch import esri          # here, so credits.py can read LEFT_OUT without the download modules
    try:
        g = esri(url, bb, fields, where)
    except Exception as ex:                       # a service that is down leaves its points out, not the step
        print(f"  access source unavailable: {url.split('/services/')[-1]} ({str(ex)[:80]})")
        return None
    return gpd.GeoDataFrame(g, crs=4326) if len(g) else None


def _title(v):
    """'NANTAHALA RIVER LAUNCH SITE' -> 'Nantahala River Launch Site'; names in mixed case are kept."""
    v = clean(v)
    if v and v.upper() == v:
        v = re.sub(r"\b[A-Z][A-Z']*\b", lambda m: m.group(0).capitalize(), v)
    return v


def _out(g, **cols):
    d = gpd.GeoDataFrame({k: (v if not callable(v) else [v(r) for r in g.itertuples()]) for k, v in cols.items()},
                         index=g.index, geometry=g.geometry.values, crs=4326)
    for c in COLS:
        if c not in d:
            d[c] = None
    return d[COLS]


def usfs(bb):
    """Forest Service fishing and boating sites (developed, existing), with the recreation page of a fishing or boating
    opportunity at the same place (within 300 m) as the link."""
    s = _g(f"{EDW}/EDW_InfraRecreationSites_01/MapServer/0", bb,
           "site_name,public_site_name,site_subtype,recarea_status,development_scale",
           where="site_subtype IN ('FISHING SITE','BOATING SITE') AND development_status='EXISTING'")
    if s is None:
        return None
    o = _g(f"{EDW}/EDW_RecreationOpportunities_01/MapServer/0", bb, "recareaname,recareaurl,markeractivity,openstatus",
           where="markeractivity IN ('Boating - Motorized','Boating - Non-Motorized','Lake and Pond Fishing',"
                 "'River and Stream Fishing')")
    url = pd.Series(None, index=s.index, dtype=object)
    if o is not None:
        j = gpd.sjoin_nearest(s[["geometry"]].to_crs(5070), o[["recareaurl", "geometry"]].to_crs(5070), how="left",
                              max_distance=300)
        url = j.groupby(level=0).recareaurl.first().reindex(s.index)
    name = [_title(a) or _title(b) for a, b in zip(s.public_site_name, s.site_name)]
    ramp = pd.Series(name, index=s.index).fillna("").str.contains(r"(?i)\bramp\b")
    return _out(s, name=name, atype=np.where(s.site_subtype.eq("FISHING SITE"), "walk-in access",
                                             np.where(ramp, "boat ramp", "hand launch")),
                source="USFS", url=url.fillna("https://www.fs.usda.gov/visit").values, parking=True,
                status=s.recarea_status.map(lambda v: v.lower() if isinstance(v, str) and re.search(r"(?i)closed", v) else None))


def nps(bb):
    """The National Park Service's points of interest: boat launches, canoe and kayak access, water access."""
    p = _g(NPS_POI, bb, "POINAME,POITYPE,POISTATUS,PUBLICDISPLAY,DATAACCESS,UNITCODE",
           where="POITYPE IN ('Boat Launch','Canoe / Kayak Access','Water Access','Fishing Pier')")
    if p is None:
        return None
    p = p[p.PUBLICDISPLAY.fillna("").str.contains("Public") & p.DATAACCESS.fillna("Unrestricted").eq("Unrestricted")]
    if not len(p):
        return None
    t = {"Boat Launch": "boat ramp", "Canoe / Kayak Access": "hand launch", "Water Access": "walk-in access",
         "Fishing Pier": "fishing pier"}
    return _out(p, name=p.POINAME.map(clean), atype=p.POITYPE.map(t), source="NPS",
                url=p.UNITCODE.map(lambda u: f"https://www.nps.gov/{u.lower()}/" if isinstance(u, str) else None),
                parking=p.POITYPE.eq("Boat Launch").map(lambda v: True if v else None),
                status=p.POISTATUS.map(lambda v: v.lower() if isinstance(v, str) and re.search(r"(?i)closed", v) else None))


def tva(bb):
    """TVA's boat ramps on its reservoirs."""
    v = _g(TVA, bb, "TRINAMETX_LAND")
    if v is None:
        return None
    return _out(v, name=v.TRINAMETX_LAND.map(lambda x: _title(re.sub(r"\s+\d{4,}$", "", x)) if isinstance(x, str) else None),
                atype="boat ramp", source="TVA",
                url="https://www.tva.com/environment/recreation", parking=True)


def pfbc(bb):
    """PFBC's fishing and boating access areas: ramps, piers and shore fishing; parking from its lot classes."""
    a = _g(PFBC, bb, "ACC_NAME,WATERBODY,RAMP,PIER,DOCK,SHORE_FISH,CABLE,PARKING,Parking_FullDesc,OWNERSHIP,Ftr_Page,"
                     "Ftr_Page_Name")
    if a is None:
        return None
    a = a[~a.OWNERSHIP.fillna("").str.contains(r"\bNJ")]          # New Jersey's sites on the far bank
    kind = np.where(a.RAMP.map(yes), "boat ramp", np.where(a.CABLE.map(yes) | a.DOCK.map(yes), "hand launch",
                    np.where(a.PIER.map(yes), "fishing pier", "walk-in access")))
    link = [u if isinstance(u, str) and u.startswith("http") and "google." not in u.lower() else
            "https://www.pa.gov/agencies/fishandboat" for u in a.Ftr_Page]
    park = a.PARKING.fillna("").str.upper().map({"L": True, "S": True, "R": True, "N": False}).where(lambda s: s.notna(), None)
    return _out(a, name=a.ACC_NAME.map(clean), atype=kind, water=a.WATERBODY.map(_title), source="PFBC", url=link,
                parking=park.values, note=a.Parking_FullDesc.map(clean))


def dnrec(bb):
    """DNREC's fishing access (one record per facility; a site's records are merged by the caller)."""
    d = _g(DNREC, bb, "TIDAL_FISHING_ACCESS_AREAS,GNIS_NAME,FACILITY,PUBLICACCESS,RAMPS,PARKINGCAP")
    if d is None:
        return None
    d = d[~d.PUBLICACCESS.fillna("Yes").str.lower().eq("no")]
    t = {"Boat Ramp": "boat ramp", "Canoe Launch": "hand launch", "Boat Dock": "hand launch", "Fishing Pier": "fishing pier",
         "Shoreline Fishing": "walk-in access"}
    d = d[d.FACILITY.isin(t)]
    cap = pd.to_numeric(d.PARKINGCAP, errors="coerce")
    return _out(d, name=[clean(a) or clean(b) for a, b in zip(d.TIDAL_FISHING_ACCESS_AREAS, d.GNIS_NAME)],
                atype=d.FACILITY.map(t), source="DNREC", url="https://dnrec.delaware.gov/fish-wildlife/fishing/",
                parking=np.where(cap > 0, True, None),
                status=d.RAMPS.map(lambda v: "closed" if isinstance(v, str) and v.strip().lower() == "closed" else None))


def cdfw(bb):
    """CDFW's fishing guide boat launches (public ones)."""
    c = _g(CDFW, bb, "Facility_Name,Facility_Type,Website,Water_Body,Facility_Users,NO_OF_PARK_SPACES_CAR_W_TRAILER")
    if c is None:
        return None
    c = c[c.Facility_Users.fillna("Public").str.contains("Public", case=False)]
    return _out(c, name=c.Facility_Name.map(clean), atype="boat ramp", water=c.Water_Body.map(clean), source="CDFW",
                url=c.Website.map(lambda u: u if isinstance(u, str) and u.startswith("http") else "https://wildlife.ca.gov/Fishing/Guide"),
                parking=True)


def wgfd(bb):
    """WGFD: the fishing guide's boat ramps, the Public Access Areas (their points, ramps and parking) and the river
    access points of its float-fishing guide."""
    parts, url = [], "https://wgfd.wyo.gov/fishing-boating"
    f = _g(f"{WGFD}/Facilities_FishingGuide_PublicView/FeatureServer/0", bb, "FacilityName,FacilityType,WaterName",
           where="FacilityType='Boat Ramp'")
    if f is not None:
        parts.append(_out(f, name=f.FacilityName.map(clean), atype="boat ramp", water=f.WaterName.map(clean), source="WGFD",
                          url=url, parking=True))
    a = _g(f"{WGFD}/PAA_Facilities/FeatureServer/3", bb, "PAA_Name,FacilityName,FacilityType",
           where="FacilityType IN ('Boat Ramp','Parking')")
    if a is not None:
        parts.append(_out(a, name=[clean(p) or clean(n) for p, n in zip(a.PAA_Name, a.FacilityName)],
                          atype=a.FacilityType.map({"Boat Ramp": "boat ramp", "Parking": "parking"}), source="WGFD",
                          url=url, parking=True, note="Public Access Area"))
    p = _g(f"{WGFD}/PAA_Locations/FeatureServer/4", bb, "PAA_Name,Amenities,AccessDates,SeasonalClosure")
    if p is not None:
        parts.append(_out(p, name=p.PAA_Name.map(clean), atype="walk-in access", source="WGFD", url=url,
                          parking=p.Amenities.fillna("").str.contains("Parking", case=False).map(lambda v: True if v else None),
                          note=["Public Access Area" + (f"; {d}" if clean(d) else "") for d in p.AccessDates],
                          status=p.SeasonalClosure.map(lambda v: "seasonal closure" if clean(v) and clean(v).lower() not in ("no", "none") else None)))
    r = _g(f"{WGFD}/All_River_Access_Points/FeatureServer/0", bb, "StreamName,LaunchLocation,IsLaunch,IsEgress")
    if r is not None:
        parts.append(_out(r, name=r.LaunchLocation.map(clean), atype="hand launch", water=r.StreamName.map(clean),
                          source="WGFD", url=url, note="river access (put-in or take-out)"))
    return pd.concat(parts, ignore_index=True) if parts else None


def idfg(bb):
    """IDFG's fishing and boating access sites."""
    d = _g(IDFG, bb, "site_name,fishing_boating,ramp,status,public_info_notes")
    if d is None:
        return None
    d = d[d.status.fillna("Active").str.lower().ne("inactive")]
    kind = np.where(d.ramp.map(yes), "boat ramp", np.where(d.fishing_boating.fillna("").str.lower().eq("boating"),
                                                           "hand launch", "walk-in access"))
    return _out(d, name=d.site_name.map(_title), atype=kind, source="IDFG", url="https://idfg.idaho.gov/",
                note=d.public_info_notes.map(lambda v: clean(v)[:200] if clean(v) else None),
                parking=d.public_info_notes.fillna("").str.contains("parking", case=False).map(lambda v: True if v else None))


def gadnr(bb):
    """Georgia DNR's water access points: boat ramps, bank fishing, canoe access, fishing piers."""
    g = _g(GADNR, bb, "Name,Waterbody,WaterType,Link1,Link2,Ramp,BankOnly,CanoeAcc,PierFish,Parking,Status,Draw")
    if g is None:
        return None
    g = g[~g.Status.fillna("").str.lower().eq("closed") & g.Draw.fillna("Public").eq("Public")]
    kind = np.where(g.Ramp.map(yes), "boat ramp", np.where(g.CanoeAcc.map(yes), "hand launch",
                    np.where(g.PierFish.map(yes) & ~g.BankOnly.map(yes), "fishing pier", "walk-in access")))
    link = [a if isinstance(a, str) and a.startswith("http") else b if isinstance(b, str) and b.startswith("http")
            else "https://georgiawildlife.com/fishing" for a, b in zip(g.Link1, g.Link2)]
    return _out(g, name=g.Name.map(clean), atype=kind, water=g.Waterbody.map(clean), source="Georgia DNR", url=link,
                parking=g.Parking.fillna("").str.upper().map({"Y": True, "N": False}).where(lambda s: s.notna(), None).values)


def scdnr(bb):
    """SCDNR's public water access (open to the public)."""
    d = _g(SCDNR, bb, "WaterAccessName,WaterAccessType,Waterbody,Parking,Status,PublicAccess")
    if d is None:
        return None
    d = d[d.PublicAccess.fillna("Open").str.lower().eq("open")]
    t = {"Boat Ramp": "boat ramp", "Paddle Launch": "hand launch", "Pier": "fishing pier", "Bank": "walk-in access"}
    d = d[d.WaterAccessType.isin(t)]
    pk = d.Parking.fillna("")
    return _out(d, name=d.WaterAccessName.map(clean), atype=d.WaterAccessType.map(t), water=d.Waterbody.map(clean),
                source="SCDNR", url="https://www.dnr.sc.gov/", note=pk.map(clean),
                parking=np.where(pk.str.contains(r"(?i)no parking"), False, np.where(pk.str.contains(r"(?i)park|space"), True, None)))


def ncwrc(bb):
    """NCWRC's boating access areas and public fishing areas (open ones)."""
    parts, url = [], "https://www.ncwildlife.gov/boating/boating-access-areas"
    b = _g(f"{NCWRC}/NCWRC_Boating_Access_Areas_view/FeatureServer/0", bb,
           "BAA_Name,Water_Access,Website,Site_Status,Launch_Lane_No,Non_Motorized_Access,Fishing_Pier")
    if b is not None:
        b = b[~b.Site_Status.fillna("").str.contains("closed", case=False)]
        lanes = pd.to_numeric(b.Launch_Lane_No, errors="coerce").fillna(0)
        parts.append(_out(b, name=b.BAA_Name.map(_title), atype=np.where(lanes > 0, "boat ramp", "hand launch"),
                          water=b.Water_Access.map(_title), source="NCWRC",
                          url=b.Website.map(lambda u: u if isinstance(u, str) and u.startswith("http") else url), parking=True))
    f = _g(f"{NCWRC}/NCWRC_Public_Fishing_Areas_view/FeatureServer/0", bb,
           "PFA_Name,Water_Access,Site_Status,Boat_Ramp,Fix_Pier_No,Float_Pier_No,Portable_Boat_Access_Type,Website")
    if f is not None:
        f = f[f.Site_Status.fillna("OPEN").str.upper().eq("OPEN")]
        pier = (pd.to_numeric(f.Fix_Pier_No, errors="coerce").fillna(0) + pd.to_numeric(f.Float_Pier_No, errors="coerce").fillna(0)) > 0
        launch = f.Portable_Boat_Access_Type.fillna("").str.contains(r"(?i)launch|slide|ramp")
        parts.append(_out(f, name=f.PFA_Name.map(_title), atype=np.where(launch, "hand launch", np.where(pier, "fishing pier", "walk-in access")),
                          water=f.Water_Access.map(_title), source="NCWRC",
                          url=f.Website.map(lambda u: u if isinstance(u, str) and u.startswith("http") else
                                            "https://www.ncwildlife.gov/fishing/where-fish"),
                          note=f.Portable_Boat_Access_Type.map(clean)))
    return pd.concat(parts, ignore_index=True) if parts else None


def twra(bb):
    """TWRA's access sites: boat launches and fishing sites (not marinas)."""
    t = _g(TWRA, bb, "Name,Waterway,Type", where="Type IN ('Boat Launch','Fishing Site')")
    if t is None:
        return None
    return _out(t, name=t.Name.map(clean), atype=t.Type.map({"Boat Launch": "boat ramp", "Fishing Site": "walk-in access"}),
                water=t.Waterway.map(clean), source="TWRA", url="https://www.tn.gov/twra/boating/boating-access-sites.html")


def vadwr(bb):
    """Virginia DWR's boating access locations (its own sites)."""
    v = _g(VADWR, bb, "SITENAME,WATERBODY,TYPE,Type_of_Ramp")
    if v is None:
        return None
    hand = v.Type_of_Ramp.fillna("").str.contains("Hand Launch", case=False) | v.TYPE.fillna("").eq("BS")
    return _out(v, name=v.SITENAME.map(_title), atype=np.where(hand, "hand launch", "boat ramp"),
                water=v.WATERBODY.map(_title), source="Virginia DWR", url="https://dwr.virginia.gov/boating/access/",
                note=v.Type_of_Ramp.map(clean))


def ctdeep(bb):
    """CT DEEP's boat launches (trailered and car-top)."""
    c = _g(CTDEEP, bb, "LAUNCHNAME,LAUNCHTYPE,LINK")
    if c is None:
        return None
    return _out(c, name=c.LAUNCHNAME.map(clean), atype=np.where(c.LAUNCHTYPE.fillna("").str.contains("Trailer", case=False),
                                                              "boat ramp", "hand launch"),
                source="CT DEEP", url=c.LINK.map(lambda u: u if isinstance(u, str) and u.startswith("http") else
                                                 "https://portal.ct.gov/deep/boating/boating-and-paddling/boat-launches"),
                parking=True)


def maofba(bb):
    """Massachusetts' Office of Fishing and Boating Access sites (MassGIS)."""
    m = _g(MAOFBA, bb, "FACNAME,RAMPTYPE,PARKING,PONDMAP_LINK")
    if m is None:
        return None
    return _out(m, name=m.FACNAME.map(clean), atype=np.where(m.RAMPTYPE.fillna("").str.strip().ne(""), "boat ramp", "hand launch"),
                source="Massachusetts OFBA", note=m.PARKING.map(lambda v: f"parking: {clean(v)}" if clean(v) else None),
                url=m.PONDMAP_LINK.map(lambda u: u if isinstance(u, str) and u.startswith("http") else
                                       "https://www.mass.gov/orgs/office-of-fishing-and-boating-access"),
                parking=m.PARKING.map(lambda v: True if clean(v) else None))


def rigis(bb):
    """RIDEM's fishing and boating access (RIGIS), fresh water."""
    r = _g(RIGIS, bb, "NAME,TYPE,PARK,Wat_Ttp")
    if r is None:
        return None
    r = r[r.Wat_Ttp.fillna("Fresh").str.lower().str.startswith("fresh")]
    t = {"trailer ramp": "boat ramp", "smallcraft launch": "hand launch", "fishing access": "walk-in access"}
    pk = r.PARK.fillna("").str.strip()
    return _out(r, name=r.NAME.map(clean), atype=r.TYPE.fillna("").str.strip().str.lower().map(t), source="RIDEM",
                url="https://dem.ri.gov/", note=pk.map(lambda v: f"parking: {v}" if v else None),
                parking=np.where(pk.str.lower().isin(["", "none", "no"]), None, True))


def vtfw(bb):
    """Vermont Fish & Wildlife's fishing access areas (the copy lakesources.py reads too)."""
    import troutdata
    try:
        a = troutdata.fetch("lake_vt_access", "https://anrmaps.vermont.gov/arcgis/rest/services/map_services/"
                            "MAP_ANR_ANRATLASFISHWILDLIFE_WM_NOCACHE/MapServer/2", fields="AccessName,WaterBody,AccessType,RampType")
    except Exception as ex:
        print(f"  access source unavailable: Vermont fishing access areas ({str(ex)[:80]})")
        return None
    if not len(a):
        return None
    a = a.to_crs(4326)
    ramp = a.RampType.fillna("").str.strip()
    shore = a.AccessType.fillna("").str.contains("Shore", case=False)
    return _out(a, name=[clean(n) or clean(w) for n, w in zip(a.AccessName, a.WaterBody)],
                atype=np.where(shore, "walk-in access", np.where(ramp.isin(["Concrete", "Concrete Plank", "Gravel"]), "boat ramp", "hand launch")),
                water=a.WaterBody.map(clean), source="Vermont F&W", url="https://vtfishandwildlife.com/fish/fishing-access-areas",
                note=ramp.map(lambda v: f"ramp: {v.lower()}" if v and v.lower() != "none" else None), parking=True)


def nydec(bb):
    """DEC's boat launches, fishing access sites and piers (facility assets), its boat launch list and its Public
    Fishing Rights parking areas, all from data.ny.gov (Open NY terms)."""
    import lakesources
    w, s_, e, n = bb
    inbox = lambda x, y: (x >= w) & (x <= e) & (y >= s_) & (y <= n)
    parts, url = [], "https://dec.ny.gov/things-to-do/freshwater-fishing"
    fa = lakesources.ny_facilities(bb)
    if len(fa):
        t = {"BOAT LAUNCH": "boat ramp", "FISHING ACCESS SITE": "walk-in access", "FISHING PIER": "fishing pier",
             "ACCESSIBLE FISHING PIER": "fishing pier", "ACCESSIBLE FISHING PLATFORM": "fishing pier",
             "ACCESSIBLE HAND LAUNCH": "hand launch"}
        fa = fa[fa.asset.isin(t)]
        parts.append(_out(fa, name=[_title(a) if clean(a) else _title(f) for a, f in zip(fa["name"], fa.facility)],
                          atype=fa.asset.map(t), source="NYSDEC", url=url, note=fa.facility.map(_title)))
    def soc(dsid, xcol, ycol):
        try:
            rows = lakesources._socrata(dsid)
        except Exception as ex:
            print(f"  access source unavailable: data.ny.gov {dsid} ({str(ex)[:80]})")
            return None
        t = pd.DataFrame(rows)
        if not len(t) or xcol not in t:
            return None
        x, y = pd.to_numeric(t[xcol], errors="coerce"), pd.to_numeric(t[ycol], errors="coerce")
        t = t[inbox(x, y)]
        return gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(x[t.index], y[t.index]), crs=4326) if len(t) else None
    b = soc("icvg-v8xr", "point_x", "point_y")
    if b is not None:
        hand = b.access.fillna("").str.contains("Hand", case=False)
        parts.append(_out(b, name=b.waterbody.map(lambda v: f"{clean(v)} boat launch" if clean(v) else None),
                          atype=np.where(hand, "hand launch", "boat ramp"), water=b.waterbody.map(clean), source="NYSDEC",
                          url=url, note=b.access.map(clean),
                          parking=[True if (pd.to_numeric(c, errors="coerce") or 0) + (pd.to_numeric(t_, errors="coerce") or 0) > 0 else None
                                   for c, t_ in zip(b.get("car", [None] * len(b)), b.get("trail", [None] * len(b)))]))
    p = soc("9vef-6whi", "longitude", "latitude")
    if p is not None:
        parts.append(_out(p, name=[f"{clean(w)} fishing rights parking" + (f" {clean(n)}" if clean(n) else "")
                                   for w, n in zip(p.water, p.get("parking_area_number", [None] * len(p)))],
                          atype="parking", water=p.water.map(clean), source="NYSDEC",
                          url=[u if isinstance(u, str) and u.startswith("http") else
                               "https://dec.ny.gov/things-to-do/freshwater-fishing/public-fishing-rights-maps"
                               for u in p.get("pdf_map_link", [None] * len(p))],
                          note=p.get("road", pd.Series(None, index=p.index)).map(lambda v: f"on {clean(v)}" if clean(v) else None),
                          parking=True))
    return pd.concat(parts, ignore_index=True) if parts else None


# Sources to leave out, by their function's name ("vadwr", "maofba", "vtfw", ...): the one line to change when a source's
# terms rule it out; their points leave the map and the route starts, and credits.py drops their access credit
LEFT_OUT = set()

ADAPTERS = {"all": (usfs, nps, tva), "CA": (cdfw,), "WY": (wgfd,), "ID": (idfg,), "GA": (gadnr,), "SC": (scdnr,),
            "NC": (ncwrc,), "TN": (twra,), "VA": (vadwr,), "PA": (pfbc,), "DE": (dnrec,),
            "CT": (ctdeep,), "MA": (maofba,), "RI": (rigis,), "VT": (vtfw,), "NY": (nydec,)}


RANK = {t: k for k, t in enumerate(TYPES)}
WATER_M = 1000.0    # a site is kept within this of a reach the map draws or a lake: one for water the map doesn't draw
                    # (the tidal Delaware's Philadelphia ramps, the ocean's marinas) is left out; New York's fishing
                    # rights parking lies up to 540 m from its creek (measured on the 12 maps, 2026-11-25)


def near_water(points, dist=WATER_M):
    """True for each projected point within `dist` of the water the map draws (trailrules.water())."""
    import trailrules
    w = trailrules.water()
    if not len(w) or not len(points):
        return np.zeros(len(points), bool)
    i = shapely.STRtree(w).query_nearest(np.asarray(points, dtype=object), max_distance=dist, all_matches=False)[0]
    out = np.zeros(len(points), bool)
    out[np.unique(i)] = True
    return out       # a site's type is its best facility's: a ramp before a launch, ...


def area_states():
    """The states the area's boxes reach into (02f_known_falls.py's list)."""
    import sources
    from config import AREA, WORKED_OUT, AREA_STATES
    return sources.pick("gnis_states", AREA, WORKED_OUT.get("gnis_states", AREA_STATES))


def area_bounds():
    """The lon/lat box around all of the area's ranges (the sources are asked for this box, and their copies kept
    under it)."""
    from config import REGIONS, CRS
    b = gpd.GeoSeries([shapely.box(*r["bbox"]) for r in REGIONS.values()], crs=CRS).to_crs(4326).total_bounds
    return tuple(round(float(v), 5) for v in b)


def official(states, bounds_ll, merge_m=75.0):
    """Every official access point in the lon/lat box from the sources for `states` and the federal ones, EPSG:4326,
    with columns COLS. Points within merge_m of each other are one site: its type the best of theirs (RANK), its name,
    water and link the first source's (the states' agencies, in the order listed, before the federal ones), the others'
    facts where it has none, and every source named."""
    parts = []
    for key in tuple(states) + ("all",):
        for f in ADAPTERS.get(key, ()):
            if f.__name__ in LEFT_OUT:
                continue
            g = f(bounds_ll)
            if g is not None and len(g):
                g = g[g.atype.isin(TYPES)]
                print(f"  access points: {f.__name__} {len(g)}")
                parts.append(g)
    if not parts:
        return gpd.GeoDataFrame({c: [] for c in COLS[:-1]}, geometry=[], crs=4326)
    a = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)
    a = a[a.name.notna()].reset_index(drop=True)
    xy = a.to_crs(5070).geometry.values
    tree = shapely.STRtree(xy)
    owner = np.arange(len(a))
    for i in range(len(a)):                          # each point joins the first earlier site within merge_m
        near = tree.query(xy[i], predicate="dwithin", distance=merge_m)
        near = near[near < i]
        if len(near):
            owner[i] = owner[near.min()]
    rows = []
    for o in np.unique(owner):
        grp = a.iloc[np.flatnonzero(owner == o)]
        r = grp.iloc[0].copy()
        r["atype"] = min(grp.atype, key=RANK.get)
        for c in ("water", "url", "status", "note"):
            if not isinstance(r[c], str):
                r[c] = next((v for v in grp[c] if isinstance(v, str)), None)
        pk = [v for v in grp.parking if v is not None and not (isinstance(v, float) and np.isnan(v))]
        r["parking"] = True if any(pk) else (False if pk else None)
        r["source"] = ", ".join(dict.fromkeys(", ".join(grp.source).split(", ")))
        rows.append(r)
    out = gpd.GeoDataFrame(rows, columns=COLS, crs=4326).reset_index(drop=True)
    # a boat ramp has room for the car and trailer unless the source says it has none
    out["parking"] = [True if p is None and t == "boat ramp" else p for p, t in zip(out.parking, out.atype)]
    return out
