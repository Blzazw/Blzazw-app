import React from 'react'

interface ConfirmDialogProps {
  show: boolean
  toolName: string
  toolArgs: string
  onApprove: () => void
  onDeny: () => void
}

export default function ConfirmDialog({ show, toolName, toolArgs, onApprove, onDeny }: ConfirmDialogProps) {
  if (!show) return null

  return (
    <div className="confirm-overlay" onClick={onDeny}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>确认操作</h3>
        <div className="sub">Blzazw 想要执行以下操作</div>
        <div className="confirm-detail">
          <div className="tool-name">{toolName}</div>
          <div className="tool-args">{toolArgs}</div>
        </div>
        <div className="confirm-actions">
          <button className="btn-deny" onClick={onDeny}>拒绝</button>
          <button className="btn-approve" onClick={onApprove}>允许</button>
        </div>
      </div>

      <style>{`
        .confirm-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.6);
          backdrop-filter: blur(4px);
          z-index: 1000;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: fadeIn 0.2s ease;
        }
        .confirm-dialog {
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: 24px;
          max-width: 440px;
          width: 90%;
          box-shadow: var(--shadow-soft);
          animation: fadeIn 0.25s ease;
        }
        .confirm-dialog h3 {
          font-family: var(--font-display);
          font-size: 18px;
          font-weight: 400;
          color: var(--accent);
          margin-bottom: 4px;
        }
        .confirm-dialog .sub {
          font-size: 12px;
          color: var(--text-muted);
          margin-bottom: 16px;
        }
        .confirm-detail {
          background: var(--bg-tertiary);
          border-radius: var(--radius-sm);
          padding: 12px 14px;
          margin-bottom: 16px;
          font-size: 13px;
        }
        .confirm-detail .tool-name {
          color: var(--accent);
          font-weight: 500;
          margin-bottom: 6px;
        }
        .confirm-detail .tool-args {
          color: var(--text-secondary);
          font-family: 'JetBrains Mono', 'SF Mono', monospace;
          font-size: 12px;
          white-space: pre-wrap;
          word-break: break-all;
          max-height: 200px;
          overflow-y: auto;
        }
        .confirm-actions {
          display: flex;
          gap: 8px;
          justify-content: flex-end;
        }
        .confirm-actions button {
          padding: 8px 20px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
          cursor: pointer;
          font-size: 13px;
          font-family: var(--font-body);
          transition: var(--transition);
        }
        .confirm-actions .btn-approve {
          background: var(--accent);
          color: #0d0d14;
          border-color: var(--accent);
          font-weight: 500;
        }
        .confirm-actions .btn-approve:hover { background: var(--accent-hover); }
        .confirm-actions .btn-deny {
          background: transparent;
          color: var(--text-secondary);
        }
        .confirm-actions .btn-deny:hover { background: var(--bg-hover); color: var(--danger); border-color: var(--danger); }
      `}</style>
    </div>
  )
}
