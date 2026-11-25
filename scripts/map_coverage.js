// Cell coverage on the map pages (the user, 2026-11-25, a feature of onWater's: where each carrier has signal, to know
// where to save an offline map before heading out). 11e_coverage.py writes a map's coverage to coverage_data.js
// (window.CELL): each carrier's 4G LTE or 5G-NR outdoors from the FCC's National Broadband Map, drawn on the FCC's own
// hexagons, and their union for "any carrier". A page loads it the first time the layer is turned on. A picker in the
// legend (and in a box of its own while the legend is folded) shows one carrier at a time, or any. With the layer on, a
// tap on the map where nothing else is says each carrier's signal there, and the other popups end with a line saying
// the same. 06_map.py puts this file in both pages: cellLeaflet(map, ctrl) on the 2D map; cellMaplibre(map, D) on the 3D
// map, whose click handler calls cellSpot() and cellNote().
(function () {
  const FILL = "#fab005", EDGE = "#f08c00", OP = 0.28;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const lbl = () => window.LBL || (window.MAP3D || {}).lbl || {};
  let C = null, wait = null, pick = "any", on = false, failed = false;
  const subs = [];                       // the page's redraw, called when the picked carrier changes
  function load() {
    if (!C && window.CELL) C = window.CELL;
    if (C) return Promise.resolve(C);
    return wait || (wait = new Promise((ok, no) => {
      const s = document.createElement("script");
      s.src = "coverage_data.js";
      s.onload = () => { C = window.CELL || null; if (C) { failed = false; ok(C); } else { wait = null; failed = true; no(new Error("no coverage data")); } };
      s.onerror = () => { s.remove(); wait = null; failed = true; no(new Error("coverage_data.js did not load")); };
      document.head.appendChild(s);
    }));
  }
  // a ring as Google's encoded polyline at 1e-4 degrees (11e_coverage.py): [[lat, lon], ...]
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
      out.push([lat / 1e4, lon / 1e4]);
    }
    return out;
  }
  const set = k => k === "any" ? C.any : C.c.find(c => c.id === k) || C.any;
  // each set's polygons decoded once: [{b: [s, w, n, e] of the outer ring, r: [[[lat, lon], ...], holes...]}]
  const cache = {};
  function polys(k) {
    if (!cache[k]) cache[k] = set(k).r.map(p => {
      const r = p.map(dec), b = [90, 180, -90, -180];       // (a loop: a ring of 100,000 points is too many arguments)
      for (const [la, lo] of r[0]) { if (la < b[0]) b[0] = la; if (lo < b[1]) b[1] = lo; if (la > b[2]) b[2] = la; if (lo > b[3]) b[3] = lo; }
      return {b, r};
    });
    return cache[k];
  }
  function inRing(lat, lon, ring) {
    let c = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [ya, xa] = ring[i], [yb, xb] = ring[j];
      if ((ya > lat) !== (yb > lat) && lon < (xb - xa) * (lat - ya) / (yb - ya) + xa) c = !c;
    }
    return c;
  }
  const covered = (k, lat, lon) => polys(k).some(p => lat >= p.b[0] && lat <= p.b[2] && lon >= p.b[1] && lon <= p.b[3] &&
    inRing(lat, lon, p.r[0]) && !p.r.slice(1).some(h => inRing(lat, lon, h)));
  const short = n => String(n).replace(/,?\s+(Inc|LLC|Corp|Corporation|Co)\.?$/i, "");
  const at = (lat, lon) => C.c.map(c => [short(c.n), covered(c.id, lat, lon)]);
  const src = () => `Derived from FCC National Broadband Map data as of ${esc(C.asof)}` +
    (C.stale ? ` (list as of ${esc(C.stale)})` : "");
  // a popup's last line (on), or the whole popup for a tap where nothing else is (full)
  function note(lat, lon, full) {
    if (!on || !C) return "";
    const rows = at(lat, lon);
    if (full)
      return `<div class="pp cellpop"><b>Cell signal here</b><div class="dw">4G LTE or 5G outdoors, as each carrier reports it</div><table>` +
        rows.map(([n, y]) => `<tr><td>${esc(n)}</td><td>${y ? "<b style='color:#2b8a3e'>4G</b>" : "<span class='warn'>none</span>"}</td></tr>`).join("") +
        `</table><div class="dm">${src()}. The carriers' models, not a measurement: the signal on the ground can be better or worse.</div></div>`;
    return `<div class="cellnote dm" style="margin-top:5px;border-top:1px solid #eee;padding-top:4px">📶 Signal here (FCC, outdoors): ` +
      rows.map(([n, y]) => `${esc(n)} ${y ? "<b style='color:#2b8a3e'>4G</b>" : "none"}`).join(" · ") + `</div>`;
  }
  // the key and the picker: in the legend while the layer is on, and alone (compact) while the legend is folded
  const swatch = `<i style="display:inline-block;width:15px;height:11px;border-radius:2px;margin-right:6px;vertical-align:-1px;` +
    `background:${FILL};opacity:.75;border:1px solid ${EDGE};box-sizing:border-box"></i>`;
  // the picker's entries: any carrier, then each carrier, with its share of the map (11e_coverage.py's order: biggest first)
  const options = () => [["any", "Any carrier", C.any.p]].concat(C.c.map(c => [c.id, short(c.n), c.p]))
    .map(([k, n, p]) => `<option value="${esc(k)}"${k === pick ? " selected" : ""}>${esc(n)} · ${p >= 1 ? Math.round(p) : "<1"} % of the map</option>`).join("");
  const sel = `font:inherit;font-size:12px;max-width:100%;border:1px solid #c9ced6;border-radius:5px;background:#fff;color:#1d1d1f;padding:1px 2px`;
  function keyHtml(compact) {
    if (!C) return `<div class="dm">${failed ? "The cell coverage layer didn't load (no connection?)" : "Cell coverage: loading…"}</div>`;
    if (compact)
      return `<div style="display:flex;align-items:center;gap:4px;white-space:nowrap">${swatch}<select class="cellpick" style="${sel};max-width:180px">${options()}</select>` +
        `<span class="dm" style="font-size:11px">4G/5G · FCC ${esc(C.asof.replace(/ \d+,/, ""))}</span></div>`;
    return `<div style="display:flex;align-items:center;gap:2px">${swatch}<b style="margin-right:4px;white-space:nowrap">Cell signal</b>` +
      `<select class="cellpick" style="${sel}">${options()}</select></div>` +
      `<div style="margin-top:3px"><b>Shaded</b>: 4G LTE or 5G outdoors, as each carrier reports it; <b>not shaded</b>: ` +
      `weak or no signal. Tap the map for each carrier.</div>` +
      `<div class="dm" style="margin-top:2px;font-size:11px">${src()}: the carriers' models, not measured; cells about ` +
      `1,100 ft across.` + (C.out || []).map(o => ` Left out, as most phones can't use it: ${esc(short(o.n))} ` +
      `(${o.p >= 1 ? Math.round(o.p) : "<1"} % of the map), ${esc(o.why)}.`).join("") +
      ` This product uses the FCC Data API but is not endorsed or certified by the FCC.</div>`;
  }
  function bindKey(el) {
    el.querySelectorAll(".cellpick").forEach(s => { s.onchange = () => setPick(s.value); });
  }
  function setPick(k) {
    pick = k;
    document.querySelectorAll(".cellpick").forEach(s => { s.value = k; });
    subs.forEach(f => f());
  }
  // the key inside a legend (parent), shown while the layer is on
  function showKey(parent, show) {
    if (!parent) return;
    let el = parent.querySelector(".cellkey");
    if (show && !el) {
      parent.insertAdjacentHTML("beforeend", `<div class="cellkey" style="margin-top:6px;border-top:1px solid #eee;padding-top:6px;font-size:12px;line-height:1.45"></div>`);
      el = parent.querySelector(".cellkey");
    }
    if (!el) return;
    if (show) { el.innerHTML = keyHtml(false); bindKey(el); }
    el.style.display = show ? "block" : "none";
  }

  // ---- the 2D map (Leaflet): the entry 06_map.py made (an empty group) fills on its first use ----
  window.cellLeaflet = function (map, ctrl) {
    const LB = lbl();
    if (!LB.cell || typeof layerKey2d !== "function") return;
    const ent = ctrl._layers.find(o => o.overlay && layerKey2d(o.name, LB) === "cell");
    if (!ent) return;
    const group = ent.layer, drawn = {};
    let keyCtl = null, popped = false, hadPopup = false;
    const legend = () => document.querySelector(".lgd .lb");
    function draw() {
      if (!on || !C) return;
      group.clearLayers();
      const k = pick;
      drawn[k] = drawn[k] || L.polygon(polys(k).map(p => p.r), {color: EDGE, weight: 0.8, opacity: 0.7, fillColor: FILL,
                                                                 fillOpacity: OP, interactive: false});
      group.addLayer(drawn[k]);
      drawn[k].bringToBack();
    }
    subs.push(draw);
    // the key of its own while the legend is folded (a phone's usual state), above it
    const KeyCtl = L.Control.extend({options: {position: "bottomleft"}, onAdd() {
      const d = L.DomUtil.create("div", "cellkey-float");
      d.style.cssText = "background:rgba(255,255,255,.95);border-radius:8px;padding:3px 7px;box-shadow:0 1px 5px rgba(0,0,0,.3);font-size:12px";
      d.innerHTML = keyHtml(true);
      bindKey(d);
      L.DomEvent.disableClickPropagation(d);
      L.DomEvent.disableScrollPropagation(d);
      return d;
    }});
    function syncKey() {
      const lg = document.querySelector(".lgd"), folded = !lg || lg.classList.contains("min");
      showKey(legend(), on);
      if (on && folded && !popped && C) { if (!keyCtl) keyCtl = new KeyCtl().addTo(map); }
      else if (keyCtl) { keyCtl.remove(); keyCtl = null; }
    }
    const lgd = document.querySelector(".lgd");
    if (lgd && window.MutationObserver) new MutationObserver(syncKey).observe(lgd, {attributes: true, attributeFilter: ["class"]});
    function show(v) {
      on = v;
      if (!v) { syncKey(); return; }
      load().then(() => { draw(); syncKey(); }).catch(() => {
        on = false;
        syncKey();
        L.popup({maxWidth: 220}).setLatLng(map.getCenter()).setContent("<div class='dm'>The cell coverage layer didn't load (no connection?)</div>").openOn(map);
      });
      syncKey();
    }
    map.on("overlayadd overlayremove", e => { if (e.layer === group) show(e.type === "overlayadd"); });
    // a tap where nothing else is: each carrier's signal there. A tap that only closes an open popup opens none.
    map.on("preclick", () => { hadPopup = !!map.getContainer().querySelector(".leaflet-popup"); });
    map.on("click", e => {
      if (!on || !C || hadPopup) return;
      const p = L.popup({maxWidth: 260}).setLatLng(e.latlng).setContent(note(e.latlng.lat, e.latlng.lng, true));
      p._cell = true;
      p.openOn(map);
    });
    // the other popups end with a line saying the same
    map.on("popupopen", e => {
      popped = true;
      syncKey();
      if (!on || !C || e.popup._cell) return;
      const el = e.popup.getElement(), c = el && el.querySelector(".leaflet-popup-content"), ll = e.popup.getLatLng();
      if (!c || !ll || c.querySelector(".cellnote")) return;
      c.insertAdjacentHTML("beforeend", note(ll.lat, ll.lng, false));
      // its size and place again, not its content: update() would build a reach's popup anew, without the line
      if (e.popup._updateLayout) { e.popup._updateLayout(); e.popup._updatePosition(); }
    });
    map.on("popupclose", () => { popped = false; setTimeout(syncKey); });
    if (map.hasLayer(group)) show(true);
  };

  // ---- the 3D map (MapLibre): an empty source filled on first use; returns the overlay entry's layers ----
  window.cellMaplibre = function (map, D3) {
    if (!((D3 || {}).lbl || {}).cell) return null;
    const none = () => ({type: "FeatureCollection", features: []});
    map.addSource("cell", {type: "geojson", data: none()});
    const under = map.getLayer("fork-fill") ? "fork-fill" : undefined;      // under the drainages, lakes and streams
    map.addLayer({id: "cell", type: "fill", source: "cell", layout: {visibility: "none"},
                  paint: {"fill-color": FILL, "fill-opacity": OP}}, under);
    map.addLayer({id: "cell-o", type: "line", source: "cell", layout: {visibility: "none"},
                  paint: {"line-color": EDGE, "line-width": 0.8, "line-opacity": 0.7}}, under);
    const close = r => { const c = r.map(([la, lo]) => [lo, la]); c.push(c[0]); return c; };
    const fill = () => {
      if (!C) return;
      map.getSource("cell").setData({type: "FeatureCollection", features: [{type: "Feature", properties: {},
        geometry: {type: "MultiPolygon", coordinates: polys(pick).map(p => p.r.map(close))}}]});
    };
    subs.push(fill);
    const legend = () => document.querySelector("#legend .pb"), panel = () => document.getElementById("legend");
    let box = null;
    function syncKey() {
      showKey(legend(), on);
      const lg = panel(), folded = lg && lg.classList.contains("min"), want = on && folded && C;
      if (want && !box) {
        box = document.createElement("div");
        box.className = "panel cellkey-float";
        box.style.cssText = "left:10px;padding:4px 8px;font-size:12px";
        box.innerHTML = keyHtml(true);
        bindKey(box);
        document.body.appendChild(box);
      } else if (!want && box) { box.remove(); box = null; }
      if (box && lg) box.style.bottom = (window.innerHeight - lg.getBoundingClientRect().top + 6) + "px";
    }
    if (panel() && window.MutationObserver) new MutationObserver(syncKey).observe(panel(), {attributes: true, attributeFilter: ["class"]});
    window.addEventListener("resize", syncKey);
    // the layer panel switches the layers' visibility (and so does a 2D link's layer list): follow it
    map.on("render", () => {
      const v = map.getLayer("cell") && map.getLayoutProperty("cell", "visibility") === "visible";
      if (v === on) return;
      on = v;
      syncKey();
      if (v) load().then(() => { fill(); syncKey(); }).catch(() => { syncKey(); });
    });
    return {ids: ["cell", "cell-o"], sym: `<span style='color:${EDGE}'>▦</span>`};
  };
  // the 3D click handler's: a stand-in feature for a tap where nothing else is, while the layer is on (none while a
  // popup is open: that tap only closes it), and the popups' last line
  window.cellSpot = function () {
    if (!on || !C || document.querySelector(".maplibregl-popup:not(.tip)")) return null;
    return {layer: {id: "cell"}, source: "cell", properties: {}};
  };
  window.cellNote = (ll, full) => ll ? note(ll.lat, ll.lng, full) : "";
  // each carrier's [name, covered] at a spot, once the data is loaded (null before); the popups' rows, for tests too
  window.cellAt = (lat, lon) => (C || (C = window.CELL || null)) ? at(lat, lon) : null;
})();
