#!/usr/bin/env python3
"""The report's per-area tables as Markdown, in imperial units, straight from the CSVs of one measured build.
    python audit/scripts/report_tables.py <label>      -> audit/tables/<label>/report_tables.md
"""
import sys, os
import numpy as np, pandas as pd
ROOT = "/Users/mac/Fishing"
label = sys.argv[1]
T = f"{ROOT}/audit/tables/{label}"
ORDER = ["la", "jackson", "n_georgia", "central_vt", "ne_ct", "lexington_va", "se_pa", "smokies",
         "adk_high_peaks", "adk_northwest", "adk_southwest", "adk_southeast"]
SQMI = 2.58999


def md(df, dec=None, default=1):
    """A Markdown table. dec = {column: decimals}; other numeric columns get `default` decimals under 100, none above."""
    dec = dec or {}
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                if isinstance(v, (float, np.floating)) and np.isnan(v):
                    cells.append("")
                elif c in dec:
                    cells.append(f"{v:,.{dec[c]}f}")
                elif "%" in c:
                    cells.append(f"{v:,.1f}")
                elif float(v).is_integer() or abs(v) >= 100:
                    cells.append(f"{v:,.0f}")
                else:
                    cells.append(f"{v:,.{default}f}")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def by_area(df):
    return df.set_index("area").reindex(ORDER).reset_index()


parts = []
# T1 streams against NHD
s = pd.read_csv(f"{T}/streams_vs_nhd.csv")
g = lambda cls, col: s[s.cls == cls].set_index("area")[col]
t = pd.DataFrame({"named NHD stream mi": g("named stream lines", "total_mi"),
                  "drawn within 500 ft %": g("named stream lines", "within150_pct"),
                  "under the size floor %": g("named stream lines", "absent_below_floor_pct"),
                  "drawn mi": g("all drawn (default layer)", "total_mi"),
                  "no NHD line within 500 ft %": g("all drawn (default layer)", "absent_1km2_plus_pct"),
                  "same, mi": g("all drawn (default layer)", "absent_1km2_plus_mi"),
                  "same, fish 60+ mi": g("drawn, fish 60+", "absent_1km2_plus_mi"),
                  "median offset ft": g("all drawn (default layer)", "offset_median_ft"),
                  "90 % within ft": g("all drawn (default layer)", "offset_p90_ft")}).reindex(ORDER).reset_index(names="area")
parts.append("### T1. Drawn streams against NHD's lines\n\n" + md(t))

# T2 drainage area
a = pd.read_csv(f"{T}/area_vs_reference_summary.csv")
g = lambda ref, col: a[a.ref == ref].set_index("area")[col]
t = pd.DataFrame({"gauges": g("USGS gauges", "matched"), "within 10 % %": g("USGS gauges", "within10_pct"),
                  "within 25 % %": g("USGS gauges", "within25_pct"),
                  "NHDPlus points 39+ sq mi": g("NHDPlus 100+ km2", "matched"),
                  "no drawn line of half the size": g("NHDPlus 100+ km2", "best_under_half_n"),
                  "nearest line under half %": g("NHDPlus 100+ km2", "under_half_pct")}).reindex(ORDER).reset_index(names="area")
parts.append("### T2. Drainage area against USGS gauges and NHDPlus\n\n" + md(t))

# T3 flow
f = pd.read_csv(f"{T}/flow_vs_gauges_summary.csv").set_index("area")
x = pd.read_csv(f"{T}/flow_class_vs_nhd.csv")
yr = x[x.map_class == "year-round"].pivot_table(index="area", columns="nhd_class", values="miles", aggfunc="sum").fillna(0)
tot = x.groupby("area").miles.sum()
notper = yr.drop(columns=[c for c in ("perennial",) if c in yr]).sum(axis=1)
t = pd.DataFrame({"year-round % of drawn mi": 100 * yr.sum(axis=1) / tot, "of it not perennial in NHD %": 100 * notper / yr.sum(axis=1),
                  "gauges": f.with_class, "same class %": f.same_class_pct, "wet gauge shown dry": f.wet_shown_dry_n,
                  "dry gauge shown wet": f.dry_shown_wet_n, "cfs within 2x %": f.typ_within_2x_pct}).reindex(ORDER).reset_index(names="area")
parts.append("### T3. Summer flow\n\n" + md(t))

# T4 fish score
fs = pd.read_csv(f"{T}/fish_score_summary.csv").set_index("area")
ft = pd.read_csv(f"{T}/fish_score_terms.csv")
m = ft.pivot(index="area", columns="term", values="mean")
c = ft.pivot(index="area", columns="term", values="corr_with_score")
t = pd.DataFrame({"median": fs["median"], "60+ % of mi": fs.mi_60_plus_pct, "at 100 %": fs.mi_at_100_pct,
                  "water mean": m.water, "thermal mean": m.thermal, "gradient mean": m.gradient, "size mean": m["size"],
                  "remoteness mean": m.remoteness, "r with size": c["size"], "r with trout record": c.trout,
                  "r with remoteness": c.remoteness}).reindex(ORDER).reset_index(names="area")
parts.append("### T4. Fish score\n\n" + md(t, {c_: 2 for c_ in t.columns if "mean" in c_ or c_.startswith("r with")}))

# T5 water temperature
p = f"{T}/watertemp_summary.csv"
if os.path.exists(p):
    w = pd.read_csv(p)
    t = by_area(w)[["area", "with_estimate_3plus_readings", "stated_pm_f", "rmse_f", "within_stated_pct", "cold_sites_bias_f", "warm_sites_bias_f",
                    "warm_read_as_full_credit"]]
    t.columns = ["area", "measured sites", "popup says +- F", "actual RMS error F", "sites inside the band %", "sites under 68 F read (F)",
                 "sites over 72 F read (F)", "72 F+ sites given full credit"]
    parts.append("### T5. Water temperature at measured sites\n\n" + md(t))

# T6 falls and lakes
fr = pd.read_csv(f"{T}/falls_recall.csv")
fr = fr[fr.known == "precise points"].set_index("area")
lk = pd.read_csv(f"{T}/lakes_summary.csv").set_index("area")
t = pd.DataFrame({"known falls (precise)": fr.n, "found by the terrain within 330 ft %": fr.drop_within_100m_pct, "lakes": lk.lakes,
                  "with a measured depth": lk.with_depth_n, "with fish records %": lk.with_fish_records_pct}).reindex(ORDER).reset_index(names="area")
parts.append("### T6. Falls and lakes\n\n" + md(t))

# T7 popup oddities and access
pc = pd.read_csv(f"{T}/popup_checks_summary.csv").set_index("area")
t = pd.DataFrame({"reaches": pc.reaches, "name agrees with NHD %": pc.name_same_pct, "no drive time %": pc.drive_missing_pct,
                  "median mph implied": pc.mph_median, "\"hike 0 min\" %": pc.hike_0_pct, "\"hike -0 min\"": pc.neg_zero_n,
                  "gradient 0.0 % %": pc.grad_zero_pct}).reindex(ORDER).reset_index(names="area")
parts.append("### T7. Names, access and popup oddities\n\n" + md(t, {"reaches": 0, "\"hike -0 min\"": 0}))

# T8 table against map
p = f"{T}/table_vs_drawn.csv"
if os.path.exists(p):
    v = by_area(pd.read_csv(p))[["area", "table_reaches", "table_mi", "drawn_mi", "lake_layer_mi", "table_60_mi", "drawn_60_mi"]]
    v.columns = ["area", "reaches in the table", "table mi", "drawn mi", "lake-layer mi", "table fish 60+ mi", "drawn fish 60+ mi"]
    parts.append("### T8. Reach tables against what the map draws\n\n" + md(v))

# T9 what 06_map.py still changes
p = f"{ROOT}/audit/tables/map_rules_by_run.csv"
if os.path.exists(p):
    d = pd.read_csv(p).groupby("area", sort=False).tail(1)
    v = by_area(d)[["area", "order_raised", "drawn_through_breaks", "drawn_through_km", "into_lake_reaches", "in_lake_reaches",
                    "shore_stubs_left_off", "pieces_below_outlet", "pieces_above_inlet", "dam_joins", "unnamed_outlines_joined"]].copy()
    v["drawn_through_km"] = v.drawn_through_km / 1.609344
    v["pieces_below_outlet"] = v.pieces_below_outlet + v.pieces_above_inlet
    v = v.drop(columns="pieces_above_inlet")
    v.columns = ["area", "order raised", "lines added below dams / at edges", "mi added", "reaches clipped at lake shores", "reaches hidden in lakes",
                 "shore stubs dropped", "pieces re-valued", "joins across dams", "drainage outlines joined"]
    parts.append("### T9. Stream features 06_map.py still changes (its own counts, newest logged run)\n\n" + md(v))

# T10 jumps and trout-found-but-dry
j = pd.read_csv(f"{T}/drawn_jumps_summary.csv").set_index("area")
p = f"{T}/trout_found_shown_dry.csv"
if os.path.exists(p):
    w = pd.read_csv(p).set_index("area")
    t = pd.DataFrame({"sudden changes along a creek": j.pairs, "of them 2+ flow classes": j.flow_2_steps, "mi on the low side": j.low_side_mi,
                      "reaches with trout found since 2016": w.trout_found_reaches, "shown mostly dry": w.shown_mostly_dry,
                      "shown seasonal": w.shown_seasonal}).reindex(ORDER).reset_index(names="area")
    parts.append("### T10. Sudden changes along a creek; trout records on water shown dry\n\n" + md(t))

open(f"{T}/report_tables.md", "w").write(f"<!-- generated by audit/scripts/report_tables.py from audit/tables/{label}/ -->\n\n" + "\n\n".join(parts) + "\n")
print(open(f"{T}/report_tables.md").read())
