# Tuning log

Every false positive, what caused it, and what changed. Newest first.

---

## 2026-09-18 — the scoring pass, with three cases instead of one

The first scheduled night added `cjlogistlcs.com` (CJ Logistics with `i` written as `l`) and `tvvorld.com` (`tworld`
with `w` written as `vv`). With `woorlbank.com` that is three homoglyph findings — enough to tune against without
fitting the rules to a single example.

`cjlogistlcs.com` is what forced the pass. Two Let's Encrypt certificates in June 2022, expired, then **four years of
silence**, then a fresh SSL.com certificate six days ago valid into 2027. The old scoring put it in `weak`, below
`kbfg.shop`, because its four-year span tripped the *established business* penalty — a penalty earned by trading
continuously, applied here to a name that had done nothing at all.

### What changed

**Penalties now apply only where the resemblance could be coincidence.** This is the principled fix. The
`long_established` and `generic_term` penalties exist for one situation: a brand term that is an ordinary word, which
somebody else uses legitimately. That is a TLD-swap problem. Nobody registers a homoglyph, a typo or a hyphenated
brand name by accident, so for those classes a long history is not innocence — it is a lookalike that has been
running for years. `woorlbank.com` had been scored *down* for exactly that.

**Three signals added:**

| Signal | Weight | Fires when |
|---|---|---|
| `recently_issued` | +3 | a certificate arrived in the last 30 days — the name is in use now, not historically |
| `reactivated` | +4 | silent for a year or more, with 20 certificates or fewer in total, then issued again |
| `high_volume` | +2 | 100 certificates or more: running infrastructure rather than a parked name |

**And one correction inside the same pass.** The first version of `reactivated` fired on any gap over a year, which
promoted `uplus.co` — 754 certificates since 2017 with one 28-month quiet spell — from `noise` to `weak`. A name with
hundreds of certificates and a gap is a business that had a gap. The signal now requires the name to have almost no
history *besides* the reactivation, which is the thing that makes it interesting.

### Before and after

| Name | Was | Now |
|---|---|---|
| `cjlogistlcs.com` | 5 weak | **16 review** — dormant four years, reissued six days ago |
| `tvvorld.com` | — | **13 review** — silent 25 months, then reissued |
| `woorlbank.com` | 9 watch | **11 review** — 1,829 certificates now counted |
| `uplus.co` | 0 noise → 3 weak (regression) | 0 noise |
| `shinhan.top`, `doortodoor.info`, `tworld.online`, `epost.site`, `koreapost.net` | 0 noise | 0 noise |

Three to review, two to watch, three weak, six noise — from 14 names that exist out of 520 asked about.

**Still not claimed:** none of the three is called phishing. Nothing was resolved or visited. What is observable is
the name, its shape, and its timing.

---

## 2026-09-17 — the first genuine finding, and three things it exposes

Replaying the cached answers from the killed run surfaced **`woorlbank.com`** — `wooribank` with the `i` replaced by
an `l`. It is the first candidate that looks like what this project was built to find.

What the data shows, and nothing more:

| | |
|---|---|
| Certificates | 1,829 |
| Distinct names | 326, across three years (2023-10-28 → 2025-10-27) |
| Names resembling remote access | 328 rows — `vpn.`, `sslvpn.`, `owa.`, `exchange.`, `citrix.`, `globalprotect.`, `fortigate.`, `ciscoasa.`, `rdweb.` |
| Also present | randomised prefixes such as `axhuqwww.cpcontacts.`, `rmcqqryyyqimap.`, `cztoqhmirofirewall.` |
| Issuer | Let's Encrypt |

The randomised prefixes and the volume together mean issuance is automated: something requests a certificate for
whatever hostname is asked for. **What that automation serves is not determinable from certificate data, and this
project does not resolve or visit anything, so it is not determined here.** It could be phishing infrastructure, a
sinkhole, a researcher's wildcard, or a squatter monetising traffic. What can be said is that the name is one
character from a Korean bank's, and that somebody has been running automated certificate issuance on it for three
years.

Three gaps it exposes:

1. **Volume is not a signal yet.** It scored 9 on two signals — homoglyph, and dedicated certificates — while 1,829
   certificates across 326 names went uncounted. A parked squat does not look like this.
2. **The threshold missed by one day.** Its history is exactly 730 days and `long_established` fires above 730, so
   the penalty that would have been wrong here was avoided by luck rather than judgement. A signal that depends on a
   coincidence is not yet a good signal.
3. **The name set is itself evidence.** Hundreds of hostnames imitating VPN and webmail endpoints is a shape worth
   scoring directly — far more telling than any count.

**Change:** none yet. These are scoring changes and they deserve to be made deliberately, with the case in front of
them, rather than tuned around a single example.

---

## 2026-09-17 — an hour of lookups, none of them stored

The first scheduled run was killed by `TimeoutStartSec` after exactly one hour, having asked crt.sh about roughly 240
names and stored **none** of them: `check.py` inserted only after its loop finished.

The answers were not actually lost, because the response cache is written per request — `--offline` replayed 232 of
them into the database afterwards, which is how `woorlbank.com` was found at all. But that was luck in the design,
not intent.

**Change:** answers are written in batches of 25, and `SIGTERM` and `SIGINT` stop the loop cleanly and store what has
been collected. An interrupted run now keeps what it learned; asking crt.sh again for answers already received costs
somebody else's service for nothing.

**Change:** the budget is sized from measurement rather than optimism. A lookup costs about 17 seconds once the
politeness pause and crt.sh's retries are counted, not the 7 seconds first estimated, so the nightly budget is 150
(about 45 minutes) inside a 90-minute timeout. Full coverage takes about six weeks rather than three.

---

## 2026-09-17 — the canary fired on its first scheduled night

The nightly service was started for the first time and immediately aborted:

```
== 2/3  asking crt.sh about 250 candidates
check: ABORTED — the canary kbstar.com came back 'absent' (HTTP 404).
       crt.sh is not answering truthfully, and recording 250 names as absent on the
       strength of that would be worse than recording nothing.
```

`kbstar.com` holds 4,114 certificates, and crt.sh had answered for it correctly twenty minutes earlier. This is
exactly the failure decision C7 exists for, caught in production on the first run — 250 names would otherwise have
been recorded as having no certificate, every one of them wrongly, and the record would have looked like a clean
night's work.

**Change:** the canary is now stubborn rather than single-shot. It tries **three names from three different brands**,
up to **three times**, waiting 20 seconds between rounds, and aborts only when none can be confirmed. Being stubborn
is safe here in a way it would not be for a candidate: a name that is *supposed* to have certificates cannot be
wrongly confirmed by retrying, only wrongly denied. Using several brands also means one brand's own migration cannot
masquerade as a crt.sh failure.

Re-run after the change: the canary confirmed on a later attempt and the night proceeded.

**Not changed:** the service still exits non-zero when the canary cannot be confirmed, and systemd still marks it
failed. A night that could not be trusted should be visible as a failure, not smoothed over — the alternative is a
timer that appears to be working while coverage silently stops advancing.

---

## 2026-09-17 — the first 89 answers, and what they taught

The first batches asked about 89 candidates across three classes. Results:

| Class | Asked | Exist |
|---|---|---|
| homoglyph | 30 | 0 |
| combosquat | 45 | 0 |
| tld | 14 | 11 |

Eleven hits, none of which is evidence of anything yet. That ratio is the finding.

### 1. A brand term that is an ordinary word collides with the rest of the world

`epost.site`, `doortodoor.info`, `koreapost.net`, `nonghyup.org`, `uplus.co` all exist. None of them needs to have
anything to do with Korea Post, CJ Logistics, NH Nonghyup or LG Uplus: *epost*, *doortodoor* and *uplus* are ordinary
compounds that businesses everywhere use, and `uplus.co` has been issuing certificates since 2017 and holds 754 of
them.

The `tld` class is where this bites hardest, because it asks about the bare term under a different suffix and
therefore matches any unrelated business that happens to share the word.

**Change:** none to the generator yet — these are real answers to the question asked. The fix belongs in scoring
(Phase 4): the `tld` class must not count as resemblance on its own, and terms that are dictionary words need to be
marked as such in the watchlist so their `tld` hits start from a lower base.

### 2. Certificate counts mean little — but I first got the reason wrong

`shinhan.top` looked significant at 64 certificates, and the names on them included `aac123.xyz`, `mixxx.fun` and
`moviezwap.cool`. I wrote that it was riding batch certificates where *dozens* of unrelated domains share one
certificate. **That was wrong, and the data says so.** The largest certificate here carries six names; the typical one
carries between one and three:

```
candidate         max names per cert   avg   certs
uplus.co                           6   1.3     754
koreapost.net                      3   2.2      75
shinhan.top                        3   1.5      64
```

The real pattern is Cloudflare's: one certificate per site, carrying `domain`, `*.domain` and
`sni.cloudflaressl.com`, and occasionally pairing two unrelated customers on one certificate. So the 64 is a busy
site renewing over five years, not a batching artefact.

**Change:** the signal is not how many names share a certificate but **whether any unrelated name does at all**.
`foreign_names` counts names on the candidate's certificates that are neither the candidate, nor a subdomain of it,
nor CDN filler. Zero means the certificate was obtained for this name (`dedicated_certificate`, +3); one or more
means a shared or reseller arrangement (`co_tenanted`, −3). Cloudflare's own `sni.cloudflaressl.com` is excluded,
because it appears on every such certificate and says nothing about who else is there.

### 3. The interesting hits are the quiet ones

The three candidates that look worth a human's attention are the *small* ones:

| Name | Certificates | Why it stands out |
|---|---|---|
| `gitlab.kbfg.shop` | 4, all in a five-day window in 2021 | a GitLab instance on a name resembling KB Financial Group, issued and then nothing |
| `nonghyup.org` | 2, both on one day in 2025 | a single-name certificate, no hosting batch around it |
| `wooricard.org` | 18, from late 2025 | `*.wooricard.org` and the bare name only — a dedicated setup |

None of these is called phishing here. Each could be the brand's own defensive registration, a partner, or a
squatter. They are simply the ones whose shape is not explained by shared hosting.

**Change:** none needed — this is what the scoring in Phase 4 has to learn to surface, and these three are its first
test cases.

### 4. Two bugs in the rotation, both found by running it

- **Alphabetical tie-breaking marched instead of sampling.** The first batch spent its entire budget on names
  beginning `0`, `1` and `c`; the punycode candidates sort last and would have been reached only after every ASCII
  one. Fixed: the tie-break is a stable hash.
- **An error counted as having been checked.** A name crt.sh could not answer got a timestamp and moved to the back
  of the queue — so the names it finds hardest would have been asked about least. Fixed: only `found` and `absent`
  count as checked; errors are recorded but leave the name overdue.

### 5. crt.sh fails about a quarter of the time

11 retries across 45 requests in one batch, and one candidate unanswerable after three attempts. Backoff absorbs it,
at the cost of making a 45-name batch take far longer than 45 × 7 seconds. This is why the budget is per run rather
than per hour, and why absences are stored with a timestamp rather than treated as settled.
