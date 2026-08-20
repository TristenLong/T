chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "SEND_TO_JESTER") {
    fetch('http://127.0.0.1:5000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message: `I have extracted the following context from the user's browser tab:\nURL: ${request.data.url}\nTitle: ${request.data.title}\nContent:\n${request.data.text}\n\nPlease analyze this and summarize it.`
      })
    })
    .then(r => r.json())
    .then(data => console.log('JESTER Response:', data))
    .catch(err => console.error('Error contacting JESTER:', err));
  }
});
