/* global chrome, JesterAuth */

const logEl = document.getElementById('log');
const promptEl = document.getElementById('prompt');
const sendBtn = document.getElementById('sendBtn');
const tokenInput = document.getElementById('tokenInput');
const tokenState = document.getElementById('tokenState');
const saveTokenBtn = document.getElementById('saveTokenBtn');

function appendLog(line) {
  logEl.innerText = `${line}\n` + logEl.innerText;
}

sendBtn.addEventListener('click', async () => {
  const prompt = promptEl.value;
  if (!prompt) return;

  appendLog('Executing...');
  sendBtn.disabled = true;

  try {
    // Send to local Jester Server
    const res = await fetch('http://localhost:5000/api/chat', {
      method: 'POST',
      headers: await JesterAuth.jesterHeaders(),
      body: JSON.stringify({ message: prompt })
    });

    if (res.status === 401) {
      throw JesterAuth.jesterAuthError();
    }
    if (!res.ok) {
      throw new Error(`JESTER responded ${res.status}`);
    }

    const data = await res.json();
    appendLog(`JESTER: ${data.response}\n`);
    promptEl.value = '';

    // Attempt DOM automation if Jester requested it (simple trigger example).
    // Guarded on `data.response` existing: an error-shaped reply has no
    // `response` field, and calling .includes() on undefined threw a TypeError
    // that masked the real server error.
    if (data.response && data.response.includes('DOM_ACTION:')) {
      const action = data.response.split('DOM_ACTION:')[1].trim();
      chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
        if (!tabs || !tabs[0]) {
          appendLog('DOM Result: no active tab');
          return;
        }
        chrome.tabs.sendMessage(tabs[0].id, { type: 'EXECUTE_DOM', action: action }, response => {
          // Without this check a missing content script surfaces as an
          // unchecked-lastError warning in the console and nothing in the UI.
          if (chrome.runtime.lastError) {
            appendLog(`DOM Result: ${chrome.runtime.lastError.message}`);
            return;
          }
          appendLog(`DOM Result: ${response?.status || 'No Response'}`);
        });
      });
    }
  } catch (e) {
    appendLog(`Error: ${e.message}`);
  } finally {
    sendBtn.disabled = false;
  }
});

/*
 * Token management.
 *
 * The backend requires an X-Jester-Token header on /api/* and an extension
 * cannot read the token file off disk -- that is deliberate, it is what stops
 * every other installed extension from calling /api/sandbox. So the user pastes
 * it in once and chrome.storage.local keeps it.
 *
 * The value is never rendered back into the input; only whether one is set.
 */
async function refreshTokenState() {
  const token = await JesterAuth.getJesterToken();
  if (token) {
    tokenState.textContent = '· SET';
    tokenState.style.color = '#00ff41';
    tokenInput.placeholder = '•••••••• (saved)';
  } else {
    tokenState.textContent = '· MISSING';
    tokenState.style.color = '#ff4455';
    tokenInput.placeholder = 'paste token';
  }
}

saveTokenBtn.addEventListener('click', async () => {
  const value = tokenInput.value.trim();
  if (!value) {
    appendLog('Error: paste the token from GOD_HAND_CORE/.jester_token first.');
    return;
  }
  try {
    await JesterAuth.setJesterToken(value);
    tokenInput.value = '';
    appendLog('Token saved.');
    await refreshTokenState();
  } catch (err) {
    appendLog(`Error: could not save token: ${err.message}`);
  }
});

tokenInput.addEventListener('keydown', event => {
  if (event.key === 'Enter') saveTokenBtn.click();
});

refreshTokenState();
