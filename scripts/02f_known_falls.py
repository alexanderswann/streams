"""Known waterfalls for one area, every source merged: data/raw/<area>/_shared/known_falls.gpkg. Run with AREA=<key>
after 02_download_vectors.py (it reads the ranges' NHD files) and before 05_score.py, which takes each range's share
(run_mid.sh runs it first).

Until 2026-11-19 the known waterfalls were OpenStreetMap nodes tagged as waterfalls and NHD waterfall points (and
CDFW's barrier surveys in LA), each range's own, taken by 05_score.py. Many well-known falls were missing: Bolton Potholes is
in OSM only as a park, Triple Buckets not at all, and USGS names some falls that nobody has put on OSM. Sources now:
  OSM       nodes, ways and areas tagged waterway=waterfall or natural=waterfall; named rapids; named swimming holes on
            streams (leisure=swimming_area or bathing_place, sport=swimming, or a beach or pool whose name says swimming
            hole or punch bowl); named parks, nature reserves, attractions and waters whose name says falls, cascade,
            cataract, pothole, flume or punch bowl. Features that aren't tagged as falls must sit on a stream (within
            60 m of an NHD stream line, not in a lake or reservoir) and be small (under 400 m across): the
            centre of a state park named for its falls is not the falls.
  NHD       USGS NHD waterfall points (FType 487)
  CDFW      (LA only) CDFW Passage Assessment Database natural barriers (falls, cascades, chutes), with their notes
  NPS       (Smokies only, source grsm_falls) Great Smoky Mountains National Park's waterfalls layer
  GNIS      USGS Geographic Names, class Falls or Rapids: the current file, and the 2021 archive for names since dropped
  Wikidata  items that are a waterfall, cascade, rapids, swimming hole or plunge pool
  curated   data/known_falls_curated*.csv: falls from guidebooks, state inventories (Vermont's 1985-88 survey of its
            waterfalls, cascades and gorges) and swimming-hole guides, each with its source page; each row's note says
            how its point was placed. Rows can also rename, replace or drop a source's point (see below).
One fall listed by several sources becomes one point: same name (ignoring words like falls, creek and the) within
500 m (exactly the same name: 2 km, since GNIS is sometimes that far off), an unnamed point within 100 m of a
named one, or any two within 25 m. A point never absorbs a second one from
the same source: two OSM nodes are two falls. The kept point is the best placed one (OSM node, curated point marked
precise, NHD, OSM way, other curated, GNIS, OSM area feature, Wikidata), the name the most deliberate one (curated,
OSM, GNIS, NHD, Wikidata), and the sources are all listed.
precise = the point sits on the fall itself (OSM falls and rapids nodes and small ways, NHD, curated points marked
precise). Only these may outrank 05_score.py's artifact tests (a mapped fall within 50 m of the step); the others, GNIS
placements especially (Bingham Falls' is 340 m off the falls), still name a drop within 200 m.
Downloads are cached in the area's _shared folder (OSM a week, Wikidata a month) and the old copy is used if a source
can't be reached; GNIS files are kept in data/raw/_national/gnis.
"""
import glob, io, json, os, re, time, zipfile, requests, shapely, numpy as np, pandas as pd, geopandas as gpd, pyogrio
from config import *
from geomatch import overpass, esri, UA
import netfetch

OUTF = f"{SHARED}/known_falls.gpkg"
# the curated lists: known_falls_curated.csv and any known_falls_curated_<name>.csv beside it (gawaterfalls.com's
# Georgia catalogue is its own file; a list to keep out of the maps for a while can be renamed to .csv.held)
CURATED = sorted(glob.glob(f"{ROOT}/data/known_falls_curated*.csv"))
GNIS_DIR = f"{NATIONAL}/gnis"
# states each area's boxes reach into (GNIS comes by state); the boxes are UTM rectangles and cross state lines.
# An area missing here gets no GNIS falls (a NOTE says so)
STATES = {"la": ("CA",), "jackson": ("WY", "ID"), "n_georgia": ("GA", "NC", "SC", "TN"), "central_vt": ("VT",),
          "ne_ct": ("CT", "MA", "RI"), "lexington_va": ("VA", "WV"), "se_pa": ("PA", "DE", "MD", "NJ"),
          "smokies": ("TN", "NC"),
          # the Adirondack maps' east edges cross Lake Champlain to the Vermont shore
          "adk_high_peaks": ("NY", "VT"), "adk_northwest": ("NY",), "adk_southwest": ("NY",), "adk_southeast": ("NY", "VT")}
SRC_LABEL = {"OSM": "OpenStreetMap", "NHD": "USGS NHD", "GNIS": "USGS GNIS", "Wikidata": "Wikidata",
             "CDFW": "CDFW barrier survey", "NPS": "Great Smoky Mountains NP"}

boxes = gpd.GeoSeries([shapely.box(*R["bbox"]) for R in REGIONS.values()], crs=CRS)
area_u = boxes.union_all()
keep_zone = area_u.buffer(300)          # a little past the boxes, so 05_score.py can match drops at an edge
W, S, E, N = gpd.GeoSeries([area_u.envelope.segmentize(1000)], crs=CRS).to_crs(4326).total_bounds


def cached(path, days, fetch, what):
    """fetch() -> JSON data, kept at path for `days` together with the lon/lat box it was fetched for: a copy made for
    other boxes (an area whose boxes changed) is fetched again. If the fetch fails, the old copy is used (or None)."""
    key = [round(v, 5) for v in (W, S, E, N)]
    old = None
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
        if not (isinstance(old, dict) and "bbox" in old):     # a copy from before the box was kept with it
            old = {"bbox": None, "data": old}
        if old["bbox"] == key and time.time() - os.path.getmtime(path) < days * 86400:
            return old["data"]
    try:
        data = fetch()
    except Exception as e:  # noqa: BLE001 (any network or service failure)
        if old is not None:
            day = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
            part = "" if old["bbox"] == key else " (fetched for other boxes: falls in the new parts are missing)"
            print(f"NOTE: {what} could not be refreshed ({str(e)[:120]}); using the copy from {day}{part}")
            return old["data"]
        print(f"NOTE: {what} could not be fetched ({str(e)[:120]}) and there is no earlier copy; going on without it")
        return None
    with open(path + ".tmp", "w") as f:
        json.dump({"bbox": key, "data": data}, f)
    os.replace(path + ".tmp", path)
    return data


GENERIC = {"the", "of", "at", "on", "falls", "fall", "waterfall", "waterfalls", "cascade", "cascades", "creek", "brook",
           "branch", "river", "run", "fork", "rapid", "rapids", "shoal", "shoals", "and", "a", "swimming", "hole", "spot",
           "area", "recreation", "scenic", "trail", "park", "natural", "state", "the", "s"}


def tokens(name):
    """A name's distinctive words: 'Falls of Lana' and 'Lana Falls' are both {lana}. A name made only of common words
    keeps them ('Fall Creek Falls' is {fall, creek}, 'Cascade Falls' {cascade}), or it would count as no name; a single
    common word ('Falls', 'Cascades') is a description, not a name."""
    if not isinstance(name, str) or not name.strip():
        return frozenset()
    t = re.sub(r"[’'`]", "", name.lower())
    t = re.sub(r"[^a-z0-9]+", " ", t).split()
    keep = frozenset(w for w in t if w not in GENERIC)
    if keep:
        return keep
    words = [w for w in t if w not in {"the", "of", "at", "on", "and", "a", "s"}]
    if len(words) <= 1:
        return frozenset()
    return frozenset(w for w in words if w not in {"falls", "waterfall", "waterfalls"}) or frozenset(words)


# words that make two falls different ones: "Little Moss Glen Falls" is not Moss Glen Falls, "Upper Soldier Creek Falls"
# not Soldier Creek Falls
DISTINCT = {"little", "big", "upper", "lower", "middle", "north", "south", "east", "west", "first", "second", "third",
            "fourth", "inner", "outer", "old", "new", "twin", "ii", "iii", "iv"}


def same_name(ti, tj):
    """One name's words are all in the other's, and what one has more says nothing like upper, little or a number."""
    if not ti or not tj or not (ti <= tj or tj <= ti):
        return False
    extra = ti ^ tj
    return not (extra & DISTINCT) and not any(w.isdigit() or re.fullmatch(r"#?\d+", w) for w in extra)


def kind_from_name(name, default):
    n = (name or "").lower()
    if re.search(r"swim|bathing", n):
        return "swimming hole"
    if re.search(r"pothole|punch ?bowl", n):
        return "potholes"
    if re.search(r"cascade", n):
        return "cascade"
    if re.search(r"\bfalls?\b|cataract", n):
        return "waterfall"
    if re.search(r"rapid|shoal|sluice|chute", n):
        return "rapids"
    return default


rows = []   # name, alt (list), kind, src, precise, rank (placement), nrank (naming), note, url, lon, lat, ref
def add(**r):
    rows.append(r)


# ---- NHD flowlines and waterbodies, for "is it on a stream" ----
fl = pd.concat([gpd.read_file(f"{raw_dir(r)}/nhd_flowlines.gpkg") for r in REGIONS], ignore_index=True)
fl = gpd.GeoDataFrame(fl, crs=CRS)
stream_lines = fl[fl.ftype.isin([460, 558])].geometry       # StreamRiver, ArtificialPath
stream_tree = shapely.STRtree(stream_lines.values)
lakes = []
for hu in sorted({h for R in REGIONS.values() for h in R["hu4"]}):
    g = f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg"
    if not os.path.exists(g):
        continue
    lyr = next((l for l in pyogrio.list_layers(g)[:, 0] if l.lower() == "nhdwaterbody"), None)
    if lyr:
        wb = gpd.read_file(g, layer=lyr, bbox=(W, S, E, N))
        wb.columns = [c.lower() if c != "geometry" else c for c in wb.columns]
        lakes.append(wb[wb.ftype.isin([390, 436])].to_crs(CRS).geometry)   # LakePond, Reservoir
lake_g = pd.concat(lakes, ignore_index=True).values if lakes else np.array([])
lake_tree = shapely.STRtree(lake_g) if len(lake_g) else None


def on_stream(pt):
    """Within 60 m of an NHD stream or river line, and not inside (or within 20 m of) a lake or reservoir."""
    near = stream_tree.query(pt, predicate="dwithin", distance=60)
    if not len(near):
        return False
    if lake_tree is not None and len(lake_tree.query(pt, predicate="dwithin", distance=20)):
        return False
    return True


# ---- OpenStreetMap ----
FW = "[Ff]alls?\\b|[Cc]ascades?|[Cc]ataract|[Pp]otholes?|[Ff]lume|[Pp]unch ?[Bb]owl|[Ss]wimming [Hh]ole"
def osm_query(bb):
    return f"""[out:json][timeout:600];
(nwr["waterway"="waterfall"]{bb}; nwr["natural"="waterfall"]{bb}; nwr["waterway"="rapids"]["name"]{bb};
 nwr["leisure"~"^(swimming_area|bathing_place)$"]["name"]{bb};
 nwr["sport"="swimming"]["name"]["leisure"!~"^(sports_centre|swimming_pool|fitness_centre|sports_hall|water_park|pitch|common)$"]{bb};
 nwr["name"~"{FW}"]["leisure"~"^(park|nature_reserve)$"]{bb};
 nwr["name"~"{FW}"]["tourism"="attraction"]{bb};
 nwr["name"~"{FW}|[Ss]wim"]["natural"~"^(water|beach)$"]{bb};);
out tags bb;"""


def osm_tiles(step=0.5):
    """The query in tiles of at most `step` degrees, merged (a way in two tiles comes once). On 2026-11-19 the Smokies'
    whole box (1.4 x 0.8 degrees) ran past 4 minutes on both public servers and hung two runs for 20+ minutes, while
    the same query in six tiles took 2-3 s each."""
    nx, ny = max(1, int(np.ceil((E - W) / step))), max(1, int(np.ceil((N - S) / step)))
    els = {}
    for i in range(nx):
        for j in range(ny):
            w_, e_ = W + (E - W) * i / nx, W + (E - W) * (i + 1) / nx
            s_, n_ = S + (N - S) * j / ny, S + (N - S) * (j + 1) / ny
            for el in overpass(osm_query(f"({s_:.5f},{w_:.5f},{n_:.5f},{e_:.5f})")):
                els[(el["type"], el["id"])] = el
    return list(els.values())


osm = cached(f"{SHARED}/osm_falls.json", 7, osm_tiles, "OpenStreetMap falls")
if osm is None:   # no Overpass and no earlier copy: the ranges' waterfall nodes from 02_download_vectors.py
    osm = []
    for r in REGIONS:
        o = gpd.read_file(f"{raw_dir(r)}/osm_waterfalls.gpkg").to_crs(4326)
        osm += [dict(type="node", id=0, lon=p.x, lat=p.y, tags={"waterway": "waterfall", **({"name": n} if isinstance(n, str) else {})})
                for n, p in zip(o.get("name", [None] * len(o)), o.geometry)]
NOT_NATURE = re.compile(r"(?i)\b(road|rd|street|lane|drive|avenue|trailhead|parking|campground|picnic|church|school|"
                        r"apartments?|village|plaza|shopping|hotel|inn|motel|restaurant|information|lodge|cabins?|farm|"
                        r"golf|club|estates?|condos?|subdivision|swim school|aquatic|pool slides|water slides|y?mca)\b")
n_osm = {"falls": 0, "rapids": 0, "swim": 0, "named": 0, "dropped": 0}
for el in osm:
    t = el.get("tags", {})
    if el["type"] == "node":
        lon, lat, span = el["lon"], el["lat"], 0.0
    else:
        b = el.get("bounds")
        if not b:
            continue
        lon, lat = (b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2
        span = float(np.hypot((b["maxlon"] - b["minlon"]) * 111320 * np.cos(np.radians(lat)), (b["maxlat"] - b["minlat"]) * 110540))
    name = t.get("name")
    ref = f"{el['type']}/{el['id']}"
    wp = re.match(r"^(\w+):(.+)$", t.get("wikipedia", ""))
    url = (f"https://{wp.group(1)}.wikipedia.org/wiki/{wp.group(2).replace(' ', '_')}" if wp else
           t.get("website") or (f"https://www.openstreetmap.org/{ref}" if el.get("id") else None))
    if t.get("waterway") == "waterfall" or t.get("natural") == "waterfall":
        precise = el["type"] == "node" or span < 100
        add(name=name, alt=[], kind=kind_from_name(name, "waterfall"), src="OSM", precise=precise,
            rank=0 if el["type"] == "node" else 3, nrank=1, note=None, url=url, lon=lon, lat=lat, ref=ref, onstream=True)
        n_osm["falls"] += 1
        continue
    if t.get("waterway") == "rapids":
        add(name=name, alt=[], kind=kind_from_name(name, "rapids"), src="OSM", precise=el["type"] == "node" or span < 100,
            rank=0 if el["type"] == "node" else 3, nrank=1, note=None, url=url, lon=lon, lat=lat, ref=ref, onstream=True)
        n_osm["rapids"] += 1
        continue
    # everything else: named, small, not a business or a road, and on a stream (tested after the projection below)
    if not name or NOT_NATURE.search(name) or span > 400 or t.get("amenity") or t.get("attraction") or t.get("shop"):
        n_osm["dropped"] += 1
        continue
    swim = t.get("leisure") in ("swimming_area", "bathing_place") or t.get("sport") == "swimming" or re.search(r"(?i)swim", name)
    add(name=name, alt=[], kind="swimming hole" if swim else kind_from_name(name, "waterfall"), src="OSM", precise=False,
        rank=6, nrank=1, note=None, url=url, lon=lon, lat=lat, ref=ref, onstream=False)
    n_osm["swim" if swim else "named"] += 1

# ---- NHD waterfall points ----
for r in REGIONS:
    p = gpd.read_file(f"{raw_dir(r)}/nhd_points.gpkg")
    p = p[p.ftype == 487].to_crs(4326)
    for n, g in zip(p.gnis_name, p.geometry):
        add(name=n if isinstance(n, str) else None, alt=[], kind=kind_from_name(n if isinstance(n, str) else "", "waterfall"),
            src="NHD", precise=True, rank=2, nrank=3, note=None, url=None, lon=g.x, lat=g.y, ref=None, onstream=True)

# ---- CDFW Passage Assessment Database (California only): natural barriers noted in the field (falls, cascades, bedrock
# chutes), many with a height and plunge-pool depth in the notes. Records whose notes say the barrier is gone are skipped.
# (Moved here from 05_score.py on 2026-11-19, so a survey point and a named fall on the same spot become one point.)
if has("cdfw_pad"):
    def pad_fetch():
        g = esri("https://services2.arcgis.com/Uq9r85Potqm3MfRV/arcgis/rest/services/biosds69_fmu/FeatureServer/0",
                 (W, S, E, N), "PAD_ID,StreamName,SiteName,BarStatus,Notes,SurveyDate", where="SiteType='Non-structural'")
        return json.loads(g.to_json()) if len(g) else {"type": "FeatureCollection", "features": []}
    pj = cached(f"{SHARED}/cdfw_pad.json", 30, pad_fetch, "CDFW barrier surveys")
    pad = gpd.GeoDataFrame.from_features(pj["features"], crs=4326) if pj and pj["features"] else gpd.GeoDataFrame()
    if len(pad):
        pad = pad[~pad.Notes.str.contains(r"no longer present|no evidence of|not a barrier|no barrier", case=False, na=False)]
        site = pad.SiteName.fillna("natural barrier").str.strip()
        creek = pad.StreamName.fillna("").str.strip().replace(r"(?i)^unnamed.*", "", regex=True)
        yr = [pd.Timestamp(float(v), unit="ms").year if str(v).replace(".", "").isdigit() and float(v) > 1e11
              else int(m.group()) if (m := re.search(r"(?:19|20)\d\d", str(v or ""))) else "" for v in pad.SurveyDate]
        for pid, s_, c_, n_, y_, b_, g_ in zip(pad.PAD_ID, site, creek, pad.Notes, yr, pad.BarStatus, pad.geometry):
            nm = s_ if not c_ or c_.lower() in s_.lower() else f"{s_}, {c_}"
            note = " ".join(filter(None, [(n_ or "").strip()[:240], f"(CDFW fish passage survey{', ' + str(y_) if str(y_)[:2] in ('19', '20') else ''}; "
                                          f"barrier to fish: {(b_ or 'unassessed').lower()})"]))
            add(name=nm, alt=[], kind=kind_from_name(nm, "waterfall"), src="CDFW", precise=True, rank=2, nrank=3, note=note,
                url=None, lon=g_.x, lat=g_.y, ref=f"cdfw/{pid}", onstream=True)

if has("grsm_falls"):     # Great Smoky Mountains NP's own waterfalls layer (80 named falls and cascades in the park). Its fish
    def grsm_fetch():     # barriers layer (359 more) is marked "Internal NPS Only" and is not used
        g = esri("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_WATERFALLS/FeatureServer/0",
                 (W, S, E, N), "GlobalID,STATION_NAME,BARRIERTYPE,STREAMNAME,TRAIL,XYACCURACY", where="DATAACCESS = 'Unrestricted'")
        return json.loads(g.to_json()) if len(g) else {"type": "FeatureCollection", "features": []}
    gj = cached(f"{SHARED}/grsm_falls.json", 30, grsm_fetch, "Great Smoky Mountains NP waterfalls")
    for f_ in (gj or {}).get("features", []):
        p_, xy = f_.get("properties") or {}, (f_.get("geometry") or {}).get("coordinates")
        if not xy:
            continue
        nm = str(p_.get("STATION_NAME") or "").strip() or f"{p_.get('BARRIERTYPE') or 'Falls'} on {p_.get('STREAMNAME') or 'a creek'}"
        # placed to under 14 m by the park ("Unknown" for many of the older points)
        exact = bool(re.match(r">=\s*\d+(?:\.\d+)?\s*(?:cm|m)\s+and\s+<\s*(?:1|5|14)\s*m", str(p_.get("XYACCURACY") or "")))
        add(name=nm, alt=[], kind=kind_from_name(nm, "waterfall"), src="NPS", precise=exact, rank=2 if exact else 4, nrank=2,
            note="Great Smoky Mountains NP waterfall" + (f", by the {p_['TRAIL']}" if p_.get("TRAIL") else ""), url=None,
            lon=xy[0], lat=xy[1], ref=f"grsm/{p_.get('GlobalID') or nm}", onstream=True)

# ---- GNIS: named Falls and Rapids ----
os.makedirs(GNIS_DIR, exist_ok=True)
def gnis_file(name, url):
    p = f"{GNIS_DIR}/{name}"
    if not os.path.exists(p):
        r = netfetch.fetch("GET", url, headers=UA, timeout=300)
        with open(p + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(p + ".tmp", p)
    return p
seen_gnis = set()
if AREA not in STATES:
    print(f"NOTE: no states listed for {AREA} in 02f_known_falls.py's STATES: no USGS GNIS falls")
for st in STATES.get(AREA, ()):
    frames = []
    try:
        z = zipfile.ZipFile(gnis_file(f"DomesticNames_{st}_Text.zip", "https://prd-tnm.s3.amazonaws.com/StagedProducts/"
                                      f"GeographicNames/DomesticNames/DomesticNames_{st}_Text.zip"))
        cur = pd.read_csv(io.StringIO(z.read(next(n for n in z.namelist() if n.endswith(".txt"))).decode("utf-8-sig")),
                          sep="|", dtype=str)
        frames.append(cur.rename(columns={"feature_id": "id", "feature_name": "name", "feature_class": "cls",
                                          "prim_lat_dec": "lat", "prim_long_dec": "lon"}))
        old = pd.read_csv(gnis_file(f"{st}_Features_20210825.txt", "https://prd-tnm.s3.amazonaws.com/StagedProducts/"
                                    f"GeographicNames/Archive/MainDomestic/{st}_Features_20210825.txt"),
                          sep="|", dtype=str, encoding="utf-8-sig")
        frames.append(old.rename(columns={"FEATURE_ID": "id", "FEATURE_NAME": "name", "FEATURE_CLASS": "cls",
                                          "PRIM_LAT_DEC": "lat", "PRIM_LONG_DEC": "lon"}))
    except (requests.RequestException, RuntimeError, OSError, zipfile.BadZipFile) as e:
        print(f"NOTE: GNIS for {st} not available ({str(e)[:100]})")
    for g in frames:
        g = g[g.cls.isin(["Falls", "Rapids"])]
        for i, n, c, la, lo in zip(g.id, g.name, g.cls, g.lat.astype(float), g.lon.astype(float)):
            if i in seen_gnis or not (S - 0.05 < la < N + 0.05 and W - 0.05 < lo < E + 0.05) or la == 0:
                continue
            seen_gnis.add(i)
            add(name=n, alt=[], kind=kind_from_name(n, "rapids" if c == "Rapids" else "waterfall"), src="GNIS", precise=False,
                rank=5, nrank=2, note=None, url=f"https://edits.nationalmap.gov/apps/gaz-domestic/public/summary/{i}",
                lon=lo, lat=la, ref=f"gnis/{i}", onstream=True)

# ---- Wikidata ----
def wikidata():
    # classes (checked 2026-11-19): Q34038 waterfall (with its subclasses: cascade, plunge, ...), Q695793 rapids,
    # Q7658373 swimming hole
    sparql = f"""SELECT ?item ?itemLabel ?coord ?article ?cls WHERE {{
      SERVICE wikibase:box {{ ?item wdt:P625 ?coord .
        bd:serviceParam wikibase:cornerSouthWest "Point({W} {S})"^^geo:wktLiteral .
        bd:serviceParam wikibase:cornerNorthEast "Point({E} {N})"^^geo:wktLiteral . }}
      ?item wdt:P31/wdt:P279* ?cls . VALUES ?cls {{ wd:Q34038 wd:Q695793 wd:Q7658373 }}
      OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""
    r = netfetch.fetch("GET", "https://query.wikidata.org/sparql", params={"query": sparql, "format": "json"},
                       headers={**UA, "Accept": "application/sparql-results+json"}, timeout=180)
    return r.json()["results"]["bindings"]
seen_q = set()
for x in cached(f"{SHARED}/wikidata_falls.json", 30, wikidata, "Wikidata falls") or []:
    lon, lat = map(float, x["coord"]["value"].replace("Point(", "").replace(")", "").split())
    qid = x["item"]["value"].rsplit("/", 1)[1]
    n = x["itemLabel"]["value"]
    if n == qid or qid in seen_q:      # no English label; or listed again (an item with two coordinates or classes)
        continue
    seen_q.add(qid)
    cls = x.get("cls", {}).get("value", "").rsplit("/", 1)[-1]
    k = {"Q695793": "rapids", "Q7658373": "swimming hole"}.get(cls, "waterfall")
    add(name=n, alt=[], kind=kind_from_name(n, k), src="Wikidata", precise=False, rank=7, nrank=4, note=None,
        url=x.get("article", {}).get("value") or f"https://www.wikidata.org/wiki/{qid}", lon=lon, lat=lat, ref=qid,
        onstream=True)

# ---- curated: guidebooks, state inventories, swimming-hole guides ----
# A row's `replaces` names source points it stands in for (node/<id>, way/<id>, gnis/<id>, Q<id>; ;-separated): those
# are dropped. With lat/lon left blank the row takes the first one's position and placement instead: that names or
# corrects a point a source has in the right place. A row of kind "drop" only removes the points it names.
by_ref = {r["ref"]: i for i, r in enumerate(rows) if r.get("ref")}
gone = set()
if CURATED:
    c = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in CURATED], ignore_index=True)
    c = c[c.area == AREA]
    for r in c.itertuples():
        refs = [x.strip() for x in r.replaces.split(";") if x.strip()]
        hit = [by_ref[x] for x in refs if x in by_ref]
        missing = [x for x in refs if x not in by_ref]
        if missing:
            print(f"NOTE: curated '{r.name}' replaces {missing}, which no source has now")
        gone.update(hit)
        if r.kind == "drop":
            continue
        precise = r.precise.strip().lower() == "yes"
        if r.lat.strip() and r.lon.strip():
            lon, lat, rank = float(r.lon), float(r.lat), 1 if precise else 4
        elif hit:
            base = rows[hit[0]]
            lon, lat, precise, rank = base["lon"], base["lat"], base["precise"], min(base["rank"], 4)
        else:
            print(f"NOTE: curated '{r.name}' has no position and replaces nothing that exists; left out")
            continue
        add(name=r.name, alt=[a.strip() for a in r.alt_names.split(";") if a.strip()], kind=r.kind or "waterfall",
            src=r.source, precise=precise, rank=rank, nrank=0, note=r.note or None, url=r.url or None,
            lon=lon, lat=lat, ref="curated", onstream=True)
rows = [r for i, r in enumerate(rows) if i not in gone]

d = pd.DataFrame(rows)
d = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(CRS)
d = d[d.within(keep_zone)].reset_index(drop=True)
# features that aren't tagged as falls must be on a stream
offstream = ~d.onstream & ~np.array([on_stream(p) for p in d.geometry])
print(f"OSM: {n_osm['falls']} falls, {n_osm['rapids']} named rapids, {n_osm['swim']} named swimming spots, "
      f"{n_osm['named']} other named features, {n_osm['dropped']} named features left out (a business, a road, too big); "
      f"{int(offstream.sum())} more left out as not on a stream: {sorted(d[offstream].name.dropna())[:12]}")
d = d[~offstream].reset_index(drop=True)
# within one source, a fall listed twice is kept once: the same name within 150 m (a node and a way of one fall in OSM;
# NHD marks Broken Falls with seven points along it), or two unnamed points within 15 m. Curated rows stay as written.
d["tok"] = [tokens(n) | frozenset().union(*[tokens(a) for a in al]) if al else tokens(n) for n, al in zip(d.name, d.alt)]
xy = np.c_[d.geometry.x, d.geometry.y]
drop = set()
for src_, idx in d.groupby("src").groups.items():
    if src_ not in SRC_LABEL:
        continue
    idx = list(idx)
    for a_, i in enumerate(idx):
        for j in idx[a_ + 1:]:
            if i in drop:
                break
            if j in drop:
                continue
            dist = np.hypot(*(xy[i] - xy[j]))
            if (d.tok[i] and d.tok[i] == d.tok[j] and dist < 150) or (not d.tok[i] and not d.tok[j] and dist < 15):
                ki, kj = (d["rank"][i], not d.precise[i]), (d["rank"][j], not d.precise[j])
                drop.add(j if kj >= ki else i)      # keep the better placed of the two
d = d.drop(index=list(drop)).reset_index(drop=True)
xy = np.c_[d.geometry.x, d.geometry.y]

# ---- merge one fall's points across sources ----
# candidate pairs, best first: same name (one name's words within the other's, up to 500 m; exactly the same name, up
# to 2 km: GNIS puts Raven Cliff Falls 1.4 km and Amicalola Falls 570 m from the falls), then unnamed next to named
# (100 m), then anything (25 m)
tree = shapely.STRtree(d.geometry.values)
pairs = []
for i, j in zip(*tree.query(d.geometry.values, predicate="dwithin", distance=2000)):
    if i >= j or d.src[i] == d.src[j]:
        continue
    dist = float(np.hypot(*(xy[i] - xy[j])))
    ti, tj = d.tok[i], d.tok[j]
    if same_name(ti, tj):
        if dist <= 500 or ti == tj:
            pairs.append((0, dist, i, j))
    elif (not ti or not tj) and dist <= 100:
        pairs.append((1, dist, i, j))
    elif dist <= 25:
        pairs.append((2, dist, i, j))
parent = list(range(len(d)))
srcs = [{s} for s in d.src]
names = [{t} if t else set() for t in d.tok]
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
for pri, _, i, j in sorted(pairs):
    a, b = find(i), find(j)
    if a == b or srcs[a] & srcs[b]:             # a point never absorbs a second one from the same source (or list)
        continue
    # nor a differently named one, except on the same spot (25 m): an unnamed point between Lewis Falls and Upper Soldier
    # Creek Falls must not make them one
    if pri < 2 and any(not same_name(x, y) for x in names[a] for y in names[b]):
        continue
    parent[b] = a
    srcs[a] |= srcs[b]
    names[a] |= names[b]
d["cl"] = [find(i) for i in range(len(d))]

out = []
for _, g in d.groupby("cl"):
    pos = g.sort_values(["rank", "precise"], ascending=[True, False]).iloc[0]
    named = g[g.name.notna() & (g.name.astype(str).str.strip() != "")].sort_values("nrank")
    name = named.name.iloc[0] if len(named) else None
    kinds = g.sort_values("nrank").kind
    kind = next((k for k in kinds if k), "waterfall")
    labels = []
    for s in g.sort_values("nrank").src:
        for lab in SRC_LABEL.get(s, s).split(" · "):
            if lab not in labels:
                labels.append(lab)
    others = sorted({n for n in named.name if tokens(n) and tokens(n) != tokens(name)} |
                    {a for al in g.alt for a in al if tokens(a) and tokens(a) != tokens(name)})
    notes = [n for n in g.sort_values("nrank").note if isinstance(n, str) and n]
    if others:
        notes.append("Also called " + ", ".join(others) + ".")
    urls = [u for u in g.sort_values("nrank").url if isinstance(u, str) and u]
    out.append(dict(name=name, src=" · ".join(labels), kind=kind, precise=bool(pos.precise),
                    note=" ".join(notes) or None, url=urls[0] if urls else None, n_src=len(labels), geometry=pos.geometry))
kf = gpd.GeoDataFrame(out, crs=CRS)
kf.to_crs(4326).to_file(OUTF + ".tmp.gpkg", driver="GPKG")
os.replace(OUTF + ".tmp.gpkg", OUTF)
# every source point with the fall it went into (`cl`), for checking the merges
d.assign(alt=["; ".join(a) for a in d.alt], tok=[" ".join(sorted(t)) for t in d.tok]).drop(columns=["lon", "lat"]).to_crs(4326) \
    .to_file(f"{SHARED}/known_falls_points.gpkg", driver="GPKG")

print(f"{AREA_LABEL}: {len(d)} points from {d.src.nunique()} sources -> {len(kf)} known falls "
      f"({int(kf.precise.sum())} precisely placed, {int(kf.name.notna().sum())} named)")
print("points by source:", d.src.value_counts().to_dict())
print("falls by kind:", kf.kind.value_counts().to_dict())
only = kf[~kf.src.str.contains("OpenStreetMap|USGS NHD")]
print(f"{len(only)} known falls that OSM and NHD don't have:", sorted(only.name.dropna())[:60])
