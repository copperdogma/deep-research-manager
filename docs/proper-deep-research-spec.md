Spec: Add “Real Deep Research” calls (OpenAI + Google) to deep-research-manager

Goal

Extend your CLI so that when you run research you can choose:
	•	OpenAI Deep Research via the Responses API using o3-deep-research / o4-mini-deep-research, with at least one real data source (web search, MCP, or file search).  ￼
	•	Google Gemini Deep Research Agent via the Interactions API using agent deep-research-pro-preview-12-2025 (async background + polling).  ￼

Keep your current behavior (parallel “standard” model calls) as default / fallback.

⸻

Current state (what you have)
	•	deep_research/cli.py command run reads research-prompt.md and calls providers.run_research(prompt_text, provider_list, timeout=...).
	•	deep_research/providers.py currently does standard single-call generation per provider:
	•	OpenAI: chat.completions
	•	Google: models.generate_content
	•	Anthropic: messages.create
	•	xAI: chat.completions (OpenAI-compatible)

So “deep research” today is workflow-deep, not API-deep.

⸻

Design overview

Add a second research execution mode per provider:
	•	standard (existing): one-shot generation
	•	deep_research (new):
	•	OpenAI deep research models + Responses API + web_search
	•	Google deep research agent + Interactions API + background job

Then expose the mode in CLI.

⸻

CLI / UX changes

1) New flags for deep-research run

Add:
	•	--mode [standard|deep] (default standard)
	•	--openai-dr-model [o3-deep-research|o4-mini-deep-research] (optional override)
	•	--google-dr-agent [deep-research-pro-preview-12-2025] (optional override)
	•	--no-web (disables web search where applicable; if used with OpenAI deep research → error, because OpenAI deep research requires at least one data source)  ￼
	•	--poll-interval <seconds> for Google agent polling (default 10)
	•	--max-walltime <seconds> for Google deep research (default 1800–3600, but hard-stop if exceeded)

2) Output file naming

Keep your current ai-agent-XX.md output scheme, but add provenance:
	•	Standard outputs remain ai-agent-01.md, ai-agent-02.md, etc.
	•	Deep research outputs should include provider + mode to avoid confusion, e.g.:
	•	ai-openai-deep-research.md
	•	ai-google-deep-research.md

Also write a debug payload (always, or behind --debug):
	•	_debug-openai-dr.json
	•	_debug-google-dr.json

⸻

Provider implementation details

A) OpenAI Deep Research (API)

Requirements from OpenAI docs
	•	Use Responses API
	•	Model must be o3-deep-research or o4-mini-deep-research
	•	Must include at least one data source tool: web search, remote MCP server, or file search over vector stores  ￼
	•	Your easiest data source to wire first: web search tool.  ￼

Implementation approach
Add new function in deep_research/providers.py:
	•	async def run_openai_deep_research(prompt: str, timeout: int, web: bool=True) -> ProviderResult

Use the OpenAI SDK equivalent of:
	•	client.responses.create(model="o3-deep-research", input=..., tools=[{"type":"web_search"}])

Key behavior:
	•	If web=False: raise a clear error: “OpenAI deep research requires at least one data source.”  ￼
	•	Capture:
	•	final report text (from response output)
	•	any citations / sources provided by the response
	•	raw response JSON for debugging

Notes:
	•	Deep research via API won’t do ChatGPT’s clarification/rewrite steps automatically; you must feed a fully formed prompt.  ￼
(Optional enhancement: use your existing “synthesis prompt” machinery or add a lightweight prompt-rewriter step with a standard model, but that’s an optional v2.)

Minimal spec for OpenAI DR prompt format (so results are good)
Your research-prompt.md should be treated as the “expanded” prompt. Consider adding a convention section at top of the file template (non-breaking; users can delete it), e.g.:
	•	scope
	•	what to include/exclude
	•	required citations
	•	output structure (headings)

⸻

B) Google Gemini Deep Research Agent (API)

Requirements / constraints from Google docs
	•	Deep Research Agent is only available via Interactions API, not generate_content.  ￼
	•	Runs as a long-running async task with background=True and polling via interactions.get(id).  ￼
	•	Agent id: deep-research-pro-preview-12-2025.  ￼
	•	background=True requires store=True.  ￼
	•	Output returned in interaction.outputs[-1].text when status == "completed".  ￼

Implementation approach
Add new function in deep_research/providers.py:
	•	async def run_google_deep_research(prompt: str, poll_interval: int, max_walltime: int) -> ProviderResult

Pseudo-flow:
	1.	interaction = client.interactions.create(input=prompt, agent="deep-research-pro-preview-12-2025", background=True, store=True)
	2.	Poll:
	•	interaction = client.interactions.get(interaction.id)
	•	if status == "completed" → take output
	•	if status == "failed" → error
	•	if walltime exceeded → cancel locally (API may continue; you just stop waiting)

Save:
	•	final text
	•	raw interaction payload (includes status, usage, etc.)  ￼

⸻

Wiring it into your existing orchestration

1) Extend MODEL_CONFIG

In providers.py, keep MODEL_CONFIG but add a capabilities/modes section:
	•	For OpenAI:
	•	standard models: current (gpt-5.2 etc)
	•	deep models: default o3-deep-research (or make it configurable)
	•	For Google:
	•	standard model: current (whatever you use)
	•	deep agent: deep-research-pro-preview-12-2025

2) Update get_available_providers()

No change needed; availability is still “API key exists”.

3) Update run_research(...)

Change signature to:
	•	run_research(prompt_text, provider_list, timeout, mode="standard", ...)

Inside:
	•	if provider == openai and mode == deep → call run_openai_deep_research
	•	if provider == google and mode == deep → call run_google_deep_research
	•	otherwise → existing standard call

If user selects --mode deep and includes Anthropic/xAI:
	•	either:
	•	warn + fall back to standard for those providers, or
	•	hard error (“deep mode currently only supports OpenAI+Google”)
I’d recommend warn + fall back (less friction).

⸻

Error handling & debuggability

Add provider-specific error text that tells the user exactly what’s missing:
	•	OpenAI deep mode:
	•	missing data source (e.g., --no-web) → explicit error.  ￼
	•	Google deep mode:
	•	if API returns failed, print interaction.error  ￼
	•	if walltime exceeded, instruct user to re-run with higher --max-walltime or lower scope

Always write:
	•	_debug-*.json with raw payload when --debug is enabled (or even always, but I’d keep it behind --debug).

⸻

Testing plan

Unit tests (no network):
	•	Verify CLI parses --mode deep, --poll-interval, --max-walltime
	•	Verify provider selection routes correctly
	•	Verify --no-web with OpenAI deep mode raises

Integration tests (optional, gated by env vars):
	•	OpenAI: run a trivial query with deep research + web_search
	•	Google: start an interaction and poll until completion with a short scope prompt

⸻

Rollout plan
	1.	Implement OpenAI deep research first (simpler: synchronous-ish, one API response).
	2.	Implement Google deep research agent second (async job + polling).
	3.	Add docs to README:
	•	how to run deep mode
	•	cost/time expectations
	•	limitations and fallbacks

⸻

Deliverables checklist (code changes)
	•	deep_research/providers.py
	•	add run_openai_deep_research
	•	add run_google_deep_research
	•	extend run_research(... mode=...)
	•	deep_research/cli.py
	•	add --mode, --poll-interval, --max-walltime, --no-web, and optional override flags
	•	adjust output file naming for deep mode
	•	deep_research/templates.py (optional)
	•	add an optional guidance block to the prompt template to help users write “fully formed” deep research prompts (since API won’t clarify for them).  ￼
	•	README update

