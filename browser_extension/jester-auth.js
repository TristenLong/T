/* global chrome */
/*
 * Shared-secret auth for the local JESTER backend.
 *
 * The Flask server now requires an X-Jester-Token header on /api/* (see
 * GOD_HAND_CORE/jester_auth.py). Without it every request comes back 401.
 *
 * An extension cannot read the token file off disk, so unlike the Vite proxy and
 * the Python clients it cannot pick the token up automatically -- the user pastes
 * it in once from the popup. That is the whole point: it is what stops any *other*
 * extension the user has installed from quietly calling /api/sandbox.
 */

const JESTER_TOKEN_KEY = 'jesterApiToken';
const JESTER_TOKEN_HEADER = 'X-Jester-Token';

async function getJesterToken() {
  try {
    const stored = await chrome.storage.local.get(JESTER_TOKEN_KEY);
    return (stored && stored[JESTER_TOKEN_KEY]) || '';
  } catch (err) {
    console.warn('[JESTER] Could not read stored token:', err);
    return '';
  }
}

async function setJesterToken(token) {
  await chrome.storage.local.set({ [JESTER_TOKEN_KEY]: (token || '').trim() });
}

async function jesterHeaders(extra = {}) {
  const token = await getJesterToken();
  const headers = { 'Content-Type': 'application/json', ...extra };
  if (token) headers[JESTER_TOKEN_HEADER] = token;
  return headers;
}

/*
 * A 401 is not a connectivity problem, so callers must not treat it as one and
 * retry the next host in their fallback list -- that just produces four
 * identical failures and an unhelpful "could not connect" message. The
 * `jesterAuth` flag lets a catch block re-throw it without string-matching the
 * message, which breaks the moment the wording changes.
 */
function jesterAuthError() {
  const err = new Error(
    'JESTER rejected the request (401). Paste the token from ' +
      'GOD_HAND_CORE/.jester_token into the API TOKEN box in this extension ' +
      "(the popup, or the side panel if that is what the toolbar icon opens)."
  );
  err.jesterAuth = true;
  return err;
}

// Reachable both from service workers (importScripts) and popup/panel pages.
if (typeof self !== 'undefined') {
  self.JesterAuth = {
    getJesterToken,
    setJesterToken,
    jesterHeaders,
    jesterAuthError,
    JESTER_TOKEN_KEY,
    JESTER_TOKEN_HEADER
  };
}
