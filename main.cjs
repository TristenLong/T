process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true';
const { app, BrowserWindow, screen, globalShortcut, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const fs = require('node:fs');
const http = require('node:http');
const net = require('net');
const path = require('path');
const { loadOrCreateToken } = require('./jester-token.cjs');

let mainWindow;
const pythonProcesses = [];
let isClickThrough = true;
let rendererHost = null;

const FLASK_HOST = '127.0.0.1';
const FLASK_PORT = 5000;

// Is something already accepting connections there?
//
// start_jester.py now starts the backend too, because when Electron was its
// only owner a failed Electron launch left the UI running against a dead port
// with no error anywhere. Both launchers check first, so whichever wins starts
// the backend and the other attaches instead of racing for EADDRINUSE.
function isPortListening(port, host = FLASK_HOST, timeout = 750) {
    return new Promise((resolve) => {
        const socket = new net.Socket();
        let settled = false;
        const finish = (result) => {
            if (settled) return;
            settled = true;
            socket.destroy();
            resolve(result);
        };
        socket.setTimeout(timeout);
        socket.once('connect', () => finish(true));
        socket.once('timeout', () => finish(false));
        socket.once('error', () => finish(false));
        socket.connect(port, host);
    });
}

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

/*
 * Production renderer host.
 *
 * The window used to be loaded with loadFile(dist/index.html) in production,
 * i.e. over file://. Every backend call in the renderer is a relative
 * '/api/...' URL, and under file:// that resolves to file:///api/... -- so the
 * built app could not reach the backend at all and only the Vite dev server
 * ever worked. Serving dist/ over loopback HTTP and proxying /api exactly the
 * way vite.config.js does makes production behave identically to dev, keeps the
 * renderer on a single origin (so no CORS at all), and keeps the shared token
 * confined to the main process.
 */
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.map': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.wasm': 'application/wasm'
};

function proxyToBackend(req, res, url, apiToken) {
    const headers = { ...req.headers, host: `${FLASK_HOST}:${FLASK_PORT}` };
    if (apiToken) headers['x-jester-token'] = apiToken;
    // Compression would buffer server-sent events, and the HUD streams
    // /api/stream_events for its whole lifetime.
    delete headers['accept-encoding'];

    const upstream = http.request(
        {
            host: FLASK_HOST,
            port: FLASK_PORT,
            method: req.method,
            path: url.pathname + url.search,
            headers
        },
        (backendRes) => {
            res.writeHead(backendRes.statusCode || 502, backendRes.headers);
            backendRes.pipe(res);
        }
    );

    upstream.on('error', (err) => {
        console.error(`[RENDERER HOST] Backend proxy error for ${url.pathname}: ${err.message}`);
        if (!res.headersSent) {
            res.writeHead(502, { 'Content-Type': 'application/json' });
        }
        res.end(JSON.stringify({ error: 'BACKEND_UNREACHABLE', detail: err.message }));
    });

    req.pipe(upstream);
}

function serveStatic(distDir, pathname, res) {
    let decoded;
    try {
        decoded = decodeURIComponent(pathname);
    } catch {
        res.writeHead(400, { 'Content-Type': 'text/plain' });
        res.end('Bad request');
        return;
    }

    const relative = decoded === '/' ? 'index.html' : decoded.replace(/^\/+/, '');
    const target = path.resolve(distDir, relative);

    // Refuse anything that escapes dist/ -- '..' in a URL must not read the disk.
    if (target !== distDir && !target.startsWith(distDir + path.sep)) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
        return;
    }

    fs.readFile(target, (err, data) => {
        if (err) {
            // SPA fallback: an unknown path is a client-side route, not a 404.
            // Guarded on the name so a missing index.html cannot recurse.
            if (relative !== 'index.html') {
                serveStatic(distDir, '/', res);
                return;
            }
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('Not found');
            return;
        }
        res.writeHead(200, {
            'Content-Type':
                MIME_TYPES[path.extname(target).toLowerCase()] || 'application/octet-stream',
            'Cache-Control': 'no-store'
        });
        res.end(data);
    });
}

function startRendererHost(distDir, apiToken) {
    return new Promise((resolve, reject) => {
        const server = http.createServer((req, res) => {
            const url = new URL(req.url, 'http://127.0.0.1');
            if (url.pathname.startsWith('/api/')) {
                proxyToBackend(req, res, url, apiToken);
            } else {
                serveStatic(distDir, url.pathname, res);
            }
        });

        server.once('error', reject);
        // Port 0: let the OS pick a free one. Nothing external needs to find us,
        // so a fixed port would only create another collision to debug.
        server.listen(0, '127.0.0.1', () => {
            resolve({ server, port: server.address().port });
        });
    });
}

async function createWindow() {
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
                nodeIntegration: false,
                contextIsolation: true,
                sandbox: false,
                webSecurity: false
            }
        });

        // Puter's free AI tier signs you in via a popup (the js.puter.com SDK
        // flow); Electron blocks window.open by default. Allow the puter.com
        // login so the one-time auth popup can open and postMessage back.
        // Any other http(s) link opens in the system's default browser instead
        // of a blocked popup (images from DREAM CORE, WEB SCOUT lookups, ...).
        mainWindow.webContents.setWindowOpenHandler(({ url }) => {
            if (url.startsWith('https://puter.com') || url.startsWith('http://puter.com')) {
                return { action: 'allow' };
            }
            if (url.startsWith('http://') || url.startsWith('https://')) {
                shell.openExternal(url).catch(err => console.log(`[ELECTRON] openExternal failed: ${err.message}`));
                return { action: 'deny' };
            }
            console.log(`[ELECTRON] Blocked popup to: ${url}`);
            return { action: 'deny' };
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
            let prodUrl = null;
            try {
                const distDir = path.resolve(__dirname, 'dist');
                const { server, port } = await startRendererHost(distDir, loadOrCreateToken());
                rendererHost = server;
                prodUrl = `http://127.0.0.1:${port}/`;
                console.log(`[ELECTRON] Serving dist/ on ${prodUrl}`);
            } catch (err) {
                console.error(`[ELECTRON] Could not start renderer host: ${err.message}`);
            }

            if (destroyed || !mainWindow) return;

            if (prodUrl) {
                mainWindow.loadURL(prodUrl);
            } else {
                // Last resort. Relative /api calls cannot work under file://, but
                // showing the UI with a dead backend beats showing nothing.
                console.warn('[ELECTRON] Falling back to file:// -- API calls will fail.');
                mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
            }
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

app.on('ready', async () => {
    console.log('[ELECTRON] App ready event fired.');
    // 1. Boot the Python Servers in the background
    const rootDir = __dirname;
    const godHandDir = path.join(rootDir, 'GOD_HAND_CORE');

    // Launch the unified API server from GOD_HAND_CORE using uv
    if (await isPortListening(FLASK_PORT)) {
        console.log(
            `[SYSTEM] Flask API already listening on ${FLASK_HOST}:${FLASK_PORT}; ` +
            'attaching instead of spawning a duplicate.'
        );
    } else {
        startPythonService('Flask API', 'uv', ['run', 'python', 'server.py'], godHandDir);
    }
    // Clean boot guards: if a previous session already owns these service
    // ports, attach instead of spawning a crash-on-bind duplicate.
    if (await isPortListening(7860)) {
        console.log('[SYSTEM] Voice Core already listening on :7860; attaching.');
    } else {
        startPythonService('God Hand Voice Core', 'uv', ['run', 'python', 'bot.py', '--transport', 'webrtc'], godHandDir);
    }
    if (await isPortListening(8765)) {
        console.log('[SYSTEM] Science Engine already listening on :8765; attaching.');
    } else {
        startPythonService('Science Engine', 'uv', ['run', 'python', 'realtime_science_engine.py'], godHandDir);
    }

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
