# Context Providers

Each provider is a sub-agent that owns one OSINT source. The orchestrator sees one `query_<id>` (+ optionally `update_<id>`) tool per provider.

## `graph` — Knowledge Graph (writable)

The platform's memory and its showpiece. Reads what we know; writes findings.

- **`query_graph`** — recall by target value, neighborhood traversal (N hops), or whole-graph summary. Handles "what do we know about X" and "who is connected to X".
- **`update_graph`** — files entities + relationships. Delegates to the graph-writer, which asks qwen3 for a strict-JSON plan, validates it, and applies it.
- **Health:** reports node + edge counts.

## `web` — Web Research (read-only)

Self-hosted meta-search + clean page extraction.

- **`query_web`** — searches SearXNG (general category), returns ranked hits with titles/URLs/snippets, and extracts clean text from the top hit via Trafilatura.
- **Health:** probes `GET {SEARXNG_URL}/healthz`.
- **Config:** `SEARXNG_URL`, `WEB_MAX_PAGES` (default 8).

Requires SearXNG's `settings.yml` to allow `formats: [html, json]` (the setup script writes one).

## `domain` — Domain / DNS / WHOIS / SSL (read-only)

Internet-infrastructure recon for a named domain.

- **`query_domain`** — resolves A/AAAA/MX/NS/TXT/CNAME/SOA via dnspython, pulls WHOIS registration (registrar, org, dates, nameservers) via python-whois, and fetches the TLS certificate (subject CN, issuer, validity, SANs) via stdlib ssl.
- **Entities returned:** `IPAddress` (from A/AAAA, linked `RESOLVES_TO`), `Domain` (from NS), `Organization` (from WHOIS org/registrar, linked `REGISTERED_BY`), `Certificate` (linked `HAS_CERTIFICATE`), plus SAN domains.
- **Health:** always `ok` (pure local resolvers).
- **Config:** `OSINT_HTTP_TIMEOUT` (default 20s).

## `github` — GitHub Reconnaissance (read-only)

Public GitHub recon via PyGithub.

- **`query_github`** — detects the target shape:
  - `github.com/<owner>/<repo>` → repo recon (description, stars, forks, language, license; owner linked `AUTHORED`).
  - `github.com/<owner>` or `@<handle>` → user or org recon. Users: profile (name, bio, location, company, followers), email (linked `OWNS`), top repos (each linked `AUTHORED`). Orgs: members (each linked `MEMBER_OF`).
- **Health:** always `ok`; reports authenticated vs anonymous mode.
- **Config:** `GITHUB_TOKEN` (optional; anonymous is 60 req/hr, authenticated 5000/hr).

## Adding a provider

1. Subclass `ContextProvider` in `saas_ai/providers/<name>.py`. Set `id` + `name`; implement `query()` + `status()`. Override `aupdate()` only if it writes the graph (rare).
2. Register it in `create_context_providers()` in `contexts.py`. Optional/env-gated providers should be wrapped in try/except.
3. Return structured `entities` on `Document`s so the orchestrator/`/ingest` can file them — don't write the graph directly from a collection provider.
4. Add a wiring invariant in `evals/wiring.py` and a unit test in `backend/tests/`.
5. Document the provider here and in the README table.
