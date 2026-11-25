"""Step 0: what an area's settings are, worked out from its outline (derive.py), for config.py.

Writes data/derived/<area>/_shared/area.json: the UTM zone holding most of the outline, the boxes (for an area given
only an outline, one box around it), each box's NHD 4-digit units (WBD), the states it reaches into, the area-specific
sources whose coverage it meets (sources.py), the lake depth surveys and state lake lists that cover it. config.py
fills in from this file whatever the area's entry leaves out; a value the entry gives by hand wins, and this step
prints every way the worked-out value differs from it (for the 12 maps of 2026-11-22 that list is the agenda of the
new-area plan's B2; for a new area there is nothing to compare).

    AREA=fryingpan python 00_area.py
It downloads (the WBD service, once per box extent; the state outlines once). If that fails for an area whose entry
gives every value by hand, it says so and the build goes on with the hand values; for any other area it stops.
"""
import json, os, sys
os.environ["AREA_SETUP"] = "1"          # config.py loads an area with no worked-out settings yet
import config
import derive, sources

AREA = config.AREA
entry = config.AREAS[AREA]
by_hand = all(k in entry for k in ("crs", "ranges", "sources")) and all("hu4" in r for r in entry["ranges"].values())
try:
    got = derive.settings(AREA, entry)
except (RuntimeError, OSError) as e:     # netfetch's FetchError / NetworkDown, a file that can't be read
    if not by_hand:
        raise SystemExit(f"{AREA}: settings not worked out ({str(e)[:200]}); the area has no hand values to fall back on")
    print(f"NOTE {AREA}: settings not worked out ({str(e)[:160]}); the hand values in config.py are used as always")
    try:        # what can be worked out without the failed download (the state outlines may be what failed)
        got = derive.settings(AREA, entry, need_hu4=False) if not isinstance(e, OSError) else None
    except (RuntimeError, OSError):
        got = None
    if got is None:
        sys.exit(0)
got["gnis_states"] = got["states"]
got["lake_states"] = tuple(s for s in got["states"] if s in sources.LAKE_LISTS)

# ---- what differs from the values given by hand ----
diff = []
if "crs" in entry and entry["crs"] != got["crs_derived"]:
    diff.append(f"crs: EPSG {entry['crs']} by hand; {got['crs_derived']} holds most of the outline")
for k, r in entry.get("ranges", {}).items():
    if "hu4" in r and "hu4" in got["ranges"][k] and set(r["hu4"]) != set(got["ranges"][k]["hu4"]):
        add, gone = sorted(set(got["ranges"][k]["hu4"]) - set(r["hu4"])), sorted(set(r["hu4"]) - set(got["ranges"][k]["hu4"]))
        diff.append(f"hu4 of {k}: {', '.join(r['hu4'])} by hand; WBD adds {', '.join(add) or 'none'}, "
                    f"drops {', '.join(gone) or 'none'}")
if "sources" in entry and set(entry["sources"]) != set(got["sources"]):
    add, gone = sorted(set(got["sources"]) - set(entry["sources"])), sorted(set(entry["sources"]) - set(got["sources"]))
    diff.append(f"sources: the coverage tests add {', '.join(add) or 'none'}, leave out {', '.join(gone) or 'none'}")
for kind in ("gnis_states", "bathymetry", "lake_states"):
    if AREA in sources.HAND[kind] and set(sources.HAND[kind][AREA]) != set(got[kind]):
        hand = sources.HAND[kind][AREA]
        diff.append(f"{kind}: {', '.join(hand) or 'none'} by hand; worked out {', '.join(got[kind]) or 'none'}")
print(f"{AREA}: zone EPSG {got['crs_derived']}; states {', '.join(f'{s} ({km:,.1f} km2)' for s, km in got['states_km2'].items()) or ', '.join(got['states'])}")
for k, r in got["ranges"].items():
    print(f"  box {k}: {r['bbox']} hu4 {', '.join(r.get('hu4', ())) or '(not worked out)'}")
print(f"  sources: {', '.join(got['sources']) or 'national only'}; lake depth surveys: "
      f"{', '.join(got['bathymetry']) or 'none'}; state lake lists: {', '.join(got['lake_states']) or 'none'}")
if diff:
    print("  differs from the hand values, which are used (B2 measures the worked-out ones):")
    for d in diff:
        print(f"    {d}")
elif any(k in entry for k in ("crs", "ranges", "sources")):
    print("  the same as the hand values")

# ---- written only when it changed (its time then says when the settings last moved) ----
out = f"{config.SHARED_DERIVED}/area.json"
text = json.dumps(got, indent=1, sort_keys=True, default=list) + "\n"
old = open(out).read() if os.path.exists(out) else None
if text != old:
    with open(out + ".tmp", "w") as f:
        f.write(text)
    os.replace(out + ".tmp", out)
    print(f"  {'written' if old is None else 'updated'}: {out}")
else:
    print(f"  unchanged: {out}")
