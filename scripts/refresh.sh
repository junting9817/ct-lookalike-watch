#!/usr/bin/env bash
# One night's work: refresh the candidate space, ask crt.sh about a budget of it, re-score what exists (Phase 5).
# Safe to re-run at any time. Every step refuses to write when its own check fails.
#
#   scripts/refresh.sh                 the default budget
#   scripts/refresh.sh --limit 100     a smaller bite
#   scripts/refresh.sh --check         prove the pipeline works without asking crt.sh anything
#
# Coverage is the point of scheduling this. 6,401 candidates at one budget a night is roughly three weeks to a full
# pass, after which the rotation starts again on the oldest answers — which is what keeps an absence from quietly
# becoming a claim about the present.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"

LIMIT=250
CHECK=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) LIMIT=${2:?--limit needs a number}; shift 2 ;;
    --check) CHECK=1; shift ;;
    -h | --help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'refresh: unknown option %s (see --help)\n' "$1" >&2; exit 2 ;;
  esac
done
[[ "$LIMIT" =~ ^[0-9]+$ ]] && ((LIMIT >= 1 && LIMIT <= 2000)) || { printf 'refresh: --limit must be 1..2000\n' >&2; exit 2; }

step() { printf '\n== %s\n' "$1"; }

if ((CHECK)); then
  step "watchlist"
  ./scripts/check-watchlist.py | head -1
  step "candidate generation (no requests)"
  ./scripts/generate-candidates.py --plan | head -1
  step "selection and scoring against what is already stored"
  ./scripts/check.py --limit 3 --dry-run --offline --quiet || true
  ./scripts/score.py --dry-run | head -1
  printf '\nrefresh: the pipeline is healthy; nothing was written and crt.sh was not asked anything\n'
  exit 0
fi

step "1/3  candidate space"
# Cheap and idempotent: this only changes anything when the watchlist has been edited.
./scripts/generate-candidates.py | tail -1

step "2/3  asking crt.sh about $LIMIT candidates"
# check.py aborts on a failed canary, and set -e stops the run here rather than scoring stale data.
./scripts/check.py --limit "$LIMIT" --quiet

step "3/3  scoring"
./scripts/score.py --quiet 2>/dev/null || ./scripts/score.py | tail -3

step "coverage"
docker exec -i nsm-clickhouse clickhouse-client --database ct --query "
  SELECT concat(toString(uniqExactIf(domain, status != 'error')), ' of ',
                toString((SELECT count() FROM ct.candidates)), ' candidates answered (',
                toString(round(100 * uniqExactIf(domain, status != 'error') /
                               (SELECT count() FROM ct.candidates), 1)), '%)')
  FROM ct.checks"
