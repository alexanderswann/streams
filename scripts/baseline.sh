#!/bin/zsh
# Shared built baselines (overview session, 2026-11-23; the user's speed-up 2; in scripts/ since the new-area plan's
# B9). After each publish the overview freezes the built project as a baseline: an APFS clone (cp -c, nearly free on
# disk until files change) of scripts/, data/ and output/ at the published state. A session clones a baseline into its scratch root instead of the moving project
# folder, and re-runs only from the step its change touches, on only the maps it affects.
#   baseline.sh make <name>          overview only, right after a publish, with no project build running (publish_site.sh
#                                    push reminds you)
#   baseline.sh clone <name> <dest>  a session: <dest> becomes a full scratch root (scripts/, data/, output/, .venv link);
#                                    since 5f518d3 a clone's drivers build only in the clone (a baseline from before says so)
#   baseline.sh list                 the baselines, newest first, with the commit and site commit each was made at
set -u
T=/Users/mac/Fishing; B=$T/baselines          # the baselines live only in the project, whichever copy runs this
case ${1:-} in
make)
  name=${2:?name}; dst=$B/$name
  [[ -e $dst ]] && { echo "STOP: $dst exists"; exit 1; }
  for p in $(pgrep -f 'run_[a-z_]+\.sh|[0-9][0-9][a-z]?_[a-z_]+\.py'); do
    [[ $(lsof -a -p $p -d cwd -Fn 2>/dev/null | sed -n 's/^n//p') == $T/scripts ]] && { echo "STOP: a project build runs (pid $p)"; exit 1; }
  done
  [[ -z $(git -C $T status --porcelain -- scripts) ]] || { echo "STOP: scripts/ has uncommitted changes"; exit 1; }
  mkdir -p $dst || exit 1
  for d in scripts data output; do cp -c -R $T/$d $dst/$d || { echo "STOP: clone of $d failed"; exit 1; }; done
  rm -rf $dst/data/.hydro.lock
  { echo "baseline $name made $(date '+%Y-%m-%d %H:%M %Z')"
    echo "code    $(git -C $T log -1 --format='%h %s')"
    echo "site    $(git -C $T/publish/streams-site log -1 --format='%h %s' 2>/dev/null)"
    echo "Clone it with: baseline.sh clone $name <your scratch root>"; } > $dst/BASELINE.txt
  cat $dst/BASELINE.txt; df -h $T | tail -1 | awk '{print "disk free:", $4}'
  ;;
clone)
  name=${2:?name}; dst=${3:?dest}; src=$B/$name
  [[ -f $src/BASELINE.txt ]] || { echo "STOP: no baseline $name (baseline.sh list)"; exit 1; }
  [[ -e $dst ]] && { echo "STOP: $dst exists"; exit 1; }
  mkdir -p $dst && for d in scripts data output; do cp -c -R $src/$d $dst/$d || exit 1; done
  ln -s $T/.venv $dst/.venv; cp $src/BASELINE.txt $dst/
  echo "scratch root ready: $dst"; head -3 $src/BASELINE.txt
  echo "Run steps from $dst/scripts with AREA=<area> ../.venv/bin/python <step>.py. Re-run only from the step your change touches."
  if grep -q 'cd /Users/mac/Fishing/scripts' $dst/scripts/run_rebuild_a.sh $dst/scripts/run_mid.sh $dst/scripts/run_late.sh 2>/dev/null; then
    echo "NEVER run this clone's run_rebuild_a.sh, run_mid.sh or run_late.sh: this baseline predates 5f518d3, and they cd"
    echo "into /Users/mac/Fishing/scripts and would build in the project. Run the steps in $dst/scripts yourself."
  else
    echo "This clone's drivers cd into their own folder (5f518d3), so they build only here: start them by their literal"
    echo "full path, not a \$VAR path (the publish guard reads command lines and must see a scratch path)."
  fi
  ;;
list)
  dirs=($B/*(N/om)); (( ${#dirs} )) || { echo "no baselines yet"; exit 0; }
  for d in $dirs; do sed -n '1,3p' $d/BASELINE.txt 2>/dev/null; echo; done
  ;;
*) echo "usage: baseline.sh make <name> | clone <name> <dest> | list"; exit 2 ;;
esac
