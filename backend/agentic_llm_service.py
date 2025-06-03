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
from data.firebase_service import get_db_reference

FIREBASE_INVOICES_URL = "https://klarbill-3de73-default-rtdb.europe-west1.firebasedatabase.app/invoices.json"

class QueryType(Enum):
    GREETING = "greeting"
    SIMPLE_FACT = "simple_fact"
    CALCULATION = "calculation" 
    COMPARISON = "comparison"
    EXPLANATION = "explanation"
    REGULATORY = "regulatory"
    TROUBLESHOOTING = "troubleshooting"
    NAVIGATION = "navigation"
    IDENTIFIER_VALIDATION = "identifier_validation"

@dataclass
class ResponseFormat:
    concise: bool = True
    detailed_calculation: bool = False
    include_regulatory_context: bool = False
    personalized: bool = True
    conciseness_level: str = "moderate"

class GermanEnergyRegulations:
    """Knowledge base for German energy regulations and billing components"""
    
    ENERGY_COMPONENTS = {
        "netznutzung": {
            "name_de": "Netznutzung",
            "name_en": "Grid Usage",
            "explanation_de": "Kosten für die Nutzung des Stromnetzes zur Übertragung und Verteilung",
            "explanation_en": "Costs for using the electricity grid for transmission and distribution",
            "regulated_by": "Bundesnetzagentur",
            "typical_amount": "Grid fees vary by region, typically 6-8 ct/kWh"
        },
        "messstellenbetrieb": {
            "name_de": "Messstellenbetrieb", 
            "name_en": "Metering Operation",
            "explanation_de": "Kosten für den Betrieb und die Wartung der Messeinrichtungen",
            "explanation_en": "Costs for operation and maintenance of measuring equipment",
            "regulated_by": "MessstellenbetriebsG",
            "typical_amount": "€20-100 per year depending on meter type"
        },
        "stromsteuer": {
            "name_de": "Stromsteuer",
            "name_en": "Electricity Tax", 
            "explanation_de": "Bundessteuer auf Stromverbrauch, derzeit 2,05 ct/kWh",
            "explanation_en": "Federal tax on electricity consumption, currently 2.05 ct/kWh",
            "current_rate": "0.0205",
            "regulated_by": "Federal Government"
        },
        "kwkg_umlage": {
            "name_de": "KWKG-Umlage",
            "name_en": "CHP Levy (Combined Heat and Power)",
            "explanation_de": "Förderung von Kraft-Wärme-Kopplung zur Energieeffizienz. 2025: 0,277 ct/kWh",
            "explanation_en": "Support for combined heat and power for energy efficiency. 2025: 0.277 ct/kWh",
            "current_rate_2025": "0.277",
            "regulated_by": "Federal Government"
        },
        "offshore_umlage": {
            "name_de": "Offshore-Netzumlage", 
            "name_en": "Offshore Grid Levy",
            "explanation_de": "Finanzierung der Offshore-Windpark-Netzanbindung. 2025: 0,816 ct/kWh",
            "explanation_en": "Financing of offshore wind farm grid connections. 2025: 0.816 ct/kWh",
            "current_rate_2025": "0.816"
        },
        "konzessionsabgabe": {
            "name_de": "Konzessionsabgabe",
            "name_en": "Concession Fee", 
            "explanation_de": "Entgelt an Gemeinden für die Nutzung öffentlicher Verkehrswege für Stromleitungen",
            "explanation_en": "Fee to municipalities for using public roads for power lines",
            "typical_rates": {
                "small_municipality": "0.11 ct/kWh",
                "medium_municipality": "1.32 ct/kWh", 
                "large_municipality": "2.39 ct/kWh"
            }
        },
        "arbeitspreis": {
            "name_de": "Arbeitspreis",
            "name_en": "Working Price",
            "explanation_de": "Preis pro verbrauchter kWh, meist in ct/kWh angegeben. NICHT die Kostenkategorien!",
            "explanation_en": "Price per kWh consumed, usually stated in ct/kWh. NOT the cost categories!",
            "note": "This is the actual tariff rate, separate from cost breakdown categories"
        },
        "grundpreis": {
            "name_de": "Grundpreis",
            "name_en": "Base Price",
            "explanation_de": "Feste jährliche Grundgebühr, unabhängig vom Verbrauch. In €/Jahr, NICHT pro kWh!",
            "explanation_en": "Fixed annual base fee, independent of consumption. In €/year, NOT per kWh!",
            "note": "This is an annual fixed fee, not a per-unit charge"
        }
    }

    BILLING_CATEGORIES_VS_TARIFFS = {
        "cost_categories": {
            "explanation_de": "Kostenkategorien zeigen die Verteilung der Gesamtkosten, NICHT die Tarife",
            "explanation_en": "Cost categories show distribution of total costs, NOT the tariff rates",
            "categories": ["Grid and Metering", "Taxes and Levies", "Procurement and Supply"]
        },
        "actual_tariffs": {
            "explanation_de": "Echte Tarife sind Arbeitspreis (ct/kWh) und Grundpreis (€/Jahr)",
            "explanation_en": "Actual tariffs are working price (ct/kWh) and base price (€/year)",
            "components": ["Working Price", "Base Price"]
        }
    }

    RECENT_CHANGES_2025 = {
        "kwkg_umlage": "KWKG-Umlage increased to 0.277 ct/kWh for 2025",
        "offshore_umlage": "Offshore-Netzumlage increased to 0.816 ct/kWh for 2025",
        "stromNEV_umlage": "StromNEV-Umlage increased significantly to 1.558 ct/kWh for 2025",
        "total_levies": "Total levies increased by 68.42% to 2.651 ct/kWh for 2025",
        "electricity_tax_reduction": "Electricity tax for companies reduced to EU minimum 0.05 ct/kWh for 2024-2025",
        "smart_meter_rollout": "Accelerated smart meter deployment: 20% by 2025, 50% by 2028, 95% by 2030"
    }

def fetch_invoice_data(customer_number=None, invoice_number=None) -> Tuple[bool, Dict[str, Any]]:
    try:
        ref = get_db_reference("invoices")
        data = ref.get()
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
    """Advanced invoice analysis with corrected data extraction"""
    
    def __init__(self, invoice_data: Dict[str, Any]):
        self.invoice_data = invoice_data
        self.process_data = invoice_data.get("ProzessDaten", {}).get("ProzessDatenElement", {})
        self.consumption_data = invoice_data.get("Abrechnungsmengen", {}).get("AbrechnungsmengenElement", [])
        self.billing_items = invoice_data.get("Abrechnungspositionen", {}).get("AbrechnungspositionenElement", [])
        self.partner_data = self.process_data.get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {})
        self.cost_breakdown = invoice_data.get("Kostenblock", {}).get("KostenblockElement", [])
        
    def get_total_consumption(self) -> Tuple[float, str, str]:
        """Get total consumption from AbrechnungsmengenElement - CORRECTED"""
        total = 0
        period_from = ""
        period_to = ""
        
        if self.consumption_data:
            # Sum all consumption periods from meter readings
            total = sum(float(item.get("consumption", 0)) for item in self.consumption_data)
            
            # Get period from first and last entries
            if len(self.consumption_data) > 0:
                period_from = self.consumption_data[0].get("dateFrom", "")
                period_to = self.consumption_data[-1].get("dateTo", "")
        
        # Fallback to process data if no consumption elements
        if total == 0:
            period_from = self.process_data.get("invoicePeriodFrom", "")
            period_to = self.process_data.get("invoicePeriodTo", "")
            total = float(self.process_data.get("consumption", 0))
        
        return total, period_from, period_to
    
    def get_invoice_amount(self) -> float:
        """Get total invoice amount"""
        return float(self.process_data.get("invoiceAmount", 0))
    
    def get_bonus_amount(self) -> float:
        """Get bonus amount applied"""
        return float(self.process_data.get("bonus", 0))
    
    def get_tax_amount(self) -> float:
        """Get tax amount"""
        return float(self.process_data.get("taxAmount", 0))
    
    def get_net_amount(self) -> float:
        """Get net invoice amount"""
        return float(self.process_data.get("netInvoiceAmount", 0))
    
    def get_invoice_date(self) -> str:
        """Get invoice date"""
        return self.process_data.get("invoiceDate", "")
    
    def get_invoice_number(self) -> str:
        """Get invoice number"""
        return self.process_data.get("invoiceNumber", "")
    
    def get_working_price_details(self) -> Dict[str, Any]:
        """Get working price information from actual billing - SIMPLIFIED"""
        working_prices = []
        current_tariff_price = float(self.process_data.get("currentWorkPrice", 0)) / 100  # Convert ct to €
        
        # Extract actual billed working prices from billing items
        for item in self.billing_items:
            if item.get("priceType") == "USAGE_RATE" and item.get("name") == "Arbeit":
                price_ct = float(item.get("price", 0))  # This is in ct/kWh
                date_from = item.get("dateFrom", "")
                date_to = item.get("dateTo", "")
                
                working_prices.append({
                    "period": f"{date_from} - {date_to}",
                    "price_ct_per_kwh": price_ct,
                    "price_euro_per_kwh": price_ct / 100,
                    "date_from": date_from,
                    "date_to": date_to
                })
        
        # If only one price period, use that as the main price
        main_price_ct = working_prices[0]["price_ct_per_kwh"] if working_prices else current_tariff_price * 100
        has_multiple_periods = len(working_prices) > 1
        
        return {
            "current_tariff_ct_per_kwh": current_tariff_price * 100,
            "main_price_ct_per_kwh": main_price_ct,
            "billed_periods": working_prices,
            "has_multiple_periods": has_multiple_periods
        }
    
    def get_base_price(self) -> Tuple[float, float]:
        """Get base price (Grundpreis) - CORRECTED"""
        base_price_net = 0
        
        # Get from billing items
        for item in self.billing_items:
            if item.get("priceType") == "BASIC_RATE" and item.get("name") == "Grundkosten":
                base_price_net = float(item.get("amount", 0))
                break
        
        # Get gross base price from process data
        base_price_gross = float(self.process_data.get("currentBasePrice", 0))
        
        return base_price_net, base_price_gross
    
    def get_specific_levy_amounts(self) -> Dict[str, float]:
        """Calculate actual levy amounts - CORRECTED"""
        levies = {
            "KWKG-Umlage": 0,
            "Offshore-Netzumlage": 0,
            "Konzessionsabgabe": 0,
            "NEV-Umlage": 0,
            "Stromsteuer": 0,
            "Netznutzung": 0,
            "Messstellenbetrieb": 0
        }
        
        total_consumption, _, _ = self.get_total_consumption()
        
        # Extract from detailed billing items
        for item in self.billing_items:
            if item.get("Abrechnungspositionen-Detailliert"):
                details = item["Abrechnungspositionen-Detailliert"]["Abrechnungspositionen-DetailliertElement"]
                for detail in details:
                    name = detail.get("name", "")
                    price_ct = float(detail.get("price", 0))
                    detail_type = detail.get("type", "")
                    
                    # For usage-based charges
                    if detail.get("priceType") == "USAGE_RATE" and total_consumption > 0:
                        amount = (price_ct / 100) * total_consumption
                        
                        if "KWKG" in name:
                            levies["KWKG-Umlage"] += amount
                        elif "Offshore" in name:
                            levies["Offshore-Netzumlage"] += amount
                        elif "Konzessionsabgabe" in name:
                            levies["Konzessionsabgabe"] += amount
                        elif "NEV" in name:
                            levies["NEV-Umlage"] += amount
                        elif "Stromsteuer" in name:
                            levies["Stromsteuer"] += amount
                        elif detail_type == "GRID_USAGE":
                            levies["Netznutzung"] += amount
                    
                    # For basic charges
                    elif detail.get("priceType") == "BASIC_RATE":
                        amount = price_ct
                        if detail_type == "GRID_USAGE":
                            levies["Netznutzung"] += amount
                        elif detail_type == "METERING_POINT_OPERATION":
                            levies["Messstellenbetrieb"] += amount
        
        return levies
    
    def is_zero_consumption_bill(self) -> bool:
        """Check if this is a zero consumption bill"""
        total_consumption, _, _ = self.get_total_consumption()
        return total_consumption == 0
    
    def get_detailed_cost_breakdown(self) -> Dict[str, Any]:
        """Get cost breakdown - CORRECTED"""
        breakdown = {
            "grid_and_metering": {"amount": 0, "percentage": 0, "components": []},
            "taxes_and_levies": {"amount": 0, "percentage": 0, "components": []}, 
            "energy_supply": {"amount": 0, "percentage": 0, "components": []},
            "bonuses": {"amount": 0, "components": []}
        }
        
        total_gross = self.get_invoice_amount()
        
        # Try Kostenblock first
        if self.cost_breakdown:
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
        
        # Calculate from components if Kostenblock not available
        else:
            levies = self.get_specific_levy_amounts()
            
            grid_amount = levies["Netznutzung"] + levies["Messstellenbetrieb"]
            levy_amount = (levies["KWKG-Umlage"] + levies["Offshore-Netzumlage"] + 
                          levies["Konzessionsabgabe"] + levies["NEV-Umlage"] + 
                          levies["Stromsteuer"] + self.get_tax_amount())
            
            net_amount = self.get_net_amount()
            supply_amount = net_amount - grid_amount - (levy_amount - self.get_tax_amount())
            
            breakdown["grid_and_metering"]["amount"] = grid_amount
            breakdown["grid_and_metering"]["percentage"] = (grid_amount / total_gross * 100) if total_gross > 0 else 0
            
            breakdown["taxes_and_levies"]["amount"] = levy_amount
            breakdown["taxes_and_levies"]["percentage"] = (levy_amount / total_gross * 100) if total_gross > 0 else 0
            
            breakdown["energy_supply"]["amount"] = supply_amount
            breakdown["energy_supply"]["percentage"] = (supply_amount / total_gross * 100) if total_gross > 0 else 0
        
        # Add bonus information
        bonus_amount = self.get_bonus_amount()
        if bonus_amount != 0:
            breakdown["bonuses"]["amount"] = bonus_amount
        
        return breakdown
    
    def analyze_unusual_charges(self) -> List[Dict[str, Any]]:
        """Identify unusual charges - keeping original logic"""
        unusual_items = []
        
        # Check for high basic charges
        for item in self.billing_items:
            if item.get("priceType") == "BASIC_RATE":
                amount = float(item.get("amount", 0))
                if amount > 100:
                    unusual_items.append({
                        "type": "high_basic_charge",
                        "amount": amount,
                        "explanation": "Higher than typical basic charge"
                    })
        
        # Check for zero consumption
        if self.is_zero_consumption_bill():
            unusual_items.append({
                "type": "zero_consumption_bill",
                "explanation": "This is a setup/initial bill with zero consumption"
            })
            
        return unusual_items

class ContextualQueryAnalyzer:
    """Analyzes user queries for intent and determines appropriate response strategy"""
    
    GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening",
                "hallo", "guten morgen", "guten abend", "servus", "grüß gott"}
    
    SIMPLE_FACT_PATTERNS = [
        r"(total|gesamt).*consumption|verbrauch",
        r"invoice.*amount|rechnungsbetrag", 
        r"customer.*number|kundennummer",
        r"how much.*did i (use|consume)|wieviel.*verbraucht",
        r"kosten.*aufschlüsseln|breakdown.*cost"
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
        r"(higher|lower|höher|niedriger)",
        r"(€|eur|euro).*higher|höher",
        r"why.*bill.*increase|warum.*rechnung.*gestiegen"
    ]
    
    NAVIGATION_PATTERNS = [
        r"where.*find|wo.*finde",
        r"location.*on.*invoice|stelle.*rechnung",
        r"section.*invoice|abschnitt.*rechnung",
        r"how.*navigate|wie.*navigiere"
    ]
    
    EXPLANATION_PATTERNS = [
        r"was ist|what is",
        r"was bedeutet|what does.*mean",
        r"erkläre|explain",
        r"definition|bedeutung"
    ]
    
    def __init__(self, conversation_history: List[str] = None):
        self.conversation_history = conversation_history or []
        
    def analyze_query(self, query: str) -> Tuple[QueryType, ResponseFormat]:
        """Analyze query and determine response strategy with conciseness"""
        query_lower = query.lower()
        query_length = len(query.split())
        
        # Determine conciseness level based on query
        if query_length <= 5 or any(word in query_lower for word in ['how much', 'total', 'amount', 'consumption', 'wieviel']):
            conciseness_level = "brief"
        elif any(word in query_lower for word in ['explain', 'detail', 'breakdown', 'why', 'understand', 'erkläre', 'aufschlüsseln']):
            conciseness_level = "detailed"
        else:
            conciseness_level = "moderate"
        
        # Check for greetings
        if any(greet in query_lower for greet in self.GREETINGS):
            return QueryType.GREETING, ResponseFormat(
                concise=True, 
                personalized=True, 
                conciseness_level="brief"
            )
        
        # Check for explanations/definitions
        if any(re.search(pattern, query_lower) for pattern in self.EXPLANATION_PATTERNS):
            return QueryType.EXPLANATION, ResponseFormat(
                concise=False,
                include_regulatory_context=True,
                personalized=True,
                conciseness_level="moderate"
            )
        
        # Check for navigation queries
        if any(re.search(pattern, query_lower) for pattern in self.NAVIGATION_PATTERNS):
            return QueryType.NAVIGATION, ResponseFormat(
                concise=False, 
                personalized=True,
                conciseness_level="moderate"
            )
        
        # Check for simple facts
        if any(re.search(pattern, query_lower) for pattern in self.SIMPLE_FACT_PATTERNS):
            return QueryType.SIMPLE_FACT, ResponseFormat(
                concise=True, 
                personalized=True,
                conciseness_level=conciseness_level
            )
        
        # Check for calculation requests
        if any(re.search(pattern, query_lower) for pattern in self.CALCULATION_PATTERNS):
            return QueryType.CALCULATION, ResponseFormat(
                detailed_calculation=True, 
                include_regulatory_context=False,
                personalized=True,
                conciseness_level="moderate"
            )
        
        # Check for comparisons
        if any(re.search(pattern, query_lower) for pattern in self.COMPARISON_PATTERNS):
            return QueryType.COMPARISON, ResponseFormat(
                detailed_calculation=False,
                personalized=True,
                conciseness_level="moderate"
            )
        
        # Default to explanation
        return QueryType.EXPLANATION, ResponseFormat(
            include_regulatory_context=False,
            personalized=True,
            conciseness_level=conciseness_level
        )

class KnowledgeBaseIntegrator:
    """Enhanced integrator that leverages category structure"""
    
    def __init__(self, knowledge_base_path: str = None):
        self.knowledge_base = {}
        self.categories = {}
        if knowledge_base_path:
            self.load_knowledge_base(knowledge_base_path)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            kb_path = os.path.join(base_dir, "knowledge_base.json")
            if os.path.exists(kb_path):
                self.load_knowledge_base(kb_path)
    
    def load_knowledge_base(self, path: str):
        """Load and organize knowledge base by categories"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
                self.categories = self.knowledge_base.get("utility_invoice_queries", {})
                print(f"✅ Loaded {len(self.categories)} knowledge base categories")
        except Exception as e:
            print(f"Error loading knowledge base: {e}")
            self.knowledge_base = {}
            self.categories = {}
    
    def get_category_for_query(self, query: str) -> str:
        """Determine the most relevant category based on query"""
        query_lower = query.lower()
        
        # Category keywords mapping
        category_keywords = {
            'invoice_structure': ['where', 'find', 'section', 'invoice structure', 'malo-id', 'obis', 'locate'],
            'consumption': ['consumption', 'usage', 'kwh', 'meter reading', 'estimate', 'verbrauch'],
            'pricing_components': ['price', 'cost', 'charge', 'fee', 'component', 'breakdown', 'tariff', 'konzessionsabgabe', 'netzentgelt', 'stromsteuer'],
            'payments_advances': ['payment', 'advance', 'installment', 'abschlag', 'prepayment', 'verpasse', 'miss'],
            'payments_credits': ['credit', 'balance', 'refund', 'guthaben'],
            'late_billing': ['late', 'delayed', 'overdue', 'verspätet'],
            'regulatory_changes': ['regulation', 'law', 'changes', 'eeg', 'reform'],
            'contract_terms': ['contract', 'term', 'agreement', 'vertrag'],
            'disputes_complaints': ['dispute', 'complaint', 'wrong', 'error', 'fehler'],
            'calculations_examples': ['calculate', 'formula', 'example', 'berechnung'],
            'bonuses_discounts': ['bonus', 'discount', 'neukunden', 'cashback', 'rabatt'],
            'meter_operations': ['meter', 'reading', 'zähler', 'ablesung'],
            'energy_efficiency': ['efficiency', 'save', 'reduce', 'sparen'],
            'green_energy_options': ['green', 'renewable', 'ökostrom', 'solar'],
            'taxes_and_vat': ['tax', 'vat', 'mwst', 'steuer'],
            'special_customer_situations': ['move', 'umzug', 'special', 'hardship'],
            'consumer_rights': ['rights', 'protection', 'verbraucherschutz'],
            'dispute_resolution': ['resolution', 'mediation', 'schlichtung'],
            'energy_transition': ['transition', 'energiewende', 'future'],
            'comparisons_graphs': ['graph', 'chart', 'compare', 'vergleich'],
            'energy_price_brake': ['price brake', 'preisbremse', 'cap', 'relief']
        }
        
        # Score each category
        scores = {}
        for category, keywords in category_keywords.items():
            score = sum(2 if keyword in query_lower else 0 for keyword in keywords)
            # Boost score for exact phrase matches
            if category.replace('_', ' ') in query_lower:
                score += 5
            if score > 0:
                scores[category] = score
        
        # Return highest scoring category
        if scores:
            return max(scores, key=scores.get)
        return 'miscellaneous'
    
    def find_relevant_context(self, query: str, language: str = 'en', max_items: int = 5) -> List[Dict[str, str]]:
        """Enhanced context finding with category awareness"""
        relevant_items = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # First, check the most relevant category
        primary_category = self.get_category_for_query(query)
        
        # Search in primary category first
        if primary_category in self.categories:
            items = self.categories.get(primary_category, [])
            for item in items:
                input_key = f"input_{language}"
                if input_key in item:
                    item_text_lower = item[input_key].lower()
                    item_words = set(item_text_lower.split())
                    
                    # Calculate overlap score
                    overlap = len(query_words.intersection(item_words))
                    
                    # Check for specific term matches
                    if "konzessionsabgabe" in query_lower and "konzessionsabgabe" in item_text_lower:
                        overlap += 10  # High boost for exact term match
                    
                    # Check for phrase matches
                    if overlap > 2 or any(phrase in query_lower for phrase in item_text_lower.split('?')[0:1]):
                        relevant_items.append({
                            "query": item[input_key],
                            "response": item.get(f"response_{language}", ""),
                            "category": primary_category,
                            "relevance": "high" if overlap > 3 else "medium",
                            "score": overlap
                        })
        
        # Then search other categories if needed
        if len(relevant_items) < max_items:
            for category, items in self.categories.items():
                if category == primary_category:
                    continue
                for item in items:
                    input_key = f"input_{language}"
                    if input_key in item:
                        item_text_lower = item[input_key].lower()
                        item_words = set(item_text_lower.split())
                        overlap = len(query_words.intersection(item_words))
                        
                        if overlap > 1:
                            relevant_items.append({
                                "query": item[input_key],
                                "response": item.get(f"response_{language}", ""),
                                "category": category,
                                "relevance": "medium" if overlap > 2 else "low",
                                "score": overlap
                            })
        
        # Sort by relevance score and return top items
        relevant_items.sort(key=lambda x: x['score'], reverse=True)
        return relevant_items[:max_items]

class AgenticUtilityBillLLM:
    """Intelligent, contextual utility bill assistant with sophisticated reasoning"""
    
    def __init__(self, model_name="mistral-7b-instruct-v0.1.Q4_0.gguf"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(base_dir, "models")
        self.model = GPT4All(model_name, model_path=self.model_path)
        
        self.regulations = GermanEnergyRegulations()
        self.knowledge_base = KnowledgeBaseIntegrator()
        self.conversation_context = {
            'queries': [],
            'language': 'en',
            'customer_data': {},
            'current_invoice': {},
            'previous_invoices': []
        }
        
    def validate_identifier(self, identifier: str) -> Tuple[bool, str, Dict]:
        """Validate if identifier is customer number or invoice number"""
        # Try as invoice number first
        is_valid, data = fetch_invoice_data(invoice_number=identifier)
        if is_valid:
            return True, "invoice", data
        
        # Try as customer number
        is_valid, data = fetch_invoice_data(customer_number=identifier)
        if is_valid:
            return True, "customer", data
        
        return False, "none", {}
    
    def compare_with_previous_invoice(self, current_invoice: Dict, all_invoices: Dict) -> Dict[str, Any]:
        """Compare current invoice with previous invoice"""
        current_analyzer = IntelligentInvoiceAnalyzer(current_invoice)
        current_date = datetime.strptime(current_analyzer.get_invoice_date(), "%d.%m.%Y")
        
        # Find previous invoice
        previous_invoice = None
        previous_date = None
        
        for invoice_data in all_invoices.values():
            invoice = invoice_data.get("Data", {})
            analyzer = IntelligentInvoiceAnalyzer(invoice)
            invoice_date = datetime.strptime(analyzer.get_invoice_date(), "%d.%m.%Y")
            
            if invoice_date < current_date:
                if previous_date is None or invoice_date > previous_date:
                    previous_date = invoice_date
                    previous_invoice = invoice
        
        if not previous_invoice:
            return {"found": False}
        
        previous_analyzer = IntelligentInvoiceAnalyzer(previous_invoice)
        
        # Compare key metrics
        current_amount = current_analyzer.get_invoice_amount()
        previous_amount = previous_analyzer.get_invoice_amount()
        amount_difference = current_amount - previous_amount
        
        current_consumption = current_analyzer.get_total_consumption()[0]
        previous_consumption = previous_analyzer.get_total_consumption()[0]
        consumption_difference = current_consumption - previous_consumption
        
        # Analyze reasons for differences
        reasons = []
        
        if consumption_difference > 0:
            reasons.append(f"Higher consumption: {consumption_difference:.0f} kWh more than previous period")
        elif consumption_difference < 0:
            reasons.append(f"Lower consumption: {abs(consumption_difference):.0f} kWh less than previous period")
        
        # Check for price changes
        if amount_difference > 0 and consumption_difference <= 0:
            reasons.append("Price increase despite similar or lower consumption - likely due to tariff changes")
        
        # Check bonus differences
        current_bonus = current_analyzer.get_bonus_amount()
        previous_bonus = previous_analyzer.get_bonus_amount()
        if current_bonus != previous_bonus:
            reasons.append(f"Bonus difference: €{current_bonus - previous_bonus:.2f}")
        
        return {
            "found": True,
            "previous_amount": previous_amount,
            "current_amount": current_amount,
            "difference": amount_difference,
            "consumption_difference": consumption_difference,
            "reasons": reasons,
            "previous_period": previous_analyzer.get_total_consumption()[1] + " to " + previous_analyzer.get_total_consumption()[2]
        }
    
    def build_contextual_prompt(self, query: str, analyzer: IntelligentInvoiceAnalyzer, 
                               query_type: QueryType, response_format: ResponseFormat,
                               language: str = 'en', comparison_data: Dict = None) -> str:
        """Build sophisticated, context-aware prompt with CORRECTED data extraction"""
        
        # Customer information
        partner = analyzer.partner_data
        raw_salutation = partner.get("salutation", "")
        if language == "en":
            if raw_salutation.lower() == "frau":
                salutation = "Ms."
            elif raw_salutation.lower() == "herr":
                salutation = "Mr."
            else:
                salutation = "Dear"
        else:
            salutation = raw_salutation
        first_name = partner.get("firstName", "")
        last_name = partner.get("name", "")
        customer_name = f"{first_name} {last_name}".strip()
        
        # CORRECTED data extraction
        total_consumption, period_from, period_to = analyzer.get_total_consumption()
        cost_breakdown = analyzer.get_detailed_cost_breakdown()
        working_price_details = analyzer.get_working_price_details()
        base_price_net, base_price_gross = analyzer.get_base_price()
        specific_levies = analyzer.get_specific_levy_amounts()
        is_zero_consumption = analyzer.is_zero_consumption_bill()
        
        # Get relevant knowledge base context
        kb_context = self.knowledge_base.find_relevant_context(query, language, max_items=3)
        
        # Language-specific instructions
        language_instruction = {
            "de": "WICHTIG: Antworte IMMER auf Deutsch. Verwende deutsche Begriffe und Formulierungen.",
            "en": "IMPORTANT: Always respond in English. Use English terms and phrases."
        }
        
        # Conciseness instructions
        conciseness_instructions = {
            "brief": {
                "de": "Antworte SEHR KURZ in 1-2 Sätzen. Nur die wichtigsten Fakten.",
                "en": "Answer VERY BRIEFLY in 1-2 sentences. Essential facts only."
            },
            "moderate": {
                "de": "Antworte präzise in 3-4 Sätzen. Wichtiger Kontext inklusive.",
                "en": "Answer concisely in 3-4 sentences. Include key context."
            },
            "detailed": {
                "de": "Gib eine ausführliche Erklärung mit allen relevanten Details.",
                "en": "Provide comprehensive explanation with all relevant details."
            }
        }
        
        # Build the corrected system instruction
        system_instruction = f"""You are KlarBill, an intelligent energy billing assistant.

{language_instruction[language]}

CUSTOMER: {salutation} {customer_name}
INVOICE: #{analyzer.get_invoice_number()}
PERIOD: {period_from} - {period_to}
TOTAL AMOUNT: €{analyzer.get_invoice_amount():.2f}
CONSUMPTION: {total_consumption:.0f} kWh{"" if not is_zero_consumption else " (ZERO CONSUMPTION - Setup/Initial Bill)"}

TARIFF RATES:
- Working Price: {working_price_details['main_price_ct_per_kwh']:.2f} ct/kWh
- Base Price: €{base_price_net:.2f}/year (net), €{base_price_gross:.2f}/year (gross)
"""
        
        # Add multiple periods only if they exist
        if working_price_details['has_multiple_periods']:
            system_instruction += "\nWORKING PRICE PERIODS:\n"
            for period in working_price_details['billed_periods']:
                system_instruction += f"- {period['period']}: {period['price_ct_per_kwh']:.2f} ct/kWh\n"
        
        system_instruction += f"""
SPECIFIC LEVY AMOUNTS (These are the actual €€ amounts charged):
- KWKG-Umlage: €{specific_levies['KWKG-Umlage']:.2f}
- Konzessionsabgabe: €{specific_levies['Konzessionsabgabe']:.2f}
- Offshore-Netzumlage: €{specific_levies['Offshore-Netzumlage']:.2f}
- NEV-Umlage: €{specific_levies['NEV-Umlage']:.2f}
- Stromsteuer: €{specific_levies['Stromsteuer']:.2f}
- Netznutzung: €{specific_levies['Netznutzung']:.2f}
- Messstellenbetrieb: €{specific_levies['Messstellenbetrieb']:.2f}

COST CATEGORIES (Distribution of costs, NOT tariff rates):
- Grid & Metering: €{cost_breakdown['grid_and_metering']['amount']:.2f} ({cost_breakdown['grid_and_metering']['percentage']:.1f}%)
- Taxes & Levies: €{cost_breakdown['taxes_and_levies']['amount']:.2f} ({cost_breakdown['taxes_and_levies']['percentage']:.1f}%)
- Energy Supply: €{cost_breakdown['energy_supply']['amount']:.2f} ({cost_breakdown['energy_supply']['percentage']:.1f}%)

RESPONSE STYLE: {conciseness_instructions[response_format.conciseness_level][language]}

CRITICAL RULES:
1. ALWAYS use actual invoice data - NEVER use placeholder values
2. {"Antworte auf DEUTSCH" if language == "de" else "Respond in ENGLISH"}
3. Working price: {working_price_details['main_price_ct_per_kwh']:.2f} ct/kWh
4. Base price: €{base_price_net:.2f}/year (annual fee)
5. Use customer's actual name: {customer_name}
6. Answer the specific question directly
"""

        # Add invoice-specific breakdown
        system_instruction += f"""
ACTUAL INVOICE CALCULATION:
- Net Amount: €{analyzer.get_net_amount():.2f}
- Tax (19% VAT): €{analyzer.get_tax_amount():.2f}
- Gross Amount: €{analyzer.get_invoice_amount():.2f}
- Bonus Applied: €{analyzer.get_bonus_amount():.2f}
- Final Payment: €{analyzer.get_invoice_amount() + analyzer.get_bonus_amount():.2f}
"""

        # Add zero consumption explanation if applicable
        if is_zero_consumption:
            if language == "de":
                system_instruction += """
WICHTIG - NULLVERBRAUCH: Diese Rechnung zeigt 0 kWh Verbrauch. Das ist typisch für Einrichtungs-/Startabrechnungen. Sie zahlen nur die Grundgebühr und Setup-Kosten, keine verbrauchsabhängigen Gebühren.
"""
            else:
                system_instruction += """
IMPORTANT - ZERO CONSUMPTION: This invoice shows 0 kWh consumption. This is typical for setup/initial bills. You're only paying base fees and setup costs, no usage-based charges.
"""

        # Add specific knowledge for common terms
        if "working price" in query.lower() or "arbeitspreis" in query.lower():
            if language == "de":
                if working_price_details['has_multiple_periods']:
                    period_info = ', '.join([f"{p['price_ct_per_kwh']:.2f} ct/kWh ({p['period']})" for p in working_price_details['billed_periods']])
                    system_instruction += f"ARBEITSPREIS DETAILS: {period_info}. "
                else:
                    system_instruction += f"ARBEITSPREIS DETAILS: {working_price_details['main_price_ct_per_kwh']:.2f} ct/kWh. "
            else:
                if working_price_details['has_multiple_periods']:
                    period_info = ', '.join([f"{p['price_ct_per_kwh']:.2f} ct/kWh ({p['period']})" for p in working_price_details['billed_periods']])
                    system_instruction += f"WORKING PRICE DETAILS: {period_info}. "
                else:
                    system_instruction += f"WORKING PRICE DETAILS: {working_price_details['main_price_ct_per_kwh']:.2f} ct/kWh. "

        if "konzessionsabgabe" in query.lower():
            if language == "de":
                system_instruction += f"""
KONZESSIONSABGABE DETAILS: Auf Ihrer Rechnung wurden €{specific_levies['Konzessionsabgabe']:.2f} für die Konzessionsabgabe berechnet. Das ist eine Gebühr an Gemeinden für die Nutzung öffentlicher Wege.
"""
            else:
                system_instruction += f"""
CONCESSION FEE DETAILS: Your invoice shows €{specific_levies['Konzessionsabgabe']:.2f} for the concession fee. This is paid to municipalities for using public roads for power lines.
"""

        if "kwkg" in query.lower():
            if language == "de":
                system_instruction += f"""
KWKG-UMLAGE DETAILS: Auf Ihrer Rechnung wurden €{specific_levies['KWKG-Umlage']:.2f} für die KWKG-Umlage berechnet. 2025 beträgt die KWKG-Umlage 0,277 ct/kWh zur Förderung von Kraft-Wärme-Kopplung.
"""
            else:
                system_instruction += f"""
KWKG-LEVY DETAILS: Your invoice shows €{specific_levies['KWKG-Umlage']:.2f} for the KWKG levy. In 2025, the KWKG levy is 0.277 ct/kWh to support combined heat and power.
"""

        # Add knowledge base context if highly relevant
        if kb_context and any(item['relevance'] == 'high' for item in kb_context):
            system_instruction += f"\n{'RELEVANTE INFO' if language == 'de' else 'RELEVANT INFO'}:\n"
            for item in kb_context[:2]:
                if item['relevance'] == 'high':
                    system_instruction += f"- {item['response']}\n"

        # Query-specific instructions with correct data
        if query_type == QueryType.SIMPLE_FACT and ("aufschlüsseln" in query.lower() or "breakdown" in query.lower()):
            if language == "de":
                system_instruction += f"""
KORREKTE KOSTENAUFSCHLÜSSELUNG:
- Grundgebühr + Verbrauchskosten = €{analyzer.get_net_amount():.2f} (netto)
- Mehrwertsteuer (19%) = €{analyzer.get_tax_amount():.2f}
- Bonus/Rabatt = €{analyzer.get_bonus_amount():.2f}
- GESAMT = €{analyzer.get_invoice_amount():.2f}
"""
            else:
                system_instruction += f"""
CORRECT COST BREAKDOWN:
- Base fee + Usage charges = €{analyzer.get_net_amount():.2f} (net)
- VAT (19%) = €{analyzer.get_tax_amount():.2f}
- Bonus/Discount = €{analyzer.get_bonus_amount():.2f}
- TOTAL = €{analyzer.get_invoice_amount():.2f}
"""

        # Add comparison data if available
        if comparison_data and comparison_data.get("found"):
            system_instruction += f"""
COMPARISON WITH PREVIOUS INVOICE:
- Previous: €{comparison_data['previous_amount']:.2f}
- Current: €{comparison_data['current_amount']:.2f}  
- Difference: €{comparison_data['difference']:.2f} ({'+' if comparison_data['difference'] > 0 else ''}{(comparison_data['difference'] / comparison_data['previous_amount'] * 100):.1f}%)
- Main Reason: {comparison_data['reasons'][0] if comparison_data['reasons'] else 'Similar billing period'}
"""

        # Final query instruction
        query_context = f"\nQUERY: {query}\n"
        
        # Strong reminder about using correct data
        if language == "de":
            query_context += "Antworte auf DEUTSCH mit korrekten Tarifdaten und echten Beträgen!\n"
        else:
            query_context += "Respond in ENGLISH with correct tariff data and actual amounts!\n"
        
        return system_instruction + query_context + f"\n{'Antwort' if language == 'de' else 'Response'}:"

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
                error_msg = {
                    "de": "Ich konnte Ihre Rechnungsdaten nicht finden. Bitte überprüfen Sie Ihre Kunden- oder Rechnungsnummer.",
                    "en": "I couldn't find your invoice data. Could you please verify your customer or invoice number?"
                }
                return {
                    "text": error_msg[language],
                    "structured": {},
                    "needs_invoice_number": False
                }

        # Handle multiple invoices
        if customer_number and not invoice_number and len(bill_context) > 1:
            invoice_suggestions = [
                v["Data"]["ProzessDaten"]["ProzessDatenElement"]["invoiceNumber"]
                for v in bill_context.values()
            ]
            msg = {
                "de": f"Ich habe {len(invoice_suggestions)} Rechnungen für Ihr Konto gefunden. Bitte wählen Sie eine Rechnung aus:",
                "en": f"I found {len(invoice_suggestions)} invoices for your account. Please specify which invoice you'd like me to analyze:"
            }
            return {
                "text": msg[language],
                "structured": {},
                "needs_invoice_number": True,
                "invoice_suggestions": invoice_suggestions
            }

        # Get the invoice data
        invoice = next(iter(bill_context.values()), {}).get("Data", {})
        if not invoice:
            error_msg = {
                "de": "Ich konnte nicht auf Ihre Rechnungsdetails zugreifen. Bitte versuchen Sie es erneut.",
                "en": "I couldn't access your invoice details. Please try again."
            }
            return {
                "text": error_msg[language],
                "structured": {}, 
                "needs_invoice_number": False
            }

        # Initialize analyzers
        analyzer = IntelligentInvoiceAnalyzer(invoice)
        query_analyzer = ContextualQueryAnalyzer(self.conversation_context['queries'])
        
        # Analyze query and determine response strategy
        query_type, response_format = query_analyzer.analyze_query(query)
        
        # Check if this is a comparison query
        comparison_data = None
        if query_type == QueryType.COMPARISON:
            # Get all invoices for comparison
            all_invoices = bill_context
            if customer_number and not invoice_number:
                # Fetch all invoices for the customer
                _, all_invoices = fetch_invoice_data(customer_number=customer_number)
            
            comparison_data = self.compare_with_previous_invoice(invoice, all_invoices)
        
        # Build contextual prompt with proper language support
        prompt = self.build_contextual_prompt(query, analyzer, query_type, response_format, language, comparison_data)
        
        # Generate response with appropriate parameters
        max_tokens = 300 if response_format.conciseness_level == "brief" else 600 if response_format.conciseness_level == "moderate" else 1200
        response = self.model.generate(prompt, max_tokens=max_tokens, temp=0.1).strip()  # Very low temp for consistency
        
        # Prepare structured data with correct information
        total_consumption, period_from, period_to = analyzer.get_total_consumption()
        cost_breakdown = analyzer.get_detailed_cost_breakdown()
        working_price_details = analyzer.get_working_price_details()
        base_price_net, base_price_gross = analyzer.get_base_price()
        specific_levies = analyzer.get_specific_levy_amounts()
        
        structured_data = {
            "customer_name": analyzer.partner_data.get("firstName", "") + " " + analyzer.partner_data.get("name", ""),
            "salutation": analyzer.partner_data.get("salutation", ""),
            "consumption": total_consumption,
            "consumption_period": f"{period_from} to {period_to}",
            "invoice_amount": analyzer.get_invoice_amount(),
            "net_amount": analyzer.get_net_amount(), 
            "tax_amount": analyzer.get_tax_amount(),
            "bonus": analyzer.get_bonus_amount(),
            "invoice_number": analyzer.get_invoice_number(),
            "cost_breakdown": cost_breakdown,
            "tariff_info": {
                "working_price_ct_per_kwh": working_price_details['main_price_ct_per_kwh'],
                "working_price_periods": working_price_details['billed_periods'] if working_price_details['has_multiple_periods'] else None,
                "base_price_net_per_year": base_price_net,
                "base_price_gross_per_year": base_price_gross
            },
            "specific_levies": specific_levies,
            "is_zero_consumption": analyzer.is_zero_consumption_bill(),
            "unusual_charges": analyzer.analyze_unusual_charges(),
            "query_type": query_type.value,
            "response_format": {
                "concise": response_format.concise,
                "detailed_calculation": response_format.detailed_calculation,
                "regulatory_context": response_format.include_regulatory_context,
                "conciseness_level": response_format.conciseness_level
            },
            "knowledge_base_category": self.knowledge_base.get_category_for_query(query),
            "language": language
        }
        
        # Add comparison data if available
        if comparison_data:
            structured_data["comparison"] = comparison_data
        
        return {
            "text": response,
            "structured": structured_data,
            "needs_invoice_number": False
        }

    def validate_number(self, customer_number=None, invoice_number=None) -> Tuple[bool, Dict]:
        """Validate and fetch invoice data"""
        return fetch_invoice_data(customer_number, invoice_number)