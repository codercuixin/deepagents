# `_utils.py` 分析

## 职责定位

`_utils.py` 当前只提供 `append_to_system_message()`。它是多个 middleware 追加系统提示的共享入口，避免后一个 middleware 覆盖前一个 middleware 注入的 prompt。

## 运行流程

1. 接收已有 `SystemMessage | None` 和待追加文本。
2. 如果已有系统消息，复制它的 `content_blocks`。
3. 如果已有内容，在新文本前加空行，保持段落边界。
4. 追加新的 text content block。
5. 返回新的 `SystemMessage`。

## 关键设计

- 使用 `content_blocks` 而不是字符串拼接，兼容结构化和多模态系统消息。
- 返回新对象而不是原地修改，避免影响其它 middleware 或 request 持有者。
- 空行分隔让模型更容易识别不同 middleware 的提示片段。

## 维护注意

- 新 middleware 需要追加系统提示时优先复用该 helper。
- 如果未来系统消息支持更多 block 类型，追加逻辑应继续只新增文本块，不重写已有 block。
