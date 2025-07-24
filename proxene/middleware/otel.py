"""OpenTelemetry instrumentation for Proxene"""

from typing import Dict, Any, Optional
import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import logging

logger = logging.getLogger(__name__)


class OTELMiddleware:
    """OpenTelemetry middleware for tracing LLM requests"""
    
    def __init__(self):
        self.tracer = None
        self.initialized = False
        
    def initialize(self, service_name: str = "proxene", export_to_console: bool = True):
        """Initialize OpenTelemetry tracing"""
        if self.initialized:
            return
            
        # Create resource
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "0.1.0",
        })
        
        # Set up tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add exporters
        if export_to_console:
            # Console exporter for development
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(
                BatchSpanProcessor(console_exporter)
            )
            
        # TODO: Add OTLP exporter for production
        # from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        # otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
        # provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
        
        self.initialized = True
        logger.info("OpenTelemetry initialized")
        
    def instrument_fastapi(self, app):
        """Instrument FastAPI application"""
        if not self.initialized:
            self.initialize()
            
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
        
    def trace_llm_request(
        self,
        model: str,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ):
        """Create span for LLM request"""
        if not self.tracer:
            return
            
        with self.tracer.start_as_current_span("llm_request") as span:
            # Set basic attributes
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.request_id", request_data.get("id", "unknown"))
            
            # Set request attributes
            messages = request_data.get("messages", [])
            span.set_attribute("llm.message_count", len(messages))
            span.set_attribute("llm.max_tokens", request_data.get("max_tokens", 0))
            span.set_attribute("llm.temperature", request_data.get("temperature", 1.0))
            
            # Count tokens in messages
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            span.set_attribute("llm.request_chars", total_chars)
            
            # Set response attributes if available
            if response_data:
                usage = response_data.get("usage", {})
                span.set_attribute("llm.prompt_tokens", usage.get("prompt_tokens", 0))
                span.set_attribute("llm.completion_tokens", usage.get("completion_tokens", 0))
                span.set_attribute("llm.total_tokens", usage.get("total_tokens", 0))
                
                # Cost tracking
                if "_proxene_cost" in response_data:
                    span.set_attribute("llm.cost_usd", response_data["_proxene_cost"])
                    
                # Cache hit
                if response_data.get("_proxene_cache_hit"):
                    span.set_attribute("cache.hit", True)
                    
                # PII detection
                if "_proxene_pii" in response_data:
                    pii_data = response_data["_proxene_pii"]
                    request_findings = len(pii_data.get("request_findings", []))
                    response_findings = len(pii_data.get("response_findings", []))
                    
                    span.set_attribute("pii.request_findings", request_findings)
                    span.set_attribute("pii.response_findings", response_findings)
                    span.set_attribute("pii.total_findings", request_findings + response_findings)
                    
                span.set_status(Status(StatusCode.OK))
            
            # Set error if occurred
            if error:
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR, str(error)))
                
    def create_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Create a custom span"""
        if not self.tracer:
            return None
            
        span = self.tracer.start_span(name)
        
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
                
        return span


# Global OTEL middleware instance
otel_middleware = OTELMiddleware()