"""Decide which existing names are worth a person's attention (Phase 4).

The first real batch made the problem concrete. Eleven candidates existed; ten of them were businesses that happen to
share a word with a Korean brand, and `uplus.co` has been issuing certificates since 2017. Existence is not the
signal. What separates a lookalike from a coincidence is its *shape*:

  - how hard the name is to read as wrong — a Cyrillic character beats a different suffix, every time
  - whether the certificate was obtained for this name, or unrelated names ride on it too
  - whether the name is young, and whether its certificates arrive in a burst and then stop

Every signal is named and carries a weight, and a finding lists the ones that fired. A score with no explanation is
not usable by the person who has to decide what to do about it — and per CLAUDE.md C5 the output describes
resemblance, never a verdict.
"""
from dataclasses import dataclass, field
from datetime import datetime

# Positive weights are reasons to look; negative ones are reasons the name is probably somebody's legitimate business.
WEIGHTS: dict[str, int] = {
    "homoglyph": 6,             # the class a reader cannot catch: a Cyrillic к rendered as k
    "hyphen": 3,                # kb-star.com reads as legitimate
    "combosquat": 3,            # the brand beside a word supplying urgency
    "typo": 3,                  # nobody registers a misspelling by accident
    "tld": 0,                   # the bare name under another suffix proves nothing on its own
    "lure_keyword": 2,          # ...-login, ...-secure: the name states its purpose
    "dedicated_certificate": 3,  # nothing else rides on the certificate: it was obtained for this name
    "young": 3,                 # first certificate inside the recency window
    "burst": 2,                 # certificates arrive close together and stop
    "co_tenanted": -3,          # unrelated names share the certificate — a reseller or shared hosting arrangement
    "long_established": -4,     # a certificate history measured in years
    "generic_term": -3,         # the brand term is also an ordinary word
}

TIERS = [(10, "review"), (6, "watch"), (3, "weak")]
DEFAULT_TIER = "noise"

RECENT_DAYS = 180
BURST_DAYS = 21
BURST_MAX_CERTIFICATES = 6
ESTABLISHED_DAYS = 730


@dataclass
class Finding:
    domain: str
    display: str
    brand: str
    klass: str
    score: int
    tier: str
    signals: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def days_between(earlier: str, later: str) -> int:
    try:
        start = datetime.strptime(str(earlier)[:19], "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(str(later)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return 0
    return (end - start).days


def tier_for(score: int) -> str:
    for threshold, name in TIERS:
        if score >= threshold:
            return name
    return DEFAULT_TIER


def score_candidate(row: dict, *, as_of: str, lure_keywords: list[str], is_generic: bool) -> Finding:
    """One candidate that exists, with the aggregates of its certificates.

    `row` carries: domain, display, brand, klass, label, certificates, foreign_names, first_not_before,
    last_not_before.
    """
    signals: list[str] = []
    reasons: list[str] = []

    def fire(signal: str, reason: str) -> None:
        signals.append(signal)
        reasons.append(reason)

    klass = str(row["klass"])
    if WEIGHTS.get(klass, 0):
        fire(klass, {
            "homoglyph": "a character is replaced by one that looks identical, so the name cannot be read as wrong",
            "hyphen": "a hyphen makes it read as an official sub-brand",
            "combosquat": "the brand sits beside a word that supplies urgency",
            "typo": "a misspelling nobody types by accident",
        }.get(klass, klass))

    name = str(row["domain"]).split(".", 1)[0]
    matched = [word for word in lure_keywords if word in name]
    if matched:
        fire("lure_keyword", f"the name contains '{matched[0]}'")

    certificates = int(row.get("certificates") or 0)
    foreign = int(row.get("foreign_names") or 0)
    first, last = str(row.get("first_not_before") or ""), str(row.get("last_not_before") or "")

    if foreign == 0:
        fire("dedicated_certificate", "nothing else rides on its certificates — they were obtained for this name")
    else:
        fire("co_tenanted",
             f"{foreign} unrelated name{' shares' if foreign == 1 else 's share'} its certificates — a shared or "
             f"reseller arrangement, not a name bought to impersonate with")

    history = days_between(first, last)
    age = days_between(first, as_of)
    if age and age <= RECENT_DAYS:
        fire("young", f"first certificate {age} days ago")
    if history > ESTABLISHED_DAYS:
        fire("long_established", f"certificates spanning {history // 365} years — an established business")
    if certificates and certificates <= BURST_MAX_CERTIFICATES and history <= BURST_DAYS and first:
        fire("burst", f"all {certificates} certificates within {max(history, 1)} day{'' if history == 1 else 's'}")

    if is_generic:
        fire("generic_term", "the brand term is also an ordinary word, so others use it legitimately")

    score = max(0, sum(WEIGHTS.get(signal, 0) for signal in signals))
    return Finding(domain=str(row["domain"]), display=str(row.get("display") or row["domain"]),
                   brand=str(row["brand"]), klass=klass, score=score, tier=tier_for(score),
                   signals=signals, reasons=reasons)
