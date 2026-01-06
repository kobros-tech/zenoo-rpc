#!/usr/bin/env python3
"""
IMPORTANT: Why HTTP calls don't work with your MCP server

This script demonstrates why direct HTTP/curl requests fail with 406 errors
and explains the correct approach.
"""

print("""
╔══════════════════════════════════════════════════════════════════════╗
║                  MCP HTTP TRANSPORT EXPLANATION                        ║
╚══════════════════════════════════════════════════════════════════════╝

Your MCP server uses FastMCP's 'streamable-http' transport, which is
based on Server-Sent Events (SSE), NOT regular HTTP/JSON-RPC.

THE PROBLEM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Direct HTTP calls (curl, requests.post, etc.) → 406 Not Acceptable
❌ Cannot use simple JSON-RPC over HTTP
❌ Requires SSE protocol understanding

WHY IT DOESN'T WORK:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FastMCP's HTTP transport uses:
  • Server-Sent Events (SSE) for streaming
  • Specific message framing
  • Bidirectional communication over HTTP

Regular HTTP POST with JSON-RPC format won't work because the server
expects SSE connection initiation, not plain HTTP requests.

THE SOLUTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use one of these approaches:

1. ✅ USE THE PROPER MCP PYTHON CLIENT
   ─────────────────────────────────────────────────────────────────
   from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType
   from zenoo_rpc.mcp.transport import MCPTransport

   config = MCPServerConfig(
       name="zenoo-mcp",
       transport_type=MCPTransportType.HTTP,
       url="http://localhost:8000",
       headers={"Authorization": "Bearer letta-secret-123"}
   )

   transport = MCPTransport(config)
   async with MCPClient(transport) as client:
       tools = await client.list_tools()
       result = await client.call_tool("search_records", {...})


2. ✅ USE STDIO TRANSPORT FOR LETTA (RECOMMENDED!)
   ─────────────────────────────────────────────────────────────────
   Stop your HTTP server and run:
   
   python -m zenoo_rpc.mcp_server.cli \\
     --transport stdio \\
     --odoo-url http://localhost:8069 \\
     --odoo-database sign_oca_16_1 \\
     --odoo-username admin \\
     --odoo-password admin

   Then configure Letta's ~/.letta/mcp_servers.json:
   
   {
     "mcpServers": {
       "zenoo-odoo": {
         "command": "python",
         "args": [
           "-m", "zenoo_rpc.mcp_server.cli",
           "--transport", "stdio",
           "--odoo-url", "http://localhost:8069",
           "--odoo-database", "sign_oca_16_1",
           "--odoo-username", "admin",
           "--odoo-password", "admin"
         ]
       }
     }
   }


3. ✅ USE THE PROVIDED TEST SCRIPTS
   ─────────────────────────────────────────────────────────────────
   These scripts properly handle the MCP protocol:
   
   # List tools (requires working virtualenv)
   python examples/list_mcp_tools.py --url http://localhost:8000
   
   # Full test suite
   python examples/mcp_server_test.py


WHAT ABOUT THE HTTP TRANSPORT?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The HTTP transport is mainly for:
  • Advanced use cases
  • Network-based MCP between different machines
  • When you can't use subprocess/stdio

But it requires:
  • Official MCP client libraries
  • Understanding of SSE protocol
  • More complex setup

FOR LETTA AI INTEGRATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👉 LETTA LOCAL: Use stdio transport
👉 LETTA CLOUD: Use HTTP transport + ngrok (you need this!)

Letta Local starts your MCP server as a subprocess and communicates via
stdin/stdout. Letta Cloud runs on remote servers and needs HTTP access.

YOUR ENVIRONMENT VARIABLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Currently set:
  MCP_API_KEYS=letta-secret-123
  MCP_TRANSPORT_TYPE=http
  MCP_PORT=8000
  MCP_AUTH_METHOD=api_key
  ODOO_URL=http://localhost:8069
  ODOO_DATABASE=sign_oca_16_1
  ODOO_USERNAME=admin
  ODOO_PASSWORD=admin

For stdio (recommended):
  REMOVE: MCP_API_KEYS, MCP_TRANSPORT_TYPE, MCP_PORT, MCP_AUTH_METHOD
  KEEP: ODOO_* variables

QUICK START FOR LETTA LOCAL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Stop your HTTP server (Ctrl+C)
2. Create Letta config:
   python examples/letta_integration_example.py --save-config
3. Start Letta: letta run
4. Your Zenoo MCP tools will be available to Letta agents!

QUICK START FOR LETTA CLOUD (YOU NEED THIS!):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Keep your HTTP server running (you already have this!)
2. Install ngrok: https://ngrok.com/download
3. Expose server: ngrok http 8000
4. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
5. Configurletta-cloud-integration.md - Letta Cloud setup (you!)
• docs/mcp-letta-integration.md - Letta Local setup
• docs/mcp-http-limitation.md - Why direct HTTP calls don't work
• docs/mcp-quick-reference.md - Command reference

╔══════════════════════════════════════════════════════════════════════╗
║  TL;DR: Letta Cloud needs HTTP + ngrok. Letta Local needs stdio.━━━
• docs/mcp-http-limitation.md - Detailed explanation
• docs/mcp-letta-integration.md - Complete Letta setup guide
• docs/mcp-quick-reference.md - Command reference
• examples/letta_integration_example.py - Working examples

╔══════════════════════════════════════════════════════════════════════╗
║  TL;DR: Use stdio transport for Letta, not HTTP!                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")
