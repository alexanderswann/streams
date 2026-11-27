#!/usr/bin/env python3
"""Is everything the maps should show on them? Streams, lakes and ponds, waterfalls and swimming holes against every
independent list we may use, per map. Read-only on the project; needs no network (reference copies that only a
download can make are read from audit/reference/ when `completeness_fetch.py` has made them, and skipped otherwise).

What is measured, all on the maps as published (SITE_DIR: <area>/map3d_data.js and <area>/map3d_layers.js, inline in
<area>/stream_map_3d.html before 2026-11-25; plain or .gz, sitefile.py):
  streams   NHD HR stream lines (StreamRiver) of every box: named ones, year-round (perennial) ones, all of them;
            OSM waterways (river, stream) and USGS 3DHP lines where audit/reference/<area>/ has a copy.
            A piece of reference line counts as drawn when a drawn line is within 150 m (500 ft). A miss is put in the
            first class that fits: at the map's outer edge (300 m), in a lake, where the terrain routing drains under
            0.25 km2 (0.1 sq mi: 03b_stitch.py starts no channel there), 0.25-1 km2 (0.1-0.39 sq mi: drawn only where
            NHD names the creek or maps it year-round, once 05_score.py has NHD_MIN_KM2), and real (1 km2 or more).
  lakes     NHD HR lakes / ponds and reservoirs (not treatment or storage basins) whose middle lies in the map, and OSM
            standing water (05d_lakes.py's copy): shown when a lake of the map overlaps it. By size: at or above the
            map's own smallest size (05d_lakes.py BUILT), between 0.5 ha and that, under 0.5 ha; named ones apart.
            What a single floor would add: the ponds of 0.5 ha (1.2 acres) or more, and the ponds of 0.1 ha or more
            that are named or that an NHD stream line runs into or out of; with their size on the site. The state
            agencies' trout lake lists as cached (shown when a map lake is within 100 m); NCWRC's game-land blanket
            rule, drawn on some unnamed ponds, is no list entry and has its own row ("state rule").
  falls     every source's waterfalls as downloaded (OSM, NHD, GNIS, Wikidata, NPS, CDFW, the curated lists): on the
            map when a map fall is within 150 m or one of the same name within 2 km; whether a terrain drop the map
            draws is within 100 m (330 ft) of each map fall (DEM artifacts and dams not counted); each source's
            licence as recorded in the project.
  swimming  the map's swimming holes; OSM's named swimming spots, Wikidata's swimming holes and the guide lists'
            (as downloaded), and OSM's unnamed ones where audit/reference/<area>/osm_swim.json exists.
  Google Maps and Apple Maps are not read here. Their terms forbid copying or caching map content, so they are a
            spot check by hand only, and nothing from them (names, coordinates, geometry) is stored in the project,
            its caches or the published files (overview session, 2026-11-22). A feature goes on the maps only from an
            open source we may publish (OSM with its credit, USGS, state open data, Overture with its credit) or the
            user's own report of a place they know.
Tables in AUDIT_TABLES: completeness_streams.csv, completeness_stream_misses.csv, completeness_lakes.csv,
completeness_lake_misses.csv, completeness_falls_sources.csv, completeness_falls.csv, completeness_swim.csv,
completeness_swim_misses.csv, and completeness.md (one short table per map).
    SITE_DIR=<maps> SITE_NAME=<label> AUDIT_TABLES=<folder> python audit/scripts/completeness.py [area ...]
    audit/scripts/completeness.sh <label> <maps folder>        (the same, as run_all.sh is run)
"""
import sys, os, re, ast, io, json, glob, zipfile, pickle, hashlib, time
os.environ.setdefault("AUDIT_CACHE", "/Users/mac/Fishing/audit/cache")
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyproj
sys.path.insert(0, os.path.dirname(__file__))
from common import *                                   # noqa: F401,F403  (ROOT, SCR, SITE_DIR, TABLES, CACHE, ...)
from streams_vs_nhd import d8_area_near, runs

REF = f"{ROOT}/audit/reference"
NEAR_M, EDGE_M, FALL_M, SAME_NAME_M, DROP_M = 150, 300, 150, 2000, 100
ACRE = 0.404686          # ha
SQMI = 2.58999           # km2


def const(path, name, default=None):
    m = re.search(rf"^{name}\s*=\s*([0-9.]+)", open(path).read(), re.M)
    return float(m.group(1)) if m else default


MAP_MIN = const(f"{SCR}/05_score.py", "MAP_MIN_KM2", 1.0)
NHD_MIN = const(f"{SCR}/05_score.py", "NHD_MIN_KM2", None)        # None until the edges-and-floor change is in
CHANNEL_MIN = 0.25                                                  # 03b_stitch.py's channel start
_m = re.search(r"^BUILT\s*=\s*(\{.*?\})", open(f"{SCR}/05d_lakes.py").read(), re.M | re.S)
LAKE_MIN_HA = ast.literal_eval(_m.group(1)) if _m else {}

# Licences as the project records them (MEMORY / audit 2.13): what may be published on the site
LICENCE = {"OpenStreetMap": "ODbL, credited", "USGS NHD": "public domain", "USGS GNIS": "public domain",
           "Wikidata": "CC0", "CDFW barrier survey": "public (CA open data)", "Great Smoky Mountains NP": "public domain",
           "gawaterfalls.com (Mark Ozboyd)": "allowed (user, 2026-11-20)",
           "World Waterfall Database": "forbids redistribution: consent asked 2026-11-20",
           "nnywaterfalls.com (David J. Schryver)": "forbids redistribution: consent asked 2026-11-20",
           "Apple Maps": "Apple's terms: not to be copied",
           "Overture Maps": "CDLA-Permissive-2.0 / Apache-2.0, credited (not used by the maps yet)"}


# ---------------------------------------------------------------- the published map
def page_layers(area, site_dir=None):
    """The 3D page's own layers (lakes, falls, drops ...): the object map3d_layers.js (before 2026-11-25: the 3D page
    itself) adds to window.MAP3D."""
    path = f"{site_dir or SITE_DIR}/{area}/map3d_layers.js"
    if not sitefile.exists(path):
        path = f"{site_dir or SITE_DIR}/{area}/stream_map_3d.html"
    raw = sitefile.read_bytes(path)
    pk = f"{CACHE}/page_{area}_{hashlib.sha1(raw).hexdigest()[:16]}.pkl"
    if os.path.exists(pk):
        return pickle.load(open(pk, "rb"))
    s = raw.decode("utf-8")
    k = "Object.assign(window.MAP3D, "
    d, _ = json.JSONDecoder().raw_decode(s[s.index(k) + len(k):])
    d["_bytes"] = {n: len(json.dumps(v, separators=(",", ":"))) for n, v in d.items() if isinstance(v, dict)}
    pickle.dump(d, open(pk, "wb"))
    return d


def layer_gdf(area, layer, d=None):
    d = d or page_layers(area)
    f = d.get(layer, {}).get("features", [])
    if not f:
        return gpd.GeoDataFrame(geometry=[], crs=epsg(area))
    g = gpd.GeoDataFrame([x["properties"] for x in f], geometry=[shapely.geometry.shape(x["geometry"]) for x in f], crs=4326)
    return g.to_crs(epsg(area))


def state_outline(area):
    st = AREAS[area].get("clip_state")
    if not st:
        return None
    # one state ("VT") or several (se_pa's ("PA", "DE", "MD") since 9b9855b), as areaclip.states() reads it
    sts = (st,) if isinstance(st, str) else tuple(st)
    q = ", ".join(f"'{s}'" for s in sts)
    g = gpd.read_file(f"zip://{ROOT}/data/raw/_national/tl_2024_us_state.zip", where=f"STUSPS IN ({q})")
    return shapely.make_valid(g.to_crs(epsg(area)).geometry.union_all())


def inside(area, x, y, clip, state):
    m = shapely.contains_xy(clip, x, y)
    if state is not None:
        m &= shapely.contains_xy(state, x, y)
    return m


def to_ll(area):
    return pyproj.Transformer.from_crs(epsg(area), 4326, always_xy=True)


# ---------------------------------------------------------------- streams
def nhd_waterbodies(area, clip, cols=("gnis_name", "ftype", "fcode", "fcode_description")):
    hu4 = sorted({h for b in boxes(area).values() for h in b["hu4"]})
    x0, y0, x1, y1 = gpd.GeoSeries([clip], crs=epsg(area)).to_crs(4269).total_bounds
    parts = []
    for h in hu4:
        g = f"{ROOT}/data/raw/_national/NHD_H_{h}_HU4_GPKG.gpkg"
        if os.path.exists(g):
            w = gpd.read_file(g, layer="NHDWaterbody", bbox=(x0, y0, x1, y1), columns=list(cols) + ["permanent_identifier"])
            parts.append(w.to_crs(epsg(area)))
    w = pd.concat(parts, ignore_index=True).drop_duplicates("permanent_identifier")
    return gpd.GeoDataFrame(w, geometry="geometry", crs=epsg(area)).reset_index(drop=True)


def line_recall(area, ref_name, ref, classes, drawn, clip, state, water_tree, name_col=None):
    """Rows of recall for each class (a boolean array over ref's lines), and the longest real misses."""
    rows, misses = [], []
    if not len(ref):
        return rows, misses
    px, py, pl, pi = seg_midpoints(ref.geometry.values, 25.0)
    k = inside(area, px, py, clip, state)
    px, py, pl, pi = px[k], py[k], pl[k], pi[k]
    d, _ = nearest_dist(px, py, drawn, 400)
    miss = d > NEAR_M
    pts = shapely.points(px[miss], py[miss])
    edge = np.zeros(len(px), bool)
    edge[miss] = shapely.distance(clip.boundary, pts) < EDGE_M
    inlake = np.zeros(len(px), bool)
    m2 = miss & ~edge
    if water_tree is not None and m2.any():
        hit = water_tree.query(shapely.points(px[m2], py[m2]), predicate="intersects")[0]
        tmp = np.zeros(m2.sum(), bool)
        tmp[np.unique(hit)] = True
        inlake[m2] = tmp
    m3 = miss & ~edge & ~inlake
    d8 = np.full(len(px), np.nan)
    d8[m3] = d8_area_near(area, px[m3], py[m3])
    edge |= m3 & np.isnan(d8)                               # off every box's raster: at an edge
    tiny = m3 & (d8 < CHANNEL_MIN)
    band = m3 & (d8 >= CHANNEL_MIN) & (d8 < MAP_MIN)
    real = m3 & (d8 >= MAP_MIN)
    for label, cls in classes.items():
        m = cls[pi]
        tot = pl[m].sum()
        if tot == 0:
            continue
        mi = lambda mask: round(pl[m & mask].sum() / MI, 1)
        rows.append(dict(area=area, reference=ref_name, lines=label, total_mi=round(tot / MI, 1),
                         drawn_pct=round(100 * pl[m & ~miss].sum() / tot, 1), missed_mi=mi(miss),
                         under_0_1_sqmi_mi=mi(tiny), from_0_1_to_0_39_sqmi_mi=mi(band), at_edge_mi=mi(edge),
                         in_lake_mi=mi(inlake), real_mi=mi(real), real_pct=round(100 * pl[m & real].sum() / tot, 2)))
    # longest real misses, by line (and by name where the reference has names)
    tr = to_ll(area)
    rr = runs(pi, real, pl, px, py)
    byk = {}
    for j, (tot, bl, bx, by) in rr.items():
        nm = ref[name_col].iat[j] if name_col else None
        key = nm if isinstance(nm, str) and nm.strip() else f"line {j}"
        t = byk.setdefault(key, [0.0, 0.0, None, None])
        t[0] += tot
        if bl > t[1]:
            t[1], t[2], t[3] = bl, bx, by
    for key, (tot, bl, bx, by) in byk.items():
        if tot >= 400:
            lon, lat = tr.transform(bx, by)
            misses.append(dict(area=area, reference=ref_name, name=None if key.startswith("line ") else key,
                               missed_mi=round(tot / MI, 2), longest_gap_mi=round(bl / MI, 2),
                               lat=round(lat, 5), lon=round(lon, 5)))
    return rows, misses


_NHD = {}


def nhd_cached(area):
    if area not in _NHD:
        _NHD.clear()
        _NHD[area] = nhd_lines(area)
    return _NHD[area]


def streams(area, clip, state, water_tree, drawn):
    rows, misses = [], []
    nhd = nhd_cached(area)
    nhd = nhd[nhd.ftype.astype(str).isin(["460", "StreamRiver"])].reset_index(drop=True)
    named = (nhd.gnis_name.notna() & (nhd.gnis_name.astype(str).str.strip().str.len() > 0)).to_numpy()
    peren = nhd.fcode.astype(str).eq("46006").to_numpy()
    r, m = line_recall(area, "NHD HR", nhd, {"named": named, "year-round": peren, "named or year-round": named | peren,
                                             "all stream lines": np.ones(len(nhd), bool)},
                       drawn, clip, state, water_tree, "gnis_name")
    rows += r
    misses += m
    for ref_name, fn, ncol in (("OSM", "osm_waterways.gpkg", "name"), ("3DHP", "3dhp_flowlines.gpkg", "gnis_name")):
        p = f"{REF}/{area}/{fn}"
        if not os.path.exists(p):
            rows.append(dict(area=area, reference=ref_name, lines="(no copy: completeness_fetch.py)"))
            continue
        g = gpd.read_file(p).to_crs(epsg(area))
        g = g[g.geom_type.isin(["LineString", "MultiLineString"])].reset_index(drop=True)
        nm = g[ncol].notna().to_numpy() if ncol in g else np.zeros(len(g), bool)
        ww = g["waterway"].astype(str).to_numpy() if "waterway" in g else np.array(["stream"] * len(g))
        cls = {"named": nm, "all": np.ones(len(g), bool)}
        if ref_name == "OSM":
            cls["rivers and streams"] = np.isin(ww, ["river", "stream"])
        r, m = line_recall(area, ref_name, g, cls, drawn, clip, state, water_tree, ncol if ncol in g else None)
        rows += r
        misses += m
    return rows, misses


# ---------------------------------------------------------------- lakes
DROP_LAKE = r"Treatment|Sewage|Settling|Evaporat|Tailings|Cooling|Disposal|Filtration|Covered|Nonearthen"
OSM_NOT_LAKE = {"river", "stream", "canal", "ditch", "drain", "wastewater", "basin", "fountain", "pool", "moat",
                "reflecting_pool", "lock", "swimming_pool", "tidal", "stream_pool", "rapids", "spring"}


def osm_lakes(area, clip, state):
    p = f"{ROOT}/data/raw/{area}/_shared/cache/osm_water.json"
    if not os.path.exists(p):
        return gpd.GeoDataFrame(geometry=[], crs=epsg(area))
    rows, geoms = [], []
    for e in json.load(open(p)):
        t = e.get("tags", {})
        if t.get("water") in OSM_NOT_LAKE or t.get("landuse") == "reservoir" and t.get("reservoir_type") in ("water_storage", "covered"):
            continue
        c = [(q["lon"], q["lat"]) for q in e.get("geometry") or []]
        if len(c) < 4:
            continue
        g = shapely.Polygon(c)
        if not g.is_valid:
            g = shapely.make_valid(g)
        rows.append(dict(osm_id=e.get("id"), name=t.get("name"), water=t.get("water")))
        geoms.append(g)
    g = gpd.GeoDataFrame(rows, geometry=geoms, crs=4326).to_crs(epsg(area))
    rp = shapely.point_on_surface(g.geometry.values)
    k = inside(area, shapely.get_x(rp), shapely.get_y(rp), clip, state)
    g = g[k].reset_index(drop=True)
    g["ha"] = g.geometry.area / 1e4
    return g


def lakes(area, clip, state, page, nhd_wb):
    L = layer_gdf(area, "lakes", page)
    if not len(L):
        return [], [], None
    Lt = shapely.STRtree(L.geometry.values)
    floor = LAKE_MIN_HA.get(area, 1.0)
    N = nhd_wb[nhd_wb.ftype.isin([390, 436]) & ~nhd_wb.fcode_description.fillna("").str.contains(DROP_LAKE)].copy()
    rp = shapely.point_on_surface(N.geometry.values)
    N = N[inside(area, shapely.get_x(rp), shapely.get_y(rp), clip, state)].reset_index(drop=True)
    N["ha"] = N.geometry.area / 1e4
    N["named"] = N.gnis_name.notna()
    N["shown"] = np.isin(np.arange(len(N)), Lt.query(N.geometry.values, predicate="intersects")[0])
    # connected: an NHD stream or river line runs into or out of it (touches or crosses the shore, within 10 m)
    fl = nhd_cached(area)
    fl = fl[fl.ftype.astype(str).isin(["460", "558", "StreamRiver", "ArtificialPath"])]
    ft = shapely.STRtree(fl.geometry.values)
    N["connected"] = np.isin(np.arange(len(N)), ft.query(N.geometry.values, predicate="dwithin", distance=10)[0])
    O = osm_lakes(area, clip, state)
    O["shown"] = np.isin(np.arange(len(O)), Lt.query(O.geometry.values, predicate="intersects")[0]) if len(O) else []
    # site bytes per lake: the 3D page's lakes layer (the 2D page carries the same lakes again)
    small = L.geometry.area < 2e4
    feats = page["lakes"]["features"]
    nb = np.array([len(json.dumps(f, separators=(",", ":"))) for f in feats])
    bytes_small = float(nb[small.to_numpy()].mean()) if small.any() else float(nb.mean())
    rows = []

    def row(ref, label, sel, df):
        s = df[sel]
        if not len(s):
            return
        rows.append(dict(area=area, reference=ref, lakes=label, n=len(s), shown_n=int(s.shown.sum()),
                         shown_pct=round(100 * s.shown.mean(), 1), acres=round(s.ha.sum() / ACRE),
                         acres_shown_pct=round(100 * s.ha[s.shown].sum() / max(s.ha.sum(), 1e-9), 1)))
    # state agencies' lake lists, as 11_context.py / troutdata.py cached them (stocked lakes, regulated lakes, access)
    for p in [q for q in sorted(glob.glob(f"{ROOT}/data/raw/{area}/_shared/cache/trout_*lake*.geojson")) if "access" not in q]:
        try:
            g = gpd.read_file(p).to_crs(epsg(area))
        except Exception:                              # noqa: BLE001  (an empty or odd file: skip it)
            continue
        g = g[g.geometry.notna()]
        rp = shapely.point_on_surface(g.geometry.values)
        g = g[inside(area, shapely.get_x(rp), shapely.get_y(rp), clip, state)].reset_index(drop=True)
        if not len(g):
            continue
        g["shown"] = np.isin(np.arange(len(g)), Lt.query(g.geometry.values, predicate="dwithin", distance=100)[0])
        g["ha"] = g.geometry.area / 1e4
        # NCWRC's game lands' blanket rule ("waters on ... Game Land ... are classified as Wild Trout Waters unless
        # otherwise noted"), drawn on some of their unnamed ponds, is a rule, not an entry of the list: troutdata.py
        # and lakesources.py leave it out, as for creeks. Counted on its own row, outside the list's share
        rule = (g.Reg_Descri.fillna("").astype(str).str.contains("unless otherwise noted", case=False).to_numpy()
                if "Reg_Descri" in g else np.zeros(len(g), bool))
        row("state list", os.path.basename(p)[6:-8], ~rule, g)
        row("state rule", os.path.basename(p)[6:-8] + " (blanket rule, not a list entry)", rule, g)
    row("NHD HR", f"at or above the map's floor ({floor / ACRE:.1f} acres)", N.ha >= floor, N)
    row("NHD HR", f"0.5 ha (1.2 acres) to the floor", (N.ha >= 0.5) & (N.ha < floor), N)
    row("NHD HR", "under 0.5 ha (1.2 acres)", N.ha < 0.5, N)
    row("NHD HR", "named, any size", N.named, N)
    if len(O):
        row("OSM", f"at or above the map's floor ({floor / ACRE:.1f} acres)", O.ha >= floor, O)
        row("OSM", "0.5 ha (1.2 acres) to the floor", (O.ha >= 0.5) & (O.ha < floor), O)
        row("OSM", "named, any size", O.name.notna(), O)
    # what one floor everywhere would add (lakes not shown now)
    add1 = N[~N.shown & (N.ha >= 0.5)]
    add2 = N[~N.shown & (N.ha >= 0.1) & (N.named | N.connected)]
    add3 = N[~N.shown & (N.ha >= 0.1) & N.named]
    rule = dict(area=area, floor_acres=round(floor / ACRE, 1), lakes_shown=len(L),
                add_0_5ha_n=len(add1), add_0_5ha_acres=round(add1.ha.sum() / ACRE),
                add_0_5ha_named_n=int(add1.named.sum()), add_0_5ha_mb=round(len(add1) * bytes_small * 2 / 1e6, 1),
                add_named_0_1ha_n=len(add3), add_named_0_1ha_mb=round(len(add3) * bytes_small * 2 / 1e6, 2),
                add_named_or_connected_0_1ha_n=len(add2), add_named_or_connected_0_1ha_named_n=int(add2.named.sum()),
                add_named_or_connected_0_1ha_mb=round(len(add2) * bytes_small * 2 / 1e6, 1),
                bytes_per_small_lake_per_page=round(bytes_small))
    tr = to_ll(area)
    miss = []
    for q in pd.concat([N[~N.shown & (N.ha >= floor)].nlargest(40, "ha"), N[~N.shown & N.named].nlargest(40, "ha")]).drop_duplicates("permanent_identifier").itertuples():
        c = shapely.point_on_surface(q.geometry)
        lon, lat = tr.transform(c.x, c.y)
        miss.append(dict(area=area, reference="NHD HR", name=q.gnis_name, acres=round(q.ha / ACRE, 1), type=q.fcode_description,
                         connected=bool(q.connected), lat=round(lat, 5), lon=round(lon, 5)))
    if len(O):    # OSM standing water at or above the floor that the map lacks (05d_lakes.py adds OSM-only lakes the lidar confirms)
        for q in O[~O.shown & (O.ha >= floor)].nlargest(40, "ha").itertuples():
            c = shapely.point_on_surface(q.geometry)
            lon, lat = tr.transform(c.x, c.y)
            miss.append(dict(area=area, reference="OSM", name=q.name, acres=round(q.ha / ACRE, 1), type=f"water={q.water}",
                             connected=None, lat=round(lat, 5), lon=round(lon, 5)))
    return rows, miss, rule


# ---------------------------------------------------------------- falls and swimming holes
GENERIC = {"the", "of", "at", "on", "falls", "fall", "waterfall", "waterfalls", "cascade", "cascades", "creek", "brook",
           "branch", "river", "run", "fork", "rapid", "rapids", "shoal", "shoals", "and", "a", "swimming", "hole", "spot",
           "area", "recreation", "scenic", "trail", "park", "natural", "state", "s"}


def tokens(name):
    """02f_known_falls.py's distinctive words of a name ('Falls of Lana' and 'Lana Falls' are both {lana})."""
    if not isinstance(name, str) or not name.strip():
        return frozenset()
    t = re.sub(r"[^a-z0-9]+", " ", re.sub(r"[’'`]", "", name.lower())).split()
    keep = frozenset(w for w in t if w not in GENERIC)
    if keep:
        return keep
    words = [w for w in t if w not in {"the", "of", "at", "on", "and", "a", "s"}]
    if len(words) <= 1:
        return frozenset()
    return frozenset(w for w in words if w not in {"falls", "waterfall", "waterfalls"}) or frozenset(words)


def on_map(area, pts, names, F, Ft):
    """For each point (and its name): a map fall within FALL_M, or one with the same name within SAME_NAME_M."""
    out = np.zeros(len(pts), bool)
    if not len(F):
        return out
    near = Ft.query(pts, predicate="dwithin", distance=FALL_M)[0]
    out[np.unique(near)] = True
    ftok = [tokens(n) for n in F.name]
    pi, fi = Ft.query(pts, predicate="dwithin", distance=SAME_NAME_M)
    for i, j in zip(pi, fi):
        if not out[i]:
            ti, tj = tokens(names[i]), ftok[j]
            if ti and tj and (ti <= tj or tj <= ti):
                out[i] = True
    return out


def raw_falls(area):
    """Every source's points as downloaded (before 02f_known_falls.py's filters and merge), in lon/lat:
    source, name, kind (waterfall / rapids / swimming hole / named feature)."""
    sh = f"{ROOT}/data/raw/{area}/_shared"
    rows = []
    unwrap = lambda p: (lambda j: j.get("data") if isinstance(j, dict) and "bbox" in j else j)(json.load(open(p))) if os.path.exists(p) else None
    for el in unwrap(f"{sh}/osm_falls.json") or []:
        t = el.get("tags", {})
        if el["type"] == "node":
            lon, lat = el["lon"], el["lat"]
        elif el.get("bounds"):
            b = el["bounds"]
            lon, lat = (b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2
        else:
            continue
        nm = t.get("name")
        if t.get("waterway") == "waterfall" or t.get("natural") == "waterfall":
            k = "waterfall"
        elif t.get("waterway") == "rapids":
            k = "rapids"
        elif t.get("leisure") in ("swimming_area", "bathing_place") or t.get("sport") == "swimming" or re.search(r"(?i)swim", nm or ""):
            k = "swimming hole"
        else:
            k = "named feature"
        rows.append(dict(src="OpenStreetMap", name=nm, kind=k, lon=lon, lat=lat))
    for r in sorted(glob.glob(f"{ROOT}/data/raw/{area}/*/nhd_points.gpkg")):
        p = gpd.read_file(r)
        p = p[p.ftype == 487].to_crs(4326)
        rows += [dict(src="USGS NHD", name=n if isinstance(n, str) else None, kind="waterfall", lon=g.x, lat=g.y)
                 for n, g in zip(p.gnis_name, p.geometry)]
    for x in unwrap(f"{sh}/wikidata_falls.json") or []:
        if True:
            lon, lat = map(float, x["coord"]["value"].replace("Point(", "").replace(")", "").split())
            cls = x.get("cls", {}).get("value", "").rsplit("/", 1)[-1]
            rows.append(dict(src="Wikidata", name=x["itemLabel"]["value"], kind={"Q695793": "rapids", "Q7658373": "swimming hole"}.get(cls, "waterfall"),
                             lon=lon, lat=lat))
    for fn, src in (("grsm_falls.json", "Great Smoky Mountains NP"), ("cdfw_pad.json", "CDFW barrier survey")):
        p = f"{sh}/{fn}"
        if os.path.exists(p):
            for f_ in (unwrap(p) or {}).get("features", []):
                xy = (f_.get("geometry") or {}).get("coordinates")
                pr = f_.get("properties") or {}
                if xy:
                    rows.append(dict(src=src, name=pr.get("STATION_NAME") or pr.get("SiteName"), kind="waterfall", lon=xy[0], lat=xy[1]))
    # GNIS: class Falls / Rapids, current file and the 2021 archive (02f_known_falls.py's STATES)
    st = re.search(r"^STATES\s*=\s*(\{.*?\})\n", open(f"{SCR}/02f_known_falls.py").read(), re.M | re.S)
    states = ast.literal_eval(re.sub(r"#[^\n]*", "", st.group(1))).get(area, ()) if st else ()
    seen = set()
    for s_ in states:
        frames = []
        z = f"{ROOT}/data/raw/_national/gnis/DomesticNames_{s_}_Text.zip"
        if os.path.exists(z):
            zz = zipfile.ZipFile(z)
            cur = pd.read_csv(io.StringIO(zz.read(next(n for n in zz.namelist() if n.endswith(".txt"))).decode("utf-8-sig")), sep="|", dtype=str)
            frames.append(cur.rename(columns={"feature_id": "id", "feature_name": "name", "feature_class": "cls", "prim_lat_dec": "lat", "prim_long_dec": "lon"}))
        o = f"{ROOT}/data/raw/_national/gnis/{s_}_Features_20210825.txt"
        if os.path.exists(o):
            old = pd.read_csv(o, sep="|", dtype=str, encoding="utf-8-sig")
            frames.append(old.rename(columns={"FEATURE_ID": "id", "FEATURE_NAME": "name", "FEATURE_CLASS": "cls", "PRIM_LAT_DEC": "lat", "PRIM_LONG_DEC": "lon"}))
        for g in frames:
            g = g[g.cls.isin(["Falls", "Rapids"])]
            for i, n, c, la, lo in zip(g.id, g.name, g.cls, g.lat.astype(float), g.lon.astype(float)):
                if i in seen or la == 0:
                    continue
                seen.add(i)
                rows.append(dict(src="USGS GNIS", name=n, kind="rapids" if c == "Rapids" else "waterfall", lon=lo, lat=la))
    for f in sorted(glob.glob(f"{ROOT}/data/known_falls_curated*.csv")):
        c = pd.read_csv(f, dtype=str, keep_default_na=False)
        c = c[(c.area == area) & (c.kind != "drop") & (c.lat.str.strip() != "")]
        for r in c.itertuples():
            for s_ in [x.strip() for x in r.source.split("·")]:
                rows.append(dict(src=s_, name=r.name, kind=r.kind or "waterfall", lon=float(r.lon), lat=float(r.lat), curated=True))
    # Overture Maps places (not a source of the maps: a witness that may be used, CDLA-Permissive-2.0 / Apache-2.0)
    ov = f"{REF}/{area}/overture_places.csv"
    if os.path.exists(ov):
        o = pd.read_csv(ov)
        o = o[o.name.notna() & ~o.status.fillna("").isin(["permanently_closed"])]
        nm = o.name.str.lower()
        swim = nm.str.contains(OV_SWIM) & ~nm.str.contains(OV_NOT_SWIM) & ~o.cat.isin(OV_SWIM_DENY)
        fall = (o.cat.eq("waterfall") | (nm.str.contains(OV_FALL) & (o.cat.isna() | o.cat.isin(OV_NATURE)))) & ~nm.str.contains(OV_NOT_FALL) & ~swim
        rows += [dict(src="Overture Maps", name=r.name, kind="swimming hole", lon=r.lon, lat=r.lat) for r in o[swim].itertuples()]
        rows += [dict(src="Overture Maps", name=r.name, kind="waterfall", lon=r.lon, lat=r.lat) for r in o[fall].itertuples()]
    d = pd.DataFrame(rows)
    if not len(d):
        return gpd.GeoDataFrame(geometry=[], crs=epsg(area))
    return gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(epsg(area))


OV_SWIM = r"swimm?in'?g? hole|swim hole|blue hole|swim(?:ming)? area|swimming spot|bathing (?:area|place)"
OV_NOT_SWIM = (r"pool|club|school|team|aquatic|lesson|instructor|ymca|diving|center|centre|gym|fitness|tech|supply|service|"
               r"academy|spa\b|restaurant|cuisine|bar\b|hookah|pet|rental|cabin|association|weecare")
OV_SWIM_DENY = {"gym", "swimming_pool", "swimming_instructor", "sports_school", "sport_league", "amateur_sport_team",
                "youth_organization", "charity_organization", "business_consulting", "hookah_bar", "restaurant",
                "caribbean_restaurant", "aquatic_pet_store", "holiday_rental_home", "cabin", "hotel", "lodging",
                "sport_or_fitness_facility", "pool_and_hot_tub_service", "hot_tub_and_pool_store", "shopping", "contractor"}
OV_FALL = r"\bfalls?\b|waterfall|cascades?\b|punch ?bowl|potholes?\b|plunge|cataract"
OV_NOT_FALL = (r"\b(?:church|school|apartments?|village|plaza|shopping|golf|club|estates?|condos?|subdivision|community|association|"
               r"hoa|road|rd|street|st|lane|drive|avenue|ave|inn|lodge|motel|hotel|resort|cabins?|rv|campground|restaurant|cafe|"
               r"grill|pizza|bar|tavern|brewing|brewery|winery|store|shop|market|bank|salon|dental|clinic|realty|homes?|"
               r"mall|center|centre|outlet|library|post office|fire|police|city of|town of|trailhead|parking|yoga|spa|"
               r"recovery|llc|inc|farm|environmental|rentals?|construction|church|chapel|apartment|mobile|motors?|auto)\b")
OV_NATURE = {"waterfall", "park", "hiking_trail", "historic_site", "mountain", "river", "national_park", "state_park", "lake",
             "forest", "beach", "nature_reserve", "landmark_and_historical_building", "scenic_point", "tourist_attraction",
             "attractions_and_activities", "sports_and_recreation", "canyon", "gorge"}


def falls(area, clip, state, page):
    F = layer_gdf(area, "falls", page)
    D = layer_gdf(area, "drops", page)
    if len(D):
        D = D[~D.s.isin(["likely DEM artifact", "dam / weir"])].reset_index(drop=True)
    Ft = shapely.STRtree(F.geometry.values) if len(F) else None
    R = raw_falls(area)
    if len(R):
        R = R[inside(area, R.geometry.x.values, R.geometry.y.values, clip, state)].reset_index(drop=True)
    rows, srows = [], []
    if len(R):
        R["shown"] = on_map(area, R.geometry.values, R.name.tolist(), F, Ft) if Ft is not None else False
        for (src, kind), g in R.groupby(["src", "kind"]):
            srows.append(dict(area=area, source=src, kind=kind, points=len(g), shown_n=int(g.shown.sum()),
                              shown_pct=round(100 * g.shown.mean(), 1),
                              licence=next((v for k, v in LICENCE.items() if src.startswith(k)), "no terms on record")))
        tr = to_ll(area)
        R["nearest_map_fall_ft"] = np.round(shapely.distance(R.geometry.values, shapely.union_all(F.geometry.values)) / FT) if len(F) else np.nan
        ll = [tr.transform(p.x, p.y) for p in R.geometry]
        R["lon_"], R["lat_"] = [round(x, 5) for x, _ in ll], [round(y, 5) for _, y in ll]
    fk = F[F.kind.isin(["waterfall", "cascade", "potholes", "gorge"])] if len(F) else F
    conf = np.zeros(len(fk), bool)
    if len(fk) and len(D):
        conf[np.unique(shapely.STRtree(D.geometry.values).query(fk.geometry.values, predicate="dwithin", distance=DROP_M)[0])] = True
    unm = D[D.s.str.startswith("unmapped")] if len(D) else D
    rows.append(dict(area=area, map_falls=len(fk), terrain_drop_within_330ft_pct=round(100 * conf.mean(), 1) if len(fk) else np.nan,
                     unlisted_terrain_drops=len(unm),
                     swimming_holes=int((F.kind == "swimming hole").sum()) if len(F) else 0,
                     rapids=int((F.kind == "rapids").sum()) if len(F) else 0))
    return rows, srows, R, F, D


def stream_test(area, clip):
    """on_stream(points): within 60 m of an NHD stream or river line and not inside (or within 20 m of) a lake or
    reservoir: 02f_known_falls.py's test for a swimming spot or a named feature that is not tagged as a fall."""
    fl = nhd_cached(area)
    st = shapely.STRtree(fl[fl.ftype.astype(str).isin(["460", "558", "StreamRiver", "ArtificialPath"])].geometry.values)
    wb = nhd_waterbodies(area, clip)
    lk = shapely.STRtree(wb[wb.ftype.isin([390, 436])].geometry.values)

    def on_stream(pts, near=60):
        a_ = np.zeros(len(pts), bool)
        a_[np.unique(st.query(pts, predicate="dwithin", distance=near)[0])] = True
        b_ = np.zeros(len(pts), bool)
        b_[np.unique(lk.query(pts, predicate="dwithin", distance=20)[0])] = True
        return a_ & ~b_
    return on_stream


def swimming(area, R, F, clip, state, on_stream):
    """The map's swimming holes against each source's swimming spots, OSM's full list (named or not, audit/reference)
    and Overture's; split by whether the spot is on a stream (a swimming hole) or not (a lake beach, a pool)."""
    out, miss = [], []
    Ft = shapely.STRtree(F.geometry.values) if len(F) else None
    tr = to_ll(area)
    if len(R):
        s = R[R.kind == "swimming hole"].copy()
        if len(s):      # Overture's points sit where a business would be geocoded: often 100-200 m off the water
            s["on_stream"] = np.where(s.src.eq("Overture Maps"), on_stream(s.geometry.values, 250), on_stream(s.geometry.values))
        for src, g in s.groupby("src"):
            out.append(dict(area=area, source=src, spots=len(g), on_stream_n=int(g.on_stream.sum()), shown_n=int(g.shown.sum()),
                            on_stream_not_shown_n=int((g.on_stream & ~g.shown).sum())))
            for q in g[g.on_stream & ~g.shown].itertuples():
                lon, lat = tr.transform(q.geometry.x, q.geometry.y)
                miss.append(dict(area=area, source=src, name=q.name, lat=round(lat, 5), lon=round(lon, 5)))
    p = f"{REF}/{area}/osm_swim.json"
    if os.path.exists(p):
        els = [e for e in json.load(open(p)) if e.get("center") or "lat" in e]
        if els:
            ll = np.array([(e.get("center") or e)["lon"] for e in els]), np.array([(e.get("center") or e)["lat"] for e in els])
            g = gpd.GeoDataFrame({"name": [e.get("tags", {}).get("name") for e in els],
                                  "what": [e.get("tags", {}).get("leisure") or e.get("tags", {}).get("water") or e.get("tags", {}).get("sport") for e in els]},
                                 geometry=gpd.points_from_xy(*ll), crs=4326).to_crs(epsg(area))
            g = g[inside(area, g.geometry.x.values, g.geometry.y.values, clip, state)].reset_index(drop=True)
            g["on_stream"] = on_stream(g.geometry.values) if len(g) else []
            g["shown"] = on_map(area, g.geometry.values, g.name.tolist(), F, Ft) if Ft is not None and len(g) else False
            out.append(dict(area=area, source="OSM, every swimming spot (reference copy)", spots=len(g),
                            on_stream_n=int(g.on_stream.sum()), shown_n=int(g.shown.sum()),
                            on_stream_not_shown_n=int((g.on_stream & ~g.shown).sum()),
                            unnamed_on_stream_not_shown_n=int((g.on_stream & ~g.shown & g.name.isna()).sum())))
            for q in g[g.on_stream & ~g.shown].itertuples():
                lon, lat = tr.transform(q.geometry.x, q.geometry.y)
                miss.append(dict(area=area, source="OSM (reference copy)", name=q.name, what=q.what, lat=round(lat, 5), lon=round(lon, 5)))
    return out, miss


# ---------------------------------------------------------------- the per-map table
def md_table(S, L, LR, FA, FS, SW):
    def get(df, area, **kw):
        if df is None or not len(df):
            return None
        m = df.area.eq(area)
        for k, v in kw.items():
            m &= df[k].eq(v)
        return df[m].iloc[0] if m.any() else None
    lines = ["| map | named NHD creeks drawn % | real misses mi | year-round NHD drawn % | OSM streams drawn % | NHD lakes at floor shown % (missing) | named NHD lakes shown % | state-listed lakes shown % | floor acres: named ponds under it (MB); all ponds to 1.2 acres (MB) | known falls listed -> on map % | falls the terrain confirms % | swimming holes on map | not on map: Overture falls / swim, OSM swim |",
             "|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---|"]
    present = set().union(*[set(df.area) for df in (S, L, FA) if df is not None and len(df)])
    for a in sorted(present, key=NAMES.index):
        nm = get(S, a, reference="NHD HR", lines="named")
        yr = get(S, a, reference="NHD HR", lines="year-round")
        osm = get(S, a, reference="OSM", lines="all")
        lk = L[L.area.eq(a) & L.reference.eq("NHD HR") & L.lakes.str.startswith("at or above")] if len(L) else []
        lk = lk.iloc[0] if len(lk) else None
        ln = get(L, a, reference="NHD HR", lakes="named, any size")
        r = get(LR, a)
        sl = L[L.area.eq(a) & L.reference.eq("state list")] if len(L) else []
        sl = f"{100 * sl.shown_n.sum() / sl.n.sum():.0f} ({int(sl.n.sum())})" if len(sl) else "no list"
        fa = get(FA, a)
        fs = FS[FS.area.eq(a) & FS.kind.isin(["waterfall"]) & ~FS.source.eq("Overture Maps")] if len(FS) else []
        listed = f"{100 * fs.shown_n.sum() / max(fs.points.sum(), 1):.0f}" if len(fs) else "-"
        ovf = FS[FS.area.eq(a) & FS.kind.eq("waterfall") & FS.source.eq("Overture Maps")] if len(FS) else []
        ovf = int(ovf.points.sum() - ovf.shown_n.sum()) if len(ovf) else 0
        sw = SW[SW.area.eq(a)] if len(SW) else SW
        ovs = sw[sw.source.eq("Overture Maps")].on_stream_not_shown_n.sum() if len(sw) else 0
        osw = sw[sw.source.str.startswith("OSM, every")] if len(sw) else []
        osw = f"{int(osw.on_stream_not_shown_n.iloc[0])}" if len(osw) else "no copy"
        f = lambda v, nd=1: "-" if v is None or v != v else f"{v:.{nd}f}"
        lines.append(f"| {a} | {f(nm.drawn_pct if nm is not None else None)} | {f(nm.real_mi if nm is not None else None, 0)} | "
                     f"{f(yr.drawn_pct if yr is not None else None)} | {f(osm.drawn_pct if osm is not None and 'drawn_pct' in osm and osm.drawn_pct == osm.drawn_pct else None)} | "
                     f"{f(lk.shown_pct if lk is not None else None)} ({'-' if lk is None else lk.n - lk.shown_n}) | {f(ln.shown_pct if ln is not None else None)} | "
                     f"{sl} | {'-' if r is None else f'{r.floor_acres:g}: {r.add_named_0_1ha_n} ({r.add_named_0_1ha_mb:g}); {r.add_0_5ha_n:,} ({r.add_0_5ha_mb:g})'} | {listed} | "
                     f"{f(fa.terrain_drop_within_330ft_pct if fa is not None else None, 0)} | {'-' if fa is None else fa.swimming_holes} | "
                     f"{ovf} / {int(ovs)}, {osw} |")
    return "\n".join(lines)


def main(areas):
    t0 = time.time()
    S, SM, L, LM, LR, FA, FS, FM, SW, SWM = [], [], [], [], [], [], [], [], [], []
    for a in areas:
        clip = area_box_union(a)
        state = state_outline(a)
        page = page_layers(a)
        wb = nhd_waterbodies(a, clip)
        if not NO_STREAMS:
            drawn = np.concatenate([streams_gdf(a, "streams").geometry.values, streams_gdf(a, "streams_lake").geometry.values])
            water = wb[wb.ftype.isin([390, 436, 493])].geometry.values      # lakes, reservoirs, estuaries (not swamps)
            maplakes = layer_gdf(a, "lakes", page).geometry.values
            water_tree = shapely.STRtree(np.concatenate([water, maplakes])) if len(water) + len(maplakes) else None
            r, m = streams(a, clip, state, water_tree, drawn)
            S += r
            SM += m
        r, m, rule = lakes(a, clip, state, page, wb)
        L += r
        LM += m
        if rule:
            LR.append(rule)
        r, sr, R, F, D = falls(a, clip, state, page)
        FA += r
        FS += sr
        if len(R):
            FM += R[~R.shown][["src", "name", "kind", "nearest_map_fall_ft", "lat_", "lon_"]].rename(
                columns={"lat_": "lat", "lon_": "lon"}).assign(area=a).to_dict("records")
        r, m = swimming(a, R, F, clip, state, stream_test(a, clip))
        SW += r
        SWM += m
        print(f"{a} done ({time.time() - t0:.0f} s)", flush=True)
    dfs = dict(streams=pd.DataFrame(S), stream_misses=pd.DataFrame(SM), lakes=pd.DataFrame(L), lake_misses=pd.DataFrame(LM),
               lake_floor=pd.DataFrame(LR), falls=pd.DataFrame(FA), falls_sources=pd.DataFrame(FS),
               falls_misses=pd.DataFrame(FM), swim=pd.DataFrame(SW), swim_misses=pd.DataFrame(SWM))
    for k, df in dfs.items():
        if k == "stream_misses" and len(df):
            df = df.sort_values("missed_mi", ascending=False)
        df.insert(0, "site", site_name())
        df.to_csv(f"{TABLES}/completeness_{k}.csv", index=False)      # written even when empty: nothing missed
    md = md_table(dfs["streams"], dfs["lakes"], dfs["lake_floor"], dfs["falls"], dfs["falls_sources"], dfs["swim"])
    floor_note = (f"floor {MAP_MIN:g} km2 (0.39 sq mi)" + (f", {NHD_MIN:g} km2 (0.1 sq mi) where NHD names or maps the creek year-round" if NHD_MIN else
                  "; NHD_MIN_KM2 not in 05_score.py (named and year-round creeks of 0.1-0.39 sq mi count under the floor)"))
    head = (f"# Completeness, {site_name()} ({time.strftime('%Y-%m-%d %H:%M')})\n\nStreams: a reference line counts as drawn within "
            f"500 ft; 'real misses' drain 0.39 sq mi or more and are not at an edge or in a lake ({floor_note}). Lakes: shown when "
            f"a map lake overlaps; the floor is 05d_lakes.py's per map. Falls: listed = every source's points as downloaded; "
            f"terrain = a drop the map draws within 330 ft.\n\n")
    open(f"{TABLES}/completeness.md", "w").write(head + md + "\n")
    print(head + md)


NO_STREAMS = "--no-streams" in sys.argv          # the light parts only (lakes, falls, swimming): a few minutes
if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("--")] or NAMES)
