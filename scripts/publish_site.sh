#!/bin/zsh
# Put the maps into a local copy of the site branch of github.com/alexanderswann/streams (branch gh-pages, folder
# docs/, which GitHub Pages serves at https://alexanderswann.github.io/streams/), and commit them there. Until
# 2026-11-22 the maps lived in the streams/ folder of the user's own site repo (alexanderswann.github.io); the user
# moved them to their own repo that night, code on main and the site on gh-pages, at the same address.
#   ./publish_site.sh          commit only; the last lines say how to publish
#   ./publish_site.sh push [now]   commit and push, which puts it live (owner's standing OK, 2026-11-19; the login is a
#                              fine-grained token in the Mac's keychain for alexanderswann.github.io and streams, and
#                              it expires: when the push is refused, the owner renews it and pushes once from a
#                              terminal)
#   docs/index.html                     the map of all areas (13_overview.py)
#   docs/preview.jpg                    the card shown when the link is sent in iMessage etc. (15_preview.py, run by hand)
#   docs/<area>/                        that area's 2D map, 3D map and data, creek profiles, hillshades
# The copy lives in publish/streams-site (ignored by this project's git). Nothing outside docs/ is added, changed or
# removed (the site branch holds only the site), and the script stops if its commit would touch anything else. No .nojekyll either: GitHub's Jekyll step copies these
# files as they are (none starts with front matter, none has a name starting with _ or .).
# A push goes up area by area (see the push section below), and after it the phone copies are rebuilt from the same
# maps: the one-file map (14_portable.py) and phone/ (phone_sync.sh), so the phone and the website match (2026-11-20).
cd /Users/mac/Fishing
PY=.venv/bin/python
SITE=publish/streams-site
DEST=$SITE/docs
# Never while maps are being built, in this session or another: on 2026-11-19 a push picked up maps another
# session was still rebuilding and had not checked. Two tests, since a build pauses between its steps: no pipeline
# step or run_*.sh driver running, and nothing in output/ written in the last 15 minutes.
# With "now" (maps just built and checked), test runs launched from a session's scratchpad folder don't count, unless
# they run a step that writes published files (03_hydrology, 06_map, 12_profiles, 13_overview, 15_preview) or are a
# run_*.sh driver from scripts/. On 2026-11-20 scratch-only lake checks kept stopping checked publishes, which were
# then copied by hand, around every guard here.
scratch_run() {   # pid: true when the process or one of its parents runs a script kept in a scratchpad folder
  local p=$1 c
  while [[ -n $p && $p -gt 1 ]]; do
    c=$(ps -o command= -p $p 2>/dev/null)
    [[ $c =~ '/scratchpad/[^ ]*\.(sh|py)' ]] && return 0
    p=$(ps -o ppid= -p $p 2>/dev/null | tr -d ' ')
  done
  return 1
}
busy=""
for pid in $(pgrep -f 'run_[a-z_]+\.sh|[0-9][0-9][a-z]?_[a-z_]+\.py'); do
  cmd=$(ps -o command= -p $pid 2>/dev/null) || continue
  if [[ $2 == now && ! $cmd =~ '(03_hydrology|06_map|12_profiles|13_overview|15_preview)\.py' &&
        ! $cmd =~ '(^| )(\./|[^ ]*/Fishing/scripts/)run_[a-z_0-9]+\.sh' ]]; then
    scratch_run $pid && continue
  fi
  busy="$pid ${cmd[1,120]}"; break
done
[[ -n $busy ]] && { echo "STOP: a build is running ($busy). Publish when it has finished and the maps are checked."; exit 1; }
fresh=$(find output -type f -mmin -15 ! -name index.html ! -name stream_maps_all.html | head -1)
# "now" as the second word skips this wait, for maps that were just built and have been checked (the owner said
# "push it now" on 2026-11-19 after the hydrology rebuild); the running-build test above still applies, except to
# scratch test runs
[[ -n $fresh && $2 != now ]] && { echo "STOP: $fresh was written in the last 15 minutes; a build may be under way. Check the maps, then publish (or: push now)."; exit 1; }
if [[ ! -d $SITE/.git ]]; then
  mkdir -p publish
  git clone -q -b gh-pages https://github.com/alexanderswann/streams.git $SITE || exit 1
fi
git -C $SITE pull -q --ff-only 2>/dev/null
$PY scripts/13_overview.py || exit 1
rm -rf $DEST
mkdir -p $DEST
cp output/index.html $DEST/
[[ -f output/preview.jpg ]] && cp output/preview.jpg $DEST/
[[ -f output/credits.html ]] && cp output/credits.html $DEST/      # where the data comes from (credits.py, by 13_overview.py)
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
git -C $SITE add -A docs
out=$(git -C $SITE diff --cached --name-only | grep -v '^docs/' | head -1)
[[ -n $out ]] && { echo "STOP: the commit would touch $out, outside docs/"; exit 1; }
if git -C $SITE diff --cached --quiet; then
  echo "nothing new to commit in $SITE"
else
  git -C $SITE commit -q -m "Stream maps: all areas ($(date '+%Y-%m-%d'))

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || exit 1
fi
du -sh $DEST | awk '{print "docs/ is", $1}'
git -C $SITE log --oneline | head -2
if [[ $1 == push ]]; then
  out=$(git -C $SITE diff --name-only origin/gh-pages HEAD | grep -v '^docs/' | head -1)
  [[ -n $out ]] && { echo "STOP: not pushed, $out is outside docs/"; exit 1; }
  # -- push, area by area --
  # Packing a push, git sends a changed file as a difference from its last version only when it finds that version,
  # and it looks for just one file of each name: every area's files have the same names, so a full republish went up
  # nearly whole (134 MB at 10:35 and 85 MB at 12:43 on 2026-11-20, for about 5 MB of real change). So the areas go up
  # one per push, to a temporary branch (publish-upload) that GitHub Pages doesn't build: each step is the site as it
  # stands plus one more area from the new commit. The last area goes in the same push as gh-pages, whose commit then
  # costs nothing more (git counts as already sent only what the steps of that same push lead from); the site builds
  # once, the temporary branch is deleted, and gh-pages' history is the same as with one push.
  base=$(git -C $SITE rev-parse origin/gh-pages)
  if [[ $base == $(git -C $SITE rev-parse HEAD) ]]; then
    echo "Nothing to push: the live site already has these maps"
    exit 0
  fi
  idx=$(mktemp -t publish_index) || exit 1
  trap 'rm -f $idx' EXIT
  GIT_INDEX_FILE=$idx git -C $SITE read-tree $base || exit 1
  parts=($(git -C $SITE diff --name-only $base HEAD | awk -F/ '{print (NF > 2 ? $1 "/" $2 : $0)}' | sort -u))
  step=$base
  for p in $parts; do
    GIT_INDEX_FILE=$idx git -C $SITE restore --staged --source=HEAD -- $p || exit 1
    step=$(git -C $SITE commit-tree $(GIT_INDEX_FILE=$idx git -C $SITE write-tree) -p $step -m "Upload step: $p") || exit 1
    if [[ $p != $parts[-1] ]]; then
      GIT_TERMINAL_PROMPT=0 git -C $SITE push -q origin "+${step}:refs/heads/publish-upload" ||
        { echo "NOT PUSHED: the upload of $p was refused (see above; the saved GitHub login?); gh-pages is unchanged"; exit 1; }
    fi
  done
  [[ $(git -C $SITE rev-parse "${step}^{tree}") == $(git -C $SITE rev-parse "HEAD^{tree}") ]] ||
    { echo "STOP: the upload steps don't add up to the commit; gh-pages not pushed"; exit 1; }
  GIT_TERMINAL_PROMPT=0 git -C $SITE push origin "+${step}:refs/heads/publish-upload" gh-pages ||
    { echo "NOT PUSHED: the saved GitHub login was refused"; exit 1; }
  GIT_TERMINAL_PROMPT=0 git -C $SITE push -q origin --delete publish-upload ||
    echo "NOTE: the temporary branch is still on GitHub: git -C /Users/mac/Fishing/$SITE push origin --delete publish-upload"
  # -- end of push --
  echo "Pushed. Live in a minute or two at https://alexanderswann.github.io/streams/"
  # the phone copies follow what was just published: the one-file map, then phone/
  { $PY scripts/14_portable.py > /dev/null && zsh scripts/phone_sync.sh | tail -1; } ||
    echo "NOTE: the phone copies were not refreshed; run 14_portable.py and phone_sync.sh"
else
  echo "Ready. To publish:  scripts/publish_site.sh push   (uploads area by area, then refreshes the phone copies)"
  echo "Then it is at https://alexanderswann.github.io/streams/"
fi
