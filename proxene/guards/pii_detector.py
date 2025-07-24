"""PII detection and handling for LLM requests/responses"""

import re
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PIIType(Enum):
    EMAIL = "email"
    PHONE = "phone" 
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    AWS_KEY = "aws_key"
    PERSON_NAME = "person_name"


class PIIAction(Enum):
    REDACT = "redact"
    BLOCK = "block"
    WARN = "warn"
    HASH = "hash"


class PIIDetector:
    """Custom PII detector with regex patterns"""
    
    def __init__(self):
        self.patterns = {
            PIIType.EMAIL: re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            PIIType.PHONE: re.compile(
                r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|'
                r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b'
            ),
            PIIType.SSN: re.compile(
                r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b'
            ),
            PIIType.CREDIT_CARD: re.compile(
                r'\b(?:\d[ -]*?){13,19}\b'
            ),
            PIIType.IP_ADDRESS: re.compile(
                r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
            ),
            PIIType.API_KEY: re.compile(
                r'\b(sk-[a-zA-Z0-9]{48}|pk_[a-zA-Z0-9]{32}|Bearer\s+[a-zA-Z0-9\-_\.]+)\b'
            ),
            PIIType.AWS_KEY: re.compile(
                r'\b(AKIA[0-9A-Z]{16}|aws_access_key_id\s*=\s*[A-Z0-9]{20})\b'
            ),
        }
        
        # Common first and last names for basic name detection
        self.common_names = {
            "john", "jane", "smith", "johnson", "williams", "brown", "jones",
            "davis", "miller", "wilson", "moore", "taylor", "anderson", "thomas",
            "jackson", "white", "harris", "martin", "thompson", "garcia", "martinez"
        }
        
    def detect(self, text: str) -> List[Tuple[PIIType, str, int, int]]:
        """
        Detect PII in text
        Returns: List of (pii_type, matched_text, start_pos, end_pos)
        """
        findings = []
        
        # Check regex patterns
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                findings.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end()
                ))
                
        # Basic name detection (case-insensitive word boundary check)
        words = text.lower().split()
        for word in words:
            cleaned_word = re.sub(r'[^\w]', '', word)
            if cleaned_word in self.common_names:
                # Find position in original text
                pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                for match in pattern.finditer(text):
                    findings.append((
                        PIIType.PERSON_NAME,
                        match.group(),
                        match.start(),
                        match.end()
                    ))
                    
        # Sort by position
        findings.sort(key=lambda x: x[2])
        
        return findings
        
    def redact_text(self, text: str, findings: List[Tuple[PIIType, str, int, int]]) -> str:
        """Redact PII from text"""
        if not findings:
            return text
            
        # Process from end to beginning to maintain positions
        result = text
        for pii_type, matched_text, start, end in reversed(findings):
            # Create redaction based on type
            if pii_type == PIIType.EMAIL:
                parts = matched_text.split('@')
                if len(parts) == 2:
                    redacted = f"{parts[0][:2]}***@***.***"
                else:
                    redacted = "[EMAIL]"
            elif pii_type == PIIType.PHONE:
                redacted = "[PHONE]"
            elif pii_type == PIIType.SSN:
                redacted = "[SSN]"
            elif pii_type == PIIType.CREDIT_CARD:
                # Keep last 4 digits if available
                digits = re.sub(r'\D', '', matched_text)
                if len(digits) >= 4:
                    redacted = f"****-****-****-{digits[-4:]}"
                else:
                    redacted = "[CREDIT_CARD]"
            elif pii_type == PIIType.API_KEY:
                redacted = "[API_KEY]"
            elif pii_type == PIIType.AWS_KEY:
                redacted = "[AWS_KEY]"
            elif pii_type == PIIType.PERSON_NAME:
                redacted = "[NAME]"
            else:
                redacted = f"[{pii_type.value.upper()}]"
                
            result = result[:start] + redacted + result[end:]
            
        return result
        
    def hash_text(self, text: str, findings: List[Tuple[PIIType, str, int, int]]) -> str:
        """Hash PII in text (for logging while preserving uniqueness)"""
        import hashlib
        
        if not findings:
            return text
            
        result = text
        for pii_type, matched_text, start, end in reversed(findings):
            # Create hash of the PII
            hash_value = hashlib.sha256(matched_text.encode()).hexdigest()[:8]
            hashed = f"[{pii_type.value}:{hash_value}]"
            result = result[:start] + hashed + result[end:]
            
        return result
        
    def process_request(
        self, 
        request_data: Dict[str, Any], 
        action: PIIAction,
        entities_to_check: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process request for PII
        Returns: (processed_request, findings_report)
        """
        findings_report = []
        processed = request_data.copy()
        
        # Check messages
        if "messages" in processed:
            for i, message in enumerate(processed["messages"]):
                if "content" in message:
                    content = message["content"]
                    findings = self.detect(content)
                    
                    # Filter by entities if specified
                    if entities_to_check:
                        findings = [
                            f for f in findings 
                            if f[0].value in entities_to_check
                        ]
                    
                    if findings:
                        # Record findings
                        for pii_type, matched_text, start, end in findings:
                            findings_report.append({
                                "location": f"messages[{i}].content",
                                "type": pii_type.value,
                                "text": matched_text if action == PIIAction.WARN else "[REDACTED]",
                                "position": {"start": start, "end": end}
                            })
                            
                        # Apply action
                        if action == PIIAction.BLOCK:
                            raise ValueError(f"PII detected in request: {len(findings)} instances found")
                        elif action == PIIAction.REDACT:
                            processed["messages"][i]["content"] = self.redact_text(content, findings)
                        elif action == PIIAction.HASH:
                            processed["messages"][i]["content"] = self.hash_text(content, findings)
                        # WARN just reports, doesn't modify
                            
        return processed, findings_report
        
    def process_response(
        self,
        response_data: Dict[str, Any],
        action: PIIAction,
        entities_to_check: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process response for PII
        Returns: (processed_response, findings_report)
        """
        findings_report = []
        processed = response_data.copy()
        
        # Check choices
        if "choices" in processed:
            for i, choice in enumerate(processed["choices"]):
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                    findings = self.detect(content)
                    
                    # Filter by entities if specified
                    if entities_to_check:
                        findings = [
                            f for f in findings 
                            if f[0].value in entities_to_check
                        ]
                    
                    if findings:
                        # Record findings
                        for pii_type, matched_text, start, end in findings:
                            findings_report.append({
                                "location": f"choices[{i}].message.content",
                                "type": pii_type.value,
                                "text": matched_text if action == PIIAction.WARN else "[REDACTED]",
                                "position": {"start": start, "end": end}
                            })
                            
                        # Apply action
                        if action == PIIAction.BLOCK:
                            # Replace entire response with error
                            processed["choices"][i]["message"]["content"] = \
                                "Response blocked due to PII detection."
                        elif action == PIIAction.REDACT:
                            processed["choices"][i]["message"]["content"] = \
                                self.redact_text(content, findings)
                        elif action == PIIAction.HASH:
                            processed["choices"][i]["message"]["content"] = \
                                self.hash_text(content, findings)
                                
        return processed, findings_report