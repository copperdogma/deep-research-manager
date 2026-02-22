"""CLI entry point for deep-research."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from deep_research import __version__, frontmatter, project, providers, synthesis, updater


def _final_model_hint() -> str:
    """Return a string like 'claude-opus-4-6 (change with: deep-research final <model>)'."""
    try:
        _, model_id = providers.resolve_synthesis_model(None)
        aliases = ", ".join(providers.MODEL_ALIASES.keys())
        return f"{model_id}\n      To change: deep-research final <model>  (options: {aliases})"
    except ValueError:
        return "no API keys found"


def _write_debug_file(project_dir: Path, name: str, content: str) -> Path:
    """Write debug content to _debug-{name}.md and return the path."""
    path = project_dir / f"_debug-{name}.md"
    path.write_text(content)
    return path


def _write_debug_json(project_dir: Path, provider: str, raw_obj: object) -> Path:
    """Write raw deep-research payload to _debug-{provider}-dr.json."""
    import json as _json

    path = project_dir / f"_debug-{provider}-dr.json"
    try:
        # Try to serialize; SDK objects often have a model_dump() or to_dict()
        if hasattr(raw_obj, "model_dump"):
            data = raw_obj.model_dump()
        elif hasattr(raw_obj, "to_dict"):
            data = raw_obj.to_dict()
        else:
            data = str(raw_obj)
        path.write_text(_json.dumps(data, indent=2, default=str))
    except Exception:
        path.write_text(str(raw_obj))
    return path


def _result_filename(result) -> str:
    """Return the output filename for a ProviderResult.

    Deep-research results use a distinct naming pattern:
      ai-{provider}-deep-research.md
    Standard results use the existing convention:
      {slugified-model}-report.md
    """
    if result.mode == "deep":
        return f"ai-{result.provider}-deep-research.md"
    return f"{project.slugify(result.model)}-report.md"


class ConfigGroup(click.Group):
    def get_help(self, ctx):
        rv = super().get_help(ctx)
        config_lines = ["", "", "Configured Providers:"]
        for k, c in providers.MODEL_CONFIG.items():
            status = "SET" if providers.has_provider_api_key(k) else "MISSING"
            config_lines.append(f"  {c['display_name']:10s} [{status:7s}] (Research: {c['research_model']})")
        return rv + "\n".join(config_lines) + "\n"


@click.group(cls=ConfigGroup, invoke_without_command=True)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx):
    """Manage multi-model deep research cycles."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        for name, cmd in sorted(ctx.command.commands.items()):
            sub_ctx = click.Context(cmd, info_name=name, parent=ctx)
            click.echo(f"\n{'─' * 60}")
            click.echo(cmd.get_help(sub_ctx))


@main.command()
@click.argument("topic")
@click.option("--agents", default=6, help="Number of blank agent placeholder files to create.")
@click.option("--dir", "base_dir", default=None, type=click.Path(path_type=Path),
              help="Create the folder somewhere other than the current directory.")
def init(topic: str, agents: int, base_dir: Path | None):
    """Create a new research project folder."""
    try:
        project_dir = project.init_project(topic, agents=agents, base_dir=base_dir)
    except FileExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    slug = project_dir.name
    click.echo(f"Created: {slug}/")
    click.echo(f"  research-prompt.md     \u2190 paste your research prompt here")
    click.echo(f"  synthesis-prompt.md    \u2190 auto-generated (edit if needed)")
    click.echo(f"  ai-agent-01.md \u2026 {agents:02d}    \u2190 paste manual results here")
    click.echo(f"  final-synthesis.md     \u2190 final report goes here")
    click.echo()

    found = project.detect_api_keys()
    missing = project.detect_missing_keys()

    if found:
        click.echo(f"API keys found: {', '.join(found.keys())}")
    if missing:
        parts = [f"{name} ({var})" for name, var in missing.items()]
        click.echo(f"API keys missing: {', '.join(parts)}")

    click.echo()
    click.echo("Next: paste your research prompt into research-prompt.md, then run:")
    click.echo(f"  cd {slug} && deep-research run")


@main.command()
def status():
    """Show the current state of the research project."""
    try:
        project_dir = project.find_project_dir()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    info = project.project_status(project_dir)

    click.echo(f"Research project: {info['topic']}")
    if info["created"]:
        click.echo(f"Created: {info['created']}")
    click.echo()

    # Prompt status
    if info["prompt_filled"]:
        click.echo(f"Research prompt:    \u2713 filled ({info['prompt_words']:,} words)")
    else:
        click.echo("Research prompt:    \u25cb empty")

    # Synthesis prompt status
    auto_label = "auto-generated" if info["synthesis_auto"] else "manually edited"
    click.echo(f"Synthesis prompt:   \u2713 {auto_label} ({info['synthesis_words']:,} words)")
    click.echo()

    # Reports
    click.echo("Reports:")
    for r in info["reports"]:
        if r["filled"]:
            click.echo(f"  \u2713 {r['filename']:<45s} {r['words']:,} words")
        else:
            click.echo(f"  \u25cb {r['filename']:<45s} empty")
    click.echo()

    # Final synthesis
    if info["final_filled"]:
        click.echo(f"Final synthesis:    \u2713 filled ({info['final_words']:,} words)")
    else:
        click.echo("Final synthesis:    \u25cb empty")
    click.echo()

    # Next steps
    filled_count = sum(1 for r in info["reports"] if r["filled"])
    empty_agents = [r for r in info["reports"] if not r["filled"] and "ai-agent" in r["filename"]]

    if not info["prompt_filled"]:
        click.echo("Next: paste your research prompt into research-prompt.md")
    elif filled_count == 0:
        click.echo("Next: deep-research run   (dispatch to API providers)")
    elif empty_agents:
        click.echo("Next: deep-research format   (rename/clean up agent files)")
        click.echo(f"      deep-research final    (synthesize with {_final_model_hint()})")
    elif not info["final_filled"]:
        click.echo(f"Next: deep-research final    (synthesize with {_final_model_hint()})")
    else:
        click.echo("Done. All files ready.")


@main.command()
def format():
    """Rename agent placeholder files based on their content and clean up unused slots."""
    try:
        project_dir = project.find_project_dir()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    scan = project.scan_agent_files(project_dir)
    renamed = []
    skipped = []

    # Files with a detected name — confirm with user
    for filename, detected_name in scan["detected"]:
        name = click.prompt(
            f"{filename} \u2192 detected \"{detected_name}\". "
            f"Enter model name (or press Enter to accept)",
            default=detected_name,
        )
        if name:
            new_name = project.rename_agent_file(project_dir, filename, name)
            renamed.append((filename, new_name))
        else:
            skipped.append(filename)

    # Files with content but no detected name
    for filename in scan["unknown"]:
        name = click.prompt(
            f"{filename} has content but no model name. "
            f"Enter model name (or press Enter to skip)",
            default="",
        )
        if name:
            new_name = project.rename_agent_file(project_dir, filename, name)
            renamed.append((filename, new_name))
        else:
            skipped.append(filename)

    # Delete empty placeholders
    project.delete_empty_agents(project_dir, scan["empty"])

    # Print summary
    if renamed:
        click.echo("Formatted:")
        for old, new in renamed:
            click.echo(f"  {old} \u2192 {new}")

    if scan["empty"]:
        if len(scan["empty"]) == 1:
            click.echo(f"Cleaned up:\n  Removed 1 unused placeholder file ({scan['empty'][0]})")
        else:
            first = scan["empty"][0]
            last = scan["empty"][-1]
            click.echo(
                f"Cleaned up:\n  Removed {len(scan['empty'])} unused placeholder files "
                f"({first} \u2026 {last})"
            )

    if skipped:
        click.echo("Skipped:")
        for f in skipped:
            click.echo(f"  {f}")
    elif not renamed and not scan["empty"]:
        click.echo("Nothing to format.")

    # Regenerate synthesis prompt
    regenerated = synthesis.regenerate_synthesis_prompt(project_dir)
    if regenerated:
        filled = len(project.get_filled_reports(project_dir))
        click.echo(f"Synthesis prompt updated ({filled} reports).")
    else:
        click.echo(
            "synthesis-prompt.md has manual edits (auto-generated: false). "
            "Skipping regeneration. Delete and re-run to regenerate."
        )

    # Next step
    click.echo(f"\nNext: deep-research final    (synthesize with {_final_model_hint()})")
    click.echo("      deep-research prepare-final   (or assemble for manual paste)")


@main.command("prepare-final")
@click.option("--clipboard/--no-clipboard", default=None,
              help="Force clipboard copy on/off.")
@click.option("--max-chars", default=200000, type=int,
              help="Warn if assembled content exceeds this character count.")
def prepare_final(clipboard: bool | None, max_chars: int):
    """Assemble synthesis prompt + all reports for manual pasting."""
    try:
        project_dir = project.find_project_dir()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    try:
        payload = synthesis.assemble_synthesis_payload(project_dir)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Write to _synthesis-input.md
    output_path = project_dir / "_synthesis-input.md"
    output_path.write_text(payload)

    words = project.word_count(payload)
    chars = len(payload)

    if chars > max_chars:
        click.echo(
            f"Warning: assembled content is {chars:,} characters ({words:,} words). "
            f"This exceeds --max-chars={max_chars:,}."
        )

    # Clipboard
    copied = False
    if clipboard is not False:
        copied = _try_clipboard(payload)
        if clipboard is True and not copied:
            click.echo("Warning: clipboard copy failed (no pbcopy/xclip/clip found).", err=True)

    click.echo(f"Assembled synthesis input:")
    click.echo(f"  _synthesis-input.md ({words:,} words, ~{chars // 4:,} tokens)")
    click.echo(f"  Copied to clipboard: {'yes' if copied else 'no'}")
    click.echo()
    click.echo("Paste this into your AI of choice, then paste the result into final-synthesis.md.")
    click.echo("To clean up: rm _synthesis-input.md")


def _try_clipboard(text: str) -> bool:
    """Try to copy text to clipboard. Returns True on success."""
    import subprocess
    import platform

    cmds = {
        "Darwin": ["pbcopy"],
        "Linux": ["xclip", "-selection", "clipboard"],
        "Windows": ["clip"],
    }
    cmd = cmds.get(platform.system())
    if not cmd:
        return False
    try:
        proc = subprocess.run(cmd, input=text.encode(), check=True, capture_output=True)
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


@main.command()
@click.option("--provider", "provider_names", multiple=True, metavar="PROVIDER",
              help="Limit to specific provider(s). Repeat for multiple: "
                   "--provider openai --provider google. "
                   "Omit to run all providers with API keys set. "
                   "Known values: openai, anthropic, google, xai.")
@click.option("--mode", "run_mode", default="standard",
              type=click.Choice(["standard", "deep"], case_sensitive=False),
              help="Research mode. 'deep' uses OpenAI/Google deep-research APIs.")
@click.option("--dry-run", is_flag=True, help="Show what would be called without making API requests.")
@click.option("--debug", is_flag=True, help="Write full prompts and responses to _debug-*.md files.")
@click.option("--timeout", default=600, type=int, help="Timeout per API call in seconds.")
@click.option("--no-web", is_flag=True, default=False,
              help="Disable web search (errors for OpenAI deep research which requires it).")
@click.option("--openai-dr-model", default=None,
              help="Override OpenAI deep-research model (e.g. o3-deep-research).")
@click.option("--google-dr-agent", default=None,
              help="Override Google deep-research agent id.")
@click.option("--poll-interval", default=10, type=int,
              help="Seconds between status polls for deep research (default 10).")
@click.option("--max-walltime", default=1800, type=int,
              help="Max seconds to wait for Google deep research (default 1800).")
def run(
    provider_names: tuple[str, ...],
    run_mode: str,
    dry_run: bool,
    debug: bool,
    timeout: int,
    no_web: bool,
    openai_dr_model: str | None,
    google_dr_agent: str | None,
    poll_interval: int,
    max_walltime: int,
):
    """Send the research prompt to all available API providers in parallel.

    \b
    Examples:
      deep-research run                              # all providers with API keys
      deep-research run --provider openai            # OpenAI only
      deep-research run --provider openai --provider google  # two providers
      deep-research run --mode deep                  # deep research mode (OpenAI + Google)

    Use --mode deep to use real deep-research APIs (OpenAI Responses API +
    Google Interactions API).  Providers without deep support (Anthropic, xAI)
    fall back to standard mode automatically.
    """
    try:
        project_dir = project.find_project_dir()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if project.is_prompt_empty(project_dir):
        click.echo("Error: research-prompt.md is empty. Paste your research prompt first.", err=True)
        sys.exit(1)

    prompt_text = project.get_research_prompt(project_dir)

    # Determine providers
    if provider_names:
        provider_list = []
        for pname in provider_names:
            key = pname.lower()
            if key not in providers.MODEL_CONFIG:
                known = ", ".join(providers.MODEL_CONFIG.keys())
                click.echo(f"Error: unknown provider '{pname}'. Known: {known}", err=True)
                sys.exit(1)
            if not providers.has_provider_api_key(key):
                click.echo(f"Error: {providers.provider_env_hint(key)} not set.", err=True)
                sys.exit(1)
            provider_list.append(key)
    else:
        provider_list = providers.get_available_providers()

    if not provider_list:
        click.echo(
            "Error: No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "GEMINI_API_KEY (or GOOGLE_API_KEY), etc. "
            "Or paste results manually into ai-agent-XX.md files.",
            err=True,
        )
        sys.exit(1)

    # Early validation: --no-web with OpenAI deep research is an error
    if run_mode == "deep" and no_web and "openai" in provider_list:
        click.echo(
            "Error: OpenAI deep research requires at least one data source. "
            "Cannot use --no-web with OpenAI deep research.",
            err=True,
        )
        sys.exit(1)

    if debug:
        debug_parts = [f"# Debug: run\n\nTimestamp: {datetime.now(timezone.utc).isoformat()}\n"]
        debug_parts.append(f"## Mode: {run_mode}\n")
        debug_parts.append(f"## Prompt Sent\n\n```\n{prompt_text}\n```\n")

    is_deep = run_mode == "deep"

    if dry_run:
        click.echo(f"Would run research prompt ({run_mode} mode) against {len(provider_list)} providers:")
        for p in provider_list:
            config = providers.MODEL_CONFIG[p]
            if is_deep and p in providers.DEEP_RESEARCH_PROVIDERS:
                dr = providers.DEEP_RESEARCH_DEFAULTS[p]
                label = openai_dr_model or dr.get("model") or google_dr_agent or dr.get("agent")
                click.echo(f"  {config['display_name']} DEEP ({label})")
            else:
                fallback = " (fallback to standard)" if is_deep else ""
                click.echo(f"  {config['display_name']} ({config['research_model']}){fallback}")
        click.echo(f"\nPrompt: {project.word_count(prompt_text):,} words")
        return

    mode_label = "deep research" if is_deep else "research"

    # Warn about fallback providers in deep mode
    if is_deep:
        fallback_providers = [p for p in provider_list if p not in providers.DEEP_RESEARCH_PROVIDERS]
        if fallback_providers:
            names = ", ".join(providers.MODEL_CONFIG[p]["display_name"] for p in fallback_providers)
            click.echo(f"Note: {names} will use standard mode (no deep research support).\n")

    click.echo(f"Running {mode_label} prompt against {len(provider_list)} providers...\n")

    # For deep mode, use a longer default timeout
    effective_timeout = timeout if timeout != 600 else (3600 if is_deep else 600)

    results = asyncio.run(
        providers.run_research(
            prompt_text,
            provider_list,
            timeout=effective_timeout,
            mode=run_mode,
            openai_dr_model=openai_dr_model,
            google_dr_agent=google_dr_agent,
            no_web=no_web,
            poll_interval=poll_interval,
            max_walltime=max_walltime,
            debug=debug,
        )
    )

    # Read topic from frontmatter (once)
    rp_meta, _ = frontmatter.parse((project_dir / "research-prompt.md").read_text())
    topic = rp_meta.get("topic", project_dir.name)

    succeeded = 0
    for result in results:
        config = providers.MODEL_CONFIG[result.provider]
        result_is_deep = result.mode == "deep"

        if result.error:
            # Write error to file
            error_filename = _result_filename(result)
            error_path = project_dir / error_filename
            error_path.write_text(
                f"# Error\n\nProvider: {config['display_name']}\n"
                f"Model: {result.model}\nMode: {result.mode}\n"
                f"Error: {result.error}\n"
            )
            click.echo(f"  \u2717 {config['display_name']} ({result.model}) \u2192 ERROR: {result.error}")
            if debug:
                debug_parts.append(
                    f"## Response: {config['display_name']} ({result.model})\n\n"
                    f"**ERROR** ({result.elapsed_seconds:.1f}s)\n\n```\n{result.error}\n```\n"
                )
        else:
            filename = _result_filename(result)
            filepath = project_dir / filename

            # Check for existing file
            if filepath.exists():
                if not click.confirm(f"  {filename} already exists. Overwrite?"):
                    click.echo(f"  Skipped {config['display_name']} ({result.model})")
                    continue

            words = project.word_count(result.content)
            elapsed_str = f"{result.elapsed_seconds:.0f}s"

            meta = {
                "type": "research-report",
                "topic": topic,
                "canonical-model-name": result.model,
                "research-mode": result.mode,
                "collected": datetime.now(timezone.utc).isoformat(),
            }
            filepath.write_text(frontmatter.dump(meta, result.content))

            mode_tag = " [DEEP]" if result_is_deep else ""
            click.echo(
                f"  \u2713 {config['display_name']} ({result.model}){mode_tag} \u2192 {filename} "
                f"({words:,} words, ${result.cost:.2f}, {elapsed_str})"
            )
            succeeded += 1

            if debug:
                debug_parts.append(
                    f"## Response: {config['display_name']} ({result.model}) [{result.mode}]\n\n"
                    f"**OK** \u2014 {words:,} words, {result.tokens_used:,} tokens, "
                    f"${result.cost:.2f}, {result.elapsed_seconds:.1f}s\n\n"
                    f"```\n{result.content}\n```\n"
                )

            # Write debug JSON payload for deep research results
            if debug and result_is_deep and getattr(result, "debug_payload", None):
                _write_debug_json(project_dir, result.provider, result.debug_payload)

    total_cost = sum(r.cost for r in results)
    click.echo(f"\nCompleted {succeeded} of {len(results)} API calls. Total cost: ${total_cost:.2f}")

    # Regenerate synthesis prompt
    regenerated = synthesis.regenerate_synthesis_prompt(project_dir)
    if regenerated:
        filled = len(project.get_filled_reports(project_dir))
        click.echo(f"Synthesis prompt updated ({filled} reports).")

    # Show unused agent slots
    empty = project.get_empty_reports(project_dir)
    agent_empty = [f for f in empty if "ai-agent" in f.name]
    if agent_empty:
        names = ", ".join(f.name for f in agent_empty)
        click.echo(f"Unused agent slots: {names} (paste manual results here)")

    click.echo("\nNext steps:")
    click.echo("  - Paste results from other models into ai-agent-XX.md files")
    click.echo("  - Run: deep-research format    (to rename and clean up)")
    click.echo(f"  - Run: deep-research final     (synthesize with {_final_model_hint()})")

    if debug:
        debug_path = _write_debug_file(project_dir, "run", "\n".join(debug_parts))
        click.echo(f"\nDebug output: {debug_path.name}")


@main.command()
@click.argument("provider_names", nargs=-1, metavar="[PROVIDER]...")
@click.option(
    "--all", "stub_all", is_flag=True,
    help="Create stubs even for providers that already have a report file.",
)
@click.option(
    "--mode", "stub_mode", default="standard",
    type=click.Choice(["standard", "deep"], case_sensitive=False),
    help="Research mode to record in the stub frontmatter (default: standard).",
)
def stub(provider_names: tuple[str, ...], stub_all: bool, stub_mode: str):
    """Create blank report stubs for manual paste-in.

    Stubs have correct frontmatter (model name, topic, timestamp) but an
    empty body, so they are excluded from synthesis until you paste content.

    \b
    Examples:
      deep-research stub               # all providers without an existing report
      deep-research stub xai           # only xAI
      deep-research stub xai anthropic # xAI and Anthropic
      deep-research stub --all         # every provider, overwriting existing stubs
      deep-research stub xai --mode deep
    """
    try:
        project_dir = project.find_project_dir()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    rp_meta, _ = frontmatter.parse((project_dir / "research-prompt.md").read_text())
    topic = rp_meta.get("topic", project_dir.name)

    # Resolve target providers
    if provider_names:
        target = []
        for name in provider_names:
            key = name.lower()
            if key not in providers.MODEL_CONFIG:
                known = ", ".join(providers.MODEL_CONFIG.keys())
                click.echo(f"Error: unknown provider '{name}'. Known: {known}", err=True)
                sys.exit(1)
            target.append(key)
    else:
        target = list(providers.MODEL_CONFIG.keys())

    created = []
    skipped = []

    for provider_key in target:
        config = providers.MODEL_CONFIG[provider_key]
        model = config["research_model"]

        if not stub_all and project.stub_exists(project_dir, provider_key, model):
            skipped.append((provider_key, model))
            continue

        path = project.write_stub(project_dir, provider_key, model, topic, mode=stub_mode)
        created.append((provider_key, model, path.name))

    if created:
        click.echo("Created stubs:")
        for _, model, filename in created:
            click.echo(f"  {filename}  ({model})")
    if skipped:
        skip_names = ", ".join(m for _, m in skipped)
        click.echo(f"Skipped (already have reports): {skip_names}")
        click.echo("  Use --all to overwrite.")
    if not created and not skipped:
        click.echo("Nothing to do.")

    if created:
        click.echo(f"\nPaste your results into the stub files, then run:")
        click.echo(f"  deep-research final    (synthesize with {_final_model_hint()})")


@main.command("final")
@click.argument("model", required=False, default=None)
@click.option("--dry-run", is_flag=True, help="Show token count / estimated cost without calling the API.")
@click.option("--debug", is_flag=True, help="Write full prompt and response to _debug-final.md.")
@click.option("--timeout", default=900, type=int, help="Timeout for the synthesis call in seconds.")
def final(model: str | None, dry_run: bool, debug: bool, timeout: int):
    """Generate the final synthesis report via API.

    Optionally specify MODEL to choose the synthesis provider.
    Aliases: opus, sonnet, chatgpt, gemini, grok.
    Default: best available (anthropic > openai > google > xai).
    """
    try:
        project_dir = project.find_project_dir()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Resolve model
    try:
        provider_key, model_id = providers.resolve_synthesis_model(model)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        if model:
            available = providers.get_available_providers()
            if available:
                click.echo(f"Available: {', '.join(available)}")
            click.echo("Or paste the synthesis manually — run: deep-research prepare-final")
        sys.exit(1)

    # Assemble payload
    try:
        payload = synthesis.assemble_synthesis_payload(project_dir)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    words = project.word_count(payload)
    est_tokens = len(payload) // 4
    filled = project.get_filled_reports(project_dir)

    config = providers.MODEL_CONFIG[provider_key]

    if dry_run:
        click.echo(f"Synthesis dry run:")
        click.echo(f"  Model: {config['display_name']} ({model_id})")
        click.echo(f"  Input: {len(filled)} reports ({words:,} words, ~{est_tokens:,} tokens)")
        click.echo(f"  Estimated cost: (depends on model pricing)")
        return

    click.echo(f"Running synthesis with {config['display_name']} ({model_id})...")

    result = asyncio.run(providers.run_synthesis(payload, provider_key, model_id, timeout=timeout))

    if result.error:
        click.echo(f"Error: {result.error}", err=True)
        if debug:
            debug_parts = [
                f"# Debug: final\n\nTimestamp: {datetime.now(timezone.utc).isoformat()}\n",
                f"Model: {config['display_name']} ({model_id})\n",
                f"## Prompt Sent\n\n```\n{payload}\n```\n",
                f"## Response\n\n**ERROR**\n\n```\n{result.error}\n```\n",
            ]
            debug_path = _write_debug_file(project_dir, "final", "\n".join(debug_parts))
            click.echo(f"Debug output: {debug_path.name}", err=True)
        sys.exit(1)

    # Write to final-synthesis.md
    rp_meta, _ = frontmatter.parse((project_dir / "research-prompt.md").read_text())
    topic = rp_meta.get("topic", project_dir.name)

    final_path = project_dir / "final-synthesis.md"
    final_path.write_text(
        frontmatter.dump(
            {
                "type": "synthesis-report",
                "topic": topic,
                "synthesis-model": model_id,
                "source-reports": [f.name for f in filled],
                "synthesized": datetime.now(timezone.utc).isoformat(),
            },
            result.content,
        )
    )

    output_words = project.word_count(result.content)
    click.echo(f"\nSynthesis complete:")
    click.echo(f"  Model: {model_id}")
    click.echo(f"  Input: {len(filled)} reports ({words:,} words total)")
    click.echo(f"  Output: final-synthesis.md ({output_words:,} words)")
    click.echo(f"  Cost: ${result.cost:.2f}")
    click.echo(f"\nDone. All files ready in {project_dir.name}/")

    if debug:
        debug_parts = [
            f"# Debug: final\n\nTimestamp: {datetime.now(timezone.utc).isoformat()}\n",
            f"Model: {config['display_name']} ({model_id})\n",
            f"Source reports: {', '.join(f.name for f in filled)}\n",
            f"## Prompt Sent\n\n({words:,} words, ~{est_tokens:,} tokens)\n\n```\n{payload}\n```\n",
            f"## Response\n\n({output_words:,} words, {result.tokens_used:,} tokens, "
            f"${result.cost:.2f}, {result.elapsed_seconds:.1f}s)\n\n```\n{result.content}\n```\n",
        ]
        debug_path = _write_debug_file(project_dir, "final", "\n".join(debug_parts))
        click.echo(f"Debug output: {debug_path.name}")


@main.command("check-providers")
@click.option("--force", is_flag=True, help="Update without confirmation.")
def check_providers(force: bool):
    """Check for newer SOTA models from each provider and update config."""
    click.echo("Checking for newer models...")
    
    # Check for API keys
    available = providers.get_available_providers()
    missing = [k for k in providers.MODEL_CONFIG if not providers.has_provider_api_key(k)]
    
    if not available:
        click.echo("Error: No API keys found. Cannot check for updates.", err=True)
        sys.exit(1)

    if missing:
        click.echo(f"Note: Skipping {', '.join(missing)} (API keys not set).")
    
    updates = asyncio.run(updater.discover_new_models())
    
    if not updates:
        click.echo("All models are up to date.")
        return

    click.echo("\nFound newer models:")
    for provider, new_model in updates.items():
        current = providers.MODEL_CONFIG[provider]["research_model"]
        click.echo(f"  {provider:10s} {current} \u2192 {new_model}")

    if not force:
        if not click.confirm("\nUpdate providers.py with these new models?"):
            click.echo("Aborted.")
            return

    updater.update_providers_file(updates)
    click.echo("\nUpdated providers.py. Run your research again with the new models!")


if __name__ == "__main__":
    main()
