# Blzazw

一个有温度、有判断力的个人助手。

Blzazw 是一个桌面 AI 助手，基于 DeepSeek 大模型，能够搜索互联网、执行代码、操作文件、控制系统命令。它像一位懂你的朋友——既有温度，也有判断力。

---

## 快速开始

### 安装

1. 前往 [Releases](https://github.com/Blzazw/Blzazw-app/releases) 下载最新版 `Blzazw.Setup.x.x.x.exe`
2. 双击安装，按提示完成安装
3. 安装完成后桌面上会出现 Blzazw 图标，双击打开

### 首次使用

1. 打开 Blzazw 后会看到**欢迎页面**
2. 输入你的 [DeepSeek API Key](https://platform.deepseek.com/api_keys)
3. 点击确认，验证通过后进入主界面
4. 开始对话

> **注意**：Blzazw 需要使用你自己的 DeepSeek API Key。Key 仅保存在你的电脑本地，不会上传。

---

## 功能介绍

### 💬 智能对话

Blzazw 有深厚的文学和哲学素养，逻辑能力强。它会从底层原理出发分析问题，用类比和具体例子让抽象概念变得好懂。

### 🔍 搜索互联网

知识不够用时，Blzazw 会主动搜索互联网获取最新信息。你也可以直接要求它搜索某个话题。

### 🐍 执行 Python 代码

Blzazw 可以编写并执行 Python 代码——用于计算、数据处理、文件分析、生成内容等。

### 💻 执行系统命令

Blzazw 可以执行终端命令——打开程序、管理系统、运行脚本。配合安全模式，你可以控制它的操作权限。

### 📁 读写文件

Blzazw 可以读取、写入、列出本地文件——帮你编辑文档、整理代码、查看配置。

---

## 安全模式

Blzazw 提供三级安全模式，控制它对电脑的操作权限。

| 模式 | 名称 | 行为 |
|---|---|---|
| 🛡️ **客卿** | 安全模式（默认） | 写文件、执行代码和命令时需要弹窗确认 |
| ⚡ **家臣** | 信任模式 | 所有工具自动执行，操作过程可见 |
| 👑 **君主** | 完全信任模式 | 所有工具静默执行，完全信赖 agent 的判断 |

点击右上角的安全模式按钮可以随时切换。

---

## 设置

点击右上角的 ⚙ 按钮可以打开设置页面：

- **修改 API Key**：更换 DeepSeek API Key
- **Key 安全提示**：Key 仅保存在你的电脑本地，使用 Electron 加密存储

---

## 自动更新

Blzazw 启动时会自动检查 GitHub 上是否有新版本。如果有新版本发布：

1. 软件会提示你"发现新版本"
2. 点击"下载"按钮开始下载更新
3. 下载完成后点击"安装"即可重启完成更新

你也可以在 [Releases](https://github.com/Blzazw/Blzazw-app/releases) 页面手动下载最新安装包。

---

## 常见问题

**问：需要自己准备 API Key 吗？**

是的。Blzazw 使用 DeepSeek 的 API，你需要去 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 注册并获取 API Key。首次打开软件时会引导你配置。

**问：我的 API Key 安全吗？**

Key 使用 Electron 的加密存储保存在你的电脑本地，不会上传或分享给任何人。

**问：Blzazw 会联网吗？**

会。当你需要搜索信息、读取网页内容时，Blzazw 会连接互联网。除此之外，所有对话和数据处理都在你的电脑本地完成。

**问：如何卸载？**

在 Windows 设置 → 应用 → 应用和功能中找到 "Blzazw"，点击卸载即可。

---

## 开发

```bash
# 克隆项目
git clone https://github.com/Blzazw/Blzazw-app.git
cd Blzazw-app

# 安装前端依赖
npm install

# 安装 Python 后端依赖
pip install -r agent/requirements.txt

# 开发模式（热更新）
npx vite

# 打包生成安装包
npm run build
npx electron-builder --win --x64 --publish never
```

### 技术栈

- **前端**: React + TypeScript + Vite
- **桌面壳**: Electron
- **后端**: Python + FastAPI
- **模型**: DeepSeek API

---

## 许可证

[MIT](LICENSE)
