import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from httpx import AsyncClient
import uuid
from jose import jwt as jose_jwt

from app_setup import app
from database.database import get_db
from models import User, Room, RoomPlayer, network_config, network_config_user
from config import settings
from vpnserver.genrator import generate_wireguard_keys


@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def test_db_session():
    async for session in get_db():
        yield session


@pytest_asyncio.fixture
async def real_test_user(test_db_session: AsyncSession):
    """Create a test user with real WireGuard keys from the database"""
    unique_suffix = str(uuid.uuid4())[:8]
    
    # Generate real WireGuard keys
    private_key, public_key = generate_wireguard_keys()
    
    user = User(
        username=f"realuser-{unique_suffix}",
        email=f"real-{unique_suffix}@example.com",
        password_hash="hashed_password_here",
        private_key=private_key,
        public_key=public_key
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def second_real_user(test_db_session: AsyncSession):
    """Create a second test user with real WireGuard keys"""
    unique_suffix = str(uuid.uuid4())[:8]
    
    # Generate real WireGuard keys
    private_key, public_key = generate_wireguard_keys()
    
    user = User(
        username=f"realuser2-{unique_suffix}",
        email=f"real2-{unique_suffix}@example.com",
        password_hash="hashed_password_here",
        private_key=private_key,
        public_key=public_key
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def real_auth_headers(real_test_user: User):
    """Create auth headers for the real test user"""
    token_data = {"sub": real_test_user.email}
    token = jose_jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_real_auth_headers(second_real_user: User):
    """Create auth headers for the second real test user"""
    token_data = {"sub": second_real_user.email}
    token = jose_jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def real_room_with_vpn(test_db_session: AsyncSession, real_test_user: User, async_client: AsyncClient, real_auth_headers: dict):
    """Create a real room using the create_room endpoint with actual VPN"""
    
    room_data = {
        "name": f"RealRoom-{uuid.uuid4().hex[:8]}",
        "description": "Real room with VPN integration",
        "is_private": False,
        "max_players": 4
    }
    
    # Use the actual create_room endpoint
    response = await async_client.post("/rooms/create_room", json=room_data, headers=real_auth_headers)
    assert response.status_code == 200
    
    room_response = response.json()
    room_id = room_response["room_id"]
    
    # Get the room from database
    result = await test_db_session.execute(select(Room).filter_by(id=room_id))
    room = result.scalars().first()
    await test_db_session.refresh(room)
    
    print(f"🏠 Created room: {room.name} (ID: {room.id})")
    print(f"🔗 Network name: {room.network_name}")
    
    return room


@pytest.mark.asyncio
async def test_join_room_real_vpn_integration(
    async_client: AsyncClient,
    real_room_with_vpn: Room,
    second_real_user: User,
    second_real_auth_headers: dict,
    test_db_session: AsyncSession
):
    """Test joining a room with real VPN integration and database operations"""
    
    print(f"\n🧪 Testing join room with real user: {second_real_user.username}")
    print(f"📧 User email: {second_real_user.email}")
    print(f"🔑 User has private key: {bool(second_real_user.private_key)}")
    print(f"🗝️ User has public key: {bool(second_real_user.public_key)}")
    
    # Get network config before joining
    network_result = await test_db_session.execute(
        select(network_config).filter_by(network_name=real_room_with_vpn.network_name)
    )
    network_cfg = network_result.scalars().first()
    
    print(f"🌐 Network config found: {bool(network_cfg)}")
    if network_cfg:
        print(f"📡 Server IP: {network_cfg.server_ip}")
        print(f"🔌 Port: {network_cfg.port}")
        print(f"🏷️ Network name: {network_cfg.network_name}")
    
    # Join the room
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": real_room_with_vpn.id},
        headers=second_real_auth_headers
    )
    
    print(f"\n📤 Join room response status: {response.status_code}")
    
    assert response.status_code == 200
    data = response.json()
    
    print(f"✅ Response received:")
    print(f"   Room ID: {data['room_id']}")
    print(f"   Message: {data['message']}")
    print(f"   Network name: {data['network_name']}")
    print(f"   Server IP: {data['server_ip']}")
    print(f"   Port: {data['port']}")
    print(f"   Server public key length: {len(data['server_public_key']) if data.get('server_public_key') else 0}")
    print(f"   Private key length: {len(data['private_key']) if data['private_key'] else 0}")
    print(f"   Public key length: {len(data['public_key']) if data['public_key'] else 0}")
    print(f"   Allowed IPs: {data.get('allowed_ips')}")
    
    # Verify response data
    assert data["room_id"] == real_room_with_vpn.id
    assert data["message"] == "Joined room successfully"
    assert data["network_name"] == real_room_with_vpn.network_name
    
    # Verify server data from network config
    assert data["server_ip"] == network_cfg.server_ip
    assert data["port"] == network_cfg.port
    
    # Verify server public key from database
    expected_server_public_key = network_cfg.public_key.decode() if isinstance(network_cfg.public_key, bytes) else network_cfg.public_key
    assert data["server_public_key"] == expected_server_public_key
    
    # Verify user keys from database
    expected_private_key = second_real_user.private_key.decode() if isinstance(second_real_user.private_key, bytes) else second_real_user.private_key
    expected_public_key = second_real_user.public_key.decode() if isinstance(second_real_user.public_key, bytes) else second_real_user.public_key
    
    assert data["private_key"] == expected_private_key
    assert data["public_key"] == expected_public_key
    
    # Verify allowed IPs from database
    assert data["allowed_ips"] == network_user.allowed_ips
    
    # Verify player was added to database
    result = await test_db_session.execute(
        select(RoomPlayer).filter_by(
            room_id=real_room_with_vpn.id,
            player_username=second_real_user.username
        )
    )
    player = result.scalars().first()
    assert player is not None
    assert player.is_host is False
    
    print(f"👤 Player added to room: {player.username}")
    print(f"👑 Is host: {player.is_host}")
    
    # Verify network_config_user entry was created (allowed IPs generated)
    network_user_result = await test_db_session.execute(
        select(network_config_user).filter_by(
            network_config_id=network_cfg.id,
            user_id=second_real_user.id
        )
    )
    network_user = network_user_result.scalars().first()
    
    assert network_user is not None
    assert network_user.allowed_ips is not None
    
    print(f"🔗 VPN peer created:")
    print(f"   User ID: {network_user.user_id}")
    print(f"   Network Config ID: {network_user.network_config_id}")
    print(f"   Allowed IPs: {network_user.allowed_ips}")
    
    # Verify allowed IP format
    allowed_ip = network_user.allowed_ips
    assert "/" in allowed_ip  # Should be in CIDR format
    assert allowed_ip.startswith("10.0.0.")  # Should be in our IP range
    assert allowed_ip.endswith("/24")  # Should have /24 subnet
    
    print(f"✅ All tests passed! VPN integration working correctly.")


@pytest.mark.asyncio
async def test_join_room_user_already_has_vpn_config(
    async_client: AsyncClient,
    real_room_with_vpn: Room,
    second_real_user: User,
    second_real_auth_headers: dict,
    test_db_session: AsyncSession
):
    """Test joining room when user already has VPN config (should update, not duplicate)"""
    
    # Join room first time
    response1 = await async_client.post(
        "/rooms/join_room",
        json={"room_id": real_room_with_vpn.id},
        headers=second_real_auth_headers
    )
    assert response1.status_code == 200
    
    # Get network config
    network_result = await test_db_session.execute(
        select(network_config).filter_by(network_name=real_room_with_vpn.network_name)
    )
    network_cfg = network_result.scalars().first()
    
    # Check initial network_config_user entries
    initial_entries = await test_db_session.execute(
        select(network_config_user).filter_by(
            network_config_id=network_cfg.id,
            user_id=second_real_user.id
        )
    )
    initial_count = len(initial_entries.scalars().all())
    
    print(f"🔢 Initial VPN entries for user: {initial_count}")
    
    # Join room second time (should return existing connection)
    response2 = await async_client.post(
        "/rooms/join_room",
        json={"room_id": real_room_with_vpn.id},
        headers=second_real_auth_headers
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert "You are already in this room" in data2["message"]
    
    # Check that no duplicate entries were created
    final_entries = await test_db_session.execute(
        select(network_config_user).filter_by(
            network_config_id=network_cfg.id,
            user_id=second_real_user.id
        )
    )
    final_count = len(final_entries.scalars().all())
    
    print(f"🔢 Final VPN entries for user: {final_count}")
    assert final_count == initial_count  # Should not have duplicated
    
    print(f"✅ No duplicate VPN configs created")


@pytest.mark.asyncio 
async def test_join_room_verify_keys_from_database(
    async_client: AsyncClient,
    real_room_with_vpn: Room,
    second_real_user: User,
    second_real_auth_headers: dict,
    test_db_session: AsyncSession
):
    """Test that the join room API returns the exact keys stored in the database"""
    
    # Get user keys directly from database before API call
    user_result = await test_db_session.execute(
        select(User).filter_by(id=second_real_user.id)
    )
    db_user = user_result.scalars().first()
    
    print(f"🔑 Database user private key: {db_user.private_key}")
    print(f"🗝️ Database user public key: {db_user.public_key}")
    
    # Get network config keys from database
    network_result = await test_db_session.execute(
        select(network_config).filter_by(network_name=real_room_with_vpn.network_name)
    )
    network_cfg = network_result.scalars().first()
    
    print(f"📡 Database server private key: {network_cfg.private_key}")
    print(f"🏢 Database server public key: {network_cfg.public_key}")
    print(f"🌐 Database server IP: {network_cfg.server_ip}")
    print(f"🔌 Database server port: {network_cfg.port}")
    
    # Call join room API
    response = await async_client.post(
        "/rooms/join_room",
        json={"room_id": real_room_with_vpn.id},
        headers=second_real_auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify API returns exact same data as stored in database
    expected_private_key = db_user.private_key.decode() if isinstance(db_user.private_key, bytes) else db_user.private_key
    expected_public_key = db_user.public_key.decode() if isinstance(db_user.public_key, bytes) else db_user.public_key
    expected_server_public_key = network_cfg.public_key.decode() if isinstance(network_cfg.public_key, bytes) else network_cfg.public_key
    
    print(f"🔄 API returned private key: {data['private_key']}")
    print(f"🔄 API returned public key: {data['public_key']}")
    print(f"🔄 API returned server public key: {data['server_public_key']}")
    print(f"🔄 API returned server IP: {data['server_ip']}")
    print(f"🔄 API returned port: {data['port']}")
    print(f"🔄 API returned allowed IPs: {data.get('allowed_ips')}")
    
    # Get user's network config for allowed IPs verification
    user_network_result = await test_db_session.execute(
        select(network_config_user).filter_by(
            network_config_id=network_cfg.id,
            user_id=second_real_user.id
        )
    )
    user_network_cfg = user_network_result.scalars().first()
    
    # Assert exact matches
    assert data["private_key"] == expected_private_key, f"Private key mismatch! DB: {expected_private_key}, API: {data['private_key']}"
    assert data["public_key"] == expected_public_key, f"Public key mismatch! DB: {expected_public_key}, API: {data['public_key']}"
    assert data["server_public_key"] == expected_server_public_key, f"Server public key mismatch! DB: {expected_server_public_key}, API: {data['server_public_key']}"
    assert data["server_ip"] == network_cfg.server_ip, f"Server IP mismatch! DB: {network_cfg.server_ip}, API: {data['server_ip']}"
    assert data["port"] == network_cfg.port, f"Port mismatch! DB: {network_cfg.port}, API: {data['port']}"
    assert data["allowed_ips"] == user_network_cfg.allowed_ips, f"Allowed IPs mismatch! DB: {user_network_cfg.allowed_ips}, API: {data['allowed_ips']}"
    
    print(f"✅ All database values match API response exactly!") 