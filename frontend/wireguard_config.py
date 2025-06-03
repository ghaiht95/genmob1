#!/usr/bin/env python3
"""
WireGuard Configuration Utility
Helps find and configure WireGuard executable path for the VPN Manager
"""

import os
import json
from vpn_manager import VPNManager

CONFIG_FILE = "wireguard_config.json"

def load_config():
    """Load WireGuard configuration"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(config):
    """Save WireGuard configuration"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Failed to save config: {e}")
        return False

def find_and_configure_wireguard():
    """Interactive WireGuard configuration"""
    print("🔧 WireGuard Configuration Utility")
    print("=" * 50)
    
    # Load existing config
    config = load_config()
    current_path = config.get('wireguard_path', '')
    
    if current_path:
        print(f"📁 Current configured path: {current_path}")
        if os.path.exists(current_path):
            print("✅ Current path is valid")
        else:
            print("❌ Current path is invalid")
        print()
    
    # Search for installations
    print("🔍 Searching for WireGuard installations...")
    installations = VPNManager.find_wireguard_installations()
    
    if installations:
        print(f"\n📋 Found {len(installations)} installation(s):")
        for i, (path, description) in enumerate(installations, 1):
            print(f"  {i}. {description}")
            print(f"     {path}")
        
        print(f"\n🎯 Options:")
        for i in range(1, len(installations) + 1):
            print(f"  {i} - Use installation #{i}")
        print(f"  c - Enter custom path")
        print(f"  q - Quit without changes")
        
        choice = input("\n👉 Enter your choice: ").strip().lower()
        
        if choice == 'q':
            print("👋 No changes made")
            return
        elif choice == 'c':
            custom_path = input("📁 Enter custom WireGuard path: ").strip()
            if os.path.exists(custom_path):
                config['wireguard_path'] = custom_path
                if save_config(config):
                    print(f"✅ Configuration saved: {custom_path}")
                else:
                    print("❌ Failed to save configuration")
            else:
                print(f"❌ Invalid path: {custom_path}")
        elif choice.isdigit() and 1 <= int(choice) <= len(installations):
            selected_path = installations[int(choice) - 1][0]
            config['wireguard_path'] = selected_path
            if save_config(config):
                print(f"✅ Configuration saved: {selected_path}")
            else:
                print("❌ Failed to save configuration")
        else:
            print("❌ Invalid choice")
    else:
        print("\n📥 No WireGuard installations found!")
        print("Please download and install WireGuard from:")
        print("🌐 https://www.wireguard.com/install/")
        
        manual_path = input("\n📁 If you have WireGuard installed elsewhere, enter the full path to wireguard.exe (or press Enter to skip): ").strip()
        if manual_path and os.path.exists(manual_path):
            config['wireguard_path'] = manual_path
            if save_config(config):
                print(f"✅ Configuration saved: {manual_path}")
            else:
                print("❌ Failed to save configuration")

def test_wireguard_config():
    """Test the current WireGuard configuration"""
    print("🧪 Testing WireGuard Configuration")
    print("=" * 40)
    
    config = load_config()
    wireguard_path = config.get('wireguard_path', '')
    
    if not wireguard_path:
        print("❌ No WireGuard path configured")
        print("💡 Run configuration first")
        return False
    
    print(f"📁 Testing path: {wireguard_path}")
    
    if not os.path.exists(wireguard_path):
        print("❌ File does not exist")
        return False
    
    print("✅ File exists")
    
    # Create a test VPN manager
    room_data = {'vpn_info': {'network_name': 'test'}}
    vpn = VPNManager(room_data)
    vpn.set_wireguard_path(wireguard_path)
    
    if vpn._check_wireguard_available():
        print("✅ WireGuard configuration is valid!")
        return True
    else:
        print("❌ WireGuard configuration failed")
        return False

if __name__ == "__main__":
    while True:
        print("\n🔧 WireGuard Configuration Menu")
        print("1. Find and configure WireGuard")
        print("2. Test current configuration")
        print("3. Show current configuration")
        print("4. Exit")
        
        choice = input("\n👉 Enter your choice (1-4): ").strip()
        
        if choice == '1':
            find_and_configure_wireguard()
        elif choice == '2':
            test_wireguard_config()
        elif choice == '3':
            config = load_config()
            if config.get('wireguard_path'):
                print(f"📁 Current path: {config['wireguard_path']}")
                print(f"✅ Valid: {os.path.exists(config['wireguard_path'])}")
            else:
                print("❌ No configuration found")
        elif choice == '4':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-4.") 