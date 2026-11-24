"""Long profiles (elevation vs. distance downstream) for every named creek, for output/profiles.html.

Creeks come from the NHD named flowlines: each name's segments are merged, split into connected pieces, and the
longest path through each piece is the creek's main stem. Elevation along it is the channel bottom: the lowest
hydro-conditioned DEM cell within BOTTOM_M (absorbs the small offsets between NHD lines and the 10 m DEM),
forced non-increasing downstream. Drainage area and the per-reach attributes (fish score, burn, trout water, critical
habitat, flow) come from the creek's own DEM channel only (see OWN_CAP). The drainage is the one the map's reaches
carry (area_full_km2), with the water from outside the map, over dams and past ponds. Drops, mapped falls and gauges
are snapped onto the profile. Run after 06_map.py (it reads the merged CSV exports).
Writes output/profiles_data.js (window.PROFILE_DATA, loads from file:// without a server).
"""
import json, re, numpy as np, pandas as pd, geopandas as gpd, rasterio
from scipy.ndimage import minimum_filter
from scipy.spatial import cKDTree
from config import REGIONS, CRS, ROOT, MAP_OUT, RES, raw_dir, derived_dir
from units import ft, sqmi, imperial_text   # the labels and notes profiles.html shows are imperial; the profile data stay metric
# which creeks get a profile (profile_stems: MIN_KM, main stems, the state line; FLOWLINE_FTYPES) and SNAP_FALL: shared
# with 06_map.py's popup links
from creekprofiles import SNAP_FALL, FLOWLINE_FTYPES, profile_stems

STEP_M = 40           # spacing along the profile
BOTTOM_M = 20         # channel-bottom search radius around the NHD line
AREA_M = 60           # drainage-area search radius (NHD lines sit up to ~60 m off the D8 channel: 58 m on lower Cabin Creek)
# The creek's own channel: DEM reaches named after it, or unnamed ones up to OWN_CAP[0] x its largest named reach +
# OWN_CAP[1] km2 (headwaters, links the name vote missed). Its drainage and reach attributes come only from these.
OWN_CAP = (2.0, 1.0)
KNN = 64              # nearest reach points searched for each profile point's own reach
GRAD_HALF_M = 60      # gradient over +/- this distance
SNAP_DROP, SNAP_GAUGE = 80, 250

reaches = pd.read_csv(f"{MAP_OUT}/stream_reaches_ranked.csv")
drops_all = pd.read_csv(f"{MAP_OUT}/waterfall_candidates.csv")
# likely DEM artifacts too, drawn apart in the viewer, so a step in the profile that is a road crossing or a filled
# depression says so rather than looking like a missed fall
SHOW = {"unmapped waterfall-like step", "unmapped cascade", "unmapped short fall (big creek)", "matches mapped waterfall",
        "likely DEM artifact"}
drops_all = drops_all[drops_all.status.isin(SHOW)]
gauges = gpd.read_file(f"{MAP_OUT}/context/gauges.gpkg").to_crs(CRS)
to_ll = lambda x, y: gpd.GeoSeries(gpd.points_from_xy(x, y), crs=CRS).to_crs(4326)


profiles = []
for region, meta in REGIONS.items():
    raw = raw_dir(region); der = derived_dir(region)
    src = rasterio.open(f"{raw}/dem_10m.tif")
    T, inv = src.transform, ~src.transform
    k = int(BOTTOM_M / RES)
    zf = rasterio.open(f"{der}/dem_filled.tif").read(1).astype("float32")
    zf[zf < -1000] = np.nan
    zbot = minimum_filter(np.nan_to_num(zf, nan=1e5), size=2 * k + 1)
    area = rasterio.open(f"{der}/area_km2.tif").read(1)
    ka = int(AREA_M / RES)
    H, W = zf.shape

    nhd = gpd.read_file(f"{raw}/nhd_flowlines.gpkg").to_crs(CRS)
    nhd = nhd[nhd.gnis_name.notna() & nhd.ftype.isin(FLOWLINE_FTYPES)]
    s = gpd.read_file(f"{MAP_OUT}/{region}/streams_scored.gpkg").to_crs(CRS)
    s = s[[c_ for c_ in ("sid", "flow", "own_x", "own_y", "geometry") if c_ in s.columns]]   # own_x/y: 05_score.py's own cell
    s = s.merge(reaches.drop(columns=["region", "flow", "lat", "lon"], errors="ignore"), on="sid", how="left")
    pts, sids = [], []
    for sid, g in zip(s.sid, s.geometry):
        for d in np.arange(0, g.length + 20, 20):
            p = g.interpolate(min(d, g.length)); pts.append((p.x, p.y)); sids.append(sid)
    rtree, sids = cKDTree(np.array(pts)), np.array(sids)
    s_attr = s.set_index("sid")
    p_name = s_attr.loc[sids, "name"].to_numpy(object); p_km2 = s_attr.loc[sids, "area_km2"].to_numpy(float)   # per reach point
    p_full = s_attr.loc[sids, "area_full_km2"].fillna(s_attr.loc[sids, "area_km2"]).to_numpy(float)
    # Each reach's cells, less its last vertex (the cell where it joins the next stream, which carries both arms; as in
    # 05_score.py), keyed by the reach's name; an unnamed reach's cells carry its drainage instead. A junction cell that
    # no reach starts from (the next stream leaves the box, or isn't mapped) stays -1: nobody's own. Vertices sit on
    # cell corners: rounded, not truncated (the round trip through EPSG:4326 leaves them a hair off).
    names = {n: i + 1 for i, n in enumerate(sorted(s["name"].dropna().unique()))}
    name_at = np.zeros((H, W), np.int32)            # 0: no reach there, or an unnamed one
    unnamed_km2 = np.zeros((H, W), np.float32)
    cells = []
    for g in s.geometry:
        v = np.asarray(g.coords)
        vc, vr = inv * (v[:, 0], v[:, 1])
        cells.append((np.clip(np.rint(vr).astype(int), 0, H - 1), np.clip(np.rint(vc).astype(int), 0, W - 1)))
        name_at[cells[-1][0][-1], cells[-1][1][-1]] = -1
    for nm, km2, (vr, vc) in zip(s["name"], s["area_km2"], cells):
        name_at[vr[:-1], vc[:-1]] = names[nm] if isinstance(nm, str) else 0
        if not isinstance(nm, str):
            unnamed_km2[vr[:-1], vc[:-1]] = km2
    # The water each reach gets from elsewhere: in from outside the map, over a dam, past a pond (crossbox.py), as the
    # map counts it (area_full_km2, which 05c_drainages.py adds at the reach's own cell): its full drainage less
    # area_km2.tif's there. area_km2.tif has only the boxes' own ground and the water behind lakes' outlets, so a river
    # from outside the map had only what gathered in its range (the Schuylkill 367 km2 where it leaves the Brandywine box
    # at Royersford, 3,087 with the river above the map; the Snake in Jackson Hole 6,368 for 13,137), and below a dam a
    # creek started again (2026-11-24). It counts on each reach's own cells, so a profile reads what its reaches' popups
    # do; nothing is added off the reaches (the tidal Delaware's flats, where creeks' NHD lines run on to its centre line).
    if {"own_x", "own_y"} <= set(s.columns):
        ox, oy = s.own_x.to_numpy(float), s.own_y.to_numpy(float)
    else:                                              # 05_score.py's own cell: the second-to-last vertex
        ox, oy = np.array([g.coords[max(len(g.coords) - 2, 0)][:2] for g in s.geometry]).T
    oc, orow = inv * (np.round(ox / RES) * RES, np.round(oy / RES) * RES)
    full = s["area_full_km2"].fillna(s["area_km2"]).to_numpy(float)
    carry = full - area[np.clip(np.rint(orow).astype(int), 0, H - 1), np.clip(np.rint(oc).astype(int), 0, W - 1)]
    # (area_full_km2 is rounded to 0.01 km2; crossbox carries nothing under 0.1.) Index -1: no reach, nothing carried
    carry, full = np.r_[np.where(carry >= 0.05, carry, 0), 0], np.r_[full, 0]
    reach_at = np.full((H, W), -1, np.int32)           # which reach's cell, as name_at has it
    for k_, (vr, vc) in enumerate(cells):
        reach_at[vr[:-1], vc[:-1]] = k_
    d_reg = drops_all[drops_all.region == meta["label"]]
    d_xy = gpd.GeoSeries(gpd.points_from_xy(d_reg.lon, d_reg.lat), crs=4326).to_crs(CRS)
    kf = gpd.read_file(f"{MAP_OUT}/{region}/known_falls.gpkg").to_crs(CRS)

    by_name = {}
    for name, grp in nhd.groupby("gnis_name"):
        for ln in profile_stems(grp.geometry):
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
            # Drainage and reach attributes from the creek's own channel (OWN_CAP). NHD draws a creek to the receiving
            # river's centreline, so the largest drainage within AREA_M from any channel was the river's at nearly every
            # mouth, and the running maximum carried it to "Drainage at mouth" (Cabin Creek showed the Snake River's
            # 3,138 km2 for its own 24; two thirds of all profiles were off, 2026-11-19). The nearest reach of any name
            # was the river's there too, and lent many creeks the river's fish score as their best.
            ik = rtree.query(np.c_[x, y], k=min(KNN, len(sids)))[1].reshape(len(x), -1)
            mine = p_name[ik] == name
            cap = OWN_CAP[0] * (p_km2[ik][mine].max() if mine.any() else np.inf) + OWN_CAP[1]
            # the nearest reach named after the creek; failing that an unnamed one within the cap; failing that any
            unnamed = pd.isna(p_name[ik]) & (p_km2[ik] <= cap)
            i_ = np.arange(len(ik))
            near = np.where(mine.any(axis=1), ik[i_, mine.argmax(axis=1)],
                            np.where(unnamed.any(axis=1), ik[i_, unnamed.argmax(axis=1)], ik[:, 0]))
            att = s_attr.loc[sids[near]]
            o = np.arange(-ka, ka + 1)
            wr, wcl = np.clip(r[:, None, None] + o[:, None], 0, H - 1), np.clip(c[:, None, None] + o[None, :], 0, W - 1)
            win = name_at[wr, wcl]
            own_named = win == names.get(name, -1)
            own_cell = own_named | ((win == 0) & (unnamed_km2[wr, wcl] <= cap))
            # the water carried from elsewhere, on the creek's own cells; on an unnamed reach's only when its full
            # drainage is within the same cap on the named reaches' full drainage: an unnamed reach beside a creek's
            # mouth that carries a river from outside is the river (Pole Creek, 23 km2 at the Santa Clara, would have
            # read the river's 2,941; Sandrock Creek in the Hoback box 55 for its reaches' 9.7)
            ri = reach_at[wr, wcl]
            cap_full = OWN_CAP[0] * (p_full[ik][mine].max() if mine.any() else np.inf) + OWN_CAP[1]
            add = np.where(own_named | (full[ri] <= cap_full), carry[ri], 0)
            # drainage only grows downstream (fixes off-DEM / off-channel cells); float64 first, as float32 rounded to
            # 2 places still writes 12.449999809265137
            ar = np.maximum.accumulate(np.where(own_cell, area[wr, wcl] + add, 0).max(axis=(1, 2)).astype("float64"))
            ll = to_ll(x, y)
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
                          excess=None if pd.isna(r_.excess_drop_m) else r_.excess_drop_m,
                          # why an artifact was set aside (05_score.py): a drivable road within 40 m, or a step in a
                          # depression the DEM fill raised more than 2 m (dam, culvert, bridge deck, bad pixels)
                          why=None if r_.status != "likely DEM artifact" else
                              "road crossing" if str(r_.road_crossing) == "True" else
                              f"filled depression ({ft(r_.fill_max_m)})")
                     for kk, r_ in sorted(zip(km[on], d_reg[on].itertuples()), key=lambda t: t[0])]
            fd, fkm = snap(kf.geometry.x.values, kf.geometry.y.values)
            falls = [dict(km=round(kk, 3), name=imperial_text(n) if isinstance(n, str) else "mapped waterfall")
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
            p["label"] += f", {sqmi(p['area_km2'])})" if len(ps) > 1 else ")"
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
