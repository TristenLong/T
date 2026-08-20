document.getElementById('extractBtn').addEventListener('click', async () => {
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    function: extractPageData,
  }, (results) => {
    if(results && results[0]) {
       // Send to background script which will send to localhost
       chrome.runtime.sendMessage({ type: "SEND_TO_JESTER", data: results[0].result });
    }
  });
});

function extractPageData() {
  return {
    title: document.title,
    url: window.location.href,
    text: document.body.innerText.substring(0, 5000) // First 5k chars
  };
}
