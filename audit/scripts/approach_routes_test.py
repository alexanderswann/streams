#!/usr/bin/env python3
"""Approach routes (scripts/approach_routes.py; built by 08_hike.py, packed by 06_map.py, drawn by map_routes.js): each
reach's fastest route from its trailhead to its approach point, drawn on a click. Read-only, on one build's files; per
map and range:
  network  segments numbered parents first, each one ending exactly where its parent starts; kinds 0-3; per route the
           metres of each kind (hike_route_starts.csv) are its segments' lengths
  starts   a route for every reach with an approach time and for no other; its trailhead in the 250 m square of the
           reach's th_id (08_hike.py's trailhead grid); its start within START_M of the reach's line (else counted: a
           start in a lake moves to the shore it leads to)
  lengths  the drawn route against route_km, 08_hike.py's metres along the cells (their staircase included): quantiles of
           the ratio; a ride of 1 min or more (bike_min) has a bike leg, and none without one rides far
  trails   the share of the routes' trail-or-road runs drawn within TRAIL_M of an OpenStreetMap trail or road: they are
           drawn on the line itself, not on the cells
  page     map_routes.js under jsc (JavaScriptCore, the engine of Safari on the iPhone) on routes_data.js and
           map3d_data.js: every drawn reach's route decoded; a route for each reach whose access line has one ("No route
           from an open road": none); each route's two ends are a route start and its trailhead in the network (to 1e-5
           degrees), and its popup line is the one approach_routes.route_text makes from that start's metres; and it is
           the feature's own reach's: the median distance from the route's start to the drawn line (streams layer) is
           under OWN_M (a feature drawn for another reach, a reach drawn in pieces and a start at a pond's shore start
           farther: counted, over 30 m)
  BEFORE   (optional) a folder <area>/<range>/ with 08_hike.py's outputs from before the change: hike_streams.csv,
           hike_drops.csv, hike_lakes.csv byte for byte, trailheads.gpkg row for row, hike_minutes.tif cell for cell
    BUILD=<root with scripts/, output/, data/> [BEFORE=<folder>] python audit/scripts/approach_routes_test.py [area ...]
Table: <AUDIT_TABLES>/approach_routes.csv (one row per range); exit 1 on a failed network, starts, page or BEFORE check.
"""
import json, os, subprocess, sys, tempfile
import numpy as np, pandas as pd, geopandas as gpd, shapely
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import TABLES, epsg, boxes

BUILD = os.environ.get("BUILD", "/Users/mac/Fishing")
BEFORE = os.environ.get("BEFORE")
sys.path.insert(0, f"{BUILD}/scripts")
import approach_routes as ar            # noqa: E402 (the build's own)
from units import mi                    # noqa: E402
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
START_M, TRAIL_M, OWN_M = 15.0, 3.0, 15.0

DRIVER = r"""
var D = window.MAP3D, out = {feat: [], bad: []};
["streams", "streams_lake"].forEach(function (k, lake) {
  ((D[k] || {}).features || []).forEach(function (f, i) {
    var r = approachRoute(!!lake, i), none = /^No route/.test(f.properties.acc || "");
    if (!r) { if (!none) out.bad.push([k, i, "no route"]); return; }
    if (none) out.bad.push([k, i, "a route where the access line has none"]);
    var a = r.runs.length ? r.runs[0].ll[0] : null, z = r.runs.length ? r.runs[r.runs.length - 1].ll : null;
    var n = 0; r.runs.forEach(function (u) { n += u.ll.length; if (u.k < 0 || u.k > 3) out.bad.push([k, i, "kind " + u.k]); });
    out.feat.push([lake, i, a && [Math.round(a[0] * 1e5), Math.round(a[1] * 1e5)],
                   z && [Math.round(z[z.length - 1][0] * 1e5), Math.round(z[z.length - 1][1] * 1e5)], n, r.text]);
  });
});
print(JSON.stringify(out));
"""


def page_check(area):
    """map_routes.js under jsc on the build's routes_data.js and map3d_data.js, or None (no jsc, no routes_data.js)."""
    d = f"{BUILD}/output/{area}"
    if not (os.path.exists(JSC) and os.path.exists(f"{d}/routes_data.js")):
        return None
    with tempfile.TemporaryDirectory() as t:
        open(f"{t}/pre.js", "w").write("var window = this;\n")
        open(f"{t}/drv.js", "w").write(DRIVER)
        r = subprocess.run([JSC, f"{t}/pre.js", f"{d}/map3d_data.js", f"{d}/routes_data.js",
                            f"{BUILD}/scripts/map_routes.js", f"{t}/drv.js"], capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        raise SystemExit(f"jsc failed on {area}: {r.stderr[-500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def own_line(area, feat):
    """How far each drawn reach's route starts from the reach's drawn line (the streams layer): median, p90 (m) and the
    share over 30 m."""
    s = open(f"{BUILD}/output/{area}/map3d_data.js").read()
    D = json.loads(s[s.index("{"):s.rindex("}") + 1])
    lines = gpd.GeoSeries([shapely.geometry.shape(f["geometry"]) for f in D["streams"]["features"]], crs=4326).to_crs(epsg(area))
    f = [x for x in feat if not x[0] and x[2]]
    pts = gpd.GeoSeries(gpd.points_from_xy([x[2][1] / 1e5 for x in f], [x[2][0] / 1e5 for x in f]), crs=4326).to_crs(epsg(area))
    d = shapely.distance(pts.values, lines.values[[x[1] for x in f]])
    return float(np.median(d)), float(np.quantile(d, 0.9)), float((d > 30).mean())


def before_check(area, rng):
    """08_hike.py's own outputs against the copies from before the change: the names of those that differ."""
    b, o, dv = f"{BEFORE}/{area}/{rng}", f"{BUILD}/output/{area}/{rng}", f"{BUILD}/data/derived/{area}/{rng}"
    bad = []
    for f in ("hike_streams.csv", "hike_drops.csv", "hike_lakes.csv"):
        if os.path.exists(f"{b}/{f}") and open(f"{b}/{f}", "rb").read() != open(f"{o}/{f}", "rb").read():
            bad.append(f)
    if os.path.exists(f"{b}/trailheads.gpkg"):    # (09_drive.py adds its columns to it later: those both have)
        x, y = gpd.read_file(f"{b}/trailheads.gpkg"), gpd.read_file(f"{o}/trailheads.gpkg")
        c = [k for k in x.columns if k in y.columns and k != "geometry"]
        if not ({"th_id", "n", "road"} <= set(c) and x[c].equals(y[c]) and x.geometry.equals(y.geometry)):
            bad.append("trailheads.gpkg")
    if os.path.exists(f"{b}/hike_minutes.tif"):
        import rasterio
        with rasterio.open(f"{b}/hike_minutes.tif") as x, rasterio.open(f"{dv}/hike_minutes.tif") as y:
            if x.transform != y.transform or not np.array_equal(x.read(1), y.read(1)):
                bad.append("hike_minutes.tif")
    return bad


def check_range(area, rng, ends):
    """One range's checks; ends collects (start, trailhead) in 1e-5 degrees -> popup lines, for the page check."""
    o = f"{BUILD}/output/{area}/{rng}"
    sg = gpd.read_file(f"{o}/hike_routes.gpkg").sort_values("seg").reset_index(drop=True)
    st = pd.read_csv(f"{o}/hike_route_starts.csv")
    hs = pd.read_csv(f"{o}/hike_streams.csv")
    row = dict(area=area, range=rng, segments=len(sg), starts=len(st), hard="")
    hard = []
    # network
    m, par, kind = len(sg), sg.parent.to_numpy(), sg.kind.to_numpy()
    if not (np.array_equal(sg.seg.to_numpy(), np.arange(m)) and ((par == -1) | ((par >= 0) & (par < np.arange(m)))).all()):
        hard.append("segments not numbered parents first")
    if not np.isin(kind, [0, 1, 2, 3]).all():
        hard.append("a kind outside 0-3")
    xy, ix = shapely.get_coordinates(sg.geometry.values, return_index=True)
    off = np.r_[0, np.cumsum(np.bincount(ix, minlength=m))]
    first, last = xy[off[:-1]], xy[off[1:] - 1]
    j = np.flatnonzero(par >= 0)
    gaps = int((first[par[j]] != last[j]).any(axis=1).sum())
    if gaps:
        hard.append(f"{gaps} segments do not end where their parent starts")
    root = np.arange(m)
    for s in range(m):
        if par[s] >= 0:
            root[s] = root[par[s]]
    ln = shapely.length(sg.geometry.values)
    acc = np.zeros((m, 4))
    for s in range(m):
        if par[s] >= 0:
            acc[s] = acc[par[s]]
        acc[s, kind[s]] += ln[s]
    s_ = st.seg.to_numpy()
    on = s_ >= 0
    got = np.where(on[:, None], acc[np.maximum(s_, 0)], 0)
    want = st[[f"{k}_m" for k in ar.KINDS]].to_numpy(float)
    if (np.abs(got - want) > 1.0).any():
        hard.append(f"{int((np.abs(got - want) > 1.0).any(axis=1).sum())} routes whose metres are not their segments'")
    # starts: a route for exactly the reaches with an approach time
    ss = st[st.what.eq("stream")].set_index("id")
    has = set(hs.sid[hs.approach_min.notna()])
    if set(ss.index) != has:
        hard.append(f"routes for {len(set(ss.index) - has)} reaches without an approach, none for {len(has - set(ss.index))} with one")
    hs = hs[hs.sid.isin(ss.index)].set_index("sid")
    ss = ss.loc[hs.index]
    s2 = ss.seg.to_numpy()
    ok = s2 >= 0
    th = last[root[np.maximum(s2, 0)]]
    gx = hs.th_id.str.extract(r":t(-?\d+)_(-?\d+)$").astype(float).to_numpy()
    outside = ok & ((th[:, 0] < gx[:, 0] * 250 - ar.SNAP_M) | (th[:, 0] > gx[:, 0] * 250 + 250 + ar.SNAP_M) |
                    (th[:, 1] < gx[:, 1] * 250 - ar.SNAP_M) | (th[:, 1] > gx[:, 1] * 250 + 250 + ar.SNAP_M))
    if outside.any():
        hard.append(f"{int(outside.sum())} routes end outside their reach's trailhead square")
    reach = gpd.read_file(f"{o}/streams_scored.gpkg", columns=["sid"]).to_crs(epsg(area)).set_index("sid").geometry
    a0 = shapely.points(first[np.maximum(s2, 0)])
    dist = np.where(ok, shapely.distance(a0, reach.loc[hs.index].values), 0.0)
    row.update(at_road=int((~ok).sum()), start_far=int((dist > START_M).sum()), start_far_max_m=round(float(dist.max()), 1))
    # lengths against 08_hike.py's
    tot = ss[[f"{k}_m" for k in ar.KINDS]].to_numpy(float).sum(axis=1)
    rk = hs.route_km.to_numpy(float) * 1000
    q = tot[rk > 100] / rk[rk > 100]
    row.update(ratio_p05=round(float(np.quantile(q, 0.05)), 3), ratio_p50=round(float(np.median(q)), 3),
               ratio_p95=round(float(np.quantile(q, 0.95)), 3), ratio_max=round(float(q.max()), 3))
    bm = ss.bike_m.to_numpy()
    row.update(rides_without_bike_leg=int(((hs.bike_min.to_numpy() >= 1) & (bm <= 0)).sum()),
               no_ride_bike_m_max=int(bm[hs.bike_min.to_numpy() < 0.5].max(initial=0)))
    # trail runs on the trails' own lines
    raw = f"{BUILD}/data/raw/{area}/{rng}"
    lines = pd.concat([gpd.read_file(f"{raw}/osm_trails.gpkg").geometry, gpd.read_file(f"{raw}/osm_roads.gpkg").geometry])
    tree = shapely.STRtree(ar.explode(lines.to_crs(epsg(area)).values))
    tr = sg.geometry.values[kind == 1]
    pts = [p for g in tr for p in shapely.line_interpolate_point(g, np.arange(0, g.length, 10.0))]
    if pts:
        near = tree.query(np.asarray(pts, dtype=object), predicate="dwithin", distance=TRAIL_M)[0]
        row["trail_points_on_line"] = round(len(np.unique(near)) / len(pts), 4)
    row["km_" + "_".join(ar.KINDS)] = " ".join(f"{ln[kind == k].sum() / 1000:.1f}" for k in range(4))
    # for the page check: each route's ends in 1e-5 degrees, with its popup line
    from pyproj import Transformer
    tf = Transformer.from_crs(epsg(area), 4326, always_xy=True)
    e5 = lambda p: tuple(int(v) for v in np.round(np.asarray(tf.transform(p[:, 0], p[:, 1]))[::-1].T * 1e5).ravel())
    for s, a, z, t in zip(s2[ok], first[s2[ok]], last[root[s2[ok]]],
                          ss[ok][[f"{k}_m" for k in ar.KINDS]].to_numpy(float).tolist()):
        ends.setdefault(e5(a[None]) + e5(z[None]), set()).add(ar.route_text(*t, mi))
    if BEFORE:
        b = before_check(area, rng)
        row["before"] = "same" if not b else "DIFFER: " + ", ".join(b)
        if b:
            hard.append("08_hike.py's outputs changed: " + ", ".join(b))
    row["hard"] = "; ".join(hard)
    return row


def main(areas):
    rows, fail = [], False
    for a in areas:
        ends = {}
        for r in boxes(a):
            if os.path.exists(f"{BUILD}/output/{a}/{r}/hike_routes.gpkg"):
                rows.append(check_range(a, r, ends))
                print({k: v for k, v in rows[-1].items() if v != ""})
                fail |= bool(rows[-1]["hard"])
        pg = page_check(a)
        if pg is None:
            print(f"{a}: no page check (no jsc or no routes_data.js)")
            continue
        miss = [f for f in pg["feat"] if f[2] and tuple(f[2] + f[3]) not in ends]
        badt = [f for f in pg["feat"] if f[2] and tuple(f[2] + f[3]) in ends and f[5] not in ends[tuple(f[2] + f[3])]]
        road = sum(1 for f in pg["feat"] if not f[2])
        print(f"{a}: page: {len(pg['feat']):,} drawn reaches with a route ({road} by the road), {len(pg['bad'])} wrong "
              f"on the access line, {len(miss)} whose ends are no route's, {len(badt)} with another popup line")
        for b in (pg["bad"] + miss + badt)[:5]:
            print("   ", b)
        own = own_line(a, pg["feat"])
        print(f"{a}: route start to its own drawn line: median {own[0]:.1f} m, p90 {own[1]:.1f} m, over 30 m {own[2]:.1%}")
        fail |= bool(pg["bad"] or miss or badt) or not own[0] < OWN_M
        for r_ in rows:
            if r_["area"] == a:
                r_.update(page_routes=len(pg["feat"]), page_bad=len(pg["bad"]) + len(miss) + len(badt),
                          own_line_median_m=round(own[0], 1), own_line_p90_m=round(own[1], 1), own_line_over_30m=round(own[2], 4))
    if rows:
        pd.DataFrame(rows).to_csv(f"{TABLES}/approach_routes.csv", index=False)
    print("FAIL" if fail else "PASS", f"({len(rows)} ranges; table {TABLES}/approach_routes.csv)")
    return 1 if fail else 0


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(a for a in os.listdir(f"{BUILD}/output") if os.path.exists(f"{BUILD}/output/{a}/routes_data.js"))
    sys.exit(main(names))
