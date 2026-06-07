"""
文件操作工具。
允许 agent 读写和列出本地文件。
"""

import os


async def file_read(path: str, encoding: str = "utf-8") -> str:
    """
    读取文件内容。

    参数:
        path: 文件路径（绝对路径或相对于工作目录的路径）
        encoding: 文件编码，默认 utf-8

    返回:
        文件内容
    """
    if not os.path.exists(path):
        return f"文件不存在: {path}"
    if not os.path.isfile(path):
        return f"路径不是文件: {path}"

    try:
        with open(path, "r", encoding=encoding) as f:
            content = f.read()
        return content
    except Exception as e:
        return f"读取文件失败: {e}"


async def file_write(path: str, content: str, encoding: str = "utf-8") -> str:
    """
    写入文件（如果文件存在则覆盖）。

    参数:
        path: 文件路径（绝对路径或相对于工作目录的路径）
        content: 要写入的内容
        encoding: 文件编码，默认 utf-8

    返回:
        操作结果
    """
    try:
        # 确保目录存在
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return f"文件已写入: {path}（{len(content)} 字符）"
    except Exception as e:
        return f"写入文件失败: {e}"


async def file_list(path: str = ".") -> str:
    """
    列出目录内容。

    参数:
        path: 目录路径，默认当前目录

    返回:
        目录内容的文本列表
    """
    if not os.path.exists(path):
        return f"路径不存在: {path}"
    if not os.path.isdir(path):
        return f"路径不是目录: {path}"

    try:
        entries = os.listdir(path)
        entries.sort()

        lines = [f"目录: {os.path.abspath(path)}", ""]
        for entry in entries:
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                size = ""
                try:
                    # 统计目录中的文件数
                    count = len(os.listdir(full_path))
                    size = f" ({count} 项)"
                except Exception:
                    pass
                lines.append(f"  📁  {entry}/{size}")
            elif os.path.isfile(full_path):
                try:
                    sz = os.path.getsize(full_path)
                    if sz < 1024:
                        size_str = f"{sz} B"
                    elif sz < 1024 * 1024:
                        size_str = f"{sz / 1024:.1f} KB"
                    else:
                        size_str = f"{sz / 1024 / 1024:.1f} MB"
                    lines.append(f"  📄  {entry}  ({size_str})")
                except Exception:
                    lines.append(f"  📄  {entry}")

        return "\n".join(lines)

    except Exception as e:
        return f"列出目录失败: {e}"
