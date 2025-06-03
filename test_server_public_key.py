#!/usr/bin/env python3

import sys
import os
import time

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

import asyncio
import json
from httpx import AsyncClient
from app_setup import app

async def test_join_room_manually():
    """Manual test to verify join_room API returns server_public_key"""
    
    timestamp = str(int(time.time()))
    
    print("🧪 Testing join_room API manually...")
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        
        # First, create a user account 
        register_data = {
            "username": f"testuser{timestamp}",
            "email": f"test{timestamp}@example.com", 
            "password": "testpass123"
        }
        
        print("📝 Registering user...")
        register_response = await client.post("/auth/register", json=register_data)
        print(f"   Register status: {register_response.status_code}")
        
        if register_response.status_code in [200, 201]:  # Accept both 200 and 201
            # Login to get token
            login_data = {
                "username": f"testuser{timestamp}",  # Use actual username
                "password": "testpass123"
            }
            
            print("🔑 Logging in...")
            login_response = await client.post("/auth/token", data=login_data)
            print(f"   Login status: {login_response.status_code}")
            
            if login_response.status_code == 200:
                login_result = login_response.json()
                access_token = login_result["access_token"]
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # Create a room
                room_data = {
                    "name": f"TestRoom{timestamp}",
                    "description": "Test room for server public key",
                    "is_private": False,
                    "max_players": 4
                }
                
                print("🏠 Creating room...")
                room_response = await client.post("/rooms/create_room", json=room_data, headers=headers)
                print(f"   Create room status: {room_response.status_code}")
                
                if room_response.status_code == 200:
                    room_result = room_response.json()
                    room_id = room_result["room_id"]
                    
                    print(f"   Room ID: {room_id}")
                    print(f"   Network name: {room_result.get('network_name')}")
                    
                    # Now create a second user to join the room
                    register_data2 = {
                        "username": f"testuser{timestamp}b", 
                        "email": f"test{timestamp}b@example.com",
                        "password": "testpass456"
                    }
                    
                    print("📝 Registering second user...")
                    register2_response = await client.post("/auth/register", json=register_data2)
                    print(f"   Register2 status: {register2_response.status_code}")
                    
                    if register2_response.status_code in [200, 201]:  # Accept both 200 and 201
                        # Login second user
                        login_data2 = {
                            "username": f"testuser{timestamp}b",  # Use actual username
                            "password": "testpass456"
                        }
                        
                        print("🔑 Logging in second user...")
                        login2_response = await client.post("/auth/token", data=login_data2)
                        print(f"   Login2 status: {login2_response.status_code}")
                        
                        if login2_response.status_code == 200:
                            login2_result = login2_response.json()
                            access_token2 = login2_result["access_token"]
                            headers2 = {"Authorization": f"Bearer {access_token2}"}
                            
                            # Join the room
                            join_data = {"room_id": room_id}
                            
                            print("🚪 Joining room...")
                            join_response = await client.post("/rooms/join_room", json=join_data, headers=headers2)
                            print(f"   Join room status: {join_response.status_code}")
                            
                            if join_response.status_code == 200:
                                join_result = join_response.json()
                                
                                print("✅ Join room response:")
                                print(f"   Room ID: {join_result.get('room_id')}")
                                print(f"   Message: {join_result.get('message')}")
                                print(f"   Network name: {join_result.get('network_name')}")
                                print(f"   Server IP: {join_result.get('server_ip')}")
                                print(f"   Port: {join_result.get('port')}")
                                print(f"   Has server_public_key: {'server_public_key' in join_result}")
                                print(f"   Has allowed_ips: {'allowed_ips' in join_result}")
                                
                                if 'server_public_key' in join_result:
                                    print(f"   Server public key length: {len(join_result['server_public_key'])}")
                                    print(f"   Server public key: {join_result['server_public_key'][:20]}...")
                                    print("🎉 SUCCESS: Server public key is included!")
                                else:
                                    print("❌ FAILURE: Server public key is missing!")
                                
                                if 'allowed_ips' in join_result:
                                    print(f"   Allowed IPs: {join_result['allowed_ips']}")
                                    print("🎉 SUCCESS: Allowed IPs are included!")
                                else:
                                    print("❌ FAILURE: Allowed IPs are missing!")
                                    
                                print(f"   Has private_key: {'private_key' in join_result}")
                                print(f"   Has public_key: {'public_key' in join_result}")
                                    
                            else:
                                print(f"❌ Join room failed: {join_response.status_code}")
                                print(f"   Error: {join_response.text}")
                        else:
                            print(f"❌ Login2 failed: {login2_response.status_code}")
                    else:
                        print(f"❌ Register2 failed: {register2_response.status_code}")
                else:
                    print(f"❌ Create room failed: {room_response.status_code}")
                    print(f"   Error: {room_response.text}")
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                print(f"   Error: {login_response.text}")
        else:
            print(f"❌ Register failed: {register_response.status_code}")
            print(f"   Error: {register_response.text}")

if __name__ == "__main__":
    asyncio.run(test_join_room_manually()) 