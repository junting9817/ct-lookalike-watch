# Tuning log

Every false positive, what caused it, and what changed. Newest first.

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
