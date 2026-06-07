"""
Agent 核心调度循环。
这是整个 agent 的大脑——决定什么时候调用 LLM、什么时候执行工具、怎么处理结果。
"""

import json
import asyncio
from typing import AsyncGenerator

from my_agent.core import llm
from my_agent.tools.registry import registry, SAFE, CAUTION, DANGEROUS
from my_agent.personality.config import SYSTEM_PROMPT

# 安全模式
MODE_SAFE = "safe"        # 客卿：危险操作需确认
MODE_TRUSTED = "trusted"  # 家臣：全部自动执行但显示操作
MODE_SOVEREIGN = "sovereign"  # 君主：全部静默执行

# 需要确认的工具等级
CONFIRM_LEVELS = {
    MODE_SAFE: [CAUTION, DANGEROUS],
    MODE_TRUSTED: [],
    MODE_SOVEREIGN: [],
}

# 确认请求队列
# { session_id: { tool_call_id: asyncio.Event() } }
_pending_confirmations: dict[str, dict[str, asyncio.Event]] = {}
_confirm_results: dict[str, dict[str, bool]] = {}


def get_pending_confirmations(session_id: str) -> dict[str, asyncio.Event]:
    """获取指定会话的待确认事件字典"""
    if session_id not in _pending_confirmations:
        _pending_confirmations[session_id] = {}
    return _pending_confirmations[session_id]


def resolve_confirmation(session_id: str, tool_call_id: str, approved: bool):
    """处理用户的确认响应"""
    events = get_pending_confirmations(session_id)
    event = events.get(tool_call_id)
    if event:
        if session_id not in _confirm_results:
            _confirm_results[session_id] = {}
        _confirm_results[session_id][tool_call_id] = approved
        event.set()


async def agent_process(
    session_id: str,
    messages: list[dict],
    mode: str = MODE_SAFE,
) -> AsyncGenerator[dict, None]:
    """
    Agent 处理循环。

    接收消息历史，依次执行：
    1. 调用 LLM → 解析响应
    2. 如果有工具调用 → 检查权限 → 执行工具 → 回到 1
    3. 如果是文本回复 → 逐 token 产出

    Yields:
        事件字典，包含 type 字段：
        - token: 文本 token
        - tool_call: agent 调用工具
        - tool_result: 工具执行结果
        - confirm_required: 需要用户确认
        - tool_skipped: 用户跳过了此工具
        - done: 处理完成
        - error: 发生错误
    """
    try:
        worker_messages = _prepare_messages(messages, mode=mode, session_id=session_id)
    except Exception as e:
        yield {"type": "error", "message": f"准备消息失败: {e}"}
        return

    # 获取工具定义
    tools = registry.to_openai_tools()
    confirm_levels = CONFIRM_LEVELS.get(mode, [])

    # 主循环：最多 10 轮工具调用，防止无限循环
    max_rounds = 10
    for _round in range(max_rounds):
        try:
            response = await llm.chat(worker_messages, tools=tools)
        except Exception as e:
            yield {"type": "error", "message": f"LLM 调用失败: {e}"}
            return

        if not response.has_tool_calls():
            # ── 纯文本回复 ──
            content = response.content or ""
            if content:
                # 流式逐 token 产出
                yield {"type": "token", "content": content}
            yield {"type": "done"}
            return

        # ── 工具调用 ──
        for tc in response.tool_calls:
            # 通知前端：agent 想调用工具
            yield {
                "type": "tool_call",
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.arguments,
            }

            # 检查安全等级
            tool_def = registry.get(tc.name)
            need_confirm = tool_def and tool_def.security in confirm_levels

            if need_confirm:
                # ── 需要用户确认 ──
                events = get_pending_confirmations(session_id)
                confirm_event = asyncio.Event()
                events[tc.id] = confirm_event

                yield {
                    "type": "confirm_required",
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }

                # 等待用户确认（超时 120 秒）
                try:
                    await asyncio.wait_for(confirm_event.wait(), timeout=120)
                except asyncio.TimeoutError:
                    yield {"type": "tool_skipped", "id": tc.id, "name": tc.name, "reason": "超时"}
                    # 给 LLM 一个提示
                    worker_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": "[用户未响应确认请求，此工具调用已跳过]",
                    })
                    continue

                # 检查用户是否批准
                approved = _confirm_results.get(session_id, {}).get(tc.id, False)
                # 清理
                events.pop(tc.id, None)
                if session_id in _confirm_results:
                    _confirm_results[session_id].pop(tc.id, None)

                if not approved:
                    yield {"type": "tool_skipped", "id": tc.id, "name": tc.name, "reason": "用户拒绝"}
                    worker_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": "[用户拒绝了此工具调用]",
                    })
                    continue

            # ── 执行工具 ──
            result = await registry.execute(tc.name, tc.arguments)

            yield {
                "type": "tool_result",
                "id": tc.id,
                "name": tc.name,
                "content": result,
            }

            # 将工具调用和结果追加到消息历史
            worker_messages.append({
                "role": "assistant",
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }],
            })
            worker_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "content": result,
            })

    # 超过最大轮数
    yield {
        "type": "token",
        "content": "[已达到最大工具调用轮数，我将基于已有信息回复。可能需要更多信息，你可以继续追问。]",
    }
    yield {"type": "done"}


def _prepare_messages(messages: list[dict], mode: str = MODE_SAFE, session_id: str | None = None) -> list[dict]:
    """准备消息：注入 system prompt、当前安全模式，并做截断"""
    mode_hints = {
        MODE_SAFE: (
            "当前安全模式：【客卿】。"
            "写文件、执行代码和执行命令需要先获得用户确认。"
            "调用这些工具时会弹窗，用户批准后才能执行。"
        ),
        MODE_TRUSTED: (
            "当前安全模式：【家臣】。"
            "所有工具可以自动执行，不需要等待用户确认。"
            "但你的每一步操作用户都能看到。"
        ),
        MODE_SOVEREIGN: (
            "当前安全模式：【君主】。"
            "你拥有完全的操作权限，所有工具都可以直接调用，无需等待任何确认。"
            "用户完全信赖你，请放心使用你的全部能力。"
        ),
    }
    mode_hint = mode_hints.get(mode, mode_hints[MODE_SAFE])

    # 加载长期记忆
    from my_agent.core.context import MemoryStore
    import os
    _mem_dir = os.getenv("BLZAZW_SESSIONS_DIR", "sessions")
    _ms = MemoryStore(_mem_dir)
    memory_text = _ms.to_prompt()

    system_content = SYSTEM_PROMPT + "\n\n" + mode_hint
    if memory_text:
        system_content += "\n\n" + memory_text
    # 注入对话摘要
    from my_agent.core.context import ConversationStore as _CS
    _summary = _CS().get_summary(session_id)
    if _summary:
        system_content += f"\n\n[对话摘要 — 本次对话之前的历史概要：]\n{_summary}"

    result = [{"role": "system", "content": system_content}]

    # 过滤掉已存在的 system 消息
    user_msgs = [m for m in messages if m.get("role") != "system"]

    from my_agent.core.context import MAX_MESSAGES, estimate_tokens

    # 用 token 预算截断而非硬性条数限制
    total_tokens = sum(estimate_tokens(json.dumps(m, ensure_ascii=False)) for m in user_msgs)
    if total_tokens > 40000 or len(user_msgs) > MAX_MESSAGES:
        kept = []
        used = 0
        for m in reversed(user_msgs):
            t = estimate_tokens(json.dumps(m, ensure_ascii=False))
            if used + t > 40000 or len(kept) >= MAX_MESSAGES:
                break
            kept.insert(0, m)
            used += t
        user_msgs = kept

    result.extend(user_msgs)
    return result
