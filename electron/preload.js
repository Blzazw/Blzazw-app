/**
 * Blzazw — Preload 脚本
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('blzazw', {
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  hasApiKey: () => ipcRenderer.invoke('has-api-key'),
  saveApiKey: (key) => ipcRenderer.invoke('save-api-key', key),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),

  // 自动更新
  onUpdateAvailable: (callback) => {
    ipcRenderer.on('update-available', (e, version) => callback(version))
  },
  onUpdateProgress: (callback) => {
    ipcRenderer.on('update-progress', (e, pct) => callback(pct))
  },
  onUpdateDownloaded: (callback) => {
    ipcRenderer.on('update-downloaded', () => callback())
  },
  startUpdateDownload: () => ipcRenderer.invoke('start-update-download'),
  installUpdate: () => ipcRenderer.invoke('install-update'),

  on: (channel, callback) => {
    const valid = ['python-status']
    if (valid.includes(channel)) {
      ipcRenderer.on(channel, (event, ...args) => callback(...args))
    }
  },
  removeAllListeners: (channel) => { ipcRenderer.removeAllListeners(channel) },
})
