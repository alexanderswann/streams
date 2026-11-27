#!/bin/zsh
# Is everything on the maps that should be? Streams, lakes, waterfalls and swimming holes against every independent
# list we may use (completeness.py says which). Read-only on the project; no network. Tables go to audit/tables/<label>/,
# the one-page table to audit/tables/<label>/completeness.md.
#   audit/scripts/completeness.sh <label> <folder with <area>/map3d_data.js and map3d_layers.js> [--no-streams] [area ...]
#   audit/scripts/completeness.sh live_<site commit> publish/streams-site/docs
#   audit/scripts/completeness.sh build output                    (a finished local build, before it is published)
# About 1 min a map with streams (peak about 1 GB), 20 s for all 12 with --no-streams.
# The reference copies that need the network are refreshed apart, when the line is good:
#   .venv/bin/python audit/scripts/completeness_fetch.py              OSM swimming spots and waterways, 3DHP status (weekly)
#   <python with duckdb> audit/scripts/completeness_overture.py      Overture Maps places (with each Overture release)
cd /Users/mac/Fishing
PY=.venv/bin/python
label=$1; maps=${2:a}
[[ -z $label || ! -d $maps ]] && { echo "usage: completeness.sh <label> <maps folder> [--no-streams] [area ...]"; exit 1; }
shift 2
export SITE_DIR=$maps SITE_NAME=$label AUDIT_TABLES=/Users/mac/Fishing/audit/tables/$label AUDIT_CACHE=/Users/mac/Fishing/audit/cache
mkdir -p $AUDIT_TABLES $AUDIT_CACHE
echo "== completeness $(date +%H:%M:%S)"
$PY audit/scripts/completeness.py "$@" > $AUDIT_TABLES/completeness.log 2>&1 || { echo "FAILED completeness (see $AUDIT_TABLES/completeness.log)"; exit 1; }
sed -n '/^| map/,$p' $AUDIT_TABLES/completeness.md
echo "== done $(date +%H:%M:%S); tables in $AUDIT_TABLES"
