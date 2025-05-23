# agentic_llm_service.py

import os
import re
import requests
from typing import Dict, Any, Optional, Tuple, List
from gpt4all import GPT4All
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

FIREBASE_INVOICES_URL = "https://klarbill-3de73-default-rtdb.europe-west1.firebasedatabase.app/invoices.json"

class QueryType(Enum):
    GREETING = "greeting"
    SIMPLE_FACT = "simple_fact"
    CALCULATION = "calculation" 
    COMPARISON = "comparison"
    EXPLANATION = "explanation"
    REGULATORY = "regulatory"
    TROUBLESHOOTING = "troubleshooting"

@dataclass
class ResponseFormat:
    concise: bool = False
    detailed_calculation: bool = False
    include_regulatory_context: bool = False
    personalized: bool = True

class GermanEnergyRegulations:
    """Knowledge base for German energy regulations and billing components"""
    
    ENERGY_COMPONENTS = {
        "netznutzung": {
            "name_de": "Netznutzung",
            "name_en": "Grid Usage",
            "explanation_de": "Kosten für die Nutzung des Stromnetzes zur Übertragung und Verteilung",
            "explanation_en": "Costs for using the electricity grid for transmission and distribution",
            "regulated_by": "Bundesnetzagentur"
        },
        "messstellenbetrieb": {
            "name_de": "Messstellenbetrieb", 
            "name_en": "Metering Operation",
            "explanation_de": "Kosten für den Betrieb und die Wartung der Messeinrichtungen",
            "explanation_en": "Costs for operation and maintenance of measuring equipment",
            "regulated_by": "MessstellenbetriebsG"
        },
        "stromsteuer": {
            "name_de": "Stromsteuer",
            "name_en": "Electricity Tax", 
            "explanation_de": "Bundessteuer auf Stromverbrauch, derzeit 2,05 ct/kWh",
            "explanation_en": "Federal tax on electricity consumption, currently 2.05 ct/kWh",
            "current_rate": "0.0205"
        },
        "kwkg_umlage": {
            "name_de": "KWKG-Umlage",
            "name_en": "CHP Levy",
            "explanation_de": "Förderung von Kraft-Wärme-Kopplung zur Energieeffizienz",
            "explanation_en": "Support for combined heat and power for energy efficiency"
        },
        "offshore_umlage": {
            "name_de": "Offshore-Netzumlage", 
            "name_en": "Offshore Grid Levy",
            "explanation_de": "Finanzierung der Offshore-Windpark-Netzanbindung",
            "explanation_en": "Financing of offshore wind farm grid connections"
        },
        "konzessionsabgabe": {
            "name_de": "Konzessionsabgabe",
            "name_en": "Concession Fee", 
            "explanation_de": "Entgelt an Gemeinden für die Nutzung öffentlicher Verkehrswege",
            "explanation_en": "Fee to municipalities for using public roads"
        }
    }

    RECENT_CHANGES_2025 = {
        "electricity_tax_reduction": "Electricity tax for companies reduced to EU minimum 0.05 ct/kWh for 2024-2025",
        "smart_meter_rollout": "Accelerated smart meter deployment: 20% by 2025, 50% by 2028, 95% by 2030",
        "grid_expansion": "€400 billion investment in grid expansion affecting future grid charges",
        "renewable_target": "80% renewable electricity by 2030, climate neutrality by 2035"
    }

def fetch_invoice_data(customer_number=None, invoice_number=None) -> Tuple[bool, Dict[str, Any]]:
    try:
        response = requests.get(FIREBASE_INVOICES_URL)
        if response.status_code != 200:
            return False, {}

        data = response.json()
        if not isinstance(data, dict):
            return False, {}

        if invoice_number and invoice_number.strip():
            filtered = {
                k: v for k, v in data.items()
                if v.get("Data", {}).get("ProzessDaten", {}).get("ProzessDatenElement", {}).get("invoiceNumber") == invoice_number
            }
            return bool(filtered), filtered

        if customer_number and customer_number.strip():
            filtered = {
                k: v for k, v in data.items()
                if v.get("Data", {}).get("ProzessDaten", {}).get("ProzessDatenElement", {})
                .get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {}).get("customerNumber") == customer_number
            }
            return bool(filtered), filtered

        return False, {}
    except Exception:
        return False, {}

class IntelligentInvoiceAnalyzer:
    """Advanced invoice analysis with deep contextual understanding"""
    
    def __init__(self, invoice_data: Dict[str, Any]):
        self.invoice_data = invoice_data
        self.process_data = invoice_data.get("ProzessDaten", {}).get("ProzessDatenElement", {})
        self.consumption_data = invoice_data.get("Abrechnungsmengen", {}).get("AbrechnungsmengenElement", [])
        self.billing_items = invoice_data.get("Abrechnungspositionen", {}).get("AbrechnungspositionenElement", [])
        self.partner_data = self.process_data.get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {})
        self.cost_breakdown = invoice_data.get("Kostenblock", {}).get("KostenblockElement", [])
        
    def get_total_consumption(self) -> Tuple[float, str, str]:
        """Get total consumption with period details"""
        total = sum(float(item.get("consumption", 0)) for item in self.consumption_data)
        period_from = self.process_data.get("invoicePeriodFrom", "")
        period_to = self.process_data.get("invoicePeriodTo", "")
        return total, period_from, period_to
    
    def analyze_unusual_charges(self) -> List[Dict[str, Any]]:
        """Identify and explain unusual or high charges"""
        unusual_items = []
        
        # Check for high basic charges
        for item in self.billing_items:
            if item.get("priceType") == "BASIC_RATE":
                amount = float(item.get("amount", 0))
                if amount > 100:  # High basic charge threshold
                    unusual_items.append({
                        "type": "high_basic_charge",
                        "amount": amount,
                        "explanation": "Higher than typical basic charge, possibly due to new contract setup or tariff change"
                    })
        
        # Check for zero usage charges (like in the provided invoice)
        usage_charges = [item for item in self.billing_items if item.get("priceType") == "USAGE_RATE"]
        if all(float(item.get("amount", 0)) == 0 for item in usage_charges):
            unusual_items.append({
                "type": "zero_usage_charges", 
                "explanation": "No usage charges applied - this typically occurs in initial/setup bills or when consumption is covered by prepayments"
            })
            
        return unusual_items
    
    def get_detailed_cost_breakdown(self) -> Dict[str, Any]:
        """Provide comprehensive cost analysis"""
        breakdown = {
            "grid_and_metering": {"amount": 0, "percentage": 0, "components": []},
            "taxes_and_levies": {"amount": 0, "percentage": 0, "components": []}, 
            "energy_supply": {"amount": 0, "percentage": 0, "components": []},
            "bonuses": {"amount": 0, "components": []}
        }
        
        total_gross = float(self.process_data.get("invoiceAmount", 0))
        
        for cost_block in self.cost_breakdown:
            name = cost_block.get("printItemName", "")
            amount = float(cost_block.get("amount", 0))
            percentage = float(cost_block.get("percentageAmount", 0))
            
            if "Netz" in name or "Messung" in name:
                breakdown["grid_and_metering"]["amount"] = amount
                breakdown["grid_and_metering"]["percentage"] = percentage
                
            elif "Steuer" in name or "Umlage" in name:
                breakdown["taxes_and_levies"]["amount"] = amount  
                breakdown["taxes_and_levies"]["percentage"] = percentage
                
            elif "Beschaffung" in name or "Vertrieb" in name:
                breakdown["energy_supply"]["amount"] = amount
                breakdown["energy_supply"]["percentage"] = percentage
        
        # Add bonus information
        bonus_amount = float(self.process_data.get("bonus", 0))
        if bonus_amount != 0:
            breakdown["bonuses"]["amount"] = bonus_amount
            
        return breakdown

class ContextualQueryAnalyzer:
    """Analyzes user queries for intent and determines appropriate response strategy"""
    
    GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening",
                "hallo", "guten morgen", "guten abend", "servus", "grüß gott", "hallo"}
    
    SIMPLE_FACT_PATTERNS = [
        r"(total|gesamt).*consumption|verbrauch",
        r"invoice.*amount|rechnungsbetrag", 
        r"customer.*number|kundennummer",
        r"how much.*did i (use|consume)|wieviel.*verbraucht"
    ]
    
    CALCULATION_PATTERNS = [
        r"(how.*calculated|calculation|breakdown|berechnung|aufschlüsselung)",
        r"(why.*cost|warum.*kostet)",
        r"(explain.*charge|erkläre.*gebühr)",
        r"(show.*detail|zeige.*detail)"
    ]
    
    COMPARISON_PATTERNS = [
        r"(compared? to|verglichen mit|unterschied)",
        r"(last.*bill|letzte.*rechnung)",
        r"(average|durchschnitt)",
        r"(higher|lower|höher|niedriger)"
    ]
    
    def __init__(self, conversation_history: List[str] = None):
        self.conversation_history = conversation_history or []
        
    def analyze_query(self, query: str) -> Tuple[QueryType, ResponseFormat]:
        """Analyze query and determine response strategy"""
        query_lower = query.lower()
        
        # Check for greetings
        if any(greet in query_lower for greet in self.GREETINGS):
            return QueryType.GREETING, ResponseFormat(concise=True, personalized=True)
        
        # Check for simple facts
        if any(re.search(pattern, query_lower) for pattern in self.SIMPLE_FACT_PATTERNS):
            if len(query.split()) <= 8:  # Short query = concise response
                return QueryType.SIMPLE_FACT, ResponseFormat(concise=True, personalized=True)
            else:
                return QueryType.SIMPLE_FACT, ResponseFormat(concise=False, personalized=True)
        
        # Check for calculation requests
        if any(re.search(pattern, query_lower) for pattern in self.CALCULATION_PATTERNS):
            return QueryType.CALCULATION, ResponseFormat(
                detailed_calculation=True, 
                include_regulatory_context=True,
                personalized=True
            )
        
        # Check for comparisons
        if any(re.search(pattern, query_lower) for pattern in self.COMPARISON_PATTERNS):
            return QueryType.COMPARISON, ResponseFormat(
                detailed_calculation=True,
                personalized=True
            )
        
        # Default to explanation with regulatory context
        return QueryType.EXPLANATION, ResponseFormat(
            include_regulatory_context=True,
            personalized=True
        )

class AgenticUtilityBillLLM:
    """Intelligent, contextual utility bill assistant with sophisticated reasoning"""
    
    def __init__(self, model_name="mistral-7b-instruct-v0.1.Q4_0.gguf"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(base_dir, "models")
        self.model = GPT4All(model_name, model_path=self.model_path)
        
        self.regulations = GermanEnergyRegulations()
        self.conversation_context = {
            'queries': [],
            'language': 'en',
            'customer_data': {},
            'current_invoice': {}
        }
        
    def validate_number(self, customer_number=None, invoice_number=None) -> Tuple[bool, Dict]:
        return fetch_invoice_data(customer_number, invoice_number)
    
    def build_contextual_prompt(self, query: str, analyzer: IntelligentInvoiceAnalyzer, 
                               query_type: QueryType, response_format: ResponseFormat,
                               language: str = 'en') -> str:
        """Build sophisticated, context-aware prompt"""
        
        # Customer information
        partner = analyzer.partner_data
        salutation = partner.get("salutation", "Dear Customer")
        first_name = partner.get("name", "")
        customer_name = f"{first_name} {partner.get('name', '')}".strip()
        
        # Invoice analysis
        total_consumption, period_from, period_to = analyzer.get_total_consumption()
        cost_breakdown = analyzer.get_detailed_cost_breakdown()
        unusual_charges = analyzer.analyze_unusual_charges()
        
        # Base system instruction
        system_instruction = f"""You are KlarBill, an intelligent energy billing assistant with deep expertise in German energy regulations and billing practices. You provide nuanced, contextual responses that adapt to the user's specific query.

CUSTOMER CONTEXT:
- Customer: {salutation} ({customer_name})
- Invoice Period: {period_from} to {period_to}
- Total Consumption: {total_consumption} kWh
- Invoice Amount: €{analyzer.process_data.get('invoiceAmount', 0)}
- Language: {'German' if language == 'de' else 'English'}

INTELLIGENT RESPONSE GUIDELINES:
1. PERSONALIZATION: Use the customer's name and salutation naturally
2. ADAPTIVE DEPTH: {"Provide concise, direct answers" if response_format.concise else "Provide comprehensive explanations with context"}
3. CALCULATION TRANSPARENCY: {"Include detailed breakdown with regulatory explanations" if response_format.detailed_calculation else "Focus on key numbers"}
4. CONVERSATIONAL: Build on previous context, avoid robotic responses
5. EDUCATIONAL: Explain the "why" behind charges when relevant

BILLING INTELLIGENCE:
- This invoice shows: {', '.join([item['type'] for item in unusual_charges]) if unusual_charges else 'standard charges'}
- Cost Structure: Grid/Metering {cost_breakdown['grid_and_metering']['percentage']:.1f}%, Taxes/Levies {cost_breakdown['taxes_and_levies']['percentage']:.1f}%, Energy Supply {cost_breakdown['energy_supply']['percentage']:.1f}%
"""

        if response_format.include_regulatory_context:
            system_instruction += f"""
REGULATORY CONTEXT (2025):
- Smart meter rollout accelerating (95% by 2030)
- €400 billion grid expansion affecting future charges
- 80% renewable target by 2030
- Electricity tax reduced for companies (0.05 ct/kWh)
"""

        # Add detailed invoice data for calculations
        if response_format.detailed_calculation:
            system_instruction += f"""
DETAILED BILLING DATA:
- Basic Charges: €{sum(float(item.get('amount', 0)) for item in analyzer.billing_items if item.get('priceType') == 'BASIC_RATE')}
- Usage Charges: €{sum(float(item.get('amount', 0)) for item in analyzer.billing_items if item.get('priceType') == 'USAGE_RATE')}  
- Tax Amount: €{analyzer.process_data.get('taxAmount', 0)}
- Bonus Applied: €{analyzer.process_data.get('bonus', 0)}
- Net Amount: €{analyzer.process_data.get('netInvoiceAmount', 0)}

COMPONENT BREAKDOWN:
{self._format_component_details(analyzer)}
"""

        # Add query-specific context
        query_context = f"\nCURRENT QUERY: {query}\nQUERY TYPE: {query_type.value}\n"
        
        # Add conversation history if available
        if self.conversation_context['queries']:
            recent_queries = self.conversation_context['queries'][-3:]  # Last 3 queries
            query_context += f"CONVERSATION CONTEXT: {'; '.join(recent_queries)}\n"
        
        return system_instruction + query_context + "\nProvide your response:"

    def _format_component_details(self, analyzer: IntelligentInvoiceAnalyzer) -> str:
        """Format detailed component breakdown for prompts"""
        details = []
        for item in analyzer.billing_items:
            if float(item.get('amount', 0)) > 0:
                details.append(f"- {item.get('name', 'Unknown')}: €{item.get('amount', 0)} ({'Base' if item.get('priceType') == 'BASIC_RATE' else 'Usage'} charge)")
        return '\n'.join(details)

    def get_response(self, query: str, bill_context: Optional[Dict[str, Any]] = None,
                    language: str = 'en', customer_number: Optional[str] = None,
                    invoice_number: Optional[str] = None) -> Dict[str, Any]:
        
        # Update conversation context
        self.conversation_context['queries'].append(query)
        self.conversation_context['language'] = language
        
        # Fetch invoice data if not provided
        if not bill_context:
            is_valid, bill_context = self.validate_number(customer_number, invoice_number)
            if not is_valid:
                return {
                    "text": "I couldn't find your invoice data. Could you please verify your customer or invoice number?",
                    "structured": {},
                    "needs_invoice_number": False
                }

        # Handle multiple invoices
        if customer_number and not invoice_number and len(bill_context) > 1:
            invoice_suggestions = [
                v["Data"]["ProzessDaten"]["ProzessDatenElement"]["invoiceNumber"]
                for v in bill_context.values()
            ]
            return {
                "text": "I found multiple invoices for your account. Please specify which invoice you'd like me to analyze:",
                "structured": {},
                "needs_invoice_number": True,
                "invoice_suggestions": invoice_suggestions
            }

        # Get the invoice data
        invoice = next(iter(bill_context.values()), {}).get("Data", {})
        if not invoice:
            return {
                "text": "I couldn't access your invoice details. Please try again.",
                "structured": {}, 
                "needs_invoice_number": False
            }

        # Initialize analyzers
        analyzer = IntelligentInvoiceAnalyzer(invoice)
        query_analyzer = ContextualQueryAnalyzer(self.conversation_context['queries'])
        
        # Analyze query and determine response strategy
        query_type, response_format = query_analyzer.analyze_query(query)
        
        # Build contextual prompt
        prompt = self.build_contextual_prompt(query, analyzer, query_type, response_format, language)
        
        # Generate response with appropriate parameters
        max_tokens = 1000 if response_format.concise else 1800
        response = self.model.generate(prompt, max_tokens=max_tokens, temp=0.3).strip()
        
        # Prepare structured data
        total_consumption, period_from, period_to = analyzer.get_total_consumption()
        cost_breakdown = analyzer.get_detailed_cost_breakdown()
        
        structured_data = {
            "customer_name": analyzer.partner_data.get("firstName", "") + " " + analyzer.partner_data.get("name", ""),
            "salutation": analyzer.partner_data.get("salutation", ""),
            "consumption": total_consumption,
            "consumption_period": f"{period_from} to {period_to}",
            "invoice_amount": analyzer.process_data.get("invoiceAmount"),
            "net_amount": analyzer.process_data.get("netInvoiceAmount"), 
            "tax_amount": analyzer.process_data.get("taxAmount"),
            "bonus": analyzer.process_data.get("bonus"),
            "invoice_number": analyzer.process_data.get("invoiceNumber"),
            "cost_breakdown": cost_breakdown,
            "unusual_charges": analyzer.analyze_unusual_charges(),
            "query_type": query_type.value,
            "response_format": {
                "concise": response_format.concise,
                "detailed_calculation": response_format.detailed_calculation,
                "regulatory_context": response_format.include_regulatory_context
            }
        }
        
        return {
            "text": response,
            "structured": structured_data,
            "needs_invoice_number": False
        }

# Example usage and testing
if __name__ == "__main__":
    llm = AgenticUtilityBillLLM()
    
    # Test with different query types
    test_queries = [
        "Hello! How much electricity did I consume this year?",  # Simple fact
        "Can you explain how my bill amount was calculated?",    # Detailed calculation
        "Why is my bill so high this time?",                    # Explanation with analysis
        "What's included in the grid charges?"                  # Regulatory explanation
    ]
    
    #customer_number = "10000593"  # From the sample invoice
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        response = llm.get_response(query, customer_number=customer_number)
        print(f"Response: {response['text']}")
        print(f"Query Type: {response['structured'].get('query_type', 'unknown')}")
        print("-" * 50)