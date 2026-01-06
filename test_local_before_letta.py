#!/usr/bin/env python3
"""
Test your MCP server locally before exposing to Letta Cloud.

This script connects to your MCP server using stdio subprocess
(which bypasses HTTP authentication) so you can list and test tools locally first.

Usage:
    # List all tools
    python test_local_before_letta.py

    # Test a specific tool
    python test_local_before_letta.py --test search_records
"""

import asyncio
import json
import sys
import os
import argparse


async def list_and_test_tools(test_tool=None):
    """List and optionally test MCP tools using stdio."""
    
    try:
        # Import here to give better error messages
        from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType
        from zenoo_rpc.mcp.transport import MCPTransport
    except ImportError as e:
        print(f"❌ Error: Cannot import zenoo_rpc modules")
        print(f"   {e}")
        print("\nMake sure you're in the virtualenv:")
        print("   source ../env/bin/activate  # or wherever your venv is")
        print("   pip install -e .")
        sys.exit(1)
    
    print("=" * 70)
    print("  TESTING MCP SERVER LOCALLY (via subprocess)")
    print("=" * 70)
    print("Using stdio transport (bypasses HTTP authentication)")
    print()
    
    # Get python path from current environment
    python_path = sys.executable
    
    # Prepare environment - disable auth for local stdio testing
    env_vars = os.environ.copy()
    env_vars['MCP_AUTH_METHOD'] = 'none'  # Disable authentication for local testing
    
    # Configure stdio connection (subprocess, no authentication needed)
    config = MCPServerConfig(
        name="zenoo-mcp-local-test",
        transport_type=MCPTransportType.STDIO,
        command=python_path,
        args=[
            "-m", "zenoo_rpc.mcp_server.cli",
            "--transport", "stdio"
        ],
        env=env_vars  # Pass environment with auth disabled
    )
    
    transport = MCPTransport(config)
    
    try:
        async with MCPClient(transport) as client:
            print("✓ Connected to MCP server!\n")
            
            # List all tools
            print("=" * 70)
            print("  AVAILABLE TOOLS (What Letta Cloud will see)")
            print("=" * 70)
            
            tools = await client.list_tools()
            
            if not tools:
                print("⚠️  No tools found!")
                return False
            
            print(f"\nFound {len(tools)} tools:\n")
            
            for i, tool in enumerate(tools, 1):
                print(f"{i}. {tool.name}")
                if hasattr(tool, 'description') and tool.description:
                    # Wrap description
                    desc = tool.description
                    if len(desc) > 70:
                        desc = desc[:67] + "..."
                    print(f"   {desc}")
                
                # Show parameters if available
                if hasattr(tool, 'inputSchema') and isinstance(tool.inputSchema, dict):
                    schema = tool.inputSchema
                    if 'properties' in schema:
                        print(f"   Parameters:")
                        for param_name, param_info in schema['properties'].items():
                            param_type = param_info.get('type', 'any')
                            required = param_name in schema.get('required', [])
                            req_marker = " (required)" if required else ""
                            print(f"     • {param_name}: {param_type}{req_marker}")
                print()
            
            # List resources
            print("=" * 70)
            print("  AVAILABLE RESOURCES")
            print("=" * 70)
            print()
            
            try:
                resources = await client.list_resources()
                if resources:
                    for i, resource in enumerate(resources, 1):
                        if hasattr(resource, 'uri'):
                            print(f"{i}. {resource.uri}")
                            if hasattr(resource, 'name') and resource.name:
                                print(f"   {resource.name}")
                    print()
                else:
                    print("No resources available\n")
            except Exception as e:
                print(f"Could not list resources: {e}\n")
            
            # Test a specific tool if requested
            if test_tool:
                print("=" * 70)
                print(f"  TESTING TOOL: {test_tool}")
                print("=" * 70)
                print()
                
                # Predefined test cases for common tools
                test_cases = {
                    "search_records": {
                        "model": "res.partner",
                        "domain": [],
                        "limit": 3
                    },
                    "get_record": {
                        "model": "res.partner",
                        "record_id": 1,
                        "fields": ["name", "email"]
                    },
                    "complex_search": {
                        "model": "res.partner",
                        "filters": {"is_company": True},
                        "limit": 3
                    }
                }
                
                if test_tool in test_cases:
                    args = test_cases[test_tool]
                    print(f"Test arguments:")
                    print(json.dumps(args, indent=2))
                    print()
                    
                    try:
                        result = await client.call_tool(test_tool, args)
                        print("✓ Tool call successful!")
                        print("\nResult:")
                        print(json.dumps(result, indent=2, default=str))
                    except Exception as e:
                        print(f"✗ Tool call failed: {e}")
                        import traceback
                        traceback.print_exc()
                        return False
                else:
                    print(f"⚠️  No predefined test case for '{test_tool}'")
                    print(f"Available test cases: {', '.join(test_cases.keys())}")
                    print()
            
            print("=" * 70)
            print("  SUMMARY")
            print("=" * 70)
            print()
            print("✓ Your MCP server is working correctly!")
            print(f"✓ {len(tools)} tools are available")
            print()
            print("These are the tools that Letta Cloud will see once exposed!")
            print()
            print("Next steps for Letta Cloud:")
            print("  1. Install ngrok: https://ngrok.com/download")
            print("  2. Run: ngrok http 8000  (in a separate terminal)")
            print("  3. Copy the HTTPS URL from ngrok")
            print("  4. Configure in Letta Cloud dashboard:")
            print("     - URL: [ngrok HTTPS URL]")
            print("     - Auth: Bearer Token")
            print("     - Token: letta-secret-123")
            print()
            print("See: docs/mcp-letta-cloud-integration.md for full guide")
            print()
            
            return True
            
    except Exception as e:
        print(f"❌ Failed to connect to MCP server: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check that you have the right Python environment")
        print(f"   Currently using: {python_path}")
        print()
        print("2. Check that zenoo_rpc is installed:")
        print("   pip install -e .")
        print()
        print("3. Check your Odoo credentials in environment variables:")
        print(f"   ODOO_URL: {os.getenv('ODOO_URL', 'not set')}")
        print(f"   ODOO_DATABASE: {os.getenv('ODOO_DATABASE', 'not set')}")
        print()
        
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test MCP server locally before exposing to Letta Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available tools
  python test_local_before_letta.py

  # Test a specific tool
  python test_local_before_letta.py --test search_records
  python test_local_before_letta.py --test get_record
        """
    )
    
    parser.add_argument(
        '--test',
        metavar='TOOL_NAME',
        help='Test a specific tool (search_records, get_record, complex_search)'
    )
    
    args = parser.parse_args()
    
    # Run the async function
    try:
        success = asyncio.run(list_and_test_tools(args.test))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
