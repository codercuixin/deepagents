# `filesystem.py` 分析

## 职责定位

`FilesystemMiddleware` 是 Deep Agents 文件能力的核心入口。它注册 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep` 和可选的 `execute`，并负责权限检查、系统提示注入、大用户消息落盘和大工具结果落盘。

## 运行流程

1. 初始化 backend、权限规则、工具描述、执行超时和 artifact 前缀。
2. 构造所有文件工具；`execute` 总是构造，但模型调用前会按 backend 能力动态隐藏。
3. 每个工具先做 POSIX 绝对路径校验，再做 middleware 层权限检查，最后调用 backend。
4. `wrap_model_call()` 追加 filesystem 系统提示，并根据当前 runtime backend 决定是否暴露 `execute`。
5. 如果最新 `HumanMessage` 太大，内容写入 `/conversation_history/<uuid>.md`，state 中原消息打 `lc_evicted_to` 标签，模型请求只使用路径和预览。
6. `wrap_tool_call()` 拦截普通大工具结果，写入 `/large_tool_results/<tool_call_id>`，再返回可恢复的 head/tail 预览。

## 权限模型

- `FilesystemPermission` 要求虚拟 POSIX 绝对路径，禁止 `..` 和 `~`。
- 规则按声明顺序 first-match，未命中默认 `allow`。
- 权限只约束 middleware 内置文件工具，不能约束 shell 命令内部自行读写。
- 如果 backend 支持执行且权限无法完全限定在 `CompositeBackend` route 内，初始化会拒绝这种组合。
- `grep` 会对每条 match 的真实路径二次过滤，避免入口 path 允许但结果泄露 deny 路径。

## 工具行为

- `read_file`：文本内容先按行分页，再按近似 token 预算截断；非文本内容返回媒体 content block。
- `write_file` / `edit_file`：先检查写权限，再调用 backend，并通过 state reducer 记录文件数据变化。
- `glob`：同步路径用单线程等待实现可控超时，异步路径用 `asyncio.wait_for`。
- `grep`：支持 files/content/count 三种输出模式，结果仍会截断。
- `execute`：执行前再次检查 backend 能力和 timeout，避免工具列表被手动保留后硬失败。

## 大内容处理

- 大用户消息和大工具结果都写入 `artifacts_root` 下，便于 `CompositeBackend` 分流持久化。
- `read_file`、`ls`、`glob`、`grep` 等内置工具有自己的分页/截断策略，不走通用大结果 eviction。
- 通用 eviction 只在 backend 写成功后替换模型可见消息；写失败则保留原消息，优先不丢内容。
- 替换消息保留稳定 id 和 `tool_call_id`，让 reducer 能覆盖旧消息。

## 维护注意

- 新增文件工具时要同时考虑路径校验、权限检查、sync/async 一致性、结果截断和错误文案。
- 新工具如果可能产生大结果，需要明确是否加入 `TOOLS_EXCLUDED_FROM_EVICTION`。
- 修改 `execute` 能力判断时要同时考虑 `SandboxBackendProtocol` 和 `CompositeBackend` 默认 backend。
- 任何历史落盘路径变更都要和 `SummarizationMiddleware` 的恢复路径保持一致。
