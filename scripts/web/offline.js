// The stream maps without a connection (the user, 2026-11-24: "what would it take to make a version of this fully
// downloadable to mobile so it can be used when in the backcountry with no connection"). Every page of the site loads
// this file from the site's root (06_map.py, 13_overview.py, profiles.html); sw.js, beside it, answers from what it
// saves. It
//  - registers the service worker (sw.js) and the web app (manifest.webmanifest: Add to Home Screen);
//  - adds "Offline use" to an area map's layer panel (2D and 3D): Save this area (both maps, their data, the creek
//    profiles, the terrain shading and the libraries the pages use; the size first, a progress bar while saving, then
//    "saved on <date>", and "update available" once the site's copy differs: each area's offline.json, written at
//    publish (weblib.py), lists its files with a hash, and its version is a hash of them all); and the USGS topo base map
//    for the whole area to zoom 13 or lower, or for the view on the screen to zoom 16, with the AWS terrain tiles the 3D
//    map needs at a low zoom (the sizes shown first; whole areas at zoom 15 or more are not offered: about 150 MB for
//    NE Connecticut and 1.4 GB for LA). USGS topo is public domain; Esri's and OpenTopoMap's tiles are never kept, as
//    their terms don't allow it;
//  - with no connection (the browser says so, or a quick request to Esri's tile server fails), switches the maps to the
//    saved topo with our own terrain shading, greys out the Esri and OpenTopoMap layers until the connection is back, and
//    shows a coarser saved tile, enlarged, where the zoom on the screen isn't saved;
//  - in the Home Screen app, opens the site's own links in the app (a link that opens a new tab would leave it).
// The "my location" button (map_phone.js; MapLibre's on the 3D map) reads the phone's GPS and needs no network.
// ?offline-test in a page's address (until ?offline-test=0) makes the site behave as with no connection, for tests on a
// computer: the worker answers only from what is saved.
(function () {
  "use strict";
  if (window.StreamsOffline) return;
  const ME = document.currentScript && document.currentScript.src;
  const ROOT = ME ? ME.replace(/offline\.js([?#].*)?$/, "") : new URL("../", location.href).href;
  const FILES = "streams-files-v1", TILES = "streams-tiles-v1", META = "streams-meta-v1", STAGE = "streams-stage-v1";
  const HTTP = /^https?:$/.test(location.protocol);
  const CAN = HTTP && "serviceWorker" in navigator && "caches" in window && !!(window.crypto && crypto.subtle);
  const TOPO = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}";
  const DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
  const PROBE = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/0/0/0";
  // average bytes per tile by zoom, from 330 USGS topo and 160 terrain tiles sampled over six areas (2026-11-24)
  const TOPO_B = {6: 27e3, 7: 32e3, 8: 31e3, 9: 35e3, 10: 31e3, 11: 33e3, 12: 26e3, 13: 24e3, 14: 22.4e3, 15: 21.2e3, 16: 13.2e3};
  const DEM_B = {6: 75e3, 7: 83e3, 8: 84e3, 9: 64e3, 10: 52e3, 11: 128e3, 12: 112e3};
  const AREA_Z = [10, 11, 12, 13], VIEW_Z = [13, 14, 15, 16];   // the zooms offered (whole area; the view on the screen)
  const AREA_DEM = 10, VIEW_DEM = 12;                            // terrain kept with them (3D map)
  const MAX_TILES = 12000;                                       // one save at most (about 250 MB at zoom 16)
  const areaKey = (() => { const p = location.href.startsWith(ROOT) ? location.href.slice(ROOT.length).split(/[?#]/)[0] : "";
    return p.includes("/") ? p.split("/")[0] : null; })();
  const iOS = /iP(hone|od|ad)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = navigator.standalone === true || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const MB = b => b == null ? "?" : b >= 995e6 ? (b / 1e9).toFixed(2) + " GB" : b >= 9.95e6 ? Math.round(b / 1e6) + " MB"
    : b >= 0.1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1e3)) + " KB";
  const day = s => new Date(s).toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric"});
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ---- the worker, the test switch ----
  const q = new URLSearchParams(location.search);
  let TEST = false;
  const toWorker = msg => { if (CAN && navigator.serviceWorker.controller) navigator.serviceWorker.controller.postMessage(msg); };
  let testRead = Promise.resolve();
  if (CAN) {
    // updateViaCache "none": the browser asks the site for sw.js at every check, never its HTTP cache, so a fixed or
    // kill-switch sw.js (sw.js's head) reaches the phone at its next page load with a connection
    navigator.serviceWorker.register(ROOT + "sw.js", {scope: ROOT, updateViaCache: "none"}).catch(() => {});
    const t = q.get("offline-test");
    testRead = (t != null ? setTest(t !== "0") : caches.open(META).then(c => c.match(ROOT + "offline-meta/test")).then(r => { TEST = !!r; }))
      .catch(() => {});
    navigator.serviceWorker.addEventListener("controllerchange", () => toWorker({test: TEST, offline: !net.on}));
  }
  async function setTest(on) {
    TEST = on;
    const c = await caches.open(META);
    if (on) await c.put(ROOT + "offline-meta/test", new Response("1")); else await c.delete(ROOT + "offline-meta/test");
    toWorker({test: on});
    if (navigator.serviceWorker && navigator.serviceWorker.ready)
      navigator.serviceWorker.ready.then(r => r.active && r.active.postMessage({test: on}));
  }

  // ---- saved records (cache META): an area's files, the base maps kept for it ----
  const metaUrl = (kind, key) => ROOT + "offline-meta/" + kind + "/" + key;
  async function getMeta(kind, key) {
    try { const r = await (await caches.open(META)).match(metaUrl(kind, key)); return r ? await r.json() : null; }
    catch (e) { return null; }
  }
  async function putMeta(kind, key, v) {
    const c = await caches.open(META);
    if (v == null) return c.delete(metaUrl(kind, key));
    return c.put(metaUrl(kind, key), new Response(JSON.stringify(v), {headers: {"Content-Type": "application/json"}}));
  }
  async function allMeta(kind) {
    const c = await caches.open(META), out = [];
    for (const k of await c.keys()) {
      if (!k.url.startsWith(ROOT + "offline-meta/" + kind + "/")) continue;
      try { out.push(await (await c.match(k)).json()); } catch (e) { /* being written */ }
    }
    return out;
  }

  // ---- an area's files ----
  // <area>/offline.json (weblib.py, at publish): {area, version, files: [[path in the area, bytes, hash]], shared:
  // [[path from the root, bytes, hash]] (the libraries and icons, part of the version)}; and the root's offline.json:
  // {root: [...]} (index.html, the credits page, offline.js, the manifest: kept fresh by the worker, not part of the
  // version; apart, as the map of all areas changes with every publish), read in as the area's list's root
  async function list(key) {
    const get = async url => {
      const r = await fetch(url, {cache: "no-store"});
      if (!r.ok) throw new Error("no list (" + r.status + ")");
      return r.json();
    };
    const [L, top] = await Promise.all([get(ROOT + key + "/offline.json"), get(ROOT + "offline.json")]);
    L.root = top.root || [];
    return L;
  }
  // [address, bytes, hash, kind]: the area's own files, the shared ones (both in the version), the root's. Addresses as
  // the caches keep them (a space as %20: the label fonts' folders)
  const href = p => new URL(p, ROOT).href;
  const wanted = (key, L) => [...L.files.map(([p, n, h]) => [href(key + "/" + p), n, h, "own"]),
                              ...(L.shared || []).map(([p, n, h]) => [href(p), n, h, "shared"]),
                              ...(L.root || []).map(([p, n, h]) => [href(p), n, h, "root"])];
  async function hashOf(blob) {
    const d = new Uint8Array(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()));
    return Array.from(d.slice(0, 8), b => b.toString(16).padStart(2, "0")).join("");
  }
  // what a save would fetch now: the files missing from the saved copy or saved at another hash (a root file only when
  // missing: the worker keeps those fresh itself)
  async function missing(key, L) {
    const files = await caches.open(FILES), out = [];
    for (const f of wanted(key, L)) {
      const r = await files.match(f[0]);
      if (!r || (f[3] !== "root" && r.headers.get("x-offline-hash") !== f[2])) out.push(f);
    }
    return out;
  }
  async function download(url, signal, onBytes) {
    const r = await fetch(url, {cache: "no-store", signal});
    if (!r.ok) throw new Error(r.status + " for " + url.slice(ROOT.length));
    const type = r.headers.get("content-type") || "";
    if (!r.body || !r.body.getReader) { const b = await r.blob(); onBytes(b.size); return [b, type]; }
    const rd = r.body.getReader(), parts = [];
    let got = 0;
    for (;;) {
      const {done, value} = await rd.read();
      if (done) break;
      parts.push(value); got += value.length; onBytes(got);
    }
    return [new Blob(parts, {type}), type];
  }
  async function pool(items, n, fn) {
    let i = 0;
    await Promise.all(Array.from({length: Math.min(n, items.length)}, async () => {
      while (i < items.length) { const it = items[i++]; await fn(it); }
    }));
  }
  // Saves (or updates) an area: the files that differ go to a staging cache first, each checked against its hash, and
  // move into the saved copy only when all are in, so a save that stops half-way leaves the last whole copy as it was.
  async function saveArea(key, label, job) {
    const L = await list(key);
    const todo = await missing(key, L), total = todo.reduce((s, f) => s + f[1], 0);
    await caches.delete(STAGE);
    const stage = await caches.open(STAGE), got = new Map();
    const report = () => job.progress([...got.values()].reduce((s, v) => s + v, 0), total, "maps");
    todo.sort((a, b) => b[1] - a[1]);
    await pool(todo, 3, async ([url, n, h, kind]) => {
      for (let attempt = 0; ; attempt++) {
        job.check();
        const [blob, type] = await download(url + "?offline-save=" + h, job.signal, b => { got.set(url, b); report(); });
        if (kind === "root" || await hashOf(blob) === h) {
          await stage.put(url, new Response(blob, {headers: {"Content-Type": type, "x-offline-hash": h}}));
          return;
        }
        // the site is being published right now: its files and their list don't match yet
        if (attempt >= 1) throw new Error("changing");
        await sleep(4000);
      }
    });
    job.check();
    job.progress(total, total, "store");
    const files = await caches.open(FILES);
    for (const req of await stage.keys()) await files.put(req, await stage.match(req));
    await caches.delete(STAGE);
    const bytes = wanted(key, L).reduce((s, f) => s + f[1], 0);
    await putMeta("area", key, {area: key, label: label || L.label || key, version: L.version, saved: new Date().toISOString(),
                                bytes, files: Object.fromEntries(wanted(key, L).map(([u, , h]) => [u, h]))});
    await sweep();
    // the area's gauges' latest readings are kept with it (map_gauges.js fetches them on this)
    document.dispatchEvent(new CustomEvent("streams-saved", {detail: {area: key}}));
    return {bytes, fetched: total};
  }
  // drop saved files no saved area lists any more (an area removed, or a library a newer site no longer uses)
  async function sweep() {
    const keep = new Set();
    (await allMeta("area")).forEach(m => Object.keys(m.files || {}).forEach(u => keep.add(u)));
    const files = await caches.open(FILES);
    for (const req of await files.keys()) if (!keep.has(req.url)) await files.delete(req);
  }
  async function removeArea(key) { await putMeta("area", key, null); await sweep(); }

  // ---- tiles: USGS topo (2D and 3D base map), AWS terrain (3D) ----
  const tx = (lon, z) => Math.max(0, Math.min(2 ** z - 1, Math.floor((lon + 180) / 360 * 2 ** z)));
  const ty = (lat, z) => { const r = lat * Math.PI / 180;
    return Math.max(0, Math.min(2 ** z - 1, Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * 2 ** z))); };
  const range = (b, z) => [tx(b[0][1], z), tx(b[1][1], z), ty(b[1][0], z), ty(b[0][0], z)];   // b = [[s, w], [n, e]]
  function count(b, z0, z1) {
    let n = 0;
    for (let z = z0; z <= z1; z++) { const [x0, x1, y0, y1] = range(b, z); n += (x1 - x0 + 1) * (y1 - y0 + 1); }
    return n;
  }
  function estimate(b, z0, z1, d0, d1) {
    let bytes = 0, n = 0;
    for (let z = z0; z <= z1; z++) { const c = count(b, z, z); n += c; bytes += c * (TOPO_B[z] || 25e3); }
    for (let z = d0; z <= d1; z++) { const c = count(b, z, z); n += c; bytes += c * (DEM_B[z] || 100e3); }
    return {n, bytes};
  }
  function* tileUrls(b, z0, z1, tpl) {
    for (let z = z0; z <= z1; z++) {
      const [x0, x1, y0, y1] = range(b, z);
      for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++)
        yield tpl.replace("{z}", z).replace("{x}", x).replace("{y}", y);
    }
  }
  // Saves a region's tiles, those not saved already; a tile that fails is tried 5 times over about 15 s (the USGS
  // server drops a few under load), and the panel offers to fetch the ones still missing. A region saved again under
  // its id at other zooms (the whole area, to another zoom) first gives up the tiles only the old zooms had.
  async function saveTiles(key, region, job) {
    let old = ((await getMeta("tiles", key)) || {regions: []}).regions.find(r => r.id === region.id);
    if (old && (old.z !== region.z || old.dz !== region.dz)) { await removeRegion(key, old.id); old = null; }
    const urls = [...tileUrls(region.b, region.z0, region.z, TOPO), ...tileUrls(region.b, region.d0, region.dz, DEM)];
    const tiles = await caches.open(TILES);
    let done = 0, bytes = 0, failed = 0;
    await pool(urls, 6, async url => {
      job.check();
      if (!(await tiles.match(url, {ignoreVary: true}))) {
        for (let attempt = 0; ; attempt++) {
          try {
            const r = await fetch(url, {mode: "cors", cache: "no-store", signal: job.signal});
            if (!r.ok) throw new Error(String(r.status));
            const blob = await r.blob();
            await tiles.put(url, new Response(blob, {headers: {"Content-Type": r.headers.get("content-type") || "image/png"}}));
            bytes += blob.size;
            break;
          } catch (e) {
            if (job.signal.aborted || (e && e.name === "QuotaExceededError")) throw e;
            if (attempt >= 4) { failed++; break; }
            await sleep(1000 * 2 ** attempt);
          }
        }
      }
      job.progress(++done, urls.length, "tiles");
    });
    const rec = (await getMeta("tiles", key)) || {area: key, regions: []};
    rec.regions = rec.regions.filter(r => r.id !== region.id);
    rec.regions.push(Object.assign({}, region, {n: urls.length, bytes: (old ? old.bytes : 0) + bytes, failed,
                                                saved: new Date().toISOString()}));
    await putMeta("tiles", key, rec);
    return {n: urls.length, bytes, failed};
  }
  // a region's tiles go, except those another saved region (of any area) also holds
  async function removeRegion(key, id) {
    const rec = await getMeta("tiles", key);
    if (!rec) return;
    const gone = rec.regions.find(r => r.id === id);
    rec.regions = rec.regions.filter(r => r.id !== id);
    await putMeta("tiles", key, rec);
    if (!gone) return;
    const others = (await allMeta("tiles")).flatMap(m => m.regions);
    const holds = (url, kind) => others.some(r => {
      const m = url.match(kind === "topo" ? /\/tile\/(\d+)\/(\d+)\/(\d+)$/ : /\/(\d+)\/(\d+)\/(\d+)\.png$/);
      if (!m) return false;
      const [z, a, c] = m.slice(1).map(Number), x = kind === "topo" ? c : a, y = kind === "topo" ? a : c;
      const [lo, hi] = kind === "topo" ? [r.z0, r.z] : [r.d0, r.dz];
      if (z < lo || z > hi) return false;
      const [x0, x1, y0, y1] = range(r.b, z);
      return x >= x0 && x <= x1 && y >= y0 && y <= y1;
    });
    const tiles = await caches.open(TILES);
    for (const u of tileUrls(gone.b, gone.z0, gone.z, TOPO)) if (!holds(u, "topo")) await tiles.delete(u, {ignoreVary: true});
    for (const u of tileUrls(gone.b, gone.d0, gone.dz, DEM)) if (!holds(u, "dem")) await tiles.delete(u, {ignoreVary: true});
  }
  // the zooms saved where a tile lies (for drawing a coarser saved tile in its place)
  let REGIONS = [];
  async function loadRegions() { REGIONS = CAN ? (await allMeta("tiles")).flatMap(m => m.regions) : []; return REGIONS; }

  // ---- the network ----
  // The browser's word, then a small request to Esri's tile server (the layers that go when the network does): in the
  // backcountry a phone with a bar of signal and no data still says it is online.
  const net = {on: true, subs: []};
  async function probe() {
    await testRead;
    if (!navigator.onLine || TEST) return false;
    const c = new AbortController(), t = setTimeout(() => c.abort(), 5000);
    try { await fetch(PROBE, {mode: "no-cors", cache: "no-store", signal: c.signal}); return true; }
    catch (e) { return false; }
    finally { clearTimeout(t); }
  }
  let checking = null;
  function check() {
    if (checking) return checking;
    return (checking = probe().then(on => {
      checking = null;
      toWorker({offline: !on, test: TEST});
      if (on !== net.on) { net.on = on; net.subs.forEach(f => f(on)); }
      return on;
    }));
  }
  function onNet(f) { net.subs.push(f); if (!net.on) f(false); }
  addEventListener("online", check);
  addEventListener("offline", check);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
  if (HTTP) setTimeout(check, 0); else net.on = navigator.onLine;

  // ---- one save at a time, with a progress bar ----
  let job = null;
  function startJob(kind, onProgress) {
    const ctl = new AbortController();
    job = {kind, signal: ctl.signal, cancel: () => ctl.abort(), lock: null,
           check() { if (ctl.signal.aborted) throw new DOMException("Stopped", "AbortError"); },
           progress: onProgress};
    if (navigator.wakeLock) navigator.wakeLock.request("screen").then(l => { job && (job.lock = l); }, () => {});
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    return job;
  }
  function endJob() { if (job && job.lock) job.lock.release().catch(() => {}); job = null; }
  const why = e => !e ? "" : e.name === "AbortError" ? "Stopped." : e.name === "QuotaExceededError"
    ? "Not enough room on this phone: remove a saved area or base map, then try again."
    : e.message === "changing" ? "The site is being updated right now: try again in a few minutes."
    : !navigator.onLine || /fetch|network|load failed/i.test(e.message) ? "No connection: saving needs one." : "Couldn't save: " + e.message;

  // ---- the panel (an area's maps) ----
  const CSS = `
.ofl { border-top: 1px solid #dee2e6; margin-top: 8px; padding-top: 7px; font: 12px/1.35 system-ui, -apple-system, sans-serif; color: #1d1d1f; }
.ofl .oh { font-weight: 700; font-size: 12.5px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: baseline; }
.ofl .oh small { font-weight: 400; color: #6b7280; }
.ofl .os { font-weight: 600; color: #495057; margin: 8px 0 2px; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
.ofl .orow { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 3px 0; }
.ofl .orow > div { min-width: 0; }
.ofl .odim { color: #6b7280; font-size: 11px; }
.ofl .ook { color: #2b8a3e; } .ofl .oup { color: #c2410c; font-weight: 600; } .ofl .oerr { color: #a61e4d; }
.ofl button.ob { flex: none; border: 1px solid #1864ab; background: #1864ab; color: #fff; border-radius: 6px; padding: 5px 10px;
  font: 600 12px system-ui, -apple-system, sans-serif; cursor: pointer; min-height: 30px; }
.ofl button.ob.alt { background: #fff; color: #1864ab; }
.ofl button.ob:disabled { opacity: .45; cursor: default; }
.ofl select { font: inherit; font-size: 12px; border: 1px solid #c9ced6; border-radius: 5px; background: #fff; color: #1d1d1f; padding: 1px 2px; }
.ofl .olist { margin: 2px 0 0; }
.ofl .olist div { display: flex; justify-content: space-between; gap: 6px; align-items: center; color: #495057; font-size: 11px; padding: 1px 0; }
.ofl .olist a, .ofl a.olink { color: #1864ab; text-decoration: none; cursor: pointer; }
.ofl .obar { height: 6px; background: #e9ecef; border-radius: 3px; overflow: hidden; margin: 6px 0 3px; }
.ofl .obar i { display: block; height: 100%; width: 0; background: #1864ab; transition: width .2s; }
.ofl .oprog { display: none; } .ofl.busy .oprog { display: block; }
.ofl.busy button.ob[data-act]:not([data-act=cancel]) { opacity: .45; pointer-events: none; }
.ofl .otip { background: #fff4e6; border-radius: 6px; padding: 5px 7px; margin-top: 7px; font-size: 11px; color: #5c3d0e; }
.ofl-net { position: absolute; z-index: 1000; left: 50%; top: 10px; transform: translateX(-50%); background: rgba(33,37,41,.88);
  color: #fff; border-radius: 14px; padding: 5px 12px; font: 600 12px/1.3 system-ui, -apple-system, sans-serif; pointer-events: none;
  text-align: center; width: max-content; max-width: calc(100% - 130px); }
.leaflet-control-layers-selector:disabled + span { opacity: .45; }
.ofl-off { opacity: .45; }`;
  function style() {
    if (document.getElementById("ofl-css")) return;
    const s = document.createElement("style"); s.id = "ofl-css"; s.textContent = CSS; document.head.appendChild(s);
  }
  // A note over the map for a few seconds ("No connection: ...")
  function toast(container, text, ms = 6000) {
    let el = container.querySelector(".ofl-net");
    if (!el) { el = document.createElement("div"); el.className = "ofl-net"; container.appendChild(el); }
    el.textContent = text; el.style.display = "";
    clearTimeout(el._t); el._t = setTimeout(() => { el.style.display = "none"; }, ms);
  }
  // nearest named drainage to a point, to name a saved view ("view near Natchaug River")
  function nearName(lat, lon) {
    const ds = (window.DRAINS || (window.MAP3D || {}).drains || []).filter(d => d.lab && d.name);
    let best = null, bd = Infinity;
    ds.forEach(d => { const dd = (d.lab[0] - lat) ** 2 + ((d.lab[1] - lon) * Math.cos(lat * Math.PI / 180)) ** 2;
      if (dd < bd) { bd = dd; best = d.name; } });
    return best;
  }
  // the area's box, from its drainage divides (map3d_data.js, both maps)
  function areaBounds() {
    const D = window.MAP3D || {}, fs = (D.divides || {}).features || [];
    let s = 90, w = 180, n = -90, e = -180;
    fs.forEach(f => (f.geometry.type === "MultiLineString" ? f.geometry.coordinates.flat() : f.geometry.coordinates)
      .forEach(([x, y]) => { if (y < s) s = y; if (y > n) n = y; if (x < w) w = x; if (x > e) e = x; }));
    return s < n ? [[s, w], [n, e]] : null;
  }
  const zSel = (zs, b, z0, d0, d1, cap) => {
    const est = zs.map(z => [z, estimate(b, z0, z, d0, d1)]);
    const pick = [...est].reverse().find(([, e]) => e.bytes <= cap && e.n <= MAX_TILES) || est[0];
    return [est, pick[0]];
  };

  // panel(host, opts): host = the element the section goes in; opts.view() = the view's bounds [[s, w], [n, e]] or null
  // (the 3D map: none, its tilted view has no box), opts.label, opts.onSaved()
  function panel(host, opts) {
    style();
    const key = areaKey, box = areaBounds();
    const el = document.createElement("div");
    el.className = "ofl";
    host.appendChild(el);
    if (!key) return;
    if (!CAN) {
      el.innerHTML = `<div class="oh">Offline use</div><div class="odim">${HTTP ? "This browser can't keep maps for offline use."
        : "Open the maps on the website (alexanderswann.github.io/streams) to save them for offline use."}</div>`;
      return;
    }
    el.innerHTML = `<div class="oh">Offline use <small class="ost"></small></div>
      <div class="orow"><div><b>This area's maps</b><div class="odim oa">2D and 3D maps, creek profiles, terrain shading</div></div>
        <button class="ob" data-act="area">Save</button></div>
      <div class="olist oas"></div>
      <div class="os">Topo base map (USGS)</div>
      <div class="orow"><div>Whole area to zoom <select class="oza"></select><div class="odim ozas"></div></div>
        <button class="ob alt" data-act="whole">Save</button></div>
      ${opts.view ? `<div class="orow"><div>This view to zoom <select class="ozv"></select><div class="odim ozvs"></div></div>
        <button class="ob alt" data-act="view">Save</button></div>` : `<div class="odim">To keep a view's detail (zoom 16), save it on the 2D map.</div>`}
      <div class="olist oreg"></div>
      <div class="oprog"><div class="obar"><i></i></div><div class="orow"><span class="odim opt"></span>
        <button class="ob alt" data-act="cancel">Stop</button></div></div>
      <div class="odim omsg"></div>
      <div class="odim ofoot"></div>
      ${iOS && !standalone ? `<div class="otip"><b>iPhone:</b> tap Share, then <b>Add to Home Screen</b>, open Stream maps
        from the Home Screen and save there. Safari can clear what a tab saved after 7 days unused; the Home Screen app keeps it.</div>` : ""}`;
    const $ = s => el.querySelector(s);
    const msg = (t, cls) => { $(".omsg").className = "odim omsg" + (cls ? " " + cls : ""); $(".omsg").textContent = t || ""; };
    let L$ = null, meta = null, todoBytes = null, upd = false, drawing = 0;
    // the whole area's choices: zooms 10 to 13, the largest under 60 MB picked
    const [aEst, aPick] = box ? zSel(AREA_Z, box, 6, 6, AREA_DEM, 60e6) : [[], null];
    $(".oza").innerHTML = aEst.map(([z, e]) => `<option value="${z}"${z === aPick ? " selected" : ""}>${z}</option>`).join("");
    const showA = () => { const e = aEst.find(([z]) => z === +$(".oza").value);
      $(".ozas").textContent = e ? `≈ ${MB(e[1].bytes)}, 3D terrain included` : ""; };
    $(".oza").onchange = showA; showA();
    // the view's choices (2D): zooms 13 to 16 over what is on the screen, the largest under 120 MB picked
    const showV = () => {
      if (!opts.view) return;
      const b = opts.view(), s = $(".ozv");
      const [est, pick] = zSel(VIEW_Z, b, 8, 8, VIEW_DEM, 120e6);
      const cur = +s.value || pick;
      s.innerHTML = est.map(([z, e]) => `<option value="${z}"${z === (est.some(x => x[0] === cur) ? cur : pick) ? " selected" : ""}` +
        `${e.n > MAX_TILES ? " disabled" : ""}>${z}</option>`).join("");
      const e = est.find(([z]) => z === +s.value);
      $(".ozvs").textContent = e ? (e[1].n > MAX_TILES ? "zoom in to save more detail"
        : `≈ ${MB(e[1].bytes)}, 3D terrain included`) : "";
      $("[data-act=view]").disabled = !e || e[1].n > MAX_TILES;
    };
    if (opts.view) { $(".ozv").onchange = () => { $(".ozvs").textContent = ""; showV(); }; showV(); }
    async function refresh(fetchList) {
      meta = await getMeta("area", key);
      if (fetchList) {
        draw();
        try { L$ = await Promise.race([list(key), sleep(8000).then(() => { throw new Error("slow"); })]); } catch (e) { L$ = null; }
      }
      return draw();
    }
    async function draw() {
      // each draw works from what it read at its start; only the newest one writes (the first, from the saved record
      // alone, can end after the one made once the site's list is in)
      const my = ++drawing, Lx = L$, mx = meta;
      const miss = Lx ? await missing(key, Lx) : null;
      // a saved copy missing files (the phone cleared some, a save cut short) counts as one to update; with no
      // connection, the saved record's own list says what should be there
      let lost = 0;
      if (mx && !Lx) { const files = await caches.open(FILES);
        for (const u of Object.keys(mx.files || {})) if (!(await files.match(u))) lost++; }
      if (my !== drawing) return;
      todoBytes = miss ? miss.reduce((s, f) => s + f[1], 0) : null;
      const total = Lx ? wanted(key, Lx).reduce((s, f) => s + f[1], 0) : mx && mx.bytes;
      upd = !!(mx && Lx && (Lx.version !== mx.version || miss.some(f => f[3] !== "root")));
      $(".ost").innerHTML = mx ? (upd ? `<span class="oup">update available</span>` : lost ? `<span class="oerr">incomplete</span>`
        : `<span class="ook">✓ saved</span>`) : "";
      $(".oa").innerHTML = mx
        ? `Saved ${esc(day(mx.saved))} · ${MB(mx.bytes)}` + (upd ? ` · <span class="oup">update available: ${MB(todoBytes)}</span>`
          : lost ? ` · <span class="oerr">${lost} files missing: update it with a connection</span>` : Lx ? " · up to date" : "")
        : `2D and 3D maps, creek profiles, terrain shading · ${total ? MB(todoBytes != null ? todoBytes : total) : "size unknown offline"}`;
      const b = $("[data-act=area]");
      b.textContent = mx ? (upd ? "Update" : "Remove") : "Save";
      b.classList.toggle("alt", !!mx && !upd);
      b.disabled = !mx && !Lx;
      $(".oas").innerHTML = mx && upd ? `<div><span></span><a data-act="remove-area">Remove the saved copy</a></div>` : "";
      const rec = await getMeta("tiles", key);
      await loadRegions();
      $(".oreg").innerHTML = (rec ? rec.regions : []).map(r => `<div><span>✓ ${esc(r.name)} to zoom ${r.z} · ${MB(r.bytes)}` +
        `${r.failed ? ` · <a data-act="retry" data-id="${esc(r.id)}" class="oerr">get the ${r.failed} missing tiles</a>` : ""}</span>` +
        `<a data-act="rm" data-id="${esc(r.id)}" title="Remove">Remove</a></div>`).join("");
      if (navigator.storage && navigator.storage.estimate) {
        const s = await navigator.storage.estimate().catch(() => null);
        if (s) $(".ofoot").textContent = `Kept on this device: ${MB(s.usage)}` + (s.quota ? ` · room for ${MB(Math.max(0, s.quota - s.usage))} more` : "");
      }
      if (opts.onSaved) opts.onSaved();
    }
    const bar = (done, total, what) => {
      $(".obar i").style.width = (total ? Math.min(100, done / total * 100) : 0).toFixed(1) + "%";
      $(".opt").textContent = what === "store" ? "Storing on this device…" : what === "maps" ? `Saving ${MB(done)} of ${MB(total)} · keep this page open`
        : `Saving tiles: ${done.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} · keep this page open`;
    };
    async function run(fn) {
      if (job) return;
      msg("");
      el.classList.add("busy"); bar(0, 0, "maps");
      const pr = $(".oprog");
      if (pr.scrollIntoView) pr.scrollIntoView({block: "nearest"});     // the bar, its words and Stop in sight
      const j = startJob("save", bar);
      try { await fn(j); } catch (e) { msg(why(e), "oerr"); }
      finally { endJob(); el.classList.remove("busy"); await refresh(false).catch(() => {}); }
    }
    el.addEventListener("click", async e => {
      const a = e.target.closest("[data-act]");
      if (!a || a.disabled) return;
      e.preventDefault(); e.stopPropagation();
      const act = a.dataset.act;
      if (act === "cancel") { if (job) job.cancel(); return; }
      if (act === "area" && meta && !upd) await confirmRemove();
      else if (act === "area") await run(async j => {
        const was = meta;
        const r = await saveArea(key, opts.label, j);
        msg(was ? `Updated (${MB(r.fetched)} downloaded). Reload the page to see the new maps.`
          : `Saved: ${MB(r.bytes)}${r.fetched < r.bytes ? ` (${MB(r.fetched)} downloaded)` : ""}. It opens without a connection now.`, "ook");
        refresh(true);
      });
      else if (act === "remove-area") await confirmRemove();
      else if (act === "whole" && box) await run(async j => {
        const z = +$(".oza").value;
        const r = await saveTiles(key, {id: "area", name: "Whole area", b: box, z0: 6, z, d0: 6, dz: AREA_DEM}, j);
        msg(`Base map saved: ${r.n.toLocaleString("en-US")} tiles, ${MB(r.bytes)} downloaded` + (r.failed ? `; ${r.failed} didn't load (try again later)` : "") + ".", r.failed ? "oerr" : "ook");
      });
      else if (act === "view" && opts.view) await run(async j => {
        const b = opts.view(), z = +$(".ozv").value, c = [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
        const nm = nearName(c[0], c[1]);
        const r = await saveTiles(key, {id: "v" + Date.now().toString(36), name: nm ? "View near " + nm : "View", b, z0: 8, z,
                                        d0: 8, dz: VIEW_DEM}, j);
        msg(`View saved: ${r.n.toLocaleString("en-US")} tiles, ${MB(r.bytes)} downloaded` + (r.failed ? `; ${r.failed} didn't load (try again later)` : "") + ".", r.failed ? "oerr" : "ook");
      });
      else if (act === "rm") { if (!job) { await removeRegion(key, a.dataset.id); msg("Removed."); refresh(false); } }
      else if (act === "retry") await run(async j => {
        const r0 = ((await getMeta("tiles", key)) || {regions: []}).regions.find(r => r.id === a.dataset.id);
        if (!r0) return;
        const r = await saveTiles(key, r0, j);
        msg(r.failed ? `${r.failed} tiles still didn't load: try again later.` : "All tiles saved.", r.failed ? "oerr" : "ook");
      });
    });
    async function confirmRemove() {
      if (job || !confirm("Remove the saved copy of this area's maps from this device? The base maps saved for it stay.")) return;
      await removeArea(key); msg("Removed."); refresh(false);
    }
    refresh(true);
    onNet(on => { if (on) refresh(true); });
    return {refresh: () => refresh(false), showView: showV};
  }

  // ---- the 2D area map (06_map.py: after initDrainageMap) ----
  function map2d(map, ctrl) {
    style();
    const all = ctrl._layers;
    const isTopo = l => l && /USGSTopo/.test(l._url || "");
    const isFar = l => l && /arcgisonline\.com|opentopomap\.org/.test(l._url || "");    // Esri, OpenTopoMap: never kept
    const topo = (all.find(o => !o.overlay && isTopo(o.layer)) || {}).layer;
    const relief = (all.find(o => o.overlay && o.layer.getLayers && o.layer.getLayers().some(l => /hillshade\.png$/.test(l._url || ""))) || {}).layer;
    // the section, under the layer list (Leaflet rebuilds only the lists above it)
    const section = document.createElement("div");
    ctrl._section.appendChild(section);
    L.DomEvent.disableClickPropagation(section);
    const view = () => { const b = map.getBounds(); return [[b.getSouth(), b.getWest()], [b.getNorth(), b.getEast()]]; };
    const p = panel(section, {view, label: (window.LBL || {}).title});
    if (p && p.showView) map.on("moveend", () => p.showView());
    // the header's "Offline" link: straight to the section
    const head = ctrl.getContainer().querySelector(".lyh b");
    if (head && CAN && areaKey) {
      const a = document.createElement("a");
      a.href = "#"; a.className = "ofl-go"; a.textContent = "Offline ↓";
      a.style.cssText = "font-weight:600;font-size:11px;color:#1864ab;margin-left:8px;text-decoration:none";
      head.after(a);
      L.DomEvent.on(a, "click", e => { L.DomEvent.stop(e); section.scrollIntoView({block: "start", behavior: "smooth"}); });
    }
    // offline: the saved topo with our own terrain shading; the far layers greyed out until the network is back
    let undo = null;
    const grey = () => ctrl._layerControlInputs.forEach(inp => {
      const o = ctrl._getLayer(inp.layerId);
      if (!o) return;
      const off = !net.on && isFar(o.layer);
      inp.disabled = off;
      const lab = inp.closest("label");
      if (lab) { lab.classList.toggle("ofl-off", off); lab.title = off ? "Needs a connection" : ""; }
    });
    const rebuild = ctrl._update;
    ctrl._update = function () { const r = rebuild.apply(this, arguments); grey(); return r; };
    const outlines = L.layerGroup();
    function apply(on) {
      if (!on && !undo) {
        undo = {base: null, over: [], relief: false, opacity: null};
        const base = all.find(o => !o.overlay && map.hasLayer(o.layer));
        if (topo && base && isFar(base.layer)) { undo.base = base.layer; map.removeLayer(base.layer); map.addLayer(topo); }
        all.filter(o => o.overlay && isFar(o.layer) && map.hasLayer(o.layer)).forEach(o => { undo.over.push(o.layer); map.removeLayer(o.layer); });
        if (relief && !map.hasLayer(relief)) { undo.relief = true; map.addLayer(relief); }
        if (relief) { undo.opacity = relief.getLayers().map(l => l.options.opacity);
                      relief.getLayers().forEach(l => l.setOpacity && l.setOpacity(0.3)); }   // over the topo
        if (topo) coarser(topo);
        loadRegions().then(rs => { outlines.clearLayers();
          rs.filter(r => r.id !== "area").forEach(r => L.rectangle(r.b, {color: "#1864ab", weight: 1.2, dashArray: "5 5", fill: false,
            interactive: false}).addTo(outlines)); });
        outlines.addTo(map);
        toast(map.getContainer(), "No connection: saved topo map and our terrain shading");
      } else if (on && undo) {
        const u = undo; undo = null;
        if (u.base && map.hasLayer(topo)) { map.removeLayer(topo); map.addLayer(u.base); }
        u.over.forEach(l => map.addLayer(l));
        if (relief) {
          if (u.opacity) relief.getLayers().forEach((l, i) => l.setOpacity && l.setOpacity(u.opacity[i]));
          if (u.relief) map.removeLayer(relief);
        }
        if (topo) finer(topo);
        map.removeLayer(outlines);
        toast(map.getContainer(), "Back online", 2500);
      }
      grey();
    }
    onNet(apply);
    standaloneLinks();
    return {apply};
  }
  // Where the zoom on the screen isn't saved, the topo layer shows the nearest coarser saved tile, enlarged (a whole
  // area kept to zoom 13 still reads at zoom 15). Only while offline: online the layer is Leaflet's own.
  function coarser(layer) {
    if (layer._oflTile) return;
    layer._oflTile = layer.createTile;
    layer.createTile = function (c, done) {
      const div = document.createElement("div"), img = document.createElement("img"), size = this.getTileSize();
      img.alt = ""; img.setAttribute("role", "presentation");
      img.style.cssText = "position:absolute;left:0;top:0;max-width:none;max-height:none";
      div.style.overflow = "hidden"; div.appendChild(img);
      // the zooms to try: this one, then those saved at this spot, coarsest last
      const lon = (c.x + 0.5) / 2 ** c.z * 360 - 180, n = Math.PI - 2 * Math.PI * (c.y + 0.5) / 2 ** c.z;
      const lat = 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
      const zs = [c.z, ...new Set(REGIONS.filter(r => lat >= r.b[0][0] && lat <= r.b[1][0] && lon >= r.b[0][1] && lon <= r.b[1][1])
        .map(r => Math.min(r.z, c.z - 1)).filter(z => z >= 0).sort((a, b) => b - a))];
      let i = 0;
      const show = () => {
        const z = zs[i], k = 2 ** (c.z - z), x = Math.floor(c.x / k), y = Math.floor(c.y / k);
        img.style.width = size.x * k + "px"; img.style.height = size.y * k + "px";
        img.style.left = -(c.x - x * k) * size.x + "px"; img.style.top = -(c.y - y * k) * size.y + "px";
        img.src = L.Util.template(this._url, L.Util.extend({}, this.options, {x, y, z, s: this._getSubdomain ? this._getSubdomain({x, y}) : "a"}));
      };
      img.onload = () => done(null, div);
      img.onerror = () => { if (++i < zs.length) show(); else done(new Error("not saved"), div); };
      show();
      return div;
    };
    layer.redraw();
  }
  function finer(layer) {
    if (!layer._oflTile) return;
    layer.createTile = layer._oflTile; delete layer._oflTile;
    layer.redraw();
  }

  // ---- the 3D map (map3d.html, after the map is made) ----
  // opts: {setBase(key), labels(on), host: the element of the layer panel the section goes in}
  function map3d(map, opts) {
    style();
    const host = opts.host || document.body;
    const sec = document.createElement("div");
    host.appendChild(sec);
    panel(sec, {label: ((window.MAP3D || {}).lbl || {}).title});
    let undo = null;
    onNet(async on => {
      const far = [...document.querySelectorAll("input[name=base]")].filter(r => r.value !== "topo");
      far.forEach(r => { r.disabled = !on; const l = r.closest("label"); if (l) l.classList.toggle("ofl-off", !on); });
      const lbl = document.getElementById("lbl");
      if (lbl) { lbl.disabled = !on; const l = lbl.closest("label"); if (l) l.classList.toggle("ofl-off", !on); }
      if (!on && !undo) {
        const cur = document.querySelector("input[name=base]:checked");
        undo = {base: cur ? cur.value : null, labels: lbl ? lbl.checked : null};
        if (cur && cur.value !== "topo") opts.setBase("topo");
        if (lbl && lbl.checked) { lbl.checked = false; opts.labels(false); }
        const regions = await loadRegions(), b = map.getBounds();
        const dem = regions.some(r => r.dz && r.b[0][0] <= b.getNorth() && r.b[1][0] >= b.getSouth() && r.b[0][1] <= b.getEast() && r.b[1][1] >= b.getWest());
        if (!dem && map.getTerrain && map.getTerrain()) { undo.terrain = map.getTerrain(); map.setTerrain(null); }
        toast(map.getContainer(), dem ? "No connection: saved topo map and terrain"
          : "No connection, and no terrain saved here: the map is flat", dem ? 6000 : 9000);
      } else if (on && undo) {
        const u = undo; undo = null;
        if (u.base && u.base !== "topo") opts.setBase(u.base);
        if (lbl && u.labels) { lbl.checked = true; opts.labels(true); }
        if (u.terrain) map.setTerrain(u.terrain);
        toast(map.getContainer(), "Back online", 2500);
      }
    });
    standaloneLinks();
  }

  // ---- the map of all areas (13_overview.py) ----
  // opts: {topo, far: [layers that need a connection], buttons: the list's buttons (data-i: the area's index)}
  function overview(map, areas, opts) {
    style();
    let undo = null;
    const mark = async () => {
      if (!CAN) return;
      const saved = Object.fromEntries((await allMeta("area")).map(m => [m.area, m]));
      (opts.buttons || []).forEach(bn => {
        const a = areas[+bn.dataset.i];
        if (!a) return;
        let s = bn.querySelector(".ofl-b");
        if (!saved[a.key]) { if (s) s.remove(); return; }
        if (!s) { s = document.createElement("span"); s.className = "ofl-b"; s.style.cssText = "float:right;color:#2b8a3e;font-size:11px;font-weight:600"; bn.querySelector("b").after(s); }
        s.textContent = "✓ saved";
        s.title = "Saved for offline use " + day(saved[a.key].saved);
      });
    };
    mark();
    onNet(on => {
      if (!on && !undo) {
        undo = opts.far.filter(l => map.hasLayer(l));
        undo.forEach(l => map.removeLayer(l));
        if (opts.topo && !map.hasLayer(opts.topo)) map.addLayer(opts.topo);
        // the list, folded at first on a phone, opens: the saved areas are marked in it
        const list = document.querySelector(".panel .list");
        if (list && list.style.display === "none") { const h = document.querySelector(".panel h1"); if (h) h.click(); }
        toast(map.getContainer(), "No connection: the areas marked saved open from the list");
      } else if (on && undo) {
        if (undo.length && opts.topo && map.hasLayer(opts.topo) && !undo.includes(opts.topo)) map.removeLayer(opts.topo);
        undo.forEach(l => map.addLayer(l)); undo = null;
      }
    });
    standaloneLinks();
    return {mark};
  }

  // ---- in the Home Screen app, the site's links open in the app ----
  // (a link with target=_blank, as the stream popups' "Open <creek> profile ↗", would leave the app for Safari, where
  // nothing is saved); and a page opened that way gets a way back
  let linksDone = false;
  function standaloneLinks() {
    if (linksDone || !standalone) return;
    linksDone = true;
    document.addEventListener("click", e => {
      const a = e.target.closest && e.target.closest("a[target=_blank]");
      if (!a || !a.href || !a.href.startsWith(ROOT) || e.defaultPrevented) return;
      e.preventDefault();
      location.href = a.href;
    }, true);
  }
  function page() {     // a page with no map of its own (profiles.html)
    standaloneLinks();
    if (standalone && history.length > 1 && !document.getElementById("ofl-back")) {
      const b = document.createElement("a");
      b.id = "ofl-back"; b.href = "#"; b.textContent = "‹ Back to the map";
      b.style.cssText = "position:fixed;z-index:50;left:10px;bottom:14px;background:#1864ab;color:#fff;border-radius:16px;" +
        "padding:6px 12px;font:600 13px system-ui,-apple-system,sans-serif;text-decoration:none;box-shadow:0 1px 6px rgba(0,0,0,.3)";
      b.onclick = e => { e.preventDefault(); history.back(); };
      (document.body ? Promise.resolve() : new Promise(r => addEventListener("DOMContentLoaded", r))).then(() => document.body.appendChild(b));
    }
  }

  window.StreamsOffline = {map2d, map3d, overview, page, check, onNet, test: setTest, root: ROOT, area: areaKey,
                           net: () => net.on, canSave: CAN,
                           saved: async key => !!(CAN && await getMeta("area", key || areaKey))};   // (map_gauges.js)
})();
