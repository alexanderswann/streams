"""Which code made each map, and the publish gate (the new-area plan's B9; the audit's finding 10; 2026-11-23).

Every pipeline step stamps itself. config.py calls start() when a step imports it, and the record is written when the
step ends, into output/<area>/build_stamp.json, keyed "<step>/<box>" ("<step>/all" for a step run for the whole
area). It keeps each step and box's latest run:
  started, ended    the run's times (epoch seconds; and as local time, for reading)
  status            "ended"; "failed" when it ended on an error it didn't catch, or when a driver saw it fail (a step
                    that stops itself with SystemExit is seen failing only by the drivers, which mark it)
  commit            the commit the project was at when the step started (git HEAD); None without git
  code              {file: git blob id} of every file in scripts/ the step loads (its local imports, followed, and
                    the page templates and other scripts/ files it names), as they were on disk when it started
  uncommitted       those that differed from that commit or weren't in it
  edited_during     those whose content changed on disk while it ran (a module a step imports late is read then)
  wrote             {path under output/<area>/: [mtime_ns, size]} of the files it wrote there
  changed_data      True when it wrote anything under data/raw/<area>, data/derived/<area> or output/<area>
Nothing here changes what a step makes, and a record that can't be written is a NOTE, never a failed step.
BUILD_STAMP=off leaves stamps out (a build made so can't be published: the gate finds no record of its files).

    python build_stamp.py show <area>                     the latest runs, in the drivers' order
    python build_stamp.py steps                           every step the drivers run, in order (run_area.sh)
    python build_stamp.py failed <area> <box|all> <step>  (the drivers) the run of that step that just ended failed
    git diff --cached --name-only -- docs | python build_stamp.py gate      (publish_site.sh)

The gate reads the site files a publish changes (docs/<area>/<file>, one a line) and refuses it (exit 1, one line per
reason) when, for an area with a changed file:
  1. a changed map file was not written by a recorded step run (a run killed midway, a copy by hand, a build from
     before the stamps, a build with BUILD_STAMP=off);
  2. the run that wrote it failed, or ran on uncommitted code, or its code was edited while it ran;
  3. a step that comes before the writer in the drivers' order changed data after the writer started (for a map file
     no run is recorded for, after the file was written): the map would not show it (profiles older than the map,
     a reach step run again after the map was drawn);
  4. one step ran on different code in two of the area's boxes;
  5. the latest run of a step failed, other than those the drivers let a map be made without (05d_lakes,
     lake_bathymetry, 07_road_closures, watertemp, 11b_calendar: a NOTE in the log then);
  6. the standing checks have not passed on this map: no audit/tables/*/run_all_status.json (audit/scripts/run_all.sh
     writes it) holds this map3d_data.js's sha1 with no check script failed and no golden place broken.
docs/index.html and docs/credits.html (13_overview.py, run by the publish itself) need 13_overview's code committed,
and the web app's files (docs/sw.js, offline.js, manifest.webmanifest, lib/, icons/ and the offline.json lists, from
weblib.py at the publish) need scripts/web/ and weblib.py committed; lib/ and icons/ are not areas.
It also lists, without refusing: steps whose code has changed since in the newest commit the area was built on (a
rebuild from a later step leaves them as they were, the publisher's call), and the commit each area was built on.
"""
import ast, atexit, fcntl, glob, hashlib, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SCR = f"{ROOT}/scripts"
STEP_RE = re.compile(r"^([0-9]{2}[a-z]?_[a-z0-9_]+|watertemp|lake_bathymetry|fish_score_diagram)\.py$")
SITE_STEPS = {"13_overview", "14_portable", "15_preview"}       # the site's pages, not an area's step
TOLERATED = {"05d_lakes", "lake_bathymetry", "07_road_closures", "watertemp",
             "11b_calendar"}                          # the drivers go on without them
PUBLISHED = {"map3d_data.js": "06_map", "stream_map.html": "06_map", "stream_map_3d.html": "06_map",
             "routes_data.js": "06_map",                         # approach_routes.pack(), beside each map
             "profiles_data.js": "12_profiles", "hillshade.png": "05_score"}    # publish_site.sh's map files: the step
SKIP_IN_SITE = {"build_stamp.json", "profiles.html"}      # the stamp itself; the page template (scripts/profiles.html)
WEB_TOP = {"sw.js", "offline.js", "manifest.webmanifest", "offline.json"}   # the web app at the site's root (weblib.py)
WEB_DIRS = {"lib", "icons"}                               # the pages' libraries and the app's icons (weblib.py), not areas


# ---- the code a step loads ----
_parsed = {}


def _deps(mod, seen):
    path = f"{SCR}/{mod}.py"
    if mod in seen or not os.path.exists(path):
        return
    seen.add(mod)
    if path not in _parsed:
        text = open(path, errors="replace").read()
        names = set()
        try:
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Import):
                    names.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names.add(node.module.split(".")[0])
        except SyntaxError:
            pass
        # modules loaded by name ("05c_drainages" can't be imported by a statement) and files read from scripts/
        names.update(re.findall(r"""['"/]((?:\d\d[a-z]?_)?[a-z_0-9]+)\.py['"]""", text))
        names.update(re.findall(r"""import_module\(\s*['"]([a-z_0-9]+)['"]""", text))
        files = set(re.findall(r"""([A-Za-z0-9_.-]+\.(?:js|css|html|json|csv))""", text))
        _parsed[path] = (names, files)
    names, _ = _parsed[path]
    for n in names:
        _deps(n, seen)


def closure(step):
    """The files in scripts/ (relative to the project) that <step>.py loads: .py modules and the other files it names."""
    seen = set()
    _deps(step, seen)
    out = {f"scripts/{m}.py" for m in seen}
    present = set(os.listdir(SCR))
    for m in seen:
        for f in _parsed.get(f"{SCR}/{m}.py", (set(), set()))[1]:
            if f in present and not f.endswith(".py") and os.path.isfile(f"{SCR}/{f}"):
                out.add(f"scripts/{f}")
    return sorted(out)


def _git(*args, inp=None):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], input=inp, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def code_state(files):
    """(commit, {file: blob id on disk}, [files that differ from the commit or aren't in it])."""
    blobs = _git("hash-object", "--stdin-paths", inp="\n".join(f"{ROOT}/{f}" for f in files) + "\n")
    disk = dict(zip(files, blobs.split())) if blobs else {}
    head = (_git("rev-parse", "HEAD") or "").strip() or None
    if head is None:
        return None, disk, None
    tree = {}
    for line in (_git("ls-tree", "HEAD", "--", *files) or "").splitlines():
        meta, path = line.split("\t", 1)
        tree[path] = meta.split()[2]
    return head, disk, sorted(f for f in files if disk.get(f) != tree.get(f))


# ---- the record a step writes ----
def _scan(top, since_ns):
    """{path under top: [mtime_ns, size]} for the files changed since since_ns."""
    out = {}
    for d, _, fs in os.walk(top):
        for f in fs:
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime_ns >= since_ns:
                out[os.path.relpath(p, top)] = [st.st_mtime_ns, st.st_size]
    return out


def _stamp_path(area):
    return f"{ROOT}/output/{area}/build_stamp.json"


def _update(area, fn):
    """Read, change (fn(stamp)) and write output/<area>/build_stamp.json under a lock."""
    lock = f"{ROOT}/data/derived/{area}/_shared/.build_stamp.lock"
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    os.makedirs(os.path.dirname(_stamp_path(area)), exist_ok=True)
    with open(lock, "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        p = _stamp_path(area)
        try:
            with open(p) as f:
                stamp = json.load(f)
        except (FileNotFoundError, ValueError):
            stamp = {"area": area, "runs": {}}
        fn(stamp)
        with open(p + ".tmp", "w") as f:
            json.dump(stamp, f, indent=1, sort_keys=True)
        os.replace(p + ".tmp", p)


def _local(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def start(area, region):
    """Called by config.py: stamp this process if it is a pipeline step run as a script. Never raises."""
    try:
        main = sys.modules.get("__main__")
        path = os.path.realpath(getattr(main, "__file__", "") or "")
        name = os.path.basename(path)
        if (os.environ.get("BUILD_STAMP") == "off" or os.path.dirname(path) != SCR or not STEP_RE.match(name)
                or name[:-3] in SITE_STEPS):
            return
        step = name[:-3]
        t0, t0_ns = time.time(), time.time_ns()
        files = closure(step)
        commit, code, dirty = code_state(files)
        mtimes = {f: os.stat(f"{ROOT}/{f}").st_mtime_ns for f in files if os.path.exists(f"{ROOT}/{f}")}
        rec = dict(step=step, box=region or "all", started=t0, started_at=_local(t0), status="ended", commit=commit,
                   code=code, uncommitted=dirty, pid=os.getpid())
        prev_hook = sys.excepthook

        def hook(*exc):
            rec["status"] = "failed"
            prev_hook(*exc)
        sys.excepthook = hook

        def finish():
            try:
                t1 = time.time()
                rec.update(ended=t1, ended_at=_local(t1))
                touched = [f for f, m in mtimes.items()
                           if not os.path.exists(f"{ROOT}/{f}") or os.stat(f"{ROOT}/{f}").st_mtime_ns != m]
                now = code_state(touched)[1] if touched else {}
                rec["edited_during"] = sorted(f for f in touched if now.get(f) != code.get(f))
                rec["wrote"] = _scan(f"{ROOT}/output/{area}", t0_ns)
                rec["wrote"].pop("build_stamp.json", None)
                rec["changed_data"] = bool(rec["wrote"]) or any(
                    _scan(f"{ROOT}/data/{k}/{area}", t0_ns) for k in ("raw", "derived"))
                _update(area, lambda s: s["runs"].__setitem__(f"{step}/{rec['box']}", rec))
            except Exception as e:                                         # never the step's failure
                print(f"NOTE build_stamp: {step} not recorded ({type(e).__name__}: {str(e)[:120]})", file=sys.stderr)
        atexit.register(finish)
    except Exception as e:
        print(f"NOTE build_stamp: not started ({type(e).__name__}: {str(e)[:120]})", file=sys.stderr)


# ---- reading the records ----
def pipeline():
    """Every step the drivers run, in their order (run_base, run_mid, run_late; a step run twice counts where it last
    runs), read from the drivers themselves."""
    names = {f[:-3] for f in os.listdir(SCR) if STEP_RE.match(f)} - SITE_STEPS
    order = []
    for d in ("run_base.sh", "run_mid.sh", "run_late.sh"):
        text = re.sub(r"NET_STEPS=\([^)]*\)", "", open(f"{SCR}/{d}").read())
        text = "\n".join(re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines())
        for t in re.findall(r"[0-9a-z_]+", text):
            if t in names:
                if t in order:
                    order.remove(t)
                order.append(t)
    return order


def load(area):
    try:
        with open(_stamp_path(area)) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"area": area, "runs": {}}


def show(area):
    order = pipeline()
    runs = load(area)["runs"]
    rank = {s: i for i, s in enumerate(order)}
    for key, r in sorted(runs.items(), key=lambda kv: (rank.get(kv[1]["step"], 999), kv[1]["started"])):
        flags = [r["status"]] + (["uncommitted: " + ", ".join(r["uncommitted"])] if r.get("uncommitted") else []) + \
                (["edited during: " + ", ".join(r["edited_during"])] if r.get("edited_during") else [])
        print(f"{key:34s} {r['started_at']} -> {r.get('ended_at', '?')[11:]}  {(r.get('commit') or 'no git')[:9]}  "
              f"{len(r.get('wrote', {})):3d} map files  {'; '.join(flags)}")


def mark_failed(area, box, step):
    def fn(s):
        r = s["runs"].get(f"{step}/{box}")
        if r:
            r["status"] = "failed"
    _update(area, fn)


def _checks_status():
    """Every run_all_status.json under audit/tables/, newest first."""
    out = []
    for p in glob.glob(f"{ROOT}/audit/tables/*/run_all_status.json"):
        try:
            with open(p) as f:
                d = json.load(f)
            d["_path"] = os.path.relpath(p, ROOT)
            out.append(d)
        except (OSError, ValueError):
            pass
    return sorted(out, key=lambda d: d.get("finished", ""), reverse=True)


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def gate(paths):
    order = pipeline()
    rank = {s: i for i, s in enumerate(order)}
    refuse, notes = [], []
    by_area, web = {}, []
    for p in paths:
        parts = p.strip().split("/")
        if len(parts) < 2 or parts[0] != "docs":
            continue
        if parts[1] in WEB_DIRS or parts[-1] == "offline.json" or (len(parts) == 2 and parts[1] in WEB_TOP):
            web.append("/".join(parts[1:]))                   # the web app's files and lists (weblib.py)
            continue
        if len(parts) == 2:                                   # docs/index.html, docs/credits.html, docs/preview.jpg
            if parts[1] in ("index.html", "credits.html"):    # 13_overview.py's pages (credits.html by credits.py)
                commit, _, dirty = code_state(closure("13_overview"))
                if dirty:
                    refuse.append(f"{parts[1]}: 13_overview.py's code has uncommitted changes ({', '.join(dirty)})")
            continue
        by_area.setdefault(parts[1], []).append("/".join(parts[2:]))
    if web:                                                   # as 13_overview's pages: their code committed
        code = sorted({"scripts/weblib.py"} | {os.path.relpath(os.path.join(d, f), ROOT)
                                               for d, _, fs in os.walk(f"{SCR}/web") for f in fs})
        _, _, dirty = code_state(code)
        if dirty:
            refuse.append(f"the web app ({len(web)} file(s): {', '.join(web[:3])}{' ...' if len(web) > 3 else ''}): its "
                          f"code has uncommitted changes ({', '.join(dirty[:6])}{' ...' if len(dirty) > 6 else ''})")
    statuses = _checks_status()
    for area, files in sorted(by_area.items()):
        out = f"{ROOT}/output/{area}"
        runs = load(area)["runs"]
        latest_change = {}                                    # step -> the latest end of a run that changed data
        for r in runs.values():
            if r.get("changed_data") and "ended" in r:
                latest_change[r["step"]] = max(latest_change.get(r["step"], 0), r["ended"])

        def stale(step, since):
            i = rank.get(step)
            if i is None:
                return []
            return [s for s, t in latest_change.items() if rank.get(s, 999) < i and t > since]

        # every map file of the area: changed ones need a clean recorded run; all must be newer than their inputs
        published = [f for f in (os.path.relpath(q, out) for q in glob.glob(f"{out}/*") + glob.glob(f"{out}/*/*"))
                     if os.path.basename(f) in PUBLISHED]
        for f in sorted(set(published) | {x for x in files if os.path.basename(x) in PUBLISHED}):
            path = f"{out}/{f}"
            if not os.path.exists(path):
                continue
            st = os.stat(path)
            rec = next((r for r in runs.values() if r.get("wrote", {}).get(f) == [st.st_mtime_ns, st.st_size]), None)
            writer = rec["step"] if rec else PUBLISHED[os.path.basename(f)]
            if f in files:
                if rec is None:
                    refuse.append(f"{area}/{f}: not written by a recorded step run (killed midway, copied by hand, "
                                  f"or built before the stamps): rebuild it from {writer}")
                    continue
                if rec["status"] == "failed":
                    refuse.append(f"{area}/{f}: written by a run of {writer} that failed ({rec['started_at']})")
                if rec.get("uncommitted") is None:
                    refuse.append(f"{area}/{f}: {writer} ran without git: its code can't be named")
                elif rec["uncommitted"]:
                    refuse.append(f"{area}/{f}: {writer} ran on uncommitted code: {', '.join(rec['uncommitted'])}")
                if rec.get("edited_during"):
                    refuse.append(f"{area}/{f}: code edited while {writer} ran: {', '.join(rec['edited_during'])}")
            since = rec["started"] if rec else st.st_mtime
            late = stale(writer, since)
            if late:
                refuse.append(f"{area}/{f}: {', '.join(sorted(late, key=rank.get))} changed data after {writer} "
                              f"{'started' if rec else 'wrote it'}: rebuild from {min(late, key=rank.get)}")
        # one step, one code state across the boxes
        per_step = {}
        for r in runs.values():
            per_step.setdefault(r["step"], []).append(r)
        for step, rs in per_step.items():
            if len(rs) > 1:
                mixed = sorted({f for a in rs for b in rs for f in set(a.get("code", {})) & set(b.get("code", {}))
                                if a["code"][f] != b["code"][f]})
                if mixed:
                    refuse.append(f"{area}: {step} ran on two versions of {', '.join(mixed)} in its boxes "
                                  f"({', '.join(sorted(r['box'] for r in rs))})")
        for key, r in sorted(runs.items()):
            if r["status"] == "failed":
                (notes if r["step"] in TOLERATED else refuse).append(
                    f"{area}: the latest run of {key} failed ({r['started_at']})"
                    + (": the map was made without its fresh data" if r["step"] in TOLERATED else ""))
        # the standing checks on this very map
        m3d = f"{out}/map3d_data.js"
        if os.path.exists(m3d):
            sha = _sha1(m3d)
            st_ = next((d for d in statuses if d.get("areas", {}).get(area) == sha), None)
            if st_ is None:
                refuse.append(f"{area}: the standing checks haven't run on this map (audit/scripts/run_all.sh "
                              f"<label> output output)")
            else:
                bad = list(st_.get("failed", [])) + [f"golden: {g}" for g in st_.get("golden", {}).get("failed", [])]
                if bad:
                    refuse.append(f"{area}: the standing checks failed ({st_['_path']}): {'; '.join(bad)}")
        # reported only: code changed since, in the newest commit the area was built on
        if runs:
            newest = max(runs.values(), key=lambda r: r["started"]).get("commit")
            if newest:
                older = {}
                for r in runs.values():
                    if r.get("commit") and r["commit"] != newest:
                        now = {}
                        for line in (_git("ls-tree", newest, "--", *r.get("code", {})) or "").splitlines():
                            meta, pth = line.split("\t", 1)
                            now[pth] = meta.split()[2]
                        ch = sorted(f for f, b in r.get("code", {}).items() if now.get(f) != b)
                        if ch:
                            older.setdefault(r["step"], set()).update(ch)
                groups = {}
                for step, ch in sorted(older.items(), key=lambda kv: rank.get(kv[0], 999)):
                    groups.setdefault(tuple(sorted(ch)), []).append(step)
                for ch, steps in groups.items():
                    notes.append(f"{area}: {len(steps)} step(s) built before {newest[:9]}, whose {', '.join(ch)} "
                                 f"differ: {', '.join(steps)} (a rebuild from a later step leaves them as they were)")
                notes.append(f"{area}: built on {newest[:9]}")
    for n in notes:
        print(f"note: {n}")
    for r in refuse:
        print(f"REFUSED: {r}")
    print(f"build gate: {len(by_area)} area(s) checked, " + ("passed" if not refuse else f"{len(refuse)} reason(s) to refuse"))
    return 0 if not refuse else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["show"] and len(a) == 2:
        show(a[1])
    elif a == ["steps"]:
        print(" ".join(pipeline()))
    elif a[:1] == ["failed"] and len(a) == 4:
        mark_failed(a[1], a[2], a[3])
    elif a[:1] == ["gate"]:
        sys.exit(gate([line for line in sys.stdin.read().splitlines() if line.strip()]))
    else:
        raise SystemExit(__doc__)
