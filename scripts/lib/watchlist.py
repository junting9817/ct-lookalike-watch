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
REVIEWED = REPO / "config" / "reviewed.yaml"
VERDICTS = {"brand-owned", "third-party", "suspicious", "unknown"}

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
    generic_terms: list[str] = field(default_factory=list)

    def is_generic(self, term: str) -> bool:
        """True when the term is also an ordinary word, so its bare appearance elsewhere means little."""
        return term in self.generic_terms

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

    generic = [str(word).strip().lower() for word in (document.get("generic_terms") or [])]
    for term in generic:
        if term not in seen_terms:
            problems.append(f"generic term '{term}' is not a watchlist term, so marking it generic does nothing")

    if problems:
        raise WatchlistError("the watchlist has problems:\n  - " + "\n  - ".join(problems))
    return Watchlist(brands=brands, lure_keywords=keywords, generic_terms=generic)


def load_verdicts(path: Path = REVIEWED) -> dict[str, dict]:
    """Human verdicts by domain, from config/reviewed.yaml. A missing file means nobody has reviewed anything yet."""
    if yaml is None:
        raise WatchlistError("PyYAML is not installed")
    if not path.is_file():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise WatchlistError(f"{path}: {exc}") from None
    entries = document.get("verdicts") or []
    if not isinstance(entries, list):
        raise WatchlistError(f"{path}: 'verdicts' must be a list")
    found: dict[str, dict] = {}
    problems: list[str] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            problems.append(f"verdict #{index}: expected a mapping")
            continue
        domain = str(entry.get("domain", "")).strip().lower()
        verdict = str(entry.get("verdict", "")).strip().lower()
        if not domain:
            problems.append(f"verdict #{index}: needs a domain")
        if verdict not in VERDICTS:
            problems.append(f"'{domain}': verdict '{verdict}' is not one of {', '.join(sorted(VERDICTS))}")
        if not str(entry.get("note", "")).strip():
            problems.append(f"'{domain}': needs a note saying what was checked")
        if not str(entry.get("checked", "")).strip():
            problems.append(f"'{domain}': needs a 'checked' date, so a stale verdict can be spotted")
        if domain in found:
            problems.append(f"'{domain}': reviewed twice")
        found[domain] = {"verdict": verdict, "note": str(entry.get("note", "")).strip(),
                         "checked": str(entry.get("checked", "")).strip()}
    if problems:
        raise WatchlistError("config/reviewed.yaml has problems:\n  - " + "\n  - ".join(problems))
    return found
