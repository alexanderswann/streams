// Shared by the area maps (06_map.py), the map of all areas (13_overview.py) and the one-file phone map
// (14_portable.py); its styles are in map_phone.css.
// phoneControls(map):
//  - on a phone the credits fold to one line: a tap opens them, another tap (not on a link) folds them again;
//  - a "my location" button under the zoom buttons: a tap asks the browser where you are and puts the map there, with
//    a blue dot and a ring for the fix's accuracy. The dot then keeps moving with you; another tap centres on it again;
//  - popups keep clear of the buttons at the top (keepPopupsClear).
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
// "fs-toggle"), the map pans the popup, with its breakdown, to the right of the buttons where it fits there (a wide
// screen), else below them; and brings the breakdown's foot up into view where there is room above. Not on hover: the
// popup would move away from the pointer.
function keepPopupsClear(map) {
  let open = null;
  const union = els => {
    const r = els.map(e => e.getBoundingClientRect()).filter(b => b.width && b.height);
    return r.length ? {left: Math.min(...r.map(b => b.left)), top: Math.min(...r.map(b => b.top)),
                       right: Math.max(...r.map(b => b.right)), bottom: Math.max(...r.map(b => b.bottom))} : null;
  };
  const clear = () => {
    const el = open && open.isOpen() && open.getElement();
    if (!el) return;
    const shown = [...el.querySelectorAll(".fsb")].filter(b => getComputedStyle(b).display !== "none");
    const p = union([el.querySelector(".leaflet-popup-content-wrapper") || el, ...shown]);
    if (!p) return;
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
      if (dy > m.height / 2) dy = 0;          // a panel opened that tall is the user's: leave the popup where it is
    }
    if (!dy && shown.length && p.bottom > m.bottom - 5) {
      const ceil = Math.max(m.top, ...[tl, tr].filter(b => across(b, dx)).map(b => b.bottom)) + 6;
      dy = -Math.max(0, Math.min(p.bottom - (m.bottom - 5), p.top - ceil));
    }
    if (dx || dy) map.panBy([-dx, -dy]);
  };
  map.on("popupopen", e => {
    open = e.popup;
    let done = false;
    const go = () => { if (!done) { done = true; clear(); } };
    map.once("moveend", go);                  // after Leaflet's own pan, or at once where it made none
    setTimeout(go, 350);
  });
  map.on("popupclose", e => { if (open === e.popup) open = null; });
  document.addEventListener("fs-toggle", clear);
}
