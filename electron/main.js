/**
 * Blzazw — Electron 主进程
 *
 * 职责：
 * - 创建应用窗口（无菜单栏）
 * - 管理 Python 后端的生命周期
 * - API Key 安全存储
 * - 系统托盘
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog, safeStorage } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')
const fs = require('fs')
const { autoUpdater } = require('electron-updater')

// ──────────── 状态 ────────────
let mainWindow = null
let tray = null
let pythonProcess = null
const PYTHON_PORT = 8080
const PYTHON_URL = `http://127.0.0.1:${PYTHON_PORT}`
const isDev = !app.isPackaged

// ──────────── 自动更新 ────────────
autoUpdater.autoDownload = false
autoUpdater.autoInstallOnAppQuit = true

function setupAutoUpdate() {
  if (isDev) {
    console.log('[Blzazw] 开发模式，跳过自动更新检查')
    return
  }

  // 检查更新（静默）
  autoUpdater.checkForUpdates()

  autoUpdater.on('update-available', (info) => {
    console.log('[Blzazw] 发现新版本:', info.version)
    // 通知前端有新版本
    if (mainWindow) {
      mainWindow.webContents.send('update-available', info.version)
    }
  })

  autoUpdater.on('update-not-available', () => {
    console.log('[Blzazw] 已是最新版本')
  })

  autoUpdater.on('download-progress', (progress) => {
    const pct = Math.round(progress.percent)
    if (mainWindow) {
      mainWindow.webContents.send('update-progress', pct)
    }
  })

  autoUpdater.on('update-downloaded', () => {
    console.log('[Blzazw] 更新已下载，准备安装')
    if (mainWindow) {
      mainWindow.webContents.send('update-downloaded')
    }
  })

  autoUpdater.on('error', (err) => {
    console.error('[Blzazw] 自动更新错误:', err.message)
  })
}

// IPC：触发更新下载
ipcMain.handle('start-update-download', () => {
  autoUpdater.downloadUpdate()
  return { ok: true }
})

// IPC：立即安装更新
ipcMain.handle('install-update', () => {
  setImmediate(() => {
    autoUpdater.quitAndInstall()
  })
  return { ok: true }
})

function getPythonDir() {
  if (isDev) return path.join(__dirname, '..', 'agent')
  return path.join(process.resourcesPath, 'agent')
}

function getPythonExe() {
  // 优先用系统 Python，用户也可以自行修改
  try {
    // 尝试已知路径
    const testPath = 'E:\\python\\python.exe'
    if (fs.existsSync(testPath)) return testPath
  } catch (e) {}
  return 'python'
}

// ──────────── API Key 存储 ────────────
const CONFIG_PATH = path.join(app.getPath('userData'), 'blzazw-config.json')

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf-8')
      return JSON.parse(raw)
    }
  } catch (e) {
    console.error('[Blzazw] 配置读取失败:', e.message)
  }
  return {}
}

function saveConfig(data) {
  try {
    const dir = path.dirname(CONFIG_PATH)
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2), 'utf-8')
    return true
  } catch (e) {
    console.error('[Blzazw] 配置保存失败:', e.message)
    return false
  }
}

function getApiKey() {
  const config = loadConfig()
  if (config.apiKey && safeStorage.isEncryptionAvailable()) {
    // 如果有加密存储，尝试解密
    try {
      const buf = Buffer.from(config.apiKey, 'base64')
      return safeStorage.decryptString(buf)
    } catch (e) {
      // 解密失败，可能是跨机器
    }
  }
  return config.apiKeyPlain || ''
}

function setApiKey(key) {
  const config = loadConfig()
  if (safeStorage.isEncryptionAvailable()) {
    const encrypted = safeStorage.encryptString(key)
    config.apiKey = encrypted.toString('base64')
    delete config.apiKeyPlain
  } else {
    config.apiKeyPlain = key
  }
  return saveConfig(config)
}

// ──────────── Python 后端管理 ────────────
function startPythonBackend() {
  const agentDir = getPythonDir()
  const apiKey = getApiKey()
  console.log(`[Blzazw] 启动 Python 后端: ${agentDir}`)

  // 只传必要的环境变量，不传父进程的 PATH/APPDATA 等，彻底隔离
  const env = {
    DEEPSEEK_API_KEY: apiKey || '',
    PATH: process.env.PATH || '',
  }

  pythonProcess = spawn(getPythonExe(), ['run.py', '--server'], {
    cwd: agentDir,
    stdio: ['pipe', 'pipe', 'pipe'],
    env,
  })

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`)
  })
  pythonProcess.stderr.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`)
  })
  pythonProcess.on('error', (err) => {
    console.error('[Blzazw] Python 启动失败:', err.message)
  })
  pythonProcess.on('exit', (code) => {
    console.log(`[Blzazw] Python 进程退出 (代码: ${code})`)
    pythonProcess = null
  })
}

function stopPythonBackend() {
  if (pythonProcess) {
    console.log('[Blzazw] 停止 Python 后端')
    pythonProcess.kill('SIGTERM')
    setTimeout(() => {
      if (pythonProcess) pythonProcess.kill('SIGKILL')
    }, 3000)
  }
}

function waitForPython(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = (attempt) => {
      http.get(`${PYTHON_URL}/api/health`, (res) => {
        let data = ''
        res.on('data', (chunk) => { data += chunk })
        res.on('end', () => {
          console.log(`[Blzazw] Python 后端就绪 (尝试 ${attempt + 1})`)
          resolve()
        })
      }).on('error', () => {
        if (attempt < retries - 1) {
          setTimeout(() => check(attempt + 1), 500)
        } else {
          reject(new Error('Python 后端启动超时'))
        }
      })
    }
    check(0)
  })
}

// ──────────── 窗口 ────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 720,
    minWidth: 640,
    minHeight: 480,
    title: 'Blzazw',
    show: false,
    backgroundColor: '#0d0d14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.setMenu(null)

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  mainWindow.on('closed', () => { mainWindow = null })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.setTitle('Blzazw')
}

// ──────────── 系统托盘 ────────────
function createTray() {
  tray = new Tray(nativeImage.createEmpty())
  tray.setToolTip('Blzazw')

  const menu = Menu.buildFromTemplate([
    {
      label: '显示 Blzazw',
      click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus() } },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => { app.isQuitting = true; app.quit() },
    },
  ])
  tray.setContextMenu(menu)
  tray.on('click', () => {
    if (mainWindow) mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show()
  })
}

// ──────────── IPC 接口 ────────────
ipcMain.handle('get-app-info', () => ({
  version: app.getVersion(),
  pythonPort: PYTHON_PORT,
  pythonUrl: PYTHON_URL,
  isDev,
}))

ipcMain.handle('open-external', (e, url) => require('electron').shell.openExternal(url))

ipcMain.handle('has-api-key', () => {
  return !!getApiKey()
})

ipcMain.handle('save-api-key', async (e, key) => {
  // 先验证 Key：调 DeepSeek API 测试
  try {
    const testRes = await fetch('https://api.deepseek.com/v1/models', {
      headers: { 'Authorization': `Bearer ${key}` },
      signal: AbortSignal.timeout(10000),
    })
    if (!testRes.ok) {
      const body = await testRes.text().catch(() => '')
      return { ok: false, error: `API Key 无效 (HTTP ${testRes.status})` }
    }
  } catch (e) {
    if (e.name === 'TimeoutError' || e.code === 'ETIMEOUT') {
      return { ok: false, error: '验证超时，请检查网络连接' }
    }
    return { ok: false, error: `验证失败: ${e.message}` }
  }

  // Key 有效，保存
  const ok = setApiKey(key)
  if (ok) {
    stopPythonBackend()
    setTimeout(() => startPythonBackend(), 500)
    return { ok: true }
  }
  return { ok: false, error: 'Key 保存失败' }
})

ipcMain.handle('restart-backend', () => {
  stopPythonBackend()
  setTimeout(() => startPythonBackend(), 500)
  return { ok: true }
})

// ──────────── 应用生命周期 ────────────
app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  startPythonBackend()

  try {
    await waitForPython()
  } catch (e) {
    console.error('[Blzazw]', e.message)
  }

  createWindow()
  createTray()
  setupAutoUpdate()

  app.on('activate', () => {
    if (mainWindow === null) createWindow()
    else mainWindow.show()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  app.isQuitting = true
  stopPythonBackend()
})

app.on('will-quit', () => {
  stopPythonBackend()
})
