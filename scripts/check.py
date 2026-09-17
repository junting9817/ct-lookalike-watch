#!/usr/bin/env python3
"""Ask Certificate Transparency which of the imagined names actually exist (Phase 3).

Checking every candidate would take about twelve hours and would be rude to a free service, so each run takes a
budget and works through the space: names never asked about first, then the ones asked about longest ago. Coverage
accumulates, and the cost per run is a number someone chose.

  scripts/check.py --limit 50                 the 50 most overdue candidates
  scripts/check.py --limit 30 --klass homoglyph
  scripts/check.py --limit 20 --brand "KB Kookmin Bank"
  scripts/check.py --limit 10 --dry-run       select and report; write nothing
  scripts/check.py --offline                  re-read cached answers, make no request

Before anything is recorded, one name known to have certificates is asked about (CLAUDE.md C7). crt.sh under load can
answer HTTP 200 with an empty array, which is indistinguishable from "this name has no certificate" — so if the
canary comes back empty the run stops rather than writing thousands of false absences.

Nothing here contacts a candidate domain; the only host spoken to is crt.sh.
"""
import argparse
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import chquery  # noqa: E402
import oracle  # noqa: E402
from watchlist import WatchlistError, load  # noqa: E402

CLASS_PRIORITY = ["homoglyph", "hyphen", "combosquat", "typo", "tld"]
EPOCH = "1970-01-01 00:00:00"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_time(value) -> str:
    text = str(value or "").replace("T", " ")[:19]
    try:
        moment = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return EPOCH
    return text if 1970 <= moment.year <= 2105 else EPOCH


def overdue(limit: int, klass: str | None, brand: str | None) -> list[dict]:
    """The candidates most in need of an answer: never asked first, then longest since asked."""
    filters = ["1"]
    params: dict[str, str] = {}
    if klass:
        filters.append("c.klass = {klass:String}")
        params["klass"] = klass
    if brand:
        filters.append("c.brand = {brand:String}")
        params["brand"] = brand
    priority = "indexOf(" + str(CLASS_PRIORITY).replace("'", "'") + ", c.klass)"
    # The last tie-break is a hash, not the name. Ordering by name walks the space alphabetically: the first run here
    # spent its whole budget on names beginning '0', '1' and 'c', and would have reached the punycode candidates —
    # the ones worth asking about — only after every ASCII one. A stable hash samples instead of marching, and stays
    # stable across runs so the rotation still makes progress.
    return chquery.query(f"""
        SELECT c.domain AS domain, c.display AS display, c.brand AS brand, c.klass AS klass, c.note AS note,
               ifNull(k.last_checked, toDateTime('{EPOCH}', 'UTC')) AS last_checked
        FROM ct.candidates AS c
        LEFT JOIN (SELECT domain, max(checked_at) AS last_checked FROM ct.checks GROUP BY domain) AS k
               ON c.domain = k.domain
        WHERE {' AND '.join(filters)}
        ORDER BY last_checked ASC, {priority} ASC, cityHash64(domain) ASC
        LIMIT {int(limit)}""", params)


def certificate_rows(answer: oracle.Answer, brand: str, seen_at: str) -> tuple[list[dict], dict]:
    """(rows for ct.certificates, summary for ct.checks)."""
    rows: list[dict] = []
    ids: set[int] = set()
    issued: list[str] = []
    for entry in answer.rows:
        try:
            crtsh_id = int(entry.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if not crtsh_id:
            continue
        ids.add(crtsh_id)
        not_before = parse_time(entry.get("not_before"))
        issued.append(not_before)
        for name in oracle.names_in(entry):
            rows.append({
                "name": name, "crtsh_id": crtsh_id, "candidate": answer.domain, "brand": brand,
                "common_name": str(entry.get("common_name") or "")[:255],
                "issuer_name": str(entry.get("issuer_name") or "")[:255],
                "issuer_ca_id": int(entry.get("issuer_ca_id") or 0),
                "serial_number": str(entry.get("serial_number") or "")[:128],
                "not_before": not_before, "not_after": parse_time(entry.get("not_after")),
                "ingested_at": seen_at,
            })
    summary = {
        "certificates": len(ids),
        "first_not_before": min(issued) if issued else EPOCH,
        "last_not_before": max(issued) if issued else EPOCH,
        "max_crtsh_id": max(ids) if ids else 0,
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=50, help="how many candidates to ask about (default 50)")
    parser.add_argument("--klass", choices=CLASS_PRIORITY, help="only this class of candidate")
    parser.add_argument("--brand", help="only this brand")
    parser.add_argument("--canary", help="the name used to prove the oracle is answering "
                                         "(default: the first brand's first legitimate domain)")
    parser.add_argument("--pause", type=float, default=oracle.SECONDS_BETWEEN_REQUESTS,
                        help=f"seconds between requests (default {oracle.SECONDS_BETWEEN_REQUESTS})")
    parser.add_argument("--offline", action="store_true", help="use cached answers; make no request")
    parser.add_argument("--dry-run", action="store_true", help="select and report; write nothing")
    parser.add_argument("--quiet", action="store_true", help="only the summary")
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 2000 or args.pause < 0:
        print("check: --limit must be 1..2000 and --pause must not be negative", file=sys.stderr)
        return 2

    log = None if args.quiet else (lambda message: print(message, file=sys.stderr))
    try:
        watchlist = load()
        canary_domain = args.canary or watchlist.brands[0].legitimate[0]
        selected = overdue(args.limit, args.klass, args.brand)
    except (WatchlistError, chquery.QueryError, IndexError) as exc:
        print(f"check: {exc}", file=sys.stderr)
        return 2

    if not selected:
        print("check: nothing to do — no candidate matched. Run scripts/generate-candidates.py first.",
              file=sys.stderr)
        return 0

    # ---------------------------------------------------------------- the canary (C7)
    if log:
        log(f"canary: asking about {canary_domain}, which certainly has certificates")
    proof = oracle.canary(canary_domain, offline=args.offline, log=log)
    if proof.status != "found":
        print(f"check: ABORTED — the canary {canary_domain} came back '{proof.status}' ({proof.detail}).\n"
              f"       crt.sh is not answering truthfully, and recording {len(selected)} names as absent on the "
              f"strength of that would be worse than recording nothing.", file=sys.stderr)
        return 1
    if log:
        log(f"canary: {proof.detail} in {proof.seconds:.1f}s — the oracle is answering\n")

    seen_at = now()
    checks: list[dict] = []
    certificates: list[dict] = []
    tally: Counter = Counter()

    for index, candidate in enumerate(selected):
        if index and not args.offline:
            time.sleep(args.pause)
        answer = oracle.lookup(candidate["domain"], offline=args.offline, log=log)
        rows, summary = certificate_rows(answer, candidate["brand"], seen_at)
        certificates += rows
        tally[answer.status] += 1
        checks.append({"domain": candidate["domain"], "checked_at": seen_at, "status": answer.status,
                       "seconds": round(answer.seconds, 2), "detail": answer.detail[:255], **summary})
        if log:
            if answer.status == "found":
                shown = candidate["display"] if candidate["display"] != candidate["domain"] else ""
                log(f"  FOUND  {candidate['domain']:<38} {summary['certificates']:>3} certs  "
                    f"{candidate['klass']:<11} {candidate['brand']}" + (f"  (shows as {shown})" if shown else ""))
            elif answer.status == "error":
                log(f"  error  {candidate['domain']:<38} {answer.detail}")

    if not args.dry_run:
        chquery.insert("ct.checks", checks)
        if certificates:
            chquery.insert("ct.certificates", certificates)
            chquery.optimize("ct.certificates")

    found = tally["found"]
    print(f"\ncheck: asked about {len(selected)} names — {found} exist, {tally['absent']} do not, "
          f"{tally['error']} could not be answered"
          + (f"; {len(certificates)} certificate names stored" if certificates and not args.dry_run else "")
          + (" (--dry-run: nothing written)" if args.dry_run else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
