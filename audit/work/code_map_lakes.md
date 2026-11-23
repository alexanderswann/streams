# Audit notes: drawing and lakes code

Read in full (static reading only, nothing in scripts/ imported or run): `06_map.py` (1,541 lines, working tree: the
committed d06b50b plus 50 uncommitted lines, file saved 11-21 22:57), `maplakes.py`, `05d_lakes.py`, `lake_bathymetry.py`,
`lakelidar.py`, `lakesources.py`, `lakedata.py`, `12_profiles.py`, `13_overview.py`, `14_portable.py`, `15_preview.py`,
`map_drainages.js`, `map3d.html`, `map_style.css`, `units.py`, `labelpaths.py`, `fish_score_diagram.py`. Greps and partial
reads of `03b_stitch.py`, `05_score.py`, `05b_flow.py`, `05c_drainages.py`, `flowlib.py`, `crossbox.py`, `scoring.py`,
`watertemp.py`, `config.py`, `troutdata.py`, the `run_*.sh` drivers and `publish_site.sh`. None of the 17 files changed
while they were being read (checked by file time at 23:35 and again at 23:48).

"Uncommitted" below means the 50 lines of 06_map.py that were in the working tree when it was read. Another session
committed them, unchanged, as 8bdf945 at 23:37 ("the stretch below a dam drawn as creek"); the file is the same and so
are the line numbers.

Line numbers are the working tree's. Every finding is marked **[C]** confirmed (code read end to end, or counted on a
file) or **[P]** plausible (follows from the code, not shown on data).

Three kinds of evidence beside the code, each named where used:
- **Logs**: `data/late_<area>.log`, `data/mid_<area>.log`. 06_map.py prints its own counters, so the logs hold each rule's
  effect for every run.
- **Published site copy**: `publish/alexanderswann.github.io/streams/` at commit 6875118 (11-21 22:16). Stable; it is
  the build before 05_score's shore cut and the side channels (d06b50b, 22:46).
- **Peeks at `output/`** with the project's Python and my own inline code: files written 22:58 to 23:33 while a rebuild
  was running. Indicative only; to be repeated by the measurements in the appendix.

Contents: A rules layered on rules · B popup values · C credits · D lakes · E the same logic twice · F dead code ·
G website size · H bugs and accuracy risks · Appendix: measurements.

---

## A. Rules in the drawing step that change stream features

### A.0 What happened, in order

| When | Commit | Where | What |
|---|---|---|---|
| 11-18 | 27a6a9f | 06_map.py 289-397 | basins cut by a box edge joined to the drainage they continue into |
| 11-19 12:45 | 3ec0e1a | 03b_stitch.py (new), 06_map.py 84-283, 398-468 | boxes routed as one surface; in the same commit 06 got the stream-order raise, `draw_through`, placing of unnamed outlines, sliver drainages |
| 11-20 16:34 | bd09086 | 06_map.py 687-713 | reaches lying in a lake moved to a layer shown only while Lakes is off |
| 11-20 17:43 | 64a4978 | 06_map.py | rivers drawn up to the lake shore |
| 11-20 23:51 | 94216dd | 06_map.py 178-255, 716-768, 820-920 | lake outlets as their own creek, every reach clipped at lake shores, shore stubs dropped, straight joins across dams |
| 11-21 01:57 | cbb8e2d | 06_map.py 724-730, 769-819, 921-939 | lake reaches' pieces past the lake take the neighbour reach's values |
| 11-21 19:50 | dd639bf | **03b_stitch.py** `route_lake` 357-413, `outflow_streams` 416-438 | root fix: lakes drain to the outlet along NHD lines, a stream line below each outlet |
| 11-21 20:26 | 80b42e8 | **05_score.py** 78-94 | root fix: the 1 km2 floor counts carried water |
| 11-21 22:46 | d06b50b | **05_score.py** 95-116, **flowlib.py** 183-304, **crossbox.py** `_at_outflow` 335-392 | root fix: links cut at lake shores; the dam link put at the top of the routed outflow |
| 22:57 (committed 23:37) | 8bdf945 | 06_map.py 204, 227-246, 273-274, 775-807, 818-819 | two more rules in 06 for a side effect of the 05_score cut |

No rule in 06_map.py was taken out when the root fixes landed. The uncommitted lines say why they exist: "since
05_score.py cuts the links at lake shores, 2026-11-21, the reach it meets there is lake water" (06:227-229), that is, a
patch in the drawing step for a consequence of the upstream fix.

**One root cause behind five patches [C].** 03b ends a lake's paths in a pit at the outlet cell (`fd[r_, c_] = PIT`,
03b:578) and starts the outflow line in the next cell (`r, c = r_ + int(DR[code]), c_ + int(DC[code])`, 03b:428). pysheds
reads pits as no direction (`fp[~np.isin(fp, CODES)] = 0`, 03b:653), so the lake's last line and the outflow line are one
cell (10 to 14 m) apart and never share a vertex. Patched in: 05_score.py 161-176 ("the lake's last reach ends one cell
short" ... `distance=1.5 * RES`), crossbox.py 335-392, 06_map.py `draw_through`, 06_map.py dam joins 835-920, and
06_map.py 785-807 (the 1 m look-up `tst_.query(en_[i], predicate="dwithin", distance=1.0)` finds no reach there, hence
the new fallback). Starting the outflow line on the outlet cell itself in 03b would remove the gap for all of them.

### A.1 Last logged run of 06_map.py per area (counters the script prints)

Runs before 22:46 are without the 05_score shore cut. Source: `data/late_<area>.log`, last `06_map` block.

| area | run | rows | order raised | draw_through breaks (km; "own creek") | in a lake | cut at a shore (pieces; stubs dropped) | re-valued: below outlet / above inlet | joins across dams (of cells; median m; in-lake joins; pit pieces) |
|---|---|---|---|---|---|---|---|---|
| la | 22:56 | 18,096 | 729 | 57 (34.4; 1) | 461 | 812 (557; 129) | 7 / 47 | 22 of 35 (15; 16; 0) |
| jackson | 22:41 | 10,739 | 788 | 46 (13.1; 1) | 478 | 821 (638; 127) | 11 / 62 | 22 of 31 (15; 7; 2) |
| n_georgia | 21:08 | 15,035 | 869 | 101 (24.2; 1) | 571 | 1,238 (1,041; 181) | 1 / 63 | 77 of 83 (43; 44; 2) |
| central_vt | 22:44 | 8,525 | 432 | 50 (12.2; 0) | 317 | 710 (679; 131) | 9 / 30 | 42 of 55 (9; 31; 1) |
| ne_ct | 22:49 | 3,879 | 650 | 105 (17.8; 1) | 488 | 1,101 (980; 223) | 14 / 65 | 81 of 147 (8; 85; 2) |
| lexington_va | 22:54 | 4,329 | 427 | 16 (5.4; 0) | 48 | 155 (204; 19) | 1 / 9 | 7 of 9 (9; 7; 0) |
| se_pa | 23:00 | 4,692 | 348 | 22 (6.9; 0) | 70 | 196 (235; 51) | 4 / 10 | 11 of 20 (18; 11; 0) |
| smokies | 20:52 | 8,943 | 628 | 28 (8.5; 0) | 430 | 627 (313; 51) | 0 / 26 | 11 of 14 (41; 5; 1) |
| adk_high_peaks | 23:08 | 9,808 | 909 | 116 (14.4; 14) | 1,196 | 1,999 (1,256; 374) | 27 / 137 | 123 of 203 (10; 99; 1) |
| adk_northwest | 21:47 | 8,751 | 1,188 | 299 (41.0; 17) | 1,376 | 2,435 (1,791; 549) | 7 / 106 | 254 of 349 (37; 131; 22) |
| adk_southwest | 21:38 | 7,156 | 710 | 193 (24.9; 10) | 712 | 1,475 (1,285; 365) | 2 / 64 | 170 of 223 (34; 89; 19) |
| adk_southeast | 22:04 | 8,853 | 1,240 | 243 (35.9; 7) | 1,175 | 2,203 (1,664; 334) | 4 / 98 | 206 of 269 (40; 102; 25) |
| **all 12** | | 108,806 | 8,918 (8.2%) | 1,276 (238.7 km) | 7,322 | 13,772 (10,643; 2,534) | 87 / 717 | 1,026 of 1,438 (in-lake 627; pit 75) |

Readings of that table [C, from the logs]:
- The joins across dams fell from a median 34-52 m to 8-18 m in the runs after 22:40: they now bridge the one-cell gap.
- The re-valued pieces did not go away with the shore cut. In Jackson they went from 1 / 28 (20:21 run) to 11 / 62 (22:41).
- `draw_through` still reports 16 to 299 breaks per area.

### A.2 The rules

Format: lines · what it does · when · upstream step with the same job · remaining effect and how to measure · verdict.
Measurements M1-M10 are spelled out in the appendix.

**A1 [C] 06:45** `done = [r for r in REGIONS if os.path.exists(f"{MAP_OUT}/{r}/streams_scored.gpkg")]`. A box that
was not scored is left off the map without a word. Baseline. Measure: boxes in config.py against
`output/<area>/<box>/streams_scored.gpkg`. **Keep**, but it should stop instead of skipping.

**A2 [C] 06:73** `s_ll = score(attach(s_ll.drop(columns="fish_score"), "sid", dirs, "streams"))`. The first-pass score
of 05_score.py:288 is thrown away and the final score is computed while the map is drawn. `scoring.score` also rewrites
`water_class` (scoring.py:309, 313) and adds `water_rule`, `tailwater`, `water_aug`, the factors. The final score exists
only in 06's exports, and 12_profiles.py reads it from there (12:31). Baseline. Measure: `flow_streams.csv.water_class`
against `stream_reaches_ranked.csv.water_class` (rows with `water_rule` set). **Move upstream** (a scoring step that
writes a table; the map then only draws).

**A3 [C] 06:76** `area_rank_pct`, "ahead of X% of reaches here". Ranked over every reach, lake reaches included
(7,322 of 108,806 in the last runs). 5398869, 11-18. **Keep** (or move with A2).

**A4 [C] 06:78-83** `drainage.fillna(MINOR)`, `fork.fillna(s_ll.drainage)`, `strahler.fillna(s_ll["order"]).clip(1, 7)`.
A missing `stream_drainage.csv` turns a whole box into "Minor drainages" silently. Baseline. Measure: NaN counts in
`<box>/stream_drainage.csv` against the sids of `streams_scored.gpkg`. **Keep.**

**A5 [C] 06:84-105 stream-order raise.** "Where a reach carries over twice its own box's drainage, its order is at
least the usual one in this area for its full drainage"; `carried = (full_ > 2 * s_ll.area_km2.values) & (full_ -
s_ll.area_km2.values > 5)`, `est = 1 + np.searchsorted(steps, np.log(full_.clip(0.01)))`. 3ec0e1a, 11-19. No upstream
step does this: 03b counts orders across boxes, but the count starts again at every lake outlet pit and at every river
entering the map. Effect: 8,918 reaches (8.2%), up to 14% in adk_southeast. For those the popup's "Order" and the legend's
"Line width = Strahler order" (map_drainages.js:548) show an estimate from drainage area, not the Strahler order.
Bug in it: see H6. Measure: M1. **Move upstream** (03b: carry the order across outlet pits and outside entries), or drop
it by drawing width from `area_full_km2`.

**A6 [C] 06:106-283 `draw_through`.** Follows the box's D8 path from each crossbox link to the first drawn reach and
draws it. 3ec0e1a 11-19; sub-rules 94216dd 11-20 and uncommitted.
- A6a 06:116 `if c_[6] >= 0.25 and c_[3] in done and c_[7] != "edge"`: only dam, pond and outside links. The link's
  0.25 km2 is below the map's own 1 km2 floor (05_score.py:12), so creeks under the floor are drawn below ponds (links of
  0.25-1 km2 in `inflows.json`: ne_ct 16 of 147, adk_northwest 53 of 349, la 3 of 36; peek).
- A6b 06:144-148, 158-176, 212-221: the `up`, `pred`, `chain` and "carrier" branches test `kind == "edge"`, which line
  116 has already removed. **Dead** (about 35 lines; `n_up` is always 0, the sort at 209 does nothing).
- A6c 06:250-252 `coords[r["hit"]] = new[:-1] + xy(r["hit"])`: the path goes on the front of the reach it meets.
- A6d 06:253-255 `extra.append((r["hit"], shapely.LineString(new), None))`: a new feature `sid+N` with the values of
  the reach it runs into.
- A6e 06:178-202, 230-249 (94216dd; widened uncommitted): "a lake's own creek". The piece takes every value (name,
  score, access, gradient) of the first reach **above the lake** and only the drainage of the link. Uncommitted 234-246:
  with no reach above, it takes the values of "the main creek running into the lake it meets" and no name.
- A6f 06:266-275: the pieces are appended to `s_ll` as rows, so they are also in `stream_reaches_ranked.csv` (H12).

Upstream now: 03b `outflow_streams` draws the line from the cell below the outlet; 05_score keeps it by the carried
floor; crossbox `_at_outflow` moves the link onto it. Remaining effect, peek at `output/` (22:58-23:33):

| | extra pieces | along an existing reach (80% of length within 8 m) | heads extended | by under 15 m |
|---|---|---|---|---|
| all 12 areas | 743 (139.9 km) | **455 (17.2 km)** | 395 (78.4 km) | **239** |
| ne_ct | 67 (11.3 km) | 41 | 38 (6.4 km) | 25 |
| adk_northwest | 175 (24.5 km) | 131 | 84 (10.9 km) | 60 |
| la | 31 (14.6 km) | 5 | 26 (19.7 km) | 4 |

So 694 of 1,138 actions (61%) redraw a reach that is already there: a second line 5-8 m beside it (mean 38 m long), or
one extra point at its head. Likely cause [P]: the path's points are cell centres (`T_ * (c_ + 0.5, r_ + 0.5)`, 06:137)
while reach vertices sit on cell corners (05_score.py:61-62), and the test `if on_[r_, c_]` reads a raster of those
lines (`all_touched=True`, 06:131-132), which marks the cell on one side of a line that runs along a cell edge. The real
work left is about 200 km: rivers entering from outside the map (9 to 37 links per area in the eight areas looked at)
and a few long paths below dams.
Measure: M2. **Verdict: keep for `kind == "outside"` only, or move that upstream** (03b can seed stream cells down the
D8 path from each outside entry, as `outflow_streams` does below a lake, so the stretch becomes a scored reach);
**remove** the dam and pond handling and the dead edge branches; A6e goes with it.

**A7 [C] 06:289-397** basins cut by a box edge take the drainage they continue into; reaches follow
(`s_ll["drainage"], s_ll["fork"] = dcur, fcur`, 06:388). 27a6a9f 11-18, parts 3ec0e1a. 05c runs per box and cannot do
it. Effect (logs): la 1,802 links, jackson 5,386, smokies 3,689; "unnamed outlines joined: 5365 of 6041" in Jackson.
Measure: M3. **Move upstream** (an area-level pass after 05c): today the lakes read the drainage 05c wrote before this
renaming (H7).

**A8 [C] 06:398-453** unnamed outlines placed "by what is across the edge" or "by what is beside them"
(`max(by_d.values()) >= 15 * 50`). 3ec0e1a. Effect (logs): 170 to 885 across, 9 to 259 beside, per area. M3. **Move
upstream** with A7.

**A9 [C] 06:454-468** a named drainage under 2 km2 joins its neighbour (`a_ < 2e6`; "Pacific Creek at Moran").
3ec0e1a. Effect: `sliver drainage ... ->` lines in the logs. M3. **Move upstream** with A7.

**A10 [C] 06:469** `basins = basins[basins.drainage != MINOR]`: unnamed outlines are not drawn. Drawing choice. **Keep.**

**A11 [C] 06:695-713 `in_lake_drawn`.** A reach flagged `"in:"` by 05b that lies "at least half inside a lake the Lakes
layer draws". bd09086 11-20. Upstream: 05b's `below_dam` "in:" (05b:587-597) and 05_score's `_wet` (05_score:116). After
the shore cut an "in:" reach lies in the water by construction. Left in use at 06:863/881 and 06:1101 only;
`cut_ |= s_ll.in_lake_drawn.values` (06:740) adds nothing, since every such reach intersects a lake (06:737-739).
"Lies in a lake" is defined three ways in this file: `in_lake_drawn` (704-712), `mostly_in_` (763), and the "in:" prefix
recomputed four times (186, 704, 770, 925). Measure: M4. **Remove** (use the "in:" flag).

**A12 [C] 06:732-753, 829-830 shore clip.** Every reach touching a Lakes-layer lake is replaced by its parts outside
(`shapely.difference(g_, shapely.union_all(lakes_[ls_]))`), and the whole reach goes once more into the Lakes-off layer.
94216dd 11-20. Upstream: `cut_at_shores` cuts links, but only at lakes of 8 ha or more that hold level water
(flowlib.py:199-207, 246-260), only where 50 m lies on each side (`LAKE_PIECE_M = 50.0`, flowlib.py:187), and it removes
nothing. The Lakes layer holds lakes from 0.5-2 ha (05d:42-43). Two lake sets and two shore tolerances are the source of
A13-A16. Effect: 13,772 reaches cut (12.7%), 28% in adk_northwest. Measure: M4. **Keep**, or cut upstream at exactly the
drawn outlines so this step only assigns layers.

**A13 [C] 06:754-768 shore stubs dropped.** A piece of a reach lying mostly in a lake, both ends on one lake's shore,
that "never gets 40 m from it" (`.max() < 40`). 94216dd. 2,534 dropped in the last runs. After the 05 cut these are the
under-50 m excursions the cut leaves. Measure: M5. **Removable** once lake reaches are hidden whole while Lakes is on.

**A14 [C] 06:769-819 lake-end pieces re-valued.** A lake reach's piece past the outline takes all values "of the reach
below (an outlet) or of the biggest reach above (an inlet)". cbb8e2d 11-21 01:57; uncommitted 786-807 adds two more
guesses (the creek it runs into if that carries at most 1.5 times as much, else the first creek above the lake with
`own_[k_] = kmv_[i]`). Effect: 804 pieces. Peek (ne_ct, jackson): all short, none over 50 m, about 1-2 km per area.
Measure: M5. **Removable** with A13; otherwise move upstream by cutting at the drawn shore.

**A15 [C] 06:820-826** a piece under 20 m "that meets no line drawn whole and no longer piece" is dropped. 94216dd.
Measure: M5. **Removable** with A13.

**A16 [C] 06:829-830, 995** the whole of every lake-touching reach is written a second time (`s_ll[cut_].assign(lk_=True)`,
`s_feat_lake`). Published: 13,590 extra features, 13.0 MB. With Lakes off, the pages draw the clipped pieces and the whole
reaches on top of each other (map_drainages.js:186-192, map3d.html:555-561). **Keep the switch, restructure** (store in-lake
and out-of-lake parts once each).

**A17 [C] 06:835-920 straight joins across dams.** A two-point line from the line below the dam to "the nearest point
of the lake's shore" or to a pit, with the values of the reach below; a second line inside the lake for the Lakes-off
layer. 94216dd. `DAM_TOL, TRUNK_TOL = 150, 300` (06:847). Upstream: `outflow_streams`, which leaves the one-cell gap
(A.0). Effect: 1,026 joins, median now 8-18 m, longest 58-147 m. Measure: M6. **Move upstream** (close the gap in 03b),
then remove.

**A18 [C] 06:921-939** a lake reach's piece "from a lake to a pit by its dam" takes the values of the line below the
dam. cbb8e2d. 75 pieces. **Removable** with A17.

**A19 [C] 06:945-946** `simplify(0.00008)`, `set_precision(..., 1e-5)`, empties dropped. bd09086 / baseline. **Keep.**

**A20 [C] 06:949-952** a side channel's name gets " (side channel)" appended. d06b50b. Upstream: 05_score `side_of`.
The 2D page strips it again for the profile link (map_drainages.js:109), the 3D page does not (H4). **Keep the flag,
drop the rename**: pass `side_of` as a property and let the page add the words.

**A21 [C] 06:953-992** the properties: colour from the renamed drainage (954), `fl` (956), the flow sentence (957-959),
`a` = full drainage with a fall-back (962), access (963), sun (964-974), heat (975), fire (976-979), trout (980-981),
notes (982-989), rank (991), midpoint (992). Formatting of upstream values; the words are built here (B, G). **Keep**,
compose the sentences in the page.

**A22 [C] 06:994** `.sort_values(["o", "fs"])`: draw order. **Keep.**

**A23 [C] 06:1237-1240** "Best remote trout water (score >= 55)": a derived layer, its geometry written a second time
into stream_map.html. **Move to the page** (a filter on `fs`).

**A24 [C] 06:1456-1458** start points "used by good water": `s_ll.fish_score >= 50`. A second threshold for good water
beside A23's 55. **Keep**, one constant.

**A25 [C] 06:1509-1512** the all-areas map takes whole reaches of order 4 and up, lake reaches and `+N` pieces
included, with the raised orders of A5. **Keep.**

**A26 [C] 06:1101** trails and roads are split into runs "beside a creek" of order 2+ not in a lake. Changes trail and
road features, not streams. **Keep.**

**A27 [C] maplakes.py:59-65** each lake's drainage and fork are looked up at map time in 05c's per-box outlines
(`dparts = [gpd.read_file(f"{MAP_OUT}/{r}/drainages.gpkg") ...]`), that is before A7-A9 rename them (H7).
**Move upstream** with A7.

**A28 [C] maplakes.py:91-130** state stocking and survey records are matched to lakes at map time, and "a lake
without a name takes the one its own stocking or survey record gives it" (127-130). The name is then missing from the
"in:<lake>" strings 05b wrote. **Move upstream** (05d).

**A29 [C] map_drainages.js:181-193, 510-511; map3d.html:117, 555-563; 14_portable.py:208-210** the Lakes-off layer is
shown or hidden with the Lakes switch. **Keep.**

**A30 [C] map_drainages.js:85, 87-99, 171-172; map3d.html:118-129** colour lightened for orders 1-2, width by score in
fish mode, casing from order 3, order clamped to 1-7 a second time (`p.o = o`, map3d.html:120). Styling. **Keep.**

**A31 [C] map_drainages.js:14-56; map3d.html:196-204** trails and roads beside a creek are drawn shifted. Drawing only;
`129500 / Math.pow(2, z)` is "metres per screen pixel at 34°N" in every area (H16). **Keep.**

---

## B. What the popups show and where it comes from

### B.1 Stream popup (map_drainages.js:107-124, map3d.html:583-594, 14_portable.py:142-156)

| shown | property | column | computed in | units |
|---|---|---|---|---|
| title | `n` | `name` | 05_score.py:131-146 (vote), 149-207, 209-278; suffix added 06:952 | |
| fork, drainage | `k`, `d` | `fork`, `drainage` | 05c_drainages.py:546, then renamed 06:289-468 | |
| Fish score | `fs` | `fish_score` | scoring.py:322-323, **called from 06:73** | |
| "ahead of X% of reaches here" | `rk` | `area_rank_pct` | **06:76** | |
| Order | `o` | `strahler` | 03b strahler.tif, sampled 05c:379-380; **raised 06:90-105** | |
| drainage | `a` | `area_full_km2`, else `area_km2` | 05c:557; 05_score:113 | km2 to 0.01 (06:962), `SQMI` in the page |
| Summer flow | `dq` | text | **06:620-661** from 05b's `water_class`, `dry_cfs`, `dry_cfs_drought`, `flow_years`, `flow_src`, `below_dam`, `below_div`, `div_share`, `div_years`, `gauge_*`; scoring's `water_rule`, `water_by_gauge`, `tailwater` | cfs |
| NHD flow | `fl` | text | **06:956** | |
| Elev | `el` | `elev_m` | 05_score:118 | whole m, `FEET` in the page |
| gradient | `gr` | `gradient_pct` | 05_score:120 | % |
| Access | `acc` | text | **06:477-492** from 08_hike (`approach_min`, `bike_min`, `walk_min`, `bike_check*`), 09_drive (`drive_min`, `drive_km`, `th_road`) | `mi()` |
| Sun | `sun` | text | **06:964-974** from 10_sun (`sun_hours`, `shade_pct`), 11_context (`canopy_pct`, `northness`, `air_aug`), scoring (`water_aug`, `tailwater`) | `degf()` |
| Heat | `ht` | text | **06:681-686** from `air_aug`, `heat_factor`, and `HOT` (06:676-678) | `degf(,1)` |
| Fire | `burn` | text | **06:976-979**, severity words 06:664-666 | |
| Trout | `tr` | `trout_water`, `trout_ev` | 11_context / troutdata | |
| Notes | `flags` | text | **06:982-989** | |
| profile link | `n`, `y`, `x` | midpoint of the drawn piece | 06:947, 992 | |

For a clipped, joined or re-valued piece (A6, A14, A17, A18) every value is another reach's.

### B.2 Text made in 06_map.py or in the page rather than upstream [C]

- 06:477-492 the access sentence; 06:620-661 the flow sentence, with "since 2011" typed in (06:634; the year is
  `FIRST_YEAR = 2011` in 02b_download_flow.py:26) and "(satellite, 2022-24)" typed in (06:648; `GREEN_YEARS` in
  flowlib.py:460).
- 06:967 "slope faces north / south / east/west or mixed" at `n > 0.04`, `n < -0.04`: a second threshold for
  northness beside the score's ±0.15 (scoring.py:285).
- 06:664-666 burn severity words at 0.85 / 0.6 / 0.3.
- 06:63-68 "Road closure X mi away": the nearest full closure within 3 km in a straight line, not on the approach.
- 06:603-617 `gauge_label` rewrites USGS station names from an abbreviation table.
- 06:1256-1282 the whole drop popup; 06:1310-1317 the falls popup; 06:1415-1418 gauges; 06:1436-1437 trout records.
- maplakes.py:174-242 the whole lake popup, the fish class (`_fish`, 136-156) and the record matching (91-130).
- The pages: the unit conversions, "ahead of X% of reaches here", every trail, road and parking tooltip
  (map_drainages.js:265-283, 343-350, 389-394), the legends.

### B.3 Drop popup (06:1256-1282) [C]

`stream`, `region`, `status`, `kind`; "Drop **ft(drop_m)** over ft(run_m) (max slope {max_slope:.2f})"; "Channel slope
above / below · knick ×"; pass 2: `excess_drop_m`, `pool_depth_m`; "Drainage sqmi(area_km2)"; "summer: water_class (about
cfs(dry_cfs) cfs typical low flow)"; elev; access; shade; burned; trout water; habitat; wilderness; access restriction;
the closure line; coordinates; links. Columns from 04_knickpoints / 04b / 05_score (`waterfall_candidates.gpkg`), 05b
(`flow_drops.csv`), 08, 10, 11. Note: the drop shows `area_km2`, the stream popup at the same spot `area_full_km2`.

### B.4 Lake popup (maplakes.py:174-242) [C]

| row | from | computed in |
|---|---|---|
| Type | `lake_type` (Wyoming's classes, words in `KIND` maplakes:22-24) or `ftype`; `acres(ha)` | 05d:742 `ha` = area of the final outline / 1e4 |
| Elevation | `ft(elev_m)` + source words | 05d:755-761 |
| Fish | summary, up to 5 record lines, survey, "Also recorded" | maplakes:136-156, 196-199; 05d:866-910, 985-998 |
| Depth | "max ft(depth_max_m), mean ft(depth_mean_m) · depth_src · depth_note" | 05d:201-214, 958-984; lake_bathymetry.py:458-473 |
| Water | outlet and inlet names or counts | 05d:795-815 |
| Access | `approach(r)` + "route about mi(route_km)" | 08_hike `hike_lakes.csv`, 09_drive |
| On site, Rules | `access`, `designation`, `rules` | lakesources.extras, 05d:1006-1028 |
| Land | PAD-US unit, access flag | 05d:1036-1071 |
| notes | `conflict`, `water_note`, `private_shore`, wilderness, drainage · fork | 05d; maplakes:59-65, 81-88 |
| Outline | `src_outline`, "(NHD acres(nhd_ha))", `outline_note`, name source | 05d:598, 593-608 |

### B.5 Parking and trailheads [C]

`poiTip` (map_drainages.js:389-394, map3d.html:607-611, 14_portable.py:223-225): name, kind, status, "with parking", fee,
"Spaces", note, "Forest Service page". All from 02e_access.py's `parking_trailheads.gpkg`. `url` and `status` come only
from Forest Service records (02e:189-197), so those words are right. Start points (06:1461-1471): "P · road · X min / mi drive".

### B.6 Metric units left in what is shown

- [C] None found in the text 06_map.py, maplakes.py, 05d_lakes.py and lake_bathymetry.py build: all go through
  `units.py` or are written in feet.
- [C] Falls names and notes keep the source's metric words with feet added in brackets, by design
  (`imperial_text`, 06:1308-1309, units.py:84-94).
- [P] Text quoted from sources is not converted anywhere else: closure reasons (06:1336), trout record labels
  (06:1435), trail `closed_why`, state lake rules. Not checked on data.

### B.7 Rounding that hides or invents precision [C]

- "~73 m" and "~43 m" (lakedata.py:39-41, quoted in the `ref`) become "max 240 ft, mean 141 ft"; Jackson Lake's
  "~143 m" becomes "max 469 ft" (published popup). Three figures from a value given as approximate.
- 05d:587 `ft(stage - lev, 1)`: "14.8 ft below its normal level", to a tenth of a foot, where the same file says NHD's
  level "can be off by a few metres, or by 12" (05d:506-507).
- 06:599-600 `cfs`: two decimals under 1 cfs ("0.03 cfs") for a model value scaled by drainage.
- Depths typed in feet go through metres rounded to 0.1 and back to whole feet (lakedata.py:47, maplakes:165). Checked
  for all 24 typed values: none changes.

### B.8 The stated error bar [C]

One in all the files: 06:672-674, "summer water about 61 °F (estimated from air temperature and elevation, ± 3 °F)".
`degf_diff(_wt.get('rmse_loo', 3))`: the leave-one-out RMSE in °C of the area's regression on its measured sites
(watertemp.py:345), times 9/5, to a whole °F. For an area using its group's fit it is the error on the area's own
sites, in sample (`rmse_loo=round(rmse_own, 2)`, watertemp.py:373). One number for every reach of the area, also where
the inputs were held at the edge of the fitted range (`np.clip(c[t], *rec["ranges"][t])`, watertemp.py:432). It is one
standard error, not a bound. The fall-back `3` is never used: `ok` and `rmse_loo` are set together (watertemp.py:344-347).

---

## C. Credits

### C.1 Where the credit line is built [C]

- 06:37-40 `LBL["credits"]`, with guides of 50 falls or more on the map added at 06:52-58.
- 2D: map_drainages.js:512-515 `"Trails &amp; PCT © ...OpenStreetMap... contributors · " + credits`, with an LA list as
  fall-back.
- 3D: map3d.html:213 `"USGS NHD · " + credits`; per-source lines at 147 (terrain), 286 (roads), 318 (trails), 406 (trout).
- One-file map: 14_portable.py:114, a fixed string. The area's credits are packed (`credits=lbl.get("credits")`,
  14:52) and never shown.
- All-areas page: 13_overview.py:74 `"Streams: USGS 3DEP &amp; NHD"`.

It names: USGS National Digital Trails, USFS, CDFW (LA), iNaturalist, CAL FIRE or NIFC, NIFC WFIGS, USGS gauges and
debris-flow hazard, CDEC (LA), TNC Natural Flows or NHDPlus V2 (EROM), PRISM, and for falls OSM, USGS GNIS, Wikidata
"and the guides named in each".

### C.2 Sources in the published files that the line does not name

Lakes (my files):
1. [C] USGS NHD High Resolution lakes and stream lines (05d:71-75, 767) and USGS 3DEP 10 m and 1 m lidar
   (lakelidar.py:29-30). The 2D line names neither; LA's has no NHD at all.
2. [C] Wyoming Game & Fish fishing guide (05d:170). Named in the popups only.
3. [C] GBIF (05d:835-848) and through it MARIS, iNaturalist, USGS NAS, museum collections. Each record line names its
   dataset; GBIF is not named. The code keeps no licence field (05d:849-854), so records under any licence are
   republished. [P] some iNaturalist records carry non-commercial licences.
4. [C] EPA National Lakes Assessment (lakesources.py:30-39); PAD-US (05d:1036); OpenStreetMap water outlines and names
   (05d:635-644; the page's OSM credit is worded for trails).
5. [C] CT DEEP, Vermont ANR and Fish & Wildlife, Virginia DWR, PFBC, PA DCNR, NCWRC, TWRA, TVA, NYSDEC through
   data.ny.gov (lakesources.py:98-231, 286-368).
6. [C] Depth surveys: CT DEEP contours, Vermont ANR soundings, USGS (Little Rock, Chambers), DCNR bands, NOAA ENC
   (lake_bathymetry.py:36-37, 123, 200, 239, 300); typed-in reports (lakedata.py). Named in the Depth row.

Other layers (credit line is in my file; sources in others'):
7. [C] Every state fisheries agency outside California, and Trout Unlimited / EBTJV (troutdata.py:132-540). The line
   has "CDFW" for LA and nothing elsewhere.
8. [C] Sentinel-2 through Element 84 (02g_greenness.py:32), shown as "(satellite, 2022-24)"; the Water Quality Portal
   (watertemp.py) behind the water temperature; USFS canopy cover; USFWS critical habitat; CPAD; wilderness outlines;
   state road-closure feeds (the closure tooltip has its own Source field).

### C.3 Licence notes recorded in the code [C]

- lakesources.py:284-285: "DEC's own ArcGIS layers say \"secondary distribution of the data is not allowed\", so lake
  facts come from these instead" (data.ny.gov). **But troutdata.py:490 reads DEC's own ArcGIS**
  (`NYDEC = "https://services6.arcgis.com/DZHaqZm9cxOD4CWM/ArcGIS/rest/services"`: `Inland_Trout_Stream_Fishing`,
  `Water_Quality_Classifications`, `Trout_Stream_Fishing_Access`, lines 497-525). Its text is in the published
  Adirondack pages: "NYSDEC" occurs 6,838 times in adk_northwest's map3d_data.js and 1,448 times in each of its pages.
  Whether those three layers carry the term was not checked (no network). [C] for the code, [P] for the licence.
- lakesources.py:12, 140: "Used with credit to PFBC, as its licence asks". The credit is the "(PFBC)" at the end of
  each popup line (lakesources.py:148, 157-158, 164); not in the credit line.
- lake_bathymetry.py:18-20: NOAA's agreement allows redistribution "if their origin and the agreement are shown: the
  popups name both". Done in the lake's Depth note (lake_bathymetry.py:418-420). The contour tooltips name the origin only
  (lake_bathymetry.py:405).
- lake_bathymetry.py:14, 20 and lakedata.py:9-12 record surveys that are "not public" or "on request"; none is used.
- No comment in any script records the terms of the falls guides. `data/known_falls_curated.csv` has 116 rows from
  nnywaterfalls.com and 93 from the World Waterfall Database; `known_falls_curated_gawaterfalls.csv` 695 from
  gawaterfalls.com. A guide is named in the credit line only from 50 falls on one map (06:54): adk_northwest's published
  line names no guide.
- No "written permission" or "no licence" note exists in the 17 files.

### C.4 Attribution gaps that can be seen on the pages [C]

- The all-areas page draws six long trails from OpenStreetMap relations (13:99-103) and "OpenStreetMap" occurs 0 times
  in the published index.html.
- "Trails & PCT ©" is typed into both maps (map_drainages.js:512, map3d.html:318) and shown in the eleven areas whose
  long trail is not the PCT.

---

## D. Lakes

### D.1 How each value is made [C]

- **Acres**: `lk["ha"] = (lk.area / 1e4).round(2)` (05d:742) on the final outline: the lidar shoreline where one was
  used (05d:597), else NHD's, an agency's or OpenStreetMap's. Computed before a lake reaching past the map is clipped
  (05d:1098-1103), so it is the whole lake. Shown by `acres()`: whole acres from 10, else one decimal.
- **Depth**: in this order. (1) Wyoming's guide text through `feet_to_m` (05d:155-161, 201-214); with several records
  the mean is `np.nanmax(dmean)` (05d:214), the largest of the means. (2) `lakedata.DEPTHS` and EPA soundings:
  `best = min(full, key=lambda d: (d["rank"], -d["max_m"]))` (05d:963) replaces it; others become "also" or "conflicts:"
  notes at "> 2 and ... > 0.2" (05d:979). (3) lake_bathymetry.py:458-473: a survey replaces the maximum unless
  `old > new + 0.5`; its mean always replaces the mean, its note always replaces the note.
- **Fish**: `game_fish` (Wyoming only, 05d:199-207); GBIF Salmonidae records within `EV_BUFFER_M = 50` and uncertainty
  up to `EV_MAX_UNCERT_M = 250`, any year (05d:862-873); state records matched at map time (maplakes:91-130); class in
  `_fish` (maplakes:136-156).
- **Outlets and inlets**: NHD HR lines of type 460 and 336 that start within 20 m of the shore and end outside a 2 m
  margin, and the reverse (05d:771, 792-803). An unnamed outlet is followed down up to 80 lines (05d:777-789) and stored
  as "unnamed, flows to X" (05d:808).
- **Regulated**: `ftype == "reservoir"` or an OSM dam or NHD dam line within 100 m (05d:520-523, again 697-703). Never
  shown; it gates the drawn-down test.
- **Drawn down**: `stage - lev > DRAWN_DOWN_M` and `shore - lev > 1.0` on a regulated lake (05d:583-584). The elevation
  shown is then the normal level (05d:759-761). Lakes over `LIDAR_MAX_HA = 600` are never tested (05d:499).
- **Dry or marsh**: under half the outline within 15 cm of one level, 0.8 ha or more, and the 10 m DEM not level
  (05d:546). The note starts "little level water" (05d:572). The map's dashed edge for it never draws (H1).

### D.2 Constants and thresholds

| name | value | where | how chosen, if recorded |
|---|---|---|---|
| `BUILT` smallest unlisted pond | 0.5 / 1.0 / 2.0 ha by area | 05d:42-43 | 44-46: "1,835 farm ponds of 0.5-2 ha" in N Georgia; 450 in SE PA; "1 ha keeps the small brook trout ponds" |
| `LEVEL_TOL_M` | 0.3 m | 05d:53 | not recorded |
| `EV_BUFFER_M`, `EV_MAX_UNCERT_M` | 50 m, 250 m | 05d:54-55 | not recorded |
| `DROP` name filter | regex | 05d:56 | 81-83: treatment ponds by the Delaware |
| pieces of one lake | 30 m same name; touch 1.0 m | 05d:117, 122 | "Beach Pond ... 20 m apart" (109) |
| agency outline joins | 0.5 of the smaller | 05d:181, 251 | not recorded |
| NY stocking by town | 300 m; 0.5 of the lake | 05d:304, 306 | not recorded |
| NY list point | 1,000 m named; 150 m | 05d:332, 337 | not recorded |
| DEM sample | 10 m in; 0.3; 10 cells | 05d:392-393, 408 | "one cell in from the shore" |
| NHD stage read as feet | within 15 m; dropped beyond 30 m | 05d:416, 418 | "Pachaug Pond 159 against a 48 m surface" |
| `LIDAR_MAX_HA` | 600 ha | 05d:438 | "Jackson Lake, Palisades: regulated" |
| `DRAWN_DOWN_M` | 2.0 m | 05d:439 | 580-582: 50 North Georgia lakes where NHD sits 2-28 m over full water |
| lidar window margins | 60, 240, 720 m | 05d:459 | not recorded |
| neighbour is the same water | 0.2 of the smaller | 05d:473 | "a small NHD pond inside a bigger OpenStreetMap one" |
| runs into a river | 2,000 m2 and 0.1 | 05d:485, 672 | "a 2.3 ha pond by the Schuylkill took in 7 ha of river" (86-87) |
| dam near the shore | 100 m | 05d:522, 702 | not recorded |
| level, not flattened | 0.7 within 15 cm | 05d:544 | "Bills Bayou Pond: 95%" |
| dry or marsh | under 0.5; 0.8 ha; DEM not 0.7 level | 05d:546 | "Dry Basin Lake: 13 m of relief" |
| neighbour reservoir | 500 m; 1.0 m; 1.5 m | 05d:549, 557-558 | "the unnamed 15 ha lake 214 m from Jackson Lake"; "Cochrans Lake North" |
| shore over the bed | 1.0 m | 05d:565, 584 | "Cave Mountain Lake" |
| stage and shore agree | 2.0 m | 05d:586 | "Lynchburg Reservoir" |
| two pools | 0.3 ft; 3 ft | 05d:604-605 | "Toccoa Reservoir" |
| OSM water kept | under 0.2 covered; MIN_HA; 0.3 same water | 05d:654, 665, 676 | "R Park in Wilson" |
| OSM name | 0.5 both ways; none within 2 km | 05d:718, 728 | "Walace Lake" on two ponds 700 m apart |
| off the map | under 0.5 inside and under MIN_HA inside | 05d:747 | "Fort Loudoun Lake", "Pascoag Reservoir" |
| shore and body margins | 20 m, 2 m | 05d:792-793 | "Holly Lake's outlet starts with a 13 m" piece |
| depth record match | 1,500 m by name; 150 m | 05d:928, 936 | "Timberline Lake's lie 783 m from NHD's lake" |
| EPA sounding to lake | 100 m | 05d:950 | not recorded |
| depths disagree | 2 m and 20% | 05d:979 | lakedata.py:4-5 |
| state fact to lake | 150 m point; 0.33 outline | 05d:1017, 1022 | not recorded |
| PAD-US ring | 30-300 m; 48 points; 0.3 or 0.6 | 05d:1052-1055 | "Jackson Lake, with a strip of shore up to ~300 m wide" |
| stored past the map | 2,000 m | 05d:1100 | "Lake Champlain's outline runs to Canada, 30,000 points" |
| `FLAT_TOL` | 0.005 m | lakelidar.py:32 | "only absorbs float rounding" |
| `MIN_PART_M2`, `MIN_STEP_M2` | 25, 200 m2 | lakelidar.py:33-34 | "a 2.7 ha Adirondack pond's specks" (189) |
| survey gap | over 2% no data | lakelidar.py:139 | not recorded |
| core, look-around | 3 m in; 30 m; 0.3 | lakelidar.py:170-171, 181, 196 | not recorded |
| contour step | 5 / 10 / 20 ft at 40 / 120 ft | lake_bathymetry.py:41-42 | not recorded |
| `LR_OFFSET_FT` | 106.4 ft | lake_bathymetry.py:130 | 126-129: median over 105,012 cells against the lidar |
| `LR_ZERO_STORAGE_FT` | 3,199.46 ft, within 3 ft | lake_bathymetry.py:131, 169 | USGS stage-storage table |
| `CH_POOL_FT` | 579.2 ft | lake_bathymetry.py:241 | USGS SIM 3346 |
| `CHAMPLAIN_LLL_FT` | 93.0 ft | lake_bathymetry.py:308 | Coast Pilot 6 |
| Champlain sanity | 300-420 ft | lake_bathymetry.py:400 | "about 400 ft" |
| deeper record stays | 0.5 m | lake_bathymetry.py:464 | not recorded |
| record to lake at map time | 2,000 m named; 150 m | maplakes.py:107, 116 | "CT DEEP's stream surveys sit at the inlets and outlets of 44 Connecticut ponds" |
| lake outline on the page | 2 m simplify, 6 decimals | maplakes.py:255 | not recorded |
| `MIN_RESERVOIR_KM2` | 0.08 km2 | flowlib.py:8 | "debris basins, ponds" |
| `LAKE_PIECE_M` | 50 m | flowlib.py:187 | "a line clipping a point or a cove" |
| `LEVEL_HA`, `LINE_PULL` | 2 ha, 5.0 | 03b_stitch.py:44-45 | not recorded |
| `DAM_TOL`, `TRUNK_TOL` | 150 m, 300 m | 06_map.py:847 | "20-150 m from the shore at some 335 outlets" |
| stub, sliver | 40 m, 20 m | 06_map.py:766, 820 | "the four stubs of the Snake by Donoho Point" |
| own-creek ratio | 1.5 | 06_map.py:230, 797 | "Taggart Creek's 2.1 km" |

### D.3 Rules made for one named lake [C]

Each of the rows above that quotes a lake. In addition:
- lake_bathymetry.py:346 `me = lk[lk["name"].fillna("").eq("Lake Champlain")]`: an adapter found by the lake's name;
  306-307 its chart cells typed in.
- lake_bathymetry.py:134-197 and 244-297: one function each for Little Rock Reservoir and Chambers Lake.
- maplakes.py:100-102 word-order matching for "Gregory Lake" and "Hansen Dam Lake"; 127-130 "Yucaipa Lake".
- maplakes.py:22-24, 227-228, 233 Wyoming's lake classes, regulations link and legend.
- 05d:890, 994-997 conflict sentences with "Game & Fish" and "gill-net" typed in.
- lakelidar.py:203-206, 231-234 "Tugaloo Lake", "Seed Lake", "Toccoa Reservoir", "Unicoi Lake", "String and Leigh".

### D.4 Lake values typed in by hand [C]

- lakedata.py:38-62 Jackson: Jenny Lake 73 / 43 m, Jackson Lake 143 m, and 24 alpine lakes in feet with UTM positions.
- lakedata.py:67-108 Lake Arrowhead 46.2 / 18.6 m; Lake Robertson 13.7 m; Marsh Creek 78.5 ft, Hopewell 20 ft,
  Scotts Run 22 ft, Struble 19 ft.
- lakedata.py:110-135 22 Jackson gill-net results and one Pennsylvania trap-net result, as sentences.
- lake_bathymetry.py:130-131, 241, 308 the four datum constants; 201-202 survey dates; 296 "150,779 soundings" typed
  into the note, not counted from the file; 405 "lake surveys of 1870-1939".
- lakedata.py's `ref` and `method` for every record are never read (F).

---

## E. The same logic written twice

Between the three pages and the two all-areas pages [C]:

| what | copies | lines that could go |
|---|---|---|
| stream popup | map_drainages.js:107-124; map3d.html:583-594; 14_portable.py:142-156 | ~27 |
| stream tooltip, `where` | map_drainages.js:101-106; map3d.html:582, 601; 14_portable.py:143 | ~6 |
| `SQMI`, `FEET`, `esc` | map_drainages.js:63-67; map3d.html:100-104; 13_overview.py:75-78; 14_portable.py:99-103; profiles.html:143, 168 | ~15 |
| widths, opacities, order colours, fish ramp | map_drainages.js:6-8, 59-60, 69-72, 85, 92; map3d.html:105-115, 121, 125; 14_portable.py:130-132 | ~20 |
| road classes | map_drainages.js:330-338; map3d.html:275-283; 14_portable.py:137-139 | ~15 |
| road tooltip, maintenance levels | map_drainages.js:339-350; map3d.html:612-622 | ~11 |
| trail tooltip, bike line | map_drainages.js:257-283; map3d.html:623-641 | ~22 |
| parking tooltip | map_drainages.js:388-394; map3d.html:607-611 | ~6 |
| legend key and focus bar | map_drainages.js:574-614; map3d.html:502-534 | ~33 |
| drainage and fork label rule | map_drainages.js:448-459; map3d.html:131-140 | ~8 |
| "Go to" menu | map_drainages.js:542, 621-624; map3d.html:70, 681-685 | ~5 |
| the all-areas map (areas, outlines, rivers, trail, labels, panel, links) | 13_overview.py:65-133, 143-153; 14_portable.py:98-123, 158-181, 289-325 | ~70 |
| trail shift beside a creek | map_drainages.js:12-17; map3d.html:196-204 | ~6 |
| layer names | 06:539-551, 1238, 1254, 1319, 1339, 1360, 1378, 1386-1397, 1412, 1431, 1447, 1459 and maplakes:261, 281, against map3d.html:229-235, 251, 259, 269, 309, 356-358, 381, 393, 398, 403, 409, 415, 430-436 | strings |

About 240 lines. The copies have already drifted: the side-channel profile link (H4); the depth-contour rule (H2); the
fires layer named with its source in 2D (`LBL["fires"]`) and "Fire perimeters since 2016" in 3D (map3d.html:229); road
classes "on by default" `true` in 2D (map_drainages.js:332-337, never read there) and `false` in 3D; three bike palettes.

Inside 06_map.py [C]:
- every point layer is built twice, once as folium markers and once as a list for 3D: drops 1283 and 1286-1288, falls
  1322 and 1325, gauges 1419 and 1421-1423, trout 1438 and 1441-1442, start points 1462-1465 and 1467-1471 (the same
  f-string twice), closures 1338 and 1347, fires 1378 and 1383. The drop radius formula is typed again at map3d.html:391.
- "follow up through the lake reaches to the first creek": 197-202, 239-245, 800-807.
- the "in:" flag: 186, 704, 770-771, 925-926. The 1.5 ratio: 230, 797.

Between the lake files [C]:
- 05d:364-366 `_locate` and 05d:918-920 `locate`, identical; `import lakedata` at 363 and 915; `import lakesources` at
  241 and 943.
- 05d:520-523 and 697-703 the regulated test; 05d:377-379 and 743-754 `in_area`, `shore_km`, `islands` (the first pass
  is overwritten); 05d:880-885 and 887-891 the same loop for a print and for the column.
- three ways to compare lake names: 05d:142-152 `norm` / `key`; 05d:280-288 `wkey` / `wkeys`; maplakes.py:99-102
  `key` / `words`.
- species tables: lakedata.py:23-32 `SALMONIDS`, 05d:895-897 `KEYWORD`, 05d:276 `TROUT_SP`, 05d:878 `GAME` (unused).
- survey months: 05d:488-492 `flown` and maplakes.py:28-31 `_flown`.
- the User-Agent: 05d:58, lakelidar.py:31, lakesources.py:28, and typed out at lake_bathymetry.py:76, 140, 255, 318, 356.
- lake_bathymetry.py: download-then-rename four times (140-145, 255-259, 318-322, 356-360); the contour loop four
  times (111-117, 181-189, 283-290, 409-416); the smoothing at 178-180 and 278-280. About 40 lines.
- unit constants beside units.py: maplakes.py:20 `FT = 3.28084` (unused), 277 `/ 0.3048`, 288 `* 2.47105`; 05d:161,
  603; lake_bathymetry.py:33; lakedata.py:47; fish_score_diagram.py:91.

Elsewhere [C]: 12_profiles.py:97-113 repeats 05_score's rule for which cells are a reach's own (it says "as in
05_score.py"); 12:35-36 and 06:517 the list of drop kinds shown; fish_score_diagram.py types every weight and cut-off of
scoring.py again by hand.

---

## F. Dead code (each checked by grep across scripts/)

06_map.py [C]:
- 9 `from pyproj import Transformer`; 11 `MousePosition`: imported, never used.
- 1253 `hidden = {"steep reach", "likely DEM artifact", "dam / weir"}`: never read.
- 144-148, 158-176, 212-221: the edge branches of `draw_through` (A6b).
- 740 `cut_ |= s_ll.in_lake_drawn.values`: no effect (A11).
- 948 `nz = lambda v, nd=0`: `nd` never passed.
- 49 `trails = ...read("trails.gpkg")` and 1086-1088: only for an area with no shared trails file; 05_score.py:396
  still writes that file for every box. 61 and 1349-1354 `gated`: same. 503-507, 1303-1305: columns "older" files may
  lack. All 12 areas have been rebuilt since.

maplakes.py [C]: 15 `REGIONS`, `HOME` imported, unused; 20 `FT = 3.28084` unused; 159-160 `_size` only calls `acres`;
277-278 fall-backs for a depth file without `depth_ft` or `major`.

05d_lakes.py [C]: 35 `out_dir` imported, unused; 47 `PLANNED = {}` and its branch at 48; 878 `GAME` never used;
624-625 a print that tests `w_.startswith("no level")`, which no note starts with; 657-662 a look-up for "caches made
before 2026-11-20".

lakedata.py [C]: 36 `NLA` never read (05d uses `lakesources.NLA`); every record's `ref` and `method` are never read
(05d sets them for EPA records too, 05d:956-957, and reads neither).

labelpaths.py [C]: 20 `MPP = {11: 65, ...}` never used.

map_drainages.js [C]: 273 `window.trailTip =` set, read nowhere; 330-338 the sixth entry of each road class (`on`) is
taken apart at 352 and not used. Comments at 139 and map3d.html:303 say the fire closure areas are "on by default";
06:1360 has `show=False` and map3d.html:310 `false`.

14_portable.py [C]: 51-52 `long_trail` and `credits` are packed into the page and never read by its script.

map_style.css [C]: every class is used (counted).

Files:
- **fish_score_diagram.py [C]**: run for every area by run_late.sh:27. It reads no area setting, so the 12 outputs are
  the same file (all 457,836 bytes). publish_site.sh:65-68 and phone_sync.sh do not copy it and no page links to it. Its
  header says "multiplied by four factors"; `scoring.score` has five (channel, scoring.py:322-323), and its water panel
  is LA's model only.
- **15_preview.py [C]**: not dead. Run by hand; its `preview.jpg` is published (publish_site.sh:61) and linked from
  13_overview.py:38.
- **profiles.html**: the viewer's source lives in `output/la/` and is copied to an area only if absent
  (run_late.sh:25). 12 copies are in git, identical today (one checksum).

---

## G. Website size, from the code's side

Published sizes (commit 6875118): 2D pages 199 MB, 3D pages 112 MB, map3d_data.js 230 MB, profiles_data.js 69 MB,
hillshades 40 MB; `streams/` is 628 MiB.

**G1 [C] Every layer outside `SHARED_3D` is written twice.** 06:1221-1223 moves 12 layers into map3d_data.js. All others
go inline into stream_map.html through folium and again into stream_map_3d.html (06:1531-1538). The 3D copies add up to
111 MB: lakes 29.4, state trout waters 24.4, restricted access 17.1, drops 13.7, lake depth 9.0, non-Forest-Service land
5.7, start points 5.6. The 2D pages hold the same data in folium's longer form: LA's 2D page is 21.2 MB for what is
10.4 MB in the 3D page. Loading these layers from one shared file and drawing them in map_drainages.js would take the 2D
pages from 199 MB to their shells. [P] for the saving, [C] for the sizes.

**G2 [C] Sentences where numbers would do.** The two stream layers are 131 MB: geometry 37 MB, `dq` 24.1, `sun` 23.8,
`acc` 13.8, `tr` 5.5, `fl` 3.1, `d` + `k` 5.2, `x` + `y` 3.2, `c` 1.7. The three sentences are 61.7 MB (47%).
- `acc` (06:477-492), mean 108 characters in LA: six numbers, a road name and "from 90404 Santa Monica" on every reach.
- `sun` (06:964-974), mean 205 characters: six numbers and one string that is the same for the whole area (`WT_HOW`).
- `dq` (06:620-661), mean 172 characters; only 3,582 different ones among LA's 17,804.
- `d`, `k`, `c`: the names and colour are already in `drains` (06:1016-1023). `x`, `y`: the page can take the midpoint.
- `to_json(na="null")` (06:1232-1233) writes every key for every feature; `ht`, `burn`, `tr`, `flags` are mostly "".

**G3 [C] Lake-touching reaches are written twice** (A16): 13,590 features, 13.0 MB; a quarter of the streams layer in
adk_northwest (2.47 of 9.39 MB).

**G4 [C] Coordinate precision by layer.**

| layer | simplify | decimals | where |
|---|---|---|---|
| streams | 0.00008° | 5 | 06:945 |
| forks, divides | 0.0002° | 5 | 06:1009-1012 |
| long trail | 0.00002° | 5 | 06:1047-1048 |
| trails, roads | 0.00004° | 5 | 06:1089, 1169, 1196 |
| parking | none | as stored | 06:1209-1213 |
| falls, gauges, drops | none | as stored | 06:1325, 1421, 1286 |
| closures, fires, context outlines | 0.0002-0.0003° | 6 | 06:1327-1331, 1377, 1400 |
| lakes | 2 m | 6 | maplakes.py:255 |
| lake depth contours | **none** | 6 | maplakes.py:279-280 |
| profiles | | 5; z to 0.1 m | 12:192-193 |

The contours are the outlier: ne_ct's are 8.07 MB in the 3D page and again in the 2D page, for 24 lakes.

**G5 [C] Smaller ones.** "Best remote trout water" repeats geometry inline (06:1237-1240). The start points are
5.6 MB of one tip string each (06:1467-1471). Every 2D page carries map_drainages.js and the stylesheet inline
(06:1227-1229; 49 KB each). The DEM colour relief, off by default and only in the 2D map, is 40 MB of PNG
(06:551-558).

**G6 [C] profiles_data.js** (12:187-203), by share of bytes in n_georgia: lon 18%, lat 16%, z 11%, area 10%, km 9%,
grad 7%, score 6%, burn 5%, habitat 5%, perennial 4%, trout 4%. `km` is a 40 m step (12:123) and `grad` is made from z
and km (12:136-137): both can be made in the page. The five per-reach strips change 9,437 times in 219,638 points.

---

## H. Bugs and accuracy risks

Shown on the published files or the logs:

**H1 [C] The dashed edge for a dry or marsh lake never draws.** maplakes.py:253
`lk["dry"] = lk.water_note.fillna("").str.startswith("no level water")`; the note 05d writes starts "little level
water in the lidar of" (05d:572). The mismatch is in every committed version since e8d5957. Published: `dry` is true for
0 of 7,450 lakes; 401 popups carry the note.

**H2 [C] Major depth contours are thin in the 3D and one-file maps.** The 2D map reads the `major` flag
(maplakes.py:282). map3d.html:258 tests `["==", ["%", ["get", "depth_m"], 10], 0]` and 14_portable.py:233
`f.properties.depth_m % 10`; `depth_m` is feet times 0.3048 to one decimal. Published: 261 contours flagged major, 0 pass
the test.

**H3 [C] "Outlet creek profile" opens the wrong thing for half the lakes.** maplakes.py:225
`quote(r.outlet_name.split(', ')[0])`; an unnamed outlet is stored as "unnamed, flows to X" (05d:808), so the link is
`profiles.html#q=unnamed`. Published: 3,601 of 7,450 lakes. The link also sends no position, so with two creeks of one
name the viewer takes the first (profiles.html:455-462).

**H4 [C] 3D map: a side channel's profile link finds nothing.** map3d.html:584 uses `p.n` as it is; the name ends
" (side channel)" (06:952) and the viewer matches names exactly (profiles.html:457). The 2D page strips it
(map_drainages.js:109). Not yet in the published build.

**H5 [C] New York state park trails are labelled "CA State Parks".** 06:1069-1075: `("State Park", "CA State Parks")`,
`("Los Angeles County", "LA County Parks")`, else `return s[:40]`, applied in every area. Published: 181 trail pieces in
the four Adirondack maps (28, 6, 1, 146). The 40-character cut shows "Pennsylvania Department of Conservation " on 2,148
pieces, "Connecticut Department of Energy and Env" on 898, "New York Department of Environmental Con" on 4,214.

**H6 [C] adk_southeast: every carried reach over 256 km2 is drawn as order 7.** 06:98-101: the medians are made
non-decreasing (`np.maximum.accumulate(logm)`), and where orders 6 and 7 have smaller medians than order 5 the steps
collapse. Log (late_adk_southeast.log:385): "5: 256, 6: 256, 7: 256". Published: 529 features of order 7, the smallest
draining 260 km2, and 11 of order 6.

**H7 [C] A lake's drainage in its popup is the one from before the map step renamed it** (A27). Published: lakes
labelled with the unnamed-drainage group that lie inside a named outline the map draws: jackson 29 of 34, ne_ct 26 of
107, adk_northwest 102 of 211, la 3 of 46.

**H8 [C] "Trout stocked or recorded here" on records that are not trout, or are old.** maplakes.py:152-153
`if getattr(r, "agency_trout", False) or rec:`, where `rec` is any GBIF Salmonidae record of any year (05d:862-873;
lakedata.py:31-32 lists whitefish and cisco). Published: of 547 such lakes, 5 list only whitefish or cisco (Massawepie
Lake, Brantingham Lake, Lake Hortonia, two unnamed Jackson lakes) and 49 list nothing newer than 2000.

**H9 [C] A depth survey's note is shown under another source.** lake_bathymetry.py:464-465, 472: when the older value
is deeper it stays, with its source, and the survey's note is put beside it with "is deeper" added. Published: "max 62
ft · EPA National Lakes Assessment 2007 (sonar), 2007-07-11 · deepest contour 60 ft: the bottom is a little deeper; 62
ft by EPA ... is deeper" (Beach Pond; also Quinebaug Pond). The same line 472 drops 05d's own notes for every surveyed
lake.

**H10 [C] Soundings at other spots are called conflicts.** 05d:974-980. Published: Lake Champlain "max 318 ft ...
conflicts: 17 ft by EPA ...; conflicts: 19 ft ...", Jackson Lake "max 469 ft ... conflicts: 97 ft by EPA". A dammed lake
NHD types as a lake is not treated as a reservoir here (`reservoir_index=lk.ftype.iat[i] == "reservoir"`, 05d:957).

**H11 [C] A state service that is down removes facts from the map without failing the step.** lakesources.py:89-95
prints and returns nothing. Log (mid_lexington_va.log:1793, tonight's 22:50 run): "lake source unavailable:
HUB_Layers/DWR_Public_Fishing_Lakes"; the two earlier runs wrote `'designation': 8`, this one none. The same pattern
decides which small lakes exist: lakesources.py:265-270 (PFBC's stocked lakes) and 239-244 (NCWRC) feed "a listed lake is
kept whatever its size" (05d:372).

**H12 [C] `stream_reaches_ranked.csv` lists pieces that are not reaches.** 06:268 names them `sid+N`, 06:510-513 writes
all of `s_ll`. 743 such rows in the current outputs (peek). README.md:138 calls the file "Every DEM stream link".

**H13 [C] `draw_through` redraws reaches that exist** (A6): 455 second lines and 239 one-point additions in the current
outputs (peek).

From the code, not shown on data:

**H14 [C] Profiles understate the drainage below every lake.** 12_profiles.py:82 reads `area_km2.tif`, which starts
again at each outlet pit, and 12:158 takes a running maximum; the water crossbox carries past dams is not added. The
map's popup uses `area_full_km2`. Measure: `profiles_data.js` `area_km2` against the largest `area_full_km2` of the
same-named reaches.

**H15 [C] Order of writing.** 06:1491 saves stream_map.html, 1520 overview.json, 1528 map3d_data.js, 1536 the 3D page,
none through a temporary file. A failure between 1491 and 1528 (the coverage simplification at 1506 is in between) leaves
a new 2D page reading the old data file.

**H16 [C] LA's latitude is typed into the drawing.** map_drainages.js:12 `129500 / Math.pow(2, z)` and map3d.html:203
`64750 / 2 ** z` ("at 34° N"); the label bands' metres per pixel (06:1050, 1177); profiles.html:459 `* 0.83`;
map_drainages.js:481 `w = 112`, the PCT's label width, used for every long trail. At 44° N the true scale is 13% smaller.

**H17 [C] "no 3 ft lidar covers it" is also written when the read failed.** 05d:445-452 returns `None` on any
exception and 05d:532-534 writes that note for `None`. Such a lake then has no `lidar_kind`, so
flowlib.py:204 leaves it out of the lakes a reach can lie in. No such failure is in tonight's logs. 107 published
popups carry the note.

**H18 [C] Dams from NHD are skipped silently.** 05d:516-517 `except Exception: pass`, with no message; `regulated`
then rests on OpenStreetMap dams alone.

**H19 [C] A cached lidar window is used forever.** lakelidar.py:98-102 returns the saved file whatever its age and
whatever `REFRESH` says, so "the newest survey" holds only for the first fetch. If the saved file's work unit is no
longer in the catalogue, `window` returns `None` for it and 05d:537 `u["workunit"]` raises [P].

**H20 [C] `lake_depth.gpkg` is never removed.** lake_bathymetry.py:453-457 writes it only when there are contours;
maplakes.py:271-272 draws whatever file is there.

**H21 [P] Champlain can get two sets of contours.** `ADAPTERS["central_vt"] = [vt_soundings, noaa_champlain]`
(lake_bathymetry.py:424): `rows += r_` keeps both sets, `facts.update(f_)` keeps the second's facts. Only if Vermont's
file has 200 soundings in the lake (lake_bathymetry.py:89).

**H22 [P] A public boat launch on a river can be pinned to a pond beside it.** 05d:1016-1018 gives a point to the
nearest lake within 150 m; only the PFBC points are filtered for lakes (lakesources.py:143).

**H23 [C] 12_profiles.py:38** reads `context/gauges.gpkg` without testing that it exists; 06 treats the same file as
optional (06:472-475).

**H24 [C] Stream lines sit half a cell off the cells they stand for.** Reach vertices are cell corners
(05_score.py:61-62; 12_profiles.py:99-100), the map-step's own points are cell centres (06:137, 859). About 7 m; it is
what A6's test trips over.

Checked and found right: the heat sentence (06:681-686) claims "hotter than any creek in these ranges where trout have
been recorded"; 11_context.py:329-331 warns when that fails, and no log has the warning (hottest trout record 26.7 °C,
gate 29.0). "Forest Service page" and "Forest Service status" on parking: both fields come only from Forest Service
records. The trailhead ids are unique across boxes (08_hike.py:359). Crossbox links: no cell is listed twice in the four
areas looked at, so the missing de-duplication in `draw_through` does no harm today.

---

## Appendix: measurements that need no pipeline run

Per area; `<box>` is each range folder. Lakes-on layer = `streams` in `output/<area>/map3d_data.js` (or the site copy);
Lakes-off layer = `streams_lake`. Geometry in the area's UTM zone.

- **M1 order raise (A5, H6).** `<box>/stream_drainage.csv` [`sid`, `strahler`], clipped to 1-7, against
  `stream_reaches_ranked.csv` [`sid`, `strahler`, `area_full_km2`], rows without "+" in `sid`. Count where the second is
  larger; table of raised order by `area_full_km2`.
- **M2 draw_through (A6, H13).** `streams_drawn.gpkg` [`sid`, `geometry`] against the boxes' `streams_scored.gpkg`.
  (a) rows with "+" in `sid`: count, km, share of each within 8 m of any scored line; for the same rows in
  `stream_reaches_ranked.csv`, whether `name` and `fish_score` equal the host's (the `sid` before "+"). (b) same `sid`:
  drawn length minus scored length over 0.5 m, split at 15 m. (c) kind: `data/derived/<area>/_shared/inflows.json`
  `["cross"]`, rows `[from, x, y, into, row, col, km2, kind]`; match each added line's first point to a row's cell through
  that box's `flowdir.tif` transform; counts by kind and by `km2` under 1.
- **M3 drainage renaming (A7-A9).** `<box>/stream_drainage.csv` [`drainage`, `fork`] against
  `stream_reaches_ranked.csv` [`drainage`, `fork`] by `sid`; count by (old, new).
- **M4 lake classification and clip (A11, A12).** `<box>/flow_streams.csv` `below_dam` starting "in:" gives set L.
  Reaches in the Lakes-off layer that are not in L, by the size and `lidar_kind` of the lake they touch
  (`data/derived/<area>/_shared/lakes.gpkg` [`ha`, `lidar_kind`, `water_note`]): what 05_score's cut does not cover.
  Reaches in L under half inside the union of lakes.gpkg: flagged but still drawn.
- **M5 stubs, slivers, re-valued pieces (A13-A15, A18).** For each row of `streams_drawn.gpkg`, its parts outside the
  union of lakes.gpkg. Parts with no Lakes-on feature within 2 m were dropped: count and km, under and over 20 m. Parts
  present whose `n`, `fs` or `a` differ from that `sid`'s `name`, `fish_score`, `area_full_km2` in the ranked CSV were
  re-valued: count and km.
- **M6 joins across dams (A17).** Lakes-on features with two vertices that do not lie within 3 m of a
  `streams_drawn.gpkg` line: count and lengths; the same in the Lakes-off layer.
- **M7 lakes' drainage (H7).** `lakes.csv` [`lid`, `drainage`, `fork`, `lat`, `lon`] against the `forks` outline
  ([`drainage`, `fork`] in map3d_data.js) containing each lake's label point (`label_x`, `label_y` in lakes.gpkg).
- **M8 dry lakes (H1).** lakes.gpkg `water_note` starting "little level water" against `dry` in the page's lakes.
- **M9 fish class (H8).** lakes.gpkg `records` (JSON: `species`, `year`, `source`), `game_fish`, and
  `lake_records.gpkg`: lakes classed fish on records with no trout, char or salmon, or none since 2000.
- **M10 profiles (H14).** `profiles_data.js` `area_km2` per profile against the ranked CSV's largest
  `area_full_km2` for that `name` and `region`.

An older and a newer drawn layer can be compared by line length with the existing
`data/stream_burning/checks/drawn_cmp.py` (another session's; reads two site commits).
