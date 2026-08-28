/* global chrome, importScripts, JesterAuth */

// Classic MV3 service worker (no "type": "module" in the manifest), so
// importScripts is how the shared auth helper gets loaded.
importScripts('jester-auth.js');

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "send-selection-to-jester",
      title: "⚡ Send Selection to JESTER Memory",
      contexts: ["selection"]
    });

    chrome.contextMenus.create({
      id: "send-page-to-jester",
      title: "🌐 Send Page URL to JESTER Memory",
      contexts: ["page"]
    });
  });
});

chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = tab?.url || info.pageUrl || "";
  const title = tab?.title || "";

  if (info.menuItemId === "send-selection-to-jester" && info.selectionText) {
    await sendToJester({
      type: "selection",
      content: info.selectionText,
      url: url,
      title: title
    });
  } else if (info.menuItemId === "send-page-to-jester") {
    await sendToJester({
      type: "page",
      url: url,
      title: title
    });
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "INJECT_MEMORY") {
    sendToJester(request.data)
      .then(res => sendResponse({ status: "SUCCESS", data: res }))
      .catch(err => sendResponse({ status: "ERROR", error: err.message }));
    return true;
  }
});

async function sendToJester(data) {
  // These are two DIFFERENT endpoints, not four fallbacks for one: the old list
  // tried /api/research/inject then /api/memory_link and returned whichever
  // answered first, so the same payload could land in either store depending on
  // timing. Pick the one that matches the payload and only vary the host.
  const endpointPath =
    data && data.type === 'selection' ? '/api/memory_link' : '/api/research/inject';
  const hosts = ['http://127.0.0.1:5000', 'http://localhost:5000'];
  const headers = await JesterAuth.jesterHeaders();

  let lastError = null;
  for (const host of hosts) {
    try {
      const response = await fetch(host + endpointPath, {
        method: 'POST',
        headers,
        body: JSON.stringify(data)
      });
      if (response.status === 401) {
        // Not a connectivity failure -- trying the other host would produce the
        // identical 401 and then report a misleading "connection failed".
        throw JesterAuth.jesterAuthError();
      }
      if (response.ok) {
        const result = await response.json();
        console.log('[JESTER Memory Clip] Synced successfully:', result);
        return result;
      }
      lastError = new Error(`JESTER responded ${response.status}`);
    } catch (err) {
      if (err && err.jesterAuth) throw err;
      lastError = err;
    }
  }
  console.error('[JESTER Memory Clip] Connection failed:', lastError);
  throw lastError || new Error('Failed to connect to JESTER server at port 5000');
}
