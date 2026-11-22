"""Read-only: drops of a scratch build that start at the outlet of a dammed lake of the lakes layer (top within NEAR m
of its outline, top no higher than the lake's level + 3 m), by status. AREA=<area> damlake.py <root> [NEAR]"""
import sys, os
ROOT = sys.argv[1]; NEAR = float(sys.argv[2]) if len(sys.argv) > 2 else 100
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
wc = pd.concat([gpd.read_file(f"{config.out_dir(r)}/waterfall_candidates.gpkg").to_crs(config.CRS) for r in config.REGIONS], ignore_index=True)
wc = gpd.GeoDataFrame(wc, crs=config.CRS)
lk = gpd.read_file(f"{config.SHARED_DERIVED}/lakes.gpkg").to_crs(config.CRS)
reg = lk[lk.regulated.fillna(False).astype(bool) | lk.ftype.eq("reservoir")][["name", "ha", "elev_m", "geometry"]]
j = gpd.sjoin_nearest(wc[["did", "status", "kind", "stream", "drop_m", "area_km2", "elev_m", "dam_m", "known_fall_m", "lat", "lon", "geometry"]], reg.rename(columns={"elev_m": "lake_elev", "name": "lake"}),
                      max_distance=NEAR, distance_col="lake_m", how="inner")
j = j[~j.index.duplicated()]
out = j[(j.elev_m >= j.lake_elev - 3) & (j.elev_m <= j.lake_elev + 6)]
inl = j[~((j.elev_m >= j.lake_elev - 3) & (j.elev_m <= j.lake_elev + 6))]
print(f"{config.AREA:15s} drops {len(wc)} | within {NEAR:.0f} m of a dammed lake: {len(j)}: at its outlet (top at or below the lake's level) {len(out)} {out.status.value_counts().to_dict()}; above its level {len(inl)} {inl.status.value_counts().to_dict()}")
if "-v" in sys.argv:
    pd.set_option("display.width", 250)
    show = out[~out.status.isin(["dam / weir", "steep reach", "likely DEM artifact"])]
    print(show.sort_values("drop_m", ascending=False)[["status", "stream", "drop_m", "area_km2", "elev_m", "lake", "lake_elev", "lake_m", "dam_m", "known_fall_m", "lat", "lon"]].head(30).to_string())
