#!/usr/bin/env python3
"""Validate the watchlist, and show exactly what a poll would ask for — without asking (Phase 1).

  scripts/check-watchlist.py              validate and summarise
  scripts/check-watchlist.py --plan       print every URL a poll would request, and what it would cost
  scripts/check-watchlist.py --owns a.com which brand, if any, legitimately operates this name

The --plan output makes no network request. It exists so the shape and cost of a run can be reviewed before the
first one happens: crt.sh is a free service run by someone else, and a watchlist that quietly grew to two hundred
terms would be rude to it and slow for us.
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
from watchlist import MIN_TERM_LENGTH, WatchlistError, load  # noqa: E402

# Matches the politeness settings the poller will use (Phase 2); kept here so the plan is honest about the cost.
SECONDS_BETWEEN_REQUESTS = 5
TYPICAL_SECONDS_PER_REQUEST = 8
QUERY_URL = "https://crt.sh/?q=%{term}%&output=json&deduplicate=Y"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", action="store_true", help="print the requests a poll would make, without making any")
    parser.add_argument("--owns", metavar="DOMAIN", help="ask which brand legitimately operates a domain")
    args = parser.parse_args()

    try:
        watchlist = load()
    except WatchlistError as exc:
        print(f"check-watchlist: {exc}", file=sys.stderr)
        return 1

    if args.owns:
        owner = watchlist.owner_of(args.owns)
        if owner:
            print(f"{args.owns} belongs to {owner.english} ({owner.name}) — certificates for it are suppressed")
        else:
            print(f"{args.owns} is not a known legitimate domain; it would be scored as a candidate")
        return 0

    if args.plan:
        terms = watchlist.terms
        seconds = len(terms) * (TYPICAL_SECONDS_PER_REQUEST + SECONDS_BETWEEN_REQUESTS)
        print(f"A poll would make {len(terms)} requests, one per term, {SECONDS_BETWEEN_REQUESTS}s apart.")
        print(f"Estimated wall time: about {seconds // 60} min {seconds % 60}s. No request is made by this command.\n")
        for term in terms:
            brand = watchlist.brand_for(term)
            print(f"  {QUERY_URL.format(term=term):<62} {brand.english if brand else ''}")
        print("\nEvery response is filtered against that brand's legitimate domains before anything is stored.")
        return 0

    by_sector: dict[str, list] = {}
    for brand in watchlist.brands:
        by_sector.setdefault(brand.sector, []).append(brand)

    print(f"Watchlist OK — {len(watchlist.brands)} brands, {len(watchlist.terms)} unique terms, "
          f"{len(watchlist.lure_keywords)} lure keywords\n")
    for sector in sorted(by_sector):
        print(f"  {sector}")
        for brand in sorted(by_sector[sector], key=lambda b: b.english):
            owned = len(brand.legitimate)
            print(f"    {brand.english:<22} {brand.name:<12} terms: {', '.join(brand.terms):<34} "
                  f"{owned} legitimate domain{'' if owned == 1 else 's'}")
    shortest = min(watchlist.terms, key=len)
    print(f"\n  shortest term: '{shortest}' ({len(shortest)} chars; the floor is {MIN_TERM_LENGTH})")
    print("  nothing in the watchlist is ever resolved, fetched or visited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
