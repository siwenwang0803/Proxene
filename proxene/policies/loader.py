"""YAML policy loader and manager"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class PolicyLoader:
    def __init__(self, policy_dir: str = "policies"):
        self.policy_dir = Path(policy_dir)
        self.policies: Dict[str, Any] = {}
        self.last_loaded: Optional[datetime] = None
        
    def load_policies(self) -> Dict[str, Any]:
        """Load all YAML policies from directory"""
        self.policies = {}
        
        # Create policy directory if it doesn't exist
        self.policy_dir.mkdir(exist_ok=True)
        
        # Load all YAML files
        for yaml_file in self.policy_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    policy_name = yaml_file.stem
                    policy_data = yaml.safe_load(f)
                    
                    if policy_data:
                        self.policies[policy_name] = policy_data
                        logger.info(f"Loaded policy: {policy_name}")
                        
            except Exception as e:
                logger.error(f"Failed to load policy {yaml_file}: {e}")
                
        self.last_loaded = datetime.now()
        
        # Create default policy if none exist
        if not self.policies and not (self.policy_dir / "default.yaml").exists():
            self._create_default_policy()
            self.load_policies()
            
        return self.policies
        
    def _create_default_policy(self):
        """Create default policy file"""
        default_policy = {
            "name": "Default Policy",
            "description": "Default governance policy for Proxene",
            "enabled": True,
            
            "cost_limits": {
                "max_per_request": 0.03,
                "max_per_minute": 1.0,
                "daily_cap": 100.0
            },
            
            "rate_limits": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "requests_per_day": 10000
            },
            
            "model_routing": [
                {
                    "condition": "request.max_tokens < 100",
                    "model": "gpt-3.5-turbo"
                },
                {
                    "condition": "default",
                    "model": "gpt-4o-mini"
                }
            ],
            
            "pii_detection": {
                "enabled": False,
                "action": "redact",
                "entities": ["email", "phone", "ssn", "credit_card"]
            },
            
            "caching": {
                "enabled": True,
                "ttl_seconds": 3600,
                "max_cache_size_mb": 100
            },
            
            "logging": {
                "log_requests": True,
                "log_responses": False,
                "log_costs": True
            }
        }
        
        # Write default policy
        default_path = self.policy_dir / "default.yaml"
        with open(default_path, 'w') as f:
            yaml.dump(default_policy, f, default_flow_style=False, sort_keys=False)
            
        logger.info(f"Created default policy at {default_path}")
        
    def get_active_policy(self, policy_name: Optional[str] = None) -> Dict[str, Any]:
        """Get active policy (default or specified)"""
        if not self.policies:
            self.load_policies()
            
        if policy_name and policy_name in self.policies:
            return self.policies[policy_name]
            
        # Return first enabled policy or default
        for name, policy in self.policies.items():
            if policy.get("enabled", True):
                return policy
                
        # Return default if exists
        if "default" in self.policies:
            return self.policies["default"]
            
        # Return empty policy as fallback
        return {}
        
    def reload_if_changed(self) -> bool:
        """Reload policies if files have changed"""
        # Check if any policy file has been modified
        if not self.last_loaded:
            self.load_policies()
            return True
            
        for yaml_file in self.policy_dir.glob("*.yaml"):
            mtime = datetime.fromtimestamp(yaml_file.stat().st_mtime)
            if mtime > self.last_loaded:
                logger.info("Policy files changed, reloading...")
                self.load_policies()
                return True
                
        return False
        
    def validate_policy(self, policy: Dict[str, Any]) -> List[str]:
        """Validate policy structure and return errors"""
        errors = []
        
        # Check required fields
        if not policy.get("name"):
            errors.append("Policy must have a 'name' field")
            
        # Validate cost limits
        if "cost_limits" in policy:
            cost_limits = policy["cost_limits"]
            for field in ["max_per_request", "max_per_minute", "daily_cap"]:
                if field in cost_limits and not isinstance(cost_limits[field], (int, float)):
                    errors.append(f"cost_limits.{field} must be a number")
                    
        # Validate rate limits
        if "rate_limits" in policy:
            rate_limits = policy["rate_limits"]
            for field in ["requests_per_minute", "requests_per_hour", "requests_per_day"]:
                if field in rate_limits and not isinstance(rate_limits[field], int):
                    errors.append(f"rate_limits.{field} must be an integer")
                    
        return errors