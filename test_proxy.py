#!/usr/bin/env python
"""Test script to verify proxy functionality"""

import httpx
import json
import os

def test_proxy():
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        return
    
    # Test request
    url = "http://localhost:8080/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Say 'Hello from Proxene!' and nothing else"}
        ],
        "max_tokens": 20
    }
    
    try:
        response = httpx.post(url, headers=headers, json=data)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result['choices'][0]['message']['content']}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        print("Make sure the proxy is running on http://localhost:8080")

if __name__ == "__main__":
    test_proxy()