"""
Blzazw — 启动入口。

运行方式：
    python run.py              ← 原生窗口模式（推荐）
    python run.py --browser    ← 浏览器模式
"""

import os
import sys
import time
import threading
import uvicorn
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载 .env
from dotenv import load_dotenv
dotenv_path = project_root / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    print("⚠️  .env 文件不存在，请先创建。")
    print("   参考: cp .env.example .env")
    print("   然后编辑 .env 填入你的 DeepSeek API Key")
    sys.exit(1)

# 检查 API Key（不是致命错误，仅警告）
api_key = os.getenv("DEEPSEEK_API_KEY", "")
if not api_key or api_key == "sk-your-api-key-here":
    print("[Blzazw] 未检测到 DeepSeek API Key")
    print("   请在 Blzazw 设置页面中配置 API Key")
    print("   获取 Key: https://platform.deepseek.com/api_keys")


def create_app():
    """创建 FastAPI 应用"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from my_agent.server.routes import router
    from my_agent.tools.registry import registry
    from my_agent.tools.setup import register_all_tools

    # 注册工具
    register_all_tools(registry)

    app = FastAPI(
        title="Blzazw",
        description="一个有温度、有判断力的个人助手",
        version="1.0.0",
    )

    # CORS — 允许 Electron/Vite 跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 路由
    app.include_router(router)

    # 静态文件（前端）
    static_dir = project_root / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
host = os.getenv("HOST", "127.0.0.1")
port = int(os.getenv("PORT", "8080"))
url = f"http://{host}:{port}"


def run_server():
    """后台启动 uvicorn 服务器"""
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_browser():
    """浏览器模式：打开系统默认浏览器"""
    import webbrowser
    webbrowser.open(url)
    print(f"✨  Blzazw 已启动")
    print(f"    浏览器已打开: {url}")
    print(f"    按 Ctrl+C 停止服务器")
    uvicorn.run(app, host=host, port=port, log_level="info")


def run_webview():
    """原生窗口模式：使用系统 WebView 弹出桌面窗口"""
    try:
        import webview
    except ImportError:
        print("⚠️  pywebview 未安装，自动切换到浏览器模式")
        print("   安装命令: pip install pywebview")
        print()
        run_browser()
        return

    # 在后台线程启动服务器
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 等服务器就绪
    for i in range(20):
        try:
            import httpx
            httpx.get(url, timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("❌  服务器启动超时")
        sys.exit(1)

    print(f"✨  Blzazw 已启动")

    # 创建原生窗口
    webview.create_window(
        title="Blzazw",
        url=url,
        width=960,
        height=720,
        min_size=(640, 480),
        resizable=True,
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    if "--browser" in sys.argv:
        run_browser()
    elif "--server" in sys.argv:
        # 纯服务模式：被 Electron 调用时使用，不启动任何窗口
        uvicorn.run(app, host=host, port=port, log_level="warning")
    else:
        run_webview()
