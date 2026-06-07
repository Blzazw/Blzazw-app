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
    on: (channel: string, callback: (...args: any[]) => void) => void
    removeAllListeners: (channel: string) => void
  }
}
