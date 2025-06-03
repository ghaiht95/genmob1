"""
Tests for SocketIO events (sio_events.py)
Tests real-time communication functionality including:
- Connection/disconnection handling
- Room joining/leaving
- Chat messaging
- Heartbeat system
- Player management
- Game state events
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from models import Room, RoomPlayer, ChatMessage, User
from shared import sio, client_rooms, last_heartbeat
import sio_events
from database.database import get_db


@pytest.fixture
async def test_db_session():
    async for session in get_db():
        yield session

class TestSocketIOEvents:

    @pytest_asyncio.fixture
    async def test_user(self, test_db_session: AsyncSession):
        """Create a test user for SocketIO events"""
        from vpnserver.genrator import generate_wireguard_keys
        
        private_key, public_key = generate_wireguard_keys()
        user = User(
            username="socketio_user",
            email="socketio@example.com", 
            password="testpass123",
            private_key=private_key,
            public_key=public_key
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)
        return user

    @pytest_asyncio.fixture
    async def test_room_with_player(self, test_db_session: AsyncSession, test_user: User):
        """Create a test room with a player for SocketIO events"""
        from services.Wiregruad import WiregruadVPN
        
        # Create room
        vpn = WiregruadVPN()
        network_name = await vpn.create_network_config(test_db_session)
        
        room = Room(
            name="SocketIO Test Room",
            description="Test room for SocketIO events",
            owner_username=test_user.username,
            network_name=network_name,
            max_players=8,
            is_private=False
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)
        
        # Add player to room
        player = RoomPlayer(
            room_id=room.id,
            player_username=test_user.username,
            is_host=True
        )
        test_db_session.add(player)
        await test_db_session.commit()
        
        return room, player

    @pytest.mark.asyncio
    async def test_connect_event(self):
        """Test SocketIO connect event"""
        sid = "test_sid_123"
        environ = {"HTTP_HOST": "localhost"}
        
        # Mock sio.emit
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await sio_events.connect(sid, environ)
            
            # Verify server_ready event was emitted
            mock_emit.assert_called_once()
            args, kwargs = mock_emit.call_args
            
            assert args[0] == "server_ready"
            assert "message" in args[1]
            assert "timestamp" in args[1]
            assert kwargs["to"] == sid
            assert kwargs["namespace"] == "/game"
            
            # Verify heartbeat was initialized
            assert sid in last_heartbeat
            assert isinstance(last_heartbeat[sid], float)

    @pytest.mark.asyncio
    async def test_disconnect_event_with_room(self, test_room_with_player):
        """Test SocketIO disconnect event when user is in a room"""
        room, player = test_room_with_player
        sid = "test_sid_disconnect"
        
        # Simulate user being in client_rooms
        client_rooms[sid] = {
            "username": player.player_username,
            "room_id": room.id
        }
        last_heartbeat[sid] = time.time()
        
        with patch.object(sio, 'leave_room', new_callable=AsyncMock) as mock_leave:
            with patch('sio_events.handle_player_leave', new_callable=AsyncMock) as mock_handle_leave:
                await sio_events.disconnect(sid)
                
                # Verify room leave was called
                mock_leave.assert_called_once_with(sid, str(room.id), namespace="/game")
                
                # Verify player leave handler was called
                mock_handle_leave.assert_called_once()
                
                # Verify cleanup
                assert sid not in client_rooms
                assert sid not in last_heartbeat

    @pytest.mark.asyncio
    async def test_join_event_success(self, test_room_with_player):
        """Test successful SocketIO join event"""
        room, player = test_room_with_player
        sid = "test_sid_join"
        
        join_data = {
            "room_id": room.id,
            "username": player.player_username
        }
        
        with patch.object(sio, 'enter_room', new_callable=AsyncMock) as mock_enter:
            with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
                with patch('sio_events.get_players_for_room', new_callable=AsyncMock) as mock_get_players:
                    mock_get_players.return_value = [{"username": player.player_username, "is_host": True}]
                    
                    await sio_events.join(sid, join_data)
                    
                    # Verify room entry
                    mock_enter.assert_called_once_with(sid, str(room.id), namespace="/game")
                    
                    # Verify client tracking
                    assert sid in client_rooms
                    assert client_rooms[sid]["username"] == player.player_username
                    assert client_rooms[sid]["room_id"] == room.id
                    
                    # Verify success response was emitted
                    success_calls = [call for call in mock_emit.call_args_list 
                                   if call[0][0] == 'join_success']
                    assert len(success_calls) > 0
                    
                    success_call = success_calls[0]
                    response_data = success_call[0][1]
                    assert response_data["success"] is True
                    assert response_data["room_id"] == room.id
                    assert response_data["username"] == player.player_username

    @pytest.mark.asyncio
    async def test_join_event_player_not_registered(self, test_room_with_player):
        """Test SocketIO join event when player is not registered in room"""
        room, _ = test_room_with_player
        sid = "test_sid_join_fail"
        
        join_data = {
            "room_id": room.id,
            "username": "unregistered_user"
        }
        
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await sio_events.join(sid, join_data)
            
            # Verify failure response
            mock_emit.assert_called_once()
            args, kwargs = mock_emit.call_args
            
            assert args[0] == "join_success"
            assert args[1]["success"] is False
            assert "not registered" in args[1]["error"]

    @pytest.mark.asyncio
    async def test_leave_event_host_transfer(self, test_db_session: AsyncSession):
        """Test SocketIO leave event with host transfer"""
        from services.Wiregruad import WiregruadVPN
        from vpnserver.genrator import generate_wireguard_keys
        
        # Create two users
        private_key1, public_key1 = generate_wireguard_keys()
        private_key2, public_key2 = generate_wireguard_keys()
        
        user1 = User(username="host_user", email="host@example.com", 
                    password="test", private_key=private_key1, public_key=public_key1)
        user2 = User(username="member_user", email="member@example.com", 
                    password="test", private_key=private_key2, public_key=public_key2)
        
        test_db_session.add_all([user1, user2])
        await test_db_session.commit()
        
        # Create room with VPN
        vpn = WiregruadVPN()
        network_name = await vpn.create_network_config(test_db_session)
        
        room = Room(
            name="Host Transfer Test",
            description="Testing host transfer",
            owner_username=user1.username,
            network_name=network_name,
            max_players=8,
            is_private=False
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)
        
        # Add both players to room
        host_player = RoomPlayer(room_id=room.id, player_username=user1.username, is_host=True)
        member_player = RoomPlayer(room_id=room.id, player_username=user2.username, is_host=False)
        
        test_db_session.add_all([host_player, member_player])
        await test_db_session.commit()
        
        sid = "test_sid_leave_host"
        leave_data = {
            "room_id": room.id,
            "username": user1.username
        }
        
        with patch.object(sio, 'leave_room', new_callable=AsyncMock):
            with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
                with patch('sio_events.get_players_for_room', new_callable=AsyncMock) as mock_get_players:
                    mock_get_players.return_value = [{"username": user2.username, "is_host": True}]
                    
                    await sio_events.leave(sid, leave_data)
                    
                    # Verify host_changed event was emitted
                    host_changed_calls = [call for call in mock_emit.call_args_list 
                                        if call[0][0] == 'host_changed']
                    assert len(host_changed_calls) > 0
                    
                    host_changed_data = host_changed_calls[0][0][1]
                    assert host_changed_data["new_host"] == user2.username

    @pytest.mark.asyncio
    async def test_send_message_event(self, test_room_with_player):
        """Test SocketIO send_message event"""
        room, player = test_room_with_player
        sid = "test_sid_message"
        
        message_data = {
            "room_id": room.id,
            "username": player.player_username,
            "message": "Hello from SocketIO test!"
        }
        
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await sio_events.send_message(sid, message_data)
            
            # Verify new_message event was emitted
            mock_emit.assert_called_once()
            args, kwargs = mock_emit.call_args
            
            assert args[0] == "new_message"
            assert args[1]["username"] == player.player_username
            assert args[1]["message"] == "Hello from SocketIO test!"
            assert args[1]["room_id"] == room.id
            assert "created_at" in args[1]
            assert kwargs["room"] == str(room.id)

    @pytest.mark.asyncio
    async def test_heartbeat_event(self):
        """Test SocketIO heartbeat event"""
        sid = "test_sid_heartbeat"
        heartbeat_data = {
            "room_id": 123,
            "username": "test_user"
        }
        
        # Initialize heartbeat
        last_heartbeat[sid] = time.time() - 10  # 10 seconds ago
        
        await sio_events.heartbeat(sid, heartbeat_data)
        
        # Verify heartbeat was updated
        assert sid in last_heartbeat
        assert last_heartbeat[sid] > time.time() - 1  # Updated within last second
        
        # Verify client_rooms was updated
        assert sid in client_rooms
        assert client_rooms[sid]["username"] == "test_user"
        assert client_rooms[sid]["room_id"] == 123

    @pytest.mark.asyncio
    async def test_check_player_event(self, test_room_with_player):
        """Test SocketIO check_player event"""
        room, player = test_room_with_player
        sid = "test_sid_check"
        
        # Test existing player
        check_data = {
            "room_id": room.id,
            "username": player.player_username
        }
        
        result = await sio_events.check_player(sid, check_data)
        assert result["exists"] is True
        
        # Test non-existing player
        check_data_nonexistent = {
            "room_id": room.id,
            "username": "nonexistent_user"
        }
        
        result = await sio_events.check_player(sid, check_data_nonexistent)
        assert result["exists"] is False

    @pytest.mark.asyncio
    async def test_start_game_event(self, test_room_with_player):
        """Test SocketIO start_game event"""
        room, player = test_room_with_player
        sid = "test_sid_start_game"
        
        start_data = {
            "room_id": room.id
        }
        
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await sio_events.start_game(sid, start_data)
            
            # Verify game_started event was emitted
            mock_emit.assert_called_once()
            args, kwargs = mock_emit.call_args
            
            assert args[0] == "game_started"
            assert args[1]["room_id"] == room.id
            assert "started_at" in args[1]
            assert kwargs["room"] == str(room.id)

    @pytest.mark.asyncio
    async def test_invalid_data_handling(self):
        """Test SocketIO events with invalid data"""
        sid = "test_sid_invalid"
        
        # Test join with missing data
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await sio_events.join(sid, {"room_id": None})
            
            mock_emit.assert_called_once()
            response = mock_emit.call_args[0][1]
            assert response["success"] is False
            assert "Missing" in response["error"]
        
        # Test send_message with missing data
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await sio_events.send_message(sid, {"room_id": 1})
            
            mock_emit.assert_called_once()
            response = mock_emit.call_args[0][1]
            assert response["message"] == "Invalid message data"

    @pytest.mark.asyncio 
    async def test_room_deletion_on_last_player_leave(self, test_room_with_player):
        """Test room deletion when last player leaves"""
        room, player = test_room_with_player
        sid = "test_sid_last_leave"
        
        leave_data = {
            "room_id": room.id,
            "username": player.player_username
        }
        
        with patch.object(sio, 'leave_room', new_callable=AsyncMock):
            with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
                await sio_events.leave(sid, leave_data)
                
                # Verify room_closed event was emitted
                room_closed_calls = [call for call in mock_emit.call_args_list 
                                   if call[0][0] == 'room_closed']
                assert len(room_closed_calls) > 0
                
                room_closed_data = room_closed_calls[0][0][1]
                assert room_closed_data["room_id"] == room.id 