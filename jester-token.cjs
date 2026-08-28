/*
 * Shared token loader for the Node side of JESTER (Vite config + Electron main).
 *
 * The Flask backend requires an X-Jester-Token header on /api/* (see
 * GOD_HAND_CORE/jester_auth.py). Anything running in Node can read that token
 * off disk, which is what keeps the secret out of the browser entirely --
 * including out of EventSource, which cannot set request headers at all.
 *
 * This is a .cjs module on purpose: package.json sets "type": "module", so a
 * plain .js file here would be ESM and lose __dirname. main.cjs requires it
 * directly; vite.config.js reaches it through createRequire.
 */

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const TOKEN_FILE =
  process.env.JESTER_TOKEN_FILE ||
  path.resolve(__dirname, 'GOD_HAND_CORE', '.jester_token');

function loadOrCreateToken() {
  if (process.env.JESTER_API_TOKEN) return process.env.JESTER_API_TOKEN.trim();

  try {
    const existing = fs.readFileSync(TOKEN_FILE, 'utf8').trim();
    if (existing) return existing;
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.warn(`[jester-token] Could not read ${TOKEN_FILE}: ${err.message}`);
      return null;
    }
  }

  // Vite, Electron and Flask all race to start, so whichever gets here first
  // creates the token. 'wx' fails instead of clobbering, so the loser re-reads
  // the winner's value rather than the two disagreeing about the secret.
  const token = crypto.randomBytes(32).toString('base64url');
  try {
    fs.mkdirSync(path.dirname(TOKEN_FILE), { recursive: true });
    fs.writeFileSync(TOKEN_FILE, token, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
    return token;
  } catch (err) {
    if (err.code === 'EEXIST') {
      try {
        return fs.readFileSync(TOKEN_FILE, 'utf8').trim() || null;
      } catch {
        return null;
      }
    }
    console.warn(`[jester-token] Could not create ${TOKEN_FILE}: ${err.message}`);
    return null;
  }
}

module.exports = { TOKEN_FILE, loadOrCreateToken };
