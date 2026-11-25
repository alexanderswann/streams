// Shared by the area maps (06_map.py), the map of all areas (13_overview.py) and the one-file phone map
// (14_portable.py); its styles are in map_phone.css.
// phoneControls(map):
//  - on a phone the credits fold to one line: a tap opens them, another tap (not on a link) folds them again;
//  - a "my location" button under the zoom buttons: a tap asks the browser where you are and puts the map there, with
//    a blue dot and a ring for the fix's accuracy. The dot then keeps moving with you; another tap centres on it again;
//  - popups keep clear of the buttons at the top, and their heads and open fish-score breakdowns of the legend too
//    (keepPopupsClear).
function phoneControls(map) {
  keepPopupsClear(map);
  const attr = map.attributionControl && map.attributionControl.getContainer();
  if (attr) {
    attr.title = "Map and data credits";
    L.DomEvent.on(attr, "click", e => {
      if (window.innerWidth > 640) return;
      if (!attr.classList.contains("open")) { L.DomEvent.preventDefault(e); attr.classList.add("open"); }
      else if (!(e.target.closest && e.target.closest("a"))) attr.classList.remove("open");
    });
  }
  if (!navigator.geolocation) return;
  const ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">'
    + '<circle cx="12" cy="12" r="3.5" fill="currentColor"/><circle cx="12" cy="12" r="7.5"/>'
    + '<path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/></svg>';
  let btn = null, dot = null, ring = null, last = null, centre = false, watching = false, note = null, noteTimer = 0;
  const say = text => {
    if (!note) { note = L.control({position: "topleft"}); note.onAdd = () => L.DomUtil.create("div", "locme-msg"); }
    note.addTo(map); note.getContainer().textContent = text;
    clearTimeout(noteTimer); noteTimer = setTimeout(() => note.remove(), 6000);
  };
  const zoomTo = () => Math.max(map.getZoom(), 14);
  // on a phone the panel at the bottom can cover the middle of the map: put the dot in the middle of what is left
  const goTo = latlng => {
    const z = zoomTo(), size = map.getSize(), box = map.getContainer().getBoundingClientRect();
    let cover = 0;
    document.querySelectorAll(".leaflet-bottom .leaflet-control").forEach(c => {
      const r = c.getBoundingClientRect();
      if (r.width > size.x / 2 && r.height > 0) cover = Math.max(cover, box.bottom - r.top);
    });
    cover = Math.min(Math.max(cover, 0), size.y * 0.7);
    map.setView(map.unproject(map.project(latlng, z).add([0, cover / 2]), z), z);
  };
  const ctl = L.control({position: "topleft"});
  ctl.onAdd = () => {
    const bar = L.DomUtil.create("div", "leaflet-bar leaflet-control");
    btn = L.DomUtil.create("a", "locme", bar);
    btn.href = "#"; btn.title = "Show my location"; btn.innerHTML = ICON;
    btn.setAttribute("role", "button"); btn.setAttribute("aria-label", "Show my location");
    L.DomEvent.disableClickPropagation(bar);
    L.DomEvent.on(btn, "click", e => {
      L.DomEvent.preventDefault(e);
      if (last) goTo(last.latlng); else centre = true;
      if (!watching) {
        watching = true; btn.classList.add("busy");
        map.locate({watch: true, setView: false, enableHighAccuracy: true, maximumAge: 15000, timeout: 20000});
      }
    });
    return bar;
  };
  ctl.addTo(map);
  map.on("locationfound", e => {
    last = e; btn.classList.remove("busy"); btn.classList.add("on");
    if (!dot) {
      ring = L.circle(e.latlng, {radius: e.accuracy, color: "#1c7ed6", weight: 1, opacity: .5, fillOpacity: .12,
                                 interactive: false}).addTo(map);
      dot = L.circleMarker(e.latlng, {radius: 7, color: "#fff", weight: 2.5, fillColor: "#1c7ed6", fillOpacity: 1,
                                      interactive: false}).addTo(map);
    } else { dot.setLatLng(e.latlng); ring.setLatLng(e.latlng).setRadius(e.accuracy); }
    if (centre) { centre = false; goTo(e.latlng); }
  });
  map.on("locationerror", e => {
    if (last && e.code !== 1) return;              // a slow fix while the dot is already shown: keep the last one
    map.stopLocate(); watching = false; centre = false;
    btn.classList.remove("busy"); if (e.code === 1) btn.classList.remove("on");
    say(e.code === 1 ? "Location is blocked for this page: allow it in the browser's settings, then tap again."
                     : "Your location isn't available right now; tap to try again.");
  });
}

// Popups keep clear of the controls at the top of the map (zoom, full screen, my location, layers, the phone map's
// panel). Leaflet pans a popup into view as it opens but doesn't count them, and doesn't pan again when the popup's
// content changes: on a phone a stream popup's first lines, its name and fish score, sat under the buttons at the top
// left. Once Leaflet's own pan is done, and when the fish score's breakdown opens or folds on a tap (map_score.js's
// "fs-toggle"), the map pans the popup (or the open breakdown) to the right of the buttons where it fits there (a wide
// screen), else below them; and brings the popup's head (its first lines down to the fish score, or its name) or the
// open breakdown up into view, above the controls at the bottom too. Where that is taller than the room the area map's
// legend leaves, the legend folds while it needs the room (on a phone it stands open over the lower half at first: at
// 320 x 568 it covered the popup's name and fish score, at 375 x 812 the breakdown's last rows, the score among them)
// and comes back when the breakdown folds (if folded for it) or the popup closes. With the breakdown folded, a trout
// calendar the user tapped (map_calendar.js, the same event) is what must be seen, the half-month's reasons under its
// strip included: at 375 x 812 the open legend covered them. Not on hover: the popup would move away from the pointer.
function keepPopupsClear(map) {
  let open = null, folded = [];          // the legends folded for the popup: [legend, for its head (else its breakdown)]
  // those folded for the breakdown come back when it folds, all of them when the popup closes and no other opens in its
  // place (those still folded: one the user opened again is left as it is)
  const unfold = all => { folded = folded.filter(([d, head]) => {
    if (head && !all) return true;
    if (d.classList.contains("min")) d.querySelector(".lx").click();
    return false; }); };
  const union = els => {
    const r = els.map(e => e.getBoundingClientRect()).filter(b => b.width && b.height);
    return r.length ? {left: Math.min(...r.map(b => b.left)), top: Math.min(...r.map(b => b.top)),
                       right: Math.max(...r.map(b => b.right)), bottom: Math.max(...r.map(b => b.bottom))} : null;
  };
  // A pan or zoom of Leaflet's still under way: the popup measured now is where it was, and a pan of ours started now
  // cuts Leaflet's short. On a big area map the page is busy as the popup opens, the check at 350 ms came before
  // Leaflet's own pan had moved, and its pan down kept the popup 33 px past the left edge (375 px). It waits for the
  // pan's end. The user's own drag is left alone.
  const busy = () => !!((map._panAnim && map._panAnim._inProgress) || map._animatingZoom);
  let waiting = false;
  const clear = (again = 1) => {
    const el = open && open.isOpen() && open.getElement();
    if (!el || (map.dragging && map.dragging._draggable && map.dragging._draggable._moving)) return;
    if (busy()) {
      if (!waiting) { waiting = true; map.once("moveend", () => { waiting = false; setTimeout(() => clear(again)); }); }
      return;
    }
    // with the breakdown open it is what must be seen whole and clear of the controls (the popup's head may go under
    // them meanwhile: on a 568 px screen the two don't fit at once); folded, a trout calendar the user tapped, else the
    // popup's head, down to its fish score (or its name)
    const w = el.querySelector(".leaflet-popup-content-wrapper") || el;
    const fsb = [...el.querySelectorAll(".fsb")].filter(b => getComputedStyle(b).display !== "none");
    const shown = fsb.length ? fsb : [...el.querySelectorAll(".calc.tapped")];
    const p = union(shown.length ? shown : [w]);
    if (!p) return;
    const h = !shown.length && (w.querySelector(".fsr") || w.querySelector("b"));
    const foot = h ? Math.min(p.bottom, h.getBoundingClientRect().bottom) : p.bottom;
    const c = map.getContainer(), m = c.getBoundingClientRect();
    const tl = union([...c.querySelectorAll(".leaflet-top.leaflet-left .leaflet-control")]);
    const tr = union([...c.querySelectorAll(".leaflet-top.leaflet-right .leaflet-control")]);
    const across = (b, dx) => b && p.left + dx < b.right && p.right + dx > b.left;
    const hits = [tl, tr].filter(b => across(b, 0) && p.top < b.bottom && p.bottom > b.top);
    let dx = 0, dy = 0;
    if (hits.length) {
      const right = hits.length === 1 && hits[0] === tl ? tl.right + 6 - p.left : 0;
      const room = (tr && p.top < tr.bottom ? tr.left : m.right) - 5;
      if (right && p.right + right <= room) dx = right;
      else dy = Math.max(...hits.map(b => b.bottom)) + 6 - p.top;
    }
    // a panel opened at the top over half the map is the user's: leave the popup where it is. Else what must be seen
    // comes up into view, above the controls at the bottom too (the area map's legend, the scale, the credits line),
    // where there is room under the controls at the top
    if (dy > m.height / 2) dy = 0;
    else {
      const floor = Math.min(m.bottom, ...[...c.querySelectorAll(".leaflet-bottom .leaflet-control")]
        .map(b => b.getBoundingClientRect()).filter(b => b.width && b.height && p.left + dx < b.right && p.right + dx > b.left)
        .map(b => b.top)) - 5;
      const ceil = Math.max(m.top, ...[tl, tr].filter(b => across(b, dx)).map(b => b.bottom)) + 6;
      const lg = foot - p.top > floor - ceil ? [...c.querySelectorAll(".lgd:not(.min)")]
        .filter(d => { const b = d.getBoundingClientRect(); return p.left + dx < b.right && p.right + dx > b.left; }) : [];
      if (lg.length) {                         // taller than the room the open legend leaves: the legend folds
        lg.forEach(d => { d.querySelector(".lx").click(); folded.push([d, !shown.length]); });
        requestAnimationFrame(() => clear(again));
        return;
      }
      if (foot + dy > floor) dy = Math.max(floor - foot, ceil - p.top);
      // above the room: a popup lifted for its breakdown kept its name off the top of the screen once it folded (a
      // pixel's slack: Leaflet's own pan leaves 5 px, the room 6)
      else if (p.top + dy < ceil - 1) dy = ceil - p.top;
    }
    if (!dx && !dy) return;
    map.panBy([-dx, -dy]);
    if (again && shown.length) map.once("moveend", () => clear(again - 1));
  };
  // After Leaflet's own pan, and again at 350 ms and 1 s: on a slow phone its pan ran past a single check, which then
  // saw the popup mid-way and was spent (320 px). A check moves the popup only where it still overlaps the controls;
  // the listener goes after 1 s, so a pan of the user's own later is left alone.
  map.on("popupopen", e => {
    open = e.popup;
    folded.forEach(f => { f[1] = true; });   // a popup opened in place of another keeps the legends folded for that one
    const p = e.popup, now = () => { if (open === p) clear(0); };
    map.on("moveend", now);
    setTimeout(now, 350);
    setTimeout(() => { now(); map.off("moveend", now); }, 1000);
  });
  // Leaflet closes a popup before it opens the next in its place: the legends come back only if none opened
  map.on("popupclose", e => { if (open === e.popup) { open = null; setTimeout(() => { if (!open) unfold(true); }); } });
  document.addEventListener("fs-toggle", () => {
    const el = open && open.isOpen() && open.getElement();
    if (el && !el.querySelector(".fsr.open")) unfold(false);
    clear();
  });
}
