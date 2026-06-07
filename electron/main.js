/**
 * Blzazw — Electron 主进程
 */
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog, safeStorage } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')
const fs = require('fs')
const { autoUpdater } = require('electron-updater')

// 文件日志（按日期轮转，本地时间）
function getLogPath() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return path.join(app.getPath('userData'), `blzazw-${y}${m}${day}.log`)
}
function log(...args) {
  const msg = args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ')
  const d = new Date()
  const time = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
  const line = `[${time}] ${msg}`
  console.log(line)
  try { fs.appendFileSync(getLogPath(), line + '\n') } catch (e) {}
}

let mainWindow = null, tray = null, pythonProcess = null
const PYTHON_PORT = 8080
const PYTHON_URL = `http://127.0.0.1:${PYTHON_PORT}`
const isDev = !app.isPackaged
let startupTime = Date.now()

// 自动更新
autoUpdater.autoDownload = false
autoUpdater.autoInstallOnAppQuit = true
function setupAutoUpdate() {
  log('[Blzazw] 自动更新已禁用（等待 Release 配置）')
}

// IPC：更新下载
ipcMain.handle('start-update-download', () => { autoUpdater.downloadUpdate(); return { ok: true } })
ipcMain.handle('install-update', () => { setImmediate(() => autoUpdater.quitAndInstall()); return { ok: true } })

// Python 路径
function getPythonDir() {
  return isDev ? path.join(__dirname, '..', 'agent') : path.join(process.resourcesPath, 'agent')
}
function getPythonExe() {
  try { if (fs.existsSync('E:\\python\\python.exe')) return 'E:\\python\\python.exe' } catch (e) {}
  return 'python'
}

// API Key 存储
const CONFIG_PATH = path.join(app.getPath('userData'), 'blzazw-config.json')
function loadConfig() {
  try { if (fs.existsSync(CONFIG_PATH)) return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8')) } catch (e) { log('[Blzazw] 配置读取失败:', e.message) }
  return {}
}
function saveConfig(data) {
  try {
    const dir = path.dirname(CONFIG_PATH)
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2), 'utf-8')
    return true
  } catch (e) { log('[Blzazw] 配置保存失败:', e.message); return false }
}
function getApiKey() {
  const config = loadConfig()
  if (config.apiKey && safeStorage.isEncryptionAvailable()) {
    try { return safeStorage.decryptString(Buffer.from(config.apiKey, 'base64')) } catch (e) {}
  }
  return config.apiKeyPlain || ''
}
function setApiKey(key) {
  const config = loadConfig()
  if (safeStorage.isEncryptionAvailable()) {
    config.apiKey = safeStorage.encryptString(key).toString('base64')
    delete config.apiKeyPlain
  } else { config.apiKeyPlain = key }
  return saveConfig(config)
}

// Python 后端管理
function startPythonBackend() {
  const agentDir = getPythonDir()
  const apiKey = getApiKey()
  log('[Blzazw] 启动 Python 后端:', agentDir)
  const env = { ...process.env }
  env.DEEPSEEK_API_KEY = apiKey || ''
  env.BLZAZW_SESSIONS_DIR = path.join(app.getPath('userData'), 'sessions')
  // 强制 Python 使用系统的 SSL 证书和代理设置
  env.SSL_CERT_FILE = process.env.SSL_CERT_FILE || ''
  env.REQUESTS_CA_BUNDLE = process.env.REQUESTS_CA_BUNDLE || ''
  env.HTTPS_PROXY = process.env.HTTPS_PROXY || process.env.HTTPS_PROXY || ''
  env.HTTP_PROXY = process.env.HTTP_PROXY || process.env.http_proxy || ''
  env.NO_PROXY = process.env.NO_PROXY || ''
  pythonProcess = spawn(getPythonExe(), ['run.py', '--server'], {
    cwd: agentDir, stdio: ['pipe', 'pipe', 'pipe'], env,
  })
  pythonProcess.stdout.on('data', (d) => log('[Python]', d.toString().trim()))
  pythonProcess.stderr.on('data', (d) => log('[Python]', d.toString().trim()))
  pythonProcess.on('error', (err) => log('[Blzazw] Python 启动失败:', err.message))
  pythonProcess.on('exit', (code) => { log('[Blzazw] Python 进程退出 (代码:', code, ')'); pythonProcess = null })
}
function stopPythonBackend() {
  if (Date.now() - startupTime < 15000) { log('[Blzazw] 启动保护：跳过停止 Python 后端'); return }
  if (pythonProcess) {
    const stack = new Error().stack.split('\n').slice(2, 5).join(' -> ')
    log('[Blzazw] 停止 Python 后端 (来自:', stack, ')')
    pythonProcess.kill('SIGTERM')
    setTimeout(() => { if (pythonProcess) pythonProcess.kill('SIGKILL') }, 3000)
  }
}
function waitForPython(retries = 60) {
  return new Promise((resolve, reject) => {
    const check = (attempt) => {
      http.get(`${PYTHON_URL}/api/health`, (res) => {
        res.on('data', () => {})
        res.on('end', () => { log('[Blzazw] Python 后端就绪 (尝试', attempt + 1, ')'); resolve() })
      }).on('error', () => {
        if (attempt < retries - 1) setTimeout(() => check(attempt + 1), 500)
        else reject(new Error('Python 后端启动超时'))
      })
    }
    check(0)
  })
}

// 窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960, height: 720, minWidth: 640, minHeight: 480,
    title: 'Blzazw', show: false, backgroundColor: '#0d0d14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false,
    },
  })
  mainWindow.setMenu(null)
  mainWindow.once('ready-to-show', () => mainWindow.show())
  if (isDev) mainWindow.loadURL('http://localhost:5173')
  else mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  mainWindow.on('closed', () => { mainWindow = null })

  // 崩溃自动恢复
  mainWindow.webContents.on('crashed', () => {
    log('[Blzazw] 渲染进程崩溃，正在重启窗口...')
    setTimeout(() => {
      if (mainWindow) { mainWindow.destroy(); mainWindow = null }
      createWindow()
    }, 1000)
  })
  mainWindow.webContents.on('unresponsive', () => log('[Blzazw] 渲染进程无响应，等待恢复...'))
  mainWindow.webContents.on('responsive', () => log('[Blzazw] 渲染进程已恢复'))

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url); return { action: 'deny' }
  })
  mainWindow.setTitle('Blzazw')
}

// 系统托盘
function createTray() {
  tray = new Tray(nativeImage.createEmpty())
  tray.setToolTip('Blzazw')
  const menu = Menu.buildFromTemplate([
    { label: '显示 Blzazw', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus() } } },
    { type: 'separator' },
    { label: '退出', click: () => { app.isQuitting = true; app.quit() } },
  ])
  tray.setContextMenu(menu)
  tray.on('click', () => { if (mainWindow) mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show() })
}

// IPC
ipcMain.handle('get-app-info', () => ({ version: app.getVersion(), pythonPort: PYTHON_PORT, pythonUrl: PYTHON_URL, isDev }))
ipcMain.handle('open-external', (e, url) => require('electron').shell.openExternal(url))
ipcMain.handle('has-api-key', () => !!getApiKey())
ipcMain.handle('save-api-key', async (e, key) => {
  try {
    const testRes = await fetch('https://api.deepseek.com/v1/models', {
      headers: { 'Authorization': `Bearer ${key}` },
      signal: AbortSignal.timeout(30000),
    })
    if (!testRes.ok) return { ok: false, error: 'API Key 无效' }
  } catch (e) {
    if (e.name === 'TimeoutError' || e.code === 'ETIMEOUT') return { ok: false, error: '验证超时，请检查网络连接' }
    return { ok: false, error: '验证失败: ' + e.message }
  }
  if (setApiKey(key)) {
    stopPythonBackend()
    await new Promise((r) => setTimeout(r, 1500))
    startPythonBackend()
    try { await waitForPython(); return { ok: true } }
    catch (e) { return { ok: false, error: '后端启动超时' } }
  }
  return { ok: false, error: 'Key 保存失败' }
})
ipcMain.handle('restart-backend', () => { stopPythonBackend(); setTimeout(() => startPythonBackend(), 500); return { ok: true } })

// 全局异常捕获
process.on('uncaughtException', (err) => log('[Blzazw] 未捕获异常:', err.message))
process.on('unhandledRejection', (reason) => log('[Blzazw] 未处理的 Promise 异常:', reason?.message || reason))

// 应用生命周期
app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  startPythonBackend()
  try { await waitForPython() } catch (e) { log('[Blzazw]', e.message) }
  createWindow()
  createTray()
  setupAutoUpdate()
  app.on('activate', () => { mainWindow === null ? createWindow() : mainWindow.show() })
})
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('before-quit', () => { app.isQuitting = true; stopPythonBackend() })
app.on('will-quit', () => { stopPythonBackend() })
