import React from 'react'
import { SessionInfo } from '../types'

interface SidebarProps {
  sessions: SessionInfo[]
  currentSession: string
  onSelect: (id: string) => void
  onNew: () => void
  open: boolean
  onClose: () => void
}

export default function Sidebar({ sessions, currentSession, onSelect, onNew, open, onClose }: SidebarProps) {
  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-header">
          <span className="sidebar-brand">Blzazw <em>✦</em></span>
          <button className="sidebar-new-btn" onClick={onNew} title="新对话">+</button>
        </div>
        <div className="sidebar-list">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`session-item ${s.id === currentSession ? 'active' : ''}`}
              onClick={() => { onSelect(s.id); onClose() }}
              title={s.preview}
            >
              {s.preview}
            </div>
          ))}
        </div>
      </aside>

      <style>{`
        .sidebar-overlay {
          display: none;
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.4);
          z-index: 90;
        }
        .sidebar {
          width: 240px;
          min-width: 240px;
          background: var(--bg-secondary);
          border-right: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          z-index: 100;
          transition: transform 0.25s cubic-bezier(0.4,0,0.2,1);
        }
        .sidebar-header {
          padding: 20px 16px 16px;
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .sidebar-brand {
          font-family: var(--font-display);
          font-size: 18px;
          font-weight: 600;
          color: var(--accent);
          letter-spacing: 0.5px;
        }
        .sidebar-brand em {
          font-style: italic;
          color: var(--text-muted);
          font-size: 14px;
        }
        .sidebar-new-btn {
          width: 32px; height: 32px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-secondary);
          font-size: 18px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: var(--transition);
        }
        .sidebar-new-btn:hover {
          background: var(--bg-hover);
          color: var(--accent);
          border-color: var(--accent);
        }
        .sidebar-list {
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }
        .session-item {
          padding: 10px 12px;
          border-radius: var(--radius-sm);
          cursor: pointer;
          margin-bottom: 2px;
          transition: var(--transition);
          color: var(--text-secondary);
          font-size: 13px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .session-item:hover { background: var(--bg-hover); color: var(--text-primary); }
        .session-item.active {
          background: var(--bg-tertiary);
          color: var(--text-primary);
          border-left: 2px solid var(--accent);
          padding-left: 10px;
        }
        @media (max-width: 768px) {
          .sidebar {
            position: fixed;
            top: 0; left: 0; bottom: 0;
            transform: translateX(-100%);
          }
          .sidebar.open { transform: translateX(0); }
          .sidebar-overlay { display: block; }
        }
      `}</style>
    </>
  )
}
