# The hydrology lock, sourced by the drivers that run conditioning steps (run_base.sh, run_rebuild_a.sh): one 03_hydrology
# or 03b_stitch at a time across all chains, since pysheds needs several GB on a big box.
#   source ./hydrolock.sh          at the driver's top level (not inside a function: the traps belong to the script)
#   locked <range or ""> <script>  runs the driver's own `step <range> <script>` with the lock held; its exit status
# The lock is the directory data/.hydro.lock, holding the pid of the driver (`pid`) and of the step it runs (`step`).
# Before 2026-11-23 a killed driver left it behind and every later conditioning step waited on it for ever. Now:
# - the lock is let go when the step ends, and when the driver ends in any other way: on exit, and on INT, TERM and HUP
#   (Ctrl-C, kill, a closed terminal), which first stop the step it was running (a step left running would be a second
#   conditioning step once the lock is free);
# - a driver killed with -9 (or a crash, a restart) can't let go: the next chain takes the lock over once neither the
#   driver nor its step is running any more (a step still running keeps the lock held). The pid file is claimed by
#   renaming it, which only one waiting chain can do; one that finds a live owner in it puts it back.
HYDRO_LOCK=../data/.hydro.lock
_hl_held=0
_hl_job=

_hl_alive() {   # _hl_alive <file>...: is any pid written in these files a running process?
  local p
  for p in $(cat "$@" 2>/dev/null); do kill -0 $p 2>/dev/null && return 0; done
  return 1
}

hydro_lock_take() {
  until mkdir $HYDRO_LOCK 2>/dev/null; do
    if [[ -f $HYDRO_LOCK/pid ]] && ! _hl_alive $HYDRO_LOCK/pid $HYDRO_LOCK/step \
        && mv $HYDRO_LOCK/pid $HYDRO_LOCK/pid.$$ 2>/dev/null; then
      if _hl_alive $HYDRO_LOCK/pid.$$ $HYDRO_LOCK/step; then      # a live owner after all: give it back
        mv $HYDRO_LOCK/pid.$$ $HYDRO_LOCK/pid
      else
        echo "== hydro lock: its owner (pid $(cat $HYDRO_LOCK/pid.$$)) and its step are gone; taken over $(date +%H:%M:%S)" >> $LOG
        rm -f $HYDRO_LOCK/pid.$$ $HYDRO_LOCK/step
        echo $$ > $HYDRO_LOCK/pid
        _hl_held=1
        return 0
      fi
    fi
    sleep 5
  done
  echo $$ > $HYDRO_LOCK/pid
  _hl_held=1
}

hydro_lock_release() {
  (( _hl_held )) || return 0
  rm -f $HYDRO_LOCK/pid $HYDRO_LOCK/step
  rmdir $HYDRO_LOCK 2>/dev/null
  _hl_held=0
}

locked() {   # locked <range or ""> <script>
  local ok
  hydro_lock_take
  step "$1" "$2" &          # in the background, so a signal reaches the driver at once (a foreground step would hold
  _hl_job=$!                # the trap back until it ended)
  echo $_hl_job > $HYDRO_LOCK/step
  wait $_hl_job; ok=$?
  _hl_job=
  hydro_lock_release
  return $ok
}

_hl_stop() {   # on INT, TERM, HUP: stop the step under the lock, let the lock go, end with 128 + the signal's number
  if [[ -n $_hl_job ]]; then
    pkill -TERM -P $_hl_job 2>/dev/null     # the step's python (background jobs ignore Ctrl-C's INT)
    kill -TERM $_hl_job 2>/dev/null
    wait $_hl_job 2>/dev/null
  fi
  hydro_lock_release
  exit $1
}
trap 'hydro_lock_release' EXIT
trap '_hl_stop 130' INT
trap '_hl_stop 143' TERM
trap '_hl_stop 129' HUP
