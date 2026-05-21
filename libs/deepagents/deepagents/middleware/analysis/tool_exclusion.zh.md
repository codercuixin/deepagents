# `_tool_exclusion.py` 分析

## 职责定位

`_ToolExclusionMiddleware` 在每次模型调用前过滤工具列表，用于 profile 级工具禁用。它不是权限系统，而是控制模型“看得见哪些工具”。

## 运行流程

1. 初始化时接收不可变的 excluded tool name 集合。
2. `wrap_model_call()` / `awrap_model_call()` 遍历 `request.tools`。
3. `_tool_name()` 同时兼容 `BaseTool` 和 dict schema。
4. 名称在 excluded 集合里的工具被移除。
5. 通过 `request.override(tools=filtered)` 生成新请求后继续调用 handler。

## 关键设计

- 该 middleware 应放在栈后段：先让其它 middleware 注入工具，再统一过滤。
- 能过滤 SDK middleware 注入工具，也能过滤调用方传入的普通工具。
- 取不到名称的工具会保留，因为没有安全的匹配依据。
- 空 excluded 集合直接透传，避免不必要的 request 重建。

## 维护注意

- 不要把它当成文件权限或安全隔离；真正的访问控制仍需要工具实现和 backend 兜底。
- 同步和异步路径必须保持一致，否则不同运行模式会暴露不同工具集。
