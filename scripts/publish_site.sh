#!/bin/zsh
# Put the maps into a local copy of the GitHub Pages site (alexanderswann.github.io), in its streams/ folder, and
# commit them there.
#   ./publish_site.sh          commit only; the last lines say how to publish
#   ./publish_site.sh push [now]   commit and push, which puts it live (owner's standing OK, 2026-11-19; the login is a
#                              token for this one repository in the Mac's keychain, and it expires: when the push is
#                              refused, the owner makes a new token and pushes once from a terminal)
#   streams/index.html                  the map of all areas (13_overview.py)
#   streams/preview.jpg                 the card shown when the link is sent in iMessage etc. (15_preview.py, run by hand)
#   streams/<area>/                     that area's 2D map, 3D map and data, creek profiles, hillshades
# The copy lives in publish/alexanderswann.github.io (ignored by this project's git). Nothing outside streams/ is
# added, changed or removed: the site that is already there stays exactly as it is (owner's rule, 2026-11-19), and
# the script stops if its commit would touch anything else. No .nojekyll either: GitHub's Jekyll step copies these
# files as they are (none starts with front matter, none has a name starting with _ or .).
cd /Users/mac/Fishing
PY=.venv/bin/python
SITE=publish/alexanderswann.github.io
DEST=$SITE/streams
# Never while maps are being built, in this session or another: on 2026-11-19 a push picked up maps another
# session was still rebuilding and had not checked. Two tests, since a build pauses between its steps: no pipeline
# step or run_*.sh driver running, and nothing in output/ written in the last 15 minutes.
busy=$(pgrep -fl 'run_[a-z_]+\.sh|[0-9][0-9][a-z]?_[a-z_]+\.py' | head -1)
[[ -n $busy ]] && { echo "STOP: a build is running ($busy). Publish when it has finished and the maps are checked."; exit 1; }
fresh=$(find output -type f -mmin -15 ! -name index.html | head -1)
# "now" as the second word skips this wait, for maps that were just built and have been checked (the owner said
# "push it now" on 2026-11-19 after the hydrology rebuild); the running-build test above always applies
[[ -n $fresh && $2 != now ]] && { echo "STOP: $fresh was written in the last 15 minutes; a build may be under way. Check the maps, then publish (or: push now)."; exit 1; }
if [[ ! -d $SITE/.git ]]; then
  mkdir -p publish
  git clone -q https://github.com/alexanderswann/alexanderswann.github.io.git $SITE || exit 1
fi
git -C $SITE pull -q --ff-only 2>/dev/null
$PY scripts/13_overview.py || exit 1
rm -rf $DEST
mkdir -p $DEST
cp output/index.html $DEST/
[[ -f output/preview.jpg ]] && cp output/preview.jpg $DEST/
for a in $($PY -c "import sys; sys.path.insert(0, 'scripts'); import config; print(' '.join(config.AREAS))"); do
  [[ -f output/$a/stream_map.html ]] || continue
  mkdir -p $DEST/$a
  for f in stream_map.html stream_map_3d.html map3d_data.js profiles.html profiles_data.js; do
    [[ -f output/$a/$f ]] && cp output/$a/$f $DEST/$a/$f
  done
  for d in output/$a/*/hillshade.png(N); do mkdir -p $DEST/$a/${d:h:t}; cp $d $DEST/$a/${d:h:t}/hillshade.png; done
done
big=$(find $DEST -type f -size +95M | head -1)
[[ -n $big ]] && { echo "STOP: $big is over 95 MB; GitHub refuses files over 100 MB"; exit 1; }
hid=$(find $DEST \( -name '_*' -o -name '.*' \) | head -1)
[[ -n $hid ]] && { echo "STOP: $hid starts with _ or . ; GitHub Pages would not serve it"; exit 1; }
git -C $SITE add -A streams
out=$(git -C $SITE diff --cached --name-only | grep -v '^streams/' | head -1)
[[ -n $out ]] && { echo "STOP: the commit would touch $out, outside streams/"; exit 1; }
if git -C $SITE diff --cached --quiet; then
  echo "nothing new to commit in $SITE"
else
  git -C $SITE commit -q -m "Stream maps: all areas under /streams/ ($(date '+%Y-%m-%d'))

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>" || exit 1
fi
du -sh $DEST | awk '{print "streams/ is", $1}'
git -C $SITE log --oneline | head -2
if [[ $1 == push ]]; then
  out=$(git -C $SITE diff --name-only origin/master HEAD | grep -v '^streams/' | head -1)
  [[ -n $out ]] && { echo "STOP: not pushed, $out is outside streams/"; exit 1; }
  GIT_TERMINAL_PROMPT=0 git -C $SITE push origin master || { echo "NOT PUSHED: the saved GitHub login was refused"; exit 1; }
  echo "Pushed. Live in a minute or two at https://alexanderswann.github.io/streams/"
else
  echo "Ready. To publish:  git -C /Users/mac/Fishing/$SITE push origin master"
  echo "Then it is at https://alexanderswann.github.io/streams/"
fi
