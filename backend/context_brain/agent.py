"""
Context Brain — Orchestrator
============================

The main agent: a LangGraph ReAct loop that routes to context providers,
reasons over company knowledge, synthesizes processes into the graph, and
exports executable skills.

One LLM hop per turn, tools collected from every registered provider, plus a
``list_providers`` meta-tool. Behavioral rules live in ``instructions.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from context_brain.contexts import (
    get_context_providers,
    provider_status_rows,
    providers_summary,
)
from context_brain.instructions import CONTEXT_BRAIN_INSTRUCTIONS
from context_brain.settings import default_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class ListProvidersArgs(BaseModel):
    reason: str = Field(default="", description="Optional reason (ignored; kept for tool-schema stability).")


def _list_providers(_reason: str = "") -> str:
    import json

    return json.dumps(provider_status_rows())


def _build_list_providers_tool() -> StructuredTool:
    return StructuredTool.from_function(
        _list_providers,
        name="list_providers",
        description=(
            "List every registered context provider with its live status "
            "(connected/healthy or not). Use this to see which sources are available."
        ),
        args_schema=ListProvidersArgs,
    )


def collect_tools() -> list[StructuredTool]:
    """Gather query_*/update_* tools from every provider + list_providers."""
    tools: list[StructuredTool] = [_build_list_providers_tool()]
    for provider in get_context_providers():
        tools.extend(provider.get_tools())
    return tools


def _system_prompt() -> str:
    return CONTEXT_BRAIN_INSTRUCTIONS.format(context_providers=providers_summary())


def build_agent():
    model = default_model()
    tools = collect_tools()
    model_with_tools = model.bind_tools(tools)
    return create_react_agent(
        model_with_tools,
        tools=tools,
        prompt=_system_prompt(),
    )


_agent: Any = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def reset_agent() -> None:
    global _agent
    _agent = None


async def ainvoke(message: str, *, thread_id: str = "default") -> dict[str, Any]:
    """One-shot async invocation. Returns {'content': str, 'tool_calls': [...]}."""
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke({"messages": [HumanMessage(content=message)]}, config=config)
    messages = result.get("messages", [])
    content = ""
    tool_calls: list[str] = []
    for msg in reversed(messages):
        if msg.__class__.__name__ == "AIMessage":
            raw_content = getattr(msg, "content", None)
            if not content and raw_content:
                content = raw_content if isinstance(raw_content, str) else str(raw_content)
            calls = getattr(msg, "tool_calls", None) or []
            tool_calls = [c.get("name", "") for c in calls if isinstance(c, dict)] + tool_calls
    return {"content": content, "tool_calls": tool_calls, "raw": result}


async def astream(message: str, *, thread_id: str = "default"):
    """Async generator yielding agent events for SSE streaming."""
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    tool_calls: list[str] = []
    final_content_parts: list[str] = []

    async for event in agent.astream_events({"messages": [HumanMessage(content=message)]}, config=config, version="v2"):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk is None:
                continue
            text = getattr(chunk, "content", "")
            if isinstance(text, str) and text:
                final_content_parts.append(text)
                yield ("token", text)
        elif kind == "on_tool_start":
            name = event.get("name", "")
            if name:
                tool_calls.append(name)
                yield ("tool", name)

    yield ("done", {"tool_calls": tool_calls, "content": "".join(final_content_parts)})
