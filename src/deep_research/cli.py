"""CLI entry point for deep-research."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from deep_research import frontmatter, project, providers, synthesis


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


@click.group()
def main():
    """Manage multi-model deep research cycles."""
    pass


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
@click.option("--provider", "provider_name", default=None,
              help="Run only a specific provider (e.g., openai, anthropic).")
@click.option("--dry-run", is_flag=True, help="Show what would be called without making API requests.")
@click.option("--debug", is_flag=True, help="Write full prompts and responses to _debug-*.md files.")
@click.option("--timeout", default=600, type=int, help="Timeout per API call in seconds.")
def run(provider_name: str | None, dry_run: bool, debug: bool, timeout: int):
    """Send the research prompt to all available API providers in parallel."""
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
    if provider_name:
        provider_list = [provider_name.lower()]
        if provider_list[0] not in providers.MODEL_CONFIG:
            click.echo(f"Error: unknown provider '{provider_name}'.", err=True)
            sys.exit(1)
        env_var = providers.MODEL_CONFIG[provider_list[0]]["env_var"]
        if not os.environ.get(env_var):
            click.echo(f"Error: {env_var} not set.", err=True)
            sys.exit(1)
    else:
        provider_list = providers.get_available_providers()

    if not provider_list:
        click.echo(
            "Error: No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, etc. "
            "Or paste results manually into ai-agent-XX.md files.",
            err=True,
        )
        sys.exit(1)

    if debug:
        debug_parts = [f"# Debug: run\n\nTimestamp: {datetime.now(timezone.utc).isoformat()}\n"]
        debug_parts.append(f"## Prompt Sent\n\n```\n{prompt_text}\n```\n")

    if dry_run:
        click.echo(f"Would run research prompt against {len(provider_list)} providers:")
        for p in provider_list:
            config = providers.MODEL_CONFIG[p]
            click.echo(f"  {config['display_name']} ({config['research_model']})")
        click.echo(f"\nPrompt: {project.word_count(prompt_text):,} words")
        return

    click.echo(f"Running research prompt against {len(provider_list)} providers...\n")
    results = asyncio.run(providers.run_research(prompt_text, provider_list, timeout=timeout))

    succeeded = 0
    for result in results:
        config = providers.MODEL_CONFIG[result.provider]
        if result.error:
            # Write error to file
            error_filename = f"{project.slugify(result.model)}-report.md"
            error_path = project_dir / error_filename
            error_path.write_text(f"# Error\n\nProvider: {config['display_name']}\nModel: {result.model}\nError: {result.error}\n")
            click.echo(f"  \u2717 {config['display_name']} ({result.model}) \u2192 ERROR: {result.error}")
            if debug:
                debug_parts.append(
                    f"## Response: {config['display_name']} ({result.model})\n\n"
                    f"**ERROR** ({result.elapsed_seconds:.1f}s)\n\n```\n{result.error}\n```\n"
                )
        else:
            # Use the model we actually called for the filename
            filename = f"{project.slugify(result.model)}-report.md"
            filepath = project_dir / filename

            # Check for existing file
            if filepath.exists():
                if not click.confirm(f"  {filename} already exists. Overwrite?"):
                    click.echo(f"  Skipped {config['display_name']} ({result.model})")
                    continue

            words = project.word_count(result.content)
            elapsed_str = f"{result.elapsed_seconds:.0f}s"

            # Read topic from frontmatter
            rp_meta, _ = frontmatter.parse((project_dir / "research-prompt.md").read_text())
            topic = rp_meta.get("topic", project_dir.name)

            filepath.write_text(
                frontmatter.dump(
                    {
                        "type": "research-report",
                        "topic": topic,
                        "canonical-model-name": result.model,
                        "collected": datetime.now(timezone.utc).isoformat(),
                    },
                    result.content,
                )
            )
            click.echo(
                f"  \u2713 {config['display_name']} ({result.model}) \u2192 {filename} "
                f"({words:,} words, ${result.cost:.2f}, {elapsed_str})"
            )
            succeeded += 1

            if debug:
                debug_parts.append(
                    f"## Response: {config['display_name']} ({result.model})\n\n"
                    f"**OK** \u2014 {words:,} words, {result.tokens_used:,} tokens, "
                    f"${result.cost:.2f}, {result.elapsed_seconds:.1f}s\n\n"
                    f"```\n{result.content}\n```\n"
                )

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


if __name__ == "__main__":
    main()
