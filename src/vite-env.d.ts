/// <reference types="vite/client" />

interface Window {
  blzazw: {
    getAppInfo: () => Promise<{
      version: string
      pythonPort: number
      pythonUrl: string
      isDev: boolean
    }>
    openExternal: (url: string) => Promise<void>
    hasApiKey: () => Promise<boolean>
    saveApiKey: (key: string) => Promise<{ ok: boolean; error?: string }>
    restartBackend: () => Promise<{ ok: boolean }>

    // 自动更新
    onUpdateAvailable: (callback: (version: string) => void) => void
    onUpdateProgress: (callback: (pct: number) => void) => void
    onUpdateDownloaded: (callback: () => void) => void
    startUpdateDownload: () => Promise<{ ok: boolean }>
    installUpdate: () => Promise<{ ok: boolean }>

    on: (channel: string, callback: (...args: any[]) => void) => void
    removeAllListeners: (channel: string) => void
  }
}
