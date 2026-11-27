#!/bin/zsh
# Every audit measurement on one set of maps (about 17 minutes, 12 of them the completeness check's streams), and the
# golden places (golden_check.py: problems once fixed, each still fixed on these maps; audit/golden_places.csv). Read-only on the project; tables go to
# audit/tables/<label>/, with the report's per-area tables in report_tables.md and the completeness table in completeness.md
# (completeness.py: streams, lakes, falls and swimming holes against every independent list we may use; completeness.sh
# runs it alone).
#   audit/scripts/run_all.sh <label> <folder with <area>/map3d_data.js> [folder with <area>/stream_reaches_ranked.csv ...]
#   audit/scripts/run_all.sh live_<site commit> publish/streams-site/docs
#   audit/scripts/run_all.sh build output output          (a finished local build, before it is published)
#   AUDIT_AREAS="ne_ct" audit/scripts/run_all.sh build_ne_ct output output    these areas only (run_area.sh)
# The third argument is where the reach tables, drop tables and lakes.csv of the same build are (default: output/).
# At the end it writes run_all_status.json beside the tables: the label, the maps folder, when it finished, the check
# scripts that failed, and the sha1 of each area's map3d_data.js it measured. The publish gate (scripts/build_stamp.py)
# lets a map out only with a status that holds its sha1 and no failure (2026-11-23).
cd ${0:a:h:h:h}          # the project this script is in (a scratch copy's own, when run from one)
PY=.venv/bin/python
label=$1; maps=${2:a}; tabs=${3:+${3:a}}
[[ -z $label || ! -d $maps ]] && { echo "usage: run_all.sh <label> <maps folder> [tables folder]"; exit 1; }
export SITE_DIR=$maps SITE_NAME=$label AUDIT_TABLES=$PWD/audit/tables/$label
[[ -n $tabs ]] && export TABLES_DIR=$tabs
mkdir -p $AUDIT_TABLES
failed=()
rm -f $AUDIT_TABLES/run_all_status.json
for s in provenance_steps streams_vs_nhd area_vs_reference flow_vs_gauges drawn_jumps popup_checks fish_score_audit falls_lakes_checks \
         watertemp_vs_sites extra_tables completeness golden_check report_tables; do
  echo "== $s $(date +%H:%M:%S)"
  if [[ $s == report_tables ]]; then $PY audit/scripts/$s.py $label > /dev/null 2>&1 || { echo "FAILED $s"; failed+=$s; }; continue; fi
  if [[ $s == provenance_steps ]]; then args=(); else args=(${=AUDIT_AREAS}); fi
  $PY audit/scripts/$s.py $args > $AUDIT_TABLES/$s.log 2>&1 || { echo "FAILED $s (see $AUDIT_TABLES/$s.log)"; failed+=$s; }
done
# the status the publish gate reads: which maps were measured (their sha1) and what failed
$PY - $AUDIT_TABLES $maps $label "${(j:,:)failed}" ${=AUDIT_AREAS} <<'PY'
import glob, json, os, sys, time
sys.path.insert(0, "audit/scripts")
from sitefile import sha1, exists     # the plain map3d_data.js's sha1, also where the folder holds it as .gz (the site)
tables, maps, label, failed, *areas = sys.argv[1:]
areas = areas or sorted({os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{maps}/*/map3d_data.js*")})
golden = {"ran": False}
if os.path.exists(f"{tables}/golden_check.json"):      # the golden places (golden_check.py), when it ran
    g = json.load(open(f"{tables}/golden_check.json"))
    golden = {"ran": True, "failed": [f"{r['row']} ({r.get('status')})" for r in g.get("rows", []) if r.get("status") != "holds"]}
st = dict(label=label, maps=maps, finished=time.strftime("%Y-%m-%d %H:%M:%S"), failed=[f for f in failed.split(",") if f],
          golden=golden, areas={a: sha1(f"{maps}/{a}/map3d_data.js") for a in areas if exists(f"{maps}/{a}/map3d_data.js")})
with open(f"{tables}/run_all_status.json.tmp", "w") as f:
    json.dump(st, f, indent=1)
os.replace(f"{tables}/run_all_status.json.tmp", f"{tables}/run_all_status.json")
print(f"status: {len(st['areas'])} map(s), {len(st['failed'])} check script(s) failed -> {tables}/run_all_status.json")
PY
echo "== done $(date +%H:%M:%S); tables in $AUDIT_TABLES"
