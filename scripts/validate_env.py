#!/usr/bin/env python3
"""
Environment Validation Script for Zenoo-RPC

This script validates that all required environment variables are properly
configured for zenoo-rpc testing and development.
"""

import os
import sys
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
import requests


class EnvironmentValidator:
    """Validates environment configuration for zenoo-rpc."""
    
    def __init__(self):
        """Initialize environment validator."""
        # ODOO_URL is preferred, ODOO_HOST is legacy fallback
        self.required_vars = [
            ("ODOO_URL", "ODOO_HOST"),  # tuple = alternatives (first preferred)
            "ODOO_DATABASE",
            "ODOO_USERNAME",
            "ODOO_PASSWORD"
        ]
        
        self.optional_vars = [
            "REDIS_URL",
            "ENVIRONMENT",
            "LOG_LEVEL",
            "CACHE_BACKEND",
            "CACHE_TTL"
        ]
        
        self.validation_results = []
    
    def validate_all(self) -> bool:
        """Validate all environment configuration."""
        print("🔍 ZENOO-RPC ENVIRONMENT VALIDATION")
        print("=" * 50)
        
        # Check required variables
        required_ok = self._validate_required_vars()
        
        # Check optional variables
        self._validate_optional_vars()
        
        # Validate Odoo configuration
        odoo_ok = self._validate_odoo_config()
        
        # Validate Redis configuration (if configured)
        redis_ok = self._validate_redis_config()
        
        # Display results
        self._display_results()
        
        # Overall status
        overall_ok = required_ok and odoo_ok
        
        if overall_ok:
            print("\n✅ Environment validation PASSED")
            print("🚀 Ready for zenoo-rpc testing!")
        else:
            print("\n❌ Environment validation FAILED")
            print("🔧 Please fix the issues above before proceeding")
        
        return overall_ok
    
    def _validate_required_vars(self) -> bool:
        """Validate required environment variables."""
        print("\n📋 Required Environment Variables:")

        all_present = True

        for var in self.required_vars:
            # Handle alternative variable names (tuple)
            if isinstance(var, tuple):
                # Try each alternative in order
                found_var = None
                found_value = None
                for alt_var in var:
                    value = os.getenv(alt_var)
                    if value:
                        found_var = alt_var
                        found_value = value
                        break

                if found_value:
                    display_value = "***" if "PASSWORD" in found_var else found_value
                    alt_info = f" (or {var[1]})" if found_var == var[0] else f" (legacy, prefer {var[0]})"
                    print(f"   ✅ {found_var}{alt_info}: {display_value}")
                    self.validation_results.append((found_var, True, "Set"))
                else:
                    print(f"   ❌ {var[0]} (or {var[1]}): Not set")
                    self.validation_results.append((var[0], False, "Missing"))
                    all_present = False
            else:
                value = os.getenv(var)

                if value:
                    # Mask password for display
                    display_value = "***" if "PASSWORD" in var else value
                    print(f"   ✅ {var}: {display_value}")
                    self.validation_results.append((var, True, "Set"))
                else:
                    print(f"   ❌ {var}: Not set")
                    self.validation_results.append((var, False, "Missing"))
                    all_present = False

        return all_present
    
    def _validate_optional_vars(self):
        """Validate optional environment variables."""
        print("\n📋 Optional Environment Variables:")
        
        for var in self.optional_vars:
            value = os.getenv(var)
            
            if value:
                print(f"   ✅ {var}: {value}")
                self.validation_results.append((var, True, "Set"))
            else:
                print(f"   ⚪ {var}: Using default")
                self.validation_results.append((var, True, "Default"))
    
    def _validate_odoo_config(self) -> bool:
        """Validate Odoo server configuration."""
        print("\n🔗 Odoo Server Configuration:")

        # Support both ODOO_URL (preferred) and ODOO_HOST (legacy)
        host = os.getenv("ODOO_URL") or os.getenv("ODOO_HOST")
        database = os.getenv("ODOO_DATABASE")
        username = os.getenv("ODOO_USERNAME")
        password = os.getenv("ODOO_PASSWORD")

        if not all([host, database, username, password]):
            print("   ❌ Missing required Odoo configuration")
            return False

        # Validate URL format
        try:
            parsed = urlparse(host)
            if not parsed.scheme or not parsed.netloc:
                print(f"   ❌ Invalid Odoo URL format: {host}")
                return False

            print(f"   ✅ Host URL format: Valid")

        except Exception as e:
            print(f"   ❌ Invalid Odoo URL: {e}")
            return False
        
        # Test connectivity (optional)
        connectivity_ok = self._test_odoo_connectivity(host)
        
        # Validate database name
        if len(database) < 1:
            print(f"   ❌ Database name too short: {database}")
            return False
        
        print(f"   ✅ Database name: Valid")
        
        # Validate username
        if len(username) < 1:
            print(f"   ❌ Username too short: {username}")
            return False
        
        print(f"   ✅ Username: Valid")
        
        # Validate password strength
        password_ok = self._validate_password_strength(password)
        
        return connectivity_ok and password_ok
    
    def _test_odoo_connectivity(self, host: str) -> bool:
        """Test connectivity to Odoo server."""
        try:
            print(f"   🔍 Testing connectivity to {host}...")
            
            # Test basic connectivity
            response = requests.get(f"{host}/web/database/selector", timeout=10)
            
            if response.status_code in [200, 303, 404]:  # 404 is OK for some Odoo setups
                print(f"   ✅ Server connectivity: OK")
                return True
            else:
                print(f"   ⚠️  Server responded with status {response.status_code}")
                return True  # Don't fail validation for this
                
        except requests.exceptions.Timeout:
            print(f"   ⚠️  Connection timeout (server may be slow)")
            return True  # Don't fail validation for timeout
            
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Cannot connect to server")
            return False
            
        except Exception as e:
            print(f"   ⚠️  Connectivity test failed: {e}")
            return True  # Don't fail validation for unexpected errors
    
    def _validate_password_strength(self, password: str) -> bool:
        """Validate password strength."""
        if len(password) < 4:
            print(f"   ⚠️  Password is very short (consider using a stronger password)")
            return True  # Don't fail validation, just warn
        
        if password in ["admin", "password", "123456", "demo"]:
            print(f"   ⚠️  Using common password (consider using a stronger password)")
            return True  # Don't fail validation, just warn
        
        print(f"   ✅ Password: Acceptable")
        return True
    
    def _validate_redis_config(self) -> bool:
        """Validate Redis configuration if present."""
        redis_url = os.getenv("REDIS_URL")
        
        if not redis_url:
            print("\n📋 Redis Configuration: Not configured (using memory cache)")
            return True
        
        print("\n📋 Redis Configuration:")
        
        try:
            parsed = urlparse(redis_url)
            
            if parsed.scheme != "redis":
                print(f"   ❌ Invalid Redis URL scheme: {parsed.scheme}")
                return False
            
            print(f"   ✅ Redis URL format: Valid")
            
            # Test Redis connectivity (optional)
            redis_ok = self._test_redis_connectivity(redis_url)
            
            return redis_ok
            
        except Exception as e:
            print(f"   ❌ Invalid Redis URL: {e}")
            return False
    
    def _test_redis_connectivity(self, redis_url: str) -> bool:
        """Test Redis connectivity."""
        try:
            import redis
            
            print(f"   🔍 Testing Redis connectivity...")
            
            client = redis.from_url(redis_url)
            client.ping()
            client.close()
            
            print(f"   ✅ Redis connectivity: OK")
            return True
            
        except ImportError:
            print(f"   ⚠️  Redis library not installed (pip install redis)")
            return True  # Don't fail validation
            
        except Exception as e:
            print(f"   ❌ Redis connection failed: {e}")
            return False
    
    def _display_results(self):
        """Display validation results summary."""
        print("\n📊 Validation Summary:")
        
        passed = sum(1 for _, ok, _ in self.validation_results if ok)
        total = len(self.validation_results)
        
        print(f"   Variables checked: {total}")
        print(f"   Passed: {passed}")
        print(f"   Failed: {total - passed}")
    
    def generate_env_template(self) -> str:
        """Generate .env template based on current configuration."""
        template = """# Zenoo-RPC Environment Configuration
# Generated by validate_env.py

# Required Odoo Configuration
ODOO_URL=https://demo.odoo.com
ODOO_DATABASE=demo_database
ODOO_USERNAME=demo_user
ODOO_PASSWORD=demo_password

# Optional Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
CACHE_BACKEND=memory
CACHE_TTL=300

# Redis Configuration (optional)
# REDIS_URL=redis://localhost:6379/0

# Testing Configuration
USE_REAL_SERVER=false
"""
        return template


def main():
    """Main function."""
    validator = EnvironmentValidator()
    
    # Check if .env file exists
    if os.path.exists(".env"):
        print("📁 Found .env file")
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✅ Loaded .env file")
        except ImportError:
            print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    else:
        print("📁 No .env file found (using system environment variables)")
    
    # Run validation
    success = validator.validate_all()
    
    # Offer to generate template
    if not success:
        print("\n💡 Quick Setup:")
        print("1. Copy .env.example to .env: cp .env.example .env")
        print("2. Edit .env with your actual values")
        print("3. Run this script again to validate")
        
        response = input("\nGenerate basic .env template? (y/n): ")
        if response.lower() in ['y', 'yes']:
            template = validator.generate_env_template()
            with open('.env', 'w') as f:
                f.write(template)
            print("✅ Generated .env template")
            print("🔧 Please edit .env with your actual values")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
