"""Combine every scored region into one interactive Leaflet map plus merged CSV/GPX exports.
Hillshades stay as separate PNGs next to the map (output/<region>/hillshade.png) to keep the HTML small."""
import json, os, colorsys, shapely, numpy as np, pandas as pd, geopandas as gpd, folium
from html import escape as hesc
from branca.element import MacroElement, Template
import shapely.ops
import rasterio
from urllib.parse import quote
from pyproj import Transformer
from labelpaths import label_paths
from folium.plugins import MeasureControl, MousePosition, Fullscreen
import matplotlib
from matplotlib import colors
from config import REGIONS, MAP_OUT, HOME, SHARED, EPSG, AREA_LABEL, MINOR, LONG_TRAIL, AREA, AREAS, has
from units import ft, mi, sqmi, degf, degf_diff, imperial_text, FT_PER_M   # what the maps show is imperial (units.py)
# Layer names and credits that depend on the area's data sources (config.py); both maps read them (window.LBL, D.lbl)
CA = has("cdfw_trout")
LBL = dict(
    title="LA mountain streams" if AREA_LABEL == "LA mountains" else f"{AREA_LABEL} streams",
    long_trail=LONG_TRAIL[0] if LONG_TRAIL else None,
    # for the "go to another area" menu in both maps (every area's map sits in output/<key>/; ../index.html is the
    # map of all areas, 13_overview.py). Only areas whose map has been built: an area just added to config.py (the
    # Smokies, 2026-11-19) was otherwise listed everywhere as a dead link until its first build and publish. Hidden
    # areas (config.py: the four Adirondack maps since 2026-11-20) are listed only in their own maps.
    area=AREA, areas=[dict(k=k_, t=v_["label"]) for k_, v_ in AREAS.items()
                      if k_ == AREA or (not v_.get("hidden")
                                        and os.path.exists(f"{os.path.dirname(MAP_OUT)}/{k_}/stream_map.html"))],
    flow="TNC Natural Flows model" if has("tnc_flows") else "NHDPlus mean flow × this area's gauge records",
    falls="Known waterfalls &amp; swimming holes (OSM, USGS, " + ("CDFW surveys, " if has("cdfw_pad") else "")
          + "guidebooks)",
    fires="Fire perimeters since 2016 (" + ("CAL FIRE" if has("cal_fire") else "NIFC") + "; this year's: WFIGS, BAER)",
    fire_src="CAL FIRE" if has("cal_fire") else "NIFC",
    trout_waters="CDFW Wild / Heritage Trout Waters" if CA else "Trout waters (state designations, brook trout patches)",
    access="Restricted or no public access (" + ("CPAD" if has("cpad") else "PAD-US") + ")",
    gauges="Stream gauges, USGS" + (" + CDEC" if has("cdec") else ""),
    trout_ev="Trout evidence: " + ("CDFW" if CA else "state") + " surveys (red = none found), stocking, iNaturalist",
    credits="USGS National Digital Trails · USFS · " + ("CDFW · " if CA else "") + "iNaturalist · "
            + ("CAL FIRE · " if has("cal_fire") else "NIFC fire history · ") + "NIFC WFIGS · USGS gauges &amp; debris-flow hazard · "
            + ("CDEC · " if has("cdec") else "") + ("TNC Natural Flows" if has("tnc_flows") else "NHDPlus V2 (EROM)")
            + " · PRISM Group, Oregon State University · known falls: OSM, USGS GNIS, Wikidata and the guides named in each")
from scoring import attach, score
import crossbox
import areaclip      # an area that stops at a state line (config clip_state) shows nothing past it

done = [r for r in REGIONS if os.path.exists(f"{MAP_OUT}/{r}/streams_scored.gpkg")]
read = lambda name: pd.concat([gpd.read_file(f"{MAP_OUT}/{r}/{name}") for r in done], ignore_index=True)
s_ll = gpd.GeoDataFrame(read("streams_scored.gpkg"), crs=4326)
kp_ll = gpd.GeoDataFrame(read("waterfall_candidates.gpkg"), crs=4326).sort_values("drop_m", ascending=False)
trails = gpd.GeoDataFrame(read("trails.gpkg"), crs=4326)
known_falls = gpd.GeoDataFrame(read("known_falls.gpkg"), crs=4326)
known_falls = known_falls[known_falls.geometry.notna()]
# a guide that puts many falls on this map (gawaterfalls.com's Georgia catalogue) is named in the credits as well as in
# each fall's popup
_guides = [s_ for s_, n_ in known_falls.src.str.split(" · ").explode().value_counts().items() if n_ >= 50 and s_ not in
           ("OpenStreetMap", "USGS GNIS", "USGS NHD", "Wikidata", "CDFW barrier survey")]
if _guides:
    LBL["credits"] = LBL["credits"].replace("known falls: OSM, USGS GNIS, Wikidata and",
                                            "known falls: OSM, USGS GNIS, Wikidata, " + ", ".join(_guides) + " and")
# road closures from 07_road_closures.py (optional; re-run that script to refresh)
closures = gpd.read_file(f"{MAP_OUT}/road_closures.gpkg") if os.path.exists(f"{MAP_OUT}/road_closures.gpkg") else None
gated = gpd.read_file(f"{MAP_OUT}/gated_roads.gpkg") if os.path.exists(f"{MAP_OUT}/gated_roads.gpkg") else None
closures, gated = areaclip.cut(closures), areaclip.cut(gated)
if closures is not None and len(closures):
    # nearest full closure within 3 km of each drop, for the popup
    full = closures[closures.severity.str.startswith("full")].to_crs(EPSG).reset_index(drop=True)
    near = gpd.sjoin_nearest(kp_ll[["geometry"]].to_crs(EPSG), full[["road", "geometry"]], how="left",
                             max_distance=3000, distance_col="closure_m").groupby(level=0).first()
    kp_ll["closure_road"], kp_ll["closure_m"] = near.road, near.closure_m.round(-1)
print("regions:", done)

# access (08/09), sun (10) and context (11) attributes, then the final fish score (scoring.py)
dirs = [f"{MAP_OUT}/{r}" for r in done]
s_ll = score(attach(s_ll.drop(columns="fish_score"), "sid", dirs, "streams"))
# the share of this area's reaches that score lower: the score was tuned on LA's mostly dry channels and runs high
# everywhere else, so the standing within the area says more than the number
s_ll["area_rank_pct"] = ((s_ll.fish_score.rank(method="min") - 1) / max(len(s_ll) - 1, 1) * 100).round(0)
# drainage / fork / channel Strahler order from 05c_drainages.py
sd = pd.concat([pd.read_csv(f"{MAP_OUT}/{r}/stream_drainage.csv") for r in done
                if os.path.exists(f"{MAP_OUT}/{r}/stream_drainage.csv")], ignore_index=True)
s_ll = s_ll.drop(columns=[c for c in ("drainage", "fork", "strahler") if c in s_ll]).merge(sd, on="sid", how="left")
s_ll["drainage"] = s_ll.drainage.fillna(MINOR)
s_ll["fork"] = s_ll.fork.fillna(s_ll.drainage)
s_ll["strahler"] = s_ll.strahler.fillna(s_ll["order"]).clip(1, 7).astype(int)
# A river that comes in from the next box, from outside the map or over a dam starts again at order 1 in this
# box's own count, so it drew as a thread until its side creeks built it back up, and dropped off the map of all
# areas (order 4 and up): the Maury from Rockbridge Baths to Lexington. Where a reach carries over twice its own
# box's drainage, its order is at least the usual one in this area for its full drainage: the orders' median
# areas come from the reaches that carry no outside water, and the steps between orders sit halfway (in logs).
# For drawing only: nothing in the scores reads the order.
if "area_full_km2" in s_ll:
    full_ = s_ll.area_full_km2.fillna(s_ll.area_km2).astype(float).values
    carried = (full_ > 2 * s_ll.area_km2.values) & (full_ - s_ll.area_km2.values > 5)
    med = s_ll[~carried].assign(f=full_[~carried]).groupby("strahler").f.agg(["median", "size"])
    med = med[med["size"] >= 5]["median"]
    if carried.any() and len(med) >= 3:
        ks = np.arange(1, 8)
        fit = np.polyfit(med.index.values, np.log(med.values.clip(0.01)), 1)       # about 4.5 times per order
        logm = np.array([np.log(max(med[k_], 0.01)) if k_ in med.index else np.polyval(fit, k_) for k_ in ks])
        logm = np.maximum.accumulate(logm)
        steps = (logm[:-1] + logm[1:]) / 2
        est = 1 + np.searchsorted(steps, np.log(full_.clip(0.01)))
        new_o = np.where(carried, np.maximum(s_ll.strahler.values, est), s_ll.strahler.values).clip(1, 7)
        print(f"stream order raised for {(new_o > s_ll.strahler.values).sum()} reaches that carry water from elsewhere "
              f"(median km2 by order: {', '.join(f'{k_}: {np.exp(v_):.3g}' for k_, v_ in zip(ks, logm))})")
        s_ll["strahler"] = new_o.astype(int)
# ---- creeks drawn through below dams and at the outer boundary ----
# Across the edges two boxes share, the streams run through by themselves since 2026-11-19 (03b_stitch.py routes
# the boxes together). Two kinds of break are left, where the routing really does stop: below a dam (paths end
# in the lake) and where a river comes in over the outer boundary of the map (its line starts only where 0.25 km2
# has gathered inside). crossbox.crossings() knows each place: from the cell the water goes on from, the box's own
# D8 path is followed to its first drawn reach, and that piece goes on the front of the reach, or, where it runs
# into the middle of one, is drawn as a piece of its own with that reach's values. Drawn lines only: the reaches
# keep their ids, scores and areas.
def draw_through(s_ll):
    from rasterio import features as rfeatures
    cross = [c_ for c_ in crossbox.crossings() if c_[6] >= 0.25 and c_[3] in done and c_[7] != "edge"]
    sm = s_ll.geometry.to_crs(EPSG).values
    line = np.array([g is not None and g.geom_type == "LineString" for g in sm])
    rk = s_ll.sid.str.split(":").str[0].values
    pos = np.flatnonzero(line)
    ends = shapely.STRtree(shapely.points([sm[i].coords[-1][:2] for i in pos]))
    all_lines = shapely.STRtree(sm[pos])
    ras, recs = {}, []
    # 1. each break: the path below it, the reach it runs into (if any) and the reach that ends above it (if any)
    for src, ex, ey, b, row, col, km2, kind in cross:
        if b not in ras:
            with rasterio.open(crossbox.fdir_path(b)) as f_:
                fd_, T_ = f_.read(1), f_.transform
            # the cells this box's drawn reaches run through (not every stream cell of 03 has a reach: short stubs
            # are dropped), so the line is carried down to one that is drawn
            ras[b] = (fd_, T_, rfeatures.rasterize([(g, 1) for g in sm[pos[rk[pos] == b]]], out_shape=fd_.shape,
                                                   transform=T_, all_touched=True, dtype="uint8"))
        fd_, T_, on_ = ras[b]
        H_, W_ = fd_.shape
        r_, c_, pts = int(row), int(col), []
        for _ in range(800):                               # 8 km at most
            pts.append(T_ * (c_ + 0.5, r_ + 0.5))
            if on_[r_, c_]:
                break
            d_ = crossbox.D8.get(int(fd_[r_, c_]))
            if d_ is None or not (0 <= r_ + d_[0] < H_ and 0 <= c_ + d_[1] < W_):
                break
            r_, c_ = r_ + d_[0], c_ + d_[1]
        up = None
        if kind == "edge" and ex is not None:
            pt = shapely.Point(ex, ey)
            cand = [pos[j] for j in ends.query(pt, predicate="dwithin", distance=45) if rk[pos[j]] == src]
            up = min(cand, key=lambda i: shapely.Point(sm[i].coords[-1][:2]).distance(pt)) if cand else None
        hit = None
        if on_[r_, c_]:                                    # the reach it runs into, and the exact spot on it
            pt = shapely.Point(pts[-1])
            cand = [pos[j] for j in all_lines.query(pt, predicate="dwithin", distance=25) if rk[pos[j]] == b and pos[j] != up]
            if cand:
                hit = min(cand, key=lambda i: sm[i].distance(pt))
                q = sm[hit].interpolate(sm[hit].project(pt))
                pts[-1] = (q.x, q.y)
        recs.append(dict(src=src, ex=ex, ey=ey, b=b, km2=km2, kind=kind, pts=pts, up=up, hit=hit, pred=None))
    # 2. a path that leaves its box again without meeting a drawn reach (a river clipping a corner, or weaving along
    # an edge) is carried on by the crossing that starts where it ends
    loose = [k for k, r in enumerate(recs) if r["hit"] is None]
    if loose:
        tails = shapely.STRtree(shapely.points([recs[k]["pts"][-1] for k in loose]))
        for k, r in enumerate(recs):
            if r["up"] is None and r["kind"] == "edge" and r["ex"] is not None:
                pt = shapely.Point(r["ex"], r["ey"])
                cand = [loose[j] for j in tails.query(pt, predicate="dwithin", distance=30)
                        if recs[loose[j]]["b"] == r["src"] and loose[j] != k]
                if cand:
                    r["pred"] = min(cand, key=lambda j: shapely.Point(recs[j]["pts"][-1]).distance(pt))
    def chain(k):
        """This break and the loose ones leading to it, first to last."""
        out, seen = [k], {k}
        while recs[out[0]]["pred"] is not None and recs[out[0]]["pred"] not in seen:
            out.insert(0, recs[out[0]]["pred"])
            seen.add(out[0])
        return out
    # 3. draw: on the end of the reach above where there is one; else on the front of the reach it leads into; else,
    # where it runs into the middle of a reach, as a piece of its own with that reach's values.
    # A path below a lake that runs into a stream carrying much more water (over 1.5 times what leaves the lake) is the
    # lake's own creek joining it, not the head of that stream: Taggart Creek's 2.1 km from Taggart Lake to Cottonwood
    # Creek were drawn on Cottonwood Creek's reach, with its name, 174 km2 and score (about 170 such paths, 140 km, over
    # the 12 maps on 2026-11-20). It is drawn as a piece of its own with the values of the lake's creek: the reach that
    # ends where the path starts, followed up through the reaches lying in the lake to the first one that doesn't, and
    # the drainage the path carries.
    km2_ = (s_ll.area_full_km2 if "area_full_km2" in s_ll else s_ll.area_km2).fillna(s_ll.area_km2).to_numpy(float)
    bd_ = s_ll.below_dam.fillna("").astype(str).to_numpy() if "below_dam" in s_ll else np.full(len(s_ll), "")
    k1 = lambda p: (round(p[0], 1), round(p[1], 1))
    ends_at = {}
    for i in pos:
        ends_at.setdefault(k1(sm[i].coords[-1]), []).append(i)
    def lake_creek(r):
        p0 = shapely.Point(r["pts"][0])
        cand = [pos[j] for j in ends.query(p0, predicate="dwithin", distance=80) if pos[j] != r["hit"]]
        if not cand:
            return None
        i = min(cand, key=lambda i: shapely.Point(sm[i].coords[-1][:2]).distance(p0))
        for _ in range(30):
            donors = ends_at.get(k1(sm[i].coords[0]), [])
            if not bd_[i].startswith("in:") or not donors:
                break
            i = max(donors, key=lambda j: km2_[j])
        return i
    coords, extra, used, n_up, n_head, n_own, n_creek, metres = {}, [], set(), 0, 0, 0, 0, 0.0
    noname = set()                                         # pieces of `extra` that don't take their reach's name
    def xy(i):
        if i not in coords:
            coords[i] = [c_[:2] for c_ in sm[i].coords]
        return coords[i]
    for k in sorted(range(len(recs)), key=lambda k: len(chain(k))):
        r = recs[k]
        ch = chain(k)
        if ch[0] in used and len(ch) > 1 and recs[ch[0]]["up"] is None:
            continue
        carrier = recs[ch[0]]["up"]
        if carrier is not None:                            # everything in the chain not yet drawn goes on that reach
            new = [p_ for j in ch if j not in used for p_ in recs[j]["pts"]]
            if not new:
                continue
            coords[carrier] = xy(carrier) + new
            used.update(ch)
            n_up += 1
        elif r["hit"] is not None:
            new = [p_ for j in ch for p_ in recs[j]["pts"]]
            if len(new) < 2:
                continue
            used.update(ch)
            # (... or one that runs into the next lake's water: since 05_score.py cuts the links at lake shores,
            # 2026-11-21, the reach it meets there is lake water, and the creek between two ponds drew with the lower
            # pond's values: 530 m between Spencer Pond and Big Pond in NE Connecticut, fish 15 for 57)
            own = lake_creek(r) if r["kind"] in ("dam", "pond") and (km2_[r["hit"]] > 1.5 * r["km2"]
                                                                     or bd_[r["hit"]].startswith("in:")) else None
            if own is not None and bd_[own].startswith("in:"):
                own = None                                 # no creek found above the lake: as before
            if own is None and bd_[r["hit"]].startswith("in:"):
                # no reach of its own above (a pond's trickle under the size floor): it is drawn with the values of
                # the main creek running into the lake it meets, as the uncut link gave it, with its own drainage
                # and no name
                i = r["hit"]
                for _ in range(30):
                    donors = ends_at.get(k1(sm[i].coords[0]), [])
                    if not bd_[i].startswith("in:") or not donors:
                        break
                    i = max(donors, key=lambda j: km2_[j])
                if not bd_[i].startswith("in:"):
                    own = i
                    noname.add(len(extra))
            if own is not None:
                extra.append((own, shapely.LineString(new), r["km2"]))
                n_creek += 1
            elif shapely.Point(sm[r["hit"]].coords[0][:2]).distance(shapely.Point(new[-1])) <= 15:
                coords[r["hit"]] = new[:-1] + xy(r["hit"])
                n_head += 1
            else:
                extra.append((r["hit"], shapely.LineString(new), None))
                n_own += 1
        else:
            continue                                        # loose: a later crossing may carry it on
        metres += shapely.LineString(new).length if len(new) > 1 else 0
    left = [r for k, r in enumerate(recs) if k not in used and len(r["pts"]) > 1]
    if coords:
        idx_ = list(coords)
        new = gpd.GeoSeries([shapely.LineString(coords[i]) for i in idx_], crs=EPSG).to_crs(4326).values
        geom = s_ll.geometry.values.copy()
        geom[idx_] = new
        s_ll = s_ll.set_geometry(gpd.GeoSeries(geom, index=s_ll.index, crs=s_ll.crs))
    if extra:
        add = s_ll.iloc[[h for h, _, _ in extra]].copy()
        add["sid"] = [f"{sid}+{n_}" for n_, sid in enumerate(add.sid.values, 1)]
        add = add.set_geometry(gpd.GeoSeries([g for _, g, _ in extra], index=add.index, crs=EPSG).to_crs(4326))
        carried = np.array([np.nan if k_ is None else k_ for _, _, k_ in extra], float)
        if "area_full_km2" in add:                       # a lake's creek: the drainage the path carries
            add["area_full_km2"] = np.where(np.isnan(carried), add.area_full_km2.to_numpy(float), np.round(carried, 2))
        if noname:
            add["name"] = [None if n_ in noname else v_ for n_, v_ in enumerate(add["name"].values)]
        s_ll = pd.concat([s_ll, add], ignore_index=True)
    s_ll.attrs["drawn_extra"] = len(extra)
    print(f"creeks drawn through {n_head + n_own + n_up + n_creek} breaks below dams and at the outer boundary "
          f"({metres / 1000:.1f} km of line; {n_creek} as a lake's own creek joining a bigger stream; "
          f"{len(left)} met no drawn reach)")
    return s_ll
s_ll = draw_through(s_ll)
N_DRAWN_EXTRA = s_ll.attrs.get("drawn_extra", 0)      # pieces added for drawing: not reaches of their own
s_ll[["sid", "geometry"]].to_file(f"{MAP_OUT}/streams_drawn.gpkg")      # the lines as drawn, for checking the breaks

# in the area's own CRS, as 05c wrote them: two boxes' outlines then meet exactly on the edge they share
basins = pd.concat([gpd.read_file(f"{MAP_OUT}/{r}/drainages.gpkg").to_crs(EPSG) for r in done
                    if os.path.exists(f"{MAP_OUT}/{r}/drainages.gpkg")], ignore_index=True)

# Basins cut by a box edge join the drainage they continue into in the neighbouring range: Sierra Pelona's
# San Francisquito and Bouquet canyons -> Santa Clara River, upper Piru Creek -> Piru Creek, North Fork Lytle ->
# Lytle Creek. 05c records where each basin leaves its box (out_x/out_y, one cell outside: on its reaches, and on the
# outline of an unnamed basin); following the neighbour's flow directions downhill from there to its first mapped
# stream gives the drainage (crossbox.py). Unnamed basins take that reach's drainage and fork; named ones keep their
# own name as a fork of it. A few passes let chains (Pelona -> San Gabriels -> Piru) settle. Unnamed outlines that
# join no named drainage are dropped.
for c_ in ("out_x", "out_y"):
    if c_ not in basins:
        basins[c_] = np.nan
basins["rkey"] = basins.region.map({cfg_["label"]: k_ for k_, cfg_ in REGIONS.items()})
if "out_x" in s_ll and s_ll.out_x.notna().any():
    s_ll["rkey"] = s_ll.sid.str.split(":").str[0]
    tree = s_ll.to_crs(EPSG).sindex
    # positions in the full s_ll (grouping a filtered copy would give positions within the copy)
    groups = {g: np.asarray(ix) for g, ix in s_ll.reset_index(drop=True).groupby(["rkey", "out_x", "out_y"],
                                                                                   dropna=True).indices.items()}
    outlines = {(r_, x_, y_) for r_, x_, y_ in zip(basins.rkey, basins.out_x, basins.out_y) if pd.notna(x_)}
    edges, fdirs = crossbox.shared_edges(done), {}
    def fdir_of(region):
        if region not in fdirs:
            with rasterio.open(crossbox.fdir_path(region)) as src_:
                fdirs[region] = (src_.read(1), src_.transform)
        return fdirs[region]
    # for a named basin whose crossing finds no mapped stream (Hightower Creek runs straight into Lake Chatuge on the
    # edge): the biggest reach of the outline its exit lands in, across the edge. Only into a bigger basin: a lake
    # lying across the edge sends each side's water to the other, and the smaller creek is the tributary.
    b_tree = shapely.STRtree(basins.geometry.values)
    rep = s_ll.reset_index(drop=True).groupby(["rkey", "drainage", "fork"]).area_km2.idxmax().to_dict()
    size_of = basins.assign(a=basins.area).groupby(["rkey", "drainage"]).a.sum().to_dict()
    def across_edge(g):
        pt = shapely.Point(g[1], g[2])
        mine = size_of.get((g[0], s_ll.drainage.iat[groups[g][0]]), 0)
        cand = [j for j in b_tree.query(pt, predicate="dwithin", distance=30)
                if basins.rkey.iat[j] != g[0] and basins.drainage.iat[j] != MINOR
                and size_of[(basins.rkey.iat[j], basins.drainage.iat[j])] > mine]
        if cand:
            j = min(cand, key=lambda j: basins.geometry.iat[j].distance(pt))
            return rep.get((basins.rkey.iat[j], basins.drainage.iat[j], basins.fork.iat[j]))
    target = {}
    for g in set(groups) | outlines:
        for b_, away in crossbox.neighbours(g[0], g[1], g[2], edges):
            # from the crossing, follow the neighbour's own D8 flow directions downhill (up to 6 km) to its first
            # mapped stream: the neighbour's streams start only where enough area has gathered below the edge
            for *_, x_, y_ in crossbox.crossing(b_, *fdir_of(b_), g[1], g[2], away):
                cand = [i for i in tree.query(shapely.Point(x_, y_), predicate="dwithin", distance=30)
                        if s_ll.rkey.iat[i] == b_]
                if cand:
                    target[g] = max(cand, key=lambda i: s_ll.area_km2.iat[i])
                    break
            if g in target:
                break
        if g not in target and g in groups and s_ll.drainage.iat[groups[g][0]] != MINOR:
            ti = across_edge(g)
            if ti is not None:
                target[g] = int(ti)
    d0, f0 = s_ll.drainage.to_numpy().copy(), s_ll.fork.to_numpy().copy()
    # Two named basins that each lead into the other: Lake Chatuge lies across the edge, so the Hiwassee's side
    # leaves into Hightower Creek's box and Hightower Creek back into the Hiwassee's (where it lands on the lake,
    # with no stream to find). The smaller is the tributary: the bigger one's link goes, and the smaller one's
    # exits that found nothing lead to the bigger one's main reach. Left in, the river took its tributary's name.
    rep_d = s_ll.reset_index(drop=True).groupby(["rkey", "drainage"]).area_km2.idxmax().to_dict()
    by_src = {}
    for g in groups:
        if d0[groups[g][0]] != MINOR:
            by_src.setdefault((g[0], d0[groups[g][0]]), []).append(g)
    pairs = {}
    for g, ti in target.items():
        if g in groups and MINOR not in (d0[groups[g][0]], d0[ti]) and d0[groups[g][0]] != d0[ti]:
            pairs.setdefault(((g[0], d0[groups[g][0]]), (s_ll.rkey.iat[ti], d0[ti])), []).append(g)
    for (a_, b_), gs in pairs.items():
        back = [g for g in by_src.get(b_, []) if any(n_ == a_[0] for n_, _ in crossbox.neighbours(g[0], g[1], g[2], edges))]
        if back and size_of.get(a_, 0) > size_of.get(b_, 0):
            print(f"two-way link: {a_[1]} ({a_[0]}) and {b_[1]} ({b_[0]}); {b_[1]} joins {a_[1]}")
            for g in gs:
                target.pop(g, None)
            for g in back:
                target.setdefault(g, int(rep_d[a_]))
    dcur, fcur = d0.copy(), f0.copy()
    for _ in range(6):
        dnew, fnew = dcur.copy(), fcur.copy()
        for g, ti in target.items():
            if g not in groups or dcur[ti] == MINOR:
                continue
            ix = groups[g]
            if d0[ix[0]] == MINOR:
                dnew[ix], fnew[ix] = dcur[ti], fcur[ti]
            else:
                dnew[ix] = dcur[ti]
        if (dnew == dcur).all() and (fnew == fcur).all():
            break
        dcur, fcur = dnew, fnew
    # only when the whole named basin moved. The parts of it that end at a dam or a pond inside the box (no exit of
    # their own) go with the rest: left behind, they kept the old name while the outline took the new one.
    moved = pd.DataFrame({"r": s_ll.region.values, "a": d0, "b": dcur, "exits": s_ll.out_x.notna().values})
    moved = moved[(moved.a != MINOR) & moved.exits].groupby(["r", "a"]).b.agg(lambda x: x.iloc[0] if x.nunique() == 1 else None)
    relabel = {k: v for k, v in moved.items() if pd.notna(v) and v != k[1]}
    dcur = np.array([relabel.get((r_, a_), b_) if b_ == a_ else b_ for r_, a_, b_ in zip(s_ll.region.values, d0, dcur)],
                    dtype=object)
    s_ll["drainage"], s_ll["fork"] = dcur, fcur
    basins["drainage"] = [relabel.get((r_, d_), d_) for r_, d_ in zip(basins.region, basins.drainage)]
    # an unnamed outline takes the drainage and fork of the reach its water continues into
    link = [target.get((r_, x_, y_)) if d_ == MINOR else None
            for r_, x_, y_, d_ in zip(basins.rkey, basins.out_x, basins.out_y, basins.drainage)]
    link = [ti if ti is not None and dcur[ti] != MINOR else None for ti in link]
    basins["drainage"] = [dcur[ti] if ti is not None else d_ for ti, d_ in zip(link, basins.drainage)]
    basins["fork"] = [fcur[ti] if ti is not None else f_ for ti, f_ in zip(link, basins.fork)]
    print("cross-range links:", len(target), "| renamed basins:", sorted(set(relabel.items()))[:12],
          f"| unnamed outlines joined: {sum(ti is not None for ti in link)} of {len(outlines)}")
# Unnamed outlines the streams couldn't place (too small to hold a mapped stream below the edge, or on a creek that
# weaves along it): each takes the drainage and fork of the outline its exit lands in across the edge, a few passes
# for chains; one of under 5 km2 still unnamed after that takes the named outline it shares the most boundary with.
# Their reaches follow. Left unnamed, they were pockets and notches down the line where two boxes meet. Only for
# outlines that leave over an edge two boxes share: one that drains off the outer boundary of the map stays unnamed.
seams_ = shapely.union_all(list(crossbox.shared_edges(done).values()))
un = np.flatnonzero((basins.drainage == MINOR).values & basins.out_x.notna().values)
if len(un) and not seams_.is_empty:
    un = un[shapely.distance(shapely.points(basins.out_x.values[un], basins.out_y.values[un]), seams_) <= 60]
if len(un):
    geoms, rk = basins.geometry.values, basins.rkey.values
    tree_b = shapely.STRtree(geoms)
    across = {}
    for i in un:
        pt = shapely.Point(basins.out_x.iat[i], basins.out_y.iat[i])
        cand = [j for j in tree_b.query(pt, predicate="dwithin", distance=30) if rk[j] != rk[i]]
        if cand:
            across[i] = min(cand, key=lambda j: geoms[j].distance(pt))
    dr, fk = basins.drainage.to_numpy().copy(), basins.fork.to_numpy().copy()
    how = {}
    for _ in range(20):
        # across first, until nothing more moves (a bigger outline often leaves into a small one that only its
        # neighbours can place: both kinds take turns)
        new = {i: j for i, j in across.items() if dr[i] == MINOR and dr[j] != MINOR}
        for i, j in new.items():
            dr[i], fk[i], how[i] = dr[j], fk[j], "across"
        if new:
            continue
        new = {}
        for i in un:
            if dr[i] != MINOR or geoms[i].area > 5e6:
                continue
            ring = geoms[i].buffer(15)
            share = {j: ring.intersection(geoms[j]).area for j in tree_b.query(ring, predicate="intersects")
                     if j != i and dr[j] != MINOR}
            by_d = {}
            for j, a_ in share.items():
                by_d[dr[j]] = by_d.get(dr[j], 0) + a_
            if by_d and max(by_d.values()) >= 15 * 50:                 # at least one 50 m cell side in common
                d_ = max(by_d, key=by_d.get)
                new[i] = max((j for j in share if dr[j] == d_), key=share.get)
        if not new:
            break
        for i, j in new.items():
            dr[i], fk[i], how[i] = dr[j], fk[j], "beside"
    basins["drainage"], basins["fork"] = dr, fk
    placed = {(rk[i], basins.out_x.iat[i], basins.out_y.iat[i]): i for i in how}
    if placed and "out_x" in s_ll:
        at = [placed.get(k_) if d_ == MINOR else None
              for k_, d_ in zip(zip(s_ll.sid.str.split(":").str[0], s_ll.out_x, s_ll.out_y), s_ll.drainage)]
        s_ll["drainage"] = [dr[i] if i is not None else d_ for i, d_ in zip(at, s_ll.drainage)]
        s_ll["fork"] = [fk[i] if i is not None else f_ for i, f_ in zip(at, s_ll.fork)]
    left = [i for i in un if dr[i] == MINOR]
    print(f"unnamed outlines placed by what is across the edge: {sum(v == 'across' for v in how.values())}, by what is "
          f"beside them: {sum(v == 'beside' for v in how.values())}; left unnamed: {len(left)} "
          f"({sum(geoms[i].area for i in left) / 1e6:.0f} km2)")
# A named drainage of under 2 km2 in all is a sliver of a creek that only clips the map (Pacific Creek at Moran:
# 1 km2 inside the boxes). It joins the named drainage it shares the most boundary with, reaches and all, rather
# than stand as a drainage of its own; with none beside it, it goes with the unnamed ones.
tot_d = basins.assign(a_=basins.area).groupby("drainage").a_.sum()
for d_ in [d_ for d_, a_ in tot_d.items() if d_ != MINOR and a_ < 2e6]:
    mine = (basins.drainage == d_).values
    ring = shapely.union_all(basins.geometry.values[mine]).buffer(15)
    share = {}
    for j in np.flatnonzero(~mine & (basins.drainage != MINOR).values & basins.intersects(ring).values):
        if tot_d[basins.drainage.iat[j]] >= 2e6:
            share[j] = ring.intersection(basins.geometry.iat[j]).area
    to_d, to_f = (basins.drainage.iat[max(share, key=share.get)], basins.fork.iat[max(share, key=share.get)]) if share else (MINOR, MINOR)
    print(f"sliver drainage {d_} ({tot_d[d_] / 1e6:.1f} km2) -> {to_d}")
    basins.loc[mine, ["drainage", "fork"]] = [to_d, to_f]
    s_ll.loc[s_ll.drainage == d_, ["drainage", "fork"]] = [to_d, to_f]
basins = basins[basins.drainage != MINOR].drop(columns=["out_x", "out_y", "rkey"]).reset_index(drop=True)
kp_ll = attach(kp_ll, "did", dirs, "drops")
CTX = f"{MAP_OUT}/context"
def ctx(n):
    """A context layer (11_context.py), or None if it wasn't written or is empty (no fires in Connecticut)."""
    g = areaclip.cut(gpd.read_file(f"{CTX}/{n}.gpkg")) if os.path.exists(f"{CTX}/{n}.gpkg") else None
    return g if g is not None and len(g) else None

def approach(r):
    """'Drive 95 min (73 mi) → park at X → bike 12 min → hike 40 min' for a reach or drop row, with today's closures
    on the way that the times (for mid-July) don't count: ' · ⚠ Teton Park Road closed for winter until Apr 30 (as of
    Nov 22)' (09_drive.py)."""
    if pd.isna(getattr(r, "approach_min", np.nan)):
        return "No route from an open road"
    bits = []
    if pd.notna(r.drive_min):
        bits.append(f"Drive {r.drive_min:.0f} min ({mi(r.drive_km)}) from {HOME['label']}")
    if isinstance(r.th_road, str):
        bits.append(f"park at {r.th_road}")
    if r.bike_min >= 1:
        chk = getattr(r, "bike_check", None)     # 08_hike.py: the ride uses a fire road bikes may not be allowed on
        bits.append(f"bike {r.bike_min:.0f} min on closed roads, fire roads or bike trails"
                    + (f" (⚠ fire road: double-check bike access, {r.bike_check_min:.0f} min of the ride: {chk})"
                       if isinstance(chk, str) else ""))
    bits.append(f"hike {r.walk_min:.0f} min")
    shut = getattr(r, "th_closed", None)
    return " → ".join(bits) + (f" · ⚠ {shut}" if isinstance(shut, str) and shut else "")

# what the approach times stand for, shown under each reach's access line by the map pages (map3d.html,
# map_drainages.js, 14_portable.py) from 07_road_closures.py's road_closures.json
_rc = json.load(open(f"{MAP_OUT}/road_closures.json")) if os.path.exists(f"{MAP_OUT}/road_closures.json") else None
_day = pd.Timestamp(_rc["fetched"]) if _rc else None
LBL["acc_asof"] = ("Times for summer (mid-July)" if _rc is None else
                   f"Times for summer (mid-July) · road closures as of {_day:%b} {_day.day}, winter ones not counted"
                   if _rc.get("feeds") else "Times for summer (mid-July) · no road-closure feed for this area")

# ---- merged exports ----
ACCESS = ["drive_min", "drive_km", "th_road", "th_lat", "th_lon", "bike_min", "bike_check", "bike_check_min", "walk_min",
          "approach_min", "th_closed"]
CONTEXT = ["sun_hours", "shade_pct", "northness", "canopy_pct", "air_aug", "burn_fire", "burn_year", "burn_sev", "debris_flow",
           "trout_water", "trout_found", "trout_absent", "trout_ev", "crit_habitat", "wilderness", "non_fs_land",
           "cpad_access"]
FLOWC = ["water_class", "dry_cfs", "dry_cfs_drought", "flow_years", "flow_src", "below_dam",   # 05b_flow.py
         "below_div", "div_share", "div_years", "gauge_name", "gauge_share", "gauge_years", "green_p90",
         "model_class", "water_floor", "water_by_gauge", "water_rule"]                       # (the last two: scoring.py)
for c_ in CONTEXT + FLOWC:   # older context files may lack a column
    if c_ not in s_ll:
        s_ll[c_] = None
    if c_ not in kp_ll:
        kp_ll[c_] = None
kp_ll.drop(columns="geometry").to_csv(f"{MAP_OUT}/waterfall_candidates.csv", index=False)
mid = s_ll.geometry.interpolate(0.5, normalized=True)
s_ll.assign(lat=mid.y.round(6), lon=mid.x.round(6)).sort_values("fish_score", ascending=False)[
    ["sid", "region", "drainage", "fork", "name", "flow", *FLOWC, "water_term", "fish_score", "thermal", "water_aug", "water_outlet", "outlet_m", "tailwater", "burn_factor", "trout_factor", "heat_factor", "channel_factor", "area_rank_pct", "area_km2", "area_edge_km2", "area_full_km2", "strahler", "elev_m",
     "gradient_pct", "len_m", "approach_med_min", "bike_med_min"] + ACCESS + CONTEXT + ["lat", "lon"]
].to_csv(f"{MAP_OUT}/stream_reaches_ranked.csv", index=False)

# GPX for a GPS / phone (onX, Gaia, CalTopo all import GPX). The apps refuse a file that isn't valid XML, so text
# is escaped: region names such as "Piru Creek & Castaic" hold a bare "&"
SHOW = ["unmapped waterfall-like step", "unmapped cascade", "unmapped short fall (big creek)", "matches mapped waterfall"]
good = kp_ll[kp_ll.status.isin(SHOW)]
with open(f"{MAP_OUT}/waterfall_candidates.gpx", "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="la-stream-analysis" xmlns="http://www.topografix.com/GPX/1/1">\n')
    for i, r in enumerate(good.itertuples()):
        tag = "WF" if r.status.startswith("matches") else "SF" if r.status.endswith("(big creek)") else "DROP"
        nm = f"{tag}{i+1:03d} {r.drop_m * FT_PER_M:.0f}ft"
        stream = r.stream if isinstance(r.stream, str) and r.stream else "unnamed"   # a missing name is NaN, not None
        desc = hesc(f"{r.region}; {stream}; {ft(r.drop_m)} over {ft(r.run_m)}; {r.flow}; {approach(r)}", quote=False)
        f.write(f'<wpt lat="{r.lat}" lon="{r.lon}"><name>{nm}</name><desc>{desc}</desc></wpt>\n')
        f.write(f'<wpt lat="{r.pool_lat}" lon="{r.pool_lon}"><name>{nm} pool</name></wpt>\n')
    f.write("</gpx>\n")

# ---- map ----
b = s_ll.total_bounds
# (no scale bar from folium: its scale shows metres too; map_drainages.js adds one in feet and miles)
m = folium.Map(location=[(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], zoom_start=9, tiles=None, control_scale=False,
               prefer_canvas=True)
# Default basemap is deliberately quiet (light gray + gray terrain shading + muted labels) so the analysis colors
# read clearly; the busier topo/satellite maps, which draw their own streams, are one click away.
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"
folium.TileLayer(f"{ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}", attr="Esri, HERE, Garmin",
                 name="Light gray terrain (default)", max_zoom=16).add_to(m)
folium.TileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
                 attr="USGS The National Map", name="USGS Topo (busy: its own streams)", max_zoom=16, show=False).add_to(m)
folium.TileLayer(f"{ESRI}/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",
                 attr="Esri, Maxar, Earthstar Geographics", name="Satellite (Esri)", max_zoom=19, show=False).add_to(m)
folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attr="OpenTopoMap (CC-BY-SA)",
                 name="OpenTopoMap", max_zoom=17, show=False).add_to(m)
folium.TileLayer(f"{ESRI}/Elevation/World_Hillshade/MapServer/tile/{{z}}/{{y}}/{{x}}", attr="Esri", overlay=True,
                 name="Terrain shading", opacity=0.45, max_zoom=16).add_to(m)
folium.TileLayer(f"{ESRI}/Canvas/World_Light_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}", attr="Esri",
                 overlay=True, name="Place & road labels", max_zoom=16, opacity=0.55).add_to(m)
hs_group = folium.FeatureGroup(name="DEM color relief (USGS 3DEP, 33 ft cells)", show=False)
for r in done:
    hb = json.load(open(f"{MAP_OUT}/{r}/hillshade_bounds.json"))
    ov = folium.raster_layers.ImageOverlay("https://example.invalid/x.png", opacity=0.75,
                                           bounds=[[hb["south"], hb["west"]], [hb["north"], hb["east"]]])
    ov.url = f"{r}/hillshade.png"  # relative link, not embedded
    ov.add_to(hs_group)
hs_group.add_to(m)

# ---- streams by drainage ----
# One hue per drainage (neighbouring drainages never share one), forks of a drainage are lighter/darker shades of
# it. Line width and lightness follow Strahler order, so trunks read first and headwater rills recede. Minor
# front-range drainages are a quiet slate. Styling, labels, legend and the colour-mode switch live in
# map_drainages.js (initDrainageMap), drawn on one canvas for speed.
PALETTE = ["#1864ab", "#d9480f", "#0b7285", "#2b8a3e", "#c92a2a", "#9c36b5", "#5c940d", "#1098ad", "#a05a2c",
           "#364fc7"]
MINOR_COL = "#8193a6"
bm = basins.to_crs(EPSG)
def fill_small_holes(g, min_m2=50000):
    """Drop pockets under 0.05 km2 (a few 50 m cells left between forks), which would draw as tiny rings."""
    parts = g.geoms if g.geom_type == "MultiPolygon" else [g]
    return shapely.MultiPolygon([shapely.Polygon(p.exterior, [h for h in p.interiors if shapely.Polygon(h).area >= min_m2])
                                 for p in parts if p.geom_type == "Polygon"])
dpoly = bm.dissolve("drainage").reset_index()
dpoly["geometry"] = [fill_small_holes(g) for g in dpoly.geometry]
dpoly["km2"] = dpoly.area / 1e6
dpoly = dpoly.sort_values("km2", ascending=False).reset_index(drop=True)
near_d = gpd.sjoin(dpoly[["drainage", "geometry"]].assign(geometry=dpoly.buffer(400)), dpoly[["drainage", "geometry"]],
                   predicate="intersects")
near_d = near_d[near_d.drainage_left != near_d.drainage_right].groupby("drainage_left").drainage_right.agg(set)
dcol, used = {}, {c: 0 for c in PALETTE}
for d in dpoly.drainage:
    banned = {dcol.get(n) for n in near_d.get(d, set())}
    c = min((c for c in PALETTE if c not in banned), key=lambda c: (used[c], PALETTE.index(c)))
    dcol[d], used[c] = c, used[c] + 1
dcol[MINOR] = MINOR_COL

def shade(hexc, dl):
    h, l, s_ = colorsys.rgb_to_hls(*colors.to_rgb(hexc))
    return colors.to_hex(colorsys.hls_to_rgb(h, min(max(l + dl, 0.18), 0.72), s_))
SHADES = [0.14, -0.11, 0.24, -0.19, 0.31, 0.07, -0.05]
fcol = {}
for d, g in bm.assign(km2=bm.area / 1e6).groupby("drainage"):
    forks = [f for f in g.sort_values("km2", ascending=False).fork if f != d]
    fcol[(d, d)] = dcol[d]
    for i, f in enumerate(forks):
        fcol[(d, f)] = shade(dcol[d], SHADES[i % len(SHADES)])

def cfs(v):
    return f"{v:.0f}" if v >= 10 else f"{v:.1f}" if v >= 1 else f"{v:.2f}"


_GAUGE_WORDS = {"C": "Creek", "Cr": "Creek", "Ck": "Creek", "R": "River", "Nr": "near", "Near": "near", "Bl": "below",
                "Blw": "below", "Ab": "above", "Abv": "above", "A": "at", "At": "at", "Cyn": "Canyon", "Lk": "Lake",
                "Res": "Reservoir", "Br": "Branch", "Trib": "tributary", "Ef": "East Fork", "Wf": "West Fork",
                "Nf": "North Fork", "Sf": "South Fork", "Mf": "Middle Fork", "Of": "of", "And": "and", "Pt": "Point"}


def gauge_label(name):
    """A USGS station name as words: "PIRU C BL PYRAMID LK NR GORMAN CA" -> "Piru Creek below Pyramid Lake near Gorman,
    CA" (the abbreviations USGS uses in its names; the state stays in capitals)."""
    w = [x for x in str(name).replace(",", " ").split() if x]
    if not w:
        return ""
    st = w.pop().upper() if len(w) > 1 and len(w[-1]) == 2 and w[-1].isalpha() else ""
    out = " ".join(_GAUGE_WORDS.get(x.title(), x.title()) for x in w)
    return out + (f", {st}" if st else "")


# the flow model sees creeks dry up (TNC's monthly natural flows); NHDPlus's mean flow, scaled by the gauges' years,
# doesn't: there a creek of the right size reads year-round whatever it does in a dry summer, so NHD's doubt goes beside it
FLOW_DRIES = has("tnc_flows")


def water_word(w):
    """The flow class a water term stands for (flowlib.water_term's limits on the share of summers flowing)."""
    return "mostly dry" if w <= 0.24 else "seasonal" if w <= 0.525 else "usually flows" if w <= 0.8575 else "year-round"


def summer_flow(r):
    """Popup line from the flow model (05b_flow.py) and the rules scoring.py applies to it: the class, why a rule set
    it where one did, the model's typical / drought-year low flow and share of summers flowing, and NHD's class.
    Below a gauged diversion, the record of the USGS gauge below it too; where the score uses it, it comes first."""
    c = r.water_class
    rule = r.water_rule if isinstance(r.water_rule, str) else ""
    if rule == "no estimate":
        nhd = {"unmapped": "doesn't map", "other": "gives no flow class"}.get(r.flow, f"maps {r.flow}")
        return (f"no flow estimate: the {LBL['flow']} has no line on this creek or below it on the map, so the score "
                f"takes what the map's other creeks of its size that NHD {nhd} mostly read, or NHD's class where that "
                f"says more: {water_word(r.water_term)} · NHD: {r.flow}")
    if not isinstance(c, str) or c == "no data":
        return ""
    dam = r.below_dam if isinstance(r.below_dam, str) else ""
    if c == "reservoir":
        return f"reservoir ({dam[3:] or 'lake'})"
    bits = []
    if pd.notna(r.dry_cfs):
        bits.append(f"low flow about {cfs(r.dry_cfs)} cfs in a typical July–October, {cfs(r.dry_cfs_drought)} cfs in a "
                    f"drought year")
    if pd.notna(r.flow_years):
        bits.append(f"kept flowing {r.flow_years:.0%} of summers since 2011")
    src = LBL["flow"] + (", scaled from the creek below" if r.flow_src == "scaled" else "")
    div = r.below_div if isinstance(r.below_div, str) else ""
    gauge = (f"below {div}: the USGS gauge there kept flowing {r.div_share:.0%} of summers in {r.div_years}"
             if div and pd.notna(r.div_share) else "")
    if gauge and r.water_by_gauge == True:
        return (f"{c} · {gauge}, which the score uses · the {src}, which can't see the diversion: " + ", ".join(bits)
                + f" · NHD: {r.flow}")
    # scoring.py's water (1) and (2): a gauge on this creek, or a creek bare in late summer, overrides the model
    if rule == "gauge" and pd.notna(r.gauge_share):
        return (f"{c} · the USGS gauge on this creek ({gauge_label(r.gauge_name)}) kept flowing {r.gauge_share:.0%} of "
                f"summers in {r.gauge_years}, which the score uses · the {src}: " + ", ".join(bits) + f" · NHD: {r.flow}")
    if rule == "bare channel":
        nhd = {"unmapped": "doesn't map it as a stream"}.get(r.flow, f"maps it {r.flow}")
        return (f"{c} · likely dry most summers: no green along the channel in late summer anywhere on this creek between "
                f"its confluences (satellite, 2022–24), and NHD {nhd}; the score takes it as seasonal · the {src} said: "
                + ", ".join(bits))
    # scoring.py's water (3): a tailwater, which its dam's releases keep flowing
    if rule == "tailwater releases":
        tw = r.tailwater if isinstance(getattr(r, "tailwater", None), str) else "the dam"
        return (f"{c} · below {tw}: its releases keep it flowing every summer, which the score uses · the {src}, "
                f"which sees only the natural flow, said: " + ", ".join(bits) + f" · NHD: {r.flow}")
    # scoring.py's water (5): trout found here
    if rule == "trout record":
        return (f"{c} · trout were found here, so it holds water most summers, whatever the model says · the {src}: "
                + ", ".join(bits) + f" · NHD: {r.flow}")
    # 05b_flow.py's floor: NHD's class where the estimate isn't about this creek's own water, or NHD maps it perennial
    # (said where it changed the class; within a class it only moved the score)
    if rule == "NHD class" and isinstance(r.model_class, str) and r.model_class != c:
        mc = r.model_class
        if r.water_floor == "dam":
            return (f"{c} · most of this creek's drainage lies above a lake or dam, and the {src} counts only its own "
                    f"ground below it (" + ", ".join(bits) + f"), which leaves out what seeps, spills or is released: "
                    f"the map takes NHD's class · NHD: {r.flow}")
        nhd = {"unmapped": "NHD has no line along it", "other": "NHD gives its line no flow class"}.get(r.flow,
                                                                                                  f"NHD maps it {r.flow}")
        why = ("NHD maps it perennial, and a creek NHD maps perennial is never shown drier" if r.water_floor == "perennial"
               else f"{nhd}, and an estimate scaled from another creek doesn't put a creek below what the map gives that")
        return (f"{c} · {why}: the {src}{',' if r.flow_src == 'scaled' else ''} had it {mc} (" + ", ".join(bits)
                + f") · NHD: {r.flow}")
    doubt = ""
    if not FLOW_DRIES and c in ("year-round", "usually flows") and r.flow in ("intermittent", "ephemeral", "unmapped"):
        doubt = (" (" + ("no NHD stream line along it" if r.flow == "unmapped" else f"NHD maps it {r.flow}")
                 + ": NHDPlus's mean flow can't see a creek drying, so it may stop flowing in a dry summer)")
    return (" · ".join([c + doubt] + bits) + f" ({src})" + (f" · below {dam}: releases set the flow" if dam else "")
            + (f" · {gauge}" if gauge else "") + f" · NHD: {r.flow}")


def sev_label(v):
    return ("mostly high soil burn severity" if v >= 0.85 else "moderate to high soil burn severity" if v >= 0.6
            else "low to moderate soil burn severity" if v >= 0.3 else "very low soil burn severity")


# how this area's water-temperature estimate is made (watertemp.py), for the popups
import watertemp
_wt = watertemp.fit_record() or {}
WT_HOW = ("estimated from " + " and ".join({"air": "air temperature", "elev_km": "elevation", "log_area": "stream size",
                                           "lake": "how close a lake lies upstream"}[t]
                                           for t in _wt.get("terms", [])) + f", ± {degf_diff(_wt.get('rmse_loo', 3))}") if _wt.get("ok") else ""
# the hottest creek with a trout record (11_context.py), for the heat gate's popup line
tev = ctx("trout_evidence")
HOT = (tev[tev.trout.astype(bool) & ~tev.lake.astype(bool)].air_aug.max()
       if tev is not None and "air_aug" in tev else np.nan)


def heat_line(air, f):
    if not (pd.notna(f) and f < 1):
        return ""
    rec = f" (at most {degf(HOT, 1)})" if pd.notna(HOT) else ""
    return (f"August air averages {degf(air, 1)} here (PRISM 1991–2020 normal), hotter than any creek in these ranges "
            f"where trout have been recorded{rec} · fish score × {f:.2f}")
# Reaches lying in a lake are drawn as the lake while the Lakes layer is on (it starts on, since 2026-11-20), and as
# streams again when it is switched off (the user: the rivers run on through the lakes then). The routing runs its paths
# straight across flat water (65 of the 143 reaches in Palisades Reservoir), and their names and colours came out of
# the lake's own drainage vote ("Trout Creek" across Palisades). A reach 05b_flow.py reads as lying in a lake
# (below_dam "in:") that lies at least half inside a lake the Lakes layer draws (about 8,200 of the 12 maps' 105,700
# reaches; some 170 at lake edges, where the two outlines differ, stay with the other streams) goes whole into a layer
# of its own (STREAMS_LAKE, which map_drainages.js, map3d.html and 14_portable.py show only while Lakes is off). The map
# of all areas keeps the whole reaches in its main rivers: it draws no lakes. Its data stays: ranks, profiles, the CSV.
s_ll["in_lake_drawn"] = False
from config import SHARED_DERIVED as SD_
lw_ = None
if os.path.exists(f"{SD_}/lakes.gpkg"):
    lw_ = gpd.read_file(f"{SD_}/lakes.gpkg").to_crs(EPSG)
    lw_ = gpd.GeoDataFrame(geometry=list(shapely.get_parts(shapely.union_all(shapely.make_valid(lw_.geometry.values)))),
                           crs=EPSG)
    lw_ = lw_[lw_.geom_type.isin(["Polygon", "MultiPolygon"]).values].reset_index(drop=True)
if lw_ is not None and len(lw_) and "below_dam" in s_ll:
    cand_ = s_ll.below_dam.fillna("").astype(str).str.startswith("in:").values
    if cand_.any():
        sc_ = s_ll[cand_][["geometry"]].to_crs(EPSG)
        j_ = gpd.sjoin(sc_, lw_, predicate="intersects")
        if len(j_):
            sh_ = (shapely.length(shapely.intersection(j_.geometry.values, lw_.geometry.reindex(j_.index_right).values))
                   / j_.geometry.length.values)
            sh_ = pd.Series(sh_, index=j_.index).groupby(level=0).sum()
            s_ll.loc[sh_.index[sh_ >= 0.5], "in_lake_drawn"] = True
    print(f"reaches lying in a lake, drawn whole only while Lakes is off: {int(s_ll.in_lake_drawn.sum())}")
# ... but their stretch outside the lake is drawn, so a river runs on to the shore and into the lake. Left off whole, a
# reach mostly in the lake took its approach with it and the line stopped short (around Jackson Lake 18.9 km of river,
# a 2.5 km gap above one inlet). Since 2026-11-20 evening this goes for every reach that runs into a lake the Lakes
# layer draws, not only those lying mostly in one: a reach under half in a lake was drawn whole, on into the water
# (Taggart Creek's inlet reach ran 0.6 km into Taggart Lake). Of the pieces outside the lakes, two kinds are left off:
# - a piece of a reach lying mostly in a lake, with both ends on the shore of one lake, that never gets 40 m from
#   it: the routing's straight path over the flat water clipping the shore or a headland (the four stubs of the Snake
#   by Donoho Point on Jackson Lake; about 980 over the 12 maps). A creek running along a shore keeps its pieces;
# - a piece under 20 m that meets no line drawn whole and no longer piece (a sliver of land the line crosses inside
#   the lake). One that does is a river's last few metres to the shore.
# A reach lying in a lake (05b_flow.py's "in:") carries the lake's values: reservoir, the lake's fish score, and the
# drainage of whatever path the routing ran across the water. Its piece past the lake's outline at the reach's own end
# or start is the river it continues there, so since 2026-11-21 that piece takes the values of the reach below (an
# outlet) or of the biggest reach above (an inlet), as the lines across dams take those of the line below the dam.
# Jackson Lake's last reach runs on 147 m through the dam, and it had been drawn as "Pilgrim Creek", reservoir, fish 23,
# before the Snake River: the routing threads only Pilgrim Creek across the lake, and the dam link puts the Snake's
# 1,957 km2 back in below the dam, onto that reach. Only with Lakes off does the whole reach still read Pilgrim Creek.
# The whole reaches go once more, marked lk_, into the layer shown while Lakes is off (STREAMS_LAKE below).
s_show = s_ll.assign(lk_=False)
if lw_ is not None and len(lw_):
    sm_ = s_ll.geometry.to_crs(EPSG).values
    lakes_ = lw_.geometry.values
    lt_ = shapely.STRtree(lakes_)
    ri_, li_ = lt_.query(sm_, predicate="intersects")
    cut_ = np.zeros(len(s_ll), bool)
    cut_[ri_] = True
    cut_ |= s_ll.in_lake_drawn.values
    by_ = pd.Series(li_).groupby(ri_).agg(list)
    rows_, geo_, inside_ = [], [], {}
    for i in np.flatnonzero(cut_):
        g_ = sm_[i]
        if g_ is None or g_.is_empty:
            continue
        ls_ = by_.get(i, [])
        d_ = shapely.difference(g_, shapely.union_all(lakes_[ls_])) if len(ls_) else g_
        inside_[i] = 1 - d_.length / g_.length if g_.length else 0.0
        for p_ in shapely.get_parts(d_):
            if p_.geom_type == "LineString" and p_.length > 0:
                rows_.append(i)
                geo_.append(p_)
    n_stub = 0
    if rows_:
        out_ = gpd.GeoDataFrame(s_ll.iloc[rows_].drop(columns="geometry").reset_index(drop=True), geometry=geo_, crs=EPSG)
        def lake_at(pt):
            h_ = lt_.query(pt, predicate="dwithin", distance=1.0)
            return int(h_[0]) if len(h_) else -1
        a_ = np.array([lake_at(shapely.Point(g_.coords[0])) for g_ in out_.geometry])
        b_ = np.array([lake_at(shapely.Point(g_.coords[-1])) for g_ in out_.geometry])
        hug_ = np.zeros(len(out_), bool)
        mostly_in_ = np.array([inside_.get(i, 0.0) >= 0.5 for i in rows_])   # a path over the water, not a lakeside creek
        for k_ in np.flatnonzero((a_ >= 0) & (a_ == b_) & mostly_in_):
            pts_ = shapely.points(shapely.get_coordinates(shapely.segmentize(out_.geometry.values[k_], 5.0)))
            hug_[k_] = shapely.distance(pts_, lakes_[a_[k_]]).max() < 40
        n_stub = int(hug_.sum())
        out_ = out_[~hug_].reset_index(drop=True)
        src_ = np.asarray(rows_)[~hug_]
        lakev_ = s_ll.below_dam.fillna("").astype(str).str.startswith("in:").values if "below_dam" in s_ll \
            else np.zeros(len(s_ll), bool)
        kmv_ = s_ll.area_full_km2.fillna(s_ll.area_km2).fillna(0).to_numpy(float)
        st_, en_ = shapely.get_point(sm_, 0), shapely.get_point(sm_, -1)
        tst_, ten_ = shapely.STRtree(st_), shapely.STRtree(en_)
        tln_ = shapely.STRtree(sm_)
        take_, riv_ = src_.copy(), np.zeros(len(out_), int)        # riv_: 1 below an outlet, 2 above an inlet
        own_ = {}                                                  # piece -> the drainage that leaves the lake
        for k_, i in enumerate(src_):
            if not lakev_[i]:
                continue
            g_ = out_.geometry.values[k_]
            at_s = shapely.Point(g_.coords[0]).distance(st_[i]) <= 0.5
            at_e = shapely.Point(g_.coords[-1]).distance(en_[i]) <= 0.5
            if at_e and not at_s:
                nb_ = [j for j in tst_.query(en_[i], predicate="dwithin", distance=1.0) if j != i]
                if not nb_:
                    # No reach starts where the line ends: draw_through's path below the dam ran into the middle of a
                    # reach, or into the next lake. Since 05_score.py cuts the links at lake shores (2026-11-21) the
                    # reach the path hangs on is always lake water, so the stretch from the dam to that spot read
                    # reservoir (530 m between Big Pond and Spencer Pond in NE Connecticut, fish 15 where the uncut
                    # link had read 57). It is the creek it runs into where that carries about what leaves the lake
                    # (up to 1.5 times, as in draw_through). Else (a much bigger stream, or another lake's water) it
                    # is the lake's own creek: the first reach above the lake not lying in it, with the drainage that
                    # leaves the lake.
                    hit_ = [j for j in tln_.query(en_[i], predicate="dwithin", distance=1.0) if j != i and not lakev_[j]]
                    h_ = max(hit_, key=lambda j: kmv_[j]) if hit_ else None
                    if h_ is not None and kmv_[h_] <= 1.5 * kmv_[i]:
                        nb_ = [h_]
                    else:
                        u_ = i
                        for _ in range(30):
                            up_ = [j for j in ten_.query(st_[u_], predicate="dwithin", distance=1.0) if j != u_]
                            if not lakev_[u_] or not up_:
                                break
                            u_ = max(up_, key=lambda j: kmv_[j])
                        if not lakev_[u_]:
                            nb_, own_[k_] = [u_], kmv_[i]
            elif at_s and not at_e:
                nb_ = [j for j in ten_.query(st_[i], predicate="dwithin", distance=1.0) if j != i]
            else:
                continue
            j_ = max(nb_, key=lambda j: kmv_[j]) if nb_ else None
            if j_ is not None and not lakev_[j_]:      # the river itself, not a creek joining it in the lake
                take_[k_], riv_[k_] = j_, 1 if at_e else 2
        if riv_.any():
            out_ = gpd.GeoDataFrame(s_ll.iloc[take_].drop(columns="geometry").reset_index(drop=True),
                                    geometry=out_.geometry.values, crs=EPSG)
            if own_ and "area_full_km2" in out_:
                out_.loc[list(own_), "area_full_km2"] = np.round(list(own_.values()), 2)
        long_ = (out_.length >= 20).values
        whole_ = [g_ for g_ in sm_[~cut_] if g_ is not None and not g_.is_empty]
        on_ = np.zeros(len(out_), bool)
        on_[shapely.STRtree(np.concatenate([np.array(whole_, dtype=object), out_.geometry.values[long_]])).query(
            out_.geometry.values, predicate="dwithin", distance=0.5)[0]] = True
        riv_ = riv_[long_ | on_]
        out_ = out_[long_ | on_].to_crs(s_ll.crs)
    else:
        out_, riv_ = s_ll.iloc[0:0], np.zeros(0, int)
    s_show = gpd.GeoDataFrame(pd.concat([s_ll[~cut_].assign(lk_=False), out_.assign(lk_=False),
                                         s_ll[cut_].assign(lk_=True)]), crs=s_ll.crs).reset_index(drop=True)
    print(f"reaches running into a lake, drawn up to its shore while Lakes is on: {int(cut_.sum())} "
          f"({len(out_)} pieces, {out_.to_crs(EPSG).length.sum() / 1000:,.1f} km outside the lakes; "
          f"{n_stub} stubs along a shore left off); drawn as the river they continue: {int((riv_ == 1).sum())} pieces "
          f"below a lake's outlet, {int((riv_ == 2).sum())} above an inlet")
# Rivers leaving a lake over a dam. pysheds can't route water across a lake's flat surface, so the routing ends a river
# in a pit in or beside the lake and starts it again in the cell below the dam (crossbox's "dam" and "pond" links, which
# draw_through above draws on from). Nothing was drawn across the dam: the line below it started 20-150 m from the
# shore at some 335 outlets over the eight shown maps (Jenny Lake, Indian Boundary Lake, Lower Slide Lake...). A short
# straight line now joins the line below the dam to the nearest point of the lake's shore, or to the end of the river's
# own line where that stops in a pit beside the lake and is nearer (the river's line: a reach end nothing goes on from,
# within 300 m, carrying at least half of what the link carries). It takes the values of the line below the dam. Where
# the river's own line ends inside the lake, a second line joins that end to the same point of the shore, in the layer
# shown while Lakes is off. A lake the line below the dam runs on into isn't the one it leaves. A join that would cross
# another line is left out, and so is one to a line running past the cell below the dam that runs into the lake rather
# than away from it (a creek coming in by the dam: about 5 of the 335); none is drawn where the line below the dam runs
# by the lake's shore itself within 80 m (a creek passing a pond's tip), which a join would only double. Drawing only.
DAM_TOL, TRUNK_TOL = 150, 300            # m: the farthest a shore or pit is joined from; the river's line looked for
dm_cr = [c_ for c_ in crossbox.crossings() if c_[7] in ("dam", "pond") and c_[6] >= 0.25 and c_[3] in done]
if dm_cr and lw_ is not None and len(lw_):
    dm_lp = lw_.geometry.values
    dm_U, dm_lt = shapely.union_all(dm_lp), shapely.STRtree(dm_lp)
    dm_below, dm_tf = {}, {}             # each cell below a dam once (a lake's several pits all go on from it)
    for dm_c in dm_cr:
        dm_b, dm_row, dm_col, dm_km2 = dm_c[3], int(dm_c[4]), int(dm_c[5]), dm_c[6]
        if dm_b not in dm_tf:
            with rasterio.open(crossbox.fdir_path(dm_b)) as f_:
                dm_tf[dm_b] = f_.transform
        dm_k = (dm_b, dm_row, dm_col)
        dm_below[dm_k] = (dm_tf[dm_b] * (dm_col + 0.5, dm_row + 0.5), max(dm_km2, dm_below.get(dm_k, (None, 0.0))[1]))
    dm_g = s_ll.geometry.to_crs(EPSG).values
    dm_ar = s_ll.area_full_km2.fillna(s_ll.area_km2).fillna(0).values
    dm_bx = s_ll.sid.astype(str).str.split(":").str[0].values
    dm_il = s_ll.in_lake_drawn.values
    dm_tree = shapely.STRtree(dm_g)
    dm_S, dm_E = shapely.get_point(dm_g, 0), shapely.get_point(dm_g, -1)
    dm_i, dm_j = dm_tree.query(dm_E, predicate="dwithin", distance=1)
    dm_dang = np.setdiff1d(np.arange(len(dm_g)), dm_i[dm_j != dm_i])  # reach ends nothing goes on from
    dm_con = []                                                     # (row whose values it takes, line, Lakes-off layer)
    dm_pit = []                                                     # (river's line stopping in a pit, line below)
    for (dm_b, dm_row, dm_col), (dm_xy, dm_km2) in dm_below.items():
        dm_p = shapely.Point(dm_xy)
        dm_d = dm_dang[(dm_bx[dm_dang] == dm_b) & (dm_ar[dm_dang] >= 0.5 * dm_km2)
                       & (shapely.distance(dm_E[dm_dang], dm_p) <= TRUNK_TOL)]
        dm_t = dm_d[np.argmax(dm_ar[dm_d])] if len(dm_d) else None
        dm_D = dm_E[dm_t] if dm_t is not None else None
        # the line the river goes on along: one starting in the cell below the dam, else one running past it
        dm_on = [i for i in dm_tree.query(dm_p, predicate="dwithin", distance=1)
                 if i != dm_t and dm_S[i].distance(dm_p) <= 1]
        dm_past = not dm_on
        if dm_past:
            dm_on = [i for i in dm_tree.query(dm_p, predicate="dwithin", distance=10) if i != dm_t and not dm_il[i]]
        if not dm_on:
            continue
        dm_jb = min(dm_on, key=lambda i: dm_g[i].distance(dm_p))
        dm_s = dm_g[dm_jb].project(dm_p)
        dm_p = dm_g[dm_jb].interpolate(dm_s)
        if dm_past and dm_g[dm_jb].interpolate(dm_s + 20).distance(dm_U) <= dm_p.distance(dm_U):
            continue                                                # a creek running into the lake, not out of it
        dm_in = dm_D is not None and shapely.within(dm_D, dm_U)
        if dm_in:
            dm_L = dm_lp[dm_lt.query(dm_D, predicate="intersects")[0]]
        else:
            dm_L = next((dm_lp[i] for i in sorted(dm_lt.query(dm_p, predicate="dwithin", distance=DAM_TOL),
                                                  key=lambda i: dm_lp[i].distance(dm_p))
                         if dm_g[dm_jb].intersection(dm_lp[i]).length <= 20), None)
        dm_Q = shapely.ops.nearest_points(dm_L.boundary, dm_p)[0] if dm_L is not None else None
        if dm_Q is not None and dm_Q.distance(dm_p) > DAM_TOL:
            dm_Q = None
        if (dm_D is not None and not dm_in and dm_D.distance(dm_p) <= DAM_TOL
                and (dm_Q is None or dm_D.distance(dm_p) < dm_Q.distance(dm_p))):
            dm_Q = dm_D                                             # its line stops in a pit beside the lake
        dm_by = (dm_Q is not None and dm_Q is not dm_D       # the line below the dam runs by the shore itself
                 and shapely.ops.substring(dm_g[dm_jb], dm_s, dm_s + 80).distance(dm_L) <= 2)
        if dm_Q is not None and dm_Q.distance(dm_p) >= 2 and not dm_by:
            dm_x = shapely.LineString([dm_Q, dm_p])
            dm_mid = shapely.difference(dm_x, shapely.union_all([dm_Q.buffer(3), dm_p.buffer(3)]))
            if not dm_mid.is_empty and any(i not in (dm_jb, dm_t) for i in dm_tree.query(dm_mid, predicate="intersects")):
                continue                                            # it would cross another line: left as it was
            dm_con.append((dm_jb, dm_x, False))
            if dm_Q is dm_D:
                dm_pit.append((dm_t, dm_jb))
        elif dm_Q is not None and dm_Q is dm_D:
            dm_pit.append((dm_t, dm_jb))                            # it stops right by the line below the dam
        if dm_Q is not None and dm_in and dm_D.distance(dm_Q) > 2:
            dm_con.append((dm_t, shapely.LineString([dm_D, dm_Q]), True))
    if dm_con:
        dm_add = s_ll.iloc[[c_[0] for c_ in dm_con]].drop(columns="geometry").reset_index(drop=True)
        dm_add = gpd.GeoDataFrame(dm_add.assign(lk_=[c_[2] for c_ in dm_con]), crs=s_ll.crs,
                                  geometry=gpd.GeoSeries([c_[1] for c_ in dm_con], crs=EPSG).to_crs(s_ll.crs).values)
        s_show = gpd.GeoDataFrame(pd.concat([s_show, dm_add]), crs=s_ll.crs).reset_index(drop=True)
    # A reach lying in a lake whose line stops in that pit beside the lake: its piece past the lake's outline, up to the
    # pit, is the river on its way to the dam, and takes the values of the line below the dam as the join does (since
    # 2026-11-21: Jenny Lake's outlet had been drawn for 36 m as Cottonwood Creek, reservoir, fish 33, before the
    # creek's fish 100). Only pieces: a reach the Lakes layer's lakes don't touch keeps its values.
    dm_lv = s_ll.below_dam.fillna("").astype(str).str.startswith("in:").values if "below_dam" in s_ll \
        else np.zeros(len(s_ll), bool)
    dm_pit = [(t_, b_) for t_, b_ in dm_pit if cut_[t_] and dm_lv[t_] and not dm_lv[b_]]
    dm_rep, dm_src = [], []
    if dm_pit:
        dm_sh = s_show[~s_show.lk_.values.astype(bool)]
        dm_shE = shapely.get_point(dm_sh.geometry.to_crs(EPSG).values, -1)
        for t_, b_ in dm_pit:
            h_ = dm_sh.index[(dm_sh.sid.values == s_ll.sid.iat[t_]) & (shapely.distance(dm_shE, dm_E[t_]) <= 1)]
            dm_rep += list(h_)
            dm_src += [b_] * len(h_)
    if dm_rep:
        dm_new = gpd.GeoDataFrame(s_ll.iloc[dm_src].drop(columns="geometry").reset_index(drop=True).assign(lk_=False),
                                  geometry=s_show.geometry.loc[dm_rep].values, crs=s_ll.crs)
        s_show = gpd.GeoDataFrame(pd.concat([s_show.drop(index=dm_rep), dm_new]), crs=s_ll.crs).reset_index(drop=True)
    dm_len = np.array([c_[1].length for c_ in dm_con if not c_[2]] or [0.0])
    print(f"rivers drawn across dams from the lake above: {sum(not c_[2] for c_ in dm_con)} of {len(dm_below)} cells "
          f"below a dam (median {np.median(dm_len):.0f} m, longest {dm_len.max():.0f} m); {sum(c_[2] for c_ in dm_con)} "
          f"joined to the shore from inside the lake, shown while Lakes is off; {len(dm_rep)} pieces from a lake to a pit "
          f"by its dam drawn as the river below the dam")
s_show = s_show.assign(geometry=shapely.set_precision(s_show.geometry.simplify(0.00008).values, 1e-5))
s_show = s_show[~s_show.geometry.is_empty & (s_show.geom_type == "LineString")]
mid_ll = s_show.geometry.interpolate(0.5, normalized=True)
nz = lambda v, nd=0: None if pd.isna(v) else round(float(v), nd) if nd else int(round(float(v)))
# a side channel of a river (05_score.py's side_of) says so in its name and in its flow line
_side = s_show.side_of.notna().values if "side_of" in s_show else np.zeros(len(s_show), bool)
props = pd.DataFrame({
    "n": np.where(_side, s_show["name"].astype(object) + " (side channel)", s_show["name"].where(s_show["name"].notna(), None)),
    "d": s_show.drainage, "k": s_show.fork, "o": s_show.strahler,
    "c": [fcol.get((d, f), dcol.get(d, MINOR_COL)) for d, f in zip(s_show.drainage, s_show.fork)],
    "fs": s_show.fish_score.round(0).astype(int),
    "fl": [f"summer: {c}" if isinstance(c, str) and c != "no data" else f"NHD {f}" for c, f in zip(s_show.water_class, s_show.flow)],
    "dq": [(f"a side channel of the {r.side_of}, which drains {sqmi(r.river_km2)} beside it: the routing sends the whole "
            f"river down one arm, so this arm's own drainage is small; it is scored on the river's size and flow · "
            if sd_ else "") + summer_flow(r) for r, sd_ in zip(s_show.itertuples(), _side)],
    # drainage (km2, to 0.01 so the popups' square miles keep two places) and elevation (m): the pages show them in
    # square miles and feet
    "a": s_show.area_full_km2.fillna(s_show.area_km2).astype(float).round(2), "el": [nz(v) for v in s_show.elev_m], "gr": s_show.gradient_pct.astype(float).round(1),
    "acc": [approach(r) for r in s_show.itertuples()],
    "sun": [" · ".join(x for x in (
                f"{h:.1f} h direct sun mid-July ({p:.0f}% shaded by terrain)" if pd.notna(h) else "",
                f"tree canopy {cv:.0f}%" if pd.notna(cv) else "",
                f"slope faces {'north' if n > 0.04 else 'south' if n < -0.04 else 'east/west or mixed'}" if pd.notna(n) else "",
                f"August air averages {degf(a)}" if pd.notna(a) else "",
                f"summer water about {degf(w)} ({WT_HOW})"
                + (f"; about {degf(wo)} over its first {ft(round(om * FT_PER_M / 50) * 50 / FT_PER_M)}, just below a lake"
                   if pd.notna(wo) and pd.notna(om) else "")      # scoring.py's water_outlet: the reach is scored as a whole
                if pd.notna(w) and not isinstance(tw, str) else "",
                f"tailwater below {tw}: the dam releases cold water from the bottom of the reservoir" if isinstance(tw, str) else "")
                       if x)
            for h, p, n, cv, a, w, tw, wo, om in zip(s_show.sun_hours, s_show.shade_pct, s_show.northness, pd.to_numeric(s_show.canopy_pct),
                                                     pd.to_numeric(s_show.air_aug), pd.to_numeric(s_show.water_aug), s_show.tailwater,
                                                     pd.to_numeric(s_show.water_outlet), pd.to_numeric(s_show.outlet_m))],
    "ht": [heat_line(a, f) for a, f in zip(pd.to_numeric(s_show.air_aug), s_show.heat_factor)],
    "burn": [" · ".join(x for x in (
                 f"{f} fire {y:.0f}" + (f" ({sev_label(sv)})" if pd.notna(sv) else "") if pd.notna(y) else "",
                 f"⚠ debris-flow hazard {dfl}" if isinstance(dfl, str) else "") if x)
             for f, y, sv, dfl in zip(s_show.burn_fire, s_show.burn_year, pd.to_numeric(s_show.burn_sev), s_show.debris_flow)],
    "tr": [" · ".join(x for x in (t if isinstance(t, str) else "", e if isinstance(e, str) else "") if x)
           for t, e in zip(s_show.trout_water, s_show.trout_ev)],
    "flags": [" · ".join(x for x in (f"⚠ critical habitat: {c}" if isinstance(c, str) else "",
                                     f"{w} (no bikes)" if isinstance(w, str) else "",
                                     f"⚠ {a}" if isinstance(a, str) else
                                     "⚠ non-Forest-Service land" if isinstance(o, str) else "",
                                     "built channel (aqueduct, canal or flood-control channel by name): fish score × 0.2"
                                     if ch < 1 else "") if x)
              for c, w, o, a, ch in zip(s_show.crit_habitat, s_show.wilderness, s_show.non_fs_land, s_show.cpad_access,
                                        s_show.channel_factor)],
    # where the reach stands among this area's reaches (scores aren't comparable between areas)
    "rk": s_show.area_rank_pct.astype(int),
    "y": mid_ll.y.round(5), "x": mid_ll.x.round(5)})
props["_lk"] = s_show.lk_.values
s_feat = gpd.GeoDataFrame(props, geometry=s_show.geometry.values, crs=4326).sort_values(["o", "fs"])
s_feat_lake = s_feat[s_feat._lk.values].drop(columns="_lk")      # the whole reaches lying in a lake (above)
s_feat = s_feat[~s_feat._lk.values].drop(columns="_lk")

# drainage / fork polygons, label points (inside the largest part) and legend entries
def label_pt(g):
    """Pole of inaccessibility of the largest part: the label sits well inside the basin."""
    g = max(g.geoms, key=lambda p: p.area) if g.geom_type == "MultiPolygon" else g
    return shapely.ops.polylabel(g, tolerance=200)
fpoly = bm.dissolve(["drainage", "fork"]).reset_index()
fpoly["geometry"] = [fill_small_holes(g) for g in fpoly.geometry]
fpoly["c"] = [fcol.get((d, f), dcol[d]) for d, f in zip(fpoly.drainage, fpoly.fork)]
to_ll = lambda geoms: gpd.GeoSeries(geoms, crs=EPSG).to_crs(4326)
fl_pts = to_ll([label_pt(g) for g in fpoly.geometry])
dl_pts = to_ll([label_pt(g) for g in dpoly.geometry])
f_json = json.loads(fpoly[["drainage", "fork", "c", "geometry"]].to_crs(4326).assign(
    geometry=lambda g: shapely.set_precision(shapely.make_valid(g.geometry.simplify(0.0002).values), 1e-5)).to_json())
d_json = json.loads(dpoly[["drainage", "geometry"]].to_crs(4326).assign(
    geometry=lambda g: shapely.set_precision(g.geometry.boundary.simplify(0.0002).values, 1e-5)).to_json())
region_of = s_ll.groupby("drainage").region.agg(lambda r: r.mode().iloc[0])
dbounds = dpoly.to_crs(4326).bounds
# km2 to 0.1 (the legends show square miles; their label rules compare km2)
drains = [dict(name=d, color=dcol[d], dark=shade(dcol[d], -0.12), region=region_of.get(d, ""), km2=round(k, 1),
               lab=[round(p.y, 5), round(p.x, 5)], b=[[r.miny, r.minx], [r.maxy, r.maxx]])
          for d, k, p, r in zip(dpoly.drainage, dpoly.km2, dl_pts, dbounds.itertuples())]
for e in drains:  # forks of each drainage, biggest first
    sel = fpoly.drainage == e["name"]
    e["forks"] = sorted([dict(name=f, color=c, km2=round(a / 1e6, 1), lab=[round(p.y, 5), round(p.x, 5)])
                         for f, c, a, p in zip(fpoly.fork[sel], fpoly.c[sel], fpoly.area[sel], fl_pts[sel])],
                        key=lambda x: -x["km2"])
drains.append(dict(name=MINOR, color=MINOR_COL, dark="#5c6b7a", region="", km2=None, lab=None, b=None, forks=[]))
def merge_lines(geoms):
    """Join touching lines into as few lines as possible (linemerge rejects a single line)."""
    u = shapely.union_all(geoms)
    u = shapely.ops.linemerge(u) if u.geom_type == "MultiLineString" else u
    return [g for g in getattr(u, "geoms", [u]) if g.geom_type == "LineString"]


# ---- Pacific Crest Trail (02c_pct.py): one line per PCT section, plus label points along the trail ----
PCT_SECTIONS = {"A": "Campo → Warner Springs", "B": "Warner Springs → San Gorgonio Pass (I-10)",
                "C": "San Gorgonio Pass (I-10) → Cajon Pass (I-15)", "D": "Cajon Pass (I-15) → Agua Dulce",
                "E": "Agua Dulce → Tehachapi Pass (Hwy 58)", "F": "Tehachapi Pass → Walker Pass"}
pct_json, pct_labels = None, []
if os.path.exists(f"{SHARED}/pct.gpkg"):
    pct = gpd.read_file(f"{SHARED}/pct.gpkg").to_crs(EPSG)
    if LONG_TRAIL and LONG_TRAIL[1] == "PCT":
        pct["sec"] = pct.section.str.extract(r"Section ([A-Z])\b", expand=False).fillna("?")
    else:   # other trails: the OSM section relation's own name ("Appalachian Trail - Georgia")
        pct["sec"] = pct.section.fillna(LONG_TRAIL[0] if LONG_TRAIL else "trail")
    secs = pct.dissolve("sec").reset_index()
    secs["geometry"] = [shapely.ops.linemerge(g) if g.geom_type == "MultiLineString" else g for g in secs.geometry]
    secs["label"] = ([f"Section {k}: {PCT_SECTIONS.get(k, '')}".rstrip(": ") for k in secs.sec]
                     if LONG_TRAIL and LONG_TRAIL[1] == "PCT" else list(secs.sec))
    pct_json = json.loads(secs[["sec", "label", "geometry"]].to_crs(4326).assign(
        geometry=lambda g: shapely.set_precision(shapely.make_valid(g.geometry.simplify(0.00002).values), 1e-5)).to_json(drop_id=True))
    # labels that bend along the trail, one set per zoom band (labelpaths.py); "Pacific Crest Trail" is ~112 px
    PCT_BANDS = [(11, 15, 10000, 12000, [65]), (12, 9, 5000, 6000, [32]), (13, 5, 2500, 3000, [16, 8])]
    pct_lines = merge_lines(pct.geometry.values)
    pct_labels = [lab for ln in pct_lines for lab in label_paths(ln, PCT_BANDS, round(5.9 * len(LONG_TRAIL[0])) if LONG_TRAIL else 112)]
    print("PCT", len(secs), "sections,", round(sum(ln.length for ln in pct_lines) / 1000), "km | labels per zoom band:",
          pd.Series([l["z"] for l in pct_labels]).value_counts().sort_index().to_dict())
# ---- Trails and fire roads (02d_trails.py; older runs fall back to each range's OSM paths) ----
# Drawn by map_drainages.js / map3d.html with detail revealed by zoom: rank 1 hiking routes and named trails, 2 named
# fire roads, 3 unnamed trails, 4 unnamed fire roads. Named trails and fire roads get labels that bend along them.
SAC = {"hiking": "easy (T1)", "mountain_hiking": "mountain hiking (T2)", "demanding_mountain_hiking": "demanding (T3)",
       "alpine_hiking": "alpine (T4)", "demanding_alpine_hiking": "demanding alpine (T5)",
       "difficult_alpine_hiking": "difficult alpine (T6)"}
study = gpd.GeoSeries([shapely.box(*v["bbox"]) for v in REGIONS.values()], crs=EPSG).union_all().buffer(1000)
if areaclip.outline() is not None:      # (the state line itself isn't widened: Crown Point is 1 km across the lake)
    study = study.intersection(areaclip.outline())
study_ll = gpd.GeoSeries([study], crs=EPSG).to_crs(4326).iloc[0]
if os.path.exists(f"{SHARED}/trails.gpkg"):
    tr = gpd.read_file(f"{SHARED}/trails.gpkg")
    tr = areaclip.cut(tr[tr.intersects(study_ll)])
    col_ = lambda c, d=None: tr[c] if c in tr else pd.Series(d, index=tr.index)
    def agency(s):
        s = str(s)
        for k, v in (("Forest Service", "USFS"), ("National Park", "NPS"), ("State Park", "CA State Parks"),
                     ("Los Angeles County", "LA County Parks")):
            if k.lower() in s.lower():
                return v
        return s[:40]
    unoff = col_("unofficial", False).fillna(False).astype(bool)
    tprops = pd.DataFrame({
        "cw": col_("closed_why"), "n": tr["name"], "k": tr.kind, "rk": tr["rank"].astype(int), "s": tr.sac_scale.map(SAC), "sf": tr.surface,
        "rt": tr.route, "cl": col_("closed", False).fillna(False).astype(int),
        "f": (tr.informal.eq("yes") | tr.trail_visibility.isin(["bad", "horrible", "no"]) | unoff
              | col_("source", "OSM").eq("official only")).astype(int),
        "u": unoff.astype(int), "of": col_("official").map(lambda v: agency(v) if isinstance(v, str) else None),
        "no": col_("trail_no"), "us": col_("uses"), "g": col_("gated"),
        "src": col_("source", "OSM").where(lambda x: x != "OSM"),
        "b": col_("bike", "unknown"), "bw": col_("bike_why"), "mtb": col_("mtb_scale")})
else:
    tr = trails.assign(name=trails["name"].where(trails["name"] != "trail"))
    tprops = pd.DataFrame({"n": tr["name"], "k": "trail", "rk": np.where(tr["name"].notna(), 1, 3)})
t_feat = gpd.GeoDataFrame(tprops, geometry=shapely.set_precision(tr.geometry.simplify(0.00004).values, 1e-5), crs=4326)
t_feat = t_feat[~t_feat.geometry.is_empty].sort_values("rk", ascending=False)
if os.path.exists(f"{SHARED}/access_roads.gpkg"):   # the road layers draw fire roads; keep the ones on hiking routes
    t_feat = t_feat[(t_feat.k != "fire road") | t_feat.get("rt", pd.Series(None, index=t_feat.index)).notna()]
def beside_creeks(feat, step=10.0, max_d=80.0, min_run=40.0):
    """Split trail / road lines into the runs that follow a creek of order 2+ (within max_d m and within ~50° of its
    direction), so the maps can draw those runs shifted to the creek's far side instead of on top of it. Adds sd (+1:
    the creek is on the line's left, so it's drawn shifted right; -1: the other way), so (the creek's order) and dm
    (median metres apart: the maps shift only by what the two line widths need at each zoom)."""
    feat = feat[~feat.geometry.is_empty]
    if not len(feat):
        return feat
    cr = s_ll[(s_ll.strahler >= 2) & ~s_ll.in_lake_drawn].to_crs(EPSG)      # the creeks drawn (not those in lakes)
    cg, co = cr.geometry.values, cr.strahler.values.astype(int)
    ex = feat.to_crs(EPSG).explode(index_parts=False)
    ex = ex[ex.geom_type == "LineString"]
    lines = ex.geometry.values
    L = shapely.length(lines)
    n = np.maximum(2, (L // step).astype(int) + 1)
    first = np.r_[0, np.cumsum(n)[:-1]]
    own = np.repeat(np.arange(len(lines)), n)
    idx = np.arange(len(own))
    d = (idx - np.repeat(first, n)) / np.repeat(n - 1, n) * np.repeat(L, n)
    pts = shapely.line_interpolate_point(np.repeat(lines, n), d)
    X, Y = shapely.get_x(pts), shapely.get_y(pts)
    nx_ = np.minimum(idx + 1, len(idx) - 1)
    nx_ = np.where(own[nx_] == own, nx_, idx)
    pv_ = np.maximum(idx - 1, 0)
    pv_ = np.where(own[pv_] == own, pv_, idx)
    tx, ty = X[nx_] - X[pv_], Y[nx_] - Y[pv_]
    sd, so, dm = np.zeros(len(idx), np.int8), np.zeros(len(idx)), np.full(len(idx), np.nan)
    (pi, ci), dist = shapely.STRtree(cg).query_nearest(pts, max_distance=max_d, return_distance=True, all_matches=False)
    if len(pi):
        cl = cg[ci]
        pos = shapely.line_locate_point(cl, pts[pi])
        a, b = shapely.line_interpolate_point(cl, np.maximum(pos - 8, 0)), shapely.line_interpolate_point(cl, pos + 8)
        q = shapely.line_interpolate_point(cl, pos)
        sx, sy = shapely.get_x(b) - shapely.get_x(a), shapely.get_y(b) - shapely.get_y(a)
        ux, uy = tx[pi], ty[pi]
        par = np.abs(ux * sx + uy * sy) >= 0.64 * np.hypot(ux, uy) * np.hypot(sx, sy)
        cross = ux * (shapely.get_y(q) - Y[pi]) - uy * (shapely.get_x(q) - X[pi])
        side = np.where(dist < 2, 2, np.sign(cross)).astype(np.int8)        # 2: right on the creek, side unknown
        ok = par & (side != 0)
        sd[pi[ok]], so[pi[ok]], dm[pi[ok]] = side[ok], co[ci[ok]], dist[ok]

    def runs(v):
        b_ = np.r_[0, np.flatnonzero(np.diff(v)) + 1, len(v)]
        return [(b_[j], b_[j + 1], v[b_[j]]) for j in range(len(b_) - 1)]
    keep, pieces = [], []
    props = ex.drop(columns="geometry").reset_index(drop=True)
    for i, ln in enumerate(lines):
        s0, s1 = first[i], first[i] + n[i]
        v = sd[s0:s1].copy()
        if v.any():
            for a_, b_, val in runs((v != 0).astype(np.int8)):      # a run on the creek takes its run's side
                if val:
                    seg = v[a_:b_]
                    seg[seg == 2] = np.sign(seg[np.abs(seg) == 1].sum()) or 1
            for a_, b_, val in runs(v):                              # bridge gaps of up to 20 m on the same side
                if val == 0 and b_ - a_ <= 2 and a_ > 0 and b_ < len(v) and v[a_ - 1] == v[b_] != 0:
                    v[a_:b_] = v[b_]
            for a_, b_, val in runs(v):                              # drop runs too short to matter
                if val and (b_ - a_) * step < min_run:
                    v[a_:b_] = 0
        if not v.any():
            keep.append((i, ln, None, None, None))
            continue
        dd = d[s0:s1]
        for a_, b_, val in runs(v):
            lo = 0 if a_ == 0 else (dd[a_ - 1] + dd[a_]) / 2
            hi = L[i] if b_ == len(v) else (dd[b_ - 1] + dd[b_]) / 2
            g_ = shapely.ops.substring(ln, lo, hi)
            if g_.geom_type != "LineString" or g_.length < 1:
                continue
            on = slice(s0 + a_, s0 + b_)
            keep.append((i, g_, int(val) if val else None, int(np.median(so[on])) if val else None,
                         int(round(np.nanmedian(dm[on]))) if val else None))
    out = props.iloc[[k[0] for k in keep]].reset_index(drop=True)
    out["sd"], out["so"], out["dm"] = [k[2] for k in keep], [k[3] for k in keep], [k[4] for k in keep]
    out = gpd.GeoDataFrame(out, geometry=[k[1] for k in keep], crs=EPSG).to_crs(4326)
    out["geometry"] = shapely.set_precision(out.geometry.values, 1e-5)
    out = out[~out.geometry.is_empty]
    on_ = out.sd.notna()
    print(f"  beside a creek: {out[on_].to_crs(EPSG).length.sum() / out.to_crs(EPSG).length.sum():.0%} of the length, "
          f"{int(on_.sum())} of {len(out)} pieces")
    return out


TRAIL_BANDS = [(13, 5, 1500, 3000, [16]), (14, 3, 800, 1500, [8, 4, 2])]
trail_labels = []
tu = t_feat[t_feat.n.notna() & ~t_feat.n.fillna("").str.contains(LONG_TRAIL[2] if LONG_TRAIL else "Pacific Crest", case=False)].to_crs(EPSG)
for nm, grp in tu.groupby("n"):
    for ln in merge_lines(grp.geometry.values):
        if ln.length >= 1600:
            trail_labels += [dict(lab, t=nm) for lab in label_paths(ln, TRAIL_BANDS, len(nm) * 5.6 + 6)]
print("trails:")
t_feat = beside_creeks(t_feat)
# ---- access roads, parking and trailheads (02e_access.py) ----
roads_json, park_json = None, None
if os.path.exists(f"{SHARED}/access_roads.gpkg"):
    ar = gpd.read_file(f"{SHARED}/access_roads.gpkg")
    ar = areaclip.cut(ar[ar.intersects(study_ll)])
    getc = lambda c: ar[c] if c in ar else pd.Series(None, index=ar.index)
    r_feat = gpd.GeoDataFrame({"n": ar["name"], "c": ar.cls, "sf": getc("surface"), "tt": getc("tracktype"),
                               "sm": getc("smoothness"), "fs": getc("fs_id"), "lv": getc("fs_level"),
                               "se": getc("seasonal"), "ac": getc("access_conditional"),
                               "mv": getc("mvum"), "od": getc("open_dates"), "cw": getc("closed_why")},
                              geometry=shapely.set_precision(ar.geometry.simplify(0.00004).values, 1e-5), crs=4326)
    print("access roads:")
    roads_json = json.loads(beside_creeks(r_feat).to_json(na="drop", drop_id=True))
    # named unpaved roads get labels too (fire roads used to be labelled as trails)
    named_r = r_feat[r_feat.n.notna() & r_feat.c.ne("paved") & ~r_feat.n.isin(set(t_feat.n.dropna()))].to_crs(EPSG)
    for nm, grp in named_r.groupby("n"):
        for ln in merge_lines(grp.geometry.values):
            if ln.length >= 1600:
                trail_labels += [dict(lab, t=nm) for lab in label_paths(ln, TRAIL_BANDS, len(nm) * 5.6 + 6)]
    print("access roads", len(r_feat), "|", r_feat.c.value_counts().to_dict())
if os.path.exists(f"{SHARED}/parking_trailheads.gpkg"):
    pk = gpd.read_file(f"{SHARED}/parking_trailheads.gpkg")
    pk = areaclip.cut(pk[pk.intersects(study_ll)])
    park_json = json.loads(gpd.GeoDataFrame(
        {"k": pk.kind, "n": pk["name"], "u": pk.url, "no": pk.note, "fee": pk.fee, "cap": pk.capacity,
         "p": pk.parking.fillna(False).astype(int), "src": pk.source,
         "st": pk["status"] if "status" in pk else None},
        geometry=pk.geometry, crs=4326).to_json(na="null", drop_id=True))
    print("parking / trailheads", len(pk), "|", pk.kind.value_counts().to_dict())
print("trails", len(t_feat), "ways |", t_feat.groupby("rk").size().to_dict(), "| labels per zoom band:",
      pd.Series([l["z"] for l in trail_labels], dtype=int).value_counts().sort_index().to_dict())
# The layers both maps draw (streams, drainage fills and divides, the long trail, trails, roads, parking, their labels)
# are written once, to map3d_data.js at the end of this script: this page loads that file and points the globals
# map_drainages.js reads at its entries. They used to be inlined here as well, a second copy of the same data (231 MB
# over the 12 areas, 2026-11-20); the published site has a 1 GB limit.
SHARED_3D = {"STREAMS": "streams", "STREAMS_LAKE": "streams_lake", "FORKS": "forks", "DIVIDES": "divides", "DRAINS": "drains", "LBL": "lbl",
             "PCT": "pct", "PCT_LABEL_LINES": "pct_labels", "TRAILS": "trails", "TRAIL_LABEL_LINES": "trail_labels",
             "ROADS": "roads", "PARKING": "parking"}
m.get_root().header.add_child(folium.Element(
    '<script src="map3d_data.js"></script>\n<script>(function (D) {'
    + " ".join(f"window.{g} = D.{k};" for g, k in SHARED_3D.items()) + "})(window.MAP3D || {});</script>"))
# map_phone.css/.js (the one-line credits on phones and the "my location" button) are shared with 13_overview.py and
# 14_portable.py
_page_file = lambda f_: open(os.path.join(os.path.dirname(__file__), f_)).read()
m.get_root().header.add_child(folium.Element(
    "<style>" + _page_file("map_style.css") + _page_file("map_phone.css") + "</style>\n<script>"
    + _page_file("map_phone.js") + _page_file("map_drainages.js") + "</script>"))

# every layer is also exported for the 3D map: the shared ones to map3d_data.js, the rest into stream_map_3d.html
X3D = {"streams": json.loads(s_feat.to_json(na="null", drop_id=True)),
       "streams_lake": json.loads(s_feat_lake.to_json(na="null", drop_id=True)), "forks": f_json, "divides": d_json,
       "drains": drains, "home": HOME, "pct": pct_json, "pct_labels": pct_labels, "lbl": LBL}
gj = lambda g: json.loads(g.to_json(na="null", drop_id=True))

top = s_feat[s_feat.fs >= 55][["geometry"]]
folium.GeoJson(top.to_json(), name="<span style='color:#e8590c'>━</span> Best remote trout water (score ≥ 55)",
               show=False, style_function=lambda f: {"color": "#e8590c", "weight": 6, "opacity": 0.55,
                                                     "interactive": False}).add_to(m)   # clicks reach the stream

X3D["trails"] = json.loads(t_feat.to_json(na="drop", drop_id=True))
X3D["trail_labels"] = trail_labels
X3D["roads"], X3D["parking"] = roads_json, park_json
drops3d = []

# magenta / yellow / violet: validated all-pairs for color-blind separation and kept clear of the blue-green streams;
# drops at mapped waterfalls are neutral ink (same encoding as profiles.html)
color = {"unmapped waterfall-like step": "#e87ba4", "unmapped cascade": "#eda100",
         "unmapped short fall (big creek)": "#6250d6",
         "matches mapped waterfall": "#3b3a37", "steep reach": "#adb5bd",
         "likely DEM artifact": "#868e96", "dam / weir": "#495057"}
hidden = {"steep reach", "likely DEM artifact", "dam / weir"}
groups = {k: folium.FeatureGroup(name=f"<span style='color:{color[k]}'>●</span> Drops: {k}", show=False) for k in color}
for r in kp_ll.rename(columns={"pass": "pass_n"}).itertuples():   # "pass" is a keyword: itertuples would rename it
    gm = f"https://www.google.com/maps/@?api=1&map_action=map&center={r.lat},{r.lon}&zoom=18&basemap=satellite"
    html = (f"<b>{r.stream if isinstance(r.stream, str) and r.stream else 'unnamed drainage'}</b> · {r.region}<br>{r.status}<br>"
            f"{r.kind}<br>Drop <b>{ft(r.drop_m)}</b> over {ft(r.run_m)} (max slope {r.max_slope:.2f})<br>"
            f"Channel slope above {r.slope_above} / below {r.slope_below} · knick ×{r.knick_ratio}<br>"
            + (f"Excess drop over creek trend <b>{ft(r.excess_drop_m)}</b> · DEM pool depth {ft(r.pool_depth_m)}<br>"
               if r.pass_n == 2 else "") +
            f"Drainage {sqmi(r.area_km2)} · "
            + (f"summer: {r.water_class}" + (f" (about {cfs(r.dry_cfs)} cfs typical low flow)" if pd.notna(r.dry_cfs) else "")
               if isinstance(r.water_class, str) and r.water_class != "no data" else f"NHD {r.flow}")
            + f" · elev {ft(r.elev_m)}<br>"
            f"<b>Access:</b> {approach(r)}<br>"
            + (f"Shade: {r.sun_hours:.1f} h direct sun mid-July ({r.shade_pct:.0f}% shaded)<br>" if pd.notna(r.sun_hours) else "")
            + (f"<span style='color:#a61e4d'>Burned: {r.burn_fire} fire {r.burn_year:.0f}</span><br>" if pd.notna(r.burn_year) else "")
            + (f"<span style='color:#2b8a3e'>{r.trout_water}</span><br>" if isinstance(r.trout_water, str) else "")
            + (f"<span style='color:#c92a2a'>⚠ Critical habitat: {r.crit_habitat} (check seasonal closures)</span><br>"
               if isinstance(r.crit_habitat, str) else "")
            + (f"{r.wilderness} (no bikes)<br>" if isinstance(r.wilderness, str) else "")
            + (f"<span style='color:#c92a2a'>⚠ {r.cpad_access}</span><br>" if isinstance(r.cpad_access, str) else "")
            + (f"<i>Bike legs use closed roads, fire roads, bike paths and bike-legal trails; some closure orders ban "
               f"all entry, check first.</i><br>"
               if pd.notna(r.bike_min) and r.bike_min >= 1 else "")
            + (f"<span style='color:#c92a2a'>⚠ Road closure {mi(r.closure_m / 1000)} away: {r.closure_road}</span><br>"
               if isinstance(r._asdict().get("closure_road"), str) else "") +
            f"Top {r.lat}, {r.lon}<br>Pool/base {r.pool_lat}, {r.pool_lon}<br>"
            f"<a href='{gm}' target='_blank'>Satellite view</a>"
            + (f" · <a href='profiles.html#q={quote(r.stream)}&lat={r.lat}&lon={r.lon}' target='_blank'>Creek profile ↗</a>"
               if isinstance(r.stream, str) else ""))
    folium.CircleMarker([r.lat, r.lon], radius=3 + min(r.drop_m, 80) / 8, color=color[r.status], weight=1.5,
                        fill=True, fill_opacity=0.7, popup=folium.Popup(html, max_width=300),
                        tooltip=f"{ft(r.drop_m)} drop").add_to(groups[r.status])
    drops3d.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                    "properties": {"s": r.status, "c": color[r.status], "h": round(float(r.drop_m), 1), "html": html,
                                   "pool": [r.pool_lon, r.pool_lat] if r.status in SHOW else None}})
    if r.status in SHOW:
        folium.CircleMarker([r.pool_lat, r.pool_lon], radius=3, color="#0b7285", fill=True, fill_opacity=1,
                            tooltip="plunge pool / base").add_to(groups[r.status])
for g in groups.values():
    g.add_to(m)
X3D["drops"] = {"type": "FeatureCollection", "features": drops3d}
X3D["drop_colors"] = color
# Diamond and triangle symbols as small SVG icons: folium's RegularPolygonMarker (leaflet-dvf) needs the SVG renderer
# and throws on this canvas map whenever the layer is shown and the map moves
FALL_SVG = ('<svg width="16" height="16" viewBox="0 0 16 16"><rect x="4" y="4" width="8" height="8" '
            'transform="rotate(45 8 8)" fill="#74c0fc" stroke="#0b3d91" stroke-width="2"/></svg>')
GAUGE_SVG = ('<svg width="18" height="16" viewBox="0 0 18 16"><path d="M9 1.5 L17 15 L1 15 Z" fill="{c}" stroke="#212529" '
             'stroke-width="1.2"/></svg>')
svg_icon = lambda html, w, h: folium.DivIcon(html=html, icon_size=(w, h), icon_anchor=(w // 2, h // 2), class_name="svgpin")
for c in ("note", "kind", "url"):     # ranges scored before 02f_known_falls.py have only name, src (and note)
    if c not in known_falls:
        known_falls[c] = None
# names and notes quoted from the sources keep their words, with feet (or miles) in brackets after each metric figure:
# CDFW's surveyors write "2.5 meters [8.2 ft] wide by 2.5 feet high" (units.py)
known_falls["name"] = known_falls.name.map(imperial_text)
known_falls["note"] = known_falls.note.map(imperial_text)
def fall_html(r):
    """The known fall's popup, shared by the 2D, 3D and one-file maps: name, kind, sources, note, the source's page."""
    nm_ = r.name if isinstance(r.name, str) and r.name else "waterfall"
    kind_ = r.kind if isinstance(r.kind, str) and r.kind not in ("", "waterfall") else ""
    note = r.note if isinstance(r.note, str) and r.note else ""
    url = r.url if isinstance(r.url, str) and r.url.startswith("http") else ""
    return (f"<b>{hesc(nm_)}</b>" + (f" · {hesc(kind_)}" if kind_ else "") + f"<br><span style='color:#6b7280'>{hesc(r.src)}</span>"
            + (f"<br>{hesc(note)}" if note else "") + (f"<br><a href='{hesc(url)}' target='_blank'>Source page ↗</a>" if url else ""))
known_falls["html"] = [fall_html(r) for r in known_falls.itertuples()]
kf = folium.FeatureGroup(name=f"<span style='color:#0b3d91'>◆</span> {LBL['falls']}", show=False)
for r in known_falls.itertuples():
    nm_ = r.name if isinstance(r.name, str) and r.name else "waterfall"
    folium.Marker([r.geometry.y, r.geometry.x], icon=svg_icon(FALL_SVG, 16, 16),
                  popup=folium.Popup(r.html, max_width=300), tooltip=f"{nm_} ({r.src})").add_to(kf)
kf.add_to(m)
X3D["falls"] = gj(known_falls[["name", "src", "note", "kind", "html", "geometry"]].assign(name=known_falls.name.fillna("waterfall")))

def r6(gs):
    """Outlines from other sources (road closures, PAD-US, USFS land status, state trout waters, critical habitat,
    wilderness, fire perimeters) come with 15 decimals. 6 (10 cm) draws them the same and takes a third of the space
    (67 MB over the 12 areas, 2026-11-20); the rest of the map is written at 5 (set_precision 1e-5)."""
    return gpd.GeoSeries(shapely.transform(np.asarray(gs.values), lambda c: np.round(c, 6)), index=gs.index, crs=gs.crs)


if closures is not None and len(closures):
    fetched = closures.fetched.iloc[0]
    if "times" not in closures:     # 07_road_closures.py before 2026-11-22: whether the approach times count it
        closures["times"] = ""
    c_show = closures.assign(**{c: closures[c].fillna("") for c in ("road", "from", "to", "reason", "start", "end", "when", "times")},
                             geometry=r6(closures.geometry))
    folium.GeoJson(c_show[["source", "road", "from", "to", "severity", "reason", "when", "start", "end", "times", "geometry"]].to_json(),
                   name=f"<span style='color:#c92a2a'>▬</span> Road closures (fetched {fetched})", show=False,
                   style_function=lambda f: {
                       "color": "#c92a2a" if f["properties"]["severity"].startswith("full") else "#f76707",
                       "weight": 7 if f["properties"]["severity"] == "full closure" else 5, "opacity": 0.85,
                       "dashArray": None if f["properties"]["severity"].startswith("full") else "8 6"},
                   tooltip=folium.GeoJsonTooltip(["road", "severity", "when", "from", "to", "reason", "start", "end", "times", "source"],
                                                 aliases=["Road", "Closure", "Status", "From", "To", "Reason", "Start",
                                                          "End / reopen", "Approach times", "Source"])).add_to(m)
    X3D["closures"] = gj(c_show[["road", "from", "to", "severity", "reason", "when", "start", "end", "times", "source", "geometry"]])
    X3D["closures_fetched"] = str(fetched)
if gated is not None and len(gated) and roads_json is None:   # older runs: the access-road layer replaces this
    folium.GeoJson(gated.assign(geometry=shapely.set_precision(gated.geometry.simplify(0.0001).values, 1e-5)).to_json(),
                   name="Gated / no public vehicles (OSM)", show=False,
                   style_function=lambda f: {"color": "#862e9c", "weight": 2.5, "dashArray": "1 5", "opacity": 0.9},
                   tooltip=folium.GeoJsonTooltip(["name", "highway", "access", "motor_vehicle"],
                                                 aliases=["Road", "Type", "Access", "Motor vehicle"])).add_to(m)

# ---- fire closure areas (LA County's Eaton Fire closures, via 02d_trails.py) ----
if os.path.exists(f"{SHARED}/closure_areas.gpkg"):
    ca_ = gpd.read_file(f"{SHARED}/closure_areas.gpkg")
    ca_ = ca_.assign(geometry=r6(ca_.geometry))
    folium.GeoJson(ca_.to_json(), name="<span style='color:#c92a2a'>▧</span> Fire closure areas (Eaton Fire)", show=False,
                   style_function=lambda f: {"color": "#c92a2a", "weight": 2, "dashArray": "6 4", "fillColor": "#c92a2a",
                                             "fillOpacity": 0.1},
                   tooltip=folium.GeoJsonTooltip(["Agency", "Closure_Date"], aliases=["Closed by", "Since"])).add_to(m)
    X3D["closure_areas"] = gj(ca_)

# ---- lakes (05d_lakes.py, in the areas where they are built; maplakes.py) ----
import maplakes
maplakes.add(m, X3D, done, approach)

# ---- context layers (11_context.py) ----
fires = ctx("fires")
if fires is not None:
    if "src" not in fires:
        fires["src"] = LBL["fire_src"]
    fcm = matplotlib.colormaps["YlOrRd"]
    yr0, yr1 = fires.year.min(), fires.year.max()
    fires = fires.assign(geometry=r6(fires.geometry.simplify(0.0003)))
    folium.GeoJson(fires.to_json(), name=LBL["fires"],
                   show=False, style_function=lambda f: {
                       "color": colors.to_hex(fcm(0.3 + 0.7 * (f["properties"]["year"] - yr0) / max(yr1 - yr0, 1))),
                       "weight": 1, "fillOpacity": 0.25},
                   tooltip=folium.GeoJsonTooltip(["fire", "year", "acres", "src"], aliases=["Fire", "Year", "Acres", "Perimeter"])).add_to(m)
    X3D["fires"] = gj(fires[["fire", "year", "acres", "src", "geometry"]].assign(
        c=[colors.to_hex(fcm(0.3 + 0.7 * (y - yr0) / max(yr1 - yr0, 1))) for y in fires.year]))
for name, label, style, fields in [
        ("wild_trout_waters", LBL["trout_waters"],
         {"color": "#2b8a3e", "weight": 2, "fillOpacity": 0.15}, (["Name", "Designation", "Designation_Boundary"],
                                                                    ["Water", "Designation", "Boundary"])),
        ("critical_habitat", "Critical habitat, stream species (not closure boundaries)",
         {"color": "#c92a2a", "weight": 1.6, "fillOpacity": 0.22, "dashArray": "4 3"}, (["species", "unit"], ["Species", "Unit"])),
        ("wilderness", "Wilderness (no bikes)",
         {"color": "#5c940d", "weight": 1.5, "fillOpacity": 0.06}, (["wilderness"], ["Wilderness"])),
        ("non_fs_land", "Non-Forest-Service land inside the forests",
         {"color": "#e67700", "weight": 1, "fillOpacity": 0.2}, (["ownerclassification"], ["Owner"])),
        ("cpad_restricted", LBL["access"],
         {"color": "#d9480f", "weight": 1, "fillOpacity": 0.25, "dashArray": "2 3"},
         (["ACCESS_TYP", "UNIT_NAME", "MNG_AGNCY"], ["Access", "Unit", "Manager"]))]:
    g = ctx(name)
    if g is not None and len(g):
        g = g.assign(geometry=r6(g.geometry.simplify(0.0002)))
        folium.GeoJson(g[fields[0] + ["geometry"]].to_json(), name=label, show=False,
                       style_function=lambda f, st=style: st,
                       tooltip=folium.GeoJsonTooltip(fields[0], aliases=fields[1])).add_to(m)
        X3D[name] = gj(g.assign(tip=[" · ".join(str(v) for v in row if isinstance(v, str) and v)
                                     for row in g[fields[0]].itertuples(index=False)])[["tip", "geometry"]])
gauges = ctx("gauges")
if gauges is not None and len(gauges):
    gcol = {"much below normal": "#c92a2a", "below normal": "#f76707", "normal": "#2b8a3e", "above normal": "#1c7ed6",
            "much above normal": "#1864ab", "dry": "#c92a2a", "dry (normal for date)": "#adb5bd",
            "flowing (usually dry on this date)": "#1c7ed6", "no history": "#868e96"}
    g3 = []
    gg = folium.FeatureGroup(name=f"<span style='color:#1c7ed6'>▲</span> {LBL['gauges']} (live, {gauges.time.max()[:10]})",
                             show=False)
    for r in gauges.itertuples():
        html = (f"<b>{r.name}</b><br>{r.cfs:g} cfs at {r.time}<br>{r.status}"
                + (f" · {r.pct_of_median:.0f}% of median for today" if pd.notna(r.pct_of_median) else "")
                + (f"<br>Median for this date {r.p50:g} cfs" if pd.notna(r.p50) else "")
                + f"<br><a href='{r.url}' target='_blank'>{'CDEC' if str(r.site).startswith('CDEC') else 'USGS'} station page</a>")
        folium.Marker([r.geometry.y, r.geometry.x], icon=svg_icon(GAUGE_SVG.format(c=gcol.get(r.status, "#868e96")), 18, 16),
                      popup=folium.Popup(html, max_width=280), tooltip=f"{r.name}: {r.cfs:g} cfs ({r.status})").add_to(gg)
        g3.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.geometry.x, r.geometry.y]},
                   "properties": {"c": gcol.get(r.status, "#868e96"), "html": html,
                                  "tip": f"{r.name}: {r.cfs:g} cfs ({r.status})"}})
    X3D["gauges"] = {"type": "FeatureCollection", "features": g3}
    gg.add_to(m)

# trout evidence and springs (11_context.py)
tev = ctx("trout_evidence")
if tev is not None and len(tev):
    TCOL = {"CDFW survey": "#2b8a3e", "CDFW stocking": "#1c7ed6", "iNaturalist": "#82c91e"}
    tgrp, t3 = folium.FeatureGroup(name=f"<span style='color:#2b8a3e'>●</span> {LBL['trout_ev']}", show=False), []
    for r in tev.sort_values("kind", ascending=False).itertuples():
        col = (TCOL.get(r.kind) or ("#1c7ed6" if r.kind.endswith("stocking") else "#2b8a3e")) if r.trout else "#e03131"
        head = r.water if isinstance(r.water, str) and r.water else r.kind
        lab = r.label + (" (at a lake: likely stocked)" if r.lake and r.kind == "iNaturalist" else "")
        html_ = (f"<b>{hesc(head)}</b><br>{hesc(lab)}"
                 + (f"<br><a href='{hesc(r.url)}' target='_blank'>iNaturalist record ↗</a>" if isinstance(r.url, str) and r.url else ""))
        folium.CircleMarker([r.geometry.y, r.geometry.x], radius=4.5 if r.kind == "iNaturalist" else 7, color="#ffffff",
                            weight=1.2, fill=True, fill_color=col, fill_opacity=0.95, popup=folium.Popup(html_, max_width=300),
                            tooltip=f"{head}: {lab}").add_to(tgrp)
        t3.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(r.geometry.x, 5), round(r.geometry.y, 5)]},
                   "properties": {"c": col, "r": 4.5 if r.kind == "iNaturalist" else 7, "html": html_, "tip": f"{head}: {lab}"}})
    tgrp.add_to(m)
    X3D["trout"] = {"type": "FeatureCollection", "features": t3}
spr = ctx("springs")
if spr is not None and len(spr):
    sgrp = folium.FeatureGroup(name="<span style='color:#1098ad'>●</span> Springs and seeps (NHD)", show=False)
    tips = [f"{n} (spring, NHD)" if isinstance(n, str) and n else "Spring or seep (NHD)" for n in spr.gnis_name]
    for g_, t_ in zip(spr.geometry, tips):
        folium.CircleMarker([g_.y, g_.x], radius=3.5, color="#0b7285", weight=1, fill=True, fill_color="#66d9e8",
                            fill_opacity=1, tooltip=t_).add_to(sgrp)
    sgrp.add_to(m)
    X3D["springs"] = gj(spr.assign(tip=tips, geometry=shapely.set_precision(spr.geometry.values, 1e-5))[["tip", "geometry"]])

# trailheads used by good water or shown drops, with drive time from HOME
used = pd.concat([s_ll.loc[s_ll.fish_score >= 50, ["th_id", "th_road", "th_lat", "th_lon", "drive_min", "drive_km"]],
                  kp_ll.loc[kp_ll.status.isin(SHOW), ["th_id", "th_road", "th_lat", "th_lon", "drive_min", "drive_km"]]])
used = used.dropna(subset=["th_lat"]).drop_duplicates("th_id")
tg = folium.FeatureGroup(name=f"<span style='color:#e0a800'>●</span> Approach start points (computed; drive from {HOME['label']})",
                         show=False)
for r in used.itertuples():
    folium.CircleMarker([r.th_lat, r.th_lon], radius=4, color="#212529", weight=1, fill=True, fill_color="#ffd43b",
                        fill_opacity=1, tooltip=f"P · {r.th_road if isinstance(r.th_road, str) else 'road end'} · "
                        + (f"{r.drive_min:.0f} min / {mi(r.drive_km)} drive" if pd.notna(r.drive_min) else "no drive route")
                        ).add_to(tg)
tg.add_to(m)
X3D["trailheads"] = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.th_lon, r.th_lat]},
     "properties": {"tip": f"P · {r.th_road if isinstance(r.th_road, str) else 'road end'} · "
                           + (f"{r.drive_min:.0f} min / {mi(r.drive_km)} drive" if pd.notna(r.drive_min) else "no drive route")}}
    for r in used.itertuples()]}
folium.Marker([HOME["lat"], HOME["lon"]], tooltip=f"Start: {HOME['label']}",
              icon=folium.Icon(color="darkblue", icon="home")).add_to(m)

# Legend, drainage list, colour-mode switch, labels and #lat,lon,zoom links (from the profile viewer) are built by
# initDrainageMap in map_drainages.js, which runs once the map and layer control exist.
lc = folium.LayerControl(collapsed=True, position="topright")
lc.add_to(m)
MeasureControl(primary_length_unit="miles", secondary_length_unit="feet", primary_area_unit="acres",
               secondary_area_unit="sqmiles", position="bottomright").add_to(m)
Fullscreen(position="topleft").add_to(m)

class InitDrainages(MacroElement):
    _template = Template("""{% macro script(this, kwargs) %}
initDrainageMap({{ this._parent.get_name() }}, {{ this.ctrl }});
{% endmacro %}""")
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
m.add_child(InitDrainages(lc.get_name()))
m.save(f"{MAP_OUT}/stream_map.html")

# ---- this area's part of the map of all areas (13_overview.py): drainage outlines and the main rivers ----
def simplify_together(geoms, tol):
    """Simplify polygons as one coverage, so neighbours keep exactly the same edge between them (each on its own,
    they pull apart and overlap along the divides). Rebuilt first from their noded boundaries, as in 05c."""
    geoms = shapely.make_valid(np.asarray(geoms))
    faces = np.asarray(shapely.get_parts(shapely.polygonize(shapely.get_parts(
        shapely.node(shapely.union_all(shapely.boundary(geoms)))))))
    inp, owner = shapely.STRtree(geoms).query(shapely.point_on_surface(faces), predicate="within")
    inp, first_ = np.unique(inp, return_index=True)                  # where two overlap, the face goes to one
    simp = gpd.GeoDataFrame({"i": owner[first_]}, geometry=shapely.coverage_simplify(faces[inp], tol)).dissolve("i")
    out = geoms.copy()
    out[simp.index.values] = simp.geometry.values
    return out
ov_d = dpoly[["drainage", "km2", "geometry"]].assign(geometry=simplify_together(dpoly.geometry.values, 120)).to_crs(4326)
ov_d = ov_d.assign(c=[dcol[d_] for d_ in ov_d.drainage], km2=ov_d.km2.round(1),
                   geometry=shapely.set_precision(shapely.make_valid(ov_d.geometry.values), 1e-5))
ov_s = s_ll[s_ll.strahler >= 4][["name", "drainage", "strahler", "fish_score", "geometry"]]   # whole: no lakes drawn there
ov_s = ov_s.assign(c=[dcol.get(d_, MINOR_COL) for d_ in ov_s.drainage],
                   geometry=shapely.set_precision(ov_s.geometry.simplify(0.0004).values, 1e-5))
ov_s = ov_s[~ov_s.geometry.is_empty]
sb = study_ll.bounds
# the long trail, for the maps of all areas (drawn there from the start, like here)
ov_t = None
if pct_json:
    tl = gpd.GeoDataFrame.from_features(pct_json["features"], crs=4326)
    tl = tl.assign(geometry=shapely.set_precision(tl.geometry.simplify(0.0004).values, 1e-5))
    ov_t = json.loads(tl[~tl.geometry.is_empty][["label", "geometry"]].to_json(drop_id=True))
with open(f"{MAP_OUT}/overview.json", "w") as f:
    json.dump(dict(key=AREA, label=AREA_LABEL, home=HOME, bounds=[[sb[1], sb[0]], [sb[3], sb[2]]],
                   reaches=int(len(s_ll)) - N_DRAWN_EXTRA, trail=ov_t, trail_name=LONG_TRAIL[0] if LONG_TRAIL else None, drains=[dict(name=e["name"], color=e["color"], km2=e["km2"], lab=e["lab"])
                                                    for e in drains if e["name"] != MINOR],
                   basins=json.loads(ov_d.to_json(drop_id=True)), streams=json.loads(ov_s.to_json(na="null", drop_id=True))), f)
# 3D map: map3d_data.js holds the layers both maps draw (SHARED_3D; the 2D page loads it too). The layers only the 3D
# map draws go into its page (map3d.html), right after its <script src="map3d_data.js">. Plain <script>s, so both maps
# also work opened straight from disk. 14_portable.py reads both parts.
with open(f"{MAP_OUT}/map3d_data.js", "w") as f:
    f.write("window.MAP3D=" + json.dumps({k: X3D[k] for k in SHARED_3D.values() if k in X3D}, separators=(",", ":"),
                                         default=str) + ";\n")
only3d = json.dumps({k: v for k, v in X3D.items() if k not in SHARED_3D.values()}, separators=(",", ":"), default=str)
only3d = only3d.replace("</", "<\\/").replace("<!--", "<\\u0021--")     # nothing in it can end or upset the <script>
page3d = open(os.path.join(os.path.dirname(__file__), "map3d.html")).read()
tag3d = '<script src="map3d_data.js"></script>'
assert page3d.count(tag3d) == 1, "map3d.html must load map3d_data.js once"
with open(f"{MAP_OUT}/stream_map_3d.html", "w") as f:
    f.write(page3d.replace(tag3d, tag3d + "\n<script>if (window.MAP3D) Object.assign(window.MAP3D, " + only3d
                           + ");</script>"))

print("streams", len(s_ll), "| drops", len(kp_ll))
print(kp_ll.groupby(["region", "status"]).size().unstack(fill_value=0).to_string())
