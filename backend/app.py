import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llm_service import UtilityBillLLM
import uvicorn
import json
from data.firebase_service import get_db_reference
from data.upload_invoices import upload_invoices_once
from config import ensure_config

ensure_config()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = UtilityBillLLM()

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