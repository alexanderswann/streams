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
Stocking and fish surveys at lakes come from 11_context.py's trout evidence (troutdata.py), read by maplakes.py.
"""
import os, time, requests, numpy as np, pandas as pd, geopandas as gpd
from config import NATIONAL
from geomatch import esri

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
                r = requests.get(url, headers=UA, timeout=300)
                if r.ok:
                    with open(path + ".tmp", "wb") as f:
                        f.write(r.content)
                    os.replace(path + ".tmp", path)
                    break
            except requests.RequestException:
                pass
            time.sleep(10 * (attempt + 1))
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
    if not parts:
        return gpd.GeoDataFrame({"kind": [], "text": [], "url": []}, geometry=[], crs=4326)
    return gpd.GeoDataFrame(pd.concat([q[["kind", "text", "url", "geometry"]] for q in parts], ignore_index=True), crs=4326)
