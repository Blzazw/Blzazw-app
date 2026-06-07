/**
 * API 通信层
 * 
 * 封装所有后端接口调用，包括 SSE 流式聊天。
 */

import { API_BASE, ChatMessage, SessionInfo, SecurityMode } from './types'

/* ──────────── 工具函数 ──────────── */

async function get(path: string) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`)
  return res.json()
}

async function post(path: string, body: any) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path}: ${res.status}`)
  return res.json()
}

/* ──────────── 会话管理 ──────────── */

export async function listSessions(): Promise<{ sessions: SessionInfo[] }> {
  return get('/api/sessions')
}

export async function newSession(): Promise<{ session_id: string; welcome: string }> {
  return post('/api/sessions/new', {})
}

export async function getSessionMessages(sessionId: string): Promise<{ messages: ChatMessage[] }> {
  return get(`/api/sessions/${sessionId}/messages`)
}

export async function clearSession(sessionId: string) {
  return post(`/api/sessions/${sessionId}/clear`, {})
}

/* ──────────── 安全模式 ──────────── */

export async function setMode(sessionId: string, mode: SecurityMode) {
  return post('/api/mode', { session_id: sessionId, mode })
}

export async function getModes() {
  return get('/api/modes')
}

/* ──────────── 工具确认 ──────────── */

export async function confirmTool(sessionId: string, toolCallId: string, approved: boolean) {
  return post('/api/confirm', { session_id: sessionId, tool_call_id: toolCallId, approved })
}

/* ──────────── SSE 流式聊天 ──────────── */

export type SSEEventCallback = {
  onToken?: (content: string) => void
  onToolCall?: (id: string, name: string, args: Record<string, any>) => void
  onToolResult?: (id: string, name: string, content: string) => void
  onConfirmRequired?: (id: string, name: string, args: Record<string, any>) => void
  onToolSkipped?: (id: string, name: string, reason: string) => void
  onDone?: () => void
  onError?: (message: string) => void
  onComplete?: () => void
}

export async function sendChatMessage(
  message: string,
  sessionId: string,
  mode: SecurityMode,
  callbacks: SSEEventCallback,
  signal?: AbortSignal
) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, mode }),
    signal,
  })

  if (!res.ok) throw new Error(`Chat error: HTTP ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const trimmed = part.trim()
      if (!trimmed) continue

      let eventType = 'message'
      let dataStr = trimmed

      const lines = trimmed.split('\n')
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          dataStr = line.slice(6)
        }
      }

      try {
        const data = JSON.parse(dataStr)
        switch (eventType) {
          case 'token':
            callbacks.onToken?.(data.content)
            break
          case 'tool_call':
            callbacks.onToolCall?.(data.id, data.name, data.arguments)
            break
          case 'tool_result':
            callbacks.onToolResult?.(data.id, data.name, data.content)
            break
          case 'confirm_required':
            callbacks.onConfirmRequired?.(data.id, data.name, data.arguments)
            break
          case 'tool_skipped':
            callbacks.onToolSkipped?.(data.id, data.name, data.reason)
            break
          case 'done':
            callbacks.onDone?.()
            break
          case 'error':
            callbacks.onError?.(data.message)
            break
          case 'complete':
            callbacks.onComplete?.()
            break
        }
      } catch (e) {
        // skip malformed data
      }
    }
  }
}
