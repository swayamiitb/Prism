"""Tests that the seeded Northwind sample data loads and is searchable.

These prove the Brain runs demoable on local data with zero credentials.
"""

from __future__ import annotations

from pathlib import Path

from context_brain.providers.drive import DriveProvider
from context_brain.providers.slack import SlackProvider
from context_brain.providers.wiki import WikiProvider

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "northwind"


class TestSeedDataPresent:
    def test_wiki_exists(self) -> None:
        pages = list((DATA_ROOT / "wiki").glob("*.md"))
        assert len(pages) >= 2, "seeded wiki should have at least 2 pages"

    def test_slack_exists(self) -> None:
        f = DATA_ROOT / "slack.jsonl"
        assert f.exists(), "seeded slack.jsonl must exist"
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) >= 3, "should seed at least 3 Slack threads"

    def test_drive_exists(self) -> None:
        docs = list((DATA_ROOT / "drive").glob("*.md"))
        assert len(docs) >= 1, "seeded drive should have at least 1 doc"


class TestWikiProviderSearchesSeed:
    def test_refund_query_hits_policy(self) -> None:
        p = WikiProvider(root=DATA_ROOT / "wiki")
        answer = p.query("how do we handle refunds over 500?")
        assert answer.results, "wiki should return pages for a refund query"
        joined = " ".join(d.name + " " + d.snippet for d in answer.results).lower()
        assert "refund" in joined

    def test_no_match_returns_clean(self) -> None:
        p = WikiProvider(root=DATA_ROOT / "wiki")
        answer = p.query("xyzzy quantum flurb")
        assert not answer.results


class TestSlackProviderSearchesSeed:
    def test_refund_query_hits_thread(self) -> None:
        p = SlackProvider()
        # Point at the real seed path (default already does, but be explicit).
        answer = p.query("how do we refund a customer over 500")
        assert answer.results, "slack should return threads for a refund query"
        joined = " ".join(d.name + " " + d.snippet for d in answer.results).lower()
        assert "refund" in joined or "500" in joined

    def test_thread_has_provenance(self) -> None:
        p = SlackProvider()
        answer = p.query("refund")
        assert answer.results
        doc = answer.results[0]
        assert doc.source == "slack"
        assert doc.raw.get("channel"), "slack docs must carry channel provenance"


class TestDriveProviderSearchesSeed:
    def test_billing_query_hits_doc(self) -> None:
        p = DriveProvider(root=DATA_ROOT / "drive")
        answer = p.query("stripe refund billing system")
        assert answer.results, "drive should return docs for a billing query"
        joined = " ".join(d.name + " " + d.snippet for d in answer.results).lower()
        assert "stripe" in joined or "refund" in joined
