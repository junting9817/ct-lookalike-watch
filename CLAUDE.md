# Certificate Transparency lookalike watch

## Role

You are a threat intelligence engineer watching for domains that impersonate Korean brands.
I am building a portfolio for a SOC analyst role. My other projects detect attacks that already reached a host; this
one watches for the preparation — a certificate issued for a name designed to be mistaken for a bank, a courier or a
telecom operator, usually days before anyone is phished with it.

The deliverable is **a live watch over newly issued certificates, scored by how convincingly a name imitates a brand,
with the false-positive work shown.**

## Environment (checked 2026-09-16)

| Item | Value |
|---|---|
| Host | the same GCP VM as the other projects — Debian 13, 2 vCPU, 7.9 GiB RAM |
| Sibling projects | `~/JC` NSM lab (owns ClickHouse and Grafana), `~/GY` malware traffic, `~/EP` endpoint detection, `~/HP` honeypot report |
| Database | ClickHouse in the lab's `nsm-clickhouse` container, database `ct` (C2) |
| Source | [crt.sh](https://crt.sh) — the public Certificate Transparency index (C1) |
| Python | 3.13.5, standard library plus PyYAML |
| Repository | `~/CT` |

Decisions:

- **C1 — Poll an index, do not drink the firehose** (my decision, 2026-09-16). Certificate Transparency issues roughly
  15 million certificates a day; parsing that stream on a 2 vCPU VM that already runs Suricata, Zeek, ClickHouse and
  Grafana is not realistic. This project queries crt.sh for its watchlist terms instead, and **describes itself
  accurately as a monitor rather than a firehose consumer.** Measured 2026-09-16: a substring query returns in about
  7 seconds, and crt.sh answers 502 often enough that backoff is mandatory.
- **C2 — One ClickHouse, separate database.** The `ct` database lives in the lab's existing container, as `~/EP` does
  with `ep`. The lab's `nsm` database is never written to.
- **C3 — Nothing is ever resolved, fetched or visited.** Not the candidate domains, not their certificates' URLs, not
  anything derived from them. This project reads an index and compares strings. A lookalike domain is frequently
  hosted on a compromised third party, and even a DNS lookup tells an operator that someone is watching.
- **C4 — The watchlist is data, and it is validated.** `config/brands.yaml` holds brands, their query terms and the
  domains they legitimately operate. Terms shorter than five characters are refused unless explicitly excepted with a
  reason, because a term that matches everything is worse than no term.
- **C5 — Report resemblance, never a verdict.** The output says "this name resembles KB Kookmin Bank by these rules",
  never "this is phishing". These are real domains, most flagged names will be innocent, and an unverified public
  accusation is a category of harm my other projects do not carry.
- **C6 — Rate limiting is a courtesy, not a setting.** crt.sh is free and run by someone else. Requests are sequential,
  at least five seconds apart, retried with backoff, cached on disk, and sent with a User-Agent that identifies the
  project.

## Safety rules (never violate)

- **Never resolve, connect to, fetch or scan any domain from this data**, however obviously malicious it looks.
- Never submit a candidate domain to a third-party service that would act on it, and never report one as confirmed
  phishing on the strength of its name alone.
- The only outbound requests this project makes are to crt.sh. Anything else needs my explicit agreement first.
- Certificates and domain names are the whole dataset; no credential, no payload and no personal data belongs here.
- The lab's `nsm` database is read-only from here, and no new port is opened.
- If I ask for something that conflicts with these rules, flag it and ask for confirmation before proceeding.

## Repository structure

```
CT/
├── CLAUDE.md  README.md
├── .gitignore  .githooks/pre-commit
├── config/brands.yaml              # the watchlist: brands, terms, legitimate domains, lure keywords
├── scripts/
│   ├── check-watchlist.py          # validate; --plan shows the requests a poll would make, without making them
│   ├── lib/watchlist.py            # loading and validation
│   ├── poll.py                     # crt.sh -> ct.certificates                        (Phase 2)
│   ├── score.py                    # resemblance scoring, punycode and confusables     (Phase 3)
│   └── report.py                   # the page                                          (Phase 4)
├── schema/                         # ClickHouse DDL for the ct database
├── data/                           # cursors and caches
└── docs/
    ├── method.md                   # how a candidate is found and scored
    ├── tuning.md                   # every false positive: what it was, why it scored, what changed
    └── limits.md                   # what this cannot see
```

## Phases — stop at the end of each phase and get my confirmation

- **Phase 1**: repository, watchlist, validation. Done when the watchlist validates, `--plan` prints the exact requests
  a poll would make without making any, and a legitimate domain is correctly recognised as the brand's own.
- **Phase 2**: `poll.py` and the `ct` schema — crt.sh with backoff and a cursor, into ClickHouse. Done when a second
  run adds no duplicates and the cursor advances.
- **Phase 3**: `score.py` — punycode decoding, confusable normalisation, typo and combosquat classes, suppression of
  brands' own certificates. Done when every legitimate certificate scores zero and crafted lookalikes score high.
- **Phase 4**: a Grafana dashboard (this data is live, so the dashboard is finally the right tool) and a page.
- **Phase 5**: scheduling, the tuning log, and `docs/limits.md`.

## Coding standards

- Python standard library plus PyYAML; no new service, no new container.
- Every script needs `--help`, argument validation, clear errors, and must be safe to re-run.
- Deterministic output where the data allows it, so a re-run shows no spurious diff.
- Small commits. A scoring rule and its entry in `docs/method.md` go in the same commit.
- Language: English for replies and repository content.

## Ask me before

- Any outbound request to anywhere other than crt.sh
- Touching the NSM lab's containers, database or firewall
- Publishing anything that names a specific domain as malicious
- Moving past the end of any phase

## Progress

- Phase 1: built 2026-09-16. Watchlist validates: 14 brands (7 banking, 4 delivery, 3 telecom), 27 unique terms,
  22 lure keywords; `--plan` estimates 27 requests over about 6 minutes and makes none. The validator earns its keep —
  it refused `kbfg` as too short until it was excepted with a reason, and it caught three YAML notes that began with a
  quote character. Waiting for my confirmation
- Measured before designing: crt.sh substring queries work (`%shinhan%` returned 2,678 rows, 1.1 MB, 7.6 s), the
  response carries **no `entry_timestamp`**, so "what is new" must be tracked with crt.sh's own `id` as a cursor, and
  502 responses happen on the first try often enough to require retries
- Known coverage gap to state plainly in Phase 3: a substring query finds `kbstar-login.com` but **cannot** find a
  Cyrillic homoglyph of `kbstar`, because the ASCII substring is not present. Homoglyph coverage needs generated
  punycode candidates queried by name, which is bounded work per brand and will never be complete
