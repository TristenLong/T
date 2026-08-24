const { app, BrowserWindow, screen, globalShortcut, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow;
const pythonProcesses = [];
let isClickThrough = true;

// Helper to spawn a python process safely
function startPythonService(name, command, args, cwd) {
    console.log(`[SYSTEM] Starting ${name}...`);
    
    const proc = spawn(command, args, {
        cwd: cwd,
        shell: true
    });

    // Without an 'error' listener a failed spawn (e.g. 'uv' not on PATH) emits
    // an unhandled 'error' event, which crashes the whole Electron process.
    proc.on('error', (err) => {
        console.error(`[${name} SPAWN ERROR] ${err.message}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('process-log', {
                source: name,
                type: 'error',
                message: `Failed to start: ${err.message}`
            });
        }
    });

    proc.stdout.on('data', (data) => {
        const msg = data.toString().trim();
        if (!msg) return;
        console.log(`[${name}] ${msg}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('process-log', { source: name, type: 'info', message: msg });
        }
    });

    proc.stderr.on('data', (data) => {
        const msg = data.toString().trim();
        if (!msg) return;
        console.error(`[${name} ERROR] ${msg}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('process-log', { source: name, type: 'error', message: msg });
        }
    });

    proc.on('close', (code) => {
        console.log(`[${name}] exited with code ${code}`);
    });

    pythonProcesses.push(proc);
}

function createWindow() {
    console.log('[ELECTRON] Inside createWindow()...');
    try {
        // Get screen size for HUD positioning
        const { width, height, x, y } = screen.getPrimaryDisplay().bounds;
        console.log(`[ELECTRON] Screen bounds: ${width}x${height} at ${x},${y}`);

        // Create the standard window
        mainWindow = new BrowserWindow({
            width: 1280,
            height: 800,
            transparent: false,
            backgroundColor: '#000000',
            frame: true,
            alwaysOnTop: false,
            resizable: true,
            skipTaskbar: false,
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
                webSecurity: false
            }
        });

        let destroyed = false;
        mainWindow.on('closed', function () {
            console.log('[ELECTRON] Window closed.');
            destroyed = true;
            mainWindow = null;
        });

        // Ghost mode (click-through) disabled for normal window operation.

        console.log('[ELECTRON] BrowserWindow created.');

        // In development mode, load Vite dev server
        // In production, load built index.html
        const startUrl = process.env.ELECTRON_START_URL || 'http://127.0.0.1:5173';

        const isDev = process.argv.includes('--dev');
        if (isDev) {
            console.log(`[ELECTRON] Loading dev server: ${startUrl}`);
            // Vite may not have bound its port yet, so retry until it does.
            // Guarded on `destroyed` -- without it the timer keeps firing after
            // the window is gone and loadURL throws on a destroyed object.
            const loadWithRetry = () => {
                if (destroyed || !mainWindow) return;
                mainWindow.loadURL(startUrl).catch((err) => {
                    if (destroyed || !mainWindow) return;
                    console.log(`[ELECTRON] Connection failed, retrying in 1s... (${err.message})`);
                    setTimeout(loadWithRetry, 1000);
                });
            };
            loadWithRetry();
        } else {
            console.log(`[ELECTRON] Loading local file: dist/index.html`);
            mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
        }

        // Dev-only. This was previously unconditional, which opened a detached
        // DevTools window in production builds too.
        if (isDev) {
            mainWindow.webContents.openDevTools({ mode: 'detach' });
        }

        mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
            console.log(`[CLIENT-LOG] ${message}`);
        });
    } catch (e) {
        console.error('[ELECTRON] Error in createWindow:', e);
    }
}

app.on('ready', () => {
    console.log('[ELECTRON] App ready event fired.');
    // 1. Boot the Python Servers in the background
    const rootDir = __dirname;
    const godHandDir = path.join(rootDir, 'GOD_HAND_CORE');

    // Launch the unified API server from GOD_HAND_CORE using uv
    startPythonService('Flask API', 'uv', ['run', 'python', 'server.py'], godHandDir);
    startPythonService('Science Engine', 'uv', ['run', 'python', 'realtime_science_engine.py'], godHandDir);
    // Use uv run to ensure GOD_HAND_CORE gets its proper virtual environment dependencies
    startPythonService('God Hand Voice Core', 'uv', ['run', 'python', 'bot.py', '--transport', 'webrtc'], godHandDir);

    // 2. Create the HUD Window
    // Give servers a tiny bit of time to bind to their ports
    console.log('[ELECTRON] Setting timeout for createWindow...');
    setTimeout(() => {
        console.log('[ELECTRON] Timeout finished, calling createWindow.');
        createWindow();
    }, 2000);
});

function killPythonProcesses() {
    pythonProcesses.forEach(proc => {
        if (!proc.killed) {
            try {
                if (process.platform === 'win32') {
                    require('child_process').execSync(`taskkill /pid ${proc.pid} /T /F`);
                } else {
                    process.kill(-proc.pid);
                }
            } catch (e) {
                console.log(`[ELECTRON] Could not kill proc ${proc.pid}:`, e);
            }
        }
    });
}

app.on('window-all-closed', function () {
    killPythonProcesses();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('quit', () => {
    killPythonProcesses();
});
