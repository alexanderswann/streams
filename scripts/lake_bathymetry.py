"""Measured lake bathymetry: depth contours and each surveyed lake's maximum and mean depth, from the surveys listed in
SOURCES (sonar, echo-sounder or sounding surveys published by agencies and universities). Modelled depths (GLOBathy,
HydroLAKES) are never used: a lake no survey covers keeps only the depth its fisheries agency measured, or none.
AREA only; run after 05d_lakes.py and before 06_map.py.

Each source is one of:
  contours  depth contour lines with a depth (or bed-elevation) field
  points    soundings (depth or bed elevation per point), gridded inside the lake with the shore at depth 0
  grid      a depth or bed-elevation raster
Bed elevations become depths below the water level of the survey (`level_m`), or below the lake's lidar level.
Downloads are cached in data/raw/<area>/_shared/bathymetry/. Writes data/derived/<area>/_shared/lake_depth.gpkg
(lid, depth_m, src: the contours the maps draw) and updates lakes.gpkg's depth columns for the lakes a survey covers.
"""
import os, io, re, json, zipfile, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from rasterio import features
from rasterio.transform import from_origin
from config import AREA, CRS, SHARED, SHARED_DERIVED

FT = 0.3048
UA = {"User-Agent": "stream-analysis/0.1 (personal GIS project)"}
DL = f"{SHARED}/bathymetry"
LAKES = os.environ.get("LAKES_OUT", f"{SHARED_DERIVED}/lakes.gpkg")
OUT = f"{SHARED_DERIVED}/lake_depth.gpkg"

# Per area: the measured surveys. Each: lake (name as in lakes.gpkg), kind, url (or path), member (file inside a zip,
# or layer), field (depth or elevation), units ("m" / "ft"), value ("depth" or "elevation"), level_m (water level of
# the survey, for elevations; default the lake's lidar level), src (who, how, when: shown on the map).
SOURCES = {
    "jackson": [],
}


def fetch(url):
    """A download, cached by its file name; returns the local path (a zip is extracted beside it)."""
    os.makedirs(DL, exist_ok=True)
    p = f"{DL}/{re.sub(r'[^A-Za-z0-9._-]', '_', url.split('/')[-1].split('?')[0])}"
    if not os.path.exists(p):
        r = requests.get(url, headers=UA, timeout=600)
        r.raise_for_status()
        with open(p + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(p + ".tmp", p)
    if p.lower().endswith(".zip"):
        d = p[:-4]
        if not os.path.isdir(d):
            zipfile.ZipFile(p).extractall(d)
        return d
    return p


def interval(dmax):
    return 1 if dmax < 12 else 2 if dmax < 30 else 5 if dmax < 80 else 10


def contour_grid(z, T, levels):
    """Contour lines (map coordinates) of a depth grid at the given depths."""
    import contourpy
    gen = contourpy.contour_generator(z=np.where(np.isfinite(z), z, np.nan), name="serial")
    out = []
    for lv in levels:
        for ln in gen.lines(lv):
            if len(ln) >= 2:
                xs, ys = T * (ln[:, 0] + 0.5, ln[:, 1] + 0.5)
                out.append((lv, shapely.LineString(np.column_stack([xs, ys]))))
    return out


def grid_from_points(pts, depth, lake, res=5.0):
    """Linear interpolation of soundings inside the lake, with the shoreline at depth 0."""
    from scipy.interpolate import griddata
    shore = np.asarray(shapely.segmentize(lake.boundary, res).coords if lake.boundary.geom_type == "LineString"
                       else np.vstack([np.asarray(shapely.segmentize(b, res).coords) for b in lake.boundary.geoms]))
    xy = np.vstack([np.column_stack([pts.x, pts.y]), shore[:, :2]])
    v = np.r_[depth, np.zeros(len(shore))]
    x0, y0, x1, y1 = lake.bounds
    T = from_origin(x0, y1, res, res)
    W, H = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
    cx, cy = T * (np.arange(W) + 0.5, np.zeros(W))
    _, ry = T * (np.zeros(H), np.arange(H) + 0.5)
    gx, gy = np.meshgrid(cx, ry)
    z = griddata(xy, v, (gx, gy), method="linear")
    inside = features.geometry_mask([lake], out_shape=z.shape, transform=T, invert=True)
    return np.where(inside, z, np.nan), T


def main():
    src = SOURCES.get(AREA, [])
    if not src or not os.path.exists(LAKES):
        print(f"bathymetry: no measured surveys listed for {AREA}" if not src else f"bathymetry: no {LAKES} yet")
        return
    lk = gpd.read_file(LAKES)
    lines, upd = [], {}
    for s in src:
        hit = lk[lk.name == s["lake"]]
        if len(hit) != 1:
            print(f"  {s['lake']}: {len(hit)} lakes of that name; skipped")
            continue
        r = hit.iloc[0]
        path = fetch(s["url"])
        if os.path.isdir(path):
            path = os.path.join(path, s["member"])
        k = 1.0 if s.get("units", "m") == "m" else FT
        level = s.get("level_m", r.water_level_m if pd.notna(r.water_level_m) else r.elev_m)
        if s["kind"] in ("contours", "points"):
            g = gpd.read_file(path, layer=s.get("layer")).to_crs(CRS)
            val = pd.to_numeric(g[s["field"]], errors="coerce") * k
            depth = (level - val) if s.get("value") == "elevation" else val.abs()
            if s["kind"] == "contours":
                g = g.assign(depth_m=depth.round(1)).dropna(subset=["depth_m"])
                g = g[g.depth_m > 0]
                g["geometry"] = g.geometry.intersection(r.geometry.buffer(25))
                lines += [(r.lid, d, gg, s["src"]) for d, gg in zip(g.depth_m, g.geometry) if not gg.is_empty]
                dmax = float(depth.max())
                upd[r.lid] = dict(depth_max_m=round(dmax, 1), depth_mean_m=np.nan, depth_src=s["src"],
                                  depth_note="contours, maximum from the deepest contour")
                continue
            z, T = grid_from_points(g.geometry, depth.values, r.geometry)
        else:   # grid
            with rasterio.open(path) as d:
                a = d.read(1, masked=True).astype(float).filled(np.nan) * k
                T = d.transform
            z = (level - a) if s.get("value") == "elevation" else np.abs(a)
            inside = features.geometry_mask([r.geometry], out_shape=z.shape, transform=T, invert=True)
            z = np.where(inside & (z > 0), z, np.nan)
        dmax = float(np.nanmax(z))
        step = interval(dmax)
        lines += [(r.lid, lv, ln, s["src"]) for lv, ln in contour_grid(z, T, np.arange(step, dmax, step))]
        upd[r.lid] = dict(depth_max_m=round(dmax, 1), depth_mean_m=round(float(np.nanmean(z)), 1), depth_src=s["src"],
                          depth_note=f"surveyed; contours every {step} m")
        print(f"  {s['lake']}: max {dmax:.1f} m, mean {np.nanmean(z):.1f} m ({s['src']})")
    if lines:
        out = gpd.GeoDataFrame([dict(lid=a, depth_m=b, src=d) for a, b, _, d in lines], geometry=[c for _, _, c, _ in lines], crs=CRS)
        out.to_file(OUT + ".tmp", driver="GPKG")
        os.replace(OUT + ".tmp", OUT)
    for lid, u in upd.items():
        i = lk.index[lk.lid == lid][0]
        for c, v in u.items():
            lk.loc[i, c] = v
    lk.to_file(LAKES + ".tmp", driver="GPKG")
    os.replace(LAKES + ".tmp", LAKES)
    print(f"bathymetry: {len(upd)} lakes surveyed, {len(lines)} contour lines -> {OUT}")


if __name__ == "__main__":
    main()
