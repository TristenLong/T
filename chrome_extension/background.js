/* global chrome */

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "analyze-selection-jester",
      title: "🧠 Analyze Selection with JESTER AI",
      contexts: ["selection"]
    });
    chrome.contextMenus.create({
      id: "dispatch-coder",
      title: "🤖 Send to Architect (CoderCore)",
      contexts: ["selection"]
    });
    chrome.contextMenus.create({
      id: "dispatch-browser",
      title: "🧭 Send to Navigator (BrowserCore)",
      contexts: ["selection"]
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = tab?.url || info.pageUrl || "";
  const title = tab?.title || "";

  if (info.menuItemId === "analyze-selection-jester" && info.selectionText) {
    try {
      const prompt = `Analyze this selected text from ${url} (${title}):\n\n${info.selectionText}`;
      await forwardToJester(prompt);
    } catch (err) {
      console.error("[JESTER Research] Context menu error:", err);
    }
  } else if (info.menuItemId === "dispatch-coder" && info.selectionText) {
    try {
      await forwardCommandToJester("coder_swarm", `Context: ${url} (${title})\nTask: ${info.selectionText}`);
    } catch (err) {
      console.error("[JESTER Research] Context menu error:", err);
    }
  } else if (info.menuItemId === "dispatch-browser" && info.selectionText) {
    try {
      await forwardCommandToJester("browser_swarm", `Context: ${url} (${title})\nTask: ${info.selectionText}`);
    } catch (err) {
      console.error("[JESTER Research] Context menu error:", err);
    }
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "SEND_TO_JESTER") {
    forwardToJester(request.data)
      .then(data => sendResponse({ status: "SUCCESS", data }))
      .catch(err => sendResponse({ status: "ERROR", error: err.message }));
    return true; // Keep message channel open for async response
  }
});

async function forwardToJester(payload) {
  const endpoints = [
    'http://127.0.0.1:5000/api/chat',
    'http://localhost:5000/api/chat'
  ];

  let messageText = '';
  if (typeof payload === 'string') {
    messageText = payload;
  } else if (payload && payload.text) {
    messageText = `I have extracted the following context from the user's browser tab:\nURL: ${payload.url || ''}\nTitle: ${payload.title || ''}\nContent:\n${payload.text}\n\nPlease analyze this, highlight key insights, and summarize actionable findings.`;
  } else {
    messageText = JSON.stringify(payload);
  }

  let lastError = null;
  for (const endpoint of endpoints) {
    try {
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText })
      });
      if (r.ok) {
        return await r.json();
      }
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError || new Error("Failed to contact JESTER backend at localhost:5000");
}

async function forwardCommandToJester(toolId, cmd) {
  const endpoints = [
    'http://127.0.0.1:5000/api/execute_tool',
    'http://localhost:5000/api/execute_tool'
  ];

  let lastError = null;
  for (const endpoint of endpoints) {
    try {
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_id: toolId, cmd: cmd })
      });
      if (r.ok) {
        return await r.json();
      }
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError || new Error("Failed to contact JESTER backend at localhost:5000");
}
