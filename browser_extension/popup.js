/* global chrome */

const statusEl = document.getElementById('status');
const sendPageBtn = document.getElementById('sendPageBtn');
const extractPageBtn = document.getElementById('extractPageBtn');

function setStatus(message, isError = false) {
  statusEl.className = `status ${isError ? 'error' : 'success'}`;
  statusEl.textContent = message;
  setTimeout(() => {
    if (statusEl.textContent === message) {
      statusEl.className = 'status';
      statusEl.textContent = '';
    }
  }, 3500);
}

sendPageBtn.addEventListener('click', async () => {
  try {
    sendPageBtn.disabled = true;
    sendPageBtn.textContent = 'LINKING...';

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url) {
      throw new Error('No active tab detected.');
    }

    await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          type: 'INJECT_MEMORY',
          data: {
            type: 'page',
            url: tab.url,
            title: tab.title || ''
          }
        },
        response => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (response?.status === 'ERROR') {
            reject(new Error(response.error || 'Server error'));
          } else {
            resolve(response);
          }
        }
      );
    });

    setStatus('✓ URL Synced to JESTER Memory Vault');
  } catch (err) {
    setStatus(`✗ ${err.message}`, true);
  } finally {
    sendPageBtn.disabled = false;
    sendPageBtn.textContent = '🔗 Link Current URL';
  }
});

extractPageBtn.addEventListener('click', async () => {
  try {
    extractPageBtn.disabled = true;
    extractPageBtn.textContent = 'INGESTING...';

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      throw new Error('No active tab detected.');
    }

    if (tab.url && (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('about:'))) {
      throw new Error('Cannot extract from internal browser pages.');
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => ({
        title: document.title || '',
        url: window.location.href || '',
        text: (document.body ? document.body.innerText : '').substring(0, 8000)
      })
    });

    if (!results || !results[0] || !results[0].result) {
      throw new Error('Could not extract page text.');
    }

    const pageData = results[0].result;

    await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          type: 'INJECT_MEMORY',
          data: {
            type: 'page_content',
            content: `Extracted Page (${pageData.title}):\n${pageData.text}`,
            url: pageData.url,
            title: pageData.title
          }
        },
        response => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (response?.status === 'ERROR') {
            reject(new Error(response.error || 'Server error'));
          } else {
            resolve(response);
          }
        }
      );
    });

    setStatus('✓ Page content ingested into JESTER');
  } catch (err) {
    setStatus(`✗ ${err.message}`, true);
  } finally {
    extractPageBtn.disabled = false;
    extractPageBtn.textContent = '📄 Ingest Page Content';
  }
});
