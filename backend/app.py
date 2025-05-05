import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llm_service import UtilityBillLLM
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = UtilityBillLLM()

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