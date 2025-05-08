// script.js - Updated with improved UX and customer ID handling
const toggle = document.getElementById('theme-toggle');
const languageToggle = document.getElementById('language-toggle');
const promptList = document.getElementById('prompt-list');
const messageList = document.getElementById('message-list');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Store state
let currentLanguage = localStorage.getItem('language') || 'en';
let chatHistory = [];
let currentCustomerId = null;
let needsCustomerId = false;
let hidePromptsAfterFirstQuery = true;

// Load customer ID from localStorage if available
if (localStorage.getItem('customerId')) {
  currentCustomerId = localStorage.getItem('customerId');
}

// Updated escalation keywords
const ESCALATION_KEYWORDS = [
  'contact', 'not helpful', 'dont understand', 'escalate', 'talk to human', 'speak with representative',
  'kontakt', 'hilfe', 'verstehe nicht', 'eskalieren', 'mit mensch sprechen'
];

// Updated translations with better prompts
const translations = {
  en: {
    prompts: [
      'What is the breakdown of my energy costs?',
      'Explain how my consumption is calculated',
      'Why did my bill increase this month?',
      'Explain the CO2 tax on my invoice'
    ],
    typing: 'KlarBill is analyzing your bill...',
    feedback: 'Was this helpful?',
    escalation: 'Would you like to contact your service provider?',
    greeting: name => `Hello ${name}! How can I help with your bill today?`,
    positiveFeedback: 'Thank you for your feedback! 👍',
    negativeFeedback: 'I\'m sorry this wasn\'t helpful. 👎',
    escalationConfirm: '📧 Your request has been forwarded! Support will contact you within 24 hours.',
    declineMessage: 'Is there anything else I can help you with? Feel free to ask. 😊',
    askCustomerId: 'Please enter your customer ID to continue.'
  },
  de: {
    prompts: [
      'Wie setzen sich meine Energiekosten zusammen?',
      'Wie wird mein Verbrauch berechnet?',
      'Warum ist meine Rechnung diesen Monat gestiegen?',
      'Erklären Sie die CO2-Abgabe auf meiner Rechnung'
    ],
    typing: 'KlarBill analysiert Ihre Rechnung...',
    feedback: 'War das hilfreich?',
    escalation: 'Möchten Sie Ihren Anbieter kontaktieren?',
    greeting: name => `Hallo ${name}! Wie kann ich Ihnen mit Ihrer Rechnung helfen?`,
    positiveFeedback: 'Danke für Ihr Feedback! 👍',
    negativeFeedback: 'Es tut mir leid, dass dies nicht hilfreich war. 👎',
    escalationConfirm: '📧 Ihre Anfrage wurde weitergeleitet! Der Support meldet sich innerhalb von 24 Stunden.',
    declineMessage: 'Gibt es etwas anderes, womit ich Ihnen helfen kann? Fragen Sie gerne. 😊',
    askCustomerId: 'Bitte geben Sie Ihre Kundennummer ein, um fortzufahren.'
  }
};

// Initialize app
window.addEventListener('DOMContentLoaded', () => {
  toggle.checked = document.body.classList.contains('light');
  languageToggle.checked = currentLanguage === 'de';
  updateLanguage();
  renderPrompts();
  
  // Extract customer ID from URL if present
  const urlCustomerId = extractCustomerId();
  if (urlCustomerId) {
    currentCustomerId = urlCustomerId;
    localStorage.setItem('customerId', currentCustomerId);
  }
  
  personalizeGreeting();
  
  // If we have a customer ID, show it in the UI
  if (currentCustomerId) {
    showCustomerIdBadge(currentCustomerId);
  }
});

function updateLanguage() {
  currentLanguage = languageToggle.checked ? 'de' : 'en';
  localStorage.setItem('language', currentLanguage);
  renderPrompts();
  personalizeGreeting();
  
  // Update customer ID prompt if visible
  if (needsCustomerId) {
    // Remove any previous prompt
    const oldPrompt = document.querySelector('.customer-id-prompt');
    if (oldPrompt) {
      oldPrompt.remove();
    }
    
    // Show new prompt in current language
    askForCustomerId();
  }
}

function renderPrompts() {
  promptList.innerHTML = '';
  translations[currentLanguage].prompts.forEach(text => {
    const btn = document.createElement('button');
    btn.className = 'prompt-btn';
    btn.textContent = text;
    btn.onclick = () => {
      sendMessage(text);
      if (hidePromptsAfterFirstQuery) {
        promptList.style.display = 'none'; // Hide prompts after selection
      }
    };
    promptList.appendChild(btn);
  });
}

function showCustomerIdBadge(id) {
  // Create or update customer ID badge
  let badge = document.getElementById('customer-id-badge');
  if (!badge) {
    badge = document.createElement('div');
    badge.id = 'customer-id-badge';
    badge.className = 'customer-id-badge';
    document.querySelector('.chat-container').prepend(badge);
  }
  
  badge.innerHTML = `
    <span>ID: ${id}</span>
    <button class="id-clear-btn">✖</button>
  `;
  
  // Add event listener to clear button
  badge.querySelector('.id-clear-btn').addEventListener('click', () => {
    currentCustomerId = null;
    localStorage.removeItem('customerId');
    badge.remove();
    askForCustomerId();
  });
}

function askForCustomerId() {
  needsCustomerId = true;
  
  // Show prompt for customer ID
  const idPrompt = document.createElement('div');
  idPrompt.className = 'customer-id-prompt';
  idPrompt.innerHTML = `
    <p>${translations[currentLanguage].askCustomerId}</p>
    <div class="id-input-container">
      <input type="text" id="customer-id-input" placeholder="ID: ABC123">
      <button id="submit-id-btn">→</button>
    </div>
  `;
  
  messageList.appendChild(idPrompt);
  messageList.scrollTop = messageList.scrollHeight;
  
  // Focus on input
  setTimeout(() => {
    const idInput = document.getElementById('customer-id-input');
    if (idInput) idInput.focus();
  }, 100);
  
  // Add event listeners
  setTimeout(() => {
    const idInput = document.getElementById('customer-id-input');
    const submitBtn = document.getElementById('submit-id-btn');
    
    if (idInput && submitBtn) {
      idInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          submitBtn.click();
        }
      });
      
      submitBtn.addEventListener('click', () => {
        const id = idInput.value.trim();
        if (id) {
          sendMessage(id);
          idPrompt.remove();
          needsCustomerId = false;
        }
      });
    }
  }, 100);
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
        language: currentLanguage,
        customer_id: currentCustomerId || null
      })
    });
    
    const data = await response.json();
    messageList.removeChild(typing);
    
    // Check if the response includes a customer ID (from ID input)
    if (data.customer_id) {
      currentCustomerId = data.customer_id;
      localStorage.setItem('customerId', currentCustomerId);
      showCustomerIdBadge(currentCustomerId);
    }
    
    // Check if we need to ask for customer ID
    if (data.needs_customer_id) {
      chatHistory.push({ role: 'assistant', content: data.response });
      const messageElement = appendMessage(data.response, 'assistant');
      askForCustomerId();
      return;
    }
    
    // Normal response flow
    chatHistory.push({ role: 'assistant', content: data.response });
    const messageElement = appendMessage(data.response, 'assistant');
    
    if (needsEscalation(text)) {
      showEscalationPrompt(messageElement);
    } else {
      addFeedbackButtons(messageElement);
    }
  } catch (error) {
    console.error("API Error:", error);
    messageList.removeChild(typing);
    appendMessage('Connection error. Please try again.', 'assistant error');
  }
}

// Rest of functions remain the same...
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
  
  // Add feedback text + thumbs up/down
  container.innerHTML = `
    ${translations[currentLanguage].feedback}
    <button class="feedback-btn positive">👍</button>
    <button class="feedback-btn negative">👎</button>
  `;
  
  // Add event listeners
  container.querySelector('.positive').addEventListener('click', e => handleFeedback(e.target, true));
  container.querySelector('.negative').addEventListener('click', e => handleFeedback(e.target, false));
  
  element.appendChild(container);
}

function handleFeedback(button, isPositive) {
  // Get the parent container for the feedback
  const feedbackContainer = button.parentElement;
  
  if (isPositive) {
    // Show positive message
    feedbackContainer.innerHTML = translations[currentLanguage].positiveFeedback;
  } else {
    // Show negative message and ask if they want to escalate
    feedbackContainer.innerHTML = translations[currentLanguage].negativeFeedback;
    
    // After showing negative feedback, show escalation option
    showEscalationPrompt(button.closest('.message'));
  }
  
  // Analytics event could be added here
  const feedbackData = {
    messageId: chatHistory.length - 1,
    wasHelpful: isPositive,
    messageContent: chatHistory[chatHistory.length - 1].content
  };
  
  // Could log this data or send to analytics service
  console.log("Feedback:", feedbackData);
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
    escalationContainer.remove();
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

function initiateEmailSupport() {
  const context = getInvoiceContext();
  const subject = `Support Request - ${context.invoiceId || 'Utility Bill'}`;
  const body = `Customer ID: ${currentCustomerId || 'Unknown'}\n\nConversation History:\n\n${chatHistory.map(m => `${m.role}: ${m.content}`).join('\n')}\n\n`;
  
  window.location.href = `mailto:support@utility.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  appendMessage(translations[currentLanguage].escalationConfirm, 'assistant');
}

function decodeBase64(str) {
  if (!str) return null;
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
    name: decodeBase64(params.get('name')) || 'Customer',
    customerId: currentCustomerId
  };
}

function extractCustomerId() {
  // Get customer ID from URL parameter
  const params = new URLSearchParams(window.location.search);
  return params.get('customerId') || params.get('cid') || null;
}

function personalizeGreeting() {
  const context = getInvoiceContext();
  const greeting = document.getElementById('greeting');
  if (greeting && context.name) {
    greeting.textContent = translations[currentLanguage].greeting(context.name);
  }
}

// Event listeners
languageToggle.addEventListener('change', updateLanguage);

sendBtn.addEventListener('click', () => {
  const text = input.value.trim();
  if (text) {
    sendMessage(text);
    if (hidePromptsAfterFirstQuery && promptList.style.display !== 'none') {
      promptList.style.display = 'none'; // Hide prompts after first message
    }
  }
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