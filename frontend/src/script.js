const toggle = document.getElementById('theme-toggle');

toggle.addEventListener('change', () => {
  document.body.classList.toggle('light');
  document.body.classList.toggle('dark');
});
// Sync toggle state with body class on load
window.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme-toggle');
    toggle.checked = document.body.classList.contains('light');
  });
  
const prompts = [
    'What is the working price? What is the basic price?',
    'How are the consumptions per time period calculated? How is it weighted?',
    'I believe I paid more installments?',
    'How does the estimation process work?'
  ];
  
  const promptList = document.getElementById('prompt-list');
  const messageList = document.getElementById('message-list');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  
  // Render predefined prompts
  function renderPrompts() {
    prompts.forEach((text) => {
      const btn = document.createElement('button');
      btn.textContent = text;
      btn.addEventListener('click', () => {
        sendMessage(text);
      });
      promptList.appendChild(btn);
    });
  }
  
  // Append a message bubble
  function appendMessage(content, role) {
    const msg = document.createElement('div');
    msg.classList.add(role);
    msg.textContent = content;
    messageList.appendChild(msg);
    messageList.scrollTop = messageList.scrollHeight;
  }
  
  // Handle sending of messages
  function sendMessage(text) {
    appendMessage(text, 'user');
  
    if (promptList) promptList.style.display = 'none';
  
    // Show "KlarBill is typing..." message
    const typingIndicator = document.createElement('div');
    typingIndicator.classList.add('assistant');
    typingIndicator.textContent = 'KlarBill is typing...';
    messageList.appendChild(typingIndicator);
    messageList.scrollTop = messageList.scrollHeight;
  
    // After short delay, replace with real response
    setTimeout(() => {
      messageList.removeChild(typingIndicator);
      appendMessage('This is a placeholder response from KlarBill.', 'assistant');
    }, 1000); // 1 second typing delay
  }
  
  // Event listeners for manual input
  sendBtn.addEventListener('click', () => {
    const text = input.value.trim();
    if (!text) return;
    sendMessage(text);
    input.value = '';
  });
  
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const text = input.value.trim();
      if (!text) return;
      sendMessage(text);
      input.value = '';
    }
  });
  
  // Initialize prompts
  renderPrompts();
  

  // Function to get query parameter
function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
  }
  
  // Function to decode Base64
  function decodeBase64(str) {
    try {
      return decodeURIComponent(escape(window.atob(str)));
    } catch (e) {
      return null;
    }
  }
  
  // Get the name and update greeting
  function personalizeGreeting() {
    const encodedName = getQueryParam('name');
    if (encodedName) {
      const decodedName = decodeBase64(encodedName);
      if (decodedName) {
        const greeting = document.getElementById('greeting');
        if (greeting) {
          greeting.textContent = `Hi ${decodedName}, how are you?`;
        }
      }
    }
  }
  
  // Run personalization when page loads
  personalizeGreeting();
  