# sio_events.py
import time
from datetime import datetime
from sqlalchemy.future import select
import asyncio
from services.Wiregruad import WiregruadVPN
from config import settings
from shared import sio, client_rooms, last_heartbeat
from database.database import create_session
from models import Room, RoomPlayer, ChatMessage
from helpers import get_players_for_room, handle_player_leave
from socket_logger import (
    log_connection, log_disconnection, log_join_event, log_leave_event,
    log_heartbeat, log_message, log_player_check, log_game_start,
    log_error, log_debug
)

NAMESPACE = "/game"
vpn = WiregruadVPN()
@sio.event(namespace=NAMESPACE)
async def connect(sid, environ):
    log_connection(sid, environ)
    log_debug("Sending server_ready event", {"sid": sid})
    log_debug("Current client_rooms state", client_rooms)
    log_debug("Current last_heartbeat state", last_heartbeat)
    
    try:
        await sio.emit("server_ready", {
            "message": "You can now send join",
            "timestamp": datetime.now().isoformat()
        }, to=sid, namespace=NAMESPACE)
        log_debug("server_ready event sent", {"sid": sid})
        last_heartbeat[sid] = time.time()
        log_debug("Heartbeat initialized", {"sid": sid})
    except Exception as e:
        log_error("server_ready", sid, e)

    # Add a small delay to ensure the client receives server_ready
    await asyncio.sleep(0.5)
    log_debug("Connection setup completed", {"sid": sid})

@sio.event(namespace="/game")
async def disconnect(sid):
    log_disconnection(sid, client_rooms)

    if sid in client_rooms:
        data = client_rooms[sid]
        username = data["username"]
        room_id = data["room_id"]

        await sio.leave_room(sid, str(room_id), namespace="/game")

        db = await create_session()
        try:
            log_debug("Calling handle_player_leave", {"username": username, "room_id": room_id})
            await handle_player_leave(username, room_id, db)
            log_debug("Finished handle_player_leave", {"username": username, "room_id": room_id})
        except Exception as e:
            log_error("disconnect", sid, e)
            await db.rollback()
        finally:
            await db.close()

        del client_rooms[sid]

    if sid in last_heartbeat:
        del last_heartbeat[sid]

@sio.event(namespace=NAMESPACE)
async def join(sid, data):
    log_join_event(sid, data)
    log_debug("Join request received", {"sid": sid, "data": data})

    room_id = data.get('room_id')
    username = data.get('username')

    if not room_id or not username:
        log_debug("Join failed - missing data", {"sid": sid, "room_id": room_id, "username": username})
        await sio.emit('join_success', {
            'success': False,
            'error': 'Missing room_id or username'
        }, to=sid, namespace=NAMESPACE)
        return

    db = await create_session()
    try:
        room_id = int(room_id)
        log_debug("Checking player existence", {"sid": sid, "room_id": room_id, "username": username})
        existing = await db.execute(
            select(RoomPlayer).filter_by(room_id=room_id, player_username=username)
        )
        player = existing.scalars().first()

        if not player:
            log_debug("Join failed - player not registered", {"sid": sid, "room_id": room_id, "username": username})
            await sio.emit('join_success', {
                'success': False,
                'error': 'Player not registered. Please join via HTTP first.'
            }, to=sid, namespace=NAMESPACE)
            return

        log_debug("Player found, proceeding with join", {"sid": sid, "room_id": room_id, "username": username})
        await sio.enter_room(sid, str(room_id), namespace=NAMESPACE)
        client_rooms[sid] = {'username': username, 'room_id': room_id}
        last_heartbeat[sid] = time.time()

        await sio.emit('user_joined', {'username': username}, room=str(room_id), namespace=NAMESPACE)

        players = await get_players_for_room(db, room_id)
        await sio.emit('update_players', {'players': players}, room=str(room_id), namespace=NAMESPACE)

        log_debug("Join successful", {"sid": sid, "room_id": room_id, "username": username, "is_host": player.is_host})
        await sio.emit('join_success', {
            'success': True,
            'room_id': room_id,
            'username': username,
            'is_host': player.is_host,
            'players': players
        }, to=sid, namespace=NAMESPACE)

    except Exception as e:
        log_error("join", sid, e)
        await sio.emit('join_success', {
            'success': False,
            'error': str(e)
        }, to=sid, namespace=NAMESPACE)
    finally:
        await db.close()

@sio.event(namespace=NAMESPACE)
async def leave(sid, data):
    log_leave_event(sid, data)
    room_id = data.get('room_id')
    username = data.get('username')

    if not room_id or not username:
        return

    db = await create_session()
    try:
        room_id = int(room_id)
        await sio.leave_room(sid, str(room_id), namespace=NAMESPACE)

        # جلب اللاعب
        result = await db.execute(
            select(RoomPlayer).filter_by(room_id=room_id, player_username=username)
        )
        player = result.scalars().first()

        if player:
            is_host_leaving = player.is_host  # ✅ نحتفظ بحالة المضيف قبل الحذف
            await db.delete(player)
            await vpn.check_user_in_network_config(db, room.network_name, username=current_user.email)
            await db.flush()
        else:
            is_host_leaving = False

        # جلب من تبقى من اللاعبين
        remaining_players_result = await db.execute(
            select(RoomPlayer).filter_by(room_id=room_id)
        )
        players_left = remaining_players_result.scalars().all()

        if not players_left:
            await vpn.down_network_config(db, room.network_name)
            # حذف الغرفة إذا لم يبق أحد
            room_result = await db.execute(select(Room).filter_by(id=room_id))
            room = room_result.scalars().first()
            if room:
                await db.delete(room)
                await sio.emit('room_closed', {'room_id': room_id}, room=str(room_id), namespace=NAMESPACE)
                await sio.emit('update_rooms', {}, namespace=NAMESPACE)
                log_debug(f"Room {room_id} deleted after last player left")
        else:
            # ✅ إذا المضيف طلع، ننقل الملكية لأول لاعب متبقٍ
            if is_host_leaving:
                room_result = await db.execute(select(Room).filter_by(id=room_id))
                room = room_result.scalars().first()
                if room:
                    new_host = players_left[0]
                    new_host.is_host = True
                    room.owner_username = new_host.player_username
                    await sio.emit('host_changed', {
                        'new_host': new_host.player_username,
                        'room_id': room_id
                    }, room=str(room_id), namespace=NAMESPACE)
                    log_debug(f"👑 New host assigned: {new_host.player_username}")

            # إرسال التحديثات
            players = await get_players_for_room(db, room_id)
            await sio.emit('update_players', {'players': players}, room=str(room_id), namespace=NAMESPACE)
            await sio.emit('user_left', {'username': username}, room=str(room_id), namespace=NAMESPACE)
            await sio.emit('update_rooms', {}, namespace=NAMESPACE)

        await db.commit()

    except Exception as e:
        log_error("leave", sid, e)
        await db.rollback()
    finally:
        await db.close()

    client_rooms.pop(sid, None)
    last_heartbeat.pop(sid, None)

@sio.event(namespace=NAMESPACE)
async def heartbeat(sid, data):
    log_heartbeat(sid, data)
    if sid in last_heartbeat:
        last_heartbeat[sid] = time.time()

        if data and 'room_id' in data and 'username' in data:
            try:
                room_id = int(data['room_id'])
                client_rooms[sid] = {
                    'username': data['username'],
                    'room_id': room_id
                }
            except (ValueError, TypeError):
                log_error("heartbeat", sid, f"Invalid room_id: {data['room_id']}")
    else:
        log_debug(f"Heartbeat from unknown SID: {sid}", data)
        last_heartbeat[sid] = time.time()
        if data and 'room_id' in data and 'username' in data:
            try:
                room_id = int(data['room_id'])
                client_rooms[sid] = {
                    'username': data['username'],
                    'room_id': room_id
                }
            except (ValueError, TypeError):
                pass

@sio.event(namespace=NAMESPACE)
async def send_message(sid, data):
    log_message(sid, data)
    room_id = data.get('room_id')
    username = data.get('username')
    message = data.get('message')

    if not all([room_id, username, message]):
        await sio.emit('error', {'message': 'Invalid message data'}, to=sid, namespace=NAMESPACE)
        return

    try:
        room_id_int = int(room_id)
    except (ValueError, TypeError):
        log_error("send_message", sid, f"Invalid room_id format: {room_id}")
        await sio.emit('error', {'message': 'Invalid room ID format'}, to=sid, namespace=NAMESPACE)
        return

    last_heartbeat[sid] = time.time()

    db = await create_session()
    try:
        chat_message = ChatMessage(
            room_id=room_id_int,
            username=username,
            message=message
        )
        db.add(chat_message)
        await db.commit()
        await db.refresh(chat_message)

        await sio.emit('new_message', {
            'username': username,
            'message': message,
            'room_id': room_id_int,
            'created_at': chat_message.created_at.isoformat()
        }, room=str(room_id), namespace=NAMESPACE)

    except Exception as e:
        log_error("send_message", sid, e)
        await db.rollback()
        await sio.emit('error', {'message': 'Failed to send message'}, to=sid, namespace=NAMESPACE)
    finally:
        await db.close()

@sio.event(namespace=NAMESPACE)
async def check_player(sid, data):
    log_player_check(sid, data)
    room_id = data.get('room_id')
    username = data.get('username')
    
    if not all([room_id, username]):
        return {'exists': False}
    try:
        room_id_int = int(room_id)
        db = await create_session()
        try:
            query = select(RoomPlayer).filter(
                RoomPlayer.room_id == room_id_int,
                RoomPlayer.player_username == username
            )
            result = await db.execute(query)
            player = result.scalars().first()
            exists = player is not None
            log_debug("Player check result", {"player": player, "exists": exists})
            return {'exists': exists}
        finally:
            await db.close()
    except Exception as e:
        log_error("check_player", sid, e)
        return {'exists': False}

@sio.event(namespace=NAMESPACE)
async def start_game(sid, data):
    log_game_start(sid, data)
    room_id = data.get('room_id')

    if not room_id:
        log_debug("Start_game event missing room_id", {"sid": sid})
        return

    try:
        room_id_int = int(room_id)
    except (ValueError, TypeError):
        log_error("start_game", sid, f"Invalid room_id format: {room_id}")
        await sio.emit('error', {'message': 'Invalid room ID format'}, to=sid, namespace=NAMESPACE)
        return

    last_heartbeat[sid] = time.time()

    await sio.emit('game_started', {
        'room_id': room_id_int,
        'started_at': datetime.now().isoformat()
    }, room=str(room_id), namespace=NAMESPACE)
    