// The stream maps' service worker (the user, 2026-11-24: "what would it take to make a version of this fully
// downloadable to mobile so it can be used when in the backcountry with no connection"). Its scope is the site's root
// (https://alexanderswann.github.io/streams/). It stores nothing by itself: a page's "Save for offline" (offline.js) puts
// an area's files, the shared libraries and USGS topo / terrain tiles into the caches below, and this worker answers
// from them:
//  - an area's files (<area>/...) and the libraries (lib/..., icons/...): the saved copy where there is one. The saved
//    pages, data and libraries are one set, kept as saved until the user updates them (the layer panel says when the
//    site has changed); unsaved files come from the network as before;
//  - the few files at the root (index.html, offline.js, the manifest): from the network when it answers within 3 s (the
//    saved copy refreshed with it), else the saved copy, so the map of all areas and the offline code stay current;
//  - USGS topo and AWS terrain tiles: the saved tile where there is one, else the network;
//  - anything else (Esri and OpenTopoMap tiles, other sites) is not touched: their terms don't allow keeping tiles.
// With no network and no saved copy, a page of the site gets a short page that lists the saved areas.
// A request with "offline-save" in its query goes to the network whatever is saved (offline.js, saving or updating),
// and so do the offline.json lists (the areas' and the root's: compared with the saved copy's) and this file.
// Replacing it (README, "Offline, as an app"): any change to this file reaches every phone at its next page load with
// a connection (offline.js registers it with updateViaCache "none", so the browser asks the site for it each time, past
// its HTTP cache), and skipWaiting / clients.claim below put the new worker in charge at once, open pages included.
// web/sw-passthrough.js, published in its place, is the kill switch: a worker that answers nothing.
const VERSION = "2026-11-24";   // shown on the no-connection page; change it to send this file out again as it is
const FILES = "streams-files-v1", TILES = "streams-tiles-v1", META = "streams-meta-v1";
const ROOT = new URL("./", self.location).href;
const TILE = /^https:\/\/(basemap\.nationalmap\.gov\/arcgis\/rest\/services\/USGSTopo\/MapServer\/tile\/|s3\.amazonaws\.com\/elevation-tiles-prod\/terrarium\/)/;
let offline = false;   // a page found no network (offline.js): a tile that isn't saved gets a short try, not a long wait
let test = false;      // the offline test (?offline-test in a page's address, offline.js): no network for this site
const readTest = () => caches.open(META).then(c => c.match(ROOT + "offline-meta/test")).then(r => (test = !!r), () => test);
const ready = readTest();
// before failing a request for the test, the switch is read again: the page turns it off in the cache first, and its
// message can come after its next request
const offTest = req => readTest().then(t => t ? Response.error() : fetch(req));

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("message", e => {
  const d = e.data || {};
  if ("offline" in d) offline = !!d.offline;
  if ("test" in d) test = !!d.test;
});

self.addEventListener("fetch", e => {
  const req = e.request, url = req.url;
  if (req.method !== "GET") return;
  if (url.startsWith(ROOT)) {
    const u = new URL(url);
    if (u.search.includes("offline-save") || u.pathname.endsWith("/offline.json") || url === ROOT + "sw.js") {
      if (test) e.respondWith(offTest(req));
      return;
    }
    e.respondWith(siteFile(req, u));
  } else if (TILE.test(url)) e.respondWith(tile(req));
  else if (test) e.respondWith(offTest(req));
});

const within = (p, ms) => new Promise((ok, no) => { const t = setTimeout(() => no(new Error("timeout")), ms);
  p.then(v => { clearTimeout(t); ok(v); }, err => { clearTimeout(t); no(err); }); });

async function siteFile(req, u) {
  await ready;
  const key = u.origin + u.pathname + (u.pathname.endsWith("/") ? "index.html" : "");
  const saved = await caches.match(key, {cacheName: FILES, ignoreVary: true});
  const top = !key.slice(ROOT.length).includes("/");
  if (saved && !top) return saved;
  if (test && await readTest()) return saved || fallback(req);
  try {
    if (!saved) return await fetch(req);
    const net = await within(fetch(req), 3000), tag = net.headers.get("etag");
    if (net.ok && net.type === "basic" && !net.redirected && !(tag && tag === saved.headers.get("etag"))) {
      const body = await net.clone().blob(), h = new Headers(net.headers);
      h.delete("x-offline-hash");
      (await caches.open(FILES)).put(key, new Response(body, {status: 200, headers: h})).catch(() => {});
    }
    return net;
  } catch (err) {
    return saved || fallback(req);
  }
}

async function tile(req) {
  await ready;
  const hit = await caches.match(req.url, {cacheName: TILES, ignoreVary: true});
  if (hit) return hit;
  if (test && await readTest()) return Response.error();
  return offline ? within(fetch(req), 2500) : fetch(req);
}

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

async function fallback(req) {
  if (req.mode !== "navigate") return Response.error();
  const m = await caches.open(META), areas = [];
  for (const k of await m.keys()) {
    if (!k.url.startsWith(ROOT + "offline-meta/area/")) continue;
    try { areas.push(await (await m.match(k)).json()); } catch (e) { /* a record being written */ }
  }
  areas.sort((a, b) => String(a.label).localeCompare(String(b.label)));
  const day = s => new Date(s).toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric"});
  const list = areas.length ? "<p>Saved on this phone:</p><ul>" + areas.map(a =>
    `<li><a href="${ROOT}${esc(a.area)}/stream_map.html">${esc(a.label || a.area)}</a> · <a href="${ROOT}${esc(a.area)}/stream_map_3d.html">3D</a>` +
    ` · <a href="${ROOT}${esc(a.area)}/profiles.html">profiles</a> <small>(saved ${esc(day(a.saved))})</small></li>`).join("") + "</ul>"
    : "<p>No area is saved on this phone yet. With a connection, open an area's map, then the layer list " +
      "(the stack button at the top right) and <b>Save for offline</b>.</p>";
  return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" ` +
    `content="width=device-width, initial-scale=1"><title>Offline · Stream maps</title><style>body{font:15px/1.5 ` +
    `system-ui,-apple-system,sans-serif;margin:0;padding:24px 18px;color:#1d1d1f}h1{font-size:19px;margin:0 0 8px}` +
    `a{color:#1864ab;font-weight:600}li{margin:8px 0}small{color:#6b7280}</style></head><body><h1>No connection</h1>` +
    `<p>This page isn't saved for offline use.</p>${list}<p><a href="${ROOT}">Map of all areas</a></p>` +
    `<p><small>web app ${VERSION}</small></p></body></html>`,
    {status: 200, headers: {"Content-Type": "text/html; charset=utf-8"}});
}
