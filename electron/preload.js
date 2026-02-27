const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  dragStart: (x, y) => ipcRenderer.send('drag-start', { x, y }),
  dragMove: (x, y) => ipcRenderer.send('drag-move', { x, y }),
  dragEnd:  ()     => ipcRenderer.send('drag-end'),
})
