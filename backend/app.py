# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from agentic_llm_service import AgenticUtilityBillLLM  # Updated import
from data.upload_invoices import upload_invoices_once
import uvicorn
import requests
from fastapi.middleware.cors import CORSMiddleware
import time
import re
from data.firebase_service import get_invoice_by_number, get_invoices_by_customer, get_db_reference

# Ensure .env config and environment variables are loaded at startup
from config import ensure_config

ensure_config()
upload_invoices_once()

app = FastAPI(title="KlarBill Agentic AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Agentic AI LLM
llm = AgenticUtilityBillLLM()

class QueryRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    language: str = 'en'
    customer_number: Optional[str] = None
    invoice_number: Optional[str] = None

class LogMessageRequest(BaseModel):
    customer_number: Optional[str] = None
    invoice_number: Optional[str] = None
    message: str
    role: str
    timestamp: str
    topic: Optional[str] = None
    session_id: Optional[str] = None

class ValidateIdentifierRequest(BaseModel):
    identifier: str
    language: str = 'en'

@app.post("/validate_identifier")
async def validate_identifier(request: ValidateIdentifierRequest):
    """Validate identifier and return customer/invoice information"""
    try:
        # Use the LLM's validate_identifier method
        is_valid, id_type, data = llm.validate_identifier(request.identifier)
        
        if not is_valid:
            return {
                "valid": False,
                "type": "none",
                "message": "Invalid customer or invoice number"
            }
        
        # Get customer information
        if data:
            first_invoice = next(iter(data.values()))
            invoice_data = first_invoice.get("Data", {})
            process_data = invoice_data.get("ProzessDaten", {}).get("ProzessDatenElement", {})
            partner_data = process_data.get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {})
            
            # Get date of birth
            date_of_birth = partner_data.get("dateOfBirth", "")
            
            # Get all invoice numbers if multiple
            invoice_numbers = []
            if id_type == "customer" and len(data) > 1:
                invoice_numbers = [
                    v["Data"]["ProzessDaten"]["ProzessDatenElement"]["invoiceNumber"]
                    for v in data.values()
                ]
            
            return {
                "valid": True,
                "type": id_type,
                "customer_number": partner_data.get("customerNumber", ""),
                "customer_name": f"{partner_data.get('firstName', '')} {partner_data.get('name', '')}".strip(),
                "salutation": partner_data.get("salutation", ""),
                "date_of_birth": date_of_birth,  # Add DOB to response
                "multiple_invoices": len(invoice_numbers) > 0,
                "invoice_numbers": invoice_numbers,
                "language": request.language
            }
        
        return {
            "valid": False,
            "type": "none",
            "message": "No data found"
        }
        
    except Exception as e:
        print(f"Validation error: {e}")
        return {
            "valid": False,
            "type": "none",
            "message": "Error validating identifier"
        }

@app.post("/chat")
async def chat_route(request: QueryRequest):
    """Enhanced chat endpoint with Agentic AI capabilities"""
    try:
        # Handle the request with the Agentic AI
        result = llm.get_response(
            query=request.message,
            bill_context=request.context,
            language=request.language,
            customer_number=request.customer_number,
            invoice_number=request.invoice_number
        )

        # Build comprehensive response
        response = {
            "response": result["text"],
            "structured": result.get("structured", {}),
            "needs_invoice_number": result.get("needs_invoice_number", False),
            "invoice_suggestions": result.get("invoice_suggestions", []),
            "query_type": result.get("structured", {}).get("query_type", "unknown"),
            "response_format": result.get("structured", {}).get("response_format", {})
        }

        # Extract key information for frontend
        structured = result.get("structured", {})

        # Customer identification
        if structured.get("customer_name"):
            response["customer_name"] = structured["customer_name"]
        if structured.get("salutation"):
            response["customer_greeting"] = structured["salutation"]
        
        # Invoice details
        if structured.get("invoice_number"):
            response["invoice_number"] = structured["invoice_number"]
        if structured.get("consumption"):
            response["consumption"] = structured["consumption"]
        if structured.get("invoice_amount"):
            response["invoice_amount"] = structured["invoice_amount"]
            
        # Set customer/invoice number for session persistence
        if request.customer_number:
            response["session_customer_number"] = request.customer_number
        if request.invoice_number or structured.get("invoice_number"):
            response["session_invoice_number"] = request.invoice_number or structured.get("invoice_number")

        return response

    except Exception as e:
         # Enhanced error handling with detailed logging
        print(f"Chat error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        error_message = f"I encountered an issue processing your request. Please try again."
        if "invoice" in str(e).lower():
            error_message = "I couldn't access your invoice data. Please verify your customer or invoice number."
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_message = "There seems to be a connection issue. Please try again in a moment."
        elif "model" in str(e).lower() or "gpt4all" in str(e).lower():
            error_message = "The AI model is not properly initialized. Please check the model configuration."
            
        return {
            "response": error_message,
            "structured": {},
            "error": True,
            "error_type": "processing_error",
            "debug_error": str(e)  # Add debug info
        }


@app.post("/log_message")
async def log_message(request: LogMessageRequest):
    """Log messages directly under invoice or customer path"""
    try:
        if request.customer_number:
            path = f"messages/customers/{re.sub(r'[^a-zA-Z0-9_-]', '_', request.customer_number)}"
        elif request.invoice_number:
            path = f"messages/invoices/{re.sub(r'[^a-zA-Z0-9_-]', '_', request.invoice_number)}"
        else:
            return {"status": "error", "logged": False, "message": "Missing invoice_number or customer_number."}

        log_data = {
            'customer_number': request.customer_number,
            'invoice_number': request.invoice_number,
            'message': request.message,
            'role': request.role,
            'timestamp': request.timestamp,
            'topic': request.topic or 'general',
            'session_id': request.session_id
        }

        ref = get_db_reference(path)
        ref.push(log_data)
        return {"status": "success", "logged": True}

    except Exception as e:
        print(f"Logging error: {e}")
        return {"status": "partial_success", "logged": False, "message": "Message processed but logging failed"}

class NameRequest(BaseModel):
    customer_number: Optional[str] = None
    invoice_number: Optional[str] = None
    language: str = 'en'

@app.post("/customer_name")
async def customer_name(request: NameRequest):
    """Return localized greeting based on customer or invoice number"""
    try:
        invoice = None
        match_type = None

        # 1. Try invoice_number first
        if request.invoice_number:
            invoice_entry = get_invoice_by_number(request.invoice_number)
            if invoice_entry:
                invoice = list(invoice_entry.values())[0]
                match_type = "invoice"
        # 2. If not found, try customer_number
        if not invoice and request.customer_number:
            invoice_entries = get_invoices_by_customer(request.customer_number)
            if invoice_entries:
                invoice = list(invoice_entries.values())[0]
                match_type = "customer"

        if not invoice:
            return {"customer_greeting": "", "type": ""}

        data = invoice.get("Data", {})
        pro_daten = data.get("ProzessDaten", {})
        prozess_element = pro_daten.get("ProzessDatenElement", {})

        if isinstance(prozess_element, list):
            process_data = prozess_element[0] if prozess_element else {}
        else:
            process_data = prozess_element

        business_partner = process_data.get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {})
        name = business_partner.get("name", "")
        salutation = business_partner.get("salutation", "")

        if not name:
            return {"customer_greeting": "", "type": ""}

        if request.language == "de":
            greeting = f"{salutation} {name}!"
        else:
            if salutation.lower() == "frau":
                salutation_translated = "Ms."
            elif salutation.lower() == "herr":
                salutation_translated = "Mr."
            else:
                salutation_translated = salutation
            greeting = f"{salutation_translated} {name}!"

        return {"customer_greeting": greeting, "type": match_type or ""}

    except Exception as e:
        print(f"Greeting fetch error: {e}")
        return {"customer_greeting": "", "type": ""}

@app.get("/health")
async def health_check():
    """Enhanced health check with system information"""
    try:
        # Test LLM availability
        llm_status = "healthy" if llm.model else "unavailable"
        
        # Test Firebase connectivity
        firebase_status = "unknown"
        try:
            try:
                test_ref = get_db_reference("/health_test_check")
                _ = test_ref.get()
                firebase_status = "healthy"
            except:
                firebase_status = "unavailable"
        except:
            firebase_status = "unavailable"
            
        return {
            "status": "healthy",
            "llm_status": llm_status,
            "firebase_status": firebase_status,
            "version": "2.0.0",
            "features": [
                "agentic_ai",
                "contextual_responses", 
                "regulatory_knowledge",
                "multi_language_support",
                "intelligent_query_analysis"
            ]
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "version": "2.0.0"
        }

@app.get("/")
async def root():
    """API information endpoint"""
    return {
        "service": "KlarBill Agentic AI",
        "version": "2.0.0",
        "description": "Intelligent utility bill assistant with contextual understanding",
        "endpoints": {
            "chat": "/chat",
            "log": "/log_message", 
            "health": "/health",
            "validate_identifier": "/validate_identifier"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)