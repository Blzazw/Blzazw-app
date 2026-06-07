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
  on: (channel, callback) => {
    const valid = ['python-status']
    if (valid.includes(channel)) {
      ipcRenderer.on(channel, (event, ...args) => callback(...args))
    }
  },
  removeAllListeners: (channel) => { ipcRenderer.removeAllListeners(channel) },
})
