import pytest
from services.room_service import RoomService
# from services.player_service import PlayerService
# from services.game_service import GameService

def test_room_service_create_room(db_session, test_user):
    room_service = RoomService(db_session)
    room = room_service.create_room(
        name="Service Test Room",
        owner_id=test_user.id,
        max_players=4,
        is_private=False
    )
    
    assert room.name == "Service Test Room"
    assert room.owner_id == test_user.id
    assert room.max_players == 4
    assert room.is_private == False

def test_room_service_get_rooms(db_session, test_room):
    room_service = RoomService(db_session)
    rooms = room_service.get_rooms()
    
    assert len(rooms) > 0
    assert rooms[0].name == test_room.name

def test_room_service_get_room(db_session, test_room):
    room_service = RoomService(db_session)
    room = room_service.get_room(test_room.id)
    
    assert room.name == test_room.name
    assert room.id == test_room.id

# def test_player_service_join_room(db_session, test_room, test_user):
#     player_service = PlayerService(db_session)
#     player = player_service.join_room(test_room.id, test_user.id)
#     
#     assert player.room_id == test_room.id
#     assert player.user_id == test_user.id
#     assert player.is_ready == False

# def test_player_service_leave_room(db_session, test_room, test_user):
#     player_service = PlayerService(db_session)
#     
#     # First join
#     player = player_service.join_room(test_room.id, test_user.id)
#     
#     # Then leave
#     result = player_service.leave_room(test_room.id, test_user.id)
#     assert result is True

# def test_player_service_get_room_players(db_session, test_room, test_user):
#     player_service = PlayerService(db_session)
#     
#     # Add multiple players
#     player1 = player_service.join_room(test_room.id, test_user.id)
#     player2 = player_service.join_room(test_room.id, 2)
#     
#     players = player_service.get_room_players(test_room.id)
#     assert len(players) == 2

# def test_game_service_create_game(db_session, test_room):
#     game_service = GameService(db_session)
#     game = game_service.create_game(test_room.id)
#     
#     assert game.room_id == test_room.id
#     assert game.status == "waiting"
#     assert game.current_round == 0

# def test_game_service_get_room_game(db_session, test_room):
#     game_service = GameService(db_session)
#     
#     # Create game
#     game = game_service.create_game(test_room.id)
#     
#     # Get game
#     retrieved_game = game_service.get_room_game(test_room.id)
#     assert retrieved_game.id == game.id
#     assert retrieved_game.status == "waiting"

# def test_game_service_update_game_status(db_session, test_room):
#     game_service = GameService(db_session)
#     
#     # Create game
#     game = game_service.create_game(test_room.id)
#     
#     # Update status
#     updated_game = game_service.update_game_status(test_room.id, "playing")
#     assert updated_game.status == "playing"

# def test_game_service_increment_round(db_session, test_room):
#     game_service = GameService(db_session)
#     
#     # Create game
#     game = game_service.create_game(test_room.id)
#     
#     # Increment round
#     updated_game = game_service.increment_round(test_room.id)
#     assert updated_game.current_round == 1 