# `memory.py` 分析

## 职责定位

`MemoryMiddleware` 从配置的 `AGENTS.md` 路径加载长期上下文，存入私有 state，并在每次模型调用前追加到 system prompt。Memory 是始终注入的参考材料，不是按需读取的工作流。

## 运行流程

1. 初始化时校验 `system_prompt`，要求包含 `{agent_memory}`。
2. `before_agent()` / `abefore_agent()` 首次进入 agent 时下载所有 source。
3. 如果 `memory_contents` 已存在于 state，即使为空也跳过加载。
4. `file_not_found` 视为正常缺省配置，其它 backend 错误抛 `ValueError`。
5. `_format_agent_memory()` 按用户配置的 source 顺序拼接成功加载的内容。
6. `modify_request()` 只做 prompt 拼接，不做 I/O。
7. 可选 `add_cache_control` 会在运行时模型是 `ChatAnthropic` 时给最后一个 system block 加 prompt-cache breakpoint。

## 关键设计

- `memory_contents` 是 `PrivateStateAttr`，不会出现在最终 agent state 中。
- backend 可以是实例，也可以是 factory；factory 通过模拟 `ToolRuntime` 解析。
- `system_prompt=None` 只关闭 prompt 注入，不关闭 memory 加载。
- memory 内容来自磁盘，应被模型当作参考材料，而不是更高优先级指令。

## 与其它模块关系

- `append_to_system_message()` 确保 memory prompt 不覆盖其它 middleware 注入内容。
- `SubAgentMiddleware` 会过滤 `memory_contents`，避免父 agent memory 泄漏给子 agent。
- Anthropic cache breakpoint 与静态系统提示缓存配合，减少 memory 更新导致的缓存失效。

## 维护注意

- 新增 source 处理逻辑时要保持“只加载一次”的语义。
- 不要在 `modify_request()` 中做 backend I/O。
- 修改 trust 文案时要继续强调 memory 不能覆盖用户显式请求、安全策略和工具验证结果。
