#!/usr/bin/env python3
"""
Simple script to list all available tools from a running MCP server.

Usage:
    # List tools from HTTP server
    python examples/list_mcp_tools.py

    # List tools with full details
    python examples/list_mcp_tools.py --verbose

    # Use custom URL
    python examples/list_mcp_tools.py --url http://localhost:8080/mcp
"""

import asyncio
import argparse
import sys
import json


async def list_tools_http(url: str, verbose: bool = False):
    """List tools from HTTP MCP server."""
    from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType
    from zenoo_rpc.mcp.transport import MCPTransport
    
    config = MCPServerConfig(
        name="zenoo-mcp",
        transport_type=MCPTransportType.HTTP,
        url=url,
        timeout=10.0
    )
    
    try:
        transport = MCPTransport(config)
        async with MCPClient(transport) as client:
            print(f"✅ Connected to MCP server at {url}\n")
            
            # Get tools
            tools = await client.list_tools()
            
            print(f"{'='*70}")
            print(f"  AVAILABLE TOOLS ({len(tools)} total)")
            print(f"{'='*70}\n")
            
            for i, tool in enumerate(tools, 1):
                print(f"{i}. {tool.name}")
                
                if verbose:
                    # Try to get description
                    if hasattr(tool, 'description') and tool.description:
                        desc = tool.description
                        # Wrap long descriptions
                        if len(desc) > 100:
                            desc = desc[:97] + "..."
                        print(f"   Description: {desc}")
                    
                    # Try to get input schema
                    if hasattr(tool, 'inputSchema'):
                        print(f"   Input Schema:")
                        schema = tool.inputSchema
                        if isinstance(schema, dict):
                            if 'properties' in schema:
                                print(f"   Parameters:")
                                for param_name, param_info in schema['properties'].items():
                                    param_type = param_info.get('type', 'any')
                                    param_desc = param_info.get('description', '')
                                    required = param_name in schema.get('required', [])
                                    req_marker = " (required)" if required else " (optional)"
                                    print(f"     - {param_name}: {param_type}{req_marker}")
                                    if param_desc:
                                        print(f"       {param_desc}")
                    print()
            
            # Get resources
            print(f"{'='*70}")
            print(f"  AVAILABLE RESOURCES")
            print(f"{'='*70}\n")
            
            resources = await client.list_resources()
            if resources:
                for i, resource in enumerate(resources, 1):
                    if hasattr(resource, 'uri'):
                        print(f"{i}. {resource.uri}")
                        if verbose and hasattr(resource, 'name') and resource.name:
                            print(f"   Name: {resource.name}")
                        if verbose and hasattr(resource, 'description') and resource.description:
                            print(f"   Description: {resource.description}")
                        print()
            else:
                print("No resources available\n")
            
            # Get prompts
            try:
                print(f"{'='*70}")
                print(f"  AVAILABLE PROMPTS")
                print(f"{'='*70}\n")
                
                prompts = await client.list_prompts()
                if prompts:
                    for i, prompt in enumerate(prompts, 1):
                        if hasattr(prompt, 'name'):
                            print(f"{i}. {prompt.name}")
                            if verbose and hasattr(prompt, 'description') and prompt.description:
                                print(f"   Description: {prompt.description}")
                            print()
                else:
                    print("No prompts available\n")
            except:
                print("Prompts not available from this server\n")
            
            print(f"{'='*70}")
            print(f"✅ Successfully listed all MCP capabilities")
            print(f"{'='*70}\n")
            
            return True
            
    except Exception as e:
        print(f"❌ Failed to connect to MCP server: {e}\n")
        print("Troubleshooting:")
        print(f"1. Is the server running at {url}?")
        print("2. Try starting it with:")
        print("   python -m zenoo_rpc.mcp_server.cli --transport http --port 8000")
        return False


async def test_tool_call(url: str, tool_name: str, arguments: dict):
    """Test calling a specific tool."""
    from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType
    from zenoo_rpc.mcp.transport import MCPTransport
    
    config = MCPServerConfig(
        name="zenoo-mcp",
        transport_type=MCPTransportType.HTTP,
        url=url,
        timeout=30.0
    )
    
    try:
        transport = MCPTransport(config)
        async with MCPClient(transport) as client:
            print(f"🔧 Testing tool: {tool_name}")
            print(f"Arguments: {json.dumps(arguments, indent=2)}\n")
            
            result = await client.call_tool(tool_name, arguments)
            
            print(f"✅ Tool call successful!")
            print(f"Result:")
            print(json.dumps(result, indent=2, default=str))
            
            return True
            
    except Exception as e:
        print(f"❌ Tool call failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="List and test tools from Zenoo MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all tools
  python examples/list_mcp_tools.py

  # List with verbose output
  python examples/list_mcp_tools.py --verbose

  # Use custom URL
  python examples/list_mcp_tools.py --url http://localhost:8080/mcp

  # Test a tool
  python examples/list_mcp_tools.py --test search_records --args '{"model":"res.partner","limit":3}'
        """
    )
    
    parser.add_argument(
        '--url',
        default='http://localhost:8000/mcp',
        help='MCP server URL (default: http://localhost:8000/mcp)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information about tools'
    )
    
    parser.add_argument(
        '--test',
        metavar='TOOL_NAME',
        help='Test calling a specific tool'
    )
    
    parser.add_argument(
        '--args',
        metavar='JSON',
        help='JSON arguments for tool test'
    )
    
    return parser.parse_args()


async def main():
    """Main function."""
    args = parse_args()
    
    print(f"\n{'='*70}")
    print(f"  ZENOO RPC MCP TOOL INSPECTOR")
    print(f"{'='*70}\n")
    
    if args.test:
        # Test a specific tool
        if not args.args:
            print("❌ --args required when using --test")
            sys.exit(1)
        
        try:
            arguments = json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in --args: {e}")
            sys.exit(1)
        
        success = await test_tool_call(args.url, args.test, arguments)
        sys.exit(0 if success else 1)
    
    else:
        # List all tools
        success = await list_tools_http(args.url, args.verbose)
        
        if success and not args.verbose:
            print("💡 Tip: Use --verbose for more details about each tool")
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
