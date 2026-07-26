"""
Context Brain — Context Registry
================================

The env-driven provider factory. Always-on: brain, wiki, slack, drive. All run
on seeded local data by default (zero credentials); real Slack/Drive light up
when their env vars are set. Provider ids are globally deduped (first wins).
"""

from __future__ import annotations

import logging

from context_brain.providers.base import ContextProvider, Status
from context_brain.providers.brain import BrainProvider
from context_brain.providers.drive import DriveProvider
from context_brain.providers.slack import SlackProvider
from context_brain.providers.wiki import WikiProvider

log = logging.getLogger(__name__)

context_providers: list[ContextProvider] = []


def create_context_providers() -> list[ContextProvider]:
    """Build the registered providers, cache them, return the list."""
    configured: list[ContextProvider] = [
        BrainProvider(),
        WikiProvider(),
        SlackProvider(),
        DriveProvider(),
    ]

    seen: set[str] = set()
    deduped: list[ContextProvider] = []
    for provider in configured:
        if provider.id in seen:
            log.warning("context id %r already registered; skipping duplicate", provider.id)
            continue
        seen.add(provider.id)
        deduped.append(provider)

    context_providers[:] = deduped
    _log_providers(deduped)
    return list(context_providers)


def _log_providers(providers: list[ContextProvider]) -> None:
    if not providers:
        log.info("Context Providers: (none)")
        return
    lines = ["Context Providers:"]
    for p in providers:
        try:
            s = p.status()
        except Exception as exc:
            s = Status(ok=False, detail=f"{type(exc).__name__}: {exc}")
        flag = "✓" if s.ok else "✗"
        lines.append(f"  {flag} {p.id:<8} {p.name:<32} {s.detail}")
    log.info("\n".join(lines))


def get_context_providers() -> list[ContextProvider]:
    if not context_providers:
        create_context_providers()
    return list(context_providers)


def update_context_providers(new_providers: list[ContextProvider]) -> None:
    """Swap the cached list in place. Used by eval fixtures."""
    context_providers[:] = new_providers


def get_provider(provider_id: str) -> ContextProvider | None:
    for p in get_context_providers():
        if p.id == provider_id:
            return p
    return None


def provider_status_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for p in get_context_providers():
        try:
            s = p.status()
        except Exception as exc:
            s = Status(ok=False, detail=f"{type(exc).__name__}: {exc}")
        rows.append({"id": p.id, "name": p.name, "ok": s.ok, "detail": s.detail, "writable": p.is_writable()})
    return rows


def providers_summary() -> str:
    """Markdown summary for prompt interpolation into the orchestrator."""
    providers = get_context_providers()
    if not providers:
        return "(no context providers registered)"
    return "\n".join(f"- `{p.id}`: {p.name}" for p in providers)
