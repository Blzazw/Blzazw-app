# Blzazw

一个有温度、有判断力的个人助手。

## 功能

- 💬 智能对话（基于 DeepSeek API）
- 🔍 搜索互联网 + 读取网页
- 🐍 执行 Python 代码
- 💻 执行系统命令
- 📁 读写文件
- 🛡️ 三级安全模式（客卿 / 家臣 / 君主）
- 📝 多会话管理

## 快速开始

1. 从 [Releases](https://github.com/Blzazw/blzazw-app/releases) 下载最新安装包
2. 安装并打开
3. 输入你的 [DeepSeek API Key](https://platform.deepseek.com/api_keys)
4. 开始对话

## 开发

```bash
# 安装依赖
npm install
pip install -r agent/requirements.txt

# 平放模式
npx vite

# 打包
npm run build
npm run dist
```

## 技术栈

- **前端**: React + TypeScript + Vite
- **桌面壳**: Electron
- **后端**: Python + FastAPI + DeepSeek API

## 许可证

MIT
