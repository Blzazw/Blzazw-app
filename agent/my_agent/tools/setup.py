"""
工具注册配置。
在这里把所有工具注册到全局注册表中。
"""

from my_agent.tools.registry import Registry, Tool, SAFE, CAUTION, DANGEROUS
from my_agent.tools.web import web_search, web_fetch
from my_agent.tools.code import python_exec, shell_exec
from my_agent.tools.files import file_read, file_write, file_list


def register_all_tools(registry: Registry):
    """注册所有工具到指定的注册表"""

    registry.register(Tool(
        name="web_search",
        description="搜索互联网。当你需要最新信息、查找资料、验证事实时使用。提供搜索关键词即可。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量（默认 8）",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
        handler=web_search,
        security=SAFE,
    ))

    registry.register(Tool(
        name="web_fetch",
        description="读取指定 URL 的网页内容并提取正文。适用于阅读文章、文档、新闻等。",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "网页的完整 URL",
                },
                "max_length": {
                    "type": "integer",
                    "description": "最大返回字符数（默认 5000）",
                    "default": 5000,
                },
            },
            "required": ["url"],
        },
        handler=web_fetch,
        security=SAFE,
    ))

    registry.register(Tool(
        name="python_exec",
        description="执行 Python 代码并返回输出。适用于计算、数据分析、生成内容、写脚本等。代码会在独立进程中运行。",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认 30）",
                    "default": 30,
                },
            },
            "required": ["code"],
        },
        handler=python_exec,
        security=DANGEROUS,
    ))

    registry.register(Tool(
        name="shell_exec",
        description="在终端中执行命令并返回输出。适用于系统操作、运行脚本、编译代码等。",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认 30）",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
        handler=shell_exec,
        security=DANGEROUS,
    ))

    registry.register(Tool(
        name="file_read",
        description="读取指定路径的文件内容。适用于查看代码、配置文件、文本文件等。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认 utf-8）",
                    "default": "utf-8",
                },
            },
            "required": ["path"],
        },
        handler=file_read,
        security=SAFE,
    ))

    registry.register(Tool(
        name="file_write",
        description="写入文件。如果文件已存在则覆盖其内容。目录会自动创建。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容",
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码（默认 utf-8）",
                    "default": "utf-8",
                },
            },
            "required": ["path", "content"],
        },
        handler=file_write,
        security=CAUTION,
    ))

    registry.register(Tool(
        name="file_list",
        description="列出指定目录的内容。显示文件和子目录的名称及大小。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（默认当前目录）",
                    "default": ".",
                },
            },
            "required": [],
        },
        handler=file_list,
        security=SAFE,
    ))
