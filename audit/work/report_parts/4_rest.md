## 4. Making a new area "just work"

You asked during the audit that naming a new location should be enough, with no round of one-off fixes each time.
This is where the code stands against that, and what would get it there.

### 4.1 What a thirteenth area needs by hand today

| Hand work | Where | What happens if it is skipped |
|---|---|---|
| A config entry: UTM zone, home point, boxes with coordinates, the HU4 codes each box needs, trail name and pattern, relief threshold, source switches | `config.py:54-359` | nothing builds |
| Box edges placed so that none cuts a lake, a reservoir's filled flat, or a river twice | by hand; the scripts that scored the Adirondack edges exist only as a description in the log | water strands on the edge; cost two Jackson rebuilds and the Raquette fix |
| The area's states | `02f_known_falls.py:45-49` | no GNIS waterfalls, with a note in a log |
| The area's smallest lake size | `05d_lakes.py:42-43` | no lakes layer at all |
| Depth-survey adapters; typed-in depths | `lake_bathymetry.py:424`; `lakedata.py` | no measured depths |
| A trout adapter per state, a lake-source adapter per state, a closure feed per state | `troutdata.py` (14), `lakesources.py`, `07_road_closures.py` (12 switches) | the area builds with national sources only (iNaturalist, GBIF, Trout Unlimited patches in the East) |
| Tailwater dams with a river name and an elevation; diversions with a gauge | `scoring.py:153-166`; `flowlib.py:393-402` | cold tailwaters read warm; bypassed reaches read the whole river |
| Drainage and fork name overrides | `05c_drainages.py:46-76` (12 entries so far) | a tributary's name on a river's basin |
| The profile page copied from `output/la/` | `run_late.sh:25` | done by the driver |
| After any change to a box edge: clear the caches keyed by box name | 15 cache families (3.5) | the old extent stays in use, silently |
| Three drivers in order, then the overview, the one-file map, the phone copies and the publish | `run_base.sh`, `run_mid.sh`, `run_late.sh`, `13`, `14`, `phone_sync.sh`, `publish_site.sh` | |
| The checks after a routing change, by hand | six in the memory notes, more in scratch folders | misses that you then catch on the map |

### 4.2 What each new area cost, from the log

Seventeen rules in the code were made for one named place and never measured on all areas before they were applied
everywhere (`audit/work/docs_log.md`, section 3): the 0.9 mi reach of a no-trout sample (Connecticut pilot), the
68-77 °F temperature window (LA's trout records), the built-channel name rule (the Pacoima channel), the 5-acre
level-water test (Devil's Gate), the 0.8 sq mi drainage merge (Pacific Creek), the dam-join distances (a pond beside
Salacoa Creek), the tailwater floor (Piru Creek), and ten more. One of them, the split-channel flags written for
SE Pennsylvania, moved 68 LA scores the wrong way before it was fenced off to non-LA areas. Ten fixes were made in the
drawing step, each for a view you reported, and are still there (3.1).

### 4.3 LA's wording and constants that ship in the other areas

- 178 New York state-park trail pieces are labelled "CA State Parks", and long agency names are cut at 40 characters
  ("New York Department of Environmental Con" on 4,214 pieces) (`06_map.py:1069-1075`).
- "Trails & PCT ©" is the credit on all eleven maps with no Pacific Crest Trail (`map_drainages.js:512`,
  `map3d.html:318`); the trail file is still `pct.gpkg`.
- The drawing scale is typed in for 34° N (`map_drainages.js:12`, `map3d.html:203`); at 44° N it is 13 % off.
- The fish-score diagram says "TNC flow model" and LA's hottest trout record in every area.
- The heat gate's 84 °F start comes from LA's hottest trout record plus 3.6 °F (`scoring.py:135`); the burn penalty
  from LA's debris-flow canyons; the off-trail walking speed from chaparral (`08_hike.py:35`); the closure filter from
  LA's mountain highways (`07_road_closures.py:38-43`).
- The docstrings of `09_drive.py`, `13_overview.py`, `14_portable.py` and the README's first screen still describe
  LA and "six areas".

### 4.4 What would get there

1. **An area is a name, an outline and a home point.** The UTM zone, the HU4 codes and the states follow from the
   outline (the state outlines are already downloaded for Vermont's clip).
2. **The code lays out the boxes.** A layout step tiles the outline to what the Mac's memory can condition and moves
   each edge off lakes, filled flats and river meanders, by the scoring that was done by hand for the Adirondacks and
   Jackson. Better still, cut along watershed lines, so that no edge crosses water at all.
3. **Water from outside is always carried**, from NHDPlus's total at every stream crossing the outer edge, without
   the 3.9 sq mi and one-quarter thresholds.
4. **One definition each of lake, outlet and reach** (3.1). Most of the one-off drawing fixes were for these three.
5. **Rules that read the data, not a list of places.** Below any dam holding half a reach's drainage: treat as
   dam-fed (no temperature penalty from the fit, flow from a gauge where there is one), instead of a hand list of six
   dams. Diversions: the gauge rule already works anywhere; add NHD's canal take-offs. Names: follow NHDPlus's main
   path over the whole area instead of a vote per box, which is what the 12 overrides patch.
6. **State sources as plug-ins with a stated fallback.** An adapter lists the values it accepts; anything else is
   left out and reported. Today the adapters list what to drop, so a new value becomes trout water by default: that
   is how "No trout documented" patches in New York, "Brown & rainbow trout only" patches and five troutless Wyoming
   streams got trout labels.
7. **No per-area constants without a rule.** One smallest lake size, or one derived from the lake-size curve. The
   relief threshold from the area's own relief. The drawing scale from the latitude. Page text from the area's
   config, with no state or trail name typed into the scripts.
8. **Caches keyed by extent and request**, with one helper (3.5).
9. **One driver, a build stamp, and the standing checks run at the end of every build**, with the publish step
   refusing a build whose checks did not pass or whose code was not committed.
10. **A new-area test.** Keep one small box somewhere the pipeline has never seen and build it from nothing in a
    scratch clone whenever the pipeline changes. If it needs an edit to finish, that edit is the bug.
11. **Measure every rule change on all areas before it is installed**, with the standing checks, and record in the
    state file which areas it was measured on. That is your existing rule; the log shows it kept about half the time.

---

## 5. Proposed order of fixes

Each batch is one commit and one rebuild from the step named. Cheap and visible first; the routing last because it
is the largest and the others do not depend on it.

| Batch | What | Findings | Rebuild from | Size |
|---|---|---|---|---|
| 0 | Build stamp in every output and in the map's footer; publish refuses uncommitted or mixed builds; drivers stop on a failed step; lock clean-up; Overpass `remark` test; the standing checks wired into one command; README build block replaced by the drivers | 10, 13 | none | small |
| 1 | Label fixes: order table, "-0", outlet profile link, dry-lake edge, lake fish label, "conflicts", trout label allow-lists, gauge and closure time zones, "CA State Parks", credits (OpenStreetMap on the all-areas page, Sentinel-2, GBIF), lower Piru's dam | 14, 11 | `11_context` (labels), `06_map` | small |
| 2 | Fish-score decisions (decision 5) and the flow wording (decision 2) | 2, 7 | `06_map` | small once decided |
| 3 | Access: open-season network with dated closures; open forest tracks driven; trail grade for walking; rivers as barriers; parking layer for starts; bike flags for the three missed cases; boxes timed together | 1 | `08_hike` | medium |
| 4 | Flow: one "never below NHD's class" rule in place of five; the trout-record floor; bare channel per creek; Connecticut and Vermont perennial creeks; October 2026 flows | 2, 3 | `05b_flow` | medium |
| 5 | Rivers from outside the map; the size floor (decision 4) | 4, 5 | `04_knickpoints` (`SKIP_03B=1`) | medium |
| 6 | Routing: outlet from NHD's line, no pit gap, one lake set, reaches cut at the drawn shores, score and order and drainage names computed before the map step; then delete the repairs in `06_map.py`, `crossbox.py`, `05b_flow.py`, `05c_drainages.py` | 6, 8 | `03b_stitch` (`SKIP_03=1`) | large; scratch clone on one small area first |
| 7 | Website: sentences from numbers; one shared file for every layer; reaches written once | 12 | `06_map` | medium; check pixels as on 20 November |
| 8 | New-area work: layout step, cache helper, one driver, adapters, text from config, the new-area test | 9 | none, then one full build of a test box | large |
| 9 | Docs: state file, archived log, shorter README; delete what 3.4 lists | 13 | none | small |

Batches 1, 2 and 7 all end in `06_map`; they can share one rebuild if they are ready together.

---

## 6. Decisions for you

1. **Approach times.** Show the open-season approach (drive the park roads that are only shut for winter) with
   today's closures as a dated note, or keep "as of the build day"? Either way the line should carry its date.
2. **Summer flow outside LA.** Keep "year-round" on every creek and add NHD's doubt beside it, or leave the class
   off where the model cannot tell? And in NE Connecticut and central Vermont: lift NHD-perennial creeks to
   year-round (834 reaches)?
3. **LA flow.** May a trout record since 2016 lift a reach to "usually flows" (81 reaches)? It changes the water
   term, which the notes say is yours to decide.
4. **The size floor.** Keep 0.39 sq mi everywhere, lower it in the humid areas (the undrawn named stretches are 55 %
   between 0.1 and 0.39 sq mi), or draw every stream NHD names?
5. **Fish score.**
   - a. One empty sample halves the score. Drop it, require two samples, or at least let a trout designation win?
   - b. No flow estimate: use a neutral value instead of NHD's "unmapped" 0.15 (364 reaches outside LA)?
   - c. Burn: apply outside LA at all? Treat unmapped severity as the worst (3,462 reaches)?
   - d. Size and remoteness: is "big and far from a road" what the score should mostly say in the wet areas, or
     should wild brook-trout patches be scored on their own terms?
   - e. The Adirondack lake term: give it distance below the pond (what the measured sites support: stronger within
     650 ft, about half beyond), exempt creeks with trout records (which takes it out of the score on 94 % of the
     miles it marks down, the warm outlets included), or leave it?
6. **Licences.**
   - New York DEC's ArcGIS layers on the four Adirondack pages: pull them (the pages stay public though unlinked), or
     ask DEC?
   - World Waterfall Database and nnywaterfalls.com: how long to wait for an answer before pulling 222 falls?
   - gawaterfalls.com: ask the author, as was done for the other two?
   - The other guide sites (about 85 falls) and the Apple Maps point: read their terms, or replace the points?
7. **Website.** Drop the colour-relief pictures (40 MB, off by default)? Squash the map history (needs a force-push)?
8. **Disk.** Delete `data/backup_*` (3.9 GB) and the 55 unused `hike_minutes.tif` rasters (3.0 GB)? Run `git gc` in
   the site clone (frees about 2 GB)?
9. **Docs.** Replace the growing log by a state file plus an archive?
10. **Areas.** Rectangles with smarter edges, or areas cut along watershed lines (a bigger change, and the end of
    edge problems)?

---

## 7. What is beside this report

`audit/scripts/` (all read-only on the project; `common.py` explains the environment variables):

| Script | What it measures |
|---|---|
| `run_all.sh` | every measurement below on one set of maps, about 5 minutes |
| `provenance_steps.py` | each step's start time against the file times of the code it loads |
| `streams_vs_nhd.py` | drawn lines against NHD's: missing, extra, offset |
| `area_vs_reference.py` | popup drainage against USGS gauges and NHDPlus |
| `flow_vs_gauges.py` | flow class and cfs against gauge records; class against NHD's label |
| `drawn_jumps.py` | sudden changes along a drawn creek |
| `popup_checks.py` | names, elevation, gradient, canopy, sun, access values |
| `fish_score_audit.py` | the score taken apart; rules that lower; trout on record with a low score |
| `falls_lakes_checks.py` | drops against known falls; lakes against NHD |
| `watertemp_vs_sites.py` | popup water temperature against measured readings |
| `extra_tables.py` | table against map, trout records on water shown dry or not drawn, NHD-perennial creeks shown drier, score against survey results, lakes missing |
| `lake_term_test.py` | the Adirondack lake term against measured sites, by distance below the pond, pond size and trout record |
| `draw_through_test.py` | what `06_map.py`'s draw-through still adds, by kind of link |
| `map_rules_from_logs.py` | what each rule of `06_map.py` still changes, from its own log lines |
| `code_inventory.py` | unused names, duplicate functions, area switches, driver steps |
| `popups.py`, `common.py`, `report_tables.py`, `build_report.py` | shared: popup parser, loaders, the tables in this report, and its assembly from `audit/work/report_parts/` |

`audit/tables/live_d16a885/`: every table for the live site, per gauge, per reach or per area as named in the text.
`audit/tables/before_6875118/`: the same for the site before tonight's publish. `audit/tables/*.csv`: the code
inventory and the map-step counters.

`audit/work/`: the five helpers' notes, with `file:line` for everything they found (`code_core.md`,
`code_map_lakes.md`, `code_sources.md`, `docs_readme.md`, `docs_log.md`), and my running log (`findings_log.md`).

**Checked twice.** After the report was written the whole set was run once more, end to end, on the site clone
itself (`audit/tables/verify_site_clone/`): all 32 tables came out identical to `live_d16a885/`.

**Limits of this audit.** The reach tables behind the live site were read from a snapshot taken when the build
finished; six areas' tables for the earlier site were saved before the rebuild overwrote them, the other six were
not. The helpers' counts on published files were spot-checked, not all redone. Nothing was built, so every "would
remove" in section 3 is from reading the code and its logs, and needs the scratch-clone run named in batch 6 before
anything is deleted. Screenshots of the map did not capture the stream lines in the browser pane, so the rendered
map was checked through the page's own loaded features, which matched the data file.
