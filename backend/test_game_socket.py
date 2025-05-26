import pytest
import httpx
from datetime import datetime

API_BASE_URL = "http://localhost:5000"  # عدّل الرابط حسب سيرفرك

@pytest.mark.asyncio
async def test_create_room_and_join_socket():
    # 1. إنشاء غرفة عبر API باستخدام المسار الصحيح
    async with httpx.AsyncClient() as client:
        room_name = f"Test Room {datetime.now().isoformat()}"
        create_room_payload = {
            "name": room_name,
            # يمكنك إضافة حقول أخرى إذا أردت مثل:
            # "description": "Test room description",
            # "is_private": False,
            # "max_players": 4,
        }
        response = await client.post(f"{API_BASE_URL}/create_room", json=create_room_payload)
        assert response.status_code == 200 or response.status_code == 201, f"Unexpected status code: {response.status_code}"
        data = response.json()
        assert "room_id" in data
        assert "vpn_hub" in data
        assert "vpn_username" in data
        assert "vpn_password" in data

    # 2. محاولة الانضمام لنفس الغرفة
    async with httpx.AsyncClient() as client:
        join_payload = {
            "room_id": data["room_id"]
        }
        response = await client.post(f"{API_BASE_URL}/join_room", json=join_payload)
        assert response.status_code == 200
        join_data = response.json()
        assert join_data["room_id"] == data["room_id"]
        assert "vpn_hub" in join_data
        assert "vpn_username" in join_data
        assert "vpn_password" in join_data
        assert "message" in join_data

    # 3. ترك الغرفة
    async with httpx.AsyncClient() as client:
        leave_payload = {
            "room_id": data["room_id"]
        }
        response = await client.post(f"{API_BASE_URL}/leave_room", json=leave_payload)
        assert response.status_code == 200
        leave_data = response.json()
        assert leave_data["message"] == "left"