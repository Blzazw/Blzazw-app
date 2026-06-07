"""
对话上下文管理。
负责维护消息历史、控制 token 长度、管理会话持久化。
"""

import json
import os
import time
from pathlib import Path

# 更准确的 token 估算（中英文混合）
MAX_TOKENS = 64000  # 扩大上下文预算
RESERVE_TOKENS = 8000
MAX_CONTEXT_TOKENS = MAX_TOKENS - RESERVE_TOKENS


def estimate_tokens(text: str) -> int:
    """估算 token 数"""
    if not text:
        return 0
    return max(1, len(text) // 2)


# 最大保留消息数
MAX_MESSAGES = 200


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


class MemoryStore:
    """长期记忆存储。存储用户的关键信息，跨对话持久化。"""
    def __init__(self, store_dir: str | None = None):
        import os
        if store_dir is None:
            store_dir = os.getenv("BLZAZW_SESSIONS_DIR", "sessions")
        self.memory_file = Path(store_dir) / "memory.json"
        self._memories: list[dict] = []
        self._load()

    def _load(self):
        if self.memory_file.exists():
            try:
                self._memories = json.loads(self.memory_file.read_text(encoding="utf-8"))
            except Exception:
                self._memories = []

    def save(self):
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory_file.write_text(json.dumps(self._memories, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_memory(self, key: str, value: str):
        """添加或更新一条记忆"""
        for m in self._memories:
            if m["key"] == key:
                m["value"] = value
                m["time"] = str(__import__("datetime").datetime.now())
                self.save()
                return
        self._memories.append({"key": key, "value": value, "time": str(__import__("datetime").datetime.now())})
        self.save()

    def get_all(self) -> str:
        """获取所有记忆的文本描述"""
        if not self._memories:
            return "暂无已保存的用户信息。"
        lines = ["关于用户，我了解到以下信息："]
        for m in self._memories:
            lines.append(f"- {m['key']}: {m['value']}")
        return "\n".join(lines)

    def to_prompt(self) -> str:
        """生成记忆提示文本，注入到系统提示词中"""
        if not self._memories:
            return ""
        parts = ["[长期记忆 — 以下是你之前了解到关于用户的信息：]"]
        for m in self._memories:
            parts.append(f"{m['key']}: {m['value']}")
        return "\n".join(parts)


class ConversationStore:
    """
    简单的会话存储。
    每个会话是一个 .jsonl 文件，保存在 sessions/ 目录下。
    """

    def __init__(self, session_dir: str | None = None):
        import os
        if session_dir is None:
            # 优先使用环境变量（Electron 传入的用户数据目录）
            session_dir = os.getenv("BLZAZW_SESSIONS_DIR", "sessions")
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

    def get_summary(self, session_id: str) -> str:
        """获取或生成会话摘要"""
        # 摘要存储在同名的 .summary 文件中
        summary_path = self.session_dir / f"{session_id}.summary"
        if summary_path.exists():
            return summary_path.read_text(encoding="utf-8").strip()
        return ""

    def save_summary(self, session_id: str, summary: str):
        """保存会话摘要"""
        if summary:
            path = self.session_dir / f"{session_id}.summary"
            path.write_text(summary, encoding="utf-8")

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
