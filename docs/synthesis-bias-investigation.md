# Synthesis Model Bias Investigation

**Date:** 2026-02-27
**Methodology:** Re-synthesized 10 ADR research projects using GPT-5.2 and Gemini 3.1 Pro alongside the original Claude Opus 4.6 syntheses, then compared source quality evaluations and overall report quality.

## Background

deep-research uses a single AI model to synthesize multiple independent research reports into a final analysis. The default synthesis model is Claude Opus (the highest-ranked in the preference order). During ADR research for the Storybook project, we noticed that Opus consistently ranked its own source reports as the best — raising the question: is the ranking accurate, or is Opus grading its own homework?

## Experiment Design

- **10 ADRs** with 2-4 source reports each (from Claude, GPT, Gemini, and Grok)
- Each ADR's research was synthesized by **three different models**: Claude Opus 4.6, GPT-5.2, and Gemini 3.1 Pro
- Compared: (1) how each synthesizer scored the source reports, and (2) the quality of the synthesis output itself
- Total: 30 synthesis runs (10 original Opus + 10 GPT + 10 Gemini)

## Finding 1: Claude's reports ARE generally the best

All three evaluators ranked Claude's source reports #1 in the majority of cases:

| Evaluator | Claude ranked #1 | Notes |
|---|---|---|
| **Opus** | 8/8 (100%) | 6 solo wins, 2 ties with GPT |
| **GPT-5.2** | 6/8 (75%) | GPT ranked itself #1 on ADR-6 and ADR-7 |
| **Gemini** | 6/8 (75%) | Also ranked GPT #1 on ADR-6 and ADR-7 |

The ranking is real. Claude's research reports are consistently the highest quality across independent evaluators.

## Finding 2: Opus exaggerates the margin (self-favoritism)

Opus shows a clear self-scoring bias pattern:

- **Opus gave Claude's reports 5.0 on 7/8 ADRs** (4.75 on the 8th). Never ranked another report above Claude.
- **GPT-5.2 showed no self-favoritism** — ranked its own provider's reports low when they deserved it (e.g., GPT report scored 3.25/5 on ADR-5, OpenAI report scored 2.75/5 on ADR-14).
- **Gemini showed no self-favoritism** — consistently ranked Google's reports 2nd-3rd, never #1.

The sharpest divergence was **ADR-11 (Competitive Analysis)**:
- Opus scored Claude's report: **5.0/5** (Evidence: 5)
- GPT-5.2 scored Claude's report: **3.5/5** (Evidence: 2) — correctly noting many claims lacked citations/URLs
- Gemini scored Claude's report: **4.75/5** (Evidence: 4)

GPT's criticism was valid: Claude's competitive analysis made many specific claims (user counts, funding amounts, company outcomes) without verifiable links.

## Finding 3: Opus produces the best synthesis output

Despite the scoring bias, Opus produces materially better synthesis reports:

| Dimension | Opus | GPT-5.2 | Gemini |
|---|---|---|---|
| **Comprehensiveness** | 300-600 lines, exhaustive | 250-400 lines, thorough | 100-200 lines, thin |
| **Implementation detail** | Complete Zod schemas, ASCII diagrams, extraction prompts | Good schemas, slightly less polished | Minimal code, high-level only |
| **Conflict resolution** | Specific reasoning chains with evidence citations | Adequate but terser | Often superficial |
| **Edge case coverage** | Catches iOS Safari MSE, AudioWorklet vs MediaRecorder, ElevenLabs tier breakpoints | Covers main points, misses some edge cases | Misses many |
| **Evaluation honesty** | Self-biased (always 5.0) | Most honest evaluator | Unreliable (see below) |

### Gemini has a serious reliability problem

Gemini **copied the Opus synthesis verbatim** on 2 of 10 ADRs (ADR-8 and ADR-10 — zero diff lines, identical text). On the remaining 8 it produced original content, but at roughly half the depth. Gemini is disqualified as a reliable synthesis model.

## Finding 4: Bias doesn't affect architectural decisions

The most important finding: **all three synthesizers reached the same architectural recommendations** on every ADR. The bias is cosmetic (inflated scores in the evaluation section) but does not change the actual decisions, conflict resolutions, or implementation plans.

Examples of unanimous decisions across all three synthesizers:
- AudioWorklet over MediaRecorder for browser audio capture
- Pipeline architecture over Realtime API for conversation mode
- Claim model over key-value for facts storage
- Two-pass extraction with tempIds over single-call extraction
- Separate identity resolution step over inline resolution

## Mitigation

Added a debiasing instruction to the synthesis prompt template (v0.3.5):

> Score each source report on its merits regardless of which AI model produced it. Do not assume the most detailed report is the most accurate — weight verifiable citations over unverified claims.

**Effect:** On a re-run of ADR-11, Opus's self-score dropped from 5.0 to 4.9 (Evidence Density from 5 to 4.5). The commentary became more critical of unverifiable claims. Marginal improvement — the instruction helps but doesn't eliminate the bias.

## Recommendation

**Keep Opus as the default synthesis model.** The synthesis output quality is materially superior to alternatives. The self-scoring bias is real but contained to the evaluation section, which is informational context rather than the decision-driving content.

If evaluation accuracy matters for a specific use case, run `deep-research final chatgpt` for a more honest source quality assessment — but expect a less detailed synthesis body.

## Cost

The full investigation cost approximately $10 in OpenAI API calls (GPT-5.2) and $0 in Google API calls (Gemini 3.1 Pro was free-tier). The debiasing re-run cost ~$4.50 for a single Opus synthesis.
