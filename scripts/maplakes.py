"""The lake layer of the maps, called by 06_map.py: 05d_lakes.py's lakes with their approach and drive times
(08_hike.py writes hike_lakes.csv per range, 09_drive.py the trailheads' drive times), wilderness, the 2D layer with
popups and tooltips, the same features for the 3D map (X3D["lakes"], X3D["lake_depth"]), and lakes.csv / lakes.gpx.
Measured depth contours (lake_bathymetry.py's lake_depth.gpkg) are their own layer. Areas without lakes.gpkg get
nothing.

Fill: blue where the fisheries agency lists game fish or a dated survey or sighting records fish there, grey where
the agency lists none, pale blue where there's no record either way. A dashed edge marks a lake whose lidar showed no
level water (it may be dry or marsh part of the year).
"""
import os, re, json, numpy as np, pandas as pd, geopandas as gpd, shapely, folium
from html import escape as hesc
from branca.element import MacroElement, Template
from urllib.parse import quote
from config import REGIONS, MAP_OUT, SHARED_DERIVED, HOME
from units import ft, mi, acres     # what the maps show is imperial (units.py)

FILL = {"fish": "#1c7ed6", "none": "#adb5bd", "unknown": "#a5d8ff"}
EDGE = {"fish": "#0b4f8a", "none": "#5c636a", "unknown": "#4a90c2"}
FT = 3.28084
# Wyoming Game & Fish's lake classes, as the popups say them
KIND = {"Alpine Lakes": "alpine lake (Game & Fish class)", "Lowland Lakes": "lowland lake (Game & Fish class)",
        "Lowland Reservoirs": "lowland reservoir (Game & Fish class)", "Trout Farm Ponds": "trout farm pond",
        "Unsuitable Standing Waters": "standing water Game & Fish rates unsuitable for fish"}
from lakedata import SALMONIDS as SCI     # the trout family's names, as the popups say them


def _flown(d):
    """A lidar survey's dates, '2017-04-14 to 2018-05-25', as months: '2017-04 to 2018-05', or one month."""
    s, e = (d.split(" to ") + [d])[:2]
    return s[:7] if s[:7] == e[:7] else f"{s[:7]} to {e[:7]}"


class ContourClick(MacroElement):
    """A click on a depth contour opens its lake's popup: over a deep lake the lines cover much of the water."""
    _template = Template("""{% macro script(this, kwargs) %}
{{ this.contours }}.on('click', function (e) {
  var lid = e.layer && e.layer.feature && e.layer.feature.properties.lid;
  if (!lid) return;
  {{ this.lakes }}.eachLayer(function (l) {
    if (l.feature && l.feature.properties.lid === lid) l.fire('click', {latlng: e.latlng}, true);
  });
});
{% endmacro %}""")

    def __init__(self, contours, lakes):
        super().__init__()
        self.contours, self.lakes = contours, lakes


def load(done):
    """lakes.gpkg (the area's CRS) with access, drive and wilderness columns and lat / lon of a point inside, or None."""
    p = f"{SHARED_DERIVED}/lakes.gpkg"
    if not os.path.exists(p):
        return None
    lk = gpd.read_file(p)
    # each lake's drainage and fork: 05c_drainages.py's outlines at the lake's label point (05d_lakes.py: its outlet,
    # or a point inside it). Looked up here since 2026-11-21, so that 05d_lakes.py can run before the reaches are made
    dparts = [gpd.read_file(f"{MAP_OUT}/{r}/drainages.gpkg") for r in done if os.path.exists(f"{MAP_OUT}/{r}/drainages.gpkg")]
    if dparts and "label_x" in lk and lk.label_x.notna().any():
        dr = gpd.GeoDataFrame(pd.concat(dparts, ignore_index=True), crs=dparts[0].crs).to_crs(lk.crs)
        at = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lk.label_x, lk.label_y), index=lk.index, crs=lk.crs)
        j = gpd.sjoin(at[lk.label_x.notna().values], dr[["drainage", "fork", "geometry"]], how="left", predicate="within")
        j = j[~j.index.duplicated()]
        lk["drainage"], lk["fork"] = j.drainage.reindex(lk.index).values, j.fork.reindex(lk.index).values
    parts = [pd.read_csv(f"{MAP_OUT}/{r}/hike_lakes.csv") for r in done if os.path.exists(f"{MAP_OUT}/{r}/hike_lakes.csv")]
    if parts:   # a lake on a box edge is reached from the box with the quicker approach
        h = pd.concat(parts, ignore_index=True).sort_values("approach_min", na_position="last").drop_duplicates("lid")
        lk = lk.merge(h, on="lid", how="left")
        ths = [gpd.read_file(f"{MAP_OUT}/{r}/trailheads.gpkg") for r in done if os.path.exists(f"{MAP_OUT}/{r}/trailheads.gpkg")]
        if ths:
            th = gpd.GeoDataFrame(pd.concat(ths, ignore_index=True), crs=ths[0].crs).to_crs(4326)
            lk = lk.merge(pd.DataFrame({"th_id": th.th_id, "th_road": th.road, "drive_min": th.get("drive_min"),
                                        "drive_km": th.get("drive_km"), "th_lat": th.geometry.y.round(6),
                                        "th_lon": th.geometry.x.round(6), "th_closed": th.get("closed_now")}),
                          on="th_id", how="left")
    for c in ("approach_min", "bike_min", "walk_min", "bike_check", "bike_check_min", "route_km", "th_road", "drive_min",
              "drive_km", "th_lat", "th_lon", "th_id", "th_closed"):
        if c not in lk:
            lk[c] = np.nan if c not in ("bike_check", "th_road", "th_id", "th_closed") else None
    # wilderness, from 11_context.py
    lk["wilderness"] = None
    wp = f"{MAP_OUT}/context/wilderness.gpkg"
    if os.path.exists(wp):
        wd = gpd.read_file(wp).to_crs(lk.crs)
        for i, g in zip(lk.index, lk.geometry):
            hit = wd[wd.intersects(g)]
            if len(hit):
                lk.loc[i, "wilderness"] = hit.loc[hit.geometry.intersection(g).area.idxmax(), "wilderness"]
    # the state agency's stocking and survey records at the lake (11_context.py's trout evidence; iNaturalist comes
    # through GBIF already): a lake record within 150 m of the shore, or one naming the lake within 2 km
    lk["agency_recs"], lk["agency_trout"] = None, False
    tp = f"{MAP_OUT}/context/trout_evidence.gpkg"
    # and the lake-only records 05d_lakes.py writes beside the lakes (New York: DEC's stocking list and lake fishing list)
    rp = f"{SHARED_DERIVED}/lake_records.gpkg"
    tparts = [gpd.read_file(p_).to_crs(lk.crs) for p_ in (tp, rp) if os.path.exists(p_)]
    if tparts:
        te = gpd.GeoDataFrame(pd.concat(tparts, ignore_index=True), crs=lk.crs)
        te = te[te.kind != "iNaturalist"]
        key = lambda v: "".join(ch for ch in str(v).lower() if ch.isalnum()) if isinstance(v, str) else ""
        # the same name in another word order or with a filler word: "Gregory Lake" is Lake Gregory, "Hansen Dam
        # Lake" is Hansen Dam Recreation Lake
        words = lambda v: frozenset(re.findall(r"[a-z0-9]+", v.lower())) - {"the", "recreation", "area"} if isinstance(v, str) else frozenset()
        names = [{key(n) for n in (r.name, r.gnis_name, r.agency_name) if isinstance(n, str)} for r in lk.itertuples()]
        wsets = [{words(n) for n in (r.name, r.gnis_name, r.agency_name) if isinstance(n, str)} for r in lk.itertuples()]
        got, named_by = {}, {}
        for e in te.itertuples():
            near = [i for i in lk.sindex.query(e.geometry.buffer(2000), predicate="intersects")]
            if not near:
                continue
            named = [i for i in near if key(e.water) and (key(e.water) in names[i] or words(e.water) in wsets[i])]
            # by position only a lake's own record: a stream's stocking or survey point beside a pond is the stream's
            # (the Blue Ridge tailwater's stocking point lies in a 5 ha pool of the Toccoa; CT DEEP's stream surveys
            # sit at the inlets and outlets of 44 Connecticut ponds)
            lake_rec = getattr(e, "lake", False)
            lake_rec = bool(lake_rec) if pd.notna(lake_rec) else False
            close = [i for i in near if lk.geometry.iat[i].distance(e.geometry) <= 150] if lake_rec else []
            pick = named or close
            if pick:
                i = min(pick, key=lambda i: lk.geometry.iat[i].distance(e.geometry))
                got.setdefault(i, []).append((e.year if pd.notna(e.year) else 0, str(e.label), bool(e.trout)))
                if lake_rec and isinstance(e.water, str) and not named:
                    named_by.setdefault(i, set()).add(e.water.strip())
        for i, v in got.items():
            v = sorted(set(v), reverse=True)
            lk.loc[lk.index[i], "agency_recs"] = json.dumps([l for _, l, _ in v][:6])
            lk.loc[lk.index[i], "agency_trout"] = any(t for _, _, t in v)
        # a lake without a name takes the one its own stocking or survey record gives it (Yucaipa Lake, CDFW)
        for i, w in named_by.items():
            if not isinstance(lk.name.iat[i], str) and len(w) == 1:
                lk.loc[lk.index[i], ["name", "name_src"]] = [w.pop(), "agency list"]
    pt = lk.geometry.representative_point().to_crs(4326)
    lk["lat"], lk["lon"] = pt.y.round(6).values, pt.x.round(6).values
    return lk


def _fish(r):
    """(class, one-line summary, list of record lines) for a lake row."""
    rec = json.loads(r.records) if isinstance(r.records, str) else []
    seen, lines = set(), []
    for x in rec:                                   # newest first; one line per species and source
        k = (x["species"], x["source"])
        if k in seen:
            continue
        seen.add(k)
        lines.append(f"{SCI.get(x['species'], x['species'])}: {x['source']}" + (f" {x['year']}" if x.get("year") else ""))
    ag = json.loads(r.agency_recs) if isinstance(getattr(r, "agency_recs", None), str) else []
    lines = ag + lines
    if isinstance(r.game_fish, str) and r.game_fish != "None":
        return "fish", f"{r.game_fish} ({r.agency})", lines
    if r.game_fish == "None":
        return ("fish" if rec else "none"), f"No game fish ({r.agency})", lines
    if getattr(r, "agency_trout", False) or rec:
        return "fish", "Trout stocked or recorded here", lines
    if ag:
        return "unknown", "No trout in the agency's records here", lines
    return "unknown", "No fisheries agency record", lines


def _size(ha):
    return acres(ha)


def _depth(r):
    if pd.notna(r.depth_max_m):
        s = f"max {ft(r.depth_max_m)}"
        if pd.notna(r.depth_mean_m):
            s += f", mean {ft(r.depth_mean_m)}"
        return s + f" · {r.depth_src}" + (f" · {r.depth_note}" if isinstance(r.depth_note, str) and r.depth_note else "")
    if isinstance(r.depth_note, str) and r.depth_note:
        return r.depth_note
    return "no measured depth found"


def popup(r, approach):
    cls, fish, recs = _fish(r)
    nm = r.name if isinstance(r.name, str) else "Unnamed lake"
    alt = r.agency_name if isinstance(r.agency_name, str) and r.agency_name != nm else None
    kind = " / ".join(KIND.get(t, t) for t in r.lake_type.split(" / ")) if isinstance(r.lake_type, str) and r.lake_type else r.ftype
    el = ft(r.elev_m) + (
        f" · water level by lidar, {_flown(r.lidar_dates)}" if r.elev_src == "lidar water level" and isinstance(r.lidar_dates, str) else
        f" · lidar water surface (not flattened), {_flown(r.lidar_dates)}" if str(r.elev_src).startswith("lidar water surface")
        and isinstance(r.lidar_dates, str) else
        f" · {r.elev_src}" if str(r.elev_src).startswith(("normal level", "its shoreline")) else "")
    conn = []
    if isinstance(r.outlet_name, str):
        conn.append(f"outlet {r.outlet_name}")
    elif r.outlets:
        conn.append("outlet (unnamed)")
    if isinstance(r.inlet_names, str):
        conn.append(f"inlets {r.inlet_names}")
    elif r.inlets:
        conn.append(f"{r.inlets} unnamed inlet{'s' if r.inlets > 1 else ''}")
    gm = f"https://www.google.com/maps/@?api=1&map_action=map&center={r.lat:.5f},{r.lon:.5f}&zoom=16&basemap=satellite"
    acc = approach(r) + (f" · route about {mi(r.route_km)}" if pd.notna(r.route_km) else "")
    rows = [("Type", hesc(f"{kind} · {_size(r.ha)}")), ("Elevation", hesc(el)),
            ("Fish", f"<b>{hesc(fish)}</b>" + ("<br>" + "<br>".join(hesc(x) for x in recs[:5]) if recs else "")
             + (f"<br>{hesc(r.survey)}" if isinstance(getattr(r, "survey", None), str) else "")
             + (f"<br><span class='warn'>Also recorded, not on the agency's list: {hesc(r.also_recorded)}</span>"
                if isinstance(getattr(r, "also_recorded", None), str) else "")),
            ("Depth", hesc(_depth(r))),
            ("Water", hesc("; ".join(conn) if conn else r.connection)),
            ("Access", hesc(acc)),
            *([("On site", hesc(r.access))] if isinstance(getattr(r, "access", None), str) else []),
            *([("Rules", hesc("; ".join(x for x in (getattr(r, "designation", None), getattr(r, "rules", None)) if isinstance(x, str))))]
              if isinstance(getattr(r, "designation", None), str) or isinstance(getattr(r, "rules", None), str) else []),
            ("Land", hesc(getattr(r, "land", None) if isinstance(getattr(r, "land", None), str) else "private or unlisted (not in PAD-US)")
             + (f" <span class='warn'>· public access {hesc(r.land_access)}</span>"
                if getattr(r, "land_access", None) in ("restricted", "closed") else ""))]
    note = [x for x in (r.conflict, r.water_note, r.private_shore,
                        f"{r.wilderness} (no bikes)" if isinstance(r.wilderness, str) else None,
                        f"{r.drainage} · {r.fork}" if isinstance(r.drainage, str) and r.fork != r.drainage else r.drainage)
            if isinstance(x, str) and x]
    # the agency's own name for it, where it differs (Wyoming Game & Fish; NCWRC's "Calderwood Reservoir")
    who = {"Wyoming Game & Fish": "Game & Fish"}.get(r.agency, r.agency) if isinstance(r.agency, str) else "agency"
    html = (f"<div class='pp'><b>{hesc(nm)}</b>" + (f" <span class='dm'>({hesc(who)}: {hesc(alt)})</span>" if alt else "")
            + "<table>" + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"
            + ("".join(f"<div class='warn'>{hesc(x)}</div>" if x in (r.conflict, r.water_note, r.private_shore) else
                       f"<div class='dw'>{hesc(x)}</div>" for x in note))
            + f"<div class='dm'>Outline: {hesc(str(r.src_outline))}"
            + (f" (NHD {acres(r.nhd_ha)})" if pd.notna(r.nhd_ha) and str(r.src_outline).startswith("lidar") else "")
            + (f"; {hesc(r.outline_note)}" if isinstance(r.outline_note, str) else "")
            + {"OpenStreetMap": " · name from OpenStreetMap", "survey": " · name from the depth survey",
               "agency list": " · name from the state's stocking or survey list"}.get(r.name_src, "") + "</div>"
            + f"<a href='{gm}' target='_blank'>Satellite view</a>"
            + (f" · <a href='profiles.html#q={quote(r.outlet_name.split(', ')[0])}' target='_blank'>Outlet creek profile ↗</a>"
               if isinstance(r.outlet_name, str) else "")
            + (" · <a href='https://wgfd.wyo.gov/current-fishing-regulations' target='_blank'>Fishing regulations ↗</a>"
               if r.agency == "Wyoming Game & Fish" else "")
            + "".join(f" · <a href='{hesc(u)}' target='_blank'>Agency page ↗</a>"
                      for u in (str(getattr(r, "links", "") or "").split("; ")[:2]) if u.startswith("http")) + "</div>")
    # Wyoming lists every lake's game fish ("None" too); elsewhere the agencies list stocking and samples, so a lake
    # without a trout among them has "no trout record", not "no fish record" (Pachaug Pond: 12 species, no trout)
    wy = r.agency == "Wyoming Game & Fish"
    if cls == "fish":
        short = fish.split(" (")[0] if wy and isinstance(r.game_fish, str) and r.game_fish != "None" else "trout stocked or recorded"
    elif cls == "none":
        short = "no game fish listed"
    else:
        short = "no fish record" if wy else "no trout record"
    tip = f"{nm} · {_size(r.ha)} · {short}" + (
        f" · {r.approach_min:.0f} min in" if pd.notna(r.approach_min) else "")
    return cls, html, tip, short


def add(m, X3D, done, approach):
    """Add the lake layers to the folium map and X3D; write lakes.csv and lakes.gpx. Returns the lakes or None."""
    lk = load(done)
    if lk is None or not len(lk):
        return None
    out = [popup(r, approach) for r in lk.itertuples()]
    lk["cls"], lk["html"], lk["tip"], lk["fish"] = ([o[k] for o in out] for k in range(4))
    lk["c"], lk["e"] = lk.cls.map(FILL), lk.cls.map(EDGE)
    lk["dry"] = lk.water_note.fillna("").str.startswith("no level water")
    g2 = lk[["lid", "c", "e", "dry", "tip", "html", "geometry"]].copy()
    g2["geometry"] = shapely.set_precision(g2.geometry.simplify(2.0).to_crs(4326).values, 1e-6)   # area CRS: metres
    js = json.loads(g2.to_json(drop_id=True))
    full = lk.agency.eq("Wyoming Game & Fish").any()           # a full inventory (game fish or "None") only there
    legend = ("<span style='color:#1c7ed6'>■</span> game fish <span style='color:#adb5bd'>■</span> none listed "
              "<span style='color:#a5d8ff'>■</span> no record") if full else \
             ("<span style='color:#1c7ed6'>■</span> trout stocked or recorded <span style='color:#a5d8ff'>■</span> no trout record")
    name = "<span style='color:#1c7ed6'>■</span> Lakes: " + legend
    X3D["lake_legend"] = "Lakes: " + legend
    lakes_layer = folium.GeoJson(js, name=name, show=True,      # on when the map opens (user, 2026-11-20)
                   style_function=lambda f: {"color": f["properties"]["e"], "weight": 1.2, "fillColor": f["properties"]["c"],
                                             "fillOpacity": 0.55, "dashArray": "4 3" if f["properties"]["dry"] else None},
                   highlight_function=lambda f: {"weight": 2.5, "fillOpacity": 0.7},
                   tooltip=folium.GeoJsonTooltip(["tip"], labels=False),
                   popup=folium.GeoJsonPopup(["html"], labels=False, max_width=360)).add_to(m)
    X3D["lakes"] = js
    # measured depth contours (lake_bathymetry.py), if any
    dp = f"{SHARED_DERIVED}/lake_depth.gpkg"
    if os.path.exists(dp):
        dc = gpd.read_file(dp)
        if len(dc):
            dc = dc.to_crs(4326)
            ft_ = dc.depth_ft if "depth_ft" in dc else dc.depth_m / 0.3048
            dc["tip"] = [f"{f:g} ft deep · {s}" for f, s in zip(ft_.round(0), dc.src)]
            dc["major"] = dc.major.astype(bool) if "major" in dc else (dc.depth_m % 10 == 0)
            dj = json.loads(dc[["lid", "depth_m", "major", "tip", "geometry"]].assign(
                geometry=shapely.set_precision(dc.geometry.values, 1e-6)).to_json(drop_id=True))
            dl = folium.GeoJson(dj, name="<span style='color:#1864ab'>〰</span> Lake depth contours (measured surveys)", show=False,
                                style_function=lambda f: {"color": "#1864ab", "weight": 1.6 if f["properties"]["major"] else 0.8,
                                                          "opacity": 0.85},
                                tooltip=folium.GeoJsonTooltip(["tip"], labels=False)).add_to(m)
            m.add_child(ContourClick(dl.get_name(), lakes_layer.get_name()))
            X3D["lake_depth"] = dj
    # table and GPX
    tab = lk.assign(acres=(lk.ha * 2.47105).round(1))
    keep = ["lid", "name", "agency_name", "lake_type", "ftype", "ha", "acres", "elev_m", "elev_src", "depth_max_m",
            "depth_mean_m", "depth_src", "depth_note", "survey", "game_fish", "common_fish", "fish", "n_records", "conflict", "outlet_name",
            "inlet_names", "connection", "drainage", "fork", "approach_min", "bike_min", "walk_min", "route_km",
            "bike_check", "th_road", "th_lat", "th_lon", "drive_min", "drive_km", "th_closed", "land", "land_access", "access", "rules",
            "designation", "links", "agency_recs", "wilderness", "private_shore",
            "water_note", "src_outline", "nhd_ha", "lidar_dates", "lat", "lon"]
    tab[[c for c in keep if c in tab]].sort_values(["ha"], ascending=False).to_csv(f"{MAP_OUT}/lakes.csv", index=False)
    with open(f"{MAP_OUT}/lakes.gpx", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<gpx version="1.1" creator="stream-analysis" xmlns="http://www.topografix.com/GPX/1/1">\n')
        for r in lk.itertuples():
            nm = r.name if isinstance(r.name, str) else f"Lake {r.lid}"
            desc = hesc(r.tip + (f"; {approach(r)}" if pd.notna(r.approach_min) else ""), quote=False)
            f.write(f'<wpt lat="{r.lat:.6f}" lon="{r.lon:.6f}"><name>{hesc(nm, quote=False)}</name><desc>{desc}</desc></wpt>\n')
        f.write("</gpx>\n")
    print(f"lakes: {len(lk)} drawn ({lk.cls.value_counts().to_dict()}), with an approach time {lk.approach_min.notna().sum()}"
          + (f", depth contours {len(X3D['lake_depth']['features'])}" if "lake_depth" in X3D else ""))
    return lk
