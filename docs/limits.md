# What this watch cannot see

The page reports names that resemble a brand and have a certificate. This file is the longer account of what that
does *not* amount to.

## It only finds what it imagined

This is the defining limit, and it is structural rather than a bug. Certificate Transparency cannot be searched by
substring from here (see [method.md](method.md)), so the project generates candidate names and asks whether each
exists. **Every impersonation nobody thought to generate is invisible to it.**

Concretely, it will miss:

- a lookalike built on a word the watchlist does not contain — `kb-onlinebanking.com` when the terms are `kbstar`,
  `kookminbank` and `kbfg`;
- a homoglyph using a confusable character that is not in the curated table;
- two substitutions at once — the generator changes one character at a time to keep the set bounded;
- anything under a TLD outside the small list the generator uses;
- a name that impersonates by structure rather than spelling, such as `kbstar.com.secure-login.net`, where the brand
  appears as a subdomain of a domain the attacker owns.

A firehose consumer — matching every certificate as it is issued — would find those. It does not fit on this VM, and
that trade is decision C1.

## An existing name is not a phishing site

A certificate proves that somebody asked a certificate authority for a name and could demonstrate control of it.
That is all it proves. A name this project flags may be:

- a brand's own domain that is not yet in the watchlist's `legitimate` list — the most common false positive, and the
  reason that list is the thing needing most maintenance;
- a partner, reseller, regional site or agency campaign, legitimately using the brand;
- a defensive registration by the brand itself, which buys lookalikes precisely so that nobody else does;
- a parked domain, a squatter waiting to sell, or a name registered and abandoned.

Nothing here is ever resolved or visited, so the project cannot know which. It reports resemblance and leaves the
verdict to someone who can investigate — which is decision C5 and is not negotiable in this design.

## Absence is a claim with a shelf life

"No certificate exists for this name" is true at the moment it was asked and decays immediately. A name checked last
week may have been registered since. `ct.checks` stores the timestamp of every answer for exactly this reason, and
any report that shows an absence without showing when it was established is misleading.

Rotation makes this worse in a predictable way: with a budget of 50 names a run, a full pass over 6,401 candidates
takes 128 runs. Parts of the space are always stale, and the page has to say which.

## The oracle can be wrong in a way that looks right

crt.sh under load returns `HTTP 200` with an empty array for names that certainly have certificates. The canary
(decision C7) catches a crt.sh that is failing *at the moment the batch starts*; it cannot catch one that starts
failing halfway through. A run could therefore contain a stretch of false absences, and nothing in the data would
distinguish them from true ones.

Re-checking is the mitigation — a name is never marked absent permanently, only absent as of a time — but a single
run's absences should not be treated as certain.

## Coverage is uneven by construction

Candidate counts differ by brand for reasons that have nothing to do with risk: a brand with three watchlist terms
generates roughly three times the candidates of a brand with one, and a longer brand name generates more typo
variants than a short one. Woori Bank has 767 candidates and iLogen has 205. That ratio reflects string length and
term count, not how often either is impersonated.

## What it says nothing about

- **Whether anyone was phished.** This watches for preparation, not for victims.
- **Who registered a name.** No WHOIS lookup is made, and no attribution is attempted.
- **Whether a name is being used at all.** A certificate can be issued and never deployed.
- **Korean brands in general.** Fourteen brands were chosen; the rest of the country's banks, couriers and retailers
  are outside the watchlist and therefore outside every figure here.

## What would make it stronger

In rough order of value: a firehose consumer, to find the unimagined names; a larger and better-maintained
`legitimate` list per brand, since that is where the false positives come from; and a second source of certificate
data, so a single service's outage or silent empty response is not the only thing standing between the report and a
page full of confident mistakes.
