// Stream specs in the stream popups, and "Similar streams" (the user, 2026-11-25, after an r/bluelining thread on an
// ArcGIS map of NHDPlus High Resolution: bluelining anglers compare small trout streams by a few figures, its popup's
// "specs"). Shared by the area maps (map_drainages.js and map3d.html, inlined by 06_map.py) and the one-file phone map
// (14_portable.py: the specs line only); it adds its own styles.
//
// The specs line, the popup's first row (in its head, above the fish score: on a phone it stays clear of the open legend
// with the head, map_phone.js), in place of the "Order / drainage" and "Elev / gradient" rows: mean annual
// flow, velocity, slope, stream order, drainage area and the elevation of the reach's lower end, in imperial units
// (units.py). The reaches carry q (cfs) and le (m) from 06_map.py (streamspecs.py), and their order (o), drainage (a,
// km²) and gradient (gr, %) as before. The velocity is worked out here, as NHDPlus does (EROM, Jobson 1996), at the
// mean annual flow from the reach's own flow, drainage and slope: streamspecs.velocity(). The flow and the velocity are
// estimates ("about"); a reach with no flow estimate shows neither, a reach lying in a lake no velocity, and a reach the
// DEM reads flat (a gradient under 0.05 %, shown 0.0) its velocity as "under" what it would be at 0.05 %.
//
// Similar streams: a button after the specs highlights the streams of the map whose specs are like this reach's, and
// dims the rest, as a drainage picked in the legend does. A stream is like it when
//   its mean annual flow is within x/÷ 2 of this one's (where either has no flow estimate: its drainage within x/÷ 2),
//   its slope within x/÷ 1.5 (and at least ±0.3 % points: a flat river finds flat rivers, 0–0.3 %),
//   and its lower end within ±750 ft;
// on 2026-11-25's maps that is about 1–5 % of a map's stream miles for a trout creek of 1–20 cfs (median; north Georgia
// 4.9 %, the Smokies 2.9 %, Jackson 2.2 %, LA 0.6 %, southeast Pennsylvania 11 %). Each band is a switch in the note it
// opens by the layer panel (a tap leaves it out, another puts it back); "order" (the same Strahler order) starts off;
// "wider" takes x/÷ 3, x/÷ 2 (±0.5 points) and ±1,500 ft. The note counts the miles highlighted among the streams shown:
// the stream filters (map_filter.js) still hide what they hide, and the highlight is among what is left. It goes along
// with the switch between the 2D and 3D maps in the link, after the filter: "&like=q,gr,le,a,o,switches,name".
window.streamSpecs = (function () {
  const FT = 3.28084, SQMI = 0.386102, NB = " ";        // (a number keeps its unit on its line)
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const cfs = v => v >= 10 ? Math.round(v).toLocaleString("en-US") : v >= 1 ? v.toFixed(1) : v >= 0.01 ? v.toFixed(2) : "0.01";
  const sqmi = km2 => { const v = km2 * SQMI;
    return (v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 1 ? v.toFixed(1) : v.toFixed(2)) + NB + "sq" + NB + "mi"; };
  const feet = m => Math.round(m * FT).toLocaleString("en-US") + NB + "ft";
  const feet10 = m => (Math.round(m * FT / 10) * 10).toLocaleString("en-US");
  const has = v => v !== undefined && v !== null && v !== "" && !Number.isNaN(+v);
  const FLAT = 0.05;                                         // %: a gradient shown 0.0 is under this

  // the velocity (ft/s) at the mean annual flow q (cfs), drainage km2 and slope pct (%), as NHDPlus works it out
  // (streamspecs.velocity: Jobson's peak-concentration velocity at Q/Qa = 1)
  function vel(q, km2, pct) {
    const Q = q * 0.028316846592, Da = km2 * 1e6, S = pct / 100;
    if (!(Q > 0 && Da > 0 && S > 0)) return null;
    const v = 0.094 + 0.0143 * Math.pow(Math.pow(Da, 1.25) * Math.sqrt(9.80665) / Q, 0.919) * Math.pow(S, 0.159) * Q / Da;
    return v / 0.3048;
  }
  const inLake = p => !!p.lk || p.fl === "summer: reservoir";
  const fps = v => (v >= 0.1 ? v.toFixed(1) : "0.1") + NB + "ft/s";

  // the specs, as the popup reads them ("about" on the estimates)
  function text(p) {
    const flat = has(p.gr) && +p.gr === 0, out = [];
    if (has(p.q) && +p.q >= 0.01) {
      const v = inLake(p) || !has(p.a) ? null : vel(+p.q, +p.a, flat ? FLAT : +p.gr);
      out.push(`about ${cfs(+p.q)}${NB}cfs mean` + (v === null ? "" : (flat ? ", under " : ", ") + fps(v)));
    } else out.push(has(p.q) ? `under 0.01${NB}cfs mean` : "no flow estimate");     // (06_map.py rounds to 0.01)
    if (has(p.gr)) out.push(flat ? `slope under ${FLAT}%` : `slope ${(+p.gr).toFixed(1)}%`);
    if (has(p.o)) out.push(`order ${p.o}`);
    if (has(p.a)) out.push(sqmi(+p.a));
    const e = has(p.le) ? +p.le : null;
    if (e !== null) out.push(`lower end ${feet(e)}`);
    return out.join(" · ");
  }
  const HOW = "Mean annual flow: NHDPlus's gauge-adjusted mean (1971–2000) of the creek's NHDPlus line, or of the first one " +
    "below it, scaled to this reach's drainage. Velocity: at that flow, by NHDPlus's own formula (Jobson 1996), from the " +
    "flow, drainage and slope. Slope and lower-end elevation: the 10 m elevation model along the reach.";
  // the popup row; opts.like false: no "Similar streams" button (a page without the highlight: 14_portable.py)
  function row(p, opts) {
    const ref = {n: p.n || null, q: has(p.q) ? +p.q : null, gr: has(p.gr) ? +p.gr : null, le: has(p.le) ? +p.le : null,
                 a: has(p.a) ? +p.a : null, o: has(p.o) ? +p.o : null, el: has(p.el) ? +p.el : null};
    const btn = (opts || {}).like === false || ref.gr === null || ref.a === null ? "" :
      `<button type="button" class="lkb" data-lk="${encodeURIComponent(JSON.stringify(ref))}">Similar streams ›</button>`;
    return `<tr class="spr"><td title="${esc(HOW)}">Specs</td><td>${esc(text(p))}${btn}</td></tr>`;
  }

  // ---- similar streams ----
  const st = {ref: null, use: {q: 1, gr: 1, le: 1, o: 0}, wide: 0};
  let o = null, b = null, miles = null, last = "";
  const on = () => !!st.ref;
  function bands() {
    const r = st.ref, w = st.wide, fq = w ? 3 : 2, fg = w ? 2 : 1.5, mg = w ? 0.5 : 0.3, de = (w ? 1500 : 750) / FT, e = 1e-9;
    const lev = r.le ?? r.el;
    b = {q: r.q !== null ? [r.q / fq - e, r.q * fq + e] : null, a: [r.a / fq - e, r.a * fq + e],
         gr: [Math.max(0, Math.min(r.gr / fg, r.gr - mg)) - e, Math.max(r.gr * fg, r.gr + mg) + e],
         le: lev === null ? null : [lev - de, lev + de]};
  }
  // p is like the reference by the switches that are on
  function test(p) {
    if (!st.ref) return true;
    const u = st.use;
    if (u.q) {
      if (b.q && has(p.q)) { if (+p.q < b.q[0] || +p.q > b.q[1]) return false; }
      else { const a = has(p.a) ? +p.a : 0; if (a < b.a[0] || a > b.a[1]) return false; }
    }
    if (u.gr && (!has(p.gr) || +p.gr < b.gr[0] || +p.gr > b.gr[1])) return false;
    if (u.le && b.le) { const e = has(p.le) ? +p.le : has(p.el) ? +p.el : null;
      if (e === null || e < b.le[0] || e > b.le[1]) return false; }
    if (u.o && st.ref.o !== null && +p.o !== st.ref.o) return false;
    return true;
  }
  // the same as a MapLibre expression (map3d.html); null while off
  function expr() {
    if (!st.ref) return null;
    const u = st.use, c = ["all"], n = k => ["to-number", ["get", k], -1];
    const inb = (x, r) => ["all", [">=", x, r[0]], ["<=", x, r[1]]];
    if (u.q) c.push(b.q ? ["case", ["has", "q"], inb(n("q"), b.q), inb(n("a"), b.a)] : inb(n("a"), b.a));
    if (u.gr) c.push(inb(n("gr"), b.gr));
    if (u.le && b.le) c.push(inb(["to-number", ["coalesce", ["get", "le"], ["get", "el"]], -99999], b.le));
    if (u.o && st.ref.o !== null) c.push(["==", n("o"), st.ref.o]);
    return c;
  }
  // the miles highlighted, among the streams the filters keep (each reach's length worked out once, when first needed)
  function count() {
    const F = (o && o.features) || [];
    if (!miles) miles = F.map(f => {
      const g = f.geometry || {}, parts = g.type === "MultiLineString" ? g.coordinates : g.type === "LineString" ? [g.coordinates] : [];
      let s = 0;
      parts.forEach(c => { for (let i = 1; i < c.length; i++) {
        const k = Math.cos((c[i - 1][1] + c[i][1]) * Math.PI / 360);
        s += Math.hypot((c[i][0] - c[i - 1][0]) * 69.172 * k, (c[i][1] - c[i - 1][1]) * 68.703);
      } });
      return s;
    });
    const keep = window.streamFilter && streamFilter.on() ? streamFilter.pass : null;
    let all = 0, like = 0;
    F.forEach((f, i) => { const p = f.properties; if (keep && !keep(p)) return; all += miles[i]; if (test(p)) like += miles[i]; });
    return [like, all];
  }
  const mi = v => v >= 10 ? Math.round(v).toLocaleString("en-US") : v.toFixed(1);
  // the note: whose specs, the bands as switches, the miles; × ends it
  function render() {
    const el = o && o.note;
    if (!el) return;
    if (!st.ref) { el.hidden = true; el.innerHTML = ""; return; }
    const r = st.ref, u = st.use, lev = r.le ?? r.el;
    const chip = (k, label, onNow, title) => `<button type="button" class="lkc${onNow ? " on" : ""}" data-k="${k}" ` +
      `aria-pressed="${onNow ? "true" : "false"}" title="${esc(title)}">${label}</button>`;
    const flow = b.q ? `${cfs(r.q / (st.wide ? 3 : 2))}–${cfs(r.q * (st.wide ? 3 : 2))}${NB}cfs`
                     : `${sqmi(b.a[0])}–${sqmi(b.a[1])}`.replace(/ sq mi–/, "–");
    const [like, all] = count();
    el.innerHTML = `<div class="lkh"><span>Streams like <b>${esc(r.n || "this reach")}</b></span>` +
      `<button type="button" class="lkx" title="Show all streams again" aria-label="Show all streams again">×</button></div>` +
      `<div class="lkcs">` +
      chip("q", flow, u.q, b.q ? "Mean annual flow (a stream with no flow estimate: its drainage)" : "Drainage (this reach has no flow estimate)") +
      chip("gr", `slope ${(b.gr[0] + 1e-9).toFixed(1)}–${(b.gr[1] - 1e-9).toFixed(1)}%`, u.gr, "Slope") +
      (lev === null ? "" : chip("le", `${feet10(lev - (st.wide ? 1500 : 750) / FT)}–${feet10(lev + (st.wide ? 1500 : 750) / FT)}${NB}ft`,
                              u.le, "Elevation of the lower end")) +
      (r.o === null ? "" : chip("o", `order ${r.o}`, u.o, "The same stream order")) +
      chip("w", "wider", st.wide, "Wider bands: flow x/÷ 3, slope x/÷ 2, ±1,500 ft") + `</div>` +
      `<div class="lkm"><b>${mi(like)}</b> of ${mi(all)} mi of streams shown${window.streamFilter && streamFilter.on() ? " (filtered)" : ""}</div>`;
    el.hidden = false;
  }
  function apply() {
    if (st.ref) bands();
    const key = st.ref ? JSON.stringify([st.ref, st.use, st.wide]) : "";
    if (key !== last) { last = key; if (o) o.apply(st.ref ? test : null); }
    render();
    document.dispatchEvent(new CustomEvent("streamlike", {detail: {on: on()}}));
  }
  // highlight the streams like ref ({n, q, gr, le, a, o, el}); use/wide: the switches (default: flow, slope, elevation)
  function start(ref, use, wide) {
    st.ref = ref;
    st.use = Object.assign({q: 1, gr: 1, le: 1, o: 0}, use || {});
    st.wide = wide ? 1 : 0;
    apply();
  }
  function clear() { st.ref = null; apply(); }

  // "&like=q,gr,le,a,o,switches,name" (switches: f flow, s slope, e elevation, o order, w wider)
  function part() {
    if (!st.ref) return "";
    const r = st.ref, u = st.use;
    const sw = (u.q ? "f" : "") + (u.gr ? "s" : "") + (u.le ? "e" : "") + (u.o ? "o" : "") + (st.wide ? "w" : "");
    return "&like=" + [r.q ?? "", r.gr, r.le ?? r.el ?? "", r.a, r.o ?? "", sw || "-", encodeURIComponent(r.n || "")]
      .join(",").replace(/%20/g, "+");
  }
  function parse(hash) {
    let got = null;
    String(hash || "").replace(/^#/, "").split("&").slice(1).forEach(p => {
      const i = p.indexOf("=");
      if (p.slice(0, i) !== "like") return;
      const v = p.slice(i + 1).split(","), num = x => x === "" || x === undefined || isNaN(+x) ? null : +x;
      let n = null;
      try { n = decodeURIComponent((v.slice(6).join(",") || "").replace(/\+/g, " ")) || null; } catch (_) { n = null; }
      const ref = {q: num(v[0]), gr: num(v[1]), le: num(v[2]), a: num(v[3]), o: num(v[4]), n, el: null};
      if (ref.gr === null || ref.a === null) return;
      const sw = v[5] || "";
      got = {ref, use: {q: +sw.includes("f"), gr: +sw.includes("s"), le: +sw.includes("e"), o: +sw.includes("o")},
             wide: sw.includes("w")};
    });
    return got;
  }

  // init({features, note, apply, closePopup}): features = the drawn reaches outside lakes (GeoJSON, for the miles); note
  // = an element to fill with the note (the page puts it by the layer panel); apply(test) = dim every stream for which
  // test(properties) is false and highlight the rest (test null: as before); closePopup() = close the stream popup
  function init(opts) {
    o = opts;
    if (o.note) { o.note.classList.add("lknote"); o.note.hidden = true; }
    // the popup's button (a capture listener: the 2D map's popups keep their clicks from the page)
    document.addEventListener("click", e => {
      const t = e.target && e.target.closest ? e.target.closest(".lkb") : null;
      if (!t) return;
      e.preventDefault(); e.stopPropagation();
      let ref = null;
      try { ref = JSON.parse(decodeURIComponent(t.dataset.lk)); } catch (_) { return; }
      if (o.closePopup) o.closePopup();
      start(ref);
    }, true);
    if (o.note) o.note.addEventListener("click", e => {
      const t = e.target.closest("button");
      if (!t) return;
      e.stopPropagation();
      if (t.classList.contains("lkx")) { clear(); return; }
      const k = t.dataset.k;
      if (k === "w") st.wide = st.wide ? 0 : 1;
      else if (k) st.use[k] = st.use[k] ? 0 : 1;
      apply();
    });
    // the stream filters change what is shown, so the miles
    document.addEventListener("streamfilter", () => { if (st.ref) render(); });
    const came = parse(location.hash);
    if (came) start(came.ref, came.use, came.wide);
  }

  if (typeof document !== "undefined" && !document.getElementById("lk-style")) {
    const s = document.createElement("style");
    s.id = "lk-style";
    s.textContent =
      // the popup's button: a link a fingertip can take
      ".lkb{display:inline-block;margin:-4px 0 -4px 2px;border:0;background:none;padding:5px 4px;font:inherit;" +
      "color:#1864ab;cursor:pointer;text-align:left;white-space:nowrap}.lkb:hover{text-decoration:underline}" +
      // the note: under the 2D map's layer button (with the filter's), at the head of the 3D map's layer panel
      ".lknote{box-sizing:border-box;max-width:240px;background:#fff8db;border-radius:8px;box-shadow:0 1px 5px rgba(0,0,0,.25);" +
      "padding:4px 2px 5px 9px;font:12px/1.35 system-ui,-apple-system,sans-serif;color:#1d1d1f;text-align:left}" +
      ".lknote[hidden]{display:none}.lknote .lkh{display:flex;align-items:center;gap:2px}.lknote .lkh span{flex:1}" +
      ".lknote .lkx{flex:none;width:32px;height:32px;margin:-4px 0 -4px;border:0;border-radius:6px;background:none;padding:0;" +
      "font:20px/32px system-ui,-apple-system,sans-serif;color:#495057;cursor:pointer}.lknote .lkx:hover{background:#ffec99}" +
      ".lknote .lkcs{display:flex;flex-wrap:wrap;gap:4px;margin:3px 6px 3px 0}" +
      ".lknote .lkc{border:1px solid #e0c35a;border-radius:12px;background:#fff;padding:3px 8px;min-height:26px;" +
      "font:inherit;font-size:11.5px;color:#868e96;text-decoration:line-through;cursor:pointer}" +
      ".lknote .lkc.on{background:#ffe066;border-color:#f0b400;color:#1d1d1f;text-decoration:none}" +
      ".lknote .lkc[data-k=w]{text-decoration:none}" +
      ".lknote .lkm{color:#56606b}.lknote .lkm b{color:#1d1d1f}" +
      ".panel>.lknote{max-width:none;margin:7px -3px 0;box-shadow:none}";
    document.head.appendChild(s);
  }
  return {row, text, vel, init, start, clear, test, expr, on, part, parse, state: () => st};
})();
