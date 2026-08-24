// content.js - Injected into all webpages to allow JESTER DOM control
console.log("JESTER DOM Control Script Loaded");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "EXECUTE_DOM") {
    console.log("JESTER DOM ACTION:", request.action);
    try {
      // Very basic execution loop (In reality, Jester would send specific selector commands)
      // e.g. ACTION: CLICK, SELECTOR: #loginBtn
      const parts = request.action.split('|');
      if (parts[0] === 'CLICK' && parts[1]) {
        const el = document.querySelector(parts[1]);
        if (el) {
          el.click();
          sendResponse({ status: "CLICKED " + parts[1] });
          return;
        }
      }
      sendResponse({ status: "ACTION_NOT_SUPPORTED_OR_FAILED" });
    } catch(e) {
      sendResponse({ status: "ERROR: " + e.message });
    }
  }
  return true;
});
