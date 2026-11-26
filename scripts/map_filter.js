// Stream filters at the top of the area maps' "View & layers" panels (the user, 2026-11-24: "add the ability to filter
// by stream order/size and fish score"; asked, they chose a minimum fish score, not a range, and the drainage area for
// the size, not the stream order). The fish score has a slider with one thumb, the least score shown. The drainage has
// one with two thumbs, the least and the most drainage shown (the user, 2026-11-25: "i want to be able to filter out
// big streams and small streams not just filter out the smaller ones"). The streams outside them, by the fish score and
// drainage their popups show, leave the map (their lines, casings and names; on the 2D map their part of the best-water
// highlight too); everything else, the popups of the streams still shown included, works as before. The maps open
// unfiltered. The filter goes along with the switch between the 2D and 3D maps in the link, after the layers
// (layer_order.js: layerLink), as "&fish=60&sqmi=5-25" ("&sqmi=5": 5 sq mi or more, "&sqmi=0-25": 25 or less), and is
// read when the page opens, as the layers are. While it is on, a note by the layer panel says so ("Streams filtered:
// fish score 60+, drainage 5–25 sq mi" and the miles still shown, with a × that shows them all again), so a filtered map
// isn't taken for a sparse one.
// The trout species (the user, 2026-11-25, after onWater's species layers): a choice of the species this map's data
// names (any, brook, brown, rainbow, cutthroat, lake trout: only those some stream here has), which keeps the streams
// with evidence of it: a trout record naming it (a survey, a stocking, an iNaturalist sighting) or a designated water
// naming it (a wild brook trout patch, a state's brook trout or cutthroat waters, a stream listed with it). "Recorded
// only" leaves out the streams only designated for it. Each reach carries its species as "sp" (06_map.py, from
// 11_context.py and troutspecies.py: B brook, N brown, R rainbow, C cutthroat, L lake trout; a capital where a record
// names it, with the latest year, "B2018", the small letter where a designation does); the popups' "Species" line
// says which, for each ("brook trout: recorded 2018, designated"). In the link: "&trout=brook", "&trout=brook-recorded".
// The mean annual flow (the user, 2026-11-25, after the r/bluelining thread whose anglers like 3-15 cfs blue lines): a
// second two-thumb slider like the drainage's, in cfs (any, 0.5, 1, 3, 5, 10, 15, 25, 50, 100, any), on the flow the
// popups' specs line shows ("q", map_specs.js / streamspecs.py). A stream with no flow estimate can't be placed, so it
// leaves the map while a flow limit is set, and the slider says so. In the link: "&cfs=3-15" ("&cfs=3", "&cfs=0-15").
// Shown only where the reaches carry q.
// Shared by map_drainages.js (2D) and map3d.html (3D), inlined by 06_map.py: each page says where the sliders and the
// note go and how it hides a stream (init below). Its styles are its own (the end of this file).
window.streamFilter = (function () {
  const FISH = [0, 100, 5];                              // the fish score slider: from, to, step (0: any)
  // the two-thumb sliders: the drainage (sq mi) and the mean annual flow (cfs). Each: its steps (0: any), the state's
  // keys for its least and most, its name, and its unit. Its last place, past the last step: no most
  const RANGES = {
    sqmi: {steps: [0, 0.5, 1, 2, 5, 10, 25, 50, 100], lo: "sqmi", hi: "sqmax", name: "Drainage", unit: "sq mi"},
    cfs: {steps: [0, 0.5, 1, 3, 5, 10, 15, 25, 50, 100], lo: "cfs", hi: "cfsmax", name: "Mean flow", unit: "cfs"}};
  const TOP = k => RANGES[k].steps.length;
  const KM2 = 2.589988;                                  // km² in a sq mi: the reaches carry km² (06_map.py "a")
  const THUMB = 26;                                      // the sliders' thumb, px (the tick labels sit under its centre)
  // the trout species, in the order shown (troutspecies.py): the reaches' code letter, the name, the button's word
  const SPECIES = [["brook", "B", "brook trout", "Brook"], ["brown", "N", "brown trout", "Brown"],
                   ["rainbow", "R", "rainbow trout", "Rainbow"], ["cutthroat", "C", "cutthroat trout", "Cutthroat"],
                   ["lake", "L", "lake trout", "Lake trout"]];
  const SPC = Object.fromEntries(SPECIES.map(([k, c]) => [k, c])), SPN = Object.fromEntries(SPECIES.map(([k, , n]) => [k, n]));
  const st = {fish: 0, sqmi: 0, sqmax: 0, cfs: 0, cfsmax: 0, sp: "", rec: false};   // 0 or "": no limit
  const NONE = {fish: 0, sqmi: 0, sqmax: 0, cfs: 0, cfsmax: 0, sp: "", rec: false};
  let o = null, el = null, note = null, miles = null, timer = 0, applied = "", have = [], hasFlow = false;

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const on = () => !!(st.fish || st.sqmi || st.sqmax || st.cfs || st.cfsmax || st.sp);
  // a reach has the chosen species: a record names it (the capital) or, unless "recorded only", a designation (small)
  const recorded = (p, k) => (p.sp || "").includes(SPC[k]);
  const hasSp = (p, k) => recorded(p, k) || (p.sp || "").includes(SPC[k].toLowerCase());
  // A reach passes "at least t sq mi" when its popup shows t or more, and "at most t sq mi" when it shows t or less: the
  // popups round to 0.01 sq mi under 1, to 0.1 from 1 and to 1 from 100 (map_drainages.js and map3d.html: SQMI), so the
  // least drainage kept is half a rounding step below t, and the most half a step above it
  const minKm2 = t => t ? (t - (t <= 1 ? 0.005 : 0.05)) * KM2 : 0;
  const maxKm2 = t => (t + (t < 1 ? 0.005 : t < 100 ? 0.05 : 0.5)) * KM2;
  // the flow: the popups show it as 06_map.py rounds it (whole cfs from 10, tenths from 1, hundredths under 1), so the
  // reach's q is compared as it is; one with no flow estimate passes no flow limit
  const hasQ = p => p.q !== undefined && p.q !== null;
  const pass = p => (!st.fish || p.fs >= st.fish) && (!st.sqmi || (p.a || 0) >= minKm2(st.sqmi)) &&
                    (!st.sqmax || (p.a || 0) < maxKm2(st.sqmax)) &&
                    (!st.cfs || (hasQ(p) && p.q >= st.cfs)) && (!st.cfsmax || (hasQ(p) && p.q <= st.cfsmax)) &&
                    (!st.sp || (st.rec ? recorded(p, st.sp) : hasSp(p, st.sp)));
  // (a number keeps its unit on its line: \u00a0, a space no line breaks at)
  const rangeWords = k => { const R = RANGES[k], a = st[R.lo], b = st[R.hi], u = "\u00a0" + R.unit.replace(" ", "\u00a0");
    return a && b ? `${a}–${b}${u}` : a ? `${a}+${u}` : b ? `up to ${b}${u}` : ""; };
  const sizeWords = () => rangeWords("sqmi");
  const spWords = () => st.sp ? SPN[st.sp] + (st.rec ? " (recorded)" : "") : "";
  const words = () => [st.fish ? `fish score ${st.fish}+` : "", sizeWords() && `drainage ${sizeWords()}`,
                        rangeWords("cfs") && `mean flow ${rangeWords("cfs")}`, spWords()]
    .filter(Boolean).join(", ");
  // a two-thumb slider's thumbs as places on its track: the least (0: none) and the most (its TOP: none)
  const places = k => { const R = RANGES[k];
    return [R.steps.indexOf(st[R.lo]), st[R.hi] ? R.steps.indexOf(st[R.hi]) : TOP(k)]; };
  const at = (i, max) => `calc(${THUMB / 2}px + (100% - ${THUMB}px) * ${i / max})`;      // a place on a slider's track

  // "#view&on=..&fish=60&sqmi=5-25&cfs=3-15&trout=brook-recorded" -> the filter. A value off the sliders' steps takes the step
  // that shows more: a least the step at or under it, a most the step at or over it (none past 100); a most not over the
  // least is left out; a species this map has no stream with is left out too (init)
  function parse(hash) {
    const r = Object.assign({}, NONE);
    String(hash || "").replace(/^#/, "").split("&").slice(1).forEach(p => {
      const i = p.indexOf("="), k = p.slice(0, i), v = p.slice(i + 1);
      if (k === "fish") {
        const f = parseFloat(v);
        if (f > 0) r.fish = Math.min(FISH[1], Math.floor(f / FISH[2]) * FISH[2]);
      } else if (RANGES[k]) {
        const R = RANGES[k], [lo, hi] = v.split("-").map(x => parseFloat(x));
        if (lo > 0) r[R.lo] = R.steps.filter(s => s <= lo).pop();
        if (hi > 0) r[R.hi] = R.steps.find(s => s >= hi) || 0;
      } else if (k === "trout") {
        let w = v;
        try { w = decodeURIComponent(v); } catch (_) {}      // a broken %-escape: the value as it is
        const [sp, how] = w.toLowerCase().split("-");
        if (SPC[sp]) { r.sp = sp; r.rec = how === "recorded"; }
      }
    });
    Object.values(RANGES).forEach(R => { if (r[R.hi] && r[R.hi] <= r[R.lo]) r[R.hi] = 0; });
    return r;
  }

  // the miles of the streams the filter keeps, of all of them, and of those kept a record names the chosen species on
  // (each reach's length worked out once, when first needed: a fresh, unfiltered open never does it)
  function count() {
    const F = o.features || [];
    if (!miles) miles = F.map(f => {
      const g = f.geometry || {}, parts = g.type === "MultiLineString" ? g.coordinates : g.type === "LineString" ? [g.coordinates] : [];
      let s = 0;
      parts.forEach(c => { for (let i = 1; i < c.length; i++) {
        const k = Math.cos((c[i - 1][1] + c[i][1]) * Math.PI / 360);
        s += Math.hypot((c[i][0] - c[i - 1][0]) * 69.172 * k, (c[i][1] - c[i - 1][1]) * 68.703);
      } });
      return s;
    });
    let all = 0, kept = 0, rec = 0;
    F.forEach((f, i) => {
      all += miles[i];
      if (pass(f.properties)) { kept += miles[i]; if (st.sp && recorded(f.properties, st.sp)) rec += miles[i]; }
    });
    return [kept, all, rec];
  }
  const mi = v => !v ? "0" : v >= 10 ? Math.round(v).toLocaleString("en-US") : v.toFixed(1);

  // the sliders, their values and ticks, the line under them, and the note by the panel
  function render() {
    if (!el) return;
    const fr = el.querySelector(".sfr[data-k=fish]"), fi = fr.querySelector("input"), fv = fr.querySelector(".sfv");
    if (+fi.value !== st.fish) fi.value = st.fish;
    fi.style.setProperty("--p", at(st.fish, FISH[1]));
    fv.textContent = st.fish ? `at least ${st.fish}` : "any";
    fv.classList.toggle("any", !st.fish);
    fi.setAttribute("aria-valuetext", fv.textContent);
    fr.querySelectorAll(".sft button").forEach(t => t.classList.toggle("on", +t.dataset.i === st.fish));
    // the drainage and the mean flow: each its two thumbs, the track blue between them
    Object.entries(RANGES).forEach(([k, R]) => {
      const dr = el.querySelector(`.sfr[data-k=${k}]`);
      if (!dr) return;
      const [a, b] = places(k), [lo, hi] = dr.querySelectorAll("input"), A = st[R.lo], B = st[R.hi], u = R.unit;
      if (+lo.value !== a) lo.value = a;
      if (+hi.value !== b) hi.value = b;
      const w = dr.querySelector(".sfw"), dv = dr.querySelector(".sfv");
      w.style.setProperty("--p1", at(a, TOP(k)));
      w.style.setProperty("--p2", at(b, TOP(k)));
      dv.textContent = A && B ? `${A} to ${B} ${u}` : A ? `at least ${A} ${u}` : B ? `at most ${B} ${u}` : "any";
      dv.classList.toggle("any", !A && !B);
      lo.setAttribute("aria-valuetext", A ? `at least ${A} ${u}` : "any");
      hi.setAttribute("aria-valuetext", B ? `at most ${B} ${u}` : "any");
      dr.querySelectorAll(".sft button").forEach(t => t.classList.toggle("on", +t.dataset.i === a || +t.dataset.i === b));
      const nq = dr.querySelector(".sfq");          // the flow: streams with no estimate are left out while it limits
      if (nq) nq.hidden = !(A || B);
    });
    // the species: its buttons, "recorded only" (while one is chosen) and what the two words mean
    const sr = el.querySelector(".sfr[data-k=sp]");
    if (sr) {
      sr.querySelectorAll(".sfc button").forEach(t => t.setAttribute("aria-pressed", String(t.dataset.s === st.sp)));
      const sv = sr.querySelector(".sfv");
      sv.textContent = st.sp ? SPN[st.sp] + (st.rec ? ", recorded" : "") : "any";
      sv.classList.toggle("any", !st.sp);
      sr.querySelector(".sfrec").hidden = !st.sp;
      sr.querySelector(".sfrec input").checked = st.rec;
    }
    el.querySelector(".sfclr").hidden = !on();
    const n = el.querySelector(".sfn");
    if (!on()) { n.textContent = "All streams shown"; note.hidden = true; return; }
    const [kept, all, rec] = count();
    n.innerHTML = `Showing <b>${mi(kept)}</b> of ${mi(all)} mi of streams` + (st.sp && !st.rec && kept ?
      `<br>${esc(SPN[st.sp])}: recorded on ${mi(rec)} mi, designated only on ${mi(Math.max(0, kept - rec))}` :
      st.sp && st.rec && !kept ? `<br>no trout record names ${esc(SPN[st.sp])} on these streams` : "");
    note.querySelector(".sfnt").innerHTML = `<b>Streams filtered:</b> ${esc(words())}<br><span>${mi(kept)} of ${mi(all)} mi shown</span>`;
    note.hidden = false;
  }
  // hide and show the streams (the page's own way), then tell the page (its links to the other map: "streamfilter")
  function apply() {
    clearTimeout(timer); timer = 0;
    const key = [st.fish, st.sqmi, st.sqmax, st.cfs, st.cfsmax, st.sp, st.rec].join("|");
    if (key !== applied) { applied = key; o.apply(on() ? pass : null); }
    render();
    document.dispatchEvent(new CustomEvent("streamfilter", {detail: Object.assign({}, st)}));
  }
  function set(change, now) {
    Object.assign(st, change);
    render();
    clearTimeout(timer);
    if (now) apply(); else timer = setTimeout(apply, 160);   // while a slider moves, once it rests a moment
  }

  // init({features, section, note, open, apply}): features = the drawn reaches (GeoJSON, for the miles); section = the
  // panel element the sliders go at the top of; note = an element to fill with the note (the page puts it by the panel);
  // open() = show the panel; apply(pass) = hide every stream for which pass(properties) is false (pass null: show all)
  function init(opts) {
    o = opts;
    Object.assign(st, parse(location.hash));
    // the species some stream on this map has (a record or a designation naming it): only those are offered, and one in
    // the link that none has is left out
    const seen = new Set();
    (o.features || []).forEach(f => { for (const ch of (f.properties || {}).sp || "") seen.add(ch.toUpperCase()); });
    have = SPECIES.filter(([, c]) => seen.has(c)).map(([k]) => k);
    if (!have.includes(st.sp)) { st.sp = ""; st.rec = false; }
    hasFlow = (o.features || []).some(f => hasQ(f.properties || {}));
    if (!hasFlow) { st.cfs = st.cfsmax = 0; }
    el = document.createElement("div");
    el.className = "sf";
    const ticks = (vals, max, lab) => vals.map(i => `<button type="button" data-i="${i}" tabindex="-1" style="left:` +
      `${at(i, max)}">${lab(i)}</button>`).join("");
    const head = name => `<div class="sfl"><span>${name}</span><b class="sfv"></b></div>`;
    // a two-thumb slider: one track, the least and the most shown ("any" at either end: no limit that way)
    const range = (k, extra) => { const R = RANGES[k], T = TOP(k);
      return `<div class="sfr" data-k="${k}">${head(R.name)}<div class="sfw">` +
        `<input type="range" class="lo" min="0" max="${T}" step="1" value="0" aria-label="${R.name}: the least shown">` +
        `<input type="range" class="hi" min="0" max="${T}" step="1" value="${T}" aria-label="${R.name}: the most shown">` +
        `</div><div class="sft">${ticks([...R.steps.keys(), T], T, i => i % T ? String(R.steps[i]).replace(/^0\./, ".") : "any")}` +
        `</div>${extra || ""}</div>`; };
    el.innerHTML = `<div class="sfh"><span>Filter streams</span><button type="button" class="sfclr" hidden>Show all</button></div>` +
      `<div class="sfr" data-k="fish">${head("Fish score")}<input type="range" min="0" max="${FISH[1]}" step="${FISH[2]}" ` +
      `value="0" aria-label="Fish score: the least shown"><div class="sft">${ticks([0, 25, 50, 75, 100], FISH[1],
        i => i ? i : "any")}</div></div>` +
      range("sqmi") +
      // the mean annual flow, where the reaches carry it
      (hasFlow ? range("cfs", `<div class="sfq" hidden>Streams with no flow estimate are left out</div>`) : "") +
      // the trout species: a button for each this map's streams have, and "recorded only" while one is chosen
      (have.length ? `<div class="sfr" data-k="sp">${head("Trout species")}<div class="sfc" role="group" ` +
        `aria-label="Trout species"><button type="button" data-s="">Any</button>` +
        have.map(k => `<button type="button" data-s="${k}">${SPECIES.find(x => x[0] === k)[3]}</button>`).join("") +
        `</div><label class="sfrec" hidden><input type="checkbox"><span>Recorded only<small>a survey, a stocking or a ` +
        `sighting names it here, not only a designated water</small></span></label></div>` : "") +
      `<div class="sfn"></div>`;
    o.section.insertBefore(el, o.section.firstChild);
    const fr = el.querySelector(".sfr[data-k=fish]"), fi = fr.querySelector("input");
    fi.addEventListener("input", () => set({fish: +fi.value}, false));
    fi.addEventListener("change", () => set({fish: +fi.value}, true));
    fr.querySelectorAll(".sft button").forEach(t => t.addEventListener("click", () => set({fish: +t.dataset.i}, true)));

    // each two-thumb slider's thumbs (0 the least, 1 the most): each stops a place short of the other
    Object.keys(RANGES).forEach(k => {
      const R = RANGES[k], dr = el.querySelector(`.sfr[data-k=${k}]`);
      if (!dr) return;
      const w = dr.querySelector(".sfw"), [lo, hi] = w.querySelectorAll("input"), T = TOP(k);
      const put = (which, i, now) => {
        const [a, b] = places(k), j = which ? Math.max(i, a + 1) : Math.min(i, b - 1);
        set(which ? {[R.hi]: j >= T ? 0 : R.steps[j]} : {[R.lo]: R.steps[j]}, now);
      };
      const nearer = f => { const [a, b] = places(k); return f <= a ? 0 : f >= b ? 1 : f - a <= b - f ? 0 : 1; };
      [lo, hi].forEach((inp, which) => ["input", "change"].forEach(ev =>      // keys and screen readers
        inp.addEventListener(ev, () => put(which, +inp.value, ev === "change"))));
      dr.querySelectorAll(".sft button").forEach(t => t.addEventListener("click", () => {
        const i = +t.dataset.i;
        put(nearer(i), i, true);
      }));
      // A finger or the mouse on the track moves the nearer thumb (the inputs under it take no pointer, only keys and
      // screen readers): a tap puts it there, a drag that starts sideways carries it, and one that starts up or down is
      // the panel's to scroll (touch-action: pan-y: the browser then cancels the pointer here; where it doesn't, the
      // slider leaves that finger alone all the same)
      let drag = null;
      const placeAt = x => { const r = w.getBoundingClientRect();
        return Math.max(0, Math.min(T, (x - r.left - THUMB / 2) / Math.max(1, r.width - THUMB) * T)); };
      w.addEventListener("pointerdown", e => {
        if (drag || (e.pointerType === "mouse" && e.button !== 0)) return;
        const f = placeAt(e.clientX);
        drag = {id: e.pointerId, x: e.clientX, y: e.clientY, which: nearer(f), moved: e.pointerType === "mouse", swipe: false};
        try { w.setPointerCapture(e.pointerId); } catch (_) {}
        if (drag.moved) { e.preventDefault(); put(drag.which, Math.round(f), false); }
    });
    w.addEventListener("pointermove", e => {
      if (!drag || e.pointerId !== drag.id || drag.swipe) return;
      if (!drag.moved) {
        const dx = Math.abs(e.clientX - drag.x), dy = Math.abs(e.clientY - drag.y);
        if (dx < 4 && dy < 4) return;
        if (dy > dx) { drag.swipe = true; return; }  // up or down: a scroll, not the slider's
        drag.moved = true;
      }
      put(drag.which, Math.round(placeAt(e.clientX)), false);
    });
    const end = e => {
      if (!drag || e.pointerId !== drag.id) return;
      const d = drag;
      drag = null;
      if (e.type === "pointerup" && !d.swipe) put(d.which, Math.round(placeAt(e.clientX)), true);
      else if (d.moved) apply();                   // taken away midway (a scroll, a lost capture): it stays where it got to
    };
    ["pointerup", "pointercancel", "lostpointercapture"].forEach(ev => w.addEventListener(ev, end));
    });

    const sr = el.querySelector(".sfr[data-k=sp]");
    if (sr) {
      sr.querySelectorAll(".sfc button").forEach(t => t.addEventListener("click", () =>
        set(t.dataset.s ? {sp: t.dataset.s} : {sp: "", rec: false}, true)));
      sr.querySelector(".sfrec input").addEventListener("change", e => set({rec: e.target.checked}, true));
    }

    const clear = () => { Object.assign(st, NONE); apply(); };
    el.querySelector(".sfclr").addEventListener("click", clear);
    note = o.note;
    note.classList.add("sfnote");
    note.hidden = true;
    note.innerHTML = `<span class="sfnt" role="button" tabindex="0" title="Change the filter"></span>` +
      `<button type="button" class="sfx" title="Show all streams" aria-label="Show all streams">×</button>`;
    note.querySelector(".sfx").addEventListener("click", e => { e.stopPropagation(); clear(); });
    const nt = note.querySelector(".sfnt");
    nt.addEventListener("click", () => o.open && o.open());
    nt.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nt.click(); } });
    if (on()) apply(); else render();
  }

  if (typeof document !== "undefined" && !document.getElementById("sf-style")) {
    const s = document.createElement("style");
    s.id = "sf-style";
    const T = THUMB, track = "height:6px;border-radius:3px;background:linear-gradient(to right,#ced4da 0,#ced4da var(--p)," +
      "#1864ab var(--p),#1864ab 100%)";
    const track2 = "background:linear-gradient(to right,#ced4da 0,#ced4da var(--p1),#1864ab var(--p1),#1864ab var(--p2)," +
      "#ced4da var(--p2),#ced4da 100%)";
    const thumb = `box-sizing:border-box;width:${T}px;height:${T}px;border-radius:50%;background:#fff;border:2px solid #1864ab;` +
      "box-shadow:0 1px 3px rgba(0,0,0,.3)";
    s.textContent =
      // the sliders: a thumb a fingertip can take, on a track blue where the streams are kept
      ".sf{min-width:212px;margin:0 0 8px;padding:0 0 6px;border-bottom:1px solid #e9ecef;font-size:12px;line-height:1.35}" +
      ".sf .sfh{display:flex;justify-content:space-between;align-items:center;min-height:24px;font-weight:600;font-size:11px;" +
      "color:#495057;text-transform:uppercase;letter-spacing:.06em}" +
      ".sf .sfclr{position:relative;border:0;background:none;padding:3px 0 3px 10px;font:inherit;font-size:12px;" +
      "font-weight:400;letter-spacing:0;text-transform:none;color:#1864ab;cursor:pointer}" +
      ".sf .sfclr::after{content:'';position:absolute;inset:-8px -8px -8px -4px}.sf .sfclr[hidden]{display:none}" +
      ".sf .sfr{margin-top:4px}.sf .sfl{display:flex;justify-content:space-between;align-items:baseline;gap:8px}" +
      ".sf .sfv{font-weight:600;color:#1864ab}.sf .sfv.any{font-weight:400;color:#7a828c}" +
      `.sf input[type=range]{-webkit-appearance:none;appearance:none;display:block;width:100%;height:${T + 8}px;` +
      `margin:0;padding:0;background:transparent;cursor:pointer;--p:${T / 2}px}` +
      `.sf input[type=range]::-webkit-slider-runnable-track{${track}}` +
      `.sf input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;${thumb};margin-top:${3 - T / 2}px}` +
      `.sf input[type=range]::-moz-range-track{${track}}.sf input[type=range]::-moz-range-thumb{${thumb}}` +
      ".sf input[type=range]:focus{outline:none}" +
      ".sf input[type=range]:focus-visible::-webkit-slider-thumb{outline:2px solid #74c0fc;outline-offset:1px}" +
      // the drainage's two thumbs: two sliders laid on one track, blue between them, the track taking the pointer (init)
      `.sf .sfw{position:relative;height:${T + 8}px;--p1:${T / 2}px;--p2:calc(100% - ${T / 2}px);cursor:pointer;` +
      "touch-action:pan-y;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;" +
      "-webkit-tap-highlight-color:transparent}" +
      ".sf .sfw input[type=range]{position:absolute;left:0;top:0;pointer-events:none}" +
      `.sf .sfw .lo::-webkit-slider-runnable-track{${track2}}.sf .sfw .lo::-moz-range-track{${track2}}` +
      ".sf .sfw .hi::-webkit-slider-runnable-track{background:none}.sf .sfw .hi::-moz-range-track{background:none}" +
      ".sf .sft{position:relative;height:18px;margin-top:-4px}" +
      ".sf .sft button{position:absolute;top:0;transform:translateX(-50%);border:0;background:none;padding:1px 3px;" +
      "font:inherit;font-size:10.5px;line-height:15px;color:#7a828c;cursor:pointer;white-space:nowrap}" +
      ".sf .sft button.on{color:#1864ab;font-weight:600}" +
      ".sf .sfn{margin-top:2px;color:#7a828c}.sf .sfn b{color:#1d1d1f}" +
      ".sf .sfq{margin-top:-2px;font-size:10.5px;color:#7a828c}.sf .sfq[hidden]{display:none}" +
      // the species: buttons a fingertip can take, the chosen one filled; "recorded only" a box with its words
      ".sf .sfc{display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 2px}" +
      ".sf .sfc button{min-height:32px;padding:0 11px;border:1px solid #ced4da;border-radius:16px;background:#fff;" +
      "font:inherit;font-size:12px;color:#343a40;cursor:pointer;-webkit-tap-highlight-color:transparent}" +
      ".sf .sfc button[aria-pressed=true]{background:#1864ab;border-color:#1864ab;color:#fff;font-weight:600}" +
      ".sf .sfrec{display:flex;align-items:flex-start;gap:7px;padding:5px 0 1px;cursor:pointer}.sf .sfrec[hidden]{display:none}" +
      ".sf .sfrec input{flex:none;width:18px;height:18px;margin:0;accent-color:#1864ab}" +
      ".sf .sfrec small{display:block;font-size:10.5px;color:#7a828c}" +
      // a popup's "Species" line: the species the filter has chosen in bold
      ".sfsp{font-weight:600}" +
      // the note: under the 2D map's layer button (hidden while its list is open: the list shows the same), at the head
      // of the 3D map's panel while it is folded
      ".sfnote{display:flex;align-items:center;gap:2px;max-width:240px;box-sizing:border-box;background:#e7f0fb;" +
      "border-radius:8px;box-shadow:0 1px 5px rgba(0,0,0,.25);padding:3px 2px 3px 9px;" +
      "font:12px/1.35 system-ui,-apple-system,sans-serif;color:#1d1d1f;text-align:left}" +
      ".sfnote[hidden]{display:none}.sfnote .sfnt{flex:1;cursor:pointer}.sfnote .sfnt span{color:#56606b}" +
      ".sfnote .sfx{flex:none;width:32px;height:32px;border:0;border-radius:6px;background:none;padding:0;" +
      "font:20px/32px system-ui,-apple-system,sans-serif;color:#495057;cursor:pointer}.sfnote .sfx:hover{background:#d0e2f7}" +
      ".leaflet-control-layers-expanded~.sfnote{display:none}" +
      ".panel>.sfnote{max-width:none;margin:7px -3px 0;box-shadow:none}.panel:not(.min)>.sfnote{display:none}";
    document.head.appendChild(s);
  }
  // a stream popup's "Species" line (map_drainages.js, map3d.html): for each species, "recorded <the latest year>" where
  // a trout record names it and "designated" where a designated water does ("" for a reach with none)
  function speciesRow(p) {
    const s = (p && p.sp) || "";
    const parts = SPECIES.map(([k, c, name]) => {
      const m = s.match(new RegExp(c + "(\\d{4})?")), d = s.includes(c.toLowerCase());
      if (!m && !d) return "";
      const how = [m ? "recorded" + (m[1] ? " " + m[1] : "") : "", d ? "designated" : ""].filter(Boolean).join(", ");
      return `<span${k === st.sp ? ' class="sfsp"' : ""}>${name}: ${how}</span>`;
    }).filter(Boolean);
    return parts.length ? `<tr><td>Species</td><td>${parts.join(" · ")}</td></tr>` : "";
  }
  // the species test as a MapLibre expression: the reach's "sp" holds the capital (recorded) or the small letter
  const spExpr = () => {
    const v = ["coalesce", ["get", "sp"], ""], c = SPC[st.sp];
    return st.rec ? ["in", c, v] : ["any", ["in", c, v], ["in", c.toLowerCase(), v]];
  };

  return {init, pass, parse, on, speciesRow,
          // "&fish=60&sqmi=5-25&cfs=3-15&trout=brook" for the link to the other map ("" unfiltered; "&sqmi=5" without a
          // most, "&sqmi=0-25" without a least, the same for "&cfs="; "&trout=brook-recorded": recorded only)
          part: () => (st.fish ? "&fish=" + st.fish : "") +
                      (st.sqmi || st.sqmax ? "&sqmi=" + st.sqmi + (st.sqmax ? "-" + st.sqmax : "") : "") +
                      (st.cfs || st.cfsmax ? "&cfs=" + st.cfs + (st.cfsmax ? "-" + st.cfsmax : "") : "") +
                      (st.sp ? "&trout=" + st.sp + (st.rec ? "-recorded" : "") : ""),
          // the filter as a MapLibre expression (map3d.html): ["all"] unfiltered
          expr: () => ["all", ...(st.fish ? [[">=", ["to-number", ["get", "fs"], 0], st.fish]] : []),
                              ...(st.sqmi ? [[">=", ["to-number", ["get", "a"], 0], minKm2(st.sqmi)]] : []),
                              ...(st.sqmax ? [["<", ["to-number", ["get", "a"], 0], maxKm2(st.sqmax)]] : []),
                              ...(st.cfs ? [["all", ["has", "q"], [">=", ["to-number", ["get", "q"], -1], st.cfs]]] : []),
                              ...(st.cfsmax ? [["all", ["has", "q"], ["<=", ["to-number", ["get", "q"], 1e12], st.cfsmax]]] : []),
                              ...(st.sp ? [spExpr()] : [])],
          state: () => Object.assign({}, st)};
})();
