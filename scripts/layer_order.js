// One order for the layer lists of every map (the user, 2026-11-23: "the order of the items is always different, lets
// make the order the same everytime"). The 2D map (map_drainages.js), the 3D map (map3d.html) and the one-file map
// (14_portable.py) name their entries by these keys (the 3D map's layer ids) and list them in this order; an entry a
// map lacks is left out and the others keep their order. Before, each page had its own: the 2D list took folium's
// layers in the order 06_map.py makes them and put the streams, drainages, trails and roads after them; the 3D list
// put each road class in front of the last, so its roads ran backwards. 06_map.py and 14_portable.py inline this file.
const LAYER_ORDER = [
  // how the 2D map looks (the 3D map has these in its Terrain and Basemap sections)
  "hillshade", "labels", "relief",
  // what the maps open with: streams, drainages, the long trail and lakes; the lakes' depths beside them
  "streams", "basins", "pct", "lakes", "lake_depth",
  // fishing
  "best", "wild_trout_waters", "trout", "gauges", "springs",
  // falls and drops (one group): the known falls, then the drops from most to least like a fall
  "falls", "drop:matches mapped waterfall", "drop:unmapped waterfall-like step", "drop:unmapped short fall (big creek)",
  "drop:unmapped cascade", "drop:steep reach", "drop:dam / weir", "drop:likely DEM artifact",
  // getting there: drive (the roads, one group: from paved to the roughest, then closed to cars, then closed by fire,
  // then those whose state isn't known), the closures, park, then walk or ride (the trails with their bike access)
  "road-paved", "road-graded", "road-high_clearance", "road-4wd", "road-bike", "road-closed", "road-dirt",
  "closures", "closures-fire", "poi-pk", "poi-th", "trailheads", "trails", "bike",
  // land and fire
  "cpad_restricted", "non_fs_land", "wilderness", "critical_habitat", "fires",
];
const layerRank = key => { const i = LAYER_ORDER.indexOf(key); return i < 0 ? LAYER_ORDER.length : i; };

// The 2D map's layers that 06_map.py makes with folium reach the page as names only: the key a name stands for. The
// names that depend on an area's sources come from LBL (06_map.py), the others are the same everywhere.
function layerKey2d(name, LBL) {
  const L = LBL || {}, has = s => !!s && name.includes(s);
  const text = String(name).replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").trim();
  const drop = text.match(/Drops: (.+)$/);
  if (drop) return "drop:" + drop[1].trim();
  if (has(L.falls)) return "falls";
  if (has(L.fires)) return "fires";
  if (has(L.trout_waters)) return "wild_trout_waters";
  if (has(L.access)) return "cpad_restricted";
  if (has(L.gauges)) return "gauges";
  if (has(L.trout_ev)) return "trout";
  const fixed = [["hillshade", /^Terrain shading/], ["labels", /^Place & road labels/], ["relief", /^DEM color relief/],
                 ["best", /Best remote trout water/], ["closures", /Road closures/], ["closures-fire", /Fire closure areas/],
                 ["lake_depth", /Lake depth contours/], ["lakes", /Lakes:/], ["critical_habitat", /^Critical habitat/],
                 ["wilderness", /^Wilderness/], ["non_fs_land", /^Non-Forest-Service land/],
                 ["springs", /Springs and seeps/], ["trailheads", /Approach start points/]];
  const hit = fixed.find(([, re]) => re.test(text));
  return hit ? hit[0] : null;
}

// The layers go along with the switch between an area's 2D and 3D maps (the user, 2026-11-24: "keep my active layers
// when switching from 2d to 3d"), in the link itself, after the view: #lat,lon,zoom[,pitch,bearing]&on=..&off=..&base=..
// with the keys above. "on" lists the layers the page shows that it opens without, "off" those it opens with that are
// off, "base" its base map when that isn't the one it opens with (gray, topo, sat; otm on the 2D map only). The page the
// link opens turns on and off the layers it has and leaves its others as it opens them (both pages open with the same
// ones: streams, drainages, the long trail, lakes, terrain shading and labels), and keeps the rest of the list (the
// layers only the other page has) in its own link back, so they are on again after a round trip. A link without the
// list (a fresh open, the overview's and the profiles' links) opens the default layers.
const layerLink = {
  // a key as it reads in a link: "drop:dam+/+weir" (a space is "+"; the few characters the link uses are %-coded)
  enc: k => String(k).replace(/[%&,=#+]/g, encodeURIComponent).replace(/ /g, "+"),
  // "#view&on=a,b&off=c&base=sat" -> {view: "view", on: Set, off: Set, base: "sat"}
  parse(hash) {
    const [view, ...parts] = String(hash || "").replace(/^#/, "").split("&");
    const st = {view, on: new Set(), off: new Set(), base: ""};
    const dec = x => { try { return decodeURIComponent(x.replace(/\+/g, " ")); } catch (_) { return ""; } };
    parts.forEach(p => {
      const i = p.indexOf("="), k = p.slice(0, i), v = p.slice(i + 1);
      if (k === "on" || k === "off") v.split(",").map(dec).filter(Boolean).forEach(x => st[k].add(x));
      else if (k === "base") st.base = dec(v);
    });
    return st;
  },
  // the part after the view: "" when the page shows what it opened with
  part(on, off, base) {
    const list = ks => [...ks].sort((a, b) => layerRank(a) - layerRank(b)).map(layerLink.enc).join(",");
    return (on.size ? "&on=" + list(on) : "") + (off.size ? "&off=" + list(off) : "") +
           (base ? "&base=" + layerLink.enc(base) : "");
  },
};
