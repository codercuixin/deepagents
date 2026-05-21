# `summarization.py` 分析

## 职责定位

`summarization.py` 提供自动摘要 middleware 和手动 compact 工具。它在 LangChain 原生摘要能力上增加 Deep Agents 的恢复机制：旧消息摘要化，完整历史写入 backend，通过 `_summarization_event` 非破坏性地重建模型实际上下文。

## 自动摘要流程

1. `wrap_model_call()` 用 `_summarization_event` 将完整 state history 映射成 effective messages。
2. 若配置了 `truncate_args_settings`，先截断旧 `write_file` / `edit_file` 的大字符串参数。
3. 重新计数 tokens，判断是否达到 trigger。
4. 未触发时正常调用模型；如果 provider 抛 `ContextOverflowError`，转入摘要 fallback。
5. 触发摘要后计算 cutoff，把消息拆成 `messages_to_summarize` 和 `preserved_messages`。
6. overflow fallback 时，对 preserved tail 中连续的大 `ToolMessage` 执行 `_clip_overflow_tail()`。
7. 待摘要消息先 append 到 `/conversation_history/{thread_id}.md`。
8. 调用摘要模型生成 summary。
9. 构造携带历史文件路径的 summary `HumanMessage`。
10. 用 `summary + preserved_messages` 重试模型调用，并通过 `ExtendedModelResponse` 写入新的 `_summarization_event`。

## 手动 compact 流程

1. `SummarizationToolMiddleware` 注册 `compact_conversation`。
2. 工具调用时读取当前 state 和旧 `_summarization_event`。
3. `_is_eligible_for_compaction()` 要求达到自动摘要阈值约一半，避免过早压缩。
4. 计算 cutoff、生成 summary、offload 历史。
5. 返回 `Command` 更新 `_summarization_event`，并写入确认 `ToolMessage`。
6. 出错时返回失败 `ToolMessage`，不抛异常，避免 tool-call 配对破坏。

## `_summarization_event`

字段：

- `cutoff_index`：原始 `state["messages"]` 中被摘要切点的绝对索引。
- `summary_message`：后续模型调用看到的摘要消息。
- `file_path`：完整历史落盘路径；offload 失败时为 `None`。

Deep Agents 不直接删除 `state["messages"]`。每次模型调用前，middleware 用事件重建模型视图：`summary_message + messages[cutoff_index:]`。这样 replay、eval 和手动 compact 可以共享同一套状态语义。

## 关键设计

- 私有实现类 `_DeepAgentsSummarizationMiddleware` 通过 public alias `SummarizationMiddleware` 暴露，方便 `excluded_middleware={"SummarizationMiddleware"}`。
- `compute_summarization_defaults()` 有模型 profile 时使用比例阈值，没有 profile 时用保守固定值。
- 参数截断是低成本预处理，只处理常见大载荷来源：`write_file` 和 `edit_file`。
- offload 失败是非致命路径，摘要仍继续，但模型无法通过文件恢复完整历史。
- 异步路径并发执行 offload 和 summary，因为二者互不依赖。

## 边界条件

- malformed `_summarization_event` 会退回完整历史。
- cutoff 越界时保留 summary 作为最小可用上下文。
- 链式摘要需要把 effective cutoff 映射回 state cutoff，并处理 summary 占 effective index 0 的 off-by-one。
- provider 真实 overflow 后会启用 tail clipping，这是二级兜底，不是常规摘要路径。

## 维护注意

- 修改 cutoff 逻辑必须重点验证链式摘要。
- 修改历史路径规则时要和 `FilesystemMiddleware` 的 `artifacts_root` 保持一致。
- compact 工具任何失败都应转成 `ToolMessage`，不能让异常跳过工具响应。
- 新增大参数截断工具时，要确认截断不会改变工具调用语义。
