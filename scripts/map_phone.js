// Shared by the area maps (06_map.py), the map of all areas (13_overview.py) and the one-file phone map
// (14_portable.py); its styles are in map_phone.css.
// phoneControls(map):
//  - on a phone the credits fold to one line: a tap opens them, another tap (not on a link) folds them again;
//  - a "my location" button under the zoom buttons: a tap asks the browser where you are and puts the map there, with
//    a blue dot and a ring for the fix's accuracy. The dot then keeps moving with you; another tap centres on it again.
function phoneControls(map) {
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
