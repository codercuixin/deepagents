# Middleware 实现分析索引

本目录是 `deepagents.middleware` 的中文实现分析。源码注释用于解释局部边界和设计意图，本文档用于串起每个实现的职责、运行流程和维护注意事项。

## 阅读顺序

1. [`package_exports.zh.md`](package_exports.zh.md)：先看包级公开 API 边界。
2. [`filesystem.zh.md`](filesystem.zh.md)：理解文件、执行、权限和大内容落盘，这是其它模块恢复历史的基础。
3. [`memory.zh.md`](memory.zh.md) 与 [`skills.zh.md`](skills.zh.md)：理解系统提示注入和私有 state。
4. [`subagents.zh.md`](subagents.zh.md) 与 [`async_subagents.zh.md`](async_subagents.zh.md)：理解同步和远程异步委托。
5. [`summarization.zh.md`](summarization.zh.md)：理解长上下文压缩、历史恢复和手动 compact。
6. 辅助模块：[`message_eviction.zh.md`](message_eviction.zh.md)、[`overflow_clip.zh.md`](overflow_clip.zh.md)、[`tool_exclusion.zh.md`](tool_exclusion.zh.md)、[`patch_tool_calls.zh.md`](patch_tool_calls.zh.md)、[`utils.zh.md`](utils.zh.md)、[`permissions.zh.md`](permissions.zh.md)。

## 总体模型

Middleware 不只是给模型增加工具。它还能在模型调用前后改写请求、工具列表、系统提示和持久 state。当前目录里的实现大致分成四类：

- 上下文注入：`MemoryMiddleware`、`SkillsMiddleware`、`SubAgentMiddleware`、`AsyncSubAgentMiddleware`。
- 工具能力：`FilesystemMiddleware`、同步 `task`、异步 task 管理工具。
- 上下文治理：`SummarizationMiddleware`、`SummarizationToolMiddleware`、大消息/大工具结果落盘。
- 协议修复和过滤：`PatchToolCallsMiddleware`、`_ToolExclusionMiddleware`、兼容导出。

维护时最重要的约束是：不要让模型看到与实际工具能力不一致的提示，不要破坏 `AIMessage.tool_calls` 与 `ToolMessage` 的配对协议，不要把父 agent 的私有 state 泄漏给子 agent。
