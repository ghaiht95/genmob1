import pytest
from fastapi import status

def test_create_room(client, test_user):
    response = client.post(
        "/rooms/",
        json={
            "name": "New Test Room",
            "max_players": 4,
            "is_private": False,
            "owner": test_user.id
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "New Test Room"
    assert data["max_players"] == 4
    assert data["is_private"] == False
    assert data["owner_id"] == test_user.id

def test_get_rooms(client, test_room):
    response = client.get("/rooms/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) > 0
    assert data[0]["name"] == test_room.name

def test_get_room(client, test_room):
    response = client.get(f"/rooms/{test_room.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == test_room.name
    assert data["id"] == test_room.id

def test_join_room(client, test_room, test_user):
    response = client.post(
        f"/rooms/{test_room.id}/join",
        json={"user_id": test_user.id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["room_id"] == test_room.id
    assert data["user_id"] == test_user.id

def test_leave_room(client, test_room, test_user):
    # First join the room
    client.post(
        f"/rooms/{test_room.id}/join",
        json={"user_id": test_user.id}
    )
    
    # Then leave
    response = client.post(
        f"/rooms/{test_room.id}/leave",
        json={"user_id": test_user.id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["room_id"] == test_room.id
    assert data["user_id"] == test_user.id

def test_delete_room(client, test_room, test_user):
    response = client.delete(f"/rooms/{test_room.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_room.id

def test_room_not_found(client):
    response = client.get("/rooms/999")
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_join_full_room(client, test_room, test_user):
    # Create max_players players
    for i in range(test_room.max_players):
        client.post(
            f"/rooms/{test_room.id}/join",
            json={"user_id": i + 1}
        )
    
    # Try to join with one more player
    response = client.post(
        f"/rooms/{test_room.id}/join",
        json={"user_id": test_user.id}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_join_private_room(client, test_room, test_user):
    # Make room private
    test_room.is_private = True
    
    # Try to join without password
    response = client.post(
        f"/rooms/{test_room.id}/join",
        json={"user_id": test_user.id}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST 