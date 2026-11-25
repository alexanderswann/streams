// Approach routes on the map pages (the user, 2026-11-24: "when i click on a section of stream draw a line that is the
// hiking/biking to the computed approach point, highlight the trails if they exist or just draw the calculated line if
// there are no trails"). A click or tap on a reach draws its fastest route from the trailhead to its approach point, as
// 08_hike.py's cost-distance found it (approach_routes.py): the bike leg orange, the walk raspberry, solid on a trail or
// road (drawn on the trail's or road's own line), dashed off trail, dotted up a creek bottom; a white dot with a dark
// ring is the trailhead. The popup's "Route" line gives the miles (made by approach_routes.py in units.py's imperial
// units) and a "See it on the map" link, which closes the popup and fits the whole route into view. On a phone the
// popup covers most of the map, so the route stays when its popup closes, until the next tap on the map (the user,
// 2026-11-24: "Keep + 'see it' link"); a tap on another reach draws that one's instead. The routes of a map are in
// routes_data.js beside the page (06_map.py), loaded on the first click only; until then the line shows "…". Shared by
// the 2D map (map_drainages.js: routesLeaflet) and the 3D map (map3d.html: routesMaplibre); inlined by 06_map.py.
(function () {
  const STYLE = [{c: "#e8590c"}, {c: "#c2255c"}, {c: "#c2255c", d: "dash"}, {c: "#c2255c", d: "dot"}];  // kinds 0-3
  const on = () => !!((window.LBL || (window.MAP3D || {}).lbl || {}).routes);   // 06_map.py wrote routes_data.js
  let R = null, wait = null;
  function load() {
    if (!R && window.ROUTES) R = window.ROUTES;      // loaded already (a page or a test that carries it)
    if (R) return Promise.resolve(R);
    return wait || (wait = new Promise((ok, no) => {
      const s = document.createElement("script");
      s.src = "routes_data.js";
      s.onload = () => { R = window.ROUTES || null; if (R) ok(R); else { wait = null; no(new Error("no routes")); } };
      s.onerror = () => { wait = null; s.remove(); no(new Error("routes_data.js did not load")); };
      document.head.appendChild(s);
    }));
  }
  // Google's encoded polyline, from a starting point (1e-5 degrees)
  function dec(str, lat, lon) {
    const out = [];
    for (let i = 0; i < str.length;) {
      let b, sh = 0, r = 0;
      do { b = str.charCodeAt(i++) - 63; r |= (b & 31) << sh; sh += 5; } while (b >= 32);
      lat += r & 1 ? ~(r >> 1) : r >> 1;
      sh = 0; r = 0;
      do { b = str.charCodeAt(i++) - 63; r |= (b & 31) << sh; sh += 5; } while (b >= 32);
      lon += r & 1 ? ~(r >> 1) : r >> 1;
      out.push([lat, lon]);
    }
    return out;
  }
  // A segment's points from its start to its end, where it runs on into its parent (p: how many segments back that
  // one is, 0 at a trailhead). It is stored from that end back: from the parent's first point (from 0,0 at a trailhead).
  // Decoded down from the nearest segment already decoded (or the trailhead), so a long chain needs no deep recursion.
  const segs = new Map(), up = s => R.p[s] ? s - R.p[s] : -1;
  function seg(s) {
    const chain = [];
    for (let x = s; x >= 0 && !segs.has(x); x = up(x)) chain.push(x);
    for (let j = chain.length - 1; j >= 0; j--) {
      const x = chain[j], p = up(x), base = p >= 0 ? segs.get(p)[0] : [0, 0];
      const q = dec(R.g[x], base[0], base[1]).reverse();
      if (p >= 0) q.push(base);
      segs.set(x, q);
    }
    return segs.get(s);
  }
  // a drawn reach's route (lake: of the streams_lake layer; i: its index there), or null: {runs: [{k, ll}], text},
  // from the reach to the trailhead, the segments of one kind in a row joined into one run
  function route(lake, i) {
    if (!R) R = window.ROUTES || null;
    if (!R) return null;
    const ri = (lake ? R.l : R.s)[i];
    if (ri == null || ri < 0) return null;
    const [s0, t] = R.r[ri], runs = [];
    for (let s = s0; s >= 0; s = up(s)) {
      const k = +R.k[s], q = seg(s), last = runs[runs.length - 1];
      if (last && last.k === k) last.q = last.q.concat(q.slice(1));
      else runs.push({k, q});
    }
    return {runs: runs.map(u => ({k: u.k, ll: u.q.map(([a, b]) => [a / 1e5, b / 1e5])})), text: R.t[t]};
  }
  window.approachRoute = route;
  window.loadApproachRoutes = load;

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  // the popup's line: filled in by fill() once the routes are loaded (no line where the reach has no route at all)
  window.routeRow = p => on() && !/^No route/.test(p.acc || "")
    ? `<tr class="rtr"><td>Route</td><td class="rtl"><span class="dm">…</span></td></tr>` : "";
  function fill(el, r, see) {
    const td = el && el.querySelector(".rtl");
    if (!td) return;
    if (!r) { td.parentNode.remove(); return; }
    td.innerHTML = esc(r.text).replace(/^bike [\d.,]+ mi/, s => `<span class="rtb">${s}</span>`)
      .replace(/hike [\d.,]+ mi/, s => `<span class="rtw">${s}</span>`)
      + (see ? `<br><a href="#" class="rts">See it on the map</a>` : "");
    if (see) td.querySelector(".rts").addEventListener("click", e => { e.preventDefault(); see(); });
  }
  // after the line fills in, the pages place the popup again (map_phone.js and map3d.html listen, as for the fish
  // score's breakdown)
  const placed = () => document.dispatchEvent(new CustomEvent("fs-toggle"));
  // a route's bounds, [[south, west], [north, east]]
  function box(r) {
    let s = 90, w = 180, n = -90, e = -180;
    r.runs.forEach(u => u.ll.forEach(([a, b]) => { s = Math.min(s, a); n = Math.max(n, a); w = Math.min(w, b); e = Math.max(e, b); }));
    return [[s, w], [n, e]];
  }
  // The room the map's controls and panels leave, as padding for a fit (px): each one is kept clear from the side that
  // costs least (the zoom buttons from the left, the area panel from the bottom), leaving at least 30 % of each way.
  function room(cont, els) {
    const m = cont.getBoundingClientRect(), p = {top: 16, bottom: 16, left: 16, right: 16};
    els.forEach(el => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || r.bottom <= m.top || r.top >= m.bottom || r.right <= m.left || r.left >= m.right) return;
      const need = {top: r.bottom - m.top, bottom: m.bottom - r.top, left: r.right - m.left, right: m.right - r.left};
      const side = Object.keys(need).reduce((a, b) => need[b] < need[a] ? b : a);
      p[side] = Math.max(p[side], need[side] + 16);
    });
    [["top", "bottom", m.height], ["left", "right", m.width]].forEach(([a, b, len]) => {
      const k = Math.min(1, 0.7 * len / (p[a] + p[b]));
      p[a] = Math.round(p[a] * k); p[b] = Math.round(p[b] * k);
    });
    return p;
  }
  // once a closing popup's panels have folded back or come back (map_phone.js, map3d.html: in timeouts and click
  // handlers; not a frame callback, which a page in the background never runs)
  const later = f => setTimeout(f, 120);

  // What both maps share. show(): the route of the popup just opened; closed(): its popup closed, and the route stays
  // until the next tap on the map (armed after the tap that closed it: Leaflet closes a popup on that same click);
  // tap(): a tap on the map takes a kept route away, unless it is half of a double tap (a zoom); other(): another popup
  // opened (a lake's, a gauge's). draw(r) draws a route (null: none), fit(bounds, r) shows route r whole, close(popup).
  function control(draw, fit, close) {
    let owner = null, kept = false, cur = null, wait = 0;
    const clear = () => { owner = null; kept = false; cur = null; draw(null); };
    return {
      show(popup, get) {
        clearTimeout(wait);
        owner = popup; kept = false;
        load().then(() => {
          if (owner !== popup) return;
          const r = get();
          cur = r && r.runs.length ? r : null;
          draw(cur);
          fill(popup.getElement(), r, cur && (() => { const c = cur; kept = true; close(popup); fit(box(c), c); }));
          placed();
        }, () => { if (owner === popup) fill(popup.getElement(), null); });
      },
      closed(popup) {
        if (owner !== popup) return;
        if (!cur) { clear(); return; }
        setTimeout(() => { if (owner === popup) kept = true; });
      },
      tap() {
        if (!kept) return;
        const o = owner;
        clearTimeout(wait);
        wait = setTimeout(() => { if (kept && owner === o) clear(); }, 350);
      },
      zoomTap() { clearTimeout(wait); },
      other() { if (kept) clear(); },
    };
  }

  // the 2D map (Leaflet): its own pane above the streams and trails, under the labels; it takes no clicks
  window.routesLeaflet = function (map) {
    const pane = map.createPane("route");
    pane.style.zIndex = 395;
    pane.style.pointerEvents = "none";
    const rnd = L.svg({pane: "route", padding: 0.5}), grp = L.layerGroup();
    const DASH = {dash: "7 6", dot: "0.5 7"};
    const at = f => {     // a drawn feature's place in the page's layers, kept on it
      if (!f._rt) {
        const S = (window.STREAMS || {}).features || [], SL = (window.STREAMS_LAKE || {}).features || [];
        const i = S.indexOf(f);
        f._rt = i >= 0 ? [false, i] : [true, SL.indexOf(f)];
      }
      return f._rt;
    };
    function draw(r) {
      grp.clearLayers();
      if (!r || !r.runs.length) { grp.remove(); return; }
      const opt = {renderer: rnd, interactive: false, lineJoin: "round"};
      r.runs.forEach(u => L.polyline(u.ll, {...opt, color: "#fff", weight: 8, opacity: 0.9, lineCap: "round"}).addTo(grp));
      r.runs.forEach(u => {
        const st = STYLE[u.k];
        L.polyline(u.ll, {...opt, color: st.c, weight: 4, opacity: 1, dashArray: st.d ? DASH[st.d] : null,
                          lineCap: st.d === "dash" ? "butt" : "round"}).addTo(grp);
      });
      const end = r.runs[r.runs.length - 1].ll;
      L.circleMarker(r.runs[0].ll[0], {...opt, radius: 4, color: "#fff", weight: 1.5, fillColor: STYLE[r.runs[0].k].c,
                                       fillOpacity: 1}).addTo(grp);
      L.circleMarker(end[end.length - 1], {...opt, radius: 6, color: "#212529", weight: 2.5, fillColor: "#fff",
                                           fillOpacity: 1}).addTo(grp);
      grp.addTo(map);
    }
    const ctl = control(draw, b => later(() => {
      const p = room(map.getContainer(), [...map.getContainer().querySelectorAll(".leaflet-control")]);
      map.fitBounds(b, {paddingTopLeft: [p.left, p.top], paddingBottomRight: [p.right, p.bottom], maxZoom: 16});
    }), popup => map.closePopup(popup));
    map.on("click", ctl.tap);
    map.on("dblclick", ctl.zoomTap);
    map.on("popupopen", ctl.other);     // before the reach's own popupopen (Leaflet fires the map's first)
    return {
      show(f, popup) {
        if (!on()) return;
        const [lake, i] = at(f);
        ctl.show(popup, () => i >= 0 ? route(lake, i) : null);
      },
      // a tap on a reach also opens its hover label (Leaflet opens a tooltip on a click), under the popup; on a phone
      // nothing moves the pointer off the reach, so the label would stay on the route the popup leaves behind
      hide(popup) {
        const src = popup._source;
        if (src && src.closeTooltip) src.closeTooltip();
        ctl.closed(popup);
      },
    };
  };

  // the 3D map (MapLibre): its layers go on top when first used; D.streams holds the streams_lake features after its
  // own, and the source's generated ids are those places. Its click listener is added before the page's own, which
  // opens the popups, so a tap that opens another reach's popup finds the kept route still there and leaves it to show()
  window.routesMaplibre = function (map, D) {
    const nl = ((D.streams_lake || {}).features || []).length, n0 = D.streams.features.length - nl;
    const none = {type: "FeatureCollection", features: []};
    let made = false;
    function make() {
      if (made) return;
      made = true;
      map.addSource("route", {type: "geojson", data: none});
      const line = ["==", ["geometry-type"], "LineString"];
      map.addLayer({id: "route-casing", type: "line", source: "route", filter: line,
                    layout: {"line-cap": "round", "line-join": "round"},
                    paint: {"line-color": "#fff", "line-width": 8, "line-opacity": 0.9}});
      STYLE.forEach((st, k) => map.addLayer({id: "route-" + k, type: "line", source: "route",
        filter: ["all", line, ["==", ["get", "k"], k]],
        layout: {"line-cap": st.d === "dash" ? "butt" : "round", "line-join": "round"},
        paint: Object.assign({"line-color": st.c, "line-width": 4},
                             st.d ? {"line-dasharray": st.d === "dash" ? [1.8, 1.5] : [0, 1.8]} : {})}));
      map.addLayer({id: "route-ends", type: "circle", source: "route", filter: ["==", ["geometry-type"], "Point"],
                    paint: {"circle-radius": ["match", ["get", "e"], "th", 6, 4],
                            "circle-color": ["match", ["get", "e"], "th", "#fff", ["get", "c"]],
                            "circle-stroke-color": ["match", ["get", "e"], "th", "#212529", "#fff"],
                            "circle-stroke-width": ["match", ["get", "e"], "th", 2.5, 1.5]}});
    }
    function draw(r) {
      if (!r && !made) return;
      make();
      const fs = r && r.runs.length ? r.runs.map(u => ({type: "Feature", properties: {k: u.k},
        geometry: {type: "LineString", coordinates: u.ll.map(([a, b]) => [b, a])}})) : [];
      if (fs.length) {
        const end = r.runs[r.runs.length - 1].ll, a = r.runs[0].ll[0], t = end[end.length - 1];
        fs.push({type: "Feature", properties: {e: "ap", c: STYLE[r.runs[0].k].c}, geometry: {type: "Point", coordinates: [a[1], a[0]]}},
                {type: "Feature", properties: {e: "th"}, geometry: {type: "Point", coordinates: [t[1], t[0]]}});
      }
      map.getSource("route").setData({type: "FeatureCollection", features: fs});
    }
    // fitBounds frames the route as if the map were flat: tilted over terrain, a near end can stay off the screen (a
    // trailhead 60° tilted, n_georgia). Once there, each point is looked up on the screen and the map zooms out half a
    // step while one is outside the room, three times at most.
    const ctl = control(draw, (b, r) => later(() => {
      const c = map.getContainer();
      const p = room(c, [...c.querySelectorAll(".maplibregl-ctrl"), ...document.querySelectorAll(".panel")]);
      const out = () => {
        const m = c.getBoundingClientRect();
        return r.runs.some(u => u.ll.some(([a, o]) => {
          const s = map.project([o, a]);
          return s.x < p.left || s.y < p.top || s.x > m.width - p.right || s.y > m.height - p.bottom;
        }));
      };
      const check = n => { if (n && out()) { map.once("moveend", () => check(n - 1)); map.easeTo({zoom: map.getZoom() - 0.5, duration: 300}); } };
      map.once("moveend", () => check(3));
      map.fitBounds([[b[0][1], b[0][0]], [b[1][1], b[1][0]]], {padding: p, maxZoom: 16, duration: 700});
    }), popup => popup.remove());
    map.on("click", ctl.tap);
    map.on("dblclick", ctl.zoomTap);
    return {
      show(id, popup) {
        if (!on() || id == null) return;
        popup.on("close", () => ctl.closed(popup));
        const lake = id >= n0, i = lake ? id - n0 : id;
        ctl.show(popup, () => route(lake, i));
      },
    };
  };

  if (typeof document !== "undefined" && !document.getElementById("rt-style")) {
    const st = document.createElement("style");
    st.id = "rt-style";
    st.textContent = ".rtb{color:#d9480f;font-weight:600}.rtw{color:#c2255c;font-weight:600}";
    document.head.appendChild(st);
  }
})();
