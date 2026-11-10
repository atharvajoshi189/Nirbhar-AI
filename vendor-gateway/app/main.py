import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Nirbhar AI Vendor Gateway",
    version="0.1.0",
    description="Dedicated sandboxed payment gateway executing PayPal Sandbox orders"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "service": "Nirbhar AI Vendor Gateway",
        "status": "ready",
        "environment": os.getenv("PAYPAL_ENVIRONMENT", "sandbox")
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "vendor-gateway"
    }

