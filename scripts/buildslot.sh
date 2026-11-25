# The build-slot cap (2026-11-23; the user's "Both", beside the overview session's memory watchdog): at most two heavy
# builds at once on this Mac, the project's and every session's scratch chains together. Three at once thrashed it.
#   source ./buildslot.sh            in a driver, after hydrolock.sh where it uses both (the slots are machine-wide, so
#                                    any copy of this file will do: the project's, or one in a scratch clone)
#   buildslot_acquire [label]        take one of the two slots, or wait for one. A project build (a driver whose folder
#                                    is /Users/mac/Fishing/scripts) goes ahead of waiting scratch builds; among equals,
#                                    whoever asked first. Exports BUILDSLOT_HELD, so a driver this one starts runs in
#                                    the same slot (run_rebuild_a.sh starts run_mid.sh and run_late.sh)
#   buildslot_release                let it go early (it goes anyway when the driver ends)
#   zsh buildslot.sh status          who holds the slots and who waits
#   zsh buildslot.sh run <command>   take a slot, run the command, let it go: for a session's own chain script (a
#                                    project build only when the command's script is in the project's scripts folder)
#   BUILDSLOT_PRIORITY=critical      (the overview session's runs only: the combined test a batch waits on) a scratch
#                                    build's ticket in the critical lane, served after project builds and before every
#                                    ordinary scratch ticket. In the environment of buildslot_acquire or of `run`.
#   buildslot_yield [label]          for a chain that holds one slot for many maps (2026-11-24: per-map tickets let
#                                    long tests take the critical test's slot at its map boundaries). Call it between
#                                    two maps: it keeps the slot unless a waiting ticket outranks the chain's class (a
#                                    project build outranks critical and scratch, critical outranks scratch); then it
#                                    queues again first, so no ordinary waiter slips in, and lets that one go ahead:
#                                      source /Users/mac/Fishing/scripts/buildslot.sh
#                                      buildslot_acquire "<label>"          (BUILDSLOT_PRIORITY=critical: the overview's)
#                                      for m in $maps; do buildslot_yield; <build $m>; done
#                                    A `buildslot.sh run` inside such a chain runs in its slot (BUILDSLOT_HELD, which
#                                    names no slot while the chain waits and the new one once it has it). Call it only
#                                    with nothing of the chain running: with a background job of its own it keeps the
#                                    slot (that step runs in it).
# The slot is let go however the driver ends: its EXIT trap (INT, TERM and HUP end the driver, which runs it; where
# hydrolock.sh's traps are set, they end it the same way and its lock is let go as before). A slot whose holder is
# gone without letting go (kill -9, a crash, a restart) is cleared by the next driver that looks: each slot records
# its holder's pid and process start time, so a reused pid isn't taken for the holder.
# Slots are symbolic links slot.1 and slot.2 in BUILDSLOT_DIR (/private/tmp/fishing-build-slots, the same for every
# clone; a restart empties it), made in one step with ln -s, which only one process can do; each link's text is
# "pid|start|kind|since|label". A waiter leaves a ticket wait.<0 project, 0c critical, 1 scratch>.<epoch>.<pid>, and
# only the first ticket in that order takes a free slot. buildslot.log there keeps one line per take, free, yield and
# clear. (Copies of this file from before the critical lane read 0c tickets the same way: they sort between 0 and 1.)
# Tests only: BUILDSLOT_DIR (another folder), BUILDSLOT_KIND (project|critical|scratch), BUILDSLOT_POLL (seconds between
# looks).
BUILDSLOT_DIR=${BUILDSLOT_DIR:-/private/tmp/fishing-build-slots}
_bs_max=2
_bs_poll=${BUILDSLOT_POLL:-5}
_bs_project=/Users/mac/Fishing/scripts
_bs_slot=""
_bs_ticket=""
_bs_home=""        # run mode: the folder of the command's script (below); a sourced driver goes by its own folder
_bs_kind=""        # the class this process queued in (project | critical | scratch), and its label: for buildslot_yield
_bs_label=""

_bs_log() { print -r -- "$(date '+%Y-%m-%d %H:%M:%S') $*" >> $BUILDSLOT_DIR/buildslot.log 2>/dev/null }

_bs_start() { ps -o lstart= -p $1 2>/dev/null | tr -s ' ' }    # a process's start time; empty once it is gone

_bs_live() {   # _bs_live <pid> <start>: that process is still running (and is the same one)
  [[ -n $1 && -n $2 ]] && kill -0 $1 2>/dev/null && [[ $(_bs_start $1) == $2 ]]
}

_bs_clean() {   # clear slots and tickets whose process is gone
  local s f info parts
  for s in $BUILDSLOT_DIR/slot.*(N@); do
    info=$(readlink $s 2>/dev/null) || continue
    parts=("${(@s:|:)info}")
    _bs_live $parts[1] $parts[2] && continue
    rm -f $s && _bs_log "clear ${s:t}: holder $parts[1] ($parts[5]) is gone"
  done
  for f in $BUILDSLOT_DIR/wait.*(N.); do
    _bs_live ${f:e} "${$(<$f 2>/dev/null)%%|*}" || rm -f $f
  done
}

_bs_holders() {   # the holders, for a message
  local s info parts out=()
  for s in $BUILDSLOT_DIR/slot.*(N@); do
    info=$(readlink $s 2>/dev/null) || continue
    parts=("${(@s:|:)info}")
    out+=("${s:t}: $parts[5] ($parts[3], pid $parts[1], since $(date -r $parts[4] +%H:%M))")
  done
  print -r -- ${(j:; :)out:-none}
}

_bs_class() {   # the class of a new ticket: project by the driver's folder; a scratch build in the critical lane when
  local kind     # BUILDSLOT_PRIORITY=critical; else scratch
  kind=${BUILDSLOT_KIND:-$([[ ${_bs_home:-${PWD:A}} == $_bs_project ]] && echo project || echo scratch)}
  case ${BUILDSLOT_PRIORITY:-} in
    "") ;;
    critical) [[ $kind == scratch ]] && kind=critical ;;
    *) print -u2 -r -- "buildslot: BUILDSLOT_PRIORITY=$BUILDSLOT_PRIORITY is not a lane (critical); a $kind ticket" ;;
  esac
  print -r -- $kind
}

_bs_prio() { case $1 in project) print 0 ;; critical) print 0c ;; *) print 1 ;; esac }   # a ticket's sort key

_bs_queue() {   # leave this process's ticket, in its class
  _bs_ticket=$BUILDSLOT_DIR/wait.$(_bs_prio $_bs_kind).$(printf %011d $(date +%s)).$$
  print -r -- "$(_bs_start $$)|$_bs_kind|$_bs_label" > $_bs_ticket
}

_bs_wait() {    # until this process's ticket is the first and a slot is free: take that slot
  local k said=0 first start=$(_bs_start $$) t0=$(date +%s)
  while true; do
    _bs_clean
    first=($BUILDSLOT_DIR/wait.*(N.on))
    if [[ ${first[1]:-} == $_bs_ticket ]]; then
      for k in {1..$_bs_max}; do
        if ln -sn "$$|$start|$_bs_kind|$(date +%s)|$_bs_label" $BUILDSLOT_DIR/slot.$k 2>/dev/null; then
          rm -f $_bs_ticket; _bs_ticket=""
          _bs_slot=$BUILDSLOT_DIR/slot.$k
          export BUILDSLOT_HELD=$_bs_slot
          _bs_log "take slot.$k: $_bs_label ($_bs_kind, pid $$) after $(( $(date +%s) - t0 )) s"
          (( said )) && print -r -- "== build slot $k taken $(date +%H:%M:%S), after $(( $(date +%s) - t0 )) s of waiting"
          return 0
        fi
      done
    fi
    if (( ! said )); then
      print -r -- "== waiting for a build slot $(date +%H:%M:%S) (at most $_bs_max heavy builds at once; $(_bs_holders))"
      said=1
    fi
    sleep $_bs_poll
  done
}

buildslot_acquire() {
  local label=${1:-${ZSH_ARGZERO:t}}
  label=${label//|//}
  if [[ -n ${BUILDSLOT_HELD:-} && -L $BUILDSLOT_HELD ]]; then   # started by a driver that holds a slot: run in it
    local info=$(readlink $BUILDSLOT_HELD 2>/dev/null) parts
    parts=("${(@s:|:)info}")
    _bs_live $parts[1] $parts[2] && return 0
  fi
  _bs_kind=$(_bs_class); _bs_label=$label
  mkdir -p $BUILDSLOT_DIR || return 1
  _bs_queue
  _bs_wait
}

buildslot_yield() {   # between two maps of a chain that holds its own slot: see the head of this file
  (( ZSH_SUBSHELL )) && return 0
  [[ -n $_bs_slot ]] || return 0             # no slot of its own (none, or a parent's): nothing to give way with
  zmodload -F zsh/parameter p:jobstates 2>/dev/null
  (( ${#jobstates} )) && return 0            # a step of this chain still runs in the background, in this slot: not now
  local info=$(readlink $_bs_slot 2>/dev/null) first tp who
  [[ ${info%%|*} == $$ ]] || { _bs_slot=""; unset BUILDSLOT_HELD; return 0; }
  _bs_clean
  first=($BUILDSLOT_DIR/wait.*(N.on))
  (( ${#first} )) || return 0
  tp=${${first[1]:t}#wait.}; tp=${tp%%.*}
  [[ $tp < $(_bs_prio $_bs_kind) ]] || return 0   # nobody waiting outranks this chain's class: it keeps its slot
  who=$(cat -- $first[1] 2>/dev/null); who=${who#*|}; who=${who#*|}   # the ticket's label (start|kind|label)
  [[ -n ${1:-} ]] && _bs_label=${1//|//}
  _bs_queue                                  # its ticket first, so no ordinary waiter can take the slot in between
  unset BUILDSLOT_HELD                       # before the slot goes: nothing this chain starts may run in it any more
  rm -f $_bs_slot && _bs_log "yield ${_bs_slot:t}: $_bs_label ($_bs_kind, pid $$) to $who"
  print -r -- "== build slot ${_bs_slot:e} yielded $(date +%H:%M:%S) to $who; it is taken back after that one"
  _bs_slot=""
  _bs_wait                                   # exports BUILDSLOT_HELD again, naming the slot it takes
}

buildslot_release() {
  (( ZSH_SUBSHELL )) && return 0              # a step run in the background ends: the driver still holds the slot
  [[ -n $_bs_ticket ]] && { rm -f $_bs_ticket; _bs_ticket=""; }
  [[ -n $_bs_slot ]] || return 0
  local info=$(readlink $_bs_slot 2>/dev/null)
  if [[ ${info%%|*} == $$ ]]; then
    rm -f $_bs_slot && _bs_log "free ${_bs_slot:t}: ${${info##*|}} (pid $$)"
  fi
  _bs_slot=""
  unset BUILDSLOT_HELD
}

_bs_exit() {
  buildslot_release
  (( ${+functions[hydro_lock_release]} )) && hydro_lock_release   # hydrolock.sh's own EXIT trap, which this one replaces
  return 0
}
trap '_bs_exit' EXIT
# hydrolock.sh's INT / TERM / HUP traps stop its step, let its lock go and exit, which runs the EXIT trap above; a driver
# without it just exits
(( ${+functions[_hl_stop]} )) || { trap 'exit 130' INT; trap 'exit 143' TERM; trap 'exit 129' HUP; }

if [[ $ZSH_EVAL_CONTEXT == toplevel ]]; then     # run as a command, not sourced
  case ${1:-} in
    status)
      mkdir -p $BUILDSLOT_DIR; _bs_clean
      print -r -- "holders: $(_bs_holders)"
      for f in $BUILDSLOT_DIR/wait.*(N.on); do print -r -- "waiting: ${${$(<$f)#*|}} (pid ${f:e}, since $(date -r $(( 10#${${f:r}:e} )) +%H:%M:%S))"; done
      ;;
    run)
      shift; (( $# )) || { print -r -- "usage: buildslot.sh run <command> [args]"; exit 2; }
      # a project build or not by where the command's script is, not by the folder it was started from (a session's
      # chain started while its shell sat in the project's scripts folder took a project slot, 2026-11-24): the first
      # argument that is a file (zsh chain.zsh, python 05_score.py), else the command itself when it is a path
      for f in ${@:2} $1; do
        [[ -f $f && ( $f == */* || $f != $1 ) ]] && { _bs_home=${f:A:h}; break; }
      done
      buildslot_acquire "$*"
      "$@"; rc=$?
      buildslot_release
      exit $rc
      ;;
    *) print -r -- "usage: zsh buildslot.sh status | run <command> [args]   (drivers source it: see its head; BUILDSLOT_PRIORITY=critical for the overview's runs)"; exit 2 ;;
  esac
fi
