#!/usr/bin/env python3
"""
MCP HTTP Proxy - Higher-Level HTTP Tool for MCP Server

This proxy provides a simple HTTP REST API wrapper around the Zenoo RPC MCP
server, which runs in stdio mode. This architecture solves the complexity of
FastMCP's SSE-based HTTP transport while providing a clean API for clients.

Architecture:
    Letta Cloud ──HTTPS──> HTTP Proxy ──stdio──> MCP Server ──> Odoo
                (ngrok)   (REST API)   (subprocess) (FastMCP)

Why This Design?
    - FastMCP's HTTP transport uses Server-Sent Events (SSE) with complex auth
    - Stdio transport is simpler and more reliable
    - HTTP Proxy provides standard REST API for external clients
    - No SSE/authentication complexity for clients

Usage:
    # Start the proxy (automatically loads .env file)
    python mcp_http_proxy.py

    # Or override with arguments
    python mcp_http_proxy.py --port 9090 --api-key your-secret-key

    # Using the startup script (recommended)
    ./scripts/start_http_proxy.sh

Note: The script automatically loads .env from the parent directory.
      No need to export variables manually!

Endpoints:
    GET  /           - Server information
    GET  /health     - Health check
    GET  /tools      - List all MCP tools
    POST /tools/{name} - Call a specific tool
    POST /           - JSON-RPC (Letta format)
    POST /mcp        - Streamable HTTP (Claude Code format)

Authentication:
    Authorization: Bearer <api-key>

For complete guide, see docs/QUICKSTART-HTTP-PROXY.md
"""

import asyncio
import json
import sys
import os
import argparse
from pathlib import Path
from aiohttp import web
import logging

# Load environment variables from .env file
def load_env_file():
    """Load .env file manually if python-dotenv is not available."""
    try:
        from dotenv import load_dotenv
        # Try to load .env from same directory as script (zenoo-rpc/.env)
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            return
        # Try current directory
        load_dotenv()
    except ImportError:
        # python-dotenv not installed, load .env manually
        # Try same directory as script first (zenoo-rpc/.env)
        env_path = Path(__file__).parent / '.env'
        if not env_path.exists():
            # Try current directory
            env_path = Path('.env')

        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Don't override existing environment variables
                        if key not in os.environ:
                            os.environ[key] = value

load_env_file()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MCPHttpProxy:
    """HTTP proxy that wraps an stdio MCP server."""
    
    def __init__(self, api_key=None, python_path=None):
        self.api_key = api_key
        self.python_path = python_path or sys.executable
        self.mcp_client = None
        self.transport = None
        
    async def initialize(self):
        """Initialize the MCP client connection."""
        try:
            from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType
            from zenoo_rpc.mcp.transport import MCPTransport
            
            # Prepare environment - disable auth for stdio
            env_vars = os.environ.copy()
            env_vars['MCP_AUTH_METHOD'] = 'none'
            
            # Configure stdio connection
            config = MCPServerConfig(
                name="zenoo-mcp-http-proxy",
                transport_type=MCPTransportType.STDIO,
                command=self.python_path,
                args=[
                    "-m", "zenoo_rpc.mcp_server.cli",
                    "--transport", "stdio"
                ],
                env=env_vars
            )
            
            self.transport = MCPTransport(config)
            self.mcp_client = MCPClient(self.transport)
            await self.mcp_client.connect()
            
            logger.info("✓ MCP stdio client initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Cleanup MCP client connection."""
        if self.mcp_client:
            try:
                await self.mcp_client.disconnect()
            except:
                pass
    
    def check_auth(self, request):
        """Check API key authentication."""
        if not self.api_key:
            return True  # No auth required
        
        auth_header = request.headers.get('Authorization', '').strip()
        
        # Handle different auth formats
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
            is_valid = token == self.api_key
            if not is_valid:
                logger.warning(f"Auth failed: got token '{token[:10]}...', expected '{self.api_key[:10]}...'")
            return is_valid
        elif auth_header == self.api_key:
            # Direct token without "Bearer " prefix
            return True
        
        logger.warning(f"Auth failed: invalid header format: '{auth_header[:50]}'")
        return False
    
    async def handle_list_tools(self, request):
        """Handle GET /tools - list all available tools."""
        if not self.check_auth(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        try:
            tools = await self.mcp_client.list_tools()
            
            # Convert tools to JSON-serializable format
            tools_list = []
            for tool in tools:
                tool_dict = {
                    'name': tool.name,
                    'description': getattr(tool, 'description', ''),
                }
                if hasattr(tool, 'inputSchema'):
                    tool_dict['inputSchema'] = tool.inputSchema
                tools_list.append(tool_dict)
            
            return web.json_response({
                'tools': tools_list,
                'count': len(tools_list)
            })
            
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_call_tool(self, request):
        """Handle POST /tools/{tool_name} - call a specific tool."""
        if not self.check_auth(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        tool_name = request.match_info['tool_name']
        
        try:
            # Get request body
            body = await request.json()
            arguments = body.get('arguments', {})
            
            # Call the tool
            logger.info(f"Calling tool: {tool_name} with args: {arguments}")
            result = await self.mcp_client.call_tool(tool_name, arguments)
            
            # Convert CallToolResult to JSON-serializable format
            if hasattr(result, 'content'):
                # Extract content from MCP result
                result_data = []
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        result_data.append({
                            'type': 'text',
                            'text': content_item.text
                        })
                    else:
                        result_data.append(str(content_item))
                
                return web.json_response({
                    'tool': tool_name,
                    'result': result_data,
                    'isError': getattr(result, 'isError', False)
                })
            else:
                # Fallback: convert to string
                return web.json_response({
                    'tool': tool_name,
                    'result': str(result)
                })
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_health(self, request):
        """Handle GET /health - health check."""
        return web.json_response({
            'status': 'healthy',
            'mcp_connected': self.mcp_client is not None
        })
    
    async def handle_info(self, request):
        """Handle GET / - server info."""
        return web.json_response({
            'name': 'MCP HTTP Proxy',
            'description': 'HTTP proxy for Zenoo MCP Server (stdio backend)',
            'endpoints': {
                'GET /': 'Server info',
                'POST /': 'JSON-RPC (Letta format)',
                'POST /mcp': 'Streamable HTTP (Claude Code)',
                'GET /health': 'Health check',
                'GET /tools': 'List available tools',
                'POST /tools/{tool_name}': 'Call a tool',
            },
            'authentication': 'Bearer token' if self.api_key else 'None'
        })
    
    async def handle_root_post(self, request):
        """Handle POST / - MCP JSON-RPC protocol."""
        # Check authentication
        if not self.check_auth(request):
            logger.warning("POST / - Authentication failed")
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        try:
            # Get request body - MCP uses JSON-RPC format
            try:
                body = await request.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON body: {e}")
                text_body = await request.text()
                logger.error(f"Raw body: {text_body[:500]}")
                return web.json_response({
                    'jsonrpc': '2.0',
                    'error': {'code': -32700, 'message': f'Parse error: {str(e)}'},
                    'id': None
                }, status=400)
            
            logger.info(f"Received MCP JSON-RPC request: {body.get('method')} (id: {body.get('id')})")
            
            # Extract JSON-RPC fields
            method = body.get('method')
            params = body.get('params', {})
            request_id = body.get('id')
            
            # Handle MCP protocol methods
            if method == 'initialize':
                # MCP handshake
                logger.info("MCP initialize request")
                return web.json_response({
                    'jsonrpc': '2.0',
                    'result': {
                        'protocolVersion': '2024-11-05',
                        'capabilities': {
                            'tools': {}
                        },
                        'serverInfo': {
                            'name': 'zenoo-mcp-http-proxy',
                            'version': '1.0.0'
                        }
                    },
                    'id': request_id
                })
            
            elif method == 'tools/list':
                # List all tools
                logger.info("MCP tools/list request")
                result = await self.mcp_client.list_tools()
                
                # Handle both list and object with .tools attribute
                if isinstance(result, list):
                    tools = result
                elif hasattr(result, 'tools'):
                    tools = result.tools
                else:
                    logger.error(f"Unexpected result type from list_tools: {type(result)}")
                    tools = []
                
                return web.json_response({
                    'jsonrpc': '2.0',
                    'result': {
                        'tools': [
                            {
                                'name': tool.name,
                                'description': tool.description or '',
                                'inputSchema': tool.inputSchema
                            }
                            for tool in tools
                        ]
                    },
                    'id': request_id
                })
            
            elif method == 'tools/call':
                # Call a tool
                tool_name = params.get('name')
                arguments = params.get('arguments', {})
                
                if not tool_name:
                    logger.error(f"Missing tool name in tools/call: {params}")
                    return web.json_response({
                        'jsonrpc': '2.0',
                        'error': {
                            'code': -32602,
                            'message': 'Invalid params: missing tool name'
                        },
                        'id': request_id
                    }, status=400)
                
                logger.info(f"MCP tools/call: {tool_name} with args: {arguments}")
                result = await self.mcp_client.call_tool(tool_name, arguments)
                
                # Convert CallToolResult to MCP format
                if hasattr(result, 'content'):
                    content = []
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            content.append({
                                'type': 'text',
                                'text': content_item.text
                            })
                        else:
                            content.append({
                                'type': 'text',
                                'text': str(content_item)
                            })
                    
                    return web.json_response({
                        'jsonrpc': '2.0',
                        'result': {
                            'content': content,
                            'isError': getattr(result, 'isError', False)
                        },
                        'id': request_id
                    })
                else:
                    return web.json_response({
                        'jsonrpc': '2.0',
                        'result': {
                            'content': [{'type': 'text', 'text': str(result)}]
                        },
                        'id': request_id
                    })
            
            elif method and method.startswith('notifications/'):
                # Handle notifications (no response needed)
                logger.info(f"Received notification: {method}")
                return web.Response(status=204)  # No content
            
            else:
                # Unknown method
                logger.warning(f"Unknown MCP method: {method}")
                return web.json_response({
                    'jsonrpc': '2.0',
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {method}'
                    },
                    'id': request_id
                }, status=404)

        except Exception as e:
            logger.error(f"Error in POST /: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({
                'jsonrpc': '2.0',
                'error': {
                    'code': -32603,
                    'message': str(e)
                },
                'id': body.get('id') if 'body' in locals() else None
            }, status=500)

    async def handle_mcp_streamable(self, request):
        """Handle POST /mcp - Streamable HTTP transport for Claude Code.

        This implements the MCP Streamable HTTP protocol that Claude Code expects.
        It handles JSON-RPC messages and returns responses in the expected format.
        """
        # Check authentication
        if not self.check_auth(request):
            logger.warning("POST /mcp - Authentication failed")
            return web.json_response({'error': 'Unauthorized'}, status=401)

        try:
            # Parse JSON-RPC request
            try:
                body = await request.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON body in /mcp: {e}")
                return web.json_response({
                    'jsonrpc': '2.0',
                    'error': {'code': -32700, 'message': f'Parse error: {str(e)}'},
                    'id': None
                }, status=400)

            logger.info(f"Streamable HTTP /mcp request: {body.get('method')} (id: {body.get('id')})")

            # Extract JSON-RPC fields
            method = body.get('method')
            params = body.get('params', {})
            request_id = body.get('id')

            # Handle MCP protocol methods
            if method == 'initialize':
                # Get client's requested protocol version and negotiate
                client_version = params.get('protocolVersion', '2024-11-05')
                # Support latest versions - use client's version if we support it
                supported_versions = ['2025-03-26', '2024-11-05', '2024-10-07']
                negotiated_version = client_version if client_version in supported_versions else '2024-11-05'

                logger.info(f"Streamable HTTP initialize request (client: {client_version}, negotiated: {negotiated_version})")
                return web.json_response({
                    'jsonrpc': '2.0',
                    'result': {
                        'protocolVersion': negotiated_version,
                        'capabilities': {
                            'tools': {'listChanged': False}
                        },
                        'serverInfo': {
                            'name': 'zenoo-mcp-server',
                            'version': '1.0.0'
                        }
                    },
                    'id': request_id
                })

            elif method == 'initialized':
                # Client acknowledges initialization
                logger.info("Streamable HTTP initialized notification")
                return web.Response(status=204)

            elif method == 'tools/list':
                logger.info("Streamable HTTP tools/list request")
                result = await self.mcp_client.list_tools()

                if isinstance(result, list):
                    tools = result
                elif hasattr(result, 'tools'):
                    tools = result.tools
                else:
                    tools = []

                return web.json_response({
                    'jsonrpc': '2.0',
                    'result': {
                        'tools': [
                            {
                                'name': tool.name,
                                'description': tool.description or '',
                                'inputSchema': tool.inputSchema
                            }
                            for tool in tools
                        ]
                    },
                    'id': request_id
                })

            elif method == 'tools/call':
                tool_name = params.get('name')
                arguments = params.get('arguments', {})

                if not tool_name:
                    return web.json_response({
                        'jsonrpc': '2.0',
                        'error': {
                            'code': -32602,
                            'message': 'Invalid params: missing tool name'
                        },
                        'id': request_id
                    }, status=400)

                logger.info(f"Streamable HTTP tools/call: {tool_name}")
                result = await self.mcp_client.call_tool(tool_name, arguments)

                # Convert result to MCP format
                if hasattr(result, 'content'):
                    content = []
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            content.append({
                                'type': 'text',
                                'text': content_item.text
                            })
                        else:
                            content.append({
                                'type': 'text',
                                'text': str(content_item)
                            })

                    return web.json_response({
                        'jsonrpc': '2.0',
                        'result': {
                            'content': content,
                            'isError': getattr(result, 'isError', False)
                        },
                        'id': request_id
                    })
                else:
                    return web.json_response({
                        'jsonrpc': '2.0',
                        'result': {
                            'content': [{'type': 'text', 'text': str(result)}]
                        },
                        'id': request_id
                    })

            elif method == 'ping':
                return web.json_response({
                    'jsonrpc': '2.0',
                    'result': {},
                    'id': request_id
                })

            elif method and method.startswith('notifications/'):
                logger.info(f"Streamable HTTP notification: {method}")
                return web.Response(status=204)

            else:
                logger.warning(f"Streamable HTTP unknown method: {method}")
                return web.json_response({
                    'jsonrpc': '2.0',
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {method}'
                    },
                    'id': request_id
                }, status=404)

        except Exception as e:
            logger.error(f"Error in POST /mcp: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({
                'jsonrpc': '2.0',
                'error': {
                    'code': -32603,
                    'message': str(e)
                },
                'id': body.get('id') if 'body' in locals() else None
            }, status=500)


async def create_app(api_key=None, python_path=None):
    """Create the web application."""
    proxy = MCPHttpProxy(api_key=api_key, python_path=python_path)
    
    # Initialize MCP client
    if not await proxy.initialize():
        raise RuntimeError("Failed to initialize MCP client")
    
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', proxy.handle_info)
    app.router.add_post('/', proxy.handle_root_post)  # Letta format (JSON-RPC)
    app.router.add_post('/mcp', proxy.handle_mcp_streamable)  # Claude Code format (Streamable HTTP)
    app.router.add_get('/health', proxy.handle_health)
    app.router.add_get('/tools', proxy.handle_list_tools)
    app.router.add_post('/tools/{tool_name}', proxy.handle_call_tool)
    
    # Cleanup on shutdown
    async def cleanup_context(app):
        yield
        await proxy.cleanup()
    
    app.cleanup_ctx.append(cleanup_context)
    
    return app


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='HTTP Proxy for MCP Server (stdio backend)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start using .env file (MCP_PORT and MCP_API_KEYS)
  python mcp_http_proxy.py

  # Override environment variables
  python mcp_http_proxy.py --port 9090 --api-key your-secret-key

Then expose with ngrok:
  ngrok http ${MCP_PORT}

Configure in Letta Cloud:
  URL: https://your-ngrok-url.ngrok.io
  Auth: Bearer Token
  Token: ${MCP_API_KEYS}
        """
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('MCP_PORT', '8080')),
        help='HTTP port (default: from MCP_PORT env or 8080)'
    )

    parser.add_argument(
        '--host',
        default=os.getenv('MCP_HOST', '0.0.0.0'),
        help='Host to bind to (default: from MCP_HOST env or 0.0.0.0)'
    )

    parser.add_argument(
        '--api-key',
        default=os.getenv('MCP_API_KEYS'),
        help='API key for Bearer token authentication (default: from MCP_API_KEYS env)'
    )
    
    parser.add_argument(
        '--python',
        help='Python executable path (default: current Python)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("  MCP HTTP PROXY SERVER")
    print("=" * 70)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Auth: {'Bearer Token' if args.api_key else 'None'}")
    print(f"Backend: stdio MCP server")
    print()
    print(f"Access at: http://{args.host}:{args.port}")
    print()
    print("Endpoints:")
    print("  POST /           - JSON-RPC (Letta format)")
    print("  POST /mcp        - Streamable HTTP (Claude Code)")
    print("  GET  /           - Server info")
    print("  GET  /health     - Health check")
    print("  GET  /tools      - List all tools")
    print("  POST /tools/{name} - Call a tool")
    print()
    if args.api_key:
        print("Authentication required:")
        print(f"  Authorization: Bearer {args.api_key}")
        print()
    print("=" * 70)
    print()
    
    try:
        web.run_app(
            create_app(api_key=args.api_key, python_path=args.python),
            host=args.host,
            port=args.port,
            print=lambda x: None  # Suppress default startup message
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Shutting down...")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
