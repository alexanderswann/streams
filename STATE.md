# State of the stream maps

How things are now. Edit this file in place, in the same commit as the change it describes: the rows a change
touches, its open items, and one ledger row when it is published. That commit's message is the record of the change:
what changed, why, and what was measured (longer results go in a note the message names). The history up to
2026-11-23 is in `MULTI_AREA_LOG.md` (frozen) and in git. Units: the data and code are metric, the maps show feet,
miles, square miles, acres and °F (`scripts/units.py`); this file gives both.

## 1. Live now

- **Repository:** github.com/alexanderswann/streams (public since 2026-11-22). The code is on `main`; the site is
  in `docs/` on `gh-pages`, served at alexanderswann.github.io/streams/. Local clones: the project
  (`/Users/mac/Fishing`, `main` tracking `origin/main`) and `publish/streams-site` (`gh-pages`; the live copy is its
  `docs/`). Until 2026-11-23 the maps lived in the `streams/` folder of the personal site repository
  (`publish/alexanderswann.github.io`), which no longer holds them (removed 2026-11-23 02:26).
- **Site:** `gh-pages` at `9acd24d` (2026-11-23 09:04 ET), 12 maps. The four Adirondack maps are built and
  published but listed nowhere (`hidden=True` in `scripts/config.py`).
- **Built from:** `70a8d76`: main as of 2026-11-23 08:02. That is `dd31f7c` (the night's installs: #1 `ee00f41`, #2
  `f71709a`, #4 `a37db23`, #5 `6e0898c`; then #6 `a9919eb`, `491aeba`, `f24e043`, `152b561`, `dd31f7c`; with `f18342c`
  and `8321c1d`), the six fixes installed at 06:09 (`b283368`, `6affd7e`, `b3411bf`, `3b97251`, `94ffe0a`, `83e9b26`;
  all 12 maps rebuilt from the drops, published 07:47 as `762269f`) and the pond-outlet floor `70a8d76` (the 10 maps it
  changes rebuilt from the drops; LA and the Smokies are the 07:47 build's, which it doesn't change).
- **Site size:** 693 MB of GitHub Pages' 1 GB (`du -sh publish/streams-site/docs`, 2026-11-23 09:20).

### Publish ledger (newest first; the builds before 2026-11-23 ran from the working tree, so their code commit is
the one nearest in time)

| Published (ET) | Site | Code | What changed on the maps |
|---|---|---|---|
| 2026-11-23 09:04 | `9acd24d` | `70a8d76` | a pond's outlet creek is drawn whichever way the routing splits its link in the pond: 17 mi more, 43 lake outlets more, none fewer (Howard Pond, a 4.7 ac pond in the High Peaks and the Dime Creek pond back; Dunham Pond Brook back unnamed) |
| 2026-11-23 07:47 | `762269f` | `83e9b26` | a river weaving along a map's edge goes in again where the river stays inside (Minister Creek); water carried across a box edge starts its line where it comes in (Still Brook, a Smokies creek); the West Branch California Aqueduct's floor lines gone; the streams layer's label names the size floor; a break below a lake takes the biggest of the creeks ending equally near it |
| 2026-11-23 06:02 | `9f6e867` | `dd31f7c` | water across swamps follows NHD's channel lines (#6); Blue Ridge Parkway closures by their Status, laid mile by mile; wild brook trout water sized for brook trout; a borrowed flow estimate outside LA never reads drier than no estimate; more swimming holes and falls (OSM creek pools, Overture, Google) and named ponds |
| 2026-11-23 02:19 | `9f778f8` | `6e0898c` | approach times for mid-July (`f18342c`); downloads fall back to the last good copy (`8321c1d`); creeks cut 650 ft below lakes (#1); summer flow never drier than NHD's class, trout records read as flowing (#2); rivers from outside carry their whole drainage, and creeks are drawn down to 0.1 sq mi where NHD maps them year-round or names them (#4); lakes' second outlets drawn as side channels (#5) |
| 2026-11-22 20:42-21:09 | `gh-pages` `d9d18d1`-`7782773` | `194bb83` | nothing: the same maps moved to their own repository, github.com/alexanderswann/streams |
| 2026-11-22 13:31 | `c178411` (old repository) | `945d3ac`, `3747e44` | an empty trout survey no longer halves a reach; a burn of unmapped severity marks nothing down; phone pages: credits on one line, my-location button |
| 2026-11-22 07:59 | `6c72e2e` | `f337bfb`, `e5fe7b2` | a lake ends at NHD's outlet and its water goes on from the top of its way out (Seventh Lake and 70 more lakes) |
| 2026-11-22 02:52 | `4315299` | `52c2139` | the Adirondack lake term counts only within 650 ft below a lake |
| 2026-11-21 23:47 | `d16a885` | `8bdf945` | reaches cut at lake shores; side channels; the stretch below a dam drawn as creek |
| 2026-11-21 22:16 | `6875118` | `40c2aa7` | lakes drain along NHD's lines; a river line below each outlet; the size floor counts carried water |

## 2. Areas

Twelve maps, each a set of boxes ("ranges") with its own UTM zone and drive-time home point (`scripts/config.py`):
`la`, `jackson`, `n_georgia`, `central_vt`, `ne_ct`, `lexington_va`, `se_pa`, `smokies`, `adk_high_peaks`,
`adk_northwest`, `adk_southwest`, `adk_southeast`. Adding one is still hand work (audit finding 9; the general-rules
plan in §5).

`se_pa` reaches the Delaware River since 2026-11-23 (the user: "expand the PA map south and east to the delaware
river", "everything here west of the delaware river", "all the way up"): everything west of the river from Wilmington
Manor and Claymont up past Chester and Philadelphia to Bristol, Morrisville and Washington Crossing, in four boxes
(`brandywine` reaches 4,390.5 km N; new `claymont` and `pennypack_neshaminy`). The boxes reach into New Jersey, and
the map is cut at the state line in the river, as central Vermont's is at the New York line in Lake Champlain.

## 3. Rules in force

One row per rule that decides what the maps show. "Measured on" is where the rule's effect was checked; "all 12"
means it was measured on every map before it went in.

### Routing (`03_hydrology.py`, `03b_stitch.py`, `crossbox.py`)

| Rule | Value | Where | Since |
|---|---|---|---|
| A channel starts where this much drains to a cell | 0.25 km² (0.10 sq mi) | `scripts/config.py:12` | |
| A pond is a lake for routing only with this much level water | 2 ha (4.9 acres) | `scripts/03b_stitch.py:57` | |
| A lake drains to its outlet along NHD's lines through it | a step off the lines costs 5 along them | `scripts/03b_stitch.py:382` | `dd639bf` |
| A lake ends at NHD's outflow line; its water goes back in at the first cell of its way out | outflow line within 300 m of where the terrain takes the water on | `scripts/03b_stitch.py:59`, `scripts/crossbox.py:289` | `f337bfb` |
| A dead end on the seam between two boxes is mended | gathering 0.25 km² or more | `scripts/03b_stitch.py:293` | |
| A river entering from outside every box brings its whole drainage: each NHDPlus main-path line crossing the outer edge flowing in, at any size, brings NHDPlus's total at its lower end, less what the routing and the edge links already have there; minor arms of split rivers left out; the same water counts once, on NHDPlus's network | water the terrain sends straight back out goes in further down the mapped river, within 15 km (9.3 mi) | `scripts/crossbox.py:33` | `a37db23` |
| Such a river starts as a reach of its own where its water goes in: the terrain path to the first stream line, stopping at a lake whose water leaves the map | | `scripts/crossbox.py:852` | `a37db23` |
| Basins draining off an edge or into a lake are carried | from 0.1 km² | `scripts/crossbox.py:32` | |
| A lake's second outlet is drawn as a side channel, with no water added: an outflow line NHD maps as a channel (StreamRiver, or a path through water into one, with no connector, canal or pipeline first) that the terrain takes the water on down within 300 m, whose path stays on NHD's line for 200 m, and that leads neither back into its lake nor up into a lake standing higher | 0.5 m (1.6 ft) higher | `scripts/03b_stitch.py:67`, `scripts/03b_stitch.py:68` | `6e0898c` |
| Water across a filled flat (a swamp, wetland or valley flat the fill levelled) follows NHD HR's channel lines (StreamRiver, ArtificialPath, Connector; named ones first) to its outlet, and out over a low rim only where the water then stays on that line; the rest of the flat goes the shortest way to a walked line within 100 m, else as pysheds' resolve_flats sends it | a filled flat: 10 cells or more raised 5 cm or more, half the flat at least; a rim of 0.5 m (1.6 ft) at most, crossed within 200 m | `scripts/flatlines.py:38`, `scripts/flatlines.py:43`, `scripts/flatlines.py:630` | `a9919eb` |
| A river from outside whose terrain path leaves over the map's edge within 300 m of the river, while NHD's lines of it stay inside, goes in again at the first point down the mapped river whose path stays in the map for 200 m, runs along NHD's lines and meets no water already taken in | 50 m steps | `scripts/crossbox.py:33` | `6affd7e` |

### Reaches (`05_score.py`, `flowlib.py`)

| Rule | Value | Where | Since |
|---|---|---|---|
| A reach is drawn when it drains this much, counting the water it carries from upstream boxes and lakes | 1 km² (0.39 sq mi) | `scripts/05_score.py:13` | `80b42e8` |
| ... and down to this where NHD maps the link's own line perennial or names it (a name or year-round class it shares with a river 10 times its size alongside is the river's; canals, ditches, pipelines and lines named after one don't count, a name being a built channel's where NHD gives it a built line of the box and its stream lines carry under a tenth of its length); a creek kept this way runs on down to the next kept line (the user's choice, 2026-11-22) | 0.25 km² (0.1 sq mi) | `scripts/config.py:12`, `scripts/05_score.py:132`, `scripts/05_score.py:163`, `scripts/05_score.py:162` | `a37db23`; the canal share `94ffe0a` |
| A link that starts in a lake of the lakes layer (any size) and isn't kept whole votes again on each part, so a pond's outlet creek doesn't depend on where the routing splits the link in the pond: its first stretch along NHD's path through the lake, where the lake isn't one NHD maps as intermittent and NHD maps a creek below it, and its creek from where it leaves the lake | the path within 20 m, half the stretch in the lake; half the rest of the link within 60 m of an NHD line | `scripts/05_score.py:187`, `scripts/05_score.py:233` | `70a8d76` |
| A link is cut at a lake shore (creek or lake, never both) | where 50 m or more lies on each side | `scripts/flowlib.py:187` | `d06b50b` |
| A side channel of a big river takes the river's values | river 50 km² or more, 10x the channel, within 250 m, 60 % alongside | `scripts/05_score.py:128` | `d06b50b` |
| A creek is cut 200 m (650 ft) below a lake, along the channel the lake's water takes, so the outlet's warmth is in that stretch's own score. The cut is for water temperature only: both pieces keep the line's gradient, NHD class, flow evidence, gauge record, trout records and designations (the user's choice, 2026-11-22) | where the lake term there is 0.5 or more and neither piece is under 50 m | `scripts/flowlib.py:431` | `ee00f41` |
| A lake's second outlet is kept from the lake down to the first link the map keeps on its own, as a side channel of the creek the lake's main outlet starts, and takes that creek's drainage | within 5 km (3.1 mi) | `scripts/05_score.py:246` | `6e0898c` |
| Water carried across an edge two boxes share starts its line where it comes in, as a river from outside does, where the box it enters has no line at that cell | edge links of 0.25 km² or more | `scripts/crossbox.py:852` | `3b97251` |
| A reach a city has buried isn't drawn: no name and no NHD class once the reaches are named, NLCD 2021 impervious cover along it (3 x 3 cells every 20 m) at the value or more, an open OpenStreetMap waterway (not tagged as a tunnel, culvert, covered or underground) within 60 m of under 20 % of it, no NHD line but a pipeline or conduit within 60 m of half of it, no designated trout water within 30 m and no trout record within 300 m whose nearest reach it is; a drop candidate on it goes too, and the steps after it go on along it as before (buried_reaches.gpkg: 05b_flow.py reads it back for the way down to the first modelled reach and the segment it matches, and a path below a dam that runs into it isn't drawn) (the user's choice, "Option A", 2026-11-24) | 40 % | `scripts/buried.py:45`, `scripts/05_score.py:1200`, `scripts/05b_flow.py:63`, `scripts/06_map.py:162`; downloads `scripts/02h_buried_inputs.py` (`run_mid.sh`, before 05_score) | (this commit) |

### Summer flow (`02b_download_flow.py`, `05b_flow.py`, `flowlib.py`)

| Rule | Value | Where | Since |
|---|---|---|---|
| LA: the class comes from The Nature Conservancy's natural-flow model; elsewhere from NHDPlus's mean flow times a yearly index | "kept flowing" from 0.1 cfs in the dry months | `scripts/flowlib.py:529` | |
| Waterbodies too small to control a creek's base flow | under 8 ha (20 acres) | `scripts/flowlib.py:8` | |
| A gauge's record stands for its creek | 4 km (2.5 mi) along its line; gauges within 500 m are one site | `scripts/flowlib.py:621` | |
| NHD's class is the floor of a borrowed estimate (one scaled from another creek, down a way through a lake, from an off-map lake's line, or one that leaves out a dam's water), and a creek NHD maps perennial reads year-round; only a USGS gauge's record, on the creek or below a diversion, goes lower | perennial 1.0, intermittent 0.35, no class 0.3, no NHD line 0.15, ephemeral 0.05 | `scripts/05b_flow.py:549` | `f71709a` |
| A trout record (trout found since 2016, no later survey finding none) means at least "usually flows" | water 0.69 | `scripts/scoring.py:180` | `f71709a` |
| LA and Jackson (Sentinel-2 greenness): a creek the model rates flowing reads seasonal where its typical summer low is under 0.45 cfs and its channel is bare in late summer, judged per creek between confluences, and only where none of the creek shows water (trout, a dam or tailwater, NHD perennial, open water, a green channel) | bare: under 0.45 in a median summer and 0.5 in every summer; green: 0.67; one creek: reaches within 0.8 of each other's drainage | `scripts/scoring.py:169`, `scripts/scoring.py:174`, `scripts/scoring.py:178` | `f71709a` |
| A reach with no estimate takes the median water of the area's reaches with its NHD label and a drainage within 2 times its own (then 4, then any size, while fewer than 20 match), never below NHD's class | | `scripts/scoring.py:406` | `f71709a` |
| Outside California a popup's "year-round" or "usually flows" carries NHD's doubt where NHD calls the line intermittent or ephemeral or has none | | `scripts/06_map.py:654` | `f71709a` |
| A lake's second outlet takes the water of the creek its lake's main outlet starts where that reads it at least as wet, NHD's class where NHD maps it intermittent or ephemeral, and never reads wetter than the creek it runs into (unless that is on its lake's own river); a trout record on it stands | | `scripts/scoring.py:222` | `6e0898c` |
| Outside LA, where the flow model can't see creeks dry up, a borrowed estimate reads no drier than the larger of NHD's class and what like creeks read; where NHD has no line and it still reads mostly dry, it reads as NHD labels it. In LA NHD's class stays the floor | | `scripts/scoring.py:429` | `152b561` |

### Water temperature (`watertemp.py`)

| Rule | Value | Where | Since |
|---|---|---|---|
| Each area fits summer water temperature to August air (PRISM), elevation and stream size from its measured sites; an area that stops at a state line, from the sites inside its states (New Jersey's coastal-plain streams had warmed southeastern Pennsylvania's fit) | at least 25 sites; must beat "every creek is the average" by 10 % (leave-one-out) | `scripts/watertemp.py:85`, `scripts/watertemp.py:218`, `scripts/watertemp.py:191` | the state-line sites: se_pa expansion |
| Three Adirondack maps add a lake term: the share of a creek's water that has just left a lake (carried past dams and ponds, and what runs on out of a lake along the routing before 03b's outlet) | counts within 200 m (650 ft) below a lake; full up to 50 km², none from 500 km² | `scripts/flowlib.py:315`, `scripts/flowlib.py:371`, `scripts/watertemp.py:208` | `52c2139`, `ee00f41` |
| Tailwaters below dams that release cold water take the elevation part of the thermal term in full | listed per area | `scripts/scoring.py:209` | |
| Full temperature credit up to, none from | 20 °C (68 °F), 25 °C (77 °F) | `scripts/scoring.py:186` | |

### Fish score (`scoring.py`)

| Rule | Value | Where | Since |
|---|---|---|---|
| The score | 100 x water x (0.30 size + 0.30 thermal + 0.15 gradient + 0.25 remoteness) x burn x trout x heat x channel, capped at 100 | `scripts/scoring.py:3` | |
| Trout | x1.2 with trout found in the last 10 years (no later survey finding none) or on a designated trout water or wild trout patch; a survey that found none marks nothing down | `scripts/scoring.py:339` | `945d3ac` |
| Burn | fire 2 years ago or less x0.4, 3-5 x0.7, 6-9 x0.9, scaled by the mapped soil burn severity; unmapped severity marks nothing down | `scripts/scoring.py:144` | `945d3ac` |
| Heat | from 29 °C (84 °F) of August air down to x0.2 at 30.5 °C (87 °F); never where trout are known or below a dam | `scripts/scoring.py:165` | |
| Built channel by name | x0.2, never where trout are recorded | `scripts/scoring.py:352` | |
| A minute ridden on the approach counts as this much remoteness (user's choice) | 2 minutes | `scripts/scoring.py:159` | |
| Wild brook trout water is sized for brook trout: its drainage counts six times over, on a reach a wild brook trout designation covers or where a survey found wild brook trout in the last 10 years with no later survey finding none (the user's choice, audit decision 5d) | x6: credit from 0.06 sq mi, full from 3.2 sq mi | `scripts/scoring.py:164`, `scripts/scoring.py:329` | `f24e043` |

### Access (`07_road_closures.py`, `08_hike.py`, `09_drive.py`)

| Rule | Value | Where | Since |
|---|---|---|---|
| Approach times are for mid-July: a closure counts only if, by its own dates and words, it will still be in force on the coming 15 July (winter gates, night work and lapsed closures don't); a counted closure cuts only the road it runs along; one the router can't lay on its road cuts nothing; today's other closures are a dated note | | `scripts/07_road_closures.py:62`, `scripts/roadclosures.py:15` | `f18342c` |
| Fire roads are ridden; a route on a doubtful one is flagged | flagged after 1 minute on it | `scripts/08_hike.py:42` | |
| Walking: trails up to 15 % grade; along a channel and off trail at a share of trail speed | 0.45 and 0.30 | `scripts/08_hike.py:37`, `scripts/08_hike.py:38` | |
| Biking | 18 km/h (11 mph) on the flat; dirt x0.7, singletrack x0.5; up to 25 % grade | `scripts/08_hike.py:40` | |
| Driving: speed by road class; winding roads slower; a trailhead joins a road within 400 m | winding x0.75 | `scripts/09_drive.py:19`, `scripts/09_drive.py:22` | |
| Blue Ridge Parkway: a section closes only when the park's Status column says Closed; in an open section, the milepost ranges its notes call closed; each mile is laid on the Parkway's own OSM lines between the park's milepost points, and a closure with no milepost range closes no road | | `scripts/07_road_closures.py` (`blri_roads`) | `491aeba` |

### Lakes, falls, the map, downloads

| Rule | Value | Where | Since |
|---|---|---|---|
| Lakes kept by size, per area (a table keyed by area name: audit finding 9) | 0.5-2 ha | `scripts/05d_lakes.py:44` | |
| A lake's outline from lidar where its surface is level | within 0.3 m; lakes over 600 ha keep NHD's outline | `scripts/05d_lakes.py:57`, `scripts/05d_lakes.py:444` | |
| A drop is a candidate fall | slope 0.25 or more, 8 m (26 ft) or more, on 1 km² or more | `scripts/04_knickpoints.py:16`, `scripts/04_knickpoints.py:17` | |
| Known falls merge OSM, NHD, GNIS, Wikidata, CDFW and the curated lists | | `scripts/02f_known_falls.py:49` | |
| An area that stops at a state line keeps what lies in its states (central Vermont: VT; southeastern Pennsylvania: PA, DE and MD, so not New Jersey across the Delaware); a reach or drop goes by its middle point, except a line lying in the water of the river that is the line (the Delaware above Trenton), kept whole: NHD's river area near the line, since TIGER's line strays up to about 250 m from NHD's centre line; the river's own known falls show with it (Scudders Falls and the Falls of the Delaware at Trenton, on the New Jersey side of the line); no creek profile past the line (New Jersey's creeks in southeastern Pennsylvania's boxes, New York's in central Vermont's) | half its length in NHD's river area within 400 m (1,300 ft) of the line; a falls within 25 m (80 ft) of that water | `scripts/areaclip.py:32`, `scripts/areaclip.py:77`, `scripts/areaclip.py:112`, `scripts/areaclip.py:133`, `scripts/config.py:225`; the map step's lines drawn through breaks go by the same test (`scripts/06_map.py:142`); the falls, `scripts/05_score.py:931`; the profiles, `scripts/creekprofiles.py:56` | se_pa expansion |
| Swimming holes and falls also from OSM creek pools and unnamed swimming spots on a creek, Overture Maps places (strictly: a waterfall-category place named falls, cascade or waterfall within 150 m of an NHD creek and not by a lake, a swimming hole within 250 m of a creek; only where no other source has a fall within 1 km, a swimming hole within 300 m, or a fall of that name within 25 km), and Google Maps listings looked up by hand | | `scripts/02f_known_falls.py:400`, `scripts/02f_known_falls.py:408` | `dd31f7c` |
| A named NHD pond is kept under any map's smallest lake size; so are CT DEEP's stocked trout lakes, as PFBC's and NCWRC's are | 0.1 ha (a quarter acre) or more | `scripts/05d_lakes.py:55` | `dd31f7c` |
| The maps open with streams, drainages, the long trail, terrain shading, place and road labels and lakes; everything else off | | | 2026-11-20 |
| A download times out, is retried, and falls back to the last good copy with a dated note; a failed download step is retried once, then stops its area | 15 s to connect; a host out after 3 failures in a row | `scripts/netfetch.py:45`, `scripts/netfetch.py:47` | `8321c1d` |
| Every download falls back offline: an empty answer is kept as a last good copy too (02d's USFS closed roads and trails, missing in some box on 9 of the 12 maps; 05_score's OSM names; 05d's GBIF table); 05d's PAD-US copy, whose box follows the lakes, is kept under a name of its own and cut to the box asked; a lidar window every survey has a gap in is remembered, so no lidar tile is read twice | | `scripts/02d_trails.py:62`, `scripts/geomatch.py:17`, `scripts/lakelidar.py:121`, `scripts/netfetch.py:337` | 2026-11-23 (no rebuild needed) |
| A layer read from a saved copy is named in the legends' one line with the copy's day ("⚠ As of Nov 23: fires, land and iNaturalist", one line on a phone; the 2D and 3D legends, and on the phone map under each area for its gauges, closures and trout records); the gauges' label says "as of" for "live". Found from the "(as of ...)" the steps write into the source wording; lakes, trails, roads and falls carry none and keep their NOTE in the log | | `scripts/06_map.py:1545` | 2026-11-24 |
| A break below a lake is drawn with the values of the creek that carries the most water among those that end equally near its start | within 1 m | `scripts/06_map.py` (`lake_creek`) | `83e9b26` (not yet built) |
| The map step still redraws the streams after the steps that compute them (clips at lake shores, draws through breaks, raises orders) | tables and map differ by about 5,500 mi | `scripts/06_map.py` | audit finding 6; map-step-repairs |

## 4. Sources and licences

| Source | Used for | Terms | Credited |
|---|---|---|---|
| USGS 3DEP, NHD, NHDPlus, GNIS; USGS gauges | terrain, streams, names, flows, drainage checks | public domain | |
| OpenStreetMap | trails, roads, parking, falls, long trail, waterways (where a city has buried its creeks) | ODbL | attribution line |
| NLCD 2021 impervious cover (USGS, MRLC) | where a city has buried its creeks (`scripts/buried.py`) | public domain | |
| USGS National Digital Trails, USFS | trails, roads, trailheads | public domain | attribution line |
| The Nature Conservancy flow model | LA summer flow | | |
| PRISM | August air temperature | | |
| Sentinel-2 | channel greenness (LA) | | due: added with the next `06_map.py` change (user, 2026-11-22) |
| State fish agencies (CDFW, GA DNR, NCWRC, TWRA, VT F&W, CT DEEP, VA DWR, PFBC, NYSDEC and others named in each record), EBTJV / Trout Unlimited, iNaturalist, GBIF | trout records and designations | PFBC asks for credit | in each record's text |
| data.ny.gov (OPEN-NY) | New York lake and stocking records | free reuse | in text |
| NYSDEC ArcGIS layers | Adirondack trout waters, trout labels, stocking, DEC lands | no distribution outside DEC without permission | in text; the user asks DEC for permission and the pages stay up (2026-11-22) |
| NOAA ENC charts | Lake Champlain depths | redistribution with origin shown | in popups |
| Road closure feeds (`scripts/07_road_closures.py:835`) | closures, dated note | | tooltip |
| gawaterfalls.com; about 85 falls from other guide sites | known falls | no licence stated; kept as is (user, 2026-11-22) | line + popup |
| World Waterfall Database, nnywaterfalls.com | known falls | full use allowed (owners, per the user, 2026-11-22) | popup |
| Google Maps, Apple Maps | single points looked up by hand: Triple Buckets (Apple), 17 falls and swimming holes (Google, `data/known_falls_curated.csv`, since `dd31f7c`) | allowed: academic use (user, 2026-11-22) | popup |
| Overture Maps places (Overture Maps Foundation) | falls and swimming holes, by a strict rule (§3) | CDLA-Permissive-2.0; Foursquare's places Apache-2.0 | credits, with Foursquare's notice, on maps that show its places (since `dd31f7c`) |

## 5. Open items

| Item | Found | Owner | Needs | State |
|---|---|---|---|---|
| The map step draws what the pipeline computed (#7, phase 2) | audit finding 6 | map-step-repairs | the user's OK on its trial numbers | a 12-map trial on `70a8d76` (patch `0bdc85fa`), numbers about 10:15; then the user's OK |
| Small wrong labels: "order 7" on 520 lines, 3,601 dead lake links, 142 "-0 min" | audit finding 14 | map-step-repairs (in #7, or a phase 3) | | planned |
| Named creeks the floor's vote misses where the terrain's path runs 40-85 m off NHD's line, read by their name along the link; with it a name whose generic term is a ditch's or canal's reads as a canal's (The Zanja, Magazine Ditch, Main Ditch: 2.0 mi intended) | edges-and-floor | edges-and-floor | | patch `7a0556c9` on `70a8d76`; scratch build from `pub_9acd24d`, then prehandoff |
| Reach names and NHD classes read along the reach too, with the same big-river guards: Dunham Pond Brook's outlet reach was named and year-round until #6 (`9f6e867`, 06:02), not drawn 06:02-09:04, and is back unnamed and "usually flows" since `9acd24d` | `70a8d76` | edges-and-floor | | after the name test |
| Two unnamed creeks in the Fivemile River's drainage (NE Connecticut, 0.43 and 0.79 km²) read "seasonal" in place of "usually flows" since `70a8d76`: the borrowed-estimate floor takes what like unmapped creeks mostly read, and the new pond outlets tip that majority | `70a8d76` | flow-class | | fixed by typical-own `3934936c`, with #7 |
| Lake outlets not drawn since #6: the northern Star Mountain Pond's (High Peaks; its water forms no link in the new routing) and Bautista Creek below Hog Lake (LA; its link starts on an unmapped creek above the lake) | `a9919eb` | stream-burning, edges-and-floor | | listed exceptions |
| 79 drawn LA pieces (46 mi) on creeks NHD doesn't map read "mostly dry" where the maps said "NHD unmapped" before 2026-11-22: `05b_flow.py` must record which borrowed estimates came through a lake, another box or an off-map lake | `152b561` | flow-class | | with the next `05b_flow.py` rerun (#7) |
| Rice's Falls, four lake outlets and North Teton (#6's follow-ups) | stream-burning | stream-burning | | trial |
| The 650 ft cut below lakes for the five second-outlet lines | second-outlets | second-outlets | | patch ready; tested on #7's build |
| Popups at confluences list the creek's own trout label first (label order only; no score change) | tributaries-labeled-with | tributaries-labeled-with | user chose this (2026-11-22) | patch rebased on `83e9b26`; rides with #7 |
| Rules written for one place replaced by rules from the data, so a new area just works; with them a publish gate that refuses failed or mixed builds, and smaller pages | audit findings 9, 10, 12 | general-rules | user said yes (2026-11-22) | planned, one install at a time after #7 |
| Sentinel-2 credit line | audit finding 11 | | user, 2026-11-22 | with the next `06_map.py` change |
| "CA State Parks" on 178 New York trail pieces | audit finding 14 | general-rules | | planned (06_map) |
| Burn severity for the 2017-2022 fires the Forest Service layer no longer holds | score-evidence | none | the user's call | open |
| The cfs figure runs about 3x high on small Vermont creeks and 7x in Tallulah Gorge | audit finding 2 | none | | open |
| NYSDEC permission for its layers on the four Adirondack maps (hidden; pages stay up) | audit finding 11 | the overview drafts, the user sends | | open |
| The smallest lake to show (with counts); hosting beyond smaller pages; national gap-fillers | general-rules | the user | | later |
| Pieces a buried reach leaves touching no other drawn line (LA 68 mi, se_pa and north Georgia 3-4 mi each, measured on the live maps): lines just under 40 % impervious, and outfalls where a creek comes back to the surface; one that meets the same test at 25 % could go too | buried creeks | none | the user's call | open |
| Philadelphia's combined sewers take dry-weather flow to the treatment plants: summer flow of creeks below big sewersheds (Frankford Creek below the Wingohocking) is likely too high | buried creeks | none | | open |
| USGS WaterServices ends 2027-02-22 | | done: `11_context.py` and `02b` use api.waterdata.usgs.gov | | watch |

## 6. Standing checks (before every publish)

- `audit/scripts/run_all.sh <label> <maps folder> [tables folder]` on the live site (`publish/streams-site/docs`,
  the default) and on the new build (about 17 minutes each, completeness included); compare the two labels' tables.
  Labels made before the move (`live_c178411` and older) stay valid: the maps are the same files. For a routing change also compare
  `area_vs_gauges.csv` and `area_vs_nhdplus.csv` between them: a drawn-line check misses a river that keeps its line
  but loses drainage.
- `data/stream_burning/checks/` (`drawn_cmp.py`: miles new and gone; `drainage_moves.py`; `outlet_gaps.py`; ...).
- After a network drop: `grep -E "FAILED|RETRY|\(as of" data/late_*.log`, and look for a step running far past its
  usual time.
- Site size under 1 GB (`du -sh publish/streams-site/docs`; GitHub Pages' limit for a published site).
- Look at the rendered map for anything visual, at phone size too.

## 7. Building and publishing

- **Drivers** (`scripts/`, logs in `data/<driver>_<area>.log`): `run_base.sh` (DEM, NHD and OSM, hydrology, drops),
  `run_mid.sh` (reach scoring, flow, drainages, lakes, trails, access roads), `run_late.sh` (closures, approach
  times, sun, drive times, context, water temperature, the map, profiles), `run_rebuild_a.sh` (03 and 03b, the drops,
  then mid and late; `SKIP_03=1` starts at 03b, `SKIP_03B=1` at the drops), `run_drainage_refresh.sh`.
- **Where a change rebuilds from:** routing: 03 / 03b; reaches and the size floor: the drops (`SKIP_03B=1`); flow:
  05b; access: 07; score and labels: 06_map.
- **Trial builds** go in a scratch root (`data/stream_burning/harness/setup_clone.sh`, `chain_from04.sh`,
  `run_chain.sh`; `data/stream_burning/README.md`), launched by their literal scratchpad path. The project drivers
  write to the project: never use them for a trial.
- **The hydrology lock:** only one conditioning step (03, 03b) runs at a time across chains: `run_base.sh` and
  `run_rebuild_a.sh` take `data/.hydro.lock` through `scripts/hydrolock.sh`, which lets it go however the driver ends;
  after a `kill -9` the next chain takes it over once that driver and its step are gone (`b283368`).
- **The machine** (12 cores, 16 GB): one project rebuild (two streams) plus at most one or two scratch chains; check
  `sysctl vm.swapusage` first.
- **Installing:** a patch on main as it is then, by the session that wrote it, on the overview session's word; one
  commit per change, with this file's rows in it.
- **Publishing:** `scripts/publish_site.sh push` (since `194bb83`) commits the maps to `gh-pages` in
  `publish/streams-site` and pushes them. It refuses while a build runs (any `06_map.py` or `12_profiles.py` process
  counts). Never publish around it. Push `main` after each install commit, so the public code matches the maps.
- **Learned on the move (2026-11-22):** pushing a `gh-pages` branch switched GitHub Pages on by itself, and the new
  repository's site at once took over alexanderswann.github.io/streams/, ahead of the personal site's `streams/`
  folder. Anything pushed to `gh-pages` is live.
