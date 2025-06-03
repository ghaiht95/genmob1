import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from httpx import AsyncClient
import uuid
from jose import jwt as jose_jwt

from app_setup import app
from database.database import get_db
from models import User, Room, RoomPlayer, network_config
from config import settings


@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def test_db_session():
    async for session in get_db():
        yield session


@pytest_asyncio.fixture
async def custom_test_user(test_db_session: AsyncSession):
    """Create a custom test user for join room tests"""
    unique_suffix = str(uuid.uuid4())[:8]
    
    user = User(
        username=f"testuser-{unique_suffix}",
        email=f"test-{unique_suffix}@example.com", 
        password_hash="fake_hash",
        private_key=b"gKXaG+2tpyariT8yZidbHPHeuxPs7iNuhekKRsMjiVg=",
        public_key=b"dgFsaavncOS7WAH3JhcD/hIMP41AMNKSmNAJ36f2OnI="
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def second_test_user(test_db_session: AsyncSession):
    """Create a second test user for join room tests"""
    unique_suffix = str(uuid.uuid4())[:8]
    
    user = User(
        username=f"testuser2-{unique_suffix}",
        email=f"test2-{unique_suffix}@example.com",
        password_hash="fake_hash",
        private_key=b"4E6frdNLenqzlsR1bCgl5RWZFYlSsH8Q6Yw8CbVmX2M=",
        public_key=b"UOQ8Bd0ga992NBV0NxgIQCrnBtr8Ds7x/j48uRWYync="
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def custom_auth_headers(custom_test_user: User):
    """Create auth headers for the custom test user"""
    token_data = {"sub": custom_test_user.email}
    token = jose_jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_auth_headers(second_test_user: User):
    """Create auth headers for the second test user"""
    token_data = {"sub": second_test_user.email}
    token = jose_jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_room_with_network(test_db_session: AsyncSession, custom_test_user: User, async_client: AsyncClient, custom_auth_headers: dict):
    """Create a test room with associated network config using the actual create_room endpoint"""
    
    # Use the actual create_room endpoint to create a real room with VPN
    room_data = {
        "name": f"TestRoom-{uuid.uuid4().hex[:8]}",
        "description": "Test room for join tests",
        "is_private": False,
        "max_players": 4
    }
    
    response = await async_client.post("/rooms/create_room", json=room_data, headers=custom_auth_headers)
    assert response.status_code == 200
    
    room_response = response.json()
    room_id = room_response["room_id"]
    
    # Get the room from database
    result = await test_db_session.execute(select(Room).filter_by(id=room_id))
    room = result.scalars().first()
    await test_db_session.refresh(room)
    return room


@pytest_asyncio.fixture
async def private_test_room(test_db_session: AsyncSession, custom_test_user: User, async_client: AsyncClient, custom_auth_headers: dict):
    """Create a private test room with password using the actual create_room endpoint"""
    
    # Use the actual create_room endpoint to create a real private room with VPN
    room_data = {
        "name": f"PrivateRoom-{uuid.uuid4().hex[:8]}",
        "description": "Private test room",
        "is_private": True,
        "password": "secret123",
        "max_players": 2
    }
    
    response = await async_client.post("/rooms/create_room", json=room_data, headers=custom_auth_headers)
    assert response.status_code == 200
    
    room_response = response.json()
    room_id = room_response["room_id"]
    
    # Get the room from database
    result = await test_db_session.execute(select(Room).filter_by(id=room_id))
    room = result.scalars().first()
    await test_db_session.refresh(room)
    return room


@pytest.mark.asyncio
async def test_join_room_success(
    async_client: AsyncClient,
    test_room_with_network: Room,
    second_test_user: User,
    second_auth_headers: dict,
    test_db_session: AsyncSession
):
    """Test successfully joining a room"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": test_room_with_network.id},
        headers=second_auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response data
    assert data["room_id"] == test_room_with_network.id
    assert data["message"] == "Joined room successfully"
    assert data["network_name"] == test_room_with_network.network_name
    assert "server_ip" in data
    assert "port" in data
    assert "server_public_key" in data  # Verify server public key is included
    assert "allowed_ips" in data  # Verify allowed IPs are included
    
    # Handle bytes vs string comparison for keys
    expected_private_key = second_test_user.private_key.decode() if isinstance(second_test_user.private_key, bytes) else second_test_user.private_key
    expected_public_key = second_test_user.public_key.decode() if isinstance(second_test_user.public_key, bytes) else second_test_user.public_key
    
    assert data["private_key"] == expected_private_key
    assert data["public_key"] == expected_public_key
    
    # Verify player was added to database
    result = await test_db_session.execute(
        select(RoomPlayer).filter_by(
            room_id=test_room_with_network.id,
            player_username=second_test_user.username
        )
    )
    player = result.scalars().first()
    assert player is not None
    assert player.is_host is False


@pytest.mark.asyncio
async def test_join_room_not_found(
    async_client: AsyncClient,
    second_auth_headers: dict
):
    """Test joining a non-existent room"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": 99999},
        headers=second_auth_headers
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"


@pytest.mark.asyncio 
async def test_join_room_missing_room_id(
    async_client: AsyncClient,
    second_auth_headers: dict
):
    """Test joining room without providing room_id"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={},
        headers=second_auth_headers
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Room ID is required"


@pytest.mark.asyncio
async def test_join_private_room_with_correct_password(
    async_client: AsyncClient,
    private_test_room: Room,
    second_test_user: User,
    second_auth_headers: dict,
    test_db_session: AsyncSession
):
    """Test joining a private room with correct password"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={
            "room_id": private_test_room.id,
            "password": "secret123"
        },
        headers=second_auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["room_id"] == private_test_room.id
    assert data["message"] == "Joined room successfully"


@pytest.mark.asyncio
async def test_join_private_room_with_wrong_password(
    async_client: AsyncClient,
    private_test_room: Room,
    second_auth_headers: dict
):
    """Test joining a private room with wrong password"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={
            "room_id": private_test_room.id,
            "password": "wrongpassword"
        },
        headers=second_auth_headers
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid room password"


@pytest.mark.asyncio
async def test_join_private_room_without_password(
    async_client: AsyncClient,
    private_test_room: Room,
    second_auth_headers: dict
):
    """Test joining a private room without providing password"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": private_test_room.id},
        headers=second_auth_headers
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid room password"


@pytest.mark.asyncio
async def test_join_room_already_in_room(
    async_client: AsyncClient,
    test_room_with_network: Room,
    custom_auth_headers: dict
):
    """Test joining a room when user is already in it"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": test_room_with_network.id},
        headers=custom_auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["room_id"] == test_room_with_network.id
    assert data["message"] == "You are already in this room. Using existing connection."
    assert data["network_name"] == test_room_with_network.network_name


@pytest.mark.asyncio
async def test_join_room_full(
    async_client: AsyncClient,
    test_db_session: AsyncSession,
    second_test_user: User,
    second_auth_headers: dict
):
    """Test joining a room that is full"""
    
    # Create a room with max 1 player and already has 1 player
    unique_suffix = str(uuid.uuid4())[:8]
    network_cfg = network_config(
        private_key=b"KHLUP2f1XVqzogTTlouGOSTaGAv7W+CovVgtPtJ69lE=",
        public_key=b"4LesyCxV4Ki/ryLYPIl6JRMg6qTuCs/RLaTQfs9JaGo=",
        server_ip="10.3.0.1/24",
        port=51822,
        is_active=True,
        network_name=f"wg-full-room-{unique_suffix}"
    )
    test_db_session.add(network_cfg)
    await test_db_session.flush()
    
    room = Room(
        name=f"Full Room {uuid.uuid4()}",
        owner_username=second_test_user.username,
        description="Full test room",
        is_private=False,
        max_players=1,  # Only 1 player allowed
        current_players=1,
        network_name=network_cfg.network_name
    )
    test_db_session.add(room)
    await test_db_session.flush()
    
    # Add owner as the only player
    owner_player = RoomPlayer(
        room_id=room.id,
        player_username=second_test_user.username,
        username=second_test_user.username,
        is_host=True
    )
    test_db_session.add(owner_player)
    await test_db_session.commit()
    
    # Create another user to try joining
    third_user = User(
        username=f"thirduser-{uuid.uuid4()}",
        email=f"third-{uuid.uuid4()}@example.com",
        password_hash="fake_hash",
        private_key=b"+PAuqXR0DEAo7W1vzMXIvUR1Va0bH7ZXYLdMYXVSTHw=",
        public_key=b"W0nRk9cLm1UnVuo8A7iZNXgsLL6pXQlzTxYUVDjQkwQ="
    )
    test_db_session.add(third_user)
    await test_db_session.commit()
    
    # Create auth headers for third user
    token_data = {"sub": third_user.email}
    token = jose_jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    third_auth_headers = {"Authorization": f"Bearer {token}"}
    
    response = await async_client.post(
        "/rooms/join_room", 
        json={"room_id": room.id},
        headers=third_auth_headers
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Room is full"


@pytest.mark.asyncio
async def test_join_room_unauthorized(
    async_client: AsyncClient,
    test_room_with_network: Room
):
    """Test joining room without authentication"""
    
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": test_room_with_network.id}
    )
    
    assert response.status_code == 401 