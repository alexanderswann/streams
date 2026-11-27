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
    credits="USGS National Digital Trails · USFS · " + ("California State Parks · " if has("la_trail_layers") else "")
            + ("CDFW · " if CA else "") + "iNaturalist · "
            + ("CAL FIRE · " if has("cal_fire") else "NIFC fire history · ") + "NIFC WFIGS · USGS gauges &amp; debris-flow hazard · "
            + ("CDEC · " if has("cdec") else "") + ("TNC Natural Flows" if has("tnc_flows") else "NHDPlus V2 (EROM)")
            + " · PRISM Group, Oregon State University · known falls: OSM, USGS GNIS, Wikidata and the guides named in each")
from scoring import attach, score, SIDE_NHD, SIDE_BELOW, THIS_YEAR
import crossbox
import areaclip      # an area that stops at a state line (config clip_state) shows nothing past it
import approach_routes   # each reach's route from its trailhead, drawn on a click (08_hike.py builds them)
import weblib        # the pages' libraries from the site's lib/, and the offline web app (sw.js, offline.js)

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
# the credits page (credits.html at the site root, from credits.py: every source, its terms and the maps it covers)
# heads the credits of both maps
LBL["credits"] = "<a href='../credits.html' target='_blank'>Data sources</a> · " + LBL["credits"]
# Overture Maps places among the known falls (02f_known_falls.py): its licences ask for the credit, and the licence
# texts and Foursquare's notice go with the data (2026-11-23)
if known_falls.src.str.contains("Overture Maps", regex=False).any():
    LBL["credits"] += (" · places: <a href='https://overturemaps.org' target='_blank'>Overture Maps Foundation</a>, "
                       "<a href='https://cdla.dev/permissive-2-0/' target='_blank'>CDLA-Permissive-2.0</a>; includes "
                       "Foursquare data © 2024 Foursquare Labs, Inc., <a href='https://www.apache.org/licenses/LICENSE-2.0' "
                       "target='_blank'>Apache-2.0</a> (<a href='https://docs.overturemaps.org/attribution/' target='_blank'>"
                       "notice</a>)")
# Sentinel-2's late-summer greenness (02g_greenness.py) goes into the summer flow classes and the fish score where the
# area has it: the Copernicus terms ask for their credit (2026-11-24)
if has("late_summer_green"):
    from flowlib import SENTINEL_CREDIT
    LBL["credits"] += " · " + SENTINEL_CREDIT
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
# (the reaches 05_score.py left out as buried, buried_reaches.gpkg, with their drainage, buried_areas.csv: the
# bare-channel test reads its creeks with them, and a lake's creek below a dam is looked for among them too)
def left_out(d_):
    lo_ = gpd.read_file(f"{d_}/buried_reaches.gpkg")
    if os.path.exists(f"{d_}/buried_areas.csv"):
        lo_["area_full_km2"] = pd.read_csv(f"{d_}/buried_areas.csv").set_index("row").area_full_km2.reindex(
            lo_["row"]).to_numpy(float)
    return lo_
def net_rows(d_):
    """d_ without the lines 03b_stitch.py laid lower along NHD's lines and the links drawn only for them (05_score.py's
    low_channel 1 and 2): the paths drawn through below dams and at the edges read the 0.25 km2 network's reaches."""
    return d_[pd.to_numeric(d_["low_channel"], errors="coerce").fillna(0).to_numpy() == 0] if "low_channel" in d_ else d_
_lo = [left_out(d_) for d_ in dirs if os.path.exists(f"{d_}/buried_reaches.gpkg")]
s_ll = score(attach(s_ll.drop(columns="fish_score"), "sid", dirs, "streams"),
             left_out=pd.concat(_lo, ignore_index=True) if _lo else None)
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
# (stream order: 05c_drainages.py, which raises it where water comes in that the routing doesn't see)
# ---- creeks drawn through below dams and at the outer boundary ----
# Across the edges two boxes share, the streams run through by themselves since 2026-11-19 (03b_stitch.py routes
# the boxes together). Two kinds of break are left, where the routing really does stop: below a dam (paths end
# in the lake) and where a river comes in over the outer boundary of the map (its line starts only where 0.25 km2
# has gathered inside). crossbox.crossings() knows each place: from the cell the water goes on from, the box's own
# D8 path is followed to its first drawn reach, and that piece goes on the front of the reach, or, where it runs
# into the middle of one, is drawn as a piece of its own with that reach's values. Drawn lines only: the reaches
# keep their ids, scores and areas.
# Since 2026-11-22 a river from outside the map is a reach of its own from where its water goes in (05_score.py lays it:
# crossbox.lead_ins), and a break whose cell a reach starts on is not drawn through: the path ran along that reach where
# its corner-to-corner line left the cells' centres unmarked, and drew it twice (318 pieces, 11.5 km, over the 12 maps;
# 126 m of McCoy Creek on the Jackson map). Where no reach starts there (no lead-in was kept), the path is drawn as before.
def draw_through(s_ll):
    from rasterio import features as rfeatures
    cross = [c_ for c_ in crossbox.crossings() if c_[6] >= 0.25 and c_[3] in done and c_[7] != "edge"]
    sm = s_ll.geometry.to_crs(EPSG).values
    # not on a line 03b_stitch.py laid lower along NHD's lines (low_channel): drawn as without them
    low_ = (pd.to_numeric(s_ll["low_channel"], errors="coerce").fillna(0).to_numpy() > 0) if "low_channel" in s_ll \
        else np.zeros(len(s_ll), bool)
    line = np.array([g is not None and g.geom_type == "LineString" for g in sm]) & ~low_
    rk = s_ll.sid.str.split(":").str[0].values
    pos = np.flatnonzero(line)
    heads = shapely.STRtree(shapely.points([sm[i].coords[0][:2] for i in pos]))
    ends = shapely.STRtree(shapely.points([sm[i].coords[-1][:2] for i in pos]))
    all_lines = shapely.STRtree(sm[pos])
    ras, recs, bur, n_bur, m_bur = {}, [], {}, 0, 0.0
    # 1. each break: the path below it, the reach it runs into (if any) and the reach that ends above it (if any)
    for src, ex, ey, b, row, col, km2, kind in cross:
        if b not in ras:
            with rasterio.open(crossbox.fdir_path(b)) as f_:
                fd_, T_ = f_.read(1), f_.transform
            # the cells this box's drawn reaches run through (not every stream cell of 03 has a reach: short stubs
            # are dropped), so the line is carried down to one that is drawn; and those of the reaches 05_score.py
            # left out as buried (buried_reaches.gpkg), where it stops as it did while they were drawn
            bp_ = f"{MAP_OUT}/{b}/buried_reaches.gpkg"
            bg_ = (net_rows(gpd.read_file(bp_)).to_crs(EPSG).geometry.values if os.path.exists(bp_)
                   else np.array([], dtype=object))
            bur[b] = (bg_, shapely.STRtree(bg_) if len(bg_) else None)
            ras[b] = (fd_, T_, rfeatures.rasterize([(g, 1) for g in sm[pos[rk[pos] == b]]], out_shape=fd_.shape,
                                                   transform=T_, all_touched=True, dtype="uint8"),
                      rfeatures.rasterize([(g, 1) for g in bg_], out_shape=fd_.shape, transform=T_, all_touched=True,
                                          dtype="uint8") if len(bg_) else np.zeros(fd_.shape, dtype="uint8"))
        fd_, T_, on_, bon_ = ras[b]
        H_, W_ = fd_.shape
        if kind == "outside" and any(rk[pos[j]] == b for j in heads.query(shapely.Point(T_ * (int(col), int(row))),
                                                                          predicate="dwithin", distance=1.0)):
            continue                                       # a reach starts on its cell: the lead-in
        r_, c_, pts = int(row), int(col), []
        for _ in range(800):                               # 8 km at most
            pts.append(T_ * (c_ + 0.5, r_ + 0.5))
            if on_[r_, c_] or bon_[r_, c_]:
                break
            d_ = crossbox.D8.get(int(fd_[r_, c_]))
            if d_ is None or not (0 <= r_ + d_[0] < H_ and 0 <= c_ + d_[1] < W_):
                break
            r_, c_ = r_ + d_[0], c_ + d_[1]
        # a break past the state line of an area that stops at one is no line of this map, as a reach there isn't
        # (areaclip.inside: by its middle, or the water of the river that is the line). A New Jersey creek coming in
        # from outside southeastern Pennsylvania's north edge was drawn from it into the Delaware with the river's values
        if not areaclip.inside([shapely.LineString(pts) if len(pts) > 1 else shapely.Point(pts[0])])[0]:
            continue
        up = None
        if kind == "edge" and ex is not None:
            pt = shapely.Point(ex, ey)
            cand = [pos[j] for j in ends.query(pt, predicate="dwithin", distance=45) if rk[pos[j]] == src]
            up = min(cand, key=lambda i: shapely.Point(sm[i].coords[-1][:2]).distance(pt)) if cand else None
        hit = None
        if on_[r_, c_] or bon_[r_, c_]:                    # the reach it runs into, and the exact spot on it
            pt = shapely.Point(pts[-1])
            cand = [pos[j] for j in all_lines.query(pt, predicate="dwithin", distance=25) if rk[pos[j]] == b and pos[j] != up]
            # where the nearest is a reach 05_score.py left out as buried, the path runs into a creek a city has
            # buried and goes with it, as it was drawn on that reach or with its values (on the 12 maps' test of
            # 2026-11-24 such paths ran on down the buried line to the next drawn reach: 1.6 mi on 4 paths, two of
            # them with that reach's name)
            bg_, bt_ = bur[b]
            d_bur = min((bg_[j].distance(pt) for j in bt_.query(pt, predicate="dwithin", distance=25)),
                        default=np.inf) if bt_ is not None else np.inf
            if d_bur < min((sm[i].distance(pt) for i in cand), default=np.inf):
                n_bur, m_bur = n_bur + 1, m_bur + (shapely.LineString(pts).length if len(pts) > 1 else 0.0)
                continue
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
    # the ends of the reaches 05_score.py left out as buried, every box: a lake's creek is looked for among them too, as
    # while they were drawn, and a path whose creek is one of them goes with it (lake_creek() gives -1; not drawn)
    lo_g = [net_rows(left_out(f"{MAP_OUT}/{r_}")).to_crs(EPSG) for r_ in done
            if os.path.exists(f"{MAP_OUT}/{r_}/buried_reaches.gpkg")]
    lo_g = pd.concat(lo_g, ignore_index=True) if lo_g else None
    lo_end = shapely.points([g_.coords[-1][:2] for g_ in lo_g.geometry.values]) if lo_g is not None else None
    lo_km2 = ((lo_g.area_full_km2 if "area_full_km2" in lo_g else lo_g.area_km2).fillna(lo_g.area_km2).to_numpy(float)
              if lo_g is not None else None)
    lo_t = shapely.STRtree(lo_end) if lo_g is not None and len(lo_g) else None
    def lake_creek(r):
        p0 = shapely.Point(r["pts"][0])
        cand = [pos[j] for j in ends.query(p0, predicate="dwithin", distance=80) if pos[j] != r["hit"]]
        cand_lo = list(lo_t.query(p0, predicate="dwithin", distance=80)) if lo_t is not None else []
        if not cand and not cand_lo:
            return None
        # the nearest end, and among ends as near (within 1 m: one confluence) the reach carrying the most water. The
        # nearest alone fell to the spatial index's order, which a reach added anywhere on the map could flip: 25 m of
        # the Champlain Canal below a lock pool (1,085 km2) took a 0.8 km2 creek's "mostly dry" when a lead-in was laid
        # in another box (2026-11-23; on the published maps 3 pieces, 62 m, change, all year-round either way)
        d_ = {i: shapely.Point(sm[i].coords[-1][:2]).distance(p0) for i in cand}
        dl_ = {k: lo_end[k].distance(p0) for k in cand_lo}
        near = min(list(d_.values()) + list(dl_.values()))
        pool = [(False, i) for i in cand if d_[i] <= near + 1.0] + [(True, k) for k in cand_lo if dl_[k] <= near + 1.0]
        lo_, i = max(pool, key=lambda t: (lo_km2[t[1]], -dl_[t[1]]) if t[0] else (km2_[t[1]], -d_[t[1]]))
        if lo_:
            return -1
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
            if own is not None and own == -1:              # its creek is a reach left out as buried: not drawn
                n_bur, m_bur = n_bur + 1, m_bur + shapely.LineString(new).length
                continue
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
    redrawn_ = []
    if coords:
        idx_ = list(coords)
        redrawn_ = list(s_ll.sid.values[idx_])
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
    s_ll.attrs["redrawn"] = redrawn_                       # reaches drawn longer than 05_score.py made them
    print(f"creeks drawn through {n_head + n_own + n_up + n_creek} breaks below dams and at the outer boundary "
          f"({metres / 1000:.1f} km of line; {n_creek} as a lake's own creek joining a bigger stream; "
          f"{len(left)} met no drawn reach; {n_bur} ran into a reach a city has buried and aren't drawn, "
          f"{m_bur / 1000:.1f} km)")
    return s_ll
s_ll = draw_through(s_ll)
N_DRAWN_EXTRA = s_ll.attrs.get("drawn_extra", 0)      # pieces added for drawing: not reaches of their own
# ---- stream specs (streamspecs.py; the user, 2026-11-25): each reach's mean annual flow (cfs), NHDPlus's on the line
# 05b_flow.py matched it to (comid), scaled to its drainage as 05b scales that line's summer flows, and the elevation of
# its lower end (m), the DEM at its own lowest cell, where 05_score.py measures its gradient to (a piece drawn through a
# break above: at its own last point). The popups' specs line (map_specs.js) shows them with the order, drainage and
# gradient, and works out the velocity
import streamspecs
from config import raw_dir
s_ll["q_ann_cfs"] = streamspecs.mean_flow(s_ll["comid"].to_numpy() if "comid" in s_ll else np.full(len(s_ll), np.nan),
                                          s_ll.area_full_km2.fillna(s_ll.area_km2).to_numpy(float),
                                          streamspecs.nhdplus_flows(f"{SHARED}/flow"))
_sp_end = shapely.get_point(gpd.GeoSeries(s_ll.geometry.values, crs=4326).to_crs(EPSG).values, -1)
_sp_xy = [pd.to_numeric(s_ll[c_], errors="coerce").to_numpy(float) if c_ in s_ll else np.full(len(s_ll), np.nan)
          for c_ in ("own_x", "own_y")]
_sp_at_end = s_ll.sid.astype(str).str.contains("+", regex=False).to_numpy() | np.isnan(_sp_xy[0]) | np.isnan(_sp_xy[1])
_sp_x = np.where(_sp_at_end, shapely.get_x(_sp_end), _sp_xy[0])
_sp_y = np.where(_sp_at_end, shapely.get_y(_sp_end), _sp_xy[1])
_sp_box = s_ll.sid.astype(str).str.split(":").str[0].to_numpy()
_sp_z = streamspecs.lower_elev({b_: (_sp_x[_sp_box == b_], _sp_y[_sp_box == b_]) for b_ in done},
                               lambda b_: f"{raw_dir(b_)}/dem_10m.tif")
s_ll["elev_low_m"] = np.nan
for b_, z_ in _sp_z.items():
    s_ll.loc[_sp_box == b_, "elev_low_m"] = np.round(z_, 0)
print(f"stream specs: mean annual flow on {s_ll.q_ann_cfs.notna().sum():,} of {len(s_ll):,} reaches (NHDPlus V2 "
      f"{'found' if os.path.exists(f'{SHARED}/flow/nhdplus_v2.gpkg') else 'MISSING'}), the lower end's elevation on "
      f"{s_ll.elev_low_m.notna().sum():,}")
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
    # The lines 03b_stitch.py laid lower along NHD's named and year-round lines and the links drawn only for them
    # (low_channel 1 and 2) take no part in joining the basins across the edges: the network's reaches find the stream
    # across an edge, stand for a basin and decide a move, as without them, and the new lines follow their group's
    # (on the first try a new line by a seam in central Vermont took 0.03 km2 of the Winooski's outline into the
    # Huntington River's drainage, and the fork shades of 69 reaches moved)
    _lo6 = ((pd.to_numeric(s_ll["low_channel"], errors="coerce").fillna(0).to_numpy() > 0) if "low_channel" in s_ll
            else np.zeros(len(s_ll), bool))
    first_ = {g: int((ix[~_lo6[ix]] if (~_lo6[ix]).any() else ix)[0]) for g, ix in groups.items()}
    net_g = {g for g, ix in groups.items() if (~_lo6[ix]).any()}
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
    rep = s_ll.reset_index(drop=True)[~_lo6].groupby(["rkey", "drainage", "fork"]).area_km2.idxmax().to_dict()
    size_of = basins.assign(a=basins.area).groupby(["rkey", "drainage"]).a.sum().to_dict()
    def across_edge(g):
        pt = shapely.Point(g[1], g[2])
        mine = size_of.get((g[0], s_ll.drainage.iat[first_[g]]), 0)
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
                        if s_ll.rkey.iat[i] == b_ and not _lo6[i]]
                if cand:
                    target[g] = max(cand, key=lambda i: s_ll.area_km2.iat[i])
                    break
            if g in target:
                break
        if g not in target and g in groups and s_ll.drainage.iat[first_[g]] != MINOR:
            ti = across_edge(g)
            if ti is not None:
                target[g] = int(ti)
    d0, f0 = s_ll.drainage.to_numpy().copy(), s_ll.fork.to_numpy().copy()
    # Two named basins that each lead into the other: Lake Chatuge lies across the edge, so the Hiwassee's side
    # leaves into Hightower Creek's box and Hightower Creek back into the Hiwassee's (where it lands on the lake,
    # with no stream to find). The smaller is the tributary: the bigger one's link goes, and the smaller one's
    # exits that found nothing lead to the bigger one's main reach. Left in, the river took its tributary's name.
    rep_d = s_ll.reset_index(drop=True)[~_lo6].groupby(["rkey", "drainage"]).area_km2.idxmax().to_dict()
    by_src = {}
    for g in net_g:
        if d0[first_[g]] != MINOR:
            by_src.setdefault((g[0], d0[first_[g]]), []).append(g)
    pairs = {}
    for g, ti in target.items():
        if g in net_g and MINOR not in (d0[first_[g]], d0[ti]) and d0[first_[g]] != d0[ti]:
            pairs.setdefault(((g[0], d0[first_[g]]), (s_ll.rkey.iat[ti], d0[ti])), []).append(g)
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
            if d0[first_[g]] == MINOR:
                dnew[ix], fnew[ix] = dcur[ti], fcur[ti]
            else:
                dnew[ix] = dcur[ti]
        if (dnew == dcur).all() and (fnew == fcur).all():
            break
        dcur, fcur = dnew, fnew
    # only when the whole named basin moved. The parts of it that end at a dam or a pond inside the box (no exit of
    # their own) go with the rest: left behind, they kept the old name while the outline took the new one.
    moved = pd.DataFrame({"r": s_ll.region.values, "a": d0, "b": dcur, "exits": s_ll.out_x.notna().values, "low": _lo6})
    moved = moved[(moved.a != MINOR) & moved.exits & ~moved.low].groupby(["r", "a"]).b.agg(
        lambda x: x.iloc[0] if x.nunique() == 1 else None)
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
           "trout_water", "trout_found", "trout_absent", "trout_survey", "trout_ev", "brook_water", "brook_found", "crit_habitat",
           "wilderness", "non_fs_land", "cpad_access", "spp_found", "spp_water"]
FLOWC = ["water_class", "dry_cfs", "dry_cfs_drought", "flow_years", "flow_src", "below_dam",   # 05b_flow.py
         "below_div", "div_share", "div_years", "gauge_name", "gauge_share", "gauge_years", "green_p90",
         "model_class", "water_floor", "borrowed_via", "water_by_gauge", "water_rule"]       # (the last two: scoring.py)
for c_ in CONTEXT + FLOWC:   # older context files may lack a column
    if c_ not in s_ll:
        s_ll[c_] = None
    if c_ not in kp_ll:
        kp_ll[c_] = None
kp_ll.drop(columns="geometry").to_csv(f"{MAP_OUT}/waterfall_candidates.csv", index=False)
mid = s_ll.geometry.interpolate(0.5, normalized=True)
s_ll.assign(lat=mid.y.round(6), lon=mid.x.round(6)).sort_values("fish_score", ascending=False)[
    ["sid", "region", "drainage", "fork", "name", "flow", *FLOWC, *[c_ for c_ in ("in_lake", "len_drawn_m") if c_ in s_ll], "water_term", "fish_score", "thermal", "water_aug", "water_outlet", "outlet_m", "tailwater", "burn_factor", "trout_factor", "brook_size", "heat_factor", "channel_factor", "warm_factor", "area_rank_pct", "area_km2", "area_edge_km2", "area_full_km2", "strahler", "elev_m",
     "gradient_pct", "len_m", "approach_med_min", "bike_med_min"] + ACCESS + CONTEXT + ["q_ann_cfs", "elev_low_m", "lat", "lon"]
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
folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",     # the credit OpenTopoMap's terms ask for
                 attr="Map data: © <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors, "
                      "SRTM | Map display: © <a href='https://opentopomap.org'>OpenTopoMap</a> "
                      "(<a href='https://creativecommons.org/licenses/by-sa/3.0/'>CC-BY-SA</a>)",
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


def peers(flow):
    """The creeks scoring.typical_water compares a reach with, by NHD's label (scoring.TYPICAL_GROUP)."""
    return {"unmapped": "", "other": " that NHD gives no flow class", "ephemeral": " that NHD maps ephemeral or "
            "intermittent"}.get(flow, f" that NHD maps {flow}")


def peers_of(r):
    """peers() for the label whose creeks gave a reach its typical value (scoring.score()'s typ_peers): a class
    05_score.py read along the reach takes every creek's where those read wetter than its class's."""
    p = getattr(r, "typ_peers", None)
    return peers(p if isinstance(p, str) else r.flow)


def trout_why(r):
    """Why scoring.py takes a reach for trout water (its water (5)): trout found here in the last 10 years with no later
    survey finding none (scoring.trout_signs), or its designation."""
    found = pd.to_numeric(getattr(r, "trout_found", None), errors="coerce")
    absent = pd.to_numeric(getattr(r, "trout_absent", None), errors="coerce")
    if pd.notna(found) and found >= THIS_YEAR - 10 and (pd.isna(absent) or found >= absent):
        return f"trout were found here ({int(found)})"
    tw = r.trout_water if isinstance(getattr(r, "trout_water", None), str) else ""
    return f"it is trout water ({tw.split(' · ')[0]})" if tw else "it is trout water"


def summer_flow(r):
    """Popup line from the flow model (05b_flow.py) and the rules scoring.py applies to it: the class, why a rule set
    it where one did, the model's typical / drought-year low flow and share of summers flowing, and NHD's class.
    Below a gauged diversion, the record of the USGS gauge below it too; where the score uses it, it comes first."""
    c = r.water_class
    rule = r.water_rule if isinstance(r.water_rule, str) else ""
    if rule == "no estimate, typical":
        doubt = ""
        if c in ("year-round", "usually flows") and r.flow in ("intermittent", "ephemeral", "unmapped"):
            doubt = (" (" + ("no NHD stream line along it" if r.flow == "unmapped" else f"NHD maps it {r.flow}")
                     + ": NHDPlus's mean flow can't see a creek drying, so it may stop flowing in a dry summer)")
        return (f"{c}{doubt} · no flow estimate: the {LBL['flow']} has no line on this creek or below it on the map, "
                f"so the map takes what its creeks of its size{peers_of(r)} read on the model's own estimates, or "
                f"NHD's class where that says more · NHD: {r.flow}")
    if rule == "no estimate, trout water":
        return (f"{c} · no flow estimate: the {LBL['flow']} has no line on this creek or below it on the map; "
                f"{trout_why(r)}, so it holds water every summer · NHD: {r.flow}")
    if rule == "no estimate":
        return (f"no flow estimate: the {LBL['flow']} has no line on this creek or below it on the map, so the score "
                f"takes what the map's creeks of its size{peers_of(r)} read on the model's own estimates, or NHD's "
                f"class where that says more: {water_word(r.water_term)} · NHD: {r.flow}")
    # scoring.py: a borrowed estimate (scaled from another creek, or leaving out the water above a dam) never reads
    # drier than a creek with no estimate, nor shows a creek NHD has no line for mostly dry (said where it changed the
    # class; within a class it only moved the score)
    # scoring.py, natural flows: an estimate the rules before 2026-11-22 threw away (05b_flow.py's borrowed_via) where it
    # read below NHD's class reads, as it read then, as a reach with no estimate does
    if rule == "borrowed, set aside":
        how = {"lake": "found down a way through a lake", "box": "found in the next box of the map",
               "off-map lake": "taken from the line of a lake draining off the map"}.get(r.borrowed_via, "borrowed")
        own = [f"kept flowing {r.flow_years:.0%} of summers since 2011"] if pd.notna(r.flow_years) else []
        mc = r.model_class if isinstance(r.model_class, str) else "drier"
        return (f"no flow class: its estimate, scaled from another creek {how}, reads drier than NHD's label for it, "
                f"which is no evidence that this creek dries, so the map gives it none; the score takes what the map's "
                f"creeks of its size{peers(r.flow)} read on the model's own estimates, or NHD's class where that says "
                f"more ({water_word(r.water_term)}) · the {LBL['flow']} had it {mc}" + (f" ({own[0]})" if own else "")
                + f" · NHD: {r.flow}")
    if rule == "borrowed, no class" or (rule == "typical" and isinstance(r.model_class, str) and r.model_class != c):
        own = []
        if pd.notna(r.dry_cfs):
            own.append(f"low flow about {cfs(r.dry_cfs)} cfs in a typical July–October, {cfs(r.dry_cfs_drought)} cfs "
                       f"in a drought year")
        if pd.notna(r.flow_years):
            own.append(f"kept flowing {r.flow_years:.0%} of summers since 2011")
        scaled = r.flow_src == "scaled"
        src = LBL["flow"] + (", scaled from the creek below," if scaled else "")
        mc = r.model_class if isinstance(r.model_class, str) else "drier"
        said = f"the {src} had it {mc}" + (f" ({', '.join(own)})" if own else "")
        why = ("an estimate scaled from another creek is no evidence that this one dries" if scaled else
               "most of this creek's drainage lies above a lake or dam, and the model counts only its own ground below "
               "it, which leaves out what seeps, spills or is released")
        if rule == "borrowed, no class":
            return (f"no flow class: {why}, and NHD has no line along it, so the map gives it none; the score takes what "
                    f"the map's creeks of its size read on the model's own estimates, or the estimate where that says "
                    f"more ({water_word(r.water_term)}) · {said} · NHD: {r.flow}")
        doubt = ""
        if not FLOW_DRIES and c in ("year-round", "usually flows") and r.flow in ("intermittent", "ephemeral", "unmapped"):
            doubt = (" (" + ("no NHD stream line along it" if r.flow == "unmapped" else f"NHD maps it {r.flow}")
                     + ": NHDPlus's mean flow can't see a creek drying, so it may stop flowing in a dry summer)")
        return (f"{c}{doubt} · {why}, so the score takes what the map's creeks of its size{peers_of(r)} read on the "
                f"model's own estimates, or NHD's class where that says more · {said} · NHD: {r.flow}")
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
    if not bits:      # a rule below gave a class to a reach the model has no estimate for (LA: piru:s2443, a trout record)
        bits.append("no estimate (no line on this creek or below it on the map)")
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
    # scoring.py's water (5) where the model can't see creeks dry up: trout water reads year-round
    if rule == "trout water":
        return (f"{c} · {trout_why(r)}, so it holds water every summer, whatever the model or NHD's label says · the "
                f"{src}: " + ", ".join(bits) + f" · NHD: {r.flow}")
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


def warm_line(w, k):
    """The warm-water gate (scoring.warm_factor), for the popup's Heat row."""
    if not (pd.notna(k) and k < 1):
        return ""
    return (f"warm water: summer water about {degf(w)} ({WT_HOW}), and no tailwater, trout survey or wild brook trout "
            f"water here · fish score × {k:g}")


def heat_line(air, f):
    if not (pd.notna(f) and f < 1):
        return ""
    rec = f" (at most {degf(HOT, 1)})" if pd.notna(HOT) else ""
    return (f"August air averages {degf(air, 1)} here (PRISM 1991–2020 normal), hotter than any creek in these ranges "
            f"where trout have been recorded{rec} · fish score × {f:.2f}")
# A reach lying in a lake the map draws is drawn with the lake while the Lakes layer is on (it starts on, since
# 2026-11-20), and as a stream when it is off (the user: the rivers run on through the lakes then): the layer
# STREAMS_LAKE, which map_drainages.js, map3d.html and 14_portable.py show only while Lakes is off. 05_score.py cuts the
# stream links exactly at the shores of the lakes this map draws and marks the reaches lying in lake water (in_lake;
# one in an NHD lake this map doesn't draw is drawn as a stream: its len_drawn_m is its length), so this step only
# sorts the reaches into the two layers. Until 2026-11-22 it clipped every line at every drawn lake itself,
# left shore stubs and slivers off, gave the pieces at a lake's ends another reach's values and moved reaches lying
# mostly in a lake to that layer: 6,290 reaches were drawn shorter than the table had them and 1,133 pieces with
# another reach's values, 574 mi of creek line in all, mostly in drawn ponds under 8 ha that the cut didn't see.
# The map of all areas draws every reach: it draws no lakes.
s_ll["in_lake_drawn"] = ((s_ll.in_lake.fillna(False).astype(bool) & s_ll.len_drawn_m.fillna(1.0).le(0)).values
                         if {"in_lake", "len_drawn_m"} <= set(s_ll.columns) else False)
from config import SHARED_DERIVED as SD_
lw_ = None
if os.path.exists(f"{SD_}/lakes.gpkg"):
    lw_ = gpd.read_file(f"{SD_}/lakes.gpkg").to_crs(EPSG)
    lw_ = gpd.GeoDataFrame(geometry=list(shapely.get_parts(shapely.union_all(shapely.make_valid(lw_.geometry.values)))),
                           crs=EPSG)
    lw_ = lw_[lw_.geom_type.isin(["Polygon", "MultiPolygon"]).values].reset_index(drop=True)
cut_ = s_ll.in_lake_drawn.values.astype(bool)
# each reach as the pieces 05_score.py cut it into at the shores of the lakes drawn (drawn_pieces.gpkg: a creek through a
# pond drawn under 8 ha is one reach, its stretch in the pond a piece drawn with the lake), with the reach's own values;
# a piece added or lengthened above (draw_through) whole
_redrawn = set(s_ll.attrs.get("redrawn", []))
if all(os.path.exists(f"{MAP_OUT}/{r}/drawn_pieces.gpkg") for r in done):
    pieces_ = read("drawn_pieces.gpkg")
    whole_ = s_ll.sid.astype(str).str.contains(r"\+").values | s_ll.sid.isin(_redrawn).values
    pc_ = pieces_[pieces_.sid.isin(set(s_ll.sid[~whole_]))].reset_index(drop=True)
    vals_ = s_ll.drop(columns="geometry").set_index("sid")
    s_show = gpd.GeoDataFrame(pd.concat([
        gpd.GeoDataFrame(vals_.loc[pc_.sid.values].reset_index(), geometry=pc_.geometry.values, crs=s_ll.crs)
        .assign(lk_=pc_.wet.astype(bool).values),
        s_ll[whole_].assign(lk_=False)], ignore_index=True), crs=s_ll.crs)
else:
    s_show = s_ll.assign(lk_=cut_)
print(f"reaches lying in a lake the map draws, shown only while Lakes is off: {int(cut_.sum())} "
      f"({s_ll[cut_].to_crs(EPSG).length.sum() / 1000:,.1f} km); pieces drawn: {int((~s_show.lk_).sum())} with Lakes on, "
      f"{int(s_show.lk_.sum())} only while Lakes is off ({s_show[s_show.lk_].to_crs(EPSG).length.sum() / 1000:,.1f} km)")
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
    dm_lo = (pd.to_numeric(s_ll["low_channel"], errors="coerce").fillna(0).to_numpy() > 0) if "low_channel" in s_ll \
        else np.zeros(len(s_ll), bool)          # lines 03b laid lower along NHD's lines (low_channel): no part here
    dm_S, dm_E = shapely.get_point(dm_g, 0), shapely.get_point(dm_g, -1)
    dm_i, dm_j = dm_tree.query(dm_E, predicate="dwithin", distance=1)
    dm_dang = np.setdiff1d(np.flatnonzero(~dm_lo), dm_i[(dm_j != dm_i) & ~dm_lo[dm_j]])  # reach ends nothing goes on from
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
                 if i != dm_t and dm_S[i].distance(dm_p) <= 1 and not dm_lo[i]]
        dm_past = not dm_on
        if dm_past:
            dm_on = [i for i in dm_tree.query(dm_p, predicate="dwithin", distance=10)
                     if i != dm_t and not dm_il[i] and not dm_lo[i]]
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
            if not dm_mid.is_empty and any(i not in (dm_jb, dm_t) and not dm_lo[i]
                                           for i in dm_tree.query(dm_mid, predicate="intersects")):
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
# A creek drawn short of the lake it runs out of or into. The routing's lines run from cell to cell of the 10 m grid, so
# an outlet starts at the first cell past the lake's water and an inlet stops at the last one before it, while the map
# draws the shore from the lidar or an agency's outline, and at phone zoom the creek stops short of its pond: the South
# Branch Middlebury River starts 11 m below Pleiad Lake (central_vt; 218 creek ends on the 12 maps, 2-28 m, median 5.5
# m, 1,643 m in all, 2026-11-23). A line's free end (no other drawn line there) lying 2 m to SHORE_GAP_M outside a lake the map draws is
# drawn on to that lake's nearest shore where the routing runs out of it (a head: up the biggest inflow) or into it (a
# mouth: down the flow) within SHORE_CELLS cells, a cell centre within 5 m of the shore. A lake the routing doesn't run
# through there is never joined. Geometry only: the reach's length, values and table stay as they are.
SHORE_GAP_M, SHORE_CELLS = 30.0, 5
if lw_ is not None and len(lw_):
    from config import derived_dir
    sh_step = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
    sh_on = np.flatnonzero(~s_show.lk_.values.astype(bool))
    # a line 03b laid lower along NHD's lines (low_channel 1 and 2) ending there leaves a reach of the network's end free
    sh_lo = ((pd.to_numeric(s_show["low_channel"], errors="coerce").fillna(0).to_numpy() > 0) if "low_channel" in s_show
             else np.zeros(len(s_show), bool))
    sh_g = np.array(s_show.geometry.to_crs(EPSG).values, dtype=object)
    sh_tree, sh_lt = shapely.STRtree(sh_g[sh_on]), shapely.STRtree(lw_.geometry.values)
    sh_ras, sh_new, sh_gaps = {}, {}, []

    def sh_routed(b_, p_, lake_, up_):
        """True where b_'s routing, from p_'s cell, runs out of (up_) or into lake_ within SHORE_CELLS cells. The lines
        run on the top-left corners of their cells (03b_stitch.py), so an end's own cell is the one whose corner it is
        (every pair of vertices on two central_vt boxes' lines follows flowdir that way, 2026-11-23)."""
        if b_ not in sh_ras:
            try:
                sh_ras[b_] = (rasterio.open(crossbox.fdir_path(b_)), rasterio.open(f"{derived_dir(b_)}/area_km2.tif"))
            except Exception:
                sh_ras[b_] = None
        if sh_ras[b_] is None:
            return False
        fd_, ar_ = sh_ras[b_]
        n_ = 2 * SHORE_CELLS + 2
        cx_, cy_ = (int(v) for v in np.rint(np.array(~fd_.transform * (p_.x, p_.y))))
        w_ = rasterio.windows.Window(cx_ - SHORE_CELLS - 1, cy_ - SHORE_CELLS - 1, n_, n_)
        F_ = fd_.read(1, window=w_, boundless=True, fill_value=0)
        A_ = ar_.read(1, window=w_, boundless=True, fill_value=0)
        T_, near_ = fd_.window_transform(w_), lake_.buffer(5)
        return sh_trace(F_, A_, T_, near_, SHORE_CELLS + 1, SHORE_CELLS + 1, up_, n_)

    def sh_trace(F_, A_, T_, near_, r_, c_, up_, n_):
        """From cell (r_, c_) of the window: up the biggest inflow (up_) or down the flow, a cell centre in near_ within
        SHORE_CELLS cells."""
        for _ in range(SHORE_CELLS):
            if up_:
                ins_ = [(r_ - a, c_ - b) for k, (a, b) in sh_step.items()
                        if 0 <= r_ - a < n_ and 0 <= c_ - b < n_ and F_[r_ - a, c_ - b] == k]
                if not ins_:
                    return False
                r_, c_ = max(ins_, key=lambda q: A_[q])
            else:
                k = int(F_[r_, c_])
                if k not in sh_step or not (0 <= r_ + sh_step[k][0] < n_ and 0 <= c_ + sh_step[k][1] < n_):
                    return False
                r_, c_ = r_ + sh_step[k][0], c_ + sh_step[k][1]
            if near_.contains(shapely.Point(*(T_ * (c_ + 0.5, r_ + 0.5)))):
                return True
        return False

    for i_ in sh_on:
        g_ = sh_g[i_]
        if g_ is None or g_.is_empty or g_.geom_type != "LineString":
            continue
        cs_ = list(g_.coords)
        for head_, p_ in ((True, shapely.Point(cs_[0])), (False, shapely.Point(cs_[-1]))):
            if any(sh_on[j] != i_ and (sh_lo[i_] or not sh_lo[sh_on[j]])
                   for j in sh_tree.query(p_, predicate="dwithin", distance=1.0)):
                continue
            k_ = sh_lt.query(p_, predicate="dwithin", distance=SHORE_GAP_M)
            if not len(k_):
                continue
            d_ = shapely.distance(lw_.geometry.values[k_], p_)
            lake_ = lw_.geometry.values[k_[int(np.argmin(d_))]]
            if not 2.0 <= d_.min() <= SHORE_GAP_M or lake_.contains(p_):
                continue
            if not sh_routed(str(s_show.sid.iat[i_]).split(":")[0], p_, lake_, head_):
                continue
            q_ = shapely.ops.nearest_points(lake_.boundary, p_)[0]     # an island's shore too
            cs_ = [q_.coords[0]] + cs_ if head_ else cs_ + [q_.coords[0]]
            sh_gaps.append(float(d_.min()))
        if len(cs_) != len(g_.coords):
            sh_new[s_show.index[i_]] = shapely.LineString(cs_)
    for f_ in sh_ras.values():
        if f_ is not None:
            f_[0].close(); f_[1].close()
    if sh_new:
        s_show.loc[list(sh_new), "geometry"] = gpd.GeoSeries(list(sh_new.values()), crs=EPSG).to_crs(s_show.crs).values
    print(f"creek ends drawn on to the shore of the lake the routing runs them out of or into: {len(sh_gaps)} (median "
          f"{np.median(sh_gaps or [0]):.0f} m, longest {max(sh_gaps or [0]):.0f} m, {sum(sh_gaps):.0f} m in all)")
s_show = s_show.assign(geometry=shapely.set_precision(s_show.geometry.simplify(0.00008).values, 1e-5))
s_show = s_show[~s_show.geometry.is_empty & (s_show.geom_type == "LineString")]
mid_ll = s_show.geometry.interpolate(0.5, normalized=True)
nz = lambda v, nd=0: None if pd.isna(v) else round(float(v), nd) if nd else int(round(float(v)))
# a side channel of a river (05_score.py's side_of), or a lake's second outlet (side_lake), says so in its name and in
# its flow line
_side = s_show.side_of.notna().values if "side_of" in s_show else np.zeros(len(s_show), bool)
_lk = s_show.side_lake.notna().values if "side_lake" in s_show else np.zeros(len(s_show), bool)
def side_text(r, sd_, lk_):
    if lk_:
        size_ = (("the creek the main outlet starts" if isinstance(getattr(r, "side_sid", None), str) else
                  "the water the lake passes on at its outlet") + f" ({sqmi(r.river_km2)})")
        rule_ = getattr(r, "water_rule", None)
        return (f"a second outlet of {r.side_lake if r.side_lake != 'unnamed' else 'an unnamed lake'}: NHD maps the "
                "lake's water leaving by this channel too, but the routing sends it all down the lake's main outlet, so "
                "this channel's own drainage is small; "
                + ("· " if pd.isna(r.river_km2) else
                   f"it is scored on the size and flow of {size_}, and the flow shown is that creek's · "
                   if getattr(r, "on_outlet_creek", False) == True else
                   f"it is scored on the size of {size_}, and reads no wetter than the creek it runs into below, "
                   f"whose flow is shown · " if rule_ == SIDE_BELOW else
                   f"it is scored on the size of {size_}, and on NHD's class for this channel, {r.flow} · "
                   if rule_ == SIDE_NHD else
                   f"it is scored on the size of {size_}, and on this channel's own flow · "))
    return (f"a side channel of the {r.side_of}, which drains {sqmi(r.river_km2)} beside it: the routing sends the whole "
            f"river down one arm, so this arm's own drainage is small; it is scored on the river's size and flow · "
            if sd_ else "")
# The fish score's breakdown in the stream popups (map_score.js: on hover on a computer, on a tap on a phone). Each
# reach carries its terms as scoring.score() combines them, in one short string (fx) the page multiplies out the same
# way, in the same order, so it comes to the score shown. Space-separated: the water term; the size term; the summer
# water temperature (°C, one decimal, as the popup shows it); tree canopy and terrain shade (%); northness
# (hundredths); the typical approach (min) and the minutes of it ridden. "-" is a value missing: score() then takes
# canopy 0, terrain 20, northness 0, approach 0. Then flags: t trout evidence (x 1.2), b sized as wild brook trout
# water, w tailwater, c built channel (x 0.2), x the warm-water gate (x 0.5, scoring.warm_factor); and, where they apply, B burn, H heat gate, C the water-temperature part
# of the thermal term (where the temperature shown doesn't give it: 0 at 25 °C and up, 1 at 20 °C and under), A the
# drainage the size term reads (where not the one shown), G the gradient (where not the one shown), N the northness
# (where not in hundredths). The page reads the gradient from gr. Water, size, burn, heat and C carry three decimals,
# or more where that takes the page's sum off the reach's score: checked here on every drawn reach, and a reach whose
# string still doesn't come to its score (score() changed and the page not) gets none, so no breakdown is shown wrong.
def _fs_dec(v, d=None):
    """v to d decimals (all its digits with d None), without a leading 0 or trailing zeros: 0.6309 -> '.631'."""
    t = repr(float(v)) if d is None else f"{v:.{d}f}"
    if "." in t and "e" not in t:
        t = t.rstrip("0").rstrip(".")
    t = "0" if t in ("", "-0") else t
    return t.replace("0.", ".", 1) if t.startswith(("0.", "-0.")) else t


def _fs_page(W, S, c1, cp, sp, nn, am, bm, gr, B, T, H, Ch, K=1.0):
    """The score as map_score.js works it out, operation by operation as scoring.score() does, before rounding."""
    terrain, canopy = sp / 100, min(max(cp / 100, 0.0), 1.0)
    shade = min(max((1 - (1 - terrain) * (1 - 0.8 * canopy)) / 0.45, 0.0), 1.0)
    north = min(max((nn + 0.15) / 0.30, 0.0), 1.0)
    thermal = 0.5 * c1 + 0.35 * shade + 0.15 * north
    grad = min(max(1 - max(max(1 - gr, gr - 8), 0.0) / 10, 0.0), 1.0)
    remote = min(max((am + bm) / 120, 0.0), 1.0)
    x = 100 * W * (0.30 * S + 0.30 * thermal + 0.15 * grad + 0.25 * remote) * B * T * H * Ch * K
    return min(max(x, 0.0), 100.0)


def fs_parts(s):
    """fx for each row of s (above), and the number of rows left without one because it doesn't come to their score."""
    if not {"t_water", "t_size", "t_cool", "t_burn", "t_heat", "t_big"} <= set(s.columns):
        return [None] * len(s), 0
    n_bad, out = 0, []
    col = lambda c: (pd.to_numeric(s[c], errors="coerce") if c in s else pd.Series(np.nan, index=s.index)).to_numpy(float)
    W, S, C1, B, H, BIG = (col(c) for c in ("t_water", "t_size", "t_cool", "t_burn", "t_heat", "t_big"))
    T, CH, FS = col("trout_factor"), col("channel_factor"), col("fish_score")
    K = col("warm_factor") if "warm_factor" in s else np.ones(len(s))
    K = np.where(np.isnan(K), 1.0, K)
    CP, SP, NN, AM, BM = col("canopy_pct"), col("shade_pct"), col("northness"), col("approach_med_min"), col("bike_med_min")
    GR, WT = col("gradient_pct"), col("water_aug")
    A = s.area_full_km2.fillna(s.area_km2).astype(float).round(2).to_numpy()
    brook = s["brook_size"].fillna(False).astype(bool).to_numpy() if "brook_size" in s else np.zeros(len(s), bool)
    tw = s["tailwater"].notna().to_numpy() if "tailwater" in s else np.zeros(len(s), bool)

    def whole(v):                                   # a count or percent: as an integer where it is one
        return "-" if np.isnan(v) else str(int(v)) if float(int(v)) == v else _fs_dec(v)
    for i in range(len(s)):
        if np.isnan(FS[i]) or np.isnan(W[i]) or np.isnan(S[i]) or np.isnan(C1[i]) or np.isnan(GR[i]):
            out.append(None)
            continue
        nn = 0.0 if np.isnan(NN[i]) else float(NN[i])
        k = int(round(nn * 100))
        flags = [f for f, on in (("t", T[i] == 1.2), ("b", brook[i]), ("w", tw[i]), ("c", CH[i] == 0.2),
                                 ("x", K[i] == 0.5)) if on]
        if round(float(GR[i]), 1) != GR[i]:          # the page reads gr, the gradient to one decimal
            flags.append("G" + _fs_dec(GR[i]))
        if k / 100 != nn:
            flags.append("N" + _fs_dec(nn))
        if not np.isnan(BIG[i]) and round(float(BIG[i]), 2) != A[i]:
            flags.append("A" + _fs_dec(BIG[i], 2))
        wt_ = None if np.isnan(WT[i]) else float(f"{WT[i]:.1f}")
        c1_page = 1.0 if tw[i] else None if wt_ is None else min(max((25 - wt_) / 5, 0.0), 1.0)
        need_c = c1_page is None or C1[i] != c1_page
        head = ["-" if wt_ is None else f"{wt_:.1f}", whole(CP[i]), whole(SP[i]), "-" if np.isnan(NN[i]) else str(k),
                whole(AM[i]), whole(BM[i])]
        cp, sp = (0.0 if np.isnan(CP[i]) else CP[i]), (20.0 if np.isnan(SP[i]) else SP[i])
        am, bm = (0.0 if np.isnan(AM[i]) else AM[i]), (0.0 if np.isnan(BM[i]) else BM[i])
        for d in (3, 4, 5, 6, 8, None):
            w_, s_, extra, c1, b_, h_ = _fs_dec(W[i], d), _fs_dec(S[i], d), list(flags), c1_page, 1.0, 1.0
            if need_c:
                extra.append("C" + _fs_dec(C1[i], d))
                c1 = float(extra[-1][1:])
            if B[i] != 1:
                extra.append("B" + _fs_dec(B[i], d))
                b_ = float(extra[-1][1:])
            if H[i] != 1:
                extra.append("H" + _fs_dec(H[i], d))
                h_ = float(extra[-1][1:])
            x = _fs_page(float(w_), float(s_), c1, cp, sp, nn, am, bm, float(GR[i]), b_, float(T[i]), h_, float(CH[i]),
                         float(K[i]))
            if round(x) == FS[i]:
                out.append(" ".join([w_, s_] + head + extra))
                break
        else:
            n_bad += 1
            out.append(None)
    return out, n_bad


fx_, fx_bad = fs_parts(s_show)
print(f"fish score breakdown (fx): {sum(v is not None for v in fx_)} of {len(fx_)} drawn reaches"
      + (f"; WARNING: {fx_bad} left without, as theirs didn't come to their score (map_score.js and scoring.score() "
         f"differ)" if fx_bad else ", each coming to its score"))

# ---- the creeks' long profiles: where 12_profiles.py draws them (creekprofiles.py, its rule: each named NHD creek's main
# stem, MIN_KM and more). A stream popup's "Open <creek> profile ↗" (map_drainages.js, map3d.html) opens profiles.html
# #q=name&lat=&lon= at the reach's popup point, which shows the profile of that name passing closest to the point. The
# link is given only where that profile passes within SNAP_FALL of the reach's own line (the drops and known falls, being
# points, test their point: below), so a braided river or a stretch past a profile's end, whose middle lies farther from
# NHD's line, keeps its link, and a link that would open another creek of the same name, or no profile, is not given:
# the popup says there is no profile here. On the live maps (site c37aa6a, 2026-11-23) every one of the 78,268 named
# reaches linked: 4,042 found no profile of that name (names NHD doesn't carry, creeks under MIN_KM) and 2,351 opened
# one more than 200 m away (median 1.1 km: another creek of the same name, or another stretch; LA's Potrero Creek opened
# San Jacinto's, 197 km off). The rule keeps 72,208 links; 570 of them on braided water and the like (Snake River, Flat
# Creek, Gros Ventre River), which a test at the reach's middle would have dropped.
from config import raw_dir
import creekprofiles
_nhd = [gpd.read_file(f"{raw_dir(r_)}/nhd_flowlines.gpkg", columns=["gnis_name", "ftype"]).to_crs(EPSG).assign(range=r_)
        for r_ in done if os.path.exists(f"{raw_dir(r_)}/nhd_flowlines.gpkg")]
# (the creeks' lines as 12_profiles.py takes them: NHD's unnamed lines along reaches the map names from OpenStreetMap
# take their name, by the map's final names: creekprofiles.fill_names)
PROFILES = creekprofiles.ProfileLines(pd.concat(_nhd, ignore_index=True) if _nhd else
                                      gpd.GeoDataFrame(columns=["gnis_name", "ftype", "range"], geometry=[]),
                                      creekprofiles.reach_lines(s_ll.drop_duplicates("sid").set_index("sid")["name"]))


def opens_here(name, line, pt, km2=0.0):
    """True where the profile a reach's link opens (of the creek `name`, the one passing closest to the link's point
    `pt`, as profiles.html picks it) passes within creekprofiles.link_m(km2) of the reach's own `line` (both in metres;
    SNAP_FALL, more on a river: braids)."""
    st = np.asarray(PROFILES.stems(name), dtype=object)
    return len(st) > 0 and float(shapely.distance(line, st[np.argmin(shapely.distance(pt, st))])) <= creekprofiles.link_m(km2)


# "np" = 1: a named reach (a side channel by its river's name, as its link) without such a profile; written only where
# set (below), a few bytes on a few thousand reaches instead of a key on every reach
_mid_m = gpd.GeoSeries(gpd.points_from_xy(mid_ll.x.round(5), mid_ll.y.round(5)), crs=4326).to_crs(EPSG).values
_line_m = gpd.GeoSeries(s_show.geometry.values, crs=4326).to_crs(EPSG).values
_km2 = s_show.area_full_km2.fillna(s_show.area_km2).astype(float).values
no_prof = pd.Series([1 if isinstance(n_, str) and n_ and not opens_here(n_, l_, p_, k_) else None
                     for n_, l_, p_, k_ in zip(s_show["name"].values, _line_m, _mid_m, _km2)], index=s_show.index, dtype=object)
_named = sum(isinstance(n_, str) and n_ != "" for n_ in s_show["name"].values)
print(f"stream popups' profile links: {_named - no_prof.notna().sum():,} of {_named:,} named reaches "
      f"({no_prof.notna().sum():,} with no profile of their name within {creekprofiles.SNAP_FALL} m of their line)")
props = pd.DataFrame({
    "n": [f"{n_} (side channel)" if (sd_ or lk_) and isinstance(n_, str) else n_ if isinstance(n_, str) else None
          for n_, sd_, lk_ in zip(s_show["name"].values, _side, _lk)],
    "d": s_show.drainage, "k": s_show.fork, "o": s_show.strahler,
    "c": [fcol.get((d, f), dcol.get(d, MINOR_COL)) for d, f in zip(s_show.drainage, s_show.fork)],
    "fs": s_show.fish_score.round(0).astype(int),
    "fl": [f"summer: {c}" if isinstance(c, str) and c != "no data" else f"NHD {f}" for c, f in zip(s_show.water_class, s_show.flow)],
    "dq": [side_text(r, sd_, lk_) + summer_flow(r) for r, sd_, lk_ in zip(s_show.itertuples(), _side, _lk)],
    # drainage (km2, to 0.01 so the popups' square miles keep two places) and elevation (m): the pages show them in
    # square miles and feet
    "a": s_show.area_full_km2.fillna(s_show.area_km2).astype(float).round(2), "el": [nz(v) for v in s_show.elev_m], "gr": s_show.gradient_pct.astype(float).round(1),
    # the specs line's mean annual flow (cfs, as the popups round a flow) and lower end (m); written only where known
    "q": [None if np.isnan(v) else int(v) if v >= 10 else float(v)
          for v in streamspecs.round_cfs(pd.to_numeric(s_show.q_ann_cfs, errors="coerce").to_numpy(float))],
    "le": [nz(v) for v in s_show.elev_low_m],
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
    "ht": [" · ".join(x for x in (heat_line(a, f), warm_line(w, k)) if x)
           for a, f, w, k in zip(pd.to_numeric(s_show.air_aug), s_show.heat_factor, pd.to_numeric(s_show.water_aug),
                                 s_show["warm_factor"] if "warm_factor" in s_show else [1.0] * len(s_show))],
    "burn": [" · ".join(x for x in (
                 f"{f} fire {y:.0f}" + (f" ({sev_label(sv)})" if pd.notna(sv) else "") if pd.notna(y) else "",
                 f"⚠ debris-flow hazard {dfl}" if isinstance(dfl, str) else "") if x)
             for f, y, sv, dfl in zip(s_show.burn_fire, s_show.burn_year, pd.to_numeric(s_show.burn_sev), s_show.debris_flow)],
    # the brook trout designation the size term reads (scoring.brook_water), where another designation is the label
    "tr": [" · ".join(x for x in (t if isinstance(t, str) else "", b if isinstance(b, str) and b != t else "",
                                  e if isinstance(e, str) else "") if x)
           for t, b, e in zip(s_show.trout_water, s_show.brook_water, s_show.trout_ev)],
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
    "fx": fx_,                                    # the score's terms, for its breakdown (fs_parts above)
    "y": mid_ll.y.round(5), "x": mid_ll.x.round(5),
    "np": no_prof})                               # no long profile here: the popup gives no profile link (above)
props["_lk"] = s_show.lk_.values
# A reach with a USGS gauge on its creek (05b_flow.py's gauge_site: the nearest gauge on its own creek's line within 4
# km, of about its drainage), where that gauge is on this map's gauges layer, carries its site: the trout calendar's
# "now" shows that gauge's latest reading (map_gauges.js). Read as text: attach() reads the tables as numbers, which
# drops the site numbers' leading zeros.
_glive = set() if ctx("gauges") is None else {str(s_) for s_ in ctx("gauges").site if not str(s_).startswith("CDEC")}
_gsite = {}
for d_ in dirs:
    if os.path.exists(f"{d_}/flow_streams.csv"):
        _t = pd.read_csv(f"{d_}/flow_streams.csv", usecols=lambda c_: c_ in ("sid", "gauge_site"), dtype={"gauge_site": str})
        if "gauge_site" in _t:
            _gsite.update(zip(_t.sid, _t.gauge_site))
props["g"] = [g_ if isinstance(g_, str) and g_ in _glive else None for g_ in map(_gsite.get, s_show.sid.values)]
print(f"reaches with a live gauge on their creek: {props.g.notna().sum():,} ({len({g_ for g_ in props.g if g_}):,} gauges)")
# The trout calendar (troutcal.py; 11b_calendar.py makes its files): each reach's horizon and, where it isn't the map's,
# its time zone (cz), and the area's tables in LBL["cal"]; map_calendar.js works it out in the popups
import troutcal
props["cz"], _cal = troutcal.page_props(s_show.sid.values, done, MAP_OUT)
if _cal:
    LBL["cal"] = _cal
print(f"trout calendar: {props.cz.notna().sum():,} of {len(props):,} drawn reaches"
      + ("" if _cal else " (11b_calendar.py not run: no calendar)"))
# The trout species on each reach, for the species filter and the popups' "Species" line (map_filter.js): per species
# (troutspecies.CODE: B brook, N brown, R rainbow, C cutthroat, L lake trout) a capital where a trout record names it,
# with the latest year one did ("B2018"), and the small letter where the reach's own designated waters name it ("b");
# 11_context.py's spp_found and spp_water. Written only where a reach has one
import re, troutspecies
def species_code(found, water):
    rec = {m.group(1): m.group(2) or "" for m in re.finditer(r"(brook|brown|rainbow|cutthroat|lake)(?: (\d{4}))?",
                                                             found if isinstance(found, str) else "")}
    des = set(re.findall(r"brook|brown|rainbow|cutthroat|lake", water if isinstance(water, str) else ""))
    c = "".join((troutspecies.CODE[x] + rec[x] if x in rec else "") + (troutspecies.CODE[x].lower() if x in des else "")
                for x in troutspecies.SPECIES)
    return c or None
props["sp"] = [species_code(f, w) for f, w in zip(s_show.spp_found, s_show.spp_water)]
print(f"trout species: {props.sp.notna().sum():,} of {len(props):,} drawn reaches; recorded / designated: " + ", ".join(
    f"{x} {props.sp.str.contains(c, regex=False).sum():,}/{props.sp.str.contains(c.lower(), regex=False).sum():,}"
    for x, c in troutspecies.CODE.items()))
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
    if "undrawn" in tr:       # sidepaths and water trails' pieces (02d_trails.py): in the layer for the routing and the
        tr = tr[~tr.undrawn.fillna(False).astype(bool)]           # parking test, not drawn
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
if os.path.exists(f"{SHARED}/access_roads.gpkg") and "osm_id" in tr:
    # the road layers draw a fire road 02e_access.py keeps (the same OSM way): the trail layer keeps the ones on hiking
    # routes and those the road layer doesn't have (02e leaves out private roads; 02d keeps one walkers may use)
    on_road = tr.osm_id.isin(set(gpd.read_file(f"{SHARED}/access_roads.gpkg", columns=["osm_id"]).osm_id.dropna()))
    t_feat = t_feat[(t_feat.k != "fire road") | t_feat.get("rt", pd.Series(None, index=t_feat.index)).notna()
                    | ~on_road.reindex(t_feat.index, fill_value=False)]
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
                               "mv": getc("mvum"), "od": getc("open_dates"), "cw": getc("closed_why"),
                               "src": getc("source").where(lambda x: x != "OSM")},     # "USFS records only" (02e)
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
         "st": pk["status"] if "status" in pk else None,
         "t": pk["atype"] if "atype" in pk else None, "w": pk["water"] if "water" in pk else None},   # access sites
        geometry=pk.geometry, crs=4326).to_json(na="null", drop_id=True))
    print("parking / trailheads", len(pk), "|", pk.kind.value_counts().to_dict())
print("trails", len(t_feat), "ways |", t_feat.groupby("rk").size().to_dict(), "| labels per zoom band:",
      pd.Series([l["z"] for l in trail_labels], dtype=int).value_counts().sort_index().to_dict())
# The layers both maps draw (streams, drainage fills and divides, the long trail, trails, roads, parking, their labels)
# are written once, to map3d_data.js at the end of this script: this page loads that file and points the globals
# map_drainages.js reads at its entries. They used to be inlined here as well, a second copy of the same data (231 MB
# over the 12 areas, 2026-11-20); the published site has a 1 GB limit. Since 2026-11-25 the page's own script (folium's:
# the map, its layers, markers and popups) is in stream_map.js beside it, after the line that points the globals
# (POINT_2D), and lib/streams/load.js runs map3d_data.js and then stream_map.js once the page is parsed: the site keeps
# both gzip-compressed (weblib.pack), and the page opened from disk runs the plain files.
SHARED_3D = {"STREAMS": "streams", "STREAMS_LAKE": "streams_lake", "FORKS": "forks", "DIVIDES": "divides", "DRAINS": "drains", "LBL": "lbl",
             "PCT": "pct", "PCT_LABEL_LINES": "pct_labels", "TRAILS": "trails", "TRAIL_LABEL_LINES": "trail_labels",
             "ROADS": "roads", "PARKING": "parking"}
POINT_2D = ("(function (D) {" + " ".join(f"window.{g} = D.{k};" for g, k in SHARED_3D.items())
            + "})(window.MAP3D || {});")
m.get_root().header.add_child(folium.Element(f'<script src="../{weblib.LOADER}"></script>'))
# map_phone.css/.js (the one-line credits on phones and the "my location" button) are shared with 13_overview.py and
# 14_portable.py; map_score.js (the fish score's breakdown in the stream popups) with the 3D page and 14_portable.py
_page_file = lambda f_: open(os.path.join(os.path.dirname(__file__), f_)).read()
# the stream filters at the top of the layer panels (map_filter.js: a fish score and a drainage under which streams leave
# the map), on the 3D page too (below)
m.get_root().header.add_child(folium.Element("<script>" + _page_file("map_filter.js") + "</script>"))
# the specs line in the stream popups and "Similar streams" (map_specs.js), on the 3D page too (below)
m.get_root().header.add_child(folium.Element("<script>" + _page_file("map_specs.js") + "</script>"))
# live gauge readings and My Waters (map_gauges.js), on the 3D page too (below)
m.get_root().header.add_child(folium.Element("<script>" + _page_file("map_gauges.js") + "</script>"))
m.get_root().header.add_child(folium.Element(
    "<style>" + _page_file("map_style.css") + _page_file("map_phone.css") + "</style>\n<script>"
    + _page_file("map_phone.js") + _page_file("map_score.js") + _page_file("layer_order.js") + _page_file("map_routes.js")
    + _page_file("map_drainages.js") + _page_file("map_land.js") + "</script>"))
# the web app and its offline copy (weblib.py, web/offline.js: "Save for offline" in the layer panel)
m.get_root().header.add_child(folium.Element(weblib.head("../")))

# every layer is also exported for the 3D map: the shared ones to map3d_data.js, the rest into stream_map_3d.html
X3D = {"streams": json.loads(s_feat.to_json(na="null", drop_id=True)),
       "streams_lake": json.loads(s_feat_lake.to_json(na="null", drop_id=True)), "forks": f_json, "divides": d_json,
       "drains": drains, "home": HOME, "pct": pct_json, "pct_labels": pct_labels, "lbl": LBL}
for f_ in X3D["streams"]["features"] + X3D["streams_lake"]["features"]:
    for k_ in ("np", "q", "le", "sp", "g"):       # "np", "sp" and "g" only where set, the specs where known (above)
        if f_["properties"].get(k_) is None:
            f_["properties"].pop(k_, None)
gj = lambda g: json.loads(g.to_json(na="null", drop_id=True))

top = s_feat[s_feat.fs >= 55][["geometry"]]
folium.GeoJson(top.to_json(), name="<span style='color:#e8590c'>━</span> Best remote trout water (score ≥ 55)",
               show=False, style_function=lambda f: {"color": "#e8590c", "weight": 6, "opacity": 0.55,
                                                     "interactive": False}).add_to(m)   # clicks reach the stream

X3D["trails"] = json.loads(t_feat.to_json(na="drop", drop_id=True))
X3D["trail_labels"] = trail_labels
X3D["roads"], X3D["parking"] = roads_json, park_json

# ---- the creek profile a drop or a known fall is on (the user, 2026-11-23: "when i clicked a known waterfall like this
# make a link to the creek profile"). Their popups link to it as the streams' do (profiles.html#q=name&lat=&lon= opens
# that creek's profile at the spot), and only where 12_profiles.py draws that creek's profile within SNAP_FALL of the
# point (creekprofiles.py, its rule): no link that would find no profile (a creek under MIN_KM), nor one that would
# open a creek of the same name elsewhere on the map. A known fall's creek: the drawn creek its source's note names
# ("on Long Creek"), within SNAP_FALL of the fall; else the nearest drawn creek, if it is within FALL_NEAR_M and named.
# Measured on the 12 maps (2,158 known falls, 2026-11-23): where a note names the creek and that creek is drawn nearby,
# its line lies within 30 m of the fall for 90% of them and within 100 m for 95%, and the nearest drawn creek is the
# named one for 97%; beyond 100 m most falls lie on creeks too small to draw, and the nearest drawn one is another.
import re
FALL_NEAR_M = 100


def profile_link(creek, lat, lon):
    """The streams' "Open <creek> profile ↗" link (map_drainages.js), for a spot on that creek."""
    return (f"<a href='profiles.html#q={quote(creek)}&lat={lat:.5f}&lon={lon:.5f}' target='_blank'>"
            f"Open {hesc(creek)} profile ↗</a>")


_creek_key = lambda s: re.sub(r"\s+", " ", re.sub(r"^the\s+", "", s.lower().replace("’", "'"))).strip()
_NOTE_CREEK = re.compile(r"((?:[A-Z][\w'’.-]*\s+){0,4}(?:Creek|Brook|River|Run|Branch|Fork|Kill|Prong|Stream|Bayou|Canyon))"
                         r"(?![\w-])(\s+(?:Trail|Trailhead|Rd|Road|Campground|[Tt]ributary|Falls|Gorge|Bridge|Dam|Ranger|"
                         r"Picnic|Wilderness|Valley|Lake|Reservoir|Overlook|Park))?")


def note_creeks(note):
    """The creeks a known fall's note names ("on Long Creek", "of Putnam Creek"): not a trail, road or campground named
    after one, nor one the fall is on a tributary of."""
    return [] if not isinstance(note, str) else [
        _creek_key(m.group(1)) for m in _NOTE_CREEK.finditer(note)
        if not m.group(2) and "tributary of" not in note[max(0, m.start() - 15):m.start()].lower()]


_rg = gpd.GeoSeries(s_show.geometry.values, crs=4326).to_crs(EPSG).values      # the drawn reaches, in metres
_rn = s_show["name"].values
_rk = np.array([_creek_key(n_) if isinstance(n_, str) else "" for n_ in _rn])
_rtree = shapely.STRtree(_rg)


def fall_creek(note, pt):
    """The creek whose profile a known fall's popup links to (above), or None. pt: the fall, in metres (EPSG)."""
    near = _rtree.query(pt, predicate="dwithin", distance=creekprofiles.SNAP_FALL)
    if not len(near):
        return None
    d = shapely.distance(pt, _rg[near])
    for c_ in note_creeks(note):
        named = _rk[near] == c_
        if named.any():
            j = near[named][np.argmin(d[named])]
            return _rn[j] if PROFILES.passes(_rn[j], pt) else None
    j = near[np.argmin(d)]
    return _rn[j] if d.min() <= FALL_NEAR_M and _rk[j] and PROFILES.passes(_rn[j], pt) else None


# a drop sits on its reach (its stream's name): the link where that creek's profile passes it
_drop_creek = {i_: s_ if PROFILES.passes(s_, p_) else None
               for i_, s_, p_ in zip(kp_ll.index, kp_ll.stream, kp_ll.geometry.to_crs(EPSG).values)}
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
            + (" · " + profile_link(_drop_creek[r.Index], r.lat, r.lon) if _drop_creek[r.Index] else ""))
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
def fall_label(r):
    """A known fall's name, or for one without a name what it is: "waterfall", or "swimming hole" for the unnamed creek
    pools and swimming spots 02f_known_falls.py keeps since 2026-11-23."""
    return r.name if isinstance(r.name, str) and r.name else (r.kind if isinstance(r.kind, str) and r.kind else "waterfall")


def fall_html(r):
    """The known fall's popup, shared by the 2D, 3D and one-file maps: name, kind, sources, note, its creek's profile
    (above), the source's page."""
    nm_ = fall_label(r)
    kind_ = r.kind if isinstance(r.kind, str) and r.kind not in ("", "waterfall", nm_) else ""
    note = r.note if isinstance(r.note, str) and r.note else ""
    url = r.url if isinstance(r.url, str) and r.url.startswith("http") else ""
    return (f"<b>{hesc(nm_)}</b>" + (f" · {hesc(kind_)}" if kind_ else "") + f"<br><span style='color:#6b7280'>{hesc(r.src)}</span>"
            + (f"<br>{hesc(note)}" if note else "")
            + (f"<br>{profile_link(r.creek, r.geometry.y, r.geometry.x)}" if isinstance(r.creek, str) else "")
            + (f"<br><a href='{hesc(url)}' target='_blank'>Source page ↗</a>" if url else ""))
known_falls["creek"] = [fall_creek(n_, p_) for n_, p_ in zip(known_falls.note, known_falls.geometry.to_crs(EPSG).values)]
known_falls["html"] = [fall_html(r) for r in known_falls.itertuples()]
kf = folium.FeatureGroup(name=f"<span style='color:#0b3d91'>◆</span> {LBL['falls']}", show=False)
for r in known_falls.itertuples():
    nm_ = fall_label(r)
    folium.Marker([r.geometry.y, r.geometry.x], icon=svg_icon(FALL_SVG, 16, 16),
                  popup=folium.Popup(r.html, max_width=300), tooltip=f"{nm_} ({r.src})").add_to(kf)
kf.add_to(m)
X3D["falls"] = gj(known_falls[["name", "src", "note", "kind", "html", "geometry"]].assign(name=[fall_label(r) for r in known_falls.itertuples()]))

def r6(gs):
    """Outlines from other sources (road closures, PAD-US, USFS land status, state trout waters, critical habitat,
    wilderness, fire perimeters) come with 15 decimals. 6 (10 cm) draws them the same and takes a third of the space
    (67 MB over the 12 areas, 2026-11-20); the rest of the map is written at 5 (set_precision 1e-5)."""
    return gpd.GeoSeries(shapely.transform(np.asarray(gs.values), lambda c: np.round(c, 6)), index=gs.index, crs=gs.crs)


# What came from a saved copy: when a download fails, 11_context.py and 07_road_closures.py use the source's last good
# copy (netfetch.py) and add "(as of Nov 23)" to its source wording. The layers read below are checked for it, and the
# legends name them in one line with the copy's day (LBL["stale_line"], 2026-11-24); the gauges' label then says
# "as of" for "live". The steps whose data carry no such wording (lakes, trails, roads, falls) keep the NOTE in the log.
import datetime as _dt
_ASOF = re.compile(r"\(as of ([A-Z][a-z]{2} \d{1,2}(?:, \d{4})?)\)")
STALE = {}          # the layer's name in that line -> (day, "Nov 23"): the oldest copy read for it


def note_stale(name, texts):
    for t_ in texts:
        for d_ in (_ASOF.findall(t_) if isinstance(t_, str) else ()):
            day_ = _dt.datetime.strptime(d_ if "," in d_ else f"{d_}, {_dt.date.today().year}", "%b %d, %Y").date()
            if name not in STALE or day_ < STALE[name][0]:
                STALE[name] = (day_, d_)


if closures is not None and len(closures):
    fetched = closures.fetched.iloc[0]
    note_stale("road closures", closures.source)
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


def lake_profile(name, x, y):
    """A lake popup's link to its outlet creek's profile, or to that of the named water its unnamed outlet flows to,
    opening at the point (x, y; the lakes' CRS, metres) where the creek leaves the shore or the outlet gets to that
    water (05d_lakes.py's outlet_links): only where 12_profiles.py draws that creek's profile within SNAP_FALL of the
    point, as for the drops and known falls (above), or where the creek's NHD lines from the point run down to it
    (creekprofiles.down_to: a first stretch below the lake NHD leaves unjoined to the rest of its creek), opening at
    the profile's point nearest the lake; else None."""
    pt = shapely.Point(x, y)
    if not PROFILES.passes(name, pt):
        pt = PROFILES.down_to(name, pt)
        if pt is None:
            return None
    ll_ = gpd.GeoSeries([pt], crs=EPSG).to_crs(4326).iloc[0]
    return profile_link(name, ll_.y, ll_.x)


maplakes.add(m, X3D, done, approach, profile=lake_profile)

# ---- context layers (11_context.py) ----
fires = ctx("fires")
if fires is not None:
    if "src" not in fires:
        fires["src"] = LBL["fire_src"]
    note_stale("fires", fires.src)
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
        note_stale({"wild_trout_waters": "trout waters", "critical_habitat": "critical habitat", "wilderness": "wilderness",
                    "non_fs_land": "land", "cpad_restricted": "land"}[name], (v for c in fields[0] for v in g[c]))
        g = g.assign(geometry=r6(g.geometry.simplify(0.0002)))
        folium.GeoJson(g[fields[0] + ["geometry"]].to_json(), name=label, show=False,
                       style_function=lambda f, st=style: st,
                       tooltip=folium.GeoJsonTooltip(fields[0], aliases=fields[1])).add_to(m)
        X3D[name] = gj(g.assign(tip=[" · ".join(str(v) for v in row if isinstance(v, str) and v)
                                     for row in g[fields[0]].itertuples(index=False)])[["tip", "geometry"]])
# ---- land ownership (11c_land.py, 11d_parcels.py): public, conservation, tribal and private land, with owners'
# names. Its pieces are in land_data.js and its parcels in parcels_data.js beside the page, which loads them when the
# layer is turned on (map_land.js); here only the entry, and LBL.land that tells both pages the files are there
if os.path.exists(f"{MAP_OUT}/land_data.js"):
    LBL["land"] = "Land ownership"
    folium.FeatureGroup(name=f"<span style='color:#e03131'>▨</span> {LBL['land']}", show=False).add_to(m)
gauges = ctx("gauges")
if gauges is not None and len(gauges):
    gcol = {"much below normal": "#c92a2a", "below normal": "#f76707", "normal": "#2b8a3e", "above normal": "#1c7ed6",
            "much above normal": "#1864ab", "dry": "#c92a2a", "dry (normal for date)": "#adb5bd",
            "flowing (usually dry on this date)": "#1c7ed6", "no history": "#868e96"}
    g3 = []
    if "asof" in gauges:        # 11_context.py since 2026-11-24: " (as of Nov 23)" when the snapshot is a saved copy
        note_stale("gauges", gauges["asof"])         # (gauges.asof would be the DataFrame's asof method)
    # A USGS gauge's popup shows its latest reading, fetched by the visitor's browser when it opens (map_gauges.js: live
    # readings and My Waters, the user's pick of 2026-11-25); the build's reading below is what it shows until then, and
    # with no connection when the phone has seen none newer. Its colour is the build's until the phone has a newer one.
    # (CDEC's server answers no other site, so LA's two CDEC gauges keep the build's reading.)
    LBL["gauges_when"] = (f"as of {STALE['gauges'][1]}; " if "gauges" in STALE else "") + "live on tap"

    # A reading's time: 11_context.py writes a USGS reading's in UTC ("...Z", since 2026-11-26), a CDEC reading's as
    # CDEC's Pacific clock time, and a gauges.gpkg from before 2026-11-26 holds Pacific clock time for every map. The
    # popups' text shows it on the area's own clock with its zone ("Nov 25, 7:30 AM EST"): the trout calendar's zone
    # (11b_calendar.py, from the states its reaches lie in), else UTC; the pages show map_gauges.js's in the phone's
    # own time from LBL.gauge_list (UTC).
    import zoneinfo
    _ZONES = {(-5, True): "America/New_York", (-6, True): "America/Chicago", (-7, True): "America/Denver",
              (-7, False): "America/Phoenix", (-8, True): "America/Los_Angeles", (-9, True): "America/Anchorage",
              (-10, False): "Pacific/Honolulu"}
    _cz = LBL.get("cal") or {}
    _zone = _ZONES.get((_cz.get("tz"), bool(_cz.get("dst", True))))
    _zone = zoneinfo.ZoneInfo(_zone) if _zone else zoneinfo.ZoneInfo("UTC")

    def _when(t_):
        """A reading's time as a UTC Timestamp, or None (unreadable; or in the hour Pacific clocks go back, which
        could be either)."""
        try:
            ts_ = pd.Timestamp(t_)
            if ts_.tzinfo is None:
                ts_ = ts_.tz_localize("America/Los_Angeles", ambiguous="NaT", nonexistent="NaT")
            return None if pd.isna(ts_) else ts_.tz_convert("UTC")
        except (ValueError, TypeError):
            return None

    def _clock(t_):
        """'Nov 25, 7:30 AM EST': the reading's time on the area's clock, or its text as written if unreadable."""
        ts_ = _when(t_)
        if ts_ is None:
            return str(t_)
        lt_ = ts_.tz_convert(_zone)
        return f"{lt_:%b} {lt_.day}, {lt_.hour % 12 or 12}:{lt_:%M} {'AM' if lt_.hour < 12 else 'PM'} {lt_.tzname()}"
    gg = folium.FeatureGroup(name=f"<span style='color:#1c7ed6'>▲</span> {LBL['gauges']} ({LBL['gauges_when']})", show=False)
    for r in gauges.itertuples():
        usgs = not str(r.site).startswith("CDEC")
        now_ = (f"{r.cfs:g} cfs at {_clock(r.time)}<br>{r.status}"
                + (f" · {r.pct_of_median:.0f}% of median for today" if pd.notna(r.pct_of_median) else "")
                + (f"<br>Median for this date {r.p50:g} cfs" if pd.notna(r.p50) else ""))
        link_ = f"<a href='{r.url}' target='_blank'>{'USGS' if usgs else 'CDEC'} station page</a>"
        html = (f"<div class='gpop' data-gauge='{r.site}'><b>{r.name}</b><div class='gnow'>{now_}</div>"
                f"<div class='gact'>{link_}</div></div>") if usgs else f"<b>{r.name}</b><br>{now_}<br>{link_}"
        # (a USGS gauge's tooltip names it only: on a phone Leaflet shows it beside the popup at a tap, and the build's
        # reading there would stand beside a newer one)
        tip_ = f"{r.name} (USGS gauge)" if usgs else f"{r.name}: {r.cfs:g} cfs ({r.status})"
        folium.Marker([r.geometry.y, r.geometry.x], icon=svg_icon(GAUGE_SVG.format(c=gcol.get(r.status, "#868e96")), 18, 16),
                      popup=folium.Popup(html, max_width=280), tooltip=tip_).add_to(gg)
        g3.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.geometry.x, r.geometry.y]},
                   "properties": {"c": gcol.get(r.status, "#868e96"), "html": html, "tip": tip_}})
    X3D["gauges"] = {"type": "FeatureCollection", "features": g3}
    gg.add_to(m)

    def _utc(t_):
        """A reading's time in UTC, for the pages to show in the phone's own time (map_gauges.js), or None."""
        ts_ = _when(t_)
        return None if ts_ is None else ts_.strftime("%Y-%m-%dT%H:%M:%SZ")
    # the USGS gauges for map_gauges.js: site, name, where, and the build's reading with its words (shown offline when the
    # phone has seen none newer): [site, name, lat, lon, cfs, time (UTC), status, % of median, median (cfs)]
    LBL["gauge_list"] = [[str(r.site), r.name, round(r.geometry.y, 5), round(r.geometry.x, 5), float(r.cfs), _utc(r.time),
                          r.status, None if pd.isna(r.pct_of_median) else int(r.pct_of_median),
                          None if pd.isna(r.p50) else float(r.p50)]
                         for r in gauges.itertuples() if not str(r.site).startswith("CDEC")]

# trout evidence and springs (11_context.py)
tev = ctx("trout_evidence")
if tev is not None and len(tev):
    TCOL = {"CDFW survey": "#2b8a3e", "CDFW stocking": "#1c7ed6", "iNaturalist": "#82c91e"}
    note_stale("iNaturalist", tev.label[tev.kind == "iNaturalist"])
    note_stale("trout records", tev.label[tev.kind != "iNaturalist"])
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

# the legends' line for what came from saved copies, oldest copy first, short enough for one line on a phone (the
# legend is 230 px inside): "⚠ As of Nov 23: fires, land and iNaturalist", or "⚠ As of Nov 22: gauges; Nov 23:
# fires". Set only when there is one, so a build on fresh downloads writes the same data as before; LBL["stale"]
# holds the same as [name, day] pairs, oldest first (14_portable.py)
if STALE:
    _order = ["fires", "land", "wilderness", "critical habitat", "trout waters", "trout records", "iNaturalist", "gauges",
              "road closures"]
    LBL["stale"] = [[n_, STALE[n_][1]] for n_ in sorted(STALE, key=lambda n_: (STALE[n_][0], (_order + [n_]).index(n_)))]
    _and = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    _days = list(dict.fromkeys(d_ for _, d_ in LBL["stale"]))
    LBL["stale_line"] = "⚠ As of " + "; ".join(f"{d_}: {_and([n_ for n_, dd_ in LBL['stale'] if dd_ == d_])}" for d_ in _days)
    print("from saved copies:", LBL["stale_line"])

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

# ---- cell coverage (11e_coverage.py): where each carrier reports 4G LTE or 5G outdoors, from the FCC's National
# Broadband Map. Its outlines are in coverage_data.js beside the page, which map_coverage.js loads the first time the
# layer is turned on (on the 3D page too, below); here only the entry, and LBL.cell that tells both pages it is there
if os.path.exists(f"{MAP_OUT}/coverage_data.js"):
    LBL["cell"] = "Cell coverage (FCC)"
    folium.FeatureGroup(name=f"<span style='color:#f08c00'>▦</span> {LBL['cell']}", show=False).add_to(m)
    m.get_root().header.add_child(folium.Element("<script>" + _page_file("map_coverage.js") + "</script>"))

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
if (window.landLeaflet) landLeaflet({{ this._parent.get_name() }}, {{ this.ctrl }});
if (window.StreamsOffline) StreamsOffline.map2d({{ this._parent.get_name() }}, {{ this.ctrl }});
{% endmacro %}""")
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
m.add_child(InitDrainages(lc.get_name()))
# the cell coverage layer (map_coverage.js) once the map and its layer list exist
class InitCell(MacroElement):
    _template = Template("""{% macro script(this, kwargs) %}
if (window.cellLeaflet) cellLeaflet({{ this._parent.get_name() }}, {{ this.ctrl }});
{% endmacro %}""")
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
if LBL.get("cell"):
    m.add_child(InitCell(lc.get_name()))
m.save(f"{MAP_OUT}/stream_map.html")
# folium's libraries from the site's lib/, not from CDNs (weblib.py): the map then needs no network once saved
with open(f"{MAP_OUT}/stream_map.html", encoding="utf-8") as f:
    page2d = weblib.localize(f.read(), "../")
# the page's own script to stream_map.js (above, at POINT_2D): the page runs it after map3d_data.js
page2d, main2d = weblib.split_script(page2d, ["map3d_data.js", "stream_map.js"])
with open(f"{MAP_OUT}/stream_map.js", "w", encoding="utf-8") as f:
    f.write(POINT_2D + "\n" + main2d)
with open(f"{MAP_OUT}/stream_map.html", "w", encoding="utf-8") as f:
    f.write(page2d)
del page2d, main2d

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
# Approach routes (approach_routes.py, from 08_hike.py): each drawn reach's route from its trailhead, in routes_data.js
# beside the pages, which load it on the first click on a reach (map_routes.js); LBL.routes tells them it is there
_routes = approach_routes.pack(MAP_OUT, done, EPSG, s_show.sid.loc[s_feat.index].values,
                               s_show.sid.loc[s_feat_lake.index].values, mi)
if _routes:
    approach_routes.write(f"{MAP_OUT}/routes_data.js", _routes)
    LBL["routes"] = 1
    print(f"approach routes: {sum(r_ >= 0 for r_ in _routes['s'] + _routes['l']):,} of "
          f"{len(_routes['s']) + len(_routes['l']):,} drawn reaches, {len(_routes['k']):,} segments, routes_data.js "
          f"{os.path.getsize(f'{MAP_OUT}/routes_data.js') / 1e6:.2f} MB")
elif os.path.exists(f"{MAP_OUT}/routes_data.js"):
    os.remove(f"{MAP_OUT}/routes_data.js")           # no range has its routes (08_hike.py not run since): none drawn
# 3D map: map3d_data.js holds the layers both maps draw (SHARED_3D; the 2D page loads it too), map3d_layers.js the
# layers only the 3D map draws (they were inline in its page until 2026-11-25). Its page (map3d.html) runs both with
# lib/streams/load.js before it draws: the site keeps them gzip-compressed (weblib.pack); opened straight from disk, the
# page runs the plain files. 14_portable.py reads both.
with open(f"{MAP_OUT}/map3d_data.js", "w") as f:
    f.write("window.MAP3D=" + json.dumps({k: X3D[k] for k in SHARED_3D.values() if k in X3D}, separators=(",", ":"),
                                         default=str) + ";\n")
only3d = json.dumps({k: v for k, v in X3D.items() if k not in SHARED_3D.values()}, separators=(",", ":"), default=str)
only3d = only3d.replace("</", "<\\/").replace("<!--", "<\\u0021--")     # as when it was inline in the page's <script>
with open(f"{MAP_OUT}/map3d_layers.js", "w") as f:
    f.write("if (window.MAP3D) Object.assign(window.MAP3D, " + only3d + ");\n")
page3d = open(os.path.join(os.path.dirname(__file__), "map3d.html")).read()
assert page3d.count("</head>") == 1, "map3d.html must have one </head>"
page3d = page3d.replace("</head>", "<script>" + _page_file("map_filter.js") + "</script>\n<script>"   # the stream filters,
                        + _page_file("map_specs.js") + "</script>\n</head>")          # the specs and similar streams
page3d = page3d.replace("</head>", "<script>" + _page_file("map_gauges.js") + "</script>\n</head>")   # live gauges
tag3d = f'<script src="../{weblib.LOADER}"></script>'
assert page3d.count(tag3d) == 1, "map3d.html must load lib/streams/load.js once"
assert page3d.count('StreamsLoad(["map3d_data.js", "map3d_layers.js"]') == 1, "map3d.html must run its two data files"
assert page3d.count("<!--webapp-->") == 1, "map3d.html must hold <!--webapp--> once (weblib.head goes there)"
page3d = weblib.localize(page3d.replace("<!--webapp-->", weblib.head("../")), "../")
with open(f"{MAP_OUT}/stream_map_3d.html", "w") as f:
    f.write(page3d.replace(tag3d, tag3d + "\n<script>" + _page_file("map_score.js") + "</script>\n<script>"
                           + _page_file("layer_order.js") + "</script>\n<script>" + _page_file("map_routes.js") + "</script>\n<script>"
                           + _page_file("map_land.js") + "</script>"))

print("streams", len(s_ll), "| drops", len(kp_ll))
print(kp_ll.groupby(["region", "status"]).size().unstack(fill_value=0).to_string())

# the trout calendar on both pages, after map_score.js (troutcal.py, map_calendar.js)
troutcal.add_to_pages(MAP_OUT)
# the cell coverage layer on the 3D page, before its own script reads it (map3d.html: cellMaplibre, cellSpot, cellNote)
if LBL.get("cell"):
    _js = _page_file("map_coverage.js")
    assert "</script" not in _js.lower(), "map_coverage.js must not close its <script>"
    with open(f"{MAP_OUT}/stream_map_3d.html") as f:
        _p3 = f.read()
    with open(f"{MAP_OUT}/stream_map_3d.html", "w") as f:
        f.write(_p3.replace(tag3d, tag3d + "\n<script>" + _js + "</script>", 1))
    del _p3, _js
