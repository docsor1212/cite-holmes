---
name: cite-holmes
version: 4.1.0
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
  in. Skip when: translation, polishing, rewriting, de-AI-flavoring — anything
  not about citation authenticity (mis-triggers are harmless; state your real
  intent). Trigger matching is semantic, not exact.
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

One verifiable fact → QUICK. Synthesis or trade-offs → FULL. "Quick check"
forces QUICK; "thorough" forces FULL. Unsure → FULL. Pre-submission
bibliography final check skips this choice: `--preset submission` (one flag =
strict + GB·T/BibTeX/CSV exports).

## Five-phase workflow

### 1. CALIBRATE (FULL only)

Ask 3–5 high-leverage questions at once: scope, timeframe, audience/depth,
output format, decision context. Never re-ask what the user provided; if they
decline, proceed with stated defaults. Three rules: order questions by dependency; **each carries a recommended answer phrased so "yes" accepts it**;
facts you can look up yourself never become questions — decisions stay with
the user.

### 2. PLAN

Show a short plan: 3–7 sub-questions, source priority (primary/official >
major media > community/blog as leads only), budget.

### 3. SEARCH (iterative)

Read `references/search-strategies.md` first. Each round targets one
sub-question; evolve queries with discovered terms; search both English and
Chinese when the topic spans both; fetch full text of the 2–5 most valuable
sources (never conclude from snippets); verify key numbers on the original
page before quoting.

### 4. VERIFY (the heart of this skill)

Register every reference in `research_refs.json` (schema in
`references/report-template.md`), then run:

```bash
python scripts/verify_refs.py --refs research_refs.json --out verify_report.md
# Zotero/EndNote .bib feeds in directly:
python scripts/verify_refs.py --refs bibliography.bib --out report.md
# Big batch? Self-check first (zero outbound by default):
python scripts/verify_refs.py --doctor --net
```

Five verdicts: `verified` / `partial` / `unreachable` (needs_human_check) /
`invalid` / `unverified`. Every identifier (`url`/`doi`/`pmid`/`arxiv`) is
cross-checked against its official registry, so fabricated IDs are judged
`invalid` — never silently `unreachable`. Every report opens with a **BLUF
dual-reader header** + **CiteScore** (0-100 + A-D grade) + a one-line
**pre-submission conclusion**.

#### Mechanical layer (the script)

| Capability | Boundary |
|---|---|
| Registry consistency (title/year/journal/author) | 12 machine-readable error codes; thresholds 0.50/0.82 |
| Clone-pair detection | same title under different DOIs / one DOI with different titles — paired leads, never verdicts |
| Cross-lingual title bridging | six writing-system families (Latin/Cyrillic/Greek/Han/Kana/Hangul); hit→`verified`, miss→`partial`; language difference is never fabrication evidence; families outside the six (Arabic/Hebrew/Thai…) do NOT trigger the guard yet — attach an English/romanized title |
| Bibliography profiling | list-level batch-fabrication fingerprints — review leads, never verdicts |
| Preprint upgrade hints | arXiv-only refs since published get the formal DOI annotated |
| Retraction checks | Crossref online, or offline via `--retraction-cache`; notice granularity: retraction / partial retraction / withdrawal → human hand-off, Expression of Concern → caps `verified` at `partial`, correction → note only; a failed check is flagged, never reported as clean |
| Identifier-less references (Vancouver) | PubMed title reverse-lookup → `verified` with PMID anchor back-filled; works from 2 content words; a transport failure is marked `network_error` and never counted as a miss |
| Wayback archive links | attached to dead links automatically |
| Completeness scoring | how many export fields the registry CSL can back-fill |
| Speed | 20-ref mixed list ≈18s at `--workers 4` (default), ≈7s cache-warm, ≈47s serial — measured table: `references/verification-details.md` |
| Weak network | `--proxy` / `--cn` / `--preflight`; auto degraded-network mode after 3+ registry transport failures |

Full semantics: `references/verification-details.md`.

#### Semantic layer (the model)

Decompose each cited claim into atomic
claim-triplets (subject–relation–object) and verify each against the source;
register the verdict structurally (`"semantic": {"claim", "support", "quote",
"note"}`) — it becomes auditable workpaper; `not_in_source`/`contradicted` cap
the mechanical verdict at `partial` — a source that exists is not a source
that agrees.

#### Task → flag

| Task | Flags |
|---|---|
| Medical topics | `--easy` · `--profile medical` |
| Share / archive | `--format html` |
| Export | `--export bibtex,gbt7714,ris,csv,auditjson` |
| CI | `--strict` · `--offline` |
| Polite pacing | `--mailto you@lab.edu` |
| API keys | `--openalex-key` / `--s2-key` / `--ncbi-key` |
| Weak network | `--proxy` · `--cn` · `--preflight` · `--timeout` |
| Cache | `--no-cache` / `--refresh-cache` / `--cache-ttl` |
| Self-check | `--doctor` (add `--net`) |
| Pre-submission check | `--preset submission` |
| Explain one verdict | `--explain N` |
| Pre-submission grill | `--grill report.json` (adversarial review checklist) |
| External judging | `--judge-url` / `--nli-url` / `--fast-judge-url` (notes only) |
| MCP server | `mcp/server.py` — `verify_references` / `explain_verdict` / `check_document` |

### 5. SYNTHESIZE

Follow `references/report-template.md`: executive summary first; every key
conclusion carries a confidence grade + citation ids; the reference table
carries verdicts; `unverified/unreachable` live only in the "human review"
section; finish with a **finding ledger** — revisit the plan's question
list and mark each as answered / partially answered / unresolved (with the
budget ledger: rounds used, remaining), then gaps, disagreements, follow-up
questions.

## Files

| File | When |
|---|---|
| `scripts/verify_refs.py` | VERIFY mechanical check (pure stdlib, cross-platform) |
| `references/GLOSSARY.md` | canonical terms (five verdicts / signals / error codes) with Avoid lists |
| `references/out-of-scope.md` | explicit non-goals + honest limits, each with a reason |
| `references/security.md` | full security & behavior declaration |
| `docs/adr/` | architecture decision records (public layer) |
| `mcp/server.py` | optional MCP server (same engine) |
| `references/search-strategies.md` | read before SEARCH |
| `references/report-template.md` | SYNTHESIZE skeleton; refs schema |
| `references/verification-details.md` | full option semantics, thresholds |
| `references/anti-patterns.md` | misuse catalog, each with an alternative |
| `references/faq.md` | common questions |
| `references/medical-mode.md` | read before medical/clinical work |
| `examples/demo_refs.json` | 8 refs, 3 planted fabrications |

## ⚠️ Common mistakes

See `references/anti-patterns.md` (14 entries, each with the right way
instead). The two that matter most: never treat `verified` as "the content is
correct" — that is the semantic layer's job; never treat `unreachable` as
"fake" — retry via `--cn`/`--proxy` first.

## Security, honest limits, FAQ

- Security & behavior declaration: single-run; HTTPS-only to the official
  academic registries (doi.org / api.crossref.org / eutils.ncbi.nlm.nih.gov /
  export.arxiv.org / api.openalex.org / api.semanticscholar.org / archive.org /
  pubmed.ncbi.nlm.nih.gov); zero telemetry. Full text: `references/security.md`
- Honest limits & explicit non-goals: `references/out-of-scope.md`
- Common questions: `references/faq.md`

## 30-second quickstart

```bash
# 1. references as JSON (title/url/source/year) — or a Zotero .bib
# 2. verify:
python scripts/verify_refs.py --refs refs.json --out report.md
# 3. read report.md — CiteScore + pre-submission conclusion at the top.
# Paper? add --export bibtex.  Medical? add --profile medical.
# Already verified once? add --grill report.json for the review checklist.
```

## Environment fallback

Without web tools: state honestly that only the "user-supplied material +
mechanical verification" mode is possible; never pretend to search.
