#!/bin/zsh
# The one check of a build (the new-area plan's B9, 2026-11-23). It is the overview session's tools/prehandoff.sh (the
# user's speed-up 1), folded in here so that a hand-off, a build (scripts/run_area.sh) and a publish (the gate reads the
# status run_all.sh writes) run the same checks, with the golden places among them.
#   audit/scripts/check_build.sh <label> <build root> [<patch> ...]
#     <label>       a new name for the audit tables, e.g. brook_v1 or build_ne_ct
#     <build root>  the root that was built (scripts/ and output/): a scratch root, or the project itself
#     <patch> ...   a hand-off: the whole chain on top of BASE, in order, the session's own patch last. Without patches
#                   (a build) the build's scripts/ must be BASE's committed tree
#   env BASE     commit the chain applies on (default: main for a hand-off, the checked-out commit for a build); set it
#                to the commit the build was made on if main has moved since (the build's scripts/ are compared with
#                BASE + the chain)
#       LIVE     audit label of the live site to compare drainage with (default: the newest audit/tables/live_*)
#       OLDMAPS  the live maps (default: publish/streams-site/docs)
#       AREAS    the areas to check (default: all 12; run_area.sh gives its one)
#       QUICK=1  leave out the 17-minute run_all.sh (then no drainage comparison and no status for the publish gate)
# Hard checks (FAIL = not ready, exit 1):
#   the chain applies on BASE; every script compiles; no name is read that nothing binds; the build's scripts/ are
#   exactly the patched (or, without patches, the committed) tree; no golden place is broken (golden_check.py, when
#   it is in; it runs with QUICK=1 too).
# Judged checks (numbers for the overview and the user, against the live maps where an area has one): drawn lines gone
# and new, drainage at gauges and NHDPlus points, fish-score moves, lake outlets, the standing audit tables (run_all.sh,
# completeness included, which also writes run_all_status.json for the publish gate).
# Output: audit/tables/<label>/PREHANDOFF.md (the summary a hand-off message carries).
set -u
T=${0:a:h:h:h}; PY=$T/.venv/bin/python; TOOLS=$T/audit/scripts
label=${1:-}; root=${2:+${2:a}}; shift 2 2>/dev/null; patches=("$@")
[[ -n $label && -d ${root:-/nonexistent}/scripts && -d $root/output ]] ||
  { echo "usage: check_build.sh <label> <build root> [<patch> ...]"; exit 2; }
# a hand-off is checked on main; a build on the code checked out
BASE=${BASE:-$( (( ${#patches} )) && git -C $T rev-parse --short main || git -C $T rev-parse --short HEAD)}
LIVE=${LIVE:-$(for d in $T/audit/tables/live_*(N/om); do [[ -f $d/area_vs_gauges.csv ]] && { basename $d; break; }; done)}
OLDMAPS=${OLDMAPS:-$T/publish/streams-site/docs}
AREAS=${AREAS:-}
OUT=$T/audit/tables/$label; mkdir -p $OUT; R=$OUT/PREHANDOFF.md; : > $R
say() { print -r -- "$*" | tee -a $R; }
say "# Build check: $label ($(date '+%Y-%m-%d %H:%M'))"
say "base $BASE; build $root; live label ${LIVE:-none}; live maps $OLDMAPS${AREAS:+; areas $AREAS}"
fail=0
# 1. the chain applies on BASE (a hand-off), or the committed tree as it is (a build)
W=$(mktemp -d -t check_build); git -C $T archive $BASE | tar -x -C $W; git -C $W init -q 2>/dev/null
for p in $patches; do
  if git -C $W apply --check "${p:a}" 2>/dev/null && git -C $W apply "${p:a}"; then
    say "- applies: ${p:t} (md5 $(md5 -q "$p" | cut -c1-8))"
  else say "- FAIL: ${p:t} does not apply on base + the patches before it"; fail=1; break; fi
done
# 2. compiles, and no unbound names; 3. the build was made with exactly this code
if (( ! fail )); then
  (cd $W && $PY -m py_compile scripts/*.py 2>&1 | head -3) | grep . && { say "- FAIL: a script does not compile"; fail=1; } || say "- all scripts compile"
  u=$($PY $TOOLS/undef_names.py $W/scripts | tail -1); say "- $u"
  [[ $u == "0 "* ]] || { $PY $TOOLS/undef_names.py $W/scripts | head -5 | tee -a $R; fail=1; }
  d=$(diff -rq -x __pycache__ -x '*.pyc' $W/scripts $root/scripts | head -5)
  what=$( (( ${#patches} )) && echo "the patched tree" || echo "the committed tree ($BASE)")
  [[ -z $d ]] && say "- the build's scripts/ are exactly $what" ||
    { say "- FAIL: the build's scripts/ differ from $what:"; say "$d"; fail=1; }
fi
rm -rf $W
(( fail )) && { say ""; say "**FAIL** on a hard check: fix it before handing off or publishing."; exit 1; }
# 4. the standing audit tables (about 17 minutes for 12 maps), and the status the publish gate reads
if [[ -z ${QUICK:-} ]]; then
  AUDIT_AREAS="$AREAS" zsh $T/audit/scripts/run_all.sh $label $root/output $root/output > $OUT/run_all.log 2>&1 &&
    say "- standing checks done: audit/tables/$label (log run_all.log)" || say "- NOTE: run_all.sh exited non-zero, see $OUT/run_all.log"
  grep -h '^FAILED' $OUT/run_all.log 2>/dev/null | sed 's/^/  /' | tee -a $R
fi
# 5. the golden places: problems once fixed, each still fixed in this build (a hard check)
if [[ -f $TOOLS/golden_check.py ]]; then
  SITE_DIR=$root/output AUDIT_TABLES=$OUT $PY $TOOLS/golden_check.py ${=AREAS} > $OUT/golden_check.txt 2>&1
  g=$?
  say ""; say "## Golden places (golden_check.txt)"
  grep -E '^(BROKEN|NOT FOUND|NO MAP)|^golden places' $OUT/golden_check.txt | tee -a $R
  if (( g != 0 )) && ! grep -q '^golden places' $OUT/golden_check.txt; then
    say "- FAIL: golden_check.py did not run to its end:"; tail -3 $OUT/golden_check.txt | sed 's/^/    /' | tee -a $R; fail=1
  elif (( g != 0 )); then
    say "- FAIL: a golden place is broken (a fixed problem is back, or the row needs the change's new value in the same patch)"; fail=1
  fi
else
  say ""; say "- golden places: golden_check.py is not in this project yet"
fi
# 6. against the live maps (areas that have one; a new area has nothing to compare with)
cmp_areas=()
for a in ${=AREAS:-$(ls $root/output)}; do
  [[ -f $root/output/$a/map3d_data.js && -f $OLDMAPS/$a/map3d_data.js ]] && cmp_areas+=$a
done
if (( ${#cmp_areas} )); then
  say ""; say "## Drawn lines, against the live maps (gone = nothing drawn within 40 m now)"
  OLDDIR=$OLDMAPS NOWDIR=$root/output $PY $TOOLS/gone_new.py - $cmp_areas > $OUT/gone_new.txt 2>&1
  grep -E '^[a-z_]+ +gone|^ALL' $OUT/gone_new.txt | tee -a $R
  if [[ -z ${QUICK:-} && -n $LIVE && -f $OUT/area_vs_gauges.csv ]]; then
    say ""; say "## Drainage at gauges and NHDPlus points ($LIVE -> $label)"
    $PY $TOOLS/gauge_area_cmp.py $LIVE $label 2>&1 | tail -5 | tee -a $R
    $PY $TOOLS/nhdplus_area_cmp.py $LIVE $label 2>&1 | tail -5 | tee -a $R
  fi
  say ""; say "## Fish-score moves (full list: score_moves.txt)"
  OLDDIR=$OLDMAPS NOWDIR=$root/output $PY $TOOLS/score_moves.py $cmp_areas > $OUT/score_moves.txt 2>&1
  tail -8 $OUT/score_moves.txt | tee -a $R
  say ""; say "## Lake outlets NHD maps (outlets.csv)"
  (cd $OUT && OLDDIR=$OLDMAPS NOWDIR=$root/output $PY $TOOLS/outlets.py $cmp_areas 2>&1 | tail -5) | tee -a $R
else
  say ""; say "- no live map to compare with for these areas"
fi
say ""
if (( fail )); then
  say "**FAIL** on a hard check (above)."; exit 1
fi
say "Hard checks PASS. The numbers above are for the overview's judgment: list every line lost, every creek"
say "shown drier, every fish 10+ lower that your change didn't mean to cause, with a reason or a fix."
