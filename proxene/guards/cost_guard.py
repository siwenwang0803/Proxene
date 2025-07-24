"""Cost tracking and limiting for LLM requests"""

import tiktoken
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import redis.asyncio as redis
import json
import logging

logger = logging.getLogger(__name__)

# Model pricing per 1K tokens (in USD)
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    
    # Claude
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-2.1": {"input": 0.008, "output": 0.024},
    "claude-2": {"input": 0.008, "output": 0.024},
}


class CostGuard:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.encodings = {}  # Cache tokenizer encodings
        
    def _get_encoding(self, model: str):
        """Get or create encoding for model"""
        if model not in self.encodings:
            try:
                # Map model to encoding
                if "gpt-4" in model:
                    encoding_name = "cl100k_base"
                elif "gpt-3.5" in model:
                    encoding_name = "cl100k_base"
                else:
                    # Default to cl100k_base for unknown models
                    encoding_name = "cl100k_base"
                    
                self.encodings[model] = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.error(f"Failed to get encoding for {model}: {e}")
                # Fallback to cl100k_base
                self.encodings[model] = tiktoken.get_encoding("cl100k_base")
                
        return self.encodings[model]
        
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text for given model"""
        try:
            encoding = self._get_encoding(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.error(f"Token counting error: {e}")
            # Rough estimate: ~4 chars per token
            return len(text) // 4
            
    def estimate_request_tokens(self, request_data: Dict[str, Any]) -> int:
        """Estimate tokens for a chat completion request"""
        model = request_data.get("model", "gpt-3.5-turbo")
        messages = request_data.get("messages", [])
        
        total_tokens = 0
        
        # Count tokens in messages
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")
            
            # Add tokens for role and message structure
            total_tokens += 4  # Approximate overhead per message
            total_tokens += self.count_tokens(role, model)
            total_tokens += self.count_tokens(content, model)
            
        # Add tokens for other parameters
        if "system" in request_data:
            total_tokens += self.count_tokens(request_data["system"], model)
            
        return total_tokens
        
    def count_response_tokens(self, response_data: Dict[str, Any]) -> int:
        """Count tokens in response"""
        # If usage data is provided, use it
        if "usage" in response_data:
            return response_data["usage"].get("completion_tokens", 0)
            
        # Otherwise estimate from content
        model = response_data.get("model", "gpt-3.5-turbo")
        total_tokens = 0
        
        for choice in response_data.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content", "")
            total_tokens += self.count_tokens(content, model)
            
        return total_tokens
        
    def calculate_cost(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> float:
        """Calculate cost for tokens"""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-3.5-turbo"])
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)
        
    async def check_cost_limits(
        self,
        request_data: Dict[str, Any],
        cost_limits: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """Check if request would exceed cost limits"""
        if not cost_limits:
            return True, None
            
        model = request_data.get("model", "gpt-3.5-turbo")
        
        # Estimate request cost
        input_tokens = self.estimate_request_tokens(request_data)
        # Estimate output tokens (use max_tokens if provided)
        output_tokens = request_data.get("max_tokens", 500)
        
        estimated_cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        # Check per-request limit
        if "max_per_request" in cost_limits:
            if estimated_cost > cost_limits["max_per_request"]:
                return False, f"Estimated cost ${estimated_cost:.4f} exceeds per-request limit ${cost_limits['max_per_request']}"
                
        # Check daily limit
        if "daily_cap" in cost_limits and self.redis_client:
            daily_cost = await self._get_daily_cost()
            if daily_cost + estimated_cost > cost_limits["daily_cap"]:
                return False, f"Would exceed daily cap ${cost_limits['daily_cap']} (current: ${daily_cost:.2f})"
                
        return True, None
        
    async def track_request_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float
    ):
        """Track cost in Redis"""
        if not self.redis_client:
            return
            
        try:
            # Track daily cost
            today = datetime.now().strftime("%Y-%m-%d")
            daily_key = f"proxene:cost:daily:{today}"
            
            await self.redis_client.incrbyfloat(daily_key, cost)
            await self.redis_client.expire(daily_key, timedelta(days=7))
            
            # Track per-model stats
            model_key = f"proxene:cost:model:{model}:{today}"
            model_data = {
                "requests": 1,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost
            }
            
            # Increment counters
            await self.redis_client.hincrby(model_key, "requests", 1)
            await self.redis_client.hincrbyfloat(model_key, "input_tokens", input_tokens)
            await self.redis_client.hincrbyfloat(model_key, "output_tokens", output_tokens)
            await self.redis_client.hincrbyfloat(model_key, "cost", cost)
            await self.redis_client.expire(model_key, timedelta(days=7))
            
            logger.info(f"Tracked cost: ${cost:.4f} for {model} ({input_tokens} in, {output_tokens} out)")
            
        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            
    async def _get_daily_cost(self) -> float:
        """Get today's total cost"""
        if not self.redis_client:
            return 0.0
            
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            daily_key = f"proxene:cost:daily:{today}"
            
            cost = await self.redis_client.get(daily_key)
            return float(cost) if cost else 0.0
            
        except Exception as e:
            logger.error(f"Failed to get daily cost: {e}")
            return 0.0