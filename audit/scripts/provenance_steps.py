#!/usr/bin/env python3
"""Which code built each step of each area's most recent build?

Read-only. For every area it parses the newest run in data/rebuild_<area>.log, mid_<area>.log and late_<area>.log
(step start times), and compares each step's start time with the modification time of the script it ran and of every
local module / template that script loads. A step that started BEFORE one of its files was last changed was built by
older code than the one on disk now.

    python audit/scripts/provenance_steps.py [--since 'MM-DD HH:MM']   (default: the last START in each log)
Writes audit/tables/provenance_steps.csv and prints a summary.
"""
import ast, csv, os, re, sys, datetime as dt, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCR = f"{ROOT}/scripts"
YEAR = 2026
AREAS = ["la", "jackson", "n_georgia", "central_vt", "ne_ct", "lexington_va", "se_pa", "smokies",
         "adk_high_peaks", "adk_northwest", "adk_southwest", "adk_southeast"]
TEMPLATES = ["map_drainages.js", "map_style.css", "map3d.html"]


def local_deps(script, seen=None):
    """Every file in scripts/ that <script>.py imports (transitively) or reads as a template."""
    seen = seen if seen is not None else set()
    path = f"{SCR}/{script}.py"
    if script in seen or not os.path.exists(path):
        return seen
    seen.add(script)
    text = open(path).read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return seen
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        for n in names:
            if os.path.exists(f"{SCR}/{n}.py"):
                local_deps(n, seen)
    # modules loaded by name through importlib / __import__ ("05c_drainages" style names can't be imported directly)
    for m in re.findall(r"""['"]((?:\d\d[a-z]?_)?[a-z_0-9]+)\.py['"]""", text):
        if os.path.exists(f"{SCR}/{m}.py"):
            local_deps(m, seen)
    for m in re.findall(r"""import_module\(\s*['"]([a-z_0-9]+)['"]""", text):
        if os.path.exists(f"{SCR}/{m}.py"):
            local_deps(m, seen)
    return seen


def file_deps(script):
    out = {f"{m}.py" for m in local_deps(script)}
    for m in list(out):
        text = open(f"{SCR}/{m}").read()
        for t in TEMPLATES:
            if t in text:
                out.add(t)
    return sorted(out)


def parse_log(path):
    """[(start datetime, range or 'all', step)] for the newest run in a driver log, and that run's start."""
    if not os.path.exists(path):
        return [], None
    lines = open(path, errors="replace").read().splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("== START")]
    if not starts:
        return [], None
    i0 = starts[-1]
    m = re.search(r"(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)", lines[i0])
    day = dt.datetime(YEAR, int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
    steps, prev = [], day
    for l in lines[i0 + 1:]:
        m = re.match(r"== (\S+)/(\S+) (\S+) (\d\d):(\d\d):(\d\d)$", l)
        if not m:
            continue
        t = prev.replace(hour=int(m.group(4)), minute=int(m.group(5)), second=int(m.group(6)))
        if t < prev - dt.timedelta(hours=12):      # past midnight
            t += dt.timedelta(days=1)
        prev = t
        steps.append((t, m.group(2), m.group(3)))
    return steps, day


def main():
    mt = {f: dt.datetime.fromtimestamp(os.path.getmtime(f"{SCR}/{f}")) for f in os.listdir(SCR)
          if f.endswith((".py", ".js", ".html", ".css", ".sh"))}
    deps = {}
    rows, summary = [], {}
    for a in AREAS:
        for kind in ("rebuild", "mid", "late"):
            steps, day = parse_log(f"{ROOT}/data/{kind}_{a}.log")
            for t, rng, step in steps:
                if step not in deps:
                    deps[step] = file_deps(step)
                newer = [(f, mt[f]) for f in deps[step] if f in mt and mt[f] > t]
                rows.append(dict(area=a, log=kind, range=rng, step=step, started=t.strftime("%m-%d %H:%M:%S"),
                                 files_changed_after="; ".join(f"{f} {m.strftime('%H:%M:%S')}" for f, m in newer)))
                if newer:
                    summary.setdefault(a, {}).setdefault(step, set()).update(f for f, _ in newer)
    os.makedirs(f"{ROOT}/audit/tables", exist_ok=True)
    with open(os.environ.get("AUDIT_TABLES", f"{ROOT}/audit/tables") + "/provenance_steps.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["area", "log", "range", "step", "started", "files_changed_after"])
        w.writeheader(); w.writerows(rows)
    head = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%h %ad", "--date=format:%m-%d %H:%M"],
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", ROOT, "status", "--short", "scripts"], capture_output=True, text=True).stdout.strip()
    print(f"HEAD {head}; uncommitted in scripts/: {dirty or 'none'}")
    print(f"{len(rows)} step runs read; steps that ran before a file they load was last changed:")
    for a in AREAS:
        s = summary.get(a)
        if not s:
            print(f"  {a:15s} none")
            continue
        for step, files in sorted(s.items()):
            n = sum(1 for r in rows if r["area"] == a and r["step"] == step and r["files_changed_after"])
            tot = sum(1 for r in rows if r["area"] == a and r["step"] == step)
            print(f"  {a:15s} {step:22s} {n}/{tot} runs older than: {', '.join(sorted(files))}")


if __name__ == "__main__":
    main()
