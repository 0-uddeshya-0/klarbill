# backend/app.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from llm_service import UtilityBillLLM, GREETINGS
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LLM service once for the application
llm = UtilityBillLLM()

class QueryRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = Field(default=None)
    language: str = Field(default='en')
    customer_id: Optional[str] = Field(default=None)

@app.post("/chat")
async def ask_question(request: QueryRequest):
    try:
        # Check if this might be a customer ID response
        if not request.customer_id and llm.is_customer_id_input(request.message):
            customer_id = llm.extract_customer_id(request.message)
            if customer_id:
                # Confirm the ID was accepted
                response = f"Thanks! I've registered your customer ID: {customer_id}. How can I help with your utility bill today?"
                if request.language == 'de':
                    response = f"Danke! Ich habe Ihre Kundennummer registriert: {customer_id}. Wie kann ich Ihnen heute mit Ihrer Versorgungsrechnung helfen?"
                return {"response": response, "customer_id": customer_id}
        
        # Check if we need to ask for ID (modified logic)
        if not request.customer_id:
            # Always ask for ID unless message is a customer ID or simple yes/no
            if request.message.strip().lower() not in ["yes", "no", "ja", "nein"]:
                # Use LLM's greeting check instead of hardcoded list
                if not any(greeting in request.message.lower() for greeting in GREETINGS):
                    return {"response": llm.ask_for_customer_id(request.language), "needs_customer_id": True}
        
        # Process normal message with LLM
        response = llm.get_response(
            query=request.message,
            bill_context=request.context,
            language=request.language,
            customer_id=request.customer_id
        )
        
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
    
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
