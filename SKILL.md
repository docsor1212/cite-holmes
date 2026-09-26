---
name: cite-holmes
version: 3.0.0
author: DoctorQ Lab
license: MIT
description: >-
  Deep research that interrogates its own sources (Verified Deep Research):
  calibrates scope first (3-5 sharp questions), then searches iteratively
  across sources and languages and machine-verifies every citation. Also works
  as a standalone citation checker: paste any reference list and it will
  verify citations against official registries — full citation verification
  covering hallucinated references, fabricated DOIs, fake PMIDs and arXiv IDs,
  stitched fakes and retracted papers. A fact check for your bibliography, not
  just a search. Five verdicts (verified / partial / unverified / unreachable /
  invalid); unverified references never masquerade as real (AI hallucination
  detection). Medical evidence mode (Cochrane/BMJ/ClinicalTrials/ChiCTR/NMPA/
  CDC/NICE/Wanfang presets, PMID existence check via NCBI E-utilities) and
  verified-bibliography export (BibTeX + audit CSV + JSON workpaper) built in.
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
`references/report-template.md`), then verify on two layers:

**Semantic (the model must do this — claim-triplets, L1)**: decompose each
cited claim into atomic claim-triplets (subject–relation–object, RefChecker
style) BEFORE judging, then verify each triplet against the source —
granularity moves from paragraph to triple, so "which half-sentence is wrong"
becomes answerable. Register the verdict structurally so it becomes auditable
workpaper, not a feeling:
`"semantic": {"claim": "...", "support": "supported|partial|not_in_source|
contradicted|unclear", "quote": "...", "note": "..."}`. The verifier carries
it into `--export auditjson` and a report section; `not_in_source` /
`contradicted` cap the mechanical verdict at `partial` with a human-review
flag — a source that exists is not a source that agrees.

**Mechanical (run the script)**:

```bash
python scripts/verify_refs.py --refs research_refs.json --out verify_report.md
# Got a .bib from Zotero/EndNote? Feed it directly (v1.9):
python scripts/verify_refs.py --refs bibliography.bib --out report.md
```

Five verdicts: `verified` / `partial` / `unreachable` (needs_human_check) /
`invalid` / `unverified`. References may carry `url`, `doi`, `pmid`, or
`arxiv`; every identifier is cross-checked against its official registry
(DOI.org metadata, NCBI E-utilities for PMID, export.arxiv.org for arXiv), so
fabricated IDs are judged `invalid` — never silently `unreachable`. Every
report opens with a **CiteScore** (0-100 + A-D grade) and a **pre-submission
conclusion** (v1.9: "can this go into a submission?" in one line — arXiv has
banned authors over hallucinated references since 2026-05; ICML 2026
desk-rejects them too). If the arXiv API itself flakes (406/403 — its anti-bot
window trips even under polite pacing), v1.11 falls back to the official
arxiv.org/abs landing page for title comparison, so verdicts stay
deterministic across re-runs.

Useful flags (details in `references/verification-details.md`):
`--easy` (auto medical profile + auto exports), `--profile medical`,
`--format html` (self-contained shareable report), `--export bibtex,csv,auditjson`
(verified-only bibliography / audit ledger / per-reference check trail),
`--offline` (structure only, caps at `partial`), `--strict` (CI exit codes),
`--mailto you@lab.edu` (Crossref polite pool — fewer rate limits),
`--openalex-key` / `--s2-key` (API keys; env `OPENALEX_API_KEY` / `S2_API_KEY`).
Agents that prefer tools over skills can run the bundled MCP server
(`mcp/server.py`, FastMCP) exposing three primitives: tools `verify_references`
and `explain_verdict` (plain-language verdict explanations), resources
(capability matrix, changelog), and a `fact_check_workflow` prompt template.
arXiv multi-version references are flagged (unversioned citations to
multi-revision papers, stale version pointers). Every report now opens with a
**BLUF dual-reader header** — a machine-parseable YAML block (verdict /
key_numbers / blocker / next_action) plus a 5-line human TL;DR — defining the
"3-second readable" report standard. Verified DOIs gain a scholarly-reception
section (Semantic Scholar citation contexts, coverage honestly labeled), and
an L4 evidence cascade adds abstract-level judging with configurable external
judge endpoints and bge-m3 passage retrieval (via local ollama, TF-IDF
fallback) for full-text verification. Optional `NCBI_API_KEY`
raises E-utilities throughput from 3 to 10 req/s for parallel batches.
Repeat runs reuse prior verdicts from a local disk cache (default on, 7-day TTL,
`~/.cache/cite-holmes/`; `--no-cache` / `--refresh-cache` / `--cache-ttl` to
tune; `--strict` always bypasses it). Behind a firewall? Pass `--proxy
http://host:port` (or set `HTTPS_PROXY`) — one honest fast pass beats minutes
of waiting. References are verified in parallel (`--workers`, default 4) — a 20-item
bibliography takes roughly a quarter of the serial time; use `--workers 1`
when strict request pacing matters more than speed.

**Multi-source confirmation**: beyond the registries, since v1.8 verified
titles get an OpenAlex bibliographic cross-check (and DOI references whose
DOI.org metadata could not be fetched get a Semantic Scholar second
confirmation since v1.9; references with no DOI/PMID/arXiv at all also get a
Semantic Scholar title-search confirmation since v1.10) — confirmation only,
never a downgrade: databases have coverage gaps, "not found" ≠ fabricated.
Since v1.8, retracted papers are flagged via the Crossref/Retraction Watch API
and capped at `partial` with human-review flags. Unreachable links get a
Wayback Machine archive link attached automatically. A host-level circuit
breaker (v1.6) skips a host after 2 consecutive transport failures instead of
stalling the batch; when 3+ different hosts fail at the transport layer in one
run (restricted-egress signature, common behind national firewalls), v1.10
flips to a degraded-network mode that fast-skips remaining lookups with an
honest note and a one-line fix suggestion (configure a proxy / retry later) —
a fast honest answer instead of minutes of waiting. Duplicate DOI/URL entries
within one run reuse the first verification (cache, marked in the note).

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
