"""Cold-water indicators from terrain: summer direct-sun hours on the water and the aspect of the canyon walls.

  - sun_hours: hours of direct sun at the channel on SUN_DATE (mid-July, peak water temperature). The horizon is
    traced from the 10 m DEM in N_AZ directions out to RAY_M; the sun is visible when its altitude clears the
    horizon at its azimuth. Trees and canyon-bottom vegetation are not modelled, so this is an upper bound.
  - northness: mean of cos(aspect) x sin(slope) over the terrain within ASPECT_M of the channel, i.e. which way
    that side of the mountain faces. (At canyon-wall scale the two walls face opposite ways and cancel.)
    +1 = steep north-facing mountainside (cool), -1 = steep south-facing (hot), 0 = flat or east/west.
Run with REGION=<name>. Writes output/<region>/sun_streams.csv and sun_drops.csv.
"""
import datetime as dt, numpy as np, pandas as pd, geopandas as gpd, rasterio
from config import *

SUN_DATE = dt.date(2026, 7, 15)
N_AZ, RAY_M, RAY_STEP = 36, 3000, 30
STEP_MIN = 10
ASPECT_M = 1000
EYE = 1.0          # m above the water surface
PTS_PER_REACH = 4

src = rasterio.open(f"{RAW}/dem_10m.tif")
z = src.read(1).astype("float32")
z[z < -1000] = np.nan
H, W = z.shape
inv = ~src.transform
lat0 = np.radians(gpd.GeoSeries([gpd.points_from_xy([XMIN], [YMIN])[0]], crs=CRS).to_crs(4326).iloc[0].y)

# ---- sun path on SUN_DATE (solar time) ----
n = SUN_DATE.timetuple().tm_yday
decl = np.radians(23.44) * np.sin(np.radians(360 / 365 * (284 + n)))
hours = np.arange(4, 20, STEP_MIN / 60)
h = np.radians((hours - 12) * 15)
alt = np.arcsin(np.sin(lat0) * np.sin(decl) + np.cos(lat0) * np.cos(decl) * np.cos(h))
az = (np.degrees(np.arctan2(np.sin(h), np.cos(h) * np.sin(lat0) - np.tan(decl) * np.cos(lat0))) + 180) % 360
up = alt > 0
alt, az = alt[up], az[up]
print(f"{LABEL}: day length {up.sum() * STEP_MIN / 60:.1f} h, max sun altitude {np.degrees(alt.max()):.0f} deg")

# ---- hillslope aspect / slope ----
gy, gx = np.gradient(np.nan_to_num(z, nan=np.nanmean(z)), RES)
slope_ang = np.arctan(np.hypot(gx, gy))
aspect = np.arctan2(-gx, gy)  # radians from north, clockwise; rows increase southward so dz/dy flips
northness_cell = np.cos(aspect) * np.sin(slope_ang)

def horizon(rc):
    """Horizon elevation angle (radians) at each point for N_AZ azimuths."""
    r0, c0 = rc[:, 0], rc[:, 1]
    z0 = z[r0, c0] + EYE
    d = np.arange(RAY_STEP, RAY_M + 1, RAY_STEP, dtype="float32")
    out = np.zeros((len(rc), N_AZ), "float32")
    for k, a in enumerate(np.radians(np.arange(0, 360, 360 / N_AZ))):
        rr = np.rint(r0[:, None] - np.cos(a) * d / RES).astype(int)
        cc = np.rint(c0[:, None] + np.sin(a) * d / RES).astype(int)
        ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        zz = np.where(ok, z[np.clip(rr, 0, H - 1), np.clip(cc, 0, W - 1)], np.nan)
        ang = np.arctan((zz - z0[:, None]) / d)
        out[:, k] = np.nan_to_num(np.nanmax(np.where(np.isnan(ang), -np.pi / 2, ang), axis=1), nan=0)
    return out

def sun_hours(rc, chunk=4000):
    res = np.zeros(len(rc))
    azg = np.arange(0, 360, 360 / N_AZ)
    for s in range(0, len(rc), chunk):
        hz = horizon(rc[s:s + chunk])
        # horizon at each sun azimuth (linear interpolation, wrapping at 360)
        pos = az / (360 / N_AZ)
        i0 = np.floor(pos).astype(int) % N_AZ
        f = pos - np.floor(pos)
        hz_sun = hz[:, i0] * (1 - f) + hz[:, (i0 + 1) % N_AZ] * f
        res[s:s + chunk] = (alt[None, :] > hz_sun).sum(axis=1) * STEP_MIN / 60
    return res

from scipy.ndimage import uniform_filter
northness_area = uniform_filter(northness_cell.astype("float32"), size=int(2 * ASPECT_M / RES) + 1, mode="nearest")
def wall_northness(rc):
    return northness_area[rc[:, 0], rc[:, 1]]

def to_rc(xs, ys):
    c, r = inv * (np.asarray(xs), np.asarray(ys))
    return np.c_[np.clip(r.astype(int), 0, H - 1), np.clip(c.astype(int), 0, W - 1)]

streams = gpd.read_file(f"{OUT}/streams_scored.gpkg").to_crs(CRS)
drops = gpd.read_file(f"{OUT}/waterfall_candidates.gpkg")
fr = (np.arange(PTS_PER_REACH) + 0.5) / PTS_PER_REACH
pts = [g.interpolate(f, normalized=True) for g in streams.geometry for f in fr]
rc_s = to_rc([p.x for p in pts], [p.y for p in pts])
pool = gpd.GeoSeries(gpd.points_from_xy(drops.pool_lon, drops.pool_lat), crs=4326).to_crs(CRS)
rc_d = to_rc(pool.x, pool.y)  # the pool is where the fish (and the water temperature) matter

sh_s, sh_d = sun_hours(rc_s), sun_hours(rc_d)
nn_s, nn_d = wall_northness(rc_s), wall_northness(rc_d)
day = up.sum() * STEP_MIN / 60
ts = pd.DataFrame({"sid": streams.sid,
                   "sun_hours": sh_s.reshape(-1, PTS_PER_REACH).mean(axis=1).round(1),
                   "northness": nn_s.reshape(-1, PTS_PER_REACH).mean(axis=1).round(2)})
td = pd.DataFrame({"did": drops.did, "sun_hours": sh_d.round(1), "northness": nn_d.round(2)})
ts["shade_pct"] = (100 * (1 - ts.sun_hours / day)).round(0)
td["shade_pct"] = (100 * (1 - td.sun_hours / day)).round(0)
ts.to_csv(f"{OUT}/sun_streams.csv", index=False)
td.to_csv(f"{OUT}/sun_drops.csv", index=False)
print(f"reaches: sun hours median {ts.sun_hours.median():.1f} (5–95%: {ts.sun_hours.quantile(.05):.1f}–"
      f"{ts.sun_hours.quantile(.95):.1f}) of {day:.1f} daylight | northness 5/50/95%: "
      f"{ts.northness.quantile(.05):+.2f} / {ts.northness.median():+.2f} / {ts.northness.quantile(.95):+.2f}")
