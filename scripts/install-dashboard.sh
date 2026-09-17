#!/usr/bin/env bash
# Put this project's dashboard where the lab's Grafana will provision it (Phase 4). Idempotent.
#
#   scripts/install-dashboard.sh            copy it in and confirm Grafana picked it up
#   scripts/install-dashboard.sh --remove   take it out again
#   scripts/install-dashboard.sh --check    is it installed, and can Grafana read the data
#
# The lab's Grafana provisions every JSON under ~/JC/dashboards/json, so copying the file in is enough: no change to
# docker-compose.yml, no container restart, and nothing about the lab's own dashboards is touched. The provider
# rescans once a minute.
#
# The source of truth is dashboards/ct-lookalikes.json in this repository. Edits made in Grafana are discarded —
# the provider runs with allowUiUpdates false.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LAB=${CT_LAB_DIR:-$HOME/JC}
SOURCE="$REPO/dashboards/ct-lookalikes.json"
TARGET="$LAB/dashboards/json/ct-lookalikes.json"
CONTAINER=${CT_GRAFANA_CONTAINER:-nsm-grafana}

die() { printf 'install-dashboard: error: %s\n' "$*" >&2; exit 1; }

readable() {
  # Asked from inside Grafana's container, because grafana_ro is only allowed to connect from the lab's network.
  docker exec -i "$CONTAINER" sh -c \
    'wget -qO- --header="X-ClickHouse-User: grafana_ro" --header="X-ClickHouse-Key: $CH_GRAFANA_PASSWORD" \
     "http://clickhouse:8123/?query=SELECT%20count()%20FROM%20ct.findings"' 2>/dev/null || true
}

case "${1:-}" in
  --check)
    [[ -f "$TARGET" ]] && printf 'installed: %s\n' "$TARGET" || printf 'not installed\n'
    count=$(readable)
    if [[ -n "$count" ]]; then
      printf 'grafana_ro can read ct.findings: %s rows\n' "$count"
    else
      printf 'grafana_ro cannot read ct.findings — check the GRANT in %s\n' \
        "$LAB/ingest/clickhouse/users.d/nsm-users.xml"
    fi
    exit 0
    ;;
  --remove)
    rm -f "$TARGET"
    printf 'install-dashboard: removed %s (Grafana drops it within a minute)\n' "$TARGET"
    exit 0
    ;;
  "") ;;
  -h | --help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die "unknown option $1 (see --help)" ;;
esac

[[ -f "$SOURCE" ]] || die "$SOURCE not found"
[[ -d "$(dirname "$TARGET")" ]] || die "$(dirname "$TARGET") not found — is the lab at $LAB?"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SOURCE" || die "the dashboard is not valid JSON"

install -m 0644 "$SOURCE" "$TARGET"
printf 'install-dashboard: copied to %s\n' "$TARGET"

count=$(readable)
[[ -n "$count" ]] || die "grafana_ro cannot read ct.findings; the dashboard would provision but show nothing"
printf 'install-dashboard: grafana_ro reads ct.findings (%s rows); Grafana rescans within a minute\n' "$count"
