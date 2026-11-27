#!/bin/zsh
# Copies of the maps for the phone (phone/, served by the "phone-maps" preview on port 8765), laid out like output/:
# phone/index.html is the map of all areas (13_overview.py) and each area's maps are in phone/<area>/, so the
# "Go to" menus and the links between the maps work the same in both places.
# LA used to sit at the top of phone/: its old file names stay there as small pages that forward to phone/la/.
# phone/creek-map.html is left alone. phone/stream_maps_all.html is the one-file map (14_portable.py), copied when there
# is one; publish_site.sh push runs 14_portable.py and this script after each publish.
cd /Users/mac/Fishing
PY=.venv/bin/python
$PY scripts/13_overview.py || exit 1
for a in $($PY -c "import sys; sys.path.insert(0, 'scripts'); import config; print(' '.join(config.AREAS))"); do
  [[ -f output/$a/stream_map.html ]] || continue
  mkdir -p phone/$a
  rm -f phone/$a/*.gz                       # packed below again from these copies (as on the website)
  for f in stream_map.html stream_map.js stream_map_3d.html map3d_data.js map3d_layers.js routes_data.js land_data.js parcels_data.js coverage_data.js profiles.html profiles_data.js; do
    [[ -f output/$a/$f ]] && cp output/$a/$f phone/$a/$f
  done
  for d in output/$a/*/hillshade.png(N); do mkdir -p phone/$a/${d:h:t}; cp $d phone/$a/${d:h:t}/hillshade.png; done
done
cp output/index.html phone/index.html
# the web app and the pages' libraries (weblib.py), as on the website, and the areas' lists for "Save for offline"
for f in sw.js offline.js manifest.webmanifest; do [[ -f output/$f ]] && cp output/$f phone/$f; done
for d in lib icons; do [[ -d output/$d ]] && { rm -rf phone/$d; cp -R output/$d phone/$d; }; done
$PY scripts/weblib.py pack phone > /dev/null || exit 1     # the big files as <name>.gz, as on the website
$PY scripts/weblib.py lists phone > /dev/null
[[ -f output/stream_maps_all.html ]] && cp output/stream_maps_all.html phone/stream_maps_all.html
# the old LA copies at the top: forwarding pages (they keep the #lat,lon,zoom part of a bookmark), and the data
# files and hillshade folders they used are removed
for f in stream_map.html stream_map_3d.html profiles.html; do
  print -r -- "<!doctype html><meta charset=\"utf-8\"><title>Moved</title><script>location.replace(\"la/$f\" + location.search + location.hash)</script><a href=\"la/$f\">The LA map is now in la/</a>" > phone/$f
done
rm -f phone/map3d_data.js phone/profiles_data.js
for r in $(AREA=la $PY -c "import sys; sys.path.insert(0, 'scripts'); import config; print(' '.join(config.REGIONS))"); do
  [[ -d phone/$r && ! -f phone/$r/stream_map.html ]] && rm -rf phone/$r
done
du -sh phone | awk '{print "phone/ is now", $1}'
