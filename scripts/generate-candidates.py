#!/usr/bin/env python3
"""Build the space of names an impersonator might register, and store it (Phase 2).

Generating costs nothing — no request leaves this machine — so the whole imagined space is written down, and the
budget is spent later on deciding which parts of it to ask crt.sh about.

  scripts/generate-candidates.py --plan         what would be generated, by class and brand; writes nothing
  scripts/generate-candidates.py                write them to ct.candidates
  scripts/generate-candidates.py --show kbstar  print the candidates built from one term

Deterministic: the same watchlist produces the same candidates in the same order, so re-running changes nothing and a
diff means the watchlist changed.
"""
import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import candidates as generator  # noqa: E402
import chquery  # noqa: E402
from watchlist import WatchlistError, load  # noqa: E402

CLASS_ORDER = ["homoglyph", "hyphen", "combosquat", "typo", "tld"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget-per-brand", type=int, default=2000,
                        help="cap per brand, applied after priority ordering (default 2000)")
    parser.add_argument("--combo-keywords", type=int, default=6,
                        help="how many lure keywords to combine with each brand (default 6)")
    parser.add_argument("--plan", action="store_true", help="summarise what would be generated; write nothing")
    parser.add_argument("--show", metavar="TERM", help="print every candidate built from one watchlist term")
    args = parser.parse_args()

    if args.budget_per_brand < 1 or args.combo_keywords < 0:
        print("generate-candidates: budget must be positive and keyword count non-negative", file=sys.stderr)
        return 2

    try:
        watchlist = load()
    except WatchlistError as exc:
        print(f"generate-candidates: {exc}", file=sys.stderr)
        return 2

    built = generator.for_watchlist(watchlist, budget_per_brand=args.budget_per_brand,
                                    combo_keywords=args.combo_keywords)

    if args.show:
        picked = [c for c in built if c.label == args.show]
        if not picked:
            print(f"generate-candidates: '{args.show}' is not a watchlist term", file=sys.stderr)
            return 2
        for candidate in picked:
            shown = candidate.display if candidate.display != candidate.domain else ""
            print(f"  {candidate.klass:<11} {candidate.domain:<40} {shown:<28} {candidate.note}")
        print(f"\n{len(picked)} candidates from '{args.show}'")
        return 0

    by_class = Counter(c.klass for c in built)
    by_brand = Counter(c.brand for c in built)
    homoglyphs = sum(1 for c in built if c.domain.startswith("xn--"))

    print(f"{len(built)} candidates from {len(watchlist.brands)} brands and {len(watchlist.terms)} terms\n")
    print("  by class")
    for klass in CLASS_ORDER:
        print(f"    {klass:<12} {by_class.get(klass, 0):>6}")
    print(f"\n  {homoglyphs} are punycode — names that look right and are not")
    print("\n  by brand")
    for brand, count in sorted(by_brand.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"    {brand:<24} {count:>6}")

    if args.plan:
        print("\nNothing was written, and no request was made. Checking these is budgeted separately: at roughly "
              f"7 seconds per lookup, asking about all {len(built)} would take about {len(built) * 7 / 3600:.1f} "
              "hours, which is why scripts/check.py works through them a batch at a time.")
        return 0

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = [{"domain": c.domain, "display": c.display, "brand": c.brand, "label": c.label,
             "klass": c.klass, "note": c.note, "generated_at": generated_at} for c in built]
    chquery.insert("ct.candidates", rows)
    chquery.optimize("ct.candidates")  # so a re-run leaves the table byte-for-byte where it was
    stored = chquery.scalar("SELECT count() FROM ct.candidates")
    total = chquery.scalar("SELECT uniqExact(domain) FROM ct.candidates")
    print(f"\nwrote {len(rows)} rows; ct.candidates holds {stored} rows for {total} distinct names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
