"""Measured lake bathymetry: depth contours and each surveyed lake's depth, from the agencies' own surveys. Modelled
depths (GLOBathy, HydroLAKES) are never used; a lake no survey covers keeps the depth 05d_lakes.py found, or none.
AREA only; run after 05d_lakes.py (it updates lakes.gpkg; running it twice gives the same result) and before 06_map.py.

Surveys, by area (checked 2026-11-19):
  ne_ct       CT DEEP lake bathymetry contours (Lake_Bathymetry_Contours): depth-finder, GPS and lead-line surveys of
              1959-2002, in feet. 24 lakes in the area. The deepest contour is a lower bound on the lake's depth.
  central_vt  Vermont ANR bathymetric soundings (BiobaseLakeBathymetry, compiled 2020-08-12): 2.4 million sonar
              points in 66 lakes, depth in feet below the water level of the survey. 15 lakes in the area. Each lake's
              points are gridded (5 m, linear, the shore at 0) into contours, its mean depth and its deepest sounding.
  se_pa       DCNR's state park lake depth bands (PA Geological Survey maps: Marsh Creek, Jan 2005; Hopewell and Scotts Run,
              Apr 2017), and USGS's sonar survey of Chambers Lake (Sept 2014: 150,779 soundings and a 1.6 ft grid)
  la          USGS multibeam survey of Little Rock Reservoir (8-9 Feb 2022, doi:10.5066/P9BQW35E): a 1 m grid of bed
              elevation. California DWR's multibeam surveys of Castaic, Pyramid and Silverwood are not public.
  central_vt, adk_high_peaks, adk_southeast   Lake Champlain: the soundings of NOAA's electronic navigational charts
              (NOAA ENC, charts 14781-14784: about 12,000 soundings of the 1870-1939 lake surveys, with the charts'
              6 and 12 ft depth curves), gridded into contours. Depths below low lake level, the chart datum (93.0 ft
              above mean sea level; the lake usually stands 2-3 ft higher). NOAA's user agreement lets the charts be
              redistributed, also inside another product, if their origin and the agreement are shown: the popups
              name both. Looked for on 2026-11-21 and not open: the Middlebury College multibeam survey (not released).
  jackson     none published (see lakedata.py)
Each contour line belongs to the lake it lies in, each sounding to the lake it falls in: no name matching.
Writes data/derived/<area>/_shared/lake_depth.gpkg (lid, depth_ft, depth_m, major, src).
"""
import os, re, json, requests, numpy as np, pandas as pd, geopandas as gpd, shapely
import netfetch
from rasterio import features
from rasterio.transform import from_origin
from config import AREA, REGIONS, CRS, SHARED, SHARED_DERIVED, WORKED_OUT
import sources
import areaclip
from units import ft, acres  # the depth notes the map popups show are in feet and acres (units.py)
from shapely.geometry import box

FT = 0.3048
LAKES = os.environ.get("LAKES_OUT", f"{SHARED_DERIVED}/lakes.gpkg")
OUT = os.environ.get("LAKE_DEPTH_OUT", f"{SHARED_DERIVED}/lake_depth.gpkg")   # with LAKES_OUT, to check an area first
CT = "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Lake_Bathymetry_Contours/FeatureServer/1"
VT_URL = "https://anrmaps.vermont.gov/websites/OpenData/Items/BathymetricData/BiobaseLakeBathymetry_08122020.zip"
VT_CSV = f"{SHARED}/bathymetry/vt_bathy/BiobaseLakeBathymetry_08122020.csv"


def step_ft(dmax_ft):
    return 5 if dmax_ft < 40 else 10 if dmax_ft < 120 else 20


def ct_contours(lk, bounds_ll):
    """(contour rows, {lid: depth facts}) from CT DEEP's contour lines."""
    from geomatch import esri
    g = esri(CT, bounds_ll, "WBNAME,WBTOWN,METHOD,DATADATE,DEPTH_FT")
    if not len(g):
        return [], {}
    g = gpd.GeoDataFrame(g, crs=4326).to_crs(CRS)
    g = g[pd.to_numeric(g.DEPTH_FT, errors="coerce") > 0]
    j = gpd.sjoin(g, lk[["lid", "geometry"]].assign(geometry=lk.buffer(30)), predicate="within", how="inner")
    rows, facts = [], {}
    for lid, d in j.groupby("lid"):
        yr = pd.to_numeric(d.DATADATE, errors="coerce")             # a plain year; 0 where it isn't known
        yr = yr[(yr >= 1900) & (yr <= 2100)]
        y = int(yr.mode().iat[0]) if len(yr) else None
        how = d.METHOD.mode().iat[0] if d.METHOD.notna().any() else "survey"
        wbn = d.WBNAME.mode().iat[0] if d.WBNAME.notna().any() else None
        src = f"CT DEEP bathymetric survey{' of ' + wbn if wbn else ''} ({how}{', ' + str(y) if y else ''})"
        dmax = float(d.DEPTH_FT.max())
        maj = 10 if dmax <= 40 else 20
        rows += [dict(lid=lid, depth_ft=float(f), depth_m=round(float(f) * FT, 1), major=bool(f % maj == 0), src=src, geometry=geo)
                 for f, geo in zip(d.DEPTH_FT, d.geometry)]
        facts[lid] = dict(max_ft=dmax, mean_ft=None, src=src, note=f"deepest contour {dmax:g} ft: the bottom is a little deeper",
                          survey_name=d.WBNAME.mode().iat[0] if d.WBNAME.notna().any() else None)
    return rows, facts


def vt_soundings(lk, bounds_ll):
    """(contour rows, {lid: depth facts}) from Vermont's sonar soundings, gridded lake by lake."""
    if not os.path.exists(VT_CSV):
        import zipfile, io
        os.makedirs(os.path.dirname(VT_CSV), exist_ok=True)
        r = netfetch.get(VT_URL, timeout=600, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
        r.raise_for_status()
        zipfile.ZipFile(io.BytesIO(r.content)).extractall(os.path.dirname(VT_CSV))
    w, s, e, n = bounds_ll
    t = pd.read_csv(VT_CSV, dtype={"Longitude": "float64", "Latitude": "float64", "DepthInFeet": "float32", "LakeName": "string"})
    t = t[(t.Longitude >= w) & (t.Longitude <= e) & (t.Latitude >= s) & (t.Latitude <= n)]
    pts = gpd.GeoDataFrame({"ft": -t.DepthInFeet.values, "lake": t.LakeName.values},
                           geometry=gpd.points_from_xy(t.Longitude, t.Latitude), crs=4326).to_crs(CRS)
    j = gpd.sjoin(pts, lk[["lid", "geometry"]], predicate="within", how="inner")
    rows, facts = [], {}
    import contourpy
    from scipy.interpolate import griddata
    for lid, d in j.groupby("lid"):
        if len(d) < 200:
            continue
        lake = lk.geometry[lk.lid == lid].iloc[0]
        d = d.sample(min(len(d), 60000), random_state=0)          # dense tracks: 60,000 points carry the shape
        res = 5.0
        shore = np.vstack([np.asarray(shapely.segmentize(b, res).coords)[:, :2] for b in
                           (lake.boundary.geoms if lake.boundary.geom_type == "MultiLineString" else [lake.boundary])])
        xy = np.vstack([np.column_stack([d.geometry.x, d.geometry.y]), shore])
        v = np.r_[d.ft.values.astype(float), np.zeros(len(shore))]
        x0, y0, x1, y1 = lake.bounds
        W, H = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
        T = from_origin(x0, y1, res, res)
        cx = x0 + (np.arange(W) + 0.5) * res
        cy = y1 - (np.arange(H) + 0.5) * res
        gx, gy = np.meshgrid(cx, cy)
        z = griddata(xy, v, (gx, gy), method="linear")
        inside = features.geometry_mask([lake], out_shape=z.shape, transform=T, invert=True)
        z = np.where(inside, z, np.nan)
        dmax = float(d.ft.max())
        step = step_ft(dmax)
        gen = contourpy.contour_generator(z=np.where(np.isfinite(z), z, np.nan), name="serial")
        src = "Vermont ANR sonar soundings (compiled 2020)"
        for lv in np.arange(step, dmax, step):
            for ln in gen.lines(lv):
                if len(ln) >= 3:
                    xs, ys = x0 + (ln[:, 0] + 0.5) * res, y1 - (ln[:, 1] + 0.5) * res
                    geo = shapely.simplify(shapely.LineString(np.column_stack([xs, ys])), 1.0)
                    rows.append(dict(lid=lid, depth_ft=float(lv), depth_m=round(lv * FT, 1), major=bool(lv % (step * 2) == 0),
                                     src=src, geometry=geo))
        facts[lid] = dict(max_ft=dmax, mean_ft=float(np.nanmean(z)), src=src,
                          note=f"{len(j[j.lid == lid]):,} soundings; depth below the water level when surveyed")
    return rows, facts


LR_URL = ("https://www.sciencebase.gov/catalog/file/get/62e8a8c9d34e749ac04cbd66?f=__disk__9f%2Fcc%2F95%2F"
          "9fcc95bef8db3e385380cf368015ec2a87029ec7")
LR_CSV = f"{SHARED}/bathymetry/little_rock/LittleRock_2022_DEM_ftNAVD88.csv"
# The file's header says ft NAVD88, but its elevations sit 106.4 ft (32.43 m) under the 3DEP lidar (NAVD88) on land:
# median over 105,012 cells against CA_LosAngeles_1_B23, IQR 104.5-108.4 ft, about the geoid separation here, so they
# read as ellipsoid heights. Raised by that much, the deepest bed comes to USGS's own stage-storage zero (3,199.46 ft
# NAVD88; the crest, 3,273 ft, is the 2023-24 lidar's water level).
LR_OFFSET_FT = 106.4
LR_ZERO_STORAGE_FT = 3199.46


def usgs_little_rock(lk, bounds_ll):
    """(contour rows, {lid: depth facts}) from USGS's multibeam survey of Little Rock Reservoir (8-9 Feb 2022; ScienceBase
    doi:10.5066/P9BQW35E): a 1 m grid of bed elevation, ft NAVD88, UTM 11N NAD83, merged with lidar above the water.
    Depth is taken below the lake's own lidar water level (here 3,273 ft, the spillway crest), cell by cell."""
    if not os.path.exists(LR_CSV):
        os.makedirs(os.path.dirname(LR_CSV), exist_ok=True)
        with netfetch.get(LR_URL, stream=True, timeout=1200, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"}) as r:
            r.raise_for_status()
            with open(LR_CSV + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.replace(LR_CSV + ".part", LR_CSV)
    t = pd.read_csv(LR_CSV, header=0, names=["x", "y", "z"], dtype="float64")
    x0, y1 = t.x.min(), t.y.max()
    col = np.rint(t.x.values - x0).astype(int)
    row = np.rint(y1 - t.y.values).astype(int)
    z = np.full((row.max() + 1, col.max() + 1), np.nan)
    z[row, col] = t.z.values + LR_OFFSET_FT
    T = from_origin(x0 - 0.5, y1 + 0.5, 1.0, 1.0)
    lk26911 = lk.to_crs(26911)
    # the lake: the one covering most of the survey's extent (the grid takes in lidar ground around the water too)
    bb = shapely.box(x0, float(t.y.min()), float(t.x.max()), y1)
    hit = lk26911[lk26911.intersects(bb)]
    if not len(hit):
        print("  Little Rock survey: no lake in its extent")
        return [], {}
    i = hit.geometry.intersection(bb).area.idxmax()
    lid, lake = lk.lid.at[i], lk26911.geometry.at[i]
    level_ft = (lk.water_level_m.at[i] if pd.notna(lk.water_level_m.at[i]) else lk.elev_m.at[i]) / FT
    inside = features.geometry_mask([lake], out_shape=z.shape, transform=T, invert=True)
    d = np.where(inside & np.isfinite(z), np.clip(level_ft - z, 0, None), np.nan)
    dmax = float(np.nanmax(d))
    low = float(np.nanmin(np.where(inside, z, np.nan)))
    print(f"  Little Rock: deepest bed {low:,.1f} ft NAVD88 (USGS stage-storage zero {LR_ZERO_STORAGE_FT:,.2f}), "
          f"water level {level_ft:,.1f} ft")
    if abs(low - LR_ZERO_STORAGE_FT) > 3:
        print("  Little Rock: the survey's datum doesn't match USGS's table; left out")
        return [], {}
    step = step_ft(dmax)
    src = "USGS multibeam survey (Feb 2022)"
    rows = []
    import contourpy
    from scipy.ndimage import gaussian_filter
    # the lines from a lightly smoothed copy (a 1 m grid draws every boulder as a ring); depths stay the grid's own
    w = np.isfinite(d)
    ds = gaussian_filter(np.where(w, d, 0.0), 2.0) / np.maximum(gaussian_filter(w.astype(float), 2.0), 1e-9)
    gen = contourpy.contour_generator(z=np.where(w, ds, np.nan), name="serial")
    for lv in np.arange(step, dmax, step):
        for ln in gen.lines(lv):
            if len(ln) >= 3:
                xs, ys = x0 + ln[:, 0], y1 - ln[:, 1]
                geo = shapely.simplify(shapely.LineString(np.column_stack([xs, ys])), 1.5)
                if geo.length < 50:
                    continue
                rows.append(dict(lid=lid, depth_ft=float(lv), depth_m=round(lv * FT, 1), major=bool(lv % (step * 2) == 0),
                                 src=src, geometry=geo))
    if rows:   # the contours in the area's CRS
        g = gpd.GeoSeries([r["geometry"] for r in rows], crs=26911).to_crs(CRS)
        for r, geo in zip(rows, g):
            r["geometry"] = geo
    facts = {lid: dict(max_ft=dmax, mean_ft=float(np.nanmean(d)), src=src,
                       note=f"{acres(np.isfinite(d).sum() / 1e4)} surveyed on a {ft(1, 1)} grid; depth "
                            f"below the lake's lidar water level ({level_ft:,.0f} ft NAVD88)")}
    return rows, facts


DCNR_BANDS = "https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/StateParkLakesBathymetryPolygons/MapServer/0"
DCNR_SURVEY = {"Marsh Creek State Park": "DCNR / PA Geological Survey depth bands (survey of January 2005)",
               "French Creek State Park": "DCNR / PA Geological Survey depth bands (survey of April 2017)"}


def dcnr_bands(lk, bounds_ll):
    """(contour rows, {lid: depth facts}) from DCNR's state park lake depth bands (the PA Geological Survey's water-depth
    maps, feet below normal pool; Marsh Creek, Hopewell and Scotts Run lakes in SE Pennsylvania). A band of depth d
    covers d to the next band, so the line at depth d is the edge of the bands of d and deeper. The deepest point each
    map gives is typed in (lakedata.py); the bands' own deepest value is a lower bound."""
    from geomatch import esri
    g = esri(DCNR_BANDS, bounds_ll, "Depth,PARK_NAME")
    if not len(g):
        return [], {}
    g = gpd.GeoDataFrame(g, crs=4326).to_crs(CRS)
    g["Depth"] = pd.to_numeric(g.Depth, errors="coerce")
    g = g[g.Depth.notna() & g.geometry.notna()].copy()
    g["geometry"] = shapely.make_valid(g.geometry.values)
    pts = g.assign(geometry=g.geometry.representative_point())
    j = gpd.sjoin(pts, lk[["lid", "geometry"]].assign(geometry=lk.buffer(60)), predicate="within", how="inner")
    rows, facts = [], {}
    for lid, d in j.groupby("lid"):
        bands = g.loc[d.index.unique()]
        levels = sorted(float(v) for v in bands.Depth.unique() if v > 0)
        if not levels:
            continue
        step = min(np.diff([0.0] + levels))
        src = DCNR_SURVEY.get(bands.PARK_NAME.mode().iat[0], "DCNR / PA Geological Survey depth bands")
        for lv in levels:
            edge = shapely.simplify(shapely.union_all(bands.geometry[bands.Depth >= lv].values).boundary, 1.0)
            for part in getattr(edge, "geoms", [edge]):
                if part.length >= 20:
                    rows.append(dict(lid=lid, depth_ft=lv, depth_m=round(lv * FT, 1), major=bool(lv % (2 * step) == 0),
                                     src=src, geometry=part))
        facts[lid] = dict(max_ft=max(levels), mean_ft=None, src=src,
                          note=f"depth bands every {step:g} ft below normal pool (the deepest band from {max(levels):g} ft)")
    return rows, facts


CH_URL = "https://pubs.usgs.gov/sim/3346/sim3346_spatial_data.zip"
CH_DIR = f"{SHARED}/bathymetry/chambers"
CH_POOL_FT = 579.2      # Chambers Lake's normal pool, ft NAVD 88 (USGS SIM 3346); the survey's grid ends at it


def usgs_chambers(lk, bounds_ll):
    """(contour rows, {lid: depth facts}) from USGS's survey of Chambers Lake (Gyves 2015, SIM 3346, doi:10.3133/sim3346):
    150,779 soundings by a 5-beam acoustic Doppler profiler with RTK GPS, 8-12 September 2014, and the bathymetric
    surface made from them (1.6 ft grid, ft NAVD 88, PA State Plane South). Depth below normal pool (579.2 ft). The
    grid agrees with the 3DEP lidar: along the lidar's shoreline it reads 576.6 ft where the lidar's water lay at 575.7."""
    import rasterio, zipfile
    tif, xyz = f"{CH_DIR}/SIM3346/sim3346_bathymetric_surface.tif", f"{CH_DIR}/SIM3346/sim3346_XYZ.csv"
    if not os.path.exists(tif):
        os.makedirs(CH_DIR, exist_ok=True)
        zp = f"{CH_DIR}/sim3346_spatial_data.zip"
        if not os.path.exists(zp):
            r = netfetch.get(CH_URL, timeout=600, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
            r.raise_for_status()
            with open(zp + ".part", "wb") as f:
                f.write(r.content)
            os.replace(zp + ".part", zp)
        with zipfile.ZipFile(zp) as z_:
            z_.extractall(CH_DIR, [m for m in z_.namelist() if m.startswith("SIM3346/sim3346_bathymetric_surface") or m.endswith("_XYZ.csv")])
    with rasterio.open(tif) as src_:
        z = src_.read(1, masked=True).astype("float64").filled(np.nan)
        T, gcrs = src_.transform, src_.crs
    lkg = lk.to_crs(gcrs)
    hit = lkg[lkg.intersects(shapely.box(*rasterio.transform.array_bounds(*z.shape, T)))]
    if not len(hit):
        print("  Chambers survey: no lake in its extent")
        return [], {}
    i = hit.geometry.area.idxmax()
    lid = lk.lid.at[i]
    d = np.clip(CH_POOL_FT - z, 0, None)                # the whole survey: the lake at normal pool
    low = float(pd.read_csv(xyz, usecols=["Z"]).Z.min()) if os.path.exists(xyz) else float(np.nanmin(z))
    dmax = CH_POOL_FT - low                               # the deepest sounding (the grid smooths it a little)
    step = step_ft(dmax)
    import contourpy
    from scipy.ndimage import gaussian_filter
    w = np.isfinite(d)
    ds = gaussian_filter(np.where(w, d, 0.0), 2.0) / np.maximum(gaussian_filter(w.astype(float), 2.0), 1e-9)
    gen = contourpy.contour_generator(z=np.where(w, ds, np.nan), name="serial")
    src = "USGS sonar survey (Sept 2014)"
    rows = []
    for lv in np.arange(step, dmax, step):
        for ln in gen.lines(lv):
            if len(ln) >= 3:
                xs, ys = rasterio.transform.xy(T, ln[:, 1], ln[:, 0])
                geo = shapely.simplify(shapely.LineString(np.column_stack([xs, ys])), 4.0)     # feet
                if geo.length >= 150:
                    rows.append(dict(lid=lid, depth_ft=float(lv), depth_m=round(lv * FT, 1), major=bool(lv % (step * 2) == 0),
                                     src=src, geometry=geo))
    if rows:
        g = gpd.GeoSeries([r["geometry"] for r in rows], crs=gcrs).to_crs(CRS)
        for r, geo in zip(rows, g):
            r["geometry"] = geo
    facts = {lid: dict(max_ft=dmax, mean_ft=float(np.nanmean(d)), src=src,
                       note=f"150,779 soundings (acoustic profiler, RTK GPS); depth below normal pool ({CH_POOL_FT:g} ft NAVD 88)")}
    return rows, facts


ENC_CAT = "https://charts.noaa.gov/ENCs/ENCProdCat.xml"
ENC_ZIP = "https://charts.noaa.gov/ENCs/{}.zip"
ENC_TERMS = "https://charts.noaa.gov/ENCs/Agreement.shtml"
ENC_DIR = f"{SHARED}/bathymetry/noaa_enc"
CHAMPLAIN_LL = (-73.55, 43.52, -73.00, 45.10)       # the lake, to the Canadian line
# the chart cells over the lake on 2026-11-21, used when NOAA's catalogue can't be read (it is re-cut now and then)
CHAMPLAIN_CELLS = ["US4NY1KS", "US4NY1LS", "US4NY1MS", "US4NY1NS", "US4NY1NT", "US4NY1OS", "US4NY1OT", "US4NY1PS", "US4NY1PT",
                   "US5VT1DD", "US5VT1ED", "US5NY3MR", "US5NY3MS"]
CHAMPLAIN_LLL_FT = 93.0     # low lake level above mean sea level, the charts' plane of reference (Coast Pilot 6, ch. 14)


def _enc_cells(box_ll):
    """Names of the NOAA ENC cells of harbour and approach scale (1:80,000 and larger) whose coverage meets box_ll."""
    import xml.etree.ElementTree as ET
    os.makedirs(ENC_DIR, exist_ok=True)
    p = f"{ENC_DIR}/ENCProdCat.xml"
    try:
        if not os.path.exists(p):
            r = netfetch.get(ENC_CAT, timeout=300, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
            r.raise_for_status()
            with open(p + ".part", "wb") as f:
                f.write(r.content)
            os.replace(p + ".part", p)
        w, s, e, n = box_ll
        out = []
        for cell in ET.parse(p).getroot().iter("cell"):
            scale = float(cell.findtext("cscale") or 0)
            if not (0 < scale <= 80000) or (cell.findtext("status") or "Active") != "Active":
                continue
            lat = [float(v.text) for v in cell.iter("lat")]
            lon = [float(v.text) for v in cell.iter("long")]
            if lat and min(lat) < n and max(lat) > s and min(lon) < e and max(lon) > w:
                out.append(cell.findtext("name"))
        if out:
            return sorted(out)
    except Exception as ex:
        print(f"  NOAA ENC catalogue not read ({str(ex)[:80]}); the cells listed on 2026-11-21 are used")
    return CHAMPLAIN_CELLS


def noaa_champlain(lk, bounds_ll):
    """(contour rows, {lid: depth facts}) for Lake Champlain from NOAA's electronic navigational charts (NOAA ENC):
    the charts' soundings (SOUNDG; metres below the chart datum, low lake level) with the vertices of their 6 and 12 ft
    depth curves (DEPCNT) and the charted shoreline at 0 (the edge of the depth areas, DEPARE), gridded over the
    whole lake (50 m, linear) into contours. The lake's deepest sounding and mean depth are the whole lake's, whichever
    map shows part of it; the contours are cut to the lake as this area stores it."""
    me = lk[lk["name"].fillna("").eq("Lake Champlain")]
    if not len(me):
        return [], {}
    os.environ["OGR_S57_OPTIONS"] = ("SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON,UPDATES=APPLY,RETURN_PRIMITIVES=OFF,"
                                     "RETURN_LINKAGES=OFF,LNAM_REFS=OFF")
    snd, cnt, are = [], [], []
    for cell in _enc_cells(CHAMPLAIN_LL):
        z = f"{ENC_DIR}/{cell}.zip"
        try:
            if not os.path.exists(z):
                r = netfetch.get(ENC_ZIP.format(cell), timeout=300, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
                r.raise_for_status()
                with open(z + ".part", "wb") as f:
                    f.write(r.content)
                os.replace(z + ".part", z)
            src = f"/vsizip/{z}/ENC_ROOT/{cell}/{cell}.000"
            snd.append(gpd.read_file(src, layer="SOUNDG")[["DEPTH", "geometry"]])
            cnt.append(gpd.read_file(src, layer="DEPCNT")[["VALDCO", "geometry"]])
            are.append(gpd.read_file(src, layer="DEPARE")[["geometry"]])
        except Exception as ex:
            print(f"  NOAA ENC cell {cell} not read: {str(ex)[:100]}")
    if not snd:
        return [], {}
    w, s, e, n = CHAMPLAIN_LL
    ll = lambda parts: gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326).cx[w:e, s:n].to_crs(CRS)
    snd, cnt, are = ll(snd), ll(cnt), ll(are)
    snd = snd[snd.DEPTH.notna() & (snd.DEPTH >= 0)]
    water = shapely.union_all(shapely.make_valid(are.geometry.values)).buffer(1).buffer(-1)
    water = max(getattr(water, "geoms", [water]), key=lambda g: g.area)          # the lake, not a pond beside it
    pts = [np.c_[snd.geometry.x, snd.geometry.y, snd.DEPTH]]
    for g, v in zip(cnt.geometry, cnt.VALDCO):
        if pd.notna(v) and g is not None and not g.is_empty:
            xy = shapely.get_coordinates(shapely.segmentize(g, 50.0))
            pts.append(np.c_[xy, np.full(len(xy), float(v))])
    sh = shapely.get_coordinates(shapely.segmentize(water.boundary, 50.0))
    pts.append(np.c_[sh, np.zeros(len(sh))])
    P = pd.DataFrame(np.vstack(pts), columns=list("xyz")).round({"x": 1, "y": 1}).groupby(["x", "y"], as_index=False).z.mean().values
    res = 50.0
    x0, y0, x1, y1 = water.bounds
    W, H = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
    T = from_origin(x0, y1, res, res)
    inside = features.geometry_mask([water], out_shape=(H, W), transform=T, invert=True)
    from scipy.interpolate import LinearNDInterpolator
    rr, cc = np.nonzero(inside)
    z = np.full((H, W), np.nan)
    z[rr, cc] = LinearNDInterpolator(P[:, :2], P[:, 2])(x0 + (cc + 0.5) * res, y1 - (rr + 0.5) * res)
    d_ft = z / FT
    dmax = float(snd.DEPTH.max()) / FT
    mean_ft = float(np.nanmean(d_ft))
    deep = snd.loc[snd.DEPTH.idxmax()].geometry
    deep_ll = gpd.GeoSeries([deep], crs=CRS).to_crs(4326).iloc[0]
    print(f"  Lake Champlain: {len(snd):,} chart soundings in {len(set(_enc_cells(CHAMPLAIN_LL)))} cells; gridded {np.isfinite(z).sum() * res * res / 1e6:,.0f} km2, "
          f"{np.nansum(z) * res * res / 1e9:.1f} km3 (the Lake Champlain Basin Program gives 1,127 km2 and 25.8 km3); deepest sounding "
          f"{dmax:.0f} ft at {deep_ll.y:.4f}, {deep_ll.x:.4f}; mean {mean_ft:.0f} ft below low lake level")
    if not (300 <= dmax <= 420):          # the lake's deepest point is about 400 ft: anything else is a unit or datum error
        print("  Lake Champlain: the deepest sounding isn't near 400 ft; left out")
        return [], {}
    import contourpy
    step = step_ft(dmax)
    src = "NOAA chart soundings (NOAA ENC, lake surveys of 1870-1939)"
    lid, lake = me.lid.iloc[0], shapely.make_valid(me.geometry.iloc[0]).buffer(30)
    gen = contourpy.contour_generator(z=d_ft, name="serial")
    rows = []
    for lv in np.arange(step, dmax, step):
        for ln in gen.lines(lv):
            if len(ln) >= 3:
                geo = shapely.simplify(shapely.LineString(np.column_stack([x0 + (ln[:, 0] + 0.5) * res, y1 - (ln[:, 1] + 0.5) * res])), 15.0)
                for part in shapely.get_parts(shapely.intersection(geo, lake)):
                    if part.geom_type == "LineString" and part.length >= 300:
                        rows.append(dict(lid=lid, depth_ft=float(lv), depth_m=round(lv * FT, 1), major=bool(lv % (step * 2) == 0),
                                         src=src, geometry=part))
    facts = {lid: dict(max_ft=dmax, mean_ft=mean_ft, src=src,
                       note=f"{len(snd):,} soundings with the charts' {ft(1.8)} and {ft(3.6)} curves; depth below low lake level "
                            f"({CHAMPLAIN_LLL_FT:g} ft above sea level, the chart datum; the lake usually stands 2 to 3 ft higher); "
                            f"from NOAA ENC charts (charts.noaa.gov, user agreement: {ENC_TERMS}); not for navigation")}
    return rows, facts


# the surveys that cover the area: sources.BATHYMETRY's coverage tests, worked out by 00_area.py (the 12 maps of
# 2026-11-22 keep the lists typed in for them, sources.HAND, until the new-area plan's B2)
SURVEYS = {f.__name__: f for f in (ct_contours, vt_soundings, noaa_champlain, usgs_little_rock, dcnr_bands, usgs_chambers)}
assert set(SURVEYS) == set(sources.BATHYMETRY)
ADAPTERS = [SURVEYS[n] for n in sources.pick("bathymetry", AREA, WORKED_OUT.get("bathymetry", ()))]


def main():
    if not ADAPTERS:
        print(f"bathymetry: no published survey to read for {AREA}")
        return
    if not os.path.exists(LAKES):
        print(f"bathymetry: no {LAKES} yet (run 05d_lakes.py)")
        return
    lk = gpd.read_file(LAKES)
    # what 05d_lakes.py found, kept beside it the first time, so that a second run starts from that and not from its
    # own last result (05d_lakes.py writes lakes.gpkg afresh, without these columns)
    KEEP = ["depth_max_m", "depth_mean_m", "depth_src", "depth_note", "name", "name_src"]
    if "depth_src_05d" in lk:
        for c in KEEP:
            lk[c] = lk[f"{c}_05d"]
    else:
        for c in KEEP:
            lk[f"{c}_05d"] = lk[c]
    lk["bathymetry"] = None
    boxes = gpd.GeoSeries([box(*v["bbox"]) for v in REGIONS.values()], crs=CRS)
    bb = tuple(boxes.buffer(3000).to_crs(4326).total_bounds)
    rows, facts = [], {}
    for f in ADAPTERS:
        r_, f_ = f(lk, bb)
        rows += r_
        facts.update(f_)
    if rows:
        out = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        out = areaclip.cut(out[~out.geometry.is_empty])       # an area that stops at a state line (areaclip.py)
        out.to_file(OUT + ".tmp", driver="GPKG")
        os.replace(OUT + ".tmp", OUT)
    for lid, f in facts.items():
        i = lk.index[lk.lid == lid][0]
        new = round(f["max_ft"] * FT, 1)
        old, old_src = lk.depth_max_m.iat[i], lk.depth_src.iat[i]
        note = f["note"]
        same = isinstance(old_src, str) and old_src.split()[0] == f["src"].split()[0]   # e.g. DCNR's map and its bands
        if pd.notna(old) and old > new + 0.5:          # a deeper sounding already on record stays the maximum
            note += "" if same else f"; {ft(old)} by {old_src} is deeper"
        else:
            if pd.notna(old) and isinstance(old_src, str):
                note += f"; also {ft(old)} by {old_src}"
            lk.loc[i, ["depth_max_m", "depth_src"]] = [new, f["src"]]
        if f["mean_ft"] is not None:
            lk.loc[i, "depth_mean_m"] = round(f["mean_ft"] * FT, 1)
        lk.loc[i, "depth_note"] = note
        lk.loc[i, "bathymetry"] = f["src"]
        # NHD has no name for it: the survey's, unless a lake beside it has that name already (the survey's contours
        # run into an unnamed cove of Pachaug Pond and of Morey Pond)
        sn = f.get("survey_name")
        if not isinstance(lk.name.iat[i], str) and isinstance(sn, str):
            near_ = lk[lk.geometry.distance(lk.geometry.iat[i]) <= 200]
            if not near_.name.fillna("").str.lower().eq(sn.lower()).any():
                lk.loc[i, ["name", "name_src"]] = [sn, "survey"]
    lk.to_file(LAKES + ".tmp", driver="GPKG")
    os.replace(LAKES + ".tmp", LAKES)
    print(f"bathymetry: {len(facts)} lakes surveyed, {len(rows)} contour lines -> {OUT}")
    for lid, f in sorted(facts.items(), key=lambda kv: -kv[1]["max_ft"]):
        nm = lk.name[lk.lid == lid].iat[0]
        print(f"  {nm if isinstance(nm, str) else lid}: max {f['max_ft']:.0f} ft" +
              (f", mean {f['mean_ft']:.0f} ft" if f["mean_ft"] else "") + f" ({f['src']})")


if __name__ == "__main__":
    main()
