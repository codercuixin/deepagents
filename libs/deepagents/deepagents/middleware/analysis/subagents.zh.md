# `subagents.py` 分析

## 职责定位

`SubAgentMiddleware` 向主 agent 注入同步 `task` 工具，让主 agent 可以把复杂、独立、上下文较重的任务委托给短生命周期子 agent。子 agent 阻塞运行到完成，只把最终结果作为一个 `ToolMessage` 回填给父 agent。

## 配置类型

- `SubAgent`：声明式配置，由 middleware 根据 `model`、`tools`、`system_prompt`、`middleware` 和 `response_format` 调用 `create_agent()`。
- `CompiledSubAgent`：调用方已经提供 `Runnable`，middleware 只绑定运行名和追踪 metadata。

## 运行流程

1. `SubAgentMiddleware.__init__()` 校验至少一个 subagent。
2. `_get_subagents()` 把不同配置统一转成 `_SubagentSpec`。
3. `_build_task_tool()` 生成 `task` 工具描述和 `subagent_type -> runnable` 映射。
4. `task()` / `atask()` 校验 `subagent_type` 和 `tool_call_id`。
5. `_validate_and_prepare_state()` 从父 state 过滤私有/不可合并 key，只用 task description 构造子 agent 的唯一 `HumanMessage`。
6. `_build_subagent_config()` 只转发 `callbacks`、`tags` 和 `configurable`。
7. 子 agent 运行时同时在 tracing metadata 和 configurable 中标记 `ls_agent_type="subagent"`。
8. 子 agent 返回后，优先序列化 `structured_response`；否则取最后一条非空 `AIMessage` 文本。
9. 返回 `Command(update=...)`，把可安全合并的 state 和一个 `ToolMessage` 写回父 agent。

## 状态边界

过滤的 key 包括 `messages`、`todos`、`structured_response`、`skills_metadata`、`skills_load_errors` 和 `memory_contents`。

这些 key 要么由父/子 agent 各自维护，要么没有安全的跨 agent reducer。过滤同时发生在传给子 agent 和子 agent 回流父 agent 两个方向，避免父 memory/skills 泄漏给子 agent，也避免子私有状态污染父 agent。

## 关键设计

- 同步 subagent 是一次性的，不能对同一个子 agent 继续追加消息。
- `metadata` 和 `recursion_limit` 不从父 config 透传，子图自己的绑定配置优先。
- `CompiledSubAgent` 使用 `with_config()`，不修改原 runnable，允许同一个 runnable 被多个名字复用。
- 子 agent 可单独配置 HITL，不影响父 agent 的工具审批策略。
- 结构化输出优先，便于父 agent 接收机器可读结果。

## 维护注意

- 修改 `_EXCLUDED_STATE_KEYS` 时要同时考虑信息泄漏和 state reducer 语义。
- 自定义 `task_description` 如果不包含 `{available_agents}`，调用方需要自己暴露可用 agent 列表。
- 新增返回字段时要确认它能被父 state reducer 安全合并。
