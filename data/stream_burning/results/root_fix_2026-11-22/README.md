# The lake-outlet fix of 2026-11-22: results

The account is in `data/stream_burning/README.md`, "Both faults fixed at the root". The 12 scratch builds were
measured against the published copy d16a885; the rebuilt maps (commit f337bfb) equal them in every routing file and
every drawn line, so the scratch tables hold for the rebuilt maps too. Fish scores differ on three Adirondack maps
by the lake term of 52c2139, which the scratch builds didn't have.

- `summary_scratch.txt`, `summary_project.txt`: every acceptance check by map (scratch against site d16a885, the
  rebuilt maps against site 4315299).
- `by_map_scratch.md`: per map, the lakes whose outlet moved and the ten largest stretches of line gone and new.
- `putin_12_maps.csv`: `checks/putin.py` on the rebuilt maps, every lake with a link (equal to the scratch table).
- `rule_tally.csv`, `name_vs_nhdplus.csv`: which step of the rule decides each lake (`checks/rule_tally.py`,
  `checks/name_vs_v.py`).
- `kept_lakes.txt`: the 12 lakes left at the terrain's cell, with the DEM along NHD's line.
- `two_outlet_lakes.csv`: the 61 lakes with several outflow lines the terrain takes on.
- `drainage_moves.csv`: every drawn line whose drainage changed by 1 km2 and 30 % or more against site 4315299,
  with the lake behind it where one was found (`checks/drainage_moves.py`, `checks/attribute_moves.py`).
- `lost_water.txt`: the reaches scoring 10+ lower because a lake's water left them, by lake (scratch).
- `gauges_d16a885_vs_scratch.txt`, `nhdplus_points_d16a885_vs_scratch.txt`: the overview session's comparisons of
  the audit's drainage tables; the rebuilt maps give the same output line for line.
- `nhdplus_worse_with_reasons.csv`: the 35 NHDPlus points that read worse, each with its reason.
- `flagged_outlets.csv`: the 16 NHD lake outlets no longer drawn, each with what the map has there.
- `falls_changed.csv`: the six known falls whose nearest drop changed.
