"""
FastAPI 路由。
提供聊天、确认、会话管理等 API 端点。
"""

import json
import uuid
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from my_agent.server.schemas import ChatRequest, ConfirmRequest, NewSessionRequest, ModeRequest
from my_agent.core.loop import agent_process, resolve_confirmation
from my_agent.memory.store import ConversationStore
from my_agent.personality.config import WELCOME_MESSAGE

router = APIRouter()
store = ConversationStore()

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

            if event_type == "token":
                assistant_content += event["content"]
                yield f"event: token\ndata: {json.dumps({'content': event['content']})}\n\n"

            elif event_type == "tool_call":
                # 追加到持久化
                store.append_message(session_id, {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": event["id"],
                        "type": "function",
                        "function": {
                            "name": event["name"],
                            "arguments": json.dumps(event["arguments"], ensure_ascii=False),
                        },
                    }],
                    "content": None,
                })
                yield f"event: tool_call\ndata: {json.dumps({'id': event['id'], 'name': event['name'], 'arguments': event['arguments']})}\n\n"

            elif event_type == "tool_result":
                # 追加到持久化
                store.append_tool_result(
                    session_id,
                    event["id"],
                    event["name"],
                    event["content"],
                )
                max_tool_runs += 1
                yield f"event: tool_result\ndata: {json.dumps({'id': event['id'], 'name': event['name'], 'content': event['content'][:500]})}\n\n"

            elif event_type == "confirm_required":
                yield f"event: confirm_required\ndata: {json.dumps({'id': event['id'], 'name': event['name'], 'arguments': event['arguments']})}\n\n"

            elif event_type == "tool_skipped":
                reason = event.get("reason", "用户拒绝")
                yield f"event: tool_skipped\ndata: {json.dumps({'id': event['id'], 'name': event['name'], 'reason': reason})}\n\n"

            elif event_type == "done":
                # 保存最终的 assistant 回复
                if assistant_content:
                    store.append_message(session_id, {
                        "role": "assistant",
                        "content": assistant_content,
                    })
                yield f"event: done\ndata: {json.dumps({})}\n\n"

            elif event_type == "error":
                yield f"event: error\ndata: {json.dumps({'message': event['message']})}\n\n"

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
