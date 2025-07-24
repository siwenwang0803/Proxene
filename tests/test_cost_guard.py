"""Tests for cost guard functionality"""

import pytest
from proxene.guards.cost_guard import CostGuard, MODEL_PRICING


class TestCostGuard:
    
    def setup_method(self):
        self.guard = CostGuard()
    
    def test_count_tokens_basic(self):
        text = "Hello, how are you?"
        tokens = self.guard.count_tokens(text, "gpt-3.5-turbo")
        
        # Should be around 6-7 tokens
        assert 5 <= tokens <= 8
    
    def test_count_tokens_long_text(self):
        text = "This is a longer text " * 100
        tokens = self.guard.count_tokens(text, "gpt-4")
        
        # Rough estimate: ~5 tokens per repetition
        assert 400 <= tokens <= 600
    
    def test_estimate_request_tokens(self):
        request = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the weather today?"}
            ]
        }
        
        tokens = self.guard.estimate_request_tokens(request)
        
        # Should include both messages plus overhead
        assert tokens > 10
        assert tokens < 50
    
    def test_calculate_cost_gpt35(self):
        cost = self.guard.calculate_cost("gpt-3.5-turbo", 1000, 500)
        
        # 1000 input tokens * $0.0005/1k + 500 output tokens * $0.0015/1k
        expected = (1000 / 1000 * 0.0005) + (500 / 1000 * 0.0015)
        assert cost == round(expected, 6)
    
    def test_calculate_cost_gpt4(self):
        cost = self.guard.calculate_cost("gpt-4", 1000, 500)
        
        # Check against known pricing
        expected = (1000 / 1000 * MODEL_PRICING["gpt-4"]["input"]) + \
                  (500 / 1000 * MODEL_PRICING["gpt-4"]["output"])
        assert cost == round(expected, 6)
    
    def test_calculate_cost_unknown_model(self):
        # Should fall back to gpt-3.5-turbo pricing
        cost = self.guard.calculate_cost("unknown-model", 1000, 500)
        fallback_cost = self.guard.calculate_cost("gpt-3.5-turbo", 1000, 500)
        
        assert cost == fallback_cost
    
    @pytest.mark.asyncio
    async def test_check_cost_limits_under_limit(self):
        request = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }
        
        limits = {"max_per_request": 1.0}
        
        allowed, reason = await self.guard.check_cost_limits(request, limits)
        
        assert allowed is True
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_check_cost_limits_over_limit(self):
        request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Test " * 1000}],
            "max_tokens": 2000
        }
        
        limits = {"max_per_request": 0.01}
        
        allowed, reason = await self.guard.check_cost_limits(request, limits)
        
        assert allowed is False
        assert "exceeds per-request limit" in reason
    
    def test_count_response_tokens_with_usage(self):
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }
        
        tokens = self.guard.count_response_tokens(response)
        assert tokens == 50
    
    def test_count_response_tokens_from_content(self):
        response = {
            "model": "gpt-3.5-turbo",
            "choices": [{
                "message": {
                    "content": "This is a test response with several words."
                }
            }]
        }
        
        tokens = self.guard.count_response_tokens(response)
        assert tokens > 5
        assert tokens < 20
    
    def test_model_pricing_consistency(self):
        # Ensure all models have both input and output pricing
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing
            assert "output" in pricing
            assert isinstance(pricing["input"], (int, float))
            assert isinstance(pricing["output"], (int, float))
            assert pricing["input"] > 0
            assert pricing["output"] > 0