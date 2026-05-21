# `permissions.py` 分析

## 职责定位

`permissions.py` 是兼容层，只 re-export `FilesystemPermission`。真实权限实现位于 `filesystem.py`。

## 运行流程

1. 从 `deepagents.middleware.filesystem` 导入 `FilesystemPermission`。
2. 通过 `__all__` 暴露这个兼容符号。
3. 保证旧代码 `from deepagents.middleware.permissions import FilesystemPermission` 继续可用。

## 关键设计

- 稳定旧导入路径，避免小重构变成用户可见的 breaking change。
- 不在这里复制或新增权限逻辑，确保权限规则只有一个实现来源。

## 维护注意

- 不要在本文件扩展新的权限 API。
- 若未来删除该兼容层，需要先有明确弃用期和迁移说明。
