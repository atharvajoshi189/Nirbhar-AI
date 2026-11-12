import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "Nirbhar AI Core API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Gemini
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    _gemini_override: Optional[str] = None

    @property
    def active_gemini_key(self) -> Optional[str]:
        if self._gemini_override is not None:
            return self._gemini_override
        return self.GEMINI_API_KEY

    def kill_gemini_key(self):
        self._gemini_override = "AIzaSy_KILLED_INVALID_KEY_PHASE2"

    def restore_gemini_key(self):
        self._gemini_override = None
    
    # Supabase
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY: Optional[str] = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # PayPal Sandbox
    PAYPAL_CLIENT_ID: Optional[str] = os.getenv("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET: Optional[str] = os.getenv("PAYPAL_CLIENT_SECRET")
    PAYPAL_ENVIRONMENT: str = os.getenv("PAYPAL_ENVIRONMENT", "sandbox")
    PAYPAL_API_BASE: str = os.getenv("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com")
    PAYPAL_WEBHOOK_ID: Optional[str] = os.getenv("PAYPAL_WEBHOOK_ID")
    
    # External Services
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    VENDOR_GATEWAY_URL: str = os.getenv("VENDOR_GATEWAY_URL", "http://localhost:8001")
    QUOTE_HMAC_SECRET: str = os.getenv("QUOTE_HMAC_SECRET", "nirbhar_sandbox_quote_hmac_secret_2026_x89a")

    # Observability & Production Resilience (Phase 8)
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "1200"))
    IDEMPOTENCY_TTL_SECONDS: int = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
    ENABLE_STRUCTURED_LOGGING: bool = os.getenv("ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"

settings = Settings()
