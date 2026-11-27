"""One file with every area in it, to send to a phone: output/stream_maps_all.html. No AREA needed; run it after
the areas' 06_map.py (it reads each area's overview.json, map3d_data.js and map3d_layers.js: the layers only the 3D map
draws, inline in stream_map_3d.html until 2026-11-25).

output/index.html (13_overview.py) is only a front page: it opens each area's own map from the folders beside it,
so sent to a phone by itself it has nothing behind its links. This file carries the detail inside it instead. It
opens as the same map of all areas; zoom into an area and that area's layers are unpacked from the file: every
stream reach with the popup of the full map (fish score and standing, summer flow, access, sun and water
temperature, trout records, notes). Like every map here it opens with streams, drainages, the long trail, terrain
shading and place labels only; drops and waterfalls, trailheads and parking, trails and dirt roads, gauges and road
closures, trout records, and lakes (where built: fish records, access, measured depths) each have a switch in the panel. Each area's data sits in the page as gzip (about a
fifth of its size) and is unpacked only when you go there, so the file is tens of MB instead of the 200+ MB of the
six full maps, and a phone holds one or two areas at a time.

Not in it, to keep it that size: the hillshade, fire perimeters, land-status and trout-water outlines, drainage
fork outlines, labels that bend along creeks and trails, the 3D view and the creek profiles. Those are in the
per-area maps. It needs a connection for the base map and the map library, as the other maps do.
"""
import base64, gzip, json, os, datetime as dt
from config import AREAS, ROOT

OUT = f"{ROOT}/output"
SITE = "https://alexanderswann.github.io/streams/"    # the website (publish_site.sh; 15_preview.py's SITE)
CORE = ["streams", "streams_lake", "drops", "falls", "parking", "gauges", "closures", "trout", "lakes", "lake_depth"]
EXTRA = ["trails", "roads"]


def pack(obj):
    return base64.b64encode(gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), 9)).decode()


areas, blobs, sizes = [], [], []
for key in AREAS:
    if AREAS[key].get("hidden"):     # built and kept, but not shown (config.py: the Adirondack maps since 2026-11-20)
        continue
    p, q = f"{OUT}/{key}/overview.json", f"{OUT}/{key}/map3d_data.js"
    if not (os.path.exists(p) and os.path.exists(q)):
        continue
    with open(p) as f:
        a = json.load(f)
    with open(q) as f:
        s = f.read()
    d = json.loads(s[s.index("{"):s.rindex("}") + 1])
    # the layers only the 3D map draws: map3d_layers.js (06_map.py, 2026-11-25); before, inline in the 3D page
    p3 = f"{OUT}/{key}/map3d_layers.js"
    if not os.path.exists(p3):
        p3 = f"{OUT}/{key}/stream_map_3d.html"
    if os.path.exists(p3):
        with open(p3) as f:
            h = f.read()
        mark = "Object.assign(window.MAP3D, "
        if mark in h:
            d.update(json.JSONDecoder().raw_decode(h, h.index(mark) + len(mark))[0])
    lbl = d.get("lbl") or {}
    a.update(built=dt.datetime.fromtimestamp(os.path.getmtime(q)).strftime("%Y-%m-%d"), long_trail=lbl.get("long_trail"),
             closures_fetched=d.get("closures_fetched"), credits=lbl.get("credits"), acc_asof=lbl.get("acc_asof"),
             **({"stale": lbl["stale"]} if lbl.get("stale") else {}))    # layers read from a saved copy (06_map.py)
    # the trout calendar's per-reach terrain horizon and time zone (cz, 06_map.py since 2026-11-24) stay out: this map
    # has no calendar (map_calendar.js is the area pages' only), and they would add about 1.5 MB packed over 8 maps; so
    # do the reaches' trout species (sp, 2026-11-25), which only the area pages' species filter reads (map_filter.js)
    for k_ in ("streams", "streams_lake"):
        for f_ in (d.get(k_) or {}).get("features", []):
            f_["properties"].pop("cz", None)
            f_["properties"].pop("sp", None)
    core, extra = pack({k: d.get(k) for k in CORE}), pack({k: d.get(k) for k in EXTRA})
    blobs.append(f'<script type="text/plain" id="core-{key}">{core}</script>\n<script type="text/plain" id="extra-{key}">{extra}</script>')
    sizes.append((key, len(core) / 1e6, len(extra) / 1e6))
    areas.append(a)
if not areas:
    raise SystemExit("no area has an overview.json and map3d_data.js yet: run 06_map.py for one first")

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Stream maps (all areas, one file)</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; }
  body { font: 13px/1.4 system-ui, -apple-system, sans-serif; color: #1d1d1f; }
  /* the panel fits in the map (fitPanel below): its header stays put and only the list under it scrolls, so the header
     can always fold it and every switch can be reached on a phone */
  .panel { background: rgba(255,255,255,.96); border-radius: 10px; box-shadow: 0 1px 8px rgba(0,0,0,.25); padding: 9px 11px; max-width: 250px;
           display: flex; flex-direction: column; }
  .panel h1 { font-size: 14px; margin: 0; cursor: pointer; flex: none; }
  .panel h1 span { float: right; color: #6b7280; padding-left: 14px; }
  .panel .list { margin-top: 6px; padding-top: 4px; border-top: 1px solid #e9ecef; overflow-y: auto; min-height: 0; }
  .panel .a { display: block; width: 100%; text-align: left; border: 0; background: none; font: inherit; padding: 6px 4px; border-radius: 6px; cursor: pointer; color: inherit; }
  .panel .a:active, .panel .a:hover { background: #eef2f7; }
  .panel .a small { color: #6b7280; display: block; }
  .seg { display: flex; margin: 8px 0 4px; border: 1px solid #c9ced6; border-radius: 7px; overflow: hidden; }
  .seg button { flex: 1; border: 0; background: #fff; font: inherit; padding: 6px 4px; cursor: pointer; }
  .seg button.on { background: #1f5fae; color: #fff; }
  .panel label { display: block; padding: 5px 2px; }
  .panel p { margin: 6px 0 0; color: #6b7280; font-size: 11.5px; }
  .ramp { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 4px 0 2px; }
  .ramp i { flex: 1; }
  .alab { font: 700 13px system-ui, sans-serif; color: #0b3d91; text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff; white-space: nowrap; }
  .dlab { font: 600 10.5px system-ui, sans-serif; letter-spacing: .06em; text-transform: uppercase; white-space: nowrap;
          text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff; }
  #toast { position: absolute; z-index: 1000; left: 50%; bottom: 26px; transform: translateX(-50%); display: none; background: #0b3d91; color: #fff;
           border-radius: 22px; padding: 9px 16px; font-weight: 600; box-shadow: 0 2px 10px rgba(0,0,0,.35); white-space: nowrap; max-width: 92vw; overflow: hidden; text-overflow: ellipsis; }
  .pp { font-size: 12.5px; max-width: 300px; }
  .pp table { border-collapse: collapse; margin-top: 5px; }
  .pp td { vertical-align: top; padding: 2px 0; }
  .pp td:first-child { color: #6b7280; padding-right: 9px; white-space: nowrap; }
  .pp .dw { color: #6b7280; } .pp .warn { color: #c92a2a; }
  .leaflet-popup-content { margin: 11px 13px; } .leaflet-popup-content a { color: #1864ab; }
__PHONE_CSS__
</style></head>
<body><div id="map"></div><div id="toast"></div>
__BLOBS__
<script>
const AREAS = __AREAS__;
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
// an area's layers that came from a saved copy when their download failed (06_map.py: lbl.stale), of those shown here
const PSTALE = new Set(["gauges", "road closures", "iNaturalist", "trout records"]);
const staleNote = a => { const s = (a.stale || []).filter(([n]) => PSTALE.has(n));
  const days = [...new Set(s.map(([, d]) => d))];        // (oldest first, as 06_map.py lists them)
  return s.length ? `<br><span style="color:#a61e4d">⚠ As of ${days.map(d => `${esc(d)}: ${s.filter(x => x[1] === d).map(x => esc(x[0])).join(", ")}`).join("; ")}</span>` : ""; };
// imperial units for everything shown (units.py; the data stay metric: drainage in km², elevation in m)
const SQMI = km2 => { if (km2 == null) return "?"; const v = km2 * 0.386102;
  return (v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 1 ? v.toFixed(1) : v.toFixed(2)) + " sq mi"; };
const canvas = L.canvas({tolerance: 9, padding: 0.3});            // a wide touch margin for thin lines under a finger
const map = L.map("map", {zoomSnap: 0.5, preferCanvas: true, renderer: canvas});
map.attributionControl.addAttribution("<a href='__SITE__credits.html'>Data sources</a>");   // the website's credits page, first in the line
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";
const gray = L.tileLayer(ESRI + "/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri, HERE, Garmin", maxZoom: 16}).addTo(map);
const topo = L.tileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}", {attribution: "USGS", maxZoom: 16});
const photo = L.tileLayer(ESRI + "/World_Imagery/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri, Maxar", maxZoom: 18});
const shade = L.tileLayer(ESRI + "/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri", maxZoom: 16, opacity: .45}).addTo(map);
const places = L.tileLayer(ESRI + "/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri", maxZoom: 16, pane: "shadowPane"}).addTo(map);
L.control.layers({"Light gray": gray, "USGS topo": topo, "Satellite": photo}, {"Terrain shading": shade, "Place &amp; road labels": places}, {collapsed: true}).addTo(map);
L.control.scale({metric: false}).addTo(map);
__PHONE_JS__
__SCORE_JS__
__SPECS_JS__
__LAYER_ORDER_JS__
// Links to a creek's profile (in the drop, known-fall and lake popups, from 06_map.py) open it on the website: this one
// file carries no profiles (each area's sits beside its maps there, as profiles.html)
const onSite = (html, a) => html == null ? html : String(html).replace(/href='profiles\.html#/g, `href='__SITE__${a.key}/profiles.html#`);
phoneControls(map);      // map_phone.js: one-line credits on phones, "my location" button
map.attributionControl.addAttribution("Streams: USGS 3DEP &amp; NHD · Trails © OpenStreetMap contributors · USFS · iNaturalist · PRISM Group, Oregon State University__SENTINEL__");

const all = L.latLngBounds([]);
AREAS.forEach(a => all.extend(L.latLngBounds(a.bounds)));
function go() {
  const h = location.hash.slice(1).split(",").map(Number);
  if (h.length >= 2 && h.every(v => !isNaN(v))) { map.setView([h[0], h[1]], h[2] || 9, {animate: false}); return true; }
  return false;
}
if (!go()) map.fitBounds(all, {padding: [30, 30]});     // the view first: layers are added to a map that has one

// ---- colours ----
let mode = "drainage", extras = false;
// What is on the map: streams, drainages, the long trail, terrain shading, place labels and lakes (since 2026-11-20).
// The rest waits for its switch in the panel.
const opt = {drops: false, access: false, live: false, trout: false, lakes: true};
const LOW = 15, LOWCOL = "#8d9aa8", RAMP = ["#3fb0a8", "#2a93c4", "#2a6fc0", "#3a4fb0", "#4b2f9c", "#3a1670"];
const ramp = fs => fs < LOW ? LOWCOL : RAMP[Math.min(RAMP.length - 1, Math.floor((fs - LOW) / (100 - LOW) * RAMP.length))];
const W = [0, 0.8, 1.15, 1.7, 2.4, 3.3, 4.4, 5.4];
const zf = () => Math.max(0.75, Math.min(1.7, 0.75 + (map.getZoom() - 10) * 0.19));
const sstyle = f => { const p = f.properties, low = mode === "fish" && p.fs < LOW;
  return {color: mode === "fish" ? ramp(p.fs) : p.c, weight: (W[p.o] || 1) * zf() * (low ? 0.7 : 1), opacity: low ? 0.55 : 0.95, lineCap: "round", lineJoin: "round"}; };
const BIKE = {yes: "#2f9e44", likely: "#94d82d", unlikely: "#f08c00", no: "#e03131", unknown: "#8c6d46"};
const ROAD = {paved: "#868e96", graded: "#b08968", high_clearance: "#9c6644", "4wd": "#7f4f24", bike: "#2f9e44", dirt: "#a68a64", closed: "#e03131"};
const ROADNAME = {paved: "paved", graded: "graded dirt (car when dry)", high_clearance: "rough dirt (high clearance)", "4wd": "very rough (4WD)",
                  bike: "closed to cars, open to bikes", dirt: "dirt, condition unknown", closed: "closed: fire closure"};

// ---- the stream popup of the full maps ----
function pop(p, a) {
  const where = p.d === p.k ? esc(p.d) : `${esc(p.k)} · ${esc(p.d)}`;
  return `<div class="pp"><b>${esc(p.n || "Unnamed creek")}</b><div class="dw">${where} · ${esc(a.label)}</div>` +
    `<table>${streamSpecs.row(p, {like: false})}` +   // map_specs.js: flow, velocity, slope, order, drainage, lower end
    fsRow(p) +                      // map_score.js: the score, and its breakdown on hover or tap
    `<tr><td>${p.dq ? "Summer flow" : "NHD flow"}</td><td>${esc(p.dq || String(p.fl || "").replace(/^NHD /, ""))}</td></tr>` +
    `<tr><td>Access</td><td>${esc(p.acc)}${a.acc_asof ? `<div class="dw">${esc(a.acc_asof)}</div>` : ""}</td></tr>` +
    (p.sun ? `<tr><td>Sun</td><td>${esc(p.sun)}</td></tr>` : "") +
    (p.tr ? `<tr><td>Trout</td><td>${esc(p.tr)}</td></tr>` : "") +
    (p.ht ? `<tr><td>Heat</td><td class="warn">${esc(p.ht)}</td></tr>` : "") +
    (p.burn ? `<tr><td>Fire</td><td class="warn">${esc(p.burn)}</td></tr>` : "") +
    (p.flags ? `<tr><td>Notes</td><td>${esc(p.flags)}</td></tr>` : "") +
    `</table><a href="https://www.google.com/maps/search/?api=1&query=${p.y},${p.x}" target="_blank">Open this spot in Google Maps ↗</a></div>`;
}

// ---- the map of all areas (always there) ----
const dlabs = [];
AREAS.forEach(a => {
  const b = L.latLngBounds(a.bounds);
  a.b = b;
  a.streams_ov = a.streams; a.streams = null;        // (the main rivers; the full network, once unpacked, is a.net)
  L.rectangle(b, {color: "#0b3d91", weight: 1, dashArray: "4 4", fill: false, interactive: false}).addTo(map);
  a.basins = L.geoJSON(a.basins, {interactive: false, style: f => ({color: f.properties.c, weight: 1, opacity: .6, fillColor: f.properties.c, fillOpacity: .12})}).addTo(map);
  a.main = L.geoJSON(a.streams_ov, {style: f => ({color: f.properties.c, weight: Math.max(1, (f.properties.strahler - 3) * 1.1), opacity: .95}),
    onEachFeature: (f, l) => l.bindTooltip(`<b>${esc(f.properties.name || "Unnamed creek")}</b><br>${esc(f.properties.drainage)} · fish score ${f.properties.fish_score}`, {sticky: true})}).addTo(map);
  if (a.trail) {                                   // the area's long trail: a dark dashed line on a soft yellow band
    L.geoJSON(a.trail, {interactive: false, style: {color: "#ffd43b", weight: 6, opacity: .5, lineCap: "round"}}).addTo(map);
    L.geoJSON(a.trail, {style: {color: "#1d1d1f", weight: 1.2, dashArray: "6 5"},
      onEachFeature: (f, l) => l.bindTooltip(`<b>${esc(a.trail_name || "Long trail")}</b>` + (f.properties.label && f.properties.label !== a.trail_name ? `<br>${esc(f.properties.label)}` : ""), {sticky: true})}).addTo(map);
  }
  a.marker = L.marker(b.getCenter(), {icon: L.divIcon({className: "alab", html: esc(a.label), iconSize: [0, 0]})})
    .on("click", () => map.flyToBounds(b, {padding: [20, 20], duration: .8}));
  L.circleMarker([a.home.lat, a.home.lon], {radius: 5, color: "#fff", weight: 2, fillColor: "#0b3d91", fillOpacity: 1}).addTo(map)
    .bindTooltip("Start: " + esc(a.home.label));
  a.drains.filter(d => d.lab && d.km2 >= 60).forEach(d => dlabs.push([d, L.marker(d.lab, {interactive: false,
    icon: L.divIcon({className: "dlab", html: `<span style="color:${d.color};filter:brightness(.72)">${esc(d.name)}</span>`, iconSize: [0, 0]})})]));
  a.state = "";                                    // "" not loaded, "loading", "on"
  a.groups = {};                                   // layer groups by the zoom they appear at
});
const show = (layer, want) => { if (want && !map.hasLayer(layer)) layer.addTo(map); else if (!want && map.hasLayer(layer)) map.removeLayer(layer); };

// ---- unpacking an area from the page ----
const toast = document.getElementById("toast");
let toasts = 0;
const say = t => { toast.textContent = t; toast.style.display = t ? "block" : "none"; };
function script(src) { return new Promise((ok, no) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); }); }
async function unpack(id) {
  const b64 = document.getElementById(id).textContent, bin = atob(b64), n = bin.length, bytes = new Uint8Array(n);
  for (let i = 0; i < n; i++) bytes[i] = bin.charCodeAt(i);
  let text;
  if (window.DecompressionStream) text = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  else { if (!window.pako) await script("https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako_inflate.min.js");   // older phones
         text = pako.ungzip(bytes, {to: "string"}); }
  return JSON.parse(text);
}
const pt = (c, o) => (f, ll) => L.circleMarker(ll, Object.assign({renderer: canvas, radius: 5, color: "#fff", weight: 1.5, fillColor: c(f), fillOpacity: 1}, o || {}));
async function load(a) {
  if (a.state) return;
  a.state = "loading"; toasts++; say(`Unpacking ${a.label}…`);
  await new Promise(r => setTimeout(r, 30));       // let the message draw first
  try {
    const d = await unpack("core-" + a.key), g = a.groups;
    a.net = L.geoJSON(d.streams, {style: sstyle, onEachFeature: (f, l) => l.bindPopup(() => pop(f.properties, a), {maxWidth: 320})});
    g.net = [L.layerGroup([a.net]), 10, null];      // [layers, the zoom they appear at, their switch]
    // the reaches lying in a lake (06_map.py): only while Lakes is off ("!lakes"), then like the other streams
    a.netl = d.streams_lake && d.streams_lake.features.length ? L.geoJSON(d.streams_lake, {style: sstyle,
      onEachFeature: (f, l) => l.bindPopup(() => pop(f.properties, a), {maxWidth: 320})}) : null;
    if (a.netl) g.netl = [L.layerGroup([a.netl]), 10, "!lakes"];
    const lines = [];
    if (d.closures) lines.push(L.geoJSON(d.closures, {style: f => ({color: /^full/.test(f.properties.severity) ? "#e03131" : "#f08c00", weight: 5, opacity: .85}),
      onEachFeature: (f, l) => { const p = f.properties; l.bindPopup(`<div class="pp"><b>${esc(p.road)}</b> · <span class="warn">${esc(p.severity)}</span><br>` +
        `${esc(p.reason || "")}<br><span class="dw">${esc(p.when || "")}${p.end ? " · until " + esc(p.end) : ""} · fetched ${esc(a.closures_fetched || "")}` +
        `${p.times ? "<br>Approach times: " + esc(p.times) : ""}</span></div>`); }}));
    if (d.gauges) lines.push(L.geoJSON(d.gauges, {pointToLayer: pt(f => f.properties.c || "#1c7ed6", {radius: 6}), onEachFeature: (f, l) => l.bindPopup(`<div class="pp">${f.properties.html}</div>`)}));
    g.live = [L.layerGroup(lines), 10.5, "live"];
    g.falls = [L.layerGroup(d.falls ? [L.geoJSON(d.falls, {pointToLayer: pt(() => "#0b3d91", {radius: 5.5}),
      onEachFeature: (f, l) => l.bindPopup(f.properties.html ? `<div class="pp">${onSite(f.properties.html, a)}</div>` :
        `<div class="pp"><b>${esc(f.properties.name || "Waterfall")}</b> (mapped, ${esc(f.properties.src || "")})` +
        (f.properties.note ? `<br>${esc(f.properties.note)}` : "") + "</div>")})] : []), 11, "drops"];
    const pts = [], acc = [];
    if (d.drops) pts.push(L.geoJSON(d.drops, {pointToLayer: pt(f => f.properties.c || "#e87ba4", {radius: 4.5}), onEachFeature: (f, l) => l.bindPopup(`<div class="pp">${onSite(f.properties.html, a)}</div>`)}));
    if (d.parking) acc.push(L.geoJSON(d.parking, {pointToLayer: pt(f => f.properties.k === "trailhead" ? "#2b8a3e" : f.properties.k === "access" ? "#0c8599" : "#1c7ed6", {radius: 4.5}),
      onEachFeature: (f, l) => { const p = f.properties, ac = p.k === "access";
        l.bindPopup(`<div class="pp"><b>${esc(p.n || (p.k === "trailhead" ? "Trailhead" : ac ? p.t || "Fishing access" : "Parking"))}</b> · ${esc(ac ? (p.t || "fishing access") + (p.w ? ", " + p.w : "") : p.k)}` +
        (p.no ? `<br>${esc(p.no)}` : "") + (ac ? `<br>Official access: ${esc(p.src)}` : "") +
        (p.u ? `<br><a href="${esc(p.u)}" target="_blank">${ac ? esc(String(p.src).split(", ")[0]) : "Forest Service"} page ↗</a>` : "") + "</div>"); }}));
    g.drops = [L.layerGroup(pts), 12, "drops"];
    g.access = [L.layerGroup(acc), 12, "access"];
    // lakes (05d_lakes.py, where built) under the streams on the one canvas; measured depth contours over them
    const lk = [];
    if (d.lakes) lk.push(L.geoJSON(d.lakes, {renderer: canvas, style: f => ({color: f.properties.e, weight: 1.2, fillColor: f.properties.c,
        fillOpacity: .55, dashArray: f.properties.dry ? "4 3" : null}),
      onEachFeature: (f, l) => { l.bindPopup(onSite(f.properties.html, a), {maxWidth: 340}); l.bindTooltip(esc(f.properties.tip), {sticky: true}); }}));
    if (d.lake_depth) lk.push(L.geoJSON(d.lake_depth, {renderer: canvas, style: f => ({color: "#1864ab", weight: f.properties.depth_m % 10 ? .8 : 1.6, opacity: .85}),
      onEachFeature: (f, l) => l.bindTooltip(esc(f.properties.tip), {sticky: true})}));
    if (lk.length) g.lakes = [L.layerGroup(lk).on("add", () => lk[0].bringToBack()), 10, "lakes"];
    a.trout = d.trout ? L.geoJSON(d.trout, {pointToLayer: pt(f => f.properties.c || "#2b8a3e", {radius: 4.5}), onEachFeature: (f, l) => l.bindPopup(`<div class="pp">${f.properties.html}</div>`)}) : null;
    a.state = "on";
    a.used = Date.now();
    map.removeLayer(a.main);                        // the full network replaces the main rivers
    a.basins.setStyle({fillOpacity: .05});
    // a phone holds two areas comfortably: the one not looked at longest goes back to its outline
    const on = AREAS.filter(x => x.state === "on").sort((x, y) => x.used - y.used);
    if (on.length > 2) unload(on[0]);
    if (extras) await loadExtra(a);
  } catch (e) { a.state = ""; say(`Couldn't unpack ${a.label}: ${e.message}`); await new Promise(r => setTimeout(r, 4000)); }
  if (--toasts <= 0) { toasts = 0; say(""); }
  place();
}
async function loadExtra(a) {
  if (a.state !== "on" || a.extra) return;
  a.extra = "loading"; say(`Unpacking ${a.label} trails and roads…`);
  await new Promise(r => setTimeout(r, 30));
  const d = await unpack("extra-" + a.key);
  const roads = L.geoJSON(d.roads, {filter: f => f.properties.c !== "paved", style: f => ({color: ROAD[f.properties.c] || "#a68a64", weight: 2.2, opacity: .9}),
    onEachFeature: (f, l) => { const p = f.properties; l.bindPopup(`<div class="pp"><b>${esc(p.n || "Unnamed road")}</b><br>${esc(ROADNAME[p.c] || p.c)}` +
      (p.sf ? ` · ${esc(p.sf)}` : "") + (p.fs ? `<br>USFS road ${esc(p.fs)}` : "") + (p.cw ? `<br><span class="warn">${esc(p.cw)}</span>` : "") + "</div>"); }});
  const trails = L.geoJSON(d.trails, {style: f => ({color: BIKE[f.properties.b] || "#8c6d46", weight: f.properties.k === "fire road" ? 2 : 1.6, opacity: .9,
      dashArray: f.properties.k === "fire road" ? "9 5" : "4 4"}),
    onEachFeature: (f, l) => { const p = f.properties; l.bindPopup(`<div class="pp"><b>${esc(p.n || (p.k === "fire road" ? "Unnamed fire road" : "Unnamed trail"))}</b> · ${esc(p.k)}` +
      (p.rt ? `<br>${esc(p.rt)}` : "") + `<br>Mountain bikes: <b>${esc(p.b)}</b> (${esc(p.bw || "")})` + (p.of ? `<br>${esc(p.of)}${p.no ? " trail " + esc(p.no) : ""}` : "") +
      (p.cw ? `<br><span class="warn">${esc(p.cw)}</span>` : "") + "</div>"); }});
  a.groups.trails = [L.layerGroup([roads, trails]), 11.5, null];
  a.extra = "on"; say(""); place();
}
function unload(a) {
  Object.values(a.groups).forEach(g => map.removeLayer(g[0]));
  if (a.trout) map.removeLayer(a.trout);
  a.groups = {}; a.net = a.netl = a.trout = null; a.extra = ""; a.state = "";
  a.main.addTo(map); a.basins.setStyle({fillOpacity: .12});
}
// what shows at this zoom, and which areas to unpack
function place() {
  const z = map.getZoom(), view = map.getBounds();
  dlabs.forEach(([d, m]) => show(m, z >= (d.km2 >= 400 ? 8.5 : d.km2 >= 150 ? 9.5 : 10.5)));
  AREAS.forEach(a => {
    show(a.marker, z < 9);
    const here = view.intersects(a.b);
    if (here && z >= 10 && !a.state) load(a);
    if (a.state === "on") {
      if (here) a.used = Date.now();
      Object.values(a.groups).forEach(([g, zmin, sw]) => show(g, z >= zmin && (!sw || (sw[0] === "!" ? !opt[sw.slice(1)] : opt[sw]))));
      if (a.trout) show(a.trout, opt.trout && z >= 11);
    }
  });
}
map.on("zoomend", () => AREAS.forEach(a => { if (a.net) a.net.setStyle(sstyle); if (a.netl) a.netl.setStyle(sstyle); }));

// ---- the panel ----
const panel = L.control({position: "topleft"});
panel.onAdd = () => {
  const d = L.DomUtil.create("div", "panel");
  d.innerHTML = "<h1>Stream maps <span>–</span></h1><div class='list'>" + AREAS.map((a, i) => `<button class="a" data-i="${i}"><b>${esc(a.label)}</b>` +
    `<small>${a.reaches.toLocaleString()} reaches · ${a.drains.length} drainages · built ${a.built}${staleNote(a)}</small></button>`).join("") +
    `<button class="a" data-i="-1"><b>All areas</b></button>` +
    `<div class="seg"><button data-m="drainage" class="on">Drainage</button><button data-m="fish">Fish score</button></div>` +
    `<div class="key"></div>` +
    `<div class="sw"><label data-k="falls"><input type="checkbox" data-o="drops"> Drops and waterfalls</label><label data-k="poi-pk"><input type="checkbox" data-o="access"> Trailheads, parking and fishing access</label>` +
    `<label data-k="road-graded"><input type="checkbox" id="xt"> Trails and dirt roads</label><label data-k="gauges"><input type="checkbox" data-o="live"> Gauges and road closures</label>` +
    `<label data-k="trout"><input type="checkbox" data-o="trout"> Trout records</label><label data-k="lakes"><input type="checkbox" data-o="lakes" checked> Lakes: fish, access, depth</label></div>` +
    `<p>Zoom into an area for every creek, and tap one for its details. The switches above add the rest once you are zoomed in. Scores rank creeks within an area; they aren't comparable between areas.</p></div>`;
  L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
  // the switches in the order of layer_order.js, as on the area maps: each by the key of its first layer there
  const sw = d.querySelector(".sw");
  [...sw.children].sort((x, y) => layerRank(x.dataset.k) - layerRank(y.dataset.k)).forEach(el => sw.appendChild(el));
  const list = d.querySelector(".list"), mark = d.querySelector("h1 span"), key = d.querySelector(".key");
  const fold = hide => { list.style.display = hide ? "none" : ""; mark.textContent = hide ? "+" : "–"; };
  d.querySelector("h1").onclick = () => fold(list.style.display !== "none");
  if (window.innerWidth < 600) fold(true);
  d.querySelectorAll(".a").forEach(bn => bn.onclick = () => { const i = +bn.dataset.i;
    map.flyToBounds(i < 0 ? all : AREAS[i].b, {padding: [20, 20], duration: .9}); if (window.innerWidth < 600) fold(true); });
  const setKey = () => key.innerHTML = mode === "fish"
    ? `<div class="ramp"><i style="background:${LOWCOL};flex:.9"></i>${RAMP.map(c => `<i style="background:${c}"></i>`).join("")}</div><small style="color:#6b7280">fish score: under ${LOW} grey, then low → high</small>`
    : `<small style="color:#6b7280">one colour per drainage; line width = stream order</small>`;
  d.querySelectorAll(".seg button").forEach(bn => bn.onclick = () => { mode = bn.dataset.m;
    d.querySelectorAll(".seg button").forEach(x => x.classList.toggle("on", x === bn)); setKey();
    AREAS.forEach(a => { if (a.net) a.net.setStyle(sstyle); if (a.netl) a.netl.setStyle(sstyle); }); });
  setKey();
  d.querySelector("#xt").onchange = async e => { extras = e.target.checked;
    for (const a of AREAS) { if (extras) await loadExtra(a); else if (a.groups.trails) { map.removeLayer(a.groups.trails[0]); delete a.groups.trails; a.extra = ""; } }
    place(); };
  d.querySelectorAll("input[data-o]").forEach(cb => cb.onchange = () => { opt[cb.dataset.o] = cb.checked; place(); });
  return d;
};
panel.addTo(map);
// as tall as the map leaves room for under the buttons above it and over the scale bar (less its own padding)
const fitPanel = () => { const d = panel.getContainer(); d.style.maxHeight = Math.max(120, map.getSize().y - d.offsetTop - 74) + "px"; };
map.on("resize", fitPanel);
fitPanel();
function sync() { const c = map.getCenter(); history.replaceState(null, "", `#${c.lat.toFixed(4)},${c.lng.toFixed(4)},${map.getZoom()}`); place(); }
map.on("moveend zoomend", sync);
window.addEventListener("hashchange", go);
sync();
</script></body></html>
"""
_page_file = lambda f_: open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f_)).read()
html = HTML.replace("__PHONE_CSS__", _page_file("map_phone.css")).replace("__PHONE_JS__", _page_file("map_phone.js"))
html = html.replace("__SCORE_JS__", _page_file("map_score.js"))      # the fish score's breakdown in the popups
html = html.replace("__SPECS_JS__", _page_file("map_specs.js"))      # the specs line in the popups (no "Similar streams")
html = html.replace("__LAYER_ORDER_JS__", _page_file("layer_order.js")).replace("__SITE__", SITE)   # the switches' order
# the Copernicus credit (flowlib.SENTINEL_CREDIT) where an area in the file has the late_summer_green source
from flowlib import SENTINEL_CREDIT
html = html.replace("__SENTINEL__", " · " + SENTINEL_CREDIT if any("late_summer_green" in AREAS[a["key"]].get("sources", ())
                                                                  for a in areas) else "")
html = html.replace("__AREAS__", json.dumps(areas, separators=(",", ":"))).replace("__BLOBS__", "\n".join(blobs))
path = f"{OUT}/stream_maps_all.html"
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"{path}: {len(areas)} areas, {len(html) / 1e6:.1f} MB")
print("  packed MB (streams and points / trails and roads): " + ", ".join(f"{k} {c:.1f} / {e:.1f}" for k, c, e in sizes))
