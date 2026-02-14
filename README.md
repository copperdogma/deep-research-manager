# deep-research

A CLI tool that manages the lifecycle of multi-model deep research cycles. Send the same research prompt to multiple AI models, collect their reports, and synthesize a final analysis.

**The folder is the state.** Every step can be done manually (paste into files) or automated via API keys. Zero keys = a structured folder manager. More keys = more automation.

## Install

```bash
pip install git+https://github.com/copperdogma/deep-research-manager.git
```

With all AI providers:

```bash
pip install "git+https://github.com/copperdogma/deep-research-manager.git#egg=deep-research[all]"
```

Or with pipx (recommended for CLI tools):

```bash
pipx install git+https://github.com/copperdogma/deep-research-manager.git
```

## API Keys

Set whichever providers you have access to. All are optional.

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AI..."
export XAI_API_KEY="xai-..."
```

## Quick Start

```bash
# 1. Create a project
deep-research init best-ui-tools

# 2. Write your research prompt
vim best-ui-tools/research-prompt.md

# 3. Dispatch to all available AI providers
cd best-ui-tools
deep-research run

# 4. Optionally paste results from other models into ai-agent-XX.md files
# 5. Rename and clean up
deep-research format

# 6. Generate the final synthesis
deep-research final
```

## Commands

| Command | Description |
|---|---|
| `deep-research init <topic>` | Create a new research project folder |
| `deep-research run` | Send prompt to all available API providers in parallel |
| `deep-research format` | Rename agent files by model name, delete empty placeholders |
| `deep-research status` | Show current project state |
| `deep-research final [model]` | Generate synthesis report via API |
| `deep-research prepare-final` | Assemble payload for manual pasting into an AI |

## How It Works

1. **Init** creates a structured folder with template files
2. **You write** a research prompt (or paste one from a Claude Project, ChatGPT, etc.)
3. **Run** dispatches the prompt to AI providers in parallel and saves their reports
4. **Manually paste** results from models you don't have API access to into `ai-agent-XX.md` files
5. **Format** renames files by model name and cleans up empty placeholders
6. **Final** sends all reports + a synthesis prompt to one model for a consolidated analysis

The result is a folder with all research reports and a final synthesis, ready to drop into your project docs.

## Folder Structure

```
best-ui-tools/
├── research-prompt.md                    ← your research question
├── synthesis-prompt.md                   ← auto-generated synthesis instructions
├── chatgpt-5-2-report.md                ← from API
├── claude-opus-4-6-report.md            ← from API
├── gemini-3-deep-research-report.md     ← manual paste, renamed by format
├── grok-4-1-deep-research-report.md     ← manual paste, renamed by format
└── final-synthesis.md                    ← the final output
```

## Provider Dependencies

Install only what you need:

```bash
pip install "deep-research[openai]"      # OpenAI (also used by xAI)
pip install "deep-research[anthropic]"   # Anthropic
pip install "deep-research[google]"      # Google
pip install "deep-research[all]"         # Everything
```

## Development

```bash
git clone https://github.com/copperdogma/deep-research-manager.git
cd deep-research-manager
pip install -e ".[dev]"
pytest tests/
```

## License

MIT
