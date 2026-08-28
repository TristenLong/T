/* global chrome, importScripts, JesterAuth */

// Classic MV3 service worker (no "type": "module" in the manifest), so
// importScripts is how the shared auth helper gets loaded.
importScripts('jester-auth.js');

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

// The two entries in each list below are the SAME endpoint on two spellings of
// the loopback host -- a genuine fallback, unlike the mixed-endpoint list this
// used to share with browser_extension. Only the host varies.
const JESTER_HOSTS = ['http://127.0.0.1:5000', 'http://localhost:5000'];

async function postToJester(endpointPath, body) {
  const headers = await JesterAuth.jesterHeaders();

  let lastError = null;
  for (const host of JESTER_HOSTS) {
    try {
      const r = await fetch(host + endpointPath, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });
      if (r.status === 401) {
        // Retrying the other host would produce an identical 401 and then
        // report a misleading "failed to contact backend".
        throw JesterAuth.jesterAuthError();
      }
      if (r.ok) {
        return await r.json();
      }
      // The old code dropped non-ok responses on the floor, so a 500 from both
      // hosts surfaced as "failed to contact JESTER backend" -- which sent the
      // user hunting a connectivity problem that did not exist.
      lastError = new Error(`JESTER responded ${r.status} on ${endpointPath}`);
    } catch (e) {
      if (e && e.jesterAuth) throw e;
      lastError = e;
    }
  }
  throw lastError || new Error('Failed to contact JESTER backend at localhost:5000');
}

async function forwardToJester(payload) {
  let messageText = '';
  if (typeof payload === 'string') {
    messageText = payload;
  } else if (payload && payload.text) {
    messageText = `I have extracted the following context from the user's browser tab:\nURL: ${payload.url || ''}\nTitle: ${payload.title || ''}\nContent:\n${payload.text}\n\nPlease analyze this, highlight key insights, and summarize actionable findings.`;
  } else {
    messageText = JSON.stringify(payload);
  }

  return postToJester('/api/chat', { message: messageText });
}

async function forwardCommandToJester(toolId, cmd) {
  return postToJester('/api/execute_tool', { tool_id: toolId, cmd: cmd });
}
