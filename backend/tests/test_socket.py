import pytest
import socketio
import asyncio
from main import socket_app

@pytest.fixture
def sio_client():
    client = socketio.AsyncClient()
    return client

@pytest.mark.asyncio
async def test_connect(sio_client):
    await sio_client.connect('http://localhost:5000')
    assert sio_client.connected
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_join_room(sio_client, test_room, test_user):
    await sio_client.connect('http://localhost:5000')
    
    # Join room
    response = await sio_client.call('join_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    assert response['room_id'] == test_room.id
    assert response['user_id'] == test_user.id
    
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_leave_room(sio_client, test_room, test_user):
    await sio_client.connect('http://localhost:5000')
    
    # First join
    await sio_client.call('join_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    # Then leave
    response = await sio_client.call('leave_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    assert response['room_id'] == test_room.id
    assert response['user_id'] == test_user.id
    
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_ready_player(sio_client, test_room, test_user):
    await sio_client.connect('http://localhost:5000')
    
    # First join
    await sio_client.call('join_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    # Then set ready
    response = await sio_client.call('ready_player', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    assert response['room_id'] == test_room.id
    assert response['user_id'] == test_user.id
    assert response['is_ready'] == True
    
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_start_game(sio_client, test_room, test_user):
    await sio_client.connect('http://localhost:5000')
    
    # First join
    await sio_client.call('join_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    # Then start game
    response = await sio_client.call('start_game', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    assert response['room_id'] == test_room.id
    assert response['status'] == 'playing'
    
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_room_events(sio_client, test_room, test_user):
    await sio_client.connect('http://localhost:5000')
    
    # Set up event handlers
    room_updated = False
    player_joined = False
    player_left = False
    
    @sio_client.on('room_updated')
    def on_room_updated(data):
        nonlocal room_updated
        room_updated = True
    
    @sio_client.on('player_joined')
    def on_player_joined(data):
        nonlocal player_joined
        player_joined = True
    
    @sio_client.on('player_left')
    def on_player_left(data):
        nonlocal player_left
        player_left = True
    
    # Join room
    await sio_client.call('join_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    # Wait for events
    await asyncio.sleep(1)
    
    assert room_updated
    assert player_joined
    
    # Leave room
    await sio_client.call('leave_room', {
        'room_id': test_room.id,
        'user_id': test_user.id
    })
    
    # Wait for events
    await asyncio.sleep(1)
    
    assert player_left
    
    await sio_client.disconnect() 