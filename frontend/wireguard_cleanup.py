#!/usr/bin/env python3
"""
WireGuard Cleanup Utility
Standalone script to clean up old WireGuard tunnel services
"""

import os
import sys
import subprocess
import logging

# Add current directory to path to import vpn_manager
sys.path.insert(0, os.path.dirname(__file__))

try:
    from vpn_manager import VPNManager
except ImportError:
    print("❌ Could not import VPNManager")
    print("💡 Make sure you're running this from the frontend directory")
    sys.exit(1)

def cleanup_all_wireguard_tunnels():
    """Clean up all WireGuard tunnels using VPNManager"""
    print("🧹 WireGuard Cleanup Utility")
    print("=" * 40)
    
    # Create a dummy VPN manager just to use its cleanup methods
    dummy_room_data = {'vpn_info': {'network_name': 'cleanup'}}
    vpn_manager = VPNManager(dummy_room_data)
    
    print("🔍 Scanning for WireGuard tunnel services...")
    
    # Get all services
    services = vpn_manager.get_all_wireguard_services()
    
    if not services:
        print("✅ No WireGuard tunnel services found")
        return True
    
    print(f"📋 Found {len(services)} WireGuard tunnel service(s):")
    for i, service in enumerate(services, 1):
        print(f"  {i}. {service}")
    
    # Ask for confirmation
    print(f"\n⚠️  This will stop and remove ALL WireGuard tunnel services listed above.")
    choice = input("🤔 Do you want to continue? (y/N): ").strip().lower()
    
    if choice not in ['y', 'yes']:
        print("❌ Operation cancelled")
        return False
    
    print("\n🚀 Starting cleanup process...")
    
    # Perform cleanup
    success = vpn_manager.cleanup_old_tunnels()
    
    if success:
        print("\n🎉 Cleanup completed successfully!")
        print("✅ All WireGuard tunnel services have been removed")
    else:
        print("\n⚠️ Cleanup completed with some errors")
        print("💡 Some services may require manual removal")
    
    return success

def list_wireguard_services():
    """List all WireGuard services without removing them"""
    print("📋 WireGuard Service Listing")
    print("=" * 30)
    
    try:
        cmd = 'sc query type= service state= all | findstr "WireGuard"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if result.returncode == 0 and result.stdout.strip():
            print("🔍 Found WireGuard services:")
            print(result.stdout)
        else:
            print("✅ No WireGuard services found")
            
    except Exception as e:
        print(f"❌ Error listing services: {e}")

def check_wireguard_installation():
    """Check WireGuard installation"""
    print("🔧 WireGuard Installation Check")
    print("=" * 35)
    
    dummy_room_data = {'vpn_info': {'network_name': 'test'}}
    vpn_manager = VPNManager(dummy_room_data)
    
    print(f"📁 WireGuard executable path: {vpn_manager.wireguard_exe}")
    
    if vpn_manager._check_wireguard_available():
        print("✅ WireGuard is properly installed and accessible")
    else:
        print("❌ WireGuard is not accessible")
        print("💡 Run 'python wireguard_config.py' to configure WireGuard path")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WireGuard Cleanup Utility")
    parser.add_argument("--list", action="store_true", help="List WireGuard services without removing")
    parser.add_argument("--check", action="store_true", help="Check WireGuard installation")
    parser.add_argument("--cleanup", action="store_true", help="Clean up all WireGuard tunnel services")
    parser.add_argument("--force", action="store_true", help="Force cleanup without confirmation")
    
    args = parser.parse_args()
    
    if args.list:
        list_wireguard_services()
    elif args.check:
        check_wireguard_installation()
    elif args.cleanup:
        if args.force:
            # Skip confirmation if --force is used
            dummy_room_data = {'vpn_info': {'network_name': 'cleanup'}}
            vpn_manager = VPNManager(dummy_room_data)
            print("🧹 Force cleanup mode - removing all WireGuard tunnels...")
            vpn_manager.cleanup_old_tunnels()
        else:
            cleanup_all_wireguard_tunnels()
    else:
        # Interactive mode
        while True:
            print("\n🔧 WireGuard Cleanup Utility")
            print("1. List WireGuard services")
            print("2. Check WireGuard installation") 
            print("3. Clean up all tunnel services")
            print("4. Exit")
            
            choice = input("\n👉 Enter your choice (1-4): ").strip()
            
            if choice == '1':
                list_wireguard_services()
            elif choice == '2':
                check_wireguard_installation()
            elif choice == '3':
                cleanup_all_wireguard_tunnels()
            elif choice == '4':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-4.") 