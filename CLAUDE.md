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

- **C1 — Generate the impersonations, then ask whether they exist** (revised 2026-09-17 after measurement).
  The original plan was to query crt.sh for substrings of each brand name. Measurement killed it: a substring query
  is an unindexed scan, and crt.sh answers it with a 502, a timeout, or — worst of all — **HTTP 200 and an empty
  array**, which looks exactly like "nothing matched". Its PostgreSQL interface, the documented way to run such
  queries, refuses connections on IPv4 and this VM has no IPv6 route.
  Exact-domain lookups are indexed and reliable: 1.3–2.8 s, with a clear 404 or empty result when a name has no
  certificate. So the project is inverted. It generates the names an impersonator would plausibly register —
  homoglyph and punycode forms, typo classes, hyphen insertions, lure-keyword combosquats — and asks Certificate
  Transparency which of them actually exist. The generator is the substance of the project; crt.sh is only the oracle.
  **The limit this accepts:** it can only find impersonations it thought to generate. A firehose consumer would find
  the unanticipated ones, and does not fit on this VM (C7).
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
  spaced apart, retried with backoff, cached on disk, and sent with a User-Agent that identifies the project. The
  candidate budget per run is capped and printed, so the cost to that service is a number someone decided rather than
  a number that grew.
- **C7 — A canary query proves the oracle is answering.** Because crt.sh can return an empty success, every run first
  asks for a domain that certainly has certificates. If the canary comes back empty, the run aborts instead of
  recording thousands of names as "no certificate found". An answer that is wrong in the shape of a right answer is
  the failure this project is most exposed to.

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
│   ├── lib/candidates.py           # the generator: homoglyph, hyphen, combosquat, typo, tld
│   ├── generate-candidates.py      # the imagined space -> ct.candidates               (Phase 2)
│   ├── check.py                    # crt.sh oracle -> ct.checks, ct.certificates       (Phase 3)
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
- **Phase 2**: the candidate generator and the `ct` schema — homoglyph, typo, hyphen and combosquat classes, a printed
  budget, and deterministic output. Done when the same watchlist produces the same candidates twice and the plan can
  be reviewed before any request is made.
- **Phase 3**: `check.py` — the crt.sh oracle with its canary, backoff and cache, recording which candidates exist.
  Done when a second run adds no duplicates, and a deliberately broken oracle aborts the run instead of recording
  everything as absent.
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

- Phase 4: **complete** 2026-09-17. Dashboard `CT — brand lookalikes` provisioned and live in the lab's Grafana
  (uid `ct-lookalikes`, NSM folder, 11 panels, every query verified against real data). `grafana_ro` was granted
  SELECT on `ct.*` in the lab's users.d and the config hot-reloaded — no restart, no compose change, no new exposure.
  Installed by copying into the lab's provisioned directory rather than adding a mount, so the internet-facing
  Grafana never had to be restarted; `scripts/install-dashboard.sh --remove` undoes it
- Phase 4 (scoring half): built 2026-09-17 (`lib/scoring.py`, `score.py`, `ct.findings`, `generic_terms` in the
  watchlist). Twelve named signals with weights; a finding lists the ones that fired, in words. On the 11 existing
  names it puts `kbfg.shop` and `nonghyup.org` at the top and every established business at 0. It also corrected a
  wrong finding of mine: certificates here carry at most six names, not dozens, so the signal is whether *any*
  unrelated name shares the certificate, not how many. The dashboard half needs `grafana_ro` granted SELECT on `ct`,
  which is a lab change and needs my agreement first. Waiting for my confirmation
- Phase 3: built 2026-09-17 (`lib/oracle.py`, `check.py`, `docs/method.md`, `docs/tuning.md`, `docs/limits.md`).
  89 candidates asked about: 30 homoglyph (0 exist), 45 combosquat (0 exist), 14 TLD-swap (11 exist, 1,712
  certificate names stored). The canary works both ways — it confirmed 4,114 certificates for the control name before
  each batch, and aborted the run when pointed at a name that cannot exist. Two rotation bugs found by running it:
  alphabetical tie-breaking marched through the space instead of sampling it, and an error counted as "checked" so
  the hardest names would have been asked about least. Both fixed. First tuning findings recorded: dictionary-word
  terms collide with unrelated businesses, and certificate counts are inflated by shared hosting certificates.
  Waiting for my confirmation
- Phase 2: built 2026-09-17 (`lib/candidates.py`, `generate-candidates.py`, `schema/001_ct.sql`). 6,401 candidates
  from 14 brands: 2,946 typo, 1,458 combosquat, 1,196 homoglyph, 504 hyphen, 297 TLD — of which **936 are punycode**,
  the class a reader cannot catch by eye. Deterministic and idempotent: a second run leaves 6,401 rows for 6,401
  distinct names. Checking all of them would take about 12.4 hours at 7 s per lookup, which is why Phase 3 budgets
  and rotates instead of sweeping. Waiting for my confirmation
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
