"""
FastAPI 路由。
提供聊天、确认、会话管理等 API 端点。
"""

import json
import uuid
import time
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from my_agent.server.schemas import ChatRequest, ConfirmRequest, NewSessionRequest, ModeRequest
from my_agent.core.loop import agent_process, resolve_confirmation
from my_agent.memory.store import ConversationStore
from my_agent.core.context import MemoryStore
from my_agent.personality.config import WELCOME_MESSAGE

router = APIRouter()
store = ConversationStore()
memory_store = MemoryStore()


async def _auto_summarize(session_id: str, conv_store: ConversationStore):
    """自动生成对话摘要（后台运行，不阻塞）"""
    try:
        messages = conv_store.load_messages(session_id)
        texts = []
        for m in messages:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                role = "用户" if m["role"] == "user" else "助手"
                texts.append(f"{role}: {m['content'][:200]}")
        if len(texts) >= 6:
            summary = "\n".join(texts[-30:])
            conv_store.save_summary(session_id, summary)
    except Exception:
        pass

# 会话安全模式缓存
_session_modes: dict[str, str] = {}


def _get_or_create_session(session_id: str) -> str:
    """获取或创建会话，返回 session_id"""
    if session_id not in _session_modes:
        _session_modes[session_id] = "safe"
    return session_id


@router.get("/api/health")
async def health_check():
    """健康检查"""
    import os
    has_key = bool(os.getenv("DEEPSEEK_API_KEY", "")) and os.getenv("DEEPSEEK_API_KEY", "") != "sk-your-api-key-here"
    return {"status": "ok", "agent": "Blzazw", "api_key_configured": has_key}


@router.post("/api/chat")
async def chat(request: ChatRequest):
    """
    发送消息并获取流式响应（SSE 格式）。
    前端使用 EventSource 或 fetch + ReadableStream 读取。
    """
    session_id = _get_or_create_session(request.session_id)
    mode = request.mode or _session_modes.get(session_id, "safe")
    _session_modes[session_id] = mode

    # 加载历史消息
    messages = store.load_messages(session_id)

    # 追加用户消息
    user_message = {"role": "user", "content": request.message}
    store.append_message(session_id, user_message)
    messages.append(user_message)

    async def event_stream():
        # 先发送 session_id
        yield f"event: session\ndata: {json.dumps({'session_id': session_id, 'mode': mode})}\n\n"

        max_tool_runs = 0
        assistant_content = ""

        async for event in agent_process(session_id, messages, mode=mode):
            event_type = event["type"]
            sse_data = None

            if event_type == "token":
                assistant_content += event["content"]
                sse_data = ("token", {"content": event["content"]})

            elif event_type == "tool_call":
                store.append_message(session_id, {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": event["id"],
                        "type": "function",
                        "function": {"name": event["name"], "arguments": json.dumps(event["arguments"], ensure_ascii=False)},
                    }],
                    "content": None,
                })
                sse_data = ("tool_call", {"id": event["id"], "name": event["name"], "arguments": event["arguments"]})

            elif event_type == "tool_result":
                store.append_tool_result(session_id, event["id"], event["name"], event["content"])
                max_tool_runs += 1
                sse_data = ("tool_result", {"id": event["id"], "name": event["name"], "content": event["content"][:500]})

            elif event_type == "confirm_required":
                sse_data = ("confirm_required", {"id": event["id"], "name": event["name"], "arguments": event["arguments"]})

            elif event_type == "tool_skipped":
                sse_data = ("tool_skipped", {"id": event["id"], "name": event["name"], "reason": event.get("reason", "用户拒绝")})

            elif event_type == "done":
                if assistant_content:
                    store.append_message(session_id, {"role": "assistant", "content": assistant_content})
                    # 异步触发摘要（不阻塞主流程）
                    try:
                        asyncio.ensure_future(_auto_summarize(session_id, store))
                    except Exception:
                        pass
                sse_data = ("done", {})

            elif event_type == "error":
                sse_data = ("error", {"message": event["message"]})

            if sse_data:
                evt, d = sse_data
                # 每个 SSE 事件后强制通过 flush 推送到前端
                line = f"event: {evt}\ndata: {json.dumps(d)}\n\n"
                yield line
                # 空 yield 给 uvicorn 一个切回事件循环的机会，避免缓冲
                await asyncio.sleep(0)

        yield f"event: complete\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/confirm")
async def confirm(request: ConfirmRequest):
    """
    用户对工具调用的确认/拒绝。
    """
    resolve_confirmation(request.session_id, request.tool_call_id, request.approved)
    return {"status": "ok"}


@router.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    sessions = store.list_sessions()
    return {"sessions": sessions}


@router.post("/api/sessions/new")
async def new_session(request: NewSessionRequest):
    """创建新会话"""
    session_id = request.session_id or str(uuid.uuid4())[:8]
    _session_modes[session_id] = "safe"
    return {"session_id": session_id, "welcome": WELCOME_MESSAGE}


@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取指定会话的消息历史"""
    messages = store.load_messages(session_id)
    return {"messages": messages}


@router.post("/api/sessions/{session_id}/clear")
async def clear_session(session_id: str):
    """清空会话"""
    store.clear_session(session_id)
    return {"status": "ok"}


@router.post("/api/sessions/{session_id}/summarize")
async def summarize_session(session_id: str):
    """生成对话摘要（异步后台执行）"""
    messages = store.load_messages(session_id)
    # 只取用户和助手的文字消息，忽略工具调用
    texts = []
    for m in messages:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            role = "用户" if m["role"] == "user" else "助手"
            texts.append(f"{role}: {m['content'][:200]}")
    if len(texts) < 4:
        return {"status": "skipped", "reason": "消息太少，无需摘要"}
    summary_text = "\n".join(texts[-20:])  # 只摘要最近 20 轮
    store.save_summary(session_id, summary_text)
    return {"status": "ok", "summarized": min(len(texts), 20)}


@router.post("/api/sessions/{session_id}/messages")
async def save_message(session_id: str, request: dict):
    """手动保存一条消息到会话（用于中断时保存不完整的回复）"""
    role = request.get("role", "assistant")
    content = request.get("content", "")
    if content:
        store.append_message(session_id, {"role": role, "content": content})
    return {"status": "ok"}


@router.post("/api/mode")
async def set_mode(request: ModeRequest):
    """切换安全模式"""
    if request.mode not in ("safe", "trusted", "sovereign"):
        raise HTTPException(400, "无效的模式，可选: safe, trusted, sovereign")
    
    old_mode = _session_modes.get(request.session_id, "safe")
    _session_modes[request.session_id] = request.mode
    
    # 如果模式变了，往对话里注入一条系统消息，让 agent 知道权限变化
    if old_mode != request.mode:
        mode_hints = {
            "safe": "用户将你的安全模式设为【客卿】。写文件、执行代码和命令时需要先获得用户确认。",
            "trusted": "用户将你的安全模式设为【家臣】。所有工具自动执行，但操作过程用户可见。",
            "sovereign": "用户将你的安全模式设为【君主】。你拥有完全的操作权限，所有工具可以直接调用，无需等待确认。请放心使用你的全部能力。",
        }
        hint = mode_hints.get(request.mode, "")
        if hint:
            store.append_message(request.session_id, {
                "role": "system",
                "content": f"[安全模式变更] {hint}",
            })
    
    return {"session_id": request.session_id, "mode": request.mode}


@router.get("/api/modes")
async def get_modes():
    """返回所有可用的安全模式"""
    return {
        "modes": [
            {"id": "safe", "name": "🛡️ 客卿", "description": "写文件、执行代码和命令需弹窗确认"},
            {"id": "trusted", "name": "⚡ 家臣", "description": "所有工具自动执行，操作过程可见"},
            {"id": "sovereign", "name": "👑 君主", "description": "完全信赖，无需确认，静默执行"},
        ],
        "default": "safe",
    }


@router.get("/api/diagnose")
async def diagnose():
    """获取诊断信息（不含敏感数据）"""
    import os
    import sys
    from datetime import datetime
    has_key = bool(os.getenv("DEEPSEEK_API_KEY", "")) and os.getenv("DEEPSEEK_API_KEY", "") != "sk-your-api-key-here"
    return {
        "timestamp": datetime.now().isoformat(),
        "platform": sys.platform,
        "python_version": sys.version,
        "api_key_configured": has_key,
        "model": os.getenv("DEEPSEEK_MODEL", "not set"),
        "env_vars": [k for k in sorted(os.environ.keys()) if not k.startswith("DEEPSEEK")][:20],
    }


@router.get("/api/memory")
async def get_memory():
    """获取长期记忆"""
    return {"memories": memory_store.to_prompt()}


@router.post("/api/memory")
async def save_memory(request: dict):
    """保存一条长期记忆"""
    key = request.get("key", "")
    value = request.get("value", "")
    if key and value:
        memory_store.add_memory(key, value)
    return {"status": "ok"}


@router.get("/api/models")
async def get_models():
    """获取可用的模型列表"""
    import os
    current = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    return {
        "models": [
            {"id": "deepseek-v4-flash", "name": "V4 Flash", "desc": "高速低成本，适合日常对话"},
            {"id": "deepseek-v4-pro", "name": "V4 Pro", "desc": "强推理能力，适合复杂任务"},
        ],
        "current": current,
    }


@router.post("/api/model")
async def set_model(request: dict):
    """切换模型"""
    import os
    model = request.get("model", "")
    if model not in ("deepseek-v4-flash", "deepseek-v4-pro"):
        raise HTTPException(400, "无效的模型")
    os.environ["DEEPSEEK_MODEL"] = model
    return {"model": model}
