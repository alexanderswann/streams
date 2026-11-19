"""Fetch current road closures for the mountain roads in every study area and write them as lines.

Sources (all live, re-run this script to refresh):
  - Caltrans Lane Closure System (D6 Fresno/Kern, D7 Los Angeles/Ventura, D8 San Bernardino/Riverside,
    D12 Orange): mountain highways, begin/end points.
    Each closure is routed along the OSM highway network between its two points.
  - LA County Public Works road closures (polylines).
  - San Bernardino County Public Works road closures (polylines).
  - Riverside County TLMA road closures (polylines) and Ventura County PWA closures (points with from / to cross
    streets, drawn along the named road between them). Orange County's feed is empty and Kern has none.
  - OSM ways tagged access/motor_vehicle = no/private: gated roads closed to public vehicles (static).
USFS closure orders are published only as PDFs and are not included.

Outside California (config.py `sources`; each feed was fetched and checked on 2026-11-18, none needs a key):
  grte_roads      Grand Teton National Park's road status (lines): closed, travel impacted, over-snow only
  teton_county    Teton County, Wyoming, emergency road closures (lines; active ones only)
  gdot_511        Georgia 511 events (points with the event's line, Google-encoded); refreshed every 15 minutes
  ne_compass      New England Compass work-zone feed (WZDx GeoJSON): Vermont's closures, seasonal ones included
                  (Lincoln Gap, Smugglers Notch), and lane closures
  vdot_511        Virginia 511's map files (points; the wording says whether the road is closed). Undocumented
                  files behind 511.vdot.virginia.gov: they may move
  blri_roads      Blue Ridge Parkway closures: the park's web table of milepost sections, drawn between the
                  park's milepost points along OSM roads
WYDOT's highway conditions and Connecticut's closures have no feed that works without an account: not included.
"""
import json, os, re, time, datetime as dt, requests, numpy as np, pandas as pd, geopandas as gpd, networkx as nx
from shapely.geometry import LineString, Point, box, shape
from shapely.ops import linemerge, substring
from config import REGIONS, CRS, EPSG, ROOT, MAP_OUT, raw_dir, has
CA = has("ca_closures")

UA = {"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"}
NOW = dt.datetime.now()
LOOKAHEAD = dt.timedelta(days=7)  # also show closures starting within a week
# Mountain highways only; urban freeway night work along the foothills would bury the map
ROUTES = {"SR-1", "SR-2", "SR-18", "SR-23", "SR-27", "SR-38", "SR-39", "SR-138", "SR-142", "SR-173", "SR-189",
          "SR-330",
          "SR-33", "SR-150", "SR-126",   # Sespe / Ojai / Fillmore
          "SR-243", "SR-74",             # San Jacinto (Idyllwild) and the Ortega Highway (Santa Ana Mountains)
          "I-5"}                         # the Grapevine, for Piru / Pyramid / Mt. Pinos
FULL_ONLY = {"I-5"}                      # freeway: only full closures matter for access
# Caltrans "facility" values that aren't the highway's own lanes (the others seen: Mainline, Conventional Hwy)
SIDE = re.compile(r"ramp|connector|rest area|vista|weigh|inspection|park\s*(?:and|&)\s*ride", re.I)

area = gpd.GeoSeries([box(*v["bbox"]).buffer(2000) for v in REGIONS.values()], crs=CRS).union_all()

def get_json(url, params=None):
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=120)
            if r.ok:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"no usable answer from {url} after 4 tries")

# ---- OSM highway graph for routing Caltrans begin/end points ----
roads = pd.concat([gpd.read_file(f"{raw_dir(r)}/osm_roads.gpkg") for r in REGIONS], ignore_index=True)
roads = gpd.GeoDataFrame(roads, crs=CRS)
# Every road type is routable (closed highways such as upper SR-39 are tagged as gated service roads in OSM),
# but minor roads cost 3x so routes stick to highways where they exist.
HW = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link", "primary_link",
      "secondary_link"}
G = nx.Graph()
for geom, cls in zip(roads.geometry, roads.highway):
    k = 1.0 if cls in HW else 3.0
    cs = [(round(x, 1), round(y, 1)) for x, y in geom.coords]
    for a, b in zip(cs[:-1], cs[1:]):
        G.add_edge(a, b, w=k * float(np.hypot(a[0] - b[0], a[1] - b[1])))
nodes = np.array(list(G.nodes))
from scipy.spatial import cKDTree
tree = cKDTree(nodes)

def route(p, q):
    """Road-following line between two points (UTM); straight line if no path or >3x crow-flies."""
    (dp, dq), (ip, iq) = tree.query([p, q])  # (distances, indices)
    if dp > 150 or dq > 150:
        return LineString([p, q])
    a, b = tuple(nodes[ip]), tuple(nodes[iq])
    if a == b:
        return Point(p).buffer(60).exterior  # spot closure: small ring so it is visible
    try:
        path = nx.shortest_path(G, a, b, weight="w")
    except nx.NetworkXNoPath:
        return LineString([p, q])
    line = LineString(path)
    return line if line.length < 3 * Point(p).distance(Point(q)) + 500 else LineString([p, q])

to_utm = lambda lon, lat: gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(CRS).iloc[0].coords[0]
rows = []

# ---- Caltrans LCS ----
for d in ((6, 7, 8, 12) if CA else ()):
    data = get_json(f"https://cwwp2.dot.ca.gov/data/d{d}/lcs/lcsStatusD{d:02d}.json")["data"]
    seen = set()
    for rec in data:
        l = rec["lcs"]; c = l["closure"]; b = l["location"]["begin"]; e = l["location"]["end"]
        if b["beginRoute"] not in ROUTES:
            continue
        key = (c["closureID"], c["logNumber"])
        if key in seen:
            continue
        seen.add(key)
        t = c["closureTimestamp"]
        start = dt.datetime.fromtimestamp(int(t["closureStartEpoch"]))
        indefinite = t["isClosureEndIndefinite"] == "true"
        end = None if indefinite or not t["closureEndEpoch"] else dt.datetime.fromtimestamp(int(t["closureEndEpoch"]))
        if (end is not None and end < NOW) or start > NOW + LOOKAHEAD:
            continue
        p = to_utm(float(b["beginLongitude"]), float(b["beginLatitude"]))
        q = to_utm(float(e["endLongitude"] or b["beginLongitude"]), float(e["endLatitude"] or b["beginLatitude"]))
        if not (area.contains(Point(p)) or area.contains(Point(q))):
            continue
        # A "Full" closure of a ramp, connector or rest area closes that, not the highway: the Tejon Pass rest areas
        # and a truck escape ramp used to count as full closures of I-5, and the routing cut the freeway there
        side = bool(SIDE.search(c.get("facility") or ""))
        full = not side and (c["typeOfClosure"] == "Full" or c["lanesClosed"] == c["totalExistingLanes"])
        if b["beginRoute"] in FULL_ONLY and not full:
            continue
        rows.append(dict(
            source="Caltrans", road=f"{b['beginRoute']} ({l['location']['travelFlowDirection']})",
            from_=b["beginLocationName"], to=e["endLocationName"],
            severity="full closure (one direction)" if full and c["typeOfClosure"] != "Full" else
                     "full closure" if full else "ramp / rest area closed" if side else "lane / one-way",
            work=c["typeOfWork"],
            reason=f"{c['typeOfWork']} · {c['typeOfClosure']} closure, {c['lanesClosed']}/{c['totalExistingLanes']} lanes"
                   + ("" if c["facility"] == "Mainline" else f" ({c['facility']})"),
            start=start.strftime("%Y-%m-%d %H:%M"),
            end="indefinite" if end is None else end.strftime("%Y-%m-%d %H:%M"),
            when="active now" if start <= NOW else "upcoming (7 days)",
            long_term=indefinite or (end is not None and end - start > dt.timedelta(days=7)),
            geometry=route(p, q)))
if CA:
    print("Caltrans", len(rows))

# ---- County Public Works ----
def county(url, fields, mk, where="1=1"):
    if not CA:
        return 0
    js = get_json(url, dict(where=where, outFields=",".join(fields), outSR=EPSG, f="geojson"))
    n = 0
    for f in js.get("features", []):
        if not f.get("geometry"):
            continue
        geom = gpd.GeoDataFrame.from_features([f], crs=CRS).geometry.iloc[0]
        rec = mk(f["properties"])
        if rec is None or geom.is_empty or not geom.intersects(area):
            continue
        rows.append(dict(rec, geometry=linemerge(geom) if geom.geom_type == "MultiLineString" else geom))
        n += 1
    return n

def reopening(reopen):
    """LA County's estimated reopening ("12 31 26 12:00 AM") as a datetime; None for "TBD" or anything else."""
    try:
        return dt.datetime.strptime(reopen, "%m %d %y %I:%M %p")
    except ValueError:
        return None

def la(p):
    reopen = (p.get("ESTIMATEDREOPENING") or "").strip()
    due = reopening(reopen)
    # county lists sometimes keep closures whose estimated reopening has already passed
    note = " · still listed, but est. reopening has passed" if due is not None and due < NOW else ""
    return dict(source="LA County DPW", road=(p.get("MAIN_") or "").strip(), from_=p.get("FROM_"), to=p.get("TO_"),
                severity="full closure", reason=(p.get("REASON") or "") + note, start=p.get("ACTUALCLOSUREDATEFORMATTED"),
                end=reopen or "TBD", when="active now",
                long_term=due is None or due - NOW > dt.timedelta(days=7))   # as for Caltrans: no date, or over a week off
print("LA County", county("https://dpw.gis.lacounty.gov/dpw/rest/services/Road_Closures/MapServer/0/query",
                          ["MAIN_", "FROM_", "TO_", "REASON", "ACTUALCLOSUREDATEFORMATTED", "ESTIMATEDREOPENING"], la))

def ms(v):
    return dt.datetime.fromtimestamp(v / 1000).strftime("%Y-%m-%d") if v else ""
def sb(p):
    return dict(source="San Bernardino County DPW", road=p.get("street") or "unnamed road", from_=None, to=None,
                severity="full closure", reason=" · ".join(x for x in (p.get("subtype"), p.get("description")) if x),
                start=ms(p.get("starttime")), end=ms(p.get("endtime")) or "TBD", when="active now",
                long_term=not p.get("endtime"))
print("SB County", county("https://services.arcgis.com/ZZ0KZXZVmgB1v555/arcgis/rest/services/"
                          "RoadClosures_89e62fc252ba4ce3b88ac0b524ebd6f0_public/FeatureServer/1/query",
                          ["street", "subtype", "description", "starttime", "endtime"], sb))

def riverside(p):
    if str(p.get("IsClosed", "Y")).strip().upper() in ("N", "NO", "0", "FALSE"):
        return None
    return dict(source="Riverside County TLMA", road=p.get("RoadName") or "unnamed road", from_=p.get("RoadFrom"),
                to=p.get("RoadTo"), severity="full closure", reason=p.get("ClosureReason") or "", start=ms(p.get("ClosedOn")),
                end=ms(p.get("OpenedOn")) or "TBD", when="active now", long_term=not p.get("OpenedOn"))
print("Riverside County", county("https://gis.countyofriverside.us/arcgis/rest/services/road_closures/"
                                 "roadClosures_wMap_prod/MapServer/11/query",
                                 ["RoadName", "RoadFrom", "RoadTo", "ClosureReason", "ClosedOn", "OpenedOn", "IsClosed"],
                                 riverside))

# Ventura County publishes points (with the road name and its from / to cross streets), not lines. The closure
# line is the named road between where it meets the from and to roads (a state route such as "SR33" matches any
# highway); if those can't be found, the named road within 2 km of the point.
def ventura():
    if not CA:
        return 0
    js = get_json("https://services5.arcgis.com/LU8yNTyyh8FrdvWy/arcgis/rest/services/ActiveRoadClosures/FeatureServer/0/query",
                  dict(where="RoadStatus='Closed'", outFields="RoadName,From_,To_,StartDate,EndDate,ClosureType,Description",
                       outSR=EPSG, f="geojson"))
    norm = lambda t: " ".join(w for w in str(t or "").lower().replace(".", " ").split()
                              if w not in {"road", "rd", "street", "st", "avenue", "ave", "highway", "hwy"})
    n = 0
    for f in js.get("features", []):
        pr, g = f["properties"], f.get("geometry")
        if not g:
            continue
        pt = Point(g["coordinates"])
        if not area.contains(pt):
            continue
        named = roads[roads["name"].fillna("").map(norm).eq(norm(pr.get("RoadName"))) & (roads.distance(pt) < 30000)]
        if not len(named):
            continue
        line = linemerge(named.geometry.union_all())
        def anchor(cross):
            if re.match(r"^(s[rh]|ca|us)[\s-]*\d+", str(cross or "").strip().lower()):
                other = roads[roads.highway.isin(["motorway", "trunk", "primary", "secondary"])]
            else:
                other = roads[roads["name"].fillna("").map(norm).eq(norm(cross))]
            hits = [h for h in [line.intersection(o) for o in other.geometry] if not h.is_empty]
            pts = [q for h in hits for q in getattr(h, "geoms", [h]) if q.geom_type == "Point"]
            return min(pts, key=lambda q: q.distance(pt)) if pts else None
        a_, b_ = anchor(pr.get("From_")), anchor(pr.get("To_"))
        geom = None
        if a_ is not None and b_ is not None and line.geom_type == "LineString":
            d1, d2 = sorted((line.project(a_), line.project(b_)))
            geom = substring(line, d1, d2) if d2 - d1 > 50 else None
        if geom is None:
            geom = named[named.distance(pt) < 2000].geometry.union_all()
            geom = linemerge(geom) if geom.geom_type == "MultiLineString" else geom
        rows.append(dict(source="Ventura County PWA", road=pr.get("RoadName"), from_=pr.get("From_"), to=pr.get("To_"),
                         severity="full closure", reason=" · ".join(x for x in (pr.get("ClosureType"), pr.get("Description")) if x),
                         start=pr.get("StartDate") or "", end=pr.get("EndDate") or "TBD", when="active now",
                         long_term=True, geometry=geom))
        n += 1
    return n
print("Ventura County", ventura())

# ---- outside California ----
W_, S_, E_, N_ = gpd.GeoSeries([area], crs=CRS).to_crs(4326).total_bounds
def arc(url, where="1=1", fields="*"):
    """Features of an ArcGIS layer in the area, as (properties, geometry in the area's CRS)."""
    js = get_json(f"{url}/query", dict(where=where, geometry=f"{W_},{S_},{E_},{N_}", geometryType="esriGeometryEnvelope",
                                       inSR=4326, spatialRel="esriSpatialRelIntersects", outFields=fields, outSR=EPSG,
                                       f="geojson"))
    g = gpd.GeoDataFrame.from_features(js.get("features", []), crs=CRS) if js.get("features") else None
    return [] if g is None else [(row._asdict(), row.geometry) for row in g[g.geometry.notna() & g.intersects(area)].itertuples()]
def line_of(g):
    g = linemerge(g) if g.geom_type == "MultiLineString" else g
    return g if g.geom_type in ("LineString", "MultiLineString") else Point(g.representative_point().coords[0]).buffer(60).exterior
def when_of(start, end):
    """(start text, end text, 'active now' / 'upcoming (7 days)' / None if it is over or further off, long-term?)."""
    if end is not None and end < NOW:
        return None
    if start is not None and start > NOW + LOOKAHEAD:
        return None
    return (start.strftime("%Y-%m-%d %H:%M") if start else "", "indefinite" if end is None else end.strftime("%Y-%m-%d %H:%M"),
            "active now" if start is None or start <= NOW else "upcoming (7 days)",
            end is None or (start is not None and end - start > dt.timedelta(days=7)))
def from_ms(v):
    return dt.datetime.fromtimestamp(float(v) / 1000) if v not in (None, "") and pd.notna(v) else None
def txt(*parts):
    """The parts that hold text, joined (the services leave empty fields as None or NaN)."""
    return " · ".join(str(x).strip() for x in parts if isinstance(x, str) and x.strip())
def add(source, road, severity, reason, start, end, geom, always=False, frm=None, to=None):
    w = when_of(start, end)
    if w is not None and geom is not None and not geom.is_empty:
        rows.append(dict(source=source, road=road if isinstance(road, str) and road.strip() else "unnamed road", from_=frm, to=to, severity=severity,
                         reason=" ".join(str(reason or "").split())[:300], start=w[0], end=w[1], when=w[2], long_term=w[3],
                         always=always, geometry=geom))

if has("grte_roads"):     # Grand Teton National Park: 1 open, 2 travel impacted, 3 closed, 4-6 over-snow travel only
    n0 = len(rows)
    for p, g in arc("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRTE_MajorRoadStatus_(PublicView)/FeatureServer/0"):
        st = pd.to_numeric(p.get("CurrentStatus"), errors="coerce")
        if pd.notna(st) and st >= 2:
            add("Grand Teton NP", p.get("RDNAME"), "full closure" if st >= 3 else "lane / one-way",
                txt("closed to cars: over-snow travel only" if st >= 4 else "", p.get("NOTES"), p.get("SEASDESC")),
                None, None, line_of(g), always=True)
    print("Grand Teton NP", len(rows) - n0)
if has("teton_county"):
    n0 = len(rows)
    for p, g in arc("https://services9.arcgis.com/6ukHJ1QHS9lvQoRO/arcgis/rest/services/RoadClosures_public_e8ea8c3a825645f3b74f657c09433efd/FeatureServer/1",
                    where="activeincid='Yes'"):
        full = "all" in str(p.get("laneimpact") or "").lower()
        add("Teton County", p.get("street"), "full closure" if full else "lane / one-way",
            txt(p.get("reason"), p.get("description")), from_ms(p.get("starttime")),
            from_ms(p.get("endtime")), line_of(g), always=True)
    print("Teton County", len(rows) - n0)
if has("gdot_511"):
    def polyline(sx):
        """Google's encoded polyline -> [(lon, lat)]."""
        out, i, lat, lon = [], 0, 0, 0
        while i < len(sx):
            for k in (0, 1):
                shift = res = 0
                while True:
                    b = ord(sx[i]) - 63; i += 1
                    res |= (b & 0x1F) << shift; shift += 5
                    if b < 0x20:
                        break
                d = ~(res >> 1) if res & 1 else res >> 1
                lat, lon = (lat + d, lon) if k == 0 else (lat, lon + d)
            out.append((lon / 1e5, lat / 1e5))
        return out
    n0 = len(rows)
    for p, g in arc("https://services1.arcgis.com/2iUE8l8JKrP2tygQ/arcgis/rest/services/GDOT_511_Events_Public_View/FeatureServer/0"):
        geom = g
        try:
            pts = polyline(p.get("EncodedPolyline") or "")
            if len(pts) >= 2:
                geom = gpd.GeoSeries([LineString(pts)], crs=4326).to_crs(CRS).iloc[0]
        except (IndexError, TypeError):
            pass
        full = str(p.get("IsFullClosure")).lower() == "true"
        add("Georgia 511", p.get("RoadwayName"), "full closure" if full else "lane / one-way",
            txt(p.get("EventType"), p.get("LanesAffected"), p.get("Description")),
            from_ms(p.get("StartDate")), from_ms(p.get("PlannedEndDate")), line_of(geom))
    print("Georgia 511", len(rows) - n0)
if has("ne_compass"):
    n0 = len(rows)
    iso = lambda v: pd.Timestamp(v).tz_convert(None).to_pydatetime() + (dt.datetime.now() - dt.datetime.utcnow()) if v else None
    for f in get_json("https://api.dx.ne-compass.com/wzdx-latest/").get("features", []):
        pr, cd = f.get("properties", {}), f.get("properties", {}).get("core_details", {})
        try:
            g = gpd.GeoSeries([shape(f["geometry"])], crs=4326).to_crs(CRS).iloc[0]
        except Exception:
            continue
        if not g.intersects(area):
            continue
        imp = str(pr.get("vehicle_impact") or "")
        if imp in ("all-lanes-open", "unknown", ""):
            continue
        add("New England Compass (VTrans)", ", ".join(cd.get("road_names") or []), "full closure" if imp == "all-lanes-closed" else "lane / one-way",
            cd.get("description"), iso(pr.get("start_date")), iso(pr.get("end_date")), line_of(g))
    print("New England Compass", len(rows) - n0)
if has("vdot_511"):
    n0 = len(rows)
    base = "https://data.511-atis-ttrip-prod.iteriscloud.com/datasets"
    for path in ("eventUnfiltered/active_construction.geojson", "incidentUnfiltered/major_incidents.geojson",
                 "incidentUnfiltered/minor_incidents.geojson", "incidentUnfiltered/weather_closures.geojson"):
        try:
            feats = get_json(f"{base}/{path}").get("features", [])
        except RuntimeError:
            print("  Virginia 511: no answer for", path)
            continue
        for f in feats:
            pr = f.get("properties", {})
            try:
                g = gpd.GeoSeries([shape(f["geometry"])], crs=4326).to_crs(CRS).iloc[0]
            except Exception:
                continue
            if not g.intersects(area):
                continue
            msg = str(pr.get("message_511") or pr.get("location_description") or "")
            full = bool(re.search(r"(?i)road (is )?closed|all (\w+ )?lanes (are )?closed|closed to (through )?traffic|is closed", msg)) \
                and not re.search(r"(?i)alternating", msg)
            sec = lambda v: dt.datetime.fromtimestamp(float(v)) if v not in (None, "") and pd.notna(v) and float(v) > 1e8 else None
            add("Virginia 511", pr.get("route"), "full closure" if full or "weather_closures" in path else "lane / one-way", msg,
                sec(pr.get("start")), sec(pr.get("end")), line_of(g), frm=pr.get("location_description"))
    print("Virginia 511", len(rows) - n0)
if has("blri_roads"):     # the Parkway's closures page: a table of milepost sections with Open / Closed / Ungated
    n0 = len(rows)
    try:
        html = requests.get("https://www.nps.gov/blri/planyourvisit/roadclosures.htm", headers=UA, timeout=120).text
        mp = {round(float(p.get("milepost")), 1): g for p, g in arc(
            "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/SEAC_BLRI_Mileposts/FeatureServer/2") if p.get("milepost") is not None}
        cell = lambda t: " ".join(re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ").replace("&amp;", "&").split())
        for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
            tds = [cell(t) for t in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)]
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)", tds[0]) if tds else None
            if not m or not any(re.search(r"(?i)\bclosed\b", t) for t in tds[1:]):
                continue
            a_, b_ = float(m.group(1)), float(m.group(2))
            near = lambda v: min(mp, key=lambda k: abs(k - v)) if mp else None
            ka, kb = near(a_), near(b_)
            if ka is None or abs(ka - a_) > 1.5 or abs(kb - b_) > 1.5 or ka == kb:
                continue                      # the section lies outside the area's mileposts
            add("Blue Ridge Parkway (NPS)", f"Blue Ridge Parkway, milepost {a_:g}–{b_:g}", "full closure", " · ".join(tds[1:]), None, None,
                route(mp[ka].coords[0], mp[kb].coords[0]), always=True)
    except requests.RequestException:
        print("  Blue Ridge Parkway: page not reachable")
    print("Blue Ridge Parkway", len(rows) - n0)

COLS = ["source", "road", "from_", "to", "severity", "work", "reason", "start", "end", "when", "long_term", "always", "geometry"]
cl = gpd.GeoDataFrame(rows, crs=CRS) if rows else gpd.GeoDataFrame({c: [] for c in COLS[:-1]}, geometry=[], crs=CRS)
for c_ in COLS:
    if c_ not in cl:
        cl[c_] = None
cl = cl.rename(columns={"from_": "from"})
cl["always"] = cl.always.fillna(False).astype(bool)

# Keep closures in mountain terrain: >= MIN_RELIEF m of elevation range within 1 km of the closure midpoint.
# This drops urban stretches (PCH in Marina del Rey, foothill freeways) that fall inside the study boxes.
MIN_RELIEF = 150
import rasterio
dems = [rasterio.open(f"{raw_dir(r)}/dem_10m.tif") for r in REGIONS]
def relief(pt):
    for d in dems:
        if d.bounds.left <= pt.x <= d.bounds.right and d.bounds.bottom <= pt.y <= d.bounds.top:
            r, c = d.index(pt.x, pt.y)
            w = d.read(1, window=((max(r - 100, 0), r + 100), (max(c - 100, 0), c + 100)))
            w = w[w > -1000]
            return float(w.max() - w.min()) if w.size else 0.0
    return 0.0
cl["relief_m"] = [relief(g.interpolate(0.5, normalized=True)) for g in cl.geometry]
cl = cl[(cl.relief_m >= MIN_RELIEF) | cl.always].copy()     # (park roads count wherever they are)

# Collapse repeat nights of the same Caltrans job into one line
cal = cl.source == "Caltrans"
if cal.any():
    key = ["source", "road", "from", "to", "work", "severity"]
    agg = cl[cal].sort_values("start").groupby(key, dropna=False).agg(
        reason=("reason", "first"), start=("start", "first"), end=("end", "last"), when=("when", "first"),
        long_term=("long_term", "max"), relief_m=("relief_m", "first"), geometry=("geometry", "first"),
        nights=("start", "size")).reset_index()
    agg["reason"] = agg.reason + np.where(agg.nights > 1, " · " + agg.nights.astype(str) + " scheduled windows", "")
    cl = pd.concat([gpd.GeoDataFrame(agg.drop(columns="nights"), crs=CRS), cl[~cal]], ignore_index=True)
cl = gpd.GeoDataFrame(cl.drop(columns=["work", "always"], errors="ignore"), crs=CRS)
cl["fetched"] = NOW.strftime("%Y-%m-%d %H:%M")
if len(cl):
    cl.to_crs(4326).to_file(f"{MAP_OUT}/road_closures.gpkg")
    cl.drop(columns="geometry").to_csv(f"{MAP_OUT}/road_closures.csv", index=False)
else:   # nothing closed (or no feed for this area): no layer, and the later steps run as without closures
    for f_ in ("road_closures.gpkg", "road_closures.csv"):
        if os.path.exists(f"{MAP_OUT}/{f_}"):
            os.remove(f"{MAP_OUT}/{f_}")

# ---- static: gated / no public vehicles (OSM) ----
gated = roads[roads.access.isin(["no", "private"]) | roads.motor_vehicle.isin(["no", "private"])]
gated = gated[gated.highway.isin(["track", "unclassified", "tertiary", "secondary", "service"])
              & (gated.length > 300) & gated.intersects(area)]
gated = gated[~gated.highway.eq("service") | gated.name.notna()]  # skip private driveways
gated.assign(name=gated.name.fillna("unnamed road"))[["name", "highway", "access", "motor_vehicle", "geometry"]] \
    .to_crs(4326).to_file(f"{MAP_OUT}/gated_roads.gpkg")

print(len(cl), "closures |", cl.groupby(["source", "severity"]).size().to_dict(), "| gated roads", len(gated))
if len(cl):
    print(cl[["source", "road", "from", "to", "severity", "when", "end", "reason"]].to_string(max_colwidth=40))
