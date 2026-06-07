"""
代码执行工具。
允许 agent 执行 Python 代码。
"""

import subprocess
import tempfile
import os
import ast
import sys


async def python_exec(code: str, timeout: int = 30) -> str:
    """
    执行 Python 代码并返回输出。

    参数:
        code: 要执行的 Python 代码
        timeout: 超时秒数，默认 30

    返回:
        代码执行的 stdout 和 stderr
    """
    # 安全检查：禁止危险操作
    forbidden_patterns = [
        "__import__('os').system",
        "__import__('subprocess')",
        "__import__('shutil').rmtree",
        "os.remove",
        "os.rmdir",
        "shutil.rmtree",
    ]
    for pattern in forbidden_patterns:
        if pattern in code:
            return f"安全限制：代码包含被禁止的操作 '{pattern}'"

    try:
        # 先做语法检查
        ast.parse(code)
    except SyntaxError as e:
        return f"语法错误: {e}"

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout.strip())
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr.strip()}")

        if not output_parts:
            return "代码执行成功，无输出。"

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"代码执行超时（超过 {timeout} 秒）"
    except Exception as e:
        return f"代码执行出错: {type(e).__name__}: {e}"


async def shell_exec(command: str, timeout: int = 30) -> str:
    """
    执行 shell 命令并返回输出。

    参数:
        command: 要执行的命令
        timeout: 超时秒数，默认 30

    返回:
        命令执行的 stdout 和 stderr
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout.strip())
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr.strip()}")

        if not output_parts:
            return "命令执行完成，无输出。"

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"命令执行超时（超过 {timeout} 秒）"
    except Exception as e:
        return f"命令执行出错: {type(e).__name__}: {e}"
