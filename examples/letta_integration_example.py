#!/usr/bin/env python3
"""
Example of integrating Zenoo RPC MCP Server with Letta AI.

This demonstrates how to configure and use Zenoo MCP tools within Letta.
"""

import asyncio
import json
import os


def create_letta_config():
    """Create Letta MCP server configuration."""
    config = {
        "mcpServers": {
            "zenoo-odoo": {
                "command": "python",
                "args": [
                    "-m",
                    "zenoo_rpc.mcp_server.cli",
                    "--transport", "stdio",
                    "--odoo-url", os.getenv("ODOO_URL", "http://localhost:8069"),
                    "--odoo-database", os.getenv("ODOO_DATABASE", "demo"),
                    "--odoo-username", os.getenv("ODOO_USERNAME", "admin"),
                    "--odoo-password", os.getenv("ODOO_PASSWORD", "admin"),
                    "--log-level", "INFO"
                ],
                "env": {
                    "PYTHONPATH": os.getcwd()
                }
            }
        }
    }
    
    return config


def save_letta_config(config_path="~/.letta/mcp_servers.json"):
    """Save Letta MCP configuration to file."""
    config = create_letta_config()
    
    # Expand user path
    config_path = os.path.expanduser(config_path)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # Save configuration
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Saved Letta MCP configuration to: {config_path}")
    print("\nConfiguration:")
    print(json.dumps(config, indent=2))
    return config_path


async def test_letta_integration():
    """Test Letta integration with Zenoo MCP server."""
    print("🚀 Testing Letta Integration with Zenoo MCP")
    print("=" * 60)
    
    try:
        # Import Letta (install with: pip install letta)
        from letta import create_client
        from letta.schemas.mcp_server import MCPServer
        
        print("✅ Letta imports successful\n")
        
        # Create Letta client
        letta_client = create_client()
        print("✅ Connected to Letta\n")
        
        # Configure Zenoo MCP server
        zenoo_mcp = MCPServer(
            name="zenoo-odoo",
            command="python",
            args=[
                "-m", "zenoo_rpc.mcp_server.cli",
                "--transport", "stdio",
                "--odoo-url", os.getenv("ODOO_URL", "http://localhost:8069"),
                "--odoo-database", os.getenv("ODOO_DATABASE", "demo"),
                "--odoo-username", os.getenv("ODOO_USERNAME", "admin"),
                "--odoo-password", os.getenv("ODOO_PASSWORD", "admin"),
                "--log-level", "INFO"
            ]
        )
        
        # Add MCP server to Letta
        letta_client.add_mcp_server(zenoo_mcp)
        print("✅ Added Zenoo MCP server to Letta\n")
        
        # List available MCP servers
        servers = letta_client.list_mcp_servers()
        print(f"📋 Available MCP servers:")
        for server in servers:
            print(f"  - {server.name}")
        print()
        
        # Create an agent with Zenoo MCP tools
        agent = letta_client.create_agent(
            name="odoo-assistant",
            system="""You are an expert Odoo assistant with access to the Odoo database.
            You have the following capabilities:
            - Search for records in any Odoo model
            - Get detailed information about specific records
            - Create new records
            - Update existing records
            - Delete records
            - Perform complex searches and analytics
            
            Always provide clear, structured responses and confirm actions.""",
            mcp_servers=["zenoo-odoo"]
        )
        print(f"✅ Created agent: {agent.name}\n")
        
        # Test queries
        test_queries = [
            "List the first 3 companies in the database",
            "How many partners are in the database?",
            "Search for partners with 'admin' in their name",
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"Test {i}: {query}")
            print('='*60)
            
            try:
                response = await agent.send_message(query)
                print(f"Response: {response}")
            except Exception as e:
                print(f"❌ Query failed: {e}")
        
        print("\n" + "=" * 60)
        print("✅ Letta integration test completed!")
        
    except ImportError:
        print("❌ Letta is not installed")
        print("\nTo install Letta:")
        print("  pip install letta")
        print("\nOr install with optional dependencies:")
        print("  pip install 'letta[all]'")
        return False
    
    except Exception as e:
        print(f"❌ Letta integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_manual_connection():
    """
    Test manual connection to MCP server without Letta.
    
    This shows how the MCP protocol works directly.
    """
    print("\n🔧 Testing Manual MCP Connection")
    print("=" * 60)
    print("This test connects directly to the MCP server without Letta\n")
    
    from zenoo_rpc.mcp import MCPClient, MCPServerConfig, MCPTransportType
    from zenoo_rpc.mcp.transport import MCPTransport
    
    # Configure stdio connection (same as Letta would use)
    config = MCPServerConfig(
        name="zenoo-odoo-manual",
        transport_type=MCPTransportType.STDIO,
        command="python",
        args=[
            "-m", "zenoo_rpc.mcp_server.cli",
            "--transport", "stdio",
            "--odoo-url", os.getenv("ODOO_URL", "http://localhost:8069"),
            "--odoo-database", os.getenv("ODOO_DATABASE", "demo"),
            "--odoo-username", os.getenv("ODOO_USERNAME", "admin"),
            "--odoo-password", os.getenv("ODOO_PASSWORD", "admin")
        ],
        timeout=30.0
    )
    
    try:
        transport = MCPTransport(config)
        
        async with MCPClient(transport) as client:
            print("✅ Connected via stdio\n")
            
            # List tools
            tools = await client.list_tools()
            print(f"📋 Available tools: {len(tools)}")
            for tool in tools[:3]:  # Show first 3
                print(f"  - {tool.name}")
            print()
            
            # Test search_records
            print("🔍 Testing search_records tool...")
            result = await client.call_tool(
                "search_records",
                {
                    "model": "res.partner",
                    "domain": [["is_company", "=", True]],
                    "limit": 2
                }
            )
            print(f"✅ Found {result.get('count', 0)} records")
            if 'records' in result and result['records']:
                print(f"Sample record: {result['records'][0].get('name', 'N/A')}")
            print()
            
            print("=" * 60)
            print("✅ Manual connection test completed!")
            
    except Exception as e:
        print(f"❌ Manual connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Is Odoo running at the configured URL?")
        print("2. Are the credentials correct?")
        print("3. Is the database accessible?")
        return False
    
    return True


def print_setup_instructions():
    """Print setup instructions for Letta integration."""
    print("\n" + "=" * 60)
    print("  LETTA + ZENOO MCP INTEGRATION SETUP")
    print("=" * 60)
    print()
    print("Follow these steps to integrate Zenoo MCP with Letta:")
    print()
    print("1. Install Letta:")
    print("   pip install letta")
    print()
    print("2. Set environment variables for Odoo connection:")
    print("   export ODOO_URL=http://localhost:8069")
    print("   export ODOO_DATABASE=demo")
    print("   export ODOO_USERNAME=admin")
    print("   export ODOO_PASSWORD=admin")
    print()
    print("3. Create Letta MCP configuration:")
    print("   python examples/letta_integration_example.py --save-config")
    print()
    print("4. Start Letta with MCP support:")
    print("   letta run")
    print()
    print("5. Test the integration:")
    print("   python examples/letta_integration_example.py --test")
    print()
    print("=" * 60)
    print()


async def main():
    """Main function."""
    import sys
    
    if "--save-config" in sys.argv:
        # Save Letta configuration
        config_path = save_letta_config()
        print(f"\nNext steps:")
        print(f"1. Review the configuration at: {config_path}")
        print(f"2. Adjust Odoo credentials if needed")
        print(f"3. Run: python {__file__} --test")
        return
    
    if "--test" in sys.argv:
        # Test Letta integration
        await test_letta_integration()
        return
    
    if "--manual" in sys.argv:
        # Test manual connection
        await test_manual_connection()
        return
    
    # Show instructions
    print_setup_instructions()
    
    # Offer to run tests
    print("Would you like to:")
    print("  1. Save Letta configuration")
    print("  2. Test manual MCP connection")
    print("  3. Test Letta integration")
    print("  4. Exit")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        save_letta_config()
    elif choice == "2":
        await test_manual_connection()
    elif choice == "3":
        await test_letta_integration()
    else:
        print("Exiting...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
