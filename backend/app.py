import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llm_service import UtilityBillLLM
import uvicorn
import json
from data.firebase_service import get_db_reference

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = UtilityBillLLM()

def upload_invoices_once():
    ref = get_db_reference('invoices')
    existing = ref.get()

    if existing:
        print("Invoices already uploaded. Skipping.")
        return

    try:
        with open("data/invoices.json", "r", encoding="utf-8") as f:
            invoices = json.load(f)
            for invoice in invoices:
                ref.push(invoice)
            print(f"Uploaded {len(invoices)} invoices to Firebase Realtime Database.")
    except Exception as e:
        print(f"Error uploading invoices: {e}")

upload_invoices_once()

class QueryRequest(BaseModel):
    message: str
    context: dict = None
    language: str = 'en'

@app.post("/chat")
async def ask_question(request: QueryRequest):
    response = llm.get_response(
        query=request.message,
        bill_context=request.context,
        language=request.language
    )
    return {"response": response}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)