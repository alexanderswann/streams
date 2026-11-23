// Streams, drainage outlines/labels, legend and colour-mode switch for stream_map.html (inlined by 06_map.py).
// Data globals written by 06_map.py: STREAMS (reaches), FORKS (fork polygons), DIVIDES (drainage outlines), DRAINS.
function initDrainageMap(map, ctrl) {
  const S = window.STREAMS, DR = window.DRAINS;
  // width / opacity by Strahler order: trunks read first, headwater rills recede
  const W = [0, 0.8, 1.15, 1.7, 2.4, 3.3, 4.4, 5.4];
  const OP = [0, 0.75, 0.85, 0.95, 1, 1, 1, 1];
  const BLUE = ["#000", "#6fa8d6", "#4a8fcb", "#2c74bb", "#1a5ca6", "#0d4590", "#08306b", "#08306b"];
  // Trails and roads that run beside a creek are drawn shifted to its far side so they don't cover it. 06_map.py
  // tags those runs (sd = side: +1 shift right of the line's direction, -1 left; so = the creek's order; dm = metres
  // apart); the shift is only what the two line widths need at the current zoom, eased in and out at the run's ends.
  const MPP = z => 129500 / Math.pow(2, z);             // metres per screen pixel at 34°N
  const zfz = z => Math.max(1, Math.min(2.2, 1 + (z - 9) * 0.3));
  const beside = (p, half) => p.sd ? z => {
    const need = (W[p.so || 2] * zfz(z) + (p.so >= 3 ? 2.6 : 0)) / 2 + half(z) + 1;
    return p.sd * Math.max(0, need - (p.dm || 0) / MPP(z));
  } : null;
  function offsetRing(pts, d) {
    const n = pts.length, seg = [];
    let total = 0;
    for (let i = 1; i < n; i++) {
      const dx = pts[i].x - pts[i - 1].x, dy = pts[i].y - pts[i - 1].y, l = Math.hypot(dx, dy) || 1e-9;
      seg.push([dx / l, dy / l, l]);
      total += l;
    }
    if (!seg.length || total < 1) return pts;
    const ease = Math.min(3 * Math.abs(d), total / 2);
    const out = [];
    let s = 0;
    for (let i = 0; i < n; i++) {
      const a = seg[Math.max(0, i - 1)], b = seg[Math.min(seg.length - 1, i)];
      let nx = -(a[1] + b[1]), ny = a[0] + b[0];        // right of the direction of travel (screen y points down)
      const nl = Math.hypot(nx, ny);
      if (nl < 1e-6) { nx = -b[1]; ny = b[0]; } else { nx /= nl; ny /= nl; }
      const miter = Math.max(0.5, -nx * a[1] + ny * a[0]);   // keep the width through bends, capped at 2x
      const f = Math.min(1, s / ease, (total - s) / ease);
      out.push(L.point(pts[i].x + nx * d * f / miter, pts[i].y + ny * d * f / miter));
      if (i < seg.length) s += seg[i][2];
    }
    return out;
  }
  if (!L.Polyline.prototype._offsetHooked) {
    const proj = L.Polyline.prototype._projectLatlngs;
    L.Polyline.include({
      _offsetHooked: true,
      _projectLatlngs(latlngs, result, bounds) {
        const start = result.length;
        proj.call(this, latlngs, result, bounds);
        const off = this.options.offset;
        if (off && latlngs.length && latlngs[0] instanceof L.LatLng) {
          const d = off(this._map.getZoom());
          if (d) result[start] = offsetRing(result[start], d);
        }
      },
    });
  }
  // fish score: most reaches score under 15 (dry or tiny), so those are a plain slate network and the colour
  // ramp, and extra width, are spent on the water worth fishing
  const LOW = 15, LOWCOL = "#8d9aa8";
  const RAMP = ["#3fb0a8", "#2a93c4", "#2a6fc0", "#3a4fb0", "#4b2f9c", "#3a1670"];
  let mode = "drainage", focus = null;

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  // imperial units for everything shown (units.py; the data stay metric: drainage in km², elevation in m)
  const SQMI = km2 => { if (km2 == null) return "?"; const v = km2 * 0.386102;
    return (v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 1 ? v.toFixed(1) : v.toFixed(2)) + " sq mi"; };
  const FEET = m => m == null ? "?" : Math.round(m * 3.28084).toLocaleString("en-US") + " ft";
  L.control.scale({metric: false}).addTo(map);
  if (window.phoneControls) phoneControls(map);     // map_phone.js: one-line credits on phones, "my location" button
  const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const mix = (h, t) => "#" + rgb(h).map(v => Math.round(v + (255 - v) * t).toString(16).padStart(2, "0")).join("");
  const ramp = fs => fs < LOW ? LOWCOL
    : RAMP[Math.min(RAMP.length - 1, Math.floor((fs - LOW) / (100 - LOW) * RAMP.length))];
  const zf = () => Math.max(1, Math.min(2.2, 1 + (map.getZoom() - 9) * 0.3));
  const dim = p => focus && p.d !== focus;

  ["basins", "halo", "streams", "dlabels"].forEach((n, i) => {
    const p = map.createPane(n);
    p.style.zIndex = [350, 380, 390, 450][i];
    if (n === "dlabels") p.style.pointerEvents = "none";
  });

  function col(p) {
    if (mode === "fish") return ramp(p.fs);
    if (mode === "order") return BLUE[p.o];
    return p.o === 1 ? mix(p.c, 0.22) : p.o === 2 ? mix(p.c, 0.1) : p.c;
  }
  function style(f) {
    const p = f.properties;
    let op = OP[p.o], w = W[p.o];
    if (mode === "fish") {
      if (p.fs < LOW) op *= 0.6;
      else w = Math.max(w, 1.6 + 2.4 * (p.fs - LOW) / (100 - LOW));   // good water is wide whatever its order
    }
    if (dim(p)) op *= 0.12;
    return {color: col(p), weight: w * zf(), opacity: op, lineCap: "round", lineJoin: "round"};
  }
  // white casing under order 3+ lifts the main channels off the terrain
  const hstyle = f => ({color: "#fff", weight: W[f.properties.o] * zf() + 2.6, opacity: dim(f.properties) ? 0 : 0.85,
                        lineCap: "round", lineJoin: "round"});

  function where(p) {
    if (p.d === p.k) return esc(p.d);
    return `${esc(p.k)} <span class="dm">· ${esc(p.d)}</span>`;
  }
  const tip = p => `<b>${esc(p.n || "Unnamed creek")}</b><div class="dw">${where(p)}</div>` +
    `Order ${p.o} · ${SQMI(p.a)} · ${esc(p.fl)} · fish ${p.fs}`;
  function pop(p) {
    // (a side channel's name carries " (side channel)", 06_map.py: its profile is the river's)
    const pn = p.n ? p.n.replace(/ \(side channel\)$/, "") : null;
    const prof = pn ? `<a href="profiles.html#q=${encodeURIComponent(pn)}&lat=${p.y}&lon=${p.x}" target="_blank">Open ${esc(pn)} profile ↗</a>`
                    : `<span class="dm">Unnamed reach (no profile)</span>`;
    return `<div class="pp"><b>${esc(p.n || "Unnamed creek")}</b><div class="dw">${where(p)}</div>` +
      `<table>${fsRow(p)}` +           // map_score.js: the score, and its breakdown on hover or tap
      `<tr><td>Order / drainage</td><td>${p.o} · ${SQMI(p.a)}</td></tr>` +
      `<tr><td>${p.dq ? "Summer flow" : "NHD flow"}</td><td>${esc(p.dq || p.fl.replace(/^NHD /, ""))}</td></tr>` +
      `<tr><td>Elev / gradient</td><td>${FEET(p.el)} · ${p.gr}%</td></tr>` +
      `<tr><td>Access</td><td>${esc(p.acc)}${(window.LBL || {}).acc_asof ? `<div class="dm">${esc(window.LBL.acc_asof)}</div>` : ""}</td></tr>` +
      (p.sun ? `<tr><td>Sun</td><td>${esc(p.sun)}</td></tr>` : "") +
      (p.tr ? `<tr><td>Trout</td><td>${esc(p.tr)}</td></tr>` : "") +
      (p.ht ? `<tr><td>Heat</td><td class="warn">${esc(p.ht)}</td></tr>` : "") +
      (p.burn ? `<tr><td>Fire</td><td class="warn">${esc(p.burn)}</td></tr>` : "") +
      (p.flags ? `<tr><td>Notes</td><td>${esc(p.flags)}</td></tr>` : "") +
      `</table>${prof}</div>`;
  }

  // ---- drainage fills + divides (tinted only when colouring by drainage) ----
  const fillOp = f => mode !== "drainage" ? 0 : dim({d: f.properties.drainage}) ? 0.02 : 0.07;
  const fills = L.geoJSON(window.FORKS, {pane: "basins", interactive: false,
    style: f => ({stroke: true, color: "#6b7785", weight: 0.7, opacity: 0.45, dashArray: "2 4",
                  fillColor: f.properties.c, fillOpacity: fillOp(f)})});
  const divides = L.geoJSON(window.DIVIDES, {pane: "basins", interactive: false,
    style: f => ({color: "#3d4651", weight: 1.4, opacity: dim({d: f.properties.drainage}) ? 0.25 : 0.55})});

  // ---- streams ----
  // One canvas for everything you can hover or click (streams, then trails, then the PCT on top), so a single hit
  // test finds what is under the cursor and no layer's canvas blocks another's mouse events.
  const r = L.canvas({pane: "streams", padding: 0.4, tolerance: 5});
  // One canvas takes the pointer. Leaflet canvases don't pass mouse events down to canvases under them, and the
  // vector overlays folium adds (the fire closure areas, on by default; drops, fire perimeters, habitat, closures...
  // when switched on) drew on the map's default canvas in the overlay pane, above the streams pane. That canvas covers
  // the whole map, so it took every hover and click: the cursor stayed the grab hand and no stream, trail or road
  // could be clicked. They now draw on the streams canvas: areas under the streams, points and lines on top.
  map.options.renderer = r;
  const adopted = new Set();
  map.on("layeradd", e => {
    const l = e.layer;
    if (!(l instanceof L.Path) || l.options.renderer || l._renderer !== r) return;   // this script's layers name theirs
    adopted.add(l);
    if (l instanceof L.Polygon) l.bringToBack();
  });
  map.on("layerremove", e => adopted.delete(e.layer));
  if (map._renderer && map._renderer !== r) {           // overlays folium added before this ran: move them over
    const old = map._renderer;
    Object.values(old._layers).forEach(l => { map.removeLayer(l); map.addLayer(l); });
    map.removeLayer(old);
    map._renderer = null;
  }
  // Hover highlight on its own small SVG layer. Restyling a line on the shared canvas redrew thousands of streams on
  // every hover, so the highlight lagged behind the cursor.
  const hp = map.createPane("hover");
  hp.style.zIndex = 396;
  hp.style.pointerEvents = "none";
  const hoverLine = L.polyline([], {renderer: L.svg({pane: "hover"}), interactive: false, lineCap: "round",
                                    lineJoin: "round"});
  const showHover = (l, color, weight) => {
    hoverLine.options.offset = l.options.offset || null;
    hoverLine.setLatLngs(l.getLatLngs()).setStyle({color, weight, opacity: 1});
    if (!map.hasLayer(hoverLine)) hoverLine.addTo(map);
  };
  const hideHover = () => { if (map.hasLayer(hoverLine)) hoverLine.remove(); };
  const halo = L.geoJSON(S, {filter: f => f.properties.o >= 3, style: hstyle, interactive: false,
                             renderer: L.canvas({pane: "halo", padding: 0.4})});
  const bindStream = (f, l) => {
    l.bindTooltip(() => tip(f.properties), {sticky: true, className: "stip", direction: "top", offset: [0, -6]});
    l.bindPopup(() => pop(f.properties), {maxWidth: 340});
    l.on("mouseover", () => showHover(l, col(f.properties), W[f.properties.o] * zf() + 3));
    l.on("mouseout", hideHover);
  };
  const lines = L.geoJSON(S, {style, renderer: r, onEachFeature: bindStream});
  const streams = L.layerGroup([halo, lines]).addTo(map);
  // Reaches lying in a lake (STREAMS_LAKE, 06_map.py): the Lakes layer draws that water, so they show only while Lakes
  // is off, and then like any other stream (the user, 2026-11-20: the rivers run on through the lakes when it's off)
  const SL = {type: "FeatureCollection", features: (window.STREAMS_LAKE || {}).features || []};
  const lakeHalo = L.geoJSON(SL, {filter: f => f.properties.o >= 3, style: hstyle, interactive: false,
                                  renderer: halo.options.renderer});
  const lakeLines = L.geoJSON(SL, {style, renderer: r, onEachFeature: bindStream});
  const lakeStreams = L.layerGroup([lakeHalo, lakeLines]);
  function syncLakeStreams() {
    const li = (ctrl._layers || []).find(x => x.overlay && /Lakes:/.test(x.name));
    const want = SL.features.length > 0 && map.hasLayer(streams) && !(li && map.hasLayer(li.layer));
    if (want && !map.hasLayer(lakeStreams)) { lakeStreams.addTo(map); restack(); }
    else if (!want && map.hasLayer(lakeStreams)) map.removeLayer(lakeStreams);
  }
  const basinLayer = L.layerGroup([fills, divides]).addTo(map);

  // ---- Pacific Crest Trail (02c_pct.py): thin dark dashed line on a soft yellow band, above the streams ----
  const LONGTRAIL = (window.LBL || {}).long_trail || "Pacific Crest Trail";   // the area's long-distance trail
  const pctGroup = L.layerGroup();
  const pctLabs = [];   // [label centre, angle, SVG <text>, zoom band]
  let pctLines = [];
  if (window.PCT) {
    const pr = r;   // drawn on the streams canvas, on top
    const pw = () => Math.max(0.8, Math.min(1.5, 0.8 + (map.getZoom() - 9) * 0.18));
    const mk = (st, extra = {}) => L.geoJSON(window.PCT, {renderer: pr, style: st, ...extra});
    pctLines = [
      mk(() => ({color: "#ffd43b", weight: 7 * pw(), opacity: 0.45, lineCap: "round", lineJoin: "round"}), {interactive: false}),
      mk(() => ({color: "#ffffff", weight: 3.4 * pw(), opacity: 0.9, lineCap: "round", lineJoin: "round"}), {interactive: false}),
      mk(() => ({color: "#1d1d1f", weight: 1.7 * pw(), opacity: 1, dashArray: "6 4", lineCap: "butt", lineJoin: "round"}), {
        onEachFeature: (f, l) => l.bindTooltip(
          `<b>${LONGTRAIL}</b><div class="dw">${esc(f.properties.label)}</div>`,
          {sticky: true, className: "stip", direction: "top", offset: [0, -8]})}),
    ];
    pctLines.forEach(l => pctGroup.addLayer(l));
    pctGroup.addTo(map);
    // Labels run along smoothed copies of the trail (SVG textPath), so the lettering bends with the line. The
    // invisible label paths stay on the map; updateLabels shows or hides the text.
    const lp = map.createPane("pctlab");
    lp.style.zIndex = 452;
    lp.style.pointerEvents = "none";
    const sr = L.svg({pane: "pctlab", padding: 0.5});
    const NS = "http://www.w3.org/2000/svg";
    (window.PCT_LABEL_LINES || []).forEach((lab, i) => {
      const pl = L.polyline(lab.p.map(([x, y]) => [y, x]), {renderer: sr, stroke: false, fill: false,
                                                           interactive: false, noClip: true, smoothFactor: 0}).addTo(map);
      pl._path.id = "pctlp" + i;
      const t = document.createElementNS(NS, "text"), tp = document.createElementNS(NS, "textPath");
      t.setAttribute("class", "pctt");
      t.setAttribute("dy", "-8");
      tp.setAttribute("href", "#pctlp" + i);
      tp.setAttribute("startOffset", "50%");
      tp.setAttribute("text-anchor", "middle");
      tp.textContent = LONGTRAIL;
      t.appendChild(tp);
      pl._path.parentNode.appendChild(t);
      pctLabs.push([L.latLng(lab.c), lab.a, t, lab.z]);
    });
  }
  const restylePct = () => pctLines.forEach(l => l.setStyle(l.options.style));

  // ---- trails and fire roads (02d_trails.py): brown dashes on a white edge, more detail with each zoom level ----
  // rank 1 hiking routes and named trails (z10+), 2 named fire roads (z11+), 3 unnamed trails (z12+), 4 unnamed fire
  // roads (z13+). Fire roads: longer dashes, a little wider. Closed or private: faded. Informal or faint: dotted.
  const trailGroup = L.layerGroup();
  const trailLabs = [];
  const TRAIL_MINZ = {1: 10, 2: 11, 3: 12, 4: 13};
  const trailLayers = {};
  let trailShown = "";
  const tw = f => Math.max(1, Math.min(3.2, 1 + (map.getZoom() - 10) * 0.4)) * (f.properties.k === "fire road" ? 1.25 : 1);
  const tstyle = f => {
    const p = f.properties, w = tw(f);
    const dash = p.f ? [0.8, 2.2] : p.k === "fire road" ? [5, 1.8] : [2.6, 1.8];
    return {color: p.k === "fire road" ? "#7a5a3a" : "#5c3317", weight: w, opacity: p.cl ? 0.4 : p.f ? 0.75 : 1,
            dashArray: dash.map(v => (v * w).toFixed(1)).join(" "), lineCap: "butt", lineJoin: "round"};
  };
  // mountain bike access (02d_trails.py), shown as the colour of the trail's edge while "Mountain bike access on
  // trails" is on; unknown keeps the plain white edge
  const BIKE = {yes: ["#37b24d", "Open to bikes"], likely: ["#a9e34b", "Likely OK for bikes"],
                unlikely: ["#ffa94d", "Probably no bikes"], no: ["#f03e3e", "No bikes"], unknown: ["#ffffff", "Unknown"]};
  let bikeOn = true;
  const thalo = f => {
    const b = bikeOn && f.properties.b && f.properties.b !== "unknown" && BIKE[f.properties.b];
    return {color: b ? b[0] : "#ffffff", weight: tw(f) + (b ? 3.6 : 2.4),
            opacity: f.properties.cl ? 0.35 : b ? 0.85 : 0.75, lineCap: "round", lineJoin: "round"};
  };
  const bikeLine = p => {
    if (!p.b) return "";
    const why = String(p.bw || "").replace(/:\s*(no bikes|open to bikes)$/i, "");
    const lab = BIKE[p.b] ? BIKE[p.b][1] : p.b;
    return `<span style="color:${p.b === "no" ? "#c92a2a" : p.b === "yes" ? "#2b8a3e" : "inherit"}">Bikes: ${lab}</span>` +
      (why && why.toLowerCase() !== lab.toLowerCase() && p.b !== "unknown" ? ` <span class="dm">(${esc(why)})</span>` : "") +
      (p.mtb ? ` · MTB difficulty S${esc(p.mtb)}` : "");
  };
  const ttip = window.trailTip = p => `<b>${esc(p.n || (p.k === "fire road" ? "Unnamed fire road" : "Unnamed trail"))}</b>` +
    `<div class="dw">${p.k === "fire road" ? (p.g ? "Fire road, gated to cars" : "Fire road / dirt road") : "Trail"}` +
    `${p.rt && p.rt !== p.n ? " · " + esc(p.rt) : ""}</div>` +
    [p.of ? `Official trail · ${esc(p.of)}${p.no ? " #" + esc(p.no) : ""}` : "",
     p.us ? "Open to: " + esc(p.us) : "",
     p.g ? `USFS road ${esc(p.g)}: closed to public vehicles, open on foot` : "",
     p.u ? "<span class='dm'>Possibly unofficial: not in agency trail data</span>" : "",
     p.src ? "<span class='dm'>From agency records only; not in OpenStreetMap, may be faint or abandoned</span>" : "",
     p.s ? "Difficulty: " + esc(p.s) : "", p.sf ? "Surface: " + esc(p.sf) : "",
     p.cl ? `<span class='warn'>Closed${p.cw ? ": " + esc(p.cw) : " or private"}</span>` : "",
     p.f && !p.u && !p.src ? "Informal or faint trail" : "", bikeLine(p)].filter(Boolean).join("<br>");
  const bikeView = L.layerGroup();
  if (window.TRAILS) {
    const trr = r;   // drawn on the streams canvas, above the streams
    [1, 2, 3, 4].forEach(rk => {
      const data = {type: "FeatureCollection", features: window.TRAILS.features.filter(f => f.properties.rk === rk)};
      const thalf = f => z => (Math.max(1, Math.min(3.2, 1 + (z - 10) * 0.4)) * (f.properties.k === "fire road" ? 1.25 : 1)
                              + 3.6) / 2;
      trailLayers[rk] = [
        L.geoJSON(data, {renderer: trr, interactive: false, style: thalo,
                         onEachFeature: (f, l) => { l.options.offset = beside(f.properties, thalf(f)); }}),
        L.geoJSON(data, {renderer: trr, style: tstyle, onEachFeature: (f, l) => {
          l.options.offset = beside(f.properties, thalf(f));
          l.bindTooltip(() => ttip(f.properties), {sticky: true, className: "stip", direction: "top", offset: [0, -6]});
          l.on("mouseover", () => showHover(l, tstyle(f).color, tw(f) + 2));
          l.on("mouseout", hideHover);
        }}),
      ];
    });
    // (not on the map until it is switched on in the layer list: the map opens with streams, drainages, the long
    // trail, terrain shading and place labels only)
    // names along named trails and fire roads from z13 (SVG text on smoothed paths, as for the PCT); only the current
    // zoom band's labels near the view are on the map at any time
    const lp2 = map.createPane("trlab");
    lp2.style.zIndex = 451;
    lp2.style.pointerEvents = "none";
    const sr2 = L.svg({pane: "trlab", padding: 0.5});
    const NS2 = "http://www.w3.org/2000/svg";
    (window.TRAIL_LABEL_LINES || []).forEach((lab, i) => {
      const pl = L.polyline(lab.p.map(([x, y]) => [y, x]), {renderer: sr2, stroke: false, fill: false,
                                                           interactive: false, noClip: true, smoothFactor: 0});
      const t = document.createElementNS(NS2, "text"), tp = document.createElementNS(NS2, "textPath");
      t.setAttribute("class", "trlt");
      t.setAttribute("dy", "-5");
      tp.setAttribute("href", "#trlp" + i);
      tp.setAttribute("startOffset", "50%");
      tp.setAttribute("text-anchor", "middle");
      tp.textContent = lab.t;
      t.appendChild(tp);
      pl.on("add", () => { pl._path.id = "trlp" + i; pl._path.parentNode.appendChild(t); });
      pl.on("remove", () => t.remove());
      trailLabs.push({pl, ll: L.latLng(lab.c), a: lab.a, z: lab.z, w: lab.t.length * 5.6 + 6, on: false});
    });
  }
  // ---- access roads (02e_access.py): one layer per what it takes to get up them. Cased lines (light centre, dark
  // edge) read as roads rather than streams; dashed centres for 4WD, bike-only and unknown-condition roads.
  //   class: [label, centre, edge, dash (x width), min zoom, on by default]
  const ROAD = {
    paved:          ["Paved: any car", "#ffffff", "#7a828c", null, 10, false],
    graded:         ["Graded dirt: car OK when dry", "#f3d9a4", "#8a6d3b", null, 10, true],
    high_clearance: ["Rough dirt: high clearance", "#ffc078", "#b35900", null, 10, true],
    "4wd":          ["Very rough: 4WD only", "#ffa8a8", "#a51d2d", [3, 2], 10, true],
    bike:           ["Closed to cars, open to bikes", "#b2f2bb", "#2b8a3e", [3, 2], 10, true],
    dirt:           ["Dirt road, condition unknown", "#e9ecef", "#7a828c", [1.5, 2], 11, true],
    closed:         ["Closed: fire closure", "#ffc9c9", "#c92a2a", [2, 2], 10, true],
  };
  const LEVEL = {1: "closed / custodial", 2: "high-clearance vehicles", 3: "passenger cars", 4: "moderate comfort",
                 5: "high comfort"};
  const roadGroups = {}, roadLayers = {}, roadOverlays = [];
  const rw = () => Math.max(1.2, Math.min(4, 1.2 + (map.getZoom() - 10) * 0.55));
  const rtip = p => `<b>${esc(p.n || "Unnamed road")}</b><div class="dw">${ROAD[p.c][0]}</div>` +
    [p.fs ? `USFS road ${esc(p.fs)}${p.lv ? ` · maintenance level ${p.lv} (${LEVEL[p.lv] || ""})` : ""}` : "",
     p.sf ? "Surface: " + esc(p.sf) : "", p.tt ? `Track grade ${esc(String(p.tt).replace("grade", ""))} of 5` : "",
     p.sm ? "Smoothness: " + esc(String(p.sm).replace(/_/g, " ")) : "",
     p.se === "yes" ? "<span class='warn'>Seasonal road</span>" : "", p.ac ? "Restrictions: " + esc(p.ac) : "",
     p.mv ? "Forest Service vehicle rules: " + esc(p.mv) : "", p.od ? "<span class='warn'>Open to " + esc(p.od) + "</span>" : "",
     p.cw ? "<span class='warn'>" + esc(p.cw) + "</span>" : ""]
      .filter(Boolean).join("<br>");
  if (window.ROADS) {
    Object.entries(ROAD).forEach(([c, [label, core, edge, dash, minz, on]]) => {
      const data = {type: "FeatureCollection", features: window.ROADS.features.filter(f => f.properties.c === c)};
      if (!data.features.length) return;
      const rhalf = z => (Math.max(1.2, Math.min(4, 1.2 + (z - 10) * 0.55)) + 2.2) / 2;
      const edgeL = L.geoJSON(data, {renderer: r, interactive: false,
        style: () => ({color: edge, weight: rw() + 2.2, opacity: 0.9, lineCap: "round", lineJoin: "round"}),
        onEachFeature: (f, l) => { l.options.offset = beside(f.properties, rhalf); }});
      const coreL = L.geoJSON(data, {renderer: r,
        style: () => ({color: core, weight: rw(), opacity: 1, lineCap: dash ? "butt" : "round", lineJoin: "round",
                       dashArray: dash ? dash.map(v => (v * rw()).toFixed(1)).join(" ") : null}),
        onEachFeature: (f, l) => {
          l.options.offset = beside(f.properties, rhalf);
          l.bindTooltip(() => rtip(f.properties), {sticky: true, className: "stip", direction: "top", offset: [0, -6]});
          l.on("mouseover", () => showHover(l, edge, rw() + 4));
          l.on("mouseout", hideHover);
        }});
      roadLayers[c] = [edgeL, coreL, minz];
      roadGroups[c] = L.layerGroup();
      roadOverlays.push([roadGroups[c], `<span class="rsym" style="background:${core};border-color:${edge}` +
                         `${dash ? ";border-style:dashed" : ""}"></span> ${label}`]);
    });
  }
  function updateRoads() {
    const z = map.getZoom();
    let added = false;
    Object.entries(roadLayers).forEach(([c, [edgeL, coreL, minz]]) => {
      const g = roadGroups[c];
      if (z < minz) { if (g.hasLayer(coreL)) g.clearLayers(); return; }
      if (!g.hasLayer(coreL)) { g.addLayer(edgeL); g.addLayer(coreL); added = true; }
      edgeL.setStyle(edgeL.options.style); coreL.setStyle(coreL.options.style);   // also when just re-added (stale width)
    });
    if (added) restack();
  }

  // ---- trailheads and parking (02e_access.py): trailheads from z11, parking from z12, only those near the view ----
  const thGroup = L.layerGroup(), pkGroup = L.layerGroup(), pois = [];
  const poiClosed = p => /closed/i.test(p.st || "");
  const poiTip = p => `<b>${esc(p.n || (p.k === "trailhead" ? "Trailhead" : "Parking"))}</b>` +
    (poiClosed(p) ? `<div class="warn">${esc(p.st[0].toUpperCase() + p.st.slice(1))} (Forest Service status)</div>` : "") +
    `<div class="dw">${p.k === "trailhead" ? "Trailhead" + (p.p ? " with parking" : "") : "Parking"}` +
    `${p.src === "USFS" ? " · Forest Service" : ""}</div>` +
    [p.fee === "yes" ? "Fee or pass required" : p.fee === "no" ? "No fee" : "", p.cap ? "Spaces: " + esc(p.cap) : "",
     p.no ? `<span class="dm">${esc(p.no)}</span>` : ""].filter(Boolean).join("<br>");
  if (window.PARKING) {
    window.PARKING.features.forEach(f => {
      const p = f.properties, th = p.k === "trailhead";
      const html = th ? `<div class="poi th${poiClosed(p) ? " closed" : ""}">T${p.p ? '<span class="pb">P</span>' : ""}</div>`
                      : `<div class="poi pk">P</div>`;
      const mk = L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]], {keyboard: false,
        icon: L.divIcon({className: "", html, iconSize: [18, 18], iconAnchor: [9, 9]})});
      mk.bindTooltip(() => poiTip(p), {direction: "top", offset: [0, -10], className: "stip"});
      if (p.u) mk.bindPopup(() => poiTip(p) + `<br><a href="${esc(p.u)}" target="_blank">Forest Service page ↗</a>`,
                            {maxWidth: 300});
      pois.push({mk, th, ll: mk.getLatLng(), on: false});
    });
  }
  function updatePois() {
    const z = map.getZoom(), view = map.getBounds().pad(0.3);
    pois.forEach(o => {
      const g = o.th ? thGroup : pkGroup;
      const want = map.hasLayer(g) && z >= (o.th ? 11 : 12) && view.contains(o.ll);
      if (want && !o.on) { g.addLayer(o.mk); o.on = true; }
      else if (!want && o.on) { g.removeLayer(o.mk); o.on = false; }
    });
  }
  map.on("moveend overlayadd overlayremove", updatePois);

  // keep the shared canvas's draw order: streams, then roads, then trails, then the PCT (re-added layers go on top)
  function restack() {
    Object.values(roadGroups).forEach(g => { if (map.hasLayer(g)) g.eachLayer(l => l.bringToFront()); });
    // halos first, then lines, rank 1 last so it ends on top (the group's own order is the order the layers were made)
    if (map.hasLayer(trailGroup)) [0, 1].forEach(i => [4, 3, 2, 1].forEach(rk => {
      const l = trailLayers[rk] && trailLayers[rk][i];
      if (l && trailGroup.hasLayer(l)) l.bringToFront();
    }));
    if (map.hasLayer(pctGroup)) pctLines.forEach(l => l.bringToFront());
    adopted.forEach(l => { if (!(l instanceof L.Polygon)) l.bringToFront(); });   // overlay points and lines on top
  }
  function updateTrails() {
    const z = map.getZoom();
    const want = [4, 3, 2, 1].filter(rk => trailLayers[rk] && z >= TRAIL_MINZ[rk]);
    if (want.join() !== trailShown) {   // tiers change: re-add in order (halos under lines, rank 1 on top)
      trailGroup.clearLayers();
      want.forEach(rk => trailGroup.addLayer(trailLayers[rk][0]));
      want.forEach(rk => trailGroup.addLayer(trailLayers[rk][1]));
      trailShown = want.join();
      restack();
    }
    // widths follow the zoom on every step, also the one that changes the tiers: a re-added layer keeps the style it
    // last had, so trails stayed at the width of the zoom they were first shown at
    want.forEach(rk => { trailLayers[rk][0].setStyle(thalo); trailLayers[rk][1].setStyle(tstyle); });
  }

  // ---- labels: drainages always (small ones from z10), forks from z11 ----
  const labels = L.layerGroup().addTo(map);
  const dlabs = [], flabs = [];
  DR.forEach(d => {
    if (!d.lab) return;
    const mk = L.marker(d.lab, {pane: "dlabels", interactive: false, keyboard: false,
      icon: L.divIcon({className: "dlab", iconSize: null, html: `<span style="color:${d.dark}">${esc(d.name)}</span>`})});
    dlabs.push([mk, d, d.km2 || 0]);
    (d.forks || []).forEach(f => {
      if (f.name === d.name || d.forks.length < 2 || f.name.includes("unnamed fork")) return;
      const fm = L.marker(f.lab, {pane: "dlabels", interactive: false, keyboard: false,
        icon: L.divIcon({className: "flab", iconSize: null, html: `<span style="color:${d.dark}">${esc(f.name)}</span>`})});
      flabs.push([fm, d, f.km2]);
    });
  });
  // biggest first; a label is skipped where it would overlap one already placed
  dlabs.sort((x, y) => y[2] - x[2]);
  flabs.sort((x, y) => y[2] - x[2]);
  function updateLabels() {
    const z = map.getZoom(), boxes = [];
    labels.clearLayers();
    const fits = (ll, w, h) => {
      const p = map.latLngToLayerPoint(ll);
      const b = [p.x - w / 2 - 4, p.y - h / 2 - 3, p.x + w / 2 + 4, p.y + h / 2 + 3];
      if (boxes.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])) return false;
      boxes.push(b);
      return true;
    };
    const show = (list, cw, h, ok) => list.forEach(([mk, d]) => {
      const name = mk.options.icon.options.html.replace(/<[^>]+>/g, "");
      if (ok(d) && !(focus && d.name !== focus) && fits(mk.getLatLng(), name.length * cw, h)) labels.addLayer(mk);
    });
    // PCT labels first (they win collisions); boxes are the label's axis-aligned extent at its general angle.
    // Each zoom band (11, 12, 13+) has its own label paths, smoothed for that scale (06_map.py).
    const band = Math.min(13, Math.floor(z));
    pctLabs.forEach(([ll, ang, t, zb]) => {
      const a = ang * Math.PI / 180, w = 112, h = 12;
      const on = z >= 11 && zb === band && map.hasLayer(pctGroup) &&
        fits(ll, Math.abs(w * Math.cos(a)) + Math.abs(h * Math.sin(a)), Math.abs(w * Math.sin(a)) + Math.abs(h * Math.cos(a)));
      t.style.display = on ? "" : "none";
    });
    if (map.hasLayer(basinLayer)) {
      show(dlabs, 8.2, 11, d => z <= 13 && (z >= 10 || d.km2 >= 45));
      if (z >= 11) show(flabs, 6.6, 12, () => true);
    }
    // trail names last (lowest priority), only near the view
    const tband = z >= 14 ? 14 : 13, view = map.getBounds().pad(0.2);
    trailLabs.forEach(L_ => {
      const a = L_.a * Math.PI / 180, h = 11;
      const want = z >= 13 && L_.z === tband && map.hasLayer(trailGroup) && view.contains(L_.ll) &&
        fits(L_.ll, Math.abs(L_.w * Math.cos(a)) + Math.abs(h * Math.sin(a)), Math.abs(L_.w * Math.sin(a)) + Math.abs(h * Math.cos(a)));
      if (want && !L_.on) { L_.pl.addTo(map); L_.on = true; }
      else if (!want && L_.on) { L_.pl.remove(); L_.on = false; }
    });
  }

  function restyle() {
    lines.setStyle(style); halo.setStyle(hstyle); lakeLines.setStyle(style); lakeHalo.setStyle(hstyle);
    fills.setStyle(f => ({fillOpacity: fillOp(f)}));
    divides.setStyle(f => ({opacity: dim({d: f.properties.drainage}) ? 0.25 : 0.55}));
    restylePct(); updateRoads(); updateTrails(); updateLabels(); updatePois(); renderKey();
  }
  map.on("zoomend", restyle);
  map.on("overlayadd overlayremove moveend", updateLabels);
  map.on("overlayadd", restack);
  map.on("overlayadd overlayremove", syncLakeStreams);
  syncLakeStreams();
  map.attributionControl.addAttribution("Trails &amp; PCT © <a href='https://www.openstreetmap.org/copyright'>" +
    "OpenStreetMap</a> contributors · " + ((window.LBL || {}).credits ||
    "USGS National Digital Trails · USFS · CDFW · iNaturalist · CAL FIRE · NIFC WFIGS · " +
    "USGS gauges &amp; debris-flow hazard · CDEC · TNC Natural Flows · PRISM Group, Oregon State University"))
  ctrl.addOverlay(streams, "<span style='color:#1864ab'>━</span> Streams (≥0.4 sq mi; ≥0.1 if named or year-round)");
  ctrl.addOverlay(basinLayer, "<span style='color:#3d4651'>▭</span> Drainage outlines &amp; names");
  if (window.PCT) ctrl.addOverlay(pctGroup, "<span class='pctsym'>━</span> <b>" + LONGTRAIL + "</b>");
  if (window.TRAILS) ctrl.addOverlay(trailGroup, "<span class='trsym'>┅</span> Trails &amp; fire roads");
  if (window.TRAILS) {
    // the bike colouring comes on with the trail layer (and can then be switched off on its own)
    ctrl.addOverlay(bikeView, "<span class='bksym'></span> Mountain bike access on trails");
    map.on("overlayadd overlayremove", e => {
      if (e.layer === trailGroup) { e.type === "overlayadd" ? bikeView.addTo(map) : map.removeLayer(bikeView); }
      if (e.layer !== bikeView && e.layer !== trailGroup) return;
      bikeOn = map.hasLayer(bikeView);
      Object.values(trailLayers).forEach(([h]) => h.setStyle(thalo));
      box.querySelector(".bk").style.display = bikeOn && map.hasLayer(trailGroup) ? "" : "none";
    });
  }
  if (window.PARKING) {
    ctrl.addOverlay(thGroup, "<span class='poi th mini'>T</span> Trailheads");
    ctrl.addOverlay(pkGroup, "<span class='poi pk mini'>P</span> Parking");
  }
  roadOverlays.forEach(([g, label]) => ctrl.addOverlay(g, "Roads: " + label));

  // ---- the layer list, as the 3D map's "View & layers" panel (the user, 2026-11-23): a header whose "–" folds the
  // list and stays put while the list under it scrolls (map_style.css), and groups of entries with one switch for them
  // all: the drops with the known falls, the trails with their bike colouring (a group of their own: the way on from
  // the road on foot or by bike, where "All roads" shows what a car can drive), and the roads. Each entry keeps its own
  // switch. A group's switch shows all on, all off or mixed; it turns them all on, or all off when they all are.
  // Leaflet rebuilds the list when a layer is added or removed other than by its own switch, so the groups are laid
  // out again after each rebuild, at the same scroll position.
  const lyc = ctrl.getContainer(), FALLS = (window.LBL || {}).falls;
  const lyh = L.DomUtil.create("div", "lyh");
  lyh.innerHTML = `<b>View &amp; layers</b><button type="button" class="lx" title="Hide the layer list">–</button>`;
  lyc.insertBefore(lyh, ctrl._section);
  L.DomEvent.on(lyh.querySelector(".lx"), "click", e => { L.DomEvent.stop(e); ctrl.collapse(); });
  const LGROUPS = [["All drops &amp; waterfalls", o => /Drops: /.test(o.name) || (!!FALLS && o.name.includes(FALLS))],
                   ["All trails &amp; bike access", o => o.layer === trailGroup || o.layer === bikeView],
                   ["All roads", o => roadOverlays.some(([g]) => g === o.layer)]];
  const lgroups = [];      // [the group's checkbox, its layers] as laid out by the last rebuild
  const syncGroups = () => lgroups.forEach(([cb, ls]) => {
    const n = ls.filter(l => map.hasLayer(l)).length;
    cb.checked = n === ls.length;
    cb.indeterminate = n > 0 && n < ls.length;
    cb.closest("label").querySelector(".lgn").textContent = cb.indeterminate ? `${n} of ${ls.length}` : "";
  });
  const rebuild = ctrl._update;
  ctrl._update = function () {
    const top = this._section ? this._section.scrollTop : 0;
    rebuild.call(this);
    lgroups.length = 0;
    const items = this._layerControlInputs.map(inp => [inp, this._getLayer(inp.layerId)]).filter(([, o]) => o && o.overlay);
    LGROUPS.forEach(([title, test]) => {
      const mine = items.filter(([, o]) => test(o));
      if (mine.length < 2) return;
      const first = mine[0][0].closest("label"), grp = L.DomUtil.create("div", "lgrp");
      first.parentNode.insertBefore(grp, first);
      L.DomUtil.create("label", "lgh", grp).innerHTML = `<span class="lgn"></span><span><input type="checkbox" ` +
        `class="leaflet-control-layers-selector"><span> ${title}</span></span>`;
      const members = L.DomUtil.create("div", "lgm", grp);
      mine.forEach(([inp]) => members.appendChild(inp.closest("label")));
      const cb = grp.querySelector("input"), ls = mine.map(([, o]) => o.layer);
      L.DomEvent.on(cb, "change", () => {
        const on = !ls.every(l => map.hasLayer(l));
        this._handlingClick = true;            // as for a click on an entry: no rebuild of the list per layer
        ls.forEach(l => { if (on !== map.hasLayer(l)) { if (on) map.addLayer(l); else map.removeLayer(l); } });
        this._handlingClick = false;
        this._layerControlInputs.forEach(inp => { inp.checked = map.hasLayer(this._getLayer(inp.layerId).layer); });
        syncGroups();
      });
      lgroups.push([cb, ls]);
    });
    syncGroups();
    if (this._section) this._section.scrollTop = top;
    return this;
  };
  map.on("overlayadd overlayremove", syncGroups);   // an entry's own switch (Leaflet doesn't rebuild the list then)
  ctrl._update();

  // ---- legend panel ----
  const panel = L.control({position: "bottomleft"});
  panel.onAdd = () => {
    const div = L.DomUtil.create("div", "lgd");
    const LBLX = window.LBL || {};
    div.innerHTML = `<div class="lh"><b>${LBLX.title || "LA mountain streams"}</b><span><a class="to3d" href="stream_map_3d.html">3D view ↗</a><select class="areasel" title="Go to another area" style="font:inherit;font-size:11px;max-width:108px;margin-left:6px;border:1px solid #c9ced6;border-radius:5px;background:#fff;color:#1d1d1f;padding:1px 2px">${["<option value=''>Go to…</option>", "<option value='*'>All areas map</option>"].concat(((LBLX.areas) || []).filter(a => a.k !== LBLX.area).map(a => `<option value="${a.k}">${a.t}</option>`)).join("")}</select>
      <button class="lx" title="Hide / show">–</button></span></div>
      <div class="lb">
        <div class="seg">${[["drainage", "Drainage"], ["order", "Stream order"], ["fish", "Fish score"]]
          .map(([k, t]) => `<button data-m="${k}">${t}</button>`).join("")}</div>
        <div class="key"></div>
        <div class="wk"><span class="dm">Line width = Strahler order</span>${[1, 2, 3, 4, 5, 6].map(o =>
          `<span class="wo"><svg width="26" height="10"><line x1="2" y1="5" x2="24" y2="5" stroke="#445" stroke-width="${W[o]}" stroke-linecap="round"/></svg>${o}</span>`).join("")}</div>
        ${window.PCT ? `<div class="pk"><svg width="40" height="12"><line x1="4" y1="6" x2="36" y2="6" stroke="#ffd43b" stroke-opacity=".45" stroke-width="7" stroke-linecap="round"/><line x1="4" y1="6" x2="36" y2="6" stroke="#fff" stroke-opacity=".9" stroke-width="3.4" stroke-linecap="round"/><line x1="4" y1="6" x2="36" y2="6" stroke="#1d1d1f" stroke-width="1.7" stroke-dasharray="6 4"/></svg>${LONGTRAIL}</div>` : ""}
        ${window.TRAILS ? `<div class="pk tk"><svg width="34" height="10"><line x1="2" y1="5" x2="32" y2="5" stroke="#fff" stroke-width="4.4"/><line x1="2" y1="5" x2="32" y2="5" stroke="#5c3317" stroke-width="2" stroke-dasharray="5.2 3.6"/></svg>Trail
          <svg width="34" height="10"><line x1="2" y1="5" x2="32" y2="5" stroke="#fff" stroke-width="4.9"/><line x1="2" y1="5" x2="32" y2="5" stroke="#7a5a3a" stroke-width="2.5" stroke-dasharray="12.5 4.5"/></svg>Fire road</div>
          <div class="bk"><span class="dm">Trail edge = mountain bikes:</span> ${["yes", "likely", "unlikely", "no"].map(k =>
            `<span class="bkc"><i style="background:${BIKE[k][0]}"></i>${BIKE[k][1].replace(" for bikes", "").replace("Open to bikes", "Open")}</span>`).join("")}</div>` : ""}
      </div>`;
    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.disableScrollPropagation(div);
    div.querySelector(".lx").onclick = e => {
      div.classList.toggle("min"); e.target.textContent = div.classList.contains("min") ? "+" : "–";
    };
    div.querySelectorAll(".seg button").forEach(b => b.onclick = () => { mode = b.dataset.m; restyle(); });
    return div;
  };
  panel.addTo(map);
  const box = panel.getContainer();
  // the trail and bike keys show only while the trail layer is on
  const trailKey = () => { const on = map.hasLayer(trailGroup);
    box.querySelectorAll(".tk").forEach(el => { el.style.display = on ? "" : "none"; });
    box.querySelectorAll(".bk").forEach(el => { el.style.display = on && map.hasLayer(bikeView) ? "" : "none"; }); };
  map.on("overlayadd overlayremove", trailKey);
  trailKey();

  // a focused drainage stays focused across colour modes, so every mode shows how to clear it
  const focusBar = () => focus ? `<div class="fbar">Showing <b>${esc(focus)}</b> · <a href="#" class="clr">show all</a></div>` : "";
  function bindClear(key) {
    const clr = key.querySelector(".clr");
    if (clr) clr.onclick = e => { e.preventDefault(); focus = null; restyle(); };
  }
  function renderKey() {
    box.querySelectorAll(".seg button").forEach(b => b.classList.toggle("on", b.dataset.m === mode));
    const key = box.querySelector(".key");
    if (mode === "fish") {
      key.innerHTML = focusBar() + `<div class="ramp"><i style="background:${LOWCOL};flex:.9"></i>${RAMP.map(c => `<i style="background:${c}"></i>`).join("")}</div>
        <div class="rl"><span>0</span><span>${LOW}</span><span>fish score</span><span>100</span></div>
        <div class="dm">Gray = under ${LOW} (dry, tiny or burned). Wider = better.</div>`;
      bindClear(key);
      return;
    }
    if (mode === "order") {
      key.innerHTML = focusBar() + `<div class="ramp">${BLUE.slice(1, 7).map(c => `<i style="background:${c}"></i>`).join("")}</div>
        <div class="rl"><span>1</span><span>Strahler order</span><span>6</span></div>`;
      bindClear(key);
      return;
    }
    const byReg = {};
    DR.forEach(d => (byReg[d.region || "Other"] ??= []).push(d));
    key.innerHTML = `<div class="dm hint">Click a drainage to focus it${focus ? ` · <a href="#" class="clr">show all</a>` : ""}</div>` +
      `<div class="dl">` + Object.entries(byReg).map(([reg, ds]) =>
        (reg !== "Other" ? `<div class="rg">${esc(reg)}</div>` : "") + ds.map(d =>
          `<div class="di${focus === d.name ? " on" : ""}${focus && focus !== d.name ? " off" : ""}" data-d="${esc(d.name)}">` +
          `<i style="background:${d.color}"></i><span>${esc(d.name)}</span>` +
          (d.km2 ? `<em>${SQMI(d.km2)}</em>` : "") + `</div>` +
          (focus === d.name && d.forks && d.forks.length > 1 ? d.forks.map(f =>
            `<div class="fk"><i style="background:${f.color}"></i>${esc(f.name)}<em>${SQMI(f.km2)}</em></div>`).join("") : "")
        ).join("")).join("") + `</div>`;
    key.querySelectorAll(".di").forEach(el => el.onclick = () => {
      const d = DR.find(x => x.name === el.dataset.d);
      if (!d.b) return;                                  // minor drainages: nothing to focus
      focus = focus === d.name ? null : d.name;
      restyle();
      if (focus) map.fitBounds(d.b, {padding: [30, 30]});
    });
    bindClear(key);
  }
  restyle();
  // the 3D link opens the 3D map tilted over the current view
  const sync3d = () => { const c = map.getCenter();
    box.querySelector(".to3d").href = `stream_map_3d.html#${c.lat.toFixed(5)},${c.lng.toFixed(5)},${map.getZoom()},55`; };
  map.on("moveend", sync3d);
  // "Go to": another area's map, or the map of all areas at this view
  const asel = box.querySelector(".areasel");
  if (asel) asel.onchange = () => { const c = map.getCenter();
    if (asel.value === "*") location.href = `../index.html#${c.lat.toFixed(4)},${c.lng.toFixed(4)},${Math.min(map.getZoom(), 10)}`;
    else if (asel.value) location.href = `../${asel.value}/stream_map.html`; };

  // The spot being looked at in the creek profile viewer (profiles.html), shown by a ring on the creek. That page
  // sends it while the mouse is over the profile ("hover": the ring follows, the map only pans to keep it in view)
  // and when a spot is clicked ("pick": the map goes there). It also comes in a link, as #lat,lon,zoom,pin.
  // BroadcastChannel reaches the other tabs of the site; the localStorage copy does the same for pages opened from
  // disk, where some browsers keep the channel to one page. Areas ignore spots outside their own range.
  const pp = map.createPane("profpin");
  pp.style.zIndex = 660; pp.style.pointerEvents = "none";
  const pin = L.layerGroup([
    L.circleMarker([0, 0], {pane: "profpin", radius: 11, color: "#fff", weight: 5, opacity: 0.9, fill: false, interactive: false}),
    L.circleMarker([0, 0], {pane: "profpin", radius: 11, color: "#2a78d6", weight: 2.5, fill: true, fillColor: "#2a78d6",
                            fillOpacity: 0.15, interactive: false}),
    L.circleMarker([0, 0], {pane: "profpin", radius: 2.5, color: "#2a78d6", weight: 0, fill: true, fillOpacity: 1, interactive: false}),
  ]);
  const pinTip = L.tooltip({pane: "profpin", permanent: true, direction: "right", offset: [14, 0], className: "profpin-tip"});
  const areaBounds = L.geoJSON(window.DIVIDES).getBounds().pad(0.05);
  let lastSeq = -1;
  // the label's × takes the ring off (it comes back with the next spot sent from the profile), and drops a ",pin"
  // link's marker from the address so a reload doesn't bring it back
  function hidePin() {
    map.removeLayer(pin); map.removeLayer(pinTip);
    const parts = location.hash.slice(1).split(",");
    if (parts[3] === "pin") history.replaceState(null, "", "#" + parts.slice(0, 3).join(","));
  }
  function showPin(m) {
    if (!m || m.seq === lastSeq || !isFinite(m.lat) || !isFinite(m.lon)) return;
    lastSeq = m.seq;
    const ll = L.latLng(m.lat, m.lon);
    if (!areaBounds.contains(ll)) return;
    pin.eachLayer(l => l.setLatLng(ll));
    if (!map.hasLayer(pin)) pin.addTo(map);
    pinTip.setLatLng(ll).setContent(`<span>${esc(m.text || "Profile spot")}</span>` +
      `<button type="button" class="profpin-x" title="Remove this marker" aria-label="Remove this marker">×</button>`);
    if (!map.hasLayer(pinTip)) {
      pinTip.addTo(map);
      const el = pinTip.getElement();
      if (!el._pinWired) {          // the tooltip keeps its element between shows: wire it once
        el._pinWired = true;
        L.DomEvent.disableClickPropagation(el);
        L.DomEvent.on(el, "click", e => { if (e.target.closest(".profpin-x")) { L.DomEvent.stop(e); hidePin(); } });
      }
    }
    if (m.kind === "pick") map.setView(ll, Math.max(map.getZoom(), 15), {animate: true});
    else map.panInside(ll, {padding: [80, 80], animate: false});
  }
  if ("BroadcastChannel" in window) new BroadcastChannel("streams-profile-spot").onmessage = e => showPin(e.data);
  window.addEventListener("storage", e => {
    if (e.key === "streams-profile-spot" && e.newValue) try { showPin(JSON.parse(e.newValue)); } catch (_) {}
  });

  // open at #lat,lon,zoom (the overview's links), with ",pin" from the profile viewer's "Show on map" links
  function go() {
    const parts = location.hash.slice(1).split(","), h = parts.slice(0, 3).map(Number);
    if (h.length >= 2 && h.every(v => !isNaN(v))) {
      map.setView([h[0], h[1]], h[2] || 15, {animate: false});
      if (parts[3] === "pin") showPin({seq: "hash" + location.hash, kind: "hover", lat: h[0], lon: h[1],
                                       text: parts[4] ? decodeURIComponent(parts.slice(4).join(",")) : "Profile spot"});
    }
  }
  if (location.hash.length > 1) go(); else map.fitBounds(L.geoJSON(window.DIVIDES).getBounds(), {padding: [10, 10], animate: false});
  window.addEventListener("hashchange", go);
  sync3d();
}
