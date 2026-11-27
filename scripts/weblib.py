"""The site as a web app that works without a connection (2026-11-24; the user: "what would it take to make a version of
this fully downloadable to mobile so it can be used when in the backcountry with no connection").

The pages load their libraries from the site itself, from lib/ (Leaflet, jQuery, Bootstrap and the folium plugins for
the 2D map, MapLibre and the label fonts for the 3D map, Plotly for the creek profiles; kept in scripts/web/lib/ at the
versions the pages loaded from CDNs, LICENSES.txt there), so no page needs a CDN. At the site's root sit sw.js (the
service worker), offline.js (the "Save for offline" panel and the switch to the saved maps with no connection), the
web app's manifest and its icons: on an iPhone, Safari's Add to Home Screen makes it an app, whose saved maps stay.
  split_script(html, names)  a folium page's own script out of it, run by StreamsLoad(names) (06_map.py's 2D map)
  localize(html, up)  a page's CDN addresses -> lib/ (up: "../" from an area's folder, "" at the root); stops on any
                      script or stylesheet it doesn't know, so a new library can't quietly need the network again
  head(up)            the tags every page's <head> gets: the manifest, icons, theme colour and offline.js
  install(dest)       sw.js, offline.js, the manifest and lib/ into dest, and the icons drawn there (13_overview.py, into
                      output/; publish_site.sh copies them on to the site); writes only files that differ
  lists(site)         <area>/offline.json in a copy of the site (publish_site.sh, on docs/): every file the area's folder
                      holds (any new per-area file is in it by being published; not its build stamp, which no page
                      reads), with its size and a hash; the shared files (lib/, icons/); and a version, a hash of the
                      area's files and the shared ones, which a saved copy is compared with ("update available"). And
                      offline.json at the root: the root's files a saved area keeps too (index.html, the credits page,
                      offline.js, the manifest), listed apart because the map of all areas changes with every publish:
                      in each area's list it would rewrite all twelve each time (and send every area through
                      build_stamp.py's publish gate)
  pack(site)          in a copy of the site (publish_site.sh: docs/; phone_sync.sh: phone/), each area's big files (GZ)
                      replaced by <name>.gz, the very bytes gzip-compressed (2026-11-25: they came to 663 MB of the
                      site's 717, 116 MB compressed; GitHub Pages' limit is 1 GB, and a phone keeps what it saves). The
                      pages fetch and unpack them with lib/streams/load.js; output/ keeps them plain, for the pages
                      opened from disk and for the checks. Run before lists(), which then lists the .gz files
Run as a script:  weblib.py lists <site dir>  |  weblib.py install <dir>  |  weblib.py pack <site dir>
"""
import concurrent.futures, hashlib, json, os, re, shutil, struct, sys, zlib

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
# the CDN addresses the pages used until 2026-11-24 -> their copies in lib/ (same versions; MapLibre was "@5", which
# unpkg served as 5.24.1 that day: map3d.html names it). folium 0.20 writes the 2D page's; 13_overview.py and
# profiles.html had Leaflet's and Plotly's.
LIB = {
    "https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js": "lib/leaflet-1.9.3/leaflet.js",
    "https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css": "lib/leaflet-1.9.3/leaflet.css",
    "https://code.jquery.com/jquery-3.7.1.min.js": "lib/jquery-3.7.1/jquery-3.7.1.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.2.2/dist/js/bootstrap.bundle.min.js": "lib/bootstrap-5.2.2/js/bootstrap.bundle.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.2.2/dist/css/bootstrap.min.css": "lib/bootstrap-5.2.2/css/bootstrap.min.css",
    "https://netdna.bootstrapcdn.com/bootstrap/3.0.0/css/bootstrap-glyphicons.css": "lib/bootstrap-3.0.0/css/bootstrap-glyphicons.css",
    "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.2.0/css/all.min.css": "lib/fontawesome-free-6.2.0/css/all.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.js":
        "lib/leaflet.awesome-markers-2.0.2/leaflet.awesome-markers.js",
    "https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.css":
        "lib/leaflet.awesome-markers-2.0.2/leaflet.awesome-markers.css",
    "https://cdn.jsdelivr.net/gh/python-visualization/folium/folium/templates/leaflet.awesome.rotate.min.css":
        "lib/folium-awesome-rotate/leaflet.awesome.rotate.min.css",
    "https://cdn.jsdelivr.net/npm/leaflet.fullscreen@3.0.0/Control.FullScreen.min.js": "lib/leaflet.fullscreen-3.0.0/Control.FullScreen.min.js",
    "https://cdn.jsdelivr.net/npm/leaflet.fullscreen@3.0.0/Control.FullScreen.css": "lib/leaflet.fullscreen-3.0.0/Control.FullScreen.css",
    "https://cdn.jsdelivr.net/gh/ljagis/leaflet-measure@2.1.7/dist/leaflet-measure.min.js": "lib/leaflet-measure-2.1.7/leaflet-measure.min.js",
    "https://cdn.jsdelivr.net/gh/ljagis/leaflet-measure@2.1.7/dist/leaflet-measure.min.css": "lib/leaflet-measure-2.1.7/leaflet-measure.min.css",
    "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js": "lib/plotly-2.35.2/plotly.min.js",
}
_EXTERNAL = re.compile(r"""<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*["']?((?:https?:)?//[^"'\s>]+)""", re.I)


def localize(html, up):
    """The page with its CDN libraries read from lib/; SystemExit if a script or stylesheet still comes from elsewhere."""
    for url, local in LIB.items():
        html = html.replace(f'"{url}"', f'"{up}{local}"')
    left = [u for u in _EXTERNAL.findall(html)]
    if left:
        raise SystemExit(f"weblib.localize: the page still loads {left[0]} from the network: add a copy to scripts/web/lib/ "
                         f"and its address to weblib.LIB (the offline maps need every library on the site)")
    return html


def split_script(html, names):
    """A folium page and its own script apart: the <script> after </body> (06_map.py's 2D map: the map, its layers,
    markers and popups) leaves the page, which runs StreamsLoad(names) (lib/streams/load.js) in its place; the caller
    writes the script to the last of names. Returns (page, script)."""
    i = html.rfind("</body>")
    m = re.fullmatch(r"(\s*)<script>(.*)</script>(\s*</html>\s*)", html[i + 7:], re.S) if i >= 0 else None
    if not m:
        raise SystemExit("weblib.split_script: no <script> after </body>, as folium writes its page (folium changed?)")
    return html[:i + 7] + m.group(1) + f"<script>StreamsLoad({json.dumps(list(names))});</script>" + m.group(3), m.group(2)


def head(up):
    """The <head> tags of every page: the web app (manifest, icons, colour) and offline.js (which registers sw.js)."""
    return (f'<link rel="manifest" href="{up}manifest.webmanifest">\n'
            f'<link rel="icon" type="image/png" sizes="192x192" href="{up}icons/icon-192.png">\n'
            f'<link rel="apple-touch-icon" href="{up}icons/apple-touch-icon.png">\n'
            '<meta name="theme-color" content="#0b3d91">\n'
            '<meta name="mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-title" content="Streams">\n'
            f'<script src="{up}offline.js"></script>\n')


# The files of an area that the site keeps gzip-compressed (pack): only those its pages load through lib/streams/load.js
# (StreamsLoad), which fetches <name>.gz and runs it as the plain <name> would run. 06_map.py writes the first four
# (stream_map.js: folium's script of the 2D page, with the 2D map's own layers; map3d_layers.js: the layers only the 3D
# map draws), approach_routes.py routes_data.js, 12_profiles.py profiles_data.js, 11c_land.py land_data.js and
# 11d_parcels.py parcels_data.js (map_land.js loads those two), 11e_coverage.py coverage_data.js (map_coverage.js).
GZ = ("map3d_data.js", "stream_map.js", "map3d_layers.js", "routes_data.js", "profiles_data.js", "land_data.js",
      "parcels_data.js", "coverage_data.js")
LOADER = "lib/streams/load.js"      # the pages' <script src> (06_map.py, map3d.html, profiles.html), from an area: ../


def gz_bytes(data):
    """data as one gzip member that depends on nothing but data (and zlib's version): no name, no time, OS "unknown",
    level 9. The same map published again gives the same bytes, so an unchanged area stays unchanged on the site."""
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
    body = c.compress(data) + c.flush()
    return b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff" + body + struct.pack("<II", zlib.crc32(data), len(data) & 0xffffffff)


def _pack_one(path):
    with open(path, "rb") as f:
        data = f.read()
    z = gz_bytes(data)
    if zlib.decompress(z, 31) != data:                    # 31: a gzip member; checked before the plain file goes
        raise SystemExit(f"weblib.pack: {path}.gz does not unpack to {path}")
    with open(path + ".gz", "wb") as f:
        f.write(z)
    os.remove(path)
    return os.path.basename(path), len(data), len(z)


_SRC = re.compile(r"""<script\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", re.I)


def pack(site):
    """Every GZ file of each area folder of a copy of the site replaced by <name>.gz; a summary per kind of file. Stops
    (SystemExit, nothing packed) if a page there loads one of them with a plain <script src>: a page from before
    2026-11-25, which would find no file on the site (06_map.py rebuilds it)."""
    areas = [k for k in sorted(os.listdir(site)) if os.path.isfile(os.path.join(site, k, "stream_map.html"))]
    for k in areas:
        for f in sorted(os.listdir(os.path.join(site, k))):
            if f.endswith(".html"):
                with open(os.path.join(site, k, f), encoding="utf-8", errors="replace") as h:
                    old = sorted(set(_SRC.findall(h.read())) & set(GZ))
                if old:
                    raise SystemExit(f"weblib.pack: {k}/{f} loads {', '.join(old)} with a <script> tag, so the site would "
                                     f"have nothing for it once packed: a page from before 2026-11-25; rebuild "
                                     f"{'the map step (06_map.py)' if f.startswith('stream_map') else 'it from scripts/' + f}")
    paths = [os.path.join(site, k, f) for k in areas for f in GZ if os.path.isfile(os.path.join(site, k, f))]
    with concurrent.futures.ThreadPoolExecutor(4) as ex:   # zlib lets go of the GIL while it compresses
        done = list(ex.map(_pack_one, paths))
    kinds = {}
    for name, a, b in done:
        k = kinds.setdefault(name, [0, 0, 0])
        k[0] += 1; k[1] += a; k[2] += b
    print(f"packed {len(done)} files, {sum(v[1] for v in kinds.values()) / 1e6:.1f} -> "
          f"{sum(v[2] for v in kinds.values()) / 1e6:.1f} MB: " +
          ", ".join(f"{n} x{v[0]} {v[1] / 1e6:.1f} -> {v[2] / 1e6:.1f} MB" for n, v in kinds.items()))
    return done


def _put(path, data):
    """Write only when the bytes differ (publish_site.sh stops on files in output/ written in the last 15 minutes)."""
    if os.path.exists(path) and open(path, "rb").read() == data:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True


def _icon(size):
    """The app's icon: a creek winding down from two peaks, white and light blue on the maps' dark blue, drawn at 4x and
    scaled down. The full square is coloured (iOS rounds the corners; Android's maskable crop keeps the middle 80%)."""
    from PIL import Image, ImageDraw
    import math
    S = size * 4
    im = Image.new("RGB", (S, S), (11, 61, 145))
    d = ImageDraw.Draw(im)
    P = lambda x, y: (x * S, y * S)
    d.polygon([P(.12, .62), P(.37, .27), P(.50, .44), P(.62, .30), P(.88, .62)], fill=(231, 240, 251))
    d.polygon([P(.37, .27), P(.31, .355), P(.35, .34), P(.39, .37), P(.43, .345)], fill=(255, 255, 255))
    r = .04 * S                                       # the creek: discs along a dense path (no seams at joints)
    for i in range(601):
        t = i / 600
        x, y = .5 + .15 * math.sin(math.pi * 1.7 * t) * (.4 + .6 * t), .43 + .45 * t
        d.ellipse([x * S - r, y * S - r, x * S + r, y * S + r], fill=(116, 192, 252))
    import io
    out = io.BytesIO()
    im.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


def install(dest):
    """sw.js, offline.js, the manifest and lib/ into dest (output/), the icons drawn there; lib/ kept equal to web/lib/."""
    n = 0
    for f in ("sw.js", "offline.js", "manifest.webmanifest"):
        n += _put(os.path.join(dest, f), open(os.path.join(WEB, f), "rb").read())
    src, dst = os.path.join(WEB, "lib"), os.path.join(dest, "lib")
    have = set()
    for d_, _, fs in os.walk(src):
        for f in fs:
            rel = os.path.relpath(os.path.join(d_, f), src)
            have.add(rel)
            n += _put(os.path.join(dst, rel), open(os.path.join(d_, f), "rb").read())
    for d_, _, fs in os.walk(dst, topdown=False):
        for f in fs:
            if os.path.relpath(os.path.join(d_, f), dst) not in have:
                os.remove(os.path.join(d_, f)); n += 1
        if d_ != dst and not os.listdir(d_):
            os.rmdir(d_)                          # a library's folder it no longer has
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
        n += _put(os.path.join(dest, "icons", name), _icon(size))
    return n


def _hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


NOT_SAVED = {"offline.json", "build_stamp.json"}   # the lists themselves; the build stamp (B9's record, no page reads it)
ROOT_FILES = ("index.html", "credits.html", "offline.js", "manifest.webmanifest")   # kept fresh by sw.js, not versioned


def _files(top, rel_to):
    out = []
    for d_, ds, fs in os.walk(top):
        ds.sort()
        for f in sorted(fs):
            p = os.path.join(d_, f)
            if f not in NOT_SAVED:
                out.append([os.path.relpath(p, rel_to).replace(os.sep, "/"), os.path.getsize(p), _hash(p)])
    return out


def lists(site):
    """<area>/offline.json for every area folder of a copy of the site (one with a stream_map.html), and offline.json at
    its root."""
    try:
        from config import AREAS
        labels = {k: v["label"] for k, v in AREAS.items()}
    except Exception:
        labels = {}
    shared = [f for d_ in ("lib", "icons") if os.path.isdir(os.path.join(site, d_)) for f in _files(os.path.join(site, d_), site)]
    root = [[f, os.path.getsize(os.path.join(site, f)), _hash(os.path.join(site, f))]
            for f in ROOT_FILES if os.path.exists(os.path.join(site, f))]
    made = []
    for key in sorted(os.listdir(site)):
        folder = os.path.join(site, key)
        if not os.path.isfile(os.path.join(folder, "stream_map.html")):
            continue
        own = _files(folder, folder)
        version = hashlib.sha256("\n".join(f"{p} {h}" for p, _, h in own + shared).encode()).hexdigest()[:12]
        doc = dict(area=key, label=labels.get(key, key), version=version, files=own, shared=shared)
        with open(os.path.join(folder, "offline.json"), "w") as f:
            json.dump(doc, f, separators=(",", ":"))
        made.append((key, sum(x[1] for x in own), version))
    if made:
        with open(os.path.join(site, "offline.json"), "w") as f:
            json.dump(dict(root=root), f, separators=(",", ":"))
    lib_b = sum(x[1] for x in shared) + sum(x[1] for x in root)
    print(f"offline lists: {len(made)} areas; shared + root files {lib_b / 1e6:.1f} MB; " +
          ", ".join(f"{k} {b / 1e6:.1f} MB" for k, b, _ in made))
    return made


if __name__ == "__main__":
    cmd, where = (sys.argv[1:3] + [None, None])[:2]
    if cmd == "lists" and where:
        if not lists(where):
            raise SystemExit(f"weblib.py lists: no area folder in {where}")
    elif cmd == "install" and where:
        print(f"weblib.py install: {install(where)} files written in {where}")
    elif cmd == "pack" and where:
        pack(where)
    else:
        raise SystemExit("usage: weblib.py lists <site dir> | install <dir> | pack <site dir>")
