---
name: cite-holmes
version: 3.12.0
author: DoctorQ Lab
license: MIT
description: >-
  Deep research that interrogates its own sources (Verified Deep Research):
  calibrates scope first (3-5 sharp questions), then searches iteratively and
  machine-verifies every citation. Also a standalone citation checker: paste
  any reference list and it runs full citation verification (it will verify
  citations before you cite) against official registries —
  hallucinated references, fabricated DOIs, fake PMIDs, arXiv IDs, stitched
  fakes, retracted papers; a fact check for your bibliography. Five verdicts;
  unverified references never masquerade as real (AI hallucination detection).
  Medical mode (Cochrane/BMJ/ChiCTR/NMPA/CDC/NICE presets, PMID check) and
  bibliography export (BibTeX/GB·T 7714-2025/RIS/CSV + JSON workpaper) built
  in. Trigger matching is semantic, not exact — mis-triggers are harmless;
  state your real intent to avoid them.
when_to_use: >-
  Use when the user says "deep research", "look into", "investigate",
  "compare A vs B", "fact check", "verify this claim", "is it true that...",
  "check these references", "are these citations real", wants a research
  report with sources, a literature review, a medical evidence lookup, or
  wants references verified before submission — even if they never say the
  word "research".
---

# cite-holmes (Cite Holmes): deep research with citation verification

One line: **a question goes in — a verified report comes out.**

Three differences from a plain "search and summarize":

1. **Calibrate before working** — ask sharp questions first; the most expensive
   waste is researching the wrong question.
2. **Conclusions carry evidence grades** — 🟢 two independent sources agree /
   🟡 single authority / 🔴 contested.
3. **Every citation is checked** — mechanical layer (reachability, domain
   authority, field completeness, dedup) plus semantic layer (does the source
   actually support the claim?). Unverified references never masquerade as real.

## ⛔ Iron rules (zero exceptions)

1. **Never fabricate**: citations must come from pages actually fetched this
   session. Re-search rather than write URLs from memory.
2. **Never pretend**: unchecked references are marked `unverified`; fetch
   failures are `unreachable` (≠ nonexistent — flagged for human review).
3. **Don't hide conflicts**: when sources disagree, present the disagreement,
   mark 🔴, show each side's evidence.
4. **Budgeted search**: QUICK ≤6 searches, FULL ≤15. Out of budget → state the
   gaps honestly instead of forcing conclusions.
5. **Calibrate before searching** (FULL mode): scope / timeframe / audience /
   output format must be locked first.

## Step 0: mode selection

| Mode | Fits | Calibration | Budget | Output |
|---|---|---|---|---|
| **QUICK** | Single fact-check: "is this claim true", "when was X released" | skipped | ≤6 | short report |
| **FULL** | Open research: "state of X", "A vs B", "do a survey" | mandatory | ≤15 | full report |

A question answerable by one verifiable fact → QUICK. Needs synthesis or
trade-offs → FULL. "Quick check" forces QUICK; "thorough/comprehensive" forces
FULL. When unsure, default FULL.

Pre-submission bibliography final check skips this choice entirely: run
`--preset submission` on the reference list (one flag = strict + exports).

## Five-phase workflow

### 1. CALIBRATE (FULL only)

Ask 3–5 high-leverage questions at once (no drip-feeding): scope, timeframe,
audience/depth, output format, decision context. Never re-ask what the user
already provided. If the user declines ("your call"), proceed with stated
defaults.

### 2. PLAN

Show a short plan: 3–7 sub-questions, source priority (primary/official >
major media > community/blog as leads only), budget.

### 3. SEARCH (iterative, not one pass)

**Read `references/search-strategies.md` first** (diamond expansion, source
pyramid, query matrix, gap-driven iteration). Essentials: each round targets
one sub-question; evolve queries with discovered terms; search both English
and Chinese for topics that span both internets; fetch full text of the 2–5
most valuable sources (never conclude from search snippets); verify key
numbers/dates in the original page before quoting.

### 4. VERIFY (the heart of this skill)

Register every reference in `research_refs.json` (schema in
`references/report-template.md`), then run:

```bash
python scripts/verify_refs.py --refs research_refs.json --out verify_report.md
# Got a .bib from Zotero/EndNote? Feed it directly (v1.9):
python scripts/verify_refs.py --refs bibliography.bib --out report.md
# Environment self-check before a big batch (v3.10) — zero outbound calls
# by default, add --net to probe every academic registry:
python scripts/verify_refs.py --doctor --net
```

Five verdicts: `verified` / `partial` / `unreachable` (needs_human_check) /
`invalid` / `unverified`. Every identifier (`url` / `doi` / `pmid` / `arxiv`)
is cross-checked against its official registry (DOI.org metadata, NCBI
E-utilities for PMID, export.arxiv.org for arXiv), so fabricated IDs are
judged `invalid` — never silently `unreachable`. Every report opens with a
**BLUF dual-reader header** (machine-parseable YAML + 5-line human TL;DR), a
**CiteScore** (0-100 + A-D grade) and a one-line **pre-submission conclusion**
(arXiv has banned authors over hallucinated references since 2026-05; ICML
2026 desk-rejects them too).

**Mechanical layer (the script)**: claim↔registry title/year/journal/author
consistency; 11 machine-readable error codes on every judgment (v3.9);
**clone-pair detection** (v3.10 — same title under different DOIs, or one DOI
carrying different titles, flagged in pairs: the most common fabrication shape
in generated text); **cross-lingual title bridging** (v3.10 — a Chinese
original title claimed against an English registry record is resolved via the
bilingual `original-title` field, the DOI landing page, or OpenAlex; a hit
upgrades to `verified`, a miss keeps `partial`, and a language difference is
never treated as fabrication evidence); retraction checks (Crossref online, or
instantly offline via an optional local Retraction Watch index
`--retraction-cache`); Wayback archive links attached to dead links; arXiv
landing-page fallback keeps verdicts deterministic when its API flakes;
**Bibliography profiling** (v3.11 — batch-fabrication
fingerprints across the whole list: serial identifier clusters, year
over-concentration or future years, single-source concentration, bare-entry
share; flags are human-review leads, never verdicts); **preprint→published
hints** (v3.11 — an arXiv-only reference that has since been registered as a
journal article gets annotated with the formal-version DOI, via Semantic
Scholar, silent on rate limits); per-reference **completeness scoring**
(v3.11 — how many export fields the registry CSL can back-fill, with the
missing-field list for authors deciding what to complete before export).
parallel verification (`--workers`, default 4) plus a local disk cache
(default on, 7-day TTL) make repeat runs cheap and verdicts stable. Behind a
firewall: `--proxy http://host:port`, `--cn` (resilient preset: 25s floor +
Crossref re-source), or `--preflight` to see registry status before the batch;
when 3+ registries fail at transport level the run flips to degraded-network
mode — fast, honest skips instead of minutes of waiting.

**Semantic layer (the model)**: decompose each cited claim into atomic
claim-triplets (subject–relation–object, RefChecker style) BEFORE judging,
then verify each triplet against the source — granularity moves from
paragraph to triple, so "which half-sentence is wrong" becomes answerable.
Register the verdict structurally so it becomes auditable workpaper, not a
feeling:
`"semantic": {"claim": "...", "support": "supported|partial|not_in_source|
contradicted|unclear", "quote": "...", "note": "..."}`. The verifier carries
it into `--export auditjson` and a report section; `not_in_source` /
`contradicted` cap the mechanical verdict at `partial` with a human-review
flag — a source that exists is not a source that agrees.

**Multi-source confirmation**: verified titles get an OpenAlex bibliographic
cross-check; DOI references whose registry metadata could not be fetched get
a Semantic Scholar second confirmation; references with no DOI/PMID/arXiv at
all get a Semantic Scholar title-search confirmation — confirmation only,
never a downgrade: databases have coverage gaps, "not found" ≠ fabricated.

**Task → flag** (details in `references/verification-details.md`):

| Task | Flags |
|---|---|
| Medical topics | `--easy` (auto medical + exports) · `--profile medical` |
| Share / archive | `--format html` (self-contained single file) |
| Export | `--export bibtex,gbt7714,ris,csv,auditjson` |
| CI | `--strict` · `--offline` (structure only, caps at `partial`) |
| Polite pacing | `--mailto you@lab.edu` |
| API keys | `--openalex-key` / `--s2-key` / `--ncbi-key` (env of same name) |
| Weak network | `--proxy` · `--cn` · `--preflight` · `--timeout` |
| Cache | `--no-cache` / `--refresh-cache` / `--cache-ttl` |
| Self-check | `--doctor` (add `--net` for registry probes) |
| Pre-submission final check | `--preset submission` (strict + GB·T/BibTeX/CSV exports in one flag) |
| Explain one verdict | `--explain N` (plain-language chain: semantics / evidence / error codes / notes / completeness) |
| External judging | `--judge-url` / `--nli-url` / `--fast-judge-url` (notes only, never flip verdicts) |
| MCP server | `mcp/server.py` — tools `verify_references` / `explain_verdict` / `check_document`, resources (capability matrix, changelog), `fact_check_workflow` prompt |

**Offline mode (`--offline`)**: structure checks only — honesty first, never
awards `verified`.

**Medical research mode (v1.2)**: for clinical questions read
`references/medical-mode.md` first and run with `--profile medical`.

### 5. SYNTHESIZE

Follow the skeleton in `references/report-template.md`: executive summary
first; every key conclusion carries a confidence grade + citation ids; the
reference table carries verdicts; `unverified/unreachable` items live only in
the "human review" section; finish with gaps, disagreements, and follow-up
questions.

## Files

| File | When |
|---|---|
| `scripts/verify_refs.py` | VERIFY phase mechanical check (pure stdlib, cross-platform, rate-limited) |
| `mcp/server.py` | optional MCP server: expose `verify_references` as an MCP tool (FastMCP; same engine) |
| `references/search-strategies.md` | read before SEARCH |
| `references/report-template.md` | skeleton for SYNTHESIZE; refs schema |
| `references/verification-details.md` | full option semantics, cross-check rules, thresholds |
| `references/faq.md` | common questions (network, PMID wording, exports) |
| `references/medical-mode.md` | read before medical/clinical research (v1.2) |
| `examples/demo_refs.json` | general demo: 8 refs, 3 planted fabrications |
| `examples/medical_refs.json` | medical demo: PMID/DOI refs + planted fake PMID + planted duplicate |

## ⚠️ Common mistakes (anti-patterns)

- Treating `verified` as "the content is correct" — verification confirms the
  source exists and matches the claim's source, not that the reasoning holds.
  The semantic check and your own reading still matter.
- Citing a `partial` source as if it were reliable — `partial` means downgrade
  or explain in the text; never silently promote it.
- Retrying `unreachable` links forever — open the Wayback link once, then
  switch sources if it stays dead.
- Relying on `--easy` for clinical work — auto-detection is a convenience;
  for real medical conclusions pass `--profile medical` explicitly.
- Running without `--strict` in CI/automated pipelines and expecting exit
  codes to gate anything.
- Assuming `verified` means "safe to cite forever" — retracted papers are
  flagged (Crossref/Retraction Watch), but retraction status can change after
  your run.

## Security & behavior declaration

- Single-run CLI: start, verify, write the report, exit. No daemons, no
  background jobs, nothing downloaded or installed at runtime (pure standard
  library).
- Network access is limited to these official academic registries, always over
  HTTPS: `doi.org`, `api.crossref.org`, `eutils.ncbi.nlm.nih.gov`,
  `export.arxiv.org` / `arxiv.org`, `archive.org`, `api.openalex.org`,
  `api.semanticscholar.org`, `pubmed.ncbi.nlm.nih.gov`. No other hosts are
  contacted; no telemetry, no analytics, no data collection.
- Your reference lists and reports stay on your machine — the only outbound
  payloads are the identifiers and titles you asked to verify.
- Optional environment variables `OPENALEX_API_KEY` / `S2_API_KEY` /
  `NCBI_API_KEY` authenticate
  your own requests to those two APIs and are never sent anywhere else. The
  local verdict cache lives under `~/.cache/cite-holmes/` (`--no-cache` to
  disable).
- No OS integration: no subprocesses, no system services, no privilege
  changes; file access is limited to your inputs/outputs plus the cache and
  report paths you pass.

## Honest limits

- Not a fit for: PDF/Word documents (extract citations manually first),
  Chinese-database-only IDs (Wanfang/CQVIP numbers — verify via URL or title
  instead), and fact-checking what a page *claims* (the mechanical layer
  verifies existence and consistency; meaning is the semantic layer's job).
- A fabricated citation pointing to a real, live, plausible page passes the
  mechanical layer; the semantic layer may catch it — model judgment, not a
  guarantee.
- `unreachable` ≠ fake; database "not found" ≠ fabricated (coverage lag).
- No public-registry check replaces reading the source — the July 2026 arXiv
  survey of citation checkers found none reliable enough to run unsupervised;
  treat this skill as a transparent multi-source assistant with a full audit
  trail (`--export auditjson`), not an oracle.
- Reproducible demo: `python scripts/verify_refs.py --refs examples/demo_refs.json`
  (8 refs, 3 planted fabrications, all caught).
- Medical demo: `python scripts/verify_refs.py --refs examples/medical_refs.json
  --profile medical --export bibtex,csv`.

## FAQ

See `references/faq.md` (slow networks / blocked endpoints, what PMID wording
means, exports into Zotero/EndNote, how arXiv IDs are judged). Quick answers:
`verified` is existence+consistency, not truth; `unreachable` ≠ fake;
`--easy` covers the medical profile auto-detection; `--export bibtex` gives
Zotero/EndNote-ready verified-only bibliography.

## 30-second quickstart

```bash
# 1. references as JSON (title/url/source/year per item) — or a Zotero .bib
# 2. verify:
python scripts/verify_refs.py --refs refs.json --out report.md
# 3. read report.md — CiteScore + pre-submission conclusion at the top.
# Medical? add --profile medical.  Paper?  add --export bibtex.
# Institution/CI?  add --mailto you@lab.edu (Crossref polite pool).
```

## Environment fallback

Without web tools: state honestly that only the "user-supplied material +
mechanical verification" mode is possible; never pretend to search.
