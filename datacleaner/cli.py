"""DataCleaner CLI — Local AI-Powered PII Detection & Redaction.

Usage:
    dc scan ./documents/                    Scan directory for PII
    dc scan contract.pdf --redact            Scan and redact
    dc scan emails.csv --no-llm              Regex-only mode (faster)
    dc audit                                 View recent audit logs
    dc license activate <key>                Activate a license
    dc config                                Show current configuration
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich import box

from datacleaner import __version__
from datacleaner.config import load_config, save_config
from datacleaner.scanner import scan_file, scan_text
from datacleaner.redactor import redact_text, generate_audit_log, save_audit_log, get_audit_path
from datacleaner.license import check_license, activate_license

console = Console()


# ============================================================
#  BANNER
# ============================================================
BANNER = """
[bold cyan]
   ██████╗  █████╗ ████████╗ █████╗  ██████╗██╗     ███████╗ █████╗ ███╗   ██╗███████╗██████╗ 
   ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔════╝██╔══██╗
   ██║  ██║███████║   ██║   ███████║██║     ██║     █████╗  ███████║██╔██╗ ██║█████╗  ██████╔╝
   ██║  ██║██╔══██║   ██║   ██╔══██║██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║██╔══╝  ██╔══██╗
   ██████╔╝██║  ██║   ██║   ██║  ██║╚██████╗███████╗███████╗██║  ██║██║ ╚████║███████╗██║  ██║
   ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
[/bold cyan]
[dim]   Local AI-Powered PII Detection & Redaction — Zero Data Leaves Your Machine[/dim]
[dim]   v{version} | Powered by Ollama + Regex | https://getdatacleaner.com[/dim]
"""


# ============================================================
#  HELPERS
# ============================================================
def _check_ollama() -> bool:
    """Check if Ollama is running."""
    import ollama
    try:
        ollama.list()
        return True
    except Exception:
        return False


def _print_license_status():
    """Print current license tier."""
    result = check_license()
    if result["valid"]:
        tier_color = {"pro": "green", "team": "blue", "free": "yellow"}.get(result["tier"], "white")
        console.print(f"  License: [{tier_color}]{result['tier'].upper()}[/{tier_color}] — {result['message']}")
    else:
        console.print(f"  License: [yellow]FREE[/yellow] — {result['message']}")
    console.print()


# ============================================================
#  MAIN CLI GROUP
# ============================================================
@click.group()
@click.version_option(version=__version__)
@click.pass_context
def main(ctx):
    """DataCleaner — Local AI-Powered PII Detection & Redaction CLI.

    Scan documents, emails, and databases for personally identifiable
    information. Everything runs on your local GPU via Ollama — zero
    data ever leaves your machine.
    """
    if ctx.invoked_subcommand is None:
        console.print(BANNER.format(version=__version__))
        _print_license_status()

        # Check Ollama
        if not _check_ollama():
            console.print(
                "[yellow]  ⚠ Ollama is not running. Start it with:[/yellow]\n"
                "    [green]ollama serve[/green]\n"
            )
        else:
            console.print("  [green]✓[/green] Ollama connected\n")

        console.print(
            "  [bold]Quick Start:[/bold]\n"
            "    [green]dc scan ./documents/[/green]          Scan a directory\n"
            "    [green]dc scan file.pdf --redact[/green]     Scan and redact\n"
            "    [green]dc audit[/green]                       View audit history\n"
            "    [green]dc license activate <key>[/green]     Activate Pro license\n"
        )


# ============================================================
#  SCAN COMMAND
# ============================================================
@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--redact", is_flag=True, help="Apply redaction to output file")
@click.option("--no-llm", is_flag=True, help="Skip LLM pass (regex only, faster)")
@click.option("--style", type=click.Choice(["block", "placeholder", "mask"]),
              default="block", help="Redaction style (default: block)")
@click.option("--output", "-o", type=click.Path(), help="Output file/directory for redacted content")
@click.option("--audit-dir", type=click.Path(), help="Directory for audit logs")
@click.option("--model", help="Ollama model to use (overrides config)")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
def scan(path, redact, no_llm, style, output, audit_dir, model, output_json):
    """Scan files or directories for PII.

    PATH can be a file or directory. Supports PDF, DOCX, CSV, XLSX, TXT,
    JSON, XML, HTML, MD, and more.
    """
    use_llm = not no_llm

    # License check for LLM usage
    if use_llm:
        lic = check_license()
        if not lic["valid"] and lic["tier"] == "free":
            console.print("[yellow]⚠ Free tier: LLM scanning limited to first 500 chars.[/yellow]\n")

    # Collect files
    target = Path(path)
    if target.is_file():
        files = [target]
    else:
        supported = {".txt", ".md", ".json", ".xml", ".html", ".csv",
                     ".pdf", ".docx", ".xlsx", ".xls", ".log", ".eml"}
        files = sorted([
            f for f in target.rglob("*")
            if f.suffix.lower() in supported and f.is_file()
        ])

    if not files:
        console.print("[red]No supported files found.[/red]")
        return

    console.print(f"\n  [bold]Scanning {len(files)} file(s)[/bold]")
    if use_llm:
        config = load_config()
        active_model = model or config["ollama"]["model"]
        console.print(f"  LLM: [cyan]{active_model}[/cyan] | Style: [cyan]{style}[/cyan]")
    else:
        console.print(f"  Regex-only mode | Style: [cyan]{style}[/cyan]")
    console.print()

    # Process each file
    all_results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=len(files))

        for filepath in files:
            progress.update(task, description=f"  [dim]{filepath.name}[/dim]")

            try:
                result = scan_file(filepath, use_llm=use_llm)
                all_results.append((filepath, result))
            except ConnectionError as e:
                console.print(f"\n[red]  ✗ Connection error:[/red] {e}")
                sys.exit(1)
            except Exception as e:
                console.print(f"\n  [yellow]⚠ Skipped {filepath.name}:[/yellow] {e}")

            progress.advance(task)

    # --- Display results ---
    grand_total = sum(r[1]["stats"]["total"] for r in all_results)

    console.print()
    if grand_total == 0:
        console.print(Panel.fit(
            "[green]✓ No PII detected in any file.[/green]",
            border_style="green"
        ))
    else:
        _display_scan_results(all_results, grand_total, style)

    # --- Redaction ---
    if redact:
        console.print("\n  [bold]Applying redactions...[/bold]")
        _apply_redactions(all_results, style, output, audit_dir)

    # --- JSON output ---
    if output_json:
        import json
        json_results = []
        for filepath, result in all_results:
            json_results.append({
                "file": str(filepath),
                "findings_count": result["stats"]["total"],
                "findings": result["findings"],
                "stats": result["stats"],
            })
        console.print("\n[JSON Output]")
        console.print(json.dumps(json_results, indent=2, ensure_ascii=False))


def _display_scan_results(all_results: list, grand_total: int, style: str):
    """Display scan results in a Rich table."""
    table = Table(title=f"PII Scan Results — {grand_total} finding(s)", box=box.ROUNDED)
    table.add_column("File", style="cyan", no_wrap=False)
    table.add_column("Findings", justify="right", style="yellow")
    table.add_column("Categories", style="dim")

    for filepath, result in all_results:
        stats = result["stats"]
        if stats["total"] == 0:
            table.add_row(
                filepath.name,
                "0",
                "[green]clean[/green]"
            )
            continue

        cats = ", ".join(
            f"{cat} ({count})"
            for cat, count in sorted(stats["by_category"].items(),
                                     key=lambda x: -x[1])[:3]
        )
        table.add_row(
            filepath.name,
            str(stats["total"]),
            cats
        )

    console.print(table)

    # Show sample findings
    console.print("\n  [bold]Sample findings:[/bold]")
    for filepath, result in all_results:
        if result["findings"]:
            console.print(f"  [cyan]{filepath.name}:[/cyan]")
            for f in result["findings"][:5]:
                method_icon = "🧠" if f["method"] == "llm" else "📋"
                snippet = f["match"][:60].replace("\n", "\\n")
                console.print(
                    f"    {method_icon} [{f['category']}] "
                    f"[yellow]{snippet}[/yellow]"
                    f" [dim]({f.get('confidence', 1.0):.0%})[/dim]"
                )
            if len(result["findings"]) > 5:
                console.print(f"    [dim]... and {len(result['findings']) - 5} more[/dim]")
            break


def _apply_redactions(all_results: list, style: str, output: str, audit_dir: str):
    """Apply redactions and save output files."""
    config = load_config()
    audit_base = Path(audit_dir or config["output"]["audit_dir"]).expanduser().resolve()

    for filepath, result in all_results:
        if not result["findings"]:
            continue

        # Read original text
        original_text = filepath.read_text(encoding="utf-8", errors="replace")

        # Redact
        redacted = redact_text(original_text, result["findings"], style=style)

        # Save redacted file
        out_dir = Path(output) if output else filepath.parent / "redacted"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{filepath.stem}_redacted{filepath.suffix}"
        out_file.write_text(redacted, encoding="utf-8")
        console.print(f"  [green]✓[/green] {out_file}")

        # Save audit log
        audit_path = get_audit_path(filepath, audit_base)
        audit_data = generate_audit_log(
            str(filepath), result["findings"], result["stats"], style
        )
        save_audit_log(audit_data, audit_path)
        console.print(f"  [dim]  Audit: {audit_path}[/dim]")


# ============================================================
#  AUDIT COMMAND
# ============================================================
@main.command()
@click.option("--limit", "-n", default=10, help="Number of entries to show")
def audit(limit):
    """View recent audit logs."""
    config = load_config()
    audit_dir = Path(config["output"]["audit_dir"]).expanduser().resolve()

    if not audit_dir.exists():
        console.print("[yellow]No audit logs found.[/yellow]")
        return

    logs = sorted(audit_dir.glob("audit_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not logs:
        console.print("[yellow]No audit logs found.[/yellow]")
        return

    table = Table(title=f"Recent Audit Logs ({min(limit, len(logs))} of {len(logs)})", box=box.ROUNDED)
    table.add_column("Date", style="dim")
    table.add_column("File")
    table.add_column("Findings", justify="right", style="yellow")
    table.add_column("Method", style="dim")

    import json
    for logfile in logs[:limit]:
        try:
            data = json.loads(logfile.read_text())
            dt = data["timestamp"][:19].replace("T", " ")
            methods = "+".join(sorted(data.get("by_method", {}).keys()))
            table.add_row(
                dt,
                Path(data["file"]).name,
                str(data["total_findings"]),
                methods,
            )
        except Exception:
            table.add_row("?", logfile.name, "?", "?")

    console.print(table)
    console.print(f"\n  [dim]Audit directory: {audit_dir}[/dim]")


# ============================================================
#  LICENSE COMMAND
# ============================================================
@main.group()
def license():
    """Manage DataCleaner license."""
    pass


@license.command()
@click.argument("key")
def activate(key):
    """Activate a Pro or Team license key."""
    console.print(f"  Validating license key...")
    success = activate_license(key)

    if success:
        result = check_license()
        tier_color = {"pro": "green", "team": "blue"}.get(result["tier"], "white")
        console.print(f"  [{tier_color}]✓ {result['tier'].upper()} license activated![/{tier_color}]")
        console.print(f"  {result['message']}")
    else:
        console.print("  [red]✗ Invalid or expired license key.[/red]")
        console.print("  Get a valid key at https://getdatacleaner.com")


@license.command()
def status():
    """Show current license status."""
    result = check_license()
    tier_color = {"pro": "green", "team": "blue", "free": "yellow"}.get(result["tier"], "white")
    console.print(f"  Tier: [{tier_color}]{result['tier'].upper()}[/{tier_color}]")
    console.print(f"  Status: {result['message']}")
    if result.get("expires"):
        console.print(f"  Expires: {result['expires']}")


# ============================================================
#  CONFIG COMMAND
# ============================================================
@main.command()
def config():
    """Show current configuration."""
    cfg = load_config()

    console.print(f"  [bold]Ollama[/bold]")
    console.print(f"    Model: [cyan]{cfg['ollama']['model']}[/cyan]")
    console.print(f"    Host:  {cfg['ollama']['host']}")
    console.print()
    console.print(f"  [bold]Scanning[/bold]")
    console.print(f"    Chunk size:      {cfg['scanning']['chunk_size']}")
    console.print(f"    Confidence min:  {cfg['scanning']['confidence_threshold']}")
    console.print(f"    Max file size:   {cfg['scanning']['max_file_size_mb']}MB")
    console.print()
    console.print(f"  [bold]Redaction[/bold]")
    console.print(f"    Style:  [cyan]{cfg['redaction']['style']}[/cyan]")
    console.print(f"    Audit:  {'ON' if cfg['redaction']['audit_log'] else 'OFF'}")

    # Check Ollama
    if _check_ollama():
        import ollama
        models = [m["name"] for m in ollama.list().get("models", [])]
        installed = [m for m in models if cfg["ollama"]["model"] in m]
        if installed:
            console.print(f"\n  [green]✓[/green] Model [cyan]{cfg['ollama']['model']}[/cyan] is installed")
        else:
            console.print(f"\n  [yellow]⚠[/yellow] Model [cyan]{cfg['ollama']['model']}[/cyan] not found")
            if models:
                console.print(f"  Installed models: {', '.join(models[:5])}")


if __name__ == "__main__":
    main()
