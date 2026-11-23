# Audit of the stream maps, 2026-11-22

**What was audited.** The live site at commit `d16a885` (published 2026-11-21 23:47, all 12 areas), the code that
built it (`8bdf945` on main), the docs, and the site as it stood before that publish (`6875118`) for comparison.
Numbers are for the live site unless they say otherwise; its 12 `map3d_data.js` files are byte-for-byte the build I
measured.

**How.** I measured what the maps state against data in the project that the value was not derived from: NHD's
stream lines, USGS gauge records and their site drainage areas, NHDPlus, the trout survey records, measured water
temperatures, the known-falls lists, NHD's lakes. Five read-only helpers read all the code and docs; I spot-checked
what they found before using it. Nothing in `scripts/`, `data/`, `output/` or `publish/` was changed; nothing was
built, committed or pushed. Scripts, tables and the helpers' notes are in `audit/` (section 7).

---

## 1. Summary

**What is right.** The streams are where they should be. Every named creek NHD maps that drains 0.39 sq mi or more is
drawn, a median 23-36 ft from NHD's line. Names agree with NHD on 99.6-99.9 % of miles. Drainage areas match USGS
gauges within 10 % at 84 % of 499 gauges. Elevation, canopy and sun hours in the popups reproduce their sources, the
fish score reproduces from its own table, and the "± °F" on water temperature is an honest error figure. No script
calls USGS WaterServices any more.

**What is not**, most important first: can it be reached, does it hold water, is the creek there; then the score,
the code, the site and the paperwork. The table is the one-page version; the same fifteen follow in a few lines each.

| # | What is wrong or wasteful | How big | Where | Fix, and the step a rebuild starts from |
|---|---|---|---|---|
| 1 | Approach times and remoteness include the build day's road closures, winter gates too | Jackson: 666 reaches start at a winter gate; Smokies 5 roads, Vermont and Lexington 1 each | `08_hike.py:64-68`, `09_drive.py:58-63` | open-season network, closures as a dated note; `08_hike` |
| 2 | Outside LA the flow class is a drainage cut: "year-round" nearly everywhere, too low in NE Connecticut | 94-99.6 % year-round on 10 maps; 669 perennial Connecticut reaches shown lower | `05b_flow.py:470-477`, `flowlib.py:369` | show NHD's doubt; lift NHD-perennial creeks; `05b_flow` |
| 3 | LA's flow class contradicts trout records and flips along one river | 81 reaches with trout shown dry; 205 flips, 90 mi | `scoring.py:224-237` | trout record sets a floor; rule per creek; `05b_flow` (LA) |
| 4 | Rivers fed from outside the map are too small | 169 river points under half size; Chattooga 37 % short, French 59 % | `crossbox.py:30`, `:451`, `:586` | carry NHDPlus's total at every crossing; `04_knickpoints` |
| 5 | The 0.39 sq mi floor hides named headwaters | 2,894 named miles, 26 % of the Smokies'; 98 trout records | `05_score.py:12` | your call; `05_score` |
| 6 | The map step rewrites the streams, so tables and map differ | 15,160 reaches clipped, 1,138 lines added, 9,122 re-ordered; 56,033 mi against 50,526 | `06_map.py:84-283`, `:687-945`; `03b_stitch.py:428`, `:578` | close the outlet gap, one set of lakes, then delete the repairs; `03b_stitch` |
| 7 | The score marks water down on thin evidence | 267 reaches halved by one sample, 364 by a failed look-up, 3,462 burned with no severity | `scoring.py:199`, `:224-226`, `:124` | your calls; `06_map` |
| 8 | Two lake-routing faults are live | 31 and 77 lakes | `crossbox.py:335`; `03b_stitch.py:552-556` | outlet from NHD's line; `03b_stitch` |
| 9 | A new area needs hand work in a dozen places | 4 tables by area, 12 name overrides, 15 caches keyed by name, 17 one-place rules | `config.py`, `05d_lakes.py:42`, `02f_known_falls.py:45` | section 4; none yet |
| 10 | A published map cannot be tied to its code; failures pass quietly | tonight: 2 scripts edited mid-build, all 12 maps redrawn outside the logs | `run_base.sh:19-20`, `geomatch.py:18` | build stamp, publish guard; none |
| 11 | Licences | NY DEC on 4 pages; 222 + 695 + about 85 falls | `troutdata.py:490-527` | your call; `02f_known_falls` / `11_context` |
| 12 | The website is a third bigger than it needs to be | 636 MiB; about 250 MB to save | `06_map.py:953-992`, `:1221`, `:1531` | numbers instead of sentences, one shared file; `06_map` |
| 13 | The checks disagree and read tables; the README's recipe is broken | 3 flow-drop checks, 14 wrong statements | `README.md:651-659` | a standing set; a state file; none |
| 14 | Small wrong labels | "order 7" on 520 lines, 3,601 dead lake links, 142 "-0 min" | `06_map.py:98-101`, `maplakes.py:225` | one commit; `11_context` |
| 15 | Not checkable from inside the project | drive and hike times, drop heights, small-creek water outside LA | | data named in section 2 |

**1. Approach times and scores carry the build day's road closures, winter gates included.** Jackson, built
21 November: 666 of 10,578 reaches (557 at fish 60+) start at a winter gate; Cascade Creek (43.76524, -110.74842)
reads "park at Teton Park Road → bike 57 min on closed roads → hike 48 min". The Smokies have five park roads shut for
the winter, Vermont and Lexington one each. Remoteness is a quarter of the score, so those reaches also score high.
*Where:* `08_hike.py:64-68`, `09_drive.py:58-63`; the `long_term` flag `07_road_closures.py` makes is read by nothing.
*Fix:* time the approach on the open-season network and show today's closures as a dated note (decision 1).
*Rebuild from* `08_hike`.

**2. Outside LA the summer-flow class cannot say anything but "year-round".** It is NHDPlus's mean flow times a
yearly index, which has no drying in it: in effect a drainage cut at 0.12-0.27 sq mi, under the map's own floor.
94-99.6 % of drawn miles read year-round on ten maps; NHD calls 46 % of Jackson's year-round miles intermittent or
unmapped, 39 % of Lexington's, 32 % of the High Peaks'. In NE Connecticut the cut sits at 0.93 sq mi and works the
other way: 669 NHD-perennial reaches (439 mi), 398 with trout on record, read below year-round and lose score. The cfs
figure runs 3x high on small Vermont creeks and 7x in Tallulah Gorge. *Where:* `02b_download_flow.py:201-232`,
`05b_flow.py:470-477`, `flowlib.py:369-384`. *Fix:* keep the class (it errs the way you asked) but show NHD's doubt
beside it; lift NHD-perennial creeks in Connecticut and Vermont (decision 2). *Rebuild from* `05b_flow`.

**3. In LA, where the class does carry information, it contradicts trout records and flips along one river.** Trout
were recorded since 2016 on 81 reaches (53 mi) shown mostly dry or seasonal (Arroyo Trabuco, 33.6005, -117.6313:
"mostly dry, 0.0 cfs"). 145 mi NHD maps perennial read mostly dry. The bare-channel rule is decided reach by reach:
the Santa Clara River flips about twenty times (205 sudden changes, 90 mi). The cfs figure is within 2x of the gauge
at 46 % of 28 gauges. *Where:* `scoring.py:224-237`. *Fix:* a trout record lifts a reach to "usually flows"; decide
the bare-channel rule per creek between confluences (decision 3). *Rebuild* LA *from* `05b_flow`.

**4. Rivers whose headwaters lie outside the map are drawn too small.** Against USGS gauges the popup's drainage is
37 % short on the Chattooga at Burrells Ford (29 against 47 sq mi), 59 % on the French River (CT), 35 % on Vermont's
Green River, 25 % on the Independence. At 169 of 4,806 NHDPlus points of 39 sq mi or more no drawn line has half the
drainage (LA 81, Jackson 19, Adirondacks south-east 19, NE Connecticut 12). *Where:* `crossbox.py:30`, `:451`, `:586`
(an outside river must bring 3.9 sq mi and a quarter of the total). *Fix:* carry NHDPlus's total at every stream
crossing the outer edge. *Rebuild from* `04_knickpoints` (`SKIP_03B=1`).

**5. The 0.39 sq mi floor leaves out named brook-trout headwaters.** 2,894 of 23,242 named NHD stream miles are not
drawn: 26 % in the Smokies (about 300 named branches missing whole), 12-13 % in North Georgia and NE Connecticut.
98 of 2,880 trout-found records sit on undrawn water. *Where:* `05_score.py:12`. *Fix:* your call (decision 4).
*Rebuild from* `05_score`.

**6. The drawing step still rewrites the streams, so map and tables disagree.** `06_map.py` clips 15,160 reaches at
lake shores, hides 8,614, adds 1,138 lines (137 mi), re-values 1,123 pieces, raises the order of 9,122 and bridges
949 dams. Tables: 56,033 mi, 26,697 at fish 60+; map: 50,526 and 25,112. None of this went away with the root fixes
of 21 November. *Where:* `06_map.py:84-283`, `:687-945`; behind it a one-cell gap at every lake outlet
(`03b_stitch.py:428`, `:578`) and two different sets of lakes (`flowlib.py:187-207` against `05d_lakes.py:42`).
*Fix:* section 3.1. *Rebuild from* `03b_stitch` (`SKIP_03=1`).

**7. The fish score marks water down on evidence that is not near-certain.** One empty sample within 0.9 mi halves a
reach even inside designated trout water: 267 reaches, 117 of them designated (`scoring.py:199`). A failed flow
look-up scores "unmapped" 0.15: 364 reaches outside LA at 8-20 beside neighbours at 60+ (`scoring.py:224-226`). An
unmapped burn severity counts as the worst: 3,462 of 4,061 burned reaches (`scoring.py:124`). The new lake term takes
10+ points from 133 mi of drawn Adirondack creek, 125 mi of it with a trout record; measured sites support it within
650 ft of the pond (29 mi) and about half of it further down (section 2.6). Outside LA the score is mostly stream size, remoteness and whether
a record exists. *Fix:* decision 5. *Rebuild from* `06_map`.

**8. Two lake-routing faults are live** (found by the other sessions, still open). 31 lakes put their water back in
650 ft or more from the outlet (Seventh Lake's outlet creek is not drawn); 77 lakes drain to a cell 1,000 ft or more
from NHD's outlet (Raquette Lake 5.7 mi). *Where:* `crossbox.py:262`, `:335`; `03b_stitch.py:552-556`. *Fix:* take
the outlet from NHD's line leaving the lake; same batch as 6. *Rebuild from* `03b_stitch`.

**9. A new area does not "just work".** It needs hand-laid boxes whose edges dodge lakes, four tables keyed by area
(`02f_known_falls.py:45`, `05d_lakes.py:42`, `lake_bathymetry.py:424`, `scoring.py:153`), per-state adapters, 12 name
overrides (`05c_drainages.py:46-76`), and caches cleared by hand after an edge moves (15 families keyed by box name).
17 rules were made for one named place and never measured on all areas. LA wording ships elsewhere: 178 New York
trail pieces read "CA State Parks". *Fix:* section 4. *No rebuild* until the pieces land.

**10. Nothing ties a published map to the code that built it, and failures pass quietly.** Tonight two scripts were
edited while areas were building, every map was drawn again by hand outside the logs, and the code was committed
after the build; it came out consistent, but only file times show it. Two drivers carry on after a failed hydrology step
(`run_base.sh:19-20`, `run_rebuild_a.sh:22-23`); an Overpass time-out is cached as a full answer (`geomatch.py:18`).
*Fix:* a build stamp in every output; publish refuses mixed or uncommitted builds. *No rebuild.*

**11. Licences.** New York DEC's ArcGIS layers are on the four Adirondack pages (unlinked, public), against your
data.ny.gov rule (`troutdata.py:490-527`, `geomatch.py:76`). 222 falls from two sites that forbid redistribution
await consent; 695 from a site with no licence went out without asking its author; about 85 more have no terms on
record. Sentinel-2 is uncredited. *Fix:* decision 6. *Rebuild from* `02f_known_falls` or `11_context` if pulled.

**12. The website can lose about a third of its size with nothing removed.** 636 MiB of 1 GB. 62 MB is three
sentences on every reach that hold 9 MB of numbers; the 3D page (114 MB) is nearly all a second copy of layers the
2D page carries; 13 MB is reaches written twice. *Where:* `06_map.py:953-992`, `:1221-1223`, `:1531-1538`.
*Fix:* section 3.7. *Rebuild from* `06_map`.

**13. The checks disagree with each other and read the tables, not the map; the README's build recipe is broken.**
"0 flow drops in all 12" and seven flow drops were logged the same day by different scripts; I count 269 sudden
changes on the drawn maps. `README.md:651-659` fails on a clean checkout; 14 statements are wrong today; the log is
314 KB with 39 open items scattered through it. *Fix:* a standing set of checks on the drawn data (3.6); a short
state file (3.8). *No rebuild.*

**14. A batch of small wrong labels.** In the Adirondacks south-east 520 of the 564 lines draining 100 sq mi or
more are "order 7" and order 6 is 11 small creeks (`06_map.py:98-101`); "hike -0 min" on 142 reaches; "Outlet creek profile" opens nothing for 3,601 of 7,450 lakes
(`maplakes.py:225`); the dry-lake edge never draws (`maplakes.py:253`); five Wyoming streams the state lists as
troutless are labelled native cutthroat water (`troutdata.py:262-264`); gauge times are Pacific on every map.
*Fix:* one commit. *Rebuild from* `11_context`.

**15. Three things could not be checked at all.** Drive and hike times (nothing independent in the project); drop
heights and whether an "unmapped" drop is real (the terrain alone finds 44-76 % of known falls); whether a small
creek outside LA holds water in August. Section 2 says what data would settle each.

---
