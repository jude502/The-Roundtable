const { app, BrowserWindow, shell, session, ipcMain } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')

const PORT = 8080
let mainWindow
let pythonProcess

function findPython() {
  const venvPython = path.join(__dirname, '..', 'venv', 'bin', 'python3')
  if (fs.existsSync(venvPython)) return venvPython
  return 'python3'
}

function startPythonServer() {
  const python = findPython()
  const cwd = path.join(__dirname, '..')
  pythonProcess = spawn(python, ['main.py'], { cwd })
  pythonProcess.stdout.on('data', d => console.log('[server]', d.toString().trim()))
  pythonProcess.stderr.on('data', d => console.error('[server]', d.toString().trim()))
  pythonProcess.on('close', code => console.log('[server] exited', code))
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#000000',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 20 },
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  // Open external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.loadURL(`http://localhost:${PORT}`, {
    extraHeaders: 'pragma: no-cache\nCache-Control: no-cache\n',
  })

  // Retry if server isn't ready yet
  mainWindow.webContents.on('did-fail-load', () => {
    setTimeout(() => mainWindow.loadURL(`http://localhost:${PORT}`), 1000)
  })
}

let dragState = null

ipcMain.on('drag-start', (_e, { x, y }) => {
  if (!mainWindow) return
  const [wx, wy] = mainWindow.getPosition()
  dragState = { startCursorX: x, startCursorY: y, startWinX: wx, startWinY: wy }
})

ipcMain.on('drag-move', (_e, { x, y }) => {
  if (!mainWindow || !dragState) return
  const dx = x - dragState.startCursorX
  const dy = y - dragState.startCursorY
  mainWindow.setPosition(dragState.startWinX + dx, dragState.startWinY + dy)
})

ipcMain.on('drag-end', () => { dragState = null })

app.whenReady().then(async () => {
  await session.defaultSession.clearCache()
  startPythonServer()
  setTimeout(createWindow, 2000)
})

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
