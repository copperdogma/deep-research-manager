"""File templates for research project folders."""

from __future__ import annotations

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def research_prompt(topic: str) -> str:
    return f"""---
type: research-prompt
topic: "{topic}"
created: "{_now_iso()}"
---

# Research Prompt

<!-- Paste your research prompt below this line -->

"""


def synthesis_prompt(topic: str, report_count: int = 0, research_context: str = "") -> str:
    return f"""---
type: synthesis-prompt
topic: "{topic}"
created: "{_now_iso()}"
auto-generated: true
---

# Synthesis Prompt

You are acting as lead research editor. Your task is to read multiple independent research reports on the same topic, reconcile them, and produce one final, implementation-ready synthesis.

## Research Context

{research_context if research_context else "<!-- Research context will be populated from research-prompt.md -->"}

## Reports to Synthesize

You will receive {report_count} research reports, each produced by a different AI model. Each report covers the same research question from the instructions above.

## Your Synthesis Goals

1. Grade each source report on quality: evidence density, practical applicability, specificity, and internal consistency (0–5 scale for each, with a one-paragraph critique).
2. Extract key claims by topic area.
3. Identify where reports agree (high confidence) vs. disagree (needs adjudication).
4. Resolve contradictions with explicit reasoning — evaluate the strength of each report's evidence, not majority vote.
5. Separate "proven / high confidence" from "promising but uncertain."
6. Produce one concrete recommendation, not a menu of options.
7. If one report is clearly higher quality, weight it accordingly and say why.

## Required Output Format

Begin your response with:

---
canonical-model-name: "{{the product name you are — e.g., chatgpt, claude, gemini, grok — lowercase, no version numbers}}"
report-date: "{{today's date in ISO 8601}}"
research-topic: "{topic}"
report-type: "synthesis"
---

Then produce the following sections:

1. **Executive Summary** (8–12 bullets)
2. **Source Quality Review** (table with scores + short commentary per report)
3. **Consolidated Findings by Topic**
4. **Conflict Resolution Ledger** (claim, conflicting views, final adjudication, confidence level)
5. **Decision Matrix** (if applicable — weighted, with scoring rationale)
6. **Final Recommendation** (concrete, with rationale)
7. **Implementation Plan / Next Steps** (if applicable)
8. **Open Questions & Confidence Statement**

## Quality Instructions

- Be concrete and specific, not generic.
- Clearly label assumptions and uncertainty.
- Prefer practical reliability over novelty.
- If evidence is weak across all reports, say so — do not manufacture false confidence.
- Do not simply merge or average — adjudicate.
- Note which report(s) contributed each key finding.
"""


def agent_placeholder(topic: str) -> str:
    return f"""---
type: research-report
topic: "{topic}"
canonical-model-name: ""
collected: ""
---

# Research Report

<!-- Paste the full output from a deep research AI below this line -->
<!-- Then fill in canonical-model-name above (e.g., "chatgpt-5-2", "gemini-2-5-pro", "grok-4-1") -->
<!-- Or leave it blank and "deep-research format" will ask you -->

"""


def final_synthesis(topic: str) -> str:
    return f"""---
type: synthesis-report
topic: "{topic}"
synthesis-model: ""
source-reports: []
synthesized: ""
---

# Final Synthesis

<!-- Paste or generate the final synthesis report below this line -->

"""
