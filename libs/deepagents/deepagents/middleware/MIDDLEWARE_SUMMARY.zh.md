# Deep Agents Middleware 实现总结

本文总结 `deepagents.middleware` 下各个实现的职责、运行时流程和主要设计取舍。

## 总体模型

Middleware 和普通工具的区别在于：普通工具只会在模型主动调用时运行，而 middleware 可以拦截模型调用前后的请求，动态调整工具列表、系统提示、消息历史和持久状态。

常见钩子分工：

- `before_agent` / `abefore_agent`：在 agent 运行前加载外部数据并写入 state，例如 memory 和 skills。
- `wrap_model_call` / `awrap_model_call`：在每次模型调用前修改 request，例如追加系统提示、过滤工具、压缩消息。
- `wrap_tool_call` / `awrap_tool_call`：在工具调用前后处理工具请求或结果，例如大工具结果落盘。

## 模块职责一览

| 文件 | 核心符号 | 职责 |
| --- | --- | --- |
| `__init__.py` | public exports | 维护 middleware 包的公共导出，并解释为什么这些能力需要 middleware 而不是普通工具。 |
| `_utils.py` | `append_to_system_message` | 统一把各 middleware 的系统提示追加到 `SystemMessage.content_blocks`。 |
| `_tool_exclusion.py` | `_ToolExclusionMiddleware` | 在 middleware 链后段统一过滤 profile 禁用的工具。 |
| `permissions.py` | `FilesystemPermission` | 为旧导入路径保留兼容性，真实实现位于 `filesystem.py`。 |
| `patch_tool_calls.py` | `PatchToolCallsMiddleware` | 修补历史中没有对应 `ToolMessage` 的悬空 tool call，保证消息协议完整。 |
| `_message_eviction.py` | `_offload_tool_message_content` | 把超大 `ToolMessage` 文本写入 backend，并用 head/tail 预览消息替换。 |
| `_overflow_clip.py` | `_clip_overflow_tail` | 在摘要 fallback 后仍溢出时，专门裁剪尾部连续 `ToolMessage` 批次。 |
| `filesystem.py` | `FilesystemMiddleware` | 提供文件系统和可选 shell 执行工具，处理权限、系统提示、大消息和大工具结果落盘。 |
| `memory.py` | `MemoryMiddleware` | 从 backend 读取 `AGENTS.md` 类记忆文件，并注入系统提示。 |
| `skills.py` | `SkillsMiddleware` | 扫描 `SKILL.md` 元数据，以渐进披露方式把技能摘要和路径注入系统提示。 |
| `subagents.py` | `SubAgentMiddleware` | 提供同步 `task` 工具，启动短生命周期子 agent 并把最终结果回填父 agent。 |
| `async_subagents.py` | `AsyncSubAgentMiddleware` | 提供远程异步 subagent 任务工具，管理启动、查询、更新、取消和列表。 |
| `summarization.py` | `SummarizationMiddleware`, `SummarizationToolMiddleware` | 自动或手动压缩长对话，历史落盘，记录 `_summarization_event` 以重建模型上下文。 |

## FilesystemMiddleware

`FilesystemMiddleware` 是文件能力的核心入口，注册 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep` 和 `execute`。

主要流程：

1. 初始化时解析 backend、权限和 artifact 前缀。
2. 每个工具 wrapper 先校验绝对路径，再执行 middleware 层权限检查，最后调用 backend。
3. `wrap_model_call` 根据当前 backend 能力动态隐藏 `execute`，并追加对应系统提示。
4. 如果最新 `HumanMessage` 太大，正文写入 `/conversation_history/<uuid>.md`，state 中给原消息打 `lc_evicted_to` 标签，模型只看到预览。
5. `wrap_tool_call` 拦截大工具结果，将正文写入 `/large_tool_results/<tool_call_id>`，模型收到包含路径和 head/tail 预览的替代消息。

关键取舍：

- 权限规则按声明顺序第一条命中生效，默认 `allow`。
- 路径权限是 middleware 工具层能力，不能约束 shell 命令内部读写；因此带执行能力的 backend 和权限组合会被严格限制。
- `read_file` 不走通用工具结果落盘，而是依靠分页和内部截断，避免模型被引导去读 offload 文件而不是原始文件。
- 大消息或大工具结果落盘失败时保留原消息，优先不丢数据，但可能继续面临上下文溢出。

## Memory 与 Skills

`MemoryMiddleware` 和 `SkillsMiddleware` 都遵循“加载阶段写 state，模型调用阶段改 request”的模式。

`MemoryMiddleware`：

- `before_agent` 从配置的 `sources` 加载记忆文件。
- `file_not_found` 视为正常缺失，其他 backend 错误会抛出。
- `modify_request` 不做 I/O，只把 `state["memory_contents"]` 格式化进系统提示。
- 可选 `add_cache_control` 会在 Anthropic 模型上给最后一个系统块添加 prompt-cache breakpoint。

`SkillsMiddleware`：

- 先 `ls` 每个 source 下的技能目录，再批量下载 `SKILL.md`。
- 只解析 YAML frontmatter 元数据，不把完整技能正文直接塞进 prompt。
- 同名技能由后面的 source 覆盖前面的 source。
- 加载错误会以转义后的 warning 进入系统提示，避免诊断文本被模型当成指令执行。

二者差异：

- memory 是始终加载的长期上下文。
- skills 是能力目录，系统提示只暴露名称、描述和路径，完整说明由模型按需 `read_file`。

## SubAgentMiddleware

同步 subagent 通过一个 `task` 工具运行。

配置类型：

- `SubAgent`：由 middleware 根据 `model`、`tools`、`system_prompt` 等配置即时创建 LangChain agent。
- `CompiledSubAgent`：调用方已经提供 `Runnable`，middleware 只绑定运行名和追踪元数据。

调用流程：

1. 父 agent 调用 `task(description, subagent_type)`。
2. middleware 根据 `subagent_type` 找到对应 runnable。
3. 构造子 agent state：过滤 `messages`、`todos`、`structured_response`、`skills_metadata`、`skills_load_errors`、`memory_contents` 等不可透传 key，并用 `description` 作为唯一用户消息。
4. 只转发父配置中的 `callbacks`、`tags`、`configurable`，再标记 `ls_agent_type="subagent"`。
5. 子 agent 阻塞式运行完成。
6. 若返回 `structured_response`，序列化为 JSON；否则取最后一条非空 `AIMessage` 文本作为工具结果。
7. 返回 `Command(update=...)`，把可合并 state 和一个 `ToolMessage` 回填父 agent。

同步 subagent 适合一次性、可隔离、需要完整完成后再汇总的任务。

## AsyncSubAgentMiddleware

异步 subagent 面向远程 Agent Protocol / LangGraph 服务，提供五个工具：

- `start_async_task`：启动远端 thread/run，并立即返回 `task_id`。
- `check_async_task`：查询远端 run 状态；成功时读取远端 thread values，返回最后一条消息内容。
- `update_async_task`：在同一 thread 上用 `multitask_strategy="interrupt"` 启动新 run，`task_id` 不变，`run_id` 更新。
- `cancel_async_task`：取消当前 run，并把本地任务状态置为 `cancelled`。
- `list_async_tasks`：按缓存状态过滤任务，再刷新 live status，返回摘要列表。

本地 state 只保存 `async_tasks` 映射，不把父 agent 完整 state 发给远端。`task_id` 使用远端 `thread_id`，这样跨轮次查询和更新都有稳定标识。

同步和异步 subagent 的核心区别：

| 维度 | 同步 `task` | 远程 async task |
| --- | --- | --- |
| 执行位置 | 本地 runnable | 远程 Agent Protocol server |
| 是否阻塞 | 阻塞到完成 | 启动后立即返回 |
| 工具数量 | 一个 `task` | 五个任务管理工具 |
| 状态传递 | 过滤后复制部分父 state | 只发送任务描述 |
| 结果获取 | 工具调用直接返回最终结果 | 后续通过 `check_async_task` 获取 |
| 后续更新 | 不支持，同步调用是一次性的 | 支持 update、cancel、list |

## SummarizationMiddleware

摘要模块在 LangChain 原生 `SummarizationMiddleware` 之上增加 Deep Agents 需要的恢复和兜底能力。

自动摘要流程：

1. 通过 `_summarization_event` 把完整 `state["messages"]` 重建成模型实际看到的 effective messages。
2. 如果配置了 `truncate_args_settings`，先截断旧 `write_file` / `edit_file` 工具调用里的大字符串参数。
3. 重新计数 tokens，判断是否达到摘要阈值。
4. 未达到阈值则正常调用模型；如果 provider 抛 `ContextOverflowError`，转入摘要 fallback。
5. 达到阈值或 overflow 时，计算 cutoff，把旧消息分为待摘要段和保留尾部。
6. overflow 情况下，额外调用 `_clip_overflow_tail` 裁剪保留尾部中连续的大 `ToolMessage`。
7. 待摘要消息先写入 `/conversation_history/{thread_id}.md`。
8. 调用摘要模型生成 summary。
9. 用 summary message 加保留尾部重试模型调用。
10. 返回 `ExtendedModelResponse`，写入新的 `_summarization_event`。

`_summarization_event` 的关键字段：

- `cutoff_index`：原始 state 中被摘要切点的绝对索引。
- `summary_message`：模型后续看到的摘要 `HumanMessage`。
- `file_path`：历史落盘路径，失败时为 `None`。

这种设计不删除原始 `state["messages"]`，而是在每次模型调用前重建 effective messages，有利于 replay、eval 和手动 compact 共享状态。

`SummarizationToolMiddleware` 额外注册 `compact_conversation` 工具。它不自动压缩，只在工具被调用时复用同一套摘要引擎和 `_summarization_event`。手动 compact 约在自动摘要阈值的 50% 后才允许，避免过早摘要造成信息损失。

## 大内容处理协作

大内容处理由三个模块协作：

- `filesystem.py`：主动处理大用户消息和普通大工具结果。
- `_message_eviction.py`：提供通用的工具结果落盘与预览构造。
- `_overflow_clip.py`：在 provider 真实溢出后，裁剪摘要保留尾部中的连续 `ToolMessage` 批次。

共同原则：

- 尽量先把完整内容写入 backend，再把模型上下文替换为路径加预览。
- 预览使用 head/tail，而不是只截开头，因为错误、总结和最终结果常出现在尾部。
- 多模态消息只替换文本块，尽量保留图片、音频等非文本块。
- 替换消息保留 `tool_call_id`、`name`、`id` 等身份字段，以便 LangGraph message reducer 能正确覆盖原消息。

## 维护注意事项

- 新 middleware 如果追加系统提示，应优先复用 `append_to_system_message`，避免覆盖其它 middleware 的 prompt 片段。
- 新工具如果可能产生大结果，应明确是否加入 `TOOLS_EXCLUDED_FROM_EVICTION`，并说明恢复路径。
- 修改 subagent 状态传递时，要同时考虑父状态泄漏到子 agent 和子私有状态回流父 agent 两个方向。
- 修改摘要 cutoff 逻辑时，要重点验证链式摘要场景；effective message list 的第 0 条摘要消息不对应真实 state message。
- 任何 profile 级工具排除应通过 `_ToolExclusionMiddleware` 在最终工具集上处理，避免遗漏 middleware 注入工具。
