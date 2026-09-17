"""Generate the domain names an impersonator would plausibly register (CLAUDE.md C1).

Certificate Transparency cannot be searched by substring from here, so the question is turned around: instead of
asking "which certificates contain this brand", the project asks "does a certificate exist for *this* name" about a
bounded, deliberately chosen set of names. That makes this module the substance of the project — everything it fails
to imagine is something the watch cannot see.

Five classes, in the order they are worth spending a request on:

  homoglyph   a character replaced by one that looks the same — Cyrillic 'а' for ASCII 'a'. The result is punycode,
              and it is the class a human eye cannot catch, so it goes first.
  hyphen      a hyphen inserted at a word boundary: kb-star.com. Reads as legitimate; costs the attacker nothing.
  combosquat  the brand plus a word that explains the urgency: kbstar-login.com, secure-kbstar.com.
  typo        one character dropped, doubled, transposed, or replaced by its keyboard neighbour.
  tld         the exact brand name under a different top-level domain.

Generation is deterministic: the same watchlist produces the same candidates in the same order, so a run can be
reviewed before it is made and diffed afterwards.

Nothing here resolves, fetches or contacts anything. These are strings.
"""
from dataclasses import dataclass

# Where an impersonator of a Korean brand would plausibly register. Kept short on purpose: every entry multiplies the
# number of requests made to a free service.
PRIMARY_TLDS = ["com", "net", "co.kr", "kr"]
COMBO_TLDS = ["com", "net", "co.kr"]
WIDE_TLDS = ["com", "net", "org", "co", "co.kr", "kr", "online", "site", "shop", "top", "xyz", "info"]

# One substitution at a time. Mixed-script names are what punycode was invented to encode and what registrars are
# supposed to refuse; they are registered anyway.
CONFUSABLES: dict[str, list[str]] = {
    "a": ["а", "ɑ"],          # Cyrillic a, Latin alpha
    "c": ["с"],               # Cyrillic es
    "d": ["ԁ"],               # Cyrillic komi de
    "e": ["е"],               # Cyrillic ie
    "g": ["ɡ"],               # Latin script g
    "h": ["һ"],               # Cyrillic shha
    "i": ["і", "1", "l"],     # Ukrainian i, then the ASCII lookalikes
    "j": ["ј"],               # Cyrillic je
    "k": ["к"],               # Cyrillic ka
    "l": ["1", "ӏ"],          # digit one, Cyrillic palochka
    "m": ["м", "rn"],         # Cyrillic em, and the classic two-letter fake
    "n": ["ո"],               # Armenian vo
    "o": ["о", "0", "ο"],     # Cyrillic o, digit zero, Greek omicron
    "p": ["р"],               # Cyrillic er
    "s": ["ѕ"],               # Cyrillic dze
    "t": ["т"],               # Cyrillic te
    "u": ["ս"],               # Armenian seh
    "w": ["ԝ", "vv"],         # Cyrillic we, and the two-letter fake
    "x": ["х"],               # Cyrillic ha
    "y": ["у"],               # Cyrillic u
}

# Physically adjacent on a QWERTY keyboard: the typo a finger makes, not the one a mind makes.
NEIGHBOURS: dict[str, str] = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr", "f": "drtgvc", "g": "ftyhbv",
    "h": "gyujnb", "i": "ujko", "j": "huikmn", "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm",
    "o": "iklp", "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy", "u": "yhji",
    "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


@dataclass(frozen=True)
class Candidate:
    domain: str          # the name to ask about, punycode-encoded where needed
    display: str         # what it looks like to a reader — differs from `domain` only for homoglyphs
    brand: str
    label: str           # the watchlist term it was built from
    klass: str           # homoglyph | hyphen | combosquat | typo | tld
    note: str            # how it was made, in words


def punycode(label: str) -> str:
    """'kbstаr' (with a Cyrillic a) -> 'xn--kbsr-54d1c'. ASCII labels pass through untouched."""
    try:
        label.encode("ascii")
        return label
    except UnicodeEncodeError:
        return "xn--" + label.encode("punycode").decode("ascii")


def homoglyph_labels(label: str) -> list[tuple[str, str]]:
    """One character swapped for a lookalike, at each position where that is possible."""
    variants = []
    for index, character in enumerate(label):
        for replacement in CONFUSABLES.get(character, []):
            variant = label[:index] + replacement + label[index + 1:]
            if variant != label:
                variants.append((variant, f"'{character}' at position {index + 1} replaced by '{replacement}'"))
    return variants


def hyphen_labels(label: str) -> list[tuple[str, str]]:
    """A hyphen inserted anywhere inside the name. Short labels are skipped: 'k-t' fools nobody."""
    if len(label) < 5:
        return []
    return [(label[:index] + "-" + label[index:], f"hyphen inserted after '{label[:index]}'")
            for index in range(2, len(label) - 1)]


def typo_labels(label: str) -> list[tuple[str, str]]:
    """The four classes of single-character slip, deduplicated and in a stable order."""
    variants: dict[str, str] = {}
    for index, character in enumerate(label):
        dropped = label[:index] + label[index + 1:]
        if len(dropped) >= 4:
            variants.setdefault(dropped, f"'{character}' dropped")
        variants.setdefault(label[:index] + character * 2 + label[index + 1:], f"'{character}' doubled")
        for neighbour in NEIGHBOURS.get(character, ""):
            variants.setdefault(label[:index] + neighbour + label[index + 1:],
                                f"'{character}' mistyped as its keyboard neighbour '{neighbour}'")
    for index in range(len(label) - 1):
        swapped = label[:index] + label[index + 1] + label[index] + label[index + 2:]
        variants.setdefault(swapped, f"'{label[index]}' and '{label[index + 1]}' transposed")
    variants.pop(label, None)
    return sorted(variants.items())


def combosquat_labels(label: str, keywords: list[str]) -> list[tuple[str, str]]:
    """The brand beside a word that supplies the urgency, in the four arrangements people actually register."""
    variants = []
    for keyword in keywords:
        variants += [
            (f"{label}-{keyword}", f"'{keyword}' appended with a hyphen"),
            (f"{keyword}-{label}", f"'{keyword}' prefixed with a hyphen"),
            (f"{label}{keyword}", f"'{keyword}' appended"),
        ]
    return variants


def for_brand(brand, keywords: list[str], *, budget: int, combo_keywords: int = 6) -> list[Candidate]:
    """Candidates for one brand, in priority order, capped at `budget`.

    The cap is applied after ordering, so cutting the budget removes the least valuable classes rather than a random
    slice, and the same budget always yields the same set.
    """
    owned = set(brand.legitimate)
    chosen: dict[str, Candidate] = {}

    def add(label_variant: str, display_label: str, tld: str, klass: str, note: str, source: str) -> None:
        domain = f"{punycode(label_variant)}.{tld}"
        display = f"{display_label}.{tld}"
        if domain in chosen or domain in owned:
            return
        chosen[domain] = Candidate(domain=domain, display=display, brand=brand.english, label=source,
                                   klass=klass, note=note)

    top_keywords = keywords[:combo_keywords]
    for term in brand.terms:
        for variant, note in homoglyph_labels(term):
            for tld in PRIMARY_TLDS:
                add(variant, variant, tld, "homoglyph", note, term)
    for term in brand.terms:
        for variant, note in hyphen_labels(term):
            for tld in PRIMARY_TLDS:
                add(variant, variant, tld, "hyphen", note, term)
    for term in brand.terms:
        for variant, note in combosquat_labels(term, top_keywords):
            for tld in COMBO_TLDS:
                add(variant, variant, tld, "combosquat", note, term)
    for term in brand.terms:
        for variant, note in typo_labels(term):
            for tld in ["com", "net"]:
                add(variant, variant, tld, "typo", note, term)
    for term in brand.terms:
        for tld in WIDE_TLDS:
            add(term, term, tld, "tld", f"the exact name under .{tld}", term)

    return list(chosen.values())[:budget]


def for_watchlist(watchlist, *, budget_per_brand: int, combo_keywords: int = 6) -> list[Candidate]:
    candidates: list[Candidate] = []
    for brand in watchlist.brands:
        candidates += for_brand(brand, watchlist.lure_keywords,
                                budget=budget_per_brand, combo_keywords=combo_keywords)
    return candidates
