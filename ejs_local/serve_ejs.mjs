// Local EmulatorJS harness for the JESTER web-agent.
//
// Serves a self-hosted EJS build (data/ + cores/) on 127.0.0.1:8801 so the
// agent gets a stable, ad/menu-free Dig Dug page we fully control. ROMs and
// BIOS are streamed through same-origin /rom and /bios proxies (removes CORS
// and keeps the copyrighted bits out of this tree).
//
//   node serve_ejs.mjs [port]
import http from 'http';
import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.argv[2] || 8801);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm',
  '.data': 'application/octet-stream',
  '.zip': 'application/octet-stream',
  '.7z': 'application/x-7z-compressed',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

// same-origin proxies: local URL -> remote target that the browser already
// downloads when you open the mirror embed.
const PROXIES = {
  'rom/digdug.zip': 'https://files6.retrogames.cc/MndKa1p4bm42SlZubVpScENaWG5aQlpoMzJlb0xKR1ZpckYwajZ3ODIrR3JtS0pBYW1ZdFZBR3MxVVFwbUNlb2oyaW5LVHBqeWdsd2R3PT0%3D/digdug.zip',
  'bios/arcade.7z': 'https://www.retrogames.cc/bios/arcade.7z',
};

function send(res, code, body, type) {
  res.writeHead(code, {
    'Content-Type': type || 'text/plain; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function proxy(req, res, target) {
  console.log(`PROXY ${req.url} -> ${target.replace(/([^/]+)$/, '$1')}`);
  const mod = /^https:/.test(target) ? https : http;
  const upstream = mod.request(target, { method: 'GET', headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' } }, (up) => {
    if (up.statusCode >= 300 && up.statusCode < 400 && up.headers.location) {
      up.resume();
      proxy(req, res, new URL(up.headers.location, target).href);
      return;
    }
    if (up.statusCode !== 200) { up.resume(); send(res, up.statusCode, `upstream ${up.statusCode}: ${target}`); return; }
    res.writeHead(200, {
      'Content-Type': up.headers['content-type'] || 'application/octet-stream',
      'Content-Length': up.headers['content-length'],
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=86400',
    });
    up.pipe(res);
  });
  upstream.on('error', (e) => send(res, 502, `proxy error: ${e.message}`));
  upstream.end();
}

const server = http.createServer((req, res) => {
  const url = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '');
  if (url === 'health') return send(res, 200, 'ok');

  const rel = PROXIES[url];
  if (rel) return proxy(req, res, rel);

  const file = url || 'host_digdug.html';
  const abs = path.resolve(ROOT, file);
  if (!abs.startsWith(ROOT)) return send(res, 403, 'forbidden');

  fs.readFile(abs, (err, buf) => {
    if (err) return send(res, 404, `not found: /${file}`);
    send(res, 200, buf, MIME[path.extname(abs).toLowerCase()] || 'application/octet-stream');
  });
});

server.listen(PORT, '127.0.0.1', () => console.log(`JESTER EJS harness on http://127.0.0.1:${PORT}/  (root: ${ROOT})`));