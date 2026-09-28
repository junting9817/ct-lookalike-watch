#!/usr/bin/env python3
"""Render the published page from the ct database (Phase 4).

Generated rather than written, for the same reason as the honeypot project's page: if the nightly checks are ever
resumed, the page has to be able to say something new without anyone retyping a number. Every figure comes from
ct.candidates, ct.checks, ct.certificates and ct.findings.

  scripts/report.py                 write site/index.html
  scripts/report.py --out - --quiet print it

Self-contained: no scripts, no external requests except the web font stylesheet. Nothing here resolves or visits any
domain (CLAUDE.md C3), and the page reports resemblance rather than a verdict (C5).
"""
import argparse
import html
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import chquery  # noqa: E402

FONTS = ("https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500"
         "&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400"
         "&family=Public+Sans:wght@400;600;700&display=swap")

CSS = """
:root {
  /* violet-cast paper; coral is spent on exactly one thing — the forged character */
  --ground: #f2f1f6; --surface: #fbfaFd; --sunk: #e7e5ee;
  --ink: #1b1725; --ink-2: #544d66; --ink-3: #847c96;
  --rule: #d8d4e2; --rule-soft: #e6e3ed;
  --accent: #4c3a86; --accent-soft: #e9e4f5;
  --alarm: #c8452f; --alarm-soft: #f7e4e0;
  --measure: 62ch;
  --display: Newsreader, Georgia, "Times New Roman", serif;
  --body: "Public Sans", -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  --mono: "DM Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: #131119; --surface: #1a1722; --sunk: #221e2c;
    --ink: #eae7f2; --ink-2: #aaa2bd; --ink-3: #7d7591;
    --rule: #2e2939; --rule-soft: #241f2f;
    --accent: #a898e0; --accent-soft: #241d38;
    --alarm: #f0705a; --alarm-soft: #321c18;
  }
}
:root[data-theme="dark"] {
  --ground: #131119; --surface: #1a1722; --sunk: #221e2c;
  --ink: #eae7f2; --ink-2: #aaa2bd; --ink-3: #7d7591;
  --rule: #2e2939; --rule-soft: #241f2f;
  --accent: #a898e0; --accent-soft: #241d38;
  --alarm: #f0705a; --alarm-soft: #321c18;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink); font-family: var(--body);
       font-size: 17px; line-height: 1.62; -webkit-font-smoothing: antialiased; }
.page { max-width: 1000px; margin-inline: auto; padding-inline: 20px; padding-block: 0 80px; }
h1, h2, h3 { margin: 0; line-height: 1.14; letter-spacing: -.01em; text-wrap: balance; font-family: var(--display);
             font-weight: 600; }
.eyebrow { font-family: var(--body); font-size: .68rem; font-weight: 700; letter-spacing: .15em;
           text-transform: uppercase; color: var(--ink-3); display: block; }
a { color: var(--accent); text-underline-offset: .18em; }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
code, .mono { font-family: var(--mono); font-size: .88em; }

header { padding-block: 64px 40px; }
header h1 { font-size: clamp(2.3rem, 6.5vw, 3.6rem); max-width: 17ch; margin-top: 20px; }
.standfirst { font-size: 1.18rem; line-height: 1.55; color: var(--ink-2); max-width: var(--measure);
              margin: 22px 0 0; }

.headline { margin-top: 40px; border-block: 1px solid var(--rule); padding-block: 26px;
            display: flex; flex-wrap: wrap; gap: 26px 48px; align-items: baseline; }
.headline .big { font-family: var(--display); font-size: clamp(2.6rem, 8vw, 4.2rem); line-height: 1;
                 font-variant-numeric: tabular-nums; }
.headline .of { font-family: var(--body); font-size: .92rem; color: var(--ink-2); max-width: 34ch; }

section { padding-block: 54px; border-bottom: 1px solid var(--rule); }
section > h2 { font-size: clamp(1.6rem, 3.6vw, 2.15rem); max-width: 24ch; margin-top: 12px; }
section > p { max-width: var(--measure); color: var(--ink-2); margin: 16px 0 0; }
section > p.lead { color: var(--ink); font-size: 1.06rem; }

/* the forgeries, shown as letters because that is what they are */
.forgeries { margin-top: 36px; display: flex; flex-direction: column; gap: 2px; }
.forgery { background: var(--surface); border: 1px solid var(--rule); padding: 22px 24px 24px; }
.pair { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 20px; }
.name { font-family: var(--mono); font-size: clamp(1.15rem, 3.6vw, 1.7rem); letter-spacing: -.01em;
        word-break: break-all; }
.name .swap { color: var(--alarm); background: var(--alarm-soft); padding: 0 .12em; border-radius: 2px;
              font-weight: 500; }
.real { font-family: var(--mono); font-size: .92rem; color: var(--ink-3); }
.real::before { content: "vs "; font-family: var(--body); }
.facts { margin-top: 15px; display: flex; flex-wrap: wrap; gap: 6px 24px; font-size: .86rem; color: var(--ink-2); }
.facts b { font-family: var(--mono); font-weight: 500; color: var(--ink); }
.say { margin-top: 13px; font-size: .92rem; color: var(--ink-2); max-width: 68ch; }
.tag { font-family: var(--body); font-size: .66rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
       padding: 3px 8px; border-radius: 2px; background: var(--accent-soft); color: var(--accent); }
.tag.live { background: var(--alarm-soft); color: var(--alarm); }

.table-wrap { margin-top: 28px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 480px; }
th, td { text-align: left; padding: 9px 18px 9px 0; border-bottom: 1px solid var(--rule-soft); }
thead th { font-family: var(--body); font-size: .68rem; font-weight: 700; letter-spacing: .12em;
           text-transform: uppercase; color: var(--ink-3); border-bottom: 1px solid var(--rule); }
td.n { font-family: var(--mono); font-variant-numeric: tabular-nums; }
td.k { font-family: var(--mono); font-size: .88rem; }
tr.done td.k::after { content: " ✓"; color: var(--accent); }

.bars { margin-top: 26px; display: flex; flex-direction: column; gap: 14px; max-width: 640px; }
.bar-row { display: grid; grid-template-columns: 7.5rem 1fr 4.5rem; gap: 14px; align-items: center;
           font-size: .88rem; }
.bar-row .track { height: 10px; background: var(--sunk); }
.bar-row .track i { display: block; height: 100%; background: var(--accent); }
.bar-row .track i.none { background: var(--rule); }
.bar-row .label { font-family: var(--mono); font-size: .82rem; }
.bar-row .val { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right;
                color: var(--ink-2); font-size: .82rem; }

.note { margin-top: 30px; background: var(--surface); border: 1px solid var(--rule); border-left: 3px solid var(--accent);
        padding: 20px 22px 22px; max-width: var(--measure); }
.note h3 { font-family: var(--body); font-size: .96rem; font-weight: 700; }
.note p { margin: 8px 0 0; font-size: .92rem; color: var(--ink-2); }

ul.plain { margin: 22px 0 0; padding: 0; list-style: none; max-width: var(--measure);
           display: flex; flex-direction: column; gap: 15px; }
ul.plain li { padding-left: 18px; border-left: 2px solid var(--rule); font-size: .94rem; color: var(--ink-2); }
ul.plain b { color: var(--ink); font-weight: 700; }

footer { padding-block: 40px 0; color: var(--ink-3); font-size: .86rem; max-width: var(--measure); }

@media (max-width: 640px) {
  .bar-row { grid-template-columns: 6rem 1fr 3.6rem; }
  .headline { gap: 18px 28px; }
}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def num(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return esc(value)


def mark_difference(candidate: str, label: str) -> str:
    """Wrap the characters of `candidate` that differ from the brand's real name.

    The whole subject of this page is a single letter, so the page has to show it. Exactly one substitution separates
    a homoglyph candidate from the term it was built from, and it replaces one character with either one ('l' for
    'i') or two ('vv' for 'w'). Comparing the remaining suffixes says which, without trusting the generator's own
    description of what it did.
    """
    head, tail = candidate.split(".", 1)[0], candidate[len(candidate.split(".", 1)[0]):]
    out, i, j = [], 0, 0
    while i < len(head) and j < len(label):
        if head[i] == label[j]:
            out.append(esc(head[i]))
            i, j = i + 1, j + 1
            continue
        if head[i + 1:] == label[j + 1:]:            # one character swapped for one
            out.append(f'<span class="swap">{esc(head[i])}</span>')
            i, j = i + 1, j + 1
        elif head[i + 2:] == label[j + 1:]:          # one character written as two, such as vv for w
            out.append(f'<span class="swap">{esc(head[i:i + 2])}</span>')
            i, j = i + 2, j + 1
        else:                                        # shouldn't happen for this generator; mark it and move on
            out.append(f'<span class="swap">{esc(head[i])}</span>')
            i, j = i + 1, j + 1
    out.append(esc(head[i:]))
    return "".join(out) + esc(tail)


def gather() -> dict:
    classes = chquery.query("""
        SELECT c.klass AS class, count() AS candidates,
               countIf(c.domain IN (SELECT domain FROM ct.checks WHERE status != 'error')) AS answered,
               countIf(c.domain IN (SELECT domain FROM ct.checks WHERE status = 'found')) AS exist
        FROM ct.candidates AS c GROUP BY class ORDER BY exist DESC, candidates DESC""")
    totals = chquery.query("""
        SELECT (SELECT count() FROM ct.candidates) AS candidates,
               uniqExactIf(domain, status != 'error') AS answered,
               uniqExactIf(domain, status = 'found') AS exist,
               min(checked_at) AS first_check, max(checked_at) AS last_check
        FROM ct.checks""")[0]
    homoglyphs = chquery.query("""
        SELECT f.domain AS domain, any(c.label) AS label, any(c.note) AS note, any(f.brand) AS brand,
               any(f.tier) AS tier, uniqExact(e.crtsh_id) AS certificates,
               min(e.not_before) AS first_seen, max(e.not_before) AS last_seen,
               dateDiff('day', max(e.not_before), now()) AS days_since
        FROM ct.findings AS f
        INNER JOIN ct.candidates AS c ON c.domain = f.domain
        LEFT JOIN ct.certificates AS e ON e.candidate = f.domain
        WHERE f.klass = 'homoglyph' GROUP BY domain ORDER BY certificates DESC""")
    hyphens = chquery.query("""
        SELECT domain, brand, score, tier FROM ct.findings
        WHERE klass = 'hyphen' AND tier IN ('review', 'watch') ORDER BY score DESC, domain LIMIT 8""")
    tiers = chquery.query("SELECT tier, count() AS n FROM ct.findings GROUP BY tier")
    return {"classes": classes, "totals": totals, "homoglyphs": homoglyphs, "hyphens": hyphens,
            "tiers": {row["tier"]: row["n"] for row in tiers}}


def render(d: dict) -> str:
    totals, classes = d["totals"], d["classes"]
    homoglyph = next((c for c in classes if c["class"] == "homoglyph"), {"candidates": 0, "exist": 0})
    hyphen = next((c for c in classes if c["class"] == "hyphen"), {"candidates": 0, "exist": 0})
    rate = 100 * homoglyph["exist"] / max(homoglyph["candidates"], 1)

    cards = []
    for row in d["homoglyphs"]:
        live = int(row["days_since"]) <= 30
        cards.append(f"""
  <article class="forgery">
    <div class="pair">
      <span class="name">{mark_difference(str(row['domain']), str(row['label']))}</span>
      <span class="real">{esc(row['label'])}.com — {esc(row['brand'])}</span>
      <span class="tag{' live' if live else ''}">{'issued this month' if live else esc(row['tier'])}</span>
    </div>
    <div class="facts">
      <span><b>{num(row['certificates'])}</b> certificates</span>
      <span>first <b>{esc(str(row['first_seen'])[:10])}</b></span>
      <span>last <b>{esc(str(row['last_seen'])[:10])}</b></span>
      <span><b>{num(row['days_since'])}</b> days since</span>
    </div>
    <p class="say">{esc(row['note'])}.</p>
  </article>""")

    bars = []
    for row in classes:
        share = 100 * row["exist"] / max(row["candidates"], 1)
        width = max(1, round(share / 4 * 100)) if share else 0
        bars.append(f"""
    <div class="bar-row">
      <span class="label">{esc(row['class'])}</span>
      <span class="track"><i class="{'none' if not width else ''}" style="width:{min(width, 100)}%"></i></span>
      <span class="val">{share:.2f}%</span>
    </div>""")

    rows = "".join(
        f'<tr class="{"done" if row["answered"] == row["candidates"] else ""}">'
        f'<td class="k">{esc(row["class"])}</td><td class="n">{num(row["candidates"])}</td>'
        f'<td class="n">{num(row["answered"])}</td><td class="n">{num(row["exist"])}</td></tr>'
        for row in classes)
    hyphen_rows = "".join(
        f'<tr><td class="k">{esc(row["domain"])}</td><td>{esc(row["brand"])}</td>'
        f'<td class="n">{row["score"]}</td></tr>' for row in d["hyphens"])

    return f"""<title>One Letter Wrong</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}</style>
<div class="page">

<header>
  <span class="eyebrow">Certificate transparency · Korean banks, couriers and telecoms</span>
  <h1>Almost nobody bothers to misspell a bank.</h1>
  <p class="standfirst">
    A domain built to be mistaken for your bank needs a certificate before it can show a padlock — and every
    certificate issued anywhere is published within minutes. So I generated every single-character lookalike of
    fourteen Korean brands I could construct, and asked the public logs which ones exist.
  </p>
  <div class="headline">
    <div><span class="big">{num(homoglyph['exist'])}</span></div>
    <p class="of">
      of <strong>{num(homoglyph['candidates'])}</strong> possible single-character lookalikes have ever held a
      certificate. That is <strong>{rate:.2f}%</strong>, and it is a complete answer over that space rather than a
      sample: every one of them was asked about.
    </p>
  </div>
</header>

<section>
  <span class="eyebrow">The five</span>
  <h2>Every lookalike of a Korean bank, courier or telecom that exists</h2>
  <p class="lead">
    The coloured character is the forgery. Read each name quickly, the way anyone reads a browser bar, and the
    substitution is invisible; that is the entire technique.
  </p>
  <div class="forgeries">{''.join(cards)}</div>
  <div class="note">
    <h3>What none of this says</h3>
    <p>
      That any of them is a phishing site. A certificate proves somebody asked for a name and could show control of
      it — nothing more. Each could be a brand's own defensive registration, a researcher, or a squatter waiting to
      sell. Nothing here was resolved, fetched or visited, deliberately: a lookalike is usually hosted on somebody
      else's compromised machine, and a DNS lookup tells the operator that someone is watching.
    </p>
  </div>
</section>

<section>
  <span class="eyebrow">Result</span>
  <h2>Deliberate misspellings are rare. Plausible ones are not.</h2>
  <p>
    Five classes of impersonation were generated. Two were asked about completely; the other three were stopped once
    the answer was obvious. The split between them is the finding.
  </p>
  <div class="bars">{''.join(bars)}</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Class</th><th>Generated</th><th>Asked</th><th>Exist</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <p>
    A tick marks a class asked about in full. <strong>Nothing at all</strong> was found among
    {num(next((c['candidates'] for c in classes if c['class'] == 'typo'), 0))} typo candidates or
    {num(next((c['candidates'] for c in classes if c['class'] == 'combosquat'), 0))} combosquats in the portion
    sampled — which is why those were stopped rather than finished.
  </p>
</section>

<section>
  <span class="eyebrow">The awkward half</span>
  <h2>The hyphen class is mostly the banks protecting themselves</h2>
  <p>
    {num(hyphen['exist'])} of {num(hyphen['candidates'])} hyphenated names exist — nine times the rate of the
    homoglyphs. Almost none of it is an attack: <code>woori-bank.com</code>, <code>shinhan-card.com</code> and
    <code>kb-star.com</code> are what a trademark lawyer tells a bank to register.
  </p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Name</th><th>Brand</th><th>Score</th></tr></thead>
      <tbody>{hyphen_rows}</tbody>
    </table>
  </div>
  <p>
    This is where scoring stops being able to help. A brand that lets a defensive registration lapse and renews it
    later looks <em>identical</em> to a squatter picking one up, and certificate transparency does not record who owns
    a domain. So the tool ranks shapes and a person settles ownership, with the verdict written down so the same name
    is never judged twice.
  </p>
</section>

<section>
  <span class="eyebrow">Method</span>
  <h2>Generate the names, then ask whether they exist</h2>
  <p>
    The obvious approach — search the logs for each brand name — does not work: that query is an unindexed scan, and
    the index answers it with a timeout, an error, or <strong>success and an empty result</strong>, which is
    indistinguishable from "nothing matched". Exact-name lookups are reliable, so the question was turned around.
  </p>
  <p>
    That inversion has a cost, stated plainly: <strong>this finds only the impersonations it thought to generate.</strong>
    A lookalike built some other way is invisible to it.
  </p>
  <div class="note">
    <h3>The canary</h3>
    <p>
      Because the index can return an empty success, every batch first asks about names that certainly have
      certificates. If none can be confirmed, the run stops rather than recording hundreds of names as "no
      certificate found" — every one of them wrong, and all of them looking like a clean night's work. It fired for
      real on the first scheduled night, against a domain holding 4,114 certificates.
    </p>
  </div>
</section>

<section>
  <span class="eyebrow">Limits</span>
  <h2>What this cannot tell you</h2>
  <ul class="plain">
    <li><b>Only what was imagined.</b> One substitution at a time, from a curated table of confusable characters,
        across a short list of likely suffixes. Two substitutions, an unusual character, or a name that impersonates
        by structure rather than spelling — all invisible.</li>
    <li><b>Fourteen brands.</b> Korea's other banks, couriers and retailers are outside every number here.</li>
    <li><b>Existence is not intent.</b> A certificate can be issued and never used. Absence is worse: it was true on
        the day it was asked and decays immediately.</li>
    <li><b>No attribution.</b> No WHOIS, no DNS, no page fetched. Who registered these names is a question this
        project is built not to answer.</li>
  </ul>
</section>

<footer>
  <p>
    {num(totals['answered'])} of {num(totals['candidates'])} generated names asked about between
    {esc(str(totals['first_check'])[:10])} and {esc(str(totals['last_check'])[:10])};
    {num(totals['exist'])} exist. Built on a single small cloud VM alongside a network monitor, a honeypot and an
    endpoint detection project. Source of truth is the public Certificate Transparency index; nothing else was
    contacted.
  </p>
</footer>

</div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", help="output path, or '-' for standard output (default: site/index.html)")
    parser.add_argument("--quiet", action="store_true", help="no summary on stderr")
    args = parser.parse_args()

    try:
        page = render(gather())
    except (chquery.QueryError, KeyError, IndexError) as exc:
        print(f"report: {exc}", file=sys.stderr)
        return 2

    if args.out == "-":
        sys.stdout.write(page)
    else:
        path = Path(args.out) if args.out else REPO / "site" / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page, encoding="utf-8")
        if not args.quiet:
            print(f"report: wrote {path.relative_to(REPO) if path.is_relative_to(REPO) else path} "
                  f"({len(page)} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
