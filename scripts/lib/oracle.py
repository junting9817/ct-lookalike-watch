"""Ask crt.sh whether a certificate exists for one exact name (CLAUDE.md C1, C6, C7).

Only indexed lookups happen here — `?q=<domain>` — because that is the question crt.sh can answer quickly and
unambiguously. It returns the name's certificates, or 404, or an empty list; each of those is a real answer.

The thing to be afraid of is the fourth case: crt.sh under load can return HTTP 200 with an empty array for a name
that certainly has certificates. Nothing in the response distinguishes that from a true "no certificate exists", so
this module cannot detect it per-request. `canary()` is the defence — one name known to have certificates, asked
before the batch — and the caller must refuse to record anything if it comes back empty.

Nothing here contacts a candidate domain. The only host this module speaks to is crt.sh.
"""
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = REPO / "data" / "cache"
BASE = "https://crt.sh/"
USER_AGENT = "ct-lookalike-watch/0.3 (portfolio project; contact via repository)"

SECONDS_BETWEEN_REQUESTS = 5
ATTEMPTS = 3
BACKOFF_SECONDS = 8
TIMEOUT_SECONDS = 60


@dataclass
class Answer:
    domain: str
    status: str            # found | absent | error
    detail: str = ""
    attempts: int = 0
    seconds: float = 0.0
    rows: list[dict] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in ("found", "absent")


def cache_path(domain: str) -> Path:
    # Sharded by first two characters: 6,400 files in one directory is slow to list and tedious to inspect.
    return CACHE_DIR / domain[:2] / f"{domain}.json.gz"


def read_cache(domain: str):
    path = cache_path(domain)
    if not path.is_file():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            content = json.load(handle)
        return content if isinstance(content, list) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(domain: str, rows: list[dict]) -> None:
    path = cache_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(rows, handle)


def url_for(domain: str) -> str:
    return BASE + "?" + urllib.parse.urlencode({"q": domain, "output": "json"})


def lookup(domain: str, *, offline: bool = False, log=None) -> Answer:
    """One name. Retries the failures crt.sh actually produces; 404 is an answer, not a failure."""
    if offline:
        cached = read_cache(domain)
        if cached is None:
            return Answer(domain, "error", "no cached answer", 0, 0.0)
        return Answer(domain, "found" if cached else "absent", f"{len(cached)} from cache", 0, 0.0, cached)

    request = urllib.request.Request(url_for(domain), headers={"User-Agent": USER_AGENT,
                                                               "Accept": "application/json"})
    started = time.monotonic()
    detail = ""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8", errors="replace")
            rows = json.loads(body)
            if not isinstance(rows, list):
                return Answer(domain, "error", "response was not a list", attempt, time.monotonic() - started)
            write_cache(domain, rows)
            return Answer(domain, "found" if rows else "absent", f"{len(rows)} certificates", attempt,
                          time.monotonic() - started, rows)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                # crt.sh answers 404 when it has never seen the identity at all.
                write_cache(domain, [])
                return Answer(domain, "absent", "HTTP 404", attempt, time.monotonic() - started)
            detail = f"HTTP {error.code}"
        except json.JSONDecodeError:
            detail = "response was not JSON"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            detail = str(exc)
        if attempt < ATTEMPTS:
            wait = BACKOFF_SECONDS * attempt
            if log:
                log(f"    {domain}: {detail}; retrying in {wait}s ({attempt}/{ATTEMPTS})")
            time.sleep(wait)
    return Answer(domain, "error", detail, ATTEMPTS, time.monotonic() - started)


CANARY_ATTEMPTS = 3
CANARY_WAIT_SECONDS = 20


def canary(domains: list[str], *, offline: bool = False, log=None) -> Answer:
    """Establish that the oracle is answering truthfully, or report that it is not.

    A single failure proves nothing: the first scheduled run of this project was aborted by crt.sh returning HTTP 404
    for a name holding 4,114 certificates, which it had answered correctly minutes earlier. So the canary is
    stubborn — several names, several attempts, with a wait between — and gives up only when none of them can be
    confirmed. Being stubborn here is safe in a way that being stubborn about a candidate is not: a name that is
    *supposed* to have certificates cannot be wrongly confirmed, only wrongly denied.
    """
    last = Answer(domains[0] if domains else "", "error", "no canary configured")
    for attempt in range(1, CANARY_ATTEMPTS + 1):
        for domain in domains:
            answer = lookup(domain, offline=offline, log=log)
            if answer.status == "found":
                return answer
            last = answer
            if log:
                log(f"canary: {domain} came back '{answer.status}' ({answer.detail})")
        if attempt < CANARY_ATTEMPTS and not offline:
            if log:
                log(f"canary: no name confirmed; waiting {CANARY_WAIT_SECONDS}s before attempt "
                    f"{attempt + 1}/{CANARY_ATTEMPTS}")
            time.sleep(CANARY_WAIT_SECONDS)
    return last


def names_in(row: dict) -> list[str]:
    """Every DNS name a crt.sh row carries, lowercased and deduplicated."""
    found: list[str] = []
    for field_name in ("common_name", "name_value"):
        for line in str(row.get(field_name) or "").split("\n"):
            name = line.strip().lower().rstrip(".")
            if name and name not in found:
                found.append(name)
    return found
