#!/usr/bin/env python3
"""Static inventory of scripts/ (nothing is imported or run):
  unused     functions and module-level constants defined in scripts/*.py whose name appears nowhere else in
             scripts/, data/*.py or data/stream_burning/ (a word match, so a name used only in a comment still counts
             as used: this list errs towards "used")
  twins      functions with the same body (after stripping comments and docstrings) in two files, and function names
             defined in more than one file
  place      literals that tie the code to one area or place: `AREA ==` / `has("...")` switches, and the hand-kept
             tables of places (dicts keyed by a place or area name)
  steps      which driver runs which step, in order
Tables: audit/tables/code_unused.csv, code_twins.csv, code_area_switches.csv, code_drivers.csv
"""
import ast, os, re, sys, glob, hashlib
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, SCR, NAMES, AREAS

OUT = os.environ.get("AUDIT_TABLES", f"{ROOT}/audit/tables")
PY = sorted(glob.glob(f"{SCR}/*.py"))
OTHER = (sorted(glob.glob(f"{SCR}/*.sh")) + sorted(glob.glob(f"{SCR}/*.js")) + sorted(glob.glob(f"{SCR}/*.html"))
         + sorted(glob.glob(f"{ROOT}/data/*.py")) + sorted(glob.glob(f"{ROOT}/data/stream_burning/*/*.py"))
         + sorted(glob.glob(f"{ROOT}/data/stream_burning/*/*.sh")))
text = {p: open(p, errors="replace").read() for p in PY + OTHER}


def uses(name, skip_def=None):
    n = 0
    pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    for p, t in text.items():
        c = len(pat.findall(t))
        n += c
    return n


def body_hash(node):
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    return hashlib.sha1("".join(ast.dump(b) for b in body).encode()).hexdigest()[:12], sum((b.end_lineno - b.lineno + 1) for b in body) if body else 0


unused, defs, twins = [], {}, {}
for p in PY:
    f = os.path.basename(p)
    tree = ast.parse(text[p])
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef,)):
            h, n = body_hash(node)
            defs.setdefault(node.name, []).append((f, node.lineno, n))
            if n >= 4:
                twins.setdefault(h, []).append((f, node.name, node.lineno, n))
            if uses(node.name) <= 1:
                unused.append(dict(file=f, line=node.lineno, kind="function", name=node.name, lines=node.end_lineno - node.lineno + 1))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                names = [t] if isinstance(t, ast.Name) else [e for e in getattr(t, "elts", []) if isinstance(e, ast.Name)]
                for nm in names:
                    if nm.id.isupper() and len(nm.id) > 2 and uses(nm.id) <= 1:
                        unused.append(dict(file=f, line=node.lineno, kind="constant", name=nm.id, lines=node.end_lineno - node.lineno + 1))
pd.DataFrame(unused).to_csv(f"{OUT}/code_unused.csv", index=False)

tw = []
for h, v in twins.items():
    if len({x[0] for x in v}) > 1:
        tw.append(dict(kind="same body", where="; ".join(f"{f}:{ln} {nm}" for f, nm, ln, n in v), lines=v[0][3]))
for nm, v in defs.items():
    if len({x[0] for x in v}) > 1:
        tw.append(dict(kind="same name", where="; ".join(f"{f}:{ln} ({n} lines)" for f, ln, n in v), lines=min(x[2] for x in v), name=nm))
pd.DataFrame(tw).to_csv(f"{OUT}/code_twins.csv", index=False)

# ---- ties to one area or place
sw = []
area_names = set(NAMES)
box_names = {b for a in AREAS.values() for b in a["ranges"]}
for p in PY:
    f = os.path.basename(p)
    if f == "config.py":
        continue
    for i, line in enumerate(text[p].splitlines(), 1):
        code = line.split("#")[0]
        for m in re.finditer(r"""has\(\s*["']([a-z_0-9]+)["']\s*\)""", code):
            sw.append(dict(file=f, line=i, kind="has(source)", what=m.group(1)))
        if re.search(r"\bAREA\s*(==|!=|in\b|not in\b)", code) or re.search(r"""\.get\(\s*(watertemp\.)?AREA\b""", code):
            sw.append(dict(file=f, line=i, kind="AREA switch", what=code.strip()[:110]))
        for m in re.finditer(r"""["']([a-z_]+)["']\s*:""", code):
            if m.group(1) in area_names or m.group(1) in box_names:
                sw.append(dict(file=f, line=i, kind="table keyed by area/box", what=m.group(1)))
S = pd.DataFrame(sw)
S.to_csv(f"{OUT}/code_area_switches.csv", index=False)

# ---- drivers: every script name a driver mentions outside comments, in order of first mention
dr = []
names = sorted((os.path.basename(p)[:-3] for p in PY), key=len, reverse=True)
for sh in sorted(glob.glob(f"{SCR}/run_*.sh")) + [f"{SCR}/publish_site.sh", f"{SCR}/phone_sync.sh"]:
    seen = []
    for line in text[sh].splitlines():
        code = line.split("#")[0]
        for tok in re.findall(r"[A-Za-z0-9_]+", code):
            if tok in names and tok not in seen and tok != "config":
                seen.append(tok)
    for i, nm in enumerate(seen, 1):
        dr.append(dict(driver=os.path.basename(sh), order=i, step=nm))
D = pd.DataFrame(dr)
D.to_csv(f"{OUT}/code_drivers.csv", index=False)

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 150)
U = pd.DataFrame(unused)
print(f"unused: {len(U)} names, {U.lines.sum()} lines"); print(U.sort_values(["file", "line"]).to_string(index=False))
print("twins:"); print(pd.DataFrame(tw).sort_values("lines", ascending=False).head(40).to_string(index=False))
print("area/place ties per file:"); print(S.groupby(["file", "kind"]).size().unstack(fill_value=0).to_string())
print("has() sources used:", S[S.kind == "has(source)"].what.value_counts().to_dict())
print("drivers:"); print(D.groupby("driver").step.apply(lambda s: " ".join(s)).to_string())
ran = set(D.step) | {m for t in text.values() for m in re.findall(r"import ((?:[a-z_]+))", t)}
print("scripts no driver runs and nothing imports:", sorted(os.path.basename(p)[:-3] for p in PY if os.path.basename(p)[:-3] not in ran
                                                              and uses(os.path.basename(p)[:-3]) <= 1))
