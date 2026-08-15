---
name: cite-holmes
version: 1.1.1
author: DoctorQ Lab
license: MIT
platforms: [linux, win32, darwin]
description: >
  Cite Holmes — deep research that interrogates its own sources (Verified Deep
  Research). Calibrates scope first (asks 3-5 sharp questions), plans sub-questions,
  searches iteratively across sources and languages, then machine-verifies every
  citation (five states: verified/partial/unverified/unreachable/invalid) before
  a confidence-graded report ships. Never outputs unverified references; treats
  fabricated DOIs, dead links and missing sources as first-class catch targets.
  Use whenever the user asks to "deep research", "look into", "investigate",
  "compare A vs B", "fact check", "verify this claim", "is it true that...",
  "check these references", "are these citations real", wants a research report
  with sources, or needs reliable multi-source answers — even if they never say
  the word "research".
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

**Semantic (the model must do this)**: for each reference ask "does the source
page actually support the sentence I cite it for?" → `supports` /
`partial_support` / `not_in_source` (drop or demote).

**Mechanical (run the script)**:

```bash
python scripts/verify_refs.py --refs research_refs.json --out verify_report.md
```

Five verdicts: `verified` / `partial` / `unreachable` (needs_human_check) /
`invalid` / `unverified`. See the script's `--help` for options (`--offline`,
`--strict` for CI).

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
| `references/search-strategies.md` | read before SEARCH |
| `references/report-template.md` | skeleton for SYNTHESIZE; refs schema |

## Honest limits

- A fabricated citation pointing to a real, live, plausible page passes the
  mechanical layer; the semantic layer may catch it — model judgment, not a
  guarantee.
- `unreachable` ≠ fake.
- Reproducible demo: `python scripts/verify_refs.py --refs examples/demo_refs.json`
  (8 refs, 3 planted fabrications, all caught — measured 7.7 s).

## Environment fallback

Without web tools: state honestly that only the "user-supplied material +
mechanical verification" mode is possible; never pretend to search.
