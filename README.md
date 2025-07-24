# Proxene – Developer-First AI Governance Proxy

**只需把 LLM 请求指向 Proxene，即刻省成本、去敏、合规审计，全部用 YAML/VS-Code 调试。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Quick Start

```bash
# Install
pip install proxene

# Start proxy
proxene start --port 8080

# Point your LLM calls to Proxene
# Old: https://api.openai.com/v1/chat/completions
# New: http://localhost:8080/v1/chat/completions
```

## ✨ Features

- **Policy-as-Code** - Define cost limits, PII detection, and routing rules in YAML
- **Cost Guard** - Real-time token counting with per-request/minute/daily caps
- **PII Shield** - Auto-detect and redact sensitive data (SSN, emails, credit cards)
- **Local-First** - Debug policies with CLI replay, no cloud dependency
- **VS Code Integration** - Live request monitoring and policy debugging

## 📋 Example Policy

```yaml
# policies/default.yaml
cost_limits:
  max_per_request: 0.03
  daily_cap: 100.00

pii_detection:
  enabled: true
  action: redact  # or: block, warn

routing:
  - if: complexity < 3
    use: claude-3-haiku
  - else:
    use: gpt-4o
```

## 🛠️ Architecture

```
Your App → Proxene Proxy → LLM Provider
             ↓
         [Policy Engine]
         [Cost Guard]
         [PII Detector]
         [OTEL Logging]
```

## 📊 Observability

Built-in OpenTelemetry support for monitoring:
- Request costs and token usage
- PII detection hits
- Policy violations
- Model routing decisions

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md).

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

Built with ❤️ for developers who need simple, powerful AI governance