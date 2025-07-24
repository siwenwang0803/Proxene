"""Tests for policy loader functionality"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml
from proxene.policies.loader import PolicyLoader


class TestPolicyLoader:
    
    def setup_method(self):
        # Create temporary directory for test policies
        self.temp_dir = tempfile.mkdtemp()
        self.loader = PolicyLoader(self.temp_dir)
    
    def teardown_method(self):
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_policies_empty_dir(self):
        policies = self.loader.load_policies()
        
        # Should create and load default policy
        assert len(policies) == 1
        assert "default" in policies
        assert policies["default"]["name"] == "Default Policy"
    
    def test_load_custom_policy(self):
        # Create a custom policy file
        custom_policy = {
            "name": "Test Policy",
            "enabled": True,
            "cost_limits": {
                "max_per_request": 0.05
            }
        }
        
        policy_file = Path(self.temp_dir) / "test.yaml"
        with open(policy_file, 'w') as f:
            yaml.dump(custom_policy, f)
        
        policies = self.loader.load_policies()
        
        assert "test" in policies
        assert policies["test"]["name"] == "Test Policy"
        assert policies["test"]["cost_limits"]["max_per_request"] == 0.05
    
    def test_get_active_policy_default(self):
        self.loader.load_policies()
        
        policy = self.loader.get_active_policy()
        
        assert policy["name"] == "Default Policy"
        assert policy["enabled"] is True
    
    def test_get_active_policy_by_name(self):
        # Create custom policy
        custom_policy = {
            "name": "Custom Policy",
            "enabled": True
        }
        
        policy_file = Path(self.temp_dir) / "custom.yaml"
        with open(policy_file, 'w') as f:
            yaml.dump(custom_policy, f)
        
        self.loader.load_policies()
        
        policy = self.loader.get_active_policy("custom")
        
        assert policy["name"] == "Custom Policy"
    
    def test_get_active_policy_disabled(self):
        # Create disabled policy and enabled policy
        disabled_policy = {
            "name": "Disabled Policy",
            "enabled": False
        }
        enabled_policy = {
            "name": "Enabled Policy", 
            "enabled": True
        }
        
        Path(self.temp_dir, "disabled.yaml").write_text(yaml.dump(disabled_policy))
        Path(self.temp_dir, "enabled.yaml").write_text(yaml.dump(enabled_policy))
        
        self.loader.load_policies()
        
        # Should return first enabled policy
        policy = self.loader.get_active_policy()
        assert policy["name"] == "Enabled Policy"
    
    def test_validate_policy_valid(self):
        policy = {
            "name": "Valid Policy",
            "cost_limits": {
                "max_per_request": 0.01,
                "daily_cap": 100.0
            },
            "rate_limits": {
                "requests_per_minute": 60
            }
        }
        
        errors = self.loader.validate_policy(policy)
        assert len(errors) == 0
    
    def test_validate_policy_missing_name(self):
        policy = {
            "cost_limits": {
                "max_per_request": 0.01
            }
        }
        
        errors = self.loader.validate_policy(policy)
        assert len(errors) == 1
        assert "must have a 'name' field" in errors[0]
    
    def test_validate_policy_invalid_cost_limit(self):
        policy = {
            "name": "Test Policy",
            "cost_limits": {
                "max_per_request": "invalid"
            }
        }
        
        errors = self.loader.validate_policy(policy)
        assert len(errors) == 1
        assert "must be a number" in errors[0]
    
    def test_validate_policy_invalid_rate_limit(self):
        policy = {
            "name": "Test Policy",
            "rate_limits": {
                "requests_per_minute": 60.5
            }
        }
        
        errors = self.loader.validate_policy(policy)
        assert len(errors) == 1
        assert "must be an integer" in errors[0]
    
    def test_reload_if_changed(self):
        # Initial load
        policies = self.loader.load_policies()
        initial_time = self.loader.last_loaded
        
        # Simulate no changes
        changed = self.loader.reload_if_changed()
        assert changed is False
        assert self.loader.last_loaded == initial_time
        
        # Add new policy file
        import time
        time.sleep(0.1)  # Ensure different timestamp
        
        new_policy = {"name": "New Policy", "enabled": True}
        policy_file = Path(self.temp_dir) / "new.yaml"
        with open(policy_file, 'w') as f:
            yaml.dump(new_policy, f)
        
        changed = self.loader.reload_if_changed()
        assert changed is True
        assert self.loader.last_loaded > initial_time
        assert "new" in self.loader.policies
    
    def test_default_policy_structure(self):
        policies = self.loader.load_policies()
        default = policies["default"]
        
        # Check all required sections exist
        assert "cost_limits" in default
        assert "rate_limits" in default
        assert "pii_detection" in default
        assert "caching" in default
        assert "logging" in default
        
        # Check cost limits
        cost_limits = default["cost_limits"]
        assert "max_per_request" in cost_limits
        assert "daily_cap" in cost_limits
        
        # Check PII detection
        pii_config = default["pii_detection"]
        assert "enabled" in pii_config
        assert "action" in pii_config
        assert "entities" in pii_config
        assert isinstance(pii_config["entities"], list)