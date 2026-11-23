# Audit notes: current-state documentation against the code

Scope: `README.md`, `data/stream_burning/README.md`, `MULTI_AREA_PLAN.md` against `scripts/*.py`, `*.sh`, `*.js`,
`map3d.html` (and the validators in `data/*.py` where the README cites them). `MULTI_AREA_LOG.md` not read.

## 0. Versions audited, method, limits of this pass

- **The docs moved under the audit.** Another session committed twice while this ran (729487d at 23:12, 03a1b4d at
  23:17, 2026-11-21). All line numbers below are for:
  - `README.md`: 989 lines, mtime 23:12:22 (HEAD 03a1b4d plus the uncommitted +10/-2 lines). Before 23:12 it had
    985 lines: everything after line 241 has since moved down by 4.
  - `data/stream_burning/README.md` (below: **SB**): 509 lines, mtime 23:16:52 (was 392 lines at 23:05).
  - `MULTI_AREA_PLAN.md` (below: **PLAN**): 84 lines, unchanged since 2026-11-18.
  - `scripts/`: no file changed after 22:57 (checked at 23:20). `06_map.py` has uncommitted changes.
- **Method:** static reading only. Nothing in `scripts/` was imported or run; no build, no network, no git command
  that changes state (`git log / diff / show / ls-files` only). `output/` and `data/derived/` were not read.
- **CONFIRMED** = both sides read (README line and code line). **PLAUSIBLE** = one side read, or the two sides
  can only be reconciled with data that was not opened.
- Not checked line by line: the cartography details of `06_map.py` / `map_drainages.js` (zoom levels, label
  rules), `troutdata.py`, `lakesources.py`, `lakedata.py`, `lake_bathymetry.py`, most of `07_road_closures.py`
  and `02d` / `02e` beyond the thresholds listed in 1.D.

## 1. README against the code

### 1.A Wrong or misleading today (highest first)

**A1. The manual build block no longer builds an area. CONFIRMED.**
- README L651-659 (the `bash` block) runs, in order: 01, 02, 03 per range; 03b; `04_knickpoints 04b_bigcreek_steps
  05_score` per range; 07; then `02b_download_flow.py`; 05c, 05b; 02c, 02d, 02e; 08, 10; 09, 11, 06; 12.
- Code:
  - `04_knickpoints.py:30-31`, `04b_bigcreek_steps.py:32-33` and `05_score.py:86-87` call
    `crossbox.carried_km2`, and `crossbox.py:404` reads `flow/nhdplus_v2.gpkg`, which only `02b_download_flow.py`
    writes. The block runs 02b after them. `run_base.sh:33` runs 02b before the drops; `run_mid.sh:20` before
    05_score. README L208-209 and L245-246 say so themselves.
  - `05_score.py:48-49` exits when `known_falls.gpkg` is missing ("run ... 02f_known_falls.py first"). The block
    never runs `02f_known_falls.py` (`run_mid.sh:17`).
  - The block never runs `05d_lakes.py` / `lake_bathymetry.py` (`run_mid.sh:27-28`), `02g_greenness.py`
    (`run_mid.sh:35`), `watertemp.py` (`run_late.sh:23`) or `fish_score_diagram.py` (`run_late.sh:27`).
- Effect: on a clean checkout 04, 04b and 05_score all fail (the shell loop carries on past them), so nothing
  after them has reaches or drops to work on; on an existing build it runs but leaves lakes, greenness and the
  water-temperature fit stale. The three drivers (README L116-120) are the only current recipe.

**A2. The Lakes layer is on when a map opens; the README says off. CONFIRMED.**
- README L849: 'a "Lakes" layer and a "Lake depth contours" layer, both off at start'. README L516-517: every
  map "opens with only streams, drainage outlines and names, the area's long trail ..., terrain shading and
  place / road labels".
- Code: `maplakes.py:263` `show=True,      # on when the map opens (user, 2026-11-20)`; `map3d.html:251-252` (the
  lakes `ov` row ends in `true`); `14_portable.py:129` `lakes: true` and `:299` (`checked`).
- README L523 itself says "(it starts on)". See 2.1.

**A3. `05d_lakes.py` runs before the reaches, not after the drainages and flow. CONFIRMED.**
- README L853: "`run_mid.sh` runs `05d_lakes.py` then `lake_bathymetry.py` after the drainages and flow".
- Code: `run_mid.sh:27-28` (05d, lake_bathymetry) come before `:32` (05_score), `:39` (05c) and `:40` (05b).
- README L255, L390 and L834 say "before `05_score.py`", which is right. See 2.2.

**A4. Idaho 511 is fetched; the README says the Idaho side has no closures. CONFIRMED.**
- README L569-572: "WYDOT's highway conditions, Idaho 511 and Connecticut's closures need a registered key ... the
  Idaho side (Teton Valley, Palisades) aren't covered." README L99 lists only "Grand Teton NP and Teton County
  (Jackson)".
- Code: `config.py:112` has `"id_511"` in Jackson's sources; `07_road_closures.py:20-21` ("Idaho 511's work-zone
  feed (WZDx 4.1 GeoJSON ...; its event API needs a key): road work closures on the Idaho side of the Jackson
  map") and `:342-358` fetch `https://511.idaho.gov/api/wzdx` with no key.
- What is true: work-zone closures on the Idaho side are in; Idaho's event feed, WYDOT and Connecticut are not.

**A5. `run_drainage_refresh.sh` also reruns the flow step, and scores can change. CONFIRMED.**
- README L37-39: "redoes 05c per range, the map and the profiles ... The scores don't change."
- Code: `run_drainage_refresh.sh:21-26` runs `05b_flow.py` for every range between 05c and 06_map; its header
  (`:2-4`, `:8`) says "Redo the drainages, the flows and everything drawn from them" and "scores change only where
  a reach's flow does".

**A6. A lake's "outlet" in the routing is the lake cell with the most water, which is not always where the
water leaves. CONFIRMED (code), size of the effect from SB.**
- README L169-170: paths are ended "at the cell where the water leaves it"; L176-177: "every cell of a lake that
  holds water drains to its outlet along NHD HR's lines".
- Code: `03b_stitch.py:520` "the cell inside with the most water"; `:552-556` picks the lake cell with the
  largest accumulation; `:570` routes the whole lake to it.
- SB L274-282 ("Fault 2", written 23:12): 77 lakes have that cell 300+ m from NHD's outlet, 20 of them 1 km or
  more (Raquette Lake 9.1 km, at an inlet's mouth). Not fixed. The main README does not mention it.

**A7. The tailwater water floor fires on more than "no gauge record". CONFIRMED.**
- README L700 (and SB L8-9, `scoring.py:23` docstring): "(3) A tailwater ... with no gauge record on the reach:
  full water".
- Code: `scoring.py:252` `tw_up = tailwater(s).ne("") & (water < 1.0) & ~rec`. `rec` (`:243`) is "the gauge
  rule changed this reach", not "the reach has a gauge record": a tailwater reach with a record is still lifted
  to 1.0 when the model is within 0.05 of the gauge, when the reach is above the gauge and the model is
  higher (`gauge_below` false), or when trout are known anywhere on the gauge's creek (`trout_site`).
- Rule (4) uses the stricter test, `gsh.isna()` (`scoring.py:269`), which matches its README text (L708).

**A8. A tailwater does not stop at the next reservoir. CONFIRMED (code); the case is in SB.**
- README L733-734: "the West Fork San Gabriel below Cogswell Dam, down to the San Gabriel Reservoir, and Piru
  Creek below Pyramid Dam, down to Lake Piru (`TAILWATERS` in `scoring.py`)".
- Code: `scoring.py:183-184`: a reach is the tailwater when `below_dam` equals the dam, or its name is the
  river, `elev_m <= top` (700 m for Piru), full drainage >= 20 km2 and `below_dam` is empty. No test for a
  reservoir in between; the function's docstring (`:177-178`) also says "down to the next reservoir".
- SB L178-181 ("Left open"): lower Piru Creek below Lake Piru, 19 reaches, takes the floor for that reason and
  its popup credits Pyramid Lake's releases.

**A9. Outside LA the flow is scaled on `area_full_km2`, not `area_edge_km2`. CONFIRMED.**
- README L347: "`area_edge_km2` (with what flows in from other boxes; `05b_flow.py` uses it)"; L356-358: "scaled
  by drainage area: the reach's `area_edge_km2`, which counts what flows in from other boxes but not water from
  above a dam".
- Code: `05b_flow.py:68-72` `col_ = "area_edge_km2" if has("tnc_flows") else "area_full_km2"` ("outside
  California the flow table is NHDPlus's gauge-adjusted mean flow, which has the dams in it"); the same at
  `:268` and in `data/check_flow_drops.py:30` (`AREA_COL`).
- True for LA (README L57: "Everything described below is the `la` area"), but the "What differs outside
  California" table (L89-104) does not list it, and 11 of 12 maps use the other column.

**A10. The water-temperature fit is described two ways, and one step is not described. CONFIRMED.**
- README L779-780: "`watertemp.py` fits the measured sites' July-August daytime medians on PRISM August air
  temperature and elevation, per study area".
- Code: `watertemp.py:180-186`: four predictors (`air`, `elev_km`, `log_area`, `lake`) in 15 sets, the best by
  leave-one-out error among those with the physical sign, a simpler set within 0.05 C winning (`:294`).
  README L108-111 says "the best of August air, elevation and drainage area" (no lake term), L786-804 adds the
  lake term.
- README L806: "Three sites with medians over 30 C are left out". Code also drops outliers: `watertemp.py:188`
  `OUTLIER_MADS = 3.0`, `:323-329` (sites over 3 robust SDs off the first fit), counted in the fit record as
  `left_out_outliers` (`:339`). Nowhere in the README.

**A11. The PRISM clip is per area, not in `_national`. CONFIRMED.**
- README L617-618: "the national file is downloaded once and clipped to `data/raw/_national/prism_tmean_aug.tif`".
- Code: `watertemp.py:101` `p_ = f"{SHARED}/prism_tmean_aug.tif"` (`data/raw/<area>/_shared/`); the national
  file is `{NATIONAL}/prism_tmean_aug_us.zip` (`:107`). `11_context.py:227` uses `watertemp.air_tif`.

**A12. The falls validation counts the detectors' raw output, and its table predates the detector change.
CONFIRMED.**
- README L933-946: "mapped falls matched by a detected drop within 200 m", "All 12 areas on 2026-11-20".
- Code: `data/validate.py:28-29` reads `knickpoints.gpkg` and `knickpoints_bigcreek.gpkg` straight from 04 and
  04b; `:43-44`, `:49-50` count any of those drops within 200 m. That is before `05_score.py:364` drops pass-2
  hits off NHD-perennial creeks (README L201) and before the statuses of `05_score.py:357-362`; drops later
  set aside as "dam / weir" or "likely DEM artifact" (left out of the GPX, `06_map.py:517-518`) still count.
- Since then the detectors changed (README L203-209, 2026-11-21: "1,025 -> 1,070 of 2,128" known falls found),
  so the table (486 / 829, 839 / 1,600) is a day older than the detectors.
- Only recall is measured. Nothing in the docs estimates how many "unmapped" candidates are real (README L963-965
  and L976-977 say to check them on imagery).

**A13. Pass 1 needs 8 m of drop; the README never says so. CONFIRMED (omission).**
- README L193-197 gives 25 % over 30 m, the 200 m reaches and the class cut-offs (0.6, 2.5x, 1.8x).
- Code: `04_knickpoints.py:17` `MIN_DROP = 8`, applied at `:112`. Also not in the README: the knick ratio's
  reference slope has a floor of 0.03 (`:119`); pass 2's trend has a floor of 0.005 (`04b_bigcreek_steps.py:22`)
  and "anything pass 1 already found" means within 100 m (`:110`).

**A14. The fish score diagram written for every area leaves out the channel factor. CONFIRMED.**
- `run_late.sh:27` writes `output/<area>/fish_score_diagram.png` from `fish_score_diagram.py`.
- `fish_score_diagram.py:31-32` "multiplied by four factors"; `:56` draws burn, trout evidence, heat gate.
  `scoring.py:322-323` multiplies by five (water, burn, trout, heat, channel), as README L678 says.
- The diagram's water panel (`:139-148`) names only the flow model and the diversion gauge (none of rules 1-4 of
  README L686-711), says "TNC flow model" and "warmest creek with a trout record, 80.1 F" (`:185`) for every
  area. The README does not mention the diagram at all.

### 1.B Stale, incomplete or imprecise

- **B1. "all six in one page" (README L28).** 12 areas in `config.py:54-359`, 8 shown. `13_overview.py` and
  `14_portable.py` docstrings say "six" too. CONFIRMED.
- **B2. README L138:** `stream_reaches_ranked.csv` is "Every DEM stream link (>=1 km2 drainage)". Since
  2026-11-21 it is pieces of links cut at lake shores (`05_score.py:104-108`), kept on own area plus carried
  water (`05_score.py:90`). README L232-257 says so. CONFIRMED.
- **B3. The flow classes have no definition in the README.** L394-395 lists "year-round, usually flows, seasonal,
  mostly dry, reservoir, no data". Code: `flowlib.py:377` cuts the share of summers at 0.2 / 0.5 / 0.85
  (`scoring.py:245`, `:271` the same). CONFIRMED (omission).
- **B4. Walking speed on paths.** README L579: "Trails, tracks and closed roads use the trail grade, capped at
  15%". Code: `08_hike.py:210` uses the cell's hillside slope capped at 15 % (`tobler(np.minimum(slope,
  TRAIL_MAX_GRADE))`); only bikes use the line's own grade (`:209`, `:213`). And "anything with a tread"
  (`:98`) is every OSM road and trail in the range files, private roads and freeways included. CONFIRMED.
- **B5. README L729:** "A reach with no estimate in an area with no measured sites gets half credit." Code:
  half credit goes to any reach without an estimate where the area mean is not in use, also a reach missing an
  input in an area whose fit has skill (`scoring.py:292-294`, `watertemp.py:429-432`). CONFIRMED.
- **B6. README L680-681** lists four NHD fallback values. Code has a fifth: any other class 0.3
  (`scoring.py:224` `.fillna(0.3)`): in LA that is NHD's artificial paths and canals ("other",
  `05_score.py:41-42`). CONFIRMED.
- **B7. The gauge rule has a dead band.** README L694-697. Code: a reach moves only where model and gauge differ
  by more than 0.05 (`scoring.py:243`). CONFIRMED (omission).
- **B8. Counts that differ between README and code comments.**
  - README L389 "397 such reaches over the 12 areas"; `05b_flow.py:585` "404 such reaches over the 12 areas".
    CONFIRMED.
  - README L271-274: 88 + 214 + 366 = 668 reaches; `05_score.py:214` "about 720 reaches". PLAUSIBLE (different
    days or definitions).
- **B9. "Strahler order" (README L154, L232, L309).** `03b_stitch.py:126-131` keeps pysheds' rule, which its own
  docstring says is not Strahler's where two of the highest order meet a lower one, and which steps up at a pit
  (a lake's outlet). CONFIRMED as a naming imprecision.
- **B10. README L148 "Steps 1-5 run once per range".** `03b_stitch.py` and `02f_known_falls.py` (inside steps 3
  and 4) run per area; steps 6 and 7 (05c, 05b) also run per range. CONFIRMED.
- **B11. `run_rebuild_a.sh` runs the drops before the flow download.** `run_rebuild_a.sh:35` (04, 04b) then
  `:37` `run_mid.sh` (whose line 20 runs 02b). README L208-209 names only `run_base.sh`. Harmless while the
  NHDPlus and reservoir files from an earlier 02b are on disk. CONFIRMED, low.
- **B12. Not in the README at all.** `SKIP_03B=1` (`run_rebuild_a.sh:8`, `:30`); `fish_score_diagram.py`;
  `15_preview.py` (the link-preview picture, run by hand); `run_la_refresh.sh`; `labelpaths.py`; `creek-map/`
  (tracked in git, left alone by `phone_sync.sh:6`); that `profiles.html` is a hand-made page with no generator,
  kept in git under `output/<area>/` and copied from `output/la/` for a new area (`.gitignore:1-2`, `:18-22`;
  `run_late.sh:25`). CONFIRMED.
- **B13. README L33 "about 24 MB"** for the one-file map. `phone/stream_maps_all.html` was 41,458,124 bytes at
  22:18 on 2026-11-21 (`ls`; `phone/` is the published copy, not `output/`). PLAUSIBLE.
- **B14. README L141:** closures are "(Caltrans, LA County, SB County)". Code and README L559-561 also have
  Riverside County and Ventura County (`07_road_closures.py:4-10`). CONFIRMED.
- **B15. Per-area relief thresholds.** README L435 "under 100 m relief within 1 km". `config.py:187`, `:212`
  set 30 m (NE Connecticut, SE Pennsylvania), `:292`, `:311`, `:328`, `:343` 50 m (Adirondacks). Not in the
  "What differs" table. The closures' 150 m (`07_road_closures.py:551`) is the same everywhere. CONFIRMED.
- **B16. Title and frame.** README L1-22 ("LA Mountains Stream & Waterfall Analysis ... It covers eight
  ranges"), L125 ("Outputs (`output/la/`)"). 12 areas. CONFIRMED.
- **B17. Profile drainage.** `12_profiles.py:82`, `:158` read `area_km2.tif` (own area, without the water carried
  past dams or in from outside), while popups show `area_full_km2`. README L635-638 does not say which.
  PLAUSIBLE (a creek below a dam may show two drainages).
- **B18. README L201** places the NHD-perennial filter in the description of `04b`; it is applied in
  `05_score.py:364`, on the class of the nearest NHD line within 80 m (`:306-307`). CONFIRMED, low.

### 1.C Stale comments in the code (they contradict the code or the README)

- `05b_flow.py:120`: 05d "reads 05c's drainages". It reads nothing of the reaches (`05d_lakes.py:4`, README L835).
- `run_drainage_refresh.sh:5-6`: "run_mid.sh runs it [05d] between them [05c and 05b]". It runs first.
- `run_late.sh:5`: "a keyless feed in four of the other areas (none for NE Connecticut)". Five have one
  (Jackson, North Georgia, Vermont, Lexington, the Smokies); six have none (NE Connecticut, SE Pennsylvania, the
  four Adirondack maps).
- `06_map.py:1253`: `hidden = {"steep reach", "likely DEM artifact", "dam / weir"}` is set and never read; those
  three statuses get layers like the others (`:1254`, all off at start).
- `05d_lakes.py:5`: "Built so far for the areas in BUILT (the Jackson pilot, 2026-11-19)". All 12 are in BUILT.
- `05d_lakes.py:12`: surface elevation "the 10 m 3DEP DEM ... (median)"; the lidar level comes first
  (`:544-598`, README L882).
- `config.py:17`: `cdfw_pad` "(05_score.py)". It is read in `02f_known_falls.py`.
- `watertemp.py:4`: readings "since 2000"; the request starts at 1995 (`:86`). `watertemp.py:69`: with too few
  sites "the score falls back to the air temperature alone"; it falls back to half credit (`scoring.py:293`).
  `watertemp.py:24-28`: "11 sites" then "those 12 sites".
- `watertemp.py:40-43` and `scoring.py:39`: the Jackson no-skill note and "Where there's no estimate the term is
  neutral (0.5)" both predate the area-mean and weighting rules (see 2.3).
- `08_hike.py:106`: cache "under data/raw/_shared/cache"; it is `data/raw/<area>/_shared/cache` (`:107`).
- `scoring.py:177-178`: `tailwater()` "down to the next reservoir" (see A8).

### 1.D Checked and matching (so the audit need not redo them)

- **Fish score** (`scoring.py`): weights 0.30 / 0.30 / 0.15 / 0.25 and the five multipliers (`:322-323`; README
  L678); water 0.05 + 0.95 x share, 0.3 in a reservoir (`flowlib.py:376-379`); NHD fallback 1.0 / 0.35 / 0.15 /
  0.05 (`:224`); bare channel 0.45 cfs, 0.45, 0.5, 0.2, 2018, 0.35 (`:138-143`, `:232-237`; `dry_cfs` is the
  median year, `05b_flow.py:475`); gauge rule (`:238-247`); `DAM_HELD` 0.5 and `tnc_flows` only (`:144`,
  `:265-273`); diversion rule (`:276-278`; `05b_flow.py:502`: recent record, drainage grown by at most 1.25);
  size log 1-50 km2 with the side channel's river size (`:281-282`); thermal 0.5 / 0.35 / 0.15, 20-25 C
  (`:149`, `:294-295`); shade formula and 45 % (`:284`); gradient band 1-8 % (`:296`); remoteness 120 min,
  ridden minutes x2 (`:134`, `:298`); burn 0.4 / 0.7 / 0.9 and debris floor (`:121-127`, `:299-305`); BAER
  shares 1.0 / 0.75 / 0.4 / 0.15 (`11_context.py:101`); trout 1.2 / 0.5, 10 years (`:189-199`); heat 29.0 /
  30.5 / 0.2, off with trout evidence or below a dam (`:135`, `:214-220`); channel 0.2 by name (`:202-211`);
  `area_rank_pct` (`06_map.py:76`).
- **Flow** (`05b_flow.py`, `flowlib.py`, `02b_download_flow.py`): July-October, since 2011, 0.1 cfs
  (`02b:26-27`, `flowlib.py:369`); 30-day cache (`02b:31`); EROM x gauge index outside LA (`02b:201-232`);
  second-driest year (`05b:476`); 8 ha lakes (`flowlib.py:8`); half-inside rule (`05b:109`, `:587-598`); the
  "old estimate stays" rule (`05b:526-547`); seven diversions (`flowlib.py:393-402`); gauge record 4 km, 2/3 to
  1.5x, 5+ summers, 100 m (`flowlib.py:434-450`, `:461`, `:542`, `:570-606`); greenness 2022-24, 15 Aug-30 Sep,
  90th percentile within 30 m (`flowlib.py:460`, `:477-515`; `02g_greenness.py`); minor-path flags off in LA
  (`flowlib.py:40`).
- **Hydrology** (`03_hydrology.py`, `03b_stitch.py`, `crossbox.py`, `05c_drainages.py`): 5 km halo and 1e-9
  flats (`03:32-33`); streams 0.25 km2, level 2 ha, line pull 5 (`03b:43-45`); exit with an error on a dead end
  left (`03b:680-683`); 25 / 35 / 120 / 100 / 2,000 km2, sea level 0.5 m, 5 km2 (`05c:19-42`); 10 km2 rivers
  from outside, 100 m put-in rule (`crossbox.py:30-31`, `:335-392`); cache key (`crossbox.py:203-207`).
- **Reaches and drops** (`05_score.py`, `04*.py`): 1 km2 floor with carried water (`05:12`, `:90`); 50 m pieces
  (`flowlib.py:187`); three-point vote (`05:124-132`); 3 km / half rule (`05:196-205`); side channels 10x, 50
  km2, 250 m, 60 %, 150 m (`05:224-272`); first-pass score (`05:283-288`); status order and 250 m / 100 m / 3 m
  / 50 m / 40 m / 200 m (`05:320-362`); pass 1 and pass 2 thresholds (`04:13-16`, `:139-142`, `:148`;
  `04b:16-21`, `:105`).
- **Access, sun, context**: `08_hike.py:34-39` (15 %, 0.45, 0.30, 45 degrees, 18 km/h, x0.7, x0.5, 25 %, 200 m,
  1 min), freeways not trailheads (`:101`), lakes (`:224-285`); `09_drive.py:14-17`, `:116` (x0.75, 3 km, 25
  km/h); `10_sun.py:14-17` (July 15, 36 directions, 3 km, 1 km); `11_context.py` fires since 2016 (`:31`),
  debris flow 4 years (`:145`), canopy 90 days (`:390`), trout matching 5 km / 150 m / 1.5 km / 400 m
  (`:315`, `:340-367`), no-trout samples from CT and TN only (`troutdata.py:149-150`, `:432`).
- **Profiles** (`12_profiles.py:19-25`): 2 km, 20 m, `OWN_CAP`.
- **Lakes**: smallest sizes (`05d_lakes.py:42-43`), 600 ha and 2 m (`:438-439`), the 15 cm / 70 % / half / 2 acre
  / 1 m rules (`:544-591`), 200 m2 patches (`lakelidar.py:34`), 2 km clip (`05d:1095-1104`).
- **Known falls** (`02f_known_falls.py`): 0.5 degree tiles (`:185`), 500 m / 2 km / 100 m / 25 m (`:432-442`),
  50+ falls for a credit (`06_map.py:52-57`).
- **Trails, access, closures**: 25 m over 60 % (`02d_trails.py:26-27`), 300 m, 150 m, a week
  (`02d:37`, `:210-212`; `02e_access.py:49`, `:178`, `:206`), 60 km past the map (`02c_pct.py:14`); Caltrans
  routes, 7 days, 150 m relief (`07_road_closures.py:36-42`, `:551`); closure within 3 km (`06_map.py:64-67`).
- **Drivers and publishing**: `run_base.sh`, `run_mid.sh`, `run_late.sh`, `run_rebuild_a.sh` match README
  L116-120 (with A3, B11, B12); `publish_site.sh` matches L40-52; ports 8765 / 8766 (`.claude/launch.json`);
  Overpass order (`geomatch.py:13`); areas, ranges, homes, long trails and `hidden` (`config.py`) match the
  tables at L60-79 and L100; the 1 x 4 km overlap of the San Gabriel and Santa Monica boxes (`config.py:66`,
  `:69`).

## 2. Contradictions inside the docs

1. **Lakes layer at start.** README L523 "(it starts on)" against L849 "both off at start" and the list at
   L516-517 (no lakes). L523 is right (A2).
2. **When 05d runs.** README L255, L390, L834 "before `05_score.py`" against L853 "after the drainages and
   flow". The first is right (A3).
3. **Jackson's water-temperature fit.** README L727-728: no skill, "so its reaches keep full credit"
   (present tense). L785-786: "Jackson's fit has skill since ... so its reaches carry an estimate". L110 lists
   a Jackson fit. The arithmetic says L727 is the older state (3.37 / 3.72 = 0.906, the "unweighted" figure of
   L785). Which holds today is in `data/raw/jackson/_shared/water_temp_fit.json` (not opened). CONFIRMED as a
   contradiction.
4. **What the fit uses.** README L779-780 (air and elevation) against L108-111 (air, elevation, drainage area)
   against L786-804 (plus a lake term). See A10.
5. **"all six"** (L28) against 12 areas (L60-73, L828).
6. **"Two ways to carry the maps"** (L31-32) is followed by three bullets; the middle one (L37-39) is a rebuild
   recipe, and wrong (A5).
7. **Closures outside California.** README L99 lists the Smokies' five feeds and "none for NE Connecticut,
   southeastern Pennsylvania or the Adirondacks"; L566-572 lists four areas, no Smokies, and names only NE
   Connecticut as having no layer. Both leave out Idaho 511 (A4).
8. **Where a tailwater ends.** README L733-734 "down to Lake Piru" against SB L178-181 "doesn't stop at Lake
   Piru" (A8).
9. **The put-in fix.** README L332-334: the water is put in at the top of the routed way out at "1,237 of
   1,430 lake dead ends". SB L268-271: "1,269 of the 1,430 ... It leaves 29 of the 31 firm cases" (Seventh Lake:
   its outlet channel is not drawn). The README gives no hint that a fault is open. PLAUSIBLE that the two counts
   are from different builds.
10. **Lake outlets.** README L169-170, L176-177 against SB L274-285 (A6).
11. **Links below outlets.** README L237-240 ties "95% ... along NHD's stream lines, 199 of the links carrying
    100 km2 or more" and "927 km of it" to 1,610 links / 1,092 km. SB L136-137 and L193 give all three for
    1,622 links / 1,100 km (and 185 for the 1,520 of L95). PLAUSIBLE (two counts mixed).
12. **Known falls denominator.** README L208 "of 2,128"; SB L34 "of 2,127".
13. **Dry creeks rated flowing.** README L687-689: 31 in LA, "outside LA only Dead Creek". L698: "13 of the 35 dry
    ones rated flowing are caught". 31 + 1 = 32. PLAUSIBLE (another gauge set or threshold).
14. **Measured sites in LA.** README L762 "83 sites"; L805-807 "65 sites" plus three left out. Both scripts
    build sites the same way (`data/validate_heat.py:70-83`, `watertemp.py:147-171`); the outlier pass (A10)
    and missing air or elevation may explain part. PRISM alone is "4.0 C" (L771) and "air alone 3.45" (L806) on
    those two sets. PLAUSIBLE.
15. **One-file map contents.** README L33-36 lists its switches without lakes; L849-850 says the lake layers
    are in it (`14_portable.py:22`).
16. **Validation date.** README L934 (2026-11-20) against L203-209 (detectors changed 2026-11-21). See A12.
17. **SB against the code.** SB L24-25 and L437-438: the lakes layer is what "05b reads"; `05_score.py:104-105`
    reads it too since the shore cut. SB L228 names `checks/gone_split.py`, which the "Files" list
    (L429-463) leaves out.
18. **SB "7 areas".** SB L312-313: `hragree.py` "fails on 0.2-2.7 % of HR lines across 7 areas";
    `results/hragree_live_6_areas.txt` has six. PLAUSIBLE (Jackson's figure may be the seventh, from
    `checks_r0_jackson.txt`).
19. **Jackson walking distances.** README L923-924: "within about 10% ... (Taggart Lake 1.3 mi against 1.5,
    Amphitheater Lake 4.5 against 4.9)". 1.3 / 1.5 is 13 % short.
20. **PLAN against README and code:** see section 6.

## 3. Numeric claims to verify against data (not verified here)

Arithmetic checked: the validation table and its two breakdowns add up (README L939-941: 108 + 294 = 402, 192 +
294 = 486, 270 + 559 = 829; L944-946 sums to 486 / 829; L950-953 sums to 127 / 212 and 70 / 105). SB's tables
at L79-93 and L117-131 add up (km of fish 60+ "now" sums to 42,722 against 42,721, rounding). The Adirondack
skill ratios of README L792-797 are all under 0.9 as the rule requires.

| # | Line | Claim | What would verify it |
|---|---|---|---|
| 1 | README 937-942 | Mapped falls found: 402 / 829 (pass 1), 486 / 829 (both); precise known falls 693 and 839 / 1,600 | `data/validate.py` per area on today's `knickpoints*.gpkg` and per-range `known_falls.gpkg` |
| 2 | README 944-946 | By area: LA 127 / 212, Jackson 12 / 21, N Georgia 110 / 193, Vermont 20 / 30, NE CT 4 / 23, Lexington 15 / 21, SE PA 0 / 11, Smokies 97 / 156, ADK 41 / 53, 18 / 33, 6 / 10, 36 / 66 | same |
| 3 | README 950-953 | LA by range; "now 70 of their 105" for the three tuning ranges; 25 of the Santa Anas' 46 under 1 km2 | same, plus `area_km2.tif` at each fall |
| 4 | README 955 | CDFW barriers: 51 of 172 with a drop within 200 m | `validate.py`'s last line (LA) |
| 5 | README 207-208; SB 34 | Known falls found, any source: 1,025 -> 1,070 of 2,128 (SB: of 2,127), none lost | `data/stream_burning/checks/falls.py` on both builds |
| 6 | README 183; SB 29 | Straight made-up lines across lakes: 986 km -> 266 km | `checks/straight.py`, `results/lakes_2026-11-21/` |
| 7 | README 188; SB 139-141 | Lake outlets under half of NHDPlus: 45 -> 39 -> 26 | `checks/lake_outlets.py`; `results/installed_2026-11-21/lake_outlets.txt` |
| 8 | README 237-243; SB 117-131, 136 | 1,610 links / 1,092 km kept on carried water; 95 % along NHD lines; 199 carrying 100+ km2; 103 km of reaches lost | 05_score's log lines in `data/mid_<area>.log`; `checks/outlet_gaps.py` |
| 9 | README 240-242; SB 193, 202-216 | 927 km already drawn; drawn line +131 mi / -149 mi; fish 60+ drawn 25,024 -> 25,095 mi, down on five maps | `checks/drawn_cmp.py` on site commits 855954f and 6875118 |
| 10 | SB 117-131 | Reaches 105,478 -> 106,609; km of fish 60+ 42,159 -> 42,721 (up on every map, reach tables); 454 down / 290 up by 10+ points | `checks/totals.py`, `drops.py`; `results/installed_2026-11-21/` |
| 11 | SB 245-260, 277 | 1,430 lakes with a link; 31 firm put-in faults carrying 1,041 km2; 77 lakes with the pit 300+ m from NHD's outlet | `checks/putin.py`; `putin_12_maps.csv` |
| 12 | README 332-334 | Put-in moved at 1,237 of 1,430 lake dead ends; joins a median 40-120 m down, 300+ m at about 60 outlets | `checks/landing.py`, `putin.py` (SB says 1,269) |
| 13 | README 250-251 | Creek read as lake 352 -> 30 km; lake read as creek 339 -> 20 km | `checks/lake_shares.py`; `results/shores_2026-11-21/` |
| 14 | README 271-274 | Small reaches beside a river: 88 renamed, 214 side channels, 366 unnamed | 05_score's log line per box; `side_of` in `streams_scored.gpkg`; `checks/side_channels.py` |
| 15 | README 297 | 33 confluences on 11 maps changed; own-name labels 484 -> 1,122 | `stream_drainage.csv` before and after (needs the older build) |
| 16 | README 329-330 | Reservoir areas carried past dams: Morris 533 km2, Pyramid 514, Castaic Lagoon 412, Big Tujunga 212, Littlerock 165, Hemet 143, Big Bear 137, Matilija 132 | `data/derived/la/_shared/inflows.json` (dam entries) against NHDPlus `totdasqkm` |
| 17 | README 339-340 | 293 ponds; 7,751 reaches; the Soquee 390 km2 against NHDPlus 414 | `inflows.json` pond links; `area_streams.csv` |
| 18 | README 358-359 | Old estimate kept on 41 reaches (LA) | 05b's log line "the old estimate is kept on N", summed over LA's boxes |
| 19 | README 380-381 | "No data" at box edges: 10 % of Jackson's reaches within 1.5 km of an edge; 569 reaches | older `flow_streams.csv` (historical) |
| 20 | README 387-390 | Reaches in lakes rescored: 397 (code comment: 404); 158 reaches / 84 km; 196 reaches, 125 at fish 60+ | 05b's log lines per box |
| 21 | README 410 | Reaches with a gauge's record: 1,170 -> 1,277 | count of `gauge_share` in every `flow_streams.csv` |
| 22 | README 680 | About 9 % of LA reaches off the model | `flow_src == "none"` share in LA's `flow_streams.csv` |
| 23 | README 684 | San Jacinto River gauge flowing in 19 % of summers | `flowlib.gauge_summers` on site 11069500, `gauges_daily.csv.gz` |
| 24 | README 687-688 | 31 of LA's 53 gauged dry creeks rated flowing; 25 of 31 gauged creeks at 0.1-0.45 cfs dry | `gauge_sites.gpkg`, `gauges_daily.csv.gz`, `flow_streams.csv` (LA) |
| 25 | README 694 | Every gauged flowing creek there has channel green 0.67-0.86 | `green_p90` at the gauged reaches |
| 26 | README 697-700 | Rule check: 0 of 221 flowing creeks lowered; 13 of 35 dry ones caught; wrong "flowing" summers 82 % -> 13 %; 636 LA reaches change (33 up), 69 Jackson, 13 Dead Creek | scoring with and without rules 1-2 against the gauges of all 12 areas |
| 27 | README 702-703 | Piru Creek: 28 reaches lifted; gauge below Pyramid Dam flowing 11 of 11 summers; gauge above Lake Piru 31 % | `gauge_summers`; `water_rule == "tailwater releases"` |
| 28 | README 710-711 | Bear Creek below Big Bear on 4 of 193 km2; 105 LA reaches rise | `water_rule == "below a dam"` count |
| 29 | README 714-715 | Of 2,430 NHD-perennial reaches the model dries 619; 850 NHD-ephemeral reaches flow | LA `stream_reaches_ranked.csv`: `flow` against `water_class` |
| 30 | README 727, 785 | Jackson: 145 sites, mean 13.4 C, 3.37 against 3.72; weighted 0.887 against 0.906 | `data/raw/jackson/_shared/water_temp_fit.json` |
| 31 | README 751-753 | About 330 creek trout records; hottest 26.7 C (lower Piru), then 26.5, 26.2 | `data/validate_heat.py`; `context/trout_evidence.gpkg` `air_aug` |
| 32 | README 762-771 | 83 sites; spread 5.7-6.0 C; leave-one-out RMSE NorWeST 5.6, StreamCat 4.1, PRISM 4.0; NorWeST missing 1,476 reaches | `data/validate_heat.py` (LA) |
| 33 | README 790-797 | Adirondack fits: 0.92-1.02 without the lake term; 90 sites 3.18 / 3.85; 123 sites 3.02 / 3.50; 2.50 / 2.99; 63 sites; 337 sites 3.13 / 3.59; 2.87 / 3.36; 3.10 | the four `adk_*` `water_temp_fit.json` and `water_temp_sites.csv` |
| 34 | README 789, 800-804 | Pond-fed creeks about 6 C warmer; lake-fed rivers 0.7 C below the fit (Sacandaga 2.9 below, Lake George 0.9 above), Jackson 1.4 below; 2.2 C above with the fade; 41 lake sites (Adirondacks), 3 (Jackson) | refit with and without the fade on the sites tables |
| 35 | README 805-809 | LA fit: 10.5 + 0.56 air - 4.17 elevation (km), 65 sites, RMSE 3.2 (air 3.45, elevation 3.3); ranges; 11-26 C over all reaches | `data/raw/la/_shared/water_temp_fit.json`; `water_aug` range |
| 36 | README 811-813 | 1,566 reaches with trout evidence, mean credit 0.91; 95 % moved 3 points or less, 33 by 10+; 189 of the top 200 stayed | LA ranked table against the elevation-band score (historical) |
| 37 | README 858-869 | Lakes table: lakes per area (543 ... 1,137), lidar shorelines, measured depths, contour lines, trout lakes, walk-in changes | each area's `lakes.gpkg`, `lake_depth.gpkg`; `hike_*.csv` before and after |
| 38 | README 871-875 | 35 to 405 reaches 5+ min slower; fish moved 5+ points at 0-154 reaches (Jackson 154, LA 60), at most 10 | older `hike_streams.csv` (historical) |
| 39 | README 881, 885 | Lidar against NHD outlines: Jackson median overlap 0.78; Tugaloo 195.5 of 203 ha; 166 lakes named from OSM | `lakes.gpkg` (`lidar_iou`, `ha`, name source) |
| 40 | README 894-896 | Lake Champlain: 12,083 soundings; deepest 399 ft; mean 74 ft; 25.9 km3 against 25.8 | `lake_bathymetry.py` output for central_vt |
| 41 | README 923-924 | Jackson routes within about 10 % of Park Service distances (two examples) | `route_km` in Jackson's `hike_lakes.csv` |
| 42 | README 929-931 | Adirondacks: 324-953 reaches per map 5+ min slower; fish 5+ points at 22-214 reaches | older `hike_streams.csv` (historical) |
| 43 | README 529-530, 539-540 | About 8,200 lake reaches, 170 at lake edges; dam joins 290 of 393 (eight maps), 1,048 of 1,436 (12); medians | 06_map's log lines; `map3d_data.js` `streams_lake` |
| 44 | README 143 | About 490 creek profiles (LA) | `12_profiles.py`'s last log line |
| 45 | README 33, 41-42, 46 | One-file map about 24 MB; `streams/` 605 MB; a push 85-134 MB | file sizes (the first is 41 MB today, B13) |
| 46 | README 645-646 | A fresh 02b gauge download takes about 115 requests; 11_context under 10 | request count on a `REFRESH=1` run |
| 47 | SB 27-38, 321-352 | Lake-routing and burn test tables (HR lines missed 1,811 -> 1,784; burn: 131 -> 109, 169 -> 112) | `results/lakes_2026-11-21/`, `checks_r0_*`, `checks_r3e_*` |

## 4. Limits and open items the docs already admit

Main README:
- L5-7: a creek crossing a range edge is split; one 1 x 4 km overlap.
- L20-22, L106-108, L820-822: the score was tuned for LA; in wet areas most reaches score over 50; scores rank
  within an area only.
- L94: outside LA one flow index per area; small headwaters are over-rated in droughts.
- L96, L97: PAD-US "unknown" holdings not flagged; Idaho and New York publish no usable survey or pond list.
- L99, L564-565, L570-572, L979-980: closure feeds missing for three areas and parts of Jackson; Forest Service
  orders are PDFs and not included.
- L110-111: SE Pennsylvania's fit cannot see limestone-spring creeks (22 C estimated, 15 measured).
- L143: profiles only for creeks with 2 km or more named in NHD.
- L163-165: a lake whose water leaves it on an edge between boxes flows on.
- L189-192: the lake-routing measurement missed vanished lines; the DEM burn is not used.
- L334-337: where the routing leaves a lake elsewhere than NHD does, NHD's cell stands; lakes with no outflow
  stay closed.
- L358-360, L384: an estimate is never lowered on uncertain evidence (41 reaches keep the old one).
- L392: the model cannot see water leave in a canal (diversions listed for LA only, L113-114).
- L399-400: an incomplete latest year counts on the months it has.
- L410-413: a gauge's record is not carried along the creek.
- L416-418: greenness rule only in LA and Jackson.
- L562: county lists keep closures past their reopening date.
- L601-603, L987: no traffic model; some drive times approximate.
- L606: trees are not in the sun hours.
- L698-699: the dry-creek rules catch 13 of 35 gauged dry creeks rated flowing (one-sided by the owner's rule).
- L716-718, L756-759: some desert canyons are probably too warm and are not gated.
- L750-751, L761-777: the heat gate uses air temperature; NorWeST and StreamCat miss by 4-6 C here.
- L802-803: warm lake-outlet rivers keep their credit (2.2 C above the estimate on average).
- L808-810: the estimate runs narrower than reality.
- L817-818: the channel factor goes by name only.
- L882, L888, L889, L905-919: NHD stage elevations unreliable; many lakes have no mapped inlet or outlet; DEC's
  layers and several bathymetry surveys cannot be used.
- L923-925: routes run a little short; times are a fit hiker's without stops; boats are not modelled.
- L928-931: Adirondack approaches go round lakes on foot, which raises remoteness and scores.
- L947-949: drop detection finds almost nothing in SE Pennsylvania and NE Connecticut.
- L950-953: thresholds were tuned on three LA ranges; falls on drainages under 1 km2 are below the floor.
- L954-957: CDFW barriers are left out of the table; before 2026-11-20 the check counted nothing.
- L961-967: named misses; pass-2 hits are places to check; `pool_depth_m` is usually 0.
- L975-989 (Caveats): drop height is not free fall; the NHD label is coarse; check closures and regulations;
  OSM check dams read as dams; some artifact flags are real falls; fire roads are ridden even where bikes may be
  banned; off-trail speeds are guesses; `non_fs_land` is not ownership.

SB:
- L14-16, L352-357: the DEM burn is parked (a reshuffle, one new flow-drop error).
- L50-51, L73-75, L114-115, L190-229: figures from the reach tables are not the map; `06_map.py` draws lines that
  are not reaches.
- L142-145: 48 creek pieces (22.5 km) newly marked down by the half-in-lake rule.
- L151-154: 19 headwater creeks of 0.52-0.99 km2 are no longer drawn.
- L162-164: 11 cut pieces lost the 1.2 trout factor.
- L177-183: lower Piru Creek credits the wrong dam; 31 short reaches carry a river's order; the first 0.4 mi of
  the Snake below Palisades Dam has no name.
- L231-272 (Fault 1): 31 lakes have their water put back in 200+ m from their outlet (Seventh Lake's outlet
  channel is not drawn); 29 remain after `_at_outflow`. Not fixed.
- L274-285 (Fault 2): 77 lakes are routed to a cell 300+ m from NHD's outlet. Not fixed.
- L506-509: `lake_outlets.py` can pick a small creek piece; look before reading its flags.

## 5. Concision

Size today: README 989 lines, 113.6 KB, 18,800 words; 13 lines are over 400 characters (L97 2,178; L390 1,310;
L881 1,564; L886 1,296; L909 1,254). It has 59 dates of November 2026, 34 "since / until 2026-..." clauses and
9 "over the 12 maps / areas" before-and-after counts. README L58 already names `MULTI_AREA_LOG.md` as "the
dated record of how the other areas were added and why".

History narrated inside the how-it-works text (could move to the log, leaving the rule):

| Lines | Now | What it is | Could be |
|---|---|---|---|
| 154-192 (step 3) | 39 lines, 4.3 KB | What 03 / 03b do, then how each rule was found (until 2026-11-19, the flat increment, Pilgrim Creek, 986 km, the measurement that missed lines) | 12 lines |
| 203-209 (step 4) | 7 lines | Why the detectors count carried water (Rainbow Falls) | 2 lines |
| 232-257 (step 5) | 26 lines, 3 KB | The floor's history and the shore cut's before / after | 8 lines |
| 258-288 (step 5) | 31 lines | Naming and status rules with a case for each | 20 lines |
| 289-353 (step 6) | 65 lines, 7 KB | 05c and crossbox; L310-345 is mostly case history | 35 lines |
| 354-418 (step 7) | 65 lines, 8.7 KB | 05b; fixes of 11-19 to 11-21 told in order, one 1,310-character line | 30 lines |
| 477-548 (cartography) | 72 lines, 7.5 KB | L511-515 a canvas bug; L523-548 three dated drawing fixes | 45 lines |
| 679-718 (water) | 40 lines, 4.6 KB | Four rules with their measurements and cases | a 12-line rule list |
| 747-759, 761-813 (heat, temperature) | 66 lines, 7 KB | A study write-up (what was tested) and the fit's history per area | 30 lines; the study to a note of its own |
| 828-931 (lakes) | 104 lines, 18.7 KB (16 % of the file) | Table column "Walk-in times changed" and L871-875 are change history; L877-891 is a source audit with cells of 700-1,560 characters; L905-919 lists surveys that could not be used | 40 lines here; the source audit and survey list to a `LAKES.md` or the log |
| 933-967 (validation) | 35 lines | L956-957 a bug's history; L959-967 LA anecdotes | 25 lines |
| 89-104 | 16 lines, 4.5 KB | L97 is one 2,178-character cell listing every state's trout sources | a per-area table, or `troutdata.py`'s docstring |
| 24-52 | 29 lines | L40-52 the publish story with dated push sizes | 20 lines |
| 651-659, 664-675 | 21 lines | The stale build block (A1) and order notes the drivers now carry | 6 lines pointing at the drivers |

Said more than once:
- The USGS Water Data API: L395-397, L612-614, L644-649.
- 05d runs before 05_score: L255, L390, L834 (and wrongly L853).
- A reach lying in a lake: L385-390 and L523-532.
- Lakes and walking: L844-848 and L921-931 (the Fontana Lake case at L846 and L927; "11.5 h" at L874 and L929).
- Carried water: L176-190, L203-209, L232-246, L324-345.
- Tailwaters: L111-114 and L732-735.
- "Tuned for LA": L106-108 and L820-822.
- Closures outside California: L99 and L566-572.
- The long trail: L100, L422-425, L489-492.
- Default layers: L493, L502, L516-522, L849.
- Forest Service orders are PDFs: L449-450, L564-565, L979-980.
- Gaia: L451-453 and L454-456.

Estimate: moving the history and the source audits out, and dropping the repeats, takes roughly 300 lines and
45 KB: a README of about 690 lines and 68 KB (about 11,000 words) with every current rule still in it. A further
split (README = how to run and what the outputs mean; a methods file for the scoring and hydrology rules; a
lakes file) would leave a README of 250-300 lines.

SB (509 lines, 40 KB) is itself a dated record: it corrects itself three times (L50-51, L73-75, L185-229) rather
than replacing the wrong figures, so a reader must reach line 185 to learn that L117-176 describe reach tables,
not maps. Its current-state parts are L1-20 (status), L231-292 (open faults) and L429-509 (files, how to rerun).

## 6. `MULTI_AREA_PLAN.md`

Verdict: a planning note of 2026-11-18, superseded. Nothing references it (not the README, not the scripts). The
area level it proposed was built (`config.py`), but as a description of the system it is wrong in most rows:

| PLAN line | PLAN says | Today |
|---|---|---|
| 1, 7-14 | "five study areas"; six listed | 12 areas (`config.py:54-359`): also `se_pa`, `smokies` and four `adk_*` |
| 10 | Jackson: three boxes | Seven boxes (`config.py:114-145`) |
| 11-12 | HU4: North Georgia 0313, 0315, 0306, 0601; Vermont 0415, 0108 | North Georgia also 0602, 0307; Vermont 0430 and 0108 (`config.py:152-159`, `:180-183`) |
| 12 | Vermont boxes "reach west to 73.25 W" | West to the New York line in Lake Champlain, cut by `clip_state` (`config.py:165-183`) |
| 21-23, 55 | Thermal term: PRISM August air temperature in every area | A fitted water-temperature estimate per area (`watertemp.py`; README L729-730) |
| 28-30 | `AREAS` holds `score={...}`; "Nothing area-specific stays hard-coded in the scripts" | No `score` key. Per-area tables live in the scripts: `scoring.py:153-166` (tailwaters), `flowlib.py:393-402` (diversions), `05c_drainages.py:46-76`, `05d_lakes.py:42-43`, `02f_known_falls.py` (`STATES`), `lake_bathymetry.py:424` |
| 34 | `creek-map/` gets one copy per area | One LA-era copy; not part of the pipeline |
| 40, 70-71 | Flow outside LA from the NOAA National Water Model; EROM as the fallback | EROM x a yearly gauge index (`02b_download_flow.py:201-232`; README L94) |
| 41 | Trout adapters share the columns `trout_found, survey_year, stocked, trout_water` | `trout_found`, `trout_absent`, `trout_water` (`11_context.py:373-374`, `:596`) |
| 46 | Long trails: AT in Vermont, Benton MacKaye / Bartram in Georgia, Nipmuck in Connecticut; layer renamed | One trail per area: none for Connecticut, only the Long Trail in Vermont (`config.py`); the file is still `pct.gpkg` |
| 47 | Closure adapters for WYDOT and CTDOT | Neither has a keyless feed (`07_road_closures.py:26`) |
| 49 | Tailwaters: Jackson Lake Dam; Tallulah lakes? | Jackson has none (`scoring.py:167-168`); Georgia has Lanier, Bull Sluice and Blue Ridge; the Smokies Nantahala |
| 56 | Heat gate start per area, hottest trout record + 2 C, "fixed in config" | One constant for every area, `HEAT_START = 29.0` (`scoring.py:135`); `11_context.py:327-331` only prints the hottest record |
| 57 | Relief filters lowered for Connecticut and the Atlanta corridor | 30 m for NE Connecticut and SE Pennsylvania, 50 m for the Adirondacks; nothing for the Atlanta corridor; closures 150 m everywhere |
| 79-84 | Status: refactor parked, `rerun.sh`, `data/fix_run.log` | Long done; `rerun.sh` no longer exists |

Still true: the area / range model and paths (L3-5, L31-33), LA under `la/` (L24), NIFC and PAD-US in place of
the California sources (L43-44), "none" for CDEC (L45), the rule that a stream loses score only when
near-certain (L61-62). Options: delete it, or head it "superseded 2026-11-19, see README and MULTI_AREA_LOG.md".
