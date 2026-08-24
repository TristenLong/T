/* global chrome */

const extractBtn = document.getElementById('extractBtn');
const errorMsg = document.getElementById('errorMsg');
const outputContainer = document.getElementById('outputContainer');
const outputBox = document.getElementById('outputBox');
const modelTag = document.getElementById('modelTag');
const statusBadge = document.getElementById('statusBadge');

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.add('visible');
  statusBadge.textContent = 'ERROR';
  statusBadge.classList.add('error');
}

function clearError() {
  errorMsg.textContent = '';
  errorMsg.classList.remove('visible');
  statusBadge.textContent = 'READY';
  statusBadge.classList.remove('error');
}

extractBtn.addEventListener('click', async () => {
  clearError();
  outputContainer.classList.remove('visible');
  extractBtn.disabled = true;
  extractBtn.innerText = 'EXTRACTING...';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab || !tab.id) {
      throw new Error('No active tab found.');
    }

    if (tab.url && (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('about:'))) {
      throw new Error('Cannot extract from internal browser pages.');
    }

    extractBtn.innerText = 'ANALYZING WITH JESTER...';

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageData,
    });

    if (!results || !results[0] || !results[0].result) {
      throw new Error('Failed to extract content from tab.');
    }

    const pageData = results[0].result;

    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: 'SEND_TO_JESTER', data: pageData },
        res => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (res?.status === 'ERROR') {
            reject(new Error(res.error || 'Server error'));
          } else {
            resolve(res);
          }
        }
      );
    });

    const aiResponse = response?.data?.response || response?.data?.result || 'Analyzed and indexed into JESTER.';
    const modelUsed = response?.data?.model || 'JESTER CORE';

    outputBox.textContent = aiResponse;
    modelTag.textContent = modelUsed;
    outputContainer.classList.add('visible');
    statusBadge.textContent = 'SYNTHESIZED';
    extractBtn.innerText = 'ANALYSIS COMPLETE';

    setTimeout(() => {
      extractBtn.disabled = false;
      extractBtn.innerText = '⚡ EXTRACT & ANALYZE TAB';
      statusBadge.textContent = 'READY';
    }, 3500);

  } catch (error) {
    showError(error.message);
    extractBtn.disabled = false;
    extractBtn.innerText = '⚡ EXTRACT & ANALYZE TAB';
  }
});

function extractPageData() {
  const title = document.title || '';
  const url = window.location.href || '';
  const text = (document.body ? document.body.innerText : '').substring(0, 6000);
  return { title, url, text };
}
