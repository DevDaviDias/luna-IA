/**
 * preload.js — Luna
 * Expõe API segura para o renderer via contextBridge.
 */
 
const { contextBridge, ipcRenderer } = require('electron');
 
contextBridge.exposeInMainWorld('electronAPI', {
  // Controles da janela
  close:      () => ipcRenderer.send('win:close'),
  minimize:   () => ipcRenderer.send('win:minimize'),
  toggleSize: () => ipcRenderer.send('win:toggle-size'),
 
  // Push-to-Talk — avisa o main que o R foi solto
  pttKeyUp: () => ipcRenderer.send('ptt:key-up'),
 
  // Recebe eventos de PTT do main process
  onPttStart: (cb) => ipcRenderer.on('ptt:start', cb),
  onPttStop:  (cb) => ipcRenderer.on('ptt:stop',  cb),
});
 