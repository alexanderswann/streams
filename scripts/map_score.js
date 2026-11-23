// The fish score's breakdown in the stream popups: it opens under the score while the pointer is on that line on a
// computer, and on a tap on a phone (another tap folds it; a click pins it on a computer). Shared by the area maps
// (map_drainages.js and map3d.html, inlined by 06_map.py) and the one-file phone map (14_portable.py); it adds its
// own styles. Each reach carries fx (06_map.py fs_parts): the terms scoring.score() combines, which fsParts multiplies
// out as score() does, operation by operation, so the breakdown comes to the score shown:
//   100 × water × (0.30 size + 0.30 thermal + 0.15 gradient + 0.25 remoteness) × burn × trout × heat × channel,
//   capped at 100 and rounded (a half to the even number, as numpy does); thermal = 0.5 water temperature + 0.35 shade
//   + 0.15 north-facing slope
// Each line gives what the reach reads, in the popup's own words and imperial units (units.py), and what it adds or
// multiplies. 06_map.py checks that every drawn reach's fx comes to its score, and audit/scripts/fish_breakdown_check.js
// runs this file on every reach of every map.
(function () {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const clip = v => Math.min(Math.max(v, 0), 1);
  const num = v => v === undefined || v === "-" ? null : Number(v);
  // units.py's degf and sqmi; a number keeps its unit on its line (\u00a0, a space no line breaks at)
  const degf = c => Math.round(c * 9 / 5 + 32) + "\u00a0°F";
  const sqmi = km2 => { const v = km2 * 0.386102;
    return (v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 1 ? v.toFixed(1) : v.toFixed(2)) + "\u00a0sq\u00a0mi"; };
  // numpy's round: a half goes to the even number (the score lies between 0 and 100)
  const rint = x => { const f = Math.floor(x), d = x - f; return d > 0.5 ? f + 1 : d < 0.5 ? f : f % 2 ? f + 1 : f; };
  const BROOK = 6;             // scoring.BROOK_SCALE: wild brook trout water's drainage counts six times over

  // fx -> the reach's terms and its score before and after rounding; null for a reach without fx
  function fsParts(p) {
    if (!p || typeof p.fx !== "string" || p.gr == null) return null;
    const t = p.fx.split(" ");
    const r = {W: num(t[0]), S: num(t[1]), wt: num(t[2]), cp: num(t[3]), sp: num(t[4]),
               nn: t[5] === "-" ? null : Number(t[5]) / 100, am: num(t[6]), bm: num(t[7]), gr: p.gr,
               B: 1, H: 1, T: 1, Ch: 1, C: null, A: null, brook: false, tw: false};
    t.slice(8).forEach(k => {
      const v = Number(k.slice(1));
      if (k === "t") r.T = 1.2; else if (k === "c") r.Ch = 0.2; else if (k === "b") r.brook = true;
      else if (k === "w") r.tw = true; else if (k[0] === "B") r.B = v; else if (k[0] === "H") r.H = v;
      else if (k[0] === "C") r.C = v; else if (k[0] === "A") r.A = v; else if (k[0] === "G") r.gr = v;
      else if (k[0] === "N") r.nn = v;
    });
    // as in scoring.score(), with its fills for an input that is missing: canopy 0, terrain 20, northness 0, approach 0
    const terrain = (r.sp == null ? 20 : r.sp) / 100, canopy = clip((r.cp == null ? 0 : r.cp) / 100);
    r.shadeAll = 1 - (1 - terrain) * (1 - 0.8 * canopy);
    r.shade = clip(r.shadeAll / 0.45);
    r.north = clip(((r.nn == null ? 0 : r.nn) + 0.15) / 0.30);
    r.c1 = r.C != null ? r.C : r.tw ? 1 : clip((25 - r.wt) / 5);
    r.thermal = 0.5 * r.c1 + 0.35 * r.shade + 0.15 * r.north;
    r.G = clip(1 - Math.max(Math.max(1 - r.gr, r.gr - 8), 0) / 10);
    r.R = clip(((r.am == null ? 0 : r.am) + (r.bm == null ? 0 : r.bm)) / 120);
    r.habitat = 0.30 * r.S + 0.30 * r.thermal + 0.15 * r.G + 0.25 * r.R;
    r.raw = 100 * r.W * r.habitat * r.B * r.T * r.H * r.Ch;
    r.x = Math.min(Math.max(r.raw, 0), 100);
    r.score = rint(r.x);
    return r;
  }

  // points to one decimal that add up to their total to one decimal (the largest remainders take the spare tenths)
  function tenths(vals, total) {
    const fl = vals.map(v => Math.floor(v * 10 + 1e-9));
    let left = Math.round(total * 10) - fl.reduce((a, b) => a + b, 0);
    vals.map((v, i) => [v * 10 - fl[i], i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (left > 0) { fl[i]++; left--; } });
    return fl.map(v => (v / 10).toFixed(1));
  }
  const times = v => "× " + String(+v.toFixed(3));
  const face = nn => nn == null ? "aspect unknown" : `faces ${nn > 0.04 ? "north" : nn < -0.04 ? "south" : "east/west or mixed"}`;

  function table(p, r) {
    const hab = 100 * r.habitat;
    const pts = tenths([30 * r.S, 15 * r.c1, 10.5 * r.shade, 4.5 * r.north, 15 * r.G, 25 * r.R], hab);
    const full = [30, 15, 10.5, 4.5, 15, 25];
    // each line: what the reach reads, and a hint where the term falls short of full (left out on the narrowest
    // phones, 360 px and under, with the heading: the breakdown must fit whole between the map's controls there)
    const mins = (r.am == null ? 0 : r.am), ride = (r.bm == null ? 0 : r.bm), sc = r.brook ? BROOK : 1;
    const rows = [
      ["Size", (r.A != null ? `scored on ${sqmi(r.A)}` : sqmi(p.a)) + (r.brook ? ", ×6 as brook trout water" : ""),
       r.S <= 0 ? `none under ${sqmi(1 / sc)}` : r.S < 1 ? `full from ${sqmi(50 / sc)}` : ""],
      ["Water temp", r.tw ? "tailwater: the dam releases cold water" : r.wt == null ? "no estimate" : `about ${degf(r.wt)}`,
       r.c1 >= 1 ? "" : r.c1 <= 0 ? "none from 77\u00a0°F" : "full to 68\u00a0°F, none from 77\u00a0°F"],
      ["Shade", `${Math.round(100 * r.shadeAll)}%: tree canopy\u00a0${r.cp == null ? "?" : r.cp + "%"}, terrain\u00a0` +
       `${r.sp == null ? "?" : r.sp + "%"}`, r.shade < 1 ? "full from 45%" : ""],
      ["Slope", face(r.nn), r.north < 1 ? "full facing north" : ""],
      ["Gradient", `${(+r.gr).toFixed(1)}%`, r.G < 1 ? "best 1–8%" : ""],
      ["Remoteness", `typical approach ${mins}\u00a0min` + (ride > 0 ? `, ${ride} of them ridden, counted twice` : ""),
       r.R < 1 ? "full from 2\u00a0h" : ""]];
    const row = (a, b, c, cls) => `<tr${cls ? ` class="${cls}"` : ""}><td>${a}</td><td>${b}</td><td>${c}</td></tr>`;
    let h = rows.map(([a, b, x], i) => row(a, esc(b) + (x ? `<span class="fsx"> (${esc(x)})</span>` : ""),
                                           `${pts[i]}<span class="fsm"> of ${full[i]}</span>`)).join("") +
      row("Habitat", "", `${hab.toFixed(1)}<span class="fsm"> of 100</span>`, "fss");
    const fl = String(p.fl || "").replace(/^summer: /, "");
    const mult = [["Summer flow", fl, r.W]];
    if (r.T !== 1) mult.push(["Trout", "trout found or trout water", r.T]);
    if (r.B !== 1) mult.push(["Fire", "a fire since 2016 (see Fire)", r.B]);
    if (r.H !== 1) mult.push(["Heat", "desert heat gate (see Heat)", r.H]);
    if (r.Ch !== 1) mult.push(["Channel", "a built channel, by its name", r.Ch]);
    h += mult.map(([a, b, v]) => row(a, esc(b), times(v))).join("");
    const half = r.x * 2 === Math.round(r.x * 2) && r.x % 1 !== 0;
    h += row("Score", `${hab.toFixed(1)} ${mult.map(m => times(m[2])).join(" ")} = ${r.raw.toFixed(1)}` +
             (r.raw > 100 ? ", capped at 100" : "") + (half ? ", a half rounding to even" : ""), `<b>${p.fs}</b>`, "fsf");
    return `<div class="fsh">How the ${esc(p.fs)} is made</div><table>${h}</table>`;
  }

  // the popup's "Fish score" line, with the breakdown under it where the reach has its terms
  window.fsRow = function (p) {
    const head = `<b class="fsn">${esc(p.fs)}</b>${p.rk != null ? ` · ahead of ${esc(p.rk)}% of reaches here` : ""}`;
    const r = fsParts(p);
    if (!r) return `<tr><td>Fish score</td><td>${head}</td></tr>`;
    return `<tr class="fsr" onclick="fsTap(this)" onmouseenter="fsFit(this)"><td>Fish score</td><td>${head}` +
      `<span class="fsi" title="How the score is made">ⓘ</span><div class="fsb">${table(p, r)}</div></td></tr>`;
  };
  // a tap or click: open or fold, place it, and tell the page (map_phone.js pans a Leaflet popup clear of the controls)
  window.fsTap = tr => {
    tr.classList.toggle("open");
    fsFit(tr);
    document.dispatchEvent(new CustomEvent("fs-toggle", {detail: tr}));
  };
  // under the line; above it where its foot would be off the screen or under a control or panel and its head is seen
  // above (the 3D map's popups don't pan into view: on a phone one opened low on the screen hid the breakdown)
  window.fsFit = tr => {
    const b = tr.querySelector(".fsb"), pp = tr.closest(".pp");
    if (!b || !pp) return;
    b.style.top = "";
    const hidden = getComputedStyle(b).display === "none";
    if (hidden) b.style.display = "block";
    const seen = (x, y) => { const e = document.elementFromPoint(x, y); return !!e && b.contains(e); };
    let box = b.getBoundingClientRect();
    if (!(seen(box.left + 6, box.bottom - 3) && seen(box.right - 6, box.bottom - 3))) {
      b.style.top = (tr.getBoundingClientRect().top - pp.getBoundingClientRect().top - box.height - 6) + "px";
      box = b.getBoundingClientRect();
      if (!(seen(box.left + 6, box.top + 3) && seen(box.right - 6, box.top + 3))) b.style.top = "";
    }
    if (hidden) b.style.display = "";
  };
  window.fsParts = fsParts;

  if (typeof document !== "undefined" && !document.getElementById("fs-style")) {
    const st = document.createElement("style");
    st.id = "fs-style";
    st.textContent = ".pp{position:relative}.fsr{cursor:pointer}.fsr .fsn{text-decoration:underline dotted #8a929c;" +
      "text-underline-offset:2px}.fsi{color:#1864ab;margin-left:5px}" +
      ".fsb{display:none;position:absolute;left:-2px;right:-2px;z-index:20;margin-top:3px;background:#fff;" +
      "border:1px solid #cfd6de;border-radius:7px;box-shadow:0 4px 14px rgba(0,0,0,.22);padding:6px 8px 5px;" +
      "color:#1d1d1f;font-size:12px;line-height:1.35;cursor:pointer;text-align:left}" +
      "@media (hover:hover){.fsr:hover .fsb{display:block}}.fsr.open .fsb{display:block}" +
      ".fsb .fsh{font-weight:600;margin-bottom:2px}.pp .fsb table{width:100%;border-collapse:collapse;margin:0}" +
      ".pp .fsb td{padding:1px 6px 1px 0;vertical-align:top;color:#1d1d1f;white-space:normal}" +
      ".pp .fsb td:first-child{color:#6b7280;white-space:nowrap}" +
      ".pp .fsb td:last-child{text-align:right;white-space:nowrap;padding-right:0;font-variant-numeric:tabular-nums}" +
      ".fsb .fsm{color:#8a929c;font-size:11px}.fsb tr.fss td,.fsb tr.fsf td{border-top:1px solid #e3e7ec;padding-top:2px}" +
      ".fsb tr.fsf td{padding-bottom:0}" +
      // the narrowest phones (320 px): no hints or heading, a smaller face, so the whole breakdown fits on the screen
      "@media (max-width:360px){.fsb .fsx,.fsb .fsh{display:none}.fsb{font-size:11px;padding:5px 6px 4px}" +
      ".fsb .fsm{font-size:10px}.pp .fsb td{padding-right:4px}}";
    document.head.appendChild(st);
  }
})();
