import time
import logging
from typing import Optional, Any
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("api.redis")

class RedisManager:
    """Manages Redis connection with in-memory fallback for rate-limiting & idempotency."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._fallback_cache: dict = {}
        self._fallback_ttls: dict = {}
        self._connected: bool = False

    async def get_client(self) -> Optional[aioredis.Redis]:
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                await self._redis.ping()
                self._connected = True
                logger.info("Connected to Redis at %s", settings.REDIS_URL)
            except Exception as e:
                logger.warning("Redis connection failed (%s); using in-memory store", e)
                self._redis = None
                self._connected = False
        return self._redis

    async def get(self, key: str) -> Optional[str]:
        client = await self.get_client()
        if client:
            try:
                return await client.get(key)
            except Exception:
                pass
        
        # Fallback
        now = time.time()
        if key in self._fallback_cache:
            if now < self._fallback_ttls.get(key, float("inf")):
                return self._fallback_cache[key]
            else:
                del self._fallback_cache[key]
                self._fallback_ttls.pop(key, None)
        return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        client = await self.get_client()
        if client:
            try:
                await client.set(key, value, ex=ex)
                return True
            except Exception:
                pass

        # Fallback
        self._fallback_cache[key] = value
        if ex:
            self._fallback_ttls[key] = time.time() + ex
        return True

    async def incr(self, key: str) -> int:
        client = await self.get_client()
        if client:
            try:
                return await client.incr(key)
            except Exception:
                pass

        # Fallback
        val = int(self._fallback_cache.get(key, 0)) + 1
        self._fallback_cache[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int) -> bool:
        client = await self.get_client()
        if client:
            try:
                return await client.expire(key, seconds)
            except Exception:
                pass

        # Fallback
        self._fallback_ttls[key] = time.time() + seconds
        return True

    async def is_healthy(self) -> bool:
        client = await self.get_client()
        if client:
            try:
                await client.ping()
                return True
            except Exception:
                return False
        return False

redis_manager = RedisManager()

