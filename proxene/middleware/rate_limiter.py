"""Rate limiting middleware for Proxene"""

import time
from typing import Dict, Optional, Tuple
import redis.asyncio as redis
from datetime import datetime, timedelta
import logging
from fastapi import HTTPException
import hashlib

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter with sliding window algorithm"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis_client
        self.redis_url = redis_url
        
    async def connect(self):
        """Connect to Redis if not already connected"""
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            
    def _get_client_id(self, request_info: Dict) -> str:
        """Generate client identifier from request info"""
        # Use IP + User-Agent for basic identification
        # In production, you might want to use API keys or user IDs
        ip = request_info.get('client_ip', 'unknown')
        user_agent = request_info.get('user_agent', 'unknown')
        
        # Create hash for privacy
        client_data = f"{ip}:{user_agent}"
        return hashlib.sha256(client_data.encode()).hexdigest()[:16]
        
    async def check_rate_limit(
        self,
        client_info: Dict,
        rate_limits: Dict[str, int]
    ) -> Tuple[bool, Optional[str], Dict[str, int]]:
        """
        Check if request is within rate limits
        
        Args:
            client_info: Dictionary with client IP, user agent, etc.
            rate_limits: Dictionary with rate limit configuration
            
        Returns:
            Tuple of (allowed, reason, remaining_limits)
        """
        if not self.redis_client:
            await self.connect()
            
        client_id = self._get_client_id(client_info)
        current_time = int(time.time())
        
        # Check each rate limit type
        remaining_limits = {}
        
        for limit_type, limit_value in rate_limits.items():
            if limit_type == "requests_per_minute":
                window_size = 60
                key_suffix = "min"
            elif limit_type == "requests_per_hour":
                window_size = 3600
                key_suffix = "hour" 
            elif limit_type == "requests_per_day":
                window_size = 86400
                key_suffix = "day"
            else:
                continue
                
            # Check this specific limit
            allowed, remaining = await self._check_sliding_window(
                client_id, key_suffix, window_size, limit_value, current_time
            )
            
            remaining_limits[limit_type] = remaining
            
            if not allowed:
                return False, f"Rate limit exceeded: {limit_type} ({limit_value} requests per {key_suffix})", remaining_limits
                
        return True, None, remaining_limits
        
    async def _check_sliding_window(
        self,
        client_id: str,
        window_type: str,
        window_size: int,
        limit: int,
        current_time: int
    ) -> Tuple[bool, int]:
        """
        Check sliding window rate limit for a specific time window
        
        Returns:
            Tuple of (allowed, remaining_requests)
        """
        key = f"proxene:ratelimit:{client_id}:{window_type}"
        
        try:
            # Use Lua script for atomic sliding window check
            lua_script = """
            local key = KEYS[1]
            local window_size = tonumber(ARGV[1])
            local limit = tonumber(ARGV[2]) 
            local current_time = tonumber(ARGV[3])
            local expire_time = current_time + window_size
            
            -- Remove expired entries
            redis.call('ZREMRANGEBYSCORE', key, 0, current_time - window_size)
            
            -- Count current requests
            local current_count = redis.call('ZCARD', key)
            
            if current_count < limit then
                -- Add current request
                redis.call('ZADD', key, current_time, current_time)
                redis.call('EXPIRE', key, window_size)
                return {1, limit - current_count - 1}
            else
                return {0, 0}
            end
            """
            
            result = await self.redis_client.eval(
                lua_script,
                1,  # Number of keys
                key,
                window_size,
                limit,
                current_time
            )
            
            allowed = bool(result[0])
            remaining = int(result[1])
            
            return allowed, remaining
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request if Redis fails
            return True, limit
            
    async def get_rate_limit_status(self, client_info: Dict, rate_limits: Dict[str, int]) -> Dict[str, Dict]:
        """Get current rate limit status for a client"""
        if not self.redis_client:
            await self.connect()
            
        client_id = self._get_client_id(client_info)
        current_time = int(time.time())
        
        status = {}
        
        for limit_type, limit_value in rate_limits.items():
            if limit_type == "requests_per_minute":
                window_size = 60
                key_suffix = "min"
            elif limit_type == "requests_per_hour":
                window_size = 3600
                key_suffix = "hour"
            elif limit_type == "requests_per_day":
                window_size = 86400
                key_suffix = "day"
            else:
                continue
                
            key = f"proxene:ratelimit:{client_id}:{key_suffix}"
            
            try:
                # Get current count
                await self.redis_client.zremrangebyscore(
                    key, 0, current_time - window_size
                )
                current_count = await self.redis_client.zcard(key)
                
                status[limit_type] = {
                    "limit": limit_value,
                    "used": current_count,
                    "remaining": max(0, limit_value - current_count),
                    "reset_time": current_time + window_size
                }
                
            except Exception as e:
                logger.error(f"Error getting rate limit status: {e}")
                status[limit_type] = {
                    "limit": limit_value,
                    "used": 0,
                    "remaining": limit_value,
                    "reset_time": current_time + window_size
                }
                
        return status
        
    async def reset_rate_limits(self, client_info: Dict):
        """Reset rate limits for a client (admin function)"""
        if not self.redis_client:
            await self.connect()
            
        client_id = self._get_client_id(client_info)
        
        # Delete all rate limit keys for this client
        pattern = f"proxene:ratelimit:{client_id}:*"
        async for key in self.redis_client.scan_iter(match=pattern):
            await self.redis_client.delete(key)
            
        logger.info(f"Reset rate limits for client {client_id}")


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting"""
    
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
        
    async def __call__(self, request, call_next):
        """Process request with rate limiting"""
        # Extract client information
        client_info = {
            'client_ip': request.client.host if request.client else 'unknown',
            'user_agent': request.headers.get('user-agent', 'unknown')
        }
        
        # Get rate limits from request state (set by policy middleware)
        rate_limits = getattr(request.state, 'rate_limits', {})
        
        if rate_limits:
            # Check rate limits
            allowed, reason, remaining = await self.rate_limiter.check_rate_limit(
                client_info, rate_limits
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=reason,
                    headers={
                        "X-RateLimit-Remaining": str(min(remaining.values()) if remaining else 0),
                        "X-RateLimit-Reset": str(int(time.time()) + 60),
                        "Retry-After": "60"
                    }
                )
                
            # Add rate limit headers to response
            response = await call_next(request)
            
            if remaining:
                for limit_type, remaining_count in remaining.items():
                    header_name = f"X-RateLimit-{limit_type.replace('_', '-')}"
                    response.headers[header_name] = str(remaining_count)
                    
            return response
        else:
            # No rate limits configured, proceed normally
            return await call_next(request)


# Global rate limiter instance
rate_limiter = RateLimiter()