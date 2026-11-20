"""Trout records from the state agencies outside California, in the two shapes 11_context.py already uses for CDFW's:

  evidence()  points: kind ("<agency> survey" / "<agency> stocking"), water, year, trout (found or not), lake, url,
              label. A survey or stocking record counts for the creek of that name near the point (11_context.py)
  waters()    polygons: Name, Designation. Designated or documented trout water; a reach inside one gets the trout
              term's x1.2 like a CDFW Wild Trout Water. Lines are buffered 25 m so both maps draw them the same way

Which sources an area has is in config.py (`sources`); all were checked against the live services on 2026-11-18:
  ct_trout   CT DEEP: fish community samples (species per sample, wild / stocked told apart), stocked streams and
             lakes (latest stocking date), fisheries management areas (Wild Trout / Trout Management Areas, trophy
             trout streams)
  vt_trout   Vermont Fish & Wildlife: brook trout waters (catchments with wild brook trout or mixed wild trout),
             the 2021 stocking list. Vermont publishes no survey layer with species per site
  va_trout   Virginia DWR: cold water stream survey (wild trout streams, classes I-IV), stocked trout reaches and lakes
  ga_trout   Georgia DNR: designated trout streams, recently stocked streams, this year's standardized trout sampling
  wy_trout   Wyoming Game & Fish: fishing-guide streams with trout (blue / red / yellow / green ribbon classes and
             the game fish present), native cutthroat waters. Its "Clear (no trout present)" class is a
             classification, not a dated survey, so it is not used as a no-trout record
  id_trout   Idaho Fish & Game (checked 2026-11-19): its Yellowstone cutthroat trout streams (year-round use; the 2002
             and 2023 range-wide status assessments and its own IFWIS records), as StreamNet's regional fish
             distribution serves them. Idaho publishes no survey or stocking layer
  pa_trout   Pennsylvania Fish & Boat Commission (checked 2026-11-19): Class A wild trout streams (as DCNR's Conservation
             Explorer serves PFBC's layer), streams with natural trout reproduction, trout special-regulation areas
             (delayed harvest, catch-and-release, fly-fishing only), the newest year's stocked sections (fish per
             species) and stocked lakes. PFBC publishes no survey layer with species per site
  de_trout   Delaware DNREC (checked 2026-11-19): the designated trout streams of New Castle County, stocked each spring,
             and their fly-fishing-only sections
  tu_brook_trout  Trout Unlimited's latest brook trout portfolio (the EBTJV wild brook trout patches), CT to GA
A "no trout" record is only made from an electrofishing sample that lists other species and no trout (CT). Nothing
else here lowers a score: when unsure, a possible trout stream stays in.
Downloads are cached for a week in <area>/_shared/cache (REFRESH=1 forces).
"""
import os, io, re, time, datetime as dt, requests, shapely, numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
from config import REGIONS, CRS, EPSG, SHARED, has

UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
CACHE = f"{SHARED}/cache"
LAKE = r"(?i)\b(?:lakes?|ponds?|reservoir)\b"
RUNNING = r"(?i)\b(?:brook|river|creek|stream|run|branch|fork|outlet)\b"     # "Mill Pond Brook" is a brook
THIS_YEAR = dt.date.today().year
_area = gpd.GeoSeries([box(*v["bbox"]).buffer(3000) for v in REGIONS.values()], crs=CRS)
_area_u = _area.union_all()
_W, _S, _E, _N = _area.to_crs(4326).total_bounds
_EMPTY = gpd.GeoDataFrame(geometry=[], crs=CRS)


def _post(url, **params):
    for attempt in range(4):
        try:
            r = requests.post(url, headers=UA, timeout=(20, 300), data=params)
            if r.ok and "error" not in r.text[:60]:
                return r
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"no answer from {url}")


def fetch(key, url, where="1=1", fields="*"):
    """Every feature of an ArcGIS layer in the study area, in the area's CRS. Asks for the ids first and then the
    features by id, which also works on the servers that refuse paging (Vermont's)."""
    os.makedirs(CACHE, exist_ok=True)
    p = f"{CACHE}/trout_{key}.geojson"
    if not (os.path.exists(p) and os.environ.get("REFRESH") != "1" and time.time() - os.path.getmtime(p) < 7 * 86400):
        ids = _post(f"{url}/query", where=where, geometry=f"{_W},{_S},{_E},{_N}", geometryType="esriGeometryEnvelope",
                    inSR=4326, spatialRel="esriSpatialRelIntersects", returnIdsOnly="true", f="json").json().get("objectIds") or []
        feats = []
        for i in range(0, len(ids), 150):
            feats += _post(f"{url}/query", objectIds=",".join(map(str, ids[i:i + 150])), outFields=fields, outSR=EPSG,
                           f="geojson").json()["features"]
        g = gpd.GeoDataFrame.from_features(feats, crs=CRS) if feats else _EMPTY
        with open(p + ".tmp", "w") as f:
            f.write(g.to_json() if len(g) else '{"type": "FeatureCollection", "features": []}')
        os.replace(p + ".tmp", p)
    g = gpd.read_file(p) if os.path.getsize(p) > 60 else _EMPTY
    if not len(g):
        return _EMPTY
    g = g.set_crs(CRS, allow_override=True)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g[g.intersects(_area_u)].reset_index(drop=True)


def _mid(g):
    """A point on each line (its middle) or inside each polygon."""
    return gpd.GeoSeries([x.interpolate(0.5, normalized=True) if x.geom_type == "LineString" else x.representative_point()
                          for x in g.geometry], index=g.index, crs=CRS)


def _ev(g, kind, water, year, trout, label, lake=None, url=None):
    water = pd.Series(water, index=g.index).fillna("").astype(str)
    water = water.str.replace(r"\s*\(.*?\)", "", regex=True).str.strip()      # "South River (Rockbridge)"
    return gpd.GeoDataFrame(dict(kind=kind, water=water, year=pd.to_numeric(pd.Series(year, index=g.index), errors="coerce"),
                                 trout=pd.Series(trout, index=g.index).astype(bool),
                                 lake=(water.str.contains(LAKE) & ~water.str.contains(RUNNING)) if lake is None else lake, url=url,
                                 label=pd.Series(label, index=g.index)),
                            geometry=_mid(g) if not (g.geom_type == "Point").all() else g.geometry, crs=CRS)


def _waters(g, name, designation, buffer=25):
    geom = g.geometry if g.geom_type.isin(["Polygon", "MultiPolygon"]).all() else g.buffer(buffer)
    # broad: an area the record covers as a whole (a catchment, a patch), not a mapped stream line
    return gpd.GeoDataFrame(dict(Name=pd.Series(name, index=g.index).fillna("").astype(str).str.strip(),
                                 Designation=pd.Series(designation, index=g.index), Designation_Boundary=None,
                                 broad=bool(g.geom_type.isin(["Polygon", "MultiPolygon"]).all())),
                            geometry=shapely.make_valid(geom.values), crs=CRS)


def _ms(v):
    return pd.to_datetime(pd.to_numeric(v, errors="coerce"), unit="ms", errors="coerce")


def _recent(when):
    return (when >= pd.Timestamp(dt.date.today()) - pd.Timedelta(days=365)).fillna(False)


# ---- Connecticut ----
CT = "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services"
def _ct():
    ev, wa = [], []
    f = fetch("ct_fish", f"{CT}/fish_community_data/FeatureServer/0", where="Sample_Year >= 2000",
              fields="Station_ID,Sample_Year,Sample_Type,Sample_ID,Fish_Species,Waterbody_Name,Quantity")
    if len(f):
        f["sp"] = f.Fish_Species.fillna("").str.strip()
        f["is_trout"] = f.sp.str.contains("Trout", case=False)
        f["efish"] = f.Sample_Type.fillna("").str.contains("lectrofishing")
        rows = []
        for (st, yr), g in f.groupby(["Station_ID", "Sample_Year"]):
            t = g[g.is_trout]
            if len(t):
                q = t.groupby("sp").Quantity.sum()
                what = ", ".join(f"{re.sub(r'^(.*?), (Wild|Stocked)$', lambda m: f'{m.group(2).lower()} {m.group(1).lower()}', s)}"
                                 + (f" ({int(n)})" if pd.notna(n) and n > 0 else "") for s, n in q.items())
                rows.append((g.index[0], yr, True, f"CT DEEP sample {int(yr)}: {what}"))
            elif g.efish.any() and g.sp.nunique() >= 2:      # an electrofishing sample of other fish, and no trout
                rows.append((g.index[0], yr, False, f"CT DEEP electrofishing sample {int(yr)}: no trout "
                                                    f"({g.sp.nunique()} other species)"))
        r = pd.DataFrame(rows, columns=["i", "year", "trout", "label"]).set_index("i")
        # per station: its latest sample, and its latest sample with trout
        st = f.loc[r.index, "Station_ID"]
        keep = r.assign(st=st.values).sort_values("year").groupby(["st", "trout"]).tail(1)
        g = f.loc[keep.index]
        ev.append(_ev(g, "CT DEEP survey", g.Waterbody_Name, keep.year.values, keep.trout.values, keep.label.values))
    s = fetch("ct_stocked_streams", f"{CT}/Connecticut_Stocked_Streams/FeatureServer/0",
              fields="STREAMS_WATERBODY,STOCKING_TABLE_STOCKDATE,STOCKING_TABLE_MGT")
    k = fetch("ct_stocked_lakes", f"{CT}/Connecticut_Stocked_Lakes/FeatureServer/0", fields="*")
    for g, col, date, lake in ((s, "STREAMS_WATERBODY", "STOCKING_TABLE_STOCKDATE", False),
                               (k, next((c for c in k.columns if c.endswith("WATERBODY")), None),
                                next((c for c in k.columns if c.endswith("STOCKDATE")), None), True)):
        if len(g) and col and date:
            when = _ms(g[date])
            g, when = g[_recent(when).values], when[_recent(when).values]
            if len(g):
                ev.append(_ev(g, "CT DEEP stocking", g[col], when.dt.year.values, True,
                              [f"stocked with trout, last on {d:%b %-d, %Y}" for d in when], lake=lake or None))
    m = fetch("ct_mgmt", f"{CT}/Fisheries_management_Areas/FeatureServer/0", where="MGMT_AREA LIKE '%Trout%'",
              fields="MGMT_AREA,FISH_TYPE,STREAM")
    if len(m):
        wa.append(_waters(m, m.STREAM, m.MGMT_AREA.str.strip() + " (CT DEEP)"))
    return ev, wa


# ---- Vermont ----
VT = "https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASFISHWILDLIFE_WM_NOCACHE/MapServer"
def _vt():
    ev, wa = [], []
    b = fetch("vt_brook", f"{VT}/49", fields="trout_stat,samp_year,featureid")
    if len(b):
        b = b[b.trout_stat.fillna("").str.contains("Trout")]
        yr = pd.to_numeric(b.samp_year, errors="coerce")
        wa.append(_waters(b, ["Vermont Fish & Wildlife" + (f", sampled {int(y)}" if pd.notna(y) and y > 1900 else "") for y in yr],
                          b.trout_stat.str.replace(" Only", "", regex=False).str.lower().str.capitalize() + " water"))
    s = fetch("vt_stock", f"{VT}/52", fields="Waterbody,Location,Town,Species")
    if len(s):
        s = s[s.Species.fillna("").str.contains("BKT|RBT|BNT|trout", case=False)]
        g = s.dissolve(by="Waterbody", aggfunc={"Species": lambda v: ", ".join(sorted(set(", ".join(v).replace(" ", "").split(","))))}).reset_index()
        g["geometry"] = [x.geoms[0] if x.geom_type == "MultiPoint" else x for x in g.geometry]
        ev.append(_ev(g, "VT F&W stocking", g.Waterbody, 2021, True,
                      "on Vermont's 2021 trout stocking list (" + g.Species + ")"))
    return ev, wa


# ---- Virginia ----
VA = "https://services.dwr.virginia.gov/arcgis/rest/services/HUB_Layers"
def _va():
    ev, wa = [], []
    c = fetch("va_coldwater", f"{VA}/DWR_Cold_Water_Stream_Survey_Trout_Streams/FeatureServer/0",
              fields="NAME,CLASS_1,BROOK,BROWN,RAINBOW")
    if len(c):
        c = c[c.CLASS_1.fillna("").str.strip().isin(["I", "II", "III", "IV"])]
        spp = [", ".join(n for n, v in (("brook", r.BROOK), ("brown", r.BROWN), ("rainbow", r.RAINBOW)) if str(v).upper().startswith("Y"))
               for r in c.itertuples()]
        wa.append(_waters(c, c.NAME, ["Wild trout stream, class " + k.strip() + (f" ({s} trout)" if s else "") + " (VA DWR)"
                                      for k, s in zip(c.CLASS_1, spp)]))
    code = {"PNT": "put-and-take", "DH": "delayed harvest", "SR": "special regulation", "WT": "wild trout water also stocked"}
    for key, lyr, lake in (("va_stock_reaches", "DWR_Stocked_Trout_Reaches", None), ("va_stock_lakes", "DWR_Stocked_Trout_Lakes", True)):
        s = fetch(key, f"{VA}/{lyr}/FeatureServer/0", fields="Waterbody,Designation")
        if len(s):
            ev.append(_ev(s, "VA DWR stocking", s.Waterbody, THIS_YEAR, True,
                          ["on Virginia's trout stocking plan" + (f" ({code.get(str(d).strip(), str(d).strip())})" if pd.notna(d) and str(d).strip() else "")
                           for d in s.Designation], lake=lake))
    return ev, wa


# ---- Georgia ----
GA = "https://services6.arcgis.com/9QlSLDqa0P1cHLhu/arcgis/rest/services"
def _ga():
    ev, wa = [], []
    t = fetch("ga_trout_streams", f"{GA}/Georgia_Trout_Streams_Public_Download_All_Layers/FeatureServer/1",
              fields="Name,Spec_Reg,Delay_har,Hvy_stock")
    if len(t):
        yes = lambda v: str(v).strip().lower() in ("y", "yes", "1", "true")
        wa.append(_waters(t, t.Name, ["Georgia designated trout stream" + (", special regulations" if yes(a) else "")
                                      + (", delayed harvest" if yes(b) else "") + " (GA DNR)" for a, b in zip(t.Spec_Reg, t.Delay_har)]))
    s = fetch("ga_recent_stock", f"{GA}/Recently_Stocked_Streams/FeatureServer/0", fields="Name,LastStock")
    if len(s):
        when = _ms(s.LastStock)
        s, when = s[_recent(when).values], when[_recent(when).values]
        if len(s):
            ev.append(_ev(s, "GA DNR stocking", s.Name, when.dt.year.values, True,
                          [f"stocked with trout, last on {d:%b %-d, %Y}" for d in when]))
    m = fetch("ga_sampling", f"{GA}/Trout_Standardized_Sampling_view/FeatureServer/0",
              fields="master_stream,master_sample_date,master_species,total_fish")
    if len(m):
        sp = {"BKT": "brook trout", "RBT": "rainbow trout", "BRT": "brown trout", "BNT": "brown trout"}
        m["when"], m["n"] = _ms(m.master_sample_date), pd.to_numeric(m.total_fish, errors="coerce").fillna(0)
        m = m[m.n > 0]
        if len(m):
            g = m.dissolve(by="master_stream", aggfunc={"when": "max", "master_species": lambda v: ", ".join(
                sorted({sp.get(str(x).strip().upper(), str(x).strip().lower()) for x in v}))}).reset_index()
            ev.append(_ev(g, "GA DNR survey", g.master_stream, g.when.dt.year.values, True,
                          [f"GA DNR trout sample {d:%Y}: {s_}" for d, s_ in zip(g.when, g.master_species)]))
    return ev, wa


# ---- Wyoming ----
WY = "https://services6.arcgis.com/cWzdqIyxbijuhPLw/arcgis/rest/services"
def _wy():
    wa = []
    g = fetch("wy_guide", f"{WY}/Streams_FishingGuide_PublicView/FeatureServer/0",
              fields="WaterName,StreamClass,GameFishPresent")
    if len(g):
        fish = g.GameFishPresent.fillna("")
        g = g[fish.str.contains("Trout|Cutthroat", case=False) & ~g.StreamClass.fillna("").str.startswith("Clear")]
        cls = g.StreamClass.fillna("").str.extract(r"^(\w+)")[0].str.lower()
        wa.append(_waters(g, g.WaterName, ["Wyoming trout stream" + (f", {c} ribbon" if isinstance(c, str) and c else "")
                                           + f": {f_.lower()} (WGFD)" for c, f_ in zip(cls, g.GameFishPresent)]))
    c = fetch("wy_cutt", f"{WY}/CuttslamRivers/FeatureServer/0", fields="Species,WaterName")
    if len(c):
        wa.append(_waters(c, c.WaterName, "Native " + c.Species.fillna("cutthroat").str.strip() + " water (WGFD)"))
    return [], wa


# ---- Idaho ----
STREAMNET = "https://gis.psmfc.org/server/rest/services/StreamNet/Fish_Dist/MapServer"
def _id():
    # layer 13 = Yellowstone cutthroat trout; only Idaho's agency compiles it here (Wyoming's waters are in wy_trout)
    y = fetch("id_yct", f"{STREAMNET}/13", where="CompiledBy = 'IDFG'", fields="StreamName,UseType,Year")
    if not len(y):
        return [], []
    name = y.StreamName.fillna("").str.replace(r"^Unnamed Stream.*$", "", regex=True)
    return [], [_waters(y, name, "Yellowstone cutthroat trout water (IDFG, via StreamNet)")]


# ---- Pennsylvania ----
PFBC = "https://fbweb.pa.gov/arcgis/rest/services/PFBC_Map_Services"
# PFBC's Class A wild trout layer: its own map services leave it out, DCNR's Conservation Explorer serves it
PA_CLASS_A = "https://conservationexplorer.dcnr.pa.gov/arcgis/rest/services/PA_Public/ClassAStreams/MapServer/0"


def _pfbc_stocked():
    """(year, service) of the newest of PFBC's yearly stocked-sections services (TroutStocked2025,
    TroutStockedSections_2026, ...): a new one is published each season."""
    try:
        names = [s["name"].split("/")[-1] for s in requests.get(f"{PFBC}?f=json", headers=UA, timeout=60).json()["services"]]
    except (requests.RequestException, ValueError, KeyError):
        return None, None
    yrs = {int(m.group(1)): n for n in names if (m := re.fullmatch(r"TroutStocked(?:Sections)?_?(\d{4})", n))}
    return (max(yrs), yrs[max(yrs)]) if yrs else (None, None)


def _pa():
    ev, wa = [], []
    a = fetch("pa_class_a", PA_CLASS_A, fields="WtrName,Fishery")
    if len(a):
        # Fishery: "Brown", "Brook", "Mixed Brook/Brown", "Wild Brown Trout Fishery"
        fish = a.Fishery.fillna("").str.replace(r"(?i)^wild\s+|\s*trout fishery$", "", regex=True).str.strip().str.lower()
        wa.append(_waters(a, a.WtrName, ["Class A wild trout stream" + (f" ({f_} trout)" if f_ else "") + " (PFBC)"
                                         for f_ in fish]))
    n = fetch("pa_natural_repro", f"{PFBC}/Trout_NaturalReproduction/MapServer/0", fields="WtrName,Limits")
    if len(n):
        wa.append(_waters(n, n.WtrName, "Wild trout stream: natural reproduction (PFBC)"))
    r = fetch("pa_special_regs", f"{PFBC}/Special_Regulations/MapServer/2", where="Reg_Type = 'Trout'",
              fields="WtrName,Spec_Reg_1")
    if len(r):
        wa.append(_waters(r, r.WtrName, r.Spec_Reg_1.fillna("Special trout regulations").str.strip() + " (PFBC)"))
    yr, svc = _pfbc_stocked()
    s = fetch(f"pa_stocked_{yr}", f"{PFBC}/{svc}/MapServer/0") if svc else _EMPTY
    if len(s) and "WtrName" in s:
        num = lambda c: pd.to_numeric(s[c], errors="coerce").fillna(0) if c in s else pd.Series(0, index=s.index)
        spp = (("brook", num("TotalBrookStocked")), ("brown", num("TotalBrownStocked")),
               ("rainbow", num("TotalRainbowStocked")), ("golden", num("TotalGoldenStocked")))
        what = [", ".join(f"{int(v[i]):,} {sp}" for sp, v in spp if v[i] > 0) for i in s.index]
        y = pd.to_numeric(s["StockingYear"], errors="coerce").fillna(yr) if "StockingYear" in s else pd.Series(yr, index=s.index)
        ev.append(_ev(s, "PFBC stocking", s.WtrName, y.values, True,
                      [f"stocked with trout in {int(y_)}" + (f" ({w_})" if w_ else "") for y_, w_ in zip(y, what)], lake=False))
    k = fetch("pa_stocked_lakes", f"{PFBC}/PFBC_Stocked_Trout_Waters/MapServer/5", fields="WtrName,GNIS_NAME")
    if len(k):
        ev.append(_ev(k, "PFBC stocking", k.WtrName.fillna(k.GNIS_NAME), THIS_YEAR, True,
                      "on PFBC's list of trout-stocked lakes (approved trout waters)", lake=True))
    return ev, wa


# ---- Delaware ----
DE = "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Society/DE_Fishing_Access/FeatureServer/1"
def _de():
    t = fetch("de_trout", DE, fields="WATERBODYNAME,RESTRICTION")
    if not len(t):
        return [], []
    ffo = t.RESTRICTION.fillna("").str.contains("Fly Fishing Only", case=False)
    ev = [_ev(t, "DE DNREC stocking", t.WATERBODYNAME, THIS_YEAR, True,
              ["a Delaware designated trout stream, stocked each spring" + (" (fly fishing only)" if f_ else "") for f_ in ffo],
              lake=False)]
    wa = [_waters(t, t.WATERBODYNAME, ["Delaware designated trout stream" + (", fly fishing only" if f_ else "") + " (DNREC)"
                                       for f_ in ffo])]
    return ev, wa


# ---- eastern brook trout patches ----
TU = ("https://services1.arcgis.com/754BERmVIq3RqSf8/arcgis/rest/services/"
      "Most_Recent_Brook_Trout_Portolio_Assessment_Results/FeatureServer/0")
def _tu():
    p = fetch("tu_brook", TU, fields="Trout_community,Portfolio_category")
    if not len(p):
        return [], []
    # (Pennsylvania's patches say only "Allopatric" / "Sympatric": alone, or with other trout species not named)
    com = p.Trout_community.fillna("").replace({"Allopatric EBT": "brook trout only", "Sympatric EBT & BNT": "brook and brown trout",
                                                "Sympatric EBT, BNT, & RBT": "brook, brown and rainbow trout",
                                                "Sympatric EBT & RBT": "brook and rainbow trout", "Allopatric": "brook trout only",
                                                "Sympatric": "brook trout with other trout",
                                                "Sympatric brook trout": "brook trout with other trout"})
    return [], [_waters(p, com, "Wild brook trout patch (EBTJV / Trout Unlimited)")]


_BY_SOURCE = (("ct_trout", _ct), ("vt_trout", _vt), ("va_trout", _va), ("ga_trout", _ga), ("wy_trout", _wy),
              ("id_trout", _id), ("pa_trout", _pa), ("de_trout", _de), ("tu_brook_trout", _tu))       # state designations first: a reach's label is the first that covers it
_done = None
def _load():
    global _done
    if _done is None:
        ev, wa = [], []
        for src, fn in _BY_SOURCE:
            if has(src):
                e, w = fn()
                ev += e
                wa += w
        _done = (ev, wa)
    return _done


def evidence():
    """List of evidence GeoDataFrames (possibly empty)."""
    return [e for e in _load()[0] if len(e)]


def waters():
    """One GeoDataFrame of trout-water polygons (possibly empty), in the columns 11_context.py uses."""
    wa = [w for w in _load()[1] if len(w)]
    if not wa:
        return gpd.GeoDataFrame({"Name": pd.Series(dtype=str), "Designation": pd.Series(dtype=str),
                                 "Designation_Boundary": pd.Series(dtype=str), "broad": pd.Series(dtype=bool)},
                                geometry=[], crs=CRS)
    out = gpd.GeoDataFrame(pd.concat(wa, ignore_index=True), crs=CRS)
    return out[~out.geometry.is_empty & out.geometry.notna()].reset_index(drop=True)


if __name__ == "__main__":
    ev, wa = evidence(), waters()
    for e in ev:
        print(e.kind.iat[0], len(e), "| trout found", int(e.trout.sum()), "| none", int((~e.trout).sum()), "| at lakes", int(e.lake.sum()))
        print("   e.g.", e.label.iat[0], "|", e.water.iat[0])
    print("trout waters", len(wa), wa.Designation.str.replace(r":.*| \(.*", "", regex=True).value_counts().head(8).to_dict() if len(wa) else {})
