# Proxene VS Code Extension

Developer-first AI governance with cost limits, PII detection, and request debugging right in your editor.

## Features

### 🚀 Proxy Control
- **Start/Stop Proxy**: One-click proxy server management
- **Real-time Status**: See proxy status in the status bar
- **Auto-start**: Optionally start proxy when VS Code opens

### 📊 Request Monitoring  
- **Live Request Logs**: See all LLM requests in real-time
- **Cost Tracking**: View per-request costs and running totals
- **PII Detection**: Get notified when sensitive data is detected
- **Error Monitoring**: Quickly spot failed requests

### 🔧 Configuration
- **Port Settings**: Configure proxy port
- **Log Levels**: Adjust logging verbosity  
- **Dashboard Integration**: Quick access to web dashboard

### 🎯 Developer Experience
- **Click-to-Debug**: Click any log entry to see full details
- **YAML Navigation**: Jump from logs to policy rules (coming soon)
- **Status Bar**: Always-visible proxy status

## Getting Started

1. **Install Proxene**: Make sure Proxene is installed in your workspace
   ```bash
   pip install proxene
   # or
   poetry add proxene
   ```

2. **Open Workspace**: Open a folder containing Proxene configuration

3. **Start Proxy**: Click the "Start Proxy" button in the Proxene panel or use the command palette

4. **Monitor Requests**: Watch requests appear in the "Request Logs" panel

## Extension Settings

- `proxene.proxyPort`: Port for proxy server (default: 8081)
- `proxene.autoStart`: Auto-start proxy when VS Code opens (default: false)
- `proxene.logLevel`: Log level (debug/info/warn/error, default: info)
- `proxene.dashboardUrl`: URL for web dashboard (default: http://localhost:8501)

## Commands

- `Proxene: Start Proxy` - Start the proxy server
- `Proxene: Stop Proxy` - Stop the proxy server  
- `Proxene: Show Request Logs` - Open the request logs panel
- `Proxene: Open Dashboard` - Open the web dashboard

## Views

### Control Panel
- Proxy status indicator
- Start/stop controls
- Configuration overview
- Quick access to dashboard

### Request Logs  
- Real-time request monitoring
- Cost and PII indicators
- Click to view full request details
- Color-coded status indicators

## Requirements

- VS Code 1.60.0 or higher
- Python 3.11+ with Proxene installed
- Node.js (for extension development)

## Known Issues

- Log parsing is basic in this version
- YAML navigation not yet implemented
- Dashboard integration requires manual setup

## Release Notes

### 0.1.0

Initial release with:
- Basic proxy control
- Request log monitoring  
- Configuration management
- Dashboard integration