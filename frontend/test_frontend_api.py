#!/usr/bin/env python3
"""
Test script to verify frontend API client works correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import api_client

def test_frontend_api():
    print("🧪 Testing Frontend API Client...")
    
    # Test 1: Check API client configuration
    print(f"📍 API Base URL: {api_client._base_url}")
    
    try:
        # Test 2: Create a user account
        import time
        timestamp = str(int(time.time()))
        
        register_data = {
            "username": f"testuser{timestamp}",
            "email": f"test{timestamp}@example.com", 
            "password": "testpass123"
        }
        
        print("📝 Registering user...")
        register_response = api_client.post("/auth/register", json=register_data)
        print(f"   Register response: {register_response}")
        
        # Test 3: Login
        login_data = {
            "username": register_data["username"],
            "password": register_data["password"]
        }
        
        print("🔑 Logging in...")
        login_response = api_client.post("/auth/token", data=login_data)
        print(f"   Login response keys: {list(login_response.keys())}")
        
        # Set token
        access_token = login_response["access_token"]
        api_client.set_token(access_token)
        print(f"   Token set: {access_token[:20]}...")
        
        # Test 4: Create room
        room_data = {
            "name": f"TestRoom{timestamp}",
            "description": "Test room",
            "is_private": False,
            "max_players": 4
        }
        
        print("🏠 Creating room...")
        create_response = api_client.post("/rooms/create_room", json=room_data)
        print(f"   Create response: {create_response}")
        
        # Test 5: Join room to get VPN data
        room_id = create_response.get("room_id") or create_response.get("id")
        print(f"🚪 Joining room {room_id}...")
        join_response = api_client.post("/rooms/join_room", json={"room_id": room_id})
        print(f"   Join response keys: {list(join_response.keys())}")
        
        # Check VPN data
        vpn_fields = ['network_name', 'private_key', 'public_key', 'server_public_key', 'server_ip', 'port', 'allowed_ips']
        print("\n🔒 VPN Data Check:")
        for field in vpn_fields:
            value = join_response.get(field)
            has_value = bool(value and value != "")
            print(f"   {field}: {'✅' if has_value else '❌'} {len(str(value)) if value else 0} chars")
            
        print(f"\n✅ Success! VPN data is {'available' if any(join_response.get(field) for field in vpn_fields) else 'missing'}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_frontend_api() 