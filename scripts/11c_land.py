"""Land ownership: who owns each piece of a map, for the maps' "Land ownership" layer (the user, 2026-11-24: "add another
overlay layer that specifically shows public land, private but ngo/open/ non profit land, and strictly private.
include land owner names and their contact info"). 06_map.py adds the layer to both maps when this step has run;
map_land.js draws it from land_data.js, which a page loads the first time the layer is turned on.

Four classes, from PAD-US's own fields (no list of places):
  public    owned by a federal, state or local government or a public district (PAD-US Own_Type FED, STAT, LOC, DIST,
            JNT); where PAD-US doesn't record the owner, by its manager's type (the Corps of Engineers' lakes in
            Georgia are Own_Type UNK). Military land (PAD-US's Department of Defense boundaries) too
  open      private conservation or open land: owned by a non-profit or land trust (NGO), or private land PAD-US records
            as open to the public (Pub_Access OA, or RA: by permit, registration or set hours), easements that give
            the public access among them
  tribal    reservations and tribal land (PAD-US's tribal boundaries and holdings): the tribe's rules apply
  private   everything else: private land under a conservation easement without public access, private holdings PAD-US
            records closed or with access unknown, and all land PAD-US doesn't list
Where PAD-US's holdings overlap (two sources' copies of one park, an easement on a land trust's own land), a piece goes
to the most public owner, then to a holding whose manager is named, then to the smaller holding.

Access is the reaches' own: 11_context.py's restricted and no-public-access holdings (output/<area>/context/
cpad_restricted.gpkg: CPAD's in California, PAD-US's elsewhere), the polygons the stream popups' "⚠ Restricted Access"
and "⚠ No Public Access" read, are cut into the pieces, and a piece inside one says so. This layer and those lines
can't disagree, whatever rule 11_context.py applies to them. On a lake the access is left to the lake's own popup
(05d_lakes.py has a rule of its own). Elsewhere PAD-US's Pub_Access: open (OA); open on foot,
with rules on use (RA that 11_context.py doesn't flag: a licence, a pass, seasons or zones); not recorded (UK). In
California the flags come from CPAD, whose unflagged land is open.

Names (the user, 2026-11-25: "i want names of owners, clearly private land, clearly public land"): every name PAD-US
gives is shown, easements and private holdings included: the holding's own name, its owner's and manager's, an
easement's holder. The popups say where each comes from and as of when. Owners of private parcels come from the
counties' and states' parcel records in 11d_parcels.py, which runs next. A name PAD-US gives only as a code or a filler
("Unknown", "Private") is left out. Contacts are for organizations only: land_contacts.csv, each organization's own
website and office phone, read from its own pages and matched by organization (agency, unit, state agency, land
trust), never by place. Never a private person's phone, e-mail or address: a private piece links to its county's
official parcel viewer (county_viewers.csv), which has them. An organization with no entry shows its name only; the
biggest of those, and counties with no viewer, are printed as NOTEs. Each named piece of a map gets label spots, which
map_land.js shows once zoomed in.

Sources: PAD-US 4.1 (USGS Gap Analysis Project, public domain; its easements from the National Conservation Easement
Database and state programs), its full-attribute "Manager Name" service: fee holdings, easements, and the tribal and
military boundaries, with their owner, manager, designation and public access. Counties: the Census Bureau's TIGERweb.
Both through netfetch.py (the last good copy when a download fails; "as of" in the popups' source line).

Writes output/<area>/land_data.js: window.LAND = {the pieces (their rings as encoded polylines, simplified together so
neighbours keep one shared edge) and the tables of names, contacts, counties and flags they point to}. A run removes the
old file first, so one that fails leaves the map without the layer, never with an old one (build_stamp.py's publish
gate: 11c_land is a step the drivers go on without).
"""
import os, re, csv, json, datetime as dt, numpy as np, pandas as pd, geopandas as gpd, shapely, pyogrio
from shapely.geometry import box
from config import REGIONS, CRS, EPSG, MAP_OUT, SHARED_DERIVED, NATIONAL, has
import areaclip, netfetch

HERE = os.path.dirname(os.path.abspath(__file__))
PADUS = "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Manager_Name_PADUS/FeatureServer/0"
COUNTIES = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1"
FIELDS = ("FeatClass,Own_Type,Own_Name,Loc_Own,Mang_Type,Mang_Name,Loc_Mang,Des_Tp,Unit_Nm,State_Nm,Pub_Access,"
          "EsmtHldr,EHoldTyp")
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
GRID_M = 1.0          # every outline is snapped to a 1 m grid before the pieces are cut: two sources' shared edges agree
SIMPLIFY_M = 12       # the pieces are simplified together by this much: 2-3 screen pixels at zoom 15
MIN_PIECE_M2 = 400    # a piece smaller than this after simplifying isn't drawn (a sliver between two sources' edges)
LABEL_M2 = 150_000    # a named part this big gets its name written in it (about 25 screen pixels across at zoom 13)
OUT = f"{MAP_OUT}/land_data.js"
if not os.environ.get("LAND_WHO") and os.path.exists(OUT):
    os.remove(OUT)      # a run that fails leaves the map no land layer, never an old one (build_stamp.py's publish gate)

PUBLIC = {"FED", "STAT", "LOC", "DIST", "JNT", "TERR"}
NAMED = PUBLIC | {"NGO", "TRIB"}        # the owners whose names a piece may show
CLASSES = ["public", "open", "tribal", "private"]        # map_land.js's colours and words, in this order
KIND = {"FED": "fed", "STAT": "state", "LOC": "local", "DIST": "district", "JNT": "joint", "NGO": "ngo",
        "TRIB": "tribe", "TERR": "territory"}
# PAD-US 4 agency codes (Own_Name, Mang_Name), as the popups word them
AGENCY = {"USFS": "USDA Forest Service", "NPS": "National Park Service", "FWS": "U.S. Fish and Wildlife Service",
          "BLM": "Bureau of Land Management", "USACE": "U.S. Army Corps of Engineers", "USBR": "Bureau of Reclamation",
          "TVA": "Tennessee Valley Authority", "DOD": "Department of Defense", "DOE": "Department of Energy",
          "NRCS": "Natural Resources Conservation Service", "NOAA": "NOAA", "BOEM": "Bureau of Ocean Energy Management",
          "ARS": "Agricultural Research Service", "BIA": "Bureau of Indian Affairs", "OTHF": "a federal agency",
          "SDC": "conservation department", "SDNR": "natural resources department", "SDOL": "lands department",
          "SFW": "fish and wildlife agency", "SPR": "state parks", "SLB": "state land board", "CNTY": "a county",
          "CITY": "a city or town", "UNKL": "a local government", "REG": "a regional agency", "RWD": "a water district",
          "NGO": "a non-profit", "TRIB": "a tribe", "JNT": "joint owners"}
# PAD-US 4 designation types (Des_Tp)
DESIG = {"NF": "National Forest", "NP": "National Park", "NM": "National Monument or Landmark",
         "NRA": "National Recreation Area", "NWR": "National Wildlife Refuge", "NT": "National Scenic or Historic Trail",
         "NSBV": "National Scenic Area", "WA": "Wilderness Area", "WSA": "Wilderness Study Area",
         "WSR": "Wild and Scenic River", "IRA": "Inventoried Roadless Area", "ACEC": "Area of Critical Environmental Concern",
         "NCA": "Conservation Area", "PUB": "National Public Lands", "REC": "Recreation Management Area",
         "RMA": "Resource Management Area", "RNA": "Research Natural Area", "SDA": "Special Designation Area",
         "MIL": "Military Land", "FOTH": "Federal land", "TRIBL": "Native American Land", "SP": "State Park",
         "SW": "State Wilderness", "SCA": "State Conservation Area", "SREC": "State Recreation Area",
         "SRMA": "State Resource Management Area", "SHCA": "State Historic or Cultural Area", "SOTH": "State land",
         "LP": "Local Park", "LREC": "Local Recreation Area", "LCA": "Local Conservation Area",
         "LRMA": "Local Resource Management Area", "LHCA": "Local Historic or Cultural Area", "LOTH": "Local land",
         "PCON": "Private Conservation", "PREC": "Private Recreation or Education", "PPRK": "Private Park",
         "PFOR": "Private Forest Stewardship", "PAGR": "Private Agricultural", "PHCA": "Private Historic or Cultural",
         "POTH": "Private land", "REA": "Research or Educational Area", "HCA": "Historic or Cultural Area",
         "WPA": "Watershed Protection Area", "ACC": "Access Area", "CONE": "Conservation Easement",
         "AGRE": "Agricultural Easement", "FORE": "Forest Stewardship Easement",
         "RECE": "Recreation or Education Easement", "HCAE": "Historic or Cultural Easement", "RANE": "Ranch Easement",
         "OTHE": "Easement", "UNKE": "Easement"}
STATES = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
          "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
          "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
          "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
          "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
          "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}
STATE_NAMES = {"AL": "Alabama", "AZ": "Arizona", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
               "DE": "Delaware", "GA": "Georgia", "ID": "Idaho", "KY": "Kentucky", "MA": "Massachusetts",
               "MD": "Maryland", "ME": "Maine", "MT": "Montana", "NC": "North Carolina", "NH": "New Hampshire",
               "NJ": "New Jersey", "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OR": "Oregon",
               "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "TN": "Tennessee", "UT": "Utah",
               "VA": "Virginia", "VT": "Vermont", "WA": "Washington", "WV": "West Virginia", "WY": "Wyoming"}
# a name field that names no one: PAD-US's codes and fillers
GENERIC = re.compile(r"(?i)^(|unknown.*|unk|unkl|unspecified|other.*|none|n/?a|private.*|pvt|ngo|stat|loc|fed|jnt|"
                     r"desg|city|cnty|county|state|sdnr|sfw|spr|sdc|oths|reg|rwd|us|trib|city land|county land|"
                     r"state fish and wildlife|other state land|state university|state department of .*|"
                     r"unknown (local|federal) government|unknown joint holder|land trust|forest service region.*|"
                     r"(the )?state of [a-z .]+|[a-z]{2,4} state|[a-z .]+ state government|state of [a-z]+ \(\w+\)|"
                     r"us federal|federal|municipality|town|.*\d{5,}.*)$")


def named(x):
    x = re.sub(r"\s+", " ", str(x if isinstance(x, str) else "")).strip()
    return "" if GENERIC.match(x) else x


def org_name(x, ngo=False):
    """A name as the map shows it (an owner's, a manager's, an easement's holder's, a holding's): '' where PAD-US gives
    only a code or a filler."""
    x = named(x)
    return x if x and re.search(r"[A-Za-z]{3}", x) and not re.fullmatch(r"[A-Z]{0,3}[\d-]+", x) else ""


# ---- the map's boxes ----
boxes = shapely.union_all([box(*v["bbox"]) for v in REGIONS.values()])
_st = areaclip.outline()
area = shapely.set_precision(boxes if _st is None else shapely.intersection(boxes, _st), GRID_M)
shapely.prepare(area)
W, S, E, N = gpd.GeoSeries([boxes], crs=CRS).to_crs(4326).total_bounds


def arcgis(url, fields, what, where="1=1"):
    """Every feature of an ArcGIS layer in the map's boxes, in the area's CRS, as 11_context.py's esri(): a page the
    server can't answer is asked for in smaller ones; the last good copy when the layer can't be read."""
    def fetch():
        feats, off, size = [], 0, 1000
        while True:
            try:
                r = netfetch.fetch("GET", f"{url}/query", tries=4, timeout=300, headers=UA, params=dict(
                    where=where, geometry=f"{W},{S},{E},{N}", geometryType="esriGeometryEnvelope", inSR=4326,
                    spatialRel="esriSpatialRelIntersects", outFields=fields, outSR=EPSG, f="geojson",
                    resultOffset=off, resultRecordCount=size), ok=lambda r: r.ok and "features" in r.json())
            except netfetch.FetchError:
                if size <= 25:
                    raise
                size //= 4                 # a page too big for the server: smaller ones
                continue
            js = r.json()
            feats += js["features"]
            if len(js["features"]) < size or not js.get("properties", {}).get("exceededTransferLimit",
                                                                                 len(js["features"]) == size):
                return feats
            off += len(js["features"])
    feats = netfetch.last_good(f"land-{netfetch.key(url, where, fields, W, S, E, N, EPSG)}", fetch, what)
    return gpd.GeoDataFrame.from_features(feats, crs=CRS) if feats else gpd.GeoDataFrame(geometry=[], crs=CRS)


def _snap(x):
    try:
        return shapely.set_precision(x, GRID_M)
    except shapely.errors.GEOSException:
        return shapely.set_precision(shapely.buffer(x, 0), GRID_M)


def polys(geoms):
    """Each geometry made flat (NHD's areas carry heights), valid, snapped to the grid, cut to the map and kept to its
    polygons."""
    g = shapely.make_valid(shapely.force_2d(np.asarray(geoms, dtype=object)))
    try:
        g = shapely.set_precision(g, GRID_M)
    except shapely.errors.GEOSException:          # one that snapping can't keep valid: each on its own, buffered
        g = np.asarray([_snap(x) for x in g], dtype=object)
    g = shapely.intersection(g, area)
    out = []
    for x in g:
        if x is None or x.is_empty:
            out.append(shapely.Polygon())
        elif x.geom_type in ("Polygon", "MultiPolygon"):
            out.append(x)
        else:
            ps = [p for p in shapely.get_parts(x) if p.geom_type in ("Polygon", "MultiPolygon")]
            out.append(shapely.union_all(ps, grid_size=GRID_M) if ps else shapely.Polygon())
    return np.asarray(out, dtype=object)


# ---- PAD-US: fee holdings, easements, tribal and military boundaries ----
pad = arcgis(PADUS, FIELDS, "PAD-US land")
for c in FIELDS.split(","):
    if c not in pad:
        pad[c] = None
pad = pad[pad.FeatClass.isin(["Fee", "Easement"]) | (pad.FeatClass.eq("Proclamation") & (
    pad.Own_Type.eq("TRIB") | pad.Mang_Type.eq("TRIB") | pad.Mang_Name.eq("DOD")))].reset_index(drop=True)
pad["geometry"] = polys(pad.geometry.values)
pad = pad[pad.area > 1].reset_index(drop=True)
FC = pad.FeatClass.values
fee, ease, procl = FC == "Fee", FC == "Easement", FC == "Proclamation"
own = pad.Own_Type.fillna("UNK").values
mng = pad.Mang_Type.fillna("UNK").values
# whose type decides: the owner's; on a holding whose owner PAD-US doesn't record, its manager's (not on an easement:
# there the manager is the holder, and the owner of the land is someone else)
typ = np.where(~ease & np.isin(own, ["UNK", "DESG"]), mng, own)
tribal = (typ == "TRIB") | (procl & ((own == "TRIB") | (mng == "TRIB")))
cls = np.select([tribal, procl | np.isin(typ, list(PUBLIC)), typ == "NGO", pad.Pub_Access.isin(["OA", "RA"]).values],
                ["tribal", "public", "open", "open"], "private")
# overlapping holdings: the most public first (a public body's land, a tribe's, a land trust's, then private land open
# to the public; fee holdings before easements), then one whose manager is named, then the smaller
known = np.array([bool(named(a)) or b not in ("UNK", "") for a, b in zip(pad.Loc_Mang, pad.Mang_Name.fillna(""))])
rank = ((np.select([cls == "public", cls == "tribal", typ == "NGO", cls == "open"], [0, 1, 2, 3], 4) * 3
         + np.where(fee, 0, np.where(ease, 1, 2))) * 2 + ~known) * 1e12 + pad.area.values
pad["cls"], pad["typ"] = cls, typ
print(f"PAD-US 4.1: {len(pad):,} holdings in the boxes:", pad.groupby(["FeatClass", "cls"]).size().to_dict())

# ---- 11_context.py's restricted and closed holdings: the reaches' access flags ----
fp = f"{MAP_OUT}/context/cpad_restricted.gpkg"
if os.path.exists(fp):
    flags = gpd.read_file(fp).to_crs(CRS)
else:
    netfetch.note("no context/cpad_restricted.gpkg (11_context.py not run): the land layer shows no access flags")
    flags = gpd.GeoDataFrame({"ACCESS_TYP": [], "UNIT_NAME": []}, geometry=[], crs=CRS)
flags["geometry"] = polys(flags.geometry.values)
flags = flags[flags.area > 1].reset_index(drop=True)

# ---- counties, for the private land's parcel viewer ----
cty = arcgis(COUNTIES, "GEOID,NAME,STATE", "TIGERweb counties")
if len(cty):
    cty["geometry"] = polys(cty.geometry.values)
    cty = cty[cty.area > 1].reset_index(drop=True)

# ---- water: the map's lakes (05d_lakes.py) and NHD's river areas. Water no holding covers is no one's private land:
# it isn't drawn (the Lakes layer draws the lakes). A lake inside a holding keeps the holding's words but makes no
# claim on access: the lake's own popup gives it, by 05d_lakes.py's own rule, until 05d reads publicland.py too (R13's
# follow-up, general-rules 2026-11-24) ----
wat, lake_ = [], []
if os.path.exists(f"{SHARED_DERIVED}/lakes.gpkg"):
    wat.append(gpd.read_file(f"{SHARED_DERIVED}/lakes.gpkg").to_crs(CRS).geometry.values)
    lake_.append(np.ones(len(wat[-1]), bool))
_bb = tuple(gpd.GeoSeries([boxes], crs=CRS).to_crs(4269).total_bounds)
for hu in sorted({h for v in REGIONS.values() for h in v["hu4"]}):
    p_ = f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg"          # as areaclip.river() reads them
    if os.path.exists(p_):
        lyr = next(l for l in pyogrio.list_layers(p_)[:, 0] if l.lower() == "nhdarea")
        a_ = gpd.read_file(p_, layer=lyr, bbox=_bb, columns=["ftype"])
        a_.columns = [c.lower() if c != "geometry" else c for c in a_.columns]
        wat.append(a_[a_.ftype == 460].to_crs(CRS).geometry.values)        # StreamRiver
        lake_.append(np.zeros(len(wat[-1]), bool))
water = polys(np.concatenate(wat)) if wat else np.asarray([], dtype=object)
is_lake = np.concatenate(lake_) if lake_ else np.zeros(0, bool)
_w = shapely.area(water) > 1 if len(water) else np.zeros(0, bool)
water, is_lake = water[_w], is_lake[_w]

# ---- what each holding says ----
STRS = {}            # the names, one table the pieces point to


def s_(x):
    if not x:
        return None
    if x not in STRS:
        STRS[x] = len(STRS)
        S_.append(x)
    return STRS[x]


S_ = []


def body(kind, code, loc, st, county):
    """The words for an owner, manager or holder: its own name where PAD-US gives one, else what its code says."""
    if kind == "FED":
        return AGENCY.get(code, "a federal agency")
    n = org_name(loc, ngo=kind == "NGO")
    if n:
        return n
    if kind == "STAT":
        return f"State of {STATE_NAMES.get(st, st)}" + (f" ({AGENCY[code]})" if code in AGENCY else "")
    if kind == "LOC" and code == "CNTY" and county:
        return county
    if kind == "TRIB":
        return ""                      # "Tribal land" says it; the unit names the reservation
    return AGENCY.get(code) or {"LOC": "a local government", "DIST": "a public district", "JNT": "joint owners",
                                "NGO": "a non-profit"}.get(kind, "")


def read_csv(name, key):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        netfetch.note(f"no {name}: the land layer has nothing from it")
        return []
    with open(p, newline="", encoding="utf-8") as f:          # (the file's own notes are its "#" lines)
        return [r for r in csv.DictReader(ln for ln in f if not ln.startswith("#")) if r.get(key)]


# contacts: the organizations' own pages, matched by organization on "kind|code|state|name|unit" (body() above)
CONTACTS = [(re.compile(r["match"], re.I), r) for r in read_csv("land_contacts.csv", "match")]
VIEWERS = {r["geoid"]: r for r in read_csv("county_viewers.csv", "geoid")}
ORGS, CTY, FLAGS, missing = {}, {}, {}, {}


def contact(who):
    for i, (rx, r) in enumerate(CONTACTS):
        if rx.search(who):
            return ORGS.setdefault(i, len(ORGS))
    return None


def county_ix(c):
    if c < 0:
        return None
    r = cty.iloc[c]
    geoid = str(r.GEOID)
    if geoid not in CTY:
        v = VIEWERS.get(geoid) or VIEWERS.get(geoid[:2]) or {}
        CTY[geoid] = (len(CTY), [f"{r.NAME}, {STATES.get(str(r.STATE), str(r.STATE))}", v.get("name", ""),
                                 v.get("url", ""), v.get("at_point", "")])
    return CTY[geoid][0]


def flag_ix(g, own_name=""):
    """The flag's entry: its status and its holding's name, as 11_context.py's file gives them, and its date."""
    u = flags.UNIT_NAME.iloc[g] if isinstance(flags.UNIT_NAME.iloc[g], str) else ""
    asof = re.search(r"\s*\(as of [^)]*\)$", u)
    unit = u[:asof.start()].strip() if asof else u.strip()
    key = (flags.ACCESS_TYP.iloc[g], unit, asof.group(0).strip() if asof else "")
    return FLAGS.setdefault(key, len(FLAGS))


# The words of each holding: its class, name, owner, manager, kind, public access, easement holder and contact; the
# pieces it covers take them, with their county's parcel viewer and the access flags over them (below)
cty_of = np.full(len(pad), -1)
if len(cty) and len(pad):
    hi, ci = shapely.STRtree(cty.geometry.values).query(shapely.point_on_surface(pad.geometry.values), predicate="within")
    cty_of[hi] = ci
HP, WHO = [], []
for h, r in enumerate(pad.itertuples()):
    c = int(cty_of[h])
    county = cty.NAME.iloc[c] if c >= 0 else ""
    st = r.State_Nm if isinstance(r.State_Nm, str) and r.State_Nm else STATES.get(str(cty.STATE.iloc[c]), "") if c >= 0 else ""
    p = {"c": CLASSES.index(r.cls), "a": r.Pub_Access if r.Pub_Access in ("OA", "RA", "UK", "XA") else "UK"}
    if has("cpad") and r.FeatClass != "Easement" and r.cls != "private":
        p["a"] = "OA"              # California's flags are CPAD's (cut in below): unflagged CPAD land is open
    d = DESIG.get(r.Des_Tp if isinstance(r.Des_Tp, str) else "")
    who = ""
    if r.typ in NAMED or r.FeatClass == "Proclamation":
        # a public, tribal or non-profit holding: its name, its owner, and its manager where that is another
        p["n"] = s_(org_name(r.Unit_Nm))
        # one body when owner and manager are of one type and code (two wordings of one agency): its better name
        same = own[h] == mng[h] and str(r.Own_Name) == str(r.Mang_Name)
        o_loc = r.Loc_Own if org_name(r.Loc_Own) or not same else r.Loc_Mang
        o_ = body(own[h], r.Own_Name, o_loc, st, county) if own[h] in NAMED else ""
        m_ = body(mng[h], r.Mang_Name, r.Loc_Mang, st, county) if mng[h] in NAMED and not ease[h] and not same else ""
        p["o"] = s_(o_)
        if m_ and m_.lower() != o_.lower():
            p["m"] = s_(m_)
        if p["n"] is not None and S_[p["n"]].lower() in (o_.lower(), m_.lower()):
            p.pop("n")                 # the holding is named for its owner: said once
        # whom to ask: the manager, else the owner. "kind|code|state|names|unit": what land_contacts.csv matches
        k_, c_ = (mng[h], r.Mang_Name) if m_ else (own[h], r.Own_Name)
        if k_ not in NAMED and mng[h] in NAMED:
            k_, c_ = mng[h], r.Mang_Name
        if k_ in NAMED:
            nms = (r.Loc_Mang, r.Loc_Own) if m_ else (r.Loc_Own, r.Loc_Mang)
            who = (f"{KIND.get(k_, k_.lower())}|{c_}|{st}|" + " / ".join(dict.fromkeys(named(x) for x in nms if named(x)))
                   + f"|{named(r.Unit_Nm)}")
        if d:
            p["d"] = s_(d)
    else:
        # a private holding (or one whose owner PAD-US doesn't record): its name and its owner's, as PAD-US gives them
        p["n"] = s_(org_name(r.Unit_Nm))
        o_ = org_name(r.Loc_Own)
        if o_:
            p["o"] = s_(o_)
        if p["n"] is not None and o_ and S_[p["n"]].lower() == o_.lower():
            p.pop("n")
        if r.FeatClass != "Easement" and r.cls == "open":
            p["d"] = s_("Private land open to the public")
    if ease[h]:
        # an easement: the land's owner keeps the land, the holder (a land trust, an agency) holds the easement
        p["e"] = 1
        ht = r.EHoldTyp if isinstance(r.EHoldTyp, str) else ""
        hc = r.Mang_Name if mng[h] == ht and isinstance(r.Mang_Name, str) else ""         # the holder's agency code
        hn = org_name(r.EsmtHldr) or (body(ht, hc, "", st, county) if ht in NAMED else "")
        if hn:
            p["h"] = s_(hn)
        if ht in NAMED:
            who = f"easement|{ht}|{st}|{named(r.EsmtHldr)}|{hc}"
        if d and "d" not in p:
            p["d"] = s_(d)
    if who:
        k = contact(who)
        if k is not None:
            p["k"] = k
    p["_y"] = r.typ not in NAMED       # land a private owner keeps (or one PAD-US doesn't name): the parcel viewer
    HP.append(p)
    WHO.append(who)
pad["who"] = WHO
if os.environ.get("LAND_WHO"):
    # the organizations and their area on this map, matched or not: for writing land_contacts.csv
    w = pad[pad.who.ne("")].assign(sqmi=pad.area / 2.59e6).groupby("who").sqmi.sum().sort_values(ascending=False)
    hit = {x: next((r["name"] for rx, r in CONTACTS if rx.search(x)), "") for x in w.index}
    pd.DataFrame({"area": os.environ.get("AREA", ""), "who": w.index, "sqmi": w.round(2).values,
                  "contact": [hit[x] for x in w.index]}).to_csv(os.environ["LAND_WHO"], index=False)
    print(f"{len(w):,} organizations, {sum(map(bool, hit.values())):,} with a contact: {os.environ['LAND_WHO']}")
    raise SystemExit(0)

# ---- the pieces: every outline cut against every other ----
lines = shapely.boundary(np.concatenate([[area], pad.geometry.values, flags.geometry.values, water,
                                         cty.geometry.values if len(cty) else []]).astype(object))
net = shapely.union_all(lines[~shapely.is_empty(lines)], grid_size=GRID_M)
faces = np.asarray(shapely.get_parts(shapely.polygonize(shapely.get_parts(net))))
pts = shapely.point_on_surface(faces)
keep = shapely.contains_xy(area, shapely.get_x(pts), shapely.get_y(pts))
faces, pts = faces[keep], pts[keep]


def covering(geoms, order):
    """For each piece, the index of the holding of `geoms` that covers it and comes first by `order`; -1 for none."""
    out = np.full(len(pts), -1)
    if len(geoms):
        pi, gi = shapely.STRtree(geoms).query(pts, predicate="within")
        d = pd.DataFrame({"p": pi, "g": gi, "o": np.asarray(order)[gi]}).sort_values(["p", "o", "g"]).drop_duplicates("p")
        out[d.p.values] = d.g.values
    return out


hold = covering(pad.geometry.values, rank)
wet = covering(water, np.where(is_lake, 0, 1))          # a lake before a river area where both are
cnty = covering(cty.geometry.values, np.arange(len(cty))) if len(cty) else np.full(len(pts), -1)
# every flagged holding over a piece, "No Public Access" first: a reach there names one of them
fl_of = [[] for _ in range(len(pts))]
if len(flags):
    pi, gi = shapely.STRtree(flags.geometry.values).query(pts, predicate="within")
    for p_, g_ in sorted(zip(pi, gi), key=lambda t: (t[0], flags.ACCESS_TYP.iloc[t[1]] != "No Public Access", t[1])):
        fl_of[p_].append(g_)
print(f"{len(faces):,} pieces cut; {int((hold >= 0).sum()):,} in PAD-US holdings, "
      f"{sum(map(bool, fl_of)):,} under access flags")

props = []
for i in range(len(faces)):
    h = int(hold[i])
    if h >= 0:
        p = dict(HP[h])
        if p.pop("_y"):
            p["y"] = county_ix(int(cnty[i]))
        if "k" not in p and WHO[h]:
            missing[WHO[h]] = missing.get(WHO[h], 0) + faces[i].area
    elif wet[i] >= 0:
        props.append(None)             # water no holding covers: not drawn
        continue
    else:
        p = {"c": 3, "y": county_ix(int(cnty[i]))}
    if p.get("y") is None:
        p.pop("y", None)
    on_lake = h >= 0 and wet[i] >= 0 and is_lake[wet[i]]
    if on_lake:
        p["a"] = "L"                   # access on a lake: its own popup's (above)
    own_nm = S_[p["n"]] if h >= 0 and p.get("n") is not None else ""
    fl = [] if on_lake else [flag_ix(g, own_nm) for g in fl_of[i]]
    if fl:
        p["g"] = list(dict.fromkeys(fl))
    props.append(p)

# ---- merged by what they say, simplified together, smallest dropped ----
key = pd.Series([json.dumps(p, sort_keys=True) if p is not None else "" for p in props])
groups = {k: v for k, v in key.groupby(key).indices.items() if k}
gkeys = list(groups)
geoms = np.asarray([shapely.coverage_union_all(faces[groups[k]]) for k in gkeys], dtype=object)
geoms = shapely.coverage_simplify(geoms, SIMPLIFY_M)
parts, pkeys = [], []
for k, g in zip(gkeys, geoms):
    for q in shapely.get_parts(g):
        if q.geom_type == "Polygon" and q.area >= MIN_PIECE_M2:
            parts.append(q)
            pkeys.append(k)
land = gpd.GeoDataFrame({"k": pkeys}, geometry=parts, crs=CRS)
land["c"] = [json.loads(k)["c"] for k in land.k]
# where a piece's name is written (map_land.js, once zoomed in): inside each of its parts big enough to hold it
_nm = np.asarray([json.loads(k).get("n") is not None or json.loads(k).get("o") is not None for k in land.k])
_big = _nm & (land.area.values >= LABEL_M2)
land["lab"] = None
if _big.any():
    import shapely.ops
    land.loc[_big, "lab"] = gpd.GeoSeries([shapely.ops.polylabel(q, 10) for q in land.geometry.values[_big]],
                                          crs=CRS).to_crs(4326).values
tot = land.area.sum()
print("land:", ", ".join(f"{CLASSES[c]} {land.area[land.c == c].sum() / 2.59e6:,.0f} sq mi "
                         f"({land.area[land.c == c].sum() / tot:.0%})" for c in range(4)),
      f"| {len(land):,} polygons in {len(gkeys):,} groups")


# ---- written out: encoded polylines (Google's, 1e-5 degrees, as map_routes.js) ----
def enc(ring):
    out, la0, lo0 = [], 0, 0
    for lo, la in ring:
        la1, lo1 = round(la * 1e5), round(lo * 1e5)
        if (la1, lo1) == (la0, lo0) and out:
            continue
        for d in (la1 - la0, lo1 - lo0):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        la0, lo0 = la1, lo1
    return "".join(out)


ll = land.to_crs(4326)
feats = []
for k, gk in ll.groupby("k", sort=False):
    p = json.loads(k)
    p["r"] = [[enc(list(q.exterior.coords)[:-1])] + [enc(list(h.coords)[:-1]) for h in q.interiors] for q in gk.geometry]
    labs = [[round(q.y * 1e5), round(q.x * 1e5)] for q in gk.lab if q is not None]
    if labs:
        p["l"] = labs
    feats.append(p)
crow = {i: r for i, (rx, r) in enumerate(CONTACTS)}
LAND = {"built": dt.date.today().isoformat(), "src": "PAD-US 4.1 (USGS)" + netfetch.asof("PAD-US land"),
        "cpad": has("cpad"), "s": list(STRS),
        "o": [[crow[i]["name"], crow[i].get("url", ""), crow[i].get("phone", "")] for i in sorted(ORGS, key=ORGS.get)],
        "y": [v for _, v in sorted(CTY.values())], "g": [list(k) for k in FLAGS], "f": feats}
with open(OUT + ".tmp", "w") as f:
    f.write("window.LAND=" + json.dumps(LAND, separators=(",", ":"), ensure_ascii=False) + ";\n")
os.replace(OUT + ".tmp", OUT)
print(f"land_data.js {os.path.getsize(OUT) / 1e6:.2f} MB: {len(feats):,} pieces, {len(ORGS)} contacts, "
      f"{len(CTY)} counties ({sum(1 for _, v in CTY.values() if v[2])} with a parcel viewer), {len(FLAGS)} flags")
for w_, a_ in sorted(missing.items(), key=lambda t: -t[1])[:12]:
    if a_ > 2e6:
        netfetch.note(f"no contact in land_contacts.csv for {w_}: {a_ / 2.59e6:,.1f} sq mi of the map")
for g_, (_, v) in sorted(CTY.items()):
    if not v[2]:
        netfetch.note(f"no parcel viewer in county_viewers.csv for {v[0]} ({g_})")
