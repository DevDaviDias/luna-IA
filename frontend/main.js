/**
 * LUNA v2 — Electron Main Process
 * Push-to-talk global: segure R para gravar, solte para transcrever.
 */

const { app, BrowserWindow, ipcMain, screen, globalShortcut } = require('electron');
const path   = require('path');
const http   = require('http');
const fs     = require('fs');
const { spawn } = require('child_process');

// ── uiohook-napi: único jeito confiável de detectar keyup global ──────────────
let uIOhook, UiohookKey;
try {
  const pkg  = require('uiohook-napi');
  uIOhook    = pkg.uIOhook;
  UiohookKey = pkg.UiohookKey;
} catch (e) {
  console.warn('[PTT] uiohook-napi não instalado — rode: npm install uiohook-napi');
}

const FRONTEND_PORT = 17420;

const JANELA = {
  compact:  { width: 300, height: 640 },
  expanded: { width: 360, height: 780 },
};

let mainWindow  = null;
let backendProc = null;
let httpServer  = null;
let isExpanded  = false;
let pttAtivo    = false;

// Keycode da tecla R (uiohook usa keycodes HID)
const R_KEYCODE = 0x0013; // keycode do R no uiohook-napi

// ── Mini servidor HTTP interno ────────────────────────────────────────────────

const ROOT = path.join(__dirname, '..');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript',
  '.css':  'text/css',
  '.vrm':  'application/octet-stream',
  '.glb':  'application/octet-stream',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.json': 'application/json',
};

function servirArquivo(res, filePath) {
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      res.writeHead(404); res.end('Not found'); return;
    }
    const ext  = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || 'application/octet-stream';
    res.writeHead(200, {
      'Content-Type':   mime,
      'Content-Length': stat.size,
      'Cache-Control':  'no-cache',
      'Access-Control-Allow-Origin': '*',
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

function iniciarServidorHTTP() {
  httpServer = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]);
    if (url === '/' || url === '/index.html') {
      servirArquivo(res, path.join(ROOT, 'frontend', 'index.html'));
    } else if (url.startsWith('/assets/')) {
      servirArquivo(res, path.join(ROOT, url));
    } else if (url.startsWith('/frontend/') || url.startsWith('/ui/')) {
      const rel = url.replace(/^\/(frontend|ui)\//, '');
      servirArquivo(res, path.join(ROOT, 'frontend', rel));
    } else {
      servirArquivo(res, path.join(ROOT, url));
    }
  });
  httpServer.listen(FRONTEND_PORT, '127.0.0.1', () => {
    console.log(`[Luna] Servidor interno: http://127.0.0.1:${FRONTEND_PORT}`);
  });
}

// ── Backend Python ────────────────────────────────────────────────────────────

function iniciarBackend() {
  const backendPath = path.join(ROOT, 'backend', 'main.py');
  const candidatos  = process.platform === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python'];

  function tentar(lista) {
    if (!lista.length) { console.error('[Luna] Python não encontrado!'); return; }
    const cmd  = lista[0];
    const proc = spawn(cmd, [backendPath], { cwd: ROOT, stdio: 'pipe' });
    proc.stdout.on('data', d => console.log('[Backend]', d.toString().trim()));
    proc.stderr.on('data', d => {
      const msg = d.toString().trim();
      if (!msg.includes('DeprecationWarning') && !msg.includes('Started server'))
        console.error('[Backend ERR]', msg);
    });
    proc.on('error', () => { console.warn(`[Luna] '${cmd}' falhou...`); tentar(lista.slice(1)); });
    proc.on('close', code => { if (code && code !== 0) console.error(`[Backend] código ${code}`); });
    backendProc = proc;
  }
  tentar(candidatos);
}

// ── Janela overlay ────────────────────────────────────────────────────────────

function criarJanela() {
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
  const size = JANELA.compact;

  mainWindow = new BrowserWindow({
    width:  size.width,
    height: size.height,
    x: sw - size.width  - 20,
    y: sh - size.height - 20,
    frame:       false,
    transparent: true,
    resizable:   true,
    alwaysOnTop: true,
    skipTaskbar: false,
    hasShadow:   false,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: false,
      autoplayPolicy: 'no-user-gesture-required',
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${FRONTEND_PORT}/`);
  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.setIgnoreMouseEvents(false);
}

// ── Push-to-Talk global via uiohook-napi ─────────────────────────────────────

// ── IPC ───────────────────────────────────────────────────────────────────────

// Mantido por compatibilidade, mas o keyup agora vem do uiohook
ipcMain.on('ptt:key-up', () => {
  if (!pttAtivo) return;
  pttAtivo = false;
  mainWindow?.webContents.send('ptt:stop');
});

ipcMain.on('win:close',    () => mainWindow?.close());
ipcMain.on('win:minimize', () => mainWindow?.minimize());
ipcMain.on('win:toggle-size', () => {
  if (!mainWindow) return;
  isExpanded = !isExpanded;
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
  const size = isExpanded ? JANELA.expanded : JANELA.compact;
  mainWindow.setSize(size.width, size.height, true);
  mainWindow.setPosition(sw - size.width - 20, sh - size.height - 20, true);
});

// ── App ───────────────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  iniciarServidorHTTP();
  iniciarBackend();
  setTimeout(() => {
    criarJanela();
    setTimeout(registrarPTT, 500);
  }, 1500);
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  uIOhook?.stop();
});

app.on('window-all-closed', () => {
  backendProc?.kill();
  httpServer?.close();
  globalShortcut.unregisterAll();
  uIOhook?.stop();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) criarJanela();
});