# deep-research CLI Tool — Product Spec
**Version:** 0.1 MVP  
**Date:** 2026-02-13  
**Status:** Ready for implementation

---

## Overview

A CLI tool that manages the lifecycle of multi-model deep research cycles. The folder is the state. Every step can be done manually or automated via API keys. The tool creates a structured folder, dispatches research prompts to AI providers, collects and formats results, and produces a final synthesis report.

**Design principles:**
- The folder is the entire project state. No database, no config server, no hidden state.
- Every step the CLI automates can also be done by hand (paste into a file, rename a file). The CLI just makes it faster.
- API keys are optional. Zero keys = a structured folder manager. More keys = more automation.
- Any AI coding agent (OpenClaw, Claude Code, Cursor, etc.) can operate on the folder because it's just files.

---

## Installation

```bash
pip install deep-research
```

Or run from source:

```bash
git clone <repo>
cd deep-research
pip install -e .
```

After install, the `deep-research` command is available globally.

---

## Commands

### `deep-research init <topic>`

Creates a new research project folder in the current directory.

**Arguments:**
- `<topic>` — short name for the research topic. Used as the folder name. Should be lowercase-hyphenated (the CLI slugifies it if needed).

**Optional flags:**
- `--agents <n>` — number of blank agent placeholder files to create (default: 6)
- `--dir <path>` — create the folder somewhere other than the current directory

**What it does:**

1. Creates folder `<topic>/` in the current directory
2. Creates the following files inside it:

```
<topic>/
├── research-prompt.md          ← template, user pastes their prompt here
├── synthesis-prompt.md         ← auto-generated template (editable)
├── ai-agent-01.md              ← blank placeholder for manual paste
├── ai-agent-02.md              ← blank placeholder for manual paste
├── ai-agent-03.md              ← blank placeholder for manual paste
├── ai-agent-04.md              ← blank placeholder for manual paste
├── ai-agent-05.md              ← blank placeholder for manual paste
├── ai-agent-06.md              ← blank placeholder for manual paste
└── final-synthesis.md          ← empty template for final report
```

3. Detects which API keys are present in the environment (see API Key Configuration) and prints a summary:

```
Created: best-ui-tools/
  research-prompt.md     ← paste your research prompt here
  synthesis-prompt.md    ← auto-generated (edit if needed)
  ai-agent-01.md … 06   ← paste manual results here
  final-synthesis.md     ← final report goes here

API keys found: OpenAI, Anthropic
API keys missing: Google (GOOGLE_API_KEY), xAI (XAI_API_KEY)

Next: paste your research prompt into research-prompt.md, then run:
  cd best-ui-tools && deep-research run
```

**File templates:**

`research-prompt.md`:
```markdown
---
type: research-prompt
topic: "{topic}"
created: "{ISO 8601 timestamp}"
---

# Research Prompt

<!-- Paste your research prompt below this line -->

```

`synthesis-prompt.md` (auto-generated — see Synthesis Prompt Generation):
```markdown
---
type: synthesis-prompt
topic: "{topic}"
created: "{ISO 8601 timestamp}"
auto-generated: true
---

# Synthesis Prompt

{auto-generated synthesis prompt text — see section below}
```

`ai-agent-XX.md`:
```markdown
---
type: research-report
topic: "{topic}"
canonical-model-name: ""
collected: ""
---

# Research Report

<!-- Paste the full output from a deep research AI below this line -->
<!-- The AI should include a metadata block at the top with its canonical-model-name -->
<!-- If it does, "deep-research format" will auto-rename this file -->

```

`final-synthesis.md`:
```markdown
---
type: synthesis-report
topic: "{topic}"
synthesis-model: ""
source-reports: []
synthesized: ""
---

# Final Synthesis

<!-- Paste or generate the final synthesis report below this line -->

```

---

### `deep-research run`

Sends the research prompt to all available API providers in parallel and writes results to the folder.

**Must be run from inside a research project folder** (contains `research-prompt.md`).

**What it does:**

1. Reads `research-prompt.md`. If empty/template-only, abort with error: "No research prompt found. Paste your prompt into research-prompt.md first."

2. Detects available API keys from environment variables.

3. For each available provider, spawns a parallel API call:
   - Sends the research prompt as the user message
   - Uses the provider's deep research / long-output model (see Model Defaults)
   - Streams progress to the terminal (see CLI Output)

4. As each call completes:
   - Parses the `canonical-model-name` from the response's metadata block (if present)
   - Writes the result to `{canonical-model-name}-report.md`
   - If no metadata block in response, writes to `{provider-slug}-report.md`

5. After all calls complete, regenerates `synthesis-prompt.md` with updated report count and model names (preserving any manual edits to the synthesis instructions — see Synthesis Prompt Generation).

6. Prints summary:
```
Completed 2 of 2 API calls:
  ✓ chatgpt-5.2-deep-research-report.md    (14,832 words, $0.47)
  ✓ claude-opus-4.6-deep-research-report.md (11,204 words, $1.23)

Total cost: $1.70
Unused agent slots: ai-agent-01.md … 06 (paste manual results here)

Next steps:
  - Paste results from other models into ai-agent-XX.md files
  - Run: deep-research format    (to rename and clean up)
  - Run: deep-research final     (to generate synthesis)
```

**Error handling:**
- If an API call fails, log the error, write a partial file with the error message, and continue with other providers
- If an API call times out (configurable, default 10 minutes), abort that call and note it
- Never fail the entire `run` because one provider errored

**Optional flags:**
- `--provider <name>` — run only a specific provider (e.g., `--provider openai`)
- `--dry-run` — show what would be called without making API requests
- `--timeout <seconds>` — override default timeout per call (default: 600)

---

### `deep-research format`

Renames agent placeholder files based on their content and cleans up unused slots.

**Must be run from inside a research project folder.**

**What it does:**

1. Scans all `ai-agent-*.md` files in the folder.

2. For each file:
   - If the file is **empty or still matches the template** (no content below the comment line): delete it.
   - If the file **has content**: attempt to parse the YAML frontmatter and/or the model's own metadata block from the content.
     - If `canonical-model-name` is found (either in the outer YAML or in an inner metadata block from the model's output): rename the file to `{canonical-model-name}-report.md`.
     - If no canonical name found: prompt the user interactively: "ai-agent-03.md has content but no model name. Enter model name (or press Enter to skip):" — then rename if provided, leave as-is if skipped.

3. Updates the YAML frontmatter `collected` timestamp on any renamed files (set to file modification time if not already set).

4. Regenerates `synthesis-prompt.md` with the updated list of report files.

5. Prints summary:
```
Formatted:
  ai-agent-01.md → claude-opus-4.6-deep-research-report.md
  ai-agent-02.md → grok-4.1-deep-research-report.md
Cleaned up:
  Removed 4 unused placeholder files (ai-agent-03.md … 06)
Skipped:
  (none)
```

**Edge cases:**
- If a rename would collide with an existing file (e.g., the API `run` already created `claude-opus-4.6-deep-research-report.md`), append `-manual` to the new name and warn the user.
- If a file has content but the user skips naming it, leave it as `ai-agent-XX.md` — it will still be included in synthesis.

---

### `deep-research final [model]`

Generates the final synthesis report by sending all collected reports plus the synthesis prompt to an AI model.

**Must be run from inside a research project folder.**

**Arguments:**
- `[model]` — optional. Which model/provider to use for synthesis. Accepts short aliases: `opus`, `sonnet`, `chatgpt`, `gemini`, `grok`. If omitted, uses the best available model (see Model Defaults — synthesis tier).

**What it does:**

1. Reads `synthesis-prompt.md`.

2. Collects all `*-report.md` files in the folder (excluding `final-synthesis.md`). Reads their content.

3. Assembles the synthesis payload:
   - The synthesis prompt
   - Each report, separated by headers with the model name (metadata blocks stripped to avoid confusing the synthesis model)

4. Sends to the selected model via API.

5. Writes the response to `final-synthesis.md`, updating its YAML frontmatter:
   - `synthesis-model`: the model used
   - `source-reports`: list of report filenames included
   - `synthesized`: ISO 8601 timestamp

6. Prints summary:
```
Synthesis complete:
  Model: claude-opus-4.6
  Input: 4 reports (52,340 words total)
  Output: final-synthesis.md (8,921 words)
  Cost: $2.15

Done. All files ready in best-ui-tools/
```

**If no API key is available for the requested model:**
```
No API key found for opus. Available: openai, google.
Use: deep-research final chatgpt
Or paste the synthesis manually — run: deep-research prepare-final
```

**Optional flags:**
- `--dry-run` — assemble the payload and print token count / estimated cost without calling the API
- `--timeout <seconds>` — override default timeout (default: 900 for synthesis, which is longer than research since the input is larger)

---

### `deep-research prepare-final`

Assembles the synthesis prompt + all reports into a single file or clipboard for manual pasting into an AI.

**This is the manual alternative to `deep-research final`.** Use it when you want to paste into a free-tier model or a model you don't have API access to.

**What it does:**

1. Reads `synthesis-prompt.md` and all `*-report.md` files.

2. Assembles them into a single markdown document:
```markdown
{synthesis prompt text}

---

## Source Reports

### Report 1: {model-name-from-filename}

{report content, metadata block stripped}

---

### Report 2: {model-name-from-filename}

{report content, metadata block stripped}

---
(etc.)
```

3. Writes to `_synthesis-input.md` (underscore prefix so it sorts to the top and is clearly a temp file).

4. Optionally copies to clipboard (if `--clipboard` flag is set or if `pbcopy`/`xclip` is available).

5. Prints:
```
Assembled synthesis input:
  _synthesis-input.md (48,231 words, ~64K tokens)
  Copied to clipboard: yes

Paste this into your AI of choice, then paste the result into final-synthesis.md.
To clean up: rm _synthesis-input.md
```

**Optional flags:**
- `--clipboard` / `--no-clipboard` — force clipboard copy on/off
- `--max-chars <n>` — warn if assembled content exceeds this (default: 200000)

---

### `deep-research status`

Shows the current state of the research project.

**Must be run from inside a research project folder.**

**Output:**
```
Research project: best-ui-tools
Created: 2026-02-13 14:00 MST

Research prompt:    ✓ filled (1,247 words)
Synthesis prompt:   ✓ auto-generated (892 words)

Reports:
  ✓ chatgpt-5.2-deep-research-report.md      14,832 words  (API)
  ✓ claude-opus-4.6-deep-research-report.md   11,204 words  (API)
  ✓ grok-4.1-deep-research-report.md           9,118 words  (manual)
  ○ ai-agent-04.md                             empty
  ○ ai-agent-05.md                             empty
  ○ ai-agent-06.md                             empty

Final synthesis:    ○ empty

Next: deep-research format   (rename/clean up agent files)
      deep-research final    (generate synthesis via API)
```

---

## Synthesis Prompt Generation

When `init` creates the folder (and when `run` or `format` update the report list), the CLI auto-generates `synthesis-prompt.md`. The synthesis prompt is a mechanical transformation of the research context — it doesn't require AI to produce.

**Template:**

```markdown
You are acting as lead research editor. Your task is to read multiple independent research reports on the same topic, reconcile them, and produce one final, implementation-ready synthesis.

## Research Context

{contents of research-prompt.md, minus the YAML frontmatter}

## Reports to Synthesize

You will receive {N} research reports, each produced by a different AI model. Each report covers the same research question from the instructions above.

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
canonical-model-name: "{the product name you are — e.g., chatgpt, claude, gemini, grok — lowercase, no version numbers}"
report-date: "{today's date in ISO 8601}"
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
```

**Regeneration rules:**
- `{N}` is updated whenever reports are added/removed/renamed
- The research context block is re-read from `research-prompt.md` on each regeneration
- If the user has manually edited `synthesis-prompt.md` and changed `auto-generated: true` to `auto-generated: false` in the frontmatter, the CLI will **not** overwrite it on regeneration — it will print a note: "synthesis-prompt.md has manual edits (auto-generated: false). Skipping regeneration. Delete and re-run to regenerate."

---

## API Key Configuration

API keys are read from environment variables. No config file needed for MVP.

| Provider | Environment Variable | Model Used (Research) | Model Used (Synthesis) |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-5.2` | `gpt-5.2` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-4-6` | `claude-opus-4-6` |
| Google | `GOOGLE_API_KEY` | `gemini-2.5-flash` | `gemini-2.5-pro` |
| xAI | `XAI_API_KEY` | `grok-4.1` | `grok-4.1` |

**Model defaults are hardcoded for MVP** but should be easy to change in the source (single config dict). A future enhancement could read overrides from `~/.deep-research.yaml` or a per-project config.

**The `final` command's model selection logic:**
1. If `[model]` argument is provided, use that provider. Abort if no key.
2. If omitted, select the best available model in order: Anthropic (Opus) → OpenAI (GPT-5.2) → Google (Gemini Pro) → xAI (Grok).
3. This ordering is a default preference — it's a single list in the source code, trivially reorderable.

**Aliases for the `final` command:**
- `opus` → Anthropic
- `sonnet` → Anthropic (but uses Sonnet 4.5 instead of Opus)
- `chatgpt` → OpenAI
- `gemini` → Google
- `grok` → xAI

---

## API Call Parameters

All research calls use these defaults:

```python
{
    "temperature": 0.0,       # Deterministic output
    "max_tokens": 128000,     # Max output — let the model use what it needs
    # Model-specific parameters added per provider
}
```

The research prompt is sent as the user message. No system prompt — the research prompt is self-contained.

For synthesis calls, same parameters but:
- The assembled synthesis payload (prompt + all reports) is sent as the user message
- `max_tokens` remains 128000 — synthesis reports can be long

**Prompt caching:** For providers that support it (OpenAI automatic, Anthropic explicit), the CLI does not need to do anything special for single-call research. If a future version does multi-call work, prompt caching layout should be considered.

---

## CLI Output During `run`

**Current (v0.1):** Results print as each call completes. No live progress while waiting.

**Future enhancement:** Live-updating progress display showing elapsed time for all in-flight API calls simultaneously. Each provider row updates in-place while waiting:

```
Running research prompt against 4 providers...

  OpenAI (gpt-5.2)       ⠋ 1m 23s
  Anthropic (opus-4.6)   ⠋ 1m 23s
  Google (gemini-2.5)    ✓ gemini-2-5-flash-report.md (9,118 words, $0.12, 58s)
  xAI (grok-4.1)         ⠋ 1m 23s
```

When a call completes, its row freezes with the result. When all calls finish, the display settles into the final summary. This requires terminal cursor management (e.g., ANSI escape codes or a library like `rich`) and concurrent progress tracking across parallel asyncio tasks. The `final` command should show similar single-line live progress (elapsed time + spinner) while waiting for the synthesis call.

---

## Technology

- **Language:** Python 3.10+
- **CLI framework:** `click` or `typer` (either works; `click` has fewer dependencies)
- **API clients:** `openai`, `anthropic`, `google-generativeai` — install as optional dependencies so the tool works with zero API packages if you only want the file management features
- **YAML parsing:** `pyyaml` for frontmatter
- **Async:** `asyncio` + `aiohttp` (or provider-native async clients) for parallel API calls in `run`
- **Clipboard:** `subprocess` call to `pbcopy` (macOS) / `xclip` (Linux) / `clip` (Windows) — optional, fail silently if unavailable
- **No other dependencies.** No frameworks, no databases, no build steps.

**Package structure:**
```
deep-research/
├── pyproject.toml
├── README.md
├── src/
│   └── deep_research/
│       ├── __init__.py
│       ├── cli.py              # Click/Typer command definitions
│       ├── project.py          # Folder/file management (init, format, status)
│       ├── providers.py        # API client wrappers (OpenAI, Anthropic, Google, xAI)
│       ├── synthesis.py        # Synthesis prompt generation, payload assembly
│       ├── frontmatter.py      # YAML frontmatter parsing/writing
│       └── templates.py        # File templates (research-prompt, ai-agent, etc.)
└── tests/
    ├── test_project.py
    ├── test_frontmatter.py
    ├── test_synthesis.py
    └── fixtures/               # Sample research folders for testing
```

---

## Folder Lifecycle (Complete Example)

```bash
# 1. Create project
$ deep-research init best-ui-tools
Created: best-ui-tools/
  API keys found: OpenAI, Anthropic

# 2. User goes to Claude Project, chats, gets research prompt, pastes it
$ vim best-ui-tools/research-prompt.md

# 3. Run API calls (auto-generates synthesis prompt first)
$ cd best-ui-tools
$ deep-research run
Running research prompt against 2 providers...
  ✓ OpenAI (gpt-5.2)      → chatgpt-5.2-deep-research-report.md (14,832 words, $0.47)
  ✓ Anthropic (opus-4.6)   → claude-opus-4.6-deep-research-report.md (11,204 words, $1.23)
Synthesis prompt updated (2 reports).

# 4. Meanwhile, user pasted prompt into Gemini and Grok manually
$ vim ai-agent-01.md   # paste Gemini deep research output
$ vim ai-agent-02.md   # paste Grok deep research output

# 5. Format — rename and clean up
$ deep-research format
Formatted:
  ai-agent-01.md → gemini-3-deep-research-report.md
  ai-agent-02.md → grok-4.1-deep-research-report.md
Cleaned up:
  Removed 4 unused placeholder files
Synthesis prompt updated (4 reports).

# 6. Check status
$ deep-research status
Research project: best-ui-tools
Reports: 4 of 4 filled
Final synthesis: empty
Next: deep-research final

# 7. Generate final synthesis via API
$ deep-research final opus
Synthesis complete:
  Model: claude-opus-4.6
  Input: 4 reports (47,006 words)
  Output: final-synthesis.md (8,921 words)
  Cost: $2.15
Done.

# 8. Or, do it manually instead:
$ deep-research prepare-final
Assembled: _synthesis-input.md (48,231 words)
Copied to clipboard.
# User pastes into their AI of choice, pastes result into final-synthesis.md

# 9. Folder is done — copy into project
$ cp -r ../best-ui-tools ~/projects/cineforge/docs/research/
```

---

## Edge Cases & Error Handling

**`run` called with no prompt:**  
Abort: "research-prompt.md is empty. Paste your research prompt first."

**`run` called with no API keys:**  
Abort: "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, etc. in your environment. Or paste results manually into ai-agent-XX.md files."

**`run` called and some calls fail:**  
Complete the successful calls, write error details to the failed provider's output file, print summary showing which succeeded and which failed. Don't abort the whole run.

**`format` finds a file with content but no parseable model name:**  
Interactive prompt: "ai-agent-03.md has content but no model name. Enter a name (e.g., 'gemini-3-deep-research') or press Enter to skip:"

**`final` assembled payload exceeds model's context window:**  
Estimate token count before sending. If likely to exceed, warn: "Assembled input is ~{n}K tokens. {model} context is {m}K. Proceed anyway? [y/N]" or suggest a different model with a larger context.

**`format` or `final` run outside a research project folder:**  
Abort: "No research project found. Run from inside a folder created by 'deep-research init'." Detection: check for `research-prompt.md` in the current directory.

**Double `run`:**  
If reports from API providers already exist, warn: "{file} already exists. Overwrite? [y/N]" — per file, not all-or-nothing.

**`final` called with no reports:**  
Abort: "No reports found. Run 'deep-research run' or paste results into ai-agent-XX.md files first."

---

## Acceptance Criteria

- [ ] `deep-research init <topic>` creates a correctly structured folder with all template files
- [ ] `init` detects and reports available API keys from environment
- [ ] `run` reads the research prompt and dispatches parallel API calls to all available providers
- [ ] `run` writes results with correct filenames parsed from canonical-model-name metadata
- [ ] `run` shows real-time streaming progress in the terminal
- [ ] `run` handles partial failures gracefully (some succeed, some fail)
- [ ] `run` auto-generates/updates synthesis-prompt.md
- [ ] `format` renames ai-agent files based on parsed metadata
- [ ] `format` deletes unused placeholder files
- [ ] `format` prompts interactively for files with content but no model name
- [ ] `format` updates synthesis-prompt.md with current report list
- [ ] `final` assembles reports + synthesis prompt and calls the selected model
- [ ] `final` writes result to final-synthesis.md with correct frontmatter
- [ ] `final` defaults to best available model when no argument given
- [ ] `prepare-final` assembles the manual synthesis payload and optionally copies to clipboard
- [ ] `status` shows accurate project state
- [ ] All file templates include correct YAML frontmatter
- [ ] Synthesis prompt auto-generation includes research context and is idempotent
- [ ] Manual edits to synthesis-prompt.md (auto-generated: false) are preserved
- [ ] Tool works with zero API keys (file management only)
- [ ] Tool works with 1–4 API keys (partial automation)
- [ ] Cost tracking is displayed for every API call
- [ ] Errors are clear, actionable, and never lose user data

---

## Distribution & Installation

### For Development

```bash
git clone https://github.com/copperdogma/deep-research-manager.git
cd deep-research-manager
pip install -e ".[dev]"
```

This installs in editable mode with dev dependencies (pytest, ruff).

### For End Users

#### Option 1: Install from GitHub (Recommended)

```bash
pip install git+https://github.com/copperdogma/deep-research-manager.git
```

Or with all provider dependencies:

```bash
pip install "git+https://github.com/copperdogma/deep-research-manager.git#egg=deep-research[all]"
```

#### Option 2: Install with pipx (Best for CLI tools)

```bash
pipx install git+https://github.com/copperdogma/deep-research-manager.git
```

`pipx` installs CLI tools in isolated environments while making them globally available.

#### Option 3: Clone and Install Locally

```bash
git clone https://github.com/copperdogma/deep-research-manager.git
cd deep-research-manager
pip install .
```

Or with specific providers:

```bash
pip install ".[openai,anthropic]"  # Only OpenAI and Anthropic
pip install ".[all]"                # All providers
```

### Provider Dependencies

The base installation includes only Click and PyYAML. Install provider packages as needed:

```bash
pip install "deep-research[openai]"      # OpenAI only
pip install "deep-research[anthropic]"   # Anthropic only
pip install "deep-research[google]"      # Google only
pip install "deep-research[all]"         # All providers
```

Or install them manually:

```bash
pip install openai                # For OpenAI
pip install anthropic             # For Anthropic
pip install google-generativeai   # For Google
# xAI uses OpenAI-compatible client, no extra package needed
```

### Verification

After installation, verify it works:

```bash
deep-research --help
deep-research init test-project
```

### GitHub Repository Setup

To prepare for GitHub distribution:

1. **Create repository** on GitHub (public or private)

2. **Add a README.md** with:
   - Project description
   - Installation instructions (copy from above)
   - Quick start example
   - API key setup instructions
   - Link to `docs/spec-cli.md` for full documentation

3. **Add a LICENSE file** (MIT or Apache 2.0 recommended for open source)

4. **Tag releases** for version tracking:
   ```bash
   git tag -a v0.1.0 -m "Initial release"
   git push origin v0.1.0
   ```

5. **Users install specific versions**:
   ```bash
   pip install git+https://github.com/copperdogma/deep-research-manager.git@v0.1.0
   ```

### Future: PyPI Distribution

Once stable, publish to PyPI for simpler installation:

```bash
pip install build twine
python -m build
twine upload dist/*
```

Then users install with:
```bash
pip install deep-research
```