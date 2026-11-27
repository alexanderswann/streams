// The pages' big files, kept gzip-compressed on the site (2026-11-25; GitHub Pages' 1 GB limit, and a saved area's room on
// the phone). publish_site.sh (weblib.py pack) publishes each of them as <name>.gz, the very bytes of <name> compressed;
// output/ keeps the plain files. A page asks for its files by their plain names:
//   StreamsLoad(names, done)   fetches every file at once, then, once the page is parsed, runs them in the order given,
//                              each as the plain <script> would run, and calls done(the names that didn't load); those
//                              are also named in a note at the top of the page
//   StreamsLoad.script(name)   one file later on (routes_data.js on the first tap on a reach): a promise, rejected when
//                              the file doesn't load
//   StreamsLoad.prefetch(names)  start fetching now (high in a page's <head>, before its big libraries), for a later
//                              StreamsLoad or StreamsLoad.script of the same names: a plain <script src> used to start
//                              then too, found early by the browser's preload scanner
// Over the web a file comes from <name>.gz, unpacked by the browser's DecompressionStream (Safari 16.4, Chrome 80,
// Firefox 113 and later) as it downloads; an older browser unpacks it with inflate.js beside this file. Opened from disk
// (file://), or where no .gz is beside the page (a local server on output/), the plain <name> runs from a <script> tag.
// Used by 06_map.py's 2D page (map3d_data.js, then stream_map.js: folium's script with the 2D map's own layers) and 3D
// page (map3d_data.js, map3d_layers.js), the creek profiles (profiles_data.js), map_routes.js (routes_data.js) and
// map_land.js (land_data.js, parcels_data.js) and map_coverage.js (coverage_data.js).
(function () {
  if (window.StreamsLoad) return;
  const HTTP = /^https?:$/.test(location.protocol);
  const HERE = (document.currentScript && document.currentScript.src) || location.href;
  const times = {};                               // per file: when it was fetched and when it ran (performance.now(), ms)
  let inflater = null;
  const pending = {};                             // name -> its fetch, started by prefetch and taken by the first run
  const get = name => { const p = pending[name] || fetchGz(name); delete pending[name]; return p; };

  // a classic script from src: true once it ran (an error inside it is reported as any script's), false if it didn't load
  function tag(src) {
    return new Promise(ok => {
      const s = document.createElement("script");
      s.src = src;
      s.async = false;
      s.onload = () => { s.remove(); ok(true); };
      s.onerror = () => { s.remove(); ok(false); };
      document.head.appendChild(s);
    });
  }
  const gz = b => b.length > 1 && b[0] === 0x1f && b[1] === 0x8b;

  // <name>.gz unpacked, as a Blob; null where there is none (then the plain file runs)
  async function fetchGz(name) {
    if (!HTTP) return null;
    let r;
    try { r = await fetch(name + ".gz"); } catch (e) { return null; }
    if (!r.ok) return null;
    if (typeof DecompressionStream === "function" && r.body && r.body.getReader) {
      // unpacked as it comes in; its first bytes say whether it is gzip at all (a server that sends it with
      // Content-Encoding: gzip has the browser unpack it on the way)
      const rd = r.body.getReader();
      let head = new Uint8Array(0);
      while (head.length < 2) {
        const {done, value} = await rd.read();
        if (done) break;
        const both = new Uint8Array(head.length + value.length);
        both.set(head); both.set(value, head.length); head = both;
      }
      const body = new ReadableStream({
        start(c) { if (head.length) c.enqueue(head); },
        async pull(c) { const {done, value} = await rd.read(); if (done) c.close(); else c.enqueue(value); },
        cancel(why) { return rd.cancel(why); }
      });
      return new Response(gz(head) ? body.pipeThrough(new DecompressionStream("gzip")) : body).blob();
    }
    const buf = new Uint8Array(await r.arrayBuffer());
    if (!gz(buf)) return new Blob([buf]);
    if (!inflater) inflater = tag(new URL("inflate.js", HERE).href).then(() => window.StreamsInflate || null);
    const inf = await inflater;
    if (!inf) throw new Error("inflate.js did not load");
    return new Blob([inf.gunzip(buf)]);
  }

  async function run(name, got) {
    let blob = null;
    try { blob = await got; } catch (e) { console.warn(name + ".gz: " + e); }
    times[name] = {fetched: Math.round(performance.now())};
    let ok = false;
    if (blob) {
      const url = URL.createObjectURL(new Blob([blob], {type: "text/javascript;charset=utf-8"}));
      ok = await tag(url);
      URL.revokeObjectURL(url);
    }
    if (!ok) ok = await tag(name);
    times[name].ran = Math.round(performance.now());
    return ok;
  }

  function note(failed) {
    const d = document.createElement("div");
    d.setAttribute("role", "alert");
    d.style.cssText = "position:fixed;z-index:100000;left:50%;top:10px;transform:translateX(-50%);max-width:90%;" +
      "background:#fff3bf;color:#5c3c00;border:1px solid #f0c36d;border-radius:8px;padding:8px 12px;" +
      "font:13px/1.4 system-ui,-apple-system,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.2)";
    d.textContent = "Part of this page didn't load (" + failed.join(", ") + "). Check the connection and reload the page.";
    document.body.appendChild(d);
  }

  const parsed = () => document.readyState !== "loading" ? Promise.resolve()
    : new Promise(r => document.addEventListener("DOMContentLoaded", r, {once: true}));

  function StreamsLoad(names, done) {
    const got = names.map(get);
    got.forEach(p => p.catch(() => {}));            // handled in run(), in order
    return parsed().then(async () => {
      const failed = [];
      for (let i = 0; i < names.length; i++) if (!(await run(names[i], got[i]))) failed.push(names[i]);
      if (failed.length) note(failed);
      if (done) try { done(failed); } catch (e) { setTimeout(() => { throw e; }); }   // reported as the page's error
      return failed;
    });
  }
  StreamsLoad.script = name => run(name, get(name)).then(ok => { if (!ok) throw new Error(name + " did not load"); });
  StreamsLoad.prefetch = names => names.forEach(n => { if (!pending[n]) (pending[n] = fetchGz(n)).catch(() => {}); });
  StreamsLoad.times = times;
  window.StreamsLoad = StreamsLoad;
})();
