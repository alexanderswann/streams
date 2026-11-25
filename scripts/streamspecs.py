"""Stream specs: the few figures bluelining anglers compare small trout streams by (the user, 2026-11-25, after an
r/bluelining thread on an ArcGIS map of NHDPlus High Resolution's flowlines): mean annual flow, velocity, slope, stream
order, drainage area and the elevation of the reach's lower end. 06_map.py puts two of them on each drawn reach for the
popups (map_specs.js shows them in one line, and finds streams with similar ones); the other four the reaches carry
already (gradient_pct, the Strahler order, area_full_km2), or the page works out (the velocity). Nothing is shown that
the map doesn't have: a reach with no flow estimate shows none, and neither its velocity.

  q   mean annual flow (cfs): NHDPlus V2's gauge-adjusted mean annual flow (EROM's QE_MA, 1971-2000, on every NHDPlus
      line in the country) of the line 05b_flow.py matched the reach to (flow_streams.csv's comid: its own line, or the
      first one downstream for a creek NHDPlus has none for), scaled to the reach's drainage as 05b scales that line's
      summer flows: x the reach's full drainage / the line's, at most x 1.2. So it is about the reach in the way the
      popup's summer low flow is. Every area has the table (02b_download_flow.py: nhdplus_v2.gpkg's qe_ma), California
      too, where the summer flows come from TNC's model instead: there NHDPlus's mean flow, with the dams and their
      reservoirs in it as its gauges saw them, is the mean annual flow shown.
  le  lower elevation (m): the DEM (dem_10m.tif) at the reach's own lowest cell (05_score.py's own_x / own_y, where its
      gradient is measured to). A piece the map step draws through a break (draw_through: not a reach of its own) at
      its own last point.
  velocity (ft/s), on the pages: NHDPlus's own method (EROM's VE_MA, Jobson 1996, "Prediction of traveltime and
      longitudinal dispersion in rivers and streams", USGS WRIR 96-4013) on the reach's own figures: velocity() below.
      With NHDPlus's inputs it gives NHDPlus's figure (Moccasin Creek, Georgia: 1.298 ft/s, NHDPlus 1.298).
"""
import os, numpy as np, pandas as pd, rasterio

RATIO_MAX = 1.2          # 05b_flow.py's evidence(): a line's flows scaled to a reach's drainage at most x 1.2
G = 9.80665
CFS = 0.028316846592     # m3/s in a cfs


def nhdplus_flows(flow_dir):
    """comid -> (qe_ma cfs, totdasqkm) from 02b_download_flow.py's NHDPlus V2 table (None where it isn't there)."""
    p = f"{flow_dir}/nhdplus_v2.gpkg"
    if not os.path.exists(p):
        return None
    import pyogrio
    v2 = pyogrio.read_dataframe(p, columns=["comid", "qe_ma", "totdasqkm"], read_geometry=False)
    return v2.drop_duplicates("comid").set_index("comid")


def mean_flow(comid, area_km2, v2):
    """Mean annual flow (cfs) for reaches matched to NHDPlus lines `comid` (NaN: none), with drainage `area_km2`."""
    q = np.full(len(comid), np.nan)
    if v2 is None:
        return q
    c = pd.to_numeric(pd.Series(comid), errors="coerce")
    ok = c.notna().to_numpy()
    k = c[ok].astype("int64")
    qe = k.map(v2.qe_ma).to_numpy(float)
    da = k.map(v2.totdasqkm).to_numpy(float)
    a = np.asarray(area_km2, float)[ok]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.minimum(a / da, RATIO_MAX)
        v = np.where((qe > 0) & (da > 0) & (a > 0), qe * r, np.nan)
    q[ok] = v
    return q


def round_cfs(v):
    """As the popups show a flow (06_map.py's cfs()): whole cfs from 10, tenths from 1, hundredths under it."""
    v = np.asarray(v, float)
    return np.where(v >= 10, np.round(v), np.where(v >= 1, np.round(v, 1), np.round(v, 2)))


def lower_elev(xy_by_range, dem_path):
    """{range: (x, y) arrays in the area's CRS} -> {range: DEM metres at those points, NaN off the DEM or nodata}."""
    out = {}
    for r, (x, y) in xy_by_range.items():
        x, y = np.asarray(x, float), np.asarray(y, float)
        z = np.full(len(x), np.nan)
        p = dem_path(r)
        if len(x) and os.path.exists(p):
            with rasterio.open(p) as src:
                ok = np.isfinite(x) & np.isfinite(y)
                if ok.any():
                    v = np.array([s[0] for s in src.sample(zip(x[ok], y[ok]))], float)
                    if src.nodata is not None:
                        v[v == src.nodata] = np.nan
                    v[v < -1000] = np.nan
                    z[ok] = v
        out[r] = z
    return out


def velocity(q_cfs, area_km2, slope_pct):
    """Velocity (ft/s) at the mean annual flow, as NHDPlus works it out (EROM, Jobson 1996): the peak-concentration
    velocity 0.094 + 0.0143 Da'^0.919 S^0.159 Q / Da (m/s), Da' = Da^1.25 sqrt(g) / Q, at Q the mean annual flow
    (so Q/Qa = 1), Da the drainage (m2), S the slope. map_specs.js does the same on the pages."""
    Q = np.asarray(q_cfs, float) * CFS
    Da = np.asarray(area_km2, float) * 1e6
    S = np.asarray(slope_pct, float) / 100
    with np.errstate(divide="ignore", invalid="ignore"):
        v = 0.094 + 0.0143 * (Da ** 1.25 * np.sqrt(G) / Q) ** 0.919 * S ** 0.159 * Q / Da
    return np.where((Q > 0) & (Da > 0) & (S > 0), v / 0.3048, np.nan)
