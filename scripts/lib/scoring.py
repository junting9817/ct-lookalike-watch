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
    "recently_issued": 3,       # a certificate arrived in the last few weeks — this name is in use now
    "reactivated": 4,           # dormant for a year or more, then issued again: somebody picked it back up
    "high_volume": 2,           # hundreds of certificates is running infrastructure, not a parked name
    "burst": 2,                 # certificates arrive close together and stop
    "co_tenanted": -3,          # unrelated names share the certificate — a reseller or shared hosting arrangement
    "long_established": -4,     # a certificate history measured in years
    "generic_term": -3,         # the brand term is also an ordinary word
}

TIERS = [(10, "review"), (6, "watch"), (3, "weak")]
DEFAULT_TIER = "noise"

RECENT_DAYS = 180
RECENTLY_ISSUED_DAYS = 30
DORMANT_DAYS = 365
# Reactivation only means something when there is almost nothing else. A name with hundreds of certificates and one
# quiet spell is a business that had a quiet spell; uplus.co has 754 certificates since 2017 and a 28-month gap, and
# reading that as "somebody picked this name back up" promoted it out of the noise it belongs in.
REACTIVATION_MAX_CERTIFICATES = 20
HIGH_VOLUME_CERTIFICATES = 100
BURST_DAYS = 21
BURST_MAX_CERTIFICATES = 6
ESTABLISHED_DAYS = 730

# The penalties exist for one situation: a name that resembles a brand *by coincidence*, because the brand's term is
# an ordinary word that somebody else uses legitimately. That is a TLD-swap problem. Nobody registers a homoglyph, a
# typo or a hyphenated brand name by accident, so for those classes a long history is not innocence — it is a
# lookalike that has been running for years. Applying the penalties there is how woorlbank.com, three years of
# automated issuance on a bank's misspelled name, was scored down for its longevity.
COINCIDENCE_POSSIBLE_CLASSES = {"tld"}


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
    since_last = days_between(last, as_of)
    gap = int(row.get("max_gap_days") or 0)
    coincidence_possible = klass in COINCIDENCE_POSSIBLE_CLASSES

    if age and age <= RECENT_DAYS:
        fire("young", f"first certificate {age} days ago")
    if last and since_last <= RECENTLY_ISSUED_DAYS:
        fire("recently_issued", f"a certificate was issued {max(since_last, 1)} days ago — this name is in use now")
    reactivated = gap >= DORMANT_DAYS and certificates <= REACTIVATION_MAX_CERTIFICATES
    if reactivated:
        fire("reactivated", f"silent for {gap // 30} months with only {certificates} certificates in total, then "
                            f"issued again — somebody picked this name back up")
    if certificates >= HIGH_VOLUME_CERTIFICATES:
        fire("high_volume", f"{certificates:,} certificates — running infrastructure, not a parked name")
    if certificates and certificates <= BURST_MAX_CERTIFICATES and history <= BURST_DAYS and first:
        fire("burst", f"all {certificates} certificates within {max(history, 1)} day{'' if history == 1 else 's'}")

    # Longevity and ordinary-word penalties apply only where the resemblance could be coincidence.
    if coincidence_possible and history > ESTABLISHED_DAYS and not reactivated:
        fire("long_established",
             f"{history // 365} years of continuous renewals — an established business, not a dormant squat")
    if coincidence_possible and is_generic:
        fire("generic_term", "the brand term is also an ordinary word, so others use it legitimately")

    score = max(0, sum(WEIGHTS.get(signal, 0) for signal in signals))
    return Finding(domain=str(row["domain"]), display=str(row.get("display") or row["domain"]),
                   brand=str(row["brand"]), klass=klass, score=score, tier=tier_for(score),
                   signals=signals, reasons=reasons)
