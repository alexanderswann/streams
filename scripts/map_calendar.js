// The trout calendar in the stream popups: when in the year a reach fishes best, by half-month, under the fish score
// (which stays as it is: the score says where, the calendar when). Fishing conditions only, no legal seasons. 06_map.py
// puts this file at the end of both area maps (stream_map.html, stream_map_3d.html), after map_score.js: it adds its
// line to the fish score's (fsRow), so the popups themselves are unchanged. troutcal.py says what the calendar is and
// does the same sum in Python (calendar()): water temperature x flow x light x ice x clarity x oxygen x hatches. This
// file works it out from the reach's fx (its summer water temperature, tree canopy, water term and flags, as
// map_score.js reads them), a (drainage, km2), el (m), x/y and cz (its horizon at the area's bearings, then its time
// zone where it isn't the map's), with the area's tables in LBL.cal (11b_calendar.py's calendar.json).
// A row of 24 half-months, darker = better; a tap on one gives its reasons. window.troutCal serves the maps' "When"
// choice in the fish score colours: the fish score scaled by how a half-month rates on each creek.
(function () {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_";
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const LAST = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const rad = d => d * Math.PI / 180, deg = r => r * 180 / Math.PI;
  const degf = c => Math.round(c * 9 / 5 + 32) + " °F";        // units.py's degf
  const tab = () => { const L = window.LBL || (window.MAP3D || {}).lbl || {}; return L.cal || null; };
  const lin = (pts, x) => {
    if (x <= pts[0][0]) return pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      if (x <= x1) return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
    }
    return pts[pts.length - 1][1];
  };
  const midDate = (h, y) => [y, Math.floor(h / 2), h % 2 ? 23 : 8];            // year, month (0-11), day
  const dst = (y, m, d) => {     // US daylight saving time: 2nd Sunday in March to 1st Sunday in November
    const t = Date.UTC(y, m, d), a = new Date(Date.UTC(y, 2, 1)), b = new Date(Date.UTC(y, 10, 1));
    const a2 = Date.UTC(y, 2, 1 + (7 - a.getUTCDay()) % 7 + 7), b1 = Date.UTC(y, 10, 1 + (7 - b.getUTCDay()) % 7);
    return a2 <= t && t < b1;
  };
  // dissolved oxygen at saturation (mg/L) at T C and el m: troutcal.do_sat()
  const doSat = (Tc, el) => { const K = Tc + 273.15;
    const ln = -139.34411 + 1.575701e5 / K - 6.642308e7 / K ** 2 + 1.2438e10 / K ** 3 - 8.621949e11 / K ** 4;
    return Math.exp(ln) * Math.exp(-Math.max(el, 0.0) / 8434.0); };

  // the sun on half-month h's middle day at a latitude rounded to 0.1 deg: troutcal.sun_path()
  const paths = {};
  function sunPath(T, h, lat) {
    const la = Math.floor(lat * 10 + 0.5) / 10, key = h + "|" + la;
    if (paths[key]) return paths[key];
    const [y, m, d] = midDate(h, T.year);
    const n = (Date.UTC(y, m, d) - Date.UTC(y, 0, 1)) / 864e5 + 1;
    const g = 2 * Math.PI / 365 * (n - 1);
    const eot = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g)
                          - 0.040849 * Math.sin(2 * g));
    const dec = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g)
                + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    const phi = rad(la), st = T.step, steps = [];
    for (let i = 0; i < 24 * 60; i += st) {
      const t = i / 60 + st / 120, ha = rad((t - 12) * 15);
      const alt = deg(Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(ha)));
      if (alt <= 0) continue;
      const az = ((deg(Math.atan2(Math.sin(ha), Math.cos(ha) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi))) + 180) % 360 + 360) % 360;
      steps.push([i + st / 2, alt, az]);
    }
    return paths[key] = {steps, up: steps.length, eot, dst: dst(y, m, d)};
  }
  // hours of direct sun on the water, its first and last minute (local clock), the day's length: troutcal.sun_day()
  function sunDay(T, h, lat, lon, hz, tz, useDst) {
    const P = sunPath(T, h, lat), AZ = T.az, pts = AZ.map((a, i) => [a, hz[i]]);
    let lit = 0, first = null, last = null;
    for (const [mm, alt, az] of P.steps) {
      const hv = az <= AZ[0] ? hz[0] : az >= AZ[AZ.length - 1] ? hz[hz.length - 1] : lin(pts, az);
      if (alt > hv) { lit++; if (first === null) first = mm; last = mm; }
    }
    const clock = m2 => m2 === null ? null : m2 - P.eot - 4 * (lon - 15 * tz) + (useDst && P.dst ? 60 : 0);
    return [lit * T.step / 60, clock(first), clock(last), P.up * T.step / 60];
  }

  // what the sum reads off a reach (troutcal.prep()), or null; kept per reach
  const preps = new WeakMap();
  function prep(T, p) {
    if (preps.has(p)) return preps.get(p);
    let r = null;
    const n = T.az.length, t = String(p.fx || "").split(" ");
    const num = v => v === undefined || v === "" || v === "-" ? null : Number(v);
    if (typeof p.cz === "string" && p.cz.length >= n && t.length >= 8) {
      const flags = t.slice(8), tw = flags.includes("w"), wt = num(t[2]), cp = num(t[3]);
      if (wt !== null || tw) {
        const la = Math.log10(Math.max(p.a, 0.01));
        let wsum = 0, isum = 0;
        const acc = new Array(24).fill(0), iacc = new Array(24).fill(0);
        T.gauges.forEach(g => {
          const dkm = 111.2 * Math.hypot(p.y - g[1], (p.x - g[2]) * Math.cos(rad(p.y)));
          const w = Math.exp(-0.5 * ((la - g[0]) / T.sig[0]) ** 2 - 0.5 * (dkm / T.sig[1]) ** 2);
          wsum += w;
          for (let h = 0; h < 24; h++) acc[h] += w * Math.log10(g[3][h]);
          if (g[5] != null) { isum += w; for (let h = 0; h < 24; h++) iacc[h] += w * g[5][h]; }
        });
        r = {W: num(t[0]), wt, cp, tw, brook: flags.includes("b"), canopy: Math.min(Math.max((cp || 0) / 100, 0), 1),
             hz: [...p.cz.slice(0, n)].map(ch => CH.indexOf(ch)), tz: p.cz.length > n ? CH.indexOf(p.cz[n]) - 12 : T.tz,
             el: p.el || 0.0, lr: acc.map(a => wsum > 0 ? a / wsum : 0), ice: iacc.map(a => isum > 0 ? a / isum : 0)};
      }
    }
    preps.set(p, r);
    return r;
  }
  // one half-month (troutcal.half())
  function half(T, P, p, h) {
    const ws = T.water, base = P.wt === null ? ws.S : P.wt;
    let Tw = Math.max(0.5, ws.S + ws.d[h] + ws.k[h] * (base - ws.S));
    if (P.tw) Tw = Math.min(Math.max(Tw, T.tail[0]), T.tail[1]);
    const sT = lin(T.thermal[P.brook ? "brook" : "trout"], Tw);
    // a tailwater's flow is the dam's; a creek year-round by its own evidence takes no low-water mark (troutcal.half())
    const lr = P.lr[h], yr = P.W !== null && P.W >= T.year_round, sQ = P.tw || (lr < 0 && yr) ? 1.0 : lin(T.flow, lr);
    const dry = P.W !== null && h >= T.dry[0] && h < T.dry[1] ? Math.min(1.0, P.W / T.year_round) : 1.0;
    const [sun, first, last, day] = sunDay(T, h, p.y, p.x, P.hz, P.tz, T.dst);
    const e = (day > 0 ? sun / day : 0.0) * (1 - 0.8 * P.canopy);
    const warm = 1 - 0.30 * e, cold = 0.85 + 0.15 * e;
    const f = Math.min(Math.max((Tw - T.light[1]) / (T.light[0] - T.light[1]), 0), 1);
    const sL = cold + (warm - cold) * f;
    const ice = P.ice[h], sI = 1 - T.ice_k * ice;
    const ntu = T.clarity.ntu[h], sC = ntu === null ? 1.0 : lin(T.clar, ntu);
    const sat = T.oxygen.sat[h], dox = sat === null ? null : doSat(Tw, P.el) * sat, sO = dox === null ? 1.0 : lin(T.oxy, dox);
    const rel = T.hatch.rel[h], sB = rel === null ? 1.0 : T.hatch_lo + (1 - T.hatch_lo) * Math.min(Math.max(rel, 0.0), 1.0);
    const x = 100 * sT * sQ * dry * sL * sI * sC * sO * sB;
    return {h, T: Tw, sT, ratio: 10 ** lr, sQ, dry, yr, sun, first, last, day, e, sL, ice, sI, ntu, sC, dox, sO, rel, sB,
            score: Math.floor(x + 0.5), brook: P.brook, tw: P.tw, cp: P.cp};
  }
  // the 24 half-months of a reach (troutcal.calendar()), or null
  function calendar(p) {
    const T = tab(), P = T && p ? prep(T, p) : null;
    if (!P) return null;
    const out = [];
    for (let h = 0; h < 24; h++) out.push(half(T, P, p, h));
    return out;
  }
  // one half-month's score, for the map's colours (kept per reach); null where the reach has no calendar
  function score(p, h) {
    const T = tab(), P = T && p ? prep(T, p) : null;
    if (!P) return null;
    P.sc = P.sc || {};
    return h in P.sc ? P.sc[h] : P.sc[h] = half(T, P, p, h).score;
  }

  // ---- words ----
  const CLS = [[75, "best", "q4"], [55, "good", "q3"], [35, "fair", "q2"], [15, "poor", "q1"], [-1, "bad", "q0"]];
  const cls = c => CLS.find(k => c.score >= k[0]).slice(1);
  const hStart = h => `${MON[h >> 1]} ${h % 2 ? 16 : 1}`, hEnd = h => `${MON[h >> 1]} ${h % 2 ? LAST[h >> 1] : 15}`;
  const hName = h => `${hStart(h)}–${h % 2 ? LAST[h >> 1] : 15}`;
  // a run of half-months in words: whole months by name ("May", "Sep – Oct"), else its dates
  const span = (a, b) => a === b ? hName(a) : a % 2 === 0 && b % 2 === 1
    ? (a >> 1 === b >> 1 ? MON[a >> 1] : `${MON[a >> 1]} – ${MON[b >> 1]}`) : `${hStart(a)} – ${hEnd(b)}`;
  const clock = m => { if (m === null) return "";
    m = ((Math.round(m / 10) * 10) % 1440 + 1440) % 1440; const H = Math.floor(m / 60), M = m % 60;
    return `${(H + 11) % 12 + 1}:${String(M).padStart(2, "0")} ${H < 12 ? "am" : "pm"}`; };
  const now = () => { const d = new Date(); return d.getMonth() * 2 + (d.getDate() > 15 ? 1 : 0); };

  // what holds a half-month down: [key, words], the lowest part (none where every part is 0.97 or more)
  function why(c) {
    const q = c.sQ * c.dry, parts = [["water", c.sT], ["flow", q], ["light", c.sL], ["ice", c.sI], ["clarity", c.sC],
                                     ["oxygen", c.sO], ["hatch", c.sB]];
    const [k, m] = parts.reduce((a, b) => b[1] < a[1] ? b : a);
    if (m >= 0.97) return ["", ""];
    if (k === "water") return c.T < 10 ? (c.T <= 1.5 ? ["icecold", "near-freezing water"] : ["cold", "cold water"]) : ["warm", "warm water"];
    if (k === "flow") return c.dry < c.sQ ? ["dry", "may run dry"] : c.ratio > 1 ? ["runoff", "runoff"] : ["low", "very low water"];
    if (k === "light") return c.T >= 12 ? ["sun", "bright sun on open water"] : ["shade", "no sun on the water"];
    return {ice: ["ice", "ice"], clarity: ["murky", "murky water"], oxygen: ["oxygen", "low oxygen"], hatch: ["hatch", "few insects hatching"]}[k];
  }
  // runs of half-months (round the year) where test holds: [[first, last], ...] in calendar order
  function runs(cal, test) {
    const on = cal.map(test);
    if (on.every(Boolean)) return [[0, 23]];
    if (!on.some(Boolean)) return [];
    const out = [], s = on.findIndex(v => !v);
    for (let i = 1; i <= 24; i++) {
      const h = (s + i) % 24;
      if (on[h] && !on[(h + 23) % 24]) out.push([h, h]);
      if (on[h]) out[out.length - 1][1] = h;
    }
    return out.sort((a, b) => a[0] - b[0]);
  }
  const hsOf = ([a, b]) => { const hs = []; for (let h = a; ; h = (h + 1) % 24) { hs.push(h); if (h === b) break; } return hs; };
  const water = c => {
    const t = c.T, sp = c.brook ? "brook trout" : "trout", best = c.brook ? "50–61" : "50–64";
    const w = c.tw ? "a tailwater, held cool by the dam" : t <= 1.5 ? "near freezing: trout barely feed"
      : t < 7 ? "cold: trout sluggish" : t < 10 ? "cool, warming fish up" : c.sT >= 0.999 ? `ideal for ${sp}`
      : t > (c.brook ? 18 : 20) ? `too warm for ${sp} (best ${best} °F)` : `warm for ${sp} (best ${best} °F)`;
    return `Water about ${degf(t)}, ${w}` + (c.ice >= 0.05 ? `; ice on about ${Math.round(c.ice * 100)}% of days` : "");
  };
  const flowWords = c => {
    if (c.dry < 1) return "may run dry: it flows only in some summers";
    if (c.tw) return "flow set by the dam's releases";
    const r = c.ratio, x = r >= 2 ? `${r >= 10 ? Math.round(r) : r.toFixed(1)}×` : r <= 0.25 ? `${r.toFixed(r < 0.1 ? 2 : 1)}×` : "";
    return (r >= 3.5 ? "runoff, high water" : r >= 2 ? "high water" : r <= 0.25 && c.yr ? "summer low flow"
      : r <= 0.05 ? "very low water" : r <= 0.25 ? "low water" : "normal flow") + (x ? ` (about ${x} its typical day)` : "");
  };
  const clarWords = c => c.ntu === null ? "" : (c.ntu < 5 ? "clear" : c.ntu < 10 ? "slightly stained" : c.ntu < 25 ? "stained"
    : c.ntu < 50 ? "murky" : "muddy") + ` (typical ${c.ntu < 10 ? c.ntu.toFixed(1) : Math.round(c.ntu)} NTU)`;
  const oxyWords = c => c.dox === null ? "" : `oxygen about ${Math.round(c.dox)} mg/L${c.dox < 6 ? ", low for trout" : ""}`;
  const hatchWords = c => c.rel === null ? "" : c.rel >= 1.2 ? "many insects hatching" : c.rel >= 0.8 ? "insects hatching"
    : c.rel >= 0.4 ? "some insects hatching" : "few insects hatching";
  const sunWords = c => (c.sun >= 0.5 ? `Sun on the water ${clock(c.first)}–${clock(c.last)}` : "No direct sun on the water (terrain)")
    + (c.cp >= 30 ? ` (${Math.round(c.cp)}% tree cover)` : "");
  const todWords = c => c.T >= 18 ? "fish early morning and evening, when it is coolest"
    : c.T <= 9 ? "fish late morning into the afternoon, when it is warmest"
    : c.e >= 0.45 ? "best in low light: early, late or on a cloudy day" : "good all day";

  function detail(cal, h, nowH) {
    const c = cal[h], [, w] = why(c), [lab] = cls(c);
    const line = xs => { const s = xs.filter(Boolean).map(esc).join(" · "); return s && s[0].toUpperCase() + s.slice(1); };
    return `<b>${h === nowH ? "Now, " : ""}${hName(h)}</b>: ${lab} (${c.score})` + (w ? ` · ${w}` : "") +
      `<div>${line([water(c), flowWords(c)])}</div><div>${line([clarWords(c), oxyWords(c), hatchWords(c)])}</div>` +
      `<div>${esc(sunWords(c))} · <i>${esc(todWords(c))}</i></div>` +
      `<div class="cdm calk">Darker = better · tap a half-month · conditions only, not legal seasons</div>`;
  }

  // the "Best" line and the worst stretches, with their reason
  function summary(cal) {
    const top = Math.max(...cal.map(c => c.score)), cut = Math.max(top - 10, 15);
    const best = runs(cal, c => c.score >= cut).map(([a, b]) => span(a, b)).join(", ");
    const at = top >= 55 ? "" : top >= 35 ? " (fair at best)" : " (poor all year)";
    const word = {icecold: "near-freezing water", cold: "cold water", warm: "warm water", runoff: "runoff", low: "very low water",
                  dry: "may run dry", sun: "bright open water", shade: "no sun on the water", ice: "ice", murky: "murky water",
                  oxygen: "low oxygen", hatch: "few insects hatching", "": "several reasons"};
    const say = r => {
      const hs = hsOf(r), n = {};
      hs.forEach(h => { const k = why(cal[h])[0]; n[k] = (n[k] || 0) + 1; });
      const key = Object.keys(n).sort((x, y) => n[y] - n[x])[0], ts = hs.map(h => cal[h].T), ice = Math.max(...hs.map(h => cal[h].ice));
      const val = key === "warm" ? `, up to ${degf(Math.max(...ts))}` : key === "cold" || key === "icecold"
        ? `, ${degf(Math.min(...ts))}` + (ice >= 0.1 ? `, ice on up to ${Math.round(ice * 100)}% of days` : "")
        : key === "runoff" ? `, ${Math.round(Math.max(...hs.map(h => cal[h].ratio)) * 10) / 10}× its typical day`
        : key === "ice" ? `, ${Math.round(Math.max(...hs.map(h => cal[h].ice)) * 100)}% of days` : "";
      return [hs.length, `${span(...r)}: ${word[key]}${val}`];
    };
    // the stretches under 35 (two at most, the longest); with none, the lowest
    let worst = runs(cal, c => c.score < 35).map(say).sort((a, b) => b[0] - a[0]).slice(0, 2).map(x => x[1]);
    if (!worst.length) {
      const bot = Math.min(...cal.map(c => c.score));
      worst = runs(cal, c => c.score <= bot + 5).map(say).sort((a, b) => b[0] - a[0]).slice(0, 1).map(x => x[1]);
    }
    return [best + at, worst.join(" · ")];
  }

  let seq = 0;
  const kept = {};
  window.calRow = function (p) {
    const cal = calendar(p);
    if (!cal) return "";
    const key = ++seq, nowH = now();
    kept[key] = {cal, nowH};
    const cells = cal.map(c => { const [lab, q] = cls(c);
      return `<i class="${q}${c.h === nowH ? " now sel" : ""}" title="${hName(c.h)}: ${lab} ${c.score}"></i>`; }).join("");
    const [best, worst] = summary(cal);
    return `<tr class="calr"><td colspan="2" class="calc"><div class="calh"><span class="calt">Best time</span> ${best}</div>` +
      `<div class="cal" data-k="${key}" onclick="calTap(event,this)"><div class="cals">${cells}</div>` +
      `<div class="calm">${MON.map(m => `<span>${m[0]}</span>`).join("")}</div></div>` +
      (worst ? `<div class="calw"><span class="calt">Worst</span> ${worst}</div>` : "") +
      `<div class="cald">${detail(cal, nowH, nowH)}</div></td></tr>`;
  };
  // a tap on the row: the half-month under the finger, its reasons below; the pages re-place the popup ("fs-toggle")
  window.calTap = (ev, el) => {
    const k = kept[el.dataset.k], strip = el.querySelector(".cals");
    if (!k || !strip) return;
    const r = strip.getBoundingClientRect(), h = Math.min(23, Math.max(0, Math.floor((ev.clientX - r.left) / r.width * 24)));
    strip.querySelectorAll("i").forEach((c, i) => c.classList.toggle("sel", i === h));
    const box = el.parentNode.querySelector(".cald");
    if (box) box.innerHTML = detail(k.cal, h, k.nowH);
    ev.stopPropagation();
    document.dispatchEvent(new CustomEvent("fs-toggle", {detail: el}));
  };
  // the calendar's line follows the fish score's in every stream popup (map_score.js's fsRow), on any page that has
  // the area's tables
  if (typeof window.fsRow === "function" && !window.fsRow.cal) {
    const fs0 = window.fsRow;
    window.fsRow = p => fs0(p) + (tab() ? window.calRow(p) : "");
    window.fsRow.cal = true;
  }
  // the maps' "When" choice: the fish score scaled by how half-month h rates on the creek (null: no calendar here)
  window.troutCal = {calendar, score, name: hName, now,
                     fishIn: (p, h) => { const s = score(p, h); return s === null ? null : Math.round(p.fs * s / 100); },
                     ready: () => !!tab()};

  if (typeof document !== "undefined" && !document.getElementById("cal-style")) {
    const st = document.createElement("style");
    st.id = "cal-style";
    // 5 ordinal steps of one blue ramp (light = worse)
    st.textContent = ".pp td.calc.calc{white-space:normal;color:#1d1d1f;padding:5px 0 3px;border-top:1px solid #e3e7ec;" +
      "border-bottom:1px solid #e3e7ec}.calt{color:#6b7280;margin-right:3px}.calh,.calw{line-height:1.35}.calw{margin-top:2px}" +
      ".cal{margin:4px 0 1px;cursor:pointer;-webkit-tap-highlight-color:transparent}" +
      ".cals{display:grid;grid-template-columns:repeat(24,1fr);gap:1px}.cals i{height:16px;border-radius:2px;position:relative}" +
      ".cals i.sel{box-shadow:0 0 0 1.5px #fff,0 0 0 3px #1d1d1f;z-index:1}" +
      ".cals i.now::after{content:'';position:absolute;left:50%;bottom:2px;width:4px;height:4px;margin-left:-2px;border-radius:50%;background:#fff}" +
      ".calm{display:grid;grid-template-columns:repeat(12,1fr);font-size:10px;color:#6b7280;text-align:center;margin-top:1px}" +
      ".q4{background:#104281}.q3{background:#1c5cab}.q2{background:#2a78d6}.q1{background:#5598e7}.q0{background:#86b6ef}" +
      ".cald{margin-top:4px;padding:4px 6px;background:#f4f6f8;border-radius:6px;line-height:1.35}" +
      ".pp .cald b{font-size:12px}.cdm{color:#6b7280}.calk{font-size:10.5px;margin-top:1px}" +
      // the "When" choice under the fish score's colour key (map_drainages.js, map3d.html)
      ".calwhen{display:flex;align-items:center;gap:6px;margin:5px 0 3px;font-size:12px;color:#1d1d1f}" +
      ".calwhen select{font:inherit;font-size:12px;flex:1;min-width:0;border:1px solid #c9ced6;border-radius:5px;" +
      "background:#fff;color:#1d1d1f;padding:2px 3px}";
    document.head.appendChild(st);
  }
})();
