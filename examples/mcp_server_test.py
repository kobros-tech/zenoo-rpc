#!/usr/bin/env python3
"""
Test script to verify MCP server functionality.

This script tests connecting to a running MCP server and exercising its tools.
Run your MCP server first:
    python -m zenoo_rpc.mcp_server.cli --transport http --host 0.0.0.0 --port 8000
"""

import asyncio
import json
from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType


async def test_http_mcp_server():
    """Test connection to HTTP MCP server."""
    print("🚀 Testing HTTP MCP Server Connection")
    print("=" * 60)
    
    # Configure connection to your running MCP server
    config = MCPServerConfig(
        name="zenoo-mcp-server",
        transport_type=MCPTransportType.HTTP,
        url="http://localhost:8000/mcp",  # Adjust if different
        timeout=30.0
    )
    
    try:
        # Create and connect client
        from zenoo_rpc.mcp.transport import MCPTransport
        transport = MCPTransport(config)
        
        async with MCPClient(transport) as client:
            print("✅ Connected to MCP server\n")
            
            # List available tools
            print("📋 Listing available tools...")
            tools = await client.list_tools()
            print(f"Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}")
                if hasattr(tool, 'description'):
                    print(f"    {tool.description[:100]}...")
            print()
            
            # List available resources
            print("📦 Listing available resources...")
            resources = await client.list_resources()
            print(f"Found {len(resources)} resources:")
            for resource in resources:
                if hasattr(resource, 'uri'):
                    print(f"  - {resource.uri}")
                    if hasattr(resource, 'name') and resource.name:
                        print(f"    {resource.name}")
            print()
            
            # Test a simple tool call - search_records
            print("🔍 Testing 'search_records' tool...")
            try:
                result = await client.call_tool(
                    "search_records",
                    {
                        "model": "res.partner",
                        "domain": [["is_company", "=", True]],
                        "fields": ["name", "email", "phone"],
                        "limit": 5
                    }
                )
                print("✅ Tool call successful!")
                print(f"Result: {json.dumps(result, indent=2, default=str)}")
            except Exception as e:
                print(f"❌ Tool call failed: {e}")
            print()
            
            # Test get_record tool
            print("📄 Testing 'get_record' tool...")
            try:
                result = await client.call_tool(
                    "get_record",
                    {
                        "model": "res.partner",
                        "record_id": 1,
                        "fields": ["name", "email"]
                    }
                )
                print("✅ Tool call successful!")
                print(f"Result: {json.dumps(result, indent=2, default=str)}")
            except Exception as e:
                print(f"❌ Tool call failed: {e}")
            print()
            
            # Test reading a resource
            print("📖 Testing resource access...")
            try:
                result = await client.read_resource("odoo://models")
                print("✅ Resource read successful!")
                print(f"Result: {str(result)[:500]}...")
            except Exception as e:
                print(f"❌ Resource read failed: {e}")
            print()
            
            print("=" * 60)
            print("✅ All MCP server tests completed!")
            
    except Exception as e:
        print(f"❌ Failed to connect to MCP server: {e}")
        print("\nTroubleshooting:")
        print("1. Is the MCP server running?")
        print("   python -m zenoo_rpc.mcp_server.cli --transport http --port 8000")
        print("2. Is the URL correct? (default: http://localhost:8000/mcp)")
        print("3. Check server logs for errors")
        return False
    
    return True


async def test_stdio_mcp_server():
    """Test connection to stdio MCP server (for Letta integration)."""
    print("\n🚀 Testing stdio MCP Server")
    print("=" * 60)
    print("Note: This starts a subprocess MCP server using stdio transport")
    print()
    
    # Configure stdio connection
    config = MCPServerConfig(
        name="zenoo-mcp-stdio",
        transport_type=MCPTransportType.STDIO,
        command="python",
        args=[
            "-m", "zenoo_rpc.mcp_server.cli",
            "--transport", "stdio",
            "--odoo-url", "http://localhost:8069",
            "--odoo-database", "demo",
            "--odoo-username", "admin",
            "--odoo-password", "admin"
        ],
        timeout=30.0
    )
    
    try:
        from zenoo_rpc.mcp.transport import MCPTransport
        transport = MCPTransport(config)
        
        async with MCPClient(transport) as client:
            print("✅ Connected to stdio MCP server\n")
            
            # List tools
            print("📋 Listing tools...")
            tools = await client.list_tools()
            print(f"Found {len(tools)} tools")
            for tool in tools[:5]:  # Show first 5
                print(f"  - {tool.name}")
            print()
            
            # Test a tool call
            print("🔍 Testing tool call...")
            result = await client.call_tool(
                "search_records",
                {
                    "model": "res.partner",
                    "domain": [],
                    "limit": 3
                }
            )
            print(f"✅ Success! Found {len(result.get('records', []))} records")
            print()
            
            print("=" * 60)
            print("✅ stdio MCP server test completed!")
            
    except Exception as e:
        print(f"❌ stdio MCP server test failed: {e}")
        print("\nThis is expected if you haven't configured Odoo credentials")
        print("or if Odoo is not running at http://localhost:8069")
        return False
    
    return True


async def check_server_availability():
    """Check if HTTP server is accessible."""
    import aiohttp
    
    print("🔍 Checking server availability...")
    print("=" * 60)
    
    urls_to_check = [
        "http://localhost:8000",
        "http://localhost:8000/mcp",
        "http://localhost:8000/health",  # If health endpoint exists
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in urls_to_check:
            try:
                async with session.get(url, timeout=5) as response:
                    print(f"✅ {url}: Status {response.status}")
            except Exception as e:
                print(f"❌ {url}: {type(e).__name__}")
    print()


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  ZENOO RPC MCP SERVER TEST SUITE")
    print("=" * 60 + "\n")
    
    # Check server availability first
    await check_server_availability()
    
    # Test HTTP server
    http_success = await test_http_mcp_server()
    
    # Optionally test stdio (uncomment if needed)
    # stdio_success = await test_stdio_mcp_server()
    
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    print(f"HTTP Server Test: {'✅ PASS' if http_success else '❌ FAIL'}")
    # print(f"stdio Server Test: {'✅ PASS' if stdio_success else '❌ FAIL'}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
