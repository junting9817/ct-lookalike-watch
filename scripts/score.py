#!/usr/bin/env python3
"""Rank the names that exist, so a person reads the three that matter and not the eleven that do not (Phase 4).

  scripts/score.py            score every candidate with certificates, write ct.findings, print the ranking
  scripts/score.py --dry-run  print the ranking, write nothing
  scripts/score.py --tier review

Reads `ct.certificates` and `ct.candidates`; writes `ct.findings`. Makes no network request, and describes
resemblance rather than passing a verdict (CLAUDE.md C5).
"""
import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import chquery  # noqa: E402
import scoring  # noqa: E402
from watchlist import WatchlistError, load, load_verdicts  # noqa: E402

# A name counts as "foreign" when it sits on the candidate's certificate without belonging to the candidate — the
# mark of a shared or reseller certificate rather than one bought for this name. CDN filler (sni.cloudflaressl.com)
# is excluded: it appears on every Cloudflare certificate and says nothing about who else is on it.
AGGREGATE = """
SELECT c.domain AS domain, any(c.display) AS display, any(c.brand) AS brand, any(c.klass) AS klass,
       any(c.label) AS label,
       uniqExact(e.crtsh_id) AS certificates,
       uniqExactIf(e.name, e.name != c.domain
                   AND e.name != concat('*.', c.domain)
                   AND NOT endsWith(e.name, concat('.', c.domain))
                   AND NOT endsWith(e.name, 'cloudflaressl.com')) AS foreign_names,
       min(e.not_before) AS first_not_before, max(e.not_before) AS last_not_before,
       -- The longest silence between two issuances. A business renews continuously; a name that goes quiet for
       -- years and then gets a fresh certificate has been picked back up by somebody.
       intDiv(arrayMax(arrayDifference(arraySort(groupUniqArray(toUnixTimestamp(e.not_before))))), 86400)
           AS max_gap_days
FROM ct.certificates AS e
INNER JOIN ct.candidates AS c ON c.domain = e.candidate
GROUP BY domain
ORDER BY domain
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", choices=["review", "watch", "weak", "noise"], help="only show this tier")
    parser.add_argument("--dry-run", action="store_true", help="print the ranking; write nothing")
    args = parser.parse_args()

    try:
        watchlist = load()
        verdicts = load_verdicts()
        rows = chquery.query(AGGREGATE)
    except (WatchlistError, chquery.QueryError) as exc:
        print(f"score: {exc}", file=sys.stderr)
        return 2

    if not rows:
        print("score: no candidate has certificates yet — run scripts/check.py first", file=sys.stderr)
        return 0

    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    findings = [scoring.score_candidate(row, as_of=as_of, lure_keywords=watchlist.lure_keywords,
                                        is_generic=watchlist.is_generic(str(row.get("label") or "")),
                                        verdict=verdicts.get(str(row.get("domain") or "").lower()))
                for row in rows]
    findings.sort(key=lambda f: (-f.score, f.domain))

    shown = [f for f in findings if not args.tier or f.tier == args.tier]
    tally = Counter(f.tier for f in findings)

    reviewed = sum(1 for f in findings if "reviewed" in f.signals)
    print(f"{len(findings)} names exist; {tally['review']} to review, {tally['watch']} to watch, "
          f"{tally['weak']} weak, {tally['noise']} noise"
          + (f" · {reviewed} settled by a person" if reviewed else
             " · none reviewed by a person yet (config/reviewed.yaml)") + "\n")
    for finding in shown:
        marker = {"review": "**", "watch": " *", "weak": "  ", "noise": "  "}[finding.tier]
        shows_as = f"  (shows as {finding.display})" if finding.display != finding.domain else ""
        print(f"{marker} {finding.score:>3}  {finding.tier:<7} {finding.domain:<26} {finding.brand}{shows_as}")
        for reason in finding.reasons:
            print(f"          · {reason}")
    print("\nThese are names that resemble a brand and have a certificate. That is all it means: a name here may be "
          "the brand's own,\na partner, a defensive registration or a squatter. Nothing was resolved or visited.")

    if not args.dry_run:
        chquery.query("SELECT 1")  # fail early if the database went away between reading and writing
        chquery.insert("ct.findings", [{
            "domain": f.domain, "display": f.display, "brand": f.brand, "klass": f.klass,
            "score": f.score, "tier": f.tier, "signals": f.signals, "reasons": f.reasons, "scored_at": as_of,
        } for f in findings])
        chquery.optimize("ct.findings")
        print(f"\nwrote {len(findings)} findings to ct.findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
