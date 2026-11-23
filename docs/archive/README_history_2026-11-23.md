# README.md history, moved out on 2026-11-23

These are the passages moved out of `README.md` on 2026-11-23, when it was trimmed: how each rule was found (dated
cases, creek anecdotes, measurements, before and after counts), the stream-temperature study, the lakes source audit
and the surveys that could not be used, and the publish story. They are kept word for word from `README.md` at commit
46ca355 (the line numbers in the headings are that file's), and they may be out of date: the rules in force are in
`STATE.md` and `README.md`, the dated record in `MULTI_AREA_LOG.md` and git. The last sections are the write-ups
committed that night, before the trim, word for word from the commit each heading names.

## One map for all areas (lines 24-57): the website, as published until 2026-11-22

### Lines 45-57
- **The website** (`scripts/publish_site.sh`): copies the map of all areas and every area's maps into
`publish/alexanderswann.github.io/streams/` (a local copy of the GitHub Pages site; `streams/` was 605 MB on
2026-11-20, and GitHub Pages refuses a site over 1 GB) and commits
there; `scripts/publish_site.sh push` also pushes, which puts it live at
`https://alexanderswann.github.io/streams/` (published 2026-11-19; the login is a token for that one repository
in the Mac's keychain). A push goes up area by area, through a temporary branch `publish-upload`, then `master`
once, so the site builds once: in a single push git sends most files whole, 85–134 MB for a full republish instead
of a few MB (2026-11-20). Afterwards it rebuilds the phone copies (`14_portable.py`, `phone_sync.sh`) from the same
maps. It stops while a build is running; with `push now` (maps just built and checked), test runs in a session's
scratchpad folder don't count, unless they run a step that writes published files. It adds the `streams/` folder
and nothing else: the site already
there is not changed, and the script stops if its commit would touch anything outside `streams/`. The maps
show the start ZIPs; that was the owner's choice.

## Study areas and folders (lines 59-145)

### Line 68
grown from three boxes to seven on 2026-11-19

### Line 127
(a sleeping Mac froze two downloads)

### Line 130
(2026-11-22, after two drops stalled a 12-map rebuild for 90 and 47 minutes)

### Line 138
(HTTP 429: the USGS Water Data API asked for 35)

## Pipeline, step 3: `03_hydrology.py` + `03b_stitch.py` (lines 176-263)

### Lines 179-180
(Until 2026-11-19 each box was solved alone and no
stream crossed an edge.)

### Lines 183-184
(the Snake below Jackson Lake,
the Raquette below Raquette Pond and Carry Falls)

### Line 190
(found 2026-11-18; LA's dry channels showed it only at reservoirs)

### Line 196
since 2026-11-20: its flat water had drained to the edge along dozens of parallel made-up creeks.

### Lines 202-212
Only the path that gathered the most water used to end at the outlet. The flat water's own
directions let other paths cross the lake and leave it on their own: Pilgrim Creek's ran to Jackson Lake Dam beside
the Snake's outlet, so the line across the lake and over the dam was Pilgrim Creek's, and Palisades Reservoir's
crossing read Trout Creek. They drew 986 km of straight made-up lines across lakes over the 12 maps (now 266 km).
And with no line of its own below the outlet, the lake's water, which `crossbox.py` puts back in below the dam,
landed on the first line it met and was counted along that whole link, a side creek's included: Lower Slide Lake's
1,539 km² on a 2.7 km creek beside the Gros Ventre, Leigh Lake's on a creek beside String Lake (120 such creeks over
the 12 maps). Measured on all 12 maps before it went in (`data/stream_burning/`): drops, known falls, flow drops and
edge dead ends unchanged or better; lake outlets reading under half of NHDPlus 45 → 39 (26 with 5.'s size floor).
That measurement compared the reaches both builds had and missed the lines that vanished below lake outlets (5.,
the size floor).

### Lines 212-214
The folder also keeps the
experiment this came from, NHD's lines burned into the DEM itself, which is not used: burned everywhere they lost
waterfall-like steps in the mountains, burned on flat ground only they reshuffled braided rivers' arms.

### Lines 215-245
Since 2026-11-22 a lake ends at NHD's outlet, not at the cell where the DEM gathers the most water
(`lake_outlet`). The two were the same place at most lakes, but 300 m or more apart at 77 of the 1,430
the maps carried on (Raquette Lake 9.1 km: the terrain's cell sat at South Inlet's mouth, and `route_lake` sent
the whole lake there). NHD's outlet is where one of its detailed stream lines that starts in the lake leaves the
water. The line is followed for up to 300 m to the first cell the terrain takes the water on from: one whose
own D8 path doesn't lead back into the lake and stays on NHD's line (80 % of its next 200 m within 40 m). The
cells before it (a dam's crest, a sill) are pointed along NHD's line; the lake's last cell on the line is the pit.
A way out that reaches another lake that holds water ends at its first cell. A pipeline or ditch counts only
where the terrain takes the water on down no stream line, and only where a stream line goes on from it within
1 km (the network runs through Palisades Dam and Stark Falls Dam as a pipe; the Los Angeles Aqueduct leaves
Bouquet Reservoir as one too, and took Bouquet Creek's water in a scratch build before the second condition).
With two or three outflow lines (61 lakes) three witnesses are asked in turn. The line NHD names is the river's
own bed (the Beaver River's below Soft Maple Reservoir, beside the unnamed power canal where the terrain spills
the lake). Else the line NHDPlus V2's 1:100,000 flowline leaves the lake by (Lake Mathews has three unnamed ways
out; the terrain spills it north over a dike, NHDPlus and the gauges on Temescal Creek have it on Cajalco Creek).
NHDPlus only chooses among NHD's detailed lines; its own geometry is never where the water goes in. Else the one
nearest the terrain's cell. D8 sends a lake's water down one way out, so the other arm is drawn only where it
gathers a creek's ground of its own. Of the 1,417 lakes ended at NHD's outlet on the 12 maps, 1,355 have one
outflow line the terrain takes on (5 of them a pipe or ditch); NHD's name decides 33, NHDPlus 17, the nearest
line 11. Name and NHDPlus disagree at 3 of the 33 (Castaic Lake, Beaver Pond on the Cedar River, Rock Lake), and
the name stands.
The terrain's cell stays (12 lakes on the 12 maps, each named in the log with the reason) where the terrain takes
the water on down none of NHD's outflow lines within 300 m (Ferris Lake, whose outlet stream the DEM runs back
into the lake for 800 m); where it takes it on only down another line than the one NHD names or NHDPlus leaves by
(Tetreault Pond: the unnamed line dried Snake Meadow Brook in a scratch build); where the line runs off the map;
where NHDPlus's line leaves the lake at the terrain's cell and every outflow line the terrain takes on is 300 m
or more from it (Lens Lake and Livingston Lake, on a divide: NHD names their outflows to one side, NHDPlus and
the terrain have them on Paul Creek); and where NHD's outlet lies on an edge between two boxes. 71 more lakes
have no NHD outflow line at all. All lakes are first ended at the terrain's cell and judged on that one surface,
then moved: judged one by one, a lake whose outflow line runs through the next pond of a chain was held back by
that pond's flat water.

### Lines 246-261
`03b` writes what it decided to `data/derived/<area>/_shared/lake_outlets.json` (outlet cell and first cell of
the way out per box; the lakes left at the terrain's cell with the reason), and `crossbox.py` puts each lake's
water back in at that first cell (6., Past dams) instead of looking for the place again. Until then the two
steps each decided where a lake drains, and where they differed the top of the outlet channel carried none of
the lake's water (Seventh Lake's 43.5 km² went in 555 m from its outlet, in the woods, and the channel to Fifth
Lake wasn't drawn; 192 lakes missed 200 m or more of their way out). `03b` reads NHDPlus's lines for the second
witness, so `run_base.sh` runs `02b_download_flow.py` before it and `run_rebuild_a.sh` fetches them when the file
is missing. Where it is still missing `03b` stops before it writes anything; `NO_NHDPLUS=1` goes on without the
second witness and says so in its last line. Measured on scratch builds of all 12 maps against the published
ones before it went in, and again on the rebuilt maps (`data/stream_burning/README.md`, "Both faults fixed at
the root"): lakes ending 300 m or more from NHD's outlet 77 → 8, put-ins 200 m or more off the way out 192 → 7,
61 lake outlets NHD maps newly drawn, USGS gauges within 10 % of their drainage 417 → 419 of 516 (the Salt River
at the Wyoming line 0.006 → 0.91 of its drainage, the Beaver below Stillwater 0.93 → 1.01), no dead end, no flow
drop. What it costs: the second outlet of 9 lakes is no longer drawn, and 15.7 mi of creek below 19 lakes read
less because the lake's water now leaves by NHD's outlet (Mad Tom Brook below Mill Creek Lake, Potash Brook
below Merino Pond); NHDPlus's coarser line has the old course at some of them.

## Pipeline, step 4: the drops and `02f_known_falls.py` (lines 264-300)

### Lines 275-279
A lake ends its paths at its outlet, so on its own area a river
was no channel for the detectors from the dam down to where 1 km² (10 km² for the second pass) had gathered again:
Rainbow Falls on the Raquette, two steps in the bypassed channel below Rainbow Falls Dam, was found only while a
path leaked out of the reservoir, and went with the leak. Known falls found (any source, 200 m): 1,025 →
1,070 of 2,128 over the 12 maps, none lost.

### Lines 282-283
one
query over a whole area's box hung on both public servers;

### Lines 291-292
GNIS puts
Raven Cliff Falls 1.4 km off

## Pipeline, step 5: `05_score.py` (lines 301-359)

### Lines 306-316
Until 2026-11-21 only its own area counted. A lake ends its paths at its outlet, so the creek below starts again
near nothing, and there was no reach below the outlet until the creek had gathered 1 km² again or met one that
had: 1,092 km of stream line on 1,610 links over the 12 maps, 95% of it along NHD's stream lines, 199 of the links
carrying 100 km² or more (rivers below dams, and rivers where they enter a map: the first kilometre of the Salt,
Greys and Hoback rivers). The map drew most of that line all along: `06_map.py` draws a creek through from a dam
to the next reach with that reach's values, 927 km of it here. What those stretches gained is a reach of their
own, with their own drainage, flow and score; measured on the drawn layer the 12 maps gained 131 mi of line and
lost 149 (`data/stream_burning/README.md`, "On the drawn maps"). Where there had been a reach, a path had leaked
across the lake and left it beside the outlet; when `03b` sent every lake cell to the outlet (3.) those 103 km of
reaches went too (1.5 km of the Oswegatchie, the Raquette between Raquette Lake and Forked Lake, Salmon Lake
Outlet), which is how the gap was found.

### Lines 318-324
pysheds draws one line per link between
confluences, so a link running from a creek into a lake was part creek and part lake water, and `05b_flow.py`'s
half-its-length rule gave the whole link one class: Taggart Creek's last 161 m above Taggart Lake scored as lake,
710 m of Indian Creek above Palisades too. Over the 12 maps 352 km of creek read as lake and
339 km of lake water as creek; with the cut 30 km and 20 km
(what is left lies in stretches under 50 m, which stay with their neighbour; ponds under 8 ha stay streams on
purpose and aren't counted).

### Lines 327-328
(the brooks
dropping into Lake George at 13-20% had read 7-12%)

### Line 339
(Cottonwood Creek's last 1.4 km read "Snake River")

### Lines 341-345
A reach of another name up its main stem makes it that
creek's lower end, with that name (88 reaches); a stem that lies along NHD's own lines of the river
(60% within 150 m, up to its head) makes it a **side channel** (214): it keeps the name, the maps say
"(side channel)", `05b_flow.py` gives it the flow evidence of the river reach beside it and `scoring.py` the river's
size; anything else is the lower end of a creek with no name, and has none (366).

### Lines 352-353
With the detectors scanning from each dam down, Buford Dam had come out as a 49.5 m
"waterfall-like step" 506 m from its mapped point, Carters Dam as a 115 m cascade

## Pipeline, step 6: `05c_drainages.py` and `crossbox.py` (lines 360-427)

### Lines 366-368
Since 2026-11-20; before, the upper
Conasauga was a fork "Jigger Creek", the upper Chestatee "Dicks Creek", upper Piru Creek "Mutau Creek" (33
confluences on 11 maps changed; reaches whose label is their own name 484 -> 1,122).

### Lines 377-378
the DEM stores it as flat 0 m, and paths running on across it joined every creek on the tidal Delaware
into one drainage.

### Lines 381-389
- **Across box edges** (`crossbox.py`): each range's hydrology sees only its own box, so a creek crossing in from
the next box would start again with no drainage area (the Santa Clara River entered the Piru & Castaic box with
none, so Piru Creek won the trunk and the river's own valley was labelled "Castaic Creek"). Every basin that
drains off an edge two boxes share is followed into the neighbour, down its flow directions to where the creek
heads away from the edge, and its area (plus whatever flowed into it from a third box) is added along the creek
before trunks and forks are picked. Where the neighbour's grid ends the creek in a pit on the edge (a road fill
just inside: Bouquet Canyon entering the Piru box), the trace restarts from the lowest nearby cell that drains
away from the edge. The inflow table is cached in `data/derived/<area>/_shared/inflows.json` until a `flowdir.tif`,
the reservoir list or the NHDPlus network changes.

### Line 395
(a second line ran 115 m beside the Hiwassee below Chatuge Dam before)

### Lines 396-419
- **Past dams**: every lake and reservoir ends its D8 paths at its outlet (`03b_stitch.py`; not one whose outlet is
on an edge between two boxes), so the creek below the dam starts again near nothing (since 2026-11-21 on a line of
its own from the outlet down to the first stream it meets, so the lake's water lands on the river below that
junction, not along a side creek's line: see 3.). `crossbox.py` links each lake's dead
ends to the cell where its water goes on (Morris 533 km², Pyramid 514, Castaic Lagoon 412, Big Tujunga 212,
Littlerock 165, Lake Hemet 143, Big Bear 137, Matilija 132). Since 2026-11-22 that is the first cell of the way
out `03b_stitch.py` laid at NHD's outlet (`lake_outlets.json`, 3.) for 1,414 of the 1,431 lakes carried on: one
decision where there were two. Until then `crossbox.py` found the cell itself by walking down the NHDPlus
flowlines leaving the lake; that cell sat beside the channel as often as on it, 300 m or more from the river's
own line at about 60 outlets, and 31 lakes' water went in 200 m or more from an outlet `03b` had right. For the rest (the 12 lakes `03b` leaves at the
terrain's cell, and lakes NHD's detailed data gives no outflow line: Castac Lake) that walk still stands, and
the cell it finds is moved to the top of the lake's routed way out where it lies within 100 m of it and runs
into it (`_at_outflow`, 4 lakes). A put-in whose path leaves its box across a rim basin too small to have an
exit link gets one, so the water goes on in the next box (the water of 2 lakes died on such an edge). The
lakes whose water is carried nowhere are named in the log. Lakes with no outflow (Baldwin Lake) and dead ends away
from lakes (desert fans, the sea)
stay closed. Drainages still end at dams; only areas use this. NHDPlus (1:100,000) has no flowline for most small
ponds, and below them a brook's drainage started again from nothing (293 ponds over the 12 areas, 2026-11-20:
7,751 reaches too small for a stretch, the Soquee 390 km2 at the Chattahoochee where NHDPlus has 414): where
NHDPlus has no line in the lake (or its lines find no way on), the box's detailed NHD stream line leaving the lake
gives the cell below its outlet. Those links carry the reaches' areas (`area_full_km2`) but not the forks and
drainage names: on them near-equal arms tipped the other way and the trunk left the named river (the upper
Chattahoochee came out as a fork "Chickamauga Creek"), so `05c` picks forks on the area without them (and its
trunks follow NHDPlus's main path, below).

### Lines 426-427
The Santa Clara River's own drainage covers
1,675 km² of its 4,210 km² watershed; the rest is those tributaries or lies outside every study box.

## Pipeline, step 7: `05b_flow.py` (lines 428-492)

### Lines 432-433
(41
reaches: the model now matching a creek it didn't before, or a side creek inheriting a different segment)

### Line 437
each table was fetched again with the flags on 2026-11-19

### Lines 440-441
the sort was unstable until 2026-11-20, so a change anywhere else could flip such a
tie.

### Lines 444-445
(a vertex is a cell corner; until 2026-11-20 truncation put about half of them one row or column off, and walks
that ought to stop in a lake slipped past it beside the channel)

### Lines 454-455
so until 2026-11-20 such creeks read "no
data" (10 % of Jackson's reaches within 1.5 km of an edge between boxes; 569 reaches over the 12 areas)

### Lines 460-461
(until 2026-11-19 such reaches read "no data" or took the flow of the river below
the dam, and were scored as streams: Fontana Lake's arms at fish 83)

### Lines 462-464
a reach matched to the creek's
line above the lake had read as that creek (a reach all inside String Lake scored 100; 397 such reaches over the 12
areas).

### Line 464
Against NHD's older outline a side creek at Lower Slide Lake's head and Emma Matilda Lake's outlet creek between its ponds read "reservoir" where the map shows no lake (158 reaches, 84 km over the 12 maps).

### Line 464
(since 2026-11-20: the Little Tennessee inside Cheoah Reservoir, NHD river area, had scored 73 as a river; 196 reaches over the 12 areas, 125 of them at fish 60+)

### Line 464
(Palisades Reservoir is four: the Salt River's crossing, 72% in the four and under half in any one, had scored 80 as a river)

### Lines 481-484
NHDPlus ends a line at every junction, and a 10 m
reach of the San Jacinto River at the junction 1.4 km above its gauge took its flow from the next line when the
routing moved a vertex, and read year-round between reaches the gauge sets at "mostly dry". Reaches with a gauge's
record: 1,170 → 1,277 over the 12 maps.

### Lines 485-486
following it across junctions (measured the same day) put dry records on reaches 2-4 km above their gauge (Murray
Canyon, San Juan Creek) and below junctions where another creek comes in;

### Line 490
about 0.7 and 0.4 GB

### Lines 490-491
and the rule
changed nothing (measured 2026-11-20)

## Trails, access roads and map cartography (lines 501-622)

### Lines 503-504
OSM was the most complete source in every
test area (Mt. Wilson, Topanga, Idyllwild, Wheeler Gorge, Trabuco).

### Line 535
and was missing until they were added

### Lines 586-588
Folium's overlays (the fire
closure areas) used to get their own full-map canvas above the streams, which took every hover and
click: the cursor stayed the grab hand and nothing could be clicked.

### Lines 592-593
Trails, access roads, trailheads, parking and the fire closure
areas used to start on in the 2D map; since 2026-11-18 they wait in the layer list like everything else.

### Lines 602-604
(the lakes session). The routing ran its paths dead straight across flat water, and their
names and colours came from the lake's own drainage vote ("Trout Creek" across Palisades Reservoir). About 8,200
reaches over the 12 maps; about 170 at lake edges, where the two outlines differ, stay with the other streams.

### Line 609
so the line below a dam began a median 21-35 m from the shore

### Lines 613-614
290
of the 393 cells below a dam on the eight shown maps, 1,048 of 1,436 over all 12 (median 28-57 m).

### Lines 616-619
With the links cut at lake
shores both are lake water wherever the path starts at a lake's last reach or runs into the next lake, and the
stretch read reservoir (530 m between Spencer Pond and Big Pond in NE Connecticut, fish 15 where the uncut link
had read 57).

## Which closures the approach times count (lines 650-674)

### Lines 657-658
(Angeles Crest Highway's "weather"
closure since December 2025)

### Line 660
(Grand Teton's Jenny Lake Loop)

### Lines 664-666
cutting 25 m around it out
of every road had severed the Antelope Valley Freeway at Stonecrest Road, Newfound Gap Road at Sugarlands, Teton Park
Road where the Jenny Lake Loop joins it and Lower Gros Ventre Road at the foot of Mormon Row.

### Lines 671-674
Before, every full closure active on the build day cut its road: in November, 654 Jackson reaches were
timed from the Teton Park Road, North Park Road or Grassy Lake Road gates with a ride up the closed road (Cascade
Creek: "park at Teton Park Road → bike 57 min on closed roads → hike 48 min", fish 100; now "park at Lupine Meadows
Park Access → hike 41 min", fish 87).

## Access, conditions and context (lines 676-743)

### Lines 683-684
A cell's own slope is the hillside's: the West Fork Road climbs 1.4% across a 30% canyon
wall, and riding it at hillside grade took twice as long.

### Lines 738-739
A creek's NHD line runs out to the receiving river's centreline, so any channel near the mouth used to
give the creek the river's drainage and fish score.

## Fish score: water, thermal, burn, trout, heat (lines 778-866)

### Line 785
which the gauge found flowing in 19% of summers

### Lines 787-816
**Creeks the model rates flowing that are dry most summers** (2026-11-20). Against the USGS gauges of all 12 areas,
31 of LA's 53 gauged creeks that are dry most summers were rated "usually flows" or "year-round", nearly all where
the model's typical summer low is 0.1–0.45 cfs (25 of 31 gauged creeks there are dry most summers); outside LA only
Dead Creek in the Champlain lowland. The fix is one-sided, as the owner put it: "id rather rate a dry creek as year
round than a year round creek as dry". (1) A **bare channel**: model low under 0.45 cfs, no green along the channel
in late summer (`green_p90` under 0.45 in the median summer and 0.5 in every one, and not 0.2 greener than the slopes
around, which keeps desert palm oases like Andreas Canyon), NHD intermittent, ephemeral or unmapped, and no trout
record, dam, tailwater, open water or fire since 2018: water 0.35 ("seasonal"), never lower. Every gauged creek in
that range that flows most summers has a green channel (0.67–0.86). (2) A **gauge on the creek**: 0.05 + 0.95 × its
share of summers flowing. It raises a reach anywhere (Piru Creek below Pyramid Dam flows every summer on its releases,
where the natural-flow model said seasonal), and lowers one only at or below the gauge and where no trout are known
on the creek it stands for. Measured before installing: none of the 221 gauged creeks that flow most summers is
lowered, 13 of the 35 dry ones rated flowing are caught, and the summers since 2011 called flowing while the gauge
was dry fall from 82% to 13%; it changes 636 LA reaches (33 of them up), 69 in Jackson and 13 on Dead Creek, and no
others. (3) A **tailwater** (see *thermal* below) with no gauge record on the reach: full water, since its dam's
releases keep it flowing every summer, which the natural-flow model can't see (since 2026-11-21). Piru Creek below
Pyramid Dam had read mostly dry or seasonal on 28 of its reaches, against the gauge just below the dam, which ran
in 11 of 11 summers; the gauge above Lake Piru (31% of summers) still sets the reaches it stands for. (4) **Below a
lake or dam** that holds half or more of a reach's drainage (LA, where the flows are natural flows), the model's
figure is for the creek's own ground below it, since `05b_flow.py` leaves the water from above a dam out. That is
the least that runs there (what seeps, spills or is released comes on top, and a natural lake passes its water on),
not evidence that the creek dries, so it doesn't put the reach below NHD's class: perennial 1.0, intermittent 0.35
(since 2026-11-21). Not where a gauge on the reach has a record, nor where the channel is bare in late summer.
Willow Creek below Lake Arrowhead had gone from seasonal to mostly dry when the routing stopped counting the lake's
shores as its own ground; Bear Creek below Big Bear Dam, trout water that NHD maps perennial, read seasonal on 4 km²
of its 193. 105 LA reaches rise. Popups say
which rule set the class and why. The
model and NHD
often disagree: of NHD's 2,430 "perennial" reaches the model has 619 drying in some or most summers, and 850 NHD
"ephemeral" reaches flowing through most summers.

### Lines 828-829
Since its 2026-11-19 expansion that is Jackson (145 sites, mean 13.4 °C, fit 3.37 °C off against a 3.72 °C
spread), so its reaches keep full credit, as under its earlier fit (which put every reach under 18 °C).

### Lines 830-831
Until 2026-11-18 this part was an elevation
band (700–2300 m); the estimate replaced it so the same cutoffs work in every study area.

### Line 844
(until 2026-11-22 it counted as the worst)

### Lines 846-847
on LA's burned creeks with no severity map,
trout were recorded after the fire on 12% of those draining 4 sq mi or more, against 9% of unburned ones.

### Lines 850-852
(until 2026-11-22 the latest one halved the score): where a later survey sampled the
same reach, it found trout after 80% of empty samples in NE Connecticut and 56% in the Smokies, and after two empty
samples in a row 83% and 53%.

### Lines 852-853
(e.g. Mill Creek and Big Santa Anita Canyon,
empty in 2023 and 2024)

### Lines 858-860
of ~330 creek records
(CDFW surveys, stocking, iNaturalist), the hottest site is 26.7 °C (lower Piru Creek, a tailwater), and the next
are Coldwater Canyon Creek 26.5 °C and Plunge Creek 26.2 °C.

### Lines 862-865
In the Water Quality Portal, the Whitewater River at White
Water read 24–27 °C on April afternoons and 25.7 °C in early June. The Agua Caliente Band's readings in Palm, Andreas, Murray, Tahquitz and West Fork canyons
were 17–22 °C on March–April mornings, when mountain trout creeks run 5–13 °C. Chino Canyon Creek read 32.7 °C on
an August afternoon, though at 28.8 °C air it sits below the gate.

## Fish score: Stream temperature: what was tested and why the gate uses air temperature (lines 868-884)

### Lines 869-884
The models were checked against 83 sites with measured July–August water temperatures in the eight ranges (Water
Quality Portal: USGS, Forest Service, EPA, and the Morongo, Soboba and Agua Caliente tribes). The error is
leave-one-out RMSE of a linear fit, where the site-to-site spread is 5.7–6.0 °C:
- **NorWeST** (USFS, August mean): 5.6 °C. It has only ~54 calibration sites in these ranges, mostly big lowland
rivers (Santa Ana, Santa Clara, Santa Paula, Sespe, Piru). On the spring-fed upper Santa Ana River and its side
creeks it predicts 20–23 °C August means where summer readings are 11–16 °C. It also has nothing in the Salton
Sea basin (HU 1810: the Palm Springs and San Gorgonio Pass canyons, 1,476 of our reaches).
- **EPA StreamCat** (Hill et al. 2013, July–August mean): 4.1 °C. It rates Palm Canyon (23.0 °C) about the same as
Deep Creek and Piru Creek, which both hold trout.
- **PRISM August air temperature**: 4.0 °C.

Southern California trout also live in warm water. Deep Creek near Hesperia averages 24.8 °C in August (USGS,
2017–26) and has wild trout upstream. SCCWRP's regional study (Tech. Report 1084, 2019) found O. mykiss mostly where
the warmest week averaged under about 22 °C, and none above a 32.5 °C weekly maximum. So the gate only takes down
water hotter than every place trout are recorded. `data/validate_heat.py` (run from `scripts/` after
`11_context.py`) reproduces these numbers and lists the readings inside the gated zone.

## Fish score: the water-temperature estimate (thermal term) (lines 886-954)

### Lines 886-954
**The water-temperature estimate (thermal term).** `watertemp.py` fits the measured sites' July–August daytime
medians on PRISM August air temperature and elevation, per study area, and stores the fit in
`data/raw/<area>/_shared/water_temp_fit.json` (run `../.venv/bin/python watertemp.py` to refit; `06_map.py` only
reads it). Since 2026-11-20 each site is weighted by how well its median is known, 1 / (τ² + σ²/n): σ is the spread
of single readings around their site's median (1.3-3.9 °C by area), n the site's number of readings, τ² what the
predictors miss on a well-measured site; a single grab sample counts for less than a logger's summer. The skill test
and the area mean are weighted the same way. Jackson's fit has skill since (0.887 of the spread against 0.906), so
its reaches carry an estimate; elsewhere scores moved by 2 points at most. Since 2026-11-21 a fit may also use
**the lake water just above a reach** (`lake`). A lake's outlet runs at the temperature of its surface, and the warmth
fades fast below it. At the Adirondack maps' measured sites with mostly lake water, the 19 within 200 m (650 ft) of
the lake read 23.8 °C (74.9 °F; 16 of them 73 °F or more, none 68 °F or less), the 8 from there to 1 km below
20.2 °C, the 7 from 1 to 3 km below 18.6 °C; the 231 sites with under half lake water read 17.2 °C. So the term is the
share of a reach's drainage that reaches it through a lake (the water `crossbox.py` carries past dams and ponds over
the reach's full drainage), counted **only for the part of the reach within 200 m below the lake, along the channel**
(`LAKE_NEAR_M`; `below_lake()` walks up the reaches that bring the lake water, to a reach lying in the lake or to
where the lake's water is put in beside its outline; no per-area setting). A reach lying in a lake takes the term in
full. A measured site takes the value at its own spot on the reach it sits on (within 150 m); a site where a creek
comes into a lake takes the creek's.
**A reach is scored and shown on its estimate as a whole, the mean along it** (`lake_parts()`): a reach that starts
at a pond and runs on for half a mile is mostly past the warmth and reads cool. Its first stretch still runs at the
outlet's temperature, so the map's popup adds that ("summer water about 64 °F (…); about 75 °F over its first
650 ft, just below a lake"; `water_outlet` and `outlet_m` in the ranked table, from `scoring.py`, with no part in the
score) where the stretch is estimated 1 °C or more warmer than the reach as a whole and is 50 m or longer: 1,193 of
the three maps' 24,914 drawn creek lines. At the 19 measured outlet sites the reach is a median 764 m long: its own
estimate reads 4.4 °C (7.9 °F) below the site, the popup's line for its first stretch 0.6 °C (1.0 °F) below. Of the
26 sites measuring 73 °F or more, 6 sit on a reach that itself reads 73 °F or more and 17 on one that keeps full
credit; with the popup's line counted, the map says 73 °F or more at 16 of them. Only a reach cut 200 m below each
lake would carry that warmth in its score (a rebuild from `05_score.py`; not done, the user's call).
As first installed (2026-11-21) the share counted however far upstream the lake was. That read creeks 1 to 3 km below
a pond 2.8 °C (5 °F) too warm and took 10 or more points from 444 creek reaches (173 mi) of three maps, 401 of them
with a trout record. With the distance in it (2026-11-22, the user's choice of three options; measured by
`audit/scripts/lake_term_test.py` and in the log) 99 short reaches just below ponds lose that much (8.7 mi, median
139 m, estimated at about 24 °C). The estimate at a site's own spot is 73 °F or more at 21 sites (16 measured there,
the other five at 70-73 °F) of the 26 that are; the first form's was at 7 (6 measured there).
Three of the four Adirondack maps had no fit with skill without a lake term (leave-one-out error 0.92-1.02 of the
spread) and gave every reach its area's mean, full credit everywhere. With the term:
the High Peaks map fits elevation and the lake term (90 sites, 3.16 °C against a spread of 3.85), the south-west map the
lake term (121 sites, 2.55 against 3.44; the fit's one pass of outlier removal now leaves out two single readings of
25.0 °C, and with them in it is 2.69 against 3.50, where the first form gave 3.02), the south-east map keeps its fit
on stream size (2.50 against 2.99), and the north-west map, still without a fit on its own 63 sites, takes the one on
all four maps' 336 sites (elevation and the lake term, 2.95 against 3.58), which misses its own sites by 2.84 °C
against their spread of 3.36
(`water_temp_group` in `config.py`: a map's own fit comes first, and the region's only where it misses the map's own
sites by no more than 0.9 × their spread. One fit for all four missed the south-east map's sites by 3.10 °C, more
than their own spread.) A creek fed wholly through a pond reads 7.2-7.9 °C warmer at the outlet than one with no lake.
The cost of the distance, said plainly: beyond 200 m the estimate reads a lake-fed creek as a creek with no lake,
1.6-3.4 °C (3-6 °F) too cool at the 26 measured sites there. That marks no creek down; a lake-fed creek that does
run warm further down keeps full credit (2 of the 8 sites from 200 m to 1 km below read 73 °F or more, 3 read 68 °F
or less). Keeping about half the warmth beyond 200 m fits the sites a little better (under 0.1 °C of leave-one-out
error) and would take about 5 points from some 100 mi on 15 thinly sampled sites: not near-certain, so not installed.
The 200 m itself is not sharp: two outlet sites 230 and 251 m below their lake read 23.2 and 23.0 °C, a third at
256 m reads 14.6 °C on one reading.
The term counts in full on creeks up to 50 km² and fades to nothing at 500 km². A pond
spills warm surface water, but a big dam may release cold water from depth, and the measured sites on lake-fed
rivers of 200+ km² are mixed: with the plain share at any distance the Adirondack ones read 0.7 °C below the fit on
average (the Sacandaga below Great Sacandaga Lake's dam 2.9 °C below, Lake George's outlet 0.9 °C above), Jackson's
1.4 °C below. A river below a dam isn't marked down for warmth on that. The cost: with the fade those Adirondack
sites read 2.2 °C above the estimate on average, so warm lake-outlet rivers keep the credit they had. The term enters
a fit only where 5 measured sites have a term of 0.5 or more (the four Adirondack maps have 28: High Peaks 6,
south-west 15; Jackson has 9, and no fit there is better for the term): every other area's fit is as it was.
In the LA ranges: water = 10.5 + 0.56 × August air (°C) − 4.17 × elevation (km), on 65 sites, with a
leave-one-out RMSE of 3.2 °C (air alone 3.45, elevation alone 3.3). Three sites with medians over 30 °C are left out
(two on Warm Creek in San Bernardino, which is fed by hot springs, and one August afternoon reading in Chino
Canyon). The estimate is held at the edge of the fitted sites' range (air 17.2–28.7 °C, elevation 142–2,120 m), and
it runs narrower than reality: 11–26 °C over all reaches. Air and elevation each miss at low elevation in opposite
ways: the Santa Clara River near Piru measured 26.5 °C under cool coastal air, and Santa Paula Creek 18.9 °C at
180 m. On the 1,566 reaches with trout evidence the new term gives the same mean credit as the elevation band did
(0.91). Against the elevation band, 95% of reaches moved by 3 points or less and 33 by 10 or more; 189 of the top
200 stayed. Stream popups show the estimate ("summer water about 21 °C").

## Lakes (lines 969-1072)

### Lines 970-974
Built for all 12 areas, each from
its own smallest size (`BUILT` in `05d_lakes.py`): Jackson 0.5 ha, NE Connecticut 1 ha, central Vermont 1 ha,
Lexington 0.5 ha, North Georgia 2 ha (below that it has 1,835 farm ponds), LA 1 ha, SE Pennsylvania 1 ha (450 suburban
and farm ponds of 0.5-2 ha, few named), the Smokies 0.5 ha (mountains with few ponds) and the four Adirondack maps 1 ha
(natural ponds; this keeps the 2.5-acre brook trout ponds). A lake a state lists is kept at any size.

### Lines 985-986
(before, a flat lake surface read as easy ground
and routes crossed lakes on foot)

### Lines 987-988
(not at its quickest shore anywhere: a creek's mouth 20 km up an arm of Fontana Lake had read 2 min away; a
shore reached across the water, an island's, is no target)

### Lines 997-1010
| Area | Lakes | Lidar shorelines | Measured depth | Depth contours | Trout stocked or recorded | Walk-in times changed |
|---|---|---|---|---|---|---|
| Jackson | 543 | 238 | 58 | none public | Game & Fish list: 56 with game fish | 272 of 6,419 reaches (pilot) |
| NE Connecticut | 706 | 632 | 44 | 1,098 lines at 35 lakes (CT DEEP) | 24 | 482 reaches quicker, none 5+ min slower |
| central Vermont | 411 | 292 | 17 | 516 lines at 14 lakes (VT ANR) | 23 | 274 reaches quicker, none 5+ min slower |
| Lexington | 182 | 111 | 1 | none public | 2 | 50 quicker; 2 slower by 5 and 9 min, beside a pond |
| North Georgia | 551 | 490 | 9 | none public | 13 (Lake Burton, Winfield Scott, Black Rock, Nancy Town...) | 782 reaches quicker (median 7 min); 4 reaches and 3 drops 5+ min slower, at most 24 |
| LA | 389 | 86 | 6 | 39 lines at Little Rock Reservoir (USGS) | 18 (Big Bear, Jenks, Gregory, Hansen Dam, Yucaipa...) | 462 reaches quicker (median 12 min); 22 reaches and 29 drops 5+ min slower, up to 3 h, all beside Castaic, Pyramid, Morris, San Gabriel, Big Tujunga or Cogswell: their old routes walked on the water |
| SE Pennsylvania | 262 | 200 | 6 | 56 lines at 4 lakes (DCNR / PA Geological Survey, USGS) | 3 (Scotts Run Lake, Loch Alsh Reservoir, Marsh Creek) | 45 reaches quicker (median 2 min); 2 reaches 5+ min slower, at most 8 |
| the Smokies | 180 | 83 | 1 | none public | 10 (Cheoah, Calderwood, Chilhowee, Tellico, Queens Creek Lake, Max Patch Pond...) | 183 reaches quicker (median 2 min); 438 reaches and 47 drops 5+ min slower, up to 10 h: Fontana's north-shore creeks and the reaches inside Fontana, Cheoah, Calderwood and Chilhowee, whose old routes walked on the water |
| Adirondacks: High Peaks | 768 | 548 | 8 | none public | 114 (DEC's stocking and lake lists: Lake Placid, the Saranacs, Taylor Pond...) | 1,068 reaches quicker (median 7 min); 406 reaches 5+ min slower, at most 119 |
| Adirondacks: northwest | 1,313 | 980 | 7 | none public | 95 (Cranberry Lake, Raquette Lake, Stillwater Reservoir...) | 683 quicker (median 4 min); 953 reaches 5+ min slower, at most 307 |
| Adirondacks: southwest | 953 | 701 | 4 | none public | 118 (Fourth Lake, Piseco Lake, Lake Pleasant...) | 409 quicker (median 3 min); 429 reaches 5+ min slower, at most 100 |
| Adirondacks: southeast | 1,137 | 808 | 8 | none public | 116 (Lake George, Indian Lake, Schroon Lake, Brant Lake...) | 945 quicker (median 5 min); 324 reaches 5+ min slower, at most 171 |

### Lines 1012-1016
The rule fixes of 2026-11-20 (the outline rows and the walking bullet above) changed the first six areas' walk-in
times as well: a reach lying in a lake is reached at its nearest shore, not the lake's quickest, so 35 (Lexington) to
405 (North Georgia) reaches got 5+ min slower, the most where a river is mapped through a big lake (the Snake through
Jackson Lake up to 11.5 h, the San Gabriel through its reservoir 5 h). Fish scores moved by 5+ points at 0-154 reaches
per area (Jackson 154, LA 60), by at most 10.

### Lines 1018-1032
Each attribute comes from the best source there is for it, and the sources were checked against each other:

| Attribute | Source | Checked |
|---|---|---|
| Outline | 1 m lidar (USGS 3DEP), the newest survey over each lake, read in place from USGS's cloud-optimized tiles (tiles in another UTM zone are reprojected). Lidar DEMs are hydro-flattened, so the cells at the lake's one elevation are its shoreline on the survey date. A lake flattened at more than one level (flown on two days, or pools split by a causeway) takes the flat patches at the other levels lying mostly inside its outline; flattened water is one patch of 200 m² or more. NHD High Resolution where the lidar didn't flatten the lake, for reservoirs and lakes drawn down that day, where the water at the lake's level runs on past it (off the window, or into NHD river area), and over 600 ha. Touching NHD lakes trim each other's lidar water. A lake mostly outside the map with under the area's smallest size inside is left out; one reaching far past the map is stored to 2 km past its boxes (its size and facts the whole lake's) | Jackson: median overlap with NHD 0.78; on imagery the lidar follows the water (Lower Slide Lake's vegetated inlet delta, Table Mountain Lake's bare shore band are in NHD's outline). North Georgia: with one level only, Tugaloo Lake was 100 ha of its 203 (now 195.5), Seed Lake 29 of 77 (now 73); Toccoa Reservoir is two pools either side of a causeway. Adirondacks: Figure Eight Pond had flooded along its flow to 5.6 times its size, Upper St. Regis into Spitfire Lake. A size rule (lidar over 1.5 times NHD: keep NHD) was tried and dropped: in Connecticut and Jackson the bigger lidar outline is usually the right one |
| Water level, elevation | The lidar's flattened level; the median of a level but unflattened surface (70%+ within 15 cm); else the 10 m DEM. A lake the lidar caught low shows its normal level | NHD's stage elevations are in feet at some lakes and metres at others (read per lake against the DEM) and can be metres off: Table Mountain Lake 12 m, 50 North Georgia lakes 2-28 m |
| Survey date | Each lidar survey's span: one can fly for a year (VA_West_Chesapeake_B1_2017: 2017-04 to 2018-05) | |
| Missing lakes | OpenStreetMap water of the area's smallest size or more that no NHD lake covers, kept where the lidar shows level water; NHD's dropped treatment and storage ponds count as covering, and water NHD maps as river, canal or estuary isn't a missing lake unless OpenStreetMap tags it a reservoir. An NHD lake OpenStreetMap names a wastewater works is left out. A state's listed lake NHD has no lake for keeps the agency's outline (Cheoah Reservoir, which NHD draws as river) | se_pa had taken in 7 tidal creeks by the Delaware, flattened at sea level, and 4 concrete or treatment basins; North Georgia 5 lined basins and a river channel; Connecticut 3 aerated lagoons. Lakes added from OpenStreetMap before that rule (2026-11-19): Jackson 61, Connecticut 124, Vermont 13, Lexington 11, North Georgia 52, LA 7 |
| Name | GNIS (NHD); Wyoming Game & Fish's where it names a group or adds a qualifier; else OpenStreetMap's, where one named outline and the lake cover half of each other, no lake within 2 km has the name, and it doesn't end in "Dam" (166 lakes); Connecticut's survey name for one more | Virginia's public-fishing-lake layer isn't used for names: it calls the 189-acre Mill Creek Reservoir "Mill Reservoir" (DWR's own page and OpenStreetMap: Mill Creek Reservoir) |
| Fish | Jackson: Wyoming Game & Fish's lake fishing guide (game fish or "None", lake class, depths, private shore). Elsewhere: the state's stocking and survey records already gathered for the streams (`context/trout_evidence.gpkg`: CT DEEP stocking and electrofishing, Vermont's trout stocking list, Virginia's trout stocking plan, Georgia DNR stocking and surveys, CDFW's stocking schedule, PFBC's stocked lakes, NCWRC's mountain trout impoundments, TWRA's reservoir stocking): a record naming the lake within 2 km (word order aside: "Gregory Lake" is Lake Gregory), or a lake record within 150 m of the shore. A stream's stocking or survey point beside a pond stays the stream's (CT DEEP's stream surveys sit at the inlets and outlets of 44 ponds). A lake record inside an unnamed lake names it (Yucaipa Lake). New York: DEC's stocking since 2011 (data.ny.gov; names by town, matched to NHD lakes by name in the town, else the only one of the name in the county) and DEC's lake fishing list (its species). SE Pennsylvania: PFBC's 2021 trap-net survey of Scotts Run Lake. Everywhere: GBIF records at the lake (state surveys, iNaturalist, USGS NAS, museums), shown with source and year | Species recorded since 2000 but not on Game & Fish's list are shown beside it (brown trout in Leigh Lake) |
| Depth | Measured values only, best first: published sonar surveys and state bathymetry (CT DEEP contours, a lower bound; Vermont ANR sonar soundings, gridded per lake), EPA National Lakes Assessment sonar (the index site: a natural lake's deepest spot, a reservoir's lower bound), fisheries transducer surveys, an agency's listed depth. SE Pennsylvania: DCNR / PA Geological Survey depth maps (Marsh Creek, Hopewell and Scotts Run lakes: the map's deepest point, its depth bands drawn as contours) and USGS's sonar survey of Chambers Lake | Vermont's grid against published figures: Lake Dunmore 106 ft deep and 29 ft mean (published 105 and 28). Disagreements over 20% (and 2 m) are shown |
| Inlets, outlets | NHD HR flowlines that start or end at the shore; an unnamed outlet is followed down to the first named water | Many small lakes have no mapped stream: "no mapped inlet or outlet (NHD)" |
| Access, rules | Connecticut: CT DEEP boat launches, fisheries-management lake designations. Vermont: fishing access areas, special regulations, restricted waters. Virginia: DWR public fishing lakes and their boat and motor rules. SE Pennsylvania: PFBC lake access points (ramps, piers, motor rules; with credit to PFBC, as its licence asks), DCNR state park launches, PFBC lake special regulations and boating rules. The Smokies: NCWRC boating access and public fishing areas, TWRA access sites, TVA ramps, NCWRC impoundment classes, the Calderwood reciprocal licence. The Adirondacks: DEC's lake fishing list (launch type, hike-in, bait and motor rules, contour map links) and DEC's launches and fishing access sites, all from data.ny.gov | DEC's own ArcGIS layers say "secondary distribution of the data is not allowed", so they aren't used for lakes |
| Land | PAD-US (the public-access service). Where PAD-US leaves the water out (Jackson Lake, with ~300 m of shore), the unit most of the shore lies in. Access is flagged only where closed, or restricted outside federal land | |
| Level water | Lakes of 2 acres or more whose lidar surface isn't level (under half the outline within 15 cm), with the 10 m DEM agreeing: "largely dry, marsh or overgrown then". A dammed lake whose bed lies over a metre under its own lidar shore, or under a neighbour's normal level where its own shore lies at that level: "caught drained / drawn down". A flattened dammed lake over 2 m under NHD's level, with its normal shore over 1 m clear of the water: "below its normal level when the lidar was flown" | On imagery (Esri World Imagery) the flagged lakes in Lexington, North Georgia and LA are forest, field, marsh, bare or low basins. Without the shore test, NHD's level made 50 full North Georgia lakes "drawn down" |

### Lines 1034-1044
**Lake Champlain** (central Vermont and two Adirondack maps; since 2026-11-21): the soundings of NOAA's electronic
navigational charts (NOAA ENC cells over the lake, charts 14781-14784: 12,083 soundings of the 1870-1939
lake surveys, with the charts' 6 and 12 ft depth curves and the charted shoreline), gridded over the whole lake (50 m,
linear) into 20 ft contours: 399 ft at the deepest sounding, off Split Rock; mean 74 ft; the grid holds 25.9 km³ where
the Lake Champlain Basin Program gives 25.8. Depths are below low lake level, the chart datum (93.0 ft above sea
level; the lake usually stands 2-3 ft higher). NOAA's user agreement: "You may download, use, and redistribute them
without restriction", and inside another product on condition that the charts' origin and the agreement are shown;
the lake's popup names charts.noaa.gov, gives the agreement's address and says the depths aren't for navigation. Looked
for and not open: Middlebury College's multibeam survey (not released for distribution). Also open, not read: NOAA's
2019-21 topobathy lidar of the shallows (Vermont's 0.7 m grid, to about 20 ft), Vermont's 1992 digitizing of the same
chart soundings, NOAA's 2018 multibeam of the north lake.

### Lines 1046-1060
**Bathymetry.** Connecticut DEEP's lake contours (24 surveys of 1959-2002 by depth finder, GPS or lead line; feet;
the deepest contour is a lower bound) and Vermont ANR's sonar soundings (2.4 million points in 66 lakes, compiled
2020; depth below the survey day's level) are read by `lake_bathymetry.py`. No lake in the Jackson boxes has a depth
survey that can be downloaded (checked 2026-11-19): Jenny Lake, Jackson Lake and Palisades Reservoir are surveyed
but published only as figures or held by their authors. LA: USGS's multibeam survey of Little Rock Reservoir (8-9 Feb 2022, a 1 m grid, doi:10.5066/P9BQW35E) gives 16 contour lines, 76 ft deep and 38 ft mean below the lidar's water level (the spillway crest). Its file says ft NAVD88, but its elevations sit 106.4 ft under the 3DEP lidar on land (the geoid separation here), so they are raised by that much; the deepest bed then comes to USGS's own stage-storage zero (3,197.5 against 3,199.5 ft). Lake Arrowhead's 2008 Reclamation sonar survey (a report: area-capacity table) gives 152 ft deep, 61 ft mean below full pool, typed in; EPA's 2007 sounding, 153 ft, agrees. California DWR's multibeam surveys of Castaic, Pyramid and Silverwood are not public. North Georgia: USACE's Lake Lanier cross-section surveys (1955-90) are sparse lines and carry a CUI marking, so they are not used; TVA has published one drawdown waterline of Chatuge; nothing for Georgia Power's or the Forest Service's lakes (Georgia DNR's contour layer covers south Georgia only). Lexington: Virginia DWR's map of Lake Robertson (5 ft contours, deepest 45 ft) is a picture, so its depth is typed in as a lower bound. Checked 2026-11-20. Modelled depths (GLOBathy, HydroLAKES) are
never used. SE Pennsylvania (checked 2026-11-20): DCNR's state park lake depth bands from the PA Geological Survey's water-depth
maps (Marsh Creek Lake, surveyed January 2005 by USGS and the Survey, 5 ft bands, deepest point 78.5 ft; Hopewell and
Scotts Run lakes, April 2017, 2 ft bands, 20 and 22 ft), drawn as contours with each map's deepest point typed in; and
USGS's sonar survey of Chambers Lake (Gyves 2015, SIM 3346: 150,779 soundings by acoustic profiler with RTK GPS,
September 2014; 47 ft deep, 12 ft mean below normal pool, as USGS's own volume table gives; its grid reads within 0.9 ft
of the 3DEP lidar along the lidar's shoreline). The Adirondacks: DEC's contour maps are scanned images without a date
or datum (linked in the popups where DEC's lake list gives them); Lake George's multibeam isn't public; the depths in the HuntFishNY layer and the Adirondack Lakes Survey's
pond pages have no stated licence (the survey's site forbids automated access). The Smokies: no published survey of
Fontana, Santeetlah, Nantahala or the Tapoco lakes; North Carolina's water-quality profiles give only lower bounds
(Fontana at least 80 m), and Duke's relicensing figures come from design drawings.

### Lines 1062-1072
**Walking.** Making lakes impassable mostly makes routes quicker: a reach mapped through a lake now counts as reached
at the shore. Few got slower, and only where the quickest route had crossed a lake on foot (Jackson: Leigh Creek's
canyon by Leigh Lake, up to 37 min). Summer routes in Jackson, without road closures, run within about 10% of the Park
Service's trail distances (Taggart Lake 1.3 mi against 1.5, Amphitheater Lake 4.5 against 4.9), a little short
because a 10 m grid cuts switchbacks. Times are a fit hiker's without stops (Tobler); boats aren't modelled. A
point in a lake is reached at the nearest reachable shore of its own lake (2026-11-20; before, at the lake's quickest
shore, which on Fontana Lake made a creek's drowned mouth 20 km up an arm 2 min from the road). So where a river is
mapped through a big lake its reaches take the time to the nearest shore on foot: the Snake through Jackson Lake up
to 11.5 h, the Little Tennessee below Calderwood Dam about 2 h (it read 6-10 min, across Chilhowee Lake's water). In
the Adirondacks, where many approaches are by canoe, routes that crossed lakes on foot now go round them: 324-953
reaches per map 5+ min slower, and their remoteness raises fish scores (5+ points at 22-214 reaches per map).

## Validation (lines 1074-1108)

### Lines 1092-1093
In the 2026-11-18 run, 25 of the Santa Anas' 46 mapped falls sat on
drainages under 1 km², below pass 1's floor.

### Lines 1097-1098
- Before 2026-11-20 the check counted no falls at all: since 02f_known_falls.py (2026-11-19) a fall's `src` lists all
its sources' labels ("OpenStreetMap · USGS GNIS"), and the check still looked for the old single values "OSM"/"NHD".

## Tonight's write-ups, as committed: #1 `435b921`, #2 `1fe612c`, #4 `9259977`, #5 `48141fc` (README.md at 48141fc; the line numbers are that file's)

### Line 160
| `stream_reaches_ranked.csv` | Every DEM stream link kept (1 km² drainage or more with the water from elsewhere, or 0.25 km² where NHD maps the creek perennial or names it: step 5), all ranges, ranked by fish score |

### Lines 232-233
   gathers a creek's ground of its own, or since 2026-11-23 as a second outlet (below). Of the 1,417 lakes ended at
   NHD's outlet on the 12 maps, 1,355 have one

### Lines 260-261
   drop. What it cost: the second outlet of 9 lakes was no longer drawn (drawn again since 2026-11-23, below), and
   15.7 mi of creek below 19 lakes read

### Lines 264-276
   **A lake's second outlets** (since 2026-11-23). `lake_outlet` hands back the outflow lines it doesn't pick, and
   each is a second outlet where it passes the outlet's own test (the terrain takes the water on down it within
   300 m, and its own path stays on NHD's line for 200 m), is a channel NHD maps (a StreamRiver line, or lines
   through water running into one, with no Connector, canal or pipeline before the first StreamRiver line: Castaic
   Lake's line through its dam and Glen Morgan Lake's connector are refused), and leads neither back into its lake
   nor up into a lake standing 0.5 m higher (Middle Flow's "outlet" climbs into Livingston Lake: an inflow NHD
   draws the wrong way round). Its way is laid as a stream line to the first stream it meets, like the outlet's, and
   listed under `sides` in `lake_outlets.json`. No flow direction or drainage area changes, and `crossbox.py` reads
   only the outlets. That gives 51 second outlets at 47 lakes on the 12 maps, which `05_score.py` draws (5.). They
   bring back 12 of the 14 lines the change above stopped drawing (13 at those lakes, and Beaver Pond's north
   channel), which the maps had drawn only where `crossbox.py` happened to put the lake's water in: Soft Maple
   Reservoir's Beaver River arm, Round Lake's, Marsh Creek Reservoir's arms among them. Castaic Lake's and Glen
   Morgan Lake's stay off by the rule.

### Lines 333-349
   **Down to 0.25 km² (0.1 sq mi) where NHD maps the creek year-round or names it** (since 2026-11-23; the user's
   choice of 2026-11-22, of keeping 1 km², NHD's year-round lines only, its named ones only, or both). At 1 km² alone
   12.5 % of NHD's named stream miles on the 12 maps were not drawn (26 % in the Smokies), named brook-trout headwaters
   among them. A link of 0.25-1 km² (with the water from elsewhere) is kept where the vote below, on the uncut link,
   finds an NHD line that is perennial (FCode 46006) or named, judged on the link's own line (`nhd_says`): a name it
   shares with a stream 10 times its size within 250 m is that stream's, and with no name of its own, the year-round
   class of a river of 50 km² or more (and 10 times its size) it runs along for 60 % of its length within 150 m is the
   river's (on the first try about 1,600 bank links of the 12 maps came out as side channels of the river beside
   them). The floor reads no canal, ditch, pipeline or conduit (NHD FType 336, 428, 420) and no line named after one,
   a name NHD gives a built line of the box and no stream line: the California Aqueduct's paths through its reservoirs
   (`floor_lines`; 9.7 mi of LA's new lines were aqueducts and canals on the first try). A creek kept this way runs on
   downstream through 0.25-1 km² links until it meets a kept line: across an edge two boxes share (the link that ends
   on it in the next box is judged here with the same rule) and on below a pond's or reservoir's outlet
   (`crossbox.dam_links`; Munson Pond's outflow in the High Peaks had lost its line). From a reach of 1 km² or more
   the stem climbs only reaches of 1 km² or more, so a side channel keeps its river's values. Nothing under 0.25 km²
   is drawn (03b's channel start: about 1,100 named NHD mi, 430 in the Smokies). The new creeks NHD maps perennial
   read year-round through `05b_flow.py`'s floor (step 7).

### Lines 361-389
   **The first 200 m (650 ft) below a lake is a reach of its own** (since 2026-11-23). A lake's outlet runs at the
   temperature of its surface, and a reach is scored on one water temperature, the mean along it: a reach that
   started at a pond and ran on for half a mile read as a cool creek, its outlet's warmth averaged away (*Stream
   temperature* below). Each creek is cut where it has run 200 m from the lake, along the channel the lake's water
   takes (`flowlib.cut_below_lakes`, finding the distance as the water-temperature term does, `flowlib.below_lake`),
   where the lake term there is 0.5 or more and neither piece would be under 50 m: 1,155 cuts over the 12 maps, on
   every map (a rule computed from the data, so a new area needs no setting). The cut is for the water temperature
   alone: both pieces keep the line's gradient and NHD class, `05b_flow.py` reads the cut creek whole, as before the
   cut, and gives both pieces its flow evidence, late-summer greenness and gauge record (`cut_sid` names the rest of
   the line), and `11_context.py` gives both the whole line's trout records and designated trout water, fires and
   critical habitat (`cut_lines`), as the uncut line had them. Measured on its own, a piece read drier than its creek
   (the model's natural flow leaves the lake's water out: a brook below a pond in north-east Connecticut "usually
   flows" -> "mostly dry"; the NHD vote fell on the reservoir's line below Big Tujunga's dam; a bare channel just below
   a dam read as a dry creek; a short rest below a small reservoir on the Arroyo Seco, where trout were found in 2024,
   matched the model's line below the dam: "year-round" -> "usually flows"), steeper (a step just below the shore cost
   64 pieces up to 15 points) and without its trout: a designated trout water or brook trout patch that starts lower
   down missed it, and a trout record goes to the nearest reach, so 53 first pieces (6.3 mi) and 23 rest pieces
   (7.6 mi) over the 12 maps lost trout's ×1.2 (9 of the first in north-east Connecticut). Drainage, elevation, August
   air, canopy, approach time, shade and land status are each piece's own.
   **A lake's second outlet** (3.; since 2026-11-23) gathers little ground of its own, so its links drain under the
   size floor. `05_score.py` keeps them from the lake down to the first link the map keeps on its own (within 5 km;
   one that meets none isn't drawn) and marks them side channels of the creek the lake's main outlet starts
   (`side_lake`, `side_sid`, `river_km2`): the maps say "(side channel)", and the popup names the lake and what the
   channel is scored on. Where the map keeps a second outlet's first link on its own, it is that creek, drawn from the
   lake on. With the floor down to 0.25 km² that includes 12 of the 51, whose first link NHD's vote keeps, though the
   vote reads the outflow line itself (MULTI_AREA_LOG, 2026-11-23; a follow-up counts only the link's own ground
   there). A junction only the new line makes leaves the creek above it as the floor had it. No water is added to any
   line: NHD gives no split of a lake's water. The 200 m cut above doesn't reach a second outlet yet, since its line
   carries none of the lake's water in the routing (a follow-up).

### Lines 452-472
     above Goshen Pass, Otter Creek, the Snake) started with nothing too. Every NHDPlus V2 main-path line that crosses
     the outer boundary flowing in, at any size, brings NHDPlus's total drainage at its lower end, less what the box's
     own routing gathers there (where the river's path passes within 150 m of the line's end; else its drainage where
     it crosses) and what the edge links already bring, carried down the creek the same way. Minor arms of split
     rivers are left out (NHDPlus gives them the whole river's drainage). The same water twice is decided on NHDPlus's
     network: a river taken before that NHDPlus has above this one counts once, where their paths meet. Water the
     terrain sends straight back out over the edge goes in further down the mapped river, at the first point, 50 m at
     a time, whose path stays in. Until 2026-11-23 only lines of 10 km² bringing 10 km² and a quarter of their total
     counted, a river whose path met this one's within 1.5 km took its water (the Chattooga's East Fork, so the
     Chattooga at Burrells Ford read 29 sq mi for its gauge's 47), and the French River at Webster found no cell to go
     in at; USGS gauges within 10 % of their drainage went from 435 to 462 of 516 on the 12 maps. One that comes in
     through a reservoir (the Chattahoochee in Lake Lanier) is handed to the cell below the dam: since 2026-11-22 the
     cell where that reservoir's own water goes in (a second line ran 115 m beside the Hiwassee below Chatuge Dam
     before). Such a river starts as a reach of its own where its water goes in (`crossbox.lead_ins`, laid by
     `05_score.py`): the terrain path from that cell to the first stream line, stopping at a lake whose water leaves
     the map, as 03b's lines do (lead-ins had run 4-10 km across Lake Champlain, and the shore creeks whose way down met
     one took the lake's flow). Before, a river's first few hundred metres in the map had no reach, and `06_map.py`
     drew them through with the values of the reach below; it now skips such a break where a reach starts on its cell
     (it had drawn 318 pieces twice along them). Not yet drawn: a stretch where a river weaves along the edge, its
     terrain path out of the map and the river (NHD) still inside, which no put-in reaches (Minister Creek on the
     SE PA map, 0.33 mi at 40.297 N, 75.588-75.583 W; accepted on 2026-11-22, a fix in test).

### Lines 522-524
   that ought to stop in a lake slipped past it beside the channel). A way that ends in a lake draining off the map
   (`03b`'s `lakes_off_map.gpkg`, which carries no reaches) takes that lake's NHDPlus line nearest where the way enters
   the water (since 2026-11-20).

### Lines 531-548
   run `05c_drainages.py` for every box before `05b_flow.py`.
   **NHD's class is the floor of a borrowed estimate** (since 2026-11-22; until then five rules each covered one kind
   of borrowed estimate, and a plain one in the reach's own box had none). An estimate scaled from another creek (the
   first modelled segment below, in the reach's box or the one it runs into, down a way through a lake, or an off-map
   lake's line) is about the creek below: a brook running into a pond inherits the river below it, which is no
   evidence that the brook dries. So is one that leaves out the water from above a lake or dam holding half the
   drainage (LA, natural flows: the model's figure is for the creek's own ground below the dam, the least that runs
   there; what seeps, spills or is released comes on top). Neither puts a reach below NHD's class, valued as the score
   values NHD's label where there's no estimate: perennial 1.0, intermittent 0.35, a line NHD gives no class 0.3, no
   NHD line 0.15, ephemeral 0.05. A creek NHD maps perennial reads year-round whatever the model says: outside
   California the model is NHDPlus's mean flow, with no drying in it, and it read 671 perennial brooks in north-east
   Connecticut below year-round (398 with trout found); in LA the natural-flow model read 145 mi that NHD maps
   perennial mostly dry. Only a USGS gauge's record (`scoring.py`: on the creek, or below a diversion) puts a reach
   below NHD's class. The floor is applied to each of the two passes (own area, and with the water from other boxes)
   before they are weighed, and once at the end (a creek cut 200 m below a lake is read whole, so both of its pieces
   take its line's floor). Columns `model_class` (the model's class where the floor raised the reach) and `water_floor`
   (perennial, inherited or dam). Reaches in or below a reservoir are flagged, since releases set their flow.
   A reach lying at least half inside an NHD lake or reservoir with no model segment of

### Lines 869-878
- **water:** dry-season flow from the Natural Flows model (outside California NHDPlus's mean flow × the area's gauge
  index, which has no drying in it; `05b_flow.py`): 0.05 + 0.95 × the share of summers since 2011 the reach kept
  ≥0.1 cfs through July–October; 0.3 in a reservoir. An estimate borrowed from another creek, or one below a dam that
  leaves the dam's water out, never puts a reach below NHD's class, and a creek NHD maps perennial reads year-round
  (`05b_flow.py`'s floor, since 2026-11-22; only a gauge's record goes lower). A reach with no estimate (no model line
  on the creek or below it on the map) takes the median water term of the area's reaches with the same NHD label and
  a drainage within a factor of 2 (4, then any size, where under 20 such reaches; `typical_water`), never below NHD's
  class: perennial 1.0, intermittent 0.35, a line NHD gives no class 0.3, no NHD line 0.15, ephemeral 0.05. A failed
  look-up is no evidence about the creek; until 2026-11-22 it took NHD's class alone, so one on a creek NHD doesn't
  map scored 0.15.

### Lines 891-895
  that range that flows most summers has a green channel (0.67–0.86). Since 2026-11-22 the test is decided per creek
  between confluences (`creeks()`: reaches end to end with drainage within 0.8 of each other): a creek reads seasonal
  only where all of it passes or already reads mostly dry, and none of it shows water (a trout record, a dam or
  tailwater, NHD perennial, open water, a channel 0.67 green or more). Decided reach by reach, it had changed a
  creek's class from one reach to the next. (2) A **gauge on the creek**: 0.05 + 0.95 × its

### Lines 908-909
  not evidence that the creek dries, so it doesn't put the reach below NHD's class (since 2026-11-21; since
  2026-11-22 part of `05b_flow.py`'s floor, on NHD's whole scale). A gauge on the reach still sets it.

### Lines 912-920
  of its 193. (5) A **trout record** (trout found since 2016, with no later survey finding none; `trout_signs`) lifts
  a reach to at least "usually flows" (water 0.69): trout don't live in a creek that is dry most summers. In LA the
  model had 81 such reaches mostly dry or seasonal (Arroyo Trabuco at 33.6005, -117.6313: 0.0 cfs, now "usually
  flows"). Popups say which rule set the class and why (the floor only where it changed the class). Outside
  California, where NHDPlus's mean flow can't see a creek drying, a popup's "year-round" or "usually flows" carries
  NHD's doubt where NHD calls the line intermittent or ephemeral or has none. Measured in scratch on all 12 maps
  before installing (2026-11-22, against site 6c72e2e): no reach lower; trout found since 2016 shown dry 96 → 0;
  NHD-perennial shown below year-round 1,729 reaches → 38, each set by a gauge's record; sudden changes of class
  along a creek 272 → 213; the gauges as before. The model and NHD

### Lines 922-924
  "ephemeral" reaches flowing through most summers; the map shows NHD's perennial ones year-round unless a gauge's
  record says otherwise (at the gauges NHD's perennial is right at 187 of 192 outside LA and 9 of 14 in LA, so some
  LA creeks shown year-round will be dry). Popups show the model's typical and drought-year low flow.

### Lines 928-935
  **A lake's second outlet** (5.; since 2026-11-23) is scored on its lake's water. It takes the water term and
  evidence of the creek its lake's main outlet starts where they read it at least as wet as its own, but NHD's class
  where NHD maps the channel intermittent or ephemeral, and it never reads wetter than the creek it runs into below,
  unless that creek is on its lake's own river. A trout record or designated trout water on the channel stands
  against both. The one-sided rule above keeps possible trout water but must not invent it: Lake Hemet's spillway
  had read year-round, fish 64, above Spillway Canyon Creek, which is mostly dry, and now reads mostly dry, fish 3.
  On the maps with the lake term (*thermal*) it takes that creek's lake share, with its warm first stretch counted
  from its own start at the lake (`watertemp.py`).

### Lines 938-939
  (`05_score.py`) takes the drainage of the river reach beside it, and a lake's second outlet the drainage of the
  creek its lake's main outlet starts.

### Lines 1015-1037
share of a reach's drainage that reaches it through a lake, counted **only for the part of the reach within 200 m
below the lake, along the channel** (`LAKE_NEAR_M`; `flowlib.below_lake()` walks up the reaches that bring the lake
water, to a reach lying in the lake or to where the lake's water is put in beside its outline; no per-area setting).
The lake water is what `crossbox.py` carries past dams and ponds over the reach's full drainage, and since 2026-11-23
also what runs on out of a lake along the routing before `03b_stitch.py` ends the lake's paths at its outlet, which
can lie past the shore the map draws (`flowlib.lake_water_km2`): the stretch between the two had read as a creek with
no lake (the first 131 m below Limekiln Lake 63 °F, where the outlet measures 78.8 °F; 184 such reaches, 30 mi, on the
three maps). A reach lying in a lake takes the term in full. A measured site takes the value at its own spot on the
reach it sits on (within 150 m; the one nearest its NHDPlus drainage, a first stretch below a lake counting with its
line's); a site where a creek comes into a lake takes the creek's.
**Since 2026-11-23 the first 200 m below a lake is a reach of its own** (`05_score.py`, *Stream links* above), so the
outlet's warmth is in that stretch's own score. Before, a reach was scored on the mean along it, and one that started
at a pond and ran on for half a mile read cool: 4.4 °C (7.9 °F) below the 19 measured outlet sites (a popup line gave
the first stretch's estimate, `water_outlet` in the ranked table; it still shows where a stretch isn't cut). Measured
in scratch on the three maps with a lake term, against the live maps: at the 19 outlet sites the reach now reads
2.4 °F below the measured 74.9 °F (7.5 °F before); of the 28 sites at 73 °F or more, 15 sit on a reach read at 73 °F
or more (4 before) and 8 on one at full credit (17); error over all sites 3.05 °C (3.20); the audit's check at sites
with 3+ readings, High Peaks 7.8 -> 6.2 °F, south-west 6.4 -> 4.1, north-west 7.7 -> 6.0, warm sites at full credit
5/9/6 -> 1/2/3, no cool site read warm. Against a score with no lake term 760 stretches (79.6 mi) score 10+ lower,
638 (66.8 mi) with a trout record (111 and 9.5 mi before); by the lake above them, under 25 acres 155 (16.7 mi; the
one measured outlet there, Owen Pond, reads 70.3 °F), 25-100 acres 383 (41.1 mi; 9 of 10 measured outlets at 73 °F
or more), over 100 acres 208 (21.2 mi; 7 of 8). The user chose the cut on these figures (2026-11-22; 758 stretches,
79.3 mi, 64.2 with a trout record, before the first stretches kept their line's trout labels).

## The brook trout write-up, as committed: `f24e043` (README.md at f24e043; the line numbers are that file's)

### Line 102
| CDFW surveys, stocking, Wild / Heritage Trout Waters | Each state's own (`troutdata.py`): CT DEEP fish samples, stocking and trout management areas; Vermont's brook trout waters and stocking list; Virginia DWR wild trout streams (classes I–IV) and stocked waters; Georgia DNR designated trout streams, stocking and samples; Wyoming Game & Fish trout-stream classes and native cutthroat waters; Idaho Fish & Game's Yellowstone cutthroat trout streams, as StreamNet's regional fish distribution serves them (the Idaho side of the Jackson map: Teton Valley and Palisades; Idaho publishes no survey or stocking layer); the Pennsylvania Fish & Boat Commission's Class A and natural-reproduction wild trout streams, trout special-regulation areas, stocked sections (fish per species) and stocked lakes; Delaware DNREC's designated trout streams; in the Smokies, North Carolina WRC's mountain trout waters by class (Hatchery Supported and Delayed Harvest, which it stocks, catch-and-release, named Wild Trout Waters; not the game lands' blanket "Wild Trout Waters unless otherwise noted", which covers every creek there), Tennessee WRA's stocking sites, electrofishing samples (1996-2022) and brook trout genetics collections, the national park's own trout distribution map (its "No Fish" code marks unsampled streams and is not used; segments it marks internal are left out) and the Cherokee tribal fishing zones (the Raven Fork trophy section and the Enterprise Waters); in the Adirondacks, New York DEC's categorized trout stream reaches (Wild-Quality, Stocked, Stocked-Extended, with the species and number stocked), the streams classed trout (T) or trout spawning (TS) in the state's water quality standards, and public fishing access along trout streams (DEC's fishing rights easements; DEC publishes no survey layer, and its pond stocking list has towns, not coordinates); plus Trout Unlimited's brook trout patches from New York and Connecticut to Georgia, and iNaturalist (rainbow, brown, brook and cutthroat trout). Each source marks its records of wild brook trout (`wild_brook`: a survey that found them, a water it lists for them), which the size term reads. Outside California a no-trout sample counts for the same creek within 1.5 km only, and only Connecticut's and Tennessee's electrofishing samples make one |

### Lines 939-956
  creek its lake's main outlet starts. Wild brook trout water is sized for brook trout (`BROOK_SCALE`; the user's
  choice, 2026-11-22): its drainage counts six times over, so the credit starts at 0.06 sq mi instead of 0.39 and is
  full from 3.2 sq mi instead of 19. Brook trout live in smaller creeks than the other trout. On the 12 maps, records
  of brook trout sit on creeks draining about a sixth of what records of other trout only do (median drainage at the
  nearest reach): 4.6 against 31 km² for agency surveys, 9.8 against 59 km² for iNaturalist sightings. Wild brook
  trout water is a reach that a designation of wild brook trout covers (any of them, not only the label the map
  shows):
  - a Trout Unlimited / EBTJV brook trout patch;
  - Vermont's brook trout waters;
  - a Virginia wild trout stream or a Pennsylvania Class A stream with brook trout;
  - the Smokies park's brook trout segments;
  - a Wyoming trout stream with brook trout among its game fish.

  It is also a reach where a survey found wild brook trout in the last 10 years and no later survey found none.

  These don't count: stocking lists, iNaturalist sightings (they can't tell wild fish from stocked), New York's
  Wild-Quality class and Connecticut's Wild Trout Management Areas (they name no species). Nothing scores lower, and
  other creeks are unchanged.

## The write-ups of the morning of 2026-11-23, as committed: `b283368`, `dfa1ccc`, `8d5ee8d`, `e0b3961`, `c983984` (README.md at f6fc38e; the line numbers are that file's)

### Lines 128-131
Only one conditioning step (03, 03b) runs at a time across chains: `run_base.sh` and `run_rebuild_a.sh` take
`data/.hydro.lock` (`scripts/hydrolock.sh`). A driver that is stopped (Ctrl-C, `kill`, a closed terminal) stops its step
and lets the lock go; one killed with `kill -9` can't, and the next chain takes the lock over once that driver and its
step are gone.

### Lines 202-218
   Since 2026-11-23 a flat of filled ground drains along NHD HR's lines instead of resolve_flats' shortest ways,
   which drew ruler-straight lines across it (the Leicester River across the Otter Creek wetland). A flat qualifies
   with 10 or more cells, half of them or more raised 5 cm or more by the fill: a swamp, a wetland, a valley flat
   behind a sill. `flatlines.py` does it in 03, and in the pieces 03b conditions again at seams. The water runs
   along the StreamRiver, ArtificialPath and Connector lines, named ones first, to the flat's outlet. A line that
   leaves the flat over a rim 0.5 m high at most, and comes down below it within 200 m, takes the water out there.
   That holds only where the water, followed on the finished surface, stays within 40 m of the line for 80 % of the
   next 200 m; without that test a crossing sent 19 km² of Alder Brook's headwaters to the Lamoille. An outlet NHD's
   line passes a few cells off, and a line broken by a hummock the fill left, are joined to it within 100 m. Cells
   within 100 m of a walked line take the shortest way to it. Farther ones keep resolve_flats' order, so no new
   straight way appears away from NHD's lines. Every other cell keeps its value, and `dem_filled.tif` and
   `fill_depth.tif` don't change. Measured on all 12 maps before it went in (`data/stream_burning/`):
   straight runs over filled ground 31.0 → 26.0 mi (fish 60+ 9.5 → 5.1); NHD lines the routing misses
   1,765 → 1,700; gauges within 10 % 419 → 423 of 516; no drainage moved across a divide. A pond is a filled flat
   too, so its water now follows NHD's path through it. That moves where the pond's links split, and with them the
   size floor's three-point vote (5.). 11 lake outlets the maps drew before are no longer drawn, and a 29 m creek
   head at Frank Pond became part of its pond's reach; both are listed in `data/stream_burning/README.md`.

### Lines 320-323
   named swimming holes, and features named for falls, cascades or potholes that sit on a stream; pools in a creek
   (water=stream_pool) and swimming spots, named or not, an unnamed one kept only on a creek and not within 60 m of a
   lake; the saved answer is keyed by the query's hash as well as the box, so a changed query is fetched again);
   NHD waterfall points;

### Lines 326-330
   (Smokies); Overture Maps places, strictly (2026-11-23; its waterfall category or a swimming-hole name, on an NHD
   creek and not by a lake, and only where no other source has a fall within 1 km or a fall of that name within 25 km:
   Overture repeats well-known falls miles off), from `data/raw/<area>/_shared/overture_places.csv`, which
   `audit/scripts/completeness_overture.py` writes with each Overture release (the maps credit Overture, its licences
   and Foursquare's notice); and the hand-researched falls in

### Lines 333-334
   (Chester, Strong & Ayers), Google Maps listings looked up by hand (2026-11-22/23, the user's permission for academic
   use; source "Google Maps") and others, each row with its source page and a note on how its point was placed. One fall

### Lines 338-339
   Moss Glen Falls); a name with or without a final s, or with its words run together, is the same name (Beldens /
   Belden Falls, Juneywhank / Juney Whank Falls). `precise` marks points on the fall itself (OSM, NHD, CDFW, guidebook GPS at the fall): only those

### Lines 795-802
The Blue Ridge Parkway's closures (Lexington, the Smokies; 2026-11-23) come from the park's table of milepost
sections: a section is closed when its Status says Closed, and in an open one only the milepost ranges its notes call
closed ("CLOSED: MP 63.5 - 63.9 around the James River Bridge"); a closed campground or picnic area closes no road.
Each closure is laid on the Parkway mile by mile between the park's milepost points, and a mile is kept only where a
road between them is about as long as the mileposts say. OSM tags the James River bridge as under construction (02
downloads no such ways): routed round it, the 61.4-66.3 section had also closed 4.2 km of US 501 and 3.4 km of Elon
Road (Peters Creek: a 106 min drive, now 39).


### Lines 916-926
  map scored 0.15. Outside California, where the flow is NHDPlus's mean flow with no drying in it, a borrowed estimate
  (scaled from another creek) never reads drier than that typical value either, and one on a creek NHD has no line
  along that still reads mostly dry shows NHD's label, as a reach with no estimate does (`scoring.borrowed`, since
  2026-11-23): floored at NHD's class alone, 103 drawn pieces (61 mi) had read "mostly dry" where the maps said "NHD
  unmapped", among them a piece of a creek in the Champlain lowland (44.5371, -73.4192) between pieces NHD maps
  perennial that read year-round. In LA, whose natural flows see creeks dry up, NHD's class stays the floor: the
  area's typical value mixes mountain creeks with desert washes, and lifting LA's borrowed estimates to it put 19
  more two-class jumps along its creeks and read two dry gauged creeks wet (Temescal Wash at Corona Lake, Castaic
  Creek below Castaic Lake). Left: 79 LA pieces (46 mi) that read "NHD unmapped" before 2026-11-22 read "mostly dry"
  on the same scores; the rules before then threw away only an estimate borrowed through a lake, from another box or
  from an off-map lake, and `05b_flow.py` doesn't yet record which kind a borrowed estimate is.

### Lines 1163-1164
(natural ponds; this keeps the 2.5-acre brook trout ponds). A lake a state lists is kept at any size, and a named pond
down to a quarter acre (0.1 ha, `NAMED_MIN_HA`; 2026-11-23: 359 more ponds, 153 of them in North Georgia).

### Lines 1170-1171
  access, rules and designations, and its own list of trout lakes: NCWRC's impoundments and PFBC's and CT DEEP's
  stocked lakes as outlines, New York DEC's stocking list and lake fishing list from data.ny.gov). New York's stocking and lake-list
