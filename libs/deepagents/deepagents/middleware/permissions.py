"""Backward-compatible re-export for filesystem permissions."""

# 旧版本从 permissions.py 导入该类型;这里保留转发,避免破坏用户代码.
# 不在本文件新增权限逻辑,确保真实实现只有 filesystem.py 一个来源.
from deepagents.middleware.filesystem import FilesystemPermission  # Re-exported for backwards compatibility.

# 只导出兼容符号;新的公开入口优先使用 deepagents.middleware 或 filesystem.py.
__all__ = ["FilesystemPermission"]
