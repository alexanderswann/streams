#!/usr/bin/env python3
"""How many features each rule of 06_map.py that changes stream lines still touches, read from the counts 06_map.py
prints itself into data/late_<area>.log (every run in the log, so the series shows what the root fixes of 2026-11-21
took off each rule). Read-only.
Table: audit/tables/map_rules_by_run.csv (one row per area and run), and the newest run per area printed.
"""
import os, re, sys, glob, datetime as dt
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, NAMES

OUT = os.environ.get("AUDIT_TABLES", f"{ROOT}/audit/tables")
PAT = {
    "order_raised": r"stream order raised for (\d+) reaches",
    "drawn_through_breaks": r"creeks drawn through (\d+) breaks",
    "drawn_through_km": r"creeks drawn through \d+ breaks .*?\(([\d.]+) km of line",
    "lake_own_creek": r"; (\d+) as a lake's own creek",
    "through_met_nothing": r"; (\d+) met no drawn reach",
    "unnamed_outlines_joined": r"unnamed outlines joined: (\d+) of",
    "outlines_placed_across_edge": r"placed by what is across the edge: (\d+)",
    "outlines_placed_beside": r"by what is beside them: (\d+)",
    "in_lake_reaches": r"reaches lying in a lake, drawn whole only while Lakes is off: (\d+)",
    "into_lake_reaches": r"reaches running into a lake, drawn up to its shore while Lakes is on: (\d+)",
    "into_lake_pieces": r"while Lakes is on: \d+ \((\d+) pieces",
    "into_lake_km_outside": r"pieces, ([\d.]+) km outside the lakes",
    "shore_stubs_left_off": r"; (\d+) stubs along a shore left off",
    "pieces_below_outlet": r"drawn as the river they continue: (\d+) pieces below",
    "pieces_above_inlet": r"below a lake's outlet, (\d+) above an inlet",
    "dam_joins": r"rivers drawn across dams from the lake above: (\d+) of",
    "dam_cells": r"rivers drawn across dams from the lake above: \d+ of (\d+) cells",
    "dam_join_median_m": r"cells below a dam \(median (\d+) m",
    "dam_join_longest_m": r"median \d+ m, longest (\d+) m",
    "renamed_basins": None,
    "streams": r"^streams (\d+) \|",
}


def runs(area):
    p = f"{ROOT}/data/late_{area}.log"
    if not os.path.exists(p):
        return []
    out, day, cur = [], None, None
    for line in open(p, errors="replace"):
        m = re.match(r"== START .*?(\d\d)-(\d\d) (\d\d:\d\d:\d\d)", line)
        if m:
            day = f"{m.group(1)}-{m.group(2)}"
        m = re.match(rf"== {area}/all 06_map (\d\d:\d\d:\d\d)", line)
        if m:
            cur = dict(area=area, run=f"{day} {m.group(1)}")
            out.append(cur)
            continue
        if re.match(r"== ", line):
            cur = None if " 06_map " not in line else cur
            continue
        if cur is None:
            continue
        for k, pat in PAT.items():
            if pat is None:
                if "renamed basins: [" in line:
                    cur[k] = line.count("((")
                continue
            m = re.search(pat, line)
            if m and k not in cur:
                cur[k] = float(m.group(1))
    return out


rows = [r for a in NAMES for r in runs(a)]
D = pd.DataFrame(rows)
D.to_csv(f"{OUT}/map_rules_by_run.csv", index=False)
last = D.groupby("area", sort=False).tail(1).set_index("area")
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
print("newest logged run per area:")
print(last.drop(columns=[c for c in ("run",) if c in last]).T.to_string())
print("\ntotals over the 12 areas, newest run:")
print(last.drop(columns="run").sum(numeric_only=True).round(1).to_string())
# the run before the lake routing of 2026-11-21 (the last one logged before 11-21 19:00) for comparison
before = D[D.run < "11-21 19:00"].groupby("area", sort=False).tail(1).set_index("area")
both = pd.DataFrame({"before 11-21 19:00": before.drop(columns="run").sum(numeric_only=True), "newest": last.drop(columns="run").sum(numeric_only=True)})
print("\nsummed over areas (areas with a run before 11-21 19:00: %d):" % len(before)); print(both.round(1).to_string())
