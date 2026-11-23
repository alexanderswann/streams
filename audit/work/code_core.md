# Core code audit: routing, reaches, flow, drainages, fish score

Read in full (static reading only, nothing in `scripts/` imported or run): `03_hydrology.py`, `03b_stitch.py`,
`crossbox.py`, `04_knickpoints.py`, `04b_bigcreek_steps.py`, `05_score.py`, `scoring.py`, `05b_flow.py`, `flowlib.py`,
`05c_drainages.py`, `flowpath.py`, `geomatch.py`, `watertemp.py`, `areaclip.py`, `config.py` (5,558 lines), plus the
`run_*.sh` drivers. Other scripts were only grepped.

Every finding is marked **CONFIRMED** (code path read end to end) or **PLAUSIBLE** (follows from the code but depends
on data I did not measure). Line numbers are the working tree on 2026-11-21 about 23:40 EST.

**Where the numbers come from** (three kinds, always named):
- `[log]` the pipeline's own printed counters, last run in `data/mid_<area>.log`, `data/rebuild_<area>.log`,
  `data/late_<area>.log` (2026-11-21 22:32-23:32, all 12 areas ended `== DONE`, no `FAILED`).
- `[raw]` stable input tables under `data/raw/<area>/_shared/flow/` (NHDPlus table, flow table).
- `[snapshot]` `output/<area>/stream_reaches_ranked.csv`, all 12 areas, read once at 23:35 EST. **Other sessions were
  still rewriting these files** (six of the twelve had been rewritten after their own `== DONE`), so these are
  indicative only and each one is paired with the comparison to re-run. 110,665 rows in all.

---

## A. The fish score

### A.0 The formula exactly as `scoring.score()` computes it (scoring.py:223-324)

`06_map.py:73` is the only caller that matters: `s_ll = score(attach(s_ll.drop(columns="fish_score"), "sid", dirs, "streams"))`
(the `fish_score` written by `05_score.py` is dropped here, see A.2-1).

```
fish_score = round( clip( 100 * W * (0.30*S + 0.30*T + 0.15*G + 0.25*R) * burn * trout * heat * chan , 0, 100) )   # scoring.py:322-323
```

**W, the water term, in the order the code applies it**

| # | step | code | file:line |
|---|---|---|---|
| W0 | NHD class value | `s.flow.map({"perennial": 1.0, "intermittent": 0.35, "unmapped": 0.15, "ephemeral": 0.05}).fillna(0.3)` ("other" and anything else 0.3) | scoring.py:224 |
| W1 | start value | `water = num(s, "water").where(cls.ne("no data"), nhd_water)`: 05b's value, or W0 where the class is "no data" | scoring.py:226 |
| W1a | 05b's value | `water = 0.05 + 0.95 * fy` (fy = share of 16 summers the scaled low flow was >= 0.1 cfs); `water.where(~res, 0.3)` in a lake | flowlib.py:376, 379 |
| W2 | bare channel (1) | class in year-round/usually flows/seasonal AND `dry_cfs < 0.45` AND `green_p90 < 0.45` AND `green_p90_max < 0.5` AND `green - green_sur < 0.2` AND `green_water < 0.05` AND NHD class intermittent/ephemeral/unmapped AND no trout evidence AND `below_dam == ""` AND not a tailwater AND not burned since 2018 AND flow_src model/scaled AND water > 0.35 -> `water = 0.35`, class "seasonal" | scoring.py:232-237 |
| W3 | gauge (2) | `gwt = 0.05 + 0.95 * gauge_share`; `rec = gsh.notna() & (((water > gwt + 0.05) & below & ~site.isin(trout_site)) \| (water < gwt - 0.05))` -> `water = gwt`. Raises anywhere on the gauge's line; lowers only where `gauge_below` and no reach of that gauge has trout evidence | scoring.py:238-247 |
| W4 | tailwater (3) | `tw_up = tailwater(s).ne("") & (water < 1.0) & ~rec` -> `water = 1.0`, "year-round" | scoring.py:252-254 |
| W5 | below a dam (4), LA only | `held = (area_full - area_edge) >= 0.5 * area_full`; `dam_up = has("tnc_flows") & held & cls in (4 flow classes) & (water < nhd_water) & gsh.isna() & ~tw_up & ~bare_ch & ~bare` -> `water = nhd_water` | scoring.py:265-273 |
| W6 | diversion gauge | `by_gauge = (gw < 0.5) & ~(trout evidence)` -> `water = 0.05 + 0.95 * gw` (replaces whatever W2-W5 gave, up or down); class "mostly dry" if `gw <= 0.2` else "seasonal" | scoring.py:276-278, 312-313 |

**The four additive terms**

| term | code | file:line |
|---|---|---|
| S size | `big = np.fmax(area_full_km2.fillna(area_km2), river_km2.fillna(0))`; `size = np.clip(np.log10(big) / np.log10(50), 0, 1)` | scoring.py:281-282 |
| T thermal | `thermal = 0.5 * np.where(tw.ne(""), 1.0, cool) + 0.35 * shade + 0.15 * north` | scoring.py:295 |
| T.cool | `cool = np.clip((25 - wt) / (25 - 20), 0, 1).fillna(no_est)`; `wt = watertemp.estimate(air_aug, elev_m, big, lake_share)`; `no_est` = 0.5, or the same clip of the area's mean site temperature where the area's fit has no skill | scoring.py:287-294 |
| T.shade | `terrain = shade_pct.fillna(20)/100`; `canopy = clip(canopy_pct.fillna(0)/100, 0, 1)`; `shade = np.clip((1 - (1 - terrain) * (1 - 0.8 * canopy)) / 0.45, 0, 1)` | scoring.py:283-284 |
| T.north | `north = np.clip((s.northness.fillna(0) + 0.15) / 0.30, 0, 1)` | scoring.py:285 |
| G gradient | `grad = band(s.gradient_pct, 1, 8, 10)`: 1 on 1-8 %, 0.9 at 0 %, 0 from 18 % | scoring.py:77-78, 296 |
| R remoteness | `remote = np.clip((approach_med_min.fillna(0) + (2.0 - 1) * bike_med_min.fillna(0)) / 120, 0, 1)` | scoring.py:297-298 |

Effective weights in points of 100: size 30, water temperature 15, shade 10.5, northness 4.5, gradient 15, remoteness 25.

**The four multipliers**

| factor | code | file:line |
|---|---|---|
| burn | `yrs = THIS_YEAR - year`; `f = select([yrs <= 2, yrs <= 5, yrs <= 9], [0.4, 0.7, 0.9], 1.0)`; `1 - (1 - f) * np.where(pd.isna(sev), 1.0, sev)`; `sev = fmax(burn_sev, debris-flow hazard {high 1.0, moderate 0.75, low 0.4})`; a reach with a hazard but no burn takes the hazard's year and severity | scoring.py:121-127, 299-305 |
| trout | `np.select([pos, neg, s.trout_water.notna()], [1.2, 0.5, 1.2], 1.0)`; `pos = (found >= THIS_YEAR - 10) & (absent.isna() \| (found >= absent))`; `neg = (absent >= THIS_YEAR - 10) & ~pos` | scoring.py:189-199 |
| heat | `f = np.clip(1 - (air - 29.0) / (30.5 - 29.0) * (1 - 0.2), 0.2, 1.0)`; 1.0 where trout evidence, below a dam (`below_dam` not "" and not "in:"), a tailwater, or no air value | scoring.py:214-220 |
| chan | 0.2 where the name matches `ARTIFICIAL` and not `NATURAL` and there is no trout evidence | scoring.py:202-211 |

**Helpers the rules share**
- "trout evidence" = `trout_signs(s)[0] | s.trout_water.notna()` (scoring.py:229, 211, 220, 277).
- `tailwater(s)` (scoring.py:176-186): `on = dam.eq(d) | (s["name"].eq(river) & (s.elev_m <= top) & (big >= 20) & dam.eq(""))`
  for each `(dam -> river, top elevation)` of `_TAILWATERS` (scoring.py:153-166).
- `watertemp.estimate` (watertemp.py:423-432): `rec["intercept"] + sum(k * np.clip(c[t], *rec["ranges"][t]) ...)`; inputs
  clipped to the range of the measured sites; NaN where the fit record is missing or `ok` is false.
- `watertemp.lake_share` (watertemp.py:202-212): `clip(1 - area_edge/area_full, 0, 1) * fade`, fade 1 up to 50 km2, 0 from
  500 km2, by log drainage.

**The fits that feed T.cool** (`data/raw/<area>/_shared/water_temp_fit.json`, read 23:34-23:40; all `ok` at that time):

| area | water temperature (C) = | sites | leave-one-out error |
|---|---|---|---|
| la | 11.52 + 0.519 air - 4.398 elev_km | 64 | 2.95 |
| jackson | 19.85 - 4.716 elev_km + 1.553 log10 km2 | 145 | 3.30 (spread 3.72: passes the 0.9 test by 0.05) |
| n_georgia | 26.34 - 11.379 elev_km | 409 | 1.69 |
| central_vt | -12.64 + 1.534 air + 0.960 log10 km2 | 291 | 2.33 |
| ne_ct | 15.20 + 3.020 log10 km2 | 60 | 1.51 |
| lexington_va | 20.58 - 5.965 elev_km + 1.758 log10 km2 | 169 | 1.77 |
| se_pa | -11.98 + 1.348 air + 1.122 log10 km2 | 230 | 1.62 |
| smokies | -6.91 + 1.093 air + 0.926 log10 km2 | 247 | 1.55 |
| adk_high_peaks | 19.02 - 5.958 elev_km + 6.958 lake | 90 | 3.18 |
| adk_southwest | 17.36 + 6.221 lake | 123 | 3.02 |
| adk_southeast | 16.85 + 1.741 log10 km2 (no lake term) | 54 | 2.50 |
| adk_northwest | 23:23 run: no skill, every reach the mean 18.39. 23:33 run: the group fit 20.02 - 5.587 elev_km + 5.977 lake | 87 / 337 | 3.41 / 2.87 |

**What `05b_flow.py` does before W1** (the value scoring.py reads as `water`, `water_class`, `flow_src`):
1. Own line ("model"): `match_points` = nearest NHDPlus V2 line within 150 m whose drainage is 0.3-1.6 x the reach's,
   side arms removed (flowlib.py:106-132; 05b_flow.py:408-411).
2. Inherited ("scaled"): the first reach downstream that has a line, up to 60 reaches on
   (`while j >= 0 and np.isnan(comid[j]) and hops < 60`, 05b_flow.py:417), on into the next box (`settle`/`into`/`beyond`,
   05b_flow.py:289-336), or the NHDPlus line of a lake draining off the map (`lake_line`, 05b_flow.py:372-397).
3. Flow per summer: `ratio = (df.area_km2 / df.comid.map(v2_area)).clip(upper=1.2)`; `q = low.reindex(...) * ratio`
   (05b_flow.py:470-471). The area is `area_edge_km2` in LA and `area_full_km2` elsewhere (05b_flow.py:70).
4. `flow_years = (q >= FLOWING_CFS).mean(axis=1)` (05b_flow.py:477), `FLOWING_CFS = 0.1` (flowlib.py:369); class by
   `pd.cut(fy, [-1, 0.2, 0.5, 0.85, 1.0])` (flowlib.py:377).
5. Four rules that stop an estimate lowering a reach: `lake_floor` (05b_flow.py:513-525), `keep` with `credible`
   (526-548), `far` (555-559), `via` (567-571). See A.3 and C-6.
6. "reservoir": `lk_ = (flow_src != "model" & in_lake) | in_wet_lake` and `lk2_ = in_layer_lake & class != reservoir`
   -> `water = 0.3` (05b_flow.py:587-598).
7. A side channel copies every column of the river reach beside it (05b_flow.py:603-612).

### A.1 Double counting

**A1-1 Hot air enters twice in LA: the water-temperature estimate and the heat gate. CONFIRMED.**
`cool` comes from a fit on PRISM August air and elevation (LA record above); `heat_factor` reads the same `air_aug`
column (scoring.py:217-218). `[snapshot]` 507 LA reaches are gated; every one has an estimate of 23.6 C or more
(cool <= 0.28), and all 308 LA reaches estimated at 25 C or more (cool = 0) are also gated. The gate is the stronger of
the two: without it 106 of the 507 would score 30+ and 73 would score 50+ (now 10 and 1); those are year-round desert
reaches (Whitewater River 26 reaches, Tahquitz Creek 12, San Gorgonio River 8, Snow Creek 5, Andreas Creek 4).
The docstring's reason for the gate ("Air temperature, not a stream-temperature model", scoring.py:62-63) predates
`watertemp.py`. Measure: recompute the LA scores with `heat = 1` and list every reach that moves 10+ points.

**A1-2 Drainage area enters five ways. CONFIRMED.**
(a) `size` (scoring.py:282). (b) The water term: flow is scaled by `area / line area` and compared with an absolute
0.1 cfs (05b_flow.py:470-477), so outside LA the class is an area threshold. `[raw]` the drainage a creek needs for
"year-round" by each area's flow table: ne_ct 2.40 km2 (10th-90th percentile of lines 1.56-3.67), lexington_va 0.69,
se_pa 0.62, central_vt 0.56, n_georgia 0.52, jackson 0.44, smokies 0.41, the four Adirondack maps 0.32, LA 8.24
(2.34-66.6). `[snapshot]` outside LA 13.3 % of creek reaches under 2 km2 have a water term under 1, 3.4 % at 2-5 km2,
0.3 % at 5-20 km2, 0.1 % above. (c) The water-temperature fit's `log_area` term, with the opposite sign (bigger =
warmer) in seven areas. (d) `lake_share`'s fade by drainage (watertemp.py:210-211). (e) The 1 km2 map floor
(05_score.py:90) and the tailwater test `big >= 20` (scoring.py:184).

**A1-3 Sun exposure enters three ways. CONFIRMED.** Terrain shade (share of mid-July daylight, which already depends
on aspect), canopy, and `northness` (aspect again) (scoring.py:283-285).

**A1-4 Trout evidence is a bonus and five exemptions. CONFIRMED.** x1.2 (scoring.py:199), and it switches off the heat
gate (220), the channel factor (211), the bare-channel rule (235), gauge lowering (242-243) and the diversion gauge
(277). `[snapshot]` 59,989 of 110,665 reaches (54 %) have the x1.2: adk_high_peaks 86 %, adk_southwest 85 %,
adk_northwest 82 %, LA 9 %. `trout_water` alone covers 81-86 % of three Adirondack maps. The median reach's combined
multiplier is 1.2.

**A1-5 NHD's class is used four ways on one scale with the model. CONFIRMED.** As the water value where there is no
flow data (scoring.py:226), as the floor of four 05b rules and of W5, as a condition of the bare-channel rule
(scoring.py:235), and as the filter of the big-creek drops (05_score.py:364). NHD "perennial" with no data is 1.0, the
same as a model line that flowed in 16 of 16 summers, and more than one that flowed in 15 (0.94).

**A1-6 A dam is counted five ways. CONFIRMED.** `below_dam` exempts from heat (scoring.py:219); a `TAILWATERS` reach
gets W = 1 (252), cool = 1 (295) and no heat gate; `held` floors W at NHD's class (265-273); the lake term warms creeks
below lakes in three Adirondack fits, and its fade exists to spare tailwaters (watertemp.py:21-30) which
`TAILWATERS` already spares.

**A1-7 Two rules read the same gauge records. CONFIRMED.** The diversion rule (W6) and the gauge rule (W3) both come
from `gauge_summers` (flowlib.py:434-450; 05b_flow.py:56, 628-636). `[snapshot]` W6 sets 10 reaches, all on the San
Jacinto River; 3 of them also carry `gauge_share` 0.19 from the same gauge, which W3 would set to the same 0.23.

**A1-8 Ridden minutes are counted twice by design.** `approach_med_min` includes the minutes ridden, and
`(RIDE_REMOTENESS - 1) * ridden` adds them again (scoring.py:298; "user's choice", scoring.py:134).

### A.2 Leftover terms

**A2-1 `05_score.py`'s first-pass score has no consumer but a per-range CSV. CONFIRMED.**
`s["fish_score"] = (100 * water * (0.35 * size + 0.25 * cold + 0.15 * grad + 0.25 * remote)).round(0)` (05_score.py:280-288),
dropped at 06_map.py:73. Read only by the per-range `stream_reaches_ranked.csv` (05_score.py:387-389) and a print
(429-430). With it: `band()` (05_score.py:281-282, a copy of scoring.py:77-78), `config.ELEV_BAND` (config.py:42, 59,
371), and `road_m` and `trail_m` of the reaches (05_score.py:121-122) and of the drops (308-309): grep finds no reader
of either outside 05_score.py.

**A2-2 The 0.10 for "no data" is never used. CONFIRMED.** `water = water.where(fy.notna() | res, 0.10)` (flowlib.py:381);
scoring.py:226 and 05b_flow.py:510 both replace it with NHD's value.

**A2-3 `order` is superseded. CONFIRMED.** `s["order"] = sample(strahler, mid)` (05_score.py:117); 06_map.py:83 uses
`s_ll.strahler.fillna(s_ll["order"])`, and 05c writes `strahler` for every reach (05c_drainages.py:379-380). See D-11.

**A2-4 The diversion machinery changes 10 reaches. CONFIRMED (count `[snapshot]`).** `_DIVERSIONS` (flowlib.py:393-402),
`below_diversion_comids` (405-431), 05b's `div_*` columns (05b_flow.py:55-57, 458-464, 492-502), `by_gauge`
(scoring.py:276-278, 310-313). 7 of the 10 are not also covered by W3. Measure: `water_by_gauge == True` rows, and of
those `gauge_share.isna()`.

**A2-5 The area-mean branch is live only when a fit loses skill. CONFIRMED.** `avg = watertemp.area_mean()` ->
`no_est` (scoring.py:292-293). At 23:40 all 12 records were `ok`; at 23:23 adk_northwest's was not (G-6).

**A2-6 A branch of `minor_arms` cannot run. CONFIRMED `[raw]`.** `if "qe_ma" in d: ... else:` Natural Flows
(flowlib.py:29-37, docstring "(California)"). `02b_download_flow.py:76` asks for `qe_ma` in every area and LA's table
has it on all 9,122 lines, so LA's side-arm pairs are judged on EROM flow, not on the Natural Flows the docstring names.

**A2-7 Defaults for missing inputs never fire today.** `[snapshot]` `approach_med_min` is never empty, `canopy_pct` is
empty on 6 reaches. If they did fire they would mark a reach down on missing data: `approach_med_min.fillna(0)` makes
an unreachable reach roadside (scoring.py:298), `canopy_pct.fillna(0)` and `shade_pct.fillna(20)` give the least shade
(283).

**A2-8 Rules that exist in the code for all areas but act in one.** Heat gate: LA only (`[snapshot]` 507, 0 elsewhere).
Bare channel: LA 545, Jackson 69. "below a dam" 111 and "tailwater releases" 46: LA. Diversions: LA.

**A2-9 Guards for tables that always exist.** `if "water_class" in s else`, `if "flow_src" in s else`,
`if "gauge_site" in s else`, `if "gauge_below" in s else`, `if "debris_flow" in s else` (scoring.py:225, 231, 240, 241,
299), `if "area_full_km2" in s else` (182). `attach` stops the run when a table is missing a reach (scoring.py:100-102).

### A.3 Every rule that lowers a score or a flow class, and the evidence it needs

| # | rule | file:line | evidence it requires | exemptions | near-certain? | count |
|---|---|---|---|---|---|---|
| L1 | Class and W from a reach's own model line | flowlib.py:376-377; 05b_flow.py:470-477 | A modelled monthly flow (TNC Natural Flows in LA; EROM x one yearly index per area elsewhere) times area ratio, under 0.1 cfs | the 05b floors below | No: a model, and outside LA an area threshold (A1-2) | `[snapshot]` NHD-perennial creek reaches with W under 1 on their own line: 1,420 (LA 812, ne_ct 380, n_georgia 122) |
| L2 | Class and W inherited from the first modelled reach downstream ("scaled") | 05b_flow.py:415-421 | The unit-area flow of another creek's line | only where the line was found in another box, through a lake, or is an off-map lake's (below) | No | `[snapshot]` 30,176 scaled reaches; 2,928 sit below NHD's class, 1,229 of them NHD-perennial (ne_ct 512, central_vt 268, n_georgia 194, LA 52) |
| L3 | A new estimate with the area from other boxes may lower one whose old line had under half the reach's drainage | 05b_flow.py:538-541 `credible = line_km2 >= 0.5 * area_edge.values` | A model line of the right size | none | No (model) | `[log]` 347 reaches |
| L4 | In a lake: W = 0.3, class "reservoir" | flowlib.py:379; 05b_flow.py:587-598 | Half the reach's length inside an NHD lake of 8 ha (as the map draws it) or a level lake of the lakes layer | none | Yes for "is lake water"; 0.3 is a judgment | `[snapshot]` 8,624 rows; `[log]` 7,922 + 447 |
| L5 | No flow data: NHD intermittent 0.35, unmapped 0.15, ephemeral 0.05, other 0.3 | scoring.py:224-226 | A 2-of-3 vote of the nearest NHD line within 60 m (05_score.py:124-132) | none | "unmapped" is absence of evidence (G-3) | `[snapshot]` no-data reaches: perennial 487, intermittent 231, unmapped 911, ephemeral 399, other 279 |
| L6 | Bare channel -> 0.35 | scoring.py:232-237 | Thirteen conditions (W2) | trout, dam, tailwater, burn since 2018 | The strongest of the lowering rules; one weak leg (G-3) | `[snapshot]` 614 (LA 545, Jackson 69); 119 are "unmapped" |
| L7 | Gauge on the creek lowers | scoring.py:243 | 5+ summers measured since 2011; reach on the gauge's line, within 4 km straight line, 0.9-1.5 x its drainage | trout on any reach of that gauge | Yes where the reach is below the gauge; a reach above with 90 % of the drainage also counts (G-12) | `[snapshot]` 85 lowered, 22 raised |
| L8 | Diversion gauge | scoring.py:276-278 | Gauge below the diversion flowing under half of 5+ summers; reach below the diversion until tributaries add 25 % | trout | Yes | `[snapshot]` 10 |
| L9 | Burn | scoring.py:121-124, 299-305 | A fire perimeter since 2017 touching the buffered reach (11_context.py:571-578) | none | Perimeter yes. **Unknown severity is treated as the highest**: `np.where(pd.isna(sev), 1.0, sev)` | `[snapshot]` 4,061 reaches; 3,373 with no severity; 3,064 with neither severity nor hazard |
| L10 | Trout x0.5 | scoring.py:194, 199 | The latest survey in 10 years found none, for the creek of that name within 5 km (CA) or 1.5 km (11_context.py:356-361) | a later or equal "found" year | **No**: one sample; and it outranks a trout-water designation (`[pos, neg, trout_water]` order) | `[snapshot]` 267 (ne_ct 154, smokies 57, LA 56); 117 in ne_ct are designated trout water; 76 also have an older "found" record |
| L11 | Heat gate | scoring.py:214-220 | PRISM August air above 29 C (800 m grid) | trout, below a dam, tailwater, no air value | Owner's judgment, set from LA trout records (scoring.py:58-61) | `[snapshot]` 507, LA only; 407 at the 0.2 floor |
| L12 | Built channel x0.2 | scoring.py:202-211 | The reach's voted name has a built word and no natural word | trout | Yes for the names found: `[snapshot]` 109 reaches, all canals, aqueducts, flood channels, storm drains. See G-13 for how a pipeline's name can land on a creek | 109 |
| L13 | T.cool | scoring.py:294 | Estimated water temperature above 20 C; estimate off by 1.5-3.4 C (fits above) | tailwater | No: the error is as wide as half the 20-25 C window | `[snapshot]` 34,970 reaches lose some credit; 510 lose all |
| L14 | Lake term warms creeks below lakes | watertemp.py:202-212 | Share of drainage through a lake x a coefficient of 6.0-7.0 C | fades on rivers | Fitted, but in three Adirondack maps and not the fourth (A.4-6) | `[snapshot]` 478 + 708 + 550 creek reaches, median 22 C against 17-18 |
| L15 | Not drawn at all | 05_score.py:90 `keep = (s.area_km2 + carried >= MAP_MIN_KM2) & (sea < 0.5) & areaclip.inside(...)` | D8 drainage with carried water under 1 km2; or half the vertices at or below 0.5 m; or past the state line | none | A spring creek with a small surface drainage is dropped | not counted |
| L16 | A side channel takes the river's evidence | 05b_flow.py:603-612 | Rule of 05_score.py:209-278 | not where either lies in a lake | Can lower as well as raise | `[log]` 214 |

**The four 05b rules that stop L2 and one scoring rule, each written for one provenance:**
- off-map lake's line: `low_ = FROM_LAKE.get(edge, ...) & (eff(e) < nhd - 1e-9)` (05b_flow.py:518), `[log]` 569 reaches use such a line;
- found in the next box: `lower = (far.notna() & (eff(ev) < nhd - 1e-9))` (05b_flow.py:556), `[log]` 637 scaled across a box edge, 62 kept at NHD's class;
- found through a lake: `lk2 = (via_final & flow_src == "scaled" & (eff(ev) < nhd - 1e-9))` (05b_flow.py:568), `[log]` 189;
- the box's own area gave a higher estimate: `keep = (eff(ev_edge) < eff(ev) - 1e-9)` (05b_flow.py:532), `[log]` 905;
- below a dam in LA: W5 (scoring.py:265-273), `[snapshot]` 111.

A plain in-box "scaled" estimate has no such floor: that is the 2,928 of L2. One general rule ("an inherited estimate
never puts a reach below NHD's class") would replace the first three and cover the rest. Measure: for
`flow_src == "scaled"` creek reaches, count `water_term < nhd value` by area and NHD class (the 2,928 / 1,229 above).

### A.4 Saturation and caps that make scores incomparable

1. **The cap at 100 binds only because of the trout bonus. CONFIRMED.** `[snapshot]` 2,975 reaches score exactly 100,
   all of them with x1.2. Jackson: 1,200 of 10,739 (11.2 %), more than its whole top decile. adk_southwest 4.5 %,
   adk_northwest 4.2 %, smokies 4.1 %.
2. **W is 1.0 on most reaches outside LA.** `[snapshot]` 81-97 % in ten areas, ne_ct 56 %, LA 18 %. 06_map.py:74-76
   says so itself ("the score was tuned on LA's mostly dry channels and runs high everywhere else") and adds
   `area_rank_pct`.
3. **T is near its top everywhere but LA and Georgia.** `[snapshot]` median thermal 0.82-0.92 in ten areas (LA 0.65,
   n_georgia 0.70). Shade is at full credit on 57,869 reaches (52 %); the estimate is at or under 20 C on 75,695 (68 %),
   on every Jackson reach.
4. **Size is flat from 50 km2** (scoring.py:282): 19,104 reaches (17 %). **Remoteness is flat from 120 minutes**: 13,111.
5. **Gradient cannot fall below 0.9 on flat water** (band lower side): `[snapshot]` 14,538 reaches have 0 %, 6,851 of
   them lake reaches.
6. **The lake term differs between the four Adirondack maps. CONFIRMED on the fit records.** A creek fed wholly
   through a lake, 10 km2, 500 m: adk_southwest 23.6 C (cool 0.28), adk_northwest group fit 23.2 (0.36), adk_high_peaks
   23.0 (0.40), adk_southeast 18.6 (1.0). `[snapshot]` lake-fed creek reaches read a median 22.0-22.4 C in three maps
   and 18.4 C in adk_southeast. About 10 points of score for the same kind of creek on either side of a map edge.
7. **An area's fit is all-or-nothing on `rmse <= 0.9 x spread`** (watertemp.py:347). Jackson passes by 0.05 C;
   adk_northwest failed at 23:23 and every reach read 18.39 C. A rebuild can move a whole area's thermal term.
8. **Missing flow data reads as the best case where NHD says perennial** (W1): 487 reaches at 1.0 on the label alone.
9. **`area_rank_pct` ranks lake water with the creeks** (06_map.py:76): `[snapshot]` "reservoir" rows are 19 % of
   adk_northwest, 17 % of adk_southeast, 13 % of ne_ct.
10. **The score steps on 1 January.** `THIS_YEAR = dt.date.today().year` (scoring.py:74). `[snapshot]` 753 reaches burned
    in 2024 go from x0.4 to x0.7 and 1,136 burned in 2017 from x0.9 to x1.0 on 2027-01-01 with no new data; the trout
    windows (scoring.py:193-194) move the same day.

---

## B. Constants and place-specific rules

"How chosen" is what the comment beside the constant records: **all** = measured on all areas; **case** = one or a few
named places; **reason** = argued, not measured; **user** = the owner's choice; **none** = nothing recorded.

### B.1 Fish score and flow evidence

| constant | value | file:line | controls | how chosen |
|---|---|---|---|---|
| weights | 0.30 / 0.30 / 0.15 / 0.25 | scoring.py:322 | size, thermal, gradient, remoteness | none |
| thermal split | 0.5 / 0.35 / 0.15 | scoring.py:295 | water temperature, shade, northness | none |
| NHD class values | 1.0 / 0.35 / 0.15 / 0.05 / 0.3 | scoring.py:224; copies at 05b_flow.py:509, 05_score.py:283 | W with no flow data | none |
| `RIDE_REMOTENESS` | 2.0 | scoring.py:134 | ridden minutes count double | user |
| remoteness cap | 120 min | scoring.py:298 | R saturates | none |
| size cap | 50 km2 | scoring.py:282 | S saturates | none |
| gradient band | 1, 8, soft 10 | scoring.py:296 | G | none |
| shade | default 20 %, canopy x0.8, full at 0.45 | scoring.py:283-284 | T.shade | none |
| northness | +-0.15 | scoring.py:285 | T.north | none |
| `HEAT_START, HEAT_FULL, HEAT_FLOOR` | 29.0, 30.5, 0.2 | scoring.py:135 | heat gate | LA trout records: hottest 26.7 C + 2 (scoring.py:58-61) |
| `DRY_MARGINAL_CFS` | 0.45 | scoring.py:138 | bare rule | all ("measured on the USGS gauges of all 12 areas", scoring.py:136-137; in effect LA's 31 gauged creeks) |
| `GREEN_BARE`, `GREEN_BARE_ANY_YEAR` | 0.45, 0.5 | scoring.py:139 | bare rule | all (same note) |
| `GREEN_STRIP` | 0.2 | scoring.py:140 | riparian strip | case (Andreas Canyon 0.31) |
| `GREEN_BURN_SINCE` | 2018 | scoring.py:142 | bare rule not read after a fire | reason |
| `GREEN_SEASONAL` | 0.35 | scoring.py:143 | bare rule's W | reason (as NHD intermittent) |
| open water share | 0.05 | scoring.py:234 | bare rule | none |
| gauge dead band | +-0.05 | scoring.py:243 | W3 | none |
| `DAM_HELD` | 0.5 | scoring.py:144 | W5 | reason (as `below_dam_comids`) |
| diversion share | under 0.5 | scoring.py:277 | W6 | none |
| `WATER_FULL, WATER_ZERO` | 20, 25 C | scoring.py:149 | T.cool | reason (trout biology) + LA check on 1,566 reaches |
| `_TAILWATERS` elevations | 715, 700, 285, 250, 475, 850 m | scoring.py:153-166 | tailwater by name | case each (250: one reach, hooch_tailwater:s1492) |
| tailwater size | 20 km2 | scoring.py:184 | main stem only | case (Toccoa 3-7 km2 of 490) |
| burn | 0.4 / 0.7 / 0.9 at 2 / 5 / 9 years | scoring.py:123 | burn | none |
| `DEBRIS` | 1.0 / 0.75 / 0.4 | scoring.py:127 | hazard as severity | none |
| trout | x1.2, x0.5, 10 years | scoring.py:193-199 | trout | none |
| channel | x0.2 | scoring.py:211 | built conveyance | none |
| class cuts | 0.2 / 0.5 / 0.85 | flowlib.py:377; scoring.py:245, 271 | class names | none |
| `FLOWING_CFS` | 0.1 | flowlib.py:369 | "kept flowing" | "calibrated on gauges" (which, not said; MULTI_AREA_LOG.md:427 says the eastern gauges never test it) |
| water value | 0.05 + 0.95 fy; lake 0.3; no data 0.10 | flowlib.py:376-381 | W1a | none |
| `MIN_RESERVOIR_KM2` | 0.08 | flowlib.py:8 | which lakes count | reason |
| `match_points` | 150 m, 0.3-1.6, rank `miss.round(1) * 1000 + dist` | flowlib.py:106, 128 | reach -> model line | none |
| `minor_arms` | 0.5 km2, 0.97, 0.5, 0.25, 0.9, 50 rounds | flowlib.py:38, 75, 87-96 | side arms | case (Guys Run, Wissahickon, Prophecy Creek) |
| `LAKE_PIECE_M` | 50 | flowlib.py:187 | shortest piece cut at a shore | none |
| in-lake shares | 0.5 | flowlib.py:225, 303, 348; 05b_flow.py:109, 130, 369 | "in" a lake | none |
| `below_dam_comids` | share 0.5, dam drainage 3 km2 | flowlib.py:341, 357 | below-dam flag | none |
| diversion line | 10 km2, 150 m, share 0.5 | flowlib.py:405-418 | diversion's line | none |
| `gauge_summers` | since 2011, 5 summers, 110 days | flowlib.py:434-443 | gauge record | none |
| `GREEN_YEARS` | 2022, 2023, 2024 | flowlib.py:460 | rasters read | "the rule was measured on these" |
| `GAUGE_KM` | 4.0 | flowlib.py:461 | reach of a gauge | none for 4; a wider rule was measured and rejected (flowlib.py:553-558) |
| `GAUGE_SITE_M` | 500 | flowlib.py:462 | gauges that are one site | case (Whitewater at Windy Point) |
| `GAUGE_END_M` | 100 | flowlib.py:542 | reach on the gauge's line | case (San Jacinto River) |
| gauge drainage | 2/3-1.5 x; below from 0.9 x | flowlib.py:596, 605 | W3 | none |
| gauge -> reach | 300 m, 0.5-2 x | flowlib.py:620-624 | gauge's reach | none |
| `channel_green` | 15 / 30 / 100-400 m, 90th percentile, 3 pixels | flowlib.py:495-512 | greenness | none |
| flow scaling | ratio capped at 1.2 | 05b_flow.py:470 | q | none |
| year kept | 90 % of lines | 05b_flow.py:44 | incomplete year | none |
| walks | 400 cells, 60 reaches, 4 boxes | 05b_flow.py:190, 297, 320, 336, 380, 417 | search downstream | none |
| `credible` | 0.5 | 05b_flow.py:539 | L3 | case (Pachaug River) |
| diversion | +0.05 km2, growth 1.25 | 05b_flow.py:495, 502 | W6 | none |
| drop -> reach | 80 m | 05b_flow.py:644 | drop's evidence | none |

### B.2 Water temperature

| constant | value | file:line | controls | how chosen |
|---|---|---|---|---|
| `GEOTHERMAL_C` | 30 | watertemp.py:68 | sites left out | case (Warm Creek) |
| `MIN_SITES` | 25 | watertemp.py:69 | no fit below | none (comment is wrong, G-15) |
| cache | 30 days | watertemp.py:75 | WQP download | none |
| record start | 1995 | watertemp.py:86 | readings | none (docstring says 2000) |
| site window | July-August, 07-18 h, 0-40 C, 3 decimals | watertemp.py:157-160 | target | reason |
| `LAKE_FULL_KM2, LAKE_NONE_KM2` | 50, 500 | watertemp.py:181 | lake term's fade | measured on Adirondack + Jackson sites (watertemp.py:23-30) |
| `LAKE_MIN_SITES` | 10 | watertemp.py:183 | lake term allowed | reason (counts given) |
| `SKILL` | 0.9 | watertemp.py:187 | fit used or not | none |
| `OUTLIER_MADS` | 3.0 | watertemp.py:188 | sites dropped | none |
| snaps | 200 m, 150 m | watertemp.py:198, 235 | site -> line, site -> reach | none |
| simpler set | within 0.05 C | watertemp.py:294 | model choice | none |
| tau2 floor, 80 % rule | 0.1, 0.8 | watertemp.py:315, 269 | weights, site set | none |

### B.3 Routing and links

| constant | value | file:line | controls | how chosen |
|---|---|---|---|---|
| `HALO` | 5000 m | 03_hydrology.py:32 | neighbour terrain conditioned | none (too small for big lakes: `mend_seams` exists for it) |
| `FLAT_EPS` | 1e-9 | 03_hydrology.py:33; copy 03b_stitch.py:50 | flat increment | measured (MULTI_AREA_LOG.md:445); the comment's "0.4 mm" is 0.4 micrometres |
| `STREAM_KM2` | 0.25 | 03b_stitch.py:43 | channel start | none |
| `LEVEL_HA` | 2 | 03b_stitch.py:44 | lake "holds water" | none |
| `LINE_PULL` | 5.0 | 03b_stitch.py:45 | lake routing follows NHD | none |
| `MEND_R`, `MEND_EDGE` | (300, 3000), 150 cells | 03b_stitch.py:48-49 | seam mend | none |
| outflow line | 3000 cells | 03b_stitch.py:416 | line below an outlet | none |
| `VERSION` | 17 | crossbox.py:28 | cache key | hand-bumped |
| `MIN_KM2` | 0.1 | crossbox.py:29 | basin carried | reason |
| `OUTSIDE_MIN_KM2` | 10, and 25 % of the river | crossbox.py:30, 586 | river carried in | none |
| `OUTFLOW_NEAR_M` | 100 | crossbox.py:31 | put-in moved to routed way out | case (Stillwater 450 m, Raquette Lake) |
| shared edge | 1000 m; exit within 60 m | crossbox.py:93, 103 | box neighbours | case (San Gabriels' corner) |
| `downhill` / `crossing` | 25 m, 100 cells, 600 steps, radius 10 | crossbox.py:109-125, 143 | entry from outside | case (Bouquet Canyon) |
| dead end -> lake | 400 m | crossbox.py:280 | which lake owns a dead end | case (Lake Mathews 338 m) |
| line in lake | 0.25 | crossbox.py:289 | NHDPlus outlet line | case (Matilija 49 %) |
| walks | 50 m / 3 km; 25 m / 3 km; lake buffer 30 m | crossbox.py:237-244, 300-309 | way on below a dam | none |
| outside river | 15 m, 150 m, 25 km, 60 m, 3 km, 6 km, 150/600 cells, 2 % | crossbox.py:479-584 | entry of outside rivers | case each (Snake at Moran, Santa Ana, Buffalo Fork, Lanier) |

### B.4 Reaches, names, drops, drainages

| constant | value | file:line | controls | how chosen |
|---|---|---|---|---|
| `MAP_MIN_KM2` | 1.0 | 05_score.py:12 | reach drawn | none |
| sea | 0.5 m, half the vertices | 05_score.py:89-90; `SEA_M` 05c_drainages.py:41 | sea links | reason |
| vote | 60 m, 2 of 3 points | 05_score.py:124-129 | name and NHD class | none |
| OSM names cache | 7 days | 05_score.py:134 | names | none |
| river rename | 1.5 cells, 20 reaches, 3 km, 0.5 | 05_score.py:174, 186, 201-202 | names along rivers | case (Snake, Castaic); effect counted on 12 maps |
| `SIDE_RATIO, SIDE_RIVER_KM2, SIDE_NEAR_M, SIDE_ALONG, SIDE_ON_RIVER` | 10, 50, 250, 0.6, 0.6; also 150 m, 6, 3x, 30 | 05_score.py:224, 239, 251, 258, 262 | side channels | effect counted ("about 720 reaches"); thresholds none |
| drop name / class | 80 m | 05_score.py:303, 306 | drop's stream | none |
| `DAM_LAKE_M` | 100; -3 / +6 / -3 m | 05_score.py:320, 330 | drop is a dam | case (Buford, Carters, Five Falls, Hinckley) |
| road crossing | 40 m | 05_score.py:339 | artifact | all (155 drops; 19 more tested) |
| fall on step | 50 m | 05_score.py:356 | mapped fall | all (14; nearest artifact 88 m) |
| dam point, known fall | 250 m, 200 m | 05_score.py:358 | status | none |
| known falls margin | 500 m | 05_score.py:52 | box overlap | reason |
| hillshade tint | 200-3100 m | 05_score.py:414 | colour range | none (LA's elevations, used in every area) |
| pass 1 | WIN 30, REACH 200, MIN_AREA 1.0, STEP_SLOPE 0.25, MIN_DROP 8; 0.03; 0.6 / 2.5 / 1.8; fill 2 m | 04_knickpoints.py:13-17, 119, 140-141, 148 | drops | LA ranges (README.md:952); fill rule: case (Santa Paula Creek) |
| pass 2 | BIG_AREA 10, WIN 30, REACH 200, MIN_DROP 3, MIN_EXCESS 2.5, RATIO 2.5, MIN_TREND 0.005, POOL_LOOK 60; 100 m; fill 2 m | 04b_bigcreek_steps.py:16-23, 105, 110 | short falls | none; fill rule: case (Middlebury River) |
| `MAJOR_KM2, FORK_KM2, SPLIT_KM2` | 25, 35, 120 | 05c_drainages.py:19-21 | drainages and forks | none |
| `PROMOTE_KM2, PROMOTE_INTO_KM2` | 100, 2000 | 05c_drainages.py:29-30 | own drainage | case (Hoback, Gros Ventre, Sespe, Mad, Maury) |
| `SEA_MAJOR_KM2` | 5 | 05c_drainages.py:42 | coastal drainages | case (Malibu canyons) |
| trunk rule | 30 cells, 150 m, 0.5-2 x, 8 lines, 40 lines; 300 km2, 300 m, 2 x | 05c_drainages.py:210-258, 321-334 | trunk follows NHDPlus | all (33 confluences on 11 maps) |
| reach -> cell | 5 x 5 cells | 05c_drainages.py:372-373 | reach's drainage | none |
| name share | 0.5 / 0.8 | 05c_drainages.py:382, 399, 406 | name vote | none |
| polygons | 50 m cells, 0.5 / 2 km2, 60 m | 05c_drainages.py:565-612 | outlines | none |
| relief, follow | 10 cells, block 5; 25 m, 0.6 | geomatch.py:91, 114 | access layers | none |

### B.5 Hard-coded places and per-area switches

| what | file:line | effect |
|---|---|---|
| 12 areas, 55 boxes, home points, sources | config.py:54-359 | everything |
| `elev_band=(700, 2300, 400)`, `artificial_path="other"`, `minor_label` (LA) | config.py:59 | first-pass score only; NHD artificial paths are "other" in LA and "perennial" elsewhere (config.py:372; 05_score.py:41-42) |
| `min_relief` 30 / 50 | config.py:187, 212, 292, 311, 328, 343 | trail and road filters |
| `clip_state="VT"` | config.py:165; areaclip.py:24, 62 | Vermont map ends at the state line |
| `water_temp_group="adirondack"` | config.py:291, 311, 328, 343; watertemp.py:66 | shared fit |
| `_TAILWATERS`: Cogswell Reservoir / West Fork San Gabriel River; Pyramid Lake / Piru Creek; Lake Sidney Lanier and Bull Sluice Lake / Chattahoochee River; Blue Ridge Lake / Toccoa River; Nantahala Lake / Nantahala River | scoring.py:153-166, chosen by `watertemp.AREA` at 169 | W = 1, cool = 1, no heat gate |
| `_DIVERSIONS`: seven LA diversions with lon/lat, creek name, USGS site | flowlib.py:393-402 | flag and W6 |
| `NAME_FIX`: 8 (box, name) pairs | 05c_drainages.py:46-65 | drainage names |
| `FORK_FIX`: 4 (box, drainage, fork) triples | 05c_drainages.py:67-76 | fork names |
| `has("tnc_flows")` | scoring.py:268; 05b_flow.py:70, 268; flowlib.py:40 | LA: flow scaled without water above dams; W5; NHDPlus split flags not used |
| late-summer rasters present (LA, Jackson) | flowlib.py:488-491 | bare rule can act |
| `has("nys_forest_preserve")` | geomatch.py:75 | Adirondack wilderness layer; "Primtive" typo patched at geomatch.py:82 |
| any waterbody named "*Lagoon*" | flowlib.py:151, 173, 206; crossbox.py:399 | pitted at any size, left out of the reservoir list (for Castaic Lagoon) |
| built-name word lists | scoring.py:202-204; 05c_drainages.py:44, 79 | channel factor; drainage names (two different lists) |
| gauge station-name lists | flowlib.py:465-468 | which gauges are plumbing |

---

## C. Rule layering

### C-1 The outlet pit is the root that ten later mechanisms work around. CONFIRMED (code); counts `[log]`.

`03b_stitch.py:577-578`: `outflow.append((r_, c_, int(fd[r_, c_])))` then `fd[r_, c_] = PIT`. Since `route_lake`
(2026-11-21) every lake cell already drains to that one cell, and 03b knows the cell its water goes on to. It still
cuts the path there, and then:

| # | compensation | file:line | measured |
|---|---|---|---|
| a | finds the dead ends again by scanning `flowdir.tif`, assigns each to a lake within 400 m | crossbox.py:429-435, 276-281 | |
| b | walks NHDPlus's outlet line 50 m at a time to a cell whose path leaves the lake | crossbox.py:288-324 | |
| c | falls back on NHD HR lines for ponds | crossbox.py:230-259, 325-329 | `[log]` 275 ponds over 11 areas |
| d | moves that cell back to "the top of each lake's routed way out", recomputing 03b's direction from `dem_cond.tif` | crossbox.py:335-391 | `[log]` 1,039 of 1,217 dead ends moved (85 %; 11 areas, adk_southwest's line lacks the figure) |
| e | adds the carried area down every path | crossbox.py:641-658; 05c_drainages.py:117-146 | `[log]` 1,655 links (1,095 km) drawn only because of it |
| f | 1 km2 floor counts it; names bridge the one-cell gap | 05_score.py:86-90, 161-176 | |
| g | drops count it, then a rule removes the dams it finds | 04_knickpoints.py:30-31; 04b_bigcreek_steps.py:32-33; 05_score.py:312-331 | |
| h | walks jump the pit; estimates found that way are floored | 05b_flow.py:166-167, 196-200, 564-571 | `[log]` 189 floored |
| i | pond basins rejoin the drainage below; lake basins share a name by vote, patched by `NAME_FIX` | 05c_drainages.py:422-423, 443-532, 46-60 | `[log]` 1,234 basins joined |
| j | Strahler order restarts at 1 below every lake and is estimated back; the line across the dam is drawn | 06_map.py:84-105, 106-113, 835-849 | |

For the 85 % of (d), pit + link returns the water to the cell the unpitted direction pointed at.
What the NHD walk still decides: whether a lake has an outflow at all (closed lakes stay closed), and the 15 % where
NHD's cell stands because the DEM's outlet is elsewhere (Stillwater, Raquette Lake; crossbox.py:346-349).
**Unlinked pits are not reported**: `[log]` 1,499 lakes were pitted and 1,440 dead ends carried, so at least 59 pitted
lakes pass nothing on (adk_high_peaks 18, adk_northwest 18, adk_southeast 7, LA 6, se_pa 5, adk_southwest 3,
n_georgia 2, jackson 1; the smokies carry one dead end more than they have pitted lakes) and no line names them
(G-7). Some are closed basins and right to stay closed; the list is what tells them apart.

Measure:
1. From `inflows.json["dams"]`, per link: is `(row, col)` the pit's pre-pit neighbour (moved) or not; for the rest, the
   distance from the pit to where NHDPlus's outlet line leaves the lake, and the km2 carried.
2. Every `flowdir == 254` cell inside a `still_water` lake that is not a key of `inflows.json["dams"][box]`, with
   `area_km2.tif` at the cell and whether an NHD HR line leaves the lake: the lakes below which a creek starts again.
3. In a clone, leave the outlet flowing where (1) says "moved" and compare the new `area_km2` with today's
   `area_full_km2` per reach.

### C-2 `05c_drainages.pond_links` repeats `crossbox._pond_outflow` and now joins 1 basin in 12 areas. CONFIRMED `[log]`.
05c_drainages.py:446-506 against crossbox.py:210-259 (same lake set, same 400 m, 30 m, 25 m, 3 km, same test). crossbox
took the rule over on 2026-11-20 (crossbox.py:269-273: "05c_drainages.py used these lines for the drainage names
only"). `[log]` "lake basins joined ...: N, M of them by the detailed stream lines": M = 1 of 1,234 (adk_northwest).
60 lines, plus a read of the national NHD waterbodies and the box's flowlines in every 05c run.

### C-3 The `full_dams` variant may have been overtaken by `main_path_trunk`. PLAUSIBLE.
`extra_lab = along(inflows(REGION, through_dams=True, ponds=False))` (05c_drainages.py:146) keeps pond water out of the
fork choice because "near-equal arms tipped the other way ... (the Soquee, 414 km2, over the upper Chattahoochee,
402)" and says "Which arm a drainage's trunk follows is decided by names another day; until then the drainages and
forks stay as they were" (141-145). `main_path_trunk` (165-297), added the same day, is that rule and names the same
Soquee case (169-172). If it holds, the third variant in crossbox (crossbox.py:599-601, `ponds=` at 631-638, the
"pond" kind and `pond_dead` at 408, 328-329, 439) can go. Measure: run 05c with `extra_lab = extra_full` in all 12
areas and diff `stream_drainage.csv` (`drainage`, `fork` per `sid`).

### C-4 Three in-lake tests and three "reservoir" patches; the shore cut already decides it. CONFIRMED (code).
- 2026-11-19: no line of its own and half in an NHD lake -> reservoir (05b_flow.py:576-582);
- 2026-11-20: in a lake that holds a pit, whatever it matched (583-586, `in_wet_lake` 112-113);
- 2026-11-20: in a lake of the lakes layer (592-598, 121-132);
- 2026-11-21: `05_score.py:105` cuts every link at the same outlines and computes `_wet` per piece
  (flowlib.py:303), used only to exclude lake pieces from naming (`in_water`, 05_score.py:116, 232, 242) and not saved.

05b then recomputes the shares against two outline sets (05b_flow.py:93-109 and 121-132), with a grouping of touching
NHD pieces (94-97, 104-106) that a cut against the union makes unnecessary. `[log]` 7,922 + 447 reaches end
"reservoir". The print at 05b_flow.py:591 says "with no model segment of their own" but counts `in_wet_lake` too.
The only reaches the three tests treat differently from "piece lies in the water": a reach on its own model line,
inside an NHD lake with no pit, not in the layer. Measure: save `in_water` from 05_score; cross-tabulate against
05b's final `water_class == "reservoir"`; the off-diagonal cells are all this code still decides.
A lake is "wet" only if its pit is in this box (`wet_lakes(wb_, REGION)` reads one box's `flowdir.tif`,
flowlib.py:232-243), so a lake across two boxes is wet in one and not the other; the layer rule covers most of that.

### C-5 "Which water is a lake" is decided five ways. CONFIRMED (code).
`still_water()` (flowlib.py:135-153: 03b's pits at 03b_stitch.py:521, 05c at 458), `reservoirs()` (156-180: crossbox,
05b, the shore cut), the lakes layer through `layer_counted()` (199-207), `lakes_off_map.gpkg` (03b_stitch.py:632-638),
`wet_lakes()` (232-243). `still_water` and `reservoirs` differ only by lagoons, bounds and a cache keyed by box names
(F-2); if that cache is stale, 03b pits a lake that crossbox has no outline for and its water is not carried.
Measure: per area, the lakes in `still_water` not in `reservoirs()` + lagoons, and the reverse.

### C-6 Five separate "never below NHD's class" rules (A.3). CONFIRMED (code); counts `[log]`.
Each was added for one case (Ticonderoga creeks, Smith and Skinner brooks, Partridge Brook, Dry Creek, Willow Creek).
`evidence(box_df.assign(comid=np.nan, flow_src="none"), box_div)` is recomputed at each (05b_flow.py:521, 558, 570).

### C-7 The off-map lake rule in 03b created a loss that 05b restores. CONFIRMED (code).
03b removes stream cells on lakes that drain off the map (03b_stitch.py:595-605); 05b then finds no modelled reach
below their creeks and adds `lake_line`, `LAKE_LINE`, `LAKE_USED`, `FROM_LAKE`, `lake_floor` (05b_flow.py:346-397,
400-430, 513-525), about 75 lines. `[log]` 569 reaches take a lake's line (central_vt 177, adk_high_peaks 154,
adk_southeast 136). The line is the lake's whole basin, so its unit-area flow says little about a 2 km2 creek;
`lake_floor` makes it raise-only. Measure: for `LAKE_USED` reaches, final `water_term` against NHD's value: how many
are raised above their NHD class, by how much.

### C-8 The 2026-11-21 lake routing lowered LA creeks below dams; scoring raises them again. CONFIRMED (code).
05b scales LA flow by `area_edge_km2`, without water from above any pitted lake (05b_flow.py:63-72). Once `route_lake`
stopped lake shores leaking into that area, creeks below lakes read drier; W4 and W5 were added in scoring
(scoring.py:248-273 name Piru Creek, Willow Creek, Bear Creek). The floor belongs with the other four in 05b.
`[snapshot]` 46 + 111 reaches.

### C-9 Counting carried water in the drop detectors found the dams; a second rule removes them. CONFIRMED (code).
04_knickpoints.py:30-31 -> "found the dams themselves: Buford Dam as a 49.5 m waterfall-like step" (05_score.py:312-319)
-> `dam_lake` (320-331). Measure: drops with `dam_lake` true and `dam_m >= 250`.

### C-10 `streams_scored.gpkg` is written in lon/lat, and every later step snaps back. CONFIRMED (code).
`s_ll.to_file(...)` (05_score.py:369, 390). Then: "+-3e-10 m after the trip through EPSG:4326: rounded, not truncated
(truncation put about half of them one row or column off, 2026-11-20)" (05b_flow.py:173-175);
`np.round(end / RES).T * RES` (05c_drainages.py:553); a 5 x 5 search (05c_drainages.py:368-375). `drainages.gpkg` is
already kept "in the area's own CRS" (05c_drainages.py:10-12).

### C-11 Names: a 3-point vote, then two repair passes for its two errors. CONFIRMED (code); counts `[log]`.
Vote (05_score.py:124-132); "names along rivers" for a river reach that took a side creek's name (149-207; 1,243
renamed); "small reach beside a river" for the opposite (209-278; 88 renamed, 366 unnamed, 214 side channels).
`match_points` exists to stop exactly this ("Stops a small tributary grabbing the main stem beside it",
flowlib.py:108) and NHDPlus lines carry `gnis_name`. Measure: for reaches with `flow_src == "model"`, the share whose
final `name` equals the matched line's `gnis_name`, and how many of the 1,243 + 668 are such reaches.

### C-12 `HALO` is 5 km, so `mend_seams` re-conditions pieces up to 60 km across. CONFIRMED (code and log).
03_hydrology.py:32 against 03b_stitch.py:193-333 (about 150 lines with its helpers). `[log]` last 03b runs:
adk_high_peaks one dead end of 1,175.7 km2 in Lake Champlain, "621,071 cells re-routed (DEM conditioned again 48 km
across)", for a lake whose stream cells are then deleted as off-map; adk_northwest at least three (85.4, 2.1 and
1.2 km2); central_vt one "NOT mended" at the map corner, which the next step reads as water leaving the map
(03b_stitch.py:505-519). config.py:101 ("No big lake may lie across an edge between two boxes") and config.py:281-282
("Boxes inside one map may cut lakes: 03b routes them as one surface") contradict each other.

### C-13 `stitched.json` and the not-stitched branches. PLAUSIBLE (dead if every box is listed).
`json.dump(sorted(set(old) | set(done)), fh)` (03b_stitch.py:679) only grows; `stitched()` gates crossbox.py:151-164,
421-427, 433. Measure: `set(stitched.json) == set(REGIONS)` in each area.

### C-14 `NAME_FIX` / `FORK_FIX` entries written before the trunk and lake-routing changes. PLAUSIBLE.
One entry was already retired in a comment (05c_drainages.py:68-69). "Gorman Creek comes in beside the dam and took
the vote" (47-48) and "the lake's centreline carries no river name there" (57-59) describe the routing before
`route_lake`. The fix is keyed by `(REGION, name)` (401, 406, 434), so any drainage of that box with that name is
renamed. The vote they patch ranks reaches by `named.area_km2` (05c_drainages.py:389, 391), the box's own area, though
the comment at 141-146 says names are picked on the carried area (`area_full_km2` is only added at 557).
Measure: log each key when it fires in a full rebuild; a key that never fires is dead.

### C-15 Tailwaters are found by river name and a hand-set elevation; the routing knows the answer. PLAUSIBLE.
`on = dam.eq(d) | (s["name"].eq(river) & (s.elev_m <= top) & (big >= 20) & dam.eq(""))` (scoring.py:184), with six
elevations set per place and one re-set for a single reach (scoring.py:156-159). The name-and-elevation half exists
because `below_dam` is set only on a reach's own model line (`.where(df.flow_src == "model")`, 05b_flow.py:479) and
only while the lake holds half the drainage (flowlib.py:362). "Downstream of this lake's outlet, to the next lake" is
what the dam link and the D8 path give. `[snapshot]` 362 reaches are flagged (n_georgia 220, LA 92, smokies 50).
Measure: the set flagged today against the main-stem reaches on the D8 path below each listed dam's link, down to the
next pitted lake.

### C-16 NHD stores some lakes as touching pieces; each piece gets its own pit, link and share. CONFIRMED (code).
03b pits per NHD polygon (`for i, (a, r_, c_) in best.items()`, 03b_stitch.py:561-579), so Palisades' four pieces
(05b_flow.py:77-81) give pits inside the reservoir, each needing a link; 05b then groups the pieces again
(05b_flow.py:94-97). Dissolving touching polygons once, where the lakes are read (flowlib.py:135-180), removes both.
Measure: per area, lake polygons of 8 ha that touch another, and the pits that lie inside the dissolved outline.

### C-17 A model line flagged "in:lake" makes a reach a reservoir, a second rule un-flags it, a third re-flags. CONFIRMED.
`water_term` reads `below_dam.str.startswith("in:")` (flowlib.py:378-380) from the line's flag
(flowlib.py:345-349); 05b un-flags reaches lying outside the water and decides "below the lake or beside it" by
projecting onto the line (`below_lake`, 05b_flow.py:139-149, 487-489); then C-4's rules flag by the reach's own
position. `[log]` 462 reaches are read as creeks this way, 105 of them below the lake. With the reach's own position
known from the cut, only "is this reach on the line's stretch below the lake" is still needed from the line.

---

## D. The same logic written more than once

| # | what | where | could save |
|---|---|---|---|
| D-1 | D8 code table | crossbox.py:26; flowpath.py:5; 04_knickpoints.py:37; 03b_stitch.py:52-57; 05b imports both (05b_flow.py:34-35) | 3 definitions |
| D-2 | "follow D8 from a cell" loop | crossbox.py:109-129, 156-163, 192-200, 359-367, 567-576, 651-657; 05b_flow.py:184-204, 380-396; 05c_drainages.py:117-127, 210-223; 03b_stitch.py:245-259, 425-437; 04_knickpoints.py:57-68, 106-110; flowpath.py:31-42, 64-71; 06_map.py:135-143 | about 15 copies, 120 lines |
| D-3 | pointers, walk, union of runs, run length | 04_knickpoints.py:36-68, 81-95, 105-110 against flowpath.py:8-71 ("shared by the step detectors"; 04 does not import it) | 45 lines |
| D-4 | carried area down each path | 05c_drainages.py:117-127 `along()` against crossbox.py:641-658; reach total at 05_score.py:115 and 05c_drainages.py:557 | 12 lines |
| D-5 | pond outflow from NHD HR lines | 05c_drainages.py:446-506 against crossbox.py:210-259 | 60 lines (C-2) |
| D-6 | "sample a mapped line until the D8 path ends elsewhere" | crossbox.py:243-255, 305-324, 499-517, 541-558; 05c_drainages.py:485-501 | 5 copies, 60 lines |
| D-7 | NHD waterbody read with the same filter | flowlib.py:135-153, 156-180; crossbox.py:399-403 | 25 lines |
| D-8 | NHD HR line read, ftype 460 / 558 / 334 | 03b_stitch.py:46, 341-354; crossbox.py:210-227; 05c_drainages.py:466-474 | 20 lines |
| D-9 | line vertex -> grid cell -> reach | 05_score.py:295-300; 05b_flow.py:168-181; 05c_drainages.py:190-203 (the same reverse-and-unique trick as 05b); 05c_drainages.py:368-375 | 3 copies, 35 lines |
| D-10 | rank "drainage first, then distance" | flowlib.py:128; flowlib.py:629; watertemp.py:238-239 | 3 copies of one expression |
| D-11 | Strahler order of a reach | 05_score.py:117 and 05c_drainages.py:379-380; comments disagree: "they always sample the channel cell itself" (05_score.py:62) against "the middle vertex ... can sit beside the channel" (05c_drainages.py:378) | one of the two. Measure: `order != strahler` per reach, by reach length |
| D-12 | NHD class values | scoring.py:224; 05b_flow.py:509; 05_score.py:283 | 2 copies |
| D-13 | `band()` | scoring.py:77-78; 05_score.py:281-282 | 2 lines (with A2-1) |
| D-14 | conditioning a DEM | 03_hydrology.py:67-71; 03b_stitch.py:231-242; `FLAT_EPS` twice | 10 lines |
| D-15 | steepest neighbour | 03b_stitch.py:60-78; crossbox.py:376-380 | (C-1 d) |
| D-16 | main stem above a reach | 05_score.py:180-185 `main_up` and 227-231 `stem_up` ("(main_up above)"), same key | 5 lines |
| D-17 | share of a line inside a lake | 05b_flow.py:99-109, 124-132, 367-369; flowlib.py:303, 345-348; crossbox.py:288-289 | (C-4) |
| D-18 | interior dead-end test | crossbox.py:429-430; 05c_drainages.py:456-457 | (C-2) |
| D-19 | "which way out of the box" | crossbox.py:65-81 `exit_points`; 05b_flow.py:227-233 ("as crossbox.exit_points() has it") | 8 lines |
| D-20 | built-conveyance word lists | scoring.py:202-203; 05c_drainages.py:44 (different words) | one list |
| D-21 | same file read twice in one script | `nhdplus_v2.gpkg` at 05c_drainages.py:185 and 319; `streams_scored.gpkg` at 189 and 366; `area_streams.csv` at 05b_flow.py:67-72 and 626-627; `gauges_daily.csv.gz` at 05b_flow.py:56 (read in full in the 11 areas with no diversion) and through flowlib.py:535; `lakes.gpkg` at 05_score.py:105 and 324 | run time |
| D-22 | point -> stream snapping, five tolerances | 80 m (05_score.py:303, 306, two joins for one answer; 05b_flow.py:644), 150 m (flowlib.py:106; watertemp.py:235), 200 m (watertemp.py:198), 300 m (flowlib.py:538, 620) | one helper |
| D-23 | the score's constants written out again | scoring.py docstring 3-68; `fish_score_diagram.py:48-49, 66, 104-173` (does not import scoring); README | drift |
| D-24 | WQP download and parse; mi2 -> km2 | watertemp.py:147-171 and data/validate_heat.py:73; `* 2.58999` at flowlib.py:527, data/validate_flow.py:17, data/validate_flow_areas.py:23 | small |

---

## E. Dead code

| # | what | file:line | check |
|---|---|---|---|
| E-1 | unused import `ROOT` | crossbox.py:24 | ast: no use |
| E-2 | unused import `from config import SHARED` | crossbox.py:396 | grep: no use |
| E-3 | unused imports `re`, `cm` | 05_score.py:3, 6 | ast |
| E-4 | unused import `MIN_RESERVOIR_KM2` | 05b_flow.py:37 | ast |
| E-5 | parameter never read: `lake_water(region)` ("`region` is kept for the callers; nothing is read per box") | flowlib.py:246-253 | read |
| E-6 | parameter never read: `relief_at(..., root, ...)` | geomatch.py:91 | read; callers pass `ROOT` |
| E-7 | parameter never passed: `fit(write=True)` | watertemp.py:378 | grep: no `write=` |
| E-8 | parameter never passed: `Walk(..., box=None)` and its `if box else {}` | 05b_flow.py:163, 167 | both callers pass a box (263, 340) |
| E-9 | parameters never varied: `share` in `below_dam_comids`, `below_diversion_comids`; `first_year`, `min_summers` in `gauge_summers`; `min_m`; `radius`; `steps`; `max_cells`; `k` | flowlib.py:341, 405, 434, 263, 279; crossbox.py:109, 143; 03b_stitch.py:174, 416 | grep |
| E-10 | first-pass score, `ELEV_BAND`, reach `road_m` / `trail_m` | A2-1 | |
| E-11 | 0.10 for no data | A2-2 | |
| E-12 | `order` | A2-3 | |
| E-13 | Natural-Flows branch of `minor_arms` | A2-6 | |
| E-14 | `pond_links` | C-2 | 1 of 1,234 |
| E-15 | "no lakes layer" branches: all 12 areas are in `BUILT` (05d_lakes.py:42-43) | 05b_flow.py:133-134; flowlib.py:193-194; 05_score.py:323 | read |
| E-16 | not-stitched branches | C-13 | to measure |
| E-17 | CLI box filter `only = set(sys.argv[1:])` | 03b_stitch.py:668-672 | no driver passes a box |
| E-18 | a print's own computation | 05b_flow.py:613-616 | read |
| E-19 | comment for a removed entry | 05c_drainages.py:68-69 | read |
| E-20 | `globals().get("via_final", VIA[False])` standing in for an `else` | 05b_flow.py:567 | read |
| E-21 | `run_la_refresh.sh`: a one-off for the 2026-11-18 Overpass outage, with hard-coded range lists | scripts/run_la_refresh.sh:2-8 | read |

Env-var switches in these files: only `AREA` and `REGION` (config.py:361, 384). No one-off switch found.

---

## F. Cache keys

| # | file | written / read | keyed by | expires | stale after a config change? |
|---|---|---|---|---|---|
| F-1 | `<area>/_shared` derived `inflows.json` | crossbox.py:676-692 | `VERSION` + mtime and size of every box's `flowdir.tif` and `nhd_flowlines.gpkg`, `reservoirs.gpkg`, `nhdplus_v2.gpkg`, `stitched.json` (crossbox.py:203-207) | any of those changes | **Yes for code**: `VERSION = 17` is bumped by hand; a change to `_dam_links`, `MIN_KM2`, `OUTFLOW_NEAR_M` without it reuses the old links. Not keyed: `dem_cond.tif`, `area_km2.tif`, `dem_filled.tif` (covered through `flowdir.tif`), the national NHD file |
| F-2 | `flow/reservoirs.gpkg` + `.regions.json` | flowlib.py:156-180 | `set(json.load(open(meta))) == set(REGIONS)`: box **names** | never otherwise | **Yes. CONFIRMED.** Moving a box edge keeps the names; so does a change to `MIN_RESERVOIR_KM2` or the lagoon rule. (The owner clears it by hand; central_vt's was rewritten 11-20 16:11 after its edge moved) |
| F-3 | `flow/nhdplus_v2_paths.csv` + `.regions.json` | flowlib.py:307-338 | box names | never otherwise | Yes, as F-2 (and 02b's `nhdplus_v2.gpkg` the same way) |
| F-4 | `_shared/cache/wqp_*_temp.csv` | watertemp.py:72-90 | file name only | 30 days | **Yes**: the bounds are in the request, not in the key. `[raw]` on 11-21 the cached stations come within 4 km of every side of the current envelope in 11 areas; LA's stop 27 km short of its north side and 8.5 km short of its west side (empty country or an older envelope: not settled) |
| F-5 | `_shared/prism_tmean_aug.tif` | watertemp.py:94-119 | its bounds cover the area's | when the area grows | No |
| F-6 | `_shared/water_temp_fit.json` | watertemp.py:398-400, 414-420 | none | next successful `watertemp.py` | **Yes. CONFIRMED.** A failed run leaves the old record in use while the driver logs "the thermal term stays neutral" (run_late.sh:23); G-5 |
| F-7 | `_shared/water_temp_sites.csv` | watertemp.py:390-392, 356-361 | none | next run of that area | **Yes. CONFIRMED and observed**: G-6 |
| F-8 | `<box>/osm_waterways.gpkg` | 05_score.py:133-147 | age under 7 days | 7 days | Yes within the week (box moved); no `REFRESH` switch as the other OSM caches have |
| F-9 | per-range `hike_ / sun_ / context_ / flow_ / area_*.csv` | scoring.py:86-118 | `set(t[key]) != set(mine)`, where keys are `f"{REGION}:s{i}"` row numbers (05_score.py:380) | never | **Yes. CONFIRMED.** The key set is {s0..sN-1}, so the test sees only a change in the *number* of reaches; the mtime test prints a NOTE and goes on (scoring.py:103-104). 05b's own test is the same (05b_flow.py:267). The drivers rerun every writer after 05_score; a hand rerun of 05_score that keeps the count attaches old values to renumbered reaches |
| F-10 | 05b reading its own box's `area_streams.csv` | 05b_flow.py:67-72, 626-627 | none | - | Yes: a stale file maps by `sid`; missing ids fall back to the box area silently (`more.where(more >= 0.01, 0.0)`) |
| F-11 | `stitched.json` | 03b_stitch.py:675-679 | - | never shrinks | old box names stay |
| F-12 | `lakes_off_map.gpkg` | 03b_stitch.py:632-638 | rewritten or removed each run | - | No |
| F-13 | `late_summer_ndvi_<year>.tif` | flowlib.py:471-474 (written by 02g) | box name and year | kept for good | A moved box reads no data past the old grid (`boundless=True, fill_value=-32768`, flowlib.py:499): the bare rule cannot act there, the safe side |
| F-14 | `wilderness.gpkg` + `.extent.json` | geomatch.py:53-88 | extent covers the area | when the area grows | Not for a change of `has("nys_forest_preserve")` |
| F-15 | `tl_2024_us_state.zip` | areaclip.py:27-32 | exists | never | No (static) |
| F-16 | `_MINOR` in memory | flowlib.py:11, 24-26 | `(id(v2), len(v2))` | process | No |
| F-17 | numba caches | 03b_stitch.py:81, 125 | source file | numba | No |

---

## G. Bugs and accuracy risks

**G-1 Outside LA the flow class is a drainage-area threshold; in NE Connecticut it marks a quarter of the creeks
below year-round. CONFIRMED (mechanism, `[raw]`); the size of the harm is PLAUSIBLE.**
05b_flow.py:470-477 with flowlib.py:369. The flow table outside LA is EROM's long-term monthly mean for each line
times one yearly index for the whole area (02b_download_flow.py:201-232), and a reach's flow is that times its
drainage ratio. So whether a creek reaches 0.1 cfs is set by its drainage and its line's unit runoff; nothing in it is
measured on the creek. The line falls at 2.40 km2 in ne_ct (1.56-3.67 across model lines). `[snapshot]` ne_ct: 785 "usually flows" + 173 "seasonal" of 3,880; 892 NHD-perennial creek reaches below
year-round (median drainage 1.7 km2, median W 0.71), 512 of them with trout evidence. The log's own check says the
eastern gauges never test this line ("Only one gauge fell under the 0.1 cfs 'flowing' line", MULTI_AREA_LOG.md:427)
and that all 200 flowing gauged creeks outside LA are rated year-round (2735-2738): the gauges are on bigger water.
Scenario: a 1.5 km2 Connecticut brook with trout records, perennial on NHD, shown "usually flows" and scored 29 %
lower because 0.1 cfs / 0.042 cfs per km2 = 2.4 km2.
Measure: outside LA, NHD-perennial creek reaches classed below year-round, by area and drainage; and the same classes
with the threshold set per km2.

**G-2 Trout x0.5 outranks a trout-water designation and rests on one sample. CONFIRMED.**
scoring.py:199 `np.select([pos, neg, s.trout_water.notna()], [1.2, 0.5, 1.2], 1.0)`. `[snapshot]` 267 reaches; 117 in
ne_ct are designated trout water; the ne_ct creeks marked down include Quanduck Brook (19 reaches under two
spellings), Great Meadow Brook 12, Bigelow Brook 10, Little River 8; LA's are Mill Creek 26, East Twin Creek 17,
Santa Anita Wash 9. 76 have an older "found" record. The same reaches stay exempt from the other rules because those test
`trout_water.notna()`. Measure: rows with `trout_factor == 0.5`, split by `trout_water.notna()` and `trout_found.notna()`.

**G-3 "unmapped" is mostly a failed vote, and it is used as evidence. CONFIRMED (code); counts `[snapshot]`.**
`s["flow"] = vote(nhd_k, "flow").fillna("unmapped")` (05_score.py:132): no NHD line within 60 m at two of three points
reads as "NHD maps no stream". `[snapshot]` 8,433 creek reaches are "unmapped"; 808 drain 20 km2 or more (Snake River
33, Santa Clara River 17, Whitewater River 16, Schuylkill River 12, Raquette River 9); 1,639 sit on an NHDPlus line of
matching drainage. Effects: 76 of the 808 have no flow data and get W = 0.15 (59 unnamed LA washes, Temescal Wash 7,
Steuben Creek in adk_southwest: 87 km2, 1.2 km, fish 11); 119 bare-channel reaches have "unmapped" as their NHD
condition, 29 of them draining 20 km2 or more (Santa Clara River 5, Cuyama River 2, Warm Creek 2, San Gorgonio
River 1); and the 05b floors protect nothing at 0.15.
Measure: "unmapped" reaches with an NHD HR line within 150 m along half their length, by area.

**G-4 Burn: unknown severity gets the full penalty, and the factor steps on New Year's Day. CONFIRMED.**
scoring.py:124 and 74. Counts at L9 and A.4-10. Scenario: a reach whose buffer touches the edge of a 2024 perimeter,
no BAER map: x0.4 until 31 December 2026, x0.7 the next morning.

**G-5 A failed water-temperature fit leaves the previous one in force and the log says otherwise. CONFIRMED.**
`run $a "" watertemp || echo "NOTE $a: no water-temperature fit; the thermal term stays neutral"` (run_late.sh:23);
`fit()` writes only on success (watertemp.py:393-400); `fit_record()` reads whatever file is there (414-420).
Scenario: the Water Quality Portal is down; the area keeps a fit made for older reaches and lake shares.

**G-6 The Adirondack group fit depends on the order the four maps are built in. CONFIRMED, observed.**
`_group_fit` reads the other maps' site tables "as their last runs wrote them" (watertemp.py:353, 356-361), and each
table's `lake` column comes from that map's current reaches (215-241). run_late.sh fits each area once, in turn.
On 2026-11-21 adk_northwest's record at 23:23 was `ok: false` (every reach 18.39 C, cool = 1); a rerun at 23:33,
after adk_southeast's table was rewritten at 23:31, gave `ok: true, group: adirondack, terms: [elev_km, lake]`.
All four driver runs logged for that map ended "NO SKILL" with no group fit (late_adk_northwest.log:85, 214, 353, 498);
the 23:33 rerun is not in the driver's log, so the group fit the docstring describes (watertemp.py:49-50) comes only
from a hand rerun after the other three maps. Fix shape: fit the group once, after all four tables exist.

**G-7 Dead ends that are not linked are never listed. CONFIRMED (no such print in crossbox.py:394-628).**
The only line is "N reservoir dead ends carried past their dams" (crossbox.py:622-624). At least 59 pitted lakes are
not carried (C-1). Scenario: NHDPlus has under a quarter of its outlet line in the lake (crossbox.py:289) and no HR
line starts inside the 30 m buffer; the creek below starts from nothing, is under 1 km2, and is not drawn. A second
way: "the creek leaves the box first: leave it closed" (crossbox.py:315-317) for a lake near a box edge.

**G-8 The drivers go on after a failed hydrology step. CONFIRMED.**
`|| echo "FAILED ..."` with no stop (run_base.sh:19-20; run_rebuild_a.sh:22-23), then `./run_mid.sh $a` and
`./run_late.sh $a` unconditionally (run_rebuild_a.sh:37-39). 03b takes any `dem_cond.tif` that exists
(03b_stitch.py:443), so a box whose 03 failed is routed on its old surface, or left out of its group as if the map
ended there. The lock is `until mkdir $LOCK` with no trap (run_base.sh:24-30; run_rebuild_a.sh:26-33): a killed chain
leaves `data/.hydro.lock` and every later chain waits forever.

**G-9 Two LA boxes overlap by 4 km2. CONFIRMED (config).**
san_gabriel `bbox=(365000, 3778000, 450000, 3820000)` (config.py:66) and santa_monica
`bbox=(320000, 3764000, 366000, 3782000)` (config.py:69) share x 365-366 km, y 3778-3782 km; config.py:14-15 says
"Boxes of one area must not overlap, or streams get drawn twice". Their borders meet in two points, so they are not
one routing group (crossbox.py:92-95), nothing links them, and the union's outer boundary does not include the
overlapped edges, so a river crossing there is not an "outside" river either (crossbox.py:450-452). The strip is the
south-east San Fernando Valley; by its coordinates the Los Angeles River below Sepulveda Dam runs through it (not
checked on the data). Urban concrete, so little effect on trout scores.
Measure: reaches of both boxes whose middle lies in the strip, and the Los Angeles River's `area_full_km2` on either
side of x = 366000.

**G-10 `pond_dead` mixes cell numbers of different boxes. CONFIRMED, latent.**
`ponds, pond_dead = [], set()` once for all boxes (crossbox.py:408); `pond_dead.update(dead)` holds flat indices of
one box (329); `"pond" if o in pond_dead else "dam"` tests another box's index against it (439). A dam link whose
cell number equals a pond's in an earlier box is tagged "pond" and left out of the fork choice. Odds are small
(about 300 ponds against 20-40 million cells).

**G-11 `05c`'s reach cell takes the biggest drainage within 2 cells. PLAUSIBLE.**
05c_drainages.py:368-375: `int(np.clip(r, 0, H - 1))` truncates a coordinate that went through lon/lat, then
`np.argmax(win)` over 5 x 5 cells. A reach of five vertices or fewer has its middle within 2 cells of the stream it
joins and takes that stream's drainage, fork and order. Measure: D-11.

**G-12 A dry gauge's record reaches upstream of the gauge. PLAUSIBLE.**
`gauge_below = area_full >= 0.9 * gauge area` (flowlib.py:605) is a drainage test, not a position test. A reach above
a diversion with 90 % of the gauge's drainage, on the gauge's own NHDPlus line, takes the dry record of the gauge
below the diversion; the older diversion rule guards exactly that (`above = key.map(div_area) > df.area_km2 + 0.05`,
05b_flow.py:495). `[raw]` four of the six gauges behind the listed diversions (Lytle, Plunge, City creeks, San Jacinto
River) are current, pass `creek_gauges`' name filter and so also feed W3; `[snapshot]` W3 acts from City Creek's
(1 reach) and the San Jacinto's (3).
Measure: reaches with `water_rule == "gauge"`, lowered, lying upstream of their gauge along the line.

**G-13 The name and class vote reads every NHD flowline type. CONFIRMED (code); effect PLAUSIBLE.**
`nhd = gpd.read_file(f"{RAW}/nhd_flowlines.gpkg")` unfiltered, `nhd_k = nhd[["gnis_name", "flow", "geometry"]]`
(05_score.py:24, 41-42, 130). 03b and crossbox keep only ftype 460 / 558 / 334. `[raw]` the san_gabriel box has
1,123 km of underground storm-drain pipeline (fcode 42823) against 427 km of perennial stream. A canyon reach with a
pipe or canal nearer than its own line at two of the three points takes that line's name, class "other" and x0.2.
`[snapshot]` 10 reaches carry aqueduct names and 2 storm-drain numbers. Also fcode 46000 (stream, class not stated; 459 km in the Smokies' le_conte box) and connectors
map to "other" = 0.3. Measure: reaches whose voted line has ftype 428, 336 or 566.

**G-14 Overpass answers that timed out are taken as complete. CONFIRMED (code).**
`if r.ok and "elements" in r.json(): return r.json()["elements"]` (geomatch.py:18-19). Overpass returns HTTP 200 with a
`remark` ("runtime error: Query timed out") and partial elements. 05_score.py:137-143 then writes a short name list
for a week. Scenario: half a box's creek names missing from one build, with no error.
The same step also fails outright in an outage: once the file is over 7 days old 05_score.py:134-138 calls Overpass,
`overpass()` raises after 14 tries (geomatch.py:23), and run_mid.sh stops the area, though the old file is still on
disk. Reach names (and through them drainage names) also change from week to week with OpenStreetMap.

**G-15 Comments that no longer match the code. CONFIRMED.**
- watertemp.py:69 "the score falls back to the air temperature alone": no such fallback exists (scoring.py:292-294).
- watertemp.py:4 "since 2000 or the cache's start": the request starts 1995 (watertemp.py:86), nothing filters later.
- flowlib.py:461 "this far along its model line": the test is straight-line distance (flowlib.py:597-598).
- scoring.py:151 "takes the elevation part of the thermal term in full": it is the water-temperature part.
- scoring.py:39 "Where there's no estimate the term is neutral (0.5)": not where the fit has no skill (293).
- 03_hydrology.py:33 "4 km of flat is 0.4 mm": 400 cells x 1e-9 m = 0.4 micrometres.
- 05c_drainages.py:436 and crossbox.py:10-11 credit the lake pits to 03_hydrology.py / pysheds; 03b makes them.
- 05b_flow.py:185-186 "over up to 4 km of unmapped channel (drainage < 1 km2 gaps don't exist downstream)".
- 05_score.py:1 "(perennial, remoteness, trout-elevation)".
- flowlib.py:22-23 "(California)" (A2-6).

**G-16 Gradient is measured to the second-to-last vertex and divided by the whole length. CONFIRMED, small.**
`((sample(dem, starts) - sample(dem, own_end)) / s.length * 100)` (05_score.py:120): a two-vertex reach always reads 0,
a three-vertex one half. `[snapshot]` 966 of 1,551 creek reaches of 30 m or less read 0 %. At most 1.5 points.

**G-17 A river from outside is tested against the box its flowline *ends* in. PLAUSIBLE.**
`b = next((r for r in regions if boxes[r].buffer(1).contains(last)), None)` (crossbox.py:481), then
`crossing(b, fd_b, T_b, pt.x, pt.y, away)` with the entry point `pt` (521). Where the entry flowline crosses into a
second box before it ends, `pt` is outside `b`'s grid, `crossing` yields nothing and the river is not carried.
Measure: NHDPlus lines of 10+ km2 crossing the outer boundary inward whose entry point and last point lie in
different boxes, and whether `inflows.json` has an "outside" entry for them.

**G-18 Things checked and found sound.**
- Truncation in `05_score.sample()` (05_score.py:19-21) is exact: the lines are read in the area's CRS and every box
  edge is a multiple of 10 m (checked for all 55 boxes).
- The `via` flag (05b_flow.py:421 `via[i] = lk_ or from_lake[j]`) does not carry `via[j]`, but pysheds emits links
  upstream-first and the only order inversions are at lake jumps, which set `lk_` themselves. Correct today, fragile.
- `flow_years` counts a missing year as dry (05b_flow.py:477); `[raw]` the LA, ne_ct and Jackson tables have no empty
  cell. LA's 2026 has 3 of 4 months, which the script reports.
- No int overflow: `acc` is int32 cells (largest group 254 million), area is made float64 first
  (03b_stitch.py:624-627); flat indices are int32 per box (largest 38.4 million).
- No unit or CRS mix-up found. Two columns named `km2` hold m2 and are only sort keys (crossbox.py:279;
  05c_drainages.py:463). n_georgia's west boxes are 3.9 degrees off their zone's meridian: +0.12 % length.
- No bare `except: pass`; the two retry loops raise in the end (geomatch.py:20-23; flowlib.py:330-332).
- Ties: `match_points` sorts stably (flowlib.py:129). `_pond_outflow` takes the first qualifying line in STRtree
  order (crossbox.py:238), arbitrary but repeatable.

---

## Not covered, and limits of this pass

- Nothing was run. No rule was switched off to see what moves: every "Measure:" line above is still to do, and the
  `[snapshot]` counts must be re-taken on a finished build.
- `06_map.py`, `05d_lakes.py`, `maplakes.py`, `08_hike.py`, `10_sun.py`, `11_context.py`, `02b_download_flow.py`,
  `12_profiles.py` were only grepped, for who reads what. Their own rules (how a trout record reaches a reach, how
  approach times are made, the map's lake drawing) are the other reader's.
- The conditioning itself (pysheds `fill_depressions`, `resolve_flats`) and the numerical side of `mend_seams` were
  read, not tested. DEM nodata cells come out of 03 as -99999 in `dem_cond.tif` (03_hydrology.py:64, 83) and 03b reads
  them as ground (03b_stitch.py:472-473), which makes each a pit; whether any box has such cells was not checked.
- `data/stream_burning/` was used only for its README's account of what was measured before the lake routing went in.
- The water-temperature fits were changing while this was written (adk_northwest's record was rewritten at 23:33).

## Appendix: measurements already in hand

`[log]` last mid run per area (sum of boxes):

| area | reaches | kept by carried water (links / km) | shore cuts | lake reaches -> reservoir (NHD / layer) | pond basins joined (by 05c's own lines) | off-map lake line | via-lake floor | far (scaled / floored) | edge area (more / kept / not kept) |
|---|---|---|---|---|---|---|---|---|---|
| la | 18,065 | 67 / 44 | 196 | 401 / 3 | 18 (0) | 37 | 92 | 21 / 40 | 621 / 48 / 0 |
| jackson | 10,713 | 55 / 34 | 159 | 463 / 7 | 19 (0) | 2 | 1 | 185 / 0 | 1,516 / 63 / 8 |
| n_georgia | 15,199 | 110 / 67 | 248 | 694 / 20 | 60 (0) | 38 | 5 | 9 / 0 | 2,451 / 44 / 22 |
| central_vt | 8,497 | 66 / 46 | 136 | 271 / 39 | 46 (0) | 177 | 4 | 60 / 11 | 1,625 / 23 / 0 |
| ne_ct | 3,813 | 161 / 98 | 219 | 433 / 40 | 132 (0) | 7 | 66 | 7 / 8 | 1,566 / 101 / 33 |
| lexington_va | 4,320 | 18 / 14 | 18 | 48 / - | 7 (0) | - | 0 | 3 / 2 | 695 / 27 / 0 |
| se_pa | 4,673 | 27 / 15 | 34 | 63 / 1 | 16 (0) | - | 0 | 2 / 0 | 838 / 0 / 0 |
| smokies | 9,068 | 22 / 13 | 146 | 388 / 56 | 4 (0) | 6 | 0 | 21 / 0 | 862 / 87 / 47 |
| adk_high_peaks | 9,739 | 220 / 131 | 432 | 1,137 / 48 | 170 (0) | 154 | 4 | 125 / 1 | 2,465 / 94 / 48 |
| adk_northwest | 9,156 | 365 / 256 | 654 | 1,659 / 69 | 321 (1) | 3 | 0 | 139 / 0 | 3,495 / 176 / 120 |
| adk_southwest | 7,426 | 235 / 172 | 424 | 917 / 59 | 199 (0) | 9 | 8 | 17 / 0 | 2,532 / 81 / 8 |
| adk_southeast | 9,253 | 309 / 206 | 602 | 1,448 / 105 | 242 (0) | 136 | 9 | 48 / 0 | 3,110 / 161 / 61 |
| all | 109,922 | 1,655 / 1,095 | 3,268 | 7,922 / 447 | 1,234 (1) | 569 | 189 | 637 / 62 | 21,776 / 905 / 347 |

`[log]` lakes: pitted by 03b / dead ends carried by crossbox / moved to the routed way out:
la 42 / 36 / 23; jackson 32 / 31 / 26; n_georgia 86 / 84 / 64; central_vt 55 / 55 / 45; ne_ct 147 / 147 / 119;
lexington_va 9 / 9 / 8; se_pa 25 / 20 / 13; smokies 13 / 14 / 12; adk_high_peaks 221 / 203 / 169;
adk_northwest 367 / 349 / 314; adk_southwest 226 / 223 / not printed; adk_southeast 276 / 269 / 246.
578 km of stream line added below outlets.

`[raw]` drainage a creek needs for "year-round" (0.1 cfs in more than 85 % of 16 summers), median model line, with the
10th-90th percentile of lines: la 8.24 (2.34-66.56); ne_ct 2.40 (1.56-3.67); lexington_va 0.69 (0.47-1.60);
se_pa 0.62 (0.48-0.89); central_vt 0.56 (0.22-1.37); n_georgia 0.52 (0.20-0.76); jackson 0.44 (0.14-1.45);
smokies 0.41 (0.17-0.99); adk_high_peaks 0.32 (0.17-0.71); adk_northwest 0.32 (0.19-0.53);
adk_southwest 0.32 (0.19-0.58); adk_southeast 0.32 (0.19-0.78).

`[snapshot]` classes per area (rows of the combined table, lake reaches included):

| area | mostly dry | seasonal | usually flows | year-round | reservoir | no data |
|---|---|---|---|---|---|---|
| la | 9,852 | 2,111 | 621 | 3,586 | 460 | 1,466 |
| jackson | 152 | 148 | 49 | 9,844 | 477 | 69 |
| n_georgia | 0 | 2 | 36 | 14,453 | 727 | 40 |
| central_vt | 0 | 32 | 183 | 7,882 | 318 | 111 |
| ne_ct | 6 | 173 | 785 | 2,354 | 488 | 74 |
| lexington_va | 7 | 20 | 40 | 4,160 | 48 | 54 |
| se_pa | 0 | 0 | 0 | 4,524 | 70 | 98 |
| smokies | 2 | 0 | 16 | 8,528 | 519 | 21 |
| adk_high_peaks | 1 | 14 | 32 | 8,404 | 1,199 | 158 |
| adk_northwest | 0 | 1 | 2 | 7,512 | 1,765 | 51 |
| adk_southwest | 0 | 0 | 2 | 6,516 | 987 | 39 |
| adk_southeast | 5 | 10 | 38 | 7,631 | 1,566 | 126 |
