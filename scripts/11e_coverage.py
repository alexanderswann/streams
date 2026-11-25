"""Cell coverage: where each mobile carrier reports 4G LTE or 5G signal outdoors, for the maps' "Cell coverage" layer
(the user, 2026-11-25, a feature of onWater's: know where there will be no signal, so the offline map is saved before
heading out). 06_map.py adds the layer to both maps when this step has run; map_coverage.js draws it from
coverage_data.js, which a page loads the first time the layer is turned on, one carrier at a time or any carrier.

Source: the FCC's National Broadband Map (Broadband Data Collection), mobile broadband availability. Each facilities-
based carrier files its coverage twice a year, modelled under the FCC's rules: 4G LTE at 5/1 Mbps and 5G-NR at 7/1 Mbps,
each at a 90 % probability of that speed at the cell's edge with the cell 50 % loaded, for a phone outdoors and standing
still (coverage in a moving car lies inside it). The FCC publishes it by carrier, state and technology as its own H3
hexagons (resolution 9: cells of 0.105 km2, about 1,100 ft across), a cell counted as covered where its centre lies in
the carrier's modelled coverage. It is a model, not a measurement: terrain, trees, the phone and the network's load make
the signal on the ground better or worse, and the FCC's own staff found carriers' earlier maps overstated. Shaded here:
4G LTE or 5G-NR at 7/1 Mbps, outdoors (5G at 35/3 Mbps lies inside 5G at 7/1 and isn't read; 3G isn't shown). Networks
most phones can't use (NOT_FOR_PHONES: Southern Linc) are left out, and the key names them where they cover the map.

Read through the FCC's Public Data API (the website turns programs away with "Access Denied"): its list of as-of dates,
its list of the carriers' hexagon files, and each file this map needs (4G LTE and 5G-NR 7/1 of every carrier in the
states the map reaches), as the user, with their username and API token (netfetch.fcc_auth; at most 10 calls a minute).
A file serves every map at once: its hexagons within all of config.py's areas (MARGIN_DEG around their boxes) are
dissolved into one outline and kept in data/raw/_national/fcc_bdc/<the file's name>.json.gz with the outline they cover;
the zip and its GeoPackage are deleted after. The FCC's revision date is in a file's name, so a revised file is read
again and its old copy dropped. A map whose boxes the copy doesn't cover (a new area, a moved box) reads the file again.
Offline (NET_FAIL), the lists' last good copies (netfetch.last_good) and these copies are all a run needs. A zip
downloaded by hand from the FCC's Data Download page, put in data/raw/_national/fcc_bdc/zips/ under its own name, is
read instead of downloading it.

Writes output/<area>/coverage_data.js: window.CELL = {each carrier's coverage within the map (its boxes; where an area
stops at a state line, there) as encoded polylines (Google's, 1e-4 degrees), simplified by SIMPLIFY_M; the union of them
all for "any carrier"; each one's share of the map; the FCC's as-of date and the files' publication date}. A run removes
the old file first, so one that fails leaves the map without the layer, never with an old one (build_stamp.py: a step
the drivers go on without). A map needs every one of its files: a carrier drawn without one of its states, or "any
carrier" without one carrier, would show coverage missing as no signal, so a file that can't be had stops the step.
"""
import os, re, json, gzip, time, base64, shutil, zipfile, datetime as dt
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyogrio, requests
from shapely.geometry import box
import config
from config import AREA, AREAS, REGIONS, EPSG, MAP_OUT, NATIONAL, A
import areaclip, netfetch

API = os.environ.get("FCC_BDC_API", "https://bdc.fcc.gov/api/public/map").rstrip("/")
DIR = f"{NATIONAL}/fcc_bdc"
ZIPS = f"{DIR}/zips"                    # zips downloaded by hand from the FCC's Data Download page (optional)
STATES_ZIP = areaclip.ZIP               # US Census TIGER/Line 2024 state outlines (public domain)
OUT = f"{MAP_OUT}/coverage_data.js"
PACE_S = 6.5            # s between calls: the FCC's limit is 10 calls a minute
MARGIN_DEG = 0.02       # about 2 km kept around every area's boxes in a file's copy
GRID_DEG = 1e-7         # the hexagons' corners snapped to 1 cm, so neighbours share their edges exactly
SIMPLIFY_M = 60         # outlines simplified by this much: a third of a hexagon's edge (174 m), about 200 ft
PREC = 1e4              # 1e-4 degrees in the encoded outlines (8-11 m), well inside SIMPLIFY_M
MIN_KM2 = 1.0           # a carrier with less than this in the map isn't listed (0.4 sq mi, about 10 hexagons)
# Networks the FCC lists that most phones can't use: left out of the picker and of "any carrier", and named in the key
# where they cover the map (the user, 2026-11-25, of Southern Linc: "Drop it"). The FCC's data can't tell them apart:
# its mobile files and provider list have no consumer or business field (the business/residential code is fixed
# broadband's only), and every network fills in "brandname", the name "advertised or offered to consumers". So they are
# named here, by the FCC's provider ID, with the reason the key gives.
NOT_FOR_PHONES = {"131227": "a network for utilities and businesses (Southern Company's)"}
WHAT = "cell coverage"  # netfetch's name for these downloads ("as of" when a list came from its last good copy)
# Run controls for a long first download (a zip is up to ~400 MB, its GeoPackage ~1 GB): no new file is begun with less
# than FCC_MIN_FREE_GB free on the disk, or after FCC_STOP_AT (HH:MM, today); the copies made so far are kept, and the
# next run goes on from there
MIN_FREE_GB = float(os.environ.get("FCC_MIN_FREE_GB") or 5)
STOP_AT = os.environ.get("FCC_STOP_AT", "")
TECHS = {"400": "4G LTE", "500": "5G-NR"}
if os.path.exists(OUT):
    os.remove(OUT)      # a run that fails leaves the map no coverage layer, never an old one


# ---- where: the map's outline, every area's boxes, the states ----
def boxes_ll(key):
    """An area's boxes as one lon/lat outline (their edges cut every km), for any area in config.py; None for an area
    not worked out yet (00_area.py)."""
    e, w = AREAS[key], config._worked_out(key)
    crs, rs = e.get("crs") or w.get("crs"), e.get("ranges") or w.get("ranges")
    if not crs or not rs:
        return None
    g = gpd.GeoSeries([box(*r["bbox"]).segmentize(1000) for r in rs.values()], crs=crs).to_crs(4326)
    return shapely.union_all(g.values)


def map_outline():
    """This map in its own CRS: its boxes, cut at its state line where it stops at one (areaclip.py)."""
    o = shapely.union_all([box(*r["bbox"]) for r in REGIONS.values()])
    clip = areaclip.outline()
    return shapely.make_valid(o.intersection(clip)) if clip is not None else o


def state_outlines():
    if not os.path.exists(STATES_ZIP):
        os.makedirs(NATIONAL, exist_ok=True)
        r = netfetch.fetch("GET", areaclip.URL, timeout=600, headers=netfetch.UA)
        with open(STATES_ZIP + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(STATES_ZIP + ".tmp", STATES_ZIP)
    return gpd.read_file(f"zip://{STATES_ZIP}", columns=["STUSPS", "STATEFP"]).to_crs(4326)


# ---- the FCC's Public Data API ----
_last = [0.0]


def call(path, **kw):
    """One request to the API (netfetch.request: its time limits and breaker), at most one every PACE_S s."""
    url = f"{API}/{path}"
    auth = netfetch.fcc_auth(url)
    if not auth:
        raise RuntimeError("no FCC username and API token (~/.config/fcc/bdc_api; README, Cell coverage)")
    if not os.environ.get("NET_FAIL"):
        time.sleep(max(0.0, _last[0] + PACE_S - time.time()))
    try:
        return netfetch.request("GET", url, headers={**netfetch.UA, **auth}, **kw)
    finally:
        _last[0] = time.time()


def api_json(path, what, params=None, tries=3):
    """The "data" of an API answer, with a few tries; a server over its limit (HTTP 429) is waited out."""
    last = None
    for n in range(tries + 2):
        try:
            r = call(path, params=params, timeout=(15, 120))
            if r.status_code == 429:
                s = r.headers.get("Retry-After", "")
                netfetch.rate_wait(min(int(s) if s.isdigit() else 60, 600) + 5, r.url)
                continue
            j = r.json() if r.ok else {}
            if isinstance(j.get("data"), list):
                return j["data"]
            last = f"HTTP {r.status_code}: {str(j.get('message') or r.text[:120])!r}"
            if 400 <= r.status_code < 500:              # refused (401: the token): not worth another try
                break
        except (requests.RequestException, ValueError) as e:
            last = f"{type(e).__name__}: {str(e)[:160]}"
        if n + 1 >= tries:
            break
        netfetch.wait(15 * (n + 1), f"{API}/{path}")
    raise netfetch.FetchError(f"{what}: no usable answer from the FCC's API ({last})")


def latest_asof():
    dates = netfetch.last_good("fcc-bdc-asof-dates", lambda: sorted(
        d["as_of_date"] for d in api_json("listAsOfDates", "the FCC's as-of dates")
        if d.get("data_type") == "availability" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d.get("as_of_date")))), WHAT)
    if not dates:
        raise RuntimeError("the FCC lists no availability data")
    return dates[-1]


FIELDS = ("file_id", "technology_code", "technology_code_desc", "speed_tier", "state_fips", "provider_id",
          "provider_name", "file_name", "record_count")


def hexagon_files(asof):
    """The carriers' hexagon files of an as-of date (every state), as the FCC lists them."""
    return netfetch.last_good(f"fcc-bdc-hexagon-files-{asof}", lambda: [
        {k: d.get(k) for k in FIELDS} for d in api_json(
            f"downloads/listAvailabilityData/{asof}", "the FCC's list of hexagon files",
            params={"category": "Provider", "subcategory": "Hexagon Coverage",
                    "technology_type": "Mobile Broadband"})], WHAT)


def wanted(f):
    """4G LTE, and 5G-NR at 7/1 Mbps (35/3 lies inside it)."""
    code = str(f.get("technology_code") or "")
    tier = f"{f.get('speed_tier') or ''} {f.get('technology_code_desc') or ''}"
    return code == "400" or (code == "500" and "7/1" in tier)


class Stop(Exception):
    """A run control (MIN_FREE_GB, STOP_AT) says no new file now."""


def download(f, dest):
    """A file's zip (its GeoPackage), from the API, into dest; a zip downloaded by hand is used as it is."""
    hand = f"{ZIPS}/{f['file_name']}.zip"
    if os.path.exists(hand) and zipfile.is_zipfile(hand):
        return hand
    free = shutil.disk_usage(DIR).free / 1e9
    if free < MIN_FREE_GB:
        raise Stop(f"{free:.1f} GB free on the disk, under FCC_MIN_FREE_GB={MIN_FREE_GB:g}")
    if STOP_AT and dt.datetime.now().strftime("%H:%M") >= STOP_AT:
        raise Stop(f"past FCC_STOP_AT={STOP_AT}")
    path, tmp, last = f"downloads/downloadFile/availability/{f['file_id']}/2", f"{dest}.part", None
    for n in range(4):
        try:
            r = call(path, stream=True, timeout=(15, 180))
            if r.status_code == 429:
                s = r.headers.get("Retry-After", "")
                netfetch.rate_wait(min(int(s) if s.isdigit() else 60, 600) + 5, r.url)
                continue
            if r.ok:
                with open(tmp, "wb") as out:
                    for chunk in r.iter_content(1 << 20):
                        out.write(chunk)
                if zipfile.is_zipfile(tmp):
                    os.replace(tmp, dest)
                    return dest
                last = f"not a zip ({os.path.getsize(tmp):,} bytes)"
            else:
                last = f"HTTP {r.status_code}: {r.text[:120]!r}"
                if 400 <= r.status_code < 500:          # refused (a wrong id, no right to it): not worth another try
                    break
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {str(e)[:160]}"
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        if n < 3:
            netfetch.wait(30 * (n + 1), f"{API}/{path}")
    raise netfetch.FetchError(f"{f['file_name']}: not downloaded ({last})")


# ---- a file's copy: its hexagons within every area, dissolved ----
def b64(g):
    return base64.b64encode(shapely.to_wkb(g)).decode()


def unb64(s):
    return shapely.from_wkb(base64.b64decode(s))


def copy_path(name):
    return f"{DIR}/{name}.json.gz"


def read_copy(name):
    try:
        with gzip.open(copy_path(name), "rt") as f:
            c = json.load(f)
        c["covers"], c["geom"] = unb64(c["covers"]), unb64(c["geom"])
        return c
    except (OSError, ValueError, KeyError, shapely.errors.GEOSException):
        return None


def dissolve(geoms):
    """The union of hexagons that tile the plane: their corners snapped together, then merged as a coverage (fast);
    an ordinary union where that fails."""
    g = shapely.set_precision(np.asarray(geoms), GRID_DEG)
    try:
        u = shapely.coverage_union_all(g)
        if u.is_valid:
            return u
    except shapely.errors.GEOSException:
        pass
    return shapely.union_all(g, grid_size=GRID_DEG)


def make_copy(f, state):
    """Download a file, keep its hexagons within every area of config.py that reaches its state (MARGIN_DEG around their
    boxes) as one outline, and delete the download."""
    outs = [o for o in (boxes_ll(k) for k in AREAS) if o is not None and o.intersects(state)]
    covers = shapely.union_all([o.buffer(MARGIN_DEG, join_style="mitre") for o in outs])
    os.makedirs(DIR, exist_ok=True)
    work = f"{DIR}/tmp-{os.getpid()}-{f['file_id']}"
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    try:
        zpath = download(f, f"{work}/{f['file_name']}.zip")
        with zipfile.ZipFile(zpath) as z:
            members = [m for m in z.namelist() if m.lower().endswith(".gpkg")]
            if not members:
                raise netfetch.FetchError(f"{f['file_name']}: no GeoPackage in its zip ({z.namelist()[:5]})")
            gpkg = z.extract(members[0], work)
        layer = pyogrio.list_layers(gpkg)[0][0]
        info = pyogrio.read_info(gpkg, layer=layer)
        cols = [c for c in info["fields"] if c in ("h3_res9_id", "brandname")]
        crs = info.get("crs") or "EPSG:4326"       # the FCC's files are in WGS84 lon/lat; any other is read as such
        sel = gpd.GeoSeries(list(shapely.get_parts(covers)), crs=4326).to_crs(crs)
        parts = [pyogrio.read_dataframe(gpkg, layer=layer, columns=cols, bbox=tuple(p.bounds)) for p in sel]
        hexes = pd.concat(parts, ignore_index=True) if parts else gpd.GeoDataFrame(geometry=[], crs=crs)
        if len(hexes) and hexes.crs is not None and hexes.crs.to_epsg() != 4326:
            hexes = hexes.to_crs(4326)
        if "h3_res9_id" in hexes:
            hexes = hexes.drop_duplicates("h3_res9_id")
        geoms = np.asarray(hexes.geometry.values)
        geoms = geoms[~shapely.is_empty(geoms) & ~shapely.is_missing(geoms)] if len(geoms) else geoms
        geom = dissolve(geoms).intersection(covers) if len(geoms) else shapely.Polygon()
        brands = hexes["brandname"].dropna().astype(str).str.strip() if "brandname" in hexes else pd.Series(dtype=str)
        brands = brands[brands != ""]
        c = dict(file=f["file_name"], fetched=dt.datetime.now().isoformat(timespec="seconds"),
                 provider_id=str(f["provider_id"]), provider_name=f.get("provider_name"),
                 brand=brands.value_counts().index[0] if len(brands) else None, tech=str(f["technology_code"]),
                 state=str(f["state_fips"]), hexes=int(len(hexes)), covers=b64(covers), geom=b64(geom))
        tmp = f"{copy_path(f['file_name'])}.{os.getpid()}.tmp"
        with gzip.open(tmp, "wt", compresslevel=6) as out:
            json.dump(c, out)
        os.replace(tmp, copy_path(f["file_name"]))
        # the same carrier, state and technology's older revisions
        stem = f["file_name"].split("_mobile_broadband_h3_")[0] + "_mobile_broadband_h3_"
        for old in os.listdir(DIR):
            if old.startswith(stem) and old.endswith(".json.gz") and old != f"{f['file_name']}.json.gz":
                os.remove(f"{DIR}/{old}")
        print(f"  {f['file_name']}: {len(hexes):,} hexagons in the areas' boxes, {time.time() - t0:.0f} s", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    c["covers"], c["geom"] = covers, geom
    return c


# ---- the map's layer ----
def enc(ring):
    """A ring as Google's encoded polyline at PREC (lat, lon), without its closing point."""
    out, la0, lo0 = [], 0, 0
    for lo, la in np.asarray(ring.coords)[:-1]:
        la1, lo1 = int(round(la * PREC)), int(round(lo * PREC))
        for v in (la1 - la0, lo1 - lo0):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        la0, lo0 = la1, lo1
    return "".join(out)


def rings(g_utm):
    """A coverage outline (this map's CRS), simplified, as [[outer, hole, ...], ...] encoded in lon/lat."""
    g = shapely.simplify(g_utm, SIMPLIFY_M, preserve_topology=True)
    g = gpd.GeoSeries([g], crs=EPSG).to_crs(4326).iloc[0]
    out = []
    for p in shapely.get_parts(g):
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        out.append([enc(p.exterior)] + [enc(i) for i in p.interiors if len(i.coords) > 3])
    return out


def nice(day):
    d = dt.date.fromisoformat(day)
    return f"{d:%b} {d.day}, {d.year}"


def published(name):
    """The FCC's revision date in a file's name (..._J26_10nov2026) as a date, or None."""
    m = re.search(r"_(\d{1,2})([a-z]{3})(\d{4})$", name)
    try:
        return dt.datetime.strptime("".join(m.groups()), "%d%b%Y").date() if m else None
    except ValueError:
        return None


outline = map_outline()
outline_ll = gpd.GeoSeries([outline], crs=EPSG).to_crs(4326).iloc[0]
states = state_outlines()
states = states[states.intersects(outline_ll)]
states = states[[gpd.GeoSeries([shapely.intersection(g, outline_ll)], crs=4326).to_crs(EPSG).area.iloc[0] >= 1e5
                 for g in states.geometry]]                     # a state the map only touches along its line: none
fips = dict(zip(states.STATEFP, states.STUSPS))
shape_of = dict(zip(states.STATEFP, states.geometry))
try:
    asof = latest_asof()
    files = [f for f in hexagon_files(asof) if str(f.get("state_fips")).zfill(2) in fips and wanted(f)]
except (RuntimeError, netfetch.FetchError) as e:        # no token and no saved list (NetworkDown is a RuntimeError)
    raise SystemExit(f"{AREA}: no cell coverage layer: {e}")
if not files:
    raise SystemExit(f"{AREA}: the FCC lists no 4G or 5G hexagon files for {', '.join(fips.values())} as of {asof}")
print(f"{AREA}: FCC mobile coverage as of {asof}, {len(files)} files ({', '.join(sorted(fips.values()))}): "
      f"{len({f['provider_id'] for f in files})} carriers", flush=True)

by_carrier, names, brands, pub = {}, {}, {}, []
for f in sorted(files, key=lambda f: (str(f["provider_id"]), str(f["state_fips"]), str(f["technology_code"]))):
    st = str(f["state_fips"]).zfill(2)
    c = read_copy(f["file_name"])
    if c is None or not c["covers"].contains(outline_ll):
        try:
            c = make_copy(f, shape_of[st])
        except Stop as e:
            raise SystemExit(f"{AREA}: stopped before {f['file_name']} ({e}); the copies made so far are kept")
        except (RuntimeError, netfetch.FetchError, OSError, ValueError) as e:
            raise SystemExit(f"{AREA}: no cell coverage layer: {f['file_name']} can't be had ({type(e).__name__}: "
                             f"{str(e)[:200]}), and the map needs every file of its states")
    pid = str(f["provider_id"])
    by_carrier.setdefault(pid, []).append(c["geom"])
    names[pid] = f.get("provider_name") or c.get("provider_name") or pid
    if c.get("brand"):
        brands.setdefault(pid, []).append(c["brand"])
    if published(f["file_name"]):
        pub.append(published(f["file_name"]))

area_km2 = outline.area / 1e6
carriers, everyone, left_out = [], [], []
for pid, gs in by_carrier.items():
    g = gpd.GeoSeries([shapely.union_all(gs)], crs=4326).to_crs(EPSG).iloc[0]
    g = shapely.make_valid(g).intersection(outline)
    km2 = g.area / 1e6
    brand = pd.Series(brands.get(pid, [])).value_counts()      # the name the carrier gives its service, else its own
    name = re.sub(r",?\s+(Inc|LLC|Corp|Corporation|Co)\.?$", "", brand.index[0] if len(brand) else names[pid])
    print(f"  {name} ({names[pid]}, provider {pid}): {km2:,.0f} km2, {100 * km2 / area_km2:.1f} % of the map",
          flush=True)
    if km2 <= 0:
        continue
    if pid in NOT_FOR_PHONES:                    # neither in the picker nor in "any carrier"; named in the key
        if km2 >= MIN_KM2:
            left_out.append(dict(n=name, p=round(100 * km2 / area_km2, 1), why=NOT_FOR_PHONES[pid]))
        print(f"    left out: {NOT_FOR_PHONES[pid]}", flush=True)
        continue
    everyone.append(g)
    if km2 < MIN_KM2:
        continue
    carriers.append(dict(n=name, w=names[pid], id=pid, p=round(100 * km2 / area_km2, 1), r=rings(g)))
if not carriers:
    raise SystemExit(f"{AREA}: no carrier reports 4G or 5G in the map")
carriers.sort(key=lambda c: (-c["p"], c["n"]))
anyone = shapely.union_all(everyone)
stale = netfetch.when(WHAT)
CELL = dict(v=1, asof=nice(asof), pub=nice(max(pub).isoformat()) if pub else None, simp=SIMPLIFY_M, km2=round(area_km2),
            c=carriers, any=dict(p=round(100 * anyone.area / 1e6 / area_km2, 1), r=rings(anyone)),
            out=left_out or None, stale=stale or None)
with open(OUT + ".tmp", "w") as f:
    f.write("window.CELL=" + json.dumps(CELL, separators=(",", ":"), ensure_ascii=False) + ";\n")
os.replace(OUT + ".tmp", OUT)
print(f"coverage_data.js {os.path.getsize(OUT) / 1e6:.2f} MB: {len(carriers)} carriers "
      f"({', '.join(c['n'] + ' ' + str(c['p']) + ' %' for c in carriers)}), "
      f"any carrier {CELL['any']['p']} % of the map; "
      f"FCC data as of {CELL['asof']}" + (f", published {CELL['pub']}" if CELL["pub"] else "")
      + (f"; lists from the copy of {stale}" if stale else ""), flush=True)
