from gpt4all import GPT4All
from typing import Dict, Any, List, Tuple, Optional
import json
import re
from functools import lru_cache
import datetime
import numpy as np

class UtilityBillLLM:
    def __init__(self, model_name="mistral-7b-instruct-v0.1.Q4_0.gguf"):
        self.model_path = "./models/"
        self.model = GPT4All(model_name, model_path=self.model_path)
        self.knowledge = self.load_knowledge()
        self.language_instructions = {
            'en': "Answer in English with:\n1. Clear explanation\n2. Legal basis if relevant\n3. Next steps if needed",
            'de': "Antworte auf Deutsch mit:\n1. Klare Erklärung\n2. Rechtsgrundlage falls zutreffend\n3. Nächste Schritte falls nötig"
        }
        self.intent_patterns = self._initialize_intent_patterns()
        self.energy_terms_glossary = self._load_energy_glossary()
        
    def _initialize_intent_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns for identifying user intents"""
        return {
            'total_amount': [
                r'total.*amount', r'total.*bill', r'how much.*pay', 
                r'final.*amount', r'invoice.*total', r'bill.*total',
                r'gesamtbetrag', r'rechnungsbetrag', r'zu zahlen'
            ],
            'consumption': [
                r'consumption', r'how much.*used', r'energy.*used',
                r'meter reading', r'kWh.*used', r'usage', 
                r'verbrauch', r'zählerstand', r'stromverbrauch'
            ],
            'payment_plan': [
                r'payment.*plan', r'installment', r'monthly.*payment',
                r'abschlag', r'teilzahlung', r'zahlungsplan'
            ],
            'taxes_levies': [
                r'tax', r'levy', r'surcharge', r'fee', 
                r'steuer', r'umlage', r'abgabe', r'gebühr'
            ],
            'contract': [
                r'contract', r'term', r'cancel', r'period', r'start.*date', r'end.*date',
                r'vertrag', r'laufzeit', r'kündigen', r'beginn', r'ende'
            ],
            'high_bill': [
                r'high.*bill', r'expensive', r'increased', r'more than', r'why.*so much',
                r'higher than', r'comparison', r'average',
                r'hohe.*rechnung', r'teuer', r'gestiegen', r'mehr als', r'warum.*so viel',
                r'höher als', r'vergleich', r'durchschnitt'
            ],
            'explain_item': [
                r'what.*is.*(?P<item>\w+( \w+)*)', r'explain.*(?P<item>\w+( \w+)*)',
                r'mean.*(?P<item>\w+( \w+)*)', r'understand.*(?P<item>\w+( \w+)*)',
                r'was.*ist.*(?P<item>\w+( \w+)*)', r'erklär.*(?P<item>\w+( \w+)*)',
                r'bedeutet.*(?P<item>\w+( \w+)*)', r'versteh.*(?P<item>\w+( \w+)*)'
            ],
            'meter_reading': [
                r'meter.*reading', r'read.*meter', r'submit.*reading',
                r'zählerstand.*mitteil', r'zähler.*abgelesen', r'zählerablesung'
            ],
            'comparison': [
                r'compare', r'previous.*bill', r'last.*year', r'average.*consumption',
                r'vergleich', r'frühere.*rechnung', r'letztes.*jahr', r'durchschnitt.*verbrauch'
            ]
        }
        
    def _load_energy_glossary(self) -> Dict[str, Dict[str, str]]:
        """Load glossary of energy-related terms with explanations"""
        try:
            with open('data/energy_glossary.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback minimal glossary
            return {
                'en': {
                    'basic rate': 'Fixed monthly charge regardless of consumption',
                    'usage rate': 'Price per unit of energy consumed',
                    'meter reading': 'The recorded number on your electricity/gas meter',
                    'levy': 'Mandatory charge imposed by regulatory authorities',
                    'consumption': 'Amount of energy used during the billing period'
                },
                'de': {
                    'grundpreis': 'Fester monatlicher Betrag unabhängig vom Verbrauch',
                    'arbeitspreis': 'Preis pro verbrauchter Energieeinheit',
                    'zählerstand': 'Die abgelesene Zahl auf Ihrem Strom- oder Gaszähler',
                    'umlage': 'Verpflichtende Abgabe, die von Regulierungsbehörden erhoben wird',
                    'verbrauch': 'Energiemenge, die im Abrechnungszeitraum verbraucht wurde'
                }
            }

    def load_knowledge(self):
        try:
            with open('data/knowledge_base.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading knowledge base: {e}")
            return {"utility_invoice_queries": {}}
    
    def get_response(self, query: str, bill_context: Dict[str, Any] = None, language: str = 'en') -> str:
        """Main entry point for generating responses to user queries"""
        # Handle escalation requests
        if self.is_escalation_request(query, language):
            return self.format_escalation_response(language)
        
        # Process and analyze the invoice data
        processed_bill = self.process_invoice_data(bill_context) if bill_context else {}
        
        # Check if query is about a specific bill component
        intent, extracted_info = self.identify_query_intent(query, language)
        
        # If we can answer from knowledge base
        kb_response = self.check_knowledge(query)
        if kb_response:
            # Personalize the knowledge base response with bill data if available
            if bill_context:
                kb_response = self.personalize_response(kb_response, processed_bill, intent, language)
            return self.format_response(kb_response, language)
        
        # Check if query is asking for a term explanation
        glossary_response = self.check_glossary_term(query, language)
        if glossary_response:
            return self.format_response(glossary_response, language)
        
        # Build context-aware prompt with detailed insights
        prompt = self.build_detailed_prompt(query, processed_bill, intent, extracted_info, language)
        
        # Generate response
        response = self.model.generate(prompt, max_tokens=500)
        
        # Post-process to enhance the response
        enhanced_response = self.enhance_response(response, intent, processed_bill, language)
        
        return self.format_response(enhanced_response, language)
    
    def process_invoice_data(self, bill_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process and extract meaningful insights from invoice JSON data"""
        processed_data = {
            "invoice_summary": {},
            "consumption_data": {},
            "payment_info": {},
            "contract_details": {},
            "tax_details": {},
            "cost_breakdown": {},
            "comparative_analysis": {}
        }
        
        try:
            # Extract from bill_context or parse from JSON depending on input format
            if isinstance(bill_context, str):
                try:
                    bill_data = json.loads(bill_context)
                except json.JSONDecodeError:
                    # Fall back to using the string as is if it's not valid JSON
                    return {"raw_text": bill_context}
            else:
                bill_data = bill_context
            
            # Process if we have a "Data" key (from the invoice structure)
            if "Data" in bill_data:
                data = bill_data["Data"]
                
                # Process billing quantities (consumption data)
                if "Abrechnungsmengen" in data:
                    consumption_elements = data["Abrechnungsmengen"].get("AbrechnungsmengenElement", [])
                    if not isinstance(consumption_elements, list):
                        consumption_elements = [consumption_elements]
                    
                    total_consumption = 0
                    consumption_periods = []
                    
                    for element in consumption_elements:
                        period = {
                            "from_date": element.get("dateFrom", ""),
                            "to_date": element.get("dateTo", ""),
                            "consumption": float(element.get("consumption", 0)),
                            "unit": element.get("consumptionUnit", ""),
                            "meter_number": element.get("meterNumber", ""),
                            "start_reading": element.get("startMeterReading", ""),
                            "end_reading": element.get("endMeterReading", "")
                        }
                        consumption_periods.append(period)
                        total_consumption += period["consumption"]
                    
                    processed_data["consumption_data"] = {
                        "total_consumption": total_consumption,
                        "unit": consumption_periods[0]["unit"] if consumption_periods else "",
                        "periods": consumption_periods
                    }
                
                # Process billing items (costs)
                if "Abrechnungspositionen" in data:
                    billing_items = data["Abrechnungspositionen"].get("AbrechnungspositionenElement", [])
                    if not isinstance(billing_items, list):
                        billing_items = [billing_items]
                    
                    basic_costs = []
                    usage_costs = []
                    taxes = []
                    total_net = 0
                    total_tax = 0
                    total_gross = 0
                    
                    for item in billing_items:
                        amount = float(item.get("amount", 0))
                        tax_amount = float(item.get("taxAmount", 0))
                        gross_amount = float(item.get("grossAmount", 0))
                        item_type = item.get("priceType", "")
                        
                        total_net += amount
                        total_tax += tax_amount
                        total_gross += gross_amount
                        
                        item_data = {
                            "name": item.get("name", ""),
                            "net_amount": amount,
                            "tax_amount": tax_amount,
                            "gross_amount": gross_amount,
                            "from_date": item.get("dateFrom", ""),
                            "to_date": item.get("dateTo", ""),
                            "tax_rate": item.get("tax", "")
                        }
                        
                        if item_type == "BASIC_RATE":
                            basic_costs.append(item_data)
                        elif item_type == "USAGE_RATE":
                            usage_costs.append(item_data)
                        
                        # Check for detailed items
                        if "Abrechnungspositionen-Detailliert" in item:
                            details = item["Abrechnungspositionen-Detailliert"].get("Abrechnungspositionen-DetailliertElement", [])
                            if not isinstance(details, list):
                                details = [details]
                            
                            detail_items = []
                            for detail in details:
                                detail_items.append({
                                    "name": detail.get("name", ""),
                                    "type": detail.get("type", ""),
                                    "net_amount": float(detail.get("amount", 0)),
                                    "tax_amount": float(detail.get("taxAmount", 0)),
                                    "gross_amount": float(detail.get("grossAmount", 0))
                                })
                            
                            item_data["details"] = detail_items
                    
                    processed_data["cost_breakdown"] = {
                        "basic_costs": basic_costs,
                        "usage_costs": usage_costs,
                        "total_net": total_net,
                        "total_tax": total_tax,
                        "total_gross": total_gross
                    }
                
                # Process payment plan if available
                if "Abschlagsplan" in data:
                    payment_plan = data["Abschlagsplan"].get("AbschlagsplanElement", {})
                    payments = []
                    
                    if "Abschlagstermine" in data:
                        payment_dates = data["Abschlagstermine"].get("AbschlagstermineElement", [])
                        if not isinstance(payment_dates, list):
                            payment_dates = [payment_dates]
                            
                        for date_item in payment_dates:
                            payments.append({
                                "date": date_item.get("date", ""),
                                "amount": float(date_item.get("amount", 0))
                            })
                    
                    processed_data["payment_info"] = {
                        "installment_amount": float(payment_plan.get("partPaymentAmount", 0)),
                        "payment_period": payment_plan.get("paymentPeriod", ""),
                        "total_installments": payment_plan.get("paymentCount", ""),
                        "payment_schedule": payments
                    }
                
                # Process discounts/bonuses
                if "Bonus-und-Rabatte" in data:
                    bonus = data["Bonus-und-Rabatte"].get("Bonus-und-RabatteElement", {})
                    if bonus:
                        processed_data["invoice_summary"]["discount"] = {
                            "name": bonus.get("name", ""),
                            "amount": float(bonus.get("discountAmount", 0)),
                            "final_discount": float(bonus.get("finalDiscount", 0)),
                            "tax_amount": float(bonus.get("taxAmount", 0))
                        }
                
                # Process process data (invoice metadata)
                if "ProzessDaten" in data:
                    process_data = data["ProzessDaten"].get("ProzessDatenElement", {})
                    
                    # Extract invoice summary
                    processed_data["invoice_summary"].update({
                        "invoice_number": process_data.get("invoiceNumber", ""),
                        "invoice_date": process_data.get("invoiceDate", ""),
                        "period_from": process_data.get("invoicePeriodFrom", ""),
                        "period_to": process_data.get("invoicePeriodTo", ""),
                        "net_amount": float(process_data.get("netInvoiceAmount", 0)),
                        "tax_amount": float(process_data.get("taxAmount", 0)),
                        "gross_amount": float(process_data.get("invoiceAmount", 0)),
                        "payment_due_date": process_data.get("paymentDueDate", ""),
                        "payment_amount": float(process_data.get("paymentAmount", 0))
                    })
                    
                    # Extract contract details
                    if "Vertrag" in process_data:
                        contract = process_data["Vertrag"].get("VertragElement", {})
                        processed_data["contract_details"] = {
                            "contract_number": contract.get("number", ""),
                            "start_date": contract.get("contractStartDate", ""),
                            "minimum_term": contract.get("minimumTerm", ""),
                            "minimum_term_unit": contract.get("minimumTermUnit", ""),
                            "commitment_date": contract.get("contractCommitment", ""),
                            "notice_period": contract.get("periodOfNotice", ""),
                            "notice_period_unit": contract.get("periodOfNoticeUnit", ""),
                            "status": contract.get("status", "")
                        }
                    
                    # Extract customer data
                    if "Geschaeftspartner" in process_data:
                        customer = process_data["Geschaeftspartner"].get("GeschaeftspartnerElement", {})
                        processed_data["customer_info"] = {
                            "name": f"{customer.get('firstName', '')} {customer.get('name', '')}".strip(),
                            "customer_number": customer.get("customerNumber", ""),
                            "address": customer.get("addressText", "").replace("\\n", ", ")
                        }
                
                # Extract cost block information (pie chart data)
                if "Kostenblock" in data:
                    cost_blocks = data["Kostenblock"].get("KostenblockElement", [])
                    if not isinstance(cost_blocks, list):
                        cost_blocks = [cost_blocks]
                    
                    cost_categories = []
                    for block in cost_blocks:
                        category = {
                            "name": block.get("printItemName", ""),
                            "amount": float(block.get("amount", 0)),
                            "percentage": float(block.get("percentageAmount", 0)),
                            "details": []
                        }
                        
                        if "Kostenblock-Detail" in block:
                            details = block["Kostenblock-Detail"].get("Kostenblock-DetailElement", [])
                            if not isinstance(details, list):
                                details = [details]
                            
                            for detail in details:
                                category["details"].append({
                                    "name": detail.get("printItemName", ""),
                                    "amount": float(detail.get("amount", 0)),
                                    "quantity": detail.get("quantity", "")
                                })
                        
                        cost_categories.append(category)
                    
                    processed_data["cost_breakdown"]["categories"] = cost_categories
                
                # Extract consumption comparison data
                if "Verbrauchsvergleich" in data:
                    comparison = data["Verbrauchsvergleich"].get("VerbrauchsvergleichElement", {})
                    if "Verbrauchsvergleich_Daten" in comparison:
                        comparisons = comparison["Verbrauchsvergleich_Daten"].get("Verbrauchsvergleich_DatenElement", [])
                        if not isinstance(comparisons, list):
                            comparisons = [comparisons]
                        
                        household_comparisons = []
                        for comp in comparisons:
                            household_comparisons.append({
                                "type": comp.get("label", ""),
                                "low": comp.get("categoryA", ""),
                                "medium_low": comp.get("categoryB", ""),
                                "medium_high": comp.get("categoryC", ""),
                                "high": comp.get("categoryD", "")
                            })
                        
                        processed_data["comparative_analysis"]["household_comparisons"] = household_comparisons
                
                # Calculate average daily consumption
                if processed_data["consumption_data"] and processed_data["invoice_summary"]:
                    try:
                        consumption = processed_data["consumption_data"]["total_consumption"]
                        from_date = processed_data["invoice_summary"]["period_from"]
                        to_date = processed_data["invoice_summary"]["period_to"]
                        
                        # Parse dates (expecting DD.MM.YYYY format)
                        start_date = datetime.datetime.strptime(from_date, "%d.%m.%Y")
                        end_date = datetime.datetime.strptime(to_date, "%d.%m.%Y")
                        days = (end_date - start_date).days + 1
                        
                        if days > 0:
                            daily_avg = consumption / days
                            processed_data["consumption_data"]["daily_average"] = round(daily_avg, 2)
                    except (ValueError, KeyError, TypeError):
                        # Skip this calculation if any required data is missing or in wrong format
                        pass
            
            return processed_data
        except Exception as e:
            print(f"Error processing invoice data: {e}")
            return {"error": str(e), "raw_data": bill_context}
    
    def identify_query_intent(self, query: str, language: str) -> Tuple[str, Dict[str, Any]]:
        """Identify the user's intent from the query"""
        query = query.lower()
        extracted_info = {}
        
        # Check each intent pattern
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, query)
                if match:
                    # If this is an explain_item intent, extract the item
                    if intent == 'explain_item' and 'item' in match.groupdict():
                        extracted_info['item'] = match.group('item')
                    return intent, extracted_info
        
        # Default to general query if no specific intent is found
        return 'general', extracted_info
    
    def check_glossary_term(self, query: str, language: str) -> str:
        """Check if the query is asking for explanation of a term in our glossary"""
        query_lower = query.lower()
        
        # Extract potential terms from "what is X" type questions
        term_patterns = [
            r'what\s+is\s+(?:a|an)?\s*(?P<term>[\w\s-]+)(\?|$|\.)',
            r'explain\s+(?:a|an)?\s*(?P<term>[\w\s-]+)(\?|$|\.)',
            r'define\s+(?:a|an)?\s*(?P<term>[\w\s-]+)(\?|$|\.)',
            r'was\s+ist\s+(?:ein|eine)?\s*(?P<term>[\w\s-]+)(\?|$|\.)',
            r'erkläre?\s+(?:ein|eine)?\s*(?P<term>[\w\s-]+)(\?|$|\.)'
        ]
        
        extracted_terms = []
        for pattern in term_patterns:
            matches = re.finditer(pattern, query_lower)
            for match in matches:
                if 'term' in match.groupdict():
                    term = match.group('term').strip().lower()
                    if len(term) > 2:  # Ignore very short terms
                        extracted_terms.append(term)
        
        # Check each extracted term against our glossary
        glossary = self.energy_terms_glossary.get(language, {})
        for term in extracted_terms:
            if term in glossary:
                return f"{term.capitalize()}: {glossary[term]}"
            
            # Try partial matches
            for glossary_term, explanation in glossary.items():
                if term in glossary_term or glossary_term in term:
                    return f"{glossary_term.capitalize()}: {explanation}"
        
        return ""
    
    def is_escalation_request(self, query: str, language: str) -> bool:
        """Determine if user wants to be redirected to human support"""
        escalation_triggers = {
            'en': ['escalate', 'contact support', 'talk to human', 'speak with agent', 
                   'connect me', 'need human', 'real person', 'customer service'],
            'de': ['eskalieren', 'support kontaktieren', 'mit mensch sprechen',
                   'kundenservice', 'kundendienst', 'berater', 'echter mensch', 'verbinden']
        }
        query_lower = query.lower()
        return any(trigger in query_lower for trigger in escalation_triggers.get(language, []))
    
    def format_escalation_response(self, language: str) -> str:
        """Format a response for escalation requests"""
        responses = {
            'en': "I've escalated your request to our support team. They'll contact you within 24 hours. 🔔",
            'de': "Ich habe Ihre Anfrage an unser Support-Team weitergeleitet. Sie werden sich innerhalb von 24 Stunden bei Ihnen melden. 🔔"
        }
        return responses.get(language, responses['en'])
    
    @lru_cache(maxsize=100)
    def check_knowledge(self, query: str) -> str:
        """Check if the query can be answered from knowledge base"""
        # Convert query to lowercase for better matching
        query_lower = query.lower()
        
        # Store matches with their match quality score
        matches = []
        
        for category in self.knowledge['utility_invoice_queries'].values():
            for item in category:
                input_text = item['input'].lower()
                
                # Exact match
                if input_text == query_lower:
                    return item['response']
                
                # Contained match (query contains knowledge base entry)
                if input_text in query_lower:
                    match_quality = len(input_text) / len(query_lower)
                    matches.append((match_quality, item['response']))
                
                # Knowledge base entry contains query
                elif query_lower in input_text:
                    match_quality = len(query_lower) / len(input_text)
                    matches.append((match_quality, item['response']))
        
        # Return best match if quality is above threshold
        if matches:
            best_match = max(matches, key=lambda x: x[0])
            if best_match[0] > 0.5:  # Threshold for match quality
                return best_match[1]
        
        return ""
    
    def personalize_response(self, response: str, bill_data: Dict[str, Any], intent: str, language: str) -> str:
        """Personalize a knowledge base response with specific bill data"""
        # Skip if no bill data
        if not bill_data or len(bill_data) == 0:
            return response
        
        # Replace placeholders with actual values based on intent
        if intent == 'total_amount' and 'invoice_summary' in bill_data:
            summary = bill_data['invoice_summary']
            if 'gross_amount' in summary:
                amount_str = f"{summary['gross_amount']:.2f}" if language == 'en' else f"{summary['gross_amount']:.2f}".replace('.', ',')
                response = response.replace('[TOTAL_AMOUNT]', amount_str)
        
        elif intent == 'consumption' and 'consumption_data' in bill_data:
            consumption = bill_data['consumption_data']
            if 'total_consumption' in consumption:
                consumption_str = str(consumption['total_consumption'])
                unit = consumption.get('unit', 'kWh')
                response = response.replace('[CONSUMPTION_AMOUNT]', f"{consumption_str} {unit}")
        
        elif intent == 'payment_plan' and 'payment_info' in bill_data:
            payment = bill_data['payment_info']
            if 'installment_amount' in payment:
                amount_str = f"{payment['installment_amount']:.2f}" if language == 'en' else f"{payment['installment_amount']:.2f}".replace('.', ',')
                response = response.replace('[PAYMENT_AMOUNT]', amount_str)
        
        return response
    
    def build_detailed_prompt(self, query: str, bill_data: Dict[str, Any], intent: str, 
                             extracted_info: Dict[str, Any], language: str) -> str:
        """Build a detailed prompt with processed bill data tailored to user intent"""
        lang_instr = self.language_instructions.get(language, self.language_instructions['en'])
        
        # Start with base prompt
        prompt = f"""You are KlarBill, a utility billing expert with deep knowledge of energy regulations and billing practices.
{lang_instr}

User query: {query}
"""
        
        # Add specific context based on intent
        if bill_data:
            if intent == 'total_amount' and 'invoice_summary' in bill_data:
                summary = bill_data['invoice_summary']
                prompt += f"""
BILLING INFORMATION:
- Invoice Number: {summary.get('invoice_number', 'N/A')}
- Invoice Date: {summary.get('invoice_date', 'N/A')}
- Billing Period: {summary.get('period_from', 'N/A')} to {summary.get('period_to', 'N/A')}
- Net Amount: {summary.get('net_amount', 0):.2f}
- Tax Amount: {summary.get('tax_amount', 0):.2f}
- Total Amount: {summary.get('gross_amount', 0):.2f}
- Payment Due Date: {summary.get('payment_due_date', 'N/A')}

The user wants to know about the total bill amount. Explain the total amount clearly, breaking down the main components.
"""
            
            elif intent == 'consumption' and 'consumption_data' in bill_data:
                consumption = bill_data['consumption_data']
                periods = consumption.get('periods', [])
                periods_text = ""
                
                for i, period in enumerate(periods):
                    periods_text += f"""
Period {i+1}: {period.get('from_date', 'N/A')} to {period.get('to_date', 'N/A')}
- Consumption: {period.get('consumption', 0)} {period.get('unit', 'kWh')}
- Meter Readings: {period.get('start_reading', 'N/A')} to {period.get('end_reading', 'N/A')}
"""
                
                prompt += f"""
CONSUMPTION INFORMATION:
- Total Consumption: {consumption.get('total_consumption', 0)} {consumption.get('unit', 'kWh')}
- Daily Average: {consumption.get('daily_average', 'N/A')} {consumption.get('unit', 'kWh')}/day
{periods_text}

The user wants to know about energy consumption. Explain the consumption details clearly.
"""
            
            elif intent == 'payment_plan' and 'payment_info' in bill_data:
                payment = bill_data['payment_info']
                payments = payment.get('payment_schedule', [])
                payments_text = ""
                
                for i, payment_item in enumerate(payments[:5]):  # Show first 5 payments
                    payments_text += f"- {payment_item.get('date', 'N/A')}: {payment_item.get('amount', 0):.2f}\n"
                
                if len(payments) > 5:
                    payments_text += f"- (and {len(payments) - 5} more payments)\n"
                
                prompt += f"""
PAYMENT PLAN INFORMATION:
- Installment Amount: {payment.get('installment_amount', 0):.2f}
- Payment Period: {payment.get('payment_period', 'N/A')}
- Number of Installments: {payment.get('total_installments', 'N/A')}
- Upcoming Payments:
{payments_text}

The user wants to know about the payment plan. Explain how the payment plan works.
"""
            
            elif intent == 'taxes_levies' and 'cost_breakdown' in bill_data:
                breakdown = bill_data['cost_breakdown']
                categories = breakdown.get('categories', [])
                taxes_text = ""
                       
		for category in categories:
                    if 'Steuern' in category.get('name', '') or 'Tax' in category.get('name', '') or 'Abgaben' in category.get('name', ''):
                        taxes_text += f"- {category.get('name', 'N/A')}: {category.get('amount', 0):.2f} ({category.get('percentage', 0):.1f}%)\n"
                        
                        for detail in category.get('details', []):
                            taxes_text += f"  • {detail.get('name', 'N/A')}: {detail.get('amount', 0):.2f}\n"
                
                prompt += f"""
TAX AND LEVIES INFORMATION:
- Total Tax Amount: {breakdown.get('total_tax', 0):.2f}
- Tax Breakdown:
{taxes_text}

The user wants to know about taxes and levies. Explain the different components and how they contribute to the total bill.
"""
            
            elif intent == 'contract' and 'contract_details' in bill_data:
                contract = bill_data['contract_details']
                
                prompt += f"""
CONTRACT INFORMATION:
- Contract Number: {contract.get('contract_number', 'N/A')}
- Start Date: {contract.get('start_date', 'N/A')}
- Minimum Term: {contract.get('minimum_term', 'N/A')} {contract.get('minimum_term_unit', '')}
- Notice Period: {contract.get('notice_period', 'N/A')} {contract.get('notice_period_unit', '')}
- Contract Status: {contract.get('status', 'N/A')}

The user wants to know about contract details. Explain the key contract terms and what they mean.
"""
            
            elif intent == 'high_bill' and 'cost_breakdown' in bill_data and 'consumption_data' in bill_data:
                breakdown = bill_data['cost_breakdown']
                consumption = bill_data['consumption_data']
                cost_categories = breakdown.get('categories', [])
                categories_text = ""
                
                # Show top 3 cost categories by amount
                sorted_categories = sorted(cost_categories, key=lambda x: x.get('amount', 0), reverse=True)
                for i, category in enumerate(sorted_categories[:3]):
                    categories_text += f"- {category.get('name', 'N/A')}: {category.get('amount', 0):.2f} ({category.get('percentage', 0):.1f}%)\n"
                
                prompt += f"""
BILL ANALYSIS:
- Total Amount: {breakdown.get('total_gross', 0):.2f}
- Total Consumption: {consumption.get('total_consumption', 0)} {consumption.get('unit', 'kWh')}
- Daily Average Usage: {consumption.get('daily_average', 'N/A')} {consumption.get('unit', 'kWh')}/day
- Top Cost Components:
{categories_text}

The user is concerned about a high bill. Analyze possible reasons for the high costs and provide context on whether the bill is indeed higher than expected.
"""
            
            elif intent == 'explain_item' and extracted_info.get('item'):
                item = extracted_info.get('item', '')
                # First check if the item is a specific cost component
                item_found = False
                item_details = ""
                
                if 'cost_breakdown' in bill_data:
                    breakdown = bill_data['cost_breakdown']
                    categories = breakdown.get('categories', [])
                    
                    for category in categories:
                        if item.lower() in category.get('name', '').lower():
                            item_found = True
                            item_details += f"- {category.get('name', 'N/A')}: {category.get('amount', 0):.2f} ({category.get('percentage', 0):.1f}%)\n"
                            
                            for detail in category.get('details', []):
                                item_details += f"  • {detail.get('name', 'N/A')}: {detail.get('amount', 0):.2f}\n"
                
                if item_found:
                    prompt += f"""
ITEM EXPLANATION:
{item_details}

The user wants to know about '{item}'. Explain what this item is, how it's calculated, and why it appears on the bill.
"""
                else:
                    # Check if it's in our glossary
                    glossary = self.energy_terms_glossary.get(language, {})
                    for term, explanation in glossary.items():
                        if item.lower() in term.lower() or term.lower() in item.lower():
                            prompt += f"""
TERM EXPLANATION:
- Term: {term}
- Definition: {explanation}

The user wants to know about '{item}'. Provide a detailed explanation of this term in the context of utility bills.
"""
                            break
                    else:
                        # General explanation prompt
                        prompt += f"""
The user wants to know about '{item}'. Provide a clear explanation of this term or component in the context of utility bills.
"""
            
            elif intent == 'meter_reading':
                if 'consumption_data' in bill_data:
                    consumption = bill_data['consumption_data']
                    periods = consumption.get('periods', [])
                    readings_text = ""
                    
                    for i, period in enumerate(periods):
                        readings_text += f"""
Period {i+1}: {period.get('from_date', 'N/A')} to {period.get('to_date', 'N/A')}
- Start Reading: {period.get('start_reading', 'N/A')}
- End Reading: {period.get('end_reading', 'N/A')}
- Consumption: {period.get('consumption', 0)} {period.get('unit', 'kWh')}
- Meter Number: {period.get('meter_number', 'N/A')}
"""
                    
                    prompt += f"""
METER READING INFORMATION:
{readings_text}

The user wants to know about meter readings. Explain how meter readings work, how they're used for billing, and any other relevant details.
"""
                else:
                    prompt += """
The user wants to know about meter readings. Explain how meter readings work, how they're used for billing, and any other relevant details.
"""
            
            elif intent == 'comparison' and 'comparative_analysis' in bill_data:
                comparisons = bill_data.get('comparative_analysis', {}).get('household_comparisons', [])
                comparison_text = ""
                
                for comparison in comparisons:
                    comparison_text += f"""
- {comparison.get('type', 'N/A')}:
  • Low usage: {comparison.get('low', 'N/A')}
  • Medium-low usage: {comparison.get('medium_low', 'N/A')}
  • Medium-high usage: {comparison.get('medium_high', 'N/A')}
  • High usage: {comparison.get('high', 'N/A')}
"""
                
                prompt += f"""
CONSUMPTION COMPARISON:
{comparison_text}

The user wants to compare their consumption. Analyze their usage relative to similar households and explain the comparison data.
"""
        
        # Add general context for any query type if bill data is available
        if bill_data and 'invoice_summary' in bill_data and 'consumption_data' in bill_data:
            summary = bill_data['invoice_summary']
            consumption = bill_data['consumption_data']
            
            prompt += f"""
GENERAL CONTEXT:
- Invoice Number: {summary.get('invoice_number', 'N/A')}
- Billing Period: {summary.get('period_from', 'N/A')} to {summary.get('period_to', 'N/A')}
- Total Amount: {summary.get('gross_amount', 0):.2f}
- Total Consumption: {consumption.get('total_consumption', 0)} {consumption.get('unit', 'kWh')}
"""
        
        # Add calculations to explain rates if usage costs are available
        if bill_data and 'cost_breakdown' in bill_data and 'usage_costs' in bill_data['cost_breakdown'] and 'consumption_data' in bill_data:
            usage_costs = bill_data['cost_breakdown']['usage_costs']
            total_consumption = bill_data['consumption_data'].get('total_consumption', 0)
            
            if usage_costs and total_consumption > 0:
                total_usage_cost = sum(item.get('net_amount', 0) for item in usage_costs)
                avg_rate = total_usage_cost / total_consumption if total_consumption > 0 else 0
                
                prompt += f"""
RATE CALCULATION:
- Total Energy Cost: {total_usage_cost:.2f}
- Total Consumption: {total_consumption} {bill_data['consumption_data'].get('unit', 'kWh')}
- Average Rate: {avg_rate:.4f} per {bill_data['consumption_data'].get('unit', 'kWh')}
"""
        
        # Final instruction
        prompt += f"""
Based on the information provided, respond to the user's query in {language} with a clear, concise explanation.
Be helpful and focus on explaining complex billing concepts in simple terms.
Include specific numbers relevant to their question.
"""
        
        return prompt
    
    def enhance_response(self, response: str, intent: str, bill_data: Dict[str, Any], language: str) -> str:
        """Post-process and enhance the LLM response based on intent and bill data"""
        enhanced_response = response
        
        # Don't enhance if response is already comprehensive
        if len(response) > 500:
            return enhanced_response
        
        # Add appropriate emojis based on intent
        intent_emojis = {
            'total_amount': '💰',
            'consumption': '⚡',
            'payment_plan': '📅',
            'taxes_levies': '📋',
            'contract': '📄',
            'high_bill': '📈',
            'explain_item': '❓',
            'meter_reading': '🔢',
            'comparison': '📊',
            'general': '📝'
        }
        
        emoji = intent_emojis.get(intent, '')
        if emoji and not emoji in enhanced_response:
            enhanced_response = f"{emoji} {enhanced_response}"
        
        # Add follow-up suggestions based on intent and available data
        if bill_data:
            suggestions = {
                'en': {
                    'total_amount': "\n\nYou can also ask about the breakdown of costs or your consumption details.",
                    'consumption': "\n\nYou can also ask about your average daily usage or how it compares to similar households.",
                    'payment_plan': "\n\nYou can also ask about payment due dates or how to adjust your payment plan.",
                    'high_bill': "\n\nYou can also ask for tips to reduce your energy consumption or about your usage patterns.",
                },
                'de': {
                    'total_amount': "\n\nSie können auch nach der Aufschlüsselung der Kosten oder Ihren Verbrauchsdetails fragen.",
                    'consumption': "\n\nSie können auch nach Ihrem durchschnittlichen Tagesverbrauch oder dem Vergleich mit ähnlichen Haushalten fragen.",
                    'payment_plan': "\n\nSie können auch nach Zahlungsfälligkeiten fragen oder wie Sie Ihren Zahlungsplan anpassen können.",
                    'high_bill': "\n\nSie können auch nach Tipps zur Reduzierung Ihres Energieverbrauchs oder nach Ihren Nutzungsmustern fragen.",
                }
            }
            
            if intent in suggestions.get(language, {}) and len(enhanced_response) < 800:
                enhanced_response += suggestions[language][intent]
        
        # Add calculation explanations when talking about costs
        if intent in ['total_amount', 'high_bill'] and 'cost_breakdown' in bill_data and 'consumption_data' in bill_data:
            if language == 'en':
                if not "calculated" in enhanced_response.lower() and len(enhanced_response) < 800:
                    unit = bill_data['consumption_data'].get('unit', 'kWh')
                    enhanced_response += f"\n\nYour bill is calculated based on your consumption of {bill_data['consumption_data'].get('total_consumption', 0)} {unit} plus fixed charges and taxes."
            else:
                if not "berechnet" in enhanced_response.lower() and len(enhanced_response) < 800:
                    unit = bill_data['consumption_data'].get('unit', 'kWh')
                    enhanced_response += f"\n\nIhre Rechnung wird auf Basis Ihres Verbrauchs von {bill_data['consumption_data'].get('total_consumption', 0)} {unit} plus Grundgebühren und Steuern berechnet."
        
        return enhanced_response
    
    def format_response(self, response: str, language: str) -> str:
        """Format the final response with appropriate styling"""
        # Add disclaimer for complex topics
        if len(response) > 300 and ('regulation' in response.lower() or 'law' in response.lower() or 'gesetz' in response.lower()):
            if language == 'en':
                response += "\n\n*Note: For legal or regulatory questions, please consult the appropriate authorities for the most accurate information.*"
            else:
                response += "\n\n*Hinweis: Für rechtliche oder regulatorische Fragen wenden Sie sich bitte an die zuständigen Behörden für die genauesten Informationen.*"
        
        return response.strip()

    def analyze_consumption_patterns(self, bill_data: Dict[str, Any], language: str = 'en') -> str:
        """Analyze consumption patterns and provide insights"""
        if not bill_data or 'consumption_data' not in bill_data:
            return ""
        
        consumption = bill_data['consumption_data']
        total = consumption.get('total_consumption', 0)
        daily_avg = consumption.get('daily_average', 0)
        unit = consumption.get('unit', 'kWh')
        periods = consumption.get('periods', [])
        
        # Skip if insufficient data
        if not total or not daily_avg or not periods:
            return ""
        
        # Calculate variance between periods if multiple periods exist
        pattern_insights = []
        if len(periods) > 1:
            # Extract consumption values for each period
            period_values = [p.get('consumption', 0) for p in periods]
            if all(period_values):
                # Calculate coefficient of variation
                std_dev = np.std(period_values)
                mean = np.mean(period_values)
                cv = (std_dev / mean) if mean > 0 else 0
                
                # Interpret variability
                if cv > 0.25:
                    if language == 'en':
                        pattern_insights.append("Your consumption shows significant variability between billing periods.")
                    else:
                        pattern_insights.append("Ihr Verbrauch zeigt erhebliche Schwankungen zwischen den Abrechnungszeiträumen.")
                else:
                    if language == 'en':
                        pattern_insights.append("Your consumption is relatively consistent across billing periods.")
                    else:
                        pattern_insights.append("Ihr Verbrauch ist über die Abrechnungszeiträume relativ konstant.")
        
        # Compare with typical household usage for that energy type
        # These are rough estimates and would ideally be replaced with actual data
        typical_usage = {
            'electricity': {'daily': 10, 'unit': 'kWh'},  # Example values
            'gas': {'daily': 40, 'unit': 'kWh'},  # Example values
            'water': {'daily': 150, 'unit': 'L'}  # Example values
        }
        
        # Try to determine energy type from unit
        energy_type = None
        if unit.lower() in ['kwh', 'kwh']:
            # Try to determine if electricity or gas from context
            if 'cost_breakdown' in bill_data:
                categories = bill_data['cost_breakdown'].get('categories', [])
                for category in categories:
                    name = category.get('name', '').lower()
                    if 'strom' in name or 'electricity' in name:
                        energy_type = 'electricity'
                        break
                    elif 'gas' in name:
                        energy_type = 'gas'
                        break
        elif unit.lower() in ['l', 'liter', 'm3']:
            energy_type = 'water'
        
        if energy_type and energy_type in typical_usage:
            typical = typical_usage[energy_type]
            if typical['unit'] == unit:
                ratio = daily_avg / typical['daily']
                
                if language == 'en':
                    if ratio > 1.3:
                        pattern_insights.append(f"Your daily usage ({daily_avg:.1f} {unit}/day) is higher than average for a typical household.")
                    elif ratio < 0.7:
                        pattern_insights.append(f"Your daily usage ({daily_avg:.1f} {unit}/day) is lower than average for a typical household.")
                    else:
                        pattern_insights.append(f"Your daily usage ({daily_avg:.1f} {unit}/day) is around the average for a typical household.")
                else:
                    if ratio > 1.3:
                        pattern_insights.append(f"Ihr täglicher Verbrauch ({daily_avg:.1f} {unit}/Tag) ist höher als der Durchschnitt für einen typischen Haushalt.")
                    elif ratio < 0.7:
                        pattern_insights.append(f"Ihr täglicher Verbrauch ({daily_avg:.1f} {unit}/Tag) ist niedriger als der Durchschnitt für einen typischen Haushalt.")
                    else:
                        pattern_insights.append(f"Ihr täglicher Verbrauch ({daily_avg:.1f} {unit}/Tag) entspricht etwa dem Durchschnitt für einen typischen Haushalt.")
        
        # Return insights if we have any
        if pattern_insights:
            if language == 'en':
                return f"CONSUMPTION ANALYSIS:\n{' '.join(pattern_insights)}"
            else:
                return f"VERBRAUCHSANALYSE:\n{' '.join(pattern_insights)}"
        
        return ""
    
    def get_energy_saving_tips(self, bill_data: Dict[str, Any], language: str = 'en') -> List[str]:
        """Provide personalized energy saving tips based on bill analysis"""
        tips = []
        
        # Determine energy type if possible
        energy_type = 'general'
        if bill_data and 'consumption_data' in bill_data:
            unit = bill_data['consumption_data'].get('unit', '').lower()
            
            if unit in ['kwh', 'kwh']:
                # Look at cost categories to determine if electric or gas
                if 'cost_breakdown' in bill_data:
                    categories = bill_data['cost_breakdown'].get('categories', [])
                    for category in categories:
                        name = category.get('name', '').lower()
                        if 'strom' in name or 'electricity' in name:
                            energy_type = 'electricity'
                            break
                        elif 'gas' in name:
                            energy_type = 'gas'
                            break
            elif unit in ['l', 'liter', 'm3']:
                energy_type = 'water'
        
        # Select appropriate tips
        if language == 'en':
            if energy_type == 'electricity':
                tips = [
                    "Switch to LED light bulbs which use up to 80% less electricity than traditional bulbs.",
                    "Unplug electronics when not in use or use power strips to eliminate phantom energy use.",
                    "Run full loads of laundry and use cold water when possible.",
                    "Use a programmable thermostat to reduce heating/cooling when you're away.",
                    "Consider energy-efficient appliances when replacing old ones."
                ]
            elif energy_type == 'gas':
                tips = [
                    "Lower your thermostat by 1-2 degrees for significant savings.",
                    "Seal drafts around windows and doors to prevent heat loss.",
                    "Insulate your hot water pipes to reduce heat loss.",
                    "Service your heating system annually for maximum efficiency.",
                    "Use curtains to keep heat in during winter and out during summer."
                ]
            elif energy_type == 'water':
                tips = [
                    "Fix leaky faucets and running toilets promptly.",
                    "Install low-flow showerheads and faucet aerators.",
                    "Take shorter showers instead of baths.",
                    "Only run full loads in dishwashers and washing machines.",
                    "Water your garden during cooler parts of the day to reduce evaporation."
                ]
            else:
                tips = [
                    "Turn off lights and appliances when not in use.",
                    "Seal drafts around windows and doors.",
                    "Use energy-efficient appliances and light bulbs.",
                    "Adjust your thermostat by a few degrees.",
                    "Reduce standby power usage by unplugging devices."
                ]
        else:  # German tips
            if energy_type == 'electricity':
                tips = [
                    "Wechseln Sie zu LED-Lampen, die bis zu 80% weniger Strom verbrauchen als herkömmliche Glühbirnen.",
                    "Ziehen Sie Elektronikgeräte aus der Steckdose oder verwenden Sie Steckerleisten, um den Standby-Verbrauch zu eliminieren.",
                    "Waschen Sie mit voller Beladung und wenn möglich mit kaltem Wasser.",
                    "Verwenden Sie einen programmierbaren Thermostat, um die Heizung/Kühlung zu reduzieren, wenn Sie nicht zu Hause sind.",
                    "Ziehen Sie energieeffiziente Geräte in Betracht, wenn Sie alte ersetzen."
                ]
            elif energy_type == 'gas':
                tips = [
                    "Senken Sie Ihren Thermostat um 1-2 Grad für erhebliche Einsparungen.",
                    "Dichten Sie Zugluft an Fenstern und Türen ab, um Wärmeverlust zu vermeiden.",
                    "Isolieren Sie Ihre Warmwasserrohre, um Wärmeverlust zu reduzieren.",
                    "Warten Sie Ihr Heizsystem jährlich für maximale Effizienz.",
                    "Nutzen Sie Vorhänge, um Wärme im Winter drinnen und im Sommer draußen zu halten."
                ]
            elif energy_type == 'water':
                tips = [
                    "Reparieren Sie tropfende Wasserhähne und laufende Toiletten umgehend.",
                    "Installieren Sie wassersparende Duschköpfe und Durchflussbegrenzer.",
                    "Nehmen Sie kürzere Duschen statt Vollbäder.",
                    "Lassen Sie Geschirrspüler und Waschmaschinen nur voll laufen.",
                    "Bewässern Sie Ihren Garten während kühlerer Tageszeiten, um Verdunstung zu reduzieren."
                ]
            else:
                tips = [
                    "Schalten Sie Lichter und Geräte aus, wenn sie nicht benutzt werden.",
                    "Dichten Sie Zugluft an Fenstern und Türen ab.",
                    "Verwenden Sie energieeffiziente Geräte und Leuchtmittel.",
                    "Passen Sie Ihren Thermostat um einige Grad an.",
                    "Reduzieren Sie den Standby-Stromverbrauch durch Ausstecken von Geräten."
                ]
        
        # Personalize the first tip if we have consumption data
        if bill_data and 'consumption_data' in bill_data and 'cost_breakdown' in bill_data:
            consumption = bill_data['consumption_data'].get('total_consumption', 0)
            if consumption > 0:
                # Rough estimate of potential savings
                potential_savings = consumption * 0.1  # Assume 10% potential savings
                
                if language == 'en':
                    tips[0] = f"Based on your consumption of {consumption} {bill_data['consumption_data'].get('unit', 'kWh')}, implementing these tips could save you approximately {potential_savings:.1f} {bill_data['consumption_data'].get('unit', 'kWh')} per billing period."
                else:
                    tips[0] = f"Basierend auf Ihrem Verbrauch von {consumption} {bill_data['consumption_data'].get('unit', 'kWh')}, könnten Sie durch diese Tipps etwa {potential_savings:.1f} {bill_data['consumption_data'].get('unit', 'kWh')} pro Abrechnungszeitraum einsparen."
        
        return tips
    
    def explain_regulations(self, country: str = 'de', language: str = 'en') -> str:
        """Provide explanations about energy regulations for specific countries"""
        regulations = {
            'de': {
                'en': """
GERMAN ENERGY REGULATIONS:

The German energy market is regulated by several key laws:

1. Energy Industry Act (EnWG): Provides the legal framework for electricity and gas supply, ensuring competition and reliable service.

2. Renewable Energy Sources Act (EEG): Promotes renewable energy by establishing feed-in tariffs and priority grid access for renewables.

3. Energy Tax Act (EnergieStG): Governs taxation of energy products including electricity and natural gas.

Key components on your bill:
- EEG-Umlage: Levy to finance renewable energy expansion
- Stromsteuer/Energiesteuer: Federal tax on electricity/energy
- Konzessionsabgabe: Fee paid to local authorities for using public infrastructure
- Netzentgelte: Grid usage fees that cover transmission and distribution costs

These regulations ensure fair pricing, promote clean energy, and maintain grid reliability.
""",
                'de': """
DEUTSCHE ENERGIEVORSCHRIFTEN:

Der deutsche Energiemarkt wird durch mehrere wichtige Gesetze reguliert:

1. Energiewirtschaftsgesetz (EnWG): Bietet den rechtlichen Rahmen für die Strom- und Gasversorgung, sichert Wettbewerb und zuverlässigen Service.

2. Erneuerbare-Energien-Gesetz (EEG): Fördert erneuerbare Energien durch Einspeisevergütungen und vorrangigen Netzzugang.

3. Energiesteuergesetz (EnergieStG): Regelt die Besteuerung von Energieerzeugnissen einschließlich Strom und Erdgas.

Wichtige Bestandteile Ihrer Rechnung:
- EEG-Umlage: Abgabe zur Finanzierung des Ausbaus erneuerbarer Energien
- Stromsteuer/Energiesteuer: Bundessteuer auf Elektrizität/Energie
- Konzessionsabgabe: Gebühr an lokale Behörden für die Nutzung öffentlicher Infrastruktur
- Netzentgelte: Netznutzungsgebühren, die Übertragungs- und Verteilungskosten decken

Diese Vorschriften gewährleisten faire Preisgestaltung, fördern saubere Energie und erhalten die Netzzuverlässigkeit.
"""
            },

        }
        
        if country in regulations and language in regulations[country]:
            return regulations[country][language]
        
        # Fallback to English German regulations if country/language not found
        return regulations['de']['en']
    
    def describe_market_trends(self, language: str = 'en') -> str:
        """Provide information about current energy market trends"""
        # This would normally be updated periodically with current data
        # Here we're providing static, example content
        trends = {
            'en': """
ENERGY MARKET TRENDS:

Recent developments in the energy market:

1. Renewable Energy Growth: Continued expansion of solar and wind capacity is gradually reducing costs over the long term.

2. Natural Gas Price Volatility: Gas prices have shown significant fluctuations due to supply chain disruptions and geopolitical tensions.

3. Grid Infrastructure Investments: Utilities are investing heavily in modernizing grid infrastructure, which may be reflected in network charges.

4. Regulatory Changes: Enhanced climate policies are introducing new levies and adjusting existing ones to support decarbonization goals.

5. Digitalization: Smart meters and digital innovations are enabling more transparent billing and consumption monitoring.

These trends are affecting bills through changing generation costs, network charges, and regulatory components.
""",
            'de': """
ENERGIEMARKT-TRENDS:

Aktuelle Entwicklungen auf dem Energiemarkt:

1. Wachstum erneuerbarer Energien: Der kontinuierliche Ausbau von Solar- und Windkapazitäten senkt langfristig die Kosten.

2. Erdgaspreisvolatilität: Die Gaspreise haben aufgrund von Lieferkettenunterbrechungen und geopolitischen Spannungen erhebliche Schwankungen gezeigt.

3. Investitionen in die Netzinfrastruktur: Versorgungsunternehmen investieren stark in die Modernisierung der Netzinfrastruktur, was sich in den Netzentgelten widerspiegeln kann.

4. Regulatorische Änderungen: Verbesserte Klimaschutzmaßnahmen führen zu neuen Abgaben und passen bestehende an, um Dekarbonisierungsziele zu unterstützen.

5. Digitalisierung: Intelligente Zähler und digitale Innovationen ermöglichen eine transparentere Abrechnung und Verbrauch
