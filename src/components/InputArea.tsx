import React, { useRef, useEffect } from 'react'

interface InputAreaProps {
  onSend: (text: string) => void
  disabled: boolean
}

export default function InputArea({ onSend, disabled }: InputAreaProps) {
  const textRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!disabled && textRef.current) {
      textRef.current.focus()
    }
  }, [disabled])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const submit = () => {
    const el = textRef.current
    if (!el) return
    const text = el.value.trim()
    if (!text || disabled) return
    el.value = ''
    el.style.height = 'auto'
    onSend(text)
  }

  const autoResize = () => {
    const el = textRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 120) + 'px'
    }
  }

  return (
    <div className="input-area">
      <div className="input-wrapper">
        <textarea
          ref={textRef}
          rows={1}
          placeholder="输入消息..."
          onKeyDown={handleKeyDown}
          onInput={autoResize}
        />
        <button className="send-btn" onClick={submit} disabled={disabled}>
          {disabled ? '⌛' : '→'}
        </button>
      </div>

      <style>{`
        .input-area {
          padding: 16px 24px 20px;
          border-top: 1px solid var(--border);
          background: rgba(13,13,20,0.85);
          backdrop-filter: blur(12px);
        }
        .input-wrapper {
          display: flex;
          gap: 8px;
          align-items: flex-end;
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          padding: 4px;
          transition: var(--transition);
        }
        .input-wrapper:focus-within {
          border-color: var(--accent);
          box-shadow: 0 0 0 2px var(--accent-glow);
        }
        .input-wrapper textarea {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          resize: none;
          padding: 8px 12px;
          color: var(--text-primary);
          font-family: var(--font-body);
          font-size: 14px;
          line-height: 1.5;
          max-height: 120px;
          min-height: 24px;
        }
        .input-wrapper textarea::placeholder { color: var(--text-muted); }
        .send-btn {
          width: 36px; height: 36px;
          border-radius: var(--radius-sm);
          border: none;
          background: var(--accent);
          color: #0d0d14;
          font-size: 18px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: var(--transition);
          flex-shrink: 0;
          margin: 2px;
          font-weight: 600;
        }
        .send-btn:hover:not(:disabled) { background: var(--accent-hover); }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        @media (max-width: 768px) {
          .input-area { padding: 12px 16px 16px; }
        }
      `}</style>
    </div>
  )
}
