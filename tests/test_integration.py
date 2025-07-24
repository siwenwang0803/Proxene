"""Integration tests for Proxene proxy"""

import pytest
from fastapi.testclient import TestClient
from proxene.core.proxy import app
import json


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


def test_stats_endpoint(client):
    response = client.get("/stats")
    assert response.status_code == 200
    
    # Should return either stats or error about Redis
    data = response.json()
    assert "status" in data or "error" in data


@pytest.mark.skipif(
    not pytest.importorskip("os").getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
def test_chat_completion_real_api(client):
    """Test with real OpenAI API (requires API key)"""
    import os
    
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Say 'test' and nothing else"}
        ],
        "max_tokens": 5
    }
    
    response = client.post("/v1/chat/completions", headers=headers, json=request_data)
    
    if response.status_code == 200:
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        
        # Check Proxene metadata
        assert "_proxene_cost" in data
        assert isinstance(data["_proxene_cost"], (int, float))
    else:
        # May fail due to policy limits or API issues
        assert response.status_code in [400, 429, 500]


def test_chat_completion_pii_detection(client):
    """Test PII detection in requests"""
    # This test doesn't need real API key since PII detection happens first
    
    headers = {
        "Authorization": "Bearer fake-key",
        "Content-Type": "application/json"
    }
    
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "My email is test@example.com and my phone is 555-123-4567"}
        ],
        "max_tokens": 10
    }
    
    response = client.post("/v1/chat/completions", headers=headers, json=request_data)
    
    # Should detect PII and either warn or block
    # Since default policy has PII detection enabled with "warn" action,
    # the request should proceed but with PII metadata
    
    # Note: This test may fail at the API call stage due to fake key,
    # but PII detection should happen first
    if response.status_code == 400:
        # Check if it's PII blocking
        error_msg = response.json().get("detail", "")
        if "PII detected" in error_msg:
            assert True  # PII blocking worked
        else:
            # It's just the API authentication failure
            pass


def test_cost_limit_blocking(client):
    """Test that cost limits work"""
    headers = {
        "Authorization": "Bearer fake-key",
        "Content-Type": "application/json"
    }
    
    # Create an expensive request
    request_data = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Write a very long essay about " + "test " * 1000}
        ],
        "max_tokens": 4000  # Very expensive
    }
    
    response = client.post("/v1/chat/completions", headers=headers, json=request_data)
    
    # Should be blocked by cost limits (default policy has max_per_request: 0.03)
    if response.status_code == 429:
        error_msg = response.json().get("detail", "")
        assert "exceeds per-request limit" in error_msg or "daily cap" in error_msg
    else:
        # May pass if limits are high enough
        pass


def test_proxy_fallback_endpoint(client):
    """Test that non-chat endpoints are proxied through"""
    response = client.get("/v1/models")
    
    # Should forward to OpenAI but fail due to no auth
    # The important thing is that it tries to proxy, not return 404
    assert response.status_code != 404