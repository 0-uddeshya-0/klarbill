// script.js - Enhanced for Agentic AI Integration

function clearSessionData() {
  localStorage.removeItem('customerNumber');
  localStorage.removeItem('invoiceNumber');
  localStorage.removeItem('customerGreeting');
  localStorage.removeItem('validatedIdentifier');
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
let isValidated = localStorage.getItem('validatedIdentifier') === 'true';

const storedGreeting = localStorage.getItem('customerGreeting');
if (storedGreeting) {
  document.getElementById('greeting').innerText = storedGreeting;
}

if ((urlCustomerNumber || urlInvoiceNumber) && !storedGreeting) {
  // Validate identifier from URL
  validateAndSetupSession(urlInvoiceNumber || urlCustomerNumber);
}

let chatStarted = false;
let conversationContext = [];
let inputEnabled = false;

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
    inputPlaceholderDisabled: 'Please enter your customer/invoice number first...',
    greeting: (name) => name ? `Hi ${name} How can I help?` : 'Hi! How can I help you today?',
    error: 'Something went wrong. Please try again.',
    selectInvoice: 'Please select an invoice:',
    thanksFeedback: 'Thanks for your feedback! 😊',
    sorryFeedback: 'Sorry I couldn\'t help better. 😔',
    defaultGreeting: 'Billing chaos? Don\'t worry. KlarBill makes it clear.',
    validating: 'Validating your information...',
    invalidIdentifier: 'Invalid customer or invoice number. Please check and try again.',
    multipleInvoices: 'Multiple invoices found. Please select one:'
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
    inputPlaceholderDisabled: 'Bitte zuerst Kunden-/Rechnungsnummer eingeben...',
    greeting: (name) => name ? `Hallo ${name} Wie kann ich helfen?` : 'Hallo! Wie kann ich dir helfen?',
    error: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    selectInvoice: 'Bitte wähle eine Rechnung:',
    thanksFeedback: 'Danke für dein Feedback! 😊',
    sorryFeedback: 'Entschuldigung, dass ich nicht besser helfen konnte. 😔',
    defaultGreeting: 'Abrechnungschaos? Keine Sorge. KlarBill macht es klar.',
    validating: 'Überprüfe deine Informationen...',
    invalidIdentifier: 'Ungültige Kunden- oder Rechnungsnummer. Bitte überprüfen und erneut versuchen.',
    multipleInvoices: 'Mehrere Rechnungen gefunden. Bitte wähle eine:'
  }
};

document.getElementById('greeting').innerText = translations[currentLanguage].defaultGreeting;

function updateInputState() {
  if (isValidated && (currentCustomerNumber || currentInvoiceNumber)) {
    input.disabled = false;
    input.placeholder = translations[currentLanguage].inputPlaceholder;
    inputEnabled = true;
  } else {
    input.disabled = true;
    input.placeholder = translations[currentLanguage].inputPlaceholderDisabled;
    inputEnabled = false;
  }
}

function updateLanguageUI() {
  currentLanguage = languageToggle.checked ? 'de' : 'en';
  localStorage.setItem('language', currentLanguage);
  updateInputState();
  renderPrompts();
  
  const storedGreeting = localStorage.getItem('customerGreeting');
  if (storedGreeting) {
    document.getElementById('greeting').innerText = storedGreeting;
  }

  // Re-fetch greeting in new language if customer/invoice number exists
  if ((currentCustomerNumber || currentInvoiceNumber) && isValidated) {
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
  if (chatStarted || !isValidated) return;
  
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

async function validateAndSetupSession(identifier) {
  const loadingMsg = appendMessage(translations[currentLanguage].validating, 'assistant');
  
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/validate_identifier`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        identifier: identifier,
        language: currentLanguage
      })
    });
    
    const data = await response.json();
    messageList.removeChild(loadingMsg);
    
    if (!data.valid) {
      appendMessage(translations[currentLanguage].invalidIdentifier, 'assistant error');
      askForIdentifier();
      return;
    }
    
    // Valid identifier found
    if (data.type === 'invoice') {
      currentInvoiceNumber = identifier;
      currentCustomerNumber = data.customer_number;
      localStorage.setItem('invoiceNumber', identifier);
      localStorage.setItem('customerNumber', data.customer_number);
    } else if (data.type === 'customer') {
      currentCustomerNumber = identifier;
      localStorage.setItem('customerNumber', identifier);
      
      // Check if multiple invoices
      if (data.multiple_invoices && data.invoice_numbers.length > 0) {
        displayInvoiceSelection(
          translations[currentLanguage].multipleInvoices, 
          data.invoice_numbers
        );
        return;
      }
    }
    
    // Set validated flag
    isValidated = true;
    localStorage.setItem('validatedIdentifier', 'true');
    
    // Update greeting
    if (data.customer_name) {
      const salutation = data.salutation;
      let greeting;
      if (currentLanguage === 'en') {
        const salutationEn = salutation.toLowerCase() === 'Frau' ? 'Ms.' : 
                           salutation.toLowerCase() === 'Herr' ? 'Mr.' : salutation;
        greeting = translations[currentLanguage].greeting(`${salutationEn} ${data.customer_name}`);
      } else {
        greeting = translations[currentLanguage].greeting(`${salutation} ${data.customer_name}`);
      }
      document.getElementById('greeting').innerText = greeting;
      localStorage.setItem('customerGreeting', greeting);
    }
    
    // Enable input and show prompts
    updateInputState();
    renderPrompts();
    input.focus();
    
  } catch (error) {
    console.error('Validation error:', error);
    messageList.removeChild(loadingMsg);
    appendMessage(translations[currentLanguage].error, 'assistant error');
    askForIdentifier();
  }
}

function askForIdentifier() {
  const div = document.createElement('div');
  div.className = 'customer-number-prompt';
  div.innerHTML = `
    <p>${translations[currentLanguage].askIdentifier}</p>
    <div class="input-container">
      <input type="text" id="customer-number-input" placeholder="e.g. INV0021 or 10000548">
      <button id="submit-number-btn">Submit</button>
    </div>
  `;
  messageList.appendChild(div);

  const inputEl = div.querySelector('#customer-number-input');
  const btn = div.querySelector('#submit-number-btn');
  inputEl.focus();

  async function processIdentifier(val) {
    div.remove();
    await validateAndSetupSession(val);
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
  
  const dropdownDiv = document.createElement('div');
  dropdownDiv.className = 'invoice-dropdown';
  
  // Sort suggestions - latest (higher numbers/letters) first
  const sortedSuggestions = [...suggestions].sort((a, b) => {
    // Extract numbers from invoice strings for proper numeric sorting
    const numA = parseInt(a.replace(/\D/g, '')) || 0;
    const numB = parseInt(b.replace(/\D/g, '')) || 0;
    return numB - numA; // Descending order (latest first)
  });
  
  sortedSuggestions.forEach((invoiceNum, index) => {
    const option = document.createElement('div');
    option.className = 'invoice-option';
    option.innerHTML = `
      <span class="invoice-number">${invoiceNum}</span>
      <span class="invoice-label">${index === 0 ? '(Latest)' : index === sortedSuggestions.length - 1 ? '(Oldest)' : ''}</span>
    `;
    
    option.onclick = async () => {
      currentInvoiceNumber = invoiceNum;
      localStorage.setItem('invoiceNumber', invoiceNum);
      isValidated = true;
      localStorage.setItem('validatedIdentifier', 'true');
      
      container.remove();
      
      // Fetch greeting for the selected invoice
      try {
        const response = await fetch(`${BACKEND_BASE_URL}/customer_name`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            invoice_number: invoiceNum,
            language: currentLanguage
          })
        });
        const data = await response.json();
        if (data.customer_greeting) {
          const greeting = translations[currentLanguage].greeting(data.customer_greeting);
          document.getElementById('greeting').innerText = greeting;
          localStorage.setItem('customerGreeting', greeting);
        }
      } catch (err) {
        console.error('Greeting fetch error:', err);
      }
      
      // Enable input and show prompts
      updateInputState();
      renderPrompts();
      input.focus();
    };
    dropdownDiv.appendChild(option);
  });
  
  container.appendChild(dropdownDiv);
  messageList.appendChild(container);
  messageList.scrollTop = messageList.scrollHeight;
}

async function sendMessage(text) {
  if (!isValidated) {
    appendMessage(translations[currentLanguage].askIdentifier, 'assistant');
    return;
  }
  
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

    // Handle multiple invoice selection (shouldn't happen if validated properly)
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

    // Always log user message
    fetch(`${BACKEND_BASE_URL}/log_message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        customer_number: currentCustomerNumber,
        invoice_number: currentInvoiceNumber,
        message: text,
        role: 'user',
        timestamp: new Date().toISOString(),
        topic: null,
        session_id: null
      })
    }).catch(err => console.error('User message log error:', err));

    // Update greeting with customer info
    if (data.customer_greeting) {
      const greeting = translations[currentLanguage].greeting(data.customer_greeting);
      localStorage.setItem('customerGreeting', greeting);
    }

    // Add assistant response
    conversationContext.push({ role: 'assistant', content: data.response });
    const assistantMsg = appendMessage(data.response, 'assistant');
    addFeedbackButtons(assistantMsg);

    // Log assistant message
    fetch(`${BACKEND_BASE_URL}/log_message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        customer_number: currentCustomerNumber,
        invoice_number: currentInvoiceNumber,
        message: data.response,
        role: 'assistant',
        timestamp: new Date().toISOString(),
        topic: null,
        session_id: null
      })
    }).catch(err => console.error('Assistant message log error:', err));

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

  // Update input state based on validation status
  updateInputState();

  // Check if we need customer/invoice info
  if (!currentCustomerNumber && !currentInvoiceNumber) {
    askForIdentifier();
  } else if (!isValidated) {
    // Validate existing identifier
    validateAndSetupSession(currentInvoiceNumber || currentCustomerNumber);
  } else {
    // Already validated
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
  if (text && isValidated) sendMessage(text);
});

input.addEventListener('keypress', (e) => {
  if (e.key === 'Enter' && isValidated) sendBtn.click();
});

// Add clear session functionality (for testing)
if (window.location.search.includes('clear=true')) {
  clearSessionData();
  localStorage.clear();
  location.reload();
}