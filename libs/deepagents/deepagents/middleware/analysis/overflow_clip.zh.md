# `_overflow_clip.py` 分析

## 职责定位

`_overflow_clip.py` 是 `SummarizationMiddleware` 的 overflow 兜底模块。只有当 provider 已经抛出 `ContextOverflowError`，并且摘要后保留尾部仍可能太大时，它才裁剪尾部连续 `ToolMessage` 批次。

## 运行流程

1. `_find_tail_tool_message_batch()` 找到 `preserved_messages` 尾部连续的 `ToolMessage`。
2. 根据 summarization 的 `keep` 配置和模型窗口推导裁剪阈值。
3. 如果尾部工具结果总 token 不够大，直接返回原消息。
4. `_build_tool_call_index()` 从历史 `AIMessage.tool_calls` 建索引。
5. 对 `read_file` 结果，反查原始 `file_path`，只截取头部并提示用 offset/limit 恢复。
6. 对其它工具结果，复用 `_message_eviction` 写入 `/large_tool_results/<tool_call_id>`。
7. 给替换消息补稳定 id，返回修改后的 preserved messages 和需要写回 state 的 replacement tail。

## 关键设计

- 只裁剪尾部连续 `ToolMessage`，避免破坏 `AIMessage.tool_calls` 与 tool response 的配对关系。
- `read_file` 的原始内容本来就在 backend 原路径，不需要额外复制到 large tool results。
- 小尾部不处理，避免为轻量消息制造额外文件和 state 更新。
- async 版本并发 offload 多个尾部消息，但失败项仍保留原消息。

## 返回值

- 第一个值：模型重试时使用的 preserved messages。
- 第二个值：需要通过 state update 写回的 replacement `ToolMessage` 列表。

## 维护注意

- `keep=("fraction", x)` 依赖模型 profile；拿不到窗口大小时只能使用保守固定阈值。
- 新增特殊工具恢复策略时，需要能从 `AIMessage.tool_calls` 可靠反查原始参数。
- 替换消息 id 是 reducer 覆盖旧消息的关键，不要移除。
