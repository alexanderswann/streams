#!/bin/zsh
# Promote a tested build into the project instead of building it again: promote.py says how (zsh run_promote.sh -h).
#   zsh /Users/mac/Fishing/scripts/run_promote.sh check   <clone> <baseline> [--maps ...] [--allow GLOB ...]
#   zsh /Users/mac/Fishing/scripts/run_promote.sh promote <clone> <baseline> --label <label> [--dry-run]
#   zsh /Users/mac/Fishing/scripts/run_promote.sh undo    <label>
#   zsh /Users/mac/Fishing/scripts/run_promote.sh asof    <clone>
#   zsh /Users/mac/Fishing/scripts/run_promote.sh gitlink <clone> <commit>
# A run_*.sh driver on purpose: while it runs, publish_site.sh's build guard (unchanged) and baseline.sh make see a
# build, so nothing is published or frozen from a half-promoted output/. The overview session runs it, nobody else.
cd ${0:a:h} || exit 1
../.venv/bin/python promote.py "$@"
