#!/usr/bin/env python3
"""The fish score's breakdown in the stream popups against the score shown, on every drawn reach of every map.

Each reach carries fx (06_map.py fs_parts): the terms scoring.score() combines. The popups (scripts/map_score.js)
multiply them out as score() does and show each one's points; this recomputes every reach's score from its fx two ways
and compares it with the fs the map shows:
  python  an implementation of its own here, from score()'s formula (README "Fish score")
  page    scripts/map_score.js itself, run by macOS's JavaScriptCore (jsc, the engine of Safari on the iPhone) on each
          map's map3d_data.js; it also builds every reach's popup line, so a breakdown that throws is caught too
A mismatch is a reach whose rebuilt score, rounded (a half to the even number, as numpy rounds), isn't fs; a reach
drawn without fx is counted apart. Table: <AUDIT_TABLES>/fish_breakdown.csv (one row per map), and the mismatches,
if any, in fish_breakdown_mismatches.csv.
    SITE_DIR=<folder with <area>/map3d_data.js> python audit/scripts/fish_breakdown_check.py [area ...]
"""
import csv, json, os, subprocess, sys, tempfile

ROOT = "/Users/mac/Fishing"
SITE_DIR = os.environ.get("SITE_DIR", f"{ROOT}/publish/streams-site/docs")
TABLES = os.environ.get("AUDIT_TABLES", f"{ROOT}/audit/tables")
SCORE_JS = os.environ.get("SCORE_JS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts",
                                                   "map_score.js"))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
clip = lambda v: min(max(v, 0.0), 1.0)


def rebuilt(p):
    """The score from fx, as scoring.score() computes it (same operations, same order); None without fx."""
    fx = p.get("fx")
    if not isinstance(fx, str) or p.get("gr") is None:
        return None
    t = fx.split(" ")
    val = lambda v, fill: fill if v == "-" else float(v)
    W, S, wt, cp, sp, am, bm = float(t[0]), float(t[1]), val(t[2], None), val(t[3], 0.0), val(t[4], 20.0), val(t[6], 0.0), val(t[7], 0.0)
    nn, gr = (0.0 if t[5] == "-" else int(t[5]) / 100), float(p["gr"])
    B = H = T = CH = K = 1.0
    C, tw = None, False
    for k in t[8:]:
        if k == "t": T = 1.2
        elif k == "c": CH = 0.2
        elif k == "x": K = 0.5
        elif k == "w": tw = True
        elif k[0] == "B": B = float(k[1:])
        elif k[0] == "H": H = float(k[1:])
        elif k[0] == "C": C = float(k[1:])
        elif k[0] == "G": gr = float(k[1:])
        elif k[0] == "N": nn = float(k[1:])
    shade = clip((1 - (1 - sp / 100) * (1 - 0.8 * clip(cp / 100))) / 0.45)
    north = clip((nn + 0.15) / 0.30)
    c1 = C if C is not None else 1.0 if tw else clip((25 - wt) / 5)
    thermal = 0.5 * c1 + 0.35 * shade + 0.15 * north
    grad = clip(1 - max(max(1 - gr, gr - 8), 0.0) / 10)
    remote = clip((am + bm) / 120)
    x = 100 * W * (0.30 * S + 0.30 * thermal + 0.15 * grad + 0.25 * remote) * B * T * H * CH * K
    return min(max(x, 0.0), 100.0)


DRIVER = r"""
var D = window.MAP3D, out = {n: 0, nofx: 0, bad: [], ties: 0, capped: 0, rows: 0};
["streams", "streams_lake"].forEach(function (k) {
  ((D[k] || {}).features || []).forEach(function (f, i) {
    var p = f.properties; out.n++;
    var r = fsParts(p);
    if (!r) { out.nofx++; return; }
    if (fsRow(p).indexOf("fsb") < 0) out.bad.push([k, i, p.fs, "no breakdown drawn"]);
    out.rows++;
    if (r.score !== p.fs) out.bad.push([k, i, p.fs, r.score, r.x]);
    if (r.x * 2 === Math.round(r.x * 2) && r.x % 1 !== 0) out.ties++;
    if (r.raw > 100) out.capped++;
  });
});
print(JSON.stringify(out));
"""


def page_check(path):
    """map_score.js under jsc on one map3d_data.js: counts and mismatches, or None where jsc isn't there."""
    if not os.path.exists(JSC):
        return None
    with tempfile.TemporaryDirectory() as d:
        open(f"{d}/pre.js", "w").write("var window = this;\n")
        open(f"{d}/drv.js", "w").write(DRIVER)
        r = subprocess.run([JSC, f"{d}/pre.js", path, SCORE_JS, f"{d}/drv.js"], capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        raise SystemExit(f"jsc failed on {path}: {r.stderr[-500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main(areas):
    os.makedirs(TABLES, exist_ok=True)
    rows, bad = [], []
    for a in areas:
        path = f"{SITE_DIR}/{a}/map3d_data.js"
        if not os.path.exists(path):
            continue
        s = open(path).read()
        d = json.loads(s[s.index("{"):s.rindex("}") + 1])
        n = nofx = mis = ties = capped = 0
        size = 0
        for k in ("streams", "streams_lake"):
            for i, f in enumerate((d.get(k) or {}).get("features", [])):
                p = f["properties"]
                n += 1
                x = rebuilt(p)
                if x is None:
                    nofx += 1
                    continue
                size += len(json.dumps(p["fx"])) + len(',"fx":')
                if round(x) != p["fs"]:
                    mis += 1
                    bad.append(dict(area=a, layer=k, i=i, name=p.get("n"), fs=p["fs"], rebuilt=round(x, 4), fx=p["fx"], how="python"))
                ties += x * 2 == round(x * 2) and x % 1 != 0
                capped += x >= 100
        pg = page_check(path)
        if pg:
            for b in pg["bad"]:
                bad.append(dict(area=a, layer=b[0], i=b[1], name=None, fs=b[2], rebuilt=b[3] if len(b) > 3 else None,
                                fx=None, how="page"))
        rows.append(dict(area=a, reaches=n, without_fx=nofx, mismatch_python=mis,
                         mismatch_page="" if pg is None else len(pg["bad"]), exact_halves=ties, at_cap=capped,
                         fx_mb=round(size / 1e6, 3)))
        print(f"{a:16s} {n:6d} drawn reaches, {nofx} without fx; mismatches: python {mis}, page "
              f"{'(no jsc)' if pg is None else len(pg['bad'])}; exact halves {ties}; at the cap {capped}; fx {size / 1e6:.2f} MB")
    with open(f"{TABLES}/fish_breakdown.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["area"])
        w.writeheader()
        w.writerows(rows)
    if bad:
        with open(f"{TABLES}/fish_breakdown_mismatches.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(bad[0]))
            w.writeheader()
            w.writerows(bad)
    tot = lambda c: sum(r[c] for r in rows if r[c] != "")
    print(f"ALL {tot('reaches')} drawn reaches on {len(rows)} maps; without fx {tot('without_fx')}; mismatches python "
          f"{tot('mismatch_python')}, page {tot('mismatch_page')}; fx {tot('fx_mb'):.2f} MB")
    return 1 if bad or tot("without_fx") else 0


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(a for a in os.listdir(SITE_DIR) if os.path.exists(f"{SITE_DIR}/{a}/map3d_data.js"))
    sys.exit(main(names))
