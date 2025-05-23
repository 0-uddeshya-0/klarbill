// script.js - Enhanced for Agentic AI Integration

function clearSessionData() {
  localStorage.removeItem('customerNumber');
  localStorage.removeItem('invoiceNumber');
  localStorage.removeItem('customerGreeting');
}

const toggle = document.getElementById('theme-toggle');
const languageToggle = document.getElementById('language-toggle');
const promptList = document.getElementById('prompt-list');
const messageList = document.getElementById('message-list');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const BACKEND_BASE_URL = 'http://localhost:8000';

// Parse URL parameters for customer/invoice numbers and persist to localStorage if present
const urlParams = new URLSearchParams(window.location.search);
const urlCustomerNumber = urlParams.get('customernumber');
const urlInvoiceNumber = urlParams.get('invoicenumber');

// Clear session data if neither URL param is present (avoid stale session reuse)
if (!urlCustomerNumber && !urlInvoiceNumber) {
  clearSessionData();  // Clear stale session if neither param is present
}

if (urlCustomerNumber || urlInvoiceNumber) {
  clearSessionData();  // Clear old session data on new param usage
}

if (urlCustomerNumber) {
  localStorage.setItem('customerNumber', urlCustomerNumber);
}

if (urlInvoiceNumber) {
  localStorage.setItem('invoiceNumber', urlInvoiceNumber);
}

let currentLanguage = localStorage.getItem('language') || 'en';
let currentCustomerNumber = urlCustomerNumber || localStorage.getItem('customerNumber') || null;
let currentInvoiceNumber = urlInvoiceNumber || localStorage.getItem('invoiceNumber') || null;

const storedGreeting = localStorage.getItem('customerGreeting');
if (storedGreeting) {
  document.getElementById('greeting').innerText = storedGreeting;
}
// document.getElementById('greeting').innerText = translations[currentLanguage].defaultGreeting;

if ((urlCustomerNumber || urlInvoiceNumber) && !storedGreeting) {
  fetch(`${BACKEND_BASE_URL}/customer_name`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer_number: urlCustomerNumber,
      invoice_number: urlInvoiceNumber,
      language: currentLanguage
    })
  })
  .then(res => res.json())
  .then(data => {
    if (data.customer_greeting) {
      const greeting = translations[currentLanguage].greeting(data.customer_greeting);
      document.getElementById('greeting').innerText = greeting;
      localStorage.setItem('customerGreeting', greeting);
    }
  })
  .catch(err => console.error('Greeting fetch error:', err));
}

let chatStarted = false;
let conversationContext = [];

const translations = {
  en: {
    prompts: [
      'How much is my total bill?',
      'What is my energy consumption?',
      'Can you break down my charges?',
      'Why did my bill change?'
    ],
    typing: 'KlarBill is analyzing...',
    askIdentifier: 'Please enter your customer number or invoice number to begin.',
    inputPlaceholder: 'Ask about your energy bill...',
    greeting: (name) => name ? `Hi ${name} How can I help?` : 'Hi! How can I help you today?',
    error: 'Something went wrong. Please try again.',
    selectInvoice: 'Please select an invoice:',
    thanksFeedback: 'Thanks for your feedback! 😊',
    sorryFeedback: 'Sorry I couldn\'t help better. 😔',
    defaultGreeting: 'Billing chaos? Don’t worry. KlarBill makes it clear.'
  },
  de: {
    prompts: [
      'Wie hoch ist meine Gesamtrechnung?',
      'Wie viel Energie habe ich verbraucht?',
      'Kannst du meine Kosten aufschlüsseln?',
      'Warum hat sich meine Rechnung geändert?'
    ],
    typing: 'KlarBill analysiert...',
    askIdentifier: 'Bitte gib deine Kunden- oder Rechnungsnummer ein.',
    inputPlaceholder: 'Frage zur Energierechnung...',
    greeting: (name) => name ? `Hallo ${name} Wie kann ich helfen?` : 'Hallo! Wie kann ich dir helfen?',
    error: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    selectInvoice: 'Bitte wähle eine Rechnung:',
    thanksFeedback: 'Danke für dein Feedback! 😊',
    sorryFeedback: 'Entschuldigung, dass ich nicht besser helfen konnte. 😔',
    defaultGreeting: 'Abrechnungschaos? Keine Sorge. KlarBill macht es klar.'
  }
};

document.getElementById('greeting').innerText = translations[currentLanguage].defaultGreeting;

function updateLanguageUI() {
  currentLanguage = languageToggle.checked ? 'de' : 'en';
  localStorage.setItem('language', currentLanguage);
  input.placeholder = translations[currentLanguage].inputPlaceholder;
  renderPrompts();
  
  const storedGreeting = localStorage.getItem('customerGreeting');
  if (storedGreeting) {
    document.getElementById('greeting').innerText = storedGreeting;
  }

  // Re-fetch greeting in new language if customer/invoice number exists

  if ((currentCustomerNumber || currentInvoiceNumber)) {
    fetch(`${BACKEND_BASE_URL}/customer_name`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        customer_number: currentCustomerNumber,
        invoice_number: currentInvoiceNumber,
        language: currentLanguage
      })
    })
    .then(res => res.json())
    .then(data => {
      if (data.customer_greeting) {
        const greeting = translations[currentLanguage].greeting(data.customer_greeting);
        document.getElementById('greeting').innerText = greeting;
        localStorage.setItem('customerGreeting', greeting);
      }
    })
    .catch(err => console.error('Greeting fetch error on language change:', err));
  }
}

function renderPrompts() {
  if (chatStarted) return;
  
  promptList.innerHTML = '';
  translations[currentLanguage].prompts.forEach(text => {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.classList.add('prompt-btn');
    btn.onclick = () => {
      sendMessage(text);
      promptList.style.display = 'none';
      chatStarted = true;
    };
    promptList.appendChild(btn);
  });
}

function appendMessage(content, role, isTyping = false) {
  const msg = document.createElement('div');
  msg.className = `message ${role}${isTyping ? ' typing' : ''}`;
  msg.innerHTML = content.replace(/\n/g, '<br>');
  messageList.appendChild(msg);
  messageList.scrollTop = messageList.scrollHeight;
  return msg;
}

function addFeedbackButtons(messageElement) {
  const container = document.createElement('div');
  container.className = 'feedback-container';
  container.innerHTML = `
    <button class="feedback-btn thumbs-up" title="Helpful">👍</button>
    <button class="feedback-btn thumbs-down" title="Not helpful">👎</button>
  `;
  
  container.querySelector('.thumbs-up').onclick = () => handleFeedback(container, true);
  container.querySelector('.thumbs-down').onclick = () => handleFeedback(container, false);
  
  messageElement.appendChild(container);
}

function handleFeedback(container, isPositive) {
  container.innerHTML = isPositive ? 
    translations[currentLanguage].thanksFeedback : 
    translations[currentLanguage].sorryFeedback;
}

function askForIdentifier() {
  const div = document.createElement('div');
  div.className = 'customer-number-prompt';
  div.innerHTML = `
    <p>${translations[currentLanguage].askIdentifier}</p>
    <div class="input-container">
      <input type="text" id="customer-number-input" placeholder="e.g. 10000000 or SWLS007446223">
      <button id="submit-number-btn">Submit</button>
    </div>
  `;
  messageList.appendChild(div);

  const inputEl = div.querySelector('#customer-number-input');
  const btn = div.querySelector('#submit-number-btn');
  inputEl.focus();

  async function processIdentifier(val) {
    // Save for possible later use
    localStorage.setItem('identifier', val);
    localStorage.removeItem('customerNumber');
    localStorage.removeItem('invoiceNumber');
    localStorage.removeItem('customerGreeting');

    // Always send both fields, backend decides which it is
    const payload = {
      customer_number: val,
      invoice_number: val,
      language: currentLanguage
    };

    try {
      const res = await fetch(`${BACKEND_BASE_URL}/customer_name`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.type === "invoice") {
        localStorage.setItem('invoiceNumber', val);
        localStorage.removeItem('customerNumber');
      } else if (data.type === "customer") {
        localStorage.setItem('customerNumber', val);
        localStorage.removeItem('invoiceNumber');
      }
      if (data.customer_greeting) {
        const greeting = translations[currentLanguage].greeting(data.customer_greeting);
        document.getElementById('greeting').innerText = greeting;
        localStorage.setItem('customerGreeting', greeting);
      }
    } catch (err) {
      console.error('Greeting fetch error:', err);
    }

    div.remove();
    renderPrompts();
    input.focus();
  }

  btn.onclick = () => {
    const val = inputEl.value.trim();
    if (val) processIdentifier(val);
  };

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = inputEl.value.trim();
      if (val) processIdentifier(val);
    }
  });
}

function displayInvoiceSelection(response, suggestions) {
  const container = document.createElement('div');
  container.className = 'invoice-selection-container';
  container.innerHTML = `<p>${response}</p>`;
  
  const buttonsDiv = document.createElement('div');
  buttonsDiv.className = 'invoice-buttons';
  
  suggestions.forEach(invoiceNum => {
    const btn = document.createElement('button');
    btn.className = 'invoice-btn';
    btn.textContent = invoiceNum;
    btn.onclick = () => {
      currentInvoiceNumber = invoiceNum;
      localStorage.setItem('invoiceNumber', invoiceNum);
      sendMessage(`Use invoice ${invoiceNum}`);
      container.remove();
    };
    buttonsDiv.appendChild(btn);
  });
  
  container.appendChild(buttonsDiv);
  messageList.appendChild(container);
  messageList.scrollTop = messageList.scrollHeight;
}

async function sendMessage(text) {
  // Add to conversation context
  conversationContext.push({ role: 'user', content: text });
  currentCustomerNumber = localStorage.getItem('customerNumber') || null;
  currentInvoiceNumber = localStorage.getItem('invoiceNumber') || null;
  
  appendMessage(text, 'user');
  input.value = '';
  
  const typingMsg = appendMessage(translations[currentLanguage].typing, 'assistant', true);

  const payload = {
    message: text,
    language: currentLanguage,
    customer_number: currentCustomerNumber,
    invoice_number: currentInvoiceNumber
  };

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    messageList.removeChild(typingMsg);

    // Handle multiple invoice selection
    if (data.needs_invoice_number && data.invoice_suggestions?.length > 0) {
      displayInvoiceSelection(data.response, data.invoice_suggestions);
      return;
    }

    // Update session information
    if (data.session_customer_number) {
      currentCustomerNumber = data.session_customer_number;
      localStorage.setItem('customerNumber', currentCustomerNumber);
    }
    
    if (data.session_invoice_number) {
      currentInvoiceNumber = data.session_invoice_number;
      localStorage.setItem('invoiceNumber', currentInvoiceNumber);
    }

    // Update greeting with customer info
    if (data.customer_greeting) {
      const greeting = translations[currentLanguage].greeting(data.customer_greeting);
      //document.getElementById('greeting').innerText = greeting;
      localStorage.setItem('customerGreeting', greeting);
    }

    // Add assistant response
    conversationContext.push({ role: 'assistant', content: data.response });
    const assistantMsg = appendMessage(data.response, 'assistant');
    addFeedbackButtons(assistantMsg);

    chatStarted = true;

  } catch (error) {
    messageList.removeChild(typingMsg);
    appendMessage(translations[currentLanguage].error, 'assistant error');
    console.error('Chat error:', error);
  }
}

// Initialize app
window.addEventListener('DOMContentLoaded', () => {
  // Set default theme to light
  document.body.classList.add('light');
  toggle.checked = true;
  localStorage.setItem('theme', 'light');

  // Initialize language
  languageToggle.checked = currentLanguage === 'de';
  updateLanguageUI();

  // Restore session
  const storedGreeting = localStorage.getItem('customerGreeting');
  if (storedGreeting) {
    document.getElementById('greeting').innerText = storedGreeting;
  }

  // Check if we need customer/invoice info
  if (!currentCustomerNumber && !currentInvoiceNumber) {
    askForIdentifier();
  } else {
    renderPrompts();
  }
});

// Event listeners
languageToggle.addEventListener('change', updateLanguageUI);

toggle.addEventListener('change', () => {
  document.body.classList.toggle('light');
  const theme = document.body.classList.contains('light') ? 'light' : 'dark';
  localStorage.setItem('theme', theme);
});

sendBtn.addEventListener('click', () => {
  const text = input.value.trim();
  if (text) sendMessage(text);
});

input.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendBtn.click();
});

// Add clear session functionality (for testing)
if (window.location.search.includes('clear=true')) {
  clearSessionData();
  localStorage.clear();
  location.reload();
}