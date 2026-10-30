"""CLI for the Security Hooks Lab.

Commands:
  lab config                      store your GitHub PAT securely (hidden prompt)
  lab review --mode M --pr N      run the PR-review agent
"""

from __future__ import annotations

import asyncio
import sys

import click

from . import config as cfg
from .agent import run_review
from .credentials import TokenStore, validate_github_token
from .hooks import SecurityViolation


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Security Hooks Lab - PR-review agent (insecure vs secure modes)."""


@cli.command(name="config")
@click.option(
    "--token",
    required=True,
    prompt="GitHub personal access token",
    hide_input=True,
    help="GitHub personal access token (taken via hidden prompt if omitted)",
)
def configure(token: str) -> None:
    """Securely store your GitHub PAT (validated, then saved with 0600 perms)."""
    store = TokenStore()

    click.echo("Validating token...", nl=False)
    ok, login = validate_github_token(token)
    if not ok:
        click.echo(" failed")
        click.secho("Error: invalid GitHub token.", fg="red", err=True)
        sys.exit(1)
    click.echo(" ok")

    store.save_token(token)
    click.secho(f"GitHub token stored for user '{login}'.", fg="green")
    click.echo(f"Saved to: {store.config_file} (permissions 0600)")


@cli.command(name="review")
@click.option(
    "--mode",
    type=click.Choice(["insecure", "secure"]),
    required=True,
    help="insecure = no security checks (may obey injection); secure = hooks block it",
)
@click.option("--pr", type=int, required=True, help="pull request number to review")
@click.option(
    "--repo",
    default=cfg.TARGET_REPO,
    show_default=True,
    help="target repo (owner/name)",
)
def review(mode: str, pr: int, repo: str) -> None:
    """Run the PR-review agent against a pull request."""
    if not TokenStore().is_configured():
        click.secho(
            "GitHub token not configured. Run `uv run lab config` first.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    try:
        asyncio.run(run_review(mode, repo, pr))
    except SecurityViolation as exc:
        click.echo("\n" + "=" * 60)
        click.secho("SECURE MODE: review ABORTED by security hooks.", fg="red", bold=True)
        click.echo("=" * 60)
        click.echo(str(exc))
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        click.secho(f"\nError: {exc}", fg="red", err=True)
        sys.exit(2)

    click.echo("\n" + "=" * 60)
    click.secho(f"Review finished (mode={mode}).", fg="green")
    click.echo("=" * 60)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
