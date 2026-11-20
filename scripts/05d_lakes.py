"""Lakes and ponds as places to go: outline, size, surface elevation, depth, fish, inlets and outlets, drainage.
AREA only. Run after 05c_drainages.py and before 08_hike.py, which reads the outlines: a lake blocks walking, and
each lake gets an approach time to its nearest shore. 06_map.py adds access, drive times and trout sightings and draws
them. Built so far for the areas in BUILT (the Jackson pilot, 2026-11-19); elsewhere the script says so and stops.

Each attribute comes from the best source there is for it, and the sources are checked against each other:
- Outline: NHD High Resolution waterbodies (USGS, 1:24,000 or better: NHDWaterbody in the HU4 GeoPackages), lakes /
  ponds and reservoirs. Not treatment, sewage, settling, evaporation or tailings ponds, or covered or concrete
  storage. Pieces of one lake (NHD splits some along reach or HU4 boundaries) are joined. Kept: lakes of MIN_HA or
  more, and any smaller one a fisheries agency lists (cutthroat live in 2-acre alpine lakes).
- Surface elevation: the 10 m 3DEP DEM inside the outline (median), and the share of the outline at that level.
  Lidar DEMs are hydro-flattened, so a lake that holds water reads as one level; a low share means the outline and
  the DEM disagree (a dry or drained basin, or an outline in the wrong place). NHD's own stage elevation is kept
  for comparison where it has one.
- Fish: the state fisheries agency's lake list. Wyoming Game & Fish's fishing guide (Lakes_FishingGuide_PublicView)
  gives the game fish present (species, or "None"), the lake type (alpine lake, lowland lake or reservoir,
  unsuitable standing water, trout farm pond), surveyed depths and private shoreline. It is joined to the NHD lakes
  by NHD reach code, else by overlap. Dated records at the lake from GBIF back it up or contradict it: MARIS (state
  agency fish surveys), iNaturalist research-grade sightings, USGS Nonindigenous Aquatic Species reports and museum
  specimens. A record counts for a lake when it lies within EV_BUFFER_M of the shore and its stated coordinate
  uncertainty (if any) is under EV_MAX_UNCERT_M; iNaturalist sightings with obscured locations are left out.
- Depth: measured values only, never modelled ones: the agency's surveyed maximum / mean depth here, and measured
  bathymetry where a survey exists (lake_bathymetry.py).
- Inlets and outlets: NHD HR flowlines that end or start at the shore (they are drawn downstream), with the creek
  names; lakes with neither are isolated.
- Drainage and fork: 05c_drainages.py's outlines, at the lake's outlet (or inside the lake when it has none).
Writes data/derived/<area>/_shared/lakes.gpkg (one row per lake, the area's CRS) and prints the cross-checks.
"""
import os, re, json, time, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from rasterio import features
from rasterio.windows import from_bounds
from shapely.geometry import box
from config import AREA, REGIONS, CRS, EPSG, NATIONAL, SHARED, SHARED_DERIVED, has, raw_dir, out_dir
from units import ft        # the notes the map popups show are in feet (units.py); the columns stay metric

# Areas with lakes, and the size from which an unlisted pond is kept. An area goes into BUILT once its lakes have been
# checked, because any build of it (run_mid.sh) then puts them on its map. A PLANNED area can be built into a file of
# one's choosing to check it first: LAKES_OUT=/some/where/lakes.gpkg AREA=<area> 05d_lakes.py
BUILT = {"jackson": 0.5, "ne_ct": 1.0, "central_vt": 1.0, "lexington_va": 0.5, "n_georgia": 2.0, "la": 1.0}
PLANNED = {}   # North Georgia: 1,835 farm ponds of 0.5-2 ha
if AREA not in BUILT and not (AREA in PLANNED and os.environ.get("LAKES_OUT")):
    print(f"lakes: not built for {AREA} yet (areas: {', '.join(sorted(BUILT))}); nothing to do")   # not an error
    raise SystemExit(0)

MIN_HA = BUILT.get(AREA, PLANNED.get(AREA))   # lakes and ponds smaller than this are kept only when an agency lists them
LEVEL_TOL_M = 0.3        # a DEM cell within this of the lake's median elevation is on its water surface
EV_BUFFER_M = 50         # a fish record this close to the shore counts for the lake
EV_MAX_UNCERT_M = 250    # ... unless its stated coordinate uncertainty is larger than this
DROP = r"Treatment|Sewage|Settling|Evaporat|Tailings|Cooling|Disposal|Filtration|Covered|Nonearthen"
FTYPE = {390: "lake / pond", 436: "reservoir"}
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
CACHE = f"{SHARED}/cache"
OUT = os.environ.get("LAKES_OUT", f"{SHARED_DERIVED}/lakes.gpkg")    # LAKES_OUT: write elsewhere (to check first)
os.makedirs(CACHE, exist_ok=True)

boxes = gpd.GeoSeries([box(*v["bbox"]) for v in REGIONS.values()], crs=CRS)
U = boxes.union_all()
W, S, E, N = boxes.to_crs(4269).total_bounds

# ---- 1. NHD HR lakes and reservoirs ----
parts = []
for hu in sorted({h for v in REGIONS.values() for h in v["hu4"]}):
    g = gpd.read_file(f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg", layer="NHDWaterbody", bbox=(W, S, E, N),
                      columns=["permanent_identifier", "gnis_id", "gnis_name", "elevation", "reachcode", "ftype",
                               "fcode", "fcode_description"])
    parts.append(g.to_crs(CRS))
wb = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS).drop_duplicates("permanent_identifier")
wb = wb[wb.ftype.isin(list(FTYPE)) & wb.intersects(U)]
dropped = wb.fcode_description.fillna("").str.contains(DROP)
print(f"NHD lakes / reservoirs touching the area: {len(wb)}; left out as treatment, settling or storage: "
      f"{int(dropped.sum())} ({', '.join(sorted(set(wb.fcode_description[dropped])))})")
wb = wb[~dropped].copy()
wb["geometry"] = shapely.make_valid(wb.geometry.force_2d().values)
wb = wb.explode(index_parts=False)
wb = wb[wb.geom_type == "Polygon"].reset_index(drop=True)

# pieces of one lake: polygons that touch and don't carry two different names, and pieces of one name within 30 m
# (NHD splits Beach Pond at the Connecticut / Rhode Island line, 20 m apart)
par = list(range(len(wb)))
def root(i):
    while par[i] != i:
        par[i] = par[par[i]]
        i = par[i]
    return i
nm = wb.gnis_name.tolist()
a_, b_ = wb.sindex.query(wb.geometry.buffer(30.0), predicate="intersects")
for i, j in zip(a_, b_):
    if i >= j:
        continue
    named_same = isinstance(nm[i], str) and nm[i] == nm[j]
    touch = wb.geometry.iat[i].distance(wb.geometry.iat[j]) <= 1.0
    if named_same or (touch and (not isinstance(nm[i], str) or not isinstance(nm[j], str))):
        par[root(i)] = root(j)
wb["grp"] = [root(i) for i in range(len(wb))]
wb["m2"] = wb.area
rows = []
for grp, d in wb.groupby("grp"):
    d = d.sort_values("m2", ascending=False)
    top = d.iloc[0]
    geom = shapely.union_all(d.geometry.values) if len(d) > 1 else top.geometry
    rows.append(dict(nhd_id=top.permanent_identifier, nhd_ids=",".join(d.permanent_identifier),
                     reachcodes=",".join(sorted(set(d.reachcode.dropna()))), gnis_id=top.gnis_id,
                     gnis_name=next((n for n in d.gnis_name if isinstance(n, str)), None),
                     nhd_elev_m=top.elevation, ftype=FTYPE[int(top.ftype)], nhd_type=top.fcode_description,
                     intermittent=bool(d.fcode_description.fillna("").str.contains("Intermittent").any()), geometry=geom))
lk = gpd.GeoDataFrame(rows, crs=CRS)
lk["src_outline"] = "NHD HR"
print(f"lakes after joining pieces: {len(lk)} ({len(wb) - len(lk)} pieces joined)")


def norm(s):
    """'Slide Lake, Lower' -> 'Lower Slide Lake'; for comparing names."""
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()
    if ", " in s:
        base, pre = s.split(", ", 1)
        s = f"{pre} {base}"
    return re.sub(r"\s+", " ", s)

key = lambda s: re.sub(r"[^a-z0-9]", "", (norm(s) or "").lower())


def feet_to_m(v):
    """'26 feet' -> 7.9; 'Undetermined' -> NaN."""
    m = re.match(r"\s*([\d.]+)\s*(feet|foot|ft|meters?|m)\b", str(v or ""), re.I)
    if not m:
        return np.nan
    x = float(m.group(1))
    return round(x * 0.3048, 1) if m.group(2).lower().startswith("f") else round(x, 1)


# ---- 2. the fisheries agency's lake list (Wyoming Game & Fish) ----
lk = lk.assign(agency=None, agency_id=None, agency_name=None, lake_type=None, game_fish=None, common_fish=None,
               private_shore=None, regs_area=None, depth_max_m=np.nan, depth_mean_m=np.nan, depth_src=None,
               depth_note=None, match=None)
if has("wy_trout"):
    import troutdata
    wg = troutdata.fetch("wy_lakes", f"{troutdata.WY}/Lakes_FishingGuide_PublicView/FeatureServer/0", fields="*")
    wg = wg[wg.intersects(U)].copy()
    wg["geometry"] = shapely.make_valid(wg.geometry.values)
    by_rc = {rc: i for i, rcs in enumerate(lk.reachcodes) for rc in rcs.split(",") if rc}
    hits, added = {}, []
    for j, r in wg.iterrows():
        i, how = by_rc.get(str(r.ReachCode)), "NHD reach code"
        if i is None:                          # reach codes move between NHD versions: then the lake it overlaps most
            cand = lk.sindex.query(r.geometry, predicate="intersects")
            ov = [(lk.geometry.iat[c].intersection(r.geometry).area / min(lk.geometry.iat[c].area, r.geometry.area), c)
                  for c in cand]
            ov = [x for x in ov if x[0] >= 0.5]
            i, how = (max(ov)[1], "overlap") if ov else (None, None)
        if i is None:
            added.append(j)
        else:
            hits.setdefault(i, []).append((j, how))
    # a WGFD lake with no NHD outline: kept, with the agency's own outline
    if added:
        extra = wg.loc[added]
        lk = pd.concat([lk, gpd.GeoDataFrame(dict(nhd_id=None, gnis_name=extra.GNIS_Name.where(extra.GNIS_Name.notna(), None),
                                                  ftype=np.where(extra.WaterType.str.contains("Reservoir", na=False),
                                                                 "reservoir", "lake / pond"),
                                                  intermittent=False, src_outline="WGFD (no NHD lake)",
                                                  geometry=extra.geometry.values), crs=CRS)], ignore_index=True)
        for k, j in enumerate(added):
            hits[len(lk) - len(added) + k] = [(j, "own outline")]
    for i, js in hits.items():
        rs = wg.loc[[j for j, _ in js]]
        fish = sorted({s.strip() for v in rs.GameFishPresent.fillna("") for s in v.split(",") if s.strip() and s.strip() != "None"})
        common = sorted({s.strip() for v in rs.CommonGameFish.fillna("") for s in v.split(",") if s.strip() and s.strip() != "None"})
        dmax = [feet_to_m(v) for v in rs.MaxDepth]
        dmean = [feet_to_m(v) for v in rs.AvgDepth]
        lk.loc[i, ["agency", "agency_id", "agency_name", "lake_type", "game_fish", "common_fish", "private_shore",
                   "regs_area", "match"]] = [
            "Wyoming Game & Fish", ",".join(rs.WaterID.astype(str)), " / ".join(norm(n) for n in rs.WaterName),
            " / ".join(sorted(set(rs.WaterType.fillna("")))), ", ".join(fish) if fish else "None",
            ", ".join(common) if common else None,
            "; ".join(sorted(set(rs.PrivateLand.dropna()))) or None,
            ",".join(sorted({str(int(x)) for x in rs.DrainageRegulationsNumber.dropna()})) or None,
            "; ".join(sorted({h for _, h in js}))]
        if np.isfinite(np.nanmax(dmax + [np.nan])) if any(np.isfinite(dmax)) else False:
            lk.loc[i, ["depth_max_m", "depth_src"]] = [np.nanmax(dmax), "Wyoming Game & Fish fishing guide (method and year not given)"]
        if any(np.isfinite(dmean)):
            lk.loc[i, "depth_mean_m"] = np.nanmax(dmean)
    for i, js in hits.items():
        for j, h in js:
            if h != "NHD reach code":
                print(f"  joined by {h}: {wg.WaterName[j]} ({wg.Acres[j]} acres) -> NHD {lk.gnis_name.iat[i]} "
                      f"{lk.geometry.iat[i].area / 1e4:.1f} ha")
    # the agency's own elevation, where it has one, against the DEM's (below)
    lk["agency_elev_m"] = np.nan
    for i, js in hits.items():
        e_ = pd.to_numeric(wg.loc[[j for j, _ in js], "Elevation"], errors="coerce").dropna()
        if len(e_):
            lk.loc[i, "agency_elev_m"] = round(float(e_.iloc[0]), 1)
    n_rc = sum(1 for js in hits.values() for _, h in js if h == "NHD reach code")
    n_ov = sum(1 for js in hits.values() for _, h in js if h == "overlap")
    print(f"Wyoming Game & Fish lakes in the area: {len(wg)}; joined by reach code {n_rc}, by overlap {n_ov}, "
          f"no NHD lake (own outline kept) {len(added)}; NHD lakes with more than one WGFD record: "
          f"{sum(len(js) > 1 for js in hits.values())}")
    bad = [(lk.gnis_name.iat[i], lk.agency_name.iat[i]) for i in hits if isinstance(lk.gnis_name.iat[i], str)
           and key(lk.gnis_name.iat[i]) not in {key(n) for n in str(lk.agency_name.iat[i]).split(" / ")}]
    if bad:
        print(f"  names that differ (NHD / GNIS vs Game & Fish), {len(bad)}: " + "; ".join(f"{a} / {b}" for a, b in bad))

# A lake's name: the official GNIS name (NHD), else the agency's (it numbers unnamed lakes: "Granite Basin Lake 2").
# The agency's name wins where GNIS names only a group ("Basin Lakes" for Two Island and Mirror lakes, "Toppings
# Lakes") or the agency adds a qualifier to it ("Green Lake" -> "Lower Green Lake").
QUAL = r"^(?:Upper|Lower|Middle|North|South|East|West|Little|Big)\s|\s\d+$"
def pick_name(g, a):
    a = a.split(" / ")[0] if isinstance(a, str) else None
    if not isinstance(g, str):
        return (a, "agency") if a else (None, None)
    if a and (re.search(r"\b(?:Lakes|Ponds|Pools)$", g) or
              (re.search(QUAL, a) and key(re.sub(QUAL, " ", a).strip()) == key(g))):
        return a, "agency"
    return g, "GNIS"
nn = [pick_name(g, a) for g, a in zip(lk.gnis_name, lk.agency_name)]
lk["name"], lk["name_src"] = [n for n, _ in nn], [s for _, s in nn]
lk["ha"] = (lk.area / 1e4).round(2)
import lakedata
def _locate(at):
    x, y = at
    return gpd.GeoSeries([shapely.Point(x, y)], crs=4326 if abs(x) <= 180 else 26912).to_crs(CRS).iloc[0]
surveyed = set()
for d in lakedata.DEPTHS.get(AREA, []) + lakedata.SURVEYS.get(AREA, []):
    p_ = _locate(d["at"])
    near_ = [i for i in lk.sindex.query(p_.buffer(1500), predicate="intersects") if key(d["lake"]) == key(lk.gnis_name.iat[i])]
    surveyed |= set(near_[:1])
keep = (lk.ha >= MIN_HA) | lk.agency.notna() | lk.index.isin(list(surveyed))
print(f"kept {int(keep.sum())} lakes: {int((lk.ha >= MIN_HA).sum())} of {MIN_HA} ha or more, "
      f"{int((keep & (lk.ha < MIN_HA)).sum())} smaller ones an agency lists; left out {int((~keep).sum())} unlisted "
      f"ponds under {MIN_HA} ha")
lk = lk[keep].reset_index(drop=True)
lk["in_area"] = (lk.geometry.intersection(U).area / lk.area).round(3)
lk["shore_km"] = (lk.geometry.boundary.length / 1000).round(2)
lk["islands"] = [sum(len(p.interiors) for p in getattr(g, "geoms", [g])) for g in lk.geometry]

# ---- 3. surface elevation and level water from the DEM ----
vals = [[] for _ in range(len(lk))]
for r in REGIONS:
    p = f"{raw_dir(r)}/dem_10m.tif"
    if not os.path.exists(p):
        continue
    with rasterio.open(p) as src:
        bb = box(*src.bounds)
        for i in lk.sindex.query(bb, predicate="intersects"):
            # one cell in from the shore, where a cell is all water (the full outline where that leaves too little)
            g0 = lk.geometry.iat[i]
            g = g0.buffer(-10).intersection(bb)
            if g.is_empty or g.area < 0.3 * g0.intersection(bb).area:
                g = g0.intersection(bb)
            if g.is_empty:
                continue
            w = from_bounds(*g.bounds, transform=src.transform).round_offsets().round_lengths()
            a = src.read(1, window=w, boundless=True, fill_value=src.nodata if src.nodata is not None else -9999)
            if not a.size:
                continue
            msk = features.geometry_mask([g], out_shape=a.shape, transform=src.window_transform(w), invert=True)
            v = a[msk & (a > -100)]
            if src.nodata is not None:
                v = v[v != src.nodata]
            vals[i].extend(v.tolist())
lk["dem_cells"] = [len(v) for v in vals]
lk["elev_m"] = [round(float(np.median(v)), 1) if len(v) else np.nan for v in vals]
lk["level_share"] = [round(float(np.mean(np.abs(np.asarray(v) - np.median(v)) <= LEVEL_TOL_M)), 2) if len(v) >= 10 else np.nan
                     for v in vals]
# NHD's stage elevation is in metres in some places (Jackson: Jenny Lake 2,067.46) and in feet in others, lake by
# lake (NE Connecticut: Pachaug Pond 159 against a 48 m surface, Lake Chaubunagungamaug in metres): each is read in
# the unit that agrees with the DEM, and dropped where neither does. Read as metres, the feet made 161 Connecticut
# lakes look drawn down by 100 m and more
_st = lk.nhd_elev_m.astype(float)
_ft = _st * 0.3048
_use_ft = _st.notna() & lk.elev_m.notna() & ((lk.elev_m - _ft).abs() < (lk.elev_m - _st).abs()) & ((lk.elev_m - _ft).abs() < 15)
lk.loc[_use_ft, "nhd_elev_m"] = _ft[_use_ft].round(2)
_bad = _st.notna() & lk.elev_m.notna() & ~_use_ft & ((lk.elev_m - lk.nhd_elev_m).abs() > 30)
lk.loc[_bad, "nhd_elev_m"] = np.nan
print(f"NHD stage elevations: {int(_st.notna().sum())}; read as feet {int(_use_ft.sum())}; matching neither, dropped {int(_bad.sum())}")
d_el = (lk.elev_m - lk.nhd_elev_m)
print(f"surface elevation: {lk.elev_m.notna().sum()} lakes; DEM minus NHD stage elevation, where NHD has one "
      f"({d_el.notna().sum()}): " + "; ".join(f"{n} {d:+.1f} m" for n, d in zip(lk.name[d_el.notna()], d_el[d_el.notna()])))
if "agency_elev_m" in lk:
    d_ag = (lk.elev_m - lk.agency_elev_m).dropna()
    print(f"DEM minus the agency's elevation ({len(d_ag)} lakes): median {d_ag.abs().median():.1f} m; over 3 m: "
          + "; ".join(f"{n} {d:+.1f}" for n, d in zip(lk.name[d_ag.index], d_ag) if abs(d) > 3))
low = lk[(lk.level_share < 0.5) & (lk.dem_cells >= 30)]
print(f"lakes whose 10 m DEM surface isn't level (under half the outline within {LEVEL_TOL_M} m of the median; 30+ "
      f"cells): {len(low)}")

# ---- 3b. 1 m lidar: the water level and shoreline on the survey date (lakelidar.py) ----
# The newest 1 m survey covering each lake. Its hydro-flattened water gives the level, measured, and the shoreline,
# which replaces NHD's (mapped from older photos and topo sheets) unless the lake is a reservoir or was drawn down
# that day: then NHD's full-pool outline stays and the popup says how low it was.
import lakelidar
from concurrent.futures import ThreadPoolExecutor
LIDAR_MAX_HA = 600      # bigger lakes keep the NHD outline (Jackson Lake, Palisades: regulated, their level swings by metres)
DRAWN_DOWN_M = 2.0      # a regulated lake's lidar level this far below NHD's stage: it was low that day
L1 = f"{CACHE}/lake_dem1m"
os.makedirs(L1, exist_ok=True)
cat = lakelidar.catalog(tuple(boxes.buffer(3000).to_crs(4326).total_bounds), CACHE)


def lidar_one(g, ck, mine):
    """(level, share, shoreline, runs off, work unit, surface stats) for one outline, or None; a lake whose lidar can't
    be read keeps its NHD outline (the step goes on)."""
    try:
        return _lidar_one(g, ck, mine)
    except Exception as ex:
        print(f"  lidar not read for {ck}: {type(ex).__name__}: {str(ex)[:120]}")
        return None


def _lidar_one(g, ck, mine):
    """(level, share, shoreline, runs off, work unit) for one outline; the window widens while the water runs off it."""
    res = None
    for pad in (60, 240, 720):
        w = lakelidar.window(g, CRS, cat, pad, f"{L1}/{ck}_{pad}.tif")
        if w is None:
            return None
        a, T, u = w
        bb = box(*g.buffer(pad).bounds)
        others = [wb.geometry.iat[j] for j in wb.sindex.query(bb, predicate="intersects")
                  if wb.permanent_identifier.iat[j] not in mine and not wb.geometry.iat[j].intersects(g)]
        res = (*lakelidar.water(a, T, g, others), u, lakelidar.surface_stats(a, T, g))
        if not res[3]:
            break
    return res


def flown(u):
    """When a lidar work unit was flown: its month, or its first to last month (one can take a year: VA_West_Chesapeake
    _B1_2017 ran from April 2017 to May 2018, so no single month is the day a lake was seen)."""
    s, e = u["start"][:7], u["end"][:7]
    return s if s == e else f"{s} to {e}"


def ckey(i):
    return re.sub(r"\W", "_", str(lk.nhd_id.iat[i] if isinstance(lk.nhd_id.iat[i], str) else lk.agency_id.iat[i]))


todo = [i for i in range(len(lk)) if lk.ha.iat[i] <= LIDAR_MAX_HA]
with ThreadPoolExecutor(6) as ex:
    got = dict(zip(todo, ex.map(lambda i: lidar_one(lk.geometry.iat[i], ckey(i),
                                                    set(str(lk.nhd_ids.iat[i] or "").split(","))), todo)))
nhd_g = lk.geometry.copy()                       # kept for the inlet / outlet test (NHD's lines end on its shore)
lk["nhd_ha"] = lk.ha
# Regulated lakes: reservoirs, and lakes with a dam on the shore (OSM dams; NHD dam / weir lines). Only their level
# goes up and down by metres. NHD's "normal level" comes from old topographic maps and can be off by a few metres, or
# by 12 (Table Mountain Lake), so a natural lake whose lidar level sits under it wasn't drawn down: NHD is wrong.
_dams = []
for r in REGIONS:
    if os.path.exists(f"{raw_dir(r)}/osm_dams.gpkg"):
        _dams.append(gpd.read_file(f"{raw_dir(r)}/osm_dams.gpkg").to_crs(CRS).geometry)
for hu in sorted({h for v in REGIONS.values() for h in v["hu4"]}):
    try:
        _l = gpd.read_file(f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg", layer="NHDLine", bbox=(W, S, E, N), columns=["ftype"])
        _dams.append(_l[_l.ftype == 343].to_crs(CRS).geometry)
    except Exception:
        pass
_dams = gpd.GeoSeries(pd.concat(_dams, ignore_index=True) if _dams else [], crs=CRS)
_dams = _dams[_dams.notna() & ~_dams.is_empty]
lk["regulated"] = lk.ftype.eq("reservoir")
if len(_dams):
    _near = set(lk.sindex.query(_dams.buffer(100).values, predicate="intersects")[1])
    lk.loc[lk.index.isin(list(_near)), "regulated"] = True
print(f"regulated (reservoir or a dam on the shore): {int(lk.regulated.sum())} of {len(lk)} lakes")
for c in ("lidar_survey", "lidar_dates", "lidar_ql", "lidar_kind", "water_note", "outline_note"):
    lk[c] = None
for c in ("water_level_m", "lidar_share", "lidar_ha", "lidar_iou", "normal_m"):
    lk[c] = np.nan
lk["normal_src"] = None     # a lake the lidar caught low: its normal level, for its elevation (set below)
n_used = 0
for i, res in got.items():
    if res is None:
        lk.loc[i, "water_note"] = "no 3 ft lidar covers it"
        continue
    lev, share, poly, edge, u, (med, w15, iqr, shore) = res
    lk.loc[i, ["lidar_survey", "lidar_dates", "lidar_ql", "lidar_share"]] = [
        u["workunit"], f"{u['start']} to {u['end']}", u["ql"], round(share, 2) if np.isfinite(share) else np.nan]
    if not np.isfinite(lev) or poly is None:
        # Not flattened. Water that the survey didn't flatten still reads level (Bills Bayou Pond: 95% of it within
        # 15 cm): its level counts, its outline stays NHD's. Only a surface that isn't level (Dry Basin Lake: 13 m of
        # relief in the outline) says the lake was largely dry, marsh or overgrown then, and only with the 10 m DEM
        # agreeing (an older survey) and from 2 acres, where open water would have been flattened
        if np.isfinite(w15) and w15 >= 0.7:
            lk.loc[i, ["water_level_m", "lidar_kind"]] = [round(med, 1), "level, not flattened"]
        elif np.isfinite(w15) and w15 < 0.5 and lk.nhd_ha.iat[i] >= 0.8 and not (lk.level_share.iat[i] >= 0.7):
            # a bed below its own or a neighbouring lake's normal level (NHD stage) fills and drains with that lake: the
            # unnamed 15 ha lake 214 m from Jackson Lake lay drained in the fall 2022 flight, under the reservoir's level
            near_ = [j for j in lk.sindex.query(lk.geometry.iat[i].buffer(500), predicate="intersects")
                     if np.isfinite(lk.nhd_elev_m.iat[j]) and lk.regulated.iat[j]]
            top = max(near_, key=lambda j: lk.nhd_elev_m.iat[j]) if near_ else None
            # Its own level only where the lidar's shore also stands over the bed (NHD's level can be metres off); a
            # neighbour's only where this lake's own shore lies at that level, one water at normal pool (the lake by
            # Jackson Lake: 0.5 m under it). A pond below a neighbour's dam sits metres under its level (Cochrans Lake
            # North, 9.7 m under Cochrans Lake South) and fills on its own.
            _stg = lk.nhd_elev_m.iat[top] if top is not None else np.nan
            if (top is not None and np.isfinite(med) and _stg - med > 1.0 and np.isfinite(shore)
                    and (shore - med > 1.0 if top == i else abs(shore - _stg) <= 1.5)):
                whose = ("its own normal water level" if top == i else
                         f"the normal level of {lk.name.iat[top] or 'the lake beside it'}")
                lk.loc[i, "water_note"] = (f"most of its bed lies below {whose} ({ft(lk.nhd_elev_m.iat[top])} in NHD): "
                                           f"the lidar of {flown(u)} caught it drawn down")
                if top == i:
                    lk.loc[i, ["normal_m", "normal_src"]] = [lk.nhd_elev_m.iat[i], "normal level (NHD)"]
            elif lk.regulated.iat[i] and np.isfinite(med) and np.isfinite(shore) and shore - med > 1.0:
                # a dammed lake NHD gives no normal level: its bed against its own shore, by the same lidar (Cave
                # Mountain Lake, a Forest Service swimming lake full on today's imagery, lay drained in the 2017-18 flight)
                lk.loc[i, "water_note"] = (f"most of its bed lies {ft(shore - med)} below its shoreline: the lidar of "
                                           f"{flown(u)} caught it drained or drawn down")
                lk.loc[i, ["normal_m", "normal_src"]] = [shore, "its shoreline, by lidar"]
            else:
                lk.loc[i, "water_note"] = (f"little level water in the lidar of {flown(u)}: only {w15:.0%} of the outline "
                                           f"lies within 6 inches of one level; it was largely dry, marsh or overgrown then")
        continue
    lk.loc[i, "lidar_kind"] = "flattened" 
    lk.loc[i, ["water_level_m", "lidar_ha", "lidar_iou"]] = [
        round(lev, 2), round(poly.area / 1e4, 2), round(poly.intersection(nhd_g.iat[i]).area / poly.union(nhd_g.iat[i]).area, 2)]
    stage = lk.nhd_elev_m.iat[i]
    # drawn down: the lidar's level well under NHD's normal level, and the normal shore (NHD's outline) standing clear
    # of the water in the same lidar. NHD's level alone isn't enough: at 50 dammed North Georgia lakes it sits 2-28 m
    # over water whose shore the lidar shows at the water's edge (Teague Lake, Etowah Number 32 Lake): NHD is wrong
    # there, the lakes were full. Lynchburg Reservoir's shore stood 3.2 m clear in the 2017-18 flight
    drawn = (bool(lk.regulated.iat[i]) and np.isfinite(stage) and stage - lev > DRAWN_DOWN_M
             and np.isfinite(shore) and shore - lev > 1.0)
    if drawn:
        if abs(stage - shore) <= 2.0:      # NHD's level and the lidar's shore agree: NHD's is the normal level
            lk.loc[i, "water_note"] = f"{ft(stage - lev, 1)} below its normal level when the lidar was flown ({flown(u)})"
            lk.loc[i, ["normal_m", "normal_src"]] = [stage, "normal level (NHD)"]
        else:
            lk.loc[i, "water_note"] = f"{ft(shore - lev, 1)} below its shoreline when the lidar was flown ({flown(u)})"
            lk.loc[i, ["normal_m", "normal_src"]] = [shore, "its shoreline, by lidar"]
    if lk.ftype.iat[i] == "reservoir" or drawn or edge:
        lk.loc[i, "outline_note"] = "NHD outline kept: " + ("reservoir" if lk.ftype.iat[i] == "reservoir" else
                                                            "drawn down on the survey date" if not edge else
                                                            "level water runs on past the lake (a river at its level)")
        continue
    lk.loc[i, "geometry"] = poly
    lk.loc[i, "src_outline"] = f"lidar 3 ft, {u['workunit']} ({flown(u)})"    # maplakes.py reads the "lidar" start
    n_used += 1
lk = gpd.GeoDataFrame(lk, geometry="geometry", crs=CRS)
r_ = lk.lidar_ha / lk.nhd_ha
print(f"1 m lidar: {len(got)} lakes tried, level water at {lk.water_level_m.notna().sum()}, shoreline used for {n_used}; "
      f"surveys: {lk.lidar_survey.value_counts().to_dict()}")
print(f"  lidar vs NHD outline: median overlap (IoU) {lk.lidar_iou.median():.2f}; area ratio lidar/NHD "
      f"p10 {r_.quantile(0.1):.2f}, median {r_.median():.2f}, p90 {r_.quantile(0.9):.2f}")
for i in np.where((r_ > 1.5) | (r_ < 0.6))[0]:
    print(f"  {lk.name.iat[i] or 'unnamed'}: NHD {lk.nhd_ha.iat[i]:.2f} ha, lidar {lk.lidar_ha.iat[i]:.2f} ha "
          f"({lk.lidar_survey.iat[i]}); {lk.outline_note.iat[i] or 'lidar outline used'}")
d_st = (lk.water_level_m - lk.nhd_elev_m).dropna()
print("  lidar level minus NHD stage: " + "; ".join(f"{n} {d:+.1f} m" for n, d in zip(lk.name[d_st.index], d_st)))
print("  no level water although 0.8 ha or more: " + "; ".join(
    f"{n or 'unnamed'} {h:.1f} ha" for n, h, w_ in zip(lk.name, lk.nhd_ha, lk.water_note) if isinstance(w_, str) and w_.startswith("no level")))

# ---- 3c. lakes NHD misses: OpenStreetMap water of MIN_HA or more that no NHD lake covers, kept where the lidar shows
# level water there (new ponds; R Park in Wilson, a gravel pit made into a park, is in NHD as a 0.3 ha remnant) ----
from geomatch import overpass
p_osm = f"{CACHE}/osm_water.json"
if os.path.exists(p_osm) and os.environ.get("REFRESH") != "1" and time.time() - os.path.getmtime(p_osm) < 7 * 86400:
    els = json.load(open(p_osm))
else:
    w_, s_, e_, n_ = boxes.to_crs(4326).total_bounds
    els = overpass(f'[out:json][timeout:300];(way["natural"="water"]({s_},{w_},{n_},{e_});'
                   f'way["landuse"="reservoir"]({s_},{w_},{n_},{e_}););out tags geom;')
    with open(p_osm + ".tmp", "w") as f:
        json.dump(els, f)
    os.replace(p_osm + ".tmp", p_osm)
NOT_LAKE = {"river", "stream", "canal", "ditch", "drain", "wastewater", "pool", "fountain", "moat", "lock", "stream_pool"}
op = [(dict(e.get("tags", {}), osm_id=e.get("id")), shapely.Polygon([(p["lon"], p["lat"]) for p in e["geometry"]])) for e in els
      if e.get("geometry") and len(e["geometry"]) >= 4 and e["geometry"][0] == e["geometry"][-1]
      and e.get("tags", {}).get("water") not in NOT_LAKE]
osm = gpd.GeoDataFrame([t for t, _ in op], geometry=[g for _, g in op], crs=4326).to_crs(CRS) if op else None
osm_all = osm          # all of it, for names (3d)
added = []
if osm is not None and len(osm):
    osm = osm[osm.is_valid & (osm.area >= MIN_HA * 1e4) & osm.intersects(U)]
    have = pd.concat([lk.geometry, wb.geometry], ignore_index=True)
    hv = gpd.GeoDataFrame(geometry=have, crs=CRS)
    cov = [sum(hv.geometry.iat[j].intersection(g).area for j in hv.sindex.query(g, predicate="intersects")) / g.area
           for g in osm.geometry]
    cand = osm[np.asarray(cov) < 0.2]
    for k, (t, g) in enumerate(zip(cand.drop(columns="geometry").to_dict("records"), cand.geometry)):
        res = lidar_one(g, f"osm_{k}_{int(g.centroid.x)}_{int(g.centroid.y)}", set())
        ok = res is not None and np.isfinite(res[0]) and res[2] is not None and not res[3] and res[2].area >= MIN_HA * 1e4
        if ok:   # a lake already in the list (or added from another OSM piece of the same pond) isn't added again
            taken = [x["geometry"] for x in added] + [lk.geometry.iat[j] for j in lk.sindex.query(res[2], predicate="intersects")]
            if sum(res[2].intersection(t_).area for t_ in taken) > 0.3 * res[2].area:
                print(f"  (the same water as a lake already in the list: skipped)")
                ok = False
        print(f"  OpenStreetMap water missing from NHD: {t.get('name') or 'unnamed'} {g.area / 1e4:.1f} ha -> "
              + (f"level water {res[0]:.2f} m on {res[1]:.0%}, kept ({res[2].area / 1e4:.2f} ha)" if ok else
                 "no level lidar water, left out"))
        if ok:
            u = res[4]
            added.append(dict(gnis_name=None, osm_id=t.get("osm_id"), name=t.get("name"), name_src="OpenStreetMap" if t.get("name") else None,
                              ftype="reservoir" if t.get("water") == "reservoir" or t.get("landuse") == "reservoir" else "lake / pond",
                              intermittent=t.get("intermittent") == "yes", src_outline=f"lidar 3 ft, {u['workunit']} ({flown(u)})",
                              outline_note="not in NHD: found in OpenStreetMap, confirmed by lidar",
                              lidar_survey=u["workunit"], lidar_dates=f"{u['start']} to {u['end']}", lidar_ql=u["ql"],
                              water_level_m=round(res[0], 2), lidar_share=round(res[1], 2), lidar_ha=round(res[2].area / 1e4, 2),
                              lidar_kind="flattened",
                              nhd_ha=np.nan, geometry=res[2]))
if added:
    lk = gpd.GeoDataFrame(pd.concat([lk, gpd.GeoDataFrame(added, crs=CRS)], ignore_index=True), geometry="geometry", crs=CRS)
    nhd_g = pd.concat([nhd_g, gpd.GeoSeries([a["geometry"] for a in added], crs=CRS)], ignore_index=True)
print(f"lakes added from OpenStreetMap + lidar: {len(added)}")
# the lakes added from OpenStreetMap get the same test as the rest (a reservoir, or a dam within 100 m of the shore);
# without it the column held True, False and empty, and was written to the GeoPackage as text ("False" reads true)
_new = np.flatnonzero(lk.regulated.isna().values)
if len(_new):
    _sub = lk.iloc[_new].reset_index(drop=True)
    _reg = _sub.ftype.eq("reservoir").values
    if len(_dams):
        _reg = _reg | np.isin(np.arange(len(_sub)), _sub.sindex.query(_dams.buffer(100).values, predicate="intersects")[1])
    lk.iloc[_new, lk.columns.get_loc("regulated")] = _reg
lk["regulated"] = lk.regulated.astype(bool)

# ---- 3d. names NHD doesn't have: OpenStreetMap's, where one named OpenStreetMap outline and the lake cover at least
# half of each other, and no lake within 2 km has that name already (Lexington: OpenStreetMap and GNIS put "Walace
# Lake" on two ponds 700 m apart on Poor Creek). Virginia's public fishing lake layer is not used for names: it calls
# the 189-acre Mill Creek Reservoir "Mill Reservoir" (DWR's own page and OpenStreetMap: Mill Creek Reservoir) ----
n_osm = []
if osm_all is not None and "name" in osm_all:
    on = osm_all[osm_all.is_valid & osm_all["name"].notna()].reset_index(drop=True)
    for i in np.flatnonzero(lk["name"].isna().values):
        g = lk.geometry.iat[i]
        hits = set()
        for j in on.sindex.query(g, predicate="intersects"):
            a = g.intersection(on.geometry.iat[j]).area
            if a >= 0.5 * g.area and a >= 0.5 * on.geometry.iat[j].area:
                hits.add(on["name"].iat[j].strip())
        if len(hits) != 1:
            continue
        nm = hits.pop()
        near_ = lk["name"].iloc[lk.sindex.query(g.buffer(2000), predicate="intersects")]
        # a name ending in "Dam" is the dam's, put on its pond (Cyril Dam, Wells Brook Dam in Connecticut): left out
        if not nm or re.search(r"\bDam$", nm) or near_.fillna("").str.lower().eq(nm.lower()).any():
            continue
        lk.iloc[i, lk.columns.get_loc("name")] = nm
        lk.iloc[i, lk.columns.get_loc("name_src")] = "OpenStreetMap"
        n_osm.append(nm)
print(f"named from OpenStreetMap where NHD has no name: {len(n_osm)}" + (f" ({', '.join(n_osm[:12])}{', …' if len(n_osm) > 12 else ''})" if n_osm else ""))

# final size, shore and elevation: the lidar's where it measured the lake
lk["ha"] = (lk.area / 1e4).round(2)
lk["in_area"] = (lk.geometry.intersection(U).area / lk.area).round(3)
lk["shore_km"] = (lk.geometry.boundary.length / 1000).round(2)
lk["islands"] = [sum(len(p.interiors) for p in getattr(g, "geoms", [g])) for g in lk.geometry]
lk["elev_src"] = np.where(lk.lidar_kind.eq("flattened"), "lidar water level", np.where(lk.water_level_m.notna(), "lidar water surface (not flattened)", np.where(lk.elev_m.notna(), "10 m DEM", None)))
lk["elev_m"] = lk.water_level_m.round(1).where(lk.water_level_m.notna(), lk.elev_m)
# a lake the lidar caught drawn down or drained: its normal level, not that day's (Lynchburg Reservoir lay 14.8 ft low
# in the 2017-18 flight; Cave Mountain Lake's bed was dry)
_lo = lk.normal_m.notna()
lk.loc[_lo, "elev_m"] = lk.normal_m[_lo].round(1)
lk.loc[_lo, "elev_src"] = lk.normal_src[_lo]

# ---- 4. inlets and outlets (NHD HR flowlines are drawn downstream) ----
# An outlet is a stream line that starts at the shore and ends outside the lake; an inlet one that ends at the shore
# and starts outside it. NHD splits streams into short pieces (Holly Lake's outlet starts with a 13 m one), so the test
# is "ends outside the lake", not "leaves the shore zone". An unnamed outlet is followed down to the first named water.
fla = pd.concat([gpd.read_file(f"{raw_dir(r)}/nhd_flowlines.gpkg") for r in REGIONS
                 if os.path.exists(f"{raw_dir(r)}/nhd_flowlines.gpkg")], ignore_index=True)
fla = gpd.GeoDataFrame(fla, crs=CRS).explode(index_parts=False)
fla = fla[fla.geom_type == "LineString"].reset_index(drop=True)
fl = fla[fla.ftype.isin([460, 336])]                  # streams and canals; 558 = paths through the lakes themselves
sta = shapely.get_point(fla.geometry.values, 0)
ena = shapely.get_point(fla.geometry.values, -1)
st_tree = shapely.STRtree(sta)


def drains_to(k):
    """The first named NHD water downstream of line k (through ponds), or None."""
    seen = {k}
    for _ in range(80):
        nm = fla.gnis_name.iat[k]
        if isinstance(nm, str):
            return nm
        nxt = [c for c in st_tree.query(shapely.buffer(ena[k], 2)) if c not in seen]
        if not nxt:
            return None
        k = nxt[0]
        seen.add(k)
    return None


shore = gpd.GeoSeries([a.union(b).buffer(20) for a, b in zip(lk.geometry, nhd_g)], crs=CRS)   # NHD's lines end on NHD's shore
body = gpd.GeoSeries([a.union(b).buffer(2) for a, b in zip(lk.geometry, nhd_g)], crs=CRS)
ins, outs, oname, iname, opt = [], [], [], [], []
for i in range(len(lk)):
    c = [k for k in fla.sindex.query(shore.iat[i], predicate="intersects") if k in fl.index]
    s_sh = [shore.iat[i].contains(sta[k]) for k in c]
    e_sh = [shore.iat[i].contains(ena[k]) for k in c]
    s_in = [body.iat[i].contains(sta[k]) for k in c]
    e_in = [body.iat[i].contains(ena[k]) for k in c]
    o = [k for k, a, b in zip(c, s_sh, e_in) if a and not b]
    n_ = [k for k, a, b in zip(c, e_sh, s_in) if a and not b]
    o = [k for k in o if k not in n_ or not body.iat[i].contains(ena[k])]
    outs.append(len(o)); ins.append(len(n_))
    named = sorted({fla.gnis_name.iat[k] for k in o if isinstance(fla.gnis_name.iat[k], str)})
    if not named and o:
        to = drains_to(max(o, key=lambda k: fla.geometry.iat[k].length))
        named = [f"unnamed, flows to {to}"] if to else []
    oname.append(", ".join(named) or None)
    iname.append(", ".join(sorted({fla.gnis_name.iat[k] for k in n_ if isinstance(fla.gnis_name.iat[k], str)})) or None)
    big = max(o, key=lambda k: fla.geometry.iat[k].length) if o else None
    opt.append(sta[big] if big is not None else None)
lk["inlets"], lk["outlets"], lk["outlet_name"], lk["inlet_names"] = ins, outs, oname, iname
lk["connection"] = np.select([(lk.inlets > 0) & (lk.outlets > 0), lk.outlets > 0, lk.inlets > 0],
                             ["inlet and outlet", "outlet only", "inlet only"], "no mapped inlet or outlet (NHD)")
print("connection:", lk.connection.value_counts().to_dict())

# ---- 5. drainage and fork (05c) at the outlet ----
dr = pd.concat([gpd.read_file(f"{out_dir(r)}/drainages.gpkg") for r in REGIONS if os.path.exists(f"{out_dir(r)}/drainages.gpkg")],
               ignore_index=True)
dr = gpd.GeoDataFrame(dr, crs=CRS)
at = gpd.GeoSeries([p if p is not None else g.representative_point() for p, g in zip(opt, lk.geometry)], crs=CRS)
j = gpd.sjoin(gpd.GeoDataFrame(geometry=at), dr[["drainage", "fork", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
lk["drainage"], lk["fork"] = j.drainage.values, j.fork.values


# ---- 6. dated fish records at the lake (GBIF: agency surveys, iNaturalist, USGS NAS, museums) ----
def gbif_salmonids():
    """Every georeferenced trout / salmon / char / grayling / whitefish record in the area (GBIF family Salmonidae),
    cached a week."""
    p = f"{CACHE}/gbif_salmonidae.csv"
    if os.path.exists(p) and os.environ.get("REFRESH") != "1" and time.time() - os.path.getmtime(p) < 7 * 86400:
        return pd.read_csv(p)
    w, s, e, n = boxes.to_crs(4326).total_bounds
    fam = requests.get("https://api.gbif.org/v1/species/match", params=dict(name="Salmonidae", rank="FAMILY",
                       kingdom="Animalia"), headers=UA, timeout=60).json()["usageKey"]
    recs, off = [], 0
    while True:
        r = requests.get("https://api.gbif.org/v1/occurrence/search", headers=UA, timeout=120, params=dict(
            familyKey=fam, decimalLatitude=f"{s - 0.02},{n + 0.02}", decimalLongitude=f"{w - 0.02},{e + 0.02}",
            hasCoordinate="true", hasGeospatialIssue="false", limit=300, offset=off)).json()
        recs += r["results"]
        off += 300
        if r.get("endOfRecords") or off >= 100000:
            break
    names = {}
    for k in {x["datasetKey"] for x in recs}:
        names[k] = requests.get(f"https://api.gbif.org/v1/dataset/{k}", headers=UA, timeout=60).json().get("title", k)
    t = pd.DataFrame([dict(gbif=x.get("key"), dataset=names[x["datasetKey"]], species=x.get("species"),
                           common=x.get("vernacularName"), year=x.get("year"), date=(x.get("eventDate") or "")[:10],
                           lat=x.get("decimalLatitude"), lon=x.get("decimalLongitude"),
                           uncert=x.get("coordinateUncertaintyInMeters"), status=x.get("occurrenceStatus"),
                           basis=x.get("basisOfRecord"), locality=x.get("locality") or x.get("waterBody"),
                           withheld=x.get("informationWithheld")) for x in recs])
    t.to_csv(p + ".tmp", index=False)
    os.replace(p + ".tmp", p)
    return t

SHORT = {"Multistate Aquatic Resources Information System - MARIS - Fish": "MARIS (state fish survey)",
         "iNaturalist Research-grade Observations": "iNaturalist", "USGS Nonindigenous Aquatic Species database": "USGS NAS"}
ev = gbif_salmonids()
ev = ev[(ev.status.fillna("PRESENT") != "ABSENT") & ev.species.notna()]
ev = ev[ev.uncert.isna() | (ev.uncert <= EV_MAX_UNCERT_M)]
ev = ev[~ev.withheld.fillna("").str.contains("obscured|withheld|uncertainty increased", case=False)]
ev = gpd.GeoDataFrame(ev, geometry=gpd.points_from_xy(ev.lon, ev.lat), crs=4326).to_crs(CRS)
li, ei = lk.sindex.query(ev.geometry, predicate="dwithin", distance=EV_BUFFER_M)
recs = {}
for e_, l_ in zip(li, ei):
    r = ev.iloc[e_]
    recs.setdefault(l_, []).append(dict(species=r.species, year=None if pd.isna(r.year) else int(r.year),
                                        source=SHORT.get(r.dataset, r.dataset), gbif=int(r.gbif)))
lk["records"] = [json.dumps(sorted(recs.get(i, []), key=lambda x: (x["year"] or 0), reverse=True)) for i in range(len(lk))]
lk["n_records"] = [len(recs.get(i, [])) for i in range(len(lk))]
print(f"fish records (GBIF) usable at lake level: {len(ev)} of the area's records; at {int((lk.n_records > 0).sum())} lakes: "
      + ", ".join(f"{k} {v}" for k, v in pd.Series([x['source'] for v in recs.values() for x in v]).value_counts().items()))

# cross-check: records of fish at a lake the agency lists as having no game fish, and the reverse
GAME = r"Trout|Cutthroat|Char|Grayling|Salmon|Kokanee|Splake|Whitefish"
SCI = lakedata.SALMONIDS
conf = []
for i, r in lk.iterrows():
    rr = json.loads(r.records)
    if r.game_fish == "None" and rr:
        conf.append(f"{r['name'] or 'unnamed'}: agency lists no game fish; records of "
                    + ", ".join(sorted({f"{SCI.get(x['species'], x['species'])} ({x['source']} {x['year']})" for x in rr})))
lk["conflict"] = None
for i, r in lk.iterrows():
    rr = json.loads(r.records)
    if r.game_fish == "None" and rr:
        lk.loc[i, "conflict"] = "Game & Fish lists no game fish, but " + "; ".join(
            sorted({f"{SCI.get(x['species'], x['species'])} recorded {x['year'] or ''} ({x['source']})" for x in rr}))
print(f"lakes where the agency's 'no game fish' meets a fish record: {len(conf)}" + ("".join(f"\n  {c}" for c in conf) if conf else ""))
# species recorded at the lake since 2000 that the agency's list doesn't have (a stocking change, a mix-up, or a fish
# that moved in): shown beside the list, not merged into it
KEYWORD = {"Oncorhynchus clarkii": "Cutthroat", "Oncorhynchus virginalis": "Cutthroat", "Oncorhynchus kisutch": "Coho", "Salvelinus fontinalis": "Brook Trout", "Salvelinus namaycush": "Lake Trout",
           "Salmo trutta": "Brown Trout", "Oncorhynchus mykiss": "Rainbow Trout", "Thymallus arcticus": "Grayling",
           "Prosopium williamsoni": "Whitefish", "Oncorhynchus nerka": "Kokanee", "Oncorhynchus aguabonita": "Golden"}
lk["also_recorded"] = None
for i, r in lk.iterrows():
    if not isinstance(r.game_fish, str):
        continue
    extra = {}
    for x in json.loads(r.records):
        kw = KEYWORD.get(x["species"])
        if kw and (x["year"] or 0) >= 2000 and kw.lower() not in r.game_fish.lower():
            extra.setdefault(SCI.get(x["species"], x["species"]), []).append(f"{x['source']} {x['year']}")
    if extra:
        lk.loc[i, "also_recorded"] = "; ".join(f"{k} ({', '.join(sorted(set(v))[-2:])})" for k, v in sorted(extra.items()))
print("species recorded since 2000 beyond the agency's list: "
      + "; ".join(f"{n}: {e}" for n, e in zip(lk.name, lk.also_recorded) if isinstance(e, str)))

# ---- 6b. measured depths and lake fish surveys typed in from their reports (lakedata.py) ----
# Each record is matched to the lake it lies in or within 300 m of, the one with its name first. The best measurement
# becomes the lake's depth; the rest are listed, and one that disagrees by more than 20% (and 2 m) is called out.
import lakedata


def locate(at):
    x, y = at
    return gpd.GeoSeries([shapely.Point(x, y)], crs=4326 if abs(x) <= 180 else 26912).to_crs(CRS).iloc[0]


def match(name, at, g=None):
    """The lake a record is about: one of its name within 1.5 km (the 2002 survey took its coordinates from a consumer
    topo program: Timberline Lake's lie 783 m from NHD's lake), else the nearest lake within 150 m."""
    g = lk if g is None else g
    p = locate(at)
    near = [i for i in g.sindex.query(p.buffer(1500), predicate="intersects")]
    if not near:
        return None
    named = [i for i in near if key(name) in (key(g.name.iat[i]) if "name" in g else "", key(g.gnis_name.iat[i]),
                                              key(g.agency_name.iat[i]) if "agency_name" in g else "")]
    if named:
        return min(named, key=lambda i: g.geometry.iat[i].distance(p))
    i = min(near, key=lambda i: g.geometry.iat[i].distance(p))
    return i if g.geometry.iat[i].distance(p) <= 150 else None


lk["survey"] = None
meas, miss = {}, []
# EPA National Lakes Assessment soundings (lakesources.py), matched to the lake they were taken in; on a reservoir
# the index site is mid-lake, a lower bound
import lakesources
_nla = lakesources.nla_depths(tuple(boxes.buffer(3000).to_crs(4326).total_bounds)).to_crs(CRS)
nla_recs = []
for r in _nla.itertuples():
    j = [i for i in lk.sindex.query(r.geometry.buffer(100), predicate="intersects")]
    if not j:
        continue
    i = min(j, key=lambda i: lk.geometry.iat[i].distance(r.geometry))
    p4 = gpd.GeoSeries([r.geometry], crs=CRS).to_crs(4326).iloc[0]
    nla_recs.append(dict(lake=lk.name.iat[i] or "", max_m=float(r.depth_m), mean_m=None, rank=2, date=r.date,
                         method=r.method, src=f"EPA National Lakes Assessment {r.cycle} (sonar)", at=(p4.x, p4.y),
                         ref=lakesources.NLA[r.cycle][0], reservoir_index=lk.ftype.iat[i] == "reservoir", _i=i))
for d in lakedata.DEPTHS.get(AREA, []) + nla_recs:
    i = d["_i"] if "_i" in d else match(d["lake"], d["at"])
    (miss.append(d["lake"]) if i is None else meas.setdefault(i, []).append(d))
for i, ds in meas.items():
    full = [d for d in ds if not d.get("reservoir_index")]
    best = min(full, key=lambda d: (d["rank"], -d["max_m"])) if full else None   # same rank: the deepest sounding
    agency = lk.depth_max_m.iat[i] if isinstance(lk.depth_src.iat[i], str) and lk.depth_src.iat[i].startswith("Wyoming") else np.nan
    notes = []
    if best is not None:
        lk.loc[i, ["depth_max_m", "depth_src"]] = [best["max_m"], f"{best['src']}, {best['date']}"]
        if best.get("note"):
            notes.append(best["note"])
        if best.get("mean_m") is not None:
            lk.loc[i, "depth_mean_m"] = best["mean_m"]
        elif pd.notna(lk.depth_mean_m.iat[i]):
            notes.append(f"mean {ft(lk.depth_mean_m.iat[i])} from the Wyoming Game & Fish fishing guide")
        others = [(d["max_m"], f"{d['src']}, {d['date']}") for d in ds if d is not best and not d.get("reservoir_index")]
        notes += [f"at least {ft(d['max_m'])} at EPA's index site ({d['date']})" for d in ds if d.get("reservoir_index")]
        if np.isfinite(agency):
            others.append((agency, "Wyoming Game & Fish fishing guide"))
        for v, src in others:
            off = abs(v - best["max_m"]) > 2 and abs(v - best["max_m"]) / max(v, best["max_m"]) > 0.2
            notes.append(("conflicts: " if off else "also ") + f"{ft(v)} by {src}")
    else:                                          # only an EPA index site on a reservoir: a lower bound
        for d in ds:
            notes.append(f"at least {ft(d['max_m'])} at EPA's index site ({d['date']})")
    lk.loc[i, "depth_note"] = "; ".join(notes) or None
for sv in lakedata.SURVEYS.get(AREA, []):
    i = match(sv["lake"], sv["at"])
    if i is None:
        miss.append(sv["lake"] + " (survey)")
        continue
    lk.loc[i, "survey"] = f"Gill-net survey {sv['date']} ({sv['src'].replace(' gill nets', '')}): " + (sv["fish"] or "no fish caught")
    gf = lk.game_fish.iat[i]
    if sv["fish"] is None and isinstance(gf, str) and gf != "None":
        lk.loc[i, "conflict"] = "; ".join(x for x in (lk.conflict.iat[i], f"the {sv['date'][:4]} gill-net survey caught no fish; "
                                                     f"Game & Fish now lists {gf}") if isinstance(x, str))
    elif sv["fish"] and gf == "None":
        lk.loc[i, "conflict"] = "; ".join(x for x in (lk.conflict.iat[i], f"Game & Fish lists no game fish; the {sv['date'][:4]} "
                                                     f"gill-net survey caught {sv['fish']}") if isinstance(x, str))
print(f"measured depths matched to {len(meas)} lakes, surveys to {lk.survey.notna().sum()}; not in the area or not "
      f"found: {', '.join(sorted(set(miss))) or 'none'}")
for i in meas:
    print(f"  {lk.name.iat[i]}: {lk.depth_max_m.iat[i]:g} m ({lk.depth_src.iat[i]})" + (f"; {lk.depth_note.iat[i]}" if isinstance(lk.depth_note.iat[i], str) else ""))

# ---- 6c. the state's lake access, rules and designations (lakesources.py): an outline that covers a third of a lake
# (or of itself) belongs to it, a point within 150 m of a lake's shore to the nearest lake ----
ex = lakesources.extras(AREA, tuple(boxes.buffer(3000).to_crs(4326).total_bounds))
for c in ("access", "rules", "designation", "links"):
    lk[c] = None
if len(ex):
    ex = ex.to_crs(CRS)
    got_ = {}
    for r in ex.itertuples():
        g = r.geometry
        if g is None or g.is_empty:
            continue
        if g.geom_type in ("Point", "MultiPoint"):
            j = [i for i in lk.sindex.query(g.buffer(150), predicate="intersects")]
            hit = [min(j, key=lambda i: lk.geometry.iat[i].distance(g))] if j else []
        else:
            g = shapely.make_valid(g)
            hit = [i for i in lk.sindex.query(g, predicate="intersects")
                   if lk.geometry.iat[i].intersection(g).area >= 0.33 * min(lk.geometry.iat[i].area, g.area)]
        for i in hit:
            got_.setdefault((i, r.kind), set()).add(r.text)
            if isinstance(r.url, str) and r.url.startswith("http"):
                got_.setdefault((i, "links"), set()).add(r.url)
    for (i, k), v in got_.items():
        lk.loc[i, k] = "; ".join(sorted(v))
    print("state lake facts:", {k: int(lk[k].notna().sum()) for k in ("access", "rules", "designation")})

# ---- 7. land: the most specific PAD-US unit at the lake (a park, refuge, wilderness or forest; fishing rules and
# access go with it), and its public access code; none = private or unlisted land ----
from geomatch import esri
# fetched over the lakes' full extent: a few reach past the study area (Jackson Lake, Palisades Reservoir)
_ext = gpd.GeoSeries([box(*boxes.total_bounds), box(*lk.total_bounds)], crs=CRS).to_crs(4326).total_bounds
pad = esri("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS_Public_Access/FeatureServer/0",
           tuple(_ext), "Unit_Nm,MngNm_Desc,Pub_Access,GIS_Acres")
lk["land"], lk["land_access"] = None, None
if len(pad):
    pad = gpd.GeoDataFrame(pad, crs=4326).to_crs(CRS)
    pad = pad[pad.geometry.notna() & ~pad.geometry.is_empty]
    pad["geometry"] = shapely.make_valid(pad.geometry.values)
    # a point of the lake inside the study area (a lake can reach past it)
    rp = [(g.intersection(U) if not g.intersection(U).is_empty else g).representative_point() for g in lk.geometry]
    for i, p_ in enumerate(rp):
        hit = pad.iloc[pad.sindex.query(p_, predicate="intersects")]
        shore = ""
        if not len(hit):
            # PAD-US leaves out the water of some lakes (Jackson Lake, with a strip of shore up to ~300 m wide): then
            # the unit a line around the lake mostly lies in (a small pond needs most of that line in one unit)
            g_ = lk.geometry.iat[i]
            ring = g_.buffer(min(300, max(30, 0.3 * g_.area ** 0.5))).boundary   # 30 m out for a pond, 300 m for a big lake
            pts = [ring.interpolate(f, normalized=True) for f in np.linspace(0, 1, 48, endpoint=False)]
            units = [pad.iloc[j] for q in pts for j in pad.sindex.query(q, predicate="intersects")[:1]]
            if units and len(units) >= (0.3 if g_.area >= 50e4 else 0.6) * len(pts):
                top = pd.Series([u_.Unit_Nm for u_ in units]).value_counts().index[0]
                hit, shore = pd.DataFrame([u_ for u_ in units if u_.Unit_Nm == top]), " (its shore; PAD-US leaves out the water)"
        if len(hit):
            u = hit.sort_values("GIS_Acres").iloc[0]
            fed = re.search(r"(?i)wilderness|national forest|national park|parkway|national recreation|roadless|"
                            r"wild and scenic|national elk refuge|wildlife refuge", str(u.Unit_Nm))
            acc = {"OA": "open", "RA": "restricted", "XA": "closed", "UK": "unknown"}.get(u.Pub_Access, u.Pub_Access)
            # federal forests, parks and BLM land: "restricted" is about rules on use (and the Wyoming Range Withdrawal
            # Area is about mineral leasing), not entry
            fed = fed or u.MngNm_Desc in ("Forest Service", "National Park Service", "Bureau of Land Management")
            # PAD-US's "Unknown" is the manager it doesn't know (most Connecticut holdings): the unit's name says enough
            known = isinstance(u.MngNm_Desc, str) and u.MngNm_Desc != "Unknown"
            unit = u.Unit_Nm if isinstance(u.Unit_Nm, str) and u.Unit_Nm != "Unknown" else None
            label = f"{u.MngNm_Desc}: {unit}" if known and unit else unit or (u.MngNm_Desc if known else "PAD-US land, manager unknown")
            lk.loc[i, ["land", "land_access"]] = [label + shore,
                                                  acc if acc == "closed" or (acc == "restricted" and not fed) else None]
print("land (PAD-US):", lk.land.fillna("private or unlisted").str.replace(r":.*", "", regex=True).value_counts().to_dict(),
      "| access flagged:", lk.land_access.value_counts().to_dict())

# ---- write ----
lk = lk.sort_values("ha", ascending=False).reset_index(drop=True)
# a stable key, so a rerun that changes outlines or sizes never hands one lake's approach (hike_lakes.csv) to another
import hashlib
src_key = [f"nhd:{n}" if isinstance(n, str) else f"wgfd:{a}" if isinstance(a, str) else f"osm:{int(o)}"
           for n, a, o in zip(lk.nhd_id, lk.agency_id, lk.get("osm_id", pd.Series(np.nan, index=lk.index)).fillna(0))]
lk["lid"] = ["L" + hashlib.md5(k.encode()).hexdigest()[:8] for k in src_key]
assert not lk.lid.duplicated().any(), "two lakes with one id"
cols = ["lid", "name", "name_src", "gnis_name", "agency_name", "nhd_id", "osm_id", "nhd_ids", "reachcodes", "src_outline",
        "outline_note", "ftype", "nhd_type", "regulated", "intermittent", "ha", "nhd_ha", "lidar_ha", "lidar_iou", "lidar_kind", "shore_km",
        "islands", "in_area", "elev_m", "elev_src", "water_level_m", "nhd_elev_m", "agency_elev_m", "lidar_survey",
        "lidar_dates", "lidar_ql", "lidar_share", "level_share", "dem_cells", "water_note", "agency", "agency_id",
        "lake_type", "game_fish", "common_fish", "private_shore", "regs_area", "depth_max_m", "depth_mean_m",
        "depth_src", "depth_note", "inlets", "inlet_names", "outlets", "outlet_name", "connection", "drainage", "fork",
        "land", "land_access", "access", "rules", "designation", "links", "n_records", "records", "also_recorded", "survey", "conflict", "match", "geometry"]
for c in cols:
    if c not in lk:
        lk[c] = None
lk = lk[cols]
lk.to_file(OUT + ".tmp", driver="GPKG")
os.replace(OUT + ".tmp", OUT)
print(f"wrote {OUT}: {len(lk)} lakes, {lk.ha.sum():,.0f} ha; agency-listed {lk.agency.notna().sum()} "
      f"(with game fish {(lk.game_fish.notna() & (lk.game_fish != 'None')).sum()}, none {(lk.game_fish == 'None').sum()}); "
      f"surveyed depth {lk.depth_max_m.notna().sum()}")
