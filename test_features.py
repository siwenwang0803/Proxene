#!/usr/bin/env python
"""Test script to verify all Proxene features"""

import httpx
import json
import os
import time
import asyncio

async def test_features():
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Please set OPENAI_API_KEY environment variable")
        return
    
    base_url = "http://localhost:8081"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("🧪 Testing Proxene Features\n")
    
    # 1. Health check
    print("1️⃣  Health Check")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("   ✅ Proxy is healthy")
            else:
                print(f"   ❌ Health check failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Cannot connect to proxy: {e}")
            return
    
    # 2. Basic request
    print("\n2️⃣  Basic Request")
    test_request = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Say 'Hello from Proxene!' and nothing else"}
        ],
        "max_tokens": 20,
        "temperature": 0.1
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=test_request
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            cost = result.get('_proxene_cost', 0)
            print(f"   ✅ Response: {content}")
            print(f"   💰 Cost: ${cost:.6f}")
            
            # Save request for CLI testing
            with open('logs/test_request.json', 'w') as f:
                json.dump(test_request, f, indent=2)
        else:
            print(f"   ❌ Request failed: {response.status_code} - {response.text}")
    
    # 3. Cache test
    print("\n3️⃣  Cache Test")
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        # First request
        response1 = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=test_request
        )
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=test_request
        )
        time2 = time.time() - start_time
        
        if response2.status_code == 200:
            result = response2.json()
            if result.get('_proxene_cache_hit'):
                print(f"   ✅ Cache hit! First: {time1:.2f}s, Cached: {time2:.2f}s")
            else:
                print(f"   ⚠️  Cache miss (Redis might not be running)")
        else:
            print(f"   ❌ Cache test failed")
    
    # 4. PII Detection Test
    print("\n4️⃣  PII Detection Test")
    pii_request = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "My email is john.doe@example.com and my phone is 555-123-4567"}
        ],
        "max_tokens": 50
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=pii_request
        )
        
        if response.status_code == 200:
            result = response.json()
            if "_proxene_pii" in result:
                pii_data = result["_proxene_pii"]
                req_findings = len(pii_data.get("request_findings", []))
                resp_findings = len(pii_data.get("response_findings", []))
                print(f"   ✅ PII detected: {req_findings} in request, {resp_findings} in response")
            else:
                print("   ⚠️  No PII metadata (detection might be disabled)")
        elif response.status_code == 400 and "PII detected" in str(response.json()):
            print(f"   ✅ PII blocking working: {response.json()['detail']}")
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")

    # 5. Cost limit test
    print("\n5️⃣  Cost Limit Test") 
    expensive_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Test " * 1000}  # Long prompt
        ],
        "max_tokens": 2000
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=expensive_request
        )
        
        if response.status_code == 429:
            print(f"   ✅ Cost limit working: {response.json()['detail']}")
        elif response.status_code == 200:
            print("   ⚠️  Request succeeded (cost limits might be high)")
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")
    
    # 6. Stats endpoint
    print("\n6️⃣  Stats Endpoint")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/stats")
        if response.status_code == 200:
            print(f"   ✅ Stats available: {response.json()}")
        else:
            print(f"   ❌ Stats failed: {response.status_code}")
    
    print("\n✨ Testing complete!")
    print("\nNext steps:")
    print("  - Check logs/test_request.json")
    print("  - Run: proxene replay logs/test_request.json")
    print("  - View policies in policies/default.yaml")

if __name__ == "__main__":
    asyncio.run(test_features())