# `__init__.py` 包级导出分析

## 职责定位

`__init__.py` 是 `deepagents.middleware` 的公开入口。它集中 re-export SDK 用户可以稳定依赖的 middleware 类型、配置类型和工厂函数，同时用模块 docstring 解释 middleware 与普通工具的能力边界。

## 运行流程

1. 导入各公开实现：filesystem、memory、skills、subagents、async subagents 和 summarization。
2. 维护 `__all__`，决定 `from deepagents.middleware import ...` 的稳定符号集合。
3. 内部 helper 和私有 middleware 不出现在 `__all__` 中，避免扩大兼容承诺。

## 关键设计

- 包级导出是 public API，新增符号要按公开接口处理。
- `FilesystemPermission` 在这里导出，因为权限配置是用户会直接构造的类型。
- `_ToolExclusionMiddleware`、`_message_eviction`、`_overflow_clip` 等保持私有，实现可以随内部需求调整。

## 维护注意

- 新增公开 middleware 时同步考虑 `__all__`、文档、测试和版本兼容。
- 不要为了方便测试或内部复用把私有 helper 加进 `__all__`。
- 删除或重命名导出符号会破坏用户导入路径，除非走明确的弃用流程。
