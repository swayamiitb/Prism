"""Unit tests for the provider base contract (no network/DB needed)."""

from __future__ import annotations

import pytest
from context_brain.providers.base import Answer, ContextProvider, Document, Status


class _ReadOnly(ContextProvider):
    id = "ro"
    name = "Read Only"

    def query(self, question: str) -> Answer:
        return Answer(text=f"read {question}")

    def status(self) -> Status:
        return Status(ok=True, detail="up")


class _Writable(ContextProvider):
    id = "wr"
    name = "Writable"

    def query(self, question: str) -> Answer:
        return Answer(text=f"read {question}")

    async def aupdate(self, instruction: str) -> Answer:
        return Answer(text=f"wrote {instruction}")

    def status(self) -> Status:
        return Status(ok=True, detail="up")


class TestWritability:
    def test_readonly_not_writable(self) -> None:
        assert not _ReadOnly().is_writable()

    def test_writable_detected(self) -> None:
        assert _Writable().is_writable()


class TestToolGeneration:
    def test_readonly_only_has_query(self) -> None:
        tools = _ReadOnly().get_tools()
        names = {getattr(t, "name", "") for t in tools}
        assert "query_ro" in names
        assert "update_ro" not in names

    def test_writable_has_both(self) -> None:
        tools = _Writable().get_tools()
        names = {getattr(t, "name", "") for t in tools}
        assert "query_wr" in names
        assert "update_wr" in names


class TestReadOnlyUpdate:
    @pytest.mark.asyncio
    async def test_readonly_update_returns_clean_error(self) -> None:
        p = _ReadOnly()
        result = await p.aupdate("create something")
        assert "read-only" in result.text


class TestAnswerFormatting:
    def test_answer_with_documents(self) -> None:
        from context_brain.providers.base import _format_answer

        answer = Answer(
            text="found 2",
            results=[
                Document(id="1", name="Refund Policy", uri="wiki/refund-policy.md", snippet="refunds over $500"),
                Document(id="2", name="Billing Doc", snippet="Stripe is source of truth"),
            ],
        )
        formatted = _format_answer(answer)
        assert "found 2" in formatted
        assert "Refund Policy" in formatted
        assert "wiki/refund-policy.md" in formatted
        assert "refunds over $500" in formatted

    def test_empty_answer(self) -> None:
        from context_brain.providers.base import _format_answer

        assert _format_answer(Answer(text="")) == "(no results)"


class TestStatus:
    def test_status_dict(self) -> None:
        s = Status(ok=True, detail="healthy")
        assert s.as_dict() == {"ok": True, "detail": "healthy"}
