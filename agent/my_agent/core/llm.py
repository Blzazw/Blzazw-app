"""
DeepSeek LLM 客户端。
封装了与 DeepSeek API 的通信，支持流式输出和函数调用。
"""

import json
import os
from typing import AsyncGenerator, Callable
from openai import AsyncOpenAI


def _get_client() -> AsyncOpenAI:
    """创建并返回 DeepSeek API 客户端"""
    import sys
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key or api_key == "sk-your-api-key-here":
        print("[Blzazw] 未配置 API Key", flush=True)
        raise ValueError("未配置 DeepSeek API Key")

    print(f"[Blzazw] API Key 已配置: {api_key[:5]}...{api_key[-4:]}", flush=True)
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _get_model() -> str:
    """获取模型名称"""
    return os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")


# ──────────────────────────── 类型定义 ────────────────────────────

class ToolCall:
    """LLM 返回的工具调用"""
    def __init__(self, id: str, name: str, arguments: dict):
        self.id = id
        self.name = name
        self.arguments = arguments

    def __repr__(self):
        return f"ToolCall({self.name}, args={self.arguments})"


class ChatResponse:
    """LLM 的一次完整响应"""
    def __init__(self, content: str | None, tool_calls: list[ToolCall] | None):
        self.content = content
        self.tool_calls = tool_calls

    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    def __repr__(self):
        if self.has_tool_calls():
            return f"ChatResponse(tool_calls={self.tool_calls})"
        return f"ChatResponse(content='{self.content[:50] if self.content else ''}...')"


# ──────────────────────────── 核心接口 ────────────────────────────

async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> ChatResponse:
    """
    使用 urllib 直接调用 DeepSeek API（兼容性最好的方式）
    """
    import json
    import os
    import urllib.request

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    model = _get_model()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    body = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools

    data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    print(f"[Blzazw] LLM call: model={model}, key_set={'yes' if api_key and len(api_key) > 8 else 'no'}, tools={len(tools) if tools else 0}", flush=True)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # urllib 是同步的，用线程池避免阻塞事件循环
            import asyncio
            resp_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=60).read()
            )
            data = json.loads(resp_data)
            result = _parse_httpx_response(data)
            print(f"[Blzazw] LLM response: has_tool_calls={result.has_tool_calls()}, content_len={len(result.content or '')}", flush=True)
            return result
        except Exception as e:
            print(f"[Blzazw] LLM error (attempt {attempt+1}/{max_attempts}): {type(e).__name__}: {e}", flush=True)
            if attempt < max_attempts - 1:
                await asyncio.sleep(2)
                continue
            raise


def _parse_httpx_response(data: dict) -> ChatResponse:
    """解析 httpx 响应的 JSON 为 ChatResponse"""
    choice = data["choices"][0]
    msg = choice.get("message", {})
    content = msg.get("content")

    tool_calls = None
    if msg.get("tool_calls"):
        tool_calls = []
        for tc in msg["tool_calls"]:
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, TypeError, KeyError):
                args = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=tc.get("function", {}).get("name", ""),
                arguments=args,
            ))

    return ChatResponse(content=content, tool_calls=tool_calls)


async def chat_stream(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    流式调用 LLM。
    逐个 token 产出文本内容。
    如果 LLM 返回了工具调用，会在最后通过特殊标记产出。
    """
    client = _get_client()
    model = _get_model()

    kwargs = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools

    stream = await client.chat.completions.create(**kwargs)

    tool_call_deltas: dict[int, dict] = {}
    reasoning_buffer = ""
    content_buffer = ""

    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        # 收集 reasoning_content（DeepSeek 的思维链）
        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            reasoning_buffer += delta.reasoning_content

        # 收集常规内容
        if delta.content:
            content_buffer += delta.content
            yield f"0:{json.dumps(delta.content)}\n"

        # 收集工具调用
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_call_deltas:
                    tool_call_deltas[idx] = {
                        "id": "",
                        "function": {"name": "", "arguments": ""},
                    }
                if tc_delta.id:
                    tool_call_deltas[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        tool_call_deltas[idx]["function"]["name"] += tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_call_deltas[idx]["function"]["arguments"] += tc_delta.function.arguments

    # 如果推测了推理内容但又没有产生最终内容，把它交出来
    if reasoning_buffer and not content_buffer and not tool_call_deltas:
        yield f"0:{json.dumps(f'[思考] {reasoning_buffer}')}\n"

    # 如果有工具调用，在流末尾一次性产出
    if tool_call_deltas:
        tool_calls_data = []
        for idx in sorted(tool_call_deltas.keys()):
            tc = tool_call_deltas[idx]
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls_data.append({
                "id": tc["id"],
                "name": tc["function"]["name"],
                "arguments": args,
            })
        yield f"2:{json.dumps(tool_calls_data)}\n"


def _parse_response(response) -> ChatResponse:
    """解析 OpenAI SDK 的响应为统一的 ChatResponse 格式"""
    choice = response.choices[0]
    message = choice.message

    content = message.content

    tool_calls = None
    if message.tool_calls:
        tool_calls = []
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))

    return ChatResponse(content=content, tool_calls=tool_calls)
