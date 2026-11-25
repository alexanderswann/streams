"""Creeks a city has buried: where the terrain still drains but the creek runs in a sewer under the streets, the maps
draw no line (05_score.py, at the end; the user's choice, "Option A", 2026-11-24).

03b_stitch.py starts a channel wherever 0.25 km2 drains, and 05_score.py draws every link of 1 km2 or more. In a city
the bare-earth DEM still drains, so its paths run down streets and across blocks where the creek was put in a sewer long
ago (West Philadelphia's Mill Creek, the Wingohocking, Saratoga Springs' Spring Run) or never had a channel (LA's urban
fans, which drain through streets and storm drains). On the 12 maps of 2026-11-24 (site cf5b90c) such lines were 568
mi: LA 477 (fish 7), se_pa 62 (Philadelphia 50), north Atlanta, Dalton and Calhoun 16, town centres elsewhere 13; se_pa's
ground to the Delaware adds 76 mi (North and Northeast Philadelphia, Wilmington). Every one had no name, and its popup
said "NHD unmapped".

A reach is not drawn (`reaches`) when all of these hold:
  - it has no name and no NHD class once 05_score.py has named its reaches (the votes, names along rivers, side
    channels): a creek named only by a later rule, such as a piece of Tacony Creek whose line runs off NHD's, stays;
  - no NHD line other than a pipeline or underground conduit lies within NHD_NEAR_M of NHD_MAX_SHARE of it or more;
  - NLCD 2021 impervious cover (MRLC, 30 m), read in 3 x 3 cell windows every STEP_M along it, averages IMP_MIN % or more;
  - an open OpenStreetMap waterway (a river, stream, canal, ditch or drain not tagged as a tunnel, culvert, covered or
    underground) lies within OSM_NEAR_M of under OSM_MAX_SHARE of it;
  - no designated trout water lies within TROUT_WATER_M of it, and no trout record within TROUT_RECORD_M has it for its
    nearest reach (the user's rule: possible trout water stays). Read from troutdata.py's designations and records, and
    from the area's trout evidence and trout waters as 11_context.py last wrote them (CDFW's in California,
    iNaturalist's everywhere; none on an area's first build). 11_context.py reads a designation onto a reach within 30 m,
    and a record onto an unnamed reach only where it is the nearest reach, within 300 m (a sighting 150 m) and with no
    creek of the record's name near: so a reach that could show a trout record stays. (Any record within 300 m kept 1.4
    mi of street lines by the Schuylkill whose nearest reach is the river.)
No one signal does it alone (measured 2026-11-24 on the 4,555 mi of unnamed lines NHD doesn't map on the 12 maps):
OSM's tunnel and culvert tags mark 2 mi in all, as OSM doesn't map Philadelphia's sewers; no OSM waterway at all marks
3,875 mi, mostly remote creeks NHD doesn't map, which OSM doesn't either (its streams came from NHD); no channel in the 10
m DEM's cross-section marks 3,081 mi and takes rail cuts and sunken roads for channels; impervious cover alone marks
682 mi, 63 of them LA lines along open flood channels OSM maps. Together they leave Cobbs, Tacony, Pennypack, Frankford
and Poquessing creeks, the Wissahickon and its tributaries in the park, and LA's channels as they were. The routing
still carries the water (so do the sewers): only the drawing changes.

Downloads, each range, through netfetch.py (the copy already there when one fails): NLCD 2021 impervious cover from
MRLC's WCS, kept as served (EPSG:5070) until the range's box outgrows it, and OpenStreetMap's waterway lines with their
tags (Overpass), kept a week.
"""
import os, json, time
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
from scipy.ndimage import uniform_filter
from pyproj import Transformer
from config import CRS, EPSG, RAW, MAP_OUT, REGION, XMIN, YMIN, XMAX, YMAX
import netfetch

IMP_MIN = 40.0                            # % impervious along the reach
OSM_NEAR_M, OSM_MAX_SHARE = 60.0, 0.2     # open OSM water within 60 m of under 20 % of the reach
NHD_NEAR_M, NHD_MAX_SHARE = 60.0, 0.5     # an NHD line within 60 m of half the reach or more: NHD maps something there
NHD_BUILT = (420, 428)                    # underground conduits and pipelines (LA files its storm drains as pipelines)
TROUT_WATER_M, TROUT_RECORD_M = 30.0, 300.0
STEP_M = 20.0
MARGIN_M = 1000.0                         # the downloads reach this far past the range's box
WCS = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"
COVERAGE = "mrlc_download__NLCD_2021_Impervious_L48"
WATERWAYS = "river|stream|brook|canal|ditch|drain|tidal_channel|culvert"
LIFECYCLE = ("disused", "abandoned", "was", "razed", "demolished", "historic", "removed")   # was:waterway etc.


def _bounds(epsg_to, margin=MARGIN_M):
    """The range's box (plus `margin`) in another CRS: (xmin, ymin, xmax, ymax)."""
    g = shapely.segmentize(shapely.box(XMIN - margin, YMIN - margin, XMAX + margin, YMAX + margin), 500)
    xy = shapely.get_coordinates(g)
    x, y = Transformer.from_crs(EPSG, epsg_to, always_xy=True).transform(xy[:, 0], xy[:, 1])
    return float(np.min(x)), float(np.min(y)), float(np.max(x)), float(np.max(y))


def impervious_tif():
    """The range's NLCD 2021 impervious cover, % per 30 m cell (over 100 is no data), as MRLC serves it (EPSG:5070)."""
    p = f"{RAW}/nlcd_impervious.tif"
    x0, y0, x1, y1 = _bounds(5070)
    if os.path.exists(p):
        with rasterio.open(p) as src:
            b = src.bounds
        if b.left <= x0 and b.bottom <= y0 and b.right >= x1 and b.top >= y1:
            return p
    x0, y0 = np.floor(x0 / 30) * 30 - 30, np.floor(y0 / 30) * 30 - 30
    x1, y1 = np.ceil(x1 / 30) * 30 + 30, np.ceil(y1 / 30) * 30 + 30
    def fetch():
        r = netfetch.fetch("GET", WCS, headers=netfetch.UA, timeout=300, tries=4,
                           ok=lambda q: q.ok and q.content[:4] in (b"II*\x00", b"MM\x00*"),
                           params=[("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"),
                                   ("CoverageId", COVERAGE), ("subset", f"X({x0:.0f},{x1:.0f})"),
                                   ("subset", f"Y({y0:.0f},{y1:.0f})"), ("format", "image/geotiff")])
        with open(p + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(p + ".tmp", p)
    netfetch.keep_old(p, fetch, f"NLCD impervious cover ({REGION})")
    return p


def waterways():
    """OpenStreetMap's waterway lines in the range's box (plus MARGIN_M): name, waterway, open (no tunnel, culvert,
    covered or underground tag, and no lifecycle prefix such as was:waterway). Kept a week, and when the box changes."""
    p = f"{RAW}/osm_waterways_tags.gpkg"
    ext = p + ".extent.json"
    box = [XMIN - MARGIN_M, YMIN - MARGIN_M, XMAX + MARGIN_M, YMAX + MARGIN_M]
    fresh = (os.path.exists(p) and os.path.exists(ext) and json.load(open(ext)) == box
             and time.time() - os.path.getmtime(p) < 7 * 86400)
    if not fresh:
        w, s, e, n = _bounds(4326)
        bb = f"({s:.5f},{w:.5f},{n:.5f},{e:.5f})"
        keys = [f'"waterway"~"^({WATERWAYS})$"'] + [f'"{k}:waterway"' for k in LIFECYCLE]
        def fetch():
            els = netfetch.overpass(f"[out:json][timeout:600];({''.join(f'way[{k}]{bb};' for k in keys)});out tags geom;")
            to = Transformer.from_crs(4326, EPSG, always_xy=True)
            rows, lines = [], []
            for el in els:
                q = el.get("geometry") or []
                if len(q) < 2:
                    continue
                t = el.get("tags", {})
                x, y = to.transform([v["lon"] for v in q], [v["lat"] for v in q])
                life = [v for k, v in t.items() if k.endswith(":waterway")]
                hidden = (bool(life) or t.get("tunnel") in ("yes", "culvert", "flooded") or t.get("covered") == "yes"
                          or t.get("location") == "underground" or t.get("waterway") == "culvert")
                rows.append({"name": t.get("name"), "waterway": t.get("waterway") or life[0], "open": not hidden})
                lines.append(shapely.LineString(np.c_[x, y]))
            # kept when empty too (a box with no waterway in OSM): it is the last good copy the step runs on offline
            gpd.GeoDataFrame(pd.DataFrame(rows, columns=["name", "waterway", "open"]), geometry=lines, crs=CRS).to_file(
                p + ".tmp.gpkg", driver="GPKG")
            os.replace(p + ".tmp.gpkg", p)
            with open(ext, "w") as f:
                json.dump(box, f)
        netfetch.keep_old(p, fetch, f"OSM waterways with their tags ({REGION})")
    return gpd.read_file(p)


def _points(geoms):
    """Points every STEP_M along each line (at least one): x, y, and the line each is on."""
    L = shapely.length(geoms)
    n = np.maximum(1, np.floor(L / STEP_M).astype(int))
    own = np.repeat(np.arange(len(geoms)), n)
    pos = np.concatenate([(np.arange(k) + 0.5) * (l / k) for k, l in zip(n, L)])
    p = shapely.line_interpolate_point(geoms[own], pos)
    return shapely.get_x(p), shapely.get_y(p), own


def _near(x, y, lines, d):
    """Which points lie within d of any of `lines`."""
    out = np.zeros(len(x), bool)
    if len(lines) and len(x):
        out[np.unique(shapely.STRtree(np.asarray(lines, dtype=object)).query(
            shapely.points(x, y), predicate="dwithin", distance=d)[0])] = True
    return out


def _impervious(x, y):
    """NLCD impervious cover at each point: the mean of the 3 x 3 cells around it (NaN with no data)."""
    with rasterio.open(impervious_tif()) as src:
        a, T = src.read(1).astype("float32"), src.transform
    ok = a <= 100
    a[~ok] = 0
    w = uniform_filter(ok.astype("float32"), 3)
    m = np.where(w > 0, uniform_filter(a, 3) / np.maximum(w, 1e-6), np.nan)
    X, Y = Transformer.from_crs(EPSG, 5070, always_xy=True).transform(x, y)
    c, r = ~T * (np.asarray(X), np.asarray(Y))
    c, r = np.floor(c).astype(int), np.floor(r).astype(int)
    v = (r >= 0) & (r < m.shape[0]) & (c >= 0) & (c < m.shape[1])
    out = np.full(len(x), np.nan)
    out[v] = m[r[v], c[v]]
    return out


def _trout():
    """(trout waters, trout records) for the guard, as two arrays of geometries in the area's CRS."""
    import troutdata
    wa = [troutdata.waters().geometry.values]
    ev = [e.geometry.values[(e.trout.astype(bool) & ~e.lake.astype(bool)).values] for e in troutdata.evidence()]
    ctx = f"{MAP_OUT}/context"
    if os.path.exists(f"{ctx}/wild_trout_waters.gpkg"):
        wa.append(gpd.read_file(f"{ctx}/wild_trout_waters.gpkg").to_crs(CRS).geometry.values)
    if os.path.exists(f"{ctx}/trout_evidence.gpkg"):
        t = gpd.read_file(f"{ctx}/trout_evidence.gpkg").to_crs(CRS)
        ev.append(t.geometry.values[(t.trout.astype(bool) & ~t.lake.astype(bool)).values])
    cat = lambda xs: (np.concatenate([np.asarray(v, dtype=object) for v in xs]) if xs else np.array([], dtype=object))
    wa, ev = cat(wa), cat(ev)
    return wa[~shapely.is_empty(wa) & ~pd.isna(wa)], ev[~shapely.is_empty(ev) & ~pd.isna(ev)]


def reaches(geoms, name, flow, in_lake, nhd):
    """Which reaches a city has buried (the module's docstring): (not drawn, kept for a trout water or record nearby),
    two boolean arrays. geoms, name, flow, in_lake: 05_score.py's reaches as named; nhd: the range's NHD lines (ftype)."""
    geoms = np.asarray(geoms, dtype=object)
    n = len(geoms)
    out, trout = np.zeros(n, bool), np.zeros(n, bool)
    cand = (pd.isna(pd.Series(name, dtype=object)).to_numpy() & (np.asarray(flow, dtype=object) == "unmapped")
            & ~np.asarray(in_lake, bool))
    k = np.flatnonzero(cand)
    if not len(k):
        return out, trout
    x, y, own = _points(geoms[k])
    cnt = np.bincount(own, minlength=len(k))
    imp = _impervious(x, y)
    ok = ~np.isnan(imp)
    nok = np.bincount(own[ok], minlength=len(k))
    imp_mean = np.where(nok > 0, np.bincount(own[ok], weights=imp[ok], minlength=len(k)) / np.maximum(nok, 1), 0.0)
    ww = waterways()
    open_ = _near(x, y, ww.geometry.values[ww["open"].astype(bool).values] if len(ww) else [], OSM_NEAR_M)
    nat = _near(x, y, nhd.geometry.values[~nhd.ftype.isin(NHD_BUILT).values], NHD_NEAR_M)
    hit = ((imp_mean >= IMP_MIN) & (np.bincount(own, weights=open_, minlength=len(k)) < OSM_MAX_SHARE * cnt)
           & (np.bincount(own, weights=nat, minlength=len(k)) < NHD_MAX_SHARE * cnt))
    k = k[hit]
    if len(k):
        tw, tr = _trout()
        near_t = np.zeros(len(k), bool)
        if len(tw):         # a designation within 30 m: 11_context.py reads it onto the reach
            near_t[np.unique(shapely.STRtree(tw).query(geoms[k], predicate="dwithin", distance=TROUT_WATER_M)[0])] = True
        if len(tr):         # a record within 300 m whose nearest reach this is: 11_context.py could read it onto it
            close = np.unique(shapely.STRtree(geoms[k]).query(tr, predicate="dwithin", distance=TROUT_RECORD_M)[0])
            if len(close):
                nearest = shapely.STRtree(geoms).query_nearest(tr[close], all_matches=True)[1]
                near_t |= np.isin(k, nearest)
        trout[k[near_t]] = True
        out[k[~near_t]] = True
    return out, trout
