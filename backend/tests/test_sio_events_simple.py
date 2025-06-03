"""
Simplified SocketIO Events Tests
Tests core event logic without circular imports
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime


class MockUser:
    def __init__(self, username, email):
        self.username = username
        self.email = email
        self.private_key = b"mock_private_key"
        self.public_key = b"mock_public_key"
        self.id = 1


class MockRoom:
    def __init__(self, room_id, name, network_name):
        self.id = room_id
        self.name = name
        self.network_name = network_name
        self.owner_username = "test_user"
        self.max_players = 8
        self.is_private = False


class MockRoomPlayer:
    def __init__(self, username, is_host=False):
        self.player_username = username
        self.is_host = is_host
        self.room_id = 1
        self.user_id = 1


class TestSocketIOEventsSimple:

    @pytest.mark.asyncio
    async def test_connect_event_logic(self):
        """Test the connect event logic"""
        # Mock the required modules and global state
        mock_sio = AsyncMock()
        mock_client_rooms = {}
        mock_last_heartbeat = {}
        
        with patch('sio_events.sio', mock_sio):
            with patch('sio_events.client_rooms', mock_client_rooms):
                with patch('sio_events.last_heartbeat', mock_last_heartbeat):
                    
                    # Import the function after patching
                    from sio_events import connect
                    
                    sid = "test_sid_123"
                    environ = {"HTTP_HOST": "localhost"}
                    
                    await connect(sid, environ)
                    
                    # Verify server_ready event was emitted
                    mock_sio.emit.assert_called_once()
                    args, kwargs = mock_sio.emit.call_args
                    
                    assert args[0] == "server_ready"
                    assert "message" in args[1]
                    assert "timestamp" in args[1]
                    assert kwargs["to"] == sid
                    assert kwargs["namespace"] == "/game"
                    
                    # Verify heartbeat was initialized
                    assert sid in mock_last_heartbeat
                    assert isinstance(mock_last_heartbeat[sid], float)

    @pytest.mark.asyncio
    async def test_heartbeat_event_logic(self):
        """Test the heartbeat event logic"""
        mock_client_rooms = {}
        mock_last_heartbeat = {}
        
        with patch('sio_events.client_rooms', mock_client_rooms):
            with patch('sio_events.last_heartbeat', mock_last_heartbeat):
                
                from sio_events import heartbeat
                
                sid = "test_sid_heartbeat"
                heartbeat_data = {
                    "room_id": 123,
                    "username": "test_user"
                }
                
                # Initialize heartbeat
                mock_last_heartbeat[sid] = time.time() - 10  # 10 seconds ago
                
                await heartbeat(sid, heartbeat_data)
                
                # Verify heartbeat was updated
                assert sid in mock_last_heartbeat
                assert mock_last_heartbeat[sid] > time.time() - 1  # Updated within last second
                
                # Verify client_rooms was updated
                assert sid in mock_client_rooms
                assert mock_client_rooms[sid]["username"] == "test_user"
                assert mock_client_rooms[sid]["room_id"] == 123

    @pytest.mark.asyncio
    async def test_join_event_missing_data(self):
        """Test join event with missing data"""
        mock_sio = AsyncMock()
        
        with patch('sio_events.sio', mock_sio):
            from sio_events import join
            
            sid = "test_sid_join"
            
            # Test with missing room_id
            await join(sid, {"username": "test_user"})
            
            # Verify error response was emitted
            mock_sio.emit.assert_called_once()
            args, kwargs = mock_sio.emit.call_args
            
            assert args[0] == "join_success"
            assert args[1]["success"] is False
            assert "Missing" in args[1]["error"]

    @pytest.mark.asyncio
    async def test_send_message_invalid_data(self):
        """Test send_message with invalid data"""
        mock_sio = AsyncMock()
        
        with patch('sio_events.sio', mock_sio):
            from sio_events import send_message
            
            sid = "test_sid_message"
            
            # Test with missing message data
            await send_message(sid, {"room_id": 1})
            
            # Verify error response was emitted
            mock_sio.emit.assert_called_once()
            args, kwargs = mock_sio.emit.call_args
            
            assert args[0] == "error"
            assert args[1]["message"] == "Invalid message data"

    @pytest.mark.asyncio
    async def test_start_game_event_logic(self):
        """Test start_game event logic"""
        mock_sio = AsyncMock()
        mock_last_heartbeat = {}
        
        with patch('sio_events.sio', mock_sio):
            with patch('sio_events.last_heartbeat', mock_last_heartbeat):
                
                from sio_events import start_game
                
                sid = "test_sid_start_game"
                start_data = {"room_id": 123}
                
                await start_game(sid, start_data)
                
                # Verify game_started event was emitted
                mock_sio.emit.assert_called_once()
                args, kwargs = mock_sio.emit.call_args
                
                assert args[0] == "game_started"
                assert args[1]["room_id"] == 123
                assert "started_at" in args[1]
                assert kwargs["room"] == "123"

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self):
        """Test disconnect event cleanup"""
        mock_sio = AsyncMock()
        mock_client_rooms = {"test_sid": {"username": "user1", "room_id": 123}}
        mock_last_heartbeat = {"test_sid": time.time()}
        
        with patch('sio_events.sio', mock_sio):
            with patch('sio_events.client_rooms', mock_client_rooms):
                with patch('sio_events.last_heartbeat', mock_last_heartbeat):
                    with patch('sio_events.create_session') as mock_create_session:
                        with patch('sio_events.handle_player_leave', new_callable=AsyncMock) as mock_handle_leave:
                            
                            # Mock database session
                            mock_db = AsyncMock()
                            mock_create_session.return_value = mock_db
                            
                            from sio_events import disconnect
                            
                            sid = "test_sid"
                            await disconnect(sid)
                            
                            # Verify room leave was called
                            mock_sio.leave_room.assert_called_once_with(sid, "123", namespace="/game")
                            
                            # Verify player leave handler was called
                            mock_handle_leave.assert_called_once()
                            
                            # Verify cleanup
                            assert sid not in mock_client_rooms
                            assert sid not in mock_last_heartbeat

    @pytest.mark.asyncio
    async def test_check_player_logic(self):
        """Test check_player event logic"""
        with patch('sio_events.create_session') as mock_create_session:
            # Mock database session and query
            mock_db = AsyncMock()
            mock_result = AsyncMock()
            mock_result.scalars.return_value.first.return_value = MockRoomPlayer("test_user")
            mock_db.execute.return_value = mock_result
            mock_create_session.return_value = mock_db
            
            from sio_events import check_player
            
            sid = "test_sid_check"
            check_data = {
                "room_id": 123,
                "username": "test_user"
            }
            
            result = await check_player(sid, check_data)
            
            # Verify player was found
            assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_invalid_room_id_format(self):
        """Test events with invalid room_id format"""
        mock_sio = AsyncMock()
        
        with patch('sio_events.sio', mock_sio):
            from sio_events import send_message
            
            sid = "test_sid_invalid"
            invalid_data = {
                "room_id": "invalid_id",
                "username": "test_user", 
                "message": "test message"
            }
            
            await send_message(sid, invalid_data)
            
            # Verify error response was emitted
            mock_sio.emit.assert_called_once()
            args, kwargs = mock_sio.emit.call_args
            
            assert args[0] == "error"
            assert "Invalid room ID format" in args[1]["message"]

    @pytest.mark.asyncio
    async def test_namespace_consistency(self):
        """Test that all events use the correct namespace"""
        mock_sio = AsyncMock()
        
        with patch('sio_events.sio', mock_sio):
            with patch('sio_events.last_heartbeat', {}):
                
                from sio_events import connect, start_game
                
                # Test connect event
                await connect("sid1", {})
                connect_call = mock_sio.emit.call_args
                assert connect_call[1]["namespace"] == "/game"
                
                mock_sio.reset_mock()
                
                # Test start_game event  
                await start_game("sid2", {"room_id": 123})
                start_game_call = mock_sio.emit.call_args
                assert start_game_call[1]["namespace"] == "/game"

    def test_event_registration(self):
        """Test that events are properly registered with the namespace"""
        # This test verifies that the event decorators are working
        import sio_events
        
        # Check that the module has the expected event functions
        assert hasattr(sio_events, 'connect')
        assert hasattr(sio_events, 'disconnect') 
        assert hasattr(sio_events, 'join')
        assert hasattr(sio_events, 'leave')
        assert hasattr(sio_events, 'heartbeat')
        assert hasattr(sio_events, 'send_message')
        assert hasattr(sio_events, 'check_player')
        assert hasattr(sio_events, 'start_game')
        
        # Verify they are callable
        assert callable(sio_events.connect)
        assert callable(sio_events.disconnect)
        assert callable(sio_events.join)
        assert callable(sio_events.leave)
        assert callable(sio_events.heartbeat)
        assert callable(sio_events.send_message)
        assert callable(sio_events.check_player)
        assert callable(sio_events.start_game) 