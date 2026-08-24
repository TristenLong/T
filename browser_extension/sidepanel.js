document.getElementById('sendBtn').addEventListener('click', async () => {
  const prompt = document.getElementById('prompt').value;
  if (!prompt) return;
  
  const log = document.getElementById('log');
  log.innerText = "Executing...\n" + log.innerText;
  
  try {
    // Send to local Jester Server
    const res = await fetch('http://localhost:5000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: prompt })
    });
    
    const data = await res.json();
    log.innerText = `JESTER: ${data.response}\n\n` + log.innerText;
    document.getElementById('prompt').value = '';
    
    // Attempt DOM automation if Jester requested it (simple trigger example)
    if (data.response.includes("DOM_ACTION:")) {
       const action = data.response.split("DOM_ACTION:")[1].trim();
       chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
         chrome.tabs.sendMessage(tabs[0].id, { type: "EXECUTE_DOM", action: action }, (response) => {
           log.innerText = `DOM Result: ${response?.status || 'No Response'}\n` + log.innerText;
         });
       });
    }
  } catch(e) {
    log.innerText = `Error: ${e.message}\n` + log.innerText;
  }
});
