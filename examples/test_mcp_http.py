#!/usr/bin/env python3
"""
Test MCP server using direct HTTP calls.

This script demonstrates how to interact with the MCP server
using HTTP requests and JSON-RPC protocol.

Usage:
    python examples/test_mcp_http.py
    python examples/test_mcp_http.py http://localhost:8080/mcp
"""

import requests
import json
import sys
import argparse
from typing import Optional, Dict, Any


class MCPHTTPClient:
    """Simple HTTP client for MCP protocol using JSON-RPC 2.0."""
    
    def __init__(self, base_url: str = "http://localhost:8000/mcp", api_key: str = None):
        """Initialize client.
        
        Args:
            base_url: Base URL of MCP server
            api_key: Optional API key for authentication
        """
        self.base_url = base_url
        self.request_id = 0
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set default headers
        if api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}"
            })
    
    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request to MCP server.
        
        Args:
            method: RPC method name (e.g., 'tools/list', 'tools/call')
            params: Optional parameters for the method
            
        Returns:
            Response result
            
        Raises:
            Exception: If request fails or server returns error
        """
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        try:
            response = self.session.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                error = result["error"]
                raise Exception(
                    f"MCP Error [{error.get('code')}]: {error.get('message')}\n"
                    f"Details: {error.get('data', {})}"
                )
            
            return result.get("result", {})
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP request failed: {e}") from e
    
    def list_tools(self) -> Dict[str, Any]:
        """List available tools from MCP server."""
        return self._send_request("tools/list")
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        return self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
    
    def list_resources(self) -> Dict[str, Any]:
        """List available resources from MCP server."""
        return self._send_request("resources/list")
    
    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource from MCP server.
        
        Args:
            uri: Resource URI (e.g., 'odoo://models')
            
        Returns:
            Resource content
        """
        return self._send_request("resources/read", {
            "uri": uri
        })
    
    def list_prompts(self) -> Dict[str, Any]:
        """List available prompts from MCP server."""
        return self._send_request("prompts/list")


def print_json(data: Any, title: str = None):
    """Pretty print JSON data."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    print(json.dumps(data, indent=2, default=str))
    print()


def test_list_tools(client: MCPHTTPClient):
    """Test listing tools."""
    print("\n" + "="*70)
    print("  TEST 1: List Available Tools")
    print("="*70)
    
    try:
        result = client.list_tools()
        tools = result.get("tools", [])
        
        print(f"\n✓ Found {len(tools)} tools:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.get('name', 'Unknown')}")
            desc = tool.get('description', '')
            if desc:
                # Truncate long descriptions
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                print(f"     {desc}")
        
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def test_search_records(client: MCPHTTPClient):
    """Test search_records tool."""
    print("\n" + "="*70)
    print("  TEST 2: Search Records (res.partner)")
    print("="*70)
    
    try:
        result = client.call_tool("search_records", {
            "model": "res.partner",
            "domain": [["is_company", "=", True]],
            "fields": ["name", "email", "phone"],
            "limit": 3
        })
        
        print("\n✓ Search successful!")
        print(f"  Found {result.get('count', 0)} records")
        
        records = result.get('records', [])
        for i, record in enumerate(records[:3], 1):
            print(f"\n  Record {i}:")
            print(f"    ID: {record.get('id')}")
            print(f"    Name: {record.get('name')}")
            print(f"    Email: {record.get('email', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def test_get_record(client: MCPHTTPClient):
    """Test get_record tool."""
    print("\n" + "="*70)
    print("  TEST 3: Get Specific Record")
    print("="*70)
    
    try:
        result = client.call_tool("get_record", {
            "model": "res.partner",
            "record_id": 1,
            "fields": ["name", "email", "phone", "website"]
        })
        
        print("\n✓ Record retrieved successfully!")
        record = result.get('record', {})
        print(f"  ID: {record.get('id')}")
        print(f"  Name: {record.get('name')}")
        print(f"  Email: {record.get('email', 'N/A')}")
        print(f"  Phone: {record.get('phone', 'N/A')}")
        print(f"  Website: {record.get('website', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def test_list_resources(client: MCPHTTPClient):
    """Test listing resources."""
    print("\n" + "="*70)
    print("  TEST 4: List Available Resources")
    print("="*70)
    
    try:
        result = client.list_resources()
        resources = result.get("resources", [])
        
        print(f"\n✓ Found {len(resources)} resources:")
        for i, resource in enumerate(resources, 1):
            uri = resource.get('uri', 'Unknown')
            name = resource.get('name', '')
            print(f"  {i}. {uri}")
            if name:
                print(f"     {name}")
        
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def test_complex_search(client: MCPHTTPClient):
    """Test complex_search tool."""
    print("\n" + "="*70)
    print("  TEST 5: Complex Search")
    print("="*70)
    
    try:
        result = client.call_tool("complex_search", {
            "model": "res.partner",
            "filters": {
                "is_company": True
            },
            "order_by": "name",
            "limit": 5
        })
        
        print("\n✓ Complex search successful!")
        print(f"  Found {result.get('count', 0)} records")
        
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return False


def run_all_tests(base_url: str = "http://localhost:8000/mcp", api_key: str = None, verbose: bool = False):
    """Run all HTTP tests."""
    print("\n" + "="*70)
    print("  MCP HTTP CLIENT TEST SUITE")
    print("="*70)
    print(f"Server URL: {base_url}")
    if api_key:
        print(f"API Key: {api_key[:10]}... (masked)")
    
    # Initialize client
    client = MCPHTTPClient(base_url, api_key)
    
    # Test connectivity
    print("\nTesting server connectivity...")
    try:
        # Try a simple request
        client.list_tools()
        print("✓ Server is accessible\n")
    except Exception as e:
        print(f"✗ Cannot connect to server: {e}")
        print("\nTroubleshooting:")
        print("1. Is the MCP server running?")
        print("   python -m zenoo_rpc.mcp_server.cli --transport http --port 8000")
        print(f"2. Is the URL correct? ({base_url})")
        print("3. Check server logs for errors")
        return False
    
    # Run tests
    tests = [
        ("List Tools", test_list_tools),
        ("Search Records", test_search_records),
        ("Get Record", test_get_record),
        ("List Resources", test_list_resources),
        ("Complex Search", test_complex_search),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func(client)
            results.append((test_name, success))
        except KeyboardInterrupt:
            print("\n\n⚠️  Tests interrupted by user")
            return False
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n  Total: {len(results)} tests")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Success Rate: {passed/len(results)*100:.1f}%")
    print("="*70 + "\n")
    
    return failed == 0


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test MCP server using HTTP/JSON-RPC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test default URL
  python examples/test_mcp_http.py

  # Test custom URL
  python examples/test_mcp_http.py --url http://localhost:8080/mcp

  # Verbose output
  python examples/test_mcp_http.py --verbose

  # Single tool test
  python examples/test_mcp_http.py --tool search_records \\
    --args '{"model":"res.partner","limit":5}'
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
        help='Show verbose output'
    )
    
    parser.add_argument(
        '--tool',
        help='Test a specific tool only'
    )
    
    parser.add_argument(
        '--args',
        help='JSON arguments for single tool test'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key for authentication (or set MCP_API_KEY env var)'
    )
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()
    
    # Get API key from args or environment
    import os
    api_key = args.api_key or os.getenv('MCP_API_KEY')
    
    if args.tool:
        # Single tool test
        if not args.args:
            print("Error: --args required when using --tool")
            sys.exit(1)
        
        try:
            arguments = json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --args: {e}")
            sys.exit(1)
        
        client = MCPHTTPClient(args.url, api_key)
        print(f"Testing tool: {args.tool}")
        print(f"Arguments: {json.dumps(arguments, indent=2)}\n")
        
        try:
            result = client.call_tool(args.tool, arguments)
            print("✓ Success!")
            print(json.dumps(result, indent=2, default=str))
            sys.exit(0)
        except Exception as e:
            print(f"✗ Failed: {e}")
            sys.exit(1)
    
    else:
        # Run all tests
        success = run_all_tests(args.url, api_key, args.verbose)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
