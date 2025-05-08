from gpt4all import GPT4All
from typing import Dict, Any
import json
import re
import os
from functools import lru_cache

class UtilityBillLLM:
    def __init__(self, model_name="mistral-7b-instruct-v0.1.Q4_0.gguf"):
        self.model_path = os.path.join(os.path.dirname(__file__), "../models")
        self.model = GPT4All(model_name, model_path=self.model_path)
        self.knowledge = self.load_knowledge()
        self.language_instructions = {
            'en': "Answer in English with:\n1. Clear explanation\n2. Legal basis if relevant\n3. Next steps if needed",
            'de': "Antworte auf Deutsch mit:\n1. Klare Erklärung\n2. Rechtsgrundlage falls zutreffend\n3. Nächste Schritte falls nötig"
        }
        
    def load_knowledge(self):
        with open(os.path.join(os.path.dirname(__file__), "data/knowledge_base.json")) as f:
            return json.load(f)
    
    def get_response(self, query: str, bill_context: Dict[str, Any] = None, language: str = 'en') -> str:
        if self.is_escalation_request(query, language):
            return self.format_escalation_response(language)
            
        kb_response = self.check_knowledge(query,language)
        if kb_response:
            return self.format_response(kb_response, language)
            
        prompt = self.build_prompt(query, bill_context, language)
        response = self.model.generate(prompt, max_tokens=300)
        return self.format_response(response, language)
    
    def is_escalation_request(self, query: str, language: str) -> bool:
        escalation_triggers = {
            'en': ['escalate', 'contact support', 'talk to human'],
            'de': ['eskalieren', 'support kontaktieren', 'mit mensch sprechen']
        }
        return any(trigger in query.lower() for trigger in escalation_triggers[language])
    
    def format_escalation_response(self, language: str) -> str:
        responses = {
            'en': "I've escalated your request to our support team. They'll contact you within 24 hours. 🔔",
            'de': "Ich habe Ihre Anfrage an unser Support-Team weitergeleitet. Sie werden sich innerhalb von 24 Stunden bei Ihnen melden. 🔔"
        }
        return responses[language]

    @lru_cache(maxsize=100)
    def check_knowledge(self, query: str, language) -> str:
        itemkey = 'input_'+language
        for category in self.knowledge['utility_invoice_queries'].values():
            for item in category:
                if item[itemkey].lower() in query.lower():
                    return item['response']
        return ""
    
    def build_prompt(self, query, context, language):
        context_str = ""
        if context:
            context_str = "Invoice Context:\n" + "\n".join(
                [f"- {k}: {v}" for k,v in context.items()]
            )
            
        return f"""You are KlarBill, a utility billing expert. Use this context:
{context_str}

{self.language_instructions[language]}

Question: {query}
Answer:"""
    
    def format_response(self, response: str, language: str) -> str:
        response = re.sub(r'(§\d+ \w+)', r'**\1**', response)
        if language == 'de':
            response = response.replace('**', '')  # German formatting
        return response.strip()