/**
 * LUNA v2 — Electron Main Process
 * Sobe um servidor HTTP local para servir o frontend e assets,
 * depois carrega via http://localhost — sem problemas de CORS ou file://.
 */

const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path   = require('path');
const http   = require('http');
const fs     = require('fs');
const { spawn } = require('child_process');

const FRONTEND_PORT = 17420; // porta interna do mini-servidor Electron

const JANELA = {
  compact:  { width: 330, height: 640 },
  expanded: { width: 330, height: 640 },
};

let mainWindow  = null;
let backendProc = null;
let httpServer  = null;
let isExpanded  = false;

// ── Mini servidor HTTP interno ────────────────────────────────────────────────
// Serve frontend/ e assets/ na mesma origem → sem CORS para o VRM

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
    // Remove query string e decodifica URI
    const url = decodeURIComponent(req.url.split('?')[0]);

    if (url === '/' || url === '/index.html') {
      servirArquivo(res, path.join(ROOT, 'frontend', 'index.html'));
    } else if (url.startsWith('/assets/')) {
      servirArquivo(res, path.join(ROOT, url));
    } else if (url.startsWith('/frontend/') || url.startsWith('/ui/')) {
      const rel = url.replace(/^\/(frontend|ui)\//, '');
      servirArquivo(res, path.join(ROOT, 'frontend', rel));
    } else {
      // Tenta servir da raiz do projeto
      const candidate = path.join(ROOT, url);
      servirArquivo(res, candidate);
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
    if (!lista.length) {
      console.error('[Luna] Python não encontrado! Instale Python 3.10+');
      return;
    }
    const cmd  = lista[0];
    const proc = spawn(cmd, [backendPath], { cwd: ROOT, stdio: 'pipe' });

    proc.stdout.on('data', d => console.log('[Backend]', d.toString().trim()));
    proc.stderr.on('data', d => {
      const msg = d.toString().trim();
      if (!msg.includes('DeprecationWarning') && !msg.includes('Started server')) {
        console.error('[Backend ERR]', msg);
      }
    });
    proc.on('error', () => {
      console.warn(`[Luna] '${cmd}' falhou, tentando próximo...`);
      tentar(lista.slice(1));
    });
    proc.on('close', code => {
      if (code && code !== 0) console.error(`[Backend] código ${code}`);
    });

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
    x: sw - size.width  - 0,
    y: sh - size.height - 0,

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
    },
  });

  // Carrega via HTTP local — VRM e assets ficam na mesma origem
  mainWindow.loadURL(`http://127.0.0.1:${FRONTEND_PORT}/`);

  // Overlay acima de tudo
  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.setIgnoreMouseEvents(false);
}

// ── IPC ───────────────────────────────────────────────────────────────────────

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
  // Aguarda o servidor HTTP subir antes de abrir a janela
  setTimeout(criarJanela, 1500);
});

app.on('window-all-closed', () => {
  backendProc?.kill();
  httpServer?.close();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) criarJanela();
});
