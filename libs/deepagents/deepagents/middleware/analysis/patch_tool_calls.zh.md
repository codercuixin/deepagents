# `patch_tool_calls.py` 分析

## 职责定位

`PatchToolCallsMiddleware` 修复历史消息中悬空的 tool call。它在 agent 运行前补齐缺失的 `ToolMessage`，保证下一次模型请求满足工具调用配对协议。

## 运行流程

1. `before_agent()` 读取 `state["messages"]`。
2. 收集已有 `ToolMessage.tool_call_id`。
3. 扫描所有 `AIMessage.tool_calls` 和 `AIMessage.invalid_tool_calls`。
4. 如果没有悬空调用，返回 `None`，不改 state。
5. 重新构造消息列表，在对应 `AIMessage` 后插入合成 `ToolMessage`。
6. 普通 tool call 使用 cancelled 文案；invalid tool call 使用 malformed/truncated 文案。
7. 返回 `Overwrite(patched_messages)`，整体替换 messages channel。

## 关键设计

- 修复发生在 `before_agent`，因此修的是持久化历史，不只是本次模型请求。
- 选择补 `ToolMessage` 而不是删除 `AIMessage`，可以最大限度保留对话事实。
- `tool_call_id is None` 的调用无法合法配对，只能跳过。
- 使用 `Overwrite` 是为了保证 synthetic `ToolMessage` 紧跟对应 `AIMessage`。

## 常见来源

- 用户或系统打断工具执行。
- 工具调用参数被截断或解析失败。
- 历史消息从外部导入时不完整。

## 维护注意

- 合成消息文案应清楚说明工具没有真正执行，避免模型误以为工具成功。
- 修改消息顺序时必须保护 `AIMessage` 与后续 `ToolMessage` 的协议关系。
