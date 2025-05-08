# backend/llm_service.py
import os
import re
import json
import faiss
import numpy as np
import requests
import tiktoken
import math
import operator
from typing import Dict, Any, List, Optional, Tuple
from functools import lru_cache
from gpt4all import GPT4All
from sentence_transformers import SentenceTransformer

# Constants to improve detection
GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
FEEDBACK_PHRASES = {"not helpful", "wrong answer", "incorrect", "doesn't make sense", "that's wrong"}
FIREBASE_URL = "https://klarbill-ef564-default-rtdb.europe-west1.firebasedatabase.app/Invoices.json"

# Track conversation history
conversation_history = []

def calculate_expression(expression: str) -> str:
    """Safely evaluate a mathematical expression and return the result."""
    # Clean the expression
    expression = expression.strip()
    expression = re.sub(r'[^\d\s\+\-\*\/\(\)\.\,]', '', expression)
    expression = expression.replace(',', '.')  # Handle European decimal format
    
    # Basic calculator implementation for safety
    try:
        # Simple tokenization and parsing
        tokens = re.findall(r'(\d+\.?\d*|\+|\-|\*|\/|\(|\))', expression)
        
        def parse_expression():
            return parse_addition()
            
        def parse_addition():
            left = parse_multiplication()
            while tokens and tokens[0] in ['+', '-']:
                op = tokens.pop(0)
                right = parse_multiplication()
                if op == '+':
                    left += right
                else:
                    left -= right
            return left
            
        def parse_multiplication():
            left = parse_number()
            while tokens and tokens[0] in ['*', '/']:
                op = tokens.pop(0)
                right = parse_number()
                if op == '*':
                    left *= right
                else:
                    if right == 0:
                        raise ValueError("Division by zero")
                    left /= right
            return left
            
        def parse_number():
            if tokens[0] == '(':
                tokens.pop(0)  # Remove '('
                result = parse_expression()
                if tokens and tokens[0] == ')':  
                    tokens.pop(0)  # Remove ')'
                return result
            else:
                return float(tokens.pop(0))
                
        # Start parsing from the beginning
        result = parse_expression()
        
        # Format the result (no trailing zeros for whole numbers)
        if result == int(result):
            return str(int(result))
        return str(result)
    except Exception as e:
        return f"Error in calculation: {str(e)}"

def flatten_json(y, prefix=""):
    """Flatten nested JSON structure for easier context processing."""
    out = {}
    def flatten(x, name=""):
        if isinstance(x, dict):
            for a in x:
                flatten(x[a], f"{name}{a}.")
        elif isinstance(x, list):
            for i, a in enumerate(x):
                flatten(a, f"{name}{i}.")
        else:
            out[f"{name[:-1]}"] = x
    flatten(y, prefix)
    return out

def truncate_by_token_limit(text_lines: List[str], max_tokens: int = 1000) -> List[str]:
    """Truncate a list of text lines to fit within token limit."""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except:
        enc = tiktoken.get_encoding("gpt2")
    result = []
    token_count = 0
    for line in text_lines:
        tokens = enc.encode(line)
        if token_count + len(tokens) > max_tokens:
            break
        result.append(line)
        token_count += len(tokens)
    return result

def fetch_invoice_data(customer_id=None) -> Dict:
    """Fetch invoice data from Firebase."""
    try:
        response = requests.get(FIREBASE_URL)
        response.raise_for_status()
        data = response.json() or {}
        
        if customer_id and isinstance(data, dict):
            # Filter by customer_id if specified
            return {k: v for k, v in data.items() 
                   if isinstance(v, dict) and v.get('customerId') == customer_id}
        return data
    except Exception as e:
        print(f"Error fetching invoice data: {e}")
        return {}

class UtilityBillLLM:
    def __init__(self, model_name="mistral-7b-instruct-v0.1.Q4_0.gguf"):
        # Set up paths correctly
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(base_dir, "models")
        self.model = GPT4All(model_name, model_path=self.model_path)
        self.knowledge = self.load_knowledge()
        
        # Load invoice data
        self.invoice_data = {}
        
        # Load vector store if available
        self.vs_path = os.path.join(base_dir, "vectorstore")
        self.docs = []
        self.index = None
        self.embedder = None
        self.setup_vector_search()
        
        # Load system prompt
        instr_file = os.path.join(base_dir, "data", "instructions.txt")
        try:
            with open(instr_file, "r", encoding="utf-8") as f:
                self.system_prompt = f.read().strip()
        except FileNotFoundError:
            self.system_prompt = """You are KlarBill, an AI assistant specializing in utility bills. 
            You provide concise, helpful explanations about invoice calculations, legal regulations, and billing procedures.
            Always be precise, accurate, and straightforward."""
            
        # Language-specific templates
        self.language_templates = {
            'en': {
                'format': "As your utility bill assistant, I'll help you understand this clearly.",
                'escalation': "I've escalated your request to our support team. They will contact you within 24 hours. 🔔",
                'greeting': "Hello! How can I help you with your utility bill today?",
                'feedback_response': "I apologize that my previous response wasn't helpful. Would you like me to try again with a different approach or would you prefer to speak with a customer service representative?",
                'positive_feedback': "Thank you for your feedback! I'm glad I could help.",
                'math_error': "I'm sorry, but I couldn't perform that calculation. Please check the format and try again.",
                'no_data': "I'm sorry, but I couldn't find that information in your account. Would you like to speak with customer service for more details?"
            },
            'de': {
                'format': "Als Ihr Assistent für Versorgungsrechnungen helfe ich Ihnen, dies klar zu verstehen.",
                'escalation': "Ich habe Ihre Anfrage an unser Support-Team weitergeleitet. Sie werden sich innerhalb von 24 Stunden bei Ihnen melden. 🔔",
                'greeting': "Hallo! Wie kann ich Ihnen heute mit Ihrer Versorgungsrechnung helfen?",
                'feedback_response': "Ich entschuldige mich, dass meine vorherige Antwort nicht hilfreich war. Möchten Sie, dass ich es mit einem anderen Ansatz versuche, oder möchten Sie lieber mit einem Kundendienstmitarbeiter sprechen?",
                'positive_feedback': "Vielen Dank für Ihr Feedback! Ich freue mich, dass ich helfen konnte.",
                'math_error': "Es tut mir leid, aber ich konnte diese Berechnung nicht durchführen. Bitte überprüfen Sie das Format und versuchen Sie es erneut.",
                'no_data': "Es tut mir leid, aber ich konnte diese Information in Ihrem Konto nicht finden. Möchten Sie mit dem Kundendienst sprechen, um weitere Details zu erhalten?"
            }
        }
        
        # Initialize conversation context
        self.conversation_context = {
            'last_query': '',
            'last_response': '',
            'previous_queries': [],
            'customer_id': None,
            'language': 'en'
        }
    def ask_for_customer_id(self, language='en'):
        """Return a prompt asking for customer ID."""
        messages = {
            'en': "Before we start, could you please provide your customer ID? This helps me access your specific information.",
            'de': "Bevor wir beginnen, könnten Sie bitte Ihre Kundennummer angeben? Dies hilft mir, auf Ihre spezifischen Informationen zuzugreifen."
        }
        return messages.get(language, messages['en'])

    def is_customer_id_input(self, query):
        """Check if the input looks like a customer ID."""
        # Simple check for customer ID format (alphanumeric, typically 4-20 chars)
        stripped = query.strip()
        return (re.match(r'^[A-Za-z0-9_-]{4,20}$', stripped) is not None or 
                re.match(r'^ID:?\s*([A-Za-z0-9_-]{4,20})$', stripped) is not None)

    def extract_customer_id(self, query):
        """Extract customer ID from text."""
        stripped = query.strip()
        # Check for "ID: XXX" format
        id_match = re.match(r'^ID:?\s*([A-Za-z0-9_-]{4,20})$', stripped)
        if id_match:
            return id_match.group(1)
        # Otherwise return the raw input if it fits customer ID format
        if re.match(r'^[A-Za-z0-9_-]{4,20}$', stripped):
            return stripped
        return None
        
    def setup_vector_search(self):
        """Initialize vector search if files exist."""
        try:
            index_path = os.path.join(self.vs_path, "kb.faiss")
            docs_path = os.path.join(self.vs_path, "kb_docs.txt")
            
            # Load faiss index
            if os.path.exists(index_path):
                self.index = faiss.read_index(index_path)
                
                # Load document store
                if os.path.exists(docs_path):
                    with open(docs_path, "r", encoding="utf-8") as f:
                        self.docs = [line.strip() for line in f]
                        
                # Load sentence transformer
                self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
                print("✅ Vector search setup complete")
        except Exception as e:
            print(f"Error setting up vector search: {e}")
            # Fall back to simple keyword matching
            
    def load_knowledge(self):
        """Load knowledge base from JSON file."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        kb_path = os.path.join(base_dir, "data", "knowledge_base.json")
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print("Knowledge base file not found")
            return {"utility_invoice_queries": {}}
    
    def get_response(self, query: str, bill_context: Optional[Dict[str, Any]] = None, 
                    language: str = 'en', customer_id: Optional[str] = None) -> str:
        """Get a response to a user query with optimizations for speed."""
        # Update conversation context
        self.conversation_context['previous_queries'].append(self.conversation_context['last_query'])
        self.conversation_context['last_query'] = query
        self.conversation_context['language'] = language
        self.conversation_context['customer_id'] = customer_id
        
        # 1. Handle simple feedback responses
        if any(phrase in query.lower() for phrase in FEEDBACK_PHRASES):
            return self.language_templates[language]['feedback_response']
            
        # 2. Handle "yes"/"no" responses in context
        if query.lower() in ['yes', 'ja']:
            return self.handle_yes_response(language)
        
        if query.lower() in ['no', 'nein']:
            return self.handle_no_response(language)
        
        # 3. Handle greetings faster without LLM call
        q_lower = query.lower().strip()
        if q_lower in GREETINGS:
            return self.language_templates[language]['greeting']
            
        # 4. Check for math calculations
        math_match = re.search(r'(\d+\s*[\+\-\*\/]\s*\d+.*)', query)
        if math_match or "calculate" in query.lower() or "compute" in query.lower():
            math_expr = math_match.group(1) if math_match else re.sub(r'[^0-9\+\-\*\/\(\)\.]', '', query)
            if math_expr:
                result = calculate_expression(math_expr)
                if "Error" not in result:
                    return result
                else:
                    return self.language_templates[language]['math_error']
            
        # 5. Check for escalation requests
        if self.is_escalation_request(query, language):
            return self.language_templates[language]['escalation']
        
        # 6. Check for consumption or bill amount queries
        if self.is_invoice_data_query(query):
            return self.get_invoice_data_response(query, bill_context, customer_id, language)
        
        # 7. First check exact knowledge base matches (fastest)
        kb_response = self.check_knowledge(query)
        if kb_response:
            self.conversation_context['last_response'] = kb_response
            return self.format_response(kb_response, language)
        
        # 8. Then try vector similarity search (medium speed)
        relevant_context = ""
        if self.index is not None and self.embedder is not None and self.docs:
            relevant_context = self.retrieve_context(query, k=1)
        
        # 9. Update invoice data
        if bill_context:
            self.invoice_data = bill_context
        elif not self.invoice_data:
            self.invoice_data = fetch_invoice_data(customer_id)
            
        # 10. Prepare invoice context
        invoice_context = self.prepare_invoice_context(self.invoice_data, customer_id)
        
        # 11. Build prompt with conversation history for better context
        prompt = self.build_prompt(query, invoice_context, relevant_context, language)
        
        # 12. Generate response
        response = self.model.generate(prompt, max_tokens=300)
        self.conversation_context['last_response'] = response
        
        return self.format_response(response, language)
    
    def handle_yes_response(self, language):
        """Handle 'yes' responses based on context."""
        last_query = self.conversation_context['last_query']
        
        # If last query was feedback related
        if any(phrase in last_query.lower() for phrase in FEEDBACK_PHRASES):
            return self.language_templates[language]['escalation']
            
        # If last response contained an escalation question
        if "speak with customer service" in self.conversation_context['last_response'].lower():
            return self.language_templates[language]['escalation']
            
        # Default response
        return self.get_response("I would like more information about my bill", 
                               language=language, 
                               customer_id=self.conversation_context['customer_id'])
    
    def handle_no_response(self, language):
        """Handle 'no' responses based on context."""
        return f"{self.language_templates[language]['greeting']} Please let me know what you'd like to know about your utility bill."
    
    def is_invoice_data_query(self, query):
        """Detect if query is asking for specific invoice data."""
        query_lower = query.lower()
        invoice_keywords = [
            'consumption total', 'my bill', 'how much do i owe', 
            'my usage', 'consumption amount', 'total cost',
            'verbrauch gesamt', 'meine rechnung', 'wie viel schulde ich',
            'mein verbrauch', 'verbrauchsmenge', 'gesamtkosten'
        ]
        return any(keyword in query_lower for keyword in invoice_keywords)
    
    def get_invoice_data_response(self, query, bill_context, customer_id, language):
        """Extract actual invoice data for the customer."""
        try:
            # Ensure we have invoice data
            if not bill_context:
                bill_context = self.invoice_data or fetch_invoice_data(customer_id)
            
            if not bill_context:
                return self.language_templates[language]['no_data']
                
            # Extract key information based on query
            query_lower = query.lower()
            response = ""
            
            # Handle specific query types
            if any(term in query_lower for term in ['consumption', 'usage', 'verbrauch']):
                for invoice_id, invoice in bill_context.items():
                    if isinstance(invoice, dict):
                        # Try to find consumption data in various possible locations
                        consumption = None
                        if 'consumption' in invoice:
                            consumption = invoice['consumption']
                        elif 'usage' in invoice:
                            consumption = invoice['usage']
                        elif 'details' in invoice and 'consumption' in invoice['details']:
                            consumption = invoice['details']['consumption']
                        
                        if consumption:
                            unit = invoice.get('unit', 'kWh')
                            if language == 'en':
                                response = f"⚡ Your total consumption is {consumption} {unit}."
                            else:
                                response = f"⚡ Ihr Gesamtverbrauch beträgt {consumption} {unit}."
                            break
            
            elif any(term in query_lower for term in ['cost', 'amount', 'bill', 'owe', 'schulde', 'rechnung', 'kosten']):
                for invoice_id, invoice in bill_context.items():
                    if isinstance(invoice, dict):
                        # Try to find amount data
                        amount = None
                        if 'totalAmount' in invoice:
                            amount = invoice['totalAmount']
                        elif 'amount' in invoice:
                            amount = invoice['amount']
                        elif 'total' in invoice:
                            amount = invoice['total']
                        
                        if amount:
                            currency = invoice.get('currency', '€')
                            if language == 'en':
                                response = f"💰 Your total bill amount is {amount} {currency}."
                            else:
                                response = f"💰 Ihr Gesamtrechnungsbetrag beträgt {amount} {currency}."
                            break
            
            # Return found data or fallback to AI response
            if response:
                return response
                
            # If no specific data was found, fall back to AI response
            flat_context = self.prepare_invoice_context(bill_context, customer_id)
            prompt = f"""Based on this invoice data:
{flat_context}

The user is asking: "{query}"
Provide a direct answer with the specific numbers from the invoice data:"""

            ai_response = self.model.generate(prompt, max_tokens=100)
            return self.format_response(ai_response, language)
                
        except Exception as e:
            print(f"Error retrieving invoice data: {e}")
            return self.language_templates[language]['no_data']
    
    def prepare_invoice_context(self, bill_context, customer_id=None):
        """Extract relevant invoice details for the specific customer."""
        if not bill_context:
            return ""

        # Match customer ID to JSON structure
        if customer_id and isinstance(bill_context, dict):
            for invoice_id, invoice_data in bill_context.items():
                customer_info = invoice_data.get('Data', {}).get('Customer', {})
                if customer_info.get('customerNumber') == customer_id:
                    return self.flatten_invoice(invoice_data.get('Data', {}))
        
        return self.flatten_invoice(bill_context)
    
    def flatten_invoice(self, invoice_data):
        """Convert invoice data to a flat string with key information."""
        if isinstance(invoice_data, dict):
            flat = flatten_json(invoice_data)
            # Focus on most important invoice fields
            important_keys = [
                k for k in flat.keys() 
                if any(term in k.lower() for term in 
                      ['amount', 'price', 'cost', 'rate', 'date', 'consumption', 
                       'period', 'customer', 'total', 'calculation', 'tax'])
            ]
            
            if important_keys:
                lines = [f"- {k}: {flat[k]}" for k in important_keys]
            else:
                # Fallback to all fields but limited
                lines = [f"- {k}: {v}" for k, v in list(flat.items())[:20]]
                
            # Use token truncation from llm_engine.py
            truncated_lines = truncate_by_token_limit(lines, max_tokens=600)
            return "\n".join(truncated_lines)
        
        return str(invoice_data)
    
    def is_escalation_request(self, query: str, language: str) -> bool:
        """Detect if the user wants to escalate the issue."""
        escalation_triggers = {
            'en': ['escalate', 'contact support', 'talk to human', 'speak to agent', 'need help', 
                  'talk to a person', 'customer service'],
            'de': ['eskalieren', 'support kontaktieren', 'mit mensch sprechen', 'brauche hilfe',
                  'mit einer person sprechen', 'kundendienst']
        }
        return any(trigger in query.lower() for trigger in escalation_triggers.get(language, escalation_triggers['en']))
    
    def retrieve_context(self, query: str, k: int = 1) -> str:
        """Find relevant knowledge using vector similarity."""
        if not self.index or not self.docs or not self.embedder:
            return ""
            
        vec = self.embedder.encode([query], normalize_embeddings=True)
        _, I = self.index.search(np.array(vec).astype("float32"), k)
        relevant_docs = "\n".join(self.docs[i] for i in I[0] if i < len(self.docs))
        return relevant_docs

    @lru_cache(maxsize=100)
    def check_knowledge(self, query: str) -> str:
        """Check if query has an exact match in knowledge base."""
        query_lower = query.lower()
        
        for category in self.knowledge.get('utility_invoice_queries', {}).values():
            for item in category:
                if item.get('input', '').lower() in query_lower:
                    return item.get('response', '')
        return ""
    
    def build_prompt(self, query, invoice_context, relevant_context, language):
        """Build an optimized prompt for faster inference."""
        # Include system prompt
        system = self.system_prompt
        
        # Include conversation history for context
        conv_history = ""
        if self.conversation_context['previous_queries']:
            last_queries = self.conversation_context['previous_queries'][-2:]  # Last 2 queries
            conv_history = "Recent conversation:\n" + "\n".join([f"User: {q}" for q in last_queries if q])
        
        # Include context sources
        context_parts = []
        if invoice_context:
            context_parts.append(f"Invoice Context:\n{invoice_context}")
        if relevant_context:
            context_parts.append(f"Relevant Information:\n{relevant_context}")
        if conv_history:
            context_parts.append(conv_history)
        
        context_str = "\n\n".join(context_parts)
        
        # Format instruction by language
        format_instr = self.language_templates[language]['format']
        
        # Final prompt assembly
        return f"""{system}

{context_str}

{format_instr}

User Question: {query}
Answer:"""
    
    def format_response(self, response: str, language: str) -> str:
        """Clean up response for presentation."""
        # Remove any system artifacts
        response = re.sub(r'^Answer:\s*', '', response)
        
        # Highlight legal references
        response = re.sub(r'(§\d+[\w\s-]*)', r'**\1**', response)
        
        # Insert emoji for better UX if not already present
        if not any(emoji in response for emoji in ['💰', '⚡', '📜', '🔔']):
            if 'price' in response.lower() or 'cost' in response.lower():
                response = "💰 " + response
            elif 'consumption' in response.lower() or 'usage' in response.lower():
                response = "⚡ " + response
            elif 'law' in response.lower() or 'regulation' in response.lower():
                response = "📜 " + response
            
        if language == 'de':
            response = response.replace('**', '')  # German formatting
            
        return response.strip()
