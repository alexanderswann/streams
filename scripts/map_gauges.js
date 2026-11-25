// Live gauge readings and My Waters on the area maps (the user, 2026-11-25, picking onWater's "My Waters": follow flow
// stations, set an ideal flow and gauge-height range for each, and see each one's flow, height and water temperature,
// green inside the range and red outside). Shared by the 2D and 3D pages: 06_map.py inlines it in both, and the trout
// calendar (map_calendar.js) asks it for the reading under its "now".
//
// Readings. A tap on a USGS gauge shows its latest flow (cfs), gauge height (ft) and water temperature (°F), as far as
// the gauge reports them, with the reading's time. The visitor's own browser asks the USGS Water Data API
// (api.waterdata.usgs.gov) for them: the OGC API's latest-continuous values, and, once a day per gauge, the Statistics
// API's percentiles of the daily mean flow for today's date, which say how the flow compares with the usual ("below
// normal", "62% of the median"), read as 11_context.py reads them for the layer's colours. Both answer any web site
// (Access-Control-Allow-Origin: *, on their error answers too). No key is sent: a keyless request counts against the
// visitor's own connection (USGS's anonymous allowance); the project's key is for builds only and is never put in a page.
// A popup asks again only when its reading was fetched over 5 minutes ago.
// The phone keeps each reading it gets (localStorage), with its time. With no connection, or when USGS doesn't answer,
// a popup shows the newer of the last reading the phone saw and the one in the map's own data (LBL.gauge_list, from
// the build's snapshot), and says which and from when. A value the gauge didn't send is never shown: USGS's reason is
// (ice, equipment, not run this season...). An area saved for offline use (offline.js) keeps its gauges' last readings:
// they are fetched as it is saved, and again when it is opened with a connection and they are over 30 minutes old. A
// gauge's icon takes the colour of the newest reading the phone has for it (else the build's).
//
// My Waters. "☆ Add to My Waters" in a gauge's popup puts the gauge in the visitor's list, with a name of their own, an
// ideal flow range and, if wanted, a gauge-height range: green when the latest reading is inside them, red outside, grey
// with no range set or no reading. The list lives on the phone (localStorage), with no account: one list for all 12 maps
// (one site, one storage). The ★ button under the map's buttons (there once the list has a gauge) opens it; each gauge's
// "Show on map" goes to it, on this map or on the map it was added from (#lat,lon,zoom&on=gauges&gauge=<site>).
//
// The pages call gaugeLive.fill(element) for every popup they open (it fills what carries data-gauge or data-gauge-now
// in it), gaugeLive.mount({...}) once the map is ready (below), and keep a popup that grows in view ("popup-grow":
// map_phone.js, map3d.html). Its styles are its own (the end of this file).
(function () {
  "use strict";
  if (window.gaugeLive) return;
  const API = "https://api.waterdata.usgs.gov";
  const KEY_R = "streams.gauges.v1", KEY_W = "streams.mywaters.v1";   // the readings kept, the visitor's list
  const FRESH = 5 * 60e3;        // a reading fetched less than this ago isn't asked for again (gauges report every 15-60 min)
  const AREA_OLD = 30 * 60e3;    // a saved area's gauges are fetched again when their readings are older than this
  const OLD = 31 * 864e5;        // a series whose last value is older than this no longer reports
  const KEEP = 60 * 864e5;       // readings kept this long on the phone (those of the visitor's list for good)
  // the layer's colours for each comparison with the usual (06_map.py: gcol)
  const GCOL = {"much below normal": "#c92a2a", "below normal": "#f76707", "normal": "#2b8a3e", "above normal": "#1c7ed6",
                "much above normal": "#1864ab", "dry": "#c92a2a", "dry (normal for date)": "#adb5bd",
                "flowing (usually dry on this date)": "#1c7ed6", "no history": "#868e96"};
  // USGS's qualifiers, in words (a value it flags, or the reason it sends none)
  const QUAL = {ICE: "ice", EQUIP: "equipment trouble", SEASONAL: "not run this season", DISCONTINUED: "discontinued",
                ESTIMATED: "estimated", BACKWATER: "backwater", RATINGDEV: "rating being worked out", UNAVAIL: "unavailable",
                FLOOD: "flood damage", DRY: "dry", ZEROFLOW: "zero flow", MAINT: "maintenance", REVISED: "revised",
                LESSTHAN: "less than shown", REGULATED: "regulated", BLWMIN: "below the sensor's range", TIDE: "tidal",
                DAMFAILURE: "dam failure", PARTIAL: "partial record", PROVISIONAL: "provisional"};
  const IN = "#2b8a3e", OUT = "#c92a2a", NONE = "#adb5bd";
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const LBLX = () => window.LBL || (window.MAP3D || {}).lbl || {};
  const md = d => String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const num = v => Number(v).toLocaleString("en-US", {maximumFractionDigits: 2});
  const sameDay = (a, b) => a.toDateString() === b.toDateString();
  const dayOf = ms => { const d = new Date(ms);
    return d.toLocaleDateString("en-US", {month: "short", day: "numeric",
                                          year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric"}); };
  const when = ms => (sameDay(new Date(ms), new Date()) ? "" : dayOf(ms) + ", ") +
    new Date(ms).toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit"});
  const ago = ms => { const m = Math.max(0, Math.round((Date.now() - ms) / 60e3));
    return m < 2 ? "just now" : m < 60 ? `${m} min ago` : m < 48 * 60 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} days ago`; };
  const old = x => !x || Date.now() - x[1] > OLD;

  // ---- this map's USGS gauges: LBL.gauge_list, [site, name, lat, lon, cfs, time (UTC), status, % of median, median] ----
  let G = null;
  function mapGauges() {
    if (!G) {
      G = new Map();
      (LBLX().gauge_list || []).forEach(([s, n, y, x, q, t, st, pct, med]) =>
        G.set(String(s), {s: String(s), n, y, x, q, t, st, pct, med}));
    }
    return G;
  }

  // ---- what the phone keeps (localStorage) ----
  const load = k => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
  const store = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } };
  // the readings, by site: {f: fetched (ms), q: flow, h: gauge height, w: water temperature, each [value (cfs, ft, °F;
  // null: none sent), time (ms), [qualifiers], provisional 1/0] or null; P: today's percentiles of the daily mean flow
  // [p10, p25, p50, p75, p90] for the day d ("MM-DD"), or null; none: 1 when USGS sent nothing current}
  let R = null;
  const readings = () => R || (R = load(KEY_R) || {});
  function keepReadings() {
    const r = readings(), now = Date.now(), mine = new Set(favs().map(f => f.s));
    Object.keys(r).forEach(s => { if (!mine.has(s) && !(now - (r[s].f || 0) <= KEEP)) delete r[s]; });
    // a full storage: the oldest that aren't the visitor's go first
    for (let i = 0; i < 50 && !store(KEY_R, r); i++) {
      const drop = Object.keys(r).filter(s => !mine.has(s)).sort((a, b) => (r[a].f || 0) - (r[b].f || 0)).slice(0, 20);
      if (!drop.length) break;
      drop.forEach(s => delete r[s]);
    }
  }
  // the visitor's list: [{s: site, n: their name, g: the gauge's own name, a: area key, at: the area's title, y, x,
  // q0, q1 (cfs), h0, h1 (ft): the ideal range, null where open, add: when added (ms)}]
  const favs = () => (load(KEY_W) || []).filter(f => f && f.s);
  const isFav = s => favs().some(f => f.s === s);
  let storeOk = true;
  function saveFavs(list) { storeOk = store(KEY_W, list); syncButton(); }

  // ---- asking USGS ----
  async function getJSON(url) {
    const c = new AbortController(), t = setTimeout(() => c.abort(), 15000);
    try {
      const r = await fetch(url, {signal: c.signal, cache: "no-store", credentials: "omit"});
      if (!r.ok) { const e = new Error("USGS answered " + r.status); e.status = r.status; throw e; }
      return await r.json();
    } finally { clearTimeout(t); }
  }
  const chunks = (xs, n) => { const out = []; for (let i = 0; i < xs.length; i += n) out.push(xs.slice(i, i + n)); return out; };
  // the newest value of each site's flow (00060), gauge height (00065) and water temperature (00010 in °C, 00011 in °F),
  // 40 sites to a request (the API refuses long addresses). A gauge can keep a retired sensor's last value beside the
  // current one (Little Falls: water temperatures from 2019): the newest series wins.
  const CODES = {"00060": "q", "00065": "h", "00010": "w", "00011": "w"};
  async function latest(sites) {
    const out = {};
    for (const ids of chunks(sites, 40)) {
      let url = `${API}/ogcapi/v1/collections/latest-continuous/items?` + new URLSearchParams({
        f: "json", monitoring_location_id: ids.map(s => "USGS-" + s).join(","), parameter_code: Object.keys(CODES).join(","),
        properties: "monitoring_location_id,parameter_code,time,value,qualifier,approval_status", skipGeometry: "true",
        limit: "1000"});
      for (let page = 0; url && page < 4; page++) {
        const js = await getJSON(url);
        (js.features || []).forEach(f => {
          const p = f.properties || {}, s = String(p.monitoring_location_id || "").replace(/^USGS-/, "");
          const k = CODES[p.parameter_code], t = Date.parse(p.time);
          if (!k || !s || !isFinite(t)) return;
          let v = p.value == null || p.value === "" ? null : Number(p.value);
          if (v !== null && !isFinite(v)) v = null;
          if (v !== null && p.parameter_code === "00010") v = v * 9 / 5 + 32;
          const ql = (Array.isArray(p.qualifier) ? p.qualifier : p.qualifier ? [p.qualifier] : []).map(String);
          const o = out[s] || (out[s] = {}), cur = o[k];
          if (!cur || t > cur[1] || (t === cur[1] && cur[0] === null && v !== null))
            o[k] = [v, t, ql, /provisional/i.test(p.approval_status || "") ? 1 : 0];
        });
        const nx = (js.features || []).length >= 1000 && (js.links || []).find(l => l.rel === "next");
        url = nx ? nx.href : null;
      }
    }
    return out;
  }
  // today's percentiles of each site's daily mean flow (the day-of-year normals over its approved record), 20 sites to
  // a request as 11_context.py asks: [p10, p25, p50, p75, p90] (null where one is missing), or null for a site with none.
  // The API's quirk: a date dry in every year gives "nan" percentiles, which a maximum of 0 makes all 0. Of a site's
  // series the daily mean's (statistic 00003), else the longest record.
  async function normals(sites, day) {
    const out = {};
    for (const ids of chunks(sites, 20)) {
      let tok = null, page = 0;
      do {
        const q = new URLSearchParams();
        ids.forEach(s => q.append("monitoring_location_id", "USGS-" + s));
        [["parameter_code", "00060"], ["normal_type", "DOY"], ["start_date", day], ["end_date", day],
         ["computation_type", "percentile"], ["computation_type", "maximum"], ["page_size", "1000"]]
          .forEach(([k, v]) => q.append(k, v));
        if (tok) q.set("next_token", tok);
        const js = await getJSON(`${API}/statistics/v0/observationNormals?${q}`);
        (js.features || []).forEach(f => {
          const pr = f.properties || {}, s = String(pr.monitoring_location_id || "").replace(/^USGS-/, "");
          let best = null;
          (pr.data || []).forEach(d => {
            const v = {};
            (d.values || []).forEach(x => { if (x.time_of_year === day) v[x.computation] = x; });
            if (!v.percentile) return;
            const pc = (v.percentile.percentiles || []).map(String), vals = v.percentile.values || [];
            let P = ["10", "25", "50", "75", "90"].map(p => { const i = pc.indexOf(p), n = i < 0 ? NaN : Number(vals[i]);
                                                            return isFinite(n) ? n : null; });
            if (v.maximum && v.maximum.value != null && Number(v.maximum.value) === 0) P = P.map(() => 0);
            const yrs = v.percentile.sample_count || 0, mean = d.parent_statistic_id === "00003";
            if (!best || (mean && !best.mean) || (mean === best.mean && yrs > best.yrs)) best = {P, yrs, mean};
          });
          if (s && best) out[s] = best.P;
        });
        tok = js.next || null;
        page++;
      } while (tok && page < 5);
      ids.forEach(s => { if (!(s in out)) out[s] = null; });
    }
    return out;
  }
  // the flow against the usual for its date: 11_context.py's rel(), word for word
  function rel(q, P) {
    if (!P || P[2] == null) return "no history";
    if (q <= 0) return P[2] > 0 ? "dry" : "dry (normal for date)";
    if (P[2] === 0) return "flowing (usually dry on this date)";
    for (const [i, lab] of [[0, "much below normal"], [1, "below normal"], [3, "normal"], [4, "above normal"]])
      if (P[i] != null && q < P[i]) return lab;
    return P[4] != null ? "much above normal" : "above normal";
  }

  // ---- fetching, once at a time per gauge ----
  const online = () => navigator.onLine !== false && !(window.StreamsOffline && StreamsOffline.net && !StreamsOffline.net());
  const loading = new Map();     // site -> the request under way
  const tried = {};              // site -> the last try's outcome: "ok", "offline", "busy" (429), "refused" (other 4xx), "failed"
  let pause = 0;                 // after a "too many requests" (429): no request before this time
  async function refresh(sites, force) {
    const r = readings(), now = Date.now(), day = md(new Date());
    sites = [...new Set(sites.map(String))].filter(s => /^\d{8,15}$/.test(s));
    const waits = sites.filter(s => loading.has(s)).map(s => loading.get(s));
    const need = sites.filter(s => !loading.has(s) && (force || !r[s] || !(now - (r[s].f || 0) <= FRESH)));
    if (need.length && !online()) need.forEach(s => { tried[s] = "offline"; });
    else if (need.length && now < pause) need.forEach(s => { tried[s] = "busy"; });
    else if (need.length) {
      const job = (async () => {
        const ask = need.filter(s => !(r[s] && r[s].d === day));
        const [lat, nor] = await Promise.all([latest(need), ask.length ? normals(ask, day).catch(() => null) : null]);
        const t = Date.now();
        need.forEach(s => {
          const o = lat[s] || {}, was = r[s] || {};
          const P = nor && s in nor ? nor[s] : was.d === day ? was.P : null;
          const d = nor && s in nor ? day : was.d === day ? day : null;
          // (USGS sent nothing for it: the last values the phone saw stay, shown as such)
          r[s] = o.q || o.h || o.w ? {f: t, q: o.q || null, h: o.h || null, w: o.w || null, P, d}
            : {f: t, q: was.q || null, h: was.h || null, w: was.w || null, P: was.P || null, d: was.d || null, none: 1};
          tried[s] = "ok";
        });
        keepReadings();
      })();
      need.forEach(s => loading.set(s, job));
      try { await job; }
      catch (e) {
        let why = e && e.status === 429 ? "busy" : e && e.status >= 400 && e.status < 500 ? "refused" : e && e.status ? "failed" : "net";
        if (why === "busy") pause = Date.now() + 10 * 60e3;     // (USGS's anonymous allowance is per hour)
        if (why === "net") why = window.StreamsOffline && StreamsOffline.check ? ((await StreamsOffline.check().catch(() => false)) ? "failed" : "offline")
                                                                               : navigator.onLine === false ? "offline" : "failed";
        need.forEach(s => { tried[s] = why; });
      } finally { need.forEach(s => { if (loading.get(s) === job) loading.delete(s); }); }
    }
    await Promise.all(waits.map(w => w.catch(() => {})));
    repaint(sites);
  }

  // ---- what to show for a gauge ----
  // the phone's reading (fetched now or before) or the map's own (the build's), whichever is newer
  function cur(s) {
    const r = readings()[s], g = mapGauges().get(s);
    const phone = r && (r.q || r.h || r.w) ? {src: "phone", q: r.q, h: r.h, w: r.w, P: r.P, d: r.d} : null;
    const t = g && g.t ? Date.parse(g.t) : NaN;
    const built = isFinite(t) && g.q != null ? {src: "map", q: [g.q, t, [], 0], h: null, w: null, st: g.st, pct: g.pct, med: g.med} : null;
    const time = c => Math.max(0, ...["q", "h", "w"].map(k => c[k] ? c[k][1] : 0));
    if (phone && (!built || time(phone) >= time(built))) return phone;
    return built || phone;
  }
  // the time the reading stands for: its flow's, else the newest of the others
  const mainTime = c => c.q && !old(c.q) ? c.q[1] : Math.max(...["q", "h", "w"].map(k => c[k] ? c[k][1] : 0));
  // the flow against the usual for its date: from today's percentiles where they are for the reading's own day, the
  // build's own words for the map's reading; null when unknown
  function stat(c) {
    if (!c || !c.q || c.q[0] == null || old(c.q)) return null;
    if (c.src === "map") return c.st && c.st !== "no history" ? {st: c.st, pct: c.pct, med: c.med} : null;
    if (!c.P || c.d !== md(new Date(c.q[1]))) return null;
    const st = rel(c.q[0], c.P);
    return st === "no history" ? null : {st, pct: c.P[2] > 0 ? Math.round(100 * c.q[0] / c.P[2]) : null, med: c.P[2]};
  }
  const quals = x => (x[2] || []).map(q => QUAL[q] || q.toLowerCase()).filter(w => w !== "provisional");
  // a value as shown: its number and unit, or why there is none; its own time where it isn't the reading's
  function val(x, unit, tm, flow) {
    if (old(x)) return `<span class="gdm">no reading since ${dayOf(x[1])}</span>`;
    const w = quals(x);
    const v = x[0] == null ? `<span class="gdm">no value${w.length ? " (" + esc(w.join(", ")) + ")" : ""}</span>`
      : (flow ? `<b>${num(x[0])} ${unit}</b>` : `${unit === "°F" ? Math.round(x[0]) : num(x[0])} ${unit}`) +
        (w.length ? ` <span class="gdm">(${esc(w.join(", "))})</span>` : "");
    return v + (Math.abs(x[1] - tm) > 2 * 3600e3 ? ` <span class="gdm">(${when(x[1])})</span>` : "");
  }
  // what kind of reading it is, and why it isn't a fresh one
  function source(s, c) {
    const r = readings()[s], why = online() ? tried[s] : "offline";
    const pre = loading.has(s) ? "" : why === "offline" ? "No connection. " : why === "busy" ? "USGS is busy (too many requests). "
      : why === "refused" ? "USGS refused the request. " : why === "failed" ? "USGS didn't answer. "
      : why === "ok" && r && r.none ? "USGS sent no current reading. " : "";
    const kind = !c ? "" : c.src === "map" ? "In the map's data" : pre ? "Last seen on this phone" : "USGS reading";
    return [pre, kind];
  }
  function readingHtml(s) {
    const c = cur(s), [pre, kind] = source(s, c), busy = loading.has(s);
    if (!c) return `<div class="gwhen">${busy ? "Getting the latest reading…" : esc(pre) + (pre.startsWith("No connection") ?
      "No reading kept on this phone." : "No reading yet.")}</div>`;
    const tm = mainTime(c), st = stat(c), rows = [];
    if (c.q) rows.push(["Flow", val(c.q, "cfs", tm, true) + (st ? ` · <span class="gst" style="color:${GCOL[st.st] || "#495057"}">${esc(st.st)}</span>` +
      (st.pct != null && st.med != null ? `<div class="gsub">${st.pct}% of the median for the date (${num(st.med)} cfs)</div>` : "") : "")]);
    if (c.h && !old(c.h)) rows.push(["Gauge height", val(c.h, "ft", tm)]);
    if (c.w && !old(c.w)) rows.push(["Water", val(c.w, "°F", tm)]);
    const prov = ["q", "h", "w"].some(k => c[k] && c[k][3]);
    return `<table class="gt">${rows.map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join("")}</table>` +
      `<div class="gwhen">${pre ? `<span class="gwarn">${esc(pre)}</span>` : ""}${kind}: ${when(tm)} · ${ago(tm)}` +
      `${prov ? " · provisional" : ""}${busy ? " · updating…" : ""}</div>`;
  }
  function paintPopup(el) {
    const s = el.dataset.gauge;
    let now = el.querySelector(".gnow");
    if (!now) { now = document.createElement("div"); now.className = "gnow"; el.appendChild(now); }
    now.innerHTML = readingHtml(s);
    let act = el.querySelector(".gact");
    if (!act) { act = document.createElement("div"); act.className = "gact"; el.appendChild(act); }
    let b = act.querySelector(".gfav");
    if (!b) { b = document.createElement("button"); b.type = "button"; b.className = "gfav"; act.insertBefore(b, act.firstChild); }
    const on = isFav(s);
    b.dataset.fav = s;
    b.classList.toggle("on", on);
    b.textContent = on ? "★ In My Waters ›" : "☆ Add to My Waters";
    b.title = on ? "Open My Waters, the gauges you follow" : "Follow this gauge in My Waters, with your ideal flow";
  }
  // the trout calendar's "now" on a reach with a gauge on its creek (map_calendar.js)
  function paintCal(el) {
    const s = el.dataset.gaugeNow, c = cur(s), g = mapGauges().get(s);
    if (!c || !c.q || c.q[0] == null || old(c.q)) {
      el.innerHTML = loading.has(s) && !c ? `<span class="cdm">At the gauge: getting the latest reading…</span>` : "";
      return;
    }
    const why = online() ? tried[s] : "offline", st = stat(c);
    const note = why === "offline" ? "no connection" : why === "busy" ? "USGS busy" : why === "refused" ? "USGS refused"
      : why === "failed" ? "USGS didn't answer" : "";
    const live = c.src === "phone" && !note && Date.now() - c.q[1] < 3 * 3600e3;
    el.title = g ? `USGS gauge: ${g.n}` : "USGS gauge";
    el.innerHTML = `<span class="cdm">At the gauge ${live ? "now" : when(c.q[1])}:</span> ` +
      `${num(c.q[0])} cfs${st ? `, <span style="color:${GCOL[st.st] || "inherit"}">${esc(st.st)}</span>` : ""}` +
      (c.w && c.w[0] != null && !old(c.w) ? ` · water ${Math.round(c.w[0])} °F` : "") +
      ` <span class="cdm">(${[ago(c.q[1]), c.src === "map" ? "the map's data" : "", note].filter(Boolean).join("; ")})</span>`;
  }
  const siteOf = el => el.dataset.gauge || el.dataset.gaugeNow;
  const paint = el => (el.dataset.gaugeNow !== undefined ? paintCal : paintPopup)(el);
  const grew = () => document.dispatchEvent(new CustomEvent("popup-grow"));
  function repaint(sites) {
    const set = new Set(sites);
    let n = 0;
    document.querySelectorAll("[data-gauge], [data-gauge-now]").forEach(el => { if (set.has(siteOf(el))) { paint(el); n++; } });
    recolor(sites);
    if (list && !list.hidden) items();
    if (n) grew();
  }
  // a popup just opened: what it has of gauges shown at once from what is kept, then fetched where it is old
  function fill(root) {
    if (!root || !root.querySelectorAll) return;
    const els = [...root.querySelectorAll("[data-gauge], [data-gauge-now]")];
    if (!els.length) return;
    style();
    const go = refresh(els.map(siteOf));     // (marks them loading first)
    els.forEach(paint);
    grew();
    return go;
  }
  // a gauge's icon in the colour of the newest reading the phone has, where it knows how that compares with the usual
  function recolor(sites) {
    if (!opts.recolor) return;
    sites.forEach(s => {
      if (!mapGauges().has(s)) return;
      const c = cur(s), st = c && c.src === "phone" ? stat(c) : null;
      if (st && GCOL[st.st]) opts.recolor(s, GCOL[st.st]);
    });
  }

  // ---- My Waters ----
  let opts = {}, list = null, bar = null, editing = null;
  const rng = (a, b, unit) => a != null && b != null ? `${num(a)}–${num(b)} ${unit}` : a != null ? `${num(a)} ${unit} or more`
    : b != null ? `up to ${num(b)} ${unit}` : "";
  // against the visitor's ranges: [colour, words]
  function judge(f, c) {
    const checks = [];
    const one = (lab, x, lo, hi, unit) => {
      if (lo == null && hi == null) return;
      const v = x && !old(x) ? x[0] : null;
      if (v == null) { checks.push([null, `no current ${lab}`]); return; }
      const ok = (lo == null || v >= lo) && (hi == null || v <= hi);
      checks.push([ok, ok ? `${lab} in your range (${rng(lo, hi, unit)})`
                              : `${lab} ${lo != null && v < lo ? "below" : "above"} your range (${rng(lo, hi, unit)})`]);
    };
    one("flow", c && c.q, f.q0, f.q1, "cfs");
    one("height", c && c.h, f.h0, f.h1, "ft");
    if (!checks.length) return [NONE, "No range set: Edit to add yours"];
    const say = ks => { const t = ks.map(k => k[1]).join(" · "); return t[0].toUpperCase() + t.slice(1); };
    const bad = checks.filter(k => k[0] === false);
    if (bad.length) return [OUT, say(bad)];
    return [checks.some(k => k[0] === null) ? NONE : IN, say(checks)];
  }
  function short(s, c) {
    if (!c) return `<span class="gdm">${loading.has(s) ? "Getting the latest reading…" : "No reading kept on this phone"}</span>`;
    const tm = mainTime(c), st = stat(c);
    const bits = [c.q ? (old(c.q) ? "no flow reading lately" : c.q[0] == null ? `flow: no value${quals(c.q).length ? " (" + quals(c.q).join(", ") + ")" : ""}`
                         : `<b>${num(c.q[0])} cfs</b>`) : "",
                  c.h && !old(c.h) && c.h[0] != null ? `${num(c.h[0])} ft` : "",
                  c.w && !old(c.w) && c.w[0] != null ? `${Math.round(c.w[0])} °F` : ""].filter(Boolean);
    const [pre, kind] = source(s, c);
    return bits.join(" · ") + (st ? ` · <span style="color:${GCOL[st.st] || "inherit"}">${esc(st.st)}</span>` : "") +
      `<div class="gdm">${pre ? `<span class="gwarn">${esc(pre)}</span>` : ""}${kind === "USGS reading" ? "" : kind + ": "}${when(tm)} · ${ago(tm)}${loading.has(s) ? " · updating…" : ""}</div>`;
  }
  const field = (k, v, ph) => `<input name="${k}" inputmode="decimal" autocomplete="off" placeholder="${ph}" value="${v == null ? "" : esc(v)}">`;
  function itemHtml(f) {
    const c = cur(f.s), [col, words] = judge(f, c), here = mapGauges().has(f.s);
    const ed = editing === f.s;
    return `<div class="mwi${ed ? " ed" : ""}" data-s="${esc(f.s)}">` +
      `<div class="mwt"><i class="mwd" style="background:${col}"></i><b>${esc(f.n)}</b>` +
      `<button type="button" class="mwb" data-act="edit">${ed ? "Close" : "Edit"}</button></div>` +
      `<div class="mwv">${short(f.s, c)}</div><div class="mwj" style="color:${col === NONE ? "#6b7280" : col}">${esc(words)}</div>` +
      `<div class="mwa"><a href="#" data-act="go">Show on map ›</a> <span class="gdm">${here ? "this map" : esc(f.at || f.a || "")}` +
      `${f.g && f.g !== f.n ? " · " + esc(f.g) : ""}</span></div>` +
      (ed ? `<form class="mwed" data-s="${esc(f.s)}" novalidate>` +
        `<label class="mwrow">Name <input name="n" autocomplete="off" value="${esc(f.n)}"></label>` +
        `<div class="mwrow">Ideal flow ${field("q0", f.q0, "least")} – ${field("q1", f.q1, "most")} cfs</div>` +
        `<div class="mwrow">Gauge height ${field("h0", f.h0, "least")} – ${field("h1", f.h1, "most")} ft</div>` +
        `<div class="gdm">Leave a box empty for no limit; the height is optional.</div><div class="mwmsg"></div>` +
        `<div class="mwbtns"><button type="submit" class="mwsave">Save</button><button type="button" data-act="cancel">Cancel</button>` +
        `<button type="button" data-act="remove" class="mwdel">Remove</button></div></form>` : "") + `</div>`;
  }
  // the list: drawn whole when gauges come or go or the editor opens; the readings alone otherwise (what the visitor is
  // typing stays)
  function draw() {
    if (!list) return;
    const F = favs();
    list.querySelector(".mwn").textContent = F.length ? `(${F.length})` : "";
    list.querySelector(".mwl").innerHTML = F.length ? F.map(itemHtml).join("")
      : `<div class="mwempty">No gauges yet. Turn on the gauges layer (View &amp; layers), tap a gauge, then ` +
        `<b>☆ Add to My Waters</b>.</div>`;
    list.querySelector(".mwst").innerHTML = storeOk ? "" : `<span class="gwarn">This browser isn't keeping data for this site ` +
      `(private browsing?): the list goes when the page closes.</span>`;
  }
  function items() {
    if (!list) return;
    const F = favs();
    list.querySelectorAll(".mwi").forEach(el => {
      const f = F.find(x => x.s === el.dataset.s);
      if (!f) return;
      const c = cur(f.s), [col, words] = judge(f, c);
      el.querySelector(".mwd").style.background = col;
      el.querySelector(".mwv").innerHTML = short(f.s, c);
      const j = el.querySelector(".mwj");
      j.textContent = words; j.style.color = col === NONE ? "#6b7280" : col;
    });
    const ts = F.map(f => (readings()[f.s] || {}).f || 0).filter(Boolean);
    list.querySelector(".mwup").textContent = F.length && ts.length ? `Checked ${when(Math.max(...ts))}` : "";
  }
  function buildList() {
    list = document.createElement("div");
    list.className = "mw";
    list.hidden = true;
    list.setAttribute("role", "dialog");
    list.setAttribute("aria-label", "My Waters");
    list.innerHTML = `<div class="mwh"><b>★ My Waters <span class="mwn"></span></b><span>` +
      `<button type="button" data-act="refresh" title="Get the latest readings" aria-label="Get the latest readings">↻</button>` +
      `<button type="button" data-act="close" title="Close" aria-label="Close">×</button></span></div>` +
      `<div class="mws"><span class="mwup"></span> <span class="mwst"></span></div><div class="mwl"></div>` +
      `<div class="mwf">Flows from USGS gauges (provisional data), read by this browser. Kept on this device only, ` +
      `with no account.</div>`;
    (opts.host || document.body).appendChild(list);
    if (opts.shield) opts.shield(list);
    list.addEventListener("click", e => {
      const a = e.target.closest("[data-act]");
      if (!a) return;
      e.preventDefault();
      const it = a.closest(".mwi"), s = it && it.dataset.s, act = a.dataset.act;
      if (act === "close") close();
      else if (act === "refresh") { const F = favs().map(f => f.s); if (F.length) { refresh(F, true); items(); } }
      else if (act === "edit") { editing = editing === s ? null : s; draw(); focusEditor(); }
      else if (act === "cancel") { editing = null; draw(); }
      else if (act === "remove") {
        const f = favs().find(x => x.s === s);
        if (f && confirm(`Remove ${f.n} from My Waters?`)) { saveFavs(favs().filter(x => x.s !== s)); editing = null; draw(); repaint([s]); }
      } else if (act === "go") goTo(favs().find(x => x.s === s));
    });
    list.addEventListener("submit", e => {
      e.preventDefault();
      const fm = e.target, s = fm.dataset.s, msg = fm.querySelector(".mwmsg");
      const numIn = k => { const t = String(fm.elements[k].value || "").trim().replace(/,/g, "");
                           if (!t) return null; const v = Number(t); return isFinite(v) && v >= 0 ? v : NaN; };
      let [q0, q1, h0, h1] = ["q0", "q1", "h0", "h1"].map(numIn);
      if ([q0, q1, h0, h1].some(v => Number.isNaN(v))) { msg.textContent = "Numbers only, 0 or more (or leave the box empty)."; return; }
      if (q0 != null && q1 != null && q0 > q1) [q0, q1] = [q1, q0];
      if (h0 != null && h1 != null && h0 > h1) [h0, h1] = [h1, h0];
      const F = favs(), f = F.find(x => x.s === s);
      if (!f) return;
      Object.assign(f, {n: String(fm.elements.n.value || "").trim().slice(0, 80) || f.g || "USGS " + s, q0, q1, h0, h1});
      saveFavs(F);
      editing = null;
      draw(); items();
    });
  }
  function focusEditor() {
    const fm = list && list.querySelector(".mwed");
    if (!fm) return;
    fm.scrollIntoView({block: "nearest"});
    const empty = ["q0", "q1"].map(k => fm.elements[k]).find(i => !i.value);
    if (empty && window.innerWidth > 640) empty.focus();     // (on a phone the keyboard would cover the list at once)
  }
  // the list; edit: a gauge whose editor opens (one just added), at: one to show (one already in it)
  function open(edit, at) {
    if (!list) buildList();
    editing = edit || null;
    list.hidden = false;
    draw(); items();
    if (editing) focusEditor();
    const it = at && [...list.querySelectorAll(".mwi")].find(el => el.dataset.s === at);
    if (it) { it.scrollIntoView({block: "nearest"}); it.classList.add("hl"); setTimeout(() => it.classList.remove("hl"), 1600); }
    const F = favs().map(f => f.s);
    if (F.length) refresh(F);
  }
  function close() { if (list) { list.hidden = true; editing = null; } }
  function add(s) {
    const F = favs();
    if (F.some(f => f.s === s)) return;
    const g = mapGauges().get(s) || {}, L0 = LBLX();
    F.push({s, n: g.n || "USGS " + s, g: g.n || "", a: L0.area || "", at: L0.title || "", y: g.y, x: g.x,
            q0: null, q1: null, h0: null, h1: null, add: Date.now()});
    saveFavs(F);
    repaint([s]);
  }
  // a gauge on this map: its popup here; one on another map: that map, the gauges on, its popup opened (the link's
  // gauge=, read by fromHash there)
  function goTo(f) {
    if (!f) return;
    if (mapGauges().has(f.s) && opts.show) { if (window.innerWidth <= 640) close(); opts.show(f.s); return; }
    if (!f.a || f.y == null) return;
    const page = opts.kind === "3d" ? "stream_map_3d.html" : "stream_map.html";
    location.href = `../${encodeURIComponent(f.a)}/${page}#${(+f.y).toFixed(5)},${(+f.x).toFixed(5)},13&on=gauges&gauge=${f.s}`;
  }
  function fromHash() {
    const m = /[#&]gauge=(\d{8,15})(?=&|$)/.exec(location.hash);
    if (!m) return;
    history.replaceState(null, "", location.href.replace(/&gauge=\d+(?=&|$)/, ""));
    if (mapGauges().has(m[1]) && opts.show) setTimeout(() => opts.show(m[1]), 250);
  }
  const STAR = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 2.6l2.9 6 6.6.8-4.9 4.6 1.3 6.5L12 17.3l-5.9 3.2 1.3-6.5L2.5 9.4l6.6-.8z" ' +
    'fill="currentColor" stroke="#7a5b00" stroke-width="1" stroke-linejoin="round"/></svg>';
  function syncButton() { if (bar) bar.style.display = favs().length ? "" : "none"; }

  // the pages, once their map is ready. o: {kind: "2d" | "3d", host: where the list goes (the map's own element, so it
  // shows in full screen too), shield(el): keeps the map's gestures out of it, place(button) -> the bar it sits in
  // (under the map's buttons), show(site): goes to a gauge of this map and opens its popup, recolor(site, colour)}
  function mount(o) {
    opts = o || {};
    style();
    if (opts.place) {
      const b = document.createElement(opts.kind === "3d" ? "button" : "a");
      b.className = "mwbtn";
      b.title = "My Waters: the gauges you follow";
      b.setAttribute("aria-label", "My Waters");
      if (b.tagName === "A") { b.href = "#"; b.setAttribute("role", "button"); } else b.type = "button";
      b.innerHTML = STAR;
      b.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); if (list && !list.hidden) close(); else open(); });
      bar = opts.place(b);
      syncButton();
    }
    recolor([...mapGauges().keys()]);
    fromHash();
    addEventListener("hashchange", fromHash);
    // an area saved for offline use keeps its gauges' last readings: fetched as it is saved, and when it is opened with
    // a connection and they are older than AREA_OLD
    const area = LBLX().area, all = () => [...mapGauges().keys()];
    const areaRefresh = force => { const r = readings(), now = Date.now();
      const due = all().filter(s => force || !r[s] || !(now - (r[s].f || 0) <= AREA_OLD));
      if (due.length && online()) refresh(due, true); };
    if (area && window.StreamsOffline && StreamsOffline.saved)
      StreamsOffline.saved(area).then(y => { if (y) areaRefresh(false); }).catch(() => {});
    document.addEventListener("streams-saved", e => { if (e.detail && e.detail.area === area) areaRefresh(true); });
    // the connection back: what is on the screen is fetched again
    if (window.StreamsOffline && StreamsOffline.onNet) StreamsOffline.onNet(on => {
      const shown = [...document.querySelectorAll("[data-gauge], [data-gauge-now]")].map(siteOf)
        .concat(list && !list.hidden ? favs().map(f => f.s) : []);
      if (on && shown.length) refresh(shown, true); else repaint(shown);
    });
    // the list changed in another tab
    addEventListener("storage", e => {
      if (e.key === KEY_R) R = null;
      if (e.key === KEY_W || e.key === KEY_R) { syncButton(); if (list && !list.hidden) { draw(); items(); } }
    });
  }
  // the buttons in the gauge popups (taps anywhere on the page, before a map stops them)
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest(".gfav");
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    const s = b.dataset.fav;
    if (!s) return;
    if (isFav(s)) open(null, s);
    else { add(s); open(s); }
  }, true);

  let styled = false;
  function style() {
    if (styled || document.getElementById("gl-style")) return;
    styled = true;
    const st = document.createElement("style");
    st.id = "gl-style";
    st.textContent =
      // the gauge popups and the calendar's line
      ".gpop .gt{border-collapse:collapse;margin:4px 0 2px}.gpop .gt td{padding:1px 8px 1px 0;vertical-align:top}" +
      ".gpop .gt td:first-child{color:#6b7280;white-space:nowrap}.gsub,.gwhen,.gdm{color:#6b7280}.gsub,.gwhen{font-size:11px}" +
      ".gwhen{margin-top:2px;line-height:1.35}.gwarn{color:#a61e4d}.gst{font-weight:600}" +
      ".gact{display:flex;align-items:center;flex-wrap:wrap;gap:6px 12px;margin-top:6px}" +
      ".gfav{font:inherit;font-size:12px;line-height:1.2;border:1px solid #c9ced6;border-radius:15px;background:#fff;" +
      "color:#1d1d1f;padding:5px 11px;cursor:pointer;-webkit-tap-highlight-color:transparent}" +
      ".gfav.on{border-color:#e0a800;background:#fff9db}.glc{margin-top:3px;line-height:1.35}" +
      // the ★ button under the map's buttons
      ".leaflet-bar a.mwbtn,.maplibregl-ctrl-group button.mwbtn{display:flex;align-items:center;justify-content:center;color:#f0b400}" +
      // the list
      ".mw{position:absolute;z-index:1100;top:10px;right:10px;width:310px;max-width:calc(100% - 20px);max-height:calc(100% - 20px);" +
      "display:flex;flex-direction:column;box-sizing:border-box;background:rgba(255,255,255,.97);border-radius:10px;" +
      "box-shadow:0 2px 12px rgba(0,0,0,.28);font:13px/1.4 system-ui,-apple-system,sans-serif;color:#1d1d1f;cursor:auto}" +
      ".mw[hidden]{display:none}.mwh{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px 6px;" +
      "border-bottom:1px solid #e9ecef}.mwh b{font-size:14px}.mwn{color:#6b7280;font-weight:400}" +
      ".mwh button{border:0;background:#f1f3f5;border-radius:6px;min-width:32px;height:30px;margin-left:6px;font-size:17px;" +
      "line-height:1;cursor:pointer;color:#1d1d1f}.mws{padding:3px 10px 0;color:#6b7280;font-size:11px}.mws:empty{display:none}" +
      ".mwl{overflow-y:auto;min-height:0;padding:0 10px;touch-action:pan-y;-webkit-overflow-scrolling:touch}" +
      ".mwi{border-bottom:1px solid #eef0f2;padding:8px 0;transition:background .4s}.mwi.hl{background:#fff9db}.mwt{display:flex;align-items:center;gap:7px}" +
      ".mwt b{flex:1;min-width:0;overflow-wrap:anywhere}.mwd{flex:none;width:12px;height:12px;border-radius:50%;" +
      "box-shadow:0 0 0 1px rgba(0,0,0,.25) inset}.mwb{flex:none;font:inherit;font-size:12px;border:1px solid #c9ced6;" +
      "border-radius:6px;background:#fff;padding:4px 9px;cursor:pointer;color:#1d1d1f}" +
      ".mwv,.mwj,.mwa{margin-left:19px}.mwv .gdm{font-size:11px}.mwj{font-size:12px}.mwa{margin-top:3px;font-size:12px}" +
      ".mwa a{color:#1864ab;font-weight:600;text-decoration:none}.mwempty{padding:12px 0;color:#495057}" +
      ".mwed{margin:6px 0 2px 19px;padding:8px;background:#f4f6f8;border-radius:8px}" +
      ".mwrow{display:flex;align-items:center;flex-wrap:wrap;gap:4px 6px;margin-bottom:6px}" +
      // (a field under 16 px makes iPhone Safari zoom in on it)
      ".mwed input{font:16px system-ui,-apple-system,sans-serif;box-sizing:border-box;border:1px solid #c9ced6;" +
      "border-radius:6px;padding:4px 6px;background:#fff;color:#1d1d1f}.mwed input[name=n]{flex:1;min-width:150px}" +
      ".mwed input[inputmode]{width:76px}.mwmsg{color:#c92a2a;font-size:12px;min-height:0}" +
      ".mwbtns{display:flex;gap:6px;margin-top:6px}.mwbtns button{font:inherit;flex:1;border:1px solid #c9ced6;" +
      "border-radius:6px;background:#fff;padding:6px 4px;cursor:pointer;color:#1d1d1f}" +
      ".mwbtns .mwsave{background:#1864ab;border-color:#1864ab;color:#fff;font-weight:600}.mwbtns .mwdel{color:#c92a2a}" +
      ".mwf{padding:6px 10px 8px;color:#6b7280;font-size:11px;border-top:1px solid #e9ecef}" +
      "@media (max-width:640px){.mw{left:10px;right:10px;width:auto;max-width:none}}";
    document.head.appendChild(st);
  }

  window.gaugeLive = {fill, mount, open, refresh, cur, readings, favs, _rel: rel};
})();
