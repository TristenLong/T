const { app, BrowserWindow } = require('electron');

app.whenReady().then(() => {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    title: 'DIG DUG ARCADE - JESTER SYSTEM',
    autoHideMenuBar: true,
    alwaysOnTop: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    }
  });

  win.webContents.on('did-finish-load', () => {
    win.webContents.executeJavaScript(`
      const autoStart = () => {
        const btn = document.querySelector('.as-play-col') || 
                    Array.from(document.querySelectorAll('a, button, div')).find(b => (b.innerText || '').includes('Play Game'));
        if (btn) {
          btn.click();
        }
      };
      setTimeout(autoStart, 1500);
      setTimeout(autoStart, 4000);
    `).catch(() => {});
  });

  win.loadURL('https://arcadespot.com/game/dig-dug/');
  win.show();
  win.focus();
});
