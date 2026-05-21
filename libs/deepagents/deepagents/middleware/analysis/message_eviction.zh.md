# `_message_eviction.py` 分析

## 职责定位

`_message_eviction.py` 是共享 helper，不直接注册 middleware。它负责把超大的 `ToolMessage` 文本写入 backend，并构造一个带恢复路径和 head/tail 预览的替代消息。

## 运行流程

1. `_extract_text_from_message()` 只提取 text content block，忽略图片、音频等非文本块。
2. `_create_content_preview()` 生成带行号的头尾预览，中间用 truncation marker 表示省略。
3. `_offload_tool_message_content()` 用 sanitized `tool_call_id` 生成落盘路径。
4. 先写 backend；写入失败返回 `None`。
5. 写入成功后构造 `TOO_LARGE_TOOL_MSG`。
6. `_build_evicted_tool_message()` 保留原 `ToolMessage` 的身份字段，替换 content。

## 关键设计

- 预览同时保留头部和尾部，因为错误、总结和最终结果常出现在尾部。
- 短内容也格式化行号，保持模型看到的预览形态一致。
- 多模态消息只替换文本 block，非文本 block 继续保留。
- 写入失败不丢原消息，由调用方决定是否继续使用完整内容。

## 调用方契约

- 返回 `ToolMessage` 表示已成功落盘并可替换。
- 返回 `None` 表示落盘失败，调用方必须保留原消息。
- sync/async 版本语义一致，差异只在 backend I/O。

## 维护注意

- 落盘路径命名依赖 `sanitize_tool_call_id()`，不要直接使用未经清洗的 tool call id。
- 替换消息必须保留 `tool_call_id`、`name`、`id`、`artifact` 和 `status` 等字段。
- 提示文案要持续告诉模型用 `read_file` 分页恢复，不要鼓励一次性读回全部内容。
