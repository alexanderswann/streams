// Land ownership on the map pages. The user, 2026-11-24: "add another overlay layer that specifically shows public
// land, private but ngo/open/ non profit land, and strictly private. include land owner names and their contact info";
// 2026-11-25: "the land ownership layer is horrible, i want names of owners, clearly private land, clearly public land
// etc". Look A, the user's pick of three iPhone mockups: public land solid green, conservation land teal, tribal land
// violet, private land red stripes with a red edge, a key in plain words, names written on the land once zoomed in.
// 11c_land.py writes a map's pieces of land to land_data.js (window.LAND); 11d_parcels.py writes the private parcels
// beside its streams and lakes, with their owners' names, to parcels_data.js (window.PARCELS). A page loads the first
// when the layer is turned on and the second once zoomed in to PZ with the layer on. Every name says where it comes
// from and as of when. A private owner gets no phone, e-mail or address: the popup links the county's official
// record, opened at the spot. 06_map.py inlines this file in both pages: landLeaflet(map, ctrl) on the 2D map,
// landMaplibre(map, D) on the 3D map, whose hover and popups call landTip(), landPopup(), landParcelTip() and
// landParcelPopup().
(function () {
  const CLS = [
    {c: "#2f9e44", e: "#2b8a3e", f: 0.42, t: "Public land", w: "open to everyone (rules apply)", lc: "#1e6b30"},
    {c: "#1098ad", e: "#0b7285", f: 0.42, t: "Conservation land", w: "open to the public; check its rules", lc: "#0b7285"},
    {c: "#7048e8", e: "#5f3dc4", f: 0.38, t: "Tribal land", w: "the tribe's rules apply", lc: "#5f3dc4"},
    {c: "#e03131", e: "#e03131", f: 1, t: "Private land", w: "ask the owner", lc: "#c92a2a"}];
  const FLAG = "#c92a2a", PZ = 13, LZ = 13, OZ = 15;   // parcels from zoom PZ, holdings' names from LZ, owners' from OZ
  const STRIPES = "repeating-linear-gradient(135deg,#e03131 0 2px,#ffe3e3 2px 5px)";
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const lbl = () => window.LBL || (window.MAP3D || {}).lbl || {};
  let D = null, P = null, waitL = null, waitP = null;
  function script(src, ok, no) {
    const s = document.createElement("script");
    s.src = src;
    s.onload = ok;
    s.onerror = () => { s.remove(); no(new Error(src + " did not load")); };
    document.head.appendChild(s);
  }
  function load() {
    if (!D && window.LAND) D = window.LAND;
    if (D) return Promise.resolve(D);
    return waitL || (waitL = new Promise((ok, no) => script("land_data.js",
      () => { D = window.LAND || null; if (D) ok(D); else { waitL = null; no(new Error("no land data")); } },
      e => { waitL = null; no(e); })));
  }
  // the parcels: none on a map whose counties publish no owner names (no file); tried again on the next zoom if missing
  function loadParcels() {
    if (!P && window.PARCELS) P = window.PARCELS;
    if (P) return Promise.resolve(P);
    return waitP || (waitP = new Promise(ok => script("parcels_data.js",
      () => { P = window.PARCELS || null; if (!P) waitP = null; ok(P); },
      () => { waitP = null; ok(null); })));
  }
  // a ring as Google's encoded polyline (1e-5 degrees, 11c_land.py and 11d_parcels.py): [[lat, lon], ...]
  function dec(str) {
    const out = [];
    let lat = 0, lon = 0;
    for (let i = 0; i < str.length;) {
      let b, sh = 0, r = 0;
      do { b = str.charCodeAt(i++) - 63; r |= (b & 31) << sh; sh += 5; } while (b >= 32);
      lat += r & 1 ? ~(r >> 1) : r >> 1;
      sh = 0; r = 0;
      do { b = str.charCodeAt(i++) - 63; r |= (b & 31) << sh; sh += 5; } while (b >= 32);
      lon += r & 1 ? ~(r >> 1) : r >> 1;
      out.push([lat / 1e5, lon / 1e5]);
    }
    return out;
  }
  // private land's stripes: red on a pale red, 10 px repeat (a canvas pattern on the 2D map, an image on the 3D map)
  function stripesCanvas(px) {
    const c = document.createElement("canvas");
    c.width = c.height = 10 * px;
    const x = c.getContext("2d");
    x.scale(px, px);
    x.fillStyle = "rgba(255,227,227,0.38)"; x.fillRect(0, 0, 10, 10);
    x.strokeStyle = "rgba(224,49,49,0.85)"; x.lineWidth = 2.4; x.lineCap = "square";
    x.beginPath(); x.moveTo(-1, 11); x.lineTo(11, -1); x.moveTo(-1, 1); x.lineTo(1, -1); x.moveTo(9, 11); x.lineTo(11, 9); x.stroke();
    return c;
  }
  const S = i => (i === undefined || i === null || !D) ? "" : D.s[i] || "";
  const arr = v => typeof v === "string" ? JSON.parse(v) : v || [];    // MapLibre hands nested values over as JSON
  const tel = ph => ph ? `<a href="tel:${esc(String(ph).replace(/[^\d+]/g, ""))}">${esc(ph)}</a>` : "";
  const row = (a, b) => b ? `<tr><td>${a}</td><td>${b}</td></tr>` : "";
  const swatch = c => `<i style="display:inline-block;width:15px;height:11px;border-radius:2px;margin-right:6px;vertical-align:-1px;` +
    `background:${c === 3 ? STRIPES : (CLS[c] || CLS[3]).c};border:1px solid ${(CLS[c] || CLS[3]).e};box-sizing:border-box"></i>`;
  function accessText(p) {
    const fl = arr(p.g).map(i => D.g[i]);
    if (fl.length)    // 11_context.py's restricted holdings: what a creek's popup there says
      return fl.map(([st, unit, asof]) => `<span class="warn">⚠ ${esc(st)}${unit ? ": " + esc(unit) : ""}${asof ? " " + esc(asof) : ""}</span>`).join("<br>");
    // PAD-US's restricted (RA) land that 11_context.py doesn't flag is public land open on foot (its rule)
    return {OA: "Open to the public", RA: p.c === 0 ? "Open on foot; rules on use apply (a licence, pass, season or zone)"
                                                    : "Restricted: by permit, registration or set hours",
            L: "On the lake: in the lake's own popup (Lakes layer)",       // 05d_lakes.py's rule, not 11_context.py's
            XA: "<span class='warn'>Closed to the public</span>", UK: "Public access not recorded"}[p.a] ||
           "Private: ask the owner before you cross it";
  }
  // the county's official parcel map, opened at the spot where its viewer allows it: where an owner's record is
  function record(y, lat, lon, label, text) {
    const c = y !== undefined && y !== null && D ? D.y[y] : null;
    if (!c) return "";
    const [county, name, url, at] = c;
    if (!url) return row(label, `In the land records of the town or county assessor (${esc(county)})`);
    const href = at ? at.replace("{lat}", lat.toFixed(6)).replace("{lon}", lon.toFixed(6)) : url;
    return row(label, `${text ? esc(text) + " " : ""}<a href="${esc(href)}" target="_blank" rel="noopener">${esc(name || county + " parcel viewer")} ↗</a>` +
                      `<div class="dm">The official parcel map for ${esc(county)}${at ? ", opened at this spot" : ""}</div>`);
  }
  // the popup for piece p tapped at lat, lon (both maps)
  function popup(p, lat, lon) {
    if (!D) return "";
    const k = CLS[p.c] || CLS[3], easement = !!p.e, name = S(p.n), own = S(p.o);
    const title = p.c === 3 ? (easement ? "Private land under a conservation easement" : "Private land") : k.t;
    const o = p.k !== undefined && p.k !== null ? D.o[p.k] : null;
    const contact = o ? `<a href="${esc(o[1])}" target="_blank" rel="noopener">${esc(o[0])} ↗</a>` + (o[2] ? `<br>${tel(o[2])}` : "") : "";
    // (<strong>, not <b>: the phone placement, map_phone.js and map3d.html, keeps the part down to a popup's first <b>
    // in view; here all of it is what matters, the owner and the record at its foot)
    return `<div class="pp lp"><strong>${swatch(p.c)}${esc(title)}</strong>` +
      (p.c === 3 ? `<div class="dw">Ask the owner before you fish or cross it</div>` : "") +
      (name ? `<div class="dw">${esc(name)}</div>` : "") + `<table>` +
      row("Owner", own ? `${esc(own)} <span class="dm">(${esc(D.src)})</span>` : "") +
      row(own ? "Managed by" : "Manager", esc(S(p.m))) +
      (easement ? row("Easement", p.h !== undefined && p.h !== null ? "Held by " + esc(S(p.h)) : "A conservation easement") : "") +
      row("Kind", esc(S(p.d))) + (p.c === 3 && !p.a && !arr(p.g).length ? "" : row("Access", accessText(p))) +
      row("Contact", contact) +
      (p.c === 3 ? record(p.y, lat, lon, own ? "Record" : "Owner", own ? "" : "Look it up in") : "") +
      `</table><div class="dm">Names and outlines: ${esc(D.src)}; outlines are approximate, not a survey</div></div>`;
  }
  function tip(p) {
    if (!D) return "";
    const k = CLS[p.c] || CLS[3], n = S(p.n) || S(p.o) || S(p.m) || S(p.h);
    return `<b>${esc(p.c === 3 ? (p.e ? "Private: conservation easement" : "Private land: ask the owner") : k.t)}</b>${n ? "<br>" + esc(n) : ""}` +
           (arr(p.g).length ? `<br><span class="warn">⚠ ${esc(D.g[arr(p.g)[0]][0])}</span>` : "");
  }
  // a parcel's popup: q is {n: its owner's name (an index), src, y: its county}, tapped at lat, lon
  function parcelPopup(q, lat, lon) {
    if (!P) return "";
    const nm = P.s[q.n] || "", s = P.src[q.src] || [], [ds, pub, lic, asof, terms] = s;
    return `<div class="pp lp"><strong>${swatch(3)}Private land</strong><div class="dw">Ask the owner before you fish or cross it</div><table>` +
      row("Owner", nm ? esc(nm) : `<span class="dm">Withheld by law at the owner's request</span>`) +
      row("Source", `${esc(ds)} (${esc(pub)})${asof ? ", as of " + esc(asof) : ""}` +
                    `<div class="dm">${terms ? `<a href="${esc(terms)}" target="_blank" rel="noopener">${esc(lic)} ↗</a>` : esc(lic)}</div>`) +
      record(q.y, lat, lon, "Record", "") +
      `</table><div class="dm">Parcel lines are approximate, not a survey</div></div>`;
  }
  const parcelTip = q => P ? `<b>Private land: ask the owner</b><br>${esc(P.s[q.n] || "Owner withheld by law")}` : "";
  // the key, in plain words: in a map's legend while the layer is on (and on the 2D map a copy of its own while the
  // legend is folded)
  const keyHtml = () => `<div class="landkey" style="margin-top:6px;border-top:1px solid #eee;padding-top:6px;font-size:12px;line-height:1.55">` +
    `<div class="dm" style="margin-bottom:2px">Who owns the land</div>` +
    CLS.map((k, i) => `<div>${swatch(i)}<b>${k.t}</b>: ${k.w}</div>`).join("") +
    `<div><svg width="15" height="11" style="vertical-align:-1px;margin-right:6px"><rect x="1" y="1" width="13" height="9" fill="none" stroke="${FLAG}" stroke-width="1.8" stroke-dasharray="3 2"/></svg>No public access or restricted</div>` +
    `<div class="dm">Owners' names once zoomed in, from county and state records; tap the land for the source</div></div>`;
  function showKey(parent, on) {
    if (!parent) return;
    let el = parent.querySelector(".landkey");
    if (on && !el) { parent.insertAdjacentHTML("beforeend", keyHtml()); el = parent.querySelector(".landkey"); }
    if (el) el.style.display = on ? "block" : "none";
  }
  // label spots in view, without overlaps, most important first: [{lat, lon, t, col, big}] -> the ones that fit
  function fit(cands, toPt, max) {
    const boxes = [], out = [];
    for (const c of cands) {
      const p = toPt(c), w = c.t.length * (c.big ? 6.8 : 6.2) + 10, h = 15;
      const b = [p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2];
      if (boxes.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])) continue;
      boxes.push(b); out.push(c);
      if (out.length >= max) break;
    }
    return out;
  }

  // ---- the 2D map (Leaflet): the entry 06_map.py made (an empty group) fills on its first use ----
  window.landLeaflet = function (map, ctrl) {
    const LB = lbl();
    if (!LB.land || typeof layerKey2d !== "function") return;
    const ent = ctrl._layers.find(o => o.overlay && layerKey2d(o.name, LB) === "land");
    if (!ent) return;
    const group = ent.layer, legend = () => document.querySelector(".lgd .lb");
    const pieces = [], shownTiles = new Map(), labels = L.layerGroup();
    let drawn = false, pat = null, tiles = null, keyCtl = null, raf = 0, popped = false;
    // the land under everything else drawn (the shared canvas draws in order): pieces at the bottom, parcels on them
    const sink = () => { shownTiles.forEach(ps => ps.forEach(p => p.bringToBack())); pieces.forEach(p => p.bringToBack()); };
    const draw = () => load().then(() => {
      if (drawn) return;
      drawn = true;
      pat = pat || stripesCanvas(1).getContext("2d").createPattern(stripesCanvas(1), "repeat");
      D.f.forEach(p => {
        const k = CLS[p.c] || CLS[3], priv = p.c === 3;
        const poly = L.polygon(p.r.map(q => q.map(dec)), {color: p.g ? FLAG : k.e, weight: p.g ? 1.8 : priv ? 1.4 : 1,
          opacity: 0.9, dashArray: p.g ? "5 4" : null, fillColor: priv ? pat : k.c, fillOpacity: k.f});
        poly.on("click", e => L.popup({maxWidth: 300}).setLatLng(e.latlng).setContent(popup(p, e.latlng.lat, e.latlng.lng)).openOn(map));
        if (!L.Browser.mobile) poly.bindTooltip(() => tip(p), {sticky: true, direction: "top", offset: [0, -6]});
        group.addLayer(poly);
        pieces.push(poly);
      });
      sink();
      update();
    }).catch(() => {
      group.addLayer(L.marker(map.getCenter(), {icon: L.divIcon({className: "", html: "<div class='dm' style='background:#fff;padding:3px 6px;border-radius:6px;width:180px'>The land layer didn't load (no connection?)</div>"})}));
    });
    // parcels, by tiles of 0.05 degrees, drawn only in and around the view once zoomed in to PZ
    const tkey = (la, lo) => Math.floor(la * 20) + ":" + Math.floor(lo * 20);
    function showParcels() {
      if (!P) return;
      if (!tiles) {
        tiles = new Map();
        P.f.forEach((f, i) => { const k = tkey(f[1] / 1e5, f[2] / 1e5); (tiles.get(k) || tiles.set(k, []).get(k)).push(i); });
      }
      const b = map.getBounds().pad(0.4), want = new Set();
      for (let la = Math.floor(b.getSouth() * 20); la <= Math.floor(b.getNorth() * 20); la++)
        for (let lo = Math.floor(b.getWest() * 20); lo <= Math.floor(b.getEast() * 20); lo++) want.add(la + ":" + lo);
      shownTiles.forEach((ps, k) => { if (!want.has(k)) { ps.forEach(p => group.removeLayer(p)); shownTiles.delete(k); } });
      want.forEach(k => {
        if (shownTiles.has(k) || !tiles.has(k)) return;
        shownTiles.set(k, tiles.get(k).map(i => {
          const f = P.f[i], q = {n: f[3], src: f[4], y: f[5]};
          const poly = L.polygon(f[0].map(r => r.map(dec)), {color: FLAG, weight: 0.9, opacity: 0.85, fill: true, fillOpacity: 0});
          poly.on("click", e => L.popup({maxWidth: 300}).setLatLng(e.latlng).setContent(parcelPopup(q, e.latlng.lat, e.latlng.lng)).openOn(map));
          if (!L.Browser.mobile) poly.bindTooltip(() => parcelTip(q), {sticky: true, direction: "top", offset: [0, -6]});
          group.addLayer(poly);
          return poly;
        }));
      });
      sink();
    }
    function hideParcels() { shownTiles.forEach(ps => ps.forEach(p => group.removeLayer(p))); shownTiles.clear(); }
    // names on the land: holdings' from LZ, private owners' from OZ
    function writeNames() {
      labels.clearLayers();
      const z = map.getZoom();
      if (!D || z < LZ || !map.hasLayer(group)) return;
      const b = map.getBounds(), seen = new Set(), cands = [];
      D.f.forEach(p => {
        const t = S(p.n) || S(p.o);
        if (!t || !p.l) return;
        p.l.forEach(([la, lo]) => {
          const ll = [la / 1e5, lo / 1e5];
          if (!b.contains(ll) || seen.has(t)) return;
          seen.add(t);
          cands.push({ll, t, col: (CLS[p.c] || CLS[3]).lc, big: p.c !== 3});
        });
      });
      if (P && z >= OZ) shownTiles.forEach((ps, k) => tiles.get(k).forEach(i => {
        const f = P.f[i], t = P.s[f[3]], ll = [f[1] / 1e5, f[2] / 1e5];
        if (t && b.contains(ll)) cands.push({ll, t, col: FLAG});
      }));
      fit(cands, c => map.latLngToContainerPoint(c.ll), 90).forEach(c => labels.addLayer(L.marker(c.ll, {interactive: false,
        icon: L.divIcon({className: "", iconSize: null, html: `<div style="transform:translate(-50%,-50%);white-space:nowrap;` +
          `pointer-events:none;font:${c.big ? 600 : 600} ${c.big ? 12 : 11.5}px -apple-system,system-ui,sans-serif;color:${c.col};` +
          `text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 2px #fff,0 0 2px #fff">${esc(c.t)}</div>`})})));
    }
    function update() {
      if (!map.hasLayer(group)) return;
      if (map.getZoom() >= PZ) loadParcels().then(() => { showParcels(); writeNames(); });
      else { hideParcels(); writeNames(); }
    }
    // the key of its own while the legend is folded (a phone's usual state), above it
    const KeyCtl = L.Control.extend({options: {position: "bottomleft"}, onAdd() {
      const d = L.DomUtil.create("div", "landkey-float");
      d.style.cssText = "background:rgba(255,255,255,.95);border-radius:8px;padding:4px 9px 6px;box-shadow:0 1px 5px rgba(0,0,0,.3);max-width:260px";
      d.innerHTML = keyHtml().replace("margin-top:6px;border-top:1px solid #eee;padding-top:6px;", "");
      L.DomEvent.disableClickPropagation(d);
      return d;
    }});
    function syncKey() {
      const lg = document.querySelector(".lgd"), on = map.hasLayer(group), folded = !lg || lg.classList.contains("min");
      showKey(legend(), on);
      if (on && folded && !popped) { if (!keyCtl) keyCtl = new KeyCtl().addTo(map); }
      else if (keyCtl) { keyCtl.remove(); keyCtl = null; }
    }
    const lgd = document.querySelector(".lgd");
    if (lgd && window.MutationObserver) new MutationObserver(syncKey).observe(lgd, {attributes: true, attributeFilter: ["class"]});
    map.on("overlayadd overlayremove", e => {
      if (e.layer !== group) return;
      syncKey();
      if (e.type === "overlayadd") { labels.addTo(map); update(); } else labels.remove();
    });
    map.on("moveend zoomend", () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(update); });
    map.on("popupopen popupclose", e => { popped = e.type === "popupopen"; syncKey(); });   // a popup gets the room
    group.on("add", draw);
    if (map.hasLayer(group)) { draw(); labels.addTo(map); syncKey(); }
  };

  // ---- the 3D map (MapLibre): empty sources filled on first use; returns the overlay entry's layers and loader ----
  window.landMaplibre = function (map, D3) {
    if (!((D3 || {}).lbl || {}).land) return null;
    const by = vals => ["match", ["get", "c"], 0, vals[0], 1, vals[1], 2, vals[2], vals[3]];
    const none = () => ({type: "FeatureCollection", features: []});
    const st = stripesCanvas(2);
    if (!map.hasImage("land-stripes")) map.addImage("land-stripes", st.getContext("2d").getImageData(0, 0, st.width, st.height), {pixelRatio: 2});
    const vis = {visibility: "none"}, font = ["Noto Sans Medium"];
    ["land", "parcels", "land-lbl", "parcels-lbl"].forEach(s => map.addSource(s, {type: "geojson", data: none()}));
    map.addLayer({id: "land", type: "fill", source: "land", filter: ["!=", ["get", "c"], 3], layout: vis,
                  paint: {"fill-color": by(CLS.map(k => k.c)), "fill-opacity": by(CLS.map(k => k.f))}});
    map.addLayer({id: "land-p", type: "fill", source: "land", filter: ["==", ["get", "c"], 3], layout: vis,
                  paint: {"fill-pattern": "land-stripes"}});
    map.addLayer({id: "land-o", type: "line", source: "land", filter: ["!", ["has", "g"]], layout: vis,
                  paint: {"line-color": by(CLS.map(k => k.e)), "line-width": ["case", ["==", ["get", "c"], 3], 1.4, 1], "line-opacity": 0.9}});
    map.addLayer({id: "land-g", type: "line", source: "land", filter: ["has", "g"], layout: vis,
                  paint: {"line-color": FLAG, "line-width": 1.8, "line-dasharray": [3, 2]}});
    map.addLayer({id: "parcels-f", type: "fill", source: "parcels", minzoom: PZ, layout: vis,
                  paint: {"fill-color": "#e03131", "fill-opacity": 0.01}});
    map.addLayer({id: "parcels-o", type: "line", source: "parcels", minzoom: PZ, layout: vis,
                  paint: {"line-color": FLAG, "line-width": 0.9, "line-opacity": 0.85}});
    const text = (size) => ({...vis, "text-field": ["get", "t"], "text-font": font, "text-size": size, "text-max-width": 10,
                             "text-padding": 3, "symbol-sort-key": ["get", "r"]});
    const halo = {"text-color": ["get", "col"], "text-halo-color": "#fff", "text-halo-width": 1.6};
    map.addLayer({id: "land-l", type: "symbol", source: "land-lbl", minzoom: LZ, layout: text(12), paint: halo});
    map.addLayer({id: "parcels-l", type: "symbol", source: "parcels-lbl", minzoom: OZ, layout: text(11.5), paint: halo});
    let filled = false, fillingP = false, filledP = false, on = false;
    const legend = () => document.querySelector("#legend .pb");
    const close = r => { const c = r.map(([la, lo]) => [lo, la]); c.push(c[0]); return c; };
    function fillParcels() {
      if (filledP || fillingP || map.getZoom() < PZ - 1) return;
      fillingP = true;
      loadParcels().then(() => {
        fillingP = false;
        if (!P) return;
        filledP = true;
        map.getSource("parcels").setData({type: "FeatureCollection", features: P.f.map(f => ({type: "Feature",
          properties: {n: f[3], src: f[4], y: f[5]}, geometry: {type: "MultiPolygon", coordinates: f[0].map(pl => pl.map(s => close(dec(s))))}}))});
        map.getSource("parcels-lbl").setData({type: "FeatureCollection", features: P.f.filter(f => P.s[f[3]]).map(f => ({type: "Feature",
          properties: {t: P.s[f[3]], col: FLAG, r: 1}, geometry: {type: "Point", coordinates: [f[2] / 1e5, f[1] / 1e5]}}))});
      });
    }
    map.on("zoomend", () => { if (on) fillParcels(); });
    return {
      ids: ["land", "land-p", "land-o", "land-g", "parcels-f", "parcels-o", "land-l", "parcels-l"],
      shown(v) {
        on = v;
        showKey(legend(), v);
        if (!v) return;
        fillParcels();
        if (filled) return;
        load().then(() => {
          filled = true;
          map.getSource("land").setData({type: "FeatureCollection", features: D.f.map(p => {
            const {r, l, ...q} = p;
            return {type: "Feature", properties: q, geometry: {type: "MultiPolygon", coordinates: r.map(pl => pl.map(s => close(dec(s))))}};
          })});
          const pts = [];
          D.f.forEach(p => { const t = S(p.n) || S(p.o); if (t && p.l) p.l.forEach(([la, lo]) => pts.push({type: "Feature",
            properties: {t, col: (CLS[p.c] || CLS[3]).lc, r: p.c === 3 ? 2 : 0}, geometry: {type: "Point", coordinates: [lo / 1e5, la / 1e5]}})); });
          map.getSource("land-lbl").setData({type: "FeatureCollection", features: pts});
        }).catch(() => {});
      },
    };
  };
  window.landPopup = popup;
  window.landTip = tip;
  window.landParcelPopup = parcelPopup;
  window.landParcelTip = parcelTip;
})();
