"""
Context Brain — Settings
========================

Centralised, env-driven configuration + the local-model factory.

Every model runs locally via Ollama on the company's own hardware — company
knowledge is sensitive, so nothing should ever leave the network. The reasoning
brain is ``gemma4:12b`` (under 31B params, built for agentic workflows).
"""

from __future__ import annotations

from functools import lru_cache

from langchain_ollama import ChatOllama
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime knobs, loaded from the environment (or ``.env``)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Runtime ─────────────────────────────────────────────────────────────
    runtime_env: str = "dev"

    # ── Ollama (local model runtime) ────────────────────────────────────────
    ollama_host: str = "http://localhost:11434"
    # Gemma 4 (released Apr 2026): frontier-level reasoning at each size,
    # explicitly built for agentic workflows. 12B dense is the local sweet spot.
    # Swap to gemma4:26b-a4b (MoE, 4B active) on stronger hardware.
    ollama_chat_model: str = "gemma4:12b"
    ollama_embed_model: str = "bge-m3"
    ollama_temperature: float = 0.2
    ollama_num_ctx: int = 32768

    # ── Neo4j (the company knowledge graph) ─────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "brain-dev-password"

    # ── Seeded data paths (default to the bundled Northwind sample data) ────
    wiki_path: str = ""
    slack_path: str = ""
    drive_path: str = ""

    # ── Optional real integrations (default: seeded sample data) ────────────
    slack_bot_token: str = ""
    google_service_account_file: str = ""

    # ── Knowledge graph + skills tuning ─────────────────────────────────────
    graph_default_hops: int = Field(2, ge=1, le=5)
    graph_min_confidence: float = Field(0.3, ge=0.0, le=1.0)
    skills_export_dir: str = "skills"
    osint_http_timeout: int = Field(20, ge=3, le=120)  # name retained for back-compat


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Importing ``get_settings()`` is cheap."""
    return Settings()


def default_model() -> ChatOllama:
    """Fresh ``ChatOllama`` instance per agent — avoids shared-state footguns.

    The model is the reasoning brain: it routes to context providers, decides
    when to synthesize company knowledge into the graph, and answers. We bind
    tools at the agent level, not here, so one factory serves every agent.
    """
    s = get_settings()
    return ChatOllama(
        base_url=s.ollama_host,
        model=s.ollama_chat_model,
        temperature=s.ollama_temperature,
        num_ctx=s.ollama_num_ctx,
    )


def embed_model_name() -> str:
    """Name of the Ollama embedding model used for semantic node search."""
    return get_settings().ollama_embed_model
