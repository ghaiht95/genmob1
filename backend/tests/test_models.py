import pytest
from datetime import datetime, timedelta
from models import User, Room, RoomPlayer

def test_user_creation(db_session):
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active == True
    assert user.created_at is not None
    assert user.updated_at is not None

def test_room_creation(db_session, test_user):
    room = Room(
        name="Test Room",
        owner_id=test_user.id,
        max_players=4,
        is_private=False
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    
    assert room.name == "Test Room"
    assert room.owner_id == test_user.id
    assert room.max_players == 4
    assert room.is_private == False
    assert room.created_at is not None
    assert room.updated_at is not None

def test_player_creation(db_session, test_user, test_room):
    player = RoomPlayer(
        user_id=test_user.id,
        room_id=test_room.id,
        is_ready=False,
        is_host=True
    )
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    
    assert player.user_id == test_user.id
    assert player.room_id == test_room.id
    assert player.is_ready == False
    assert player.is_host == True
    assert player.created_at is not None
    assert player.updated_at is not None

# def test_game_creation(db_session, test_room):
#     ...

# def test_room_relationships(db_session, test_user, test_room):
#     ... 