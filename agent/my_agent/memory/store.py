"""
短期记忆存储。
提供最小化的会话管理能力，为未来扩展长期记忆预留接口。
"""

from my_agent.core.context import ConversationStore, trim_messages

# 导出 ConversationStore 和 trim_messages，方便其他地方引用
__all__ = ["ConversationStore", "trim_messages"]
