# Certificate Transparency lookalike watch

Every TLS certificate issued on the public internet is published to append-only logs within minutes. That makes the
logs an early-warning feed: a domain built to be mistaken for a bank usually gets a certificate days before anyone is
phished with it.

This project watches those logs for names that imitate Korean banks, couriers and telecom operators — the brands that
Korean smishing actually uses — and scores how convincing each imitation is.

It is the threat-intelligence half of a set that already covers
[network monitoring](../JC), [malware traffic](../GY), [endpoint detection](../EP) and
[honeypot reporting](../HP).

## Status

Phase 1 of 5. The watchlist is built and validated; nothing has been polled yet.

```console
$ scripts/check-watchlist.py
Watchlist OK — 14 brands, 27 unique terms, 22 lure keywords
...
  shortest term: 'kbfg' (4 chars; the floor is 5)
  nothing in the watchlist is ever resolved, fetched or visited

$ scripts/check-watchlist.py --plan
A poll would make 27 requests, one per term, 5s apart.
Estimated wall time: about 5 min 51s. No request is made by this command.
```

## Two rules that shape everything here

**Nothing is ever resolved, fetched or visited.** Not a candidate domain, not a URL from a certificate, nothing. A
lookalike domain is often hosted on a compromised third party, and even a DNS lookup tells the operator that somebody
is watching. This project reads an index and compares strings.

**The output reports resemblance, never a verdict.** It says "this name resembles KB Kookmin Bank by these rules", not
"this is phishing". These are real domains, most flagged names will turn out to be innocent, and an unverified public
accusation is a kind of harm the rest of my projects do not risk.

## What the watchlist is

`config/brands.yaml` — 14 brands across banking, delivery and telecom, each with the terms an impersonator has to
include for a name to look right, and the domains the brand genuinely operates so its own certificates are suppressed.

The file is validated rather than trusted. Terms shorter than five characters are refused unless excepted with a
reason: `kt` as a substring matches thousands of unrelated names, and a term that matches everything is worse than no
term. The validator has already earned it — it refused `kbfg` until the exception was written down.

## What it cannot see

A substring query finds `kbstar-login.com`. It **cannot** find a Cyrillic homoglyph of `kbstar`, because the ASCII
substring is not there. Homoglyph coverage needs generated punycode candidates queried by name — bounded work per
brand, and never complete. That gap is stated rather than papered over, and it is the interesting part of Phase 3.

## Phases

1. **Watchlist** — brands, terms, legitimate domains, and validation. Built.
2. **Poll** — crt.sh with backoff and a cursor, into ClickHouse.
3. **Score** — punycode, confusables, typo and combosquat classes, suppression.
4. **Watch** — a Grafana dashboard, which this time is the right tool because the data is live.
5. **Tune** — the false-positive log and the limits.

Rules in full: [CLAUDE.md](CLAUDE.md).
