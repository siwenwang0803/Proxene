"""Core proxy functionality for forwarding LLM requests"""

from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import json
import logging
import redis.asyncio as redis

from proxene.core.cache import CacheService
from proxene.guards.cost_guard import CostGuard
from proxene.policies.loader import PolicyLoader

logger = logging.getLogger(__name__)

app = FastAPI(title="Proxene AI Governance Proxy", version="0.1.0")


class ProxyService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.cache_service = CacheService()
        self.redis_client: Optional[redis.Redis] = None
        self.cost_guard: Optional[CostGuard] = None
        self.policy_loader = PolicyLoader()
        
    async def initialize(self):
        """Initialize services"""
        try:
            # Connect to Redis
            await self.cache_service.connect()
            self.redis_client = self.cache_service.client
            
            # Initialize cost guard with Redis
            self.cost_guard = CostGuard(self.redis_client)
            
            # Load policies
            self.policy_loader.load_policies()
            
            logger.info("Proxy services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            # Continue without Redis if it fails
            self.cost_guard = CostGuard()
            
    async def shutdown(self):
        """Shutdown services"""
        await self.cache_service.disconnect()
        await self.client.aclose()
        
    async def process_chat_completion(
        self, 
        request_data: Dict[str, Any],
        headers: Dict[str, str],
        policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process chat completion request with governance"""
        
        # 1. Check cost limits
        if self.cost_guard and policy.get("cost_limits"):
            allowed, reason = await self.cost_guard.check_cost_limits(
                request_data, 
                policy["cost_limits"]
            )
            if not allowed:
                raise HTTPException(status_code=429, detail=reason)
                
        # 2. Check cache
        if policy.get("caching", {}).get("enabled", True):
            cached_response = await self.cache_service.get(request_data)
            if cached_response:
                # Add cache hit header
                cached_response["_proxene_cache_hit"] = True
                return cached_response
                
        # 3. Forward request
        response = await self._forward_llm_request(request_data, headers)
        
        # 4. Track costs
        if self.cost_guard and response.get("usage"):
            model = request_data.get("model", "gpt-3.5-turbo")
            usage = response["usage"]
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            
            cost = self.cost_guard.calculate_cost(model, input_tokens, output_tokens)
            
            await self.cost_guard.track_request_cost(
                model, input_tokens, output_tokens, cost
            )
            
            # Add cost to response metadata
            response["_proxene_cost"] = cost
            
        # 5. Cache response
        if policy.get("caching", {}).get("enabled", True):
            ttl = policy.get("caching", {}).get("ttl_seconds", 3600)
            await self.cache_service.set(request_data, response, ttl)
            
        return response
        
    async def _forward_llm_request(
        self,
        request_data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Forward request to LLM provider"""
        url = "https://api.openai.com/v1/chat/completions"
        
        # Remove host header
        headers = dict(headers)
        headers.pop("host", None)
        
        response = await self.client.post(
            url,
            json=request_data,
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )
            
        return response.json()
        
    async def forward_request(
        self, 
        path: str, 
        request: Request,
        target_base_url: str = "https://api.openai.com"
    ) -> Response:
        """Forward request to target LLM provider"""
        try:
            # Build target URL
            url = f"{target_base_url}{path}"
            
            # Get request body
            body = await request.body()
            
            # Forward headers (excluding host)
            headers = dict(request.headers)
            headers.pop("host", None)
            
            # Make request
            response = await self.client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=dict(request.query_params)
            )
            
            # Return response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {str(e)}")


# Create global proxy service
proxy_service = ProxyService()


@app.on_event("startup")
async def startup():
    await proxy_service.initialize()
    logger.info("Proxene proxy started")


@app.on_event("shutdown")
async def shutdown():
    await proxy_service.shutdown()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/stats")
async def get_stats():
    """Get proxy statistics"""
    if not proxy_service.redis_client:
        return {"error": "Redis not connected"}
        
    # TODO: Implement stats collection
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Handle chat completion requests with governance"""
    try:
        # Parse request
        request_data = await request.json()
        
        # Get active policy
        policy = proxy_service.policy_loader.get_active_policy()
        
        # Process with governance
        response = await proxy_service.process_chat_completion(
            request_data,
            dict(request.headers),
            policy
        )
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_endpoint(path: str, request: Request):
    """Main proxy endpoint - forwards all other requests"""
    
    # Skip chat completions (handled separately)
    if path == "v1/chat/completions":
        return await chat_completions(request)
    
    # Log request
    logger.info(f"Proxying request: {request.method} /{path}")
    
    # Forward request
    response = await proxy_service.forward_request(f"/{path}", request)
    
    return response