# Cite Holmes 🔍

![icon](assets/icon-512.png)

**Deep research that interrogates its own sources.**

Every AI research report you've ever read had a dirty secret: some of those polished references were probably fabricated. [A Nature news analysis suggests tens of thousands of 2025 publications might include invalid AI-generated references](https://www.nature.com/articles/d41586-026-00969-z). [GPTZero scanned 4,841 NeurIPS 2025 submissions; as independently reported, at least 100 hallucinated citations were found across 51 accepted papers](https://medium.com/@ljingshan6/100-fake-citations-just-slipped-through-neurips-2025-peer-review-5f34f4436560).

Cite Holmes is a deep-research skill with a badge and a magnifying glass: it researches like any deep-research agent — then **arrests its own citations before you can cite them**.

![demo](assets/demo.gif)

*(Demo is real output: 8 references, 3 deliberately planted fabrications — a fake DOI, a dead URL, and a no-URL citation. All 3 were caught and excluded; the 5 real ones passed. Measured: **7.7 s for all 8** — 4.2 s of pure network checks, the rest is deliberate throttling.)*

Reproduce it yourself — the planted-fakes file ships with the repo:

```bash
python scripts/verify_refs.py --refs examples/demo_refs.json
```

## 30-second quickstart

```bash
python scripts/verify_refs.py --refs refs.json --out report.md
# or verify straight from your reference manager (v1.9):
python scripts/verify_refs.py --refs bibliography.bib --out report.md
```

Open `report.md`: CiteScore + pre-submission conclusion at the top,
per-reference verdicts below.
Medical work: add `--profile medical`.  Writing a paper: add `--export bibtex`.
Institution/CI: add `--mailto you@lab.edu` (Crossref polite pool).

## How it works

Five phases, two modes:

| Phase | What happens |
|---|---|
| **CALIBRATE** | Asks you 3–5 sharp questions first (scope, timeframe, audience) — prevents researching the wrong question |
| **PLAN** | Breaks your question into 3–7 sub-questions with a search budget |
| **SEARCH** | Diamond-shaped iterative search: broad → narrow → gap-filling, Chinese + English, source-tier pyramid |
| **VERIFY** | Two layers: semantic check (does the source actually support the claim?) + mechanical check (reachability, domain authority, field completeness, dedup) |
| **SYNTHESIZE** | Report where every conclusion carries a confidence grade — 🟢 two independent sources / 🟡 single authority / 🔴 contested |

Modes: **QUICK** (single fact-check, ≤6 searches, no interrogation) vs **FULL** (open-ended research, ≤15 searches, calibration mandatory).

## The five citation verdicts

| Verdict | Meaning |
|---|---|
| `verified` | Reachable + authoritative tier (official/journal/preprint/major media) + complete fields — may support conclusions |
| `partial` | Reachable but community/blog tier or missing fields — downgraded use |
| `unreachable` | 404/timeout (≠ nonexistent — flagged for human review) |
| `invalid` | Unresolvable or nonexistent identifier (bad/fake DOI, arXiv ID, PMID, URL) — never enters the report |
| `unverified` | Not checked — never masquerades as verified |

## v1.2: medical evidence mode + bibliography export

```bash
# medical profile: journal-tier sources extend to Cochrane/BMJ/ClinicalTrials/
# NMPA/CDC/NICE/万方/ChiCTR; community-tier sources get an explicit
# "unfit for medical conclusions" warning
python scripts/verify_refs.py --refs refs.json --profile medical

# PMID-only references work out of the box — and every PubMed URL gets its
# PMID existence-checked via NCBI E-utilities. A fabricated PMID is caught
# even though PubMed's own page happily returns 2xx for it.

# export: verified-only BibTeX (straight into your paper) + full audit CSV
python scripts/verify_refs.py --refs refs.json --export bibtex,csv
```

Try the medical demo — real tocilizumab/sJIA references from PubMed, plus one
planted fake PMID and one planted duplicate (both caught):

```bash
python scripts/verify_refs.py --refs examples/medical_refs.json --profile medical --export bibtex,csv
```

## v1.5: arXiv verification + Wayback fallback

```bash
# arXiv IDs are now first-class: the official export.arxiv.org API cross-checks
# the registered title/year with the same thresholds as DOIs. A well-formed but
# nonexistent ID is judged invalid (fabricated) — never silently "unreachable".
# refs may carry "arxiv": "2310.10631" (or "hep-th/9901001"); arxiv.org/abs|pdf
# URLs are auto-detected.
python scripts/verify_refs.py --refs refs.json

# Unreachable entries are automatically checked against the Wayback Machine;
# when an archived copy exists, the report note carries the archive link so
# human review has something to compare against.
```

## Install

**AI agents (skills.sh / one command):**

```bash
npx skills add docsor1212/cite-holmes
```

**OpenClaw users (ClawHub — versioned, auto-updatable):**

```bash
clawhub search cite-holmes        # find it on the registry
clawhub install @docsor1212/cite-holmes
```

**Any Agent Skills-compatible agent** (Claude Code, Codex, Cursor, Gemini CLI, ZCode):

```bash
clawhub install @docsor1212/cite-holmes        # ClawHub registry
# or grab the folder directly from SkillHub: https://skillhub.cn/skills/cite-holmes
# then drop it into ~/.claude/skills/cite-holmes (or your agent's skills directory)
```

**China mirror (SkillHub 腾讯)**: <https://skillhub.cn/skills/cite-holmes> — fast downloads inside China, 中文说明.

## The DoctorQ Lab academic family

Cite Holmes works alongside three sibling skills:

- [academic-figures](https://skillhub.cn/skills/academic-figures) — publication-ready scientific figures (22+ chart types incl. composite panels, PRISMA, forest, KM) from one command
- [paper-polisher](https://skillhub.cn/skills/paper-polisher) — AI-detection, de-AI rewriting and terminology checks for academic writing, bilingual
- [pubmed-verifier](https://skillhub.cn/skills/pubmed-verifier) — focused PubMed citation verification for medical literature

## Usage

Just talk to your agent — it triggers automatically:

```
> deep research: what changed in the agent-skills ecosystem this year?
> is it true that NeurIPS 2025 papers contained 100+ hallucinated citations?
```

Or use the verifier standalone on any reference list:

```bash
python scripts/verify_refs.py --refs research_refs.json --out report.md
# offline structural check / strict CI mode
python scripts/verify_refs.py --refs refs.json --offline
python scripts/verify_refs.py --refs refs.json --strict
```

## What it won't catch (honest limits)

- A fabricated citation that points to a **real, live, plausible page** passes the mechanical check. The semantic layer (the model judging whether the source actually supports the claim) may catch it — it is model judgment, not a guarantee.
- `unreachable` ≠ fake: pages behind login walls or bot-blocking are flagged for human review, not condemned.
- The planted fakes in our demo are exactly the catchable types (dead URL / fake DOI / missing URL). We are not claiming it catches everything.

## Why not just use deep research / a citation checker?

- Deep-research skills **research more** but trust their own citations.
- Standalone citation checkers verify but don't research.
- Cite Holmes does both in one flow: **every reference in every report is machine-checked before it reaches you.**

Zero dependencies (pure Python stdlib), cross-platform (Windows/Linux/macOS), MIT license.

## CiteScore — every report carries a grade

Each verification report opens with a **CiteScore**: a 0-100 confidence score
(verified +10 / partial +4 / unreachable 0 / unverified −2 / invalid −8,
normalized by reference count) with an A–D grade. Screenshot it, quote it,
or gate your CI on it (`--strict`).

## What's new

- **v3.0.0** — the BLUF release. Every report opens with a machine-parseable
  YAML block (verdict / key_numbers / blocker / next_action) plus a 5-line
  human TL;DR — cite-holmes defines the "3-second dual-reader" report standard
  (a gap no tool fills today). Scholarly reception: verified DOIs fetch
  Semantic Scholar citation contexts (times-cited, context excerpts, coverage
  honestly labeled — the free Scite.ai counterpart). L4 evidence cascade:
  abstract-level judging via configurable external judge endpoints (OpenAI-
  compatible: ollama / llama-server), NEI escalates to full-text passage
  retrieval with local bge-m3 embeddings (TF-IDF fallback, zero hard deps).
  Cross-language title guard (Chinese claims vs English registrations no
  longer misjudged invalid). 210 tests green.

- **v2.0.0** — MCP three-primitives server (`verify_references` + `explain_verdict`
  tools, capability-matrix/changelog resources, fact-check workflow prompt),
  arXiv multi-version notes (unversioned citations to multi-revision papers,
  stale version pointers), optional `NCBI_API_KEY` (E-utilities 3→10 req/s for
  parallel batches), and a per-reference **evidence chain** in HTML reports
  (doi.org → retraction → S2 → OpenAlex → reachability, at a glance). First
  Major: the transparent multi-source citation verification stack, as shipped.
  195 tests green, real-network acceptance, package security self-scan clean.

- **v1.13.0** — the discoverability release. EN description rewritten around
  task-language roots (citation verification, verify citations, citation
  checker, hallucinated references, fact check) so task-word searches on
  skills.sh and agent skill markets finally surface it. New MCP server
  (`mcp/server.py`, FastMCP): expose the same mechanical verification engine
  as a `verify_references` tool for agents that prefer tools over skills —
  official MCP Registry ready (publish-once to Smithery, mcp.so, PulseMCP).
  Security & behavior declaration retained. 188 tests green, real-network
  acceptance 5/5, package security self-scan clean.

- **v1.12.0** — trust & transparency release. Persistent disk cache (default
  on, 7-day TTL, local SQLite): re-running or extending a bibliography reuses
  stable verdicts with zero network round-trips — the repeat-run pain behind
  every Trust score. `--strict` always bypasses the cache; `--refresh-cache`
  forces re-verification; `unreachable` is never cached. `--proxy` flag for
  restricted-egress environments (env `HTTPS_PROXY` also honored). A
  **Security & behavior declaration** section now ships in both languages:
  network access limited to the official academic registries over HTTPS, no
  telemetry, single-run CLI, nothing installed, env vars limited to your own
  API keys. The capability matrix adds an explicit "unsupported inputs" line
  (PDF/Word documents, Wanfang/CQVIP-only IDs, fact-checking claims).
  Private maintainer tooling removed from the shipped package. 181 tests.

- **v1.11.0** — the determinism release: arXiv API transient 406/403 (its anti-bot
  window trips even under our 3s global pacing) no longer silently skips content
  verification — exponential backoff, then a fallback to the official arXiv.org/abs
  landing page for title comparison (0.50/0.82 thresholds), so the same references
  produce the same verdicts on re-runs. Structured semantic audit: the model's
  per-reference semantic judgment now travels as machine-readable workpapers
  (`semantic: {claim, support, quote, note}` → `semantic_audit` in `--export
  auditjson` and a dedicated report section); `not_in_source`/`contradicted`
  judgments cap the verdict at `partial` with a human-review flag. Pre-submission
  conclusion corrected to arXiv's actual May 2026 enforcement start (was June) and
  now names ICML 2026 desk-rejections too. `tools/agentskills_check.py --distro`
  prints a skills.sh/agentskills.io distribution readiness checklist. 166 tests
  green. Zero new dependencies.

- **v1.10.0** — the speed release, aimed squarely at the top evaluation
  complaint ("verification leans on overseas databases; flaky from CN
  networks"): **parallel verification** (`--workers`, default 4 — references
  are independent, so a 20-item bibliography takes roughly a quarter of the
  serial time; results stay index-ordered and the host circuit breaker /
  rate-limiters are now thread-safe), **degraded-network mode** (3+ different
  hosts failing at the transport layer in one run flips remaining lookups to
  fast honest skips with a proxy/retry suggestion — minutes of waiting become
  a fast verdict), **Semantic Scholar title-search confirmation** for
  references with no DOI/PMID/arXiv (confirmation only, never a downgrade;
  hyphens normalized to spaces per S2 API docs), **intra-run cache** (a
  duplicate DOI/URL reuses the first verdict instead of re-hitting the
  network), fast-fail (no retry) once the network is known-degraded, and an
  OpenAlex 429 hint (key now required for production since 2026-02; free tier
  is 100 credits/day). 147 tests.
- **v1.9.0** — Semantic Scholar third source: when DOI.org metadata cannot be
  fetched, the DOI is re-confirmed at the S2 Graph API (confirmation only,
  never a downgrade — S2 record quality is uneven; 403/429 landing pages can
  now be rescued on S2 confirmation too). BibTeX import: `--refs
  bibliography.bib` verifies Zotero/EndNote exports directly (nested braces,
  `\url{}` macros, eprint→arXiv). OpenAlex API key support
  (`--openalex-key`/`OPENALEX_API_KEY`) with an actionable 403 hint — OpenAlex
  requires keys for production use since 2026-02. `--mailto` joins the
  Crossref polite pool; 429 `Retry-After` is honored. Every report now opens
  with a one-line **pre-submission conclusion** (arXiv has banned authors over
  hallucinated references since 2026-06). `--export auditjson`: a
  machine-readable per-reference check trail for institutional audit.
  SKILL.md slimmed (details moved to `references/verification-details.md` +
  `references/faq.md`). 120 tests.
- **v1.8.1** — fix: OpenAlex bibliographic confirmation could silently
  no-op (response read outside its context manager); caught by the new strict
  real-network acceptance gate and corrected.
- **v1.8.0** — retraction detection: verified DOIs are cross-checked against
  the Crossref/Retraction Watch database (free, updated every working day);
  a retracted paper is real — and uncitable — so retracted references are
  capped at `partial` and flagged for human review. Bibliographic existence
  check via OpenAlex for references without DOI/PMID/arXiv (positive
  confirmation only; "not found" never means "fabricated"). UA-rotation retry
  for metadata endpoints (403/406 resilience). New "common mistakes"
  anti-patterns section and a 30-second quickstart. Capability matrix now
  covers 10 fabrication/problem types. 89 tests.
- **v1.7.0** — author-name consistency check against DOI-registered authors
  (any claimed surname hit counts; a full miss downgrades to `partial`),
  capability-boundary matrix in every report (9 machine-caught fabrication
  types vs what stays with the semantic layer), `--format html`: a
  self-contained single-file HTML report (zero external assets, mobile
  readable — shareable with advisors/editors), agentskills.io spec self-check,
  internal competitive landscape. 73 tests.
- **v1.6.0** — host-level circuit breaker (2 consecutive transport failures to
  the same host → skip for the rest of the batch with an honest note; broken
  networks no longer stall the whole run), actionable error notes (timeout
  suggests `--timeout 20`, DNS vs refused distinguished, human-review section
  carries suggested actions), DOI↔PMID cross-check (catches "stitched fakes"
  where both IDs are real but belong to different papers), journal-name
  consistency check against DOI-registered metadata (mismatch → `partial`),
  CN-network FAQ section, regression suite grown to 62 tests.
- **v1.5.0** — arXiv ID metadata validation (export.arxiv.org official API,
  DOI-grade similarity thresholds; nonexistent IDs → `invalid`, never
  `unreachable`), Wayback Machine fallback for unreachable entries (archive
  link attached for human review), `arxiv` reference field, `eprint` in BibTeX
  + arXiv column in the audit CSV, regression suite grown to 53 tests.
- **v1.4.0** — DOI metadata cross-check (DOI.org CSL JSON vs cited title/year —
  catches "real DOI, wrong paper"), `--easy` one-flag mode (auto medical profile +
  auto BibTeX/CSV export), transient-network retry, human-readable Chinese error
  messages, expanded FAQ.
- **v1.3.0** — CiteScore scorecard in every report (Markdown + JSON), official
  icon, `tests/` regression suite (offline golden + medical profile + exports).
- **v1.2.0** — medical evidence mode (`--profile medical`), PMID verification
  via NCBI E-utilities, BibTeX/CSV bibliography export, 3-key dedup
  (URL/DOI/PMID).

## License

MIT © DoctorQ Lab
