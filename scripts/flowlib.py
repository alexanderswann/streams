"""Shared helpers for the flow evidence (05b_flow.py, data/validate_flow.py)."""
import os, json, numpy as np, pandas as pd, geopandas as gpd, pyogrio
from shapely.geometry import box
import shapely
from config import REGIONS, CRS, SHARED, SHARED_DERIVED, NATIONAL, AREA, has, derived_dir

FLOW = f"{SHARED}/flow"
MIN_RESERVOIR_KM2 = 0.08     # waterbodies smaller than 8 ha (debris basins, ponds) don't control a creek's base flow


_MINOR = {}
def minor_arms(v2):
    """COMIDs of the side arms of split channels. Where a creek splits and rejoins, NHDPlus gives both arms the whole
    drainage upstream (totdasqkm) but sends nearly all the flow down the main arm: beside Guys Run's 18.65 km2 and
    13 cfs runs an unnamed arm with 18.51 km2 and 0.14 cfs. Matched by drainage area and distance alone, a reach
    7 m from the side arm took its trickle and was rated mostly dry between two reaches rated year-round (the same
    on five reaches of the Maury itself, 0.0 to 0.08 cfs where it carries 90 to 150).
    A side arm: where the table has NHDPlus's own flags, every line of a split's minor path and the lines it runs
    into that carry its drainage but not its flow (below); and, from the table alone, one of two lines into the
    same downstream line whose drainage areas agree within 3 %, carrying under half the other's flow; and the lines
    above it on the same arm (running into a side arm with at least 90 % of its drainage, and under a quarter of
    the main arm's flow per km2). Flow: NHDPlus's mean annual (qe_ma), or the Natural Flows mean where the table
    has no qe_ma (California). Pairs with no flow figure for both are left alone."""
    key = (id(v2), len(v2))
    if key in _MINOR:
        return _MINOR[key]
    d = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath", "Connector"])]
    d = pd.DataFrame(d.drop(columns="geometry", errors="ignore"))
    if "qe_ma" in d:
        q = d.set_index("comid").qe_ma.astype(float)
    else:
        nfp = f"{FLOW}/natural_flows.csv"
        if os.path.exists(nfp):
            nf_ = pd.read_csv(nfp, usecols=["comid", "variable", "statistic", "value"])
            q = nf_[(nf_.variable == "estimated") & (nf_.statistic == "mean")].groupby("comid").value.mean()
        else:
            q = pd.Series(dtype=float)
    d = d[d.dnhydroseq.notna() & (d.dnhydroseq != 0) & (d.totdasqkm > 0.5)].assign(q=lambda t: t.comid.map(q))
    minor, unit = set(), {}                              # side arm -> the main arm's flow per km2
    if "divergence" in d and d.divergence.notna().any() and not has("tnc_flows"):
        # NHDPlus marks split channels itself (02b downloads the flags since 2026-11-19; an older cached table has
        # none, and then only the rules below apply). Only where the flow is NHDPlus's own (EROM), which splits the
        # water at a divergence: California's Natural Flows model gives a minor path the natural flow of its whole
        # drainage (Day Creek's line: 0.63 cfs there, 0.02 in EROM), so in LA these lines are no trap and leaving
        # them out only moved reaches onto other lines (tried 2026-11-19: 68 LA scores moved, Bear Creek's 100 -> 38).
        # Divergence 2 is the first line of a split's minor path and
        # streamcalc 0 the rest of it, until another creek joins. On the Wissahickon at Fort Washington the minor
        # path carries 0.01 cfs on 54 km2; beside the Brandywine at Chadds Ford one carries 0.16 cfs on 3.6 km2,
        # and two reaches matched to them read as near-dry between reaches that flow. The line such a path runs
        # into, where another creek joins it, has the path's whole drainage in its own (Prophecy Creek's last
        # 0.3 km: 60 km2 and 3.9 cfs, while the Wissahickon beside it has 56 km2 and 34 cfs): it counts as a side
        # arm too, and the lines below it, while their flow per km2 stays under a quarter of the split's.
        path = d[(d.divergence == 2) | (d.streamcalc == 0)]
        minor.update(path.comid.astype(int))
        split = d[d.dnminorhyd.fillna(0) > 0]
        split_unit = dict(zip(split.dnminorhyd.astype(float), split.q / split.totdasqkm))
        on_path = set(path.hydroseq.astype(float))
        u_ = {h: split_unit.get(h) for h in on_path}
        for _ in range(50):                              # down the path: the split's flow per km2 goes with it
            more = {float(r.dnhydroseq): u_[float(r.hydroseq)] for r in path.itertuples()
                    if u_.get(float(r.hydroseq)) is not None and float(r.dnhydroseq) in on_path
                    and u_.get(float(r.dnhydroseq)) is None}
            if not more:
                break
            u_.update(more)
        by_hs = d.drop_duplicates("hydroseq").set_index("hydroseq")
        front = [(float(r.dnhydroseq), u_.get(float(r.hydroseq))) for r in path.itertuples()
                 if float(r.dnhydroseq) not in on_path]
        for _ in range(50):
            nxt_ = []
            for h, u in front:
                if u is None or h not in by_hs.index:
                    continue
                r = by_hs.loc[h]
                if int(r.comid) not in minor and pd.notna(r.q) and r.q / r.totdasqkm < 0.25 * u:
                    minor.add(int(r.comid))
                    nxt_.append((float(r.dnhydroseq), u))
            if not nxt_:
                break
            front = nxt_
    for _, g in d.groupby("dnhydroseq"):
        if len(g) < 2:
            continue
        g = g.sort_values("totdasqkm", ascending=False)
        top = g.iloc[0]
        for _, r in g.iloc[1:].iterrows():
            if r.totdasqkm >= 0.97 * top.totdasqkm and pd.notna(r.q) and pd.notna(top.q):
                lo_, hi_ = (r, top) if r.q < top.q else (top, r)
                if lo_.q < 0.5 * hi_.q:
                    minor.add(int(lo_.comid))
                    unit[float(lo_.hydroseq)] = hi_.q / hi_.totdasqkm
    da = d.drop_duplicates("hydroseq").set_index("hydroseq").totdasqkm
    for _ in range(50):                                  # up each side arm: the same drainage, still next to no flow
        add = d[d.dnhydroseq.isin(list(unit)) & ~d.comid.isin(minor) & d.q.notna()]
        add = add[(add.q / add.totdasqkm < 0.25 * add.dnhydroseq.map(unit))
                  & (add.totdasqkm >= 0.9 * add.dnhydroseq.map(da))]
        if not len(add):
            break
        for r in add.itertuples():
            minor.add(int(r.comid))
            unit[float(r.hydroseq)] = unit[float(r.dnhydroseq)]
    _MINOR[key] = minor
    return minor


def match_points(points, areas, v2, max_dist=150, lo=0.3, hi=1.6):
    """COMID for each point: the nearest NHDPlus V2 flowline within max_dist whose total drainage area agrees
    with the point's (ratio point/flowline in [lo, hi]). Stops a small tributary grabbing the main stem beside it.
    The side arms of split channels are left out (minor_arms): they carry the main arm's drainage area but not its
    flow. A point with unknown area takes the nearest flowline. Returns a float Series (NaN = no match)."""
    pts = gpd.GeoDataFrame({"a": np.asarray(areas, float)}, geometry=list(points), crs=CRS)
    pts["pid"] = np.arange(len(pts))
    lines = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath", "Connector"])][["comid", "totdasqkm", "geometry"]]
    lines = lines[~lines.comid.isin(minor_arms(v2))]
    j = gpd.sjoin(pts.assign(geometry=pts.buffer(max_dist)), lines, predicate="intersects")
    if j.empty:
        return pd.Series(np.nan, index=getattr(points, "index", None))
    geom = lines.geometry.reindex(j.index_right).values
    j["dist"] = gpd.GeoSeries(pts.geometry.reindex(j.index).values, crs=CRS).distance(gpd.GeoSeries(geom, crs=CRS)).values
    ratio = j.a / j.totdasqkm.replace(0, np.nan)
    ok = j.a.isna() | ratio.between(lo, hi)
    j = j[ok].assign(miss=np.abs(np.log(ratio[ok].fillna(1.0))))
    # prefer close area agreement, then distance; a tie (two lines at the same distance: the point is nearest to the
    # node they share) goes to the closer drainage, then the lower comid. The sort was unstable before (2026-11-20), so
    # a tie went whichever way the other points' values happened to leave it: an unrelated change elsewhere could flip
    # a reach between the line above a lake and the one through it (Stevenson Brook and the Little River at Waterbury
    # Reservoir), and the same points in another order matched differently (4 of 2,500 in one box)
    j["rank"] = j.miss.round(1) * 1000 + j.dist
    best = j.sort_values(["rank", "miss", "comid"], kind="stable").drop_duplicates("pid").set_index("pid").comid
    out = best.reindex(np.arange(len(pts))).astype(float)
    out.index = getattr(points, "index", out.index)
    return out


def still_water(hu4, bounds):
    """NHD lakes and reservoirs of at least MIN_RESERVOIR_KM2, and lagoons of any size, in `bounds` (this area's CRS)
    from the given HU4 downloads: the waterbodies 03_hydrology.py ends flow paths at, and crossbox.py carries the
    water past (the same set as reservoirs() plus crossbox's lagoons, read straight from the NHD so it can run
    before the other ranges are downloaded)."""
    W, S, E, N = gpd.GeoSeries([box(*bounds)], crs=CRS).to_crs(4269).total_bounds
    parts = []
    for hu in hu4:
        g = f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg"
        lyr = next(l for l in pyogrio.list_layers(g)[:, 0] if l.lower() == "nhdwaterbody")
        d = gpd.read_file(g, layer=lyr, bbox=(W, S, E, N))
        d.columns = [c.lower() if c != "geometry" else c for c in d.columns]
        parts.append(d.to_crs(CRS))
    wb = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    if not len(wb):
        return wb
    wb = wb[wb.ftype.isin([390, 436]) & ((wb.area >= MIN_RESERVOIR_KM2 * 1e6) | wb.gnis_name.fillna("").str.contains("Lagoon"))]
    wb = wb.drop_duplicates("permanent_identifier")[["gnis_name", "geometry"]]
    return wb.assign(geometry=wb.geometry.force_2d()).reset_index(drop=True)


def reservoirs():
    """NHD waterbodies >= MIN_RESERVOIR_KM2 in the study areas (cached; rebuilt when ranges are added)."""
    os.makedirs(FLOW, exist_ok=True)
    path, meta = f"{FLOW}/reservoirs.gpkg", f"{FLOW}/reservoirs.gpkg.regions.json"
    if os.path.exists(path) and os.path.exists(meta) and set(json.load(open(meta))) == set(REGIONS):
        return gpd.read_file(path)
    area = gpd.GeoSeries([box(*v["bbox"]).buffer(2000) for v in REGIONS.values()], crs=CRS)
    W, S, E, N = area.to_crs(4269).total_bounds
    parts = []
    for hu in sorted({h for v in REGIONS.values() for h in v["hu4"]}):
        g = f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg"
        lyr = next(l for l in pyogrio.list_layers(g)[:, 0] if l.lower() == "nhdwaterbody")
        d = gpd.read_file(g, layer=lyr, bbox=(W, S, E, N))
        d.columns = [c.lower() if c != "geometry" else c for c in d.columns]
        parts.append(d.to_crs(CRS))
    wb = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    wb = wb[wb.ftype.isin([390, 436]) & (wb.area >= MIN_RESERVOIR_KM2 * 1e6) & wb.intersects(area.union_all())]
    wb = wb[~wb.gnis_name.fillna("").str.contains("Lagoon")]
    wb = wb.drop_duplicates("permanent_identifier")[["gnis_name", "ftype", "geometry"]]
    wb["geometry"] = wb.geometry.force_2d()
    wb["gnis_name"] = wb.gnis_name.fillna("unnamed reservoir")
    wb.to_file(path + ".tmp.gpkg", driver="GPKG")
    os.replace(path + ".tmp.gpkg", path)
    json.dump(sorted(REGIONS), open(meta, "w"))
    return wb


# ---- the lake water a reach can lie in ----
# 05b_flow.py reads a reach as lying in a lake ("in:<lake>", class reservoir) when half its length is in the water, and
# 05_score.py cuts the stream links at the same shores, so that a reach is creek or lake and not half of each. The
# water is NHD's lakes of MIN_RESERVOIR_KM2 or more (reservoirs()) and the lakes layer's (05d_lakes.py's lakes.gpkg).
LAKE_PIECE_M = 50.0      # 05_score.py cuts a link at a lake's shore where at least this much of it lies on each side


def lakes_layer():
    """The lakes layer (05d_lakes.py's lakes.gpkg) in this area's CRS, with valid outlines; None where there is none."""
    p = f"{SHARED_DERIVED}/lakes.gpkg"
    if not os.path.exists(p):
        return None
    ll = gpd.read_file(p).to_crs(CRS)
    return ll.assign(geometry=shapely.make_valid(ll.geometry.values))


def layer_counted(ll):
    """The layer's lakes a reach can lie in: 8 ha or more (the whole lake's size: one reaching far past the map is
    stored clipped), level in the lidar ("flattened" or "level, not flattened"; not "little level water", a dry, marsh
    or overgrown bed; not drawn down or drained), not intermittent, and not a lagoon (as reservoirs())."""
    note = ll.water_note.fillna("").astype(str).str.strip().str.lower()
    return ll[ll.lidar_kind.isin(["flattened", "level, not flattened"]) & ~note.str.startswith("little level water")
              & ~note.str.contains("drawn down|drained") & ~ll.intermittent.fillna(False).astype(bool)
              & ~ll["name"].fillna("").str.contains("Lagoon")
              & (ll.ha.fillna(ll.geometry.area / 1e4) >= MIN_RESERVOIR_KM2 * 100)]


def as_drawn(wb, ll):
    """The outlines of NHD's lakes (wb, from reservoirs()) with the shore the lakes layer draws, where it drew that lake
    from the lidar: NHD's outline cut to the lidar's. NHD's outlines come from older photos and topographic sheets, and
    at a natural lake the lidar's shoreline replaces them on the map (05d_lakes.py; a reservoir, a lake caught drawn
    down and one over 600 ha keep NHD's). Read against NHD's, a creek beside a lake whose mapped outline reaches
    further than its water lay "in" it: a 324 m side creek at Lower Slide Lake's head and Emma Matilda Lake's outlet
    creek between its ponds drew as reservoir where the map shows no lake (158 reaches, 84 km, over the 12 maps,
    2026-11-21). A layer lake is the NHD lake's own where their overlap covers half of the smaller of the two.
    Returns a GeoSeries on wb's index."""
    geom = np.array(wb.geometry.values, dtype=object)
    if ll is not None and len(ll) and len(wb):
        lid = ll.geometry.values[ll.src_outline.fillna("").astype(str).str.startswith("lidar").values]
        if len(lid):
            wi, li = shapely.STRtree(lid).query(geom, predicate="intersects")
            for i in np.unique(wi):
                own = [L for L in lid[li[wi == i]] if geom[i].intersection(L).area >= 0.5 * min(geom[i].area, L.area)]
                if own:
                    parts = shapely.get_parts(shapely.intersection(geom[i], shapely.union_all(own)))
                    geom[i] = shapely.union_all([q for q in parts if q.geom_type == "Polygon"])
    return gpd.GeoSeries(geom, index=wb.index, crs=wb.crs)


def wet_lakes(wb, region):
    """The index labels of the lakes in wb that hold water in this box: 03b_stitch.py ends the paths at the outlet of
    every lake with 2+ ha of its outline at one level in the DEM (a pit, 254 in flowdir.tif); one without (a marsh or
    meadow NHD maps as a pond, a dry basin) has none."""
    import rasterio
    with rasterio.open(f"{derived_dir(region)}/flowdir.tif") as src:
        rr, cc = np.nonzero(src.read(1) == 254)
        xs, ys = src.transform * (cc + 0.5, rr + 0.5)
    if not len(wb) or not len(rr):
        return set()
    pits = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs, ys), crs=CRS)
    return set(gpd.sjoin(pits, wb[["geometry"]], predicate="within").index_right.tolist())


def lake_water(region):
    """The outlines 05_score.py cuts this box's stream links at: every lake 05b_flow.py can flag a reach in. NHD's lakes
    (reservoirs()) with the shore the map draws (as_drawn), and the lakes layer's lakes a reach can lie in
    (layer_counted). NHD's lakes all count, not only those holding level water in this box's lidar (wet_lakes): 05b
    also makes a reach "reservoir" that lies half in a lake without one and has no model line of its own, so with the
    cut at wet lakes only, links into a reservoir caught drawn down stayed half creek: 880 m of the West Fork San
    Gabriel and 1.3 km of Devils Canyon above Cogswell Reservoir read as lake (47 such links, 16 km, on the 12 maps,
    2026-11-21). An array of polygons in this area's CRS. `region` is kept for the callers; nothing is read per box."""
    wb = reservoirs()
    wb = wb.assign(geometry=shapely.make_valid(wb.geometry.values))
    ll = lakes_layer()
    out = list(as_drawn(wb, ll).values)
    if ll is not None:
        out += list(layer_counted(ll).geometry.values)
    return np.array([g for g in out if g is not None and not g.is_empty], dtype=object)


def shore_cuts(inside, seglen, min_m=LAKE_PIECE_M):
    """The vertices at which a line is cut at lake shores. inside: for each of its segments, whether it lies in the
    water; seglen: their lengths. Runs of segments in or out of the water shorter than min_m join their neighbours,
    the shortest first (a line clipping a point or a cove, a sliver of shore inside the outline); the line is cut
    between the runs left. Returns vertex numbers (a cut at vertex k ends one piece and starts the next there)."""
    b = (np.flatnonzero(np.diff(np.asarray(inside, bool).astype(np.int8))) + 1).tolist()
    runs = [[s, e, float(np.sum(seglen[s:e]))] for s, e in zip([0] + b, b + [len(inside)])]
    while len(runs) > 1:
        k = min(range(len(runs)), key=lambda j: runs[j][2])
        if runs[k][2] >= min_m:
            break
        lo, hi = max(k - 1, 0), min(k + 1, len(runs) - 1)
        runs[lo:hi + 1] = [[runs[lo][0], runs[hi][1], sum(r[2] for r in runs[lo:hi + 1])]]
    return [r[0] for r in runs[1:]]


def cut_at_shores(lines, water, min_m=LAKE_PIECE_M):
    """Each line cut where it crosses the shore of the water (an array of polygons): (pieces, the number of the line
    each piece comes from, whether the piece lies in the water: half its length or more), in order along each line.
    A line the water doesn't touch stays whole."""
    lines = np.asarray(lines, dtype=object)
    pieces, src, wet = [], [], []
    hit = {}
    if len(water):
        li, wi = shapely.STRtree(water).query(lines, predicate="intersects")
        for i, w in zip(li.tolist(), wi.tolist()):
            hit.setdefault(i, []).append(w)
    for i, g in enumerate(lines):
        cuts, inside, seg = [], None, None
        if i in hit and len(g.coords) >= 2:
            xy = np.asarray(g.coords)[:, :2]
            u = shapely.union_all(water[hit[i]])
            inside = shapely.contains(u, shapely.points((xy[:-1] + xy[1:]) / 2))
            seg = np.hypot(*(xy[1:] - xy[:-1]).T)
            if len(inside) >= 2 and inside.any() and not inside.all():
                cuts = shore_cuts(inside, seg, min_m)
        c = list(g.coords)
        for a_, b_ in zip([0] + cuts, cuts + [len(c) - 1]):
            pieces.append(g if not cuts else shapely.LineString(c[a_:b_ + 1]))
            src.append(i)
            wet.append(bool(inside is not None and seg[a_:b_][inside[a_:b_]].sum() >= 0.5 * seg[a_:b_].sum()))
    return pieces, src, wet


def level_paths():
    """NHDPlus V2's main paths for the area's flowlines: comid, hydroseq, dnhydroseq, uphydroseq (the main line above),
    levelpathi (the path the line's river follows), uplevelpat, dnlevelpat. From the USGS service 02b_download_flow.py
    reads the flowlines from, for the same boxes (each range's box and 2 km around it). 05c_drainages.py uses it to keep
    a river's trunk on the arm NHDPlus continues it up. Cached in FLOW; fetched again when ranges are added."""
    import requests, time
    path, meta = f"{FLOW}/nhdplus_v2_paths.csv", f"{FLOW}/nhdplus_v2_paths.csv.regions.json"
    if os.path.exists(path) and os.path.exists(meta) and set(json.load(open(meta))) == set(REGIONS):
        return pd.read_csv(path)
    os.makedirs(FLOW, exist_ok=True)
    area = gpd.GeoSeries([box(*v["bbox"]).buffer(2000) for v in REGIONS.values()], crs=CRS)
    rows = []
    for w, s, e, n in area.to_crs(4326).bounds.values:
        for k in range(4):
            try:
                r = requests.get("https://api.water.usgs.gov/geoserver/wmadata/ows", timeout=300, params=dict(
                    service="WFS", version="1.0.0", request="GetFeature", typeName="wmadata:nhdflowline_network",
                    outputFormat="application/json", srsName="EPSG:4326", bbox=f"{w},{s},{e},{n},EPSG:4326",
                    propertyName="comid,levelpathi,uplevelpat,dnlevelpat,uphydroseq,hydroseq,dnhydroseq"),
                    headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
                r.raise_for_status()
                rows += [f["properties"] for f in r.json()["features"]]
                break
            except Exception:
                if k == 3:
                    raise
                time.sleep(10 * (k + 1))
    t = pd.DataFrame(rows).drop_duplicates("comid")
    t.to_csv(path + ".tmp", index=False)
    os.replace(path + ".tmp", path)
    json.dump(sorted(REGIONS), open(meta, "w"))
    return t


def below_dam_comids(v2, share=0.5):
    """{comid: reservoir name} for V2 flowlines inside a reservoir ('in:<name>') or downstream of one while the
    reservoir still controls >= `share` of the drainage area."""
    wb = reservoirs()
    inside = gpd.sjoin(v2[["comid", "totdasqkm", "hydroseq", "geometry"]], wb[["gnis_name", "geometry"]], predicate="intersects")
    # only flowlines mostly inside the water
    inter = inside.geometry.intersection(gpd.GeoSeries(wb.geometry.reindex(inside.index_right).values, index=inside.index, crs=CRS))
    inside = inside[inter.length >= 0.5 * inside.length]
    out = {int(c): f"in:{n}" for c, n in zip(inside.comid, inside.gnis_name)}
    by_seq = v2.drop_duplicates("hydroseq").set_index("hydroseq")
    # One lake at a time, not one name at a time: the 60 lakes NHD doesn't name all carry "unnamed reservoir", and
    # grouped by name only the biggest of them was followed downstream (the basins on Arroyo Seco, East Twin Creek
    # and Eaton Wash weren't). Named lakes go first, in the order they always did, so their claims stay the same.
    for (name, _), grp in inside.groupby(["gnis_name", "index_right"]):
        outlet = grp.sort_values("totdasqkm").iloc[-1]          # the flowline at the dam
        a_dam = max(outlet.totdasqkm, 0.01)
        if a_dam < 3:                                            # off-channel tanks / tiny headwater ponds
            continue
        seq = by_seq.dnhydroseq.get(outlet.hydroseq)
        while seq in by_seq.index:
            row = by_seq.loc[seq]
            if a_dam / max(row.totdasqkm, 0.01) < share:
                break
            out.setdefault(int(row.comid), name)
            seq = row.dnhydroseq
    return out


FLOWING_CFS = 0.1            # dry-season monthly mean that counts as "kept flowing" (calibrated on gauges)


def water_term(ev):
    """Score term (0-1) and label from the flow evidence.
    flow_years = share of recent years the reach held >= FLOWING_CFS through Jul-Oct."""
    fy = ev.flow_years.astype(float)
    water = 0.05 + 0.95 * fy
    cls = pd.cut(fy, [-1, 0.2, 0.5, 0.85, 1.0], labels=["mostly dry", "seasonal", "usually flows", "year-round"]).astype(object)
    res = ev.below_dam.fillna("").str.startswith("in:")
    water = water.where(~res, 0.3)
    cls = np.where(res, "reservoir", cls)
    water = water.where(fy.notna() | res, 0.10)
    cls = np.where(fy.isna() & ~res, "no data", cls)
    return water.round(2), cls


# Diversions with a USGS gauge on the creek just below them, where that gauge shows the creek often dry. The flow
# model is for unimpaired flow, so it can't see the water leave in a canal. The creek is followed down from the
# diversion as below a dam (while the diverted creek is still >= half the drainage), and the gauge's record goes into
# the popups. scoring.py uses it as the water term where it's dry most summers.
# Gauged diversions that leave the creek flowing in 80%+ of summers are not listed: Snow, Falls and Day Creeks,
# the Whitewater River at White Water, San Antonio Creek, and Sespe Creek at Fillmore.
# name -> (lon, lat on the creek just below the diversion, creek name in NHDPlus V2, USGS site of the gauge below)
_DIVERSIONS = {"la": {
    "the Santa Ana River No. 1 diversion dam": ((-117.0156, 34.1614), "Santa Ana River", "11049250"),  # the release
    "the Mill Creek power-canal intakes": ((-116.9380, 34.0904), "Mill Creek", "11054000"),
    "the Mill Creek No. 1 canal": ((-117.0398, 34.0898), "Mill Creek", "11054000"),
    "the Lytle Creek diversions": ((-117.4581, 34.2122), "Lytle Creek", "11062000"),
    "the Plunge Creek diversions": ((-117.1397, 34.1277), "Plunge Creek", "11055500"),
    "the City Creek canal": ((-117.1884, 34.1472), "City Creek", "11055800"),
    "the San Jacinto River canals": ((-116.8339, 33.7381), "San Jacinto River", "11069500"),
}}
DIVERSIONS = _DIVERSIONS.get(AREA, {})      # other areas: none listed yet


def below_diversion_comids(v2, share=0.5):
    """DataFrame by COMID: below_div (the DIVERSIONS name above it), div_growth (the flowline's drainage over the
    drainage at the diversion) and div_first (the diversion's own flowline, which can start above it), from the
    diversion down while the diverted creek is >= `share` of the drainage.
    The diversion's flowline is the nearest one within 150 m carrying the creek's name (or none) and 10+ km2."""
    lines = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"]) & (v2.totdasqkm >= 10)]
    by_seq = v2.drop_duplicates("hydroseq").set_index("hydroseq")
    pts = gpd.GeoSeries(gpd.points_from_xy([p[0][0] for p in DIVERSIONS.values()], [p[0][1] for p in DIVERSIONS.values()]),
                        crs=4326).to_crs(CRS)
    rows = []
    for (name, (_, creek, _)), p in zip(DIVERSIONS.items(), pts):
        cand = lines[lines.gnis_name.isna() | lines.gnis_name.eq(creek)]
        d = cand.distance(p)
        if d.empty or d.min() > 150:
            print("no NHDPlus V2 flowline at", name)
            continue
        row = cand.loc[d.idxmin()]
        a0, first = max(row.totdasqkm, 0.01), True
        while True:
            rows.append((int(row.comid), name, row.totdasqkm / a0, first))
            if row.dnhydroseq not in by_seq.index:
                break
            row, first = by_seq.loc[row.dnhydroseq], False
            if a0 / max(row.totdasqkm, 0.01) < share:
                break
    return (pd.DataFrame(rows, columns=["comid", "below_div", "div_growth", "div_first"]).drop_duplicates("comid")
            .astype({"div_first": bool, "div_growth": float}).set_index("comid"))   # typed, so an empty table still filters


def gauge_summers(sites, first_year=2011, min_summers=5):
    """Per USGS site: the share of July-October summers (110+ days of record) whose lowest monthly mean was
    >= FLOWING_CFS, as for the model. Over the summers since first_year if there are min_summers of them (recent =
    True), else over the whole record. From 02b_download_flow.py's gauges_daily.csv.gz.
    -> DataFrame by site: div_share, div_summers, div_years ('2011-2026'), div_recent."""
    dv = pd.read_csv(f"{FLOW}/gauges_daily.csv.gz", dtype={"site_no": str}, parse_dates=["date"])
    dv = dv[dv.site_no.isin(set(sites)) & dv.date.dt.month.between(7, 10)]
    m = dv.groupby([dv.site_no, dv.date.dt.year.rename("year"), dv.date.dt.month.rename("month")]).cfs.agg(["mean", "size"])
    y = m.groupby(level=["site_no", "year"]).agg(low=("mean", "min"), days=("size", "sum")).reset_index()
    y = y[y.days >= 110]
    out = {}
    for site, g in y.groupby("site_no"):
        recent = g[g.year >= first_year]
        g = recent if len(recent) >= min_summers else g
        out[site] = dict(div_share=round(float((g.low >= FLOWING_CFS).mean()), 2), div_summers=len(g),
                         div_years=f"{g.year.min()}–{g.year.max()}", div_recent=len(recent) >= min_summers)
    return pd.DataFrame.from_dict(out, orient="index", columns=["div_share", "div_summers", "div_years", "div_recent"])


# ---- Creeks the flow model rates as flowing that are dry most summers (2026-11-20) ----
# Checked against the USGS gauges of all 12 areas: in LA 31 of the 53 gauged creeks dry most summers were rated "usually
# flows" or "year-round", nearly all where the model's typical summer low is 0.1-0.45 cfs; elsewhere only Dead Creek
# (Champlain lowland). Two kinds of evidence go into flow_streams.csv (05b_flow.py) and scoring.py decides, one-sided
# (the user: "id rather rate a dry creek as year round than a year round creek as dry"):
#   - a gauge on the reach's own creek (creek_gauges, gauge_record): its share of summers flowing;
#   - the channel's late-summer greenness (channel_green): bare where it's near-certainly dry.
GREEN_YEARS = (2022, 2023, 2024)     # the late summers 02g_greenness.py fetches (the rule was measured on these)
GAUGE_KM = 4.0                       # a gauge's record stands for its creek this far along its model line
GAUGE_SITE_M = 500                   # gauges this close together are one site (Whitewater River at Windy Point)
# Station names of gauges that measure plumbing, not a creek (canals, conduits, powerhouses, spills, reservoirs),
# as in the 2026-11-18 review of the flow model; "above the canal / reservoir / dam" is the creek upstream of it.
PLUMBING = (r"(?:\bCN\b|CANAL|\bDIV\b|DIVERSION|FLUME|AQUEDUCT|SPILL|TUNNEL|PIPELINE|CONDUIT|\bCOND\b|COMBINED|\bPP\b|"
            r"\bPH\b|POWERHOUSE|FOREBAY|BYPASS|OVERFLOW|INFIL|BREEDLINE|BRLNE|RETURN FLOW|SUPP|QUALITY CONTROL|FLOODWAY|"
            r"\+|DITCH|\bDT\b|RACEWAY|TAILRACE|HEADRACE|OUTLET WORKS|RESERVOIR|\bRES\b|\bLAKE\b.*\bOUTLET\b|\bNR\b.*\bDAM\b)")
ABOVE = r"\b(?:AB|ABOVE|ABV)\b\s+(?:[A-Z.]+\s+){0,3}(?:CANAL|RESERVOIR|RES|LAKE|LK|DIV|DIVERSION|DAM)\b"


def green_path(box, year):
    """02g_greenness.py's late-summer NDVI raster for a range box and year."""
    from config import raw_dir
    return f"{raw_dir(box)}/late_summer_ndvi_{year}.tif"


def channel_green(geoms, box):
    """Late-summer greenness of each reach's channel (geoms in CRS) from 02g_greenness.py's rasters for `box`:
    green_p90 the 90th percentile of the NDVI within 30 m of the line (the greenest strip, so a DEM line a little off the
    creek still finds its trees), the median over the summers; green_p90_max its greenest summer; green_sur the median
    NDVI 100-400 m away (the slopes around), median over the summers; green_water the share of the pixels within 15 m
    with NDVI < 0 (open water), median over the summers. A summer with under 3 clear pixels within 15 m doesn't count.
    All NaN where the box has no rasters (an area without the late_summer_green source)."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds
    cols = ["green_p90", "green_p90_max", "green_sur", "green_water"]
    paths = [p for p in (green_path(box, y) for y in GREEN_YEARS) if os.path.exists(p)]
    out = pd.DataFrame(np.nan, index=range(len(geoms)), columns=cols)
    if not paths:
        return out
    srcs = [rasterio.open(p) for p in paths]
    lines = gpd.GeoSeries(list(geoms), crs=CRS).to_crs(srcs[0].crs)
    for i, line in enumerate(lines):
        c15, c30, ring = line.buffer(15), line.buffer(30), line.buffer(400).difference(line.buffer(100))
        yr = []
        for s in srcs:
            w = from_bounds(*ring.bounds, s.transform).round_offsets().round_lengths()
            a = s.read(1, window=w, boundless=True, fill_value=-32768)
            if a.size == 0:
                continue
            tr, ok = s.window_transform(w), a != -32768
            v15 = a[~geometry_mask([c15], a.shape, tr) & ok] / 1e4
            if len(v15) < 3:
                continue
            v30 = a[~geometry_mask([c30], a.shape, tr) & ok] / 1e4
            vr = a[~geometry_mask([ring], a.shape, tr) & ok] / 1e4
            yr.append((np.percentile(v30, 90), (v15 < 0).mean(), np.median(vr) if len(vr) else np.nan))
        if yr:
            y = np.array(yr)
            out.iloc[i] = [np.median(y[:, 0]), y[:, 0].max(), np.nanmedian(y[:, 2]) if np.isfinite(y[:, 2]).any() else np.nan,
                           np.median(y[:, 1])]
    for s in srcs:
        s.close()
    return out.round(3)


def creek_gauges(v2):
    """The area's USGS gauges (02b_download_flow.py) that measure a creek itself, natural or below a diversion or dam (not
    a canal, conduit, powerhouse or reservoir gauge, nor one with no drainage area), with 5+ summers since 2011: site_no,
    station_nm, area_km2, comid (their NHDPlus line, as validate_flow.py matches them), geometry (CRS), and their record
    (gauge_summers: div_share, div_summers, div_years)."""
    p = f"{FLOW}/gauge_sites.gpkg"
    if not os.path.exists(p):
        return gpd.GeoDataFrame(columns=["site_no", "station_nm", "area_km2", "comid", "geometry"], geometry="geometry", crs=CRS)
    gs = gpd.read_file(p).to_crs(CRS)
    gs["area_km2"] = pd.to_numeric(gs.drain_area_va, errors="coerce") * 2.58999
    nm = gs.station_nm.fillna("")
    plumbing = nm.str.contains(PLUMBING, case=False, regex=True) & ~(
        nm.str.contains(ABOVE, case=False, regex=True)
        & ~nm.str.contains(r"\b(?:CN|CANAL|DITCH|FLUME|CONDUIT|TUNNEL|PIPELINE)\b.*\b(?:AB|ABOVE)\b", case=False, regex=True))
    gs = gs[~plumbing & gs.area_km2.notna()].copy()
    if not len(gs):
        return gs
    rec = gauge_summers(list(gs.site_no))
    gs = gs.join(rec, on="site_no", how="inner")
    gs = gs[gs.div_recent.eq(True)].copy()
    gs["comid"] = match_points(gs.geometry, gs.area_km2, v2, max_dist=300).values
    return gs.reset_index(drop=True)


GAUGE_END_M = 100.0                  # a reach whose middle lies this near the gauge's own model line is on it


def gauge_own_lines(gauges, v2, near_comid=None):
    """{site_no: the gauge's own model line(s), one geometry in the area's CRS}: its NHDPlus line and the one the reach
    it sits on takes its flow from (`near_comid`). gauge_record counts a reach as on the gauge's line where it took
    its flow from that line or its middle lies within GAUGE_END_M of it. NHDPlus ends a line at every junction,
    however small the creek joining, and a short reach at the end of the gauge's line can take its flow from the
    next one: a 10 m reach of the San Jacinto River, at the junction 1.4 km above its gauge near San Jacinto, did
    when the routing moved a vertex (2026-11-21), and read year-round below reaches the same and above reaches the
    gauge sets at "mostly dry" (19 % of summers).
    The record is not carried further along the creek. Following it across junctions was measured the same day (down
    NHDPlus's path and up its main stem while the drainage stayed within 2/3 to 1.5 x the gauge's): reaches with a
    record 1,170 -> 3,097 over the 12 maps, but it put dry records on reaches 2-4 km above their gauge (Murray Canyon,
    fish 58 -> 3; San Juan Creek above La Novia, 60 -> 10, along a channel green in late summer) and below junctions
    where another creek comes in (the East Fork of the West Fork Mojave, 72 -> 8). The canyon above a dry gauge may
    still run, and a wet creek is never shown as dry."""
    out = {}
    if not len(gauges):
        return out
    geo = v2.drop_duplicates("comid").set_index("comid").geometry.to_crs(CRS)
    for g in gauges.itertuples():
        own = [c for c in (g.comid, (near_comid or {}).get(g.site_no)) if pd.notna(c) and c in geo.index]
        if own:
            out[g.site_no] = shapely.union_all(geo.loc[own].values)
    return out


def gauge_record(mid, area_full, comid, flow_src, in_lake, gauges, near_comid=None, own=None):
    """Per reach: the record of the nearest gauge (creek_gauges) on its own creek, within GAUGE_KM, where the reach is on
    the gauge's model line (its own, or the one the reach the gauge sits on takes its flow from: `near_comid`, by
    site_no; a reach took its flow from that line, or its middle lies within GAUGE_END_M of it: `own`,
    gauge_own_lines) and drains 2/3 to 1.5 x the gauge's area, and isn't in a lake. Gauges within GAUGE_SITE_M of each other
    are one site: their shares are averaged. -> DataFrame: gauge_site, gauge_name, gauge_share, gauge_summers,
    gauge_years, gauge_area_km2, gauge_m (distance), gauge_below (the reach drains 0.9 x the gauge's area or more: at or
    below it, where a dry record also holds; the canyon above a dry gauge may still run)."""
    n = len(mid)
    best_d = np.full(n, np.inf)
    out = pd.DataFrame({"gauge_site": None, "gauge_name": None, "gauge_share": np.nan, "gauge_summers": np.nan,
                        "gauge_years": None, "gauge_area_km2": np.nan, "gauge_m": np.nan}, index=range(n))
    if not len(gauges):
        out["gauge_below"] = False
        return out
    mx, my = np.array([p.x for p in mid]), np.array([p.y for p in mid])
    pts = shapely.points(mx, my)
    area_full, comid = np.asarray(area_full, float), np.asarray(comid, float)
    ok_src = np.isin(np.asarray(flow_src, dtype=object), ["model", "scaled"]) & ~np.asarray(in_lake, bool)
    gx, gy = gauges.geometry.x.values, gauges.geometry.y.values
    for k, g in gauges.reset_index(drop=True).iterrows():
        site = np.hypot(gx - gx[k], gy - gy[k]) <= GAUGE_SITE_M
        lines = [c for c in (g.comid, (near_comid or {}).get(g.site_no)) if pd.notna(c)]
        at = np.isin(comid, lines)
        if own is not None and g.site_no in own:
            at |= shapely.distance(pts, own[g.site_no]) <= GAUGE_END_M
        on = ok_src & at & (area_full >= g.area_km2 / 1.5) & (area_full <= g.area_km2 * 1.5)
        d = np.hypot(mx - gx[k], my - gy[k])
        take = on & (d <= GAUGE_KM * 1000) & (d < best_d)
        if take.any():
            best_d[take] = d[take]
            out.loc[take, ["gauge_site", "gauge_name", "gauge_share", "gauge_summers", "gauge_years", "gauge_area_km2",
                           "gauge_m"]] = [g.site_no, g.station_nm, round(float(gauges.div_share[site].mean()), 3),
                                          int(g.div_summers), g.div_years, round(float(g.area_km2), 1), 0.0]
            out.loc[take, "gauge_m"] = np.round(d[take])
    out["gauge_below"] = out.gauge_share.notna() & (area_full >= 0.9 * out.gauge_area_km2.astype(float))
    return out


def gauge_reach_comids(gauges, lines, area_full, comid):
    """{site_no: the model line of the reach each gauge (creek_gauges) sits on}: the reach within 300 m whose drainage
    is 0.5-2 x the gauge's, the closest in drainage, then in distance. A "scaled" reach takes its flow from a line
    further down, and the reaches beside the gauge do too (Piru Creek below Pyramid Dam): gauge_record follows that line."""
    out = {}
    if not len(gauges):
        return out
    ln = gpd.GeoSeries(list(lines), crs=CRS)
    area_full, comid = np.asarray(area_full, float), np.asarray(comid, float)
    idx = ln.sindex
    for g in gauges.itertuples():
        k = idx.query(g.geometry.buffer(300), predicate="intersects")
        if not len(k):
            continue
        ratio = area_full[k] / g.area_km2
        ok = (ratio >= 0.5) & (ratio <= 2)
        if not ok.any():
            continue
        k, ratio = k[ok], ratio[ok]
        d = ln.iloc[k].distance(g.geometry).values
        rank = np.round(np.abs(np.log(ratio)), 1) * 1000 + d
        c = comid[k[np.argmin(rank)]]
        if not np.isnan(c):
            out[g.site_no] = float(c)
    return out
