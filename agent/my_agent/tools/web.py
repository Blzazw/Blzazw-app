"""
网络工具：搜索和读取网页。
"""

from duckduckgo_search import DDGS
import httpx


async def web_search(query: str, max_results: int = 8) -> str:
    """
    搜索互联网。使用 DuckDuckGo，无需 API Key。

    参数:
        query: 搜索关键词
        max_results: 返回结果数量，默认 8

    返回:
        搜索结果的文本摘要
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"搜索失败: {e}"

    if not results:
        return f"搜索 '{query}' 没有找到结果。"

    lines = [f"搜索结果: {query}", ""]
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        snippet = r.get("body", "")
        url = r.get("href", "")
        lines.append(f"{i}. {title}")
        lines.append(f"   {snippet[:200]}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


async def web_fetch(url: str, max_length: int = 5000) -> str:
    """
    读取网页内容并提取正文文本。

    参数:
        url: 网页 URL
        max_length: 最大返回字符数，默认 5000

    返回:
        网页的文本内容
    """
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Blzazw/1.0)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception as e:
        return f"读取网页失败: {e}"

    # 简单提取文本（去除 HTML 标签）
    import re
    html = response.text
    # 移除 script 和 style 块
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', html)
    # 合并空白字符
    text = re.sub(r'\s+', ' ', text).strip()
    # 解码 HTML 实体
    import html as html_mod
    text = html_mod.unescape(text)

    if len(text) > max_length:
        text = text[:max_length] + "\n\n[内容已截断，仅显示前 {} 字符]".format(max_length)

    return text
