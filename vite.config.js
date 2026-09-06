import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import { createRequire } from 'node:module'

// The Flask backend now requires a shared token on /api/* (see
// GOD_HAND_CORE/jester_auth.py). This config runs in Node, so it can read that
// token from disk and inject it into every proxied request. That keeps the
// secret out of the browser entirely and means the React app needs no changes
// at all -- crucially including EventSource, which cannot set request headers.
//
// The loader lives in jester-token.cjs so Electron's main process uses the exact
// same file-and-race logic. package.json sets "type": "module", so this config
// is ESM and has no __dirname; createRequire bridges to the CJS helper, which
// does.
const require = createRequire(import.meta.url)
const { TOKEN_FILE, loadOrCreateToken } = require('./jester-token.cjs')

const apiToken = loadOrCreateToken()
if (!apiToken) {
  console.warn(
    `[vite] No Jester API token available (${TOKEN_FILE}); proxied /api requests ` +
      'will be rejected with 401. Start the backend once, or set JESTER_API_TOKEN.'
  )
}

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
        // Dropped a `rewrite: path => path.replace(/^\/api/, '/api')` here: it
        // substituted '/api' for '/api', i.e. did nothing.
        ...(apiToken ? { headers: { 'X-Jester-Token': apiToken } } : {})
      }
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setupTests.jsx',
    include: ['src/App.test.jsx']
  }
})
