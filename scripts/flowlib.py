"""Shared helpers for the flow evidence (05b_flow.py, data/validate_flow.py)."""
import os, json, numpy as np, pandas as pd, geopandas as gpd, pyogrio
from shapely.geometry import box
from config import REGIONS, CRS, SHARED, NATIONAL, AREA

FLOW = f"{SHARED}/flow"
MIN_RESERVOIR_KM2 = 0.08     # waterbodies smaller than 8 ha (debris basins, ponds) don't control a creek's base flow


def match_points(points, areas, v2, max_dist=150, lo=0.3, hi=1.6):
    """COMID for each point: the nearest NHDPlus V2 flowline within max_dist whose total drainage area agrees
    with the point's (ratio point/flowline in [lo, hi]). Stops a small tributary grabbing the main stem beside it.
    A point with unknown area takes the nearest flowline. Returns a float Series (NaN = no match)."""
    pts = gpd.GeoDataFrame({"a": np.asarray(areas, float)}, geometry=list(points), crs=CRS)
    pts["pid"] = np.arange(len(pts))
    lines = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath", "Connector"])][["comid", "totdasqkm", "geometry"]]
    j = gpd.sjoin(pts.assign(geometry=pts.buffer(max_dist)), lines, predicate="intersects")
    if j.empty:
        return pd.Series(np.nan, index=getattr(points, "index", None))
    geom = lines.geometry.reindex(j.index_right).values
    j["dist"] = gpd.GeoSeries(pts.geometry.reindex(j.index).values, crs=CRS).distance(gpd.GeoSeries(geom, crs=CRS)).values
    ratio = j.a / j.totdasqkm.replace(0, np.nan)
    ok = j.a.isna() | ratio.between(lo, hi)
    j = j[ok].assign(miss=np.abs(np.log(ratio[ok].fillna(1.0))))
    # prefer close area agreement, then distance
    j["rank"] = j.miss.round(1) * 1000 + j.dist
    best = j.sort_values("rank").drop_duplicates("pid").set_index("pid").comid
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
