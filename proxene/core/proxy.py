"""Core proxy functionality for forwarding LLM requests"""

from typing import Dict, Any
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
import json
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Proxene AI Governance Proxy", version="0.1.0")


class ProxyService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        
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
    logger.info("Proxene proxy started")


@app.on_event("shutdown")
async def shutdown():
    await proxy_service.client.aclose()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_endpoint(path: str, request: Request):
    """Main proxy endpoint - forwards all requests to OpenAI by default"""
    
    # Log request
    logger.info(f"Proxying request: {request.method} /{path}")
    
    # Forward request
    response = await proxy_service.forward_request(f"/{path}", request)
    
    return response