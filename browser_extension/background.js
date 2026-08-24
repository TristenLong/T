/* global chrome */

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
  const endpoints = [
    'http://127.0.0.1:5000/api/research/inject',
    'http://localhost:5000/api/research/inject',
    'http://127.0.0.1:5000/api/memory_link',
    'http://localhost:5000/api/memory_link'
  ];

  let lastError = null;
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (response.ok) {
        const result = await response.json();
        console.log('[JESTER Memory Clip] Synced successfully:', result);
        return result;
      }
    } catch (err) {
      lastError = err;
    }
  }
  console.error('[JESTER Memory Clip] Connection failed:', lastError);
  throw lastError || new Error("Failed to connect to JESTER server at port 5000");
}
