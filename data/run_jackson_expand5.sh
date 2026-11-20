#!/bin/zsh
# 2026-11-19, fourth pass: hoback / palisades edge at x 506 (outside Palisades' filled flat). 01 + 02 for those two boxes,
# then 03 / 03b / 04 / 04b for all seven; stop if a dead end of 20+ km2 sits on a shared edge; else run_mid and run_late.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOG=../data/expand_jackson.log
RB=../data/rebuild_jackson.log
LOCK=../data/.hydro.lock
echo "== START x506 $(date '+%m-%d %H:%M:%S')" >> $LOG
for r in hoback palisades; do
  echo "== jackson/$r 01_download_dem $(date +%H:%M:%S)" >> $LOG
  AREA=jackson REGION=$r perl -e 'alarm shift; exec @ARGV' 1800 $PY 01_download_dem.py >> $LOG 2>&1 || echo "FAILED jackson/$r 01 $(date +%H:%M:%S)" >> $LOG
  for i in 1 2 3; do
    echo "== jackson/$r 02_download_vectors try $i $(date +%H:%M:%S)" >> $LOG
    AREA=jackson REGION=$r perl -e 'alarm shift; exec @ARGV' 900 $PY 02_download_vectors.py >> $LOG 2>&1 && break
    echo "FAILED-OR-TIMED-OUT jackson/$r 02 try $i $(date +%H:%M:%S)" >> $LOG
  done
done
echo "== START jackson (x506 relayout) $(date '+%m-%d %H:%M:%S')" >> $RB
ranges=($(AREA=jackson $PY -c "import config; print(' '.join(config.REGIONS))"))
for r in $ranges; do
  until mkdir $LOCK 2>/dev/null; do sleep 5; done
  echo "== jackson/$r 03_hydrology $(date +%H:%M:%S)" >> $RB
  AREA=jackson REGION=$r $PY 03_hydrology.py >> $RB 2>&1 || echo "FAILED jackson/$r 03_hydrology" >> $RB
  rmdir $LOCK
done
until mkdir $LOCK 2>/dev/null; do sleep 5; done
echo "== jackson/all 03b_stitch $(date +%H:%M:%S)" >> $RB
AREA=jackson $PY 03b_stitch.py >> $RB 2>&1 || echo "FAILED jackson/all 03b_stitch" >> $RB
rmdir $LOCK
for r in $ranges; do
  for s in 04_knickpoints 04b_bigcreek_steps; do
    echo "== jackson/$r $s $(date +%H:%M:%S)" >> $RB
    AREA=jackson REGION=$r $PY $s.py >> $RB 2>&1 || echo "FAILED jackson/$r $s" >> $RB
  done
done
if grep -q "^FAILED" <(sed -n '/START jackson (x506 relayout)/,$p' $RB); then echo "FAILED hydrology or drops: stopped $(date +%H:%M:%S)" >> $LOG; exit 1; fi
if ! AREA=jackson $PY /private/tmp/claude-501/-Users-mac--claude-spares-spare-QG7eB8/fc6af4e4-dcbb-480a-8d84-99095868d1c1/scratchpad/wy/edge_gate.py >> $LOG 2>&1; then
  echo "FAILED edge gate: stopped before mid $(date +%H:%M:%S)" >> $LOG; exit 1
fi
echo "== mid $(date +%H:%M:%S)" >> $LOG
./run_mid.sh jackson
S=$(grep -n '== START jackson' ../data/mid_jackson.log | tail -1 | cut -d: -f1)
if sed -n "$S,\$p" ../data/mid_jackson.log | grep -q "== DONE jackson"; then
  echo "== late $(date +%H:%M:%S)" >> $LOG
  ./run_late.sh jackson
  echo "== DONE x506 $(date '+%m-%d %H:%M:%S')" >> $LOG
else
  echo "FAILED mid: late not run $(date +%H:%M:%S)" >> $LOG
fi
