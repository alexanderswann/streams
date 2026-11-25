"""Owner names for the private parcels beside the water (the user, 2026-11-25: "the land ownership layer is horrible, i
want names of owners, clearly private land, clearly public land etc").

For each map: every parcel on the land layer's private land (11c_land.py's land_data.js) that touches a drawn stream or
a lake's shore within TOUCH_M, from the official parcel layers in scripts/parcel_sources.csv. Those are layers whose
terms allow reuse, and official layers that publish owner names openly with no reuse terms stated (the user's choice,
2026-11-25); never a layer whose terms restrict or forbid it, never a data broker.

What is kept: the parcel's outline, its owner's name as the source publishes it, the source and its date. Never a
mailing address, a phone number or an e-mail address. The popup links the county's official record (county_viewers.csv),
where the rest is. A name that a source withholds by law (a protected owner's placeholder, such as Connecticut's
"Current Owner") is shown as withheld and never looked for elsewhere.

The servers are asked only for parcels near the water (an ArcGIS distance query along the map's streams and lake shores,
a cell at a time), and only for the owner fields. A source that can't be read leaves its parcels out with a NOTE.
Offline, its last good copy is used (netfetch.py).

Output: MAP_OUT/parcels_data.js (window.PARCELS), which map_land.js loads with the land layer. A run that fails leaves no
old file (build_stamp.py's publish gate).
"""
import os, re, csv, sys, glob, json, math, datetime as dt
import numpy as np, geopandas as gpd, shapely, shapely.ops, shapely.geometry
from config import CRS, MAP_OUT, SHARED_DERIVED, AREA
import netfetch

TOUCH_M = 30            # a parcel within this of a drawn stream or a lake's shore (the parcels a fisher may need to cross)
SIMPLIFY_M = 3          # outlines drawn to about 3 m
CELL_M = 4000           # the water sent to a server a cell at a time
MAX_GEOM = 60000        # characters of geometry in one request at most; a bigger cell is asked for in quarters
FRESH_DAYS = 30         # a parcel layer fetched within this long is used again as it is: tax rolls change once a year
OUT = f"{MAP_OUT}/parcels_data.js"
if os.path.exists(OUT):
    os.remove(OUT)      # a run that fails leaves the map no parcels, never old ones
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
HERE = os.path.dirname(os.path.abspath(__file__))
# placeholders a source writes for an owner whose name the law withholds (besides the source's own, in the csv)
WITHHELD = re.compile(r"^(confidential|name withheld|withheld|protected|redacted|suppressed|not disclosed|exempt)$", re.I)
KEEP_UPPER = {"LLC", "LLP", "LP", "INC", "LTD", "PC", "PLLC", "II", "III", "IV", "USA", "US", "TR", "TRS", "DBA", "NA",
              "CT", "MA", "VT", "NY", "NC", "GA", "PA", "VA", "WY", "ID", "RI", "TN", "SC", "DE", "MD", "CA"}


def read_csv(name):
    with open(f"{HERE}/{name}") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def dec(s):
    """a Google-encoded ring (1e-5 degrees) as [(lon, lat), ...]"""
    out, la, lo, i = [], 0, 0, 0
    while i < len(s):
        for k in (0, 1):
            sh = r = 0
            while True:
                b = ord(s[i]) - 63; i += 1; r |= (b & 31) << sh; sh += 5
                if b < 32:
                    break
            d = ~(r >> 1) if r & 1 else r >> 1
            if k == 0:
                la += d
            else:
                lo += d
        out.append((lo / 1e5, la / 1e5))
    return out


def enc(coords):
    """[(lon, lat), ...] as a Google-encoded ring at 1e-5 degrees"""
    out, pla, plo = [], 0, 0
    for lo, la in coords:
        a, b = int(round(la * 1e5)), int(round(lo * 1e5))
        for d in (a - pla, b - plo):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63)); v >>= 5
            out.append(chr(v + 63))
        pla, plo = a, b
    return "".join(out)


# the mailing parts some owner fields carry, cut off with all that follows them: a care-of or attention line, a P.O.
# box, a street address, a ZIP code (the popup links the county's record instead; never a mailing address)
MAILING = [re.compile(p, re.I) for p in (
    r"\s*[,;]?\s*\b(c/o|c / o|care of|attn:?|attention)\b.*$",
    r"\s*[,;]?\s*\bp\.?\s*o\.?\s*(box|bx|drawer)\b.*$",
    r"\s*[,;]?\s*\b\d{1,6}[a-z]?\s+(?:[nsew]\.?\s+)?(?:[a-z0-9'.-]+\s+){0,3}(st|street|rd|road|ave|avenue|ln|lane|dr|drive|"
    r"hwy|highway|blvd|boulevard|ct|court|way|pl|place|pike|tpke|turnpike|cir|circle|ter|terrace|pkwy|parkway|trl|trail|"
    r"route|rte|rt)\b\.?.*$",
    r"\s*[,;]?\s*\b\d{5}(-\d{4})?\s*$")]


def unmail(name):
    for rx in MAILING:
        name = rx.sub("", name)
    return name.strip(" ,;&-")


def pretty(name):
    """a name as a source spells it, in capitals or not; capitals are written as a name is (Smith John A & Mary B)"""
    n = " ".join(str(name).replace(" ", " ").split()).strip(" ,;")
    if not n or n.upper() != n or not re.search(r"[A-Z]", n):
        return n
    def word(w):
        core = re.sub(r"[^A-Za-z]", "", w)
        if core.upper() in KEEP_UPPER or (core and not re.search(r"[AEIOUY]", core.upper()) and len(core) > 1):
            return w
        w = w.lower().capitalize() if not w[:1].isdigit() else w.lower()
        w = re.sub(r"^(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
        return re.sub(r"(['-])([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
    return " ".join(word(w) for w in n.split(" "))


def fill(tpl, props):
    """a template's {FIELD}s from a feature's properties, the field's case as the answer spells it (a layer's
    metadata may say Owner and its answers OWNER: Cherokee County, Georgia)"""
    low = {str(k).lower(): v for k, v in props.items()}
    out = re.sub(r"\{([^}]+)\}", lambda m: str(low.get(m.group(1).lower()) or "").strip(), tpl or "")
    return " ".join(out.split())


# ---- the land layer's private land and its counties ----
LD = f"{MAP_OUT}/land_data.js"
if not os.path.exists(LD):
    print(f"{AREA}: no land_data.js (11c_land.py made none), so no parcels")
    sys.exit(0)
L = json.loads(open(LD).read().split("=", 1)[1].rstrip().rstrip(";"))
cty_names = [y[0] for y in L["y"]]
priv, priv_y = [], []
for f in L["f"]:
    if f.get("c") != 3 or f.get("y") is None:
        continue
    for q in f["r"]:
        rings = [dec(r) for r in q]
        if len(rings[0]) >= 3:
            priv.append(shapely.make_valid(shapely.Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])))
            priv_y.append(f["y"])
priv = gpd.GeoSeries(priv, crs=4326).to_crs(CRS)
priv_y = np.asarray(priv_y)
ptree = shapely.STRtree(priv.values)
here = set(cty_names[i] for i in set(priv_y.tolist()))

# ---- the water: the map's streams (05_score's reaches, every range) and its lakes' shores ----
water = []
for p in glob.glob(f"{MAP_OUT}/*/streams_scored.gpkg"):
    water += list(gpd.read_file(p, columns=[]).to_crs(CRS).geometry.values)
if os.path.exists(f"{SHARED_DERIVED}/lakes.gpkg"):
    water += list(gpd.read_file(f"{SHARED_DERIVED}/lakes.gpkg", columns=[]).to_crs(CRS).geometry.boundary.values)
water = [g for g in water if g is not None and not g.is_empty]
wtree = shapely.STRtree(water)
x0, y0, x1, y1 = shapely.total_bounds(np.asarray(water, dtype=object)) if water else (0, 0, 0, 0)


def cells():
    """the ground within TOUCH_M of the water, CELL_M by CELL_M, as Esri polygons in degrees (a cell with too much in it
    as four smaller ones). The 30 m band is drawn here, valid, and sent as it is: a server asked to buffer the lines
    itself (a distance query) refused some cells, its own buffer being invalid ("24144: ... the instance is not valid",
    ArcGIS Online, 2026-11-25), even where the cell held no parcel at all"""
    def esri(bx):
        ix = wtree.query(bx.buffer(TOUCH_M), predicate="intersects")
        if not len(ix):
            return []
        band = shapely.union_all([water[i] for i in ix]).simplify(5).buffer(TOUCH_M, quad_segs=4)
        band = shapely.make_valid(shapely.intersection(band, bx).simplify(4))
        band = gpd.GeoSeries([band], crs=CRS).to_crs(4326).iloc[0]
        try:
            band = shapely.set_precision(band, 1e-6)          # what is sent: to 1e-6 degrees, valid
        except shapely.errors.GEOSException:                # a hole GEOS can't place on that grid: sent as it is
            pass
        band = shapely.make_valid(band)
        rings = []
        for part in getattr(band, "geoms", [band]):
            if part.geom_type != "Polygon" or part.is_empty:
                continue
            part = shapely.geometry.polygon.orient(part, sign=-1.0)       # Esri: outer rings clockwise, holes not
            rings += [[[round(x, 6), round(y, 6)] for x, y in r.coords] for r in [part.exterior, *part.interiors]]
        if not rings:
            return []
        js = json.dumps({"rings": rings, "spatialReference": {"wkid": 4326}}, separators=(",", ":"))
        if len(js) <= MAX_GEOM or bx.length < 800:
            return [js]
        a, b, c, d = bx.bounds
        mx, my = (a + c) / 2, (b + d) / 2
        return [j for q in (shapely.box(a, b, mx, my), shapely.box(mx, b, c, my), shapely.box(a, my, mx, d),
                            shapely.box(mx, my, c, d)) for j in esri(q)]
    out = []
    for x in np.arange(x0, x1, CELL_M):
        for y in np.arange(y0, y1, CELL_M):
            out += esri(shapely.box(x, y, x + CELL_M, y + CELL_M))
    return out


def query(url, params, what):
    """every feature an ArcGIS layer answers to params (POST), page by page"""
    feats, off, size = [], 0, 1000
    while True:
        try:
            r = netfetch.fetch("POST", f"{url}/query", tries=4, timeout=300, headers=UA,
                               data=dict(params, resultOffset=off, resultRecordCount=size),
                               ok=lambda r: r.ok and ("features" in r.json()))
        except netfetch.FetchError:
            if size <= 50:
                raise
            size //= 4
            continue
        js = r.json()
        fs = js["features"]
        feats += fs
        more = js.get("exceededTransferLimit") or js.get("properties", {}).get("exceededTransferLimit")
        if len(fs) < size and not more:
            return feats
        if not fs:
            return feats
        off += len(fs)


def by_ids(url, params):
    """A cell's parcels by their ids, for a server that refuses the cell as a whole: ArcGIS Online can't hand over a
    parcel whose stored outline is invalid within a spatial query ("24144: ... the instance is not valid"), but takes
    the same parcels by id. A chunk it still refuses is halved until the parcel it can't give is alone, and that one
    is left out."""
    js = netfetch.fetch("POST", f"{url}/query", tries=3, timeout=300, headers=UA,
                        data=dict(params, returnIdsOnly="true", returnGeometry="false", f="json"),
                        ok=lambda r: r.ok and "objectIds" in r.json()).json()
    ids, out, lost = sorted(js.get("objectIds") or []), [], []
    def get(chunk):
        try:
            r = netfetch.fetch("POST", f"{url}/query", tries=2, pause=5, timeout=300, headers=UA,
                               data=dict(objectIds=",".join(map(str, chunk)), outFields=params["outFields"],
                                         returnGeometry="true", outSR=4326, f="geojson"),
                               ok=lambda r: r.ok and "features" in r.json())
            out.extend(r.json()["features"])
        except netfetch.FetchError:
            if len(chunk) == 1:
                lost.append(chunk[0])
            else:
                get(chunk[:len(chunk) // 2]); get(chunk[len(chunk) // 2:])
    for i in range(0, len(ids), 200):
        get(ids[i:i + 200])
    return out, lost


def fields_of(*tpls):
    return sorted({m for t in tpls for m in re.findall(r"\{([^}]+)\}", t or "")})


def fetch_source(src, geoms):
    """the source's parcels near the water: GeoJSON features in the map's CRS"""
    join_poly = (src["join"] or "").split("=")[0] if src["table"] else ""
    flds = ",".join(fields_of(src["owner"], src["co_owner"]) if not src["table"] else [join_poly])
    def run():
        got, seen, unread, dropped = [], set(), 0, 0
        for n, g in enumerate(geoms):
            # in degrees: ArcGIS Online can't project a parcel whose stored outline is invalid ("24144: ... the
            # instance is not valid"), and then refuses the whole cell; it hands the same parcels over in degrees
            params = dict(where=src["where"] or "1=1", geometry=g, geometryType="esriGeometryPolygon", inSR=4326,
                          spatialRel="esriSpatialRelIntersects", outFields=flds, returnGeometry="true", outSR=4326,
                          f="geojson")
            fs = None
            try:
                fs = query(src["url"], params, src["key"])
            except netfetch.FetchError:
                try:                        # the cell refused as a whole: its parcels one chunk of ids at a time
                    fs, lost = by_ids(src["url"], params)
                    dropped += len(lost)
                except netfetch.FetchError:
                    fs = None
            if fs is None:
                unread += 1
                if unread > max(3, len(geoms) // 10):
                    raise netfetch.FetchError(f"{unread} of the first {n + 1} cells unread")
                continue
            for f in fs:
                k = f.get("id") if f.get("id") is not None else json.dumps(f.get("geometry"))[:200]
                if k not in seen:
                    seen.add(k); got.append(f)
            netfetch.wait(0.2, src["url"])  # gently: one server, hundreds of cells
        if dropped:
            netfetch.note(f"{src['name']}: {dropped} parcels the server can't hand over (invalid outlines) left out")
        if unread:
            netfetch.note(f"{src['name']}: {unread} of {len(geoms)} cells of water unread; parcels there have no names")
        return netfetch.Partial(got, f"{unread} cells unread") if unread else got
    name = f"parcels-{netfetch.key(src['url'], src['where'], flds, AREA, TOUCH_M, 4326)}"
    got = netfetch.fresh_copy(name, FRESH_DAYS)
    return got if got is not None else netfetch.last_good(name, run, f"{src['name']} ({src['publisher']})")


def join_table(src, feats):
    """the owner fields of a joined table, onto each feature by its key"""
    pf, rest = src["join"].split("=")
    tf, dash = rest.split("~")[0], rest.endswith("~dash")
    keys = sorted({str(f["properties"].get(pf) or "").strip() for f in feats} - {""})
    tflds = ",".join(sorted(set(fields_of(src["owner"], src["co_owner"])) | {tf}))
    def norm(v):
        v = str(v or "").strip()
        return "-".join(v.split()) if dash else v
    def run():
        rows = {}
        if dash:          # a spaced key can't be matched in SQL: the whole table, once
            for f in query(src["table"], dict(where="1=1", outFields=tflds, returnGeometry="false", f="json"), src["key"]):
                a = f.get("attributes", {})
                rows.setdefault(norm(a.get(tf)), a)
        else:
            for i in range(0, len(keys), 150):
                part = ",".join("'" + k.replace("'", "''") + "'" for k in keys[i:i + 150])
                for f in query(src["table"], dict(where=f"{tf} IN ({part})", outFields=tflds, returnGeometry="false",
                                                  f="json"), src["key"]):
                    a = f.get("attributes", {})
                    rows.setdefault(norm(a.get(tf)), a)
        return {"keys": "*" if dash else keys, "rows": rows}
    name = f"parcels-{netfetch.key(src['table'], tflds, AREA)}"
    got = netfetch.fresh_copy(name, FRESH_DAYS)        # a copy asked for these parcels' keys, or the whole table
    if got is None or not (got.get("keys") == "*" or set(keys) <= set(got.get("keys") or [])):
        got = netfetch.last_good(name, run, f"{src['name']}: owner table")
    rows = got["rows"]
    for f in feats:
        f["properties"].update(rows.get(norm(f["properties"].get(pf)), {}))
    return feats


def as_of(src):
    if src["as_of"]:
        return src["as_of"]
    def run():
        js = netfetch.fetch("GET", src["url"], tries=3, timeout=60, headers=UA, params={"f": "json"}).json()
        t = (js.get("editingInfo") or {}).get("lastEditDate") or (js.get("editingInfo") or {}).get("dataLastEditDate")
        return {"t": t}
    try:
        name = f"parcels-meta-{netfetch.key(src['url'])}"
        t = (netfetch.fresh_copy(name, FRESH_DAYS) or netfetch.last_good(name, run, f"{src['name']}: its date"))["t"]
        return dt.datetime.utcfromtimestamp(t / 1000).strftime("%Y-%m-%d") if t else ""
    except Exception:          # noqa: BLE001 (the date is a nicety)
        return ""


# ---- each source used for a county under this map ----
SRC = [s for s in read_csv("parcel_sources.csv") if here & set(c.strip() for c in s["counties"].split(";"))]
if not SRC or not water:
    print(f"{AREA}: no parcel source for its counties" if water else f"{AREA}: no water, so no parcels")
    sys.exit(0)
geoms = cells()
print(f"{AREA}: {len(geoms):,} cells of water; sources: {', '.join(s['key'] for s in SRC)}")
S_, SI = [], {}
def s_(x):
    if x not in SI:
        SI[x] = len(S_); S_.append(x)
    return SI[x]
sources, out, stats = [], [], []
for src in SRC:
    try:
        feats = fetch_source(src, geoms)
        if src["table"]:
            feats = join_table(src, feats)
    except Exception as e:          # noqa: BLE001 (a source that can't be read: its parcels are left out)
        netfetch.note(f"{src['name']} ({src['publisher']}) not read ({type(e).__name__}: {str(e)[:120]}); "
                      "its counties show private land without owner names")
        continue
    if not feats:
        stats.append((src["key"], 0, 0)); continue
    g = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(CRS)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = shapely.make_valid(g.geometry.values)
    g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    rp = shapely.point_on_surface(g.geometry.values)
    pi, gi = ptree.query(rp, predicate="within")
    on = np.full(len(g), -1); on[pi] = priv_y[gi]
    mine = set(c.strip() for c in src["counties"].split(";"))
    withheld = set(w.strip().lower() for w in src["withheld"].split(";") if w.strip())
    si = len(sources)
    sources.append([src["name"], src["publisher"], src["licence"], as_of(src), src["terms"]])
    keep, names = [], []
    for i, (props, y) in enumerate(zip(g.drop(columns="geometry").to_dict("records"), on)):
        if y < 0 or cty_names[y] not in mine:
            continue
        o, co = fill(src["owner"], props), fill(src["co_owner"], props)
        if not o:
            continue
        if o.lower() in withheld or WITHHELD.match(o):
            names.append("")               # withheld by law: the popup says so
        else:
            o = re.sub(r"\s*(&|\band)\s*$", "", unmail(o), flags=re.I)  # an owner field that runs on into the next
            co = re.sub(r"^\s*(&|and\b)\s*", "", unmail(co), flags=re.I)
            if not o:
                continue                       # the owner field held only a mailing address: no name to show
            names.append(pretty(o) + (" & " + pretty(co) if co and co.lower() not in o.lower() else ""))
        keep.append(i)
    simp = shapely.simplify(g.geometry.values[keep], SIMPLIFY_M)
    labs = [shapely.ops.polylabel(max(getattr(p, "geoms", [p]), key=lambda q: q.area), 2) if not p.is_empty
            else shapely.Point() for p in simp]
    G = gpd.GeoSeries(simp, crs=CRS).to_crs(4326).values
    P = gpd.GeoSeries(labs, crs=CRS).to_crs(4326).values
    kept = 0
    for gi_, lab, name, i in zip(G, P, names, keep):
        rings = []
        for part in getattr(gi_, "geoms", [gi_]):
            if part.is_empty or part.geom_type != "Polygon" or len(part.exterior.coords) < 4:
                continue
            rings.append([enc(part.exterior.coords[:-1])] + [enc(r.coords[:-1]) for r in part.interiors if len(r.coords) >= 4])
        if not rings or lab.is_empty:
            continue
        out.append([rings, round(lab.y * 1e5), round(lab.x * 1e5), s_(name), si, int(on[i])])
        kept += 1
    stats.append((src["key"], len(g), kept))

if not out:
    print(f"{AREA}: no parcels kept"); sys.exit(0)
data = {"built": dt.date.today().isoformat(), "touch_m": TOUCH_M, "s": S_, "src": sources, "f": out}
with open(OUT, "w") as f:
    f.write("window.PARCELS=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n")
named = sum(1 for p in out if S_[p[3]])
print(f"{AREA}: parcels_data.js {os.path.getsize(OUT) / 1e6:.2f} MB: {len(out):,} parcels ({named:,} named, "
      f"{len(out) - named:,} withheld), {len(S_):,} names | " + "; ".join(f"{k} {n:,} fetched, {m:,} kept" for k, n, m in stats))
