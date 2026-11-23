## 2. Accuracy by topic

Each topic says what was verified right and how, what is wrong, and what could not be checked and what data would
settle it. Tables are per area; `adk_*` are the four hidden Adirondack maps.

### 2.1 Is the creek there, and in the right place

**Right.**
- Named creeks. I walked all 23,242 mi of NHD's named stream lines inside the maps in 80 ft steps and looked for a
  drawn line within 500 ft. The 2,894 mi with nothing drawn all lie where the terrain routing has under 0.39 sq mi,
  the map's size floor. No named creek above the floor is missing, apart from three kinds left out on purpose: New
  York's shore inside the Vermont boxes (cut at the state line), the centrelines of lakes cut by a map edge (Tugaloo
  11 mi, Tellico 9.8 mi) and tidal water (Darby Creek 5 mi, the Delaware, the Christina, the lower Schuylkill).
- Course. Where NHD has a line within 500 ft, the drawn line sits a median 23-36 ft from it, and 90 % of it within
  69-138 ft.

**Wrong, or worth knowing.**
- The floor hides named headwaters (finding 5; the 98 trout records on undrawn water are in
  `trout_records_off_map.csv`).
- 3,472 of 50,526 drawn miles (6.9 %) have no NHD line of any kind within 500 ft, 741 mi of them rated fish 60+
  (High Peaks 199, Jackson 135, Adirondacks north-west 133, south-west 127, south-east 77). Nearly all are order 1-2.
  Their popups give a modelled year-round flow; only 5-20 mi per map carry the "NHD unmapped" note. They may be real
  brooks NHD never drew or lines across wet flats. The 796 longest are in `streams_vs_nhd_extra.csv`; three to look
  at: 43.84733, -75.16794 (2.6 mi, fish 66), 44.70281, -73.95909 (2.6 mi, fish 63), 44.04024, -110.97289 (2.4 mi,
  fish 61).
- Rivers fed from outside the map are too small (finding 4, and 2.3).
- Beside big rivers the nearest drawn line is often a small side line: at 20 % of LA's river points of 39 sq mi or
  more, 14 % of Jackson's, 12 % of the Adirondacks south-east's. Tap the river and the popup can be a 0.5 sq mi
  creek's. The live build names 215 of them "(side channel)".
- Two lake-routing faults leave outlet creeks undrawn or fed from the wrong end (finding 8).

**Not checked.** Whether the 3,472 mi with no NHD line are real water. A lidar-derived stream network would settle
it (USGS 3DHP as it is released; NHDPlus HR where finished), or imagery for a sample from the list above.

{{T1}}

### 2.2 Names and drainage labels

**Right.** Where a drawn reach follows one NHD-named stream (60 % of its length within 130 ft of it), the name is the
same on 99.6-99.9 % of miles. Per area 0-4 mi carry a different name and 0.4-5.8 mi lack one; the 67 cases of 1,000 ft
or more are in `name_mismatches.csv` (longest: Douglass Creek, 1.8 mi unnamed at 43.66819, -75.44434; a mile of Deep
Creek named "Santa Ana River" at 34.10487, -117.09321).

**Worth knowing.** 585 mi in LA (20 % of its named miles) and 52 mi in Jackson carry names NHD has no stream line
for: canyon names (Fish Canyon, Devils Canyon, Death Canyon Creek, Paintbrush Canyon). They read sensibly; NHD cannot
confirm them.

**Wrong.** A lake's popup gives the drainage the lake had before the map step renamed the basins (the helpers counted
29 of Jackson's 34 lakes in the unnamed group lying inside a named outline, 102 of 211 in the Adirondacks north-west).
Twelve drainage and fork names are hand overrides (`05c_drainages.py:46-76`).

**Not checked.** Drainage (basin) labels against an outside source. The national watershed boundary names (WBD
HU12) would do.

### 2.3 Drainage area and stream order

**Right.** Against the drainage area in each USGS gauge's own site record: the median ratio is 0.97-1.02 in every
area, 84 % of 499 gauges are within 10 % and 92 % within 25 %. Against NHDPlus at 4,806 points of 39 sq mi or more, a
drawn line carrying at least half that drainage is within reach at 96 %, and one within 25 % at 86-100 % by area.

**Wrong.**
- Too small where the headwaters are off the map (best-fitting drawn line at the gauge, drawn / gauge): Chattooga at
  Burrells Ford 0.63 (34.975, -83.116), Suwanee Creek 0.66, Big Creek near Cumming 0.56 and near Alpharetta 0.79,
  Green River at Garfield VT 0.65 (44.603, -72.535), French River at North Grosvenordale 0.41 (41.978, -71.901),
  Quinebaug at Putnam 0.79, North Branch Neshaminy 0.67, Independence River 0.74 and 0.76 (two gauges), Sugar River
  0.78. In LA: Santa Ana River below Prado Dam 0.43, the Los Angeles River at Sepulveda Dam 0.03, and Warm Creek 3.5
  times too big (routing across the San Bernardino valley floor). All in `area_vs_gauges.csv`.
- Stream order is an estimate on 9,122 reaches: the map step replaces the counted order by "the usual order for this
  drainage" wherever water is carried in from elsewhere (`06_map.py:84-105`). In the Adirondacks south-east that
  table collapses: every carried reach of 100 sq mi or more is order 7 (520 lines) and order 6 holds 11 creeks of
  about 1.5 sq mi. 121 lines of order 5 or more drain under 2 sq mi.

**Not checked.** Order against NHDPlus's own order (its network starts at bigger creeks, so the two differ by about
one by design).

{{T2}}

### 2.4 Summer flow: class and cfs

**Right.** At 243 gauges with five or more full summers since 2011, matched to a drawn reach of the gauge's own
size: outside LA every gauged creek is wet and every one is shown wet. In LA the class agrees at 38 of 47 gauges.
The one wet gauged creek shown dry on the site before tonight (the first 0.87 mi of Piru Creek below Santa Felicia
Dam: "mostly dry, 0.00 cfs, fish 3" where USGS 11109800 has never dropped under 7 cfs) is fixed in the live build.

**Wrong.**
- Outside LA the class carries no information (finding 2). It is a drainage cut: by each area's flow table a creek
  reads year-round from 0.12-0.27 sq mi on nine maps, 0.93 sq mi in NE Connecticut and 3.2 sq mi in LA (a helper's
  working, `audit/work/code_core.md` G-1). The agreement at gauges above means little there: the gauges are on creeks
  big enough to gauge, and the yearly index is made from the same gauges, canals and tailwaters included
  (`02b_download_flow.py:149-150`, `:203-216`).
- Creeks NHD maps perennial that the map shows below year-round: 1,736 reaches, 993 mi. LA 770; NE Connecticut 669,
  of which 398 have trout on record; central Vermont 165 (`perennial_shown_drier.csv`).
- "Low flow about X cfs": within 2x of the gauge at 86-100 % of gauges outside LA, but 70 % in central Vermont
  (West Branch Little River 19 cfs against 6.2 measured; Ranch Brook 11 against 3.1; Dead Creek 3-4 against 0.07-0.2)
  and 46 % in LA (Lytle Creek 8.3 against 0.34; Santa Clara River near Piru 0.39 against 17.8). Reaches a tunnel or
  canal bypasses read the whole river: Tallulah Gorge 277-281 cfs against 39, the Cheoah 209 against 91, Granite
  Creek above its supplemental ditch 38 against 9.
- LA (finding 3): trout on record on 81 reaches shown dry (`trout_found_shown_dry.csv`); 145 mi NHD-perennial shown
  mostly dry (Hot Springs Canyon Creek 6.6 mi, San Mateo Creek 4.8, Oso Creek 4.3, Black Star Creek 3.2); 4 of 20 dry
  gauged creeks shown wet (Sespe Creek near Wheeler Springs flows in 31 % of summers and reads year-round, fish 77).
- Sudden changes along a creek with no tributary between: 269 places over the 12 maps, 205 of them in LA
  (`drawn_jumps.csv`).
- Where the flow look-up finds no model line below a creek, the popup falls back to NHD's label and the score to
  0.15-0.35: 364 reaches outside LA, 1,456 in LA. That is a failed look-up, not evidence about the creek.

**Not checked.** Whether a small creek outside LA holds water in August. Nothing in the project can say. What would:
USGS's streamflow-permanence models where they exist (PROSPER covers the Snake basin), StreamStats low-flow statistics
in the East, or field notes. The greenness test that works in LA found nothing to separate in the humid areas.

{{T3}}

{{T10}}

### 2.5 Fish score

**Right.** The score in the popups follows the documented formula: recomputed from each area's reach table it lands
within 2 points on 99.6-99.9 % of reaches (`scoring.py:322`). It tops out at 100 on 0-7 % of miles (Jackson 7.3 %),
so piling up at the cap is a smaller problem than the log feared.

**Wrong, or worth knowing.**
- What the score measures outside LA. The water term averages 0.97-1.00 (NE Connecticut 0.90), gradient 0.84-0.96,
  temperature and shade 0.70-0.88. Those barely vary, so the ranking comes from stream size (correlation with the
  score 0.58-0.82), a trout record (0.31-0.67) and remoteness (0.0-0.52). A creek of 0.39 sq mi gets no size credit
  and one of 19 sq mi gets all of it, which is why small roadside brook-trout water cannot pass about 54.
- Markdowns without near-certain evidence (finding 7):
  - One empty sample halves the score for the same-named creek within 0.9 mi (3.1 mi in California), and it
    outranks a trout designation (`scoring.py:199`, `11_context.py:361`): NE Connecticut 154 reaches, 117 of them
    inside a designated trout water or brook-trout patch; Smokies 57; LA 56, where a survey with an empty species
    field is read as "no trout found" (`11_context.py:253-258`).
  - No flow estimate: the score uses NHD's label, and "unmapped" (no NHD line within 200 ft at two of three points,
    `05_score.py:132`) counts 0.15. 364 reaches outside LA; 808 "unmapped" reaches drain 8 sq mi or more.
  - Burn: a severity nobody mapped counts as the worst (3,462 of 4,061 burned reaches, `scoring.py:124`), and the
    factor applies everywhere: Spread Creek in Jackson (70 sq mi, year-round cutthroat water) scores 35.
  - The burn and trout windows go by calendar year, so scores step on 1 January with no new data.
- Trout on record and a score under 40: 1,322 reaches (LA 641, NE Connecticut 400, Jackson 63), listed with the term
  that did it in `trout_low_scores.csv`.
- The trout bonus is on 54 % of all reaches and 82-86 % of three Adirondack maps (New York's (T) water classes), so
  there it lifts nearly everything and separates little. Every one of the 2,975 reaches at exactly 100 has it.
- The same thing counted in more than one place: hot air marks LA's desert reaches down twice (all 308 reaches with
  no temperature credit are also cut by the heat gate, which reads the same air figure); drainage area raises the
  size term, lowers the temperature credit in seven areas' fits and sets the flow in LA and, through the cut above,
  the class everywhere else; a minute ridden counts twice in remoteness (your choice,
  `scoring.py:134`); a trout designation is taken by any reach whose buffer touches the designated line, so the
  lowest reach of each side creek inherits the main stem's (`11_context.py:590-596`).
- Left over: `05_score.py:283-288` computes a first score with an elevation band that only LA has (`config.py:59`);
  the map step throws it away and scores again (`06_map.py:73`). `fish_score_diagram.py` draws four factors where
  the score has five, with LA's wording, as 12 identical unpublished files.
- Against survey results. Taking the trout factor out and asking whether the score separates reaches where trout
  were found from reaches whose latest sample found none (0.5 = no better than chance): LA 0.63 (766 against 53),
  NE Connecticut 0.73 overall but 0.51 for wild trout (415 against 133), Smokies 0.93 (1,623 against 57, where the
  empty samples sit on 1.2 sq mi creeks). Thin evidence, three areas only (`fish_score_vs_surveys.csv`).

**The trout records behind the labels** (from reading `troutdata.py` and `11_context.py`; counts on cached data by
a helper):
- A reach takes a designation by touching the designated line, so the lowest reach of every side creek carries the
  main stem's (`11_context.py:590-596`).
- Adapters list the values to drop, so a new value becomes trout water by default: three Adirondack patches valued
  "Brown & rainbow trout only" are labelled "Wild brook trout patch"; five Wyoming streams the state lists as "Clear
  (No trout present)" are labelled native cutthroat water (`troutdata.py:543-556`, `:262-264`).
- Stocking lists with no date are stamped with the build year (Virginia, Delaware, North Carolina, Tennessee, New
  York; `troutdata.py:55`), so their bonus never ages out.
- New York fishing-rights easements count as trout water, a bonus for access rather than fish (`troutdata.py:525-527`).

**Not checked.** Whether a high score means good fishing. Fish counts per sample would settle it: Connecticut's are
in the cache already, the Smokies' three-pass workbook and Tennessee's are not used.

{{T4}}

### 2.6 Water temperature

**Right.** The popup's "± N °F" is the fit's real error: at the measured sites that lie on a drawn line, 58-84 % of
sites fall inside the stated band, about what a one-standard-error figure should give.

**Wrong, or worth knowing.**
- The estimates are squeezed toward the middle. Sites measured under 68 °F read 1-4 °F warm; sites over 72 °F read
  2-6 °F cool. Of the sites measured at 72 °F or more, 19 are shown at 68 °F or less and so get full temperature
  credit.
- Dams are handled by a hand list of three areas (`scoring.py:153-166`). The Nottely River below its dam measures
  59 °F and reads 69; the Snake below Jackson Lake Dam measures 61 °F and reads 51 (lake water leaving over the top;
  only the Adirondack fits have a lake term).
- The four Adirondack maps disagree at their edges: a creek fed wholly through a lake reads 73-74 °F on three maps
  and 65 °F on the south-east one, whose fit has no lake term, about 10 score points for the same creek type. The
  north-west map's fit depends on the order the maps are built in (3.5).
- The readings come from the Water Quality Portal's older interface (`watertemp.py:84-89`), which a helper recalls
  stopped receiving USGS's own samples in March 2024. Not verified here; worth a check.

**The lake term, tested** (asked by the overview session; `lake_term_test.py`, tables `lake_term_*.csv`). The
answer: it is supported at the pond's outlet and overstated below it.

Since 21 November three Adirondack fits add 11-12.5 °F times the share of a reach's water that arrives through a lake
or pond. On the drawn maps that takes 10 or more points from 133 mi of creek (High Peaks 46, north-west 31,
south-west 56), where the estimate reads 73-75 °F against 61-64 °F without the term, and 5 to 10 points from a
further 331 mi. Of the 133 mi, 125 carry a trout record (105 mi New York's trout water class, 19 mi a wild brook
trout patch), and 28 mi fall from a score of 60 or more to under 60. "10 points" is a knife-edge, because the term's
commonest markdown is 9 to 12 points: at 9 points it is 190 mi, at 8 points 242 mi. That is most likely why the
overview session's count (179 mi) differs from mine; I could not rerun theirs.

I walked up the main stem from every measured site and every marked-down stretch to the first lake, to see how far
below what size of pond each lies. The three maps have 276 measured sites on a reach. 36 of them are mostly lake
water (145 readings):

| Where the site is | Sites | Readings | Measured | Sites at 73 °F or more | Sites at 68 °F or less | Warmer than a creek with no lake | The map's estimate is |
|---|---:|---:|---:|---:|---:|---:|---|
| within 650 ft of the pond | 18 | 102 | 74.9 °F | 15 | 0 | 12.6 °F | 2.8 °F too cool |
| 650 ft to 0.6 mi below | 8 | 18 | 68.3 °F | 2 | 4 | 6.3 °F | 2.4 °F too warm |
| 0.6 to 1.9 mi below | 7 | 18 | 65.5 °F | 0 | 5 | 3.3 °F | 5.3 °F too warm |
| over 1.9 mi below | 3 | 7 | 71.1 °F | 1 | 1 | 8.2 °F | 0.6 °F too cool |

Water of 68 °F or less earns the score's full temperature credit; a 10-point markdown needs about 73 °F.

- **At the outlet the warmth is real, and bigger than the map says.** The 18 sites are monitoring sites named for a
  pond's outlet or dam, with 4 to 7 readings each. They measure 70 to 79 °F and none is cool. The 29 mi of marked-down
  creek within 650 ft of a pond are supported.
- **Below the outlet the warming is about half.** From 650 ft to 1.9 mi the 15 sites average 67.0 °F: 4.9 °F
  (give or take 1.3) warmer than creeks with no lake, against 12.6 °F (give or take 0.6) at the outlet. The term has
  no distance in it, so it splits the difference: too cool at the outlets, 3.8 °F (give or take 1.4) too warm below.
  92 of the 133 marked-down miles lie in this zone and 9 mi further down.
- **That evidence is thin and uneven.** It is 15 sites and 36 readings. The five sites with three or more readings
  average 69.9 °F and agree with the map (0.7 °F too warm). The ten visited once or twice average 65.5 °F (5.3 °F
  too warm). Counting all of them, the sites support a markdown of 3 to 5 points on these reaches; counting only
  the well-sampled five, about 9. The map takes 10 to 13. So below the outlet the markdown is not near-certain,
  which is your rule for marking water down.
- **Pond size.** The routing treats a pond as a lake only where 5 acres of it lie level (`03b_stitch.py:44`), so the
  log's worry that any pond counts, however small, is bounded: the smallest pond above a marked-down reach is
  5.7 acres. 21 of the 133 mi lie below ponds of 5-25 acres, where only 4 sites were measured (5.9 °F warmer than a
  creek with no lake, against 9-10 °F below bigger ponds). Three of those four are over 0.6 mi below the pond, so
  size and distance cannot be told apart.
- **Trout records do not separate warm from cool.** 35 of the 36 lake-fed sites are on a reach with a trout record;
  they average 71.3 °F and 18 of them measure 73 °F or more. Exempting creeks with a trout record switches the term
  off on 94 % of the miles it marks down, the pond outlets included, where the warmth is measured. In effect it
  takes the term out of the score.
- **What the sites support instead: a lake term with distance in it.** Fitted to the 62 measured sites that have
  lake water and a lake upstream, with the fit's other terms held, the warming per unit of lake share is 14.9 °F
  within 650 ft of the pond and 7.6 °F beyond. Its leave-one-out error on the lake-fed sites is 4.5 °F, against
  5.3 °F for the single value used now (`lake_term_distance_fit.csv`). On the map that would deepen the markdown on
  the 29 mi at outlets (to about 17 points) and cut it to about 5 points on the 100 mi below. It is decision 5e.

**Not checked.** The fits against sites they did not see. A hold-out, or a second network (EcoSHEDS in the
Northeast, NorWeST in the West), would settle it.

{{T5}}

### 2.7 Elevation and gradient

**Right.** Popup elevation equals the 10 m elevation model at the reach's middle (median difference half a foot, 95 %
within 7-42 ft). Gradient is within 0.5-1.3 percentage points of (top minus bottom) / length on 90 % of reaches.
2-13 % of reaches read 0.0 %.

**Not checked.** The elevation model itself.

### 2.8 Drops and falls

**Right.** Every fall from the lists is on the map whether or not the terrain found it.

**Worth knowing.** The terrain method alone finds a drop within 330 ft of 44-76 % of the known falls that have a
precise point (NE Connecticut 20 %, SE Pennsylvania 0 of 11). The README's validation table counts the detectors' raw
output, before the filters and statuses that decide what the map shows, and is a day older than the detectors
(`data/validate.py:28-50`). "Precise" is given by source type, not measured: every OpenStreetMap falls node is
precise, and 29 of 1,205 still sit on the old GNIS coordinate.

**Not checked.** Drop heights, and how many "unmapped" candidates are real falls. Only imagery or a visit can say;
no list in the project carries heights.

### 2.9 Lakes

**Right.** 7,450 lakes. Against NHD at each area's own smallest size the layer misses 85 lakes, nearly all treatment
or storage basins left out on purpose and New York's shore of the Vermont boxes. Acreage is within 10 % of NHD's for
56-89 % of lakes; the rest are lidar shorelines, which are the better source.

**Worth knowing.** A measured depth exists for 170 lakes (2.3 %): Jackson 58, NE Connecticut 44, central Vermont 18,
4-9 on each other map, one each in Lexington and the Smokies. Fish records exist for 0.5-5.5 % of lakes.

**Wrong.** "Outlet creek profile" opens nothing for the 3,601 lakes whose outlet has no name (`maplakes.py:225`).
"Trout stocked or recorded here" comes from any salmonid record of any year: 5 lakes list only whitefish or cisco, 49
nothing since 2000 (`maplakes.py:152`). Soundings taken at other spots are called conflicts: "Lake Champlain max 318
ft ... conflicts: 17 ft by EPA" (`05d_lakes.py:974-980`). The dashed edge for a dry or marsh lake never draws: one
file writes "little level water", the other looks for "no level water" (`05d_lakes.py:572`, `maplakes.py:253`; 401
lakes). The smallest lake kept is set by hand per area: 1.2, 2.5 or 4.9 acres (`05d_lakes.py:42`).

**Not checked.** Depths against a second survey; acreage against agency figures.

{{T6}}

### 2.10 Access: drive, bike and hike times

**Right, as far as it can be tested from inside.** No impossible values: implied driving speed has a median of 34-51
mph and stays under 60 at the 95th percentile; no drive is shorter than the straight line from home. The fire-road
rule is kept for the trail layer's fire roads, wilderness included, with the "double-check bike access" flag.

**Wrong** (finding 1, and from reading `08_hike.py`, `09_drive.py`, `07_road_closures.py`):
- The build day's closures are in the times; the access line has no date. A four-hour night closure or a county
  closure whose reopening date passed months ago is cut the same way.
- Any drivable road cell is a place to park; the parking and trailhead layer is not used (`08_hike.py:61-62`).
- No OpenStreetMap track is ever driven, though the access step knows which forest roads are open to cars, so
  drives up open forest roads become rides or walks, and remoteness rises with them (`09_drive.py:53-54`).
- Walking on a trail uses the hillside's slope, not the trail's grade (`08_hike.py:210`); the README says the trail's.
- Rivers are not barriers: a route crosses the Snake or the Hudson at creek-bed speed (`08_hike.py:210-211`). Private
  land and closed trails cost nothing on foot.
- Each box is timed alone, so a reach near a box edge is timed from a road in its own box (`08_hike.py:44`).
- Trails the map draws from agency data but OpenStreetMap lacks are bushwhacks to the timing (`08_hike.py:59-60`).
- Drive times snapped across a gap are computed as approximate and never marked (`09_drive.py:167`); the README says
  they are flagged.
- Your bike rule is not kept in three cases: fire roads that carry the Appalachian Trail or the Long Trail are ridden
  with no flag (`08_hike.py:41-42`); gated roads that are not tracks are ridden with no flag even where bikes are
  barred (`08_hike.py:134-137`); private tracks are dropped rather than flagged (`08_hike.py:136-137`).
- 1.5 % of LA's reaches and 0.5-2.7 % of three Adirondack maps' have no drive time at all.

**Not checked.** The times themselves: nothing independent is in the project. A routing engine run on this Mac over
the same OpenStreetMap extract would test the drives; 20-30 trailhead-to-lake distances from agency pages would test
the walks (the README tried two in Jackson and found them 8-13 % short).

{{T7}}

### 2.11 Sun and canopy

**Right.** Popup canopy equals the canopy raster along the line (median difference 0-2 points). Possible sun hours
come out at 14.2-15.1 by latitude, as they should for mid-July.

**Worth knowing.** Sun hours lean high: trees are left out, ridges more than 1.9 mi away are not seen (the Tetons
stand 3-6 mi west of the valley floor), and terrain past a box edge is missing. The canopy layer's year is not
recorded anywhere, so "the 2024-25 fires show" is unproven (`11_context.py:392-417`).

**Not checked.** Sun hours against a full-horizon solar model.

### 2.12 Do the published files come from committed code, and were all 12 built by the same code?

- The site before tonight (`6875118`): built 19:30-22:04 on 21 November, the scripts committed at 19:50 and 20:26
  during the builds; no later commit touched a script before the push. Consistent with one code state. It cannot be
  proven: nothing in an output records what built it.
- The live site (`d16a885`): built 22:31-23:34. `05_score.py` was saved at 22:41 after LA, Jackson and central
  Vermont had run it; I compared it with the copy in the building session's scratch folder and only a comment
  differs. `06_map.py` gained 48 working lines at 22:57, after five maps had been drawn (Jackson, central
  Vermont, LA, Lexington, NE Connecticut). Every map was then drawn once more outside the driver logs, 30 seconds to
  17 minutes after its driver finished, so all 12 come from the final file. The profile step was not rerun after
  that: `profiles_data.js` is older than the map in 11 of 12 areas. The code was committed at 23:37
  and the site pushed at 23:47. So: one code state in substance, committed after the fact.
- All 12 live data files carry the same fields and wording, and no step of the newest runs logged a failure.
- What tonight's publish changed, by the same measures on both sites: drawn stream line 50,549 → 50,526 mi; drawn
  fish 60+ 25,154 → 25,112 mi (up 1-17 mi on the eight shown maps, down 8-27 mi on each Adirondack map); sudden
  changes along a creek 287 → 269; the dry stretch of Piru Creek below Santa Felicia Dam fixed. Named-creek cover,
  drainage against gauges, flow classes at gauges and names did not move.
- `audit/scripts/provenance_steps.py` compares each step's start time with the file times of the code it loads. It
  caught both edits, and it cannot see reruns made by hand: a stamp in the outputs is the real fix (finding 10).

### 2.13 Licences and credits

| Source | On the site | Terms as recorded in the project | Credit shown | Status |
|---|---|---|---|---|
| NY DEC ArcGIS: trout stream reaches, (T)/(TS) classes, fishing access; DEC lands | 4 Adirondack pages (unlinked, public) | "secondary distribution not allowed"; "may NOT be distributed outside DEC without permission" | in each label | against your rule (data.ny.gov only); open since 20 Nov |
| World Waterfall Database | 106 falls: central Vermont 44, LA 13, Smokies 6, Adirondacks 43 | no redistribution without written consent | popups only (under 50 falls per map, `06_map.py:54`) | consent asked 20 Nov, no reply |
| nnywaterfalls.com | 116 falls, Adirondacks | no distribution without written permission | popups; credit line on one map | consent asked 20 Nov, no reply |
| gawaterfalls.com | 695 falls, North Georgia | no licence | credit line and popups | published on your decision; author not asked |
| New England Waterfalls 35, tchester.org 27, RiverBrain 9, Vermont River Conservancy 6, ncwaterfalls.com 4, four one-row sites | curated falls | none recorded | popups | terms never read |
| Apple Maps (1 point), komoot (1 link) | Triple Buckets; Wigwam Falls | Apple forbids taking data out of Maps | popup | replace the point |
| iNaturalist sightings; GBIF records at lakes | trout evidence | each record has its own licence; not kept | "iNaturalist" in the line; GBIF not named | fine for a personal site; name GBIF |
| OpenStreetMap | trails, roads, parking, falls, lake outlines | ODbL | "© OpenStreetMap contributors" on the area maps; missing on the all-areas page | add the credit there and a line that the derived layers are ODbL |
| Sentinel-2 | decides "bare channel" in LA and Jackson | Copernicus asks for a credit line | none | add |
| State and tribal fish agencies, Trout Unlimited / EBTJV, StreamNet | trout labels and outlines | none recorded (PFBC: credit required, and given) | in each label, not in the credit line | record the terms |
| TNC Natural Flows, PRISM, NIFC, CAL FIRE, USGS, USFS, EPA, NOAA charts, Census | flows, air temperature, fires, lakes | public or credit-only; NOAA's agreement quoted in the popup | credit line or popup | fine |

Also: the home ZIP codes are printed on every reach's access line (your choice of 18 November). The curated falls
files have no column for a source's terms or consent, which is how the terms came to be read after publishing.

### 2.14 Claims in the docs that the data does not bear out

- "Fish 60+ up on every map" and "1,196 new reaches" for the lake routing (README, log L3173): true of the reach
  tables, not the map (already corrected in the log's last entries, not where the claims stand).
- "0 sudden flow drops in all 12 areas" (log L2346, L3109): another script the same day listed seven (L2913-2917).
  On the drawn maps I count 269 sudden changes.
- Falls found: "839 of 1,600" and the README's per-area table count raw detector hits; on what the map shows it is
  44-76 % per area (table T6).
- "Approximate drive times are flagged" (`README.md:602`): the flag is never shown. "Walking uses the trail grade"
  (`README.md:579`): it uses the hillside. "Scores don't change" after `run_drainage_refresh.sh` (`README.md:37-39`):
  it reruns the flow step.
- The Lakes layer is "off at start" (`README.md:849`): it is on. `05d_lakes.py` runs "after the drainages and flow"
  (`README.md:853`): it runs first. Idaho's closures "aren't covered" (`README.md:569-572`): they are fetched.
- "628 MB of Pages' 1 GB" (memory, log): it is 628 MiB, which is 658 MB; the same commit is logged as 577 MB and
  605 MB in different places.
- Jackson's water-temperature fit is described as having no skill (`README.md:727`) and as having skill
  (`README.md:785`); the fit file says skill.
- "Strahler order" on the map: an estimate from drainage on 9,122 reaches (2.3).
- Memory, "dry creeks": "0 of 221 wet gauged creeks lowered" holds on the reach tables; one wet gauged creek was
  still drawn dry until tonight, through a line the map step added.

The helpers' full lists: `audit/work/docs_readme.md` (14 wrong statements, 18 stale, 20 contradictions) and
`audit/work/docs_log.md` (22 revised claims, 39 open items).

### 2.15 Outside deadlines

- USGS WaterServices (ends 2027-02-22): no script calls it; both gauge callers use `api.waterdata.usgs.gov`
  (checked by search over `scripts/`, `data/*.py` and `data/stream_burning/`).
- The Water Quality Portal's older interface behind the water-temperature fits (2.6): check and move.
- `api.waterdata.usgs.gov/statistics/v0` is a beta (`11_context.py:501`); a failed request reads "no history" on the
  map.
- TNC's October 2026 flows: LA's flow step still reports 2026 on three of four months.
- NHD was frozen in 2023 and is being replaced by 3DHP; the staged download path may go.
- The GitHub token for publishing expires (yours to renew).
