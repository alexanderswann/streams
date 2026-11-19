#!/bin/zsh
# Put the maps into a local copy of the GitHub Pages site (alexanderswann.github.io), in its streams/ folder, and
# commit them there. It does NOT push: publishing is the owner's step (see the last lines it prints).
#   streams/index.html                  the map of all areas (13_overview.py)
#   streams/<area>/                     that area's 2D map, 3D map and data, creek profiles, hillshades
# The copy lives in publish/alexanderswann.github.io (ignored by this project's git). The rest of the site is not
# touched, except for an empty .nojekyll at the top so GitHub serves the files as they are instead of running them
# through Jekyll (the site uses no Jekyll features; 430 MB of maps would only slow that step down).
cd /Users/mac/Fishing
PY=.venv/bin/python
SITE=publish/alexanderswann.github.io
DEST=$SITE/streams
if [[ ! -d $SITE/.git ]]; then
  mkdir -p publish
  git clone -q https://github.com/alexanderswann/alexanderswann.github.io.git $SITE || exit 1
fi
git -C $SITE pull -q --ff-only 2>/dev/null
$PY scripts/13_overview.py || exit 1
rm -rf $DEST
mkdir -p $DEST
cp output/index.html $DEST/index.html
for a in $($PY -c "import sys; sys.path.insert(0, 'scripts'); import config; print(' '.join(config.AREAS))"); do
  [[ -f output/$a/stream_map.html ]] || continue
  mkdir -p $DEST/$a
  for f in stream_map.html stream_map_3d.html map3d_data.js profiles.html profiles_data.js; do
    [[ -f output/$a/$f ]] && cp output/$a/$f $DEST/$a/$f
  done
  for d in output/$a/*/hillshade.png(N); do mkdir -p $DEST/$a/${d:h:t}; cp $d $DEST/$a/${d:h:t}/hillshade.png; done
done
touch $SITE/.nojekyll
big=$(find $DEST -type f -size +95M | head -1)
[[ -n $big ]] && { echo "STOP: $big is over 95 MB; GitHub refuses files over 100 MB"; exit 1; }
git -C $SITE add -A .nojekyll streams
if git -C $SITE diff --cached --quiet; then
  echo "nothing new to commit in $SITE"
else
  git -C $SITE commit -q -m "Stream maps: all areas under /streams/ ($(date '+%Y-%m-%d'))

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>" || exit 1
fi
du -sh $DEST | awk '{print "streams/ is", $1}'
git -C $SITE log --oneline | head -2
echo "Ready. To publish:  git -C /Users/mac/Fishing/$SITE push origin master"
echo "Then it is at https://alexanderswann.github.io/streams/"
