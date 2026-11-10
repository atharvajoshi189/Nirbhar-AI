import os
import uuid
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

QUOTE_HMAC_SECRET = os.getenv("QUOTE_HMAC_SECRET", "nirbhar_sandbox_quote_hmac_secret_2026_x89a")

app = FastAPI(
    title="Nirbhar AI Vendor Gateway",
    version="0.2.0",
    description="Dedicated sandboxed merchant bridge generating cryptographically signed quotes and simulating PayPal Sandbox payees"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Three Sandbox Merchants mapping to distinct PayPal Sandbox Business Payee Accounts
MERCHANTS: Dict[str, Dict[str, Any]] = {
    "merch_cloudscale": {
        "id": "merch_cloudscale",
        "name": "CloudScale Infrastructure Solutions",
        "payee_email": "sb-cloudscale@business.example.com",
        "categories": ["cloud_compute", "web_hosting", "data_storage", "api_credits", "infrastructure", "compute"],
        "base_rates": {
            "cloud_compute": 12.0,
            "web_hosting": 8.0,
            "data_storage": 5.0,
            "api_credits": 10.0,
            "default": 10.0
        }
    },
    "merch_apexresearch": {
        "id": "merch_apexresearch",
        "name": "Apex Global Market Intelligence",
        "payee_email": "sb-apexresearch@business.example.com",
        "categories": ["market_research", "competitor_analysis", "data_enrichment", "consulting", "research", "reports"],
        "base_rates": {
            "market_research": 14.50,
            "competitor_analysis": 15.00,
            "data_enrichment": 9.50,
            "consulting": 18.00,
            "default": 13.00
        }
    },
    "merch_cybershield": {
        "id": "merch_cybershield",
        "name": "CyberShield SecOps & Domain Registry",
        "payee_email": "sb-cybershield@business.example.com",
        "categories": ["domain_registration", "security", "ssl_certs", "penetration_testing", "audit"],
        "base_rates": {
            "domain_registration": 7.50,
            "security": 16.00,
            "ssl_certs": 6.50,
            "penetration_testing": 19.00,
            "default": 12.00
        }
    }
}

class QuoteRequest(BaseModel):
    task_id: str = Field(description="Associated Nirbhar AI task UUID")
    service_category: str = Field(description="Target category (e.g. competitor_analysis, cloud_compute, domain_registration)")
    service_name: str = Field(description="Name or description of service to quote")
    scope_details: str = Field(min_length=3, description="Scope description used to dynamically compute service effort")
    tier: str = Field(default="standard", description="basic, standard, or premium tier")
    units: int = Field(default=1, ge=1, description="Number of units or seats requested")
    merchant_hint: Optional[str] = Field(default=None, description="Optional merchant id or name hint")

class PricingBreakdown(BaseModel):
    base_rate: float
    tier_multiplier: float
    scope_complexity_factor: float
    units: int
    raw_subtotal: float

class QuoteResponse(BaseModel):
    quote_id: str
    merchant_id: str
    merchant_name: str
    payee_email: str
    service_category: str
    service_name: str
    amount: float
    currency: str
    pricing_breakdown: PricingBreakdown
    created_at: str
    expires_at: str
    hmac_signature: str

class VerifyQuoteRequest(BaseModel):
    quote_id: str
    merchant_id: str
    payee_email: str
    amount: float
    currency: str
    expires_at: str
    hmac_signature: str

def compute_quote_signature(
    quote_id: str,
    merchant_id: str,
    payee_email: str,
    amount: float,
    currency: str,
    expires_at: str
) -> str:
    """Computes HMAC-SHA256 signature for canonical quote fields."""
    canonical = f"{quote_id}:{merchant_id}:{payee_email}:{amount:.2f}:{currency.upper()}:{expires_at}"
    return hmac.new(QUOTE_HMAC_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

def select_merchant(category: str, hint: Optional[str] = None) -> Dict[str, Any]:
    """Selects the best matching sandbox merchant based on category or hint."""
    clean_cat = category.lower().strip()
    clean_hint = (hint or "").lower().strip()

    if clean_hint:
        for m_id, m in MERCHANTS.items():
            if clean_hint in m_id.lower() or clean_hint in m["name"].lower():
                return m

    # Match by category
    for m in MERCHANTS.values():
        if any(cat in clean_cat or clean_cat in cat for cat in m["categories"]):
            return m

    # Default to Apex Research for research tasks, otherwise CloudScale
    if "research" in clean_cat or "analysis" in clean_cat or "report" in clean_cat:
        return MERCHANTS["merch_apexresearch"]
    return MERCHANTS["merch_cloudscale"]

@app.get("/")
async def root():
    return {
        "service": "Nirbhar AI Vendor Gateway",
        "status": "ready",
        "environment": os.getenv("PAYPAL_ENVIRONMENT", "sandbox"),
        "merchants_count": len(MERCHANTS)
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "vendor-gateway",
        "merchants": [m["name"] for m in MERCHANTS.values()]
    }

@app.get("/merchants")
async def list_merchants():
    """Returns available sandbox merchants and their supported categories."""
    return [
        {
            "id": m["id"],
            "name": m["name"],
            "payee_email": m["payee_email"],
            "categories": m["categories"]
        }
        for m in MERCHANTS.values()
    ]

@app.post("/quote", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def generate_quote(req: QuoteRequest):
    """
    Computes a dynamic quote from request parameters for one of the three sandbox merchants.
    Sets a strict 10-minute expiry and cryptographically signs it with HMAC-SHA256.
    Rule 1 (No Simulation): Dynamically computed based on scope, units, tier, and category.
    """
    merchant = select_merchant(category=req.service_category, hint=req.merchant_hint)

    # 1. Base rate resolution
    cat_rates = merchant.get("base_rates", {})
    base_rate = float(cat_rates.get(req.service_category.lower(), cat_rates.get("default", 12.0)))

    # 2. Tier multiplier
    tier_multipliers = {
        "basic": 0.85,
        "standard": 1.0,
        "premium": 1.45
    }
    tier_mult = tier_multipliers.get(req.tier.lower(), 1.0)

    # 3. Dynamic scope complexity factor (computed from scope text length and words)
    words_count = len(req.scope_details.split())
    scope_factor = round(1.0 + min(words_count / 40.0, 0.45), 2)

    # 4. Final price computation
    raw_subtotal = base_rate * tier_mult * scope_factor * req.units
    final_amount = round(raw_subtotal, 2)

    # 5. 10-minute expiry
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)

    quote_id = f"QTE-{uuid.uuid4().hex[:12].upper()}"
    created_at_iso = now.isoformat()
    expires_at_iso = expires_at.isoformat()

    # 6. HMAC-SHA256 signature
    hmac_sig = compute_quote_signature(
        quote_id=quote_id,
        merchant_id=merchant["id"],
        payee_email=merchant["payee_email"],
        amount=final_amount,
        currency="USD",
        expires_at=expires_at_iso
    )

    return QuoteResponse(
        quote_id=quote_id,
        merchant_id=merchant["id"],
        merchant_name=merchant["name"],
        payee_email=merchant["payee_email"],
        service_category=req.service_category,
        service_name=req.service_name,
        amount=final_amount,
        currency="USD",
        pricing_breakdown=PricingBreakdown(
            base_rate=base_rate,
            tier_multiplier=tier_mult,
            scope_complexity_factor=scope_factor,
            units=req.units,
            raw_subtotal=round(raw_subtotal, 2)
        ),
        created_at=created_at_iso,
        expires_at=expires_at_iso,
        hmac_signature=hmac_sig
    )

@app.post("/quote/verify")
async def verify_quote(req: VerifyQuoteRequest):
    """
    Verifies that a quote was legitimately generated by the Vendor Gateway
    and has not expired or been tampered with.
    """
    # 1. Check expiration
    try:
        exp_dt = datetime.fromisoformat(req.expires_at)
        if datetime.now(timezone.utc) > exp_dt:
            raise HTTPException(
                status_code=400,
                detail=f"Quote {req.quote_id} expired at {req.expires_at}. Maximum validity is 10 minutes."
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Invalid expires_at timestamp: {e}")

    # 2. Check HMAC signature
    expected_sig = compute_quote_signature(
        quote_id=req.quote_id,
        merchant_id=req.merchant_id,
        payee_email=req.payee_email,
        amount=req.amount,
        currency=req.currency,
        expires_at=req.expires_at
    )

    if not hmac.compare_digest(expected_sig, req.hmac_signature):
        raise HTTPException(
            status_code=403,
            detail="Quote HMAC signature verification failed. Quote has been altered or forged."
        )

    return {
        "valid": True,
        "quote_id": req.quote_id,
        "merchant_id": req.merchant_id,
        "payee_email": req.payee_email,
        "amount": req.amount,
        "currency": req.currency,
        "expires_at": req.expires_at,
        "verified_at": datetime.now(timezone.utc).isoformat()
    }
