/**
 * preload.js
 * Expõe API segura para o renderer (index.html) via contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  close:      () => ipcRenderer.send('win:close'),
  minimize:   () => ipcRenderer.send('win:minimize'),
  toggleSize: () => ipcRenderer.send('win:toggle-size'),
});
