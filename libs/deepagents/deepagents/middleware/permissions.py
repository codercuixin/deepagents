"""Backward-compatible re-export for filesystem permissions."""

# 旧版本从 permissions.py 导入该类型;这里保留转发,避免破坏用户代码.
from deepagents.middleware.filesystem import FilesystemPermission  # Re-exported for backwards compatibility.

__all__ = ["FilesystemPermission"]
