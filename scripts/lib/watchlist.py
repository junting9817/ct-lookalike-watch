"""Load and validate the brand watchlist (config/brands.yaml).

The watchlist is the whole premise of this project, so it is validated rather than trusted: a term that is too short
matches half the internet, a legitimate domain written as a URL silently never suppresses anything, and a duplicated
term wastes a request against a rate-limited index every single run.

Nothing here resolves, fetches or contacts anything. These are strings to compare against.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the installer names the package
    yaml = None

REPO = Path(__file__).resolve().parent.parent.parent
WATCHLIST = REPO / "config" / "brands.yaml"

MIN_TERM_LENGTH = 5
TERM_RE = re.compile(r"^[a-z0-9-]+$")
DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
SECTORS = {"banking", "delivery", "telecom", "government", "retail", "other"}


class WatchlistError(Exception):
    """The watchlist is unusable."""


@dataclass
class Brand:
    name: str
    english: str
    sector: str
    terms: list[str]
    legitimate: list[str]
    note: str = ""
    allow_short: list[str] = field(default_factory=list)

    def owns(self, domain: str) -> bool:
        """True when this name is the brand's own domain, or a subdomain of one."""
        candidate = domain.lower().strip(".")
        return any(candidate == owned or candidate.endswith("." + owned) for owned in self.legitimate)


@dataclass
class Watchlist:
    brands: list[Brand]
    lure_keywords: list[str]

    @property
    def terms(self) -> list[str]:
        """Every term, in the order they will be queried — deduplicated across brands."""
        seen: dict[str, str] = {}
        for brand in self.brands:
            for term in brand.terms:
                seen.setdefault(term, brand.english)
        return sorted(seen)

    def brand_for(self, term: str) -> Brand | None:
        return next((brand for brand in self.brands if term in brand.terms), None)

    def owner_of(self, domain: str) -> Brand | None:
        """The brand that legitimately operates this domain, if any."""
        return next((brand for brand in self.brands if brand.owns(domain)), None)


def load(path: Path = WATCHLIST) -> Watchlist:
    if yaml is None:
        raise WatchlistError("PyYAML is not installed (Debian: apt install python3-yaml)")
    if not path.is_file():
        raise WatchlistError(f"{path} not found")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WatchlistError(f"{path}: {exc}") from None
    if not isinstance(document, dict):
        raise WatchlistError(f"{path}: expected a mapping at the top level")

    problems: list[str] = []
    brands: list[Brand] = []
    seen_terms: dict[str, str] = {}

    entries = document.get("brands")
    if not isinstance(entries, list) or not entries:
        raise WatchlistError(f"{path}: 'brands' must be a non-empty list")

    for index, entry in enumerate(entries, 1):
        where = f"brand #{index}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: expected a mapping")
            continue
        name = str(entry.get("name", "")).strip()
        english = str(entry.get("english", "")).strip()
        where = f"'{english or name or where}'"
        if not name or not english:
            problems.append(f"{where}: both 'name' and 'english' are required")
        sector = str(entry.get("sector", "")).strip().lower()
        if sector not in SECTORS:
            problems.append(f"{where}: sector '{sector}' is not one of {', '.join(sorted(SECTORS))}")
        allow_short = [str(term).lower() for term in (entry.get("allow_short") or [])]

        terms = [str(term).strip().lower() for term in (entry.get("terms") or [])]
        if not terms:
            problems.append(f"{where}: needs at least one term")
        for term in terms:
            if not TERM_RE.match(term):
                problems.append(f"{where}: term '{term}' may only contain a-z, 0-9 and '-'")
            elif len(term) < MIN_TERM_LENGTH and term not in allow_short:
                problems.append(f"{where}: term '{term}' is {len(term)} characters; terms shorter than "
                                f"{MIN_TERM_LENGTH} match too much. Add it to allow_short with a reason if it is "
                                f"genuinely distinctive.")
            if term in seen_terms and seen_terms[term] != english:
                problems.append(f"{where}: term '{term}' is already claimed by {seen_terms[term]}; "
                                f"each term is queried once, so a duplicate is a wasted request")
            seen_terms.setdefault(term, english)

        legitimate = [str(domain).strip().lower().rstrip(".") for domain in (entry.get("legitimate") or [])]
        if not legitimate:
            problems.append(f"{where}: needs at least one legitimate domain, or every one of its own certificates "
                            f"is reported as a lookalike")
        for domain in legitimate:
            if not DOMAIN_RE.match(domain):
                problems.append(f"{where}: '{domain}' is not a bare domain — no scheme, no path, no leading dot")

        brands.append(Brand(name=name, english=english, sector=sector, terms=terms, legitimate=legitimate,
                            note=str(entry.get("note", "")).strip(), allow_short=allow_short))

    keywords = [str(word).strip().lower() for word in (document.get("lure_keywords") or [])]
    if not keywords:
        problems.append("lure_keywords is empty; scoring would lose the combosquat signal")
    for keyword in keywords:
        if not TERM_RE.match(keyword):
            problems.append(f"lure keyword '{keyword}' may only contain a-z, 0-9 and '-'")
    if len(set(keywords)) != len(keywords):
        problems.append("lure_keywords contains duplicates")

    if problems:
        raise WatchlistError("the watchlist has problems:\n  - " + "\n  - ".join(problems))
    return Watchlist(brands=brands, lure_keywords=keywords)
