#!/usr/bin/env python3
"""Assemble audit/AUDIT_2026-11-22.md from the text parts in audit/work/report_parts/ and the per-area tables that
report_tables.py makes from the measured CSVs, so no number in a table is typed by hand.
    python audit/scripts/report_tables.py live_d16a885 && python audit/scripts/build_report.py live_d16a885
"""
import re, sys, glob
ROOT = "/Users/mac/Fishing"
label = sys.argv[1] if len(sys.argv) > 1 else "live_d16a885"
tables = {}
for block in re.split(r"\n(?=### T\d+\. )", open(f"{ROOT}/audit/tables/{label}/report_tables.md").read()):
    m = re.match(r"### (T\d+)\. (.*?)\n\n(.*)", block, re.S)
    if m:
        tables[m.group(1)] = f"**Table {m.group(1)}. {m.group(2)}** (`audit/tables/{label}/`)\n\n{m.group(3).strip()}"
text = "\n".join(open(p).read().rstrip() + "\n" for p in sorted(glob.glob(f"{ROOT}/audit/work/report_parts/*.md")))
missing = [k for k in re.findall(r"\{\{(T\d+)\}\}", text) if k not in tables]
if missing:
    raise SystemExit(f"no table for {missing}")
text = re.sub(r"\{\{(T\d+)\}\}", lambda m: tables[m.group(1)], text)
open(f"{ROOT}/audit/AUDIT_2026-11-22.md", "w").write(text)
print(f"wrote audit/AUDIT_2026-11-22.md: {len(text.splitlines())} lines, {len(text) // 1000} KB; tables used: {sorted(set(re.findall(r'Table (T[0-9]+)', text)))}")
