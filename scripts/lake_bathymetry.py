"""Measured lake bathymetry: depth contours and each surveyed lake's depth, from the agencies' own surveys. Modelled
depths (GLOBathy, HydroLAKES) are never used; a lake no survey covers keeps the depth 05d_lakes.py found, or none.
AREA only; run after 05d_lakes.py (it updates lakes.gpkg) and before 06_map.py.

Surveys, by area (checked 2026-11-19):
  ne_ct       CT DEEP lake bathymetry contours (Lake_Bathymetry_Contours): depth-finder, GPS and lead-line surveys of
              1959-2002, in feet. 24 lakes in the area. The deepest contour is a lower bound on the lake's depth.
  central_vt  Vermont ANR bathymetric soundings (BiobaseLakeBathymetry, compiled 2020-08-12): 2.4 million sonar
              points in 66 lakes, depth in feet below the water level of the survey. 15 lakes in the area. Each lake's
              points are gridded (5 m, linear, the shore at 0) into contours, its mean depth and its deepest sounding.
  jackson     none published (see lakedata.py)
Each contour line belongs to the lake it lies in, each sounding to the lake it falls in: no name matching.
Writes data/derived/<area>/_shared/lake_depth.gpkg (lid, depth_ft, depth_m, major, src).
"""
import os, re, json, requests, numpy as np, pandas as pd, geopandas as gpd, shapely
from rasterio import features
from rasterio.transform import from_origin
from config import AREA, REGIONS, CRS, SHARED, SHARED_DERIVED
from shapely.geometry import box

FT = 0.3048
LAKES = os.environ.get("LAKES_OUT", f"{SHARED_DERIVED}/lakes.gpkg")
OUT = f"{SHARED_DERIVED}/lake_depth.gpkg"
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
        src = f"CT DEEP bathymetric survey ({how}{', ' + str(y) if y else ''})"
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
        r = requests.get(VT_URL, timeout=600, headers={"User-Agent": "stream-analysis/0.1 (personal GIS project)"})
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
        src = f"Vermont ANR sonar soundings ({d.lake.iat[0].title()}; compiled 2020)"
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


ADAPTERS = {"ne_ct": [ct_contours], "central_vt": [vt_soundings]}


def main():
    if AREA not in ADAPTERS:
        print(f"bathymetry: no published survey to read for {AREA}")
        return
    if not os.path.exists(LAKES):
        print(f"bathymetry: no {LAKES} yet (run 05d_lakes.py)")
        return
    lk = gpd.read_file(LAKES)
    boxes = gpd.GeoSeries([box(*v["bbox"]) for v in REGIONS.values()], crs=CRS)
    bb = tuple(boxes.buffer(3000).to_crs(4326).total_bounds)
    rows, facts = [], {}
    for f in ADAPTERS[AREA]:
        r_, f_ = f(lk, bb)
        rows += r_
        facts.update(f_)
    if rows:
        out = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
        out = out[~out.geometry.is_empty]
        out.to_file(OUT + ".tmp", driver="GPKG")
        os.replace(OUT + ".tmp", OUT)
    for lid, f in facts.items():
        i = lk.index[lk.lid == lid][0]
        new = round(f["max_ft"] * FT, 1)
        old, old_src = lk.depth_max_m.iat[i], lk.depth_src.iat[i]
        note = f["note"]
        if pd.notna(old) and old > new + 0.5:          # a deeper sounding already on record stays the maximum
            note += f"; {old:g} m by {old_src} is deeper"
        else:
            if pd.notna(old) and isinstance(old_src, str):
                note += f"; also {old:g} m by {old_src}"
            lk.loc[i, ["depth_max_m", "depth_src"]] = [new, f["src"]]
        if f["mean_ft"] is not None:
            lk.loc[i, "depth_mean_m"] = round(f["mean_ft"] * FT, 1)
        lk.loc[i, "depth_note"] = note
        lk.loc[i, "bathymetry"] = f["src"]
        if not isinstance(lk.name.iat[i], str) and isinstance(f.get("survey_name"), str):   # NHD has no name for it
            lk.loc[i, ["name", "name_src"]] = [f["survey_name"], "survey"]
    if "bathymetry" not in lk:
        lk["bathymetry"] = None
    lk.to_file(LAKES + ".tmp", driver="GPKG")
    os.replace(LAKES + ".tmp", LAKES)
    print(f"bathymetry: {len(facts)} lakes surveyed, {len(rows)} contour lines -> {OUT}")
    for lid, f in sorted(facts.items(), key=lambda kv: -kv[1]["max_ft"]):
        nm = lk.name[lk.lid == lid].iat[0]
        print(f"  {nm if isinstance(nm, str) else lid}: max {f['max_ft']:.0f} ft" +
              (f", mean {f['mean_ft']:.0f} ft" if f["mean_ft"] else "") + f" ({f['src']})")


if __name__ == "__main__":
    main()
