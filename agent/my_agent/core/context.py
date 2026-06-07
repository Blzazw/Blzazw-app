"""
对话上下文管理。
负责维护消息历史、控制 token 长度、管理会话持久化。
"""

import json
import os
import time
from pathlib import Path

# 假设每 token 约 4 个中文字符
MAX_TOKENS = 32000
RESERVE_TOKENS = 4000  # 为回复预留的 token
MAX_CONTEXT_TOKENS = MAX_TOKENS - RESERVE_TOKENS


def estimate_tokens(text: str) -> int:
    """估算一段文本的 token 数（粗略）"""
    return len(text)


def trim_messages(messages: list[dict], max_tokens: int = MAX_CONTEXT_TOKENS) -> list[dict]:
    """
    如果消息太长，从最早的对话（保留 system prompt）开始裁剪。
    保留 system prompt，然后尽可能保留最新的对话。
    """
    if not messages:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    history = [m for m in messages if m.get("role") != "system"]

    # 估算 system prompt 长度
    system_tokens = sum(estimate_tokens(json.dumps(m, ensure_ascii=False)) for m in system_msgs)
    available = max_tokens - system_tokens

    # 从最新的消息往前保留
    kept = []
    used = 0
    for m in reversed(history):
        tokens = estimate_tokens(json.dumps(m, ensure_ascii=False))
        if used + tokens > available:
            break
        kept.insert(0, m)
        used += tokens

    return system_msgs + kept


class ConversationStore:
    """
    简单的会话存储。
    每个会话是一个 .jsonl 文件，保存在 sessions/ 目录下。
    """

    def __init__(self, session_dir: str = "sessions"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.jsonl"

    def load_messages(self, session_id: str) -> list[dict]:
        """加载会话历史"""
        path = self._session_path(session_id)
        if not path.exists():
            return []
        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    def append_message(self, session_id: str, message: dict):
        """追加一条消息到会话文件"""
        path = self._session_path(session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")

    def append_tool_result(self, session_id: str, tool_call_id: str, name: str, content: str):
        """追加工具调用的结果消息"""
        msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": str(content),
        }
        self.append_message(session_id, msg)

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        sessions = []
        for f in sorted(self.session_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True):
            session_id = f.stem
            # 读取第一条消息作为标题
            first_msg = ""
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        msg = json.loads(line.strip())
                        if msg.get("role") == "user":
                            first_msg = msg.get("content", "")[:50]
                            break
            except Exception:
                pass
            sessions.append({
                "id": session_id,
                "preview": first_msg or "空会话",
                "mtime": os.path.getmtime(f),
            })
        return sessions

    def clear_session(self, session_id: str):
        """清空会话"""
        path = self._session_path(session_id)
        if path.exists():
            path.write_text("", encoding="utf-8")
