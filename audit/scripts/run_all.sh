#!/bin/zsh
# Every audit measurement on one set of maps (about 17 minutes, 12 of them the completeness check's streams). Read-only on the project; tables go to
# audit/tables/<label>/, with the report's per-area tables in report_tables.md and the completeness table in completeness.md
# (completeness.py: streams, lakes, falls and swimming holes against every independent list we may use; completeness.sh
# runs it alone).
#   audit/scripts/run_all.sh <label> <folder with <area>/map3d_data.js> [folder with <area>/stream_reaches_ranked.csv ...]
#   audit/scripts/run_all.sh live_<site commit> publish/streams-site/docs
#   audit/scripts/run_all.sh build output output          (a finished local build, before it is published)
# The third argument is where the reach tables, drop tables and lakes.csv of the same build are (default: output/).
cd /Users/mac/Fishing
PY=.venv/bin/python
label=$1; maps=${2:a}; tabs=${3:+${3:a}}
[[ -z $label || ! -d $maps ]] && { echo "usage: run_all.sh <label> <maps folder> [tables folder]"; exit 1; }
export SITE_DIR=$maps SITE_NAME=$label AUDIT_TABLES=/Users/mac/Fishing/audit/tables/$label
[[ -n $tabs ]] && export TABLES_DIR=$tabs
mkdir -p $AUDIT_TABLES
for s in provenance_steps streams_vs_nhd area_vs_reference flow_vs_gauges drawn_jumps popup_checks fish_score_audit falls_lakes_checks \
         watertemp_vs_sites extra_tables completeness report_tables; do
  echo "== $s $(date +%H:%M:%S)"
  if [[ $s == report_tables ]]; then $PY audit/scripts/$s.py $label > /dev/null 2>&1 || echo "FAILED $s"; continue; fi
  $PY audit/scripts/$s.py > $AUDIT_TABLES/$s.log 2>&1 || echo "FAILED $s (see $AUDIT_TABLES/$s.log)"
done
echo "== done $(date +%H:%M:%S); tables in $AUDIT_TABLES"
