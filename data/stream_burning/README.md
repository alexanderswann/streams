# Stream burning: NHD lines into the routing (lakes installed 2026-11-21, lake outlets 2026-11-22; the DEM burn parked)

**Status:**
- **Installed 2026-11-21: NHD's lines through lakes** (`harness/patch_lakes.py`, now in `scripts/03b_stitch.py`).
  - `route_lake`: every cell of a lake that holds water drains to its outlet, along NHD HR's lines through the lake
    where they run.
  - `outflow_streams`: the way the water takes below the outlet is a stream line down to the first stream it meets.
  - It went in with a tailwater floor in `scripts/scoring.py`: a `TAILWATERS` reach with no gauge record gets full
    water credit.
  - Asked for by the user ("implement and commit the nhd stream burning") after the routing let Pilgrim Creek, not
    the Snake, cross Jackson Lake to the dam. Measured on all 12 maps first: see *Lakes* below.
  - **It needs `05_score.py`'s size floor to count carried water** (added the same evening): without it the creek
    below a lake's outlet is no longer a reach. See *What the lake measurement missed*.
- **Installed 2026-11-22: a lake ends at NHD's outlet** (`lake_outlet` in `scripts/03b_stitch.py`, written to
  `lake_outlets.json` and read by `scripts/crossbox.py`). One step decides where a lake drains: the two faults
  found after the maps of 2026-11-21 went out, fixed at the root. See *Both faults fixed at the root*; the gap at a
  lake's outlet was left open on purpose, and that section says what closing it takes.
- **Parked: the burn into the DEM itself** (`burnlib.py`, `patch_burn.py`), measured on 2026-11-20 on two whole
  maps. The user decided then to leave it out and keep it to come back to. It doesn't fix the lake crossings: at a
  lake that drains over a dam, filling raises the burned trench back to the water's level.
- **Log entries** in `MULTI_AREA_LOG.md`:
  - "2026-11-20, afternoon: burning NHD stream lines into the routing DEM";
  - "2026-11-21: NHD's lines through lakes";
  - "2026-11-21, evening: creeks below lake outlets";
  - "2026-11-22: a lake ends at NHD's outlet; one step decides where a lake drains".

## Lakes (installed 2026-11-21)
Measured with `harness/measure_area.sh` (each area's scratch copy from 03b, the live 03 outputs linked) against the
live build, all 12 maps; `harness/remeasure_05b.sh` after the lakes layer (05d's `lakes.gpkg`, which 05b reads) was
copied into the copies; totals by `checks/summarize.py`:

| all 12 maps | live | lake routing |
|---|---|---|
| straight made-up lines across lakes (300+ m runs) | 986 km | 266 km |
| lake outlets reading under half of NHDPlus (`lake_outlets.py`, the reach carrying the most water) | 45 | 39 |
| HR lines D8 misses (`hragree.py`) | 1,811 | 1,784 |
| NHDPlus V2 line ends under half | 669 | 677 |
| mapped falls found (`data/validate.py`, both passes) | 486 of 829 | 487 |
| known falls found (any source, 200 m, `falls.py`) | 1,025 of 2,127 | 1,025 |
| sudden flow drops; reach ends dead on an edge between boxes | 0; 0 | 0; 0 |
| reaches | 105,478 | 104,999 |
| km of fish 60+ | 42,159 | 41,911 |
| reaches moving 10+ fish-score points | | 265 up, 408 down |

- **Fixed:**
  - Jackson Lake's crossing (the Snake's line now runs to the dam; nothing crosses beside it).
  - Palisades (45 of 47 in-lake reaches named Snake River, against 6 of 46).
  - 120 creeks drawn carrying a lake's water lose it: Lower Slide Lake's 1,539 km² on a 2.7 km creek, Jenny, Leigh,
    Roseland and Bailey lakes' outlets, and others.
  - Lake Mathews' 111 km² reaches Temescal Wash (113 km² below it; NHDPlus 105).
- **The 10+ point moves** (by cause, `checks/drops.py`): of the 408 down, 276 are reaches that now read "reservoir"
  (their ends cross the 50%-in-lake line: the lines inside lakes follow NHD's, so the reaches split differently at
  the shores), 100 are the creeks above, which had carried a lake's water, 12 lost drainage another way, 12 changed
  flow class and 8 are other; of the 265 up, 213 left the "reservoir" class.
  - **Corrected 2026-11-21, evening:** the table's "reaches 105,478 → 104,999" and "km of fish 60+ 42,159 → 41,911"
    were first read as that lake-shore churn. Part of both was creek lines that vanished: see the next section.
  - LA's flow classes: about 20 Piru Creek reaches below Pyramid Dam would have gone from year-round to seasonal.
    Their natural-flow drainage had included Pyramid Lake's own shores through a path leaking out of the lake. The
    tailwater floor restores them, and 28 that the live build already showed mostly dry or seasonal.
  - Willow Creek (San Bernardinos, 6 reaches) drops a class for the same reason, without a release to keep it up.
  - One San Jacinto River reach changes its NHDPlus line match at a junction and loses its gauge record.
- **Checked by picture:** Jackson Lake, Palisades, Leigh / String / Jenny lakes, Lower Slide Lake, Roseland Lake, and
  the Indian River below its reservoir.

## What the lake measurement missed (2026-11-21, evening)
Found while breaking the 408 drops down by cause for the overview session (the user's rule: mark a stream down only
when near-certain). The checks above compare the reaches two builds share. `checks/drops.py` also lists the lines only
one build has, and the measured lake-routing builds lacked 197 creek reaches (286 km) of the builds before: not lake
reaches, 200+ m outside every lake outline.

- **Cause.** `05_score.py` kept a stream link when its own D8 drainage was 1 km² or more. A lake ends its paths at
  its outlet, so the creek below starts again near nothing: its links stayed under the floor until it had gathered
  1 km² again or met a creek that had. Where the old builds did draw that stretch, a path had leaked across the lake
  and left it beside the outlet. `route_lake` sends every lake cell to the outlet, so those stretches went:
  102 links, 103 km over the 12 maps (83 km of it fish 60+). North-west Adirondacks: 1.5 km of the Oswegatchie, the
  Raquette between Raquette Lake and Forked Lake, Salmon Lake Outlet, South Pond Outlet, Cage Lake Outlet. Jackson
  (published 19:49 with it): Emma Matilda Lake's outlet and three more, 3.4 km.
  - **Corrected 2026-11-21, late:** these went as reaches, not as lines. `06_map.py` draws a creek through from a dam
    to the next reach, so the Jackson map published at 19:49 still drew all four, with the next reach's values. See
    *On the drawn maps*.
- **The gap behind it** (`checks/outlet_gaps.py`, on the 12 lake-routing builds): stream links (`dem_streams.gpkg`)
  under 1 km² of their own that carry 1 km² or more with the water crossbox links to them, and that no reach covers.

  | map | links | km | along an NHD stream line | drawn before the lake routing |
  |---|---|---|---|---|
  | adk_northwest | 336 | 255.0 | 247.7 km | 35.3 km |
  | adk_southeast | 282 | 204.4 | 194.2 km | 17.1 km |
  | adk_southwest | 223 | 170.1 | 163.7 km | 12.2 km |
  | adk_high_peaks | 199 | 129.7 | 125.8 km | 6.8 km |
  | ne_ct | 139 | 95.5 | 91.5 km | 5.7 km |
  | n_georgia | 100 | 67.2 | 55.9 km | 7.1 km |
  | central_vt | 65 | 46.3 | 45.0 km | 4.7 km |
  | la | 62 | 43.4 | 38.5 km | 8.7 km |
  | jackson | 48 | 32.8 | 28.6 km | 3.4 km |
  | se_pa | 27 | 16.7 | 15.4 km | 2.2 km |
  | lexington_va | 18 | 13.6 | 11.1 km | 0.0 km |
  | smokies | 21 | 12.8 | 12.0 km | 0.0 km |
  | all 12 | 1,520 | 1,087.5 | 1,029.4 km | 103.2 km |

  185 of the links carry 100 km² or more: rivers below dams, and rivers where they enter a map.
- **Fix** (`scripts/05_score.py`, `scripts/crossbox.py`, `scripts/run_mid.sh`): the floor counts the water that
  reaches the link from elsewhere (`crossbox.carried_km2`: every `inflows(through_dams=True)` entry's area added down
  its D8 path, as 05c does for `area_full_km2`), sampled where the link's own area is. `run_mid.sh` runs
  `02b_download_flow.py` before `05_score.py`, since crossbox needs the reservoir list and NHDPlus's lines.
- **Jackson rebuilt with it** (mid and late, 20:13-20:22): 54 links, 33 km kept on carried water; none left undrawn.
  Against the build before any of this: creek lines gone 8 → 3 (one drains 0.95 km² once the lake's cells no longer
  pad it, one is drawn 116 m away, one is 141 m at a lake's edge), 49 new creek reaches (40 km, 26 km of it fish 60+), km of
  fish 60+ 5,588 → 5,607, flow drops 0, mapped falls 12 of 21 as before. On the rendered map: Emma Matilda Lake's
  outlet creek, Taggart Creek from its lake, the Snake from Palisades Dam.
- **Lesson for the next routing change:** run `drops.py` against the build before. A reach count that falls
  (105,478 → 104,999 here) is lines lost, whatever the matched reaches say.

## Installed on all 12 maps (2026-11-21; live 22:18, site commit 6875118)
Both changes, the lake routing and the floor that counts carried water, built into every map and checked against the
builds before either (`results/installed_2026-11-21/`). Jackson by mid and late steps from 20:13; ne_ct,
lexington_va, se_pa and central_vt the same way from 20:24; smokies, n_georgia, la and the four Adirondack maps from
03b (`SKIP_03=1 run_rebuild_a.sh`), the last done 22:04.

**Every figure in this section is from the reach tables.** The map draws more than its reaches, so "new" and "gone"
here are reaches, not lines: the next section has what the maps draw.

| map | links kept on carried water | km | reaches, before → now | km of fish 60+ (reach tables) | 10+ points down (lake / lost a lake's water / other) | up |
|---|---|---|---|---|---|---|
| jackson | 54 | 33.0 | 10,528 → 10,553 | 5,588 → 5,607 | 27 (18 / 5 / 4) | 29 |
| ne_ct | 155 | 96.7 | 3,419 → 3,588 | 1,189 → 1,204 | 42 (16 / 17 / 9) | 14 |
| lexington_va | 18 | 13.6 | 4,287 → 4,302 | 1,397 → 1,402 | 1 (1 / 0 / 0) | 1 |
| se_pa | 26 | 14.9 | 4,623 → 4,638 | 1,392 → 1,402 | 1 (1 / 0 / 0) | 4 |
| central_vt | 63 | 45.5 | 8,298 → 8,358 | 3,489 → 3,507 | 14 (6 / 6 / 2) | 3 |
| smokies | 21 | 12.9 | 8,947 → 8,921 | 3,800 → 3,812 | 14 (7 / 2 / 5) | 13 |
| n_georgia | 104 | 67.5 | 14,912 → 14,945 | 5,379 → 5,399 | 29 (21 / 5 / 3) | 15 |
| la | 65 | 43.8 | 17,805 → 17,867 | 1,389 → 1,396 | 21 (4 / 0 / 17) | 36 |
| adk_southwest | 232 | 170.9 | 6,815 → 6,999 | 4,493 → 4,608 | 43 (31 / 9 / 3) | 31 |
| adk_northwest | 355 | 256.5 | 8,279 → 8,492 | 4,747 → 4,899 | 91 (63 / 18 / 10) | 51 |
| adk_high_peaks | 219 | 131.6 | 9,138 → 9,306 | 5,055 → 5,129 | 79 (53 / 20 / 6) | 33 |
| adk_southeast | 298 | 205.5 | 8,427 → 8,640 | 4,241 → 4,357 | 92 (63 / 19 / 10) | 60 |
| all 12 | 1,610 | 1,092 | 105,478 → 106,609 | 42,159 → 42,721 | 454 (284 / 101 / 69) | 290 |

- **Every build check passes on all 12:** no failed step; 03b's rasters and drops equal the measured lake-routing
  builds (`verify_install.py <root> hydro`); no reach ends dead on an edge between boxes; no sudden flow drops;
  mapped falls found as in the measured builds.
- **Stream links below outlets** (`outlet_gaps.py`): 1,622 links, 1,100 km (95% along NHD's stream lines, 199
  carrying 100+ km²); all drawn but 7 (3.0 km): three at sea level on the tidal Delaware (se_pa) and four west of
  Vermont's line in Lake Champlain's New York shore (central_vt), which other rules leave out.
- **Lake outlets reading under half of NHDPlus** (`lake_outlets.py`): 45 before, 39 with the lake routing alone,
  26 now. Lake Junaluska (0.96 of NHDPlus), Little Rock Reservoir (1.00) and The Vly (1.00), which the lake routing
  alone had made worse, are right.
- **Stream line drawn with a lake's values outside the lakes the map draws** (`drawn_lake_values.py`): 390 → 173 km.
  341 pieces (223 km) of creek are put right; 48 pieces (22.5 km) are newly marked down, 45 of them fish 40+ before:
  headwater reaches lying half or more in a lake. Theirs is 05b's 50%-in-lake rule, which the session "Fix the
  lake-routing side effects and open items" is changing.
- **Creek reaches only one build has** (not lake reaches, 200+ m outside every lake outline): 1,196 new (983 km,
  695 km of it fish 60+) against 121 gone (174 km). Most of the new ones were lines on the map already.
  - Of the gone, 20 (32 km, 14 km fish 60+) lie along an NHD stream line with no reach of the new build nearby
    (`why_gone.py`). One is the Lamoille's line inside Arrowhead Mountain Lake, now a lake reach, with the river
    drawn from the dam.
  - The other 19 are headwater creeks whose own drainage is 0.52-0.99 km² where they now end, with no water carried
    to them: under the floor. The build before drew each as part of a longer link that reached 1 km² further down;
    a new line (a lake's outlet line, NHD's line through a lake) now joins it and ends the link there, or lake
    cells that had padded it drain to the lake's outlet. Finkle Brook's upper 1.4 km (0.86 km²) is one.
- **The 10+ point moves down, 454** (`drops.py` against the builds before, `why_moved.py` for the terms):
  - 284 now read "reservoir": half or more of the reach lies in a lake. 185 of them were fish 60+. 37 have 200+ m
    outside every lake outline (24 km of creek in all).
  - 101 had carried a lake's water that belongs to another line. Where NHDPlus V2 has a line by the reach (40 of
    them), the new drainage is within 0.5-2x of V2's on 34; the old was on 6. 46 of the 101 still score 60+.
  - 69 other (18 lost drainage another way, 12 changed flow class, 39 neither). 48 of them are reaches cut
    differently: a newly drawn line joins the creek, the reach ends there, and each piece is scored on its own.
    - 11 pieces no longer touch the trout record the whole reach touched (a state trout-water line, a brook trout
      patch, a survey point) and lose the 1.2 factor: the Opalescent 100 → 88, Kunjamuk River 92 → 74, Stewart
      Brook 88 → 74, the Oswegatchie 83 → 70, West Branch Sacandaga 82 → 68, Doyle Brook 84 → 70.
    - 12 are short flat open pieces beside a lake (20-700 m) that lose gradient and shade credit.
    - The rest are upper pieces with less drainage than the whole reach had at its lower end.
  - LA, 17: Willow Creek below Lake Arrowhead (7 reaches) and the South Fork San Jacinto below Lake Hemet (2): LA's
    flows leave out water held behind a dam, and both lakes now end at theirs. 4 small creeks that left a lake's
    outline and read mostly dry like their neighbours. One Piru Creek reach just above its gauge above Lake Piru
    (73 → 25): its drainage crossed the size at which the gauge's record (flowing 31% of summers) applies, as it
    does on the 7 reaches below it. Three more are small pieces, two of them inside lakes.
  - Smokies, 4 (Mingo Creek): the way in is 31 minutes shorter (no ride), which lowers remoteness. Not routing.
  - 244 reaches in all went from 60+ to under 60 (lake 185, lost a lake's water 44, other 15); 154 went the other way.
- **Checked on the rendered maps:** adk_northwest (Salmon Lake Outlet 100, South Pond Outlet 89, Cage Lake Outlet
  91, the Raquette from Raquette Lake to Forked Lake at 114 sq mi), ne_ct (four pond outlets), la (Piru Creek),
  jackson (Emma Matilda Lake's outlet, Taggart Creek, the Snake below Palisades Dam).
- **Left open:**
  - Lower Piru Creek below Lake Piru (19 reaches) now reads year-round, fish 64-73, where it read mostly dry: the
    tailwater floor reaches it because `scoring.tailwater()` takes Piru Creek by name below 700 m and doesn't stop at
    Lake Piru. The rating is right (USGS 11109800 below Santa Felicia Dam: 7 cfs or more on every July-September
    day on record since 2011), but the popup credits Pyramid Lake's releases. A `TAILWATERS` entry for Lake Piru would name the right dam.
  - 31 short reaches in adk_northwest (4.9 km) carry a river's stream order with a creek's drainage; 29 did before.
  - The first 0.4 mi of the Snake below Palisades Dam has no name on it.

## On the drawn maps, and two faults found after publishing (2026-11-21, late)
The overview session measured what the published maps draw (the Lakes-on layer of `map3d_data.js`, site 855954f
against 6875118) and found my figures above didn't describe it, and one lake's water put back in 530 m from its
outlet. Measured again here (`checks/drawn_cmp.py`, `checks/putin.py`; `results/installed_2026-11-21/`).

### The reach tables are not the map
`06_map.py` (`draw_through`) has drawn a creek through below every dam, pond and map edge since before this work: from
the cell where crossbox puts the water in, down the D8 path to the next reach, with that reach's values.
- Of the 1,622 stream links below outlets (1,100 km), the maps published before already drew 927 km (a line within
  40 m of the link's middle); 61 km were drawn only with Lakes off; 111 km were not drawn.
- So the floor change gave those stretches a reach of their own (their own drainage, flow, score and popup), not a
  line.
- The "creeks that vanished" from the measured lake-routing builds had vanished from the tables. On the Jackson map
  published at 19:49 all four were drawn, with the next reach's values: Emma Matilda Lake's outlet creek read fish
  58 there, where it had read 65 and reads 66 now. I told the user they were missing from the map without looking
  at that map.

| drawn by default, miles | line before → now | fish 60+ before → now | new line | gone line |
|---|---|---|---|---|
| jackson | 5,307 → 5,314 | 3,330.5 → 3,330.3 | 10.7 | 5.0 |
| ne_ct | 1,529 → 1,532 | 712.3 → 701.5 | 11.1 | 9.6 |
| lexington_va | 2,035 → 2,037 | 834.1 → 831.7 | 1.4 | 0.6 |
| se_pa | 2,181 → 2,182 | 827.6 → 830.2 | 2.1 | 1.6 |
| central_vt | 3,956 → 3,956 | 2,079.7 → 2,078.5 | 3.1 | 4.9 |
| smokies | 4,044 → 4,044 | 2,256.9 → 2,256.2 | 1.7 | 2.3 |
| n_georgia | 6,998 → 7,004 | 3,206.2 → 3,207.1 | 13.9 | 9.7 |
| la | 9,440 → 9,440 | 829.8 → 832.8 | 9.8 | 10.0 |
| adk_southwest | 3,374 → 3,371 | 2,654.7 → 2,675.7 | 15.5 | 20.6 |
| adk_northwest | 3,685 → 3,680 | 2,798.4 → 2,836.4 | 23.5 | 31.3 |
| adk_high_peaks | 4,134 → 4,129 | 2,970.0 → 2,973.9 | 12.8 | 20.2 |
| adk_southeast | 3,753 → 3,750 | 2,523.9 → 2,540.4 | 26.0 | 32.9 |
| all 12 | 50,436 → 50,438 | 25,024 → 25,095 | 131.5 | 148.6 |

- "New" and "gone" line: nothing of the other version drawn within 40 m. 54 mi of the new line and 66 mi of the gone
  line score 60+.
- Fish 60+ on the drawn map is up 71 mi over the 12 maps and down on five of them (ne_ct 10.8 mi, lexington_va 2.4,
  central_vt 1.2, smokies 0.7, jackson 0.2). "Up on every map" was true of the reach tables only. In ne_ct the pond
  outlets had been drawn with the score of the brook below and now score lower on their own flat ground.
- On line both versions draw, the score fell 10+ points on 154 mi and rose 10+ on 240 mi; 93 mi went from 60+ to
  under 60 and 165 mi the other way.
- The overview session sorted the gone line (stretches of 0.2+ mi that weren't lake pieces, 87 mi): 15 mi in 33
  lines lie along an NHD stream line and drained 0.8+ sq mi, 15 mi in 24 lines along one and drained less (the
  headwater creeks under the floor), 57 mi in 119 lines along no NHD line. Derived again here from the two site
  commits alone (`checks/gone_split.py`), with the same result. The first group holds lake outlet channels, which
  is the next fault.

### Fault 1: a lake's water put back in away from its own outlet
Seventh Lake (adk_southwest, with Sixth Lake): the outlet channel to Fifth Lake, 16.9 sq mi and fish 87 on the maps
before, isn't drawn; the lake's 43.5 km² goes in 555 m away in the woods and runs 570 m to Fifth Lake's shore where
NHD has no line.
- **Why.** Two steps each decide where a lake's water goes on, and nothing ties them together.
  - `03b_stitch.py` ends the lake at one outlet cell, a pit, and makes the D8 path below it a stream line
    (`outflow_streams`): the routed way out.
  - `crossbox.py` (`_dam_links`) walks NHDPlus V2's 1:100,000 outlet line from the lake's edge, 50 m at a time, to
    the first cell whose D8 path doesn't lead back into the lake's dead ends, and puts the water in there.
  - Before `route_lake`, paths leaked out of a lake beside its outlet, so a cell at the shore whose path ran into the
    lake and out through the leak counted as leading on: the water went in at the shore and ran out down the real
    channel. With every lake cell sent to the pit, such a cell leads back, and the walk goes on along V2's coarse
    line until it finds a cell on some other slope.
  - The outlet channel then carries none of the lake's water. Its links are under 05_score's floor and not drawn.
- **How many** (`checks/putin.py` on the published hydrology, 1,430 lakes with a link, `putin_12_maps.csv`):

  | how much of the way out misses the lake's water | pit at NHD's outlet | pit 100+ m from it | no NHD outlet line | all |
  |---|---|---|---|---|
  | none: the put-in is on it | 233 | 4 | 0 | 237 |
  | under 100 m | 856 | 10 | 4 | 870 |
  | 100-199 m | 96 | 33 | 2 | 131 |
  | 200+ m | 52 | 82 | 3 | 137 |
  | all of it: the put-in's path never joins | 19 | 34 | 2 | 55 |
  | all | 1,256 | 163 | 11 | 1,430 |

  - "Pit at NHD's outlet": within 100 m of where a detailed NHD (HR) stream line leaves the lake.
  - The firm cases, like Seventh Lake: pit at NHD's outlet, put-in 200+ m from it, 200+ m of channel missed.
    31 lakes carrying 1,041 km²: adk_southwest 10, adk_northwest 6, ne_ct 5, adk_southeast 3, adk_high_peaks 2,
    la 2, se_pa 2, central_vt 1. Soft Maple Reservoir (597 km², 520 m of channel), Lake Mathews (112 km²), Merino
    Pond (76 km², 1.8 km), Marsh Creek Reservoir (52 km², 910 m), Seventh Lake, Sand Lake (35 km²), Spy Lake.
  - The 870 "under 100 m" are the short stubs at outlets that still read as lake or small.
  - Below Palisades Dam the put-in's own path runs 790 m beside the way out before joining it, which is likely the
    first 0.4 mi of the Snake there with no name on it.
  - A put-in under 100 m from its pit that "never joins" is usually the check reading another stream link that
    starts by the pit (Chilhowee Lake): look before counting those.
- **What would fix it.** Where the pit sits at NHD's outlet (1,256 of 1,430 lakes), the routed way out is the lake's
  real outlet channel: put the water in at its top, whatever V2's line does.
  - The side-effects session's crossbox (d06b50b, `_at_outflow`) moves a put-in to the top of the way out where
    V2's cell lies within 100 m of the way out and its path joins it. On the published hydrology that is 1,269 of
    the 1,430: every stub, and 50 of the 192. It leaves 29 of the 31 firm cases: Seventh Lake's put-in is 458 m from
    its way out.
  - The lakes neither test moves (pit 100+ m from NHD's outlet) are fault 2's, and V2's cell is right for them.

### Fault 2: the outlet 03b picks is not always the lake's outlet
03b's lake rule ends a lake's paths at "the cell inside with the most water". Where the flat water's routing doesn't
carry the main inflow across the lake, that cell is where the biggest inflow enters.
- 77 lakes (20,200 ha) have their pit 300+ m from NHD's outlet, 20 of them 1 km or more: Raquette Lake 9.1 km (at
  South Inlet's mouth), Upper Saranac Lake 6.8 km, Arrowhead Mountain Lake 5.3 km, Rainbow Lake 2.2 km.
- The rule is older than this work, but then only the path that gathered the most water ended at that cell.
  `route_lake` now sends the whole lake there: every line inside such a lake (Lakes off) runs to the wrong end.
- Below the lake little shows: in 53 of the 77, crossbox's put-in lies within 100 m of NHD's outlet, so the river
  goes on from the right place (the Raquette below Raquette Lake reads 114 sq mi).
- **What would fix both faults at the root:** in 03b take the lake cell nearest NHD's outlet point as the outlet
  wherever a detailed NHD line leaves the lake (1,419 of 1,430 lakes have one), keep "most water" for the rest, and
  have crossbox put the water in at the top of that pit's way out. Then one step decides where a lake drains.

### Lesson
- Measure a change on what the map draws (`drawn_cmp.py` on two versions of `map3d_data.js`) before saying what the
  map gained or lost. `drops.py` and `outlet_gaps.py` compare reaches, and 06_map draws lines that aren't reaches.
- Look at the published map before saying something is missing from it.
- After a routing change, run `putin.py`: a put-in away from the way out is a channel without its lake's water.

## Both faults fixed at the root: a lake ends at NHD's outlet (2026-11-22, commit f337bfb)
One step now decides where a lake drains. `03b_stitch.py` (`lake_outlet`) takes the outlet from NHD's detailed
network and writes it to `data/derived/<area>/_shared/lake_outlets.json`; `crossbox.py` puts the lake's water back
in at the first cell of the way out `03b` laid there. The user's "Yes, fix it" of 2026-11-21 23:30; measured on
scratch builds of all 12 maps before it went in (`results/root_fix_2026-11-22/`), reviewed twice by the overview
session against the published copy, then installed and rebuilt.

### The rule, in the order it asks
1. **NHD's detailed outflow line.** A stream line (types 460, 558, 334) that starts in the lake and ends outside it;
   the outlet is where it leaves the water. It counts only where the terrain takes the water on within 300 m down
   it (`WAY_MAX`): a cell outside the lake whose own D8 path doesn't lead back into the lake and stays on NHD's line
   (80 % of the next 200 m within 40 m, `follows`). The cells before that cell (a dam's crest, a sill the DEM kept)
   are pointed along NHD's line. A way out that reaches another lake that holds water ends at its first cell.
2. **Several such lines: NHD's name.** The named line is the river's own bed (the Beaver River below Soft Maple
   Reservoir, beside the unnamed power canal where the terrain spills the lake).
3. **Else NHDPlus as a witness.** The line NHDPlus V2's 1:100,000 flowline leaves the lake by (within 300 m of
   where it leaves the outline). NHDPlus only chooses among NHD's detailed lines; its coarse geometry is never
   where the water goes in.
4. **Else the line nearest the cell where the terrain gathers the lake's water.**
5. **A pipe or ditch** (types 336, 428) counts only where the terrain takes the water on down no stream line, and
   only where a stream line goes on from it within 1 km (`BUILT_MAX`): the network runs through Palisades Dam and
   Stark Falls Dam as a pipe.
6. **The lake stays at the terrain's cell** (and `crossbox.py`'s older search carries its water) where NHD has no
   outflow line; where the terrain refuses every line; where it takes the water on only down another line than the
   one NHD names or NHDPlus leaves by; where the line runs off the map; where NHDPlus leaves the lake within 100 m
   of the terrain's cell (`V_AT`) while every outflow line the terrain takes on is 300 m or more from it; and where
   NHD's outlet lies on an edge between two boxes.

No per-area constant and no named place is in the rule. All lakes are first ended at the terrain's cell and judged
on that one surface, then moved: judged one by one, a lake whose outflow line runs through the next pond of a chain
was held back by that pond's flat water.

**How many lakes each step decides** (`checks/rule_tally.py`: the rule replayed on the published surfaces and
matched to the build's `lake_outlets.json`; 12 maps):

| step | lakes | of them moved 100 m+ / 300 m+ |
|---|---|---|
| one outflow line the terrain takes on | 1,355 (5 through a pipe or ditch) | 155 / 70 |
| several lines, NHD's name decides | 33 | 11 / 3 |
| several lines, NHDPlus decides | 17 | 6 / 4 |
| several lines, the nearest | 11 | 2 / 2 |
| ended at NHD's outlet, all | 1,417 (one more the replay doesn't match) | |
| left at the terrain's cell though NHD has an outflow line | 12 (below) | |

Where NHD names one line and NHDPlus leaves by another, the name wins. That happens at 3 of the 33
(`checks/name_vs_v.py`): Castaic Lake (the named line passes the Parshall flume gauge, which now reads 1.05 of its
drainage), Beaver Pond on the Cedar River, and Rock Lake (Sand Lake Outlet). At the other 30 NHDPlus leaves by the
named line too.

**NHDPlus's lines must be there.** `03b` reads `nhdplus_v2.gpkg` for step 3, so `run_base.sh` runs
`02b_download_flow.py` before it and `run_rebuild_a.sh` fetches the file when it is missing (02b reads nothing that
03 or 03b writes). Where the file is missing `03b` stops before it writes anything. `NO_NHDPLUS=1` lets it go on
with steps 2 and 4 alone, and its last line then says so: without that stop a failed download would have moved 9
lakes' outlets with only a note in a log.

### How the rule was found
Five versions were built in scratch; each fault below was a regression against the published maps, found by reading
the reaches that scored 10+ lower against NHDPlus's drainage there (`checks/down_review.py`,
`checks/lost_water_lakes.py`) and the audit's drainage tables point by point. Totals hid every one of them.
- **A pipe taken as the outlet.** With "a pipe or ditch where no stream line leaves", Bouquet Reservoir drained
  into the Los Angeles Aqueduct's pipeline and Bouquet Creek (7.7 mi, fish 64-68) went mostly dry. Hence step 5's
  second condition.
- **The named line refused.** At Tetreault Pond the terrain takes the water on only down an unnamed line; taking it
  dried Snake Meadow Brook (1.1 mi). Hence the third case of step 6.
- **A second dead end left behind** where a lake's cells don't all reach NHD's outlet (Chub Pond): the old cell's
  direction is restored before the lake is routed again.
- **The nearest line was the wrong one.** Lake Mathews has three unnamed ways out and the terrain spills it north
  over a dike; its 43 sq mi left Cajalco Creek and both Temescal Creek gauges fell (near Corona 1.005 to 0.742).
  Lens Lake and Livingston Lake sit on a divide: NHD names their outflows to Roaring Branch and Sand Creek, NHDPlus
  and the terrain's spill send both to Paul Creek, whose upper 2.3 mi lost them. The overview session's bar ("no
  gauge and no NHDPlus point on a named river worse without a stated reason") sent that version back; step 3 and
  the fifth case of step 6 came from it. Three witnesses were laid side by side for every lake first (the terrain's
  cell, NHD's detailed outflow lines, where NHDPlus leaves the outline): of 60 lakes that move 300 m or more and
  have an NHDPlus line, NHDPlus leaves within 80 m of NHD's outlet at about 50.
- **A lake's water lost at a box edge.** A put-in whose path left its box across a rim basin too small to have an
  exit link carried its water nowhere (Grass Pond; 2 lakes on the published NW Adirondack map already). `crossbox.py`
  gives such a path an exit.
A change to the rule is tested in minutes before any map is built: `checks/cmp_rules.py` replays two versions of
`lake_outlet` on one build's surfaces and lists the lakes whose decision differs.

### Results on the 12 maps
Measured on scratch builds first (`results/root_fix_2026-11-22/*_scratch.*`), then on the rebuilt maps: all 12
from `03b` (`SKIP_03=1`), 2026-11-22 06:27 to 07:28, from commit f337bfb with no edit in between, no failed step.
- **The rebuilt maps equal the scratch builds** (`checks/verify_install.py`, `drawn_cmp.py`): every box's
  `flowdir`, `area_km2` and `strahler` rasters, the drops, the reaches (ids and geometry), the drainage tables and
  the flow classes; `lake_outlets.json`, the link cache, and every drawn line. Fish scores differ on three
  Adirondack maps, by the lake term of 52c2139 that the scratch builds didn't have (60+: high_peaks +15.5 mi,
  northwest +22.2, southwest +23.8), and on one 1,200 ft piece in LA that takes its values from another neighbour
  (34.1393, -118.4594; not traced).
- Against the published copy (site 4315299), on what the maps draw (`checks/drawn_cmp.py`; "new" and "gone" line:
  nothing of the other version drawn within 40 m):

| drawn by default, miles | line before → now | fish 60+ before → now | new line | gone line | 10+ lower | 10+ higher | NHD lake outlets newly drawn / flagged |
|---|---|---|---|---|---|---|---|
| adk_high_peaks | 4,126 → 4,126 | 2,975.3 → 2,975.7 | 4.0 | 4.5 | 1.7 | 3.0 | 9 / 0 |
| adk_northwest | 3,674 → 3,672 | 2,839.0 → 2,839.0 | 6.5 | 8.6 | 2.6 | 5.0 | 10 / 4 |
| adk_southeast | 3,736 → 3,734 | 2,526.4 → 2,527.0 | 3.9 | 6.0 | 1.3 | 0.1 | 5 / 1 |
| adk_southwest | 3,369 → 3,371 | 2,681.3 → 2,683.1 | 7.3 | 5.0 | 3.4 | 0.5 | 7 / 1 |
| central_vt | 3,955 → 3,954 | 2,081.4 → 2,080.6 | 0.2 | 1.1 | 0.0 | 0.1 | 0 / 1 |
| jackson | 5,313 → 5,313 | 3,332.2 → 3,331.8 | 1.8 | 1.4 | 0.4 | 0.0 | 4 / 0 |
| la | 9,440 → 9,439 | 850.2 → 849.7 | 3.6 | 4.2 | 0.2 | 1.0 | 5 / 1 |
| lexington_va | 2,036 → 2,036 | 832.6 → 832.9 | 0.3 | 0.9 | 0.0 | 0.0 | 1 / 0 |
| n_georgia | 7,001 → 6,997 | 3,208.3 → 3,205.3 | 2.9 | 6.8 | 1.8 | 0.0 | 9 / 0 |
| ne_ct | 1,527 → 1,524 | 701.0 → 697.9 | 3.8 | 6.7 | 3.3 | 2.5 | 10 / 4 |
| se_pa | 2,181 → 2,180 | 831.0 → 829.8 | 0.5 | 1.4 | 0.4 | 0.0 | 1 / 4 |
| smokies | 4,040 → 4,040 | 2,256.5 → 2,256.4 | 0.0 | 0.3 | 0.0 | 0.2 | 0 / 0 |
| all 12 | 50,399 → 50,387 | 25,115.2 → 25,109.3 | 34.9 | 46.8 | 15.2 | 12.3 | 61 / 16 |

- Lakes (`03b`'s log): 2,072 of 8+ ha in the boxes, 1,500 hold water and end their paths; 1,417 of those at NHD's
  outlet, 79 of them 300 m or more from the cell with the most water; 12 left though NHD has an outflow line; 71
  have no NHD outflow line.
- Put-ins (`checks/putin.py`, 1,431 lakes with a link, `putin_12_maps.csv`): 1,414 on the way out. Of the other 17,
  8 are at the top of the way out where the check cannot follow (4 run straight into the next lake), 7 are lakes
  left where they were, 2 have no NHD outflow line (Baldwin Lake, Castac Lake). The firm cases of fault 1: 31 → 1
  (Tetreault Pond, kept on purpose). Lakes ending 300 m or more from NHD's outlet: 77 → 8, all lakes left on purpose.
- Standing checks: dead ends on box edges 0, sudden flow drops 0; the same 17 lakes with more than one dead end, all
  cut by a box edge; lake outlets under half of NHDPlus 27 → 27; creek drawn with lake values 3.7 → 2.9 mi.
- Known falls (the audit's `falls_recall.csv`, 2,128 falls): a drop within 100 m of 958 → 961, nearest drop an
  artifact 8 → 7. Six changed: Clarks Falls, Effley Falls, Meacham Falls and Mansfield Hollow gained a drop; at
  Penfield Pond a 3.4 m drop on the dam itself went (hidden on the map as a dam), and near Virgin Falls a 10 m drop
  that sat on Huntley Pond's misplaced put-in path.
- USGS gauges (the audit's `area_vs_gauges.csv`, 516; compared by the overview session's script): 5 moved by 0.02
  or more. Salt River at the Wyoming line 0.006 → 0.906, Castaic Lagoon's flume 0.004 → 1.050, the Beaver below
  Stillwater Dam 0.934 → 1.005, the Oswegatchie near Oswegatchie 0.944 → 1.010. One worse, Temescal Creek at Corona
  Lake 0.935 → 0.860: the gauge sits at Lee Lake's dam and the map now draws the first 110 m below it (129.0 km²),
  7 m from the gauge; the line below Indian Canyon Creek's mouth keeps its 140.2 km². Within 10 %: 417 → 419.
- NHDPlus points of 10+ km² (`area_vs_nhdplus.csv`, 13,949): 88 moved by 10 % or more, 53 better, 35 worse; within
  10 % 10,283 → 10,310; under half 836 → 829. Each of the 35 has its reason in `nhdplus_worse_with_reasons.csv`:
  19 where NHD's detailed outflow line and the terrain agree and NHDPlus leaves the lake another way, 14 where the
  river has its water and the point is read against another line (a point inside a lake, a junction moved a few
  hundred feet), 2 that were under a seventh of NHDPlus before.
- **Every drawn line whose drainage changed** by 1 km² and 30 % or more, whatever its score did
  (`checks/drainage_moves.py`, `drainage_moves.csv`): 91 pieces gained (27.4 mi; 18.6 mi of it towards NHDPlus's
  value, the Little River's 12.0 mi among them, +17 sq mi), 97 lost (24.1 mi). Of the lost, 15.7 mi lie below 19
  lakes whose water now leaves by NHD's outlet (next table; `checks/attribute_moves.py`). The rest are lines the
  published maps drew with the value of the reach below them (the creek between Bottle Pond's inflow and its
  outflow, Wolf Pond's outlet creek drawn as "Salmon River, 10.7 sq mi", Baltic Reservoir's side channel as the
  Shetucket), and junctions that moved a few hundred feet with the creek below reading what it read (Willys Lake
  on the Middle Branch Oswegatchie, Crooked Lake, Grass Pond, Lake Luzerne).

**Creeks that read less because a lake's water now leaves by NHD's outlet** (all of them; the published maps put
the water in 1 to 2 km from the outlet, on these):

| lake | map | the creek that lost it | what decided |
|---|---|---|---|
| Mill Creek Lake | adk_southwest | Mad Tom Brook, 3.5 mi, 3.3 km² | one NHD outflow line, named Mill Creek, at the terrain's cell; NHDPlus has the lake on Mad Tom Brook, where NHD draws an inflow |
| Butler Pond | adk_southeast | an unnamed creek, 2.3 mi, 2.8 km² | two unnamed NHD outflow lines and no NHDPlus line: the one at the terrain's cell (north); the published put-in was at the south one |
| Merino Pond | ne_ct | Potash Brook, 2.0 mi, 76 km² | one NHD outflow line, east to the French River, at the terrain's cell |
| Beaver Pond | adk_southwest | its unnamed north channel, 1.3 mi, 9.2 km² | NHD's name: the Cedar River leaves by the south-east outlet |
| King Lake | n_georgia | a side creek, 1.3 mi, 25 km² | one NHD outflow line; NHDPlus agrees with the new course |
| Mono Pond | ne_ct | an unnamed creek to Cabin Brook, 1.0 mi, 3.0 km² | one NHD outflow line, north to Giffords Brook |
| Boyd Pond | adk_northwest | a Grass River tributary, 0.9 mi, 2.4 km² | one NHD outflow line, at the east end and the terrain's cell; NHDPlus leaves by the north-west corner, where NHD draws inflows |
| Halls Pond | ne_ct | East Branch Stonehouse Brook, 0.9 mi, 3.0 km² | one NHD outflow line, named Slovik Brook |
| unnamed, 13.2 ha | adk_northwest | 0.65 mi of lake-class line, 44 km² | one NHD outflow line |
| Middle South Pond | adk_northwest | an unnamed creek, 0.5 mi, 1.1 km² | one NHD outflow line |
| West Thompson Lake, Spy Lake, Loughberry Lake, Gooseneck Pond, Grass Pond | | 0.2 to 0.3 mi each | one NHD outflow line |
| Antediluvian Pond, Goose Island Lake, Simon Pond, Wolf Pond | | under 0.1 mi each | one NHD outflow line (Simon Pond: NHD's name) |

Only the reaches that scored 10+ lower had been read one by one on the scratch builds; this table came from the
drainage comparison run on the rebuilt maps, and Boyd Pond, Butler Pond's creek and Middle South Pond were new on
it (their creeks score 4 to 11 lower).

### The 12 lakes left at the terrain's cell
| lake | map | why (`checks/kept_explain.py` follows NHD's line on the DEM) |
|---|---|---|
| Huckleberry Pond | adk_northwest | NHD's line climbs 67 m above the pond: an inflow drawn the wrong way |
| Ferris Lake | adk_southwest | ground 6 m above the lake for 975 m down the line |
| Eagle Pond | adk_high_peaks | ground 5 m above the pond for 380 m |
| Burntbridge Pond | adk_northwest | ground 2.4 m above the pond for 830 m (the old search still puts its water on that brook) |
| unnamed, 17.9 ha | adk_southwest | ground 2.3 m above it, never below within 1.5 km |
| unnamed, 8.1 ha | central_vt | ground 1.4 m above it, never below within 1.5 km |
| Long Pond | ne_ct | ground 1 m above it, never below within 1.5 km |
| Tetreault Pond | ne_ct | the terrain refuses the outlet NHD names (Snake Meadow Brook) and takes only an unnamed one |
| Lens Lake | adk_southeast | NHDPlus leaves at the terrain's cell, to Paul Creek; NHD's named outflow is 800 m away |
| Livingston Lake | adk_southeast | the same; NHD's named outflow is 2.4 km away |
| Stone Mountain Lake | n_georgia | NHD's line runs off the map at the lake |
| Badluck Lake | ne_ct | NHD's line runs off the map at the lake |

These keep the two old faults in small: their dead end is up to 2.4 km from NHD's outlet (Livingston Lake), and the
water of seven of them goes in 370 m to 2.5 km from the dead end, by `crossbox.py`'s walk down NHDPlus's line.

### Known, and left as it is
- **Second outlets are no longer drawn.** D8 sends a lake's water down one way out. 13 NHD outflow lines at 9
  lakes that the published maps drew are gone (`flagged_outlets.csv`): the power canal arm of Soft Maple Reservoir, Round Lake, Butler
  Pond, Perch Pond, Castaic Lake, Number Four Reservoir (2), Number Five Reservoir, Baltic Reservoir, Glen Morgan
  Lake, Marsh Creek Reservoir (3). The published maps drew most of them by accident: one arm was the path from
  where the water was put in. Proposed, not built: draw a lake's second NHD outlet as a side channel of the first.
- **Merino Pond and Mono Pond (ne_ct).** NHD's detailed line and the terrain agree, NHDPlus differs, and the creek
  NHDPlus names loses the water. Merino Pond's 29.5 sq mi leave by the east end through Larner Pond to the French
  River, not south as Potash Brook (its lower 2.0 mi read 0.5 to 1.3 sq mi; fish 71 to 33 and 70 to 53). The USGS
  gauge French River at Webster (86.0 sq mi) can only reach its drainage with this stream in: by the east outlet
  it joins about 800 ft from the gauge, by Potash Brook 0.8 mi below it. Mono Pond's 1.1 sq mi leave north to
  Giffords Brook, not south to Cabin Brook and Bartlett Brook.
- **Lens Lake and Livingston Lake** stay on Paul Creek, against the outflows NHD names.
- **Lake Mathews** drains by Cajalco Creek as NHDPlus and the Temescal gauges have it, 43.4 sq mi, mostly dry,
  fish 3. At the dam about 230 ft of line (two pieces near 33.8423, -117.4587) read year-round, 42.8 sq mi, fish
  56, above that mostly dry creek. Noted, not fixed.
- **The first stretch below two LA dams reads drier than the creek below it.** Bouquet Creek's first 0.31 mi below
  Bouquet Reservoir is new line and reads seasonal, fish 20, above a creek that reads year-round, fish 65 to 68;
  the San Gabriel's first 50 ft below Morris Dam reads seasonal, fish 15. The below-dam water rule of
  `05b_flow.py` doesn't reach these new first reaches. Noted, not fixed (the audit's `drawn_jumps.csv` lists both).
- **Seen on the way, not from this change and not fixed by it:**
  - Little Neshaminy Creek's main water passes beside Bradford Reservoir (se_pa), 720 ft north-east of it, not
    through it as NHDPlus has it; as before.
  - The French River's water from outside the Connecticut map (60 sq mi at the north edge) is not brought in (the
    audit has it: North Grosvenordale gauge 0.41). Merino Pond's water now reaches the river above Webster, so the
    river there reads 30 sq mi where the published map had 1.
  - The 400 ft of creek between Beaver Pond and Cedar Lakes (adk_southwest) reads 3.5 sq mi where the pond passes on
    1.1 (2.4 on the published map); it looks like a piece between two lakes taking the value at the end of its
    link. Not traced.

### The gap at a lake's outlet: why it stays, and what closing it takes
(the audit of 2026-11-22, cause A and batch 6)

`03b` ends a lake's water in a pit at its outlet cell; the way out starts in the next cell, and `crossbox.py` carries
the water across. After this change the two cells are known to `03b` for every lake at NHD's outlet
(`lake_outlets.json`), next to each other and in one box, so closing the gap is one assignment: point the outlet cell
at the first cell of its way out instead of making it a pit (for a lake left at the terrain's cell, back at the
direction `outflow` holds for it). It was left out of the outlet fix on purpose. With the gap closed, `area_km2`
(the D8 count of cells above) includes the water behind every dam, and five steps read that raster with a different
meaning of "the water behind a dam", each of which would change at once:
1. flow where the TNC model is used (LA): `05b_flow.py` reads `area_edge_km2`, the area without the water behind
   dams, on purpose (a dam holds it back), and `scoring.py` reads the dam-held share off the difference to
   `area_full_km2`;
2. drainages: `05c_drainages.py` ends a drainage at a dam and carries the area on for the names and forks by its own
   links (`inflows(through_dams=True)`, `pond_links`);
3. the drop detectors and the size floor: `04_knickpoints.py`, `04b_bigcreek_steps.py` and `05_score.py` add
   `crossbox.carried_km2` on top of `area_km2`; with the gap closed the lake's water would be counted twice;
4. flow: `05b_flow.py` walks a reach's path to the lake's dead end and jumps to the cell below it
   (`crossbox.dam_links`);
5. the map: `06_map.py` raises the stream order below a dam (Strahler starts again at 1 below a pit: the Snake below
   Jackson Lake Dam is order 7 by that estimate) and draws the joins across dams.
So closing it changes drainage areas, orders, the drainages' extents, LA's flows and the map's joins together: the
audit's batch 6, to be measured on scratch builds of all 12 maps like this change was.
What batch 6 has left to do in the routing itself: (a) `fd[outlet] = direction to the first cell of the way out`
for the lakes in `lake_outlets.json`'s `tops`, and the saved direction for the rest; (b) keep the pit at closed lakes
(no NHD outflow line and no NHDPlus line through them: Baldwin Lake), which today stay closed because crossbox finds
no way on; (c) decide the 12 lakes left at the terrain's cell (`kept` in `lake_outlets.json`): today crossbox's
walk puts their water on NHD's creek, with the gap closed it would follow the terrain's spill; (d) lakes whose
outlet lies on an edge between two boxes already flow on. Then `crossbox._dam_links`, `_pond_outflow` and
`_at_outflow` (which still moves 4 put-ins: El Toro Reservoir, DeKalb County Water Works, two unnamed Adirondack
ponds), the `carried_km2` additions, `05b`'s jump, `05c`'s `pond_links` and `06_map`'s order estimate and joins
across dams can go, each checked against the map it draws.

### Checks added, and how the change was accepted
In `checks/` (each says in its first lines what it reads; none needs a scratch folder):
- `cmp_rules.py`: two versions of the rule replayed on one build; `rule_tally.py`: which step decides each lake;
  `name_vs_v.py`: NHD's name against NHDPlus.
- `two_outlets.py`: every lake with several outflow lines the terrain takes on, and which the maps drew;
  `kept_explain.py`: the DEM along NHD's line at each lake left where it was; `follows_matter.py`: where the "stays
  on NHD's line" test changes a decision.
- `putin.py` (now with `at_top`, `putin_in`, `kept_why`), `lake_outlets.py` (reads the reach at the put-in too),
  `stray_pits.py` (lakes with more than one dead end), `top_drawn.py`.
- `down_review.py` and `lost_water_lakes.py`: the reaches scoring 10+ lower, with NHDPlus's drainage there and the
  lake behind each. `lost_explain.py`: each lake outlet flagged as no longer drawn, with what the map has there.
  `gone_explain.py`: the gone line by cause.
- `drainage_moves.py`: every drawn line whose drainage changed between two sets of maps, whatever its score did,
  with NHDPlus's drainage there; `attribute_moves.py`: the lake behind each.
- `place.py`: one place on two sets of maps, as lists and as a picture; `lake_look.py`: one lake's NHD and NHDPlus
  lines with the published and the new outlet; `seam_look.py`: a lake by a seam between boxes; `line_area.py`.
Accepted on: no failed step, no dead end on a box edge, no sudden flow drop, the same lakes with more than one dead
end (all cut by a box edge), known falls, every put-in on its way out or explained, the drawn lines against the
published copy by place (`drawn_cmp.py`, `gone_split.py`), every flagged outlet explained, and the audit's
`run_all.sh` with the overview session's two comparison scripts on its drainage tables, gauge by gauge and point by
point.

### Lessons
- Compare a routing change per lake and per reference point. LA's fish 60+ was 6 mi down while Bouquet Creek had
  lost its water.
- Read every line whose drainage fell (`drainage_moves.py`), not only the reaches that score 10+ lower. A creek
  that loses a pond's 1 sq mi scores 4 to 11 lower: Boyd Pond's tributary of the Grass River scored 9 lower in the
  scratch builds and was on no list until the rebuilt maps were compared by drainage.
- A reference point that reads worse is not always a loss: 14 of the 35 worse NHDPlus points sat in a lake or beside
  a junction that moved a few hundred feet, with the river's water unchanged. Look at the place
  (`place.py`) before calling it.
- Two builds' reach ids are not the same reaches: one new reach renumbers the rest of its box (Grass Pond Outlet
  looked like it had lost 3 km²; it was a different reach under the same id).
- A scratch root needs `data/known_falls_curated*.csv` in its `data/` folder. Without them nothing fails, but drops
  lose their "matches mapped waterfall" label and the audit's falls table for that build is wrong.
- `lake_outlets.json` doesn't keep the terrain's cell of a moved lake, so the rule can only be replayed on a build
  from before 2026-11-22. Storing it would let `cmp_rules.py` run on any build.

## The question
In flat ground the 10 m DEM's D8 routing can send a creek's water somewhere other than where NHD's stream network
sends it. The idea: lower ("burn") NHD HR's stream lines into the DEM before routing. Does that fix those places,
and at what cost?

## What was measured

### The problem is smaller than it looked
The count that started this was 826 reaches named after the NHDPlus V2 line they lie on, with under a quarter of
its drainage.
- **About half are side arms of split rivers.** D8 sends all the water down one arm, so the other reads only its
  own small drainage. No burn changes this.
- **Most of the rest are an artefact of that comparison.** V2 gives a line's drainage at its lower end. These
  reaches sit near the top of long V2 lines: in jackson and central_vt, a median of 15-18 % of the way down lines
  of 9-10 km, and 88-95 % of them in the upper half. Against NHD HR's own network their drainage is normal (km of
  HR line upstream per km2 of our drainage is the area's usual density).
- **The West Branch Beaver (adk_northwest) is V2's own network.** V2 sends Twitchell Creek's 50 km2 east into the
  West Branch. HR's lines and the DEM both send it north-west into Stillwater Reservoir.
- **Real disagreement with NHD HR is small.** `checks/hragree.py` asks, for each HR line, whether the D8 path from
  its middle reaches its end or the lines below it. It fails on 0.2-2.7 % of HR lines across 7 areas, mostly small
  lines in flat lowlands and wetlands (se_pa's 2.7 % is the tidal Delaware).

### Burning every NHD line hurts the waterfalls
Window test, n_georgia's rabun box, 19 x 19 km with 50 mapped falls:
- The DEM already agreed with every HR line there.
- At every depth tried (1, 3, 10 m), the burn lost 3 of the 4 waterfall-like steps and added 5 / 13 / 89 false
  cascades: burned paths run beside a fall instead of over it. Rejected.

### Burning flat ground only
The burn: lines lowered 3 m where the 50 m mean slope is under 5 %, and nothing within 2 km of an area's outer edge.
Without that edge rule, burned lines led the Deer River, the St. Regis and the West Branch Oswegatchie off the map.
Measured on whole areas, against baselines that reproduce the live builds byte for byte:

| | adk_northwest | jackson |
|---|---|---|
| HR lines D8 misses | 131 → 109 | 169 → 112 |
| NHDPlus V2 line ends where we read under half | 71 → 56 | 107 → 98 |
| reaches moving 10+ fish-score points (up / down) | 58 / 56 | 126 / 119 |
| km of drawn stream lines moving 20+ m | 741 of 6,963 | 753 of 9,240 |
| known falls found (both drop passes, 200 m) | 29 → 29 of 81 | 13 → 13 of 27 |
| sudden flow drops (`data/check_flow_drops.py`) | 0 → 0 | 0 → 1 |
| dead ends on edges between boxes; lake outlets under half | 0 → 0; 9 → 9 | 0 → 0; 0 → 0 |

- **Fixed:**
  - adk_northwest: the Raquette between Simon Pond and Raquette Pond (about 2 → 1,485 km2 on its reaches), stretches
    of the St. Regis and the Oswegatchie, and Sucker, Hopkinton, South Creek, Dan Wright and Indian River brooks.
  - jackson: the Snake fits V2 better (45 → 53 of its V2 lines within 0.67-1.5x), and so do the Salt and the
    Teton's Spring Creek arm.
  - Both: straight flat-resolution lines across wetlands and lakes drop by about a quarter in adk_northwest.
- **Made worse:**
  - Braided valley-floor rivers swap which arm carries the river. The lower Gros Ventre's named arm drops
    1,600 → 15 km2, and one Teton River stretch 1,042 → 71.
  - Windfall Brook drops 20 → 1, and one Raquette arm too.
  - A new sudden flow drop (teton_valley:s636).
  - In adk_northwest, 56 reaches swing 50-70 points only because their ends cross the 50 %-in-lake line of the
    "reservoir" class.
- **Overall:** jackson's 10+ point moves by drainage are 99 up and 91 down, a reshuffle. Fish 60+ km:
  adk_northwest 4,801 → 4,720, jackson 5,604 → 5,565.

### Verdict
Not worth installing as it stands.
- It fits NHD's lines better, but leaves the maps' content about level: a reshuffle in jackson, a small gain with as
  much churn in adk_northwest.
- It adds a flow-drop error.
- Installing changes every reach id and needs a full rebuild (`run_rebuild_a.sh`) and republish of all 12 maps.

## If we come back to it
Ideas, in the order they look most promising:
- **Burn only where the routing disagrees.** Burn just the HR lines `hragree.py` flags on the unburned build, plus
  their way on downstream, on flat ground. That would keep fixes like the Raquette without reshuffling braided rivers
  or moving lines elsewhere. Reach ids would still change wherever a box's routing changes.
- **Braided rivers.** Prefer NHDPlus's main path at splits, for example by burning lines that lie on V2 main paths
  (divergence 0/1) a little deeper than minor ones (divergence 2).
- **Side arms**, half of the original count, aren't a routing question. They would need a label ("side channel of
  the Snake") or the main river's size for the score.
- **The lake-class churn** comes from the 50 %-in-lake rule meeting new reach ends, not from the burn as such.
- **`checks/hragree.py` and `checks/v2_ends.py` are better routing checks** than the short-named count. Worth
  making standing checks in `data/` for any future routing change.

## How it works
- `harness/burnlib.py` builds the burn.
  - Lines: StreamRiver, ArtificialPath and Connector from every box's `nhd_flowlines.gpkg` (each box's file reaches
    0.5-3.7 km past its box, so together they cover any halo); canals, pipelines and coastline left out.
  - Rasterized one cell wide and lowered `BURN_M` m.
  - Only where the ground's 50 m mean slope is under `BURN_SLOPE` (0 = everywhere).
  - Not within `BURN_EDGE_M` m of the area's outer edge (edges between boxes are inside).
- `harness/patch_burn.py` patches a copy of `scripts/`:
  - `03_hydrology.py` keeps its unburned fill for `dem_filled.tif` / `fill_depth.tif` (what drops, profiles and
    crossbox measure on) and conditions the burned DEM for `dem_cond.tif` (the routing surface).
  - `03b_stitch.py`'s `condition()` (the seam mends) burns its piece of raw DEM the same way.
  - With `BURN_M=0` both run exactly as before.
- Lakes: the HR line through a lake that holds water is burned like any flat line. The lake drains along it to NHD's
  outlet, which 03b's lake rule then takes as the cell where paths end.
- Seams: every box's halo is burned from the same lines, so both sides of a shared edge see the same surface. 03b
  mended every dead end on a shared edge in both test areas.

## Rerunning the measurement
Put the roots outside the repo: they hold 0.5-1.5 GB per area once built. One heavy step at a time: 03 peaks at
2.8 GB on a big box, 03b at about 2.5 GB. If another session is about to publish, pause: `publish_site.sh`'s
build guard can't tell a scratch 03b from a real build.
```
H=/Users/mac/Fishing/data/stream_burning/harness
$H/setup_root.sh /private/tmp/burn/r0 adk_northwest      # baseline copy
$H/setup_root.sh /private/tmp/burn/r3e adk_northwest     # burned copy
# baseline: copy the project's dem_cond / dem_filled / fill_depth into r0/data/derived/<area>/<box>/, then start at 03b
BURN_M=0 $H/run_chain.sh /private/tmp/burn/r0 adk_northwest 03b
BURN_M=3 BURN_SLOPE=0.05 BURN_EDGE_M=2000 $H/run_chain.sh /private/tmp/burn/r3e adk_northwest 03
$H/run_checks.sh /private/tmp/burn/r0 adk_northwest
$H/run_checks.sh /private/tmp/burn/r3e adk_northwest
$H/compare.sh /private/tmp/burn/r0 /private/tmp/burn/r3e adk_northwest
```
- `setup_root.sh` copies `scripts/` (patched), links the raw inputs one file at a time, and copies the area's
  `_shared` (its `cache/` linked). Nothing in the project is written.
- `run_chain.sh` runs 03 → 03b → 04 / 04b → 05_score → 05c → 05b. It takes `BOXES="a b"` to condition only some
  boxes, and starts at `04` to resume after a finished 03b. Each step's time and memory go in
  `<root>/data/chain_<area>.log`.
- `run_checks.sh` runs everything below.
  - `score_root.py` gives the root's reaches fish scores without the late steps. Access, sun and context come from
    the project's reach nearest each new reach (they belong to the place, not the routing); area, flow and reach
    attributes come from the root's own build. It refuses to run on the project.
  - Then `standing.py` (lowest drainage, dead ends on shared edges, order-3+ cells with no reach), `short_named.py`,
    `classify_short.py`, `v2_ends.py`, `hragree.py`, `lake_outlets.py`, and the root's `check_flow_drops.py` and
    `validate.py`.
- `compare.sh` lists the reach moves (`compare_roots.py`), how far the lines moved (`moved.py`), straight runs
  (`straight.py`) and known falls found (`falls.py`).
- A baseline that doesn't reproduce the live build means the pipeline has changed under it. Check flowdir,
  area_km2, knickpoints and streams_scored byte for byte before trusting a comparison.
- Window tests, quick and light (a 15-20 km window in a few seconds):
  - `window_hr.py` scores depths by HR agreement;
  - `window_drops.py` scores them by drops and known falls (it copies 04's detector);
  - `window_plot.py` draws two depths side by side.
  - Set `NUMBA_CACHE_DIR` to a scratch folder when importing `03b_stitch.py` from tests, so no numba cache lands in
    `scripts/__pycache__`.
- One pitfall already met: scipy's `uniform_filter` keeps a running sum, so one `inf` turns the rest of its row into
  NaN. `burnlib.flat()` gives no-data cells 1e3 instead.

## Files
- `harness/`:
  - the DEM burn (parked): `burnlib.py`, `patch_burn.py`;
  - the lake routing (installed): `patch_lakes.py`, which patches a `scripts/` copy (or the project) exactly as
    measured;
  - scratch builds: `setup_root.sh`, `run_chain.sh` (starts at 03, 03b, 04 or 05b), `run_checks.sh`, `compare.sh`;
  - whole-area measuring against the live build: `measure_area.sh`, `remeasure_05b.sh`;
  - windows: `window_hr.py`, `window_drops.py`, `window_plot.py`.
- A scratch copy needs the area's lakes layer, which 05b reads: copy `data/derived/<area>/_shared/lakes.gpkg` into
  it, or its reservoir classes differ from the live build's.
- `checks/`: the measures above, plus:
  - `summarize.py` (one table over the measured areas);
  - `hr_density.py` (HR km per km2 of drainage for flagged reaches);
  - `xref.py` (flagged reaches against nearby HR misses).
  - `drops.py` (two builds of one area: the 10+ point fish-score moves by cause, and the lines only one has);
    `outlet_gaps.py` (stream links under 05_score's floor that carry a lake's water); `drawn_lake_values.py` (stream
    line a map draws with a lake's values outside the lakes it draws, in two versions of its `map3d_data.js`);
    `summarize_drops.py` (their CSVs over the areas); `verify_install.py <root> hydro` compares only 03b's rasters
    and the drops.
  - `why_moved.py` (which score terms moved for the moves in a cause group, and whether the reach was cut
    differently); `why_gone.py` (what 03b has now along a creek line only the older build draws); `totals.py`
    (reaches, km, km of fish 60+ per area for any builds).
  - `drawn_cmp.py` (what two versions of the published map draw by default: line, fish 60+, new and gone line, score
    moves; takes folders of `<area>.js` or site commits); `putin.py` (each lake's put-in against its routed way out
    and NHD's outlet).
  - Since 2026-11-21, `lake_outlets.py` takes the reach carrying the most water within 150 m of NHDPlus's outlet
    point (the nearest one was often a side creek), and `standing.py` counts a reach that starts in the same box as
    continuing a reach end on an edge.
- `results/`: the 2026-11-20 runs.
  - `checks_r0_*` baseline, `checks_r3e_*` the burn above, `checks_r3_adk_northwest` the same without the edge rule.
  - `compare_*` the comparisons; `hragree_live_6_areas.txt`; `classify_short_live_12_areas.txt`.
  - `lakes_2026-11-21/`: the lake routing's 12-area summary and per-area checks and comparisons.
  - `installed_2026-11-21/`: the 12 installed builds (lake routing and the carried-water floor) against the builds
    before: totals, moves by cause, the named cases, lines gone, lake outlets, each area's checks.
  - `root_fix_2026-11-22/`: the lake-outlet fix: the 12 scratch builds and the rebuilt maps against the published
    copy. Its `README.md` lists the tables.

## Lake shores, side channels, drops below dams (installed 2026-11-21, late)
Work of the session "Fix the lake-routing side effects and open items", measured from the drops on (04) in scratch
copies of all 12 maps, against a baseline built the same way from the same 03b outputs with the scripts of 80b42e8.
Log entry: "2026-11-21, late: reaches cut at lake shores" in `MULTI_AREA_LOG.md`.

- **What went in** (`scripts/`):
  - `05_score.py` cuts the stream links at lake shores, names a creek's last stretch beside a river after the creek,
    marks true side channels, and calls a drop at a dammed lake's outlet the dam.
  - `05b_flow.py` measures a reach's length in a lake against the shore the map draws, counts a reach at the end of
    a gauge's own model line as on it, and gives a side channel its river's flow.
  - `04_knickpoints.py` / `04b_bigcreek_steps.py` size channels with the water carried past dams.
  - `crossbox.py` puts a lake's water back in at the top of the routed outflow line.
  - `scoring.py` keeps a creek below a lake or dam at NHD's class or better (LA).
  - `watertemp.py` has a lake term, and a map without a fit of its own can take its region's.
  - `lake_bathymetry.py` reads Lake Champlain's chart soundings.
- **Scratch builds from 04** (`harness/`):
  - `setup_clone.sh <root> <derived source root> <area> ...` copies `scripts/` and clones the raw and derived files
    (APFS `cp -c`: no space, and nothing in the scratch root can write through to the project).
  - `chain_from04.sh <root> <04|05|05b> <area> ...` runs 04 + 04b, 05_score, 05c, 05b.
  - `evaluate.sh <rootA> <rootB> <outdir> <area> ...` scores both roots (`checks/score_root.py`; set `LATE_ROOT` to a
    frozen root while the project itself is being rebuilt), runs the checks on each and compares B with A.
- **Checks** (`checks/`):
  - `lake_shares.py <root> <csv>`: each reach's length inside the drawn lakes, with 05b's flag; km of creek scored as
    lake and of lake scored as creek.
  - `sumeval.py <outdir>`: one table over the areas of an evaluation.
  - `moves2.py <outdir> <root name>`: the 10+ point moves by what the reach is in the new build (lake water, creek).
  - `landing.py <root>`: where crossbox puts each lake's water back in against the routed outflow line.
  - `piece_water.py <root>`: pieces of cut links that end above the point where carried water joins their link.
  - `side_channels.py <root> <csv>`: small reaches named after the river beside them, by kind.
  - `damlake.py <root>`: drops at the outlets of dammed lakes, by status.
  - `under_floor.py <root>`: creek pieces under the 1 km2 floor (kept: they are stretches the map drew before).
- **Numbers**: `results/shores_2026-11-21/` (the table over the 12 areas, the moves by kind, per-area check output).
- **Measured and not installed:**
  - Carrying a gauge's record along its creek across junctions (reaches with a record 1,170 -> 3,097): it put dry
    records on reaches 2-4 km above their gauge and below junctions where another creek comes in.
  - The plain lake share in the water-temperature fits, and one fit for all four Adirondack maps: see `watertemp.py`.
- **Things that bit:**
  - A scratch `06_map.py` run needs the late tables for drops too (08, 10, 11), which a scratch root doesn't have: it
    runs through the streams and stops at the drops. Enough to test the stream popups; the lakes can be tested with
    `maplakes.load()`.
  - A helper named `numbers.py` in the folder the checks run from shadows Python's own `numbers` module and breaks
    every numpy import there.
  - `lake_outlets.py` looks 100 m down NHDPlus's outlet line and leaves out reaches mostly inside NHD's outline. With
    the links cut it can pick a small creek piece: where the routed way out leaves the lake somewhere else
    (Stillwater Reservoir), where the next lake starts right below (Number Four Reservoir), or where the lidar's lake
    is smaller than NHD's (Spy Lake). Look at the reaches around the lake before reading such a flag as lost water.
