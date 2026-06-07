/* ──────────── 类型定义 ──────────── */

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content?: string | null
  tool_calls?: ToolCallData[]
  tool_call_id?: string
  name?: string
}

export interface ToolCallData {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

export interface SessionInfo {
  id: string
  preview: string
  mtime: number
}

export interface ToolEvent {
  id: string
  name: string
  arguments: Record<string, any>
}

export interface ToolResultEvent {
  id: string
  name: string
  content: string
}

export type SecurityMode = 'safe' | 'trusted' | 'sovereign'

export const MODE_LABELS: Record<SecurityMode, { icon: string; name: string; desc: string }> = {
  safe: { icon: '🛡️', name: '客卿', desc: '写文件、执行代码需弹窗确认' },
  trusted: { icon: '⚡', name: '家臣', desc: '所有工具自动执行，操作过程可见' },
  sovereign: { icon: '👑', name: '君主', desc: '完全信赖，静默执行，无需确认' },
}

// Python 后端地址
// 开发环境：Vite 代理 /api 到后端
// 生产环境：直接请求后端
export const API_BASE = 'http://127.0.0.1:8080'
