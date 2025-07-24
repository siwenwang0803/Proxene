"""Tests for PII detection functionality"""

import pytest
from proxene.guards.pii_detector import PIIDetector, PIIType, PIIAction


class TestPIIDetector:
    
    def setup_method(self):
        self.detector = PIIDetector()
    
    def test_detect_email(self):
        text = "Contact me at john.doe@example.com for more info"
        findings = self.detector.detect(text)
        
        assert len(findings) == 1
        assert findings[0][0] == PIIType.EMAIL
        assert findings[0][1] == "john.doe@example.com"
    
    def test_detect_phone(self):
        texts = [
            "Call me at 555-123-4567",
            "My number is (555) 123-4567",
            "Phone: +1-555-123-4567"
        ]
        
        for text in texts:
            findings = self.detector.detect(text)
            assert len(findings) >= 1
            assert any(f[0] == PIIType.PHONE for f in findings)
    
    def test_detect_ssn(self):
        text = "SSN: 123-45-6789"
        findings = self.detector.detect(text)
        
        assert len(findings) == 1
        assert findings[0][0] == PIIType.SSN
        assert findings[0][1] == "123-45-6789"
    
    def test_detect_credit_card(self):
        text = "Card number: 4111 1111 1111 1111"
        findings = self.detector.detect(text)
        
        assert len(findings) == 1
        assert findings[0][0] == PIIType.CREDIT_CARD
    
    def test_detect_api_key(self):
        text = "Use this key: sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234"
        findings = self.detector.detect(text)
        
        assert len(findings) == 1
        assert findings[0][0] == PIIType.API_KEY
    
    def test_detect_multiple_pii(self):
        text = "Email john@example.com or call 555-123-4567"
        findings = self.detector.detect(text)
        
        assert len(findings) == 2
        types = [f[0] for f in findings]
        assert PIIType.EMAIL in types
        assert PIIType.PHONE in types
    
    def test_redact_email(self):
        text = "Contact john.doe@example.com"
        findings = self.detector.detect(text)
        redacted = self.detector.redact_text(text, findings)
        
        assert "john.doe@example.com" not in redacted
        assert "jo***@***.***" in redacted
    
    def test_redact_phone(self):
        text = "Call 555-123-4567"
        findings = self.detector.detect(text)
        redacted = self.detector.redact_text(text, findings)
        
        assert "555-123-4567" not in redacted
        assert "[PHONE]" in redacted
    
    def test_redact_credit_card(self):
        text = "Card: 4111 1111 1111 1234"
        findings = self.detector.detect(text)
        redacted = self.detector.redact_text(text, findings)
        
        assert "4111 1111 1111 1234" not in redacted
        assert "****-****-****-1234" in redacted
    
    def test_hash_pii(self):
        text = "Email: test@example.com"
        findings = self.detector.detect(text)
        hashed = self.detector.hash_text(text, findings)
        
        assert "test@example.com" not in hashed
        assert "[email:" in hashed
        assert "]" in hashed
    
    def test_process_request_warn(self):
        request = {
            "messages": [
                {"role": "user", "content": "My email is test@example.com"}
            ]
        }
        
        processed, findings = self.detector.process_request(request, PIIAction.WARN)
        
        # Original should be unchanged
        assert processed["messages"][0]["content"] == "My email is test@example.com"
        assert len(findings) == 1
        assert findings[0]["type"] == "email"
        assert findings[0]["text"] == "test@example.com"
    
    def test_process_request_redact(self):
        request = {
            "messages": [
                {"role": "user", "content": "My SSN is 123-45-6789"}
            ]
        }
        
        processed, findings = self.detector.process_request(request, PIIAction.REDACT)
        
        assert "123-45-6789" not in processed["messages"][0]["content"]
        assert "[SSN]" in processed["messages"][0]["content"]
        assert len(findings) == 1
    
    def test_process_request_block(self):
        request = {
            "messages": [
                {"role": "user", "content": "My credit card is 4111 1111 1111 1111"}
            ]
        }
        
        with pytest.raises(ValueError) as exc_info:
            self.detector.process_request(request, PIIAction.BLOCK)
        
        assert "PII detected" in str(exc_info.value)
    
    def test_process_response_redact(self):
        response = {
            "choices": [{
                "message": {
                    "content": "Your phone number 555-123-4567 has been saved"
                }
            }]
        }
        
        processed, findings = self.detector.process_response(response, PIIAction.REDACT)
        
        assert "555-123-4567" not in processed["choices"][0]["message"]["content"]
        assert "[PHONE]" in processed["choices"][0]["message"]["content"]
        assert len(findings) == 1
    
    def test_entity_filtering(self):
        request = {
            "messages": [
                {"role": "user", "content": "Email: test@example.com, Phone: 555-123-4567"}
            ]
        }
        
        # Only check for emails
        processed, findings = self.detector.process_request(
            request, PIIAction.WARN, entities_to_check=["email"]
        )
        
        assert len(findings) == 1
        assert findings[0]["type"] == "email"