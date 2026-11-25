"""The map of all areas: output/index.html. No AREA needed; run it after any area's 06_map.py.

Every built area's drainage outlines and main rivers (order 4 and up) and long trail on one map, over terrain shading and place labels, from the overview.json each
06_map.py writes. Pan and zoom across the country; a click inside an area opens that area's own map (2D, 3D or the
creek profiles) at the spot. The Open Graph tags in its head give links to it the
preview card, a screenshot of the site that 15_preview.py takes (output/preview.jpg, published next to it). The areas' own maps have a "Go to" menu that leads back here at the same view and
across to the other areas.

All six areas in one full-detail page would be over 200 MB (LA's alone is 67 MB), too heavy to open, on a phone
above all; so the detail stays in the per-area maps and this page ties them together.

It is also the web app's start page (2026-11-24): Leaflet comes from the site's lib/, and weblib.install() puts sw.js,
offline.js, the manifest, the icons and lib/ into output/, where publish_site.sh takes them from. With no connection it
shows the saved USGS topo, and the list marks the areas saved on the device.
"""
import json, os, datetime as dt
from config import AREAS, ROOT
import weblib

OUT = f"{ROOT}/output"
areas = []
for key in AREAS:
    if AREAS[key].get("hidden"):     # built and kept, but not shown (config.py: the Adirondack maps since 2026-11-20)
        continue
    p = f"{OUT}/{key}/overview.json"
    if os.path.exists(p) and os.path.exists(f"{OUT}/{key}/stream_map.html"):
        with open(p) as f:
            a = json.load(f)
        a["built"] = dt.datetime.fromtimestamp(os.path.getmtime(f"{OUT}/{key}/stream_map.html")).strftime("%Y-%m-%d")
        areas.append(a)
if not areas:
    raise SystemExit("no area has an overview.json yet: run 06_map.py for one first")
# the credits page beside this one, credits.html (credits.py: every source the maps use, its terms and the maps it
# covers); a download address or a waterfall guide with no entry there gets a NOTE in the log
import credits
credits.write(f"{OUT}/credits.html")

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Stream maps: all areas</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="Stream maps">
<meta property="og:title" content="Stream maps: trout water, waterfalls &amp; swimming holes">
<meta property="og:description" content="Every creek in __NAREAS__ mountain areas, scored for trout and mapped with its waterfalls, plunge pools and the way in.">
<meta property="og:url" content="https://alexanderswann.github.io/streams/">
<meta property="og:image" content="https://alexanderswann.github.io/streams/preview.jpg?v=__PREVIEW_V__">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="The LA mountains stream map: the San Gabriel River and its forks over terrain shading">
<meta name="twitter:card" content="summary_large_image">
<meta name="description" content="Every creek in __NAREAS__ mountain areas, scored for trout and mapped with its waterfalls, plunge pools and the way in.">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
__WEBAPP__<style>
  html, body, #map { height: 100%; margin: 0; }
  body { font: 13px/1.4 system-ui, -apple-system, sans-serif; color: #1d1d1f; }
  .panel { background: rgba(255,255,255,.96); border-radius: 10px; box-shadow: 0 1px 8px rgba(0,0,0,.25); padding: 10px 12px; max-width: 250px; }
  .panel h1 { font-size: 14px; margin: 0 0 6px; }
  .panel .a { display: block; width: 100%; text-align: left; border: 0; background: none; font: inherit; padding: 5px 4px; border-radius: 6px; cursor: pointer; color: inherit; }
  .panel .a:hover { background: #eef2f7; }
  .panel .a small { color: #6b7280; display: block; }
  .panel p { margin: 6px 0 0; color: #6b7280; font-size: 11.5px; }
  .alab { font: 700 13px system-ui, sans-serif; color: #0b3d91; text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff; white-space: nowrap; }
  .dlab { font: 600 10.5px system-ui, sans-serif; letter-spacing: .06em; text-transform: uppercase; white-space: nowrap;
          text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff; }
  #open { position: absolute; z-index: 1000; left: 50%; bottom: 26px; transform: translateX(-50%); display: none; background: #0b3d91; color: #fff;
          border-radius: 22px; padding: 9px 16px; font-weight: 600; box-shadow: 0 2px 10px rgba(0,0,0,.35); text-decoration: none; white-space: nowrap; }
  .leaflet-popup-content a { color: #1864ab; font-weight: 600; }
__PHONE_CSS__
</style></head>
<body><div id="map"></div><a id="open" href="#"></a>
<script>
const AREAS = __AREAS__;
const map = L.map("map", {zoomSnap: 0.5, preferCanvas: true});
map.attributionControl.addAttribution("<a href='credits.html'>Data sources</a>");   // first, so a phone's folded credits line shows it
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";
const gray = L.tileLayer(ESRI + "/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri, HERE, Garmin", maxZoom: 16}).addTo(map);
const topo = L.tileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}", {attribution: "USGS", maxZoom: 16});
const shade = L.tileLayer(ESRI + "/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri", maxZoom: 16, opacity: .45}).addTo(map);
const places = L.tileLayer(ESRI + "/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {attribution: "Esri", maxZoom: 16, pane: "shadowPane"}).addTo(map);
L.control.layers({"Light gray": gray, "USGS topo": topo}, {"Terrain shading": shade, "Place &amp; road labels": places}, {collapsed: true}).addTo(map);
L.control.scale({metric: false}).addTo(map);
map.attributionControl.addAttribution("Streams: USGS 3DEP &amp; NHD__SENTINEL__");
__PHONE_JS__
phoneControls(map);      // map_phone.js: one-line credits on phones, "my location" button
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
// imperial units for everything shown (units.py; the data stay metric: drainage in km²)
const SQMI = km2 => { if (km2 == null) return "?"; const v = km2 * 0.386102;
  return (v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 1 ? v.toFixed(1) : v.toFixed(2)) + " sq mi"; };
const inside = (a, ll) => ll.lat >= a.bounds[0][0] && ll.lat <= a.bounds[1][0] && ll.lng >= a.bounds[0][1] && ll.lng <= a.bounds[1][1];
const areaAt = ll => AREAS.find(a => inside(a, ll));
const link = (a, page, ll, z) => `${a.key}/${page}#${ll.lat.toFixed(5)},${ll.lng.toFixed(5)},${z}`;
const all = L.latLngBounds([]);
AREAS.forEach(a => all.extend(L.latLngBounds(a.bounds)));
// the view first, then the layers: taking a label off while the map is still starting up breaks its start
function go() {
  const h = location.hash.slice(1).split(",").map(Number);
  if (h.length >= 2 && h.every(v => !isNaN(v))) { map.setView([h[0], h[1]], h[2] || 9, {animate: false}); return true; }
  return false;
}
if (!go()) map.fitBounds(all, {padding: [30, 30]});
const dlabs = [];
AREAS.forEach(a => {
  const b = L.latLngBounds(a.bounds);
  L.rectangle(b, {color: "#0b3d91", weight: 1, dashArray: "4 4", fill: false, interactive: false}).addTo(map);
  L.geoJSON(a.basins, {style: f => ({color: f.properties.c, weight: 1, opacity: .7, fillColor: f.properties.c, fillOpacity: .13}),
    onEachFeature: (f, l) => l.bindTooltip(`<b>${esc(f.properties.drainage)}</b> · ${SQMI(f.properties.km2)}<br>${esc(a.label)}`, {sticky: true})}).addTo(map);
  L.geoJSON(a.streams, {style: f => ({color: f.properties.c, weight: Math.max(1, (f.properties.strahler - 3) * 1.1), opacity: .95}),
    onEachFeature: (f, l) => l.bindTooltip(`<b>${esc(f.properties.name || "Unnamed creek")}</b><br>${esc(f.properties.drainage)} · fish score ${f.properties.fish_score}`, {sticky: true})}).addTo(map);
  if (a.trail) {                                   // the area's long trail: a dark dashed line on a soft yellow band
    L.geoJSON(a.trail, {interactive: false, style: {color: "#ffd43b", weight: 6, opacity: .5, lineCap: "round"}}).addTo(map);
    L.geoJSON(a.trail, {style: {color: "#1d1d1f", weight: 1.2, dashArray: "6 5"},
      onEachFeature: (f, l) => l.bindTooltip(`<b>${esc(a.trail_name || "Long trail")}</b>` + (f.properties.label && f.properties.label !== a.trail_name ? `<br>${esc(f.properties.label)}` : ""), {sticky: true})}).addTo(map);
  }
  a.marker = L.marker(b.getCenter(), {interactive: true, icon: L.divIcon({className: "alab", html: esc(a.label), iconSize: [0, 0]})}).addTo(map)
    .on("click", () => map.flyToBounds(b, {padding: [20, 20], duration: .8}));
  L.circleMarker([a.home.lat, a.home.lon], {radius: 5, color: "#fff", weight: 2, fillColor: "#0b3d91", fillOpacity: 1}).addTo(map)
    .bindTooltip("Start: " + esc(a.home.label));
  a.drains.filter(d => d.lab && d.km2 >= 60).forEach(d => dlabs.push([d, L.marker(d.lab, {interactive: false,
    icon: L.divIcon({className: "dlab", html: `<span style="color:${d.color};filter:brightness(.72)">${esc(d.name)}</span>`, iconSize: [0, 0]})})]));
});
// drainage names from zoom 9 (bigger drainages first), area names until then
function labels() {
  const z = map.getZoom();
  dlabs.forEach(([d, m]) => { const want = z >= (d.km2 >= 400 ? 8.5 : d.km2 >= 150 ? 9.5 : 10.5); want ? m.addTo(map) : m.remove(); });
  AREAS.forEach(a => z < 9 ? a.marker.addTo(map) : a.marker.remove());
}
// the list of areas
const panel = L.control({position: "topleft"});
panel.onAdd = () => {
  const d = L.DomUtil.create("div", "panel");
  d.innerHTML = "<h1 style='cursor:pointer' title='Hide / show the list'>Stream maps <span style='float:right;color:#6b7280'>–</span></h1><div class='list'>" + AREAS.map((a, i) => `<button class="a" data-i="${i}"><b>${esc(a.label)}</b>` +
    `<small>${a.reaches.toLocaleString()} reaches · ${a.drains.length} drainages · built ${a.built}</small></button>`).join("") +
    `<button class="a" data-i="-1"><b>All areas</b></button><p>Click in an area to open its full map there. Scores rank creeks within an area; they aren't comparable between areas. <a href="credits.html">Where the data comes from</a></p></div>`;
  L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
  const list = d.querySelector(".list"), mark = d.querySelector("h1 span");
  const fold = hide => { list.style.display = hide ? "none" : ""; mark.textContent = hide ? "+" : "–"; };
  d.querySelector("h1").onclick = () => fold(list.style.display !== "none");
  if (window.innerWidth < 600) fold(true);          // a phone: start with just the title
  d.querySelectorAll(".a").forEach(bn => bn.onclick = () => { const i = +bn.dataset.i;
    map.flyToBounds(i < 0 ? all : L.latLngBounds(AREAS[i].bounds), {padding: [20, 20], duration: .9}); });
  return d;
};
panel.addTo(map);
// offline use (offline.js): saved areas marked in the list; with no connection the saved topo, no Esri layers
if (window.StreamsOffline) StreamsOffline.overview(map, AREAS, {topo, far: [gray, shade, places],
  buttons: [...document.querySelectorAll(".panel .a")]});
// a click inside an area: links to its full maps at that spot
map.on("click", e => {
  const a = areaAt(e.latlng);
  if (!a) return;
  const z = Math.max(12, Math.round(map.getZoom()));
  L.popup().setLatLng(e.latlng).setContent(`<b>${esc(a.label)}</b><br><a href="${link(a, "stream_map.html", e.latlng, z)}">Open the full map here</a>` +
    ` · <a href="${link(a, "stream_map_3d.html", e.latlng, z)},55">3D</a><br><a href="${a.key}/profiles.html">Creek profiles</a>`).openOn(map);
});
// zoomed in on an area: one button to its full map at this view
const open = document.getElementById("open");
function sync() {
  const c = map.getCenter(), z = map.getZoom(), a = areaAt(c);
  history.replaceState(null, "", `#${c.lat.toFixed(4)},${c.lng.toFixed(4)},${z}`);
  if (a && z >= 9.5) { open.style.display = "block"; open.textContent = `Open the full ${a.label} map here →`;
    open.href = link(a, "stream_map.html", c, Math.max(11, Math.round(z))); } else open.style.display = "none";
  labels();
}
map.on("moveend zoomend", sync);
window.addEventListener("hashchange", go);
sync();
</script></body></html>
"""
HTML = weblib.localize(HTML.replace("__WEBAPP__", weblib.head("")), "")      # Leaflet from lib/; the web app's tags
words = "one two three four five six seven eight nine ten eleven twelve".split()
html = HTML.replace("__AREAS__", json.dumps(areas, separators=(",", ":"))).replace(
    "__NAREAS__", words[len(areas) - 1] if len(areas) <= len(words) else str(len(areas))).replace(
    "__PREVIEW_V__", str(int(os.path.getmtime(f"{OUT}/preview.jpg"))) if os.path.exists(f"{OUT}/preview.jpg") else "0")   # a new picture, a new link: apps keep the old card otherwise
_page_file = lambda f_: open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f_)).read()
html = html.replace("__PHONE_CSS__", _page_file("map_phone.css")).replace("__PHONE_JS__", _page_file("map_phone.js"))
# the Copernicus credit (flowlib.SENTINEL_CREDIT) where an area shown here has the late_summer_green source
from flowlib import SENTINEL_CREDIT
html = html.replace("__SENTINEL__", " · " + SENTINEL_CREDIT if any("late_summer_green" in AREAS[a["key"]].get("sources", ())
                                                                  for a in areas) else "")
with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"{OUT}/index.html: {len(areas)} areas ({', '.join(a['key'] for a in areas)}), {len(html) / 1e6:.1f} MB")
weblib.localize(html, "")            # the check again on the page as written: no script or stylesheet from elsewhere
n_web = weblib.install(OUT)          # sw.js, offline.js, the manifest, the icons and lib/ beside it (only what changed)
if n_web:
    print(f"{OUT}: {n_web} web app files written (sw.js, offline.js, manifest, icons, lib/)")
