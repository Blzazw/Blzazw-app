"""
工具注册表。
所有工具的注册、描述、调度都在这里统一管理。
"""

from typing import Any, Callable, Coroutine


# 工具安全等级
SAFE = "safe"        # 只读，无需确认
CAUTION = "caution"  # 写操作，安全模式下需确认
DANGEROUS = "danger"  # 执行代码/命令，安全模式下需确认


class Tool:
    """一个工具的完整定义"""
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Coroutine[Any, Any, str]],
        security: str = SAFE,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema
        self.handler = handler
        self.security = security

    def to_openai_tool(self) -> dict:
        """转换为 OpenAI 格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Registry:
    """
    工具注册表。
    注册: registry.register(tool)
    调度: registry.execute(name, args) → str
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """注册一个工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """按名称获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """列出所有已注册的工具"""
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        """获取所有工具的 OpenAI 格式描述"""
        return [t.to_openai_tool() for t in self._tools.values()]

    def get_security(self, name: str) -> str | None:
        """获取工具的安全等级"""
        tool = self._tools.get(name)
        return tool.security if tool else None

    async def execute(self, name: str, arguments: dict) -> str:
        """执行一个工具，返回结果字符串"""
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未知工具 '{name}'"
        try:
            result = await tool.handler(**arguments)
            return str(result)
        except Exception as e:
            return f"工具 '{name}' 执行出错: {type(e).__name__}: {e}"


# 全局唯一的工具注册表
registry = Registry()
