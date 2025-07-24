"""Redis caching for LLM responses"""

import json
import hashlib
from typing import Optional, Dict, Any
import redis.asyncio as redis
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, redis_url: str = None):
        import os
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Connect to Redis"""
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        await self.client.ping()
        logger.info("Connected to Redis")
        
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            
    def _generate_cache_key(self, request_data: Dict[str, Any]) -> str:
        """Generate cache key from request data"""
        # Create deterministic key from request
        key_data = {
            "model": request_data.get("model"),
            "messages": request_data.get("messages"),
            "temperature": request_data.get("temperature", 1.0),
            "max_tokens": request_data.get("max_tokens"),
            "top_p": request_data.get("top_p", 1.0),
        }
        
        # Hash the request data
        key_str = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()
        
        return f"proxene:cache:{key_hash}"
        
    async def get(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached response if exists"""
        if not self.client:
            return None
            
        try:
            key = self._generate_cache_key(request_data)
            cached = await self.client.get(key)
            
            if cached:
                logger.info(f"Cache hit for key: {key[:16]}...")
                return json.loads(cached)
                
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
            
    async def set(
        self, 
        request_data: Dict[str, Any], 
        response_data: Dict[str, Any],
        ttl_seconds: int = 3600
    ):
        """Cache response with TTL"""
        if not self.client:
            return
            
        try:
            key = self._generate_cache_key(request_data)
            value = json.dumps(response_data)
            
            await self.client.setex(
                key,
                timedelta(seconds=ttl_seconds),
                value
            )
            
            logger.info(f"Cached response for key: {key[:16]}... (TTL: {ttl_seconds}s)")
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        if not self.client:
            return
            
        try:
            async for key in self.client.scan_iter(match=f"proxene:cache:{pattern}"):
                await self.client.delete(key)
                
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")