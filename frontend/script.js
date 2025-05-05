const toggle = document.getElementById('theme-toggle');
const languageToggle = document.getElementById('language-toggle');
const promptList = document.getElementById('prompt-list');
const messageList = document.getElementById('message-list');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

let currentLanguage = localStorage.getItem('language') || 'en';
let chatHistory = [];
const ESCALATION_KEYWORDS = ['contact', 'not helpful', 'dont understand', 'escalate', 'kontakt', 'hilfe', 'verstehe nicht'];
const translations = {
  en: {
    prompts: [
      'What is the working price?',
      'How is consumption calculated?',
      'Why is my payment increasing?',
      'Explain CO2 charges'
    ],
    typing: 'KlarBill is typing...',
    feedback: 'Was this helpful?',
    escalation: 'Would you like to email your service provider?',
    greeting: name => `Hi ${name}!`,
    positiveFeedback: 'Thank you! 👍',
    negativeFeedback: 'Sorry! We\'ll improve 👎',
    escalationConfirm: '📧 Your request has been escalated! Support will contact you within 24 hours.',
    declineMessage: 'No problem! Feel free to ask if you need anything else. 😊'
  },
  de: {
    prompts: [
      'Was ist der Arbeitspreis?',
      'Wie wird der Verbrauch berechnet?',
      'Warum erhöht sich meine Zahlung?',
      'CO2-Abgabe erklären'
    ],
    typing: 'KlarBill schreibt...',
    feedback: 'War diese Antwort hilfreich?',
    escalation: 'Möchten Sie Ihren Anbieter kontaktieren?',
    greeting: name => `Hallo ${name}!`,
    positiveFeedback: 'Danke! 👍',
    negativeFeedback: 'Entschuldigung! Wir verbessern uns 👎',
    escalationConfirm: '📧 Ihre Anfrage wurde weitergeleitet! Der Support meldet sich innerhalb von 24 Stunden.',
    declineMessage: 'Kein Problem! Fragen Sie gerne bei weiteren Anliegen. 😊'
  }
};

window.addEventListener('DOMContentLoaded', () => {
  toggle.checked = document.body.classList.contains('light');
  languageToggle.checked = currentLanguage === 'de';
  updateLanguage();
  renderPrompts();
  personalizeGreeting();
});

function updateLanguage() {
  currentLanguage = languageToggle.checked ? 'de' : 'en';
  localStorage.setItem('language', currentLanguage);
  renderPrompts();
  personalizeGreeting();
}

function renderPrompts() {
  promptList.innerHTML = '';
  translations[currentLanguage].prompts.forEach(text => {
    const btn = document.createElement('button');
    btn.className = 'prompt-btn';
    btn.textContent = text;
    btn.onclick = () => sendMessage(text);
    promptList.appendChild(btn);
  });
}

async function sendMessage(text) {
  const context = getInvoiceContext();
  chatHistory.push({ role: 'user', content: text });
  appendMessage(text, 'user');
  input.value = '';
  
  const typing = appendMessage(translations[currentLanguage].typing, 'assistant typing');
  
  try {
    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ 
        message: text,
        context: context,
        language: currentLanguage
      })
    });
    
    const data = await response.json();
    chatHistory.push({ role: 'assistant', content: data.response });
    messageList.removeChild(typing);
    const messageElement = appendMessage(data.response, 'assistant');
    
    if (needsEscalation(text)) {
      showEscalationPrompt(messageElement);
    } else {
      addFeedbackButtons(messageElement);
    }
  } catch (error) {
    messageList.removeChild(typing);
    appendMessage('Connection error. Please try again.', 'assistant error');
  }
}

function appendMessage(content, className) {
  const msg = document.createElement('div');
  msg.className = `message ${className}`;
  msg.innerHTML = content.replace(/\n/g, '<br>');
  messageList.appendChild(msg);
  messageList.scrollTop = messageList.scrollHeight;
  return msg;
}

function addFeedbackButtons(element) {
  const container = document.createElement('div');
  container.className = 'feedback-container';
  container.innerHTML = `
    <span>${translations[currentLanguage].feedback}</span>
    <button class="feedback-btn" onclick="handleFeedback(this, true)">👍</button>
    <button class="feedback-btn" onclick="handleFeedback(this, false)">👎</button>
  `;
  element.appendChild(container);
}

function needsEscalation(userInput) {
  return ESCALATION_KEYWORDS.some(keyword => 
    userInput.toLowerCase().includes(keyword.toLowerCase())
  );
}

function showEscalationPrompt(parentElement) {
  // Create container for the entire escalation message
  const escalationContainer = document.createElement('div');
  escalationContainer.className = 'escalation-container';
  
  // Add question text
  const question = document.createElement('div');
  question.textContent = translations[currentLanguage].escalation;
  escalationContainer.appendChild(question);

  // Add buttons container
  const buttons = document.createElement('div');
  buttons.className = 'escalation-buttons';
  
  // Create Yes/No buttons
  const yesButton = document.createElement('button');
  yesButton.className = 'escalation-btn yes';
  yesButton.textContent = currentLanguage === 'de' ? 'Ja' : 'Yes';
  
  const noButton = document.createElement('button');
  noButton.className = 'escalation-btn no';
  noButton.textContent = currentLanguage === 'de' ? 'Nein' : 'No';

  // Add click handlers
  yesButton.addEventListener('click', () => {
    initiateEmailSupport();
    escalationContainer.innerHTML = translations[currentLanguage].escalationConfirm;
  });

  noButton.addEventListener('click', () => {
    parentElement.remove();
    appendMessage(translations[currentLanguage].declineMessage, 'assistant');
  });

  // Append buttons
  buttons.appendChild(yesButton);
  buttons.appendChild(noButton);
  escalationContainer.appendChild(buttons);

  // Add to message list
  messageList.appendChild(escalationContainer);
  messageList.scrollTop = messageList.scrollHeight;
}

function handleFeedback(button, isPositive) {
  button.parentElement.innerHTML = isPositive 
    ? translations[currentLanguage].positiveFeedback 
    : translations[currentLanguage].negativeFeedback;

  if (!isPositive) {
    const feedbackElement = button.closest('.message');
    showEscalationPrompt(feedbackElement);
  }
}

function initiateEmailSupport() {
  const context = getInvoiceContext();
  const subject = `Support Request - Invoice ${context.invoiceId}`;
  const body = `Conversation History:\n\n${chatHistory.map(m => `${m.role}: ${m.content}`).join('\n')}\n\n`;
  
  window.location.href = `mailto:support@utility.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  appendMessage(translations[currentLanguage].escalationConfirm, 'assistant');
}

function decodeBase64(str) {
  try {
    str = str.replace(/_/g, '=');
    return decodeURIComponent(escape(window.atob(str)));
  } catch(e) {
    return null;
  }
}

function getInvoiceContext() {
  const params = new URLSearchParams(window.location.search);
  return {
    invoiceId: params.get('id'),
    name: decodeBase64(params.get('name')) || 'Customer'
  };
}

function personalizeGreeting() {
  const context = getInvoiceContext();
  const greeting = document.getElementById('greeting');
  if (greeting && context.name) {
    greeting.textContent = translations[currentLanguage].greeting(context.name);
  }
}

languageToggle.addEventListener('change', updateLanguage);
sendBtn.addEventListener('click', () => {
  const text = input.value.trim();
  if (text) sendMessage(text);
});

input.addEventListener('keypress', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendBtn.click();
  }
});

toggle.addEventListener('change', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', toggle.checked ? 'light' : 'dark');
});