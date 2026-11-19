"""Long profiles (elevation vs. distance downstream) for every named creek, for output/profiles.html.

Creeks come from the NHD named flowlines: each name's segments are merged, split into connected pieces, and the
longest path through each piece is the creek's main stem. Elevation along it is the channel bottom: the lowest
hydro-conditioned DEM cell within BOTTOM_M (absorbs the small offsets between NHD lines and the 10 m DEM),
forced non-increasing downstream. Drops, mapped falls, gauges and per-reach attributes (fish score, burn, trout
water, critical habitat) are snapped onto the profile. Run after 06_map.py (it reads the merged CSV exports).
Writes output/profiles_data.js (window.PROFILE_DATA, loads from file:// without a server).
"""
import json, re, numpy as np, pandas as pd, geopandas as gpd, rasterio, networkx as nx
from scipy.ndimage import minimum_filter, maximum_filter
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union
from config import REGIONS, CRS, ROOT, MAP_OUT, RES, raw_dir, derived_dir

MIN_KM = 2.0          # skip shorter creeks
STEP_M = 40           # spacing along the profile
BOTTOM_M = 20         # channel-bottom search radius around the NHD line
AREA_M = 60           # drainage-area search radius (NHD lines can sit a few cells off the D8 channel)
GRAD_HALF_M = 60      # gradient over +/- this distance
SNAP_DROP, SNAP_FALL, SNAP_GAUGE = 80, 150, 250
FLOWLINE_FTYPES = {460, 558}   # StreamRiver, ArtificialPath (through ponds / reservoirs)

reaches = pd.read_csv(f"{MAP_OUT}/stream_reaches_ranked.csv")
drops_all = pd.read_csv(f"{MAP_OUT}/waterfall_candidates.csv")
SHOW = {"unmapped waterfall-like step", "unmapped cascade", "unmapped short fall (big creek)", "matches mapped waterfall"}
drops_all = drops_all[drops_all.status.isin(SHOW)]
gauges = gpd.read_file(f"{MAP_OUT}/context/gauges.gpkg").to_crs(CRS)
to_ll = lambda x, y: gpd.GeoSeries(gpd.points_from_xy(x, y), crs=CRS).to_crs(4326)


def main_stems(lines):
    """Longest path through each connected piece of a creek's merged NHD lines."""
    u = unary_union(list(lines))
    merged = u if u.geom_type == "LineString" else linemerge(u)
    parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
    G = nx.Graph()
    key = lambda c: (round(c[0], 1), round(c[1], 1))
    for i, ln in enumerate(parts):
        a, b = key(ln.coords[0]), key(ln.coords[-1])
        G.add_edge(a, b, w=ln.length, i=i) if a != b else None
    out = []
    for comp in nx.connected_components(G):
        sub = G.subgraph(comp)
        # tree diameter by two weighted sweeps (good enough for creek networks)
        start = next(iter(comp))
        d1 = nx.single_source_dijkstra_path_length(sub, start, weight="w")
        far = max(d1, key=d1.get)
        d2, paths = nx.single_source_dijkstra(sub, far, weight="w")
        end = max(d2, key=d2.get)
        nodes = paths[end]
        coords = []
        for u, v in zip(nodes[:-1], nodes[1:]):
            seg = list(parts[sub[u][v]["i"]].coords)
            if key(seg[0]) != u:
                seg = seg[::-1]
            coords += seg if not coords else seg[1:]
        if len(coords) >= 2:
            out.append(LineString(coords))
    return out


profiles = []
for region, meta in REGIONS.items():
    raw = raw_dir(region); der = derived_dir(region)
    src = rasterio.open(f"{raw}/dem_10m.tif")
    T, inv = src.transform, ~src.transform
    k = int(BOTTOM_M / RES)
    zf = rasterio.open(f"{der}/dem_filled.tif").read(1).astype("float32")
    zf[zf < -1000] = np.nan
    zbot = minimum_filter(np.nan_to_num(zf, nan=1e5), size=2 * k + 1)
    area = maximum_filter(rasterio.open(f"{der}/area_km2.tif").read(1), size=2 * int(AREA_M / RES) + 1)
    H, W = zf.shape

    nhd = gpd.read_file(f"{raw}/nhd_flowlines.gpkg").to_crs(CRS)
    nhd = nhd[nhd.gnis_name.notna() & nhd.ftype.isin(FLOWLINE_FTYPES)]
    s = gpd.read_file(f"{MAP_OUT}/{region}/streams_scored.gpkg").to_crs(CRS)[["sid", "flow", "geometry"]]
    s = s.merge(reaches.drop(columns=["region", "name", "flow", "lat", "lon"], errors="ignore"), on="sid", how="left")
    pts, sids = [], []
    for sid, g in zip(s.sid, s.geometry):
        for d in np.arange(0, g.length + 20, 20):
            p = g.interpolate(min(d, g.length)); pts.append((p.x, p.y)); sids.append(sid)
    rtree, sids = cKDTree(np.array(pts)), np.array(sids)
    s_attr = s.set_index("sid")
    d_reg = drops_all[drops_all.region == meta["label"]]
    d_xy = gpd.GeoSeries(gpd.points_from_xy(d_reg.lon, d_reg.lat), crs=4326).to_crs(CRS)
    kf = gpd.read_file(f"{MAP_OUT}/{region}/known_falls.gpkg").to_crs(CRS)

    by_name = {}
    for name, grp in nhd.groupby("gnis_name"):
        for ln in main_stems(grp.geometry):
            if ln.length < MIN_KM * 1000:
                continue
            dist = np.r_[np.arange(0, ln.length, STEP_M), ln.length]
            p = [ln.interpolate(d) for d in dist]
            x, y = np.array([q.x for q in p]), np.array([q.y for q in p])
            c, r = inv * (x, y)
            r = np.clip(r.astype(int), 0, H - 1); c = np.clip(c.astype(int), 0, W - 1)
            z = zbot[r, c].astype(float)
            ok = z < 1e4
            if ok.mean() < 0.8:
                continue          # mostly outside the DEM
            z = np.interp(dist, dist[ok], z[ok])
            if z[0] < z[-1]:      # orient head -> mouth
                x, y, z, r, c = x[::-1], y[::-1], z[::-1], r[::-1], c[::-1]
            z = np.minimum.accumulate(z)
            lo = np.searchsorted(dist, dist - GRAD_HALF_M); hi = np.clip(np.searchsorted(dist, dist + GRAD_HALF_M), 0, len(dist) - 1)
            grad = np.where(dist[hi] > dist[lo], (z[lo] - z[hi]) / (dist[hi] - dist[lo]) * 100, 0)
            ar = np.maximum.accumulate(area[r, c])   # drainage only grows downstream (fixes off-DEM / off-channel cells)
            ll = to_ll(x, y)
            _, near = rtree.query(np.c_[x, y])
            att = s_attr.loc[sids[near]]
            ptree = cKDTree(np.c_[x, y])

            def snap(gx, gy):
                if not len(gx):
                    return np.array([]), np.array([])
                dd, ii = ptree.query(np.c_[gx, gy])
                return dd, dist[ii] / 1000

            dd, km = snap(d_xy.x.values, d_xy.y.values)
            on = dd < SNAP_DROP
            drops = [dict(km=round(kk, 3), drop=r_.drop_m, status=r_.status, kind=r_.kind, lat=r_.lat, lon=r_.lon,
                          approach=None if pd.isna(r_.approach_min) else int(r_.approach_min),
                          bike=None if pd.isna(r_.bike_min) else int(r_.bike_min),
                          drive=None if pd.isna(r_.drive_min) else int(r_.drive_min),
                          excess=None if pd.isna(r_.excess_drop_m) else r_.excess_drop_m)
                     for kk, r_ in sorted(zip(km[on], d_reg[on].itertuples()), key=lambda t: t[0])]
            fd, fkm = snap(kf.geometry.x.values, kf.geometry.y.values)
            falls = [dict(km=round(kk, 3), name=n if isinstance(n, str) else "mapped waterfall")
                     for kk, n, d in zip(fkm, kf.name, fd) if d < SNAP_FALL]
            gd, gkm = snap(gauges.geometry.x.values, gauges.geometry.y.values)
            gs = [dict(km=round(kk, 3), name=g.name, cfs=g.cfs, status=g.status, url=g.url)
                  for kk, d, g in zip(gkm, gd, gauges.itertuples()) if d < SNAP_GAUGE]
            by_name.setdefault(name, []).append(dict(
                id=f"{region}:{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}:{int(x[-1])}_{int(y[-1])}",
                name=name, region=meta["label"], area_km2=round(float(ar.max()), 1),
                length_km=round(dist[-1] / 1000, 2), top_m=round(float(z[0])), bottom_m=round(float(z[-1])),
                best_score=float(np.nanmax(att.fish_score.values)) if att.fish_score.notna().any() else 0.0,
                km=np.round(dist / 1000, 3).tolist(), z=np.round(z, 1).tolist(), grad=np.round(grad, 1).tolist(),
                area=np.round(ar, 2).tolist(), lat=np.round(ll.y.values, 5).tolist(), lon=np.round(ll.x.values, 5).tolist(),
                score=[None if pd.isna(v) else int(v) for v in att.fish_score.values],
                burn=[f"{f} {int(yv)}" if pd.notna(yv) else None for f, yv in zip(att.burn_fire.values, att.burn_year.values)],
                trout=[1 if isinstance(t, str) else 0 for t in att.trout_water.values],
                habitat=[h if isinstance(h, str) else None for h in att.crit_habitat.values],
                # flows through the dry season: the flow model's class where it has data, else NHD perennial
                perennial=[1 if (wc in ("year-round", "usually flows") if isinstance(wc, str) and wc != "no data"
                                 else f == "perennial") else 0
                           for f, wc in zip(att.flow.values, att["water_class"].values if "water_class" in att
                                            else [None] * len(att))],
                drops=drops, falls=falls, gauges=gs))

    # disambiguate repeated names within a range by drainage area
    for name, ps in by_name.items():
        for p in ps:
            p["label"] = f"{name} ({meta['label'].replace(' Mountains', '')}"
            p["label"] += f", {p['area_km2']:g} km²)" if len(ps) > 1 else ")"
        profiles += ps
    print(f"{meta['label']}: {sum(len(v) for v in by_name.values())} creek profiles")

# compact: repeated labels as indexes into a per-profile lookup list
for p in profiles:
    for key in ("burn", "habitat"):
        vals = sorted({v for v in p[key] if v})
        p[key + "_vals"] = vals
        p[key] = [vals.index(v) if v else -1 for v in p[key]]
profiles.sort(key=lambda p: (-p["best_score"], p["name"]))
with open(f"{MAP_OUT}/profiles_data.js", "w") as f:
    f.write("window.PROFILE_DATA = ")
    json.dump(dict(generated=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), profiles=profiles), f,
              separators=(",", ":"), allow_nan=False, default=lambda o: None)
    f.write(";\n")
print(f"{len(profiles)} profiles, {sum(len(p['km']) for p in profiles):,} points, "
      f"{sum(len(p['drops']) for p in profiles)} drops on profiles")
