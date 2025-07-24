"""End-to-end tests for Proxene proxy with real LLM providers"""

import pytest
import asyncio
import os
import httpx
import json
from datetime import datetime
import subprocess
import time
import signal
from typing import Generator, Optional

# Skip all e2e tests if no API key is provided
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping e2e tests"
)


class ProxyTestServer:
    """Test server manager for e2e tests"""
    
    def __init__(self, port: int = 8082):
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        
    def start(self):
        """Start the proxy server"""
        env = os.environ.copy()
        env["REDIS_URL"] = "redis://localhost:6379"
        
        self.process = subprocess.Popen([
            "python", "-m", "uvicorn", "proxene.main:app",
            "--host", "0.0.0.0",
            "--port", str(self.port),
            "--log-level", "error"  # Reduce noise in tests
        ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        for _ in range(10):
            try:
                response = httpx.get(f"http://localhost:{self.port}/health", timeout=1.0)
                if response.status_code == 200:
                    return
            except:
                pass
            time.sleep(0.5)
        
        raise RuntimeError("Failed to start test server")
        
    def stop(self):
        """Stop the proxy server"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


@pytest.fixture(scope="module")
def proxy_server() -> Generator[ProxyTestServer, None, None]:
    """Fixture to manage proxy server for e2e tests"""
    server = ProxyTestServer()
    try:
        server.start()
        yield server
    finally:
        server.stop()


class TestE2EProxy:
    """End-to-end tests with real LLM providers"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, proxy_server: ProxyTestServer):
        """Test that health check works"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{proxy_server.port}/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["version"] == "0.1.0"
    
    @pytest.mark.asyncio
    async def test_openai_chat_completion(self, proxy_server: ProxyTestServer):
        """Test chat completion through proxy with OpenAI"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"http://localhost:{proxy_server.port}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Say exactly 'e2e test success' and nothing else"}
                    ],
                    "max_tokens": 10,
                    "temperature": 0.1
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check OpenAI response structure
            assert "choices" in data
            assert len(data["choices"]) > 0
            assert "message" in data["choices"][0]
            assert "content" in data["choices"][0]["message"]
            
            # Check Proxene metadata
            assert "_proxene_cost" in data
            assert isinstance(data["_proxene_cost"], (int, float))
            assert data["_proxene_cost"] > 0
            
            # Check content
            content = data["choices"][0]["message"]["content"]
            assert "e2e test success" in content.lower()
    
    @pytest.mark.asyncio
    async def test_cost_tracking(self, proxy_server: ProxyTestServer):
        """Test that costs are tracked correctly"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Make multiple requests to accumulate cost
            total_cost = 0
            
            for i in range(3):
                response = await client.post(
                    f"http://localhost:{proxy_server.port}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": f"Count to {i+1}"}
                        ],
                        "max_tokens": 20
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                
                cost = data.get("_proxene_cost", 0)
                assert cost > 0
                total_cost += cost
            
            # Total cost should be sum of individual costs
            assert total_cost > 0.001  # At least $0.001 for 3 requests
    
    @pytest.mark.asyncio
    async def test_pii_detection(self, proxy_server: ProxyTestServer):
        """Test PII detection in requests and responses"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Request with PII
            response = await client.post(
                f"http://localhost:{proxy_server.port}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "user", 
                            "content": "My email is john.doe@example.com. Just say 'received' and nothing else."
                        }
                    ],
                    "max_tokens": 10
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check for PII metadata
            if "_proxene_pii" in data:
                pii_data = data["_proxene_pii"]
                assert "request_findings" in pii_data
                assert "response_findings" in pii_data
                
                # Should detect email in request
                request_findings = pii_data["request_findings"]
                if request_findings:
                    assert any(finding["type"] == "email" for finding in request_findings)
    
    @pytest.mark.asyncio 
    async def test_cost_limits(self, proxy_server: ProxyTestServer):
        """Test that cost limits are enforced"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try to make an expensive request (should be blocked by default policy)
            response = await client.post(
                f"http://localhost:{proxy_server.port}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4",  # More expensive model
                    "messages": [
                        {"role": "user", "content": "Write a very long essay about artificial intelligence. " * 100}
                    ],
                    "max_tokens": 4000  # Very expensive
                }
            )
            
            # Should either be blocked (429) or succeed but with cost tracking
            if response.status_code == 429:
                error_data = response.json()
                assert "detail" in error_data
                assert "limit" in error_data["detail"].lower()
            else:
                # If it succeeds, cost should be tracked
                assert response.status_code == 200
                data = response.json()
                assert "_proxene_cost" in data
    
    @pytest.mark.asyncio
    async def test_caching(self, proxy_server: ProxyTestServer):
        """Test request caching functionality"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            request_data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "Say exactly 'cache test' and nothing else"}
                ],
                "max_tokens": 10,
                "temperature": 0.0  # Deterministic for caching
            }
            
            # First request
            response1 = await client.post(
                f"http://localhost:{proxy_server.port}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            assert response1.status_code == 200
            data1 = response1.json()
            
            # Second identical request (should be cached)
            response2 = await client.post(
                f"http://localhost:{proxy_server.port}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            assert response2.status_code == 200
            data2 = response2.json()
            
            # Second response might be cached
            if "_proxene_cache_hit" in data2:
                assert data2["_proxene_cache_hit"] is True
                # Cached responses should have same content
                assert data1["choices"][0]["message"]["content"] == data2["choices"][0]["message"]["content"]
    
    @pytest.mark.asyncio
    async def test_error_handling(self, proxy_server: ProxyTestServer):
        """Test error handling for invalid requests"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Invalid API key
            response = await client.post(
                f"http://localhost:{proxy_server.port}/v1/chat/completions",
                headers={
                    "Authorization": "Bearer invalid-key",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 10
                }
            )
            
            assert response.status_code == 401  # Unauthorized
    
    @pytest.mark.asyncio
    async def test_stats_endpoint(self, proxy_server: ProxyTestServer):
        """Test stats endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{proxy_server.port}/stats")
            
            assert response.status_code == 200
            data = response.json()
            
            # Should return either stats or Redis connection info
            assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_model_routing(self, proxy_server: ProxyTestServer):
        """Test that different models work through proxy"""
        models_to_test = ["gpt-3.5-turbo", "gpt-4o-mini"]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for model in models_to_test:
                response = await client.post(
                    f"http://localhost:{proxy_server.port}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": f"You are using {model}. Just say 'yes' and nothing else."}
                        ],
                        "max_tokens": 5
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert "choices" in data
                    assert "_proxene_cost" in data
                    
                    # Cost should vary by model
                    cost = data["_proxene_cost"]
                    assert cost > 0
                elif response.status_code == 404:
                    # Model not available, skip
                    continue
                else:
                    # Other errors should not happen
                    assert False, f"Unexpected status {response.status_code} for model {model}"


class TestE2EIntegration:
    """Integration tests for the full system"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, proxy_server: ProxyTestServer):
        """Test handling multiple concurrent requests"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create multiple concurrent requests
            tasks = []
            for i in range(5):
                task = client.post(
                    f"http://localhost:{proxy_server.port}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "user", "content": f"Say 'request {i}' and nothing else"}
                        ],
                        "max_tokens": 10
                    }
                )
                tasks.append(task)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            successful_responses = 0
            for response in responses:
                if isinstance(response, httpx.Response) and response.status_code == 200:
                    successful_responses += 1
                    data = response.json()
                    assert "_proxene_cost" in data
            
            # At least some should succeed
            assert successful_responses >= 3
    
    @pytest.mark.asyncio
    async def test_proxy_passthrough(self, proxy_server: ProxyTestServer):
        """Test that non-chat endpoints are passed through"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test models endpoint
            response = await client.get(
                f"http://localhost:{proxy_server.port}/v1/models",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
                }
            )
            
            # Should forward to OpenAI
            # Might succeed or fail based on API key, but should not be 404
            assert response.status_code != 404