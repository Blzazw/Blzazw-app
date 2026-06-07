import React, { useState, useEffect, useRef, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import InputArea from './components/InputArea'
import ConfirmDialog from './components/ConfirmDialog'
import {
  ChatMessage, SessionInfo, SecurityMode,
  MODE_LABELS, ToolEvent, ToolResultEvent,
} from './types'
import {
  listSessions, newSession, getSessionMessages,
  sendChatMessage, confirmTool, setMode, clearSession,
} from './api'

/* ──────────── Markdown 渲染 ──────────── */
function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
  html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  if (!html.startsWith('<') || html.startsWith('<br>')) {
    html = '<p>' + html + '</p>'
  }
  return html
}

/* ──────────── 消息气泡组件 ──────────── */
function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const label = isUser ? '你' : 'Blzazw'

  return (
    <div className={`msg-group ${isUser ? 'user-group' : 'agent-group'}`}>
      <div className={`msg-label ${isUser ? 'user-label' : ''}`}>{label}</div>
      {msg.content && (
        <div className={`msg ${isUser ? 'user' : 'agent'}`}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
      )}
      {msg.tool_calls?.map((tc) => (
        <div key={tc.id} className="thinking-step agent-side result">
          <div className="thinking-toggle">
            <span className="icon">⚙</span>
            <span>{tc.function.name}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ──────────── 流式消息组件 ──────────── */
function StreamMessage({ content, toolCalls }: { content: string; toolCalls: ToolCallInfo[] }) {
  return (
    <div className="msg-group agent-group">
      <div className="msg-label">Blzazw</div>
      <div className="msg agent stream-active">
        {content ? (
          <span dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />
        ) : (
          <span className="stream-cursor" />
        )}
        {content && <span className="stream-cursor" />}
      </div>
      {toolCalls.map((tc) => (
        <div key={tc.id} className={`thinking-step agent-side ${tc.status}`}>
          <div className="thinking-toggle">
            <span className="icon">
              {tc.status === 'pending' ? '⟳' : tc.status === 'running' ? '⟳' : tc.status === 'done' ? '✓' : tc.status === 'skipped' ? '—' : '⚠'}
            </span>
            <span>{tc.name}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

interface ToolCallInfo {
  id: string
  name: string
  status: 'pending' | 'running' | 'done' | 'skipped' | 'error'
}

/* ──────────── 主应用 ──────────── */
export default function App() {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [currentSession, setCurrentSession] = useState('default')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [mode, setModeState] = useState<SecurityMode>('safe')
  const [processing, setProcessing] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [apiKeySet, setApiKeySet] = useState<boolean | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [settingsKey, setSettingsKey] = useState('')
  const [savingKey, setSavingKey] = useState(false)
  const [keyError, setKeyError] = useState<string | null>(null)

  // 流式回复状态
  const [streamContent, setStreamContent] = useState('')
  const [toolCalls, setToolCalls] = useState<ToolCallInfo[]>([])

  // 确认弹窗
  const [confirm, setConfirm] = useState<{ id: string; name: string; args: string } | null>(null)

  // 中断控制
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const streamContentRef = useRef('')
  const toolCallsRef = useRef<ToolCallInfo[]>([])

  /* ── 自动滚动 ── */
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamContent, toolCalls])

  /* ── 初始化 ── */
  useEffect(() => {
    checkApiKey()
    loadSessions()
    loadMessages('default')
  }, [])

  /* ── 检查 API Key ── */
  const checkApiKey = async () => {
    try {
      if (window.blzazw?.hasApiKey) {
        const has = await window.blzazw.hasApiKey()
        setApiKeySet(has)
      } else {
        setApiKeySet(true) // 浏览器环境默认跳过
      }
    } catch (e) {
      setApiKeySet(true)
    }
  }

  /* ── 加载会话列表 ── */
  const loadSessions = async () => {
    try {
      const data = await listSessions()
      setSessions(data.sessions)
    } catch (e) { /* ignore */ }
  }

  /* ── 加载消息历史 ── */
  const loadMessages = async (id: string) => {
    try {
      const data = await getSessionMessages(id)
      setMessages(data.messages)
    } catch (e) {
      setMessages([])
    }
  }

  /* ── 切换会话 ── */
  const selectSession = useCallback(async (id: string) => {
    // 打断进行中的请求
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setProcessing(false)
    setStreamContent('')
    setToolCalls([])
    streamContentRef.current = ''
    toolCallsRef.current = []

    setCurrentSession(id)
    await loadMessages(id)
  }, [])

  /* ── 新建会话 ── */
  const handleNewSession = async () => {
    try {
      const data = await newSession()
      await loadSessions()
      selectSession(data.session_id)
    } catch (e) { /* ignore */ }
  }

  /* ── 清空对话 ── */
  const handleClear = async () => {
    try {
      await clearSession(currentSession)
      setMessages([])
      setStreamContent('')
      setToolCalls([])
    } catch (e) { /* ignore */ }
  }

  /* ── 切换模式 ── */
  const cycleMode = async () => {
    const modes: SecurityMode[] = ['safe', 'trusted', 'sovereign']
    const idx = modes.indexOf(mode)
    const next = modes[(idx + 1) % modes.length]
    setModeState(next)
    try {
      await setMode(currentSession, next)
    } catch (e) { /* ignore */ }
  }

  /* ── 发送消息 ── */
  const handleSend = async (text: string) => {
    setProcessing(true)
    setStreamContent('')
    setToolCalls([])
    streamContentRef.current = ''
    toolCallsRef.current = []

    // 添加用户消息
    const userMsg: ChatMessage = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])

    const abortController = new AbortController()
    abortRef.current = abortController

    try {
      await sendChatMessage(text, currentSession, mode, {
        onToken: (content) => {
          streamContentRef.current += content
          setStreamContent(streamContentRef.current)
        },
        onToolCall: (id, name) => {
          const tc: ToolCallInfo = { id, name, status: 'running' }
          toolCallsRef.current = [...toolCallsRef.current, tc]
          setToolCalls(toolCallsRef.current)
        },
        onToolResult: (id) => {
          toolCallsRef.current = toolCallsRef.current.map((t) =>
            t.id === id ? { ...t, status: 'done' as const } : t
          )
          setToolCalls(toolCallsRef.current)
        },
        onConfirmRequired: (id, name, args) => {
          const argsStr = JSON.stringify(args, null, 2)
          setConfirm({ id, name, args: argsStr })
        },
        onToolSkipped: (id) => {
          toolCallsRef.current = toolCallsRef.current.map((t) =>
            t.id === id ? { ...t, status: 'skipped' as const } : t
          )
          setToolCalls(toolCallsRef.current)
        },
        onDone: () => {
          // 把流式内容转为正式消息
          const content = streamContentRef.current
          if (content) {
            const assistantMsg: ChatMessage = { role: 'assistant', content }
            setMessages((prev) => [...prev, assistantMsg])
          }
          setStreamContent('')
          setToolCalls([])
          streamContentRef.current = ''
          toolCallsRef.current = []
        },
        onError: (msg) => {
          console.error('Chat error:', msg)
          addAgentMessage(`[错误] ${msg}`)
        },
        onComplete: () => {
          loadSessions()
        },
      }, abortController.signal)
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Send failed:', err)
      }
    } finally {
      setProcessing(false)
      abortRef.current = null
    }

    // 重新加载会话列表
    loadSessions()
  }

  /* ── 设置 API Key ── */
  const handleSaveKey = async () => {
    if (!settingsKey.trim()) return
    setSavingKey(true)
    setKeyError(null)
    try {
      if (window.blzazw?.saveApiKey) {
        const result = await window.blzazw.saveApiKey(settingsKey.trim())
        if (result.ok) {
          setApiKeySet(true)
          setShowSettings(false)
          setSettingsKey('')
        } else {
          setKeyError(result.error || '保存失败')
        }
      }
    } catch (e) {
      setKeyError('保存失败: ' + (e as Error).message)
    }
    setSavingKey(false)
  }

  /* ── 确认工具调用 ── */
  const handleApprove = async () => {
    if (!confirm) return
    try {
      await confirmTool(currentSession, confirm.id, true)
    } catch (e) { /* ignore */ }
    setConfirm(null)
  }

  const handleDeny = async () => {
    if (!confirm) return
    try {
      await confirmTool(currentSession, confirm.id, false)
    } catch (e) { /* ignore */ }
    setConfirm(null)
  }

  /* ── 渲染 ── */
  const modeInfo = MODE_LABELS[mode]

  // 首次使用：显示 API Key 设置
  if (apiKeySet === false) {
    return (
      <div className="setup-screen">
        <div className="setup-card">
          <div className="setup-icon">B</div>
          <h1>欢迎使用 Blzazw</h1>
          <p>请先配置你的 DeepSeek API Key</p>
          <p className="setup-hint">
            去{' '}
            <a href="#" onClick={(e) => { e.preventDefault(); window.blzazw?.openExternal('https://platform.deepseek.com/api_keys') }}>
              platform.deepseek.com
            </a>
            {' '}获取 Key
          </p>
          <div className="setup-input-group">
            <input
              type="password"
              placeholder="输入你的 DeepSeek API Key..."
              value={settingsKey}
              onChange={(e) => { setSettingsKey(e.target.value); setKeyError(null) }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveKey() }}
              autoFocus
            />
            <button onClick={handleSaveKey} disabled={savingKey || !settingsKey.trim()}>
              {savingKey ? '验证中...' : '确认'}
            </button>
          </div>
          {keyError && <p style={{color: 'var(--danger)', fontSize: 13, marginTop: 12}}>{keyError}</p>}
        </div>
        <style>{`
          .setup-screen {
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-primary);
          }
          .setup-card {
            text-align: center;
            max-width: 400px;
            padding: 40px;
          }
          .setup-icon {
            width: 64px; height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent), #b88a5a);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: var(--font-display);
            font-size: 28px;
            color: #0d0d14;
            font-weight: 600;
            margin: 0 auto 20px;
            box-shadow: 0 0 40px var(--accent-glow);
          }
          .setup-card h1 {
            font-family: var(--font-display);
            font-size: 28px;
            font-weight: 400;
            color: var(--text-primary);
            margin-bottom: 8px;
          }
          .setup-card p {
            color: var(--text-muted);
            font-size: 14px;
            margin-bottom: 4px;
          }
          .setup-card .setup-hint { margin-bottom: 24px; }
          .setup-card a {
            color: var(--accent);
            text-decoration: underline;
            text-underline-offset: 2px;
          }
          .setup-input-group {
            display: flex;
            gap: 8px;
          }
          .setup-input-group input {
            flex: 1;
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-family: var(--font-body);
            font-size: 14px;
            outline: none;
            transition: var(--transition);
          }
          .setup-input-group input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-glow);
          }
          .setup-input-group button {
            padding: 10px 20px;
            border-radius: var(--radius-sm);
            border: none;
            background: var(--accent);
            color: #0d0d14;
            font-family: var(--font-body);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: var(--transition);
            white-space: nowrap;
          }
          .setup-input-group button:hover:not(:disabled) { background: var(--accent-hover); }
          .setup-input-group button:disabled { opacity: 0.5; cursor: not-allowed; }
        `}</style>
      </div>
    )
  }

  // 加载中
  if (apiKeySet === null) {
    return (
      <div className="setup-screen">
        <div className="setup-card">
          <p style={{color: 'var(--text-muted)'}}>加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app-layout">
      <Sidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelect={selectSession}
        onNew={handleNewSession}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="main">
        {/* 顶栏 */}
        <header className="main-header">
          <div className="main-header-left">
            <button className="menu-btn" onClick={() => setSidebarOpen(true)}>☰</button>
            <div className="agent-avatar">B</div>
            <div className="agent-info">
              <h2>Blzazw</h2>
              <p>
                <span className={`status-dot ${processing ? 'thinking' : ''}`} />
                {' '}{processing ? '思考中' : '在线'}
              </p>
            </div>
          </div>
          <div className="main-header-right">
            <button className="clear-btn" onClick={handleClear} title="清空当前对话">✕</button>
            <button className="settings-btn" onClick={() => setShowSettings(true)} title="设置">⚙</button>
            <button className={`mode-badge ${mode}`} onClick={cycleMode}>
              {modeInfo.icon} {modeInfo.name}
            </button>
          </div>
        </header>

        {/* 消息区 */}
        <div className="messages-area" ref={scrollRef}>
          {messages.length === 0 && !streamContent ? (
            <div className="welcome-screen">
              <h1>Blzazw</h1>
              <p>有温度、有判断力的个人助手。</p>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageBubble key={i} msg={msg} />
              ))}
              {processing && (
                <StreamMessage content={streamContent} toolCalls={toolCalls} />
              )}
            </>
          )}
        </div>

        {/* 输入区 */}
        <InputArea onSend={handleSend} disabled={processing} />
      </div>

      {/* 设置弹窗 */}
      {showSettings && (
        <div className="confirm-overlay" onClick={() => setShowSettings(false)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>设置</h3>
            <div className="sub">配置 API Key</div>
            <div className="confirm-detail">
              <input
                type="password"
                placeholder="DeepSeek API Key"
                value={settingsKey}
                onChange={(e) => setSettingsKey(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSaveKey() }}
                autoFocus
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-body)',
                  fontSize: '14px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <p style={{marginTop: 12, fontSize: 12, color: 'var(--text-muted)'}}>
                去{' '}
                <a href="#" style={{color: 'var(--accent)'}} onClick={(e) => { e.preventDefault(); window.blzazw?.openExternal('https://platform.deepseek.com/api_keys') }}>
                  platform.deepseek.com
                </a>
                {' '}获取 API Key
              </p>
            </div>
            <div className="confirm-actions">
              <button className="btn-deny" onClick={() => setShowSettings(false)}>取消</button>
              <button className="btn-approve" onClick={handleSaveKey} disabled={savingKey || !settingsKey.trim()}>
                {savingKey ? '验证中...' : '保存'}
              </button>
            </div>
            {keyError && <p style={{color: 'var(--danger)', fontSize: 13, marginTop: 12}}>{keyError}</p>}
          </div>
        </div>
      )}

      {/* 确认弹窗 */}
      <ConfirmDialog
        show={confirm !== null}
        toolName={confirm?.name || ''}
        toolArgs={confirm?.args || ''}
        onApprove={handleApprove}
        onDeny={handleDeny}
      />

      <style>{`
        .app-layout {
          display: flex;
          height: 100vh;
          overflow: hidden;
        }
        .main {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-width: 0;
        }
        .main-header {
          padding: 12px 20px;
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(13,13,20,0.85);
          backdrop-filter: blur(12px);
          z-index: 10;
          -webkit-app-region: drag;
        }
        .main-header-left {
          display: flex;
          align-items: center;
          gap: 12px;
          -webkit-app-region: no-drag;
        }
        .main-header-right {
          -webkit-app-region: no-drag;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .clear-btn {
          width: 28px; height: 28px;
          border-radius: 50%;
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-muted);
          font-size: 12px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: var(--transition);
          font-family: var(--font-body);
        }
        .clear-btn:hover {
          border-color: var(--danger);
          color: var(--danger);
          background: rgba(224,96,96,0.1);
        }
        .settings-btn {
          width: 28px; height: 28px;
          border-radius: 50%;
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-muted);
          font-size: 14px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: var(--transition);
          font-family: var(--font-body);
        }
        .settings-btn:hover {
          border-color: var(--accent);
          color: var(--accent);
          background: var(--accent-glow);
        }
        .menu-btn {
          display: none;
          width: 32px; height: 32px;
          border: none;
          background: transparent;
          color: var(--text-secondary);
          font-size: 20px;
          cursor: pointer;
          border-radius: var(--radius-sm);
        }
        .menu-btn:hover { background: var(--bg-hover); }
        .agent-avatar {
          width: 34px; height: 34px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent), #b88a5a);
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-display);
          font-size: 15px;
          color: #0d0d14;
          font-weight: 600;
        }
        .agent-info h2 {
          font-family: var(--font-display);
          font-size: 15px;
          font-weight: 600;
        }
        .agent-info p {
          font-size: 11px;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .status-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: var(--success);
          display: inline-block;
          flex-shrink: 0;
        }
        .status-dot.thinking {
          animation: pulse 1.2s infinite;
          background: var(--accent);
        }
        .mode-badge {
          font-size: 11px;
          padding: 4px 12px;
          border-radius: 20px;
          cursor: pointer;
          transition: var(--transition);
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-muted);
          font-family: var(--font-body);
          white-space: nowrap;
        }
        .mode-badge:hover { border-color: var(--accent); color: var(--accent); }
        .mode-badge.safe { border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }
        .mode-badge.trusted { border-color: #7ab8e0; color: #7ab8e0; background: rgba(122,184,224,0.1); }
        .mode-badge.sovereign { border-color: var(--success); color: var(--success); background: rgba(106,191,138,0.1); }
        @media (max-width: 768px) {
          .menu-btn { display: flex; }
        }

        /* ── 消息区 ── */
        .messages-area {
          flex: 1;
          overflow-y: auto;
          padding: 20px 20px 0;
        }
        .messages-area:empty {
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .welcome-screen {
          text-align: center;
          margin: auto;
          max-width: 360px;
        }
        .welcome-screen h1 {
          font-family: var(--font-display);
          font-size: 32px;
          font-weight: 400;
          color: var(--accent);
          margin-bottom: 8px;
        }
        .welcome-screen p {
          color: var(--text-muted);
          font-size: 14px;
          line-height: 1.7;
        }

        /* ── 消息气泡 ── */
        .msg-group { margin-bottom: 18px; }
        .msg {
          max-width: 76%;
          padding: 12px 16px;
          border-radius: var(--radius-md);
          line-height: 1.7;
          font-size: 14px;
          animation: fadeIn 0.3s ease;
          overflow-wrap: break-word;
        }
        .msg p { margin-bottom: 6px; }
        .msg p:last-child { margin-bottom: 0; }
        .msg code {
          background: rgba(212,165,116,0.1);
          padding: 1px 6px;
          border-radius: 4px;
          font-size: 13px;
          font-family: 'JetBrains Mono', 'SF Mono', monospace;
          color: var(--accent);
        }
        .msg pre {
          background: var(--bg-tertiary);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 10px 14px;
          margin: 6px 0;
          overflow-x: auto;
          font-size: 13px;
          font-family: 'JetBrains Mono', 'SF Mono', monospace;
        }
        .msg pre code {
          background: none; padding: 0; color: var(--text-primary);
        }
        .msg ul, .msg ol { padding-left: 20px; margin: 4px 0; }
        .msg li { margin-bottom: 3px; }
        .msg strong { color: var(--accent); font-weight: 600; }
        .msg a { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
        .msg.user {
          background: var(--bg-msg-user);
          border: 1px solid var(--border);
          margin-left: auto;
          border-bottom-right-radius: 4px;
        }
        .msg.agent {
          background: var(--bg-msg-agent);
          border: 1px solid var(--border);
          margin-right: auto;
          border-bottom-left-radius: 4px;
        }
        .msg-label {
          font-size: 11px;
          color: var(--text-muted);
          margin-bottom: 4px;
          font-weight: 500;
          letter-spacing: 0.3px;
        }
        .user-label { text-align: right; }

        /* ── 流式光标 ── */
        .stream-cursor::after {
          content: '';
          display: inline-block;
          width: 2px;
          height: 1em;
          background: var(--accent);
          margin-left: 2px;
          vertical-align: text-bottom;
          animation: blink 0.8s step-end infinite;
        }

        /* ── 思考步骤 ── */
        .thinking-step {
          max-width: 80%;
          margin: 6px 0 6px auto;
          animation: fadeIn 0.3s ease;
        }
        .thinking-step.agent-side { margin-left: 0; margin-right: auto; }
        .thinking-toggle {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          background: var(--bg-tool);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          font-size: 12px;
          color: var(--text-secondary);
          font-family: var(--font-body);
          cursor: default;
        }
        .thinking-toggle .icon { font-size: 13px; }
        .thinking-step.result .thinking-toggle {
          color: var(--text-muted);
          border-color: transparent;
        }
        .thinking-step.skipped .thinking-toggle {
          color: var(--text-muted);
          text-decoration: line-through;
        }
      `}</style>
    </div>
  )
}
