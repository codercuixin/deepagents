"""Middleware to patch dangling tool calls in the messages history."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite


class PatchToolCallsMiddleware(AgentMiddleware):
    """Middleware to patch dangling tool calls in the messages history."""

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """Before the agent runs, handle dangling tool calls from any AIMessage."""
        # 在 before_agent 修复持久化历史,而不只是修复本次模型请求.
        messages = state["messages"]
        if not messages:
            return None

        # 先收集已经有 ToolMessage 回复的 tool_call_id,剩下的就是需要补洞的调用.
        answered_ids = {msg.tool_call_id for msg in messages if msg.type == "tool"}  # ty: ignore[unresolved-attribute]

        # 没有悬空调用时不返回 Overwrite,避免制造无意义的 state churn.
        if not any(
            tool_call["id"] is not None and tool_call["id"] not in answered_ids
            for msg in messages
            if isinstance(msg, AIMessage)
            for tool_call in (*msg.tool_calls, *msg.invalid_tool_calls)
        ):
            return None

        patched_messages: list[AnyMessage] = []
        for msg in messages:
            patched_messages.append(msg)
            if not isinstance(msg, AIMessage):
                continue
            # invalid_tool_calls 也需要闭合;部分 provider 会把坏 JSON 或截断参数放到这里.
            for tool_call in (*msg.tool_calls, *msg.invalid_tool_calls):
                tool_call_id = tool_call["id"]
                # 没有 id 的 tool call 无法构造协议要求的配对 ToolMessage.
                if tool_call_id is None or tool_call_id in answered_ids:
                    continue
                name = tool_call["name"] or "unknown"
                # 用合成 ToolMessage 闭合悬空调用,保证后续模型请求满足 tool call 配对约束.
                if tool_call.get("type") == "invalid_tool_call":
                    content = f"Tool call {name} with id {tool_call_id} could not be executed - arguments were malformed or truncated."
                else:
                    content = f"Tool call {name} with id {tool_call_id} was cancelled - another message came in before it could be completed."
                patched_messages.append(ToolMessage(content=content, name=name, tool_call_id=tool_call_id))

        return {"messages": Overwrite(patched_messages)}
