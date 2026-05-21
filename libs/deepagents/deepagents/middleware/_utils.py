"""Utility functions for middleware."""

from langchain_core.messages import ContentBlock, SystemMessage


def append_to_system_message(
    system_message: SystemMessage | None,
    text: str,
) -> SystemMessage:
    """Append text to a system message.

    Args:
        system_message: Existing system message or None.
        text: Text to add to the system message.

    Returns:
        New SystemMessage with the text appended.
    """
    # 使用 content_blocks 而不是 content 字符串,兼容已有结构化/多模态系统消息.
    # 保留原系统消息的 content blocks,再追加新的文本块,避免覆盖上游中间件注入的内容.
    new_content: list[ContentBlock] = list(system_message.content_blocks) if system_message else []
    if new_content:
        # 多个中间件连续追加系统提示时,用空行分隔,保持模型看到的段落边界清晰.
        text = f"\n\n{text}"
    new_content.append({"type": "text", "text": text})
    # 始终返回新对象,避免原地修改影响其它 middleware 持有的 request/system message.
    return SystemMessage(content_blocks=new_content)
