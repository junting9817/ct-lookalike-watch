# How a candidate is found

## The question, turned around

The obvious design was to search Certificate Transparency for the brand names. Measurement killed it. crt.sh answers
a substring query (`?q=%kbstar%`) with a 502, a timeout, or — worst — **HTTP 200 and an empty array**, which is
indistinguishable from "nothing matched". Its PostgreSQL interface, the documented way to run heavy queries, refuses
IPv4 connections, and this VM has no IPv6 route.

Exact-name lookups are a different story: indexed, 1.3–2.8 seconds, with an unambiguous answer.

| Query | Result |
|---|---|
| `?q=%shinhan%` | 2,678 rows once, then 502s and empty successes |
| `?q=%kbstar%` | 502, or `200` with `[]` |
| `?q=kbstar.com` | 4,060 rows in 9.5 s |
| `?q=shinhan-secure.com` | `200`, 0 rows, 1.3 s — a true absence |

So the project asks a different question. Instead of *which certificates contain this brand*, it asks *does a
certificate exist for this specific name* — about a set of names it generates itself.

**What that costs:** the watch can only find impersonations it thought to generate. That limit is real, it is not
recoverable by better engineering within this design, and it is the first thing `docs/limits.md` says.

## Generating the names

`scripts/lib/candidates.py`, five classes, ordered by what a request is worth spending on:

| Class | Example | Why it is worth a request |
|---|---|---|
| `homoglyph` | `xn--bstar-txe.com` → displays as `кbstar.com` | The reader cannot see it. A Cyrillic `к` is not a `k`, and no amount of care catches that in a browser bar |
| `hyphen` | `kb-star.com` | Reads as legitimate, costs the attacker nothing |
| `combosquat` | `kbstar-login.com` | The brand plus the word that supplies the urgency |
| `typo` | `bkstar.com` | One character dropped, doubled, transposed, or hit by a neighbouring key |
| `tld` | `kbstar.xyz` | The exact name somewhere cheap |

From 14 brands and 27 terms: **6,401 candidates, of which 936 are punycode.** Generation is deterministic — the same
watchlist yields the same names in the same order — and costs no requests, so the whole imagined space is stored and
the budget is spent later on deciding which parts of it to ask about.

The homoglyph table is deliberately small and curated. Every entry is a character that renders close enough to its
ASCII counterpart to fool a reader at a glance: Cyrillic `а е о р с х`, Armenian `ս`, the digit `0` for `o`, and the
two-letter fakes `rn` for `m` and `vv` for `w`. One substitution at a time, so the set stays bounded and every hit is
explainable in a sentence.

## Asking

`scripts/check.py` takes a budget and works through the space: names never asked about first, then the ones asked
about longest ago. Coverage accumulates over runs while the cost of any single run stays a number someone chose.
Asking about all 6,401 would take about 12.4 hours at a polite five seconds apart, which is the reason the rotation
exists.

Each answer is recorded in `ct.checks` — including the absences, because "no certificate exists for this name" is a
finding that decays, and without a timestamp there is no way to know how stale it is.

## The canary

This is the part worth explaining to anyone reading the code.

crt.sh under load can return `HTTP 200` with an empty array for a name that certainly has certificates. Nothing in
that response distinguishes it from a true absence. A batch run against a degraded crt.sh would therefore record
hundreds of names as "no certificate found" — every one of them wrong, and wrong in a way that looks exactly like a
clean result.

So before any batch, one name known to have certificates is asked about. If it comes back empty, the run stops:

```console
$ scripts/check.py --limit 5 --canary nonexistent-canary-zzz9.example
canary: asking about nonexistent-canary-zzz9.example, which certainly has certificates
check: ABORTED — the canary came back 'absent' (0 certificates).
       crt.sh is not answering truthfully, and recording 5 names as absent on the strength of that
       would be worse than recording nothing.
```

The first version of this project had exactly that bug: its poller read an empty `200` as a clean "no results" and
reported zero findings with every appearance of success. The poller was deleted rather than patched, and the canary
is what replaced it.

## What is stored

| Table | Holds |
|---|---|
| `ct.candidates` | every name the generator imagined, with the class and the sentence explaining how it was built |
| `ct.checks` | one row per question asked: found, absent or error, with timing and the count |
| `ct.certificates` | one row per (name, certificate) for the names that exist |

## What is never done

No candidate domain is resolved, connected to, fetched or scanned — however obviously malicious it looks. A lookalike
is usually hosted on a compromised third party, and even a DNS lookup tells the operator that somebody is watching.
The only host this project speaks to is crt.sh.

And the output reports resemblance, never a verdict. A name that exists is a name that exists; calling it phishing
would be a claim this project has no evidence for.
