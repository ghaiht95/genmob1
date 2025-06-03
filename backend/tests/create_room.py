import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import AsyncClient
from fastapi import status
from app_setup import app
from database.database import get_db
from models import User
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import uuid
# Import jose.jwt explicitly to avoid conflicts with PyJWT (import jwt)
from jose import jwt as jose_jwt  
from config import settings
from sqlalchemy.future import select

# Print all routes
print("Available routes:")
for route in app.routes:
    print(f"- {route.path}")

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

@pytest.fixture
async def db_session():
    async for session in get_db():
        yield session

@pytest.fixture
async def custom_test_user(db_session: AsyncSession):
    # Create test user with unique email
    unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    test_user = User(
        username=f"testuser-{uuid.uuid4().hex[:8]}",
        email=unique_email,
        password_hash="hashed_password_here"
    )
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)
    return test_user

@pytest.fixture
async def custom_auth_headers(custom_test_user: User):
    # Create JWT token with email in sub claim to match friends.py implementation
    token_data = {
        "sub": custom_test_user.email,  # Using email as per friends.py implementation
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    
    # Debug: Print settings
    print("\nSettings Debug Info:")
    print(f"SECRET_KEY: {settings.SECRET_KEY}")
    print(f"ALGORITHM: {settings.ALGORITHM}")
    print(f"Token Data: {token_data}")
    
    token = jose_jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    # Debug: Print token and decoded contents
    print("\nToken Debug Info:")
    print(f"Token: {token}")
    try:
        decoded = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print(f"Decoded token: {decoded}")
    except Exception as e:
        print(f"Error decoding token: {e}")
    
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_create_room_success(async_client, custom_test_user, db_session, custom_auth_headers):
    room_data = {
        "name": f"TestRoom-{uuid.uuid4().hex[:8]}",  # Make room name unique too
        "description": "Test room description",
        "is_private": False,
        "max_players": 4
    }
    
    # Print debug information
    print("\nTest Debug Info:")
    print(f"Auth Headers: {custom_auth_headers}")
    print(f"Room Data: {room_data}")
    print(f"Test User Email: {custom_test_user.email}")
    print(f"Test User Username: {custom_test_user.username}")
    
    response = await async_client.post("/rooms/create_room", json=room_data, headers=custom_auth_headers)
    
    print("\nResponse Info:")
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] is not None
    assert data["room_id"] is not None
    assert data["network_name"] is not None 