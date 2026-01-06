"""
Zenoo RPC HTTP Server - REST API for Odoo Operations

Provides a simple HTTP REST API wrapper around the Zenoo RPC MCP server.
Exposes 8 powerful tools for Odoo operations via standard HTTP/JSON.
Works with any HTTP client: AI agents, custom apps, curl, or any language.

Architecture:
    Any HTTP Client ──HTTPS──> HTTP Server ──stdio──> MCP Server ──> Odoo
    (AI, Apps, curl)         (REST API)    (Python)   (FastMCP)    (JSON-RPC)

Why This Design?
    - Standard REST API - simple HTTP/JSON, no special protocols
    - Universal compatibility - works with any HTTP client
    - Easy authentication - standard Bearer token
    - No complex setup - just HTTP POST with JSON

Usage:
    # Start the server (reads MCP_PORT and MCP_API_KEYS from .env)
    bash scripts/start_http_proxy.sh

    # List available tools
    curl http://localhost:${MCP_PORT}/tools \\
      -H "Authorization: Bearer ${MCP_API_KEYS}"

    # Call a tool
    curl -X POST http://localhost:${MCP_PORT}/tools/search_records \\
      -H "Authorization: Bearer ${MCP_API_KEYS}" \\
      -H "Content-Type: application/json" \\
      -d '{"arguments": {"model": "res.partner", "limit": 3}}'

For AI Agent Integration:
    1. Configure .env with MCP_PORT and MCP_API_KEYS
    2. Start server: bash scripts/start_http_proxy.sh
    3. (Optional) Expose: ngrok http ${MCP_PORT}
    4. Configure in your AI platform with URL and Bearer token

See docs/HTTP-SERVER.md for complete guide.
"""

__all__ = ['MCPHttpProxy', 'main']
__version__ = '1.0.0'
