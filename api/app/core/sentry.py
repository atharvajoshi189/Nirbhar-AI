import os
import logging
from typing import Optional

logger = logging.getLogger("api.sentry")

def init_sentry(dsn: Optional[str] = None, environment: str = "development") -> bool:
    """
    Initializes Sentry error tracking and performance monitoring.
    Falls back gracefully if SENTRY_DSN is not configured.
    """
    sentry_dsn = dsn or os.getenv("SENTRY_DSN")
    if not sentry_dsn or sentry_dsn in ("your_sentry_dsn_here", "none", ""):
        logger.info("Sentry monitoring not configured (SENTRY_DSN unset). Continuing in standard logging mode.")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],
        )
        logger.info("Sentry initialized successfully for environment: %s", environment)
        return True
    except Exception as e:
        logger.warning("Failed to initialize Sentry: %s", e)
        return False

