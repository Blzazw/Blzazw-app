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
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key or api_key == "sk-your-api-key-here":
        raise ValueError(
            "未配置 DeepSeek API Key。\n"
            "请前往 https://platform.deepseek.com/api_keys 获取 Key，\n"
            "然后编辑项目根目录的 .env 文件填入 DEEPSEEK_API_KEY。"
        )

    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _get_model() -> str:
    """获取模型名称"""
    return os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


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
    非流式调用 LLM。
    返回完整的响应，适用于需要解析工具调用的场景。
    """
    client = _get_client()
    model = _get_model()

    kwargs = {
        "model": model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    response = await client.chat.completions.create(**kwargs)
    return _parse_response(response)


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
