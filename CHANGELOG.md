# Changelog

All notable changes to Proxene will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-alpha] - 2024-01-XX

### 🎉 Initial Alpha Release

First public release of Proxene - Developer-First AI Governance Proxy.

### ✨ Added

#### Core Proxy Features
- **FastAPI-based reverse proxy** for LLM providers (OpenAI, Claude, etc.)
- **Request/response forwarding** with governance layer
- **Health check endpoint** (`/health`)
- **Statistics endpoint** (`/stats`)

#### 💰 Cost Management
- **Real-time token counting** using tiktoken
- **Per-request cost calculation** with model-specific pricing
- **Cost limits enforcement** (per-request, per-minute, daily caps)
- **Cost tracking in Redis** with model breakdowns
- **Budget alerts and blocking** when limits exceeded

#### 🔒 PII Detection & Protection
- **Custom regex-based PII detector** (emails, phones, SSNs, credit cards, API keys)
- **Configurable PII actions**: redact, block, warn, hash
- **Request and response scanning** with metadata injection
- **Entity filtering** for selective PII detection
- **Privacy-preserving redaction** with partial information retention

#### 📋 Policy-as-Code Engine
- **YAML-based policy configuration** with hot reload
- **Policy validation** with detailed error reporting
- **Multiple policy support** with named configurations
- **Default policy creation** for out-of-box experience
- **Policy inheritance** and composition

#### 🗄️ Caching & Performance
- **Redis-based response caching** with SHA256 key generation
- **TTL-based cache expiration** with configurable timeouts
- **Cache hit/miss tracking** with metadata injection
- **Cache invalidation** patterns and utilities

#### 🚦 Rate Limiting
- **Sliding window rate limiting** with Redis backend
- **Per-client rate tracking** using IP + User-Agent hashing
- **Multiple time windows** (per-minute, per-hour, per-day)
- **Rate limit headers** in responses
- **Graceful degradation** on Redis failures

#### 📊 Observability & Monitoring
- **OpenTelemetry integration** with FastAPI instrumentation
- **Request tracing** with cost, PII, and performance metadata
- **Structured logging** with configurable levels
- **Metrics export** for cost, usage, and performance
- **Error tracking** with detailed context

#### 🎨 VS Code Extension
- **TypeScript-based extension** with proper VS Code integration
- **One-click proxy control** (start/stop) with process management
- **Real-time request logs** with cost and PII indicators
- **Status bar integration** with visual proxy state
- **Command palette support** and keyboard shortcuts
- **Configuration management** via VS Code settings

#### 📈 Streamlit Dashboard
- **Modern web dashboard** with dark theme and interactive charts
- **Cost trend visualization** with 7-day Plotly line charts
- **Model usage analytics** with pie charts and bar graphs
- **PII detection analysis** with rate tracking by model
- **Real-time request logs** with auto-refresh
- **Redis data integration** for live metrics

#### 🐳 Docker & Deployment
- **Multi-stage Dockerfiles** for proxy and dashboard
- **Docker Compose setup** with Redis, proxy, and dashboard
- **Environment variable configuration** for flexible deployment
- **Health checks** and graceful shutdowns
- **Volume mounts** for persistent data and configuration

#### 🧪 Testing & Quality
- **Comprehensive unit tests** (42 tests, 52% coverage)
- **End-to-end testing** with real LLM providers
- **Integration tests** with FastAPI TestClient
- **Mock data generators** for dashboard development
- **Async test support** with pytest-asyncio

#### 🔧 Developer Experience
- **Poetry-based dependency management** with lock files
- **CLI interface** with multiple commands (test, dashboard, replay)
- **Request replay functionality** for debugging
- **Policy validation tools** with detailed error reporting
- **Configuration hot reload** for development

#### 📚 Documentation
- **Comprehensive README** with quick start guides
- **API documentation** with FastAPI auto-generation
- **Policy configuration guide** with examples
- **VS Code extension documentation** with screenshots
- **Dashboard user guide** with feature explanations
- **Docker deployment guide** with production considerations

### 🏗️ Architecture

#### Core Components
- **Proxy Server**: FastAPI-based with async request handling
- **Policy Engine**: YAML-driven governance with hot reload
- **Cost Guard**: Token counting and budget enforcement
- **PII Detector**: Privacy protection with configurable actions
- **Cache Service**: Redis-based response caching
- **Rate Limiter**: Sliding window rate limiting
- **OTEL Middleware**: Observability and tracing

#### Data Flow
```
Client → Proxy → [Policy Engine] → [Cost Guard] → [PII Detector] → 
[Rate Limiter] → [Cache Check] → LLM Provider → [PII Scan] → 
[Cache Store] → [OTEL Trace] → Client
```

#### Integrations
- **OpenAI API**: Full compatibility with chat completions
- **Redis**: Caching, cost tracking, rate limiting
- **OpenTelemetry**: Distributed tracing and metrics
- **VS Code**: Developer tooling and monitoring
- **Streamlit**: Web-based analytics dashboard

### 🔐 Security Features
- **PII detection and redaction** in requests and responses
- **Cost-based attack prevention** with budget enforcement
- **Rate limiting** to prevent abuse
- **Input sanitization** and validation
- **Secure defaults** in policy configuration

### 🎯 Performance
- **Async request handling** with FastAPI and httpx
- **Redis caching** for response deduplication
- **Connection pooling** for upstream providers
- **Efficient token counting** with tiktoken
- **Optimized data structures** for rate limiting

### 📦 Distribution
- **Python package** via Poetry with proper dependencies
- **Docker images** for containerized deployment
- **VS Code Extension** (development build)
- **GitHub repository** with comprehensive documentation

### 🐛 Known Issues
- VS Code extension requires manual compilation
- Dashboard uses mock data for some features
- Limited to OpenAI API compatibility
- Redis is required for full functionality

### 🔮 Future Roadmap
- **Multi-provider support** (Anthropic, Google, etc.)
- **Advanced policy rules** with conditional logic
- **Team management** and multi-user support
- **Compliance reporting** (SOC2, GDPR, etc.)
- **Advanced analytics** with ML-based insights
- **Plugin system** for extensibility

---

## Development

### Building from Source
```bash
git clone https://github.com/siwenwang0803/Proxene.git
cd Proxene
poetry install
poetry run python run.py
```

### Running Tests
```bash
poetry run proxene test --coverage
```

### Building Docker Images
```bash
docker-compose up --build
```

### VS Code Extension Development
```bash
cd vscode-extension
npm install
npm run compile
# Press F5 to launch development host
```

---

## Credits

Built with ❤️ by the Proxene team.

- **FastAPI**: Modern Python web framework
- **Redis**: In-memory data structure store
- **OpenTelemetry**: Observability framework
- **Streamlit**: Python web app framework
- **VS Code API**: Extension development platform
- **tiktoken**: Token counting library