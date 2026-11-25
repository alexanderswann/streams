"""Promote a tested build into the project instead of building it again (build-speed, 2026-11-24).

A batch is tested on a clone of a baseline (baseline.sh clone <X> <root>; the test's steps run there, downloads offline
with NET_FAIL=1). Once the test has passed and the very same patches are on main, a project rebuild from the same step
would remake what the clone holds: same code, same inputs (the project is still baseline X), same last good copies.
This puts the clone's built files into the project as APFS clones (no data copied) instead: seconds, not 75-100 minutes
on both build slots. Run by the overview session only, like baseline.sh make, through run_promote.sh (a run_*.sh name,
so publish_site.sh's build guard, which is not touched, sees a promotion under way as a build).

  promote.py check   <clone> <baseline> [--maps M ...] [--allow GLOB ...]   the checks below; exit 1 when one fails
  promote.py promote <clone> <baseline> --label L [--maps M ...] [--allow GLOB ...] [--dry-run]
  promote.py undo    <label>                      the project back as it was before promote L (exact files, by rename)
  promote.py forget  <label>                      once L is published and checked: drop its undo folder (the replaced
                                                  files; they share their blocks with baseline X while X is kept)
  promote.py asof    <clone> [--maps M ...] [--log FILE ...]   what the clone's maps took from a saved copy, of when
  promote.py gitlink <clone> <commit>             (for B9's build stamps, before the test runs) make the clone's root a
                                                  git work tree at <commit>, reading the project's objects (nothing is
                                                  written there), so each step's stamp names that commit
Options for tests: --project DIR (default /Users/mac/Fishing), --baselines DIR (where baseline X is read; default
<project>/baselines). The undo folder is always under --project's own baselines/ (git-ignored, the same disk).

The checks (all must pass):
  code   the clone's scripts/ are main's committed scripts/ (git archive HEAD), byte for byte, and so are the tracked
         files under output/ (the profile pages); the project's scripts/ have no uncommitted change
  state  the project's data/ and output/ are still baseline X: the same paths, each the same size and mtime to the
         nanosecond (cp -c keeps mtimes, and every pipeline write sets a new one), so nothing was built, installed or
         copied in since X was made. A path that differs where the project already holds the clone's file byte for
         byte (a tracked page the install changed) is fine; --allow GLOB keeps a known difference (listed)
  idle   no pipeline step or driver runs in the project or in the clone, the project's hydro lock is free, and no
         project build holds a build slot
  built  every map promoted was rebuilt in the clone (its map3d_data.js is newer than the clone), and no step failed in
         the clone's logs since the clone was made, other than those the drivers go on without (05d_lakes,
         lake_bathymetry, 07_road_closures, watertemp, 11b_calendar: listed)
  stamps (with build_stamp.py in scripts/: B9) each published map file was written by a clean recorded run that names a
         commit, with no uncommitted or edited code; else publish_site.sh's build gate would refuse it. A clone tested
         without `gitlink` fails here: test again on a git-linked clone, or rebuild as before
promote then moves every project file it replaces or deletes into <project>/baselines/.promote_undo/<label>/ (a
rename: instant, same disk; baseline.sh's lists skip dot folders), clones the clone's files in, checks that data/ and output/ now equal the clone's, and logs one line to
data/promoted.log. The as-of report (also printed by promote) lists the saved copies the clone's offline steps read:
they stay as of their dates unless run_refresh_late.sh brings the late steps up to date first (build-speed.md).
"""
import argparse, ctypes, ctypes.util, fnmatch, json, os, re, shlex, subprocess, sys, tempfile, time, filecmp, shutil
from collections import defaultdict

PROJECT = "/Users/mac/Fishing"
TOPS = ("data", "output")
EXCLUDE = [re.compile(p) for p in (r"^data/\.hydro\.lock(/|$)", r"(^|/)__pycache__(/|$)", r"\.pyc$",
                                   r"(^|/)\.DS_Store$", r"(^|/)\.build_stamp\.lock$", r"^data/promoted\.log$")]
TOLERATED = {"05d_lakes", "lake_bathymetry", "07_road_closures", "watertemp", "11b_calendar"}   # the drivers' NOTEs
STEP_PAT = r"run_[a-z_]+\.sh|[0-9][0-9][a-z]?_[a-z_]+\.py|watertemp\.py|lake_bathymetry\.py|fish_score_diagram\.py"
PUBLISHED = {"map3d_data.js", "stream_map.html", "stream_map_3d.html", "profiles_data.js", "hillshade.png"}
SLOTS = os.environ.get("BUILDSLOT_DIR", "/private/tmp/fishing-build-slots")


def say(*a):
    print(*a, flush=True)


def excluded(rel):
    return any(p.search(rel) for p in EXCLUDE)


def manifest(root):
    """{path under root: (kind, size, mtime_ns, link target)} for every file and symbolic link in data/ and output/."""
    out = {}
    for top in TOPS:
        base = os.path.join(root, top)
        for d, dirs, files in os.walk(base):
            for name in dirs + files:
                p = os.path.join(d, name)
                rel = os.path.relpath(p, root)
                if excluded(rel):
                    continue
                st = os.lstat(p)
                if os.path.islink(p):
                    out[rel] = ("link", 0, 0, os.readlink(p))
                elif name in files:
                    out[rel] = ("file", st.st_size, st.st_mtime_ns, "")
            dirs[:] = [x for x in dirs if not os.path.islink(os.path.join(d, x))
                       and not excluded(os.path.relpath(os.path.join(d, x), root))]
    return out


def diff(a, b):
    """(only in a, only in b, in both but different), sorted."""
    return (sorted(set(a) - set(b)), sorted(set(b) - set(a)), sorted(k for k in set(a) & set(b) if a[k] != b[k]))


def same_content(p, q):
    """Two paths hold the same thing: both missing, the same link, or two files with the same bytes."""
    if not os.path.lexists(p) or not os.path.lexists(q):
        return not os.path.lexists(p) and not os.path.lexists(q)
    if os.path.islink(p) or os.path.islink(q):
        return os.path.islink(p) and os.path.islink(q) and os.readlink(p) == os.readlink(q)
    return filecmp.cmp(p, q, shallow=False)


def git(*args, cwd=None, check=True):
    # --no-optional-locks: `git status` must not refresh (write) the project's index while other sessions use git there
    r = subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def clone_time(clone):
    """When the clone was made: the birth time of its folders (cp -c -R makes them; their files keep older mtimes)."""
    return min(os.stat(os.path.join(clone, d)).st_birthtime for d in ("scripts",) + TOPS)


def undo_dir(project, label):
    """Where promote L puts the project files it replaces: under the project's own baselines/ (git-ignored; renames
    stay on its disk), whatever --baselines says (a test may read the project's baselines but promote into a clone)."""
    return os.path.join(os.path.abspath(project), "baselines", ".promote_undo", label)


def log_line(project, text):
    with open(os.path.join(project, "data", "promoted.log"), "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")


def area_of(rel):
    m = re.match(r"(?:output|data/raw|data/derived)/([a-z_0-9]+)/", rel)
    return m.group(1) if m else None


# ---- the checks ----
class Checks:
    def __init__(self, a):
        self.a, self.fail, self.notes = a, [], []
        # real paths: the idle check compares them with lsof's cwd, which names /private/tmp, not /tmp
        self.project = os.path.realpath(a.project)
        self.clone = os.path.realpath(a.clone)
        self.base = os.path.join(a.baselines or os.path.join(self.project, "baselines"), a.baseline)

    def bad(self, msg):
        self.fail.append(msg)
        say(f"  FAIL {msg}")

    def note(self, msg):
        self.notes.append(msg)
        say(f"  note {msg}")

    def run(self):
        say(f"promote check: clone {self.clone}\n  baseline {self.base}\n  project {self.project}")
        for d in ("scripts",) + TOPS:
            if not os.path.isdir(os.path.join(self.clone, d)):
                raise SystemExit(f"STOP: {self.clone} has no {d}/: not a scratch root")
        if not os.path.isfile(os.path.join(self.base, "BASELINE.txt")):
            raise SystemExit(f"STOP: no baseline {self.base} (baseline.sh list)")
        first = open(os.path.join(self.clone, "BASELINE.txt")).readline().split() if os.path.exists(
            os.path.join(self.clone, "BASELINE.txt")) else []
        if first[:2] != ["baseline", self.a.baseline]:
            self.bad(f"the clone's BASELINE.txt names {' '.join(first[:2]) or 'nothing'}, not baseline {self.a.baseline}")
        self.made = clone_time(self.clone)
        say(f"  clone made {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.made))}")
        self.code()
        self.idle()
        self.state()
        self.built()
        self.stamps()
        say(f"promote check: {'PASS' if not self.fail else f'FAIL ({len(self.fail)})'}")
        return not self.fail

    def code(self):
        say("code: the clone's scripts/ against main's committed tree")
        head = git("rev-parse", "HEAD", cwd=self.project).strip()
        self.head = head
        dirty = git("status", "--porcelain", "--untracked-files=all", "--", "scripts", "output", cwd=self.project)
        dirty = [l for l in dirty.splitlines() if not re.search(r"__pycache__|\.pyc$", l)]
        if dirty:
            self.bad(f"the project's scripts/ or tracked output/ have uncommitted changes: {'; '.join(dirty[:5])}")
        with tempfile.TemporaryDirectory(prefix="promote") as w:
            tracked_out = [p for p in git("ls-files", "output", cwd=self.project).splitlines()]
            subprocess.run(f"git --no-optional-locks -C {shlex.quote(self.project)} archive HEAD scripts "
                           f"{' '.join(map(shlex.quote, tracked_out))} | tar -x -C {shlex.quote(w)}",
                           shell=True, check=True)
            r = subprocess.run(["diff", "-rq", "-x", "__pycache__", "-x", "*.pyc", "-x", ".DS_Store",
                                os.path.join(w, "scripts"), os.path.join(self.clone, "scripts")],
                               capture_output=True, text=True)
            lines = [l.replace(w + "/", "main:").replace(self.clone + "/", "clone:") for l in r.stdout.splitlines()]
            for p in tracked_out:
                if not same_content(os.path.join(w, p), os.path.join(self.clone, p)):
                    lines.append(f"tracked {p} differs from main's")
        if lines:
            self.bad(f"the clone's code is not main's {head[:9]}: " + "; ".join(lines[:6])
                     + (f" (+{len(lines) - 6} more)" if len(lines) > 6 else ""))
        else:
            say(f"  ok: scripts/ and the {len(tracked_out)} tracked output files equal main {head[:9]}")

    def idle(self):
        say("idle: nothing builds in the project or the clone")
        mine, p = set(), os.getpid()                 # this run and its own driver (run_promote.sh) don't count
        while p > 1 and p not in mine:
            mine.add(p)
            p = int(subprocess.run(["ps", "-o", "ppid=", "-p", str(p)], capture_output=True, text=True).stdout or 1)
        r = subprocess.run(["pgrep", "-f", STEP_PAT], capture_output=True, text=True)
        for pid in (q for q in r.stdout.split() if int(q) not in mine):
            cwd = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True).stdout
            cwd = next((l[1:] for l in cwd.splitlines() if l.startswith("n")), "")
            cmd = subprocess.run(["ps", "-o", "command=", "-p", pid], capture_output=True, text=True).stdout.strip()
            if cwd == os.path.join(self.project, "scripts") or cwd.startswith(self.clone + "/") or cwd == self.clone:
                self.bad(f"a build runs (pid {pid}, in {cwd}): {cmd[:100]}")
        if os.path.exists(os.path.join(self.project, "data", ".hydro.lock")):
            self.bad("the project's hydro lock is held (data/.hydro.lock)")
        for s in sorted(os.listdir(SLOTS)) if os.path.isdir(SLOTS) else []:
            if s.startswith("slot."):
                try:
                    info = os.readlink(os.path.join(SLOTS, s)).split("|")
                except OSError:
                    continue
                if len(info) >= 5 and info[2] == "project":
                    self.bad(f"a project build holds {s}: {info[4]} (pid {info[0]})")
        if not self.fail:
            say("  ok")

    def state(self):
        say("state: the project's data/ and output/ against the baseline")
        t0 = time.time()
        self.m_proj, self.m_base, self.m_clone = manifest(self.project), manifest(self.base), manifest(self.clone)
        say(f"  {len(self.m_proj)} files in the project, {len(self.m_base)} in the baseline, {len(self.m_clone)} in the "
            f"clone (read in {time.time() - t0:.0f} s)")
        added, removed, changed = diff(self.m_proj, self.m_base)
        self.allowed, self.already = [], []
        bad = []
        for kind, paths in (("new in the project", added), ("gone from the project", removed),
                            ("changed in the project", changed)):
            for p in paths:
                if same_content(os.path.join(self.project, p), os.path.join(self.clone, p)):
                    self.already.append(p)
                elif any(fnmatch.fnmatch(p, g) for g in self.a.allow):
                    self.allowed.append(p)
                else:
                    bad.append(f"{p} ({kind})")
        if self.already:
            self.note(f"{len(self.already)} path(s) differ from the baseline but already hold the clone's bytes "
                      f"(left as they are): {', '.join(self.already[:4])}")
        if self.allowed:
            self.note(f"{len(self.allowed)} difference(s) kept by --allow: {', '.join(self.allowed[:6])}")
        if bad:
            self.bad(f"the project is no longer baseline {self.a.baseline}: {len(bad)} difference(s), e.g. "
                     + "; ".join(bad[:8]))
        else:
            say(f"  ok: the project is baseline {self.a.baseline}")

    def built(self):
        say("built: the maps rebuilt in the clone")
        a_c, r_c, c_c = diff(self.m_clone, self.m_base)
        self.plan_add, self.plan_del, self.plan_chg = a_c, r_c, c_c
        touched = sorted({area_of(p) for p in a_c + r_c + c_c} - {None})
        rebuilt = sorted(m for m in touched if os.path.exists(os.path.join(self.clone, "output", m, "map3d_data.js"))
                         and os.stat(os.path.join(self.clone, "output", m, "map3d_data.js")).st_mtime > self.made)
        self.maps = self.a.maps or rebuilt
        say(f"  maps whose files changed in the clone: {', '.join(touched) or 'none'}; maps redrawn: "
            f"{', '.join(rebuilt) or 'none'}")
        if not self.maps:
            self.bad("no map was redrawn in the clone: nothing to promote")
        for m in self.maps:
            if m not in rebuilt:
                self.bad(f"{m}: its map was not redrawn in the clone (output/{m}/map3d_data.js is from the baseline)")
        partial = sorted(set(touched) - set(self.maps))
        if partial:
            self.bad(f"files changed in the clone for maps not promoted ({', '.join(partial)}): promote them too "
                     f"(--maps), or the project would mix the two builds")
        # failed steps in the clone's logs written since the clone was made
        logs = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(self.clone, "data")) for f in fs
                if f.endswith(".log") and os.stat(os.path.join(d, f)).st_mtime > self.made] + list(self.a.log or [])
        self.logs = logs
        failed = []
        for lg in logs:
            for line in open(lg, errors="replace").read().splitlines()[-200000:]:
                m = re.match(r"FAILED (?:s\d+ )?([a-z_0-9]+)/([a-z_0-9]+) (\S+)", line)
                if m and (not self.a.maps or m.group(1) in self.maps):
                    failed.append((m.group(1), m.group(2), m.group(3), os.path.basename(lg)))
        for a_, b_, s_, lg in sorted(set(failed)):
            if s_ in TOLERATED:
                self.note(f"{a_}/{b_} {s_} failed in the clone ({lg}); the drivers go on without it")
            else:
                self.bad(f"{a_}/{b_} {s_} failed in the clone ({lg})")
        if not self.fail:
            say(f"  ok: {len(self.maps)} map(s) to promote: {', '.join(self.maps)}")

    def stamps(self):
        if not os.path.exists(os.path.join(self.clone, "scripts", "build_stamp.py")):
            return
        say("stamps: the runs that wrote the published map files (B9's build gate)")
        n = 0
        for m in self.maps:
            sp = os.path.join(self.clone, "output", m, "build_stamp.json")
            runs = json.load(open(sp))["runs"] if os.path.exists(sp) else {}
            out = os.path.join(self.clone, "output", m)
            for d, _, fs in os.walk(out):
                if os.path.relpath(d, out).count("/") > 0:
                    continue
                for f in fs:
                    if f not in PUBLISHED:
                        continue
                    rel = os.path.relpath(os.path.join(d, f), out)
                    st = os.stat(os.path.join(d, f))
                    if st.st_mtime < self.made:
                        continue
                    n += 1
                    rec = next((r for r in runs.values() if r.get("wrote", {}).get(rel) == [st.st_mtime_ns, st.st_size]), None)
                    if rec is None:
                        self.bad(f"{m}/{rel}: no recorded run wrote it (the gate refuses it)")
                    elif rec.get("uncommitted") is None:
                        self.bad(f"{m}/{rel}: {rec['step']} ran without git in the clone (gitlink it before the test)")
                    elif rec["uncommitted"] or rec.get("edited_during") or rec.get("status") != "ended":
                        self.bad(f"{m}/{rel}: {rec['step']} ran on uncommitted or edited code, or failed")
                    elif rec.get("commit") != self.head:
                        self.note(f"{m}/{rel}: built on {str(rec.get('commit'))[:9]}, main is {self.head[:9]} (same "
                                  f"scripts/; the gate notes it)")
        if not self.fail:
            say(f"  ok: {n} published files with clean stamps")


# ---- the as-of report ----
NOTE_RE = re.compile(r"NOTE (\S+) (\d{4}-\d\d-\d\d \d\d:\d\d): (.*?) (not fetched|not refreshed) \((.*)\)(?:; using the "
                     r"(?:last good copy, of|copy of) (\d{4}-\d\d-\d\d \d\d:\d\d)| and there is no earlier copy)")
STEP_RE = re.compile(r"== ([a-z_0-9]+)/([a-z_0-9]+) (\S+) \d\d:\d\d:\d\d")
CHAIN_RE = re.compile(r"\d\d:\d\d:\d\d s\d+ ([a-z_0-9]+)/([a-z_0-9]+) (\S+) \d+s rc=")


def asof(clone, maps=None, logs=None, made=None):
    """{(step, source): {map: oldest copy date or 'none'}} from the NOTE lines of the clone's logs, and the '(as of'
    wording in its map files."""
    made = made or clone_time(clone)
    if logs is None:
        logs = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(clone, "data")) for f in fs
                if f.endswith(".log") and os.stat(os.path.join(d, f)).st_mtime > made]
    rows = defaultdict(dict)
    for lg in logs:
        step = "?"
        for line in open(lg, errors="replace"):
            m = STEP_RE.match(line)
            if m:
                step = m.group(3)
                continue
            m = NOTE_RE.search(line)
            if not m:
                continue
            area, what, copy = m.group(1), m.group(3).strip(), m.group(6) or "no copy"
            if maps and area not in maps:
                continue
            k = (step, what)
            rows[k][area] = min(rows[k].get(area, copy), copy)
    wording = defaultdict(lambda: defaultdict(int))
    for m in maps or sorted(os.listdir(os.path.join(clone, "output"))):
        for f in ("map3d_data.js", "stream_map.html"):
            p = os.path.join(clone, "output", m, f)
            if os.path.exists(p) and os.stat(p).st_mtime > made:
                for w in re.findall(r"\(as of [A-Z][a-z]{2} \d{1,2}(?:, \d{4})?\)|As of [A-Z][a-z]{2} \d{1,2}[^<\"]{0,80}",
                                    open(p, errors="replace").read()):
                    wording[m][w] += 1
    return rows, wording


def print_asof(rows, wording):
    say("\nas of: the saved copies the clone's steps read instead of downloading (they stay as of these dates)")
    if not rows:
        say("  none: every download in the clone's logs was fetched")
    by_step = defaultdict(list)
    for (step, what), per in rows.items():
        by_step[step].append((what, per))
    for step in sorted(by_step):
        for what, per in sorted(by_step[step]):
            dates = sorted(set(per.values()))
            say(f"  {step:18s} {what[:60]:60s} {len(per):2d} map(s), copies of {dates[0]}"
                + (f" .. {dates[-1]}" if len(dates) > 1 else ""))
    if wording:
        say("the maps' own 'as of' wording (popups and legend; gone where a refresh fetches the source):")
        for m in sorted(wording):
            say(f"  {m:16s} " + "; ".join(f"{w} x{n}" for w, n in sorted(wording[m].items(), key=lambda kv: -kv[1])[:4]))


# ---- promote and undo ----
_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


def clonefile(src, dst):
    """An APFS clone of src at dst (dst must not exist), keeping its times; a plain copy on another disk."""
    if _libc.clonefile(os.fsencode(src), os.fsencode(dst), ctypes.c_int(1)) != 0:     # CLONE_NOFOLLOW
        e = ctypes.get_errno()
        if e != 18:                                                                    # EXDEV
            raise OSError(e, os.strerror(e), dst)
        if os.path.islink(src):
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
    st = os.lstat(src)
    if not os.path.islink(dst) and os.lstat(dst).st_mtime_ns != st.st_mtime_ns:
        os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns))


def promote(a):
    c = Checks(a)
    ok = c.run()
    rows, wording = asof(c.clone, c.maps, c.logs, c.made)
    print_asof(rows, wording)
    if not ok:
        raise SystemExit("STOP: a check failed; nothing was changed")
    skip = set(c.already) | set(c.allowed)
    conflict = sorted(set(c.allowed) & set(c.plan_add + c.plan_chg + c.plan_del))
    if conflict:
        raise SystemExit(f"STOP: --allow kept {len(conflict)} path(s) the clone changed too: {', '.join(conflict[:5])}")
    put = [p for p in c.plan_add + c.plan_chg if p not in skip]
    drop = [p for p in c.plan_del if p not in skip]
    size = sum(c.m_clone[p][1] for p in put)
    per = defaultdict(lambda: [0, 0])
    for p in put:
        per[area_of(p) or p.split("/")[0]][0] += 1
    for p in drop:
        per[area_of(p) or p.split("/")[0]][1] += 1
    say(f"\nplan: {len(put)} file(s) in from the clone ({size / 1e9:.2f} GB, cloned: no data copied), {len(drop)} removed")
    for k in sorted(per):
        say(f"  {k:16s} {per[k][0]:6d} in, {per[k][1]:4d} out")
    if a.dry_run:
        say("dry run: nothing changed")
        return
    undo = undo_dir(c.project, a.label)
    if os.path.exists(undo):
        raise SystemExit(f"STOP: {undo} exists (a promote with this label ran; `forget` it, or pick another label)")
    os.makedirs(os.path.join(undo, "files"))
    record = dict(label=a.label, clone=c.clone, baseline=a.baseline, head=c.head, maps=c.maps,
                  started=time.strftime("%Y-%m-%d %H:%M:%S"), moved=[], put=[], stamp={}, done=False)
    rec_path = os.path.join(undo, "undo.json")

    def save():
        with open(rec_path + ".tmp", "w") as f:
            json.dump(record, f, indent=1)
        os.replace(rec_path + ".tmp", rec_path)
    save()
    t0 = time.time()
    try:
        for p in sorted(set(put) | set(drop)):        # the project's own files first, aside (renames)
            src = os.path.join(c.project, p)
            if os.path.lexists(src):
                dst = os.path.join(undo, "files", p)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)
                record["moved"].append(p)
        save()
        for p in put:
            dst = os.path.join(c.project, p)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            clonefile(os.path.join(c.clone, p), dst)
            record["put"].append(p)
            st = os.lstat(dst)
            record["stamp"][p] = [st.st_mtime_ns, st.st_size]     # undo refuses once a later build rewrote it
        record["done"] = True
        save()
    except BaseException as e:
        save()
        say(f"FAILED midway ({type(e).__name__}: {e}): putting the project back")
        _undo(c.project, undo)
        raise SystemExit(1)
    # the project's data/ and output/ now equal the clone's (but for the paths kept by --allow)
    m_now = manifest(c.project)
    x, y, z = diff(m_now, c.m_clone)
    left = [p for p in x + y + z if p not in set(c.allowed)
            and not (p in set(c.already) and same_content(os.path.join(c.project, p), os.path.join(c.clone, p)))]
    if left:
        say(f"CHECK FAILED: {len(left)} path(s) differ from the clone after the promote: {', '.join(left[:6])}; "
            f"putting the project back")
        _undo(c.project, undo)
        raise SystemExit(1)
    log_line(c.project, f"{a.label}: {len(put)} files in, {len(drop)} out, maps {' '.join(c.maps)}, from {c.clone} "
                        f"(baseline {a.baseline}, main {c.head[:9]}); undo: promote.py undo {a.label}")
    say(f"\nPROMOTED {a.label} in {time.time() - t0:.1f} s: the project's data/ and output/ now equal the clone's "
        f"({len(m_now)} files). Undo: promote.py undo {a.label} (the replaced files are in {undo}).")


def _undo(project, undo):
    """Put the project back: remove the promoted files, rename the replaced ones back. The record is kept current as
    it goes (saved on any error), so a second undo after a failure goes on from where the first stopped."""
    path = os.path.join(undo, "undo.json")
    rec = json.load(open(path))
    n = len(rec["moved"])
    try:
        while rec["put"]:
            q = os.path.join(project, rec["put"][-1])
            if os.path.lexists(q):
                os.remove(q)
            rec["put"].pop()
        while rec["moved"]:
            p = rec["moved"][-1]
            q = os.path.join(project, p)
            os.makedirs(os.path.dirname(q), exist_ok=True)
            os.rename(os.path.join(undo, "files", p), q)
            rec["moved"].pop()
    finally:
        if rec["put"] or rec["moved"]:
            with open(path + ".tmp", "w") as f:
                json.dump(rec, f, indent=1)
            os.replace(path + ".tmp", path)
    left = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(undo, "files")) for f in fs]
    if left:
        say(f"undone, but {len(left)} file(s) are still in {undo}/files (not from this promote's record): look first")
        return
    shutil.rmtree(undo)
    log_line(project, f"{rec['label']}: undone ({n} replaced file(s) back)")
    say(f"undone: the project's files are as before {rec['label']} ({n} back); {undo} removed")


def undo(a):
    u = undo_dir(a.project, a.label)
    if not os.path.exists(os.path.join(u, "undo.json")):
        raise SystemExit(f"STOP: no promotion {a.label} to undo ({u})")
    rec = json.load(open(os.path.join(u, "undo.json")))
    changed = []
    for p in rec["put"]:                      # refuse when something wrote over the promoted files since
        q = os.path.join(a.project, p)
        was = rec.get("stamp", {}).get(p)
        if was is None:                       # a record without stamps: compare with the clone's file, if still there
            s = os.path.join(rec["clone"], p)
            was = [os.lstat(s).st_mtime_ns, os.lstat(s).st_size] if os.path.lexists(s) else None
        if was and os.path.lexists(q) and [os.lstat(q).st_mtime_ns, os.lstat(q).st_size] != was:
            changed.append(p)
    if changed:
        raise SystemExit(f"STOP: {len(changed)} promoted file(s) were rewritten since ({', '.join(changed[:4])}): undo "
                         f"would lose that work")
    _undo(a.project, u)


def forget(a):
    """Drop a finished promotion's undo folder (after the publish is checked): it can no longer be undone."""
    u = undo_dir(a.project, a.label)
    if not os.path.exists(os.path.join(u, "undo.json")):
        raise SystemExit(f"STOP: no promotion {a.label} ({u})")
    rec = json.load(open(os.path.join(u, "undo.json")))
    if not rec.get("done"):
        raise SystemExit(f"STOP: {a.label} did not finish (undo.json done=false): undo it instead")
    n = size = 0
    for d, _, fs in os.walk(os.path.join(u, "files")):
        for f in fs:
            n += 1
            size += os.lstat(os.path.join(d, f)).st_size
    shutil.rmtree(u)
    log_line(a.project, f"{a.label}: forgotten ({n} replaced file(s), {size / 1e9:.2f} GB, dropped; no undo now)")
    say(f"forgot {a.label}: {n} replaced file(s) ({size / 1e9:.2f} GB) removed from {os.path.dirname(u)}")


def gitlink(a):
    clone, commit = os.path.abspath(a.clone), a.commit
    full = git("rev-parse", "--verify", f"{commit}^{{commit}}", cwd=a.project).strip()
    if os.path.exists(os.path.join(clone, ".git")):
        raise SystemExit(f"STOP: {clone}/.git exists")
    git("init", "-q", clone)
    with open(os.path.join(clone, ".git", "objects", "info", "alternates"), "w") as f:
        f.write(os.path.join(os.path.abspath(a.project), ".git", "objects") + "\n")
    git("update-ref", "--no-deref", "HEAD", full, cwd=clone)
    git("read-tree", full, cwd=clone)
    names = git("diff", "--name-only", full, "--", "scripts", cwd=clone, check=False).split()
    names += [f for f in git("ls-files", "--others", "--", "scripts", cwd=clone, check=False).split()
              if not re.search(r"__pycache__|\.pyc$|\.DS_Store$", f)]
    if names:
        shutil.rmtree(os.path.join(clone, ".git"))
        raise SystemExit(f"STOP: the clone's scripts/ are not {full[:9]}'s: {', '.join(names[:6])} (no link made)")
    say(f"{clone} is a git work tree at {full[:9]} (objects read from {a.project}); its steps' stamps name that commit")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "promote"):
        s = sub.add_parser(name)
        s.add_argument("clone")
        s.add_argument("baseline")
        s.add_argument("--maps", nargs="*", default=[])
        s.add_argument("--allow", nargs="*", default=[])
        s.add_argument("--log", nargs="*", default=[])
        if name == "promote":
            s.add_argument("--label", required=True)
            s.add_argument("--dry-run", action="store_true")
    for name in ("undo", "forget"):
        s = sub.add_parser(name)
        s.add_argument("label")
    s = sub.add_parser("asof")
    s.add_argument("clone")
    s.add_argument("--maps", nargs="*", default=[])
    s.add_argument("--log", nargs="*", default=None)
    s = sub.add_parser("gitlink")
    s.add_argument("clone")
    s.add_argument("commit")
    for s in sub.choices.values():
        s.add_argument("--project", default=PROJECT)
        s.add_argument("--baselines", default=None)
    a = ap.parse_args()
    if a.cmd == "check":
        sys.exit(0 if Checks(a).run() else 1)
    elif a.cmd == "promote":
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.label):
            raise SystemExit("STOP: a label is letters, digits, . _ -")
        promote(a)
    elif a.cmd == "undo":
        undo(a)
    elif a.cmd == "forget":
        forget(a)
    elif a.cmd == "asof":
        print_asof(*asof(os.path.abspath(a.clone), a.maps or None, a.log))
    elif a.cmd == "gitlink":
        gitlink(a)


if __name__ == "__main__":
    main()
