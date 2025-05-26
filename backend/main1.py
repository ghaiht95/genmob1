import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
import socketio
import asyncio
import time
from datetime import datetime, timedelta
from sqlalchemy.future import select

# Local imports
from config import settings
from database.database import get_session, init_db, create_session
from models import User, Room, RoomPlayer, ChatMessage
from routers.auth import router as auth_router
from routers.rooms import router as rooms_router
from routers.friends import router as friends_router
from services.softether import SoftEtherVPN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create SocketIO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*', ping_timeout=60)

# Session storage for keeping track of users and their rooms
client_rooms = {}  # Maps sid to {username, room_id}
last_heartbeat = {}  # Store last heartbeat time for each client

# Function to get players for a room (helper function)
async def get_players_for_room(db, room_id):
    """Get all players in a room"""
    query = select(RoomPlayer.player_username).filter(RoomPlayer.room_id == room_id)
    result = await db.execute(query)
    players = [row[0] for row in result.all()]
    return players


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")
    
    if sid not in client_rooms:
        return

    client_data = client_rooms[sid]
    username = client_data['username']
    room_id = client_data['room_id']

    db = await create_session()
    try:
        vpn = SoftEtherVPN()

        # جلب اللاعب
        player_result = await db.execute(
            select(RoomPlayer).filter(
                RoomPlayer.room_id == room_id,
                RoomPlayer.player_username == username
            )
        )
        player = player_result.scalars().first()

        # جلب الغرفة
        room = await db.get(Room, room_id)
        if not room:
            return

        # حذف المستخدم من VPN
        if player and room.vpn_hub:
            try:
                await vpn.delete_user(room.vpn_hub, player.username)
                logger.info(f"Deleted VPN user {player.username} from hub {room.vpn_hub}")
            except Exception as e:
                logger.warning(f"Error deleting VPN user: {e}")

        # حذف اللاعب من قاعدة البيانات
        if player:
            is_host = player.is_host
            await db.delete(player)
            await db.flush()
        else:
            is_host = False

        # تحديث عدد اللاعبين أو حذف الغرفة
        players_left = (await db.execute(select(RoomPlayer).filter_by(room_id=room.id))).scalars().all()
        room.current_players = len(players_left)

        if room.current_players == 0:
            # حذف الهب والغرفة
            try:
                if room.vpn_hub:
                    await vpn.delete_hub(room.vpn_hub)
                    logger.info(f"Deleted VPN hub {room.vpn_hub}")
            except Exception as e:
                logger.warning(f"Error deleting VPN hub: {e}")

            await db.execute(ChatMessage.__table__.delete().where(ChatMessage.room_id == room.id))
            await db.delete(room)
            await sio.emit('room_closed', {'room_id': room_id})
        else:
            # إعادة تعيين المضيف
            if is_host:
                new_host = players_left[0]
                new_host.is_host = True
                room.owner_username = new_host.player_username
                logger.info(f"New host assigned: {new_host.player_username}")
                await sio.emit('host_changed', {'new_host': new_host.player_username}, room=str(room_id))

            # إرسال إشعار بالمغادرة
            await sio.emit('user_left', {'username': username, 'room_id': room_id}, room=str(room_id))

            # تحديث قائمة اللاعبين
            await sio.emit('update_players', {
                'players': [p.player_username for p in players_left]
            }, room=str(room_id))

        await db.commit()

    except Exception as e:
        logger.error(f"[disconnect] error: {e}")
        await db.rollback()
    finally:
        await db.close()
        # تنظيف الخرائط
        client_rooms.pop(sid, None)
        last_heartbeat.pop(sid, None)



# Function to handle player leave
async def handle_player_leave(username, room_id):
    """Handle a player leaving a room"""
    logger.info(f"Handling player leave: {username} from room {room_id}")
    
    try:
        # Get database session
        db = await create_session()
        
        try:
            # Call the leave_room API endpoint logic directly
            
            # Check if room exists
            room_result = await db.execute(select(Room).filter(Room.id == room_id))
            room = room_result.scalars().first()
            
            if not room:
                logger.warning(f"Room {room_id} not found when handling disconnect for {username}")
                return
            
            # Check if user is in the room
            player_result = await db.execute(
                select(RoomPlayer).filter(
                    RoomPlayer.room_id == room_id,
                    RoomPlayer.player_username == username
                )
            )
            player = player_result.scalars().first()
            
            if not player:
                logger.warning(f"Player {username} not found in room {room_id}")
                return
            
            # Check if player is the host and reassign if needed
            if player.is_host and room.current_players > 1:
                other_player_result = await db.execute(
                    select(RoomPlayer).filter(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.player_username != username
                    ).limit(1)
                )
                other_player = other_player_result.scalars().first()
                
                if other_player:
                    other_player.is_host = True
                    room.owner_username = other_player.player_username
                    logger.info(f"Host {username} disconnected, new host: {other_player.player_username}")
                    
                    # Notify remaining players of host change
                    await sio.emit('host_changed', {
                        'new_host': other_player.player_username,
                        'room_id': room_id
                    }, room=str(room_id))
            
            # Try to delete VPN user if hub exists
            try:
                if room.vpn_hub:
                    vpn = SoftEtherVPN()
                    await vpn.delete_user(room.vpn_hub, username)
                    logger.info(f"Deleted VPN user {username} from hub {room.vpn_hub}")
            except Exception as e:
                logger.error(f"Error deleting VPN user: {str(e)}")
            
            # Remove player from room
            await db.delete(player)
            
            # Update player count
            room.current_players -= 1
            
            # Delete room if empty
            if room.current_players <= 0:
                logger.info(f"Last player left room {room_id} due to disconnect. Deleting room and VPN hub.")
                
                # Delete VPN hub
                try:
                    if room.vpn_hub:
                        vpn = SoftEtherVPN()
                        result = await vpn.delete_hub(room.vpn_hub)
                        if result:
                            logger.info(f"Successfully deleted VPN hub: {room.vpn_hub}")
                        else:
                            # Try with direct hub name
                            hub_name = f"room_{room_id}"
                            result = await vpn.delete_hub(hub_name)
                            if result:
                                logger.info(f"Successfully deleted VPN hub on second attempt: {hub_name}")
                            else:
                                logger.warning(f"Failed to delete VPN hub: {room.vpn_hub}")
                except Exception as e:
                    logger.error(f"Error deleting VPN hub: {str(e)}")
                
                # Delete ChatMessages for the room
                await db.execute(ChatMessage.__table__.delete().where(ChatMessage.room_id == room.id))
                # Delete room
                await db.delete(room)
                logger.info(f"Room {room_id} deleted")
                
                # Notify all clients that the room is closed
                await sio.emit('room_closed', {'room_id': room_id})
            else:
                logger.info(f"Player {username} left room {room_id} due to disconnect. {room.current_players} players remaining.")
                
                # Broadcast to room that a user has left
                await sio.emit('user_left', {
                    'username': username,
                    'room_id': room_id
                }, room=str(room_id))
                
                # Update players list for remaining clients
                players = await get_players_for_room(db, room_id)
                await sio.emit('update_players', {
                    'players': players
                }, room=str(room_id))
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error in handle_player_leave: {str(e)}")
            await db.rollback()
        finally:
            await db.close()
            
    except Exception as e:
        logger.error(f"Database connection error in handle_player_leave: {str(e)}")

# Heartbeat monitor task
async def check_heartbeats():
    """Background task to check for stale connections"""
    while True:
        try:
            current_time = time.time()
            stale_clients = []
            
            # Find stale clients (no heartbeat in 40 seconds)
            for sid, last_time in list(last_heartbeat.items()):
                if current_time - last_time > 40:  # 40 seconds timeout
                    stale_clients.append(sid)
            
            # Handle disconnects for stale clients
            for sid in stale_clients:
                logger.warning(f"Client {sid} detected as stale (no heartbeat)")
                
                # If client is in a room, handle leave
                if sid in client_rooms:
                    client_data = client_rooms[sid]
                    await handle_player_leave(client_data['username'], client_data['room_id'])
                    
                    # Clean up data
                    del client_rooms[sid]
                
                # Remove from heartbeat tracking
                if sid in last_heartbeat:
                    del last_heartbeat[sid]
                    
        except Exception as e:
            logger.error(f"Error in heartbeat monitor: {str(e)}")
            
        # Check every 20 seconds
        await asyncio.sleep(20)

# Startup & shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")
    
    # Start the heartbeat monitor
    heartbeat_task = asyncio.create_task(check_heartbeats())
    logger.info("Started heartbeat monitor task")
    
    yield
    
    # Shutdown: Cleanup operations
    logger.info("Shutting down application...")
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        logger.info("Heartbeat monitor task cancelled")

# Create FastAPI app
app = FastAPI(
    title="MyApp API",
    description="FastAPI backend with PostgreSQL and SQLAlchemy async",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(rooms_router, prefix="/rooms", tags=["Rooms"])
app.include_router(friends_router, prefix="/friends", tags=["Friends"])

# SocketIO event handlers
@sio.event
async def connect(sid, environ, auth):
    logger.info(f"Client connected: {sid}")
    last_heartbeat[sid] = time.time()  # Initialize heartbeat tracking


@sio.event
async def join(sid, data):
    room_id = data.get('room_id')
    username = data.get('username')

    if not room_id or not username:
        logger.error(f"Invalid join data - room_id: {room_id}, username: {username}")
        await sio.emit('join_success', {
            'success': False,
            'error': 'Invalid data provided'
        }, to=sid)
        return

    try:
        room_id = int(room_id)
        db = await create_session()

        try:
            # 🔍 تحقق هل اللاعب موجود بالفعل في نفس الغرفة
            existing = await db.execute(
                select(RoomPlayer).filter_by(room_id=room_id, player_username=username)
            )
            existing_player = existing.scalars().first()

            if not existing_player:
                # 🧹 إزالة أي عضوية سابقة في غرف أخرى فقط
                old_membership = await db.execute(
                    select(RoomPlayer).filter(RoomPlayer.player_username == username)
                )
                old_player = old_membership.scalars().first()
                if old_player:
                    await db.delete(old_player)
                    logger.info(f"Removed player {username} from old room {old_player.room_id}")

                # ✅ تحقق من الغرفة
                room_result = await db.execute(select(Room).filter(Room.id == room_id))
                room = room_result.scalars().first()

                if not room:
                    await sio.emit('join_success', {
                        'success': False,
                        'error': 'Room not found'
                    }, to=sid)
                    return

                if room.current_players >= room.max_players:
                    await sio.emit('join_success', {
                        'success': False,
                        'error': 'Room is full'
                    }, to=sid)
                    return

                # ➕ إضافة اللاعب
                is_host = (room.current_players == 0)
                player = RoomPlayer(
                    room_id=room_id,
                    player_username=username,
                    username=username,
                    is_host=is_host
                )
                db.add(player)
                room.current_players += 1

                # 🔁 تحديث المالك
                if is_host:
                    room.owner_username = username

                await db.commit()
                logger.info(f"Added new player {username} to room {room_id}")
            else:
                player = existing_player
                logger.info(f"Player {username} already in room {room_id}")

            # 🌐 ضم اللاعب لغرفة socket
            await sio.enter_room(sid, str(room_id))
            client_rooms[sid] = {'username': username, 'room_id': room_id}
            last_heartbeat[sid] = time.time()

            await sio.emit('user_joined', {'username': username, 'room_id': room_id}, room=str(room_id))
            players = await get_players_for_room(db, room_id)
            await sio.emit('update_players', {'players': players}, room=str(room_id))
            await sio.emit('join_success', {
                'success': True,
                'room_id': room_id,
                'username': username,
                'is_host': player.is_host
            }, to=sid)

        except Exception as e:
            logger.error(f"Database error in join event: {e}")
            await sio.emit('join_success', {
                'success': False,
                'error': 'Database error'
            }, to=sid)

        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Error in join event: {e}")
        await sio.emit('join_success', {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }, to=sid)


@sio.event
async def leave(sid, data):
    room_id = data.get('room_id')
    username = data.get('username')
    
    if not room_id or not username:
        return

    try:
        room_id = int(room_id)
    except (ValueError, TypeError):
        logger.error(f"Invalid room_id format: {room_id}")
        return

    logger.info(f"User {username} explicitly leaving room {room_id}")
    sio.leave_room(sid, str(room_id))

    if sid in client_rooms:
        del client_rooms[sid]

    db = await create_session()
    try:
        # Fetch player
        player_result = await db.execute(select(RoomPlayer).filter(
            RoomPlayer.room_id == room_id,
            RoomPlayer.player_username == username
        ))
        player = player_result.scalars().first()

        # Fetch room
        room_result = await db.execute(select(Room).filter(Room.id == room_id))
        room = room_result.scalars().first()

        if player and room:
            await db.delete(player)
            room.current_players -= 1

            # حذف المستخدم من VPN
            if room.vpn_hub:
                vpn = SoftEtherVPN()
                try:
                    await vpn.delete_user(room.vpn_hub, player.username)
                    logger.info(f"Deleted VPN user {player.username} from hub {room.vpn_hub}")
                except Exception as e:
                    logger.error(f"Error deleting VPN user: {e}")

            # إذا كان آخر لاعب
            if room.current_players <= 0:
                logger.info(f"Room {room_id} is now empty. Cleaning up...")

                if room.vpn_hub:
                    try:
                        vpn = SoftEtherVPN()
                        result = await vpn.delete_hub(room.vpn_hub)
                        if result:
                            logger.info(f"Deleted VPN hub {room.vpn_hub}")
                        else:
                            # Try with direct hub name
                            hub_name = f"room_{room_id}"
                            result = await vpn.delete_hub(hub_name)
                            if result:
                                logger.info(f"Successfully deleted VPN hub on second attempt: {hub_name}")
                            else:
                                logger.warning(f"Failed to delete VPN hub: {room.vpn_hub}")
                    except Exception as e:
                        logger.error(f"Error deleting VPN hub: {str(e)}")

                await db.execute(ChatMessage.__table__.delete().where(ChatMessage.room_id == room.id))
                await db.delete(room)
                await sio.emit('room_closed', {'room_id': room_id})
            else:
                # إعادة تعيين المالك إذا كان المغادر هو المضيف
                if player.is_host:
                    next_host_result = await db.execute(
                        select(RoomPlayer).filter(RoomPlayer.room_id == room_id)
                    )
                    new_host = next_host_result.scalars().first()
                    if new_host:
                        new_host.is_host = True
                        room.owner_username = new_host.player_username
                        await sio.emit('host_changed', {'new_host': new_host.player_username}, room=str(room_id))

                # إعلام الجميع بخروجه وتحديث القائمة
                await sio.emit('user_left', {'username': username, 'room_id': room_id}, room=str(room_id))
                players_result = await db.execute(select(RoomPlayer).filter(RoomPlayer.room_id == room_id))
                players = [p.player_username for p in players_result.scalars().all()]
                await sio.emit('update_players', {'players': players}, room=str(room_id))

        await db.commit()

    except Exception as e:
        logger.error(f"Error in leave event: {e}")
        await db.rollback()
    finally:
        await db.close()


@sio.event
async def heartbeat(sid, data):
    """Handle heartbeat from client to keep track of active connections"""
    if sid in last_heartbeat:
        last_heartbeat[sid] = time.time()
        
        # Update room info if provided
        if data and 'room_id' in data and 'username' in data:
            client_rooms[sid] = {
                'username': data['username'],
                'room_id': data['room_id']
            }

@sio.event
async def send_message(sid, data):
    room_id = data.get('room_id')
    username = data.get('username')
    message = data.get('message')
    
    if not all([room_id, username, message]):
        await sio.emit('error', {'message': 'Invalid message data'}, to=sid)
        return

    try:
        room_id = int(room_id)
    except (ValueError, TypeError):
        logger.error(f"Invalid room_id format: {room_id}")
        await sio.emit('error', {'message': 'Invalid room ID format'}, to=sid)
        return

    last_heartbeat[sid] = time.time()

    db = await create_session()
    try:
        chat_message = ChatMessage(
            room_id=room_id,
            username=username,
            message=message
        )
        db.add(chat_message)
        await db.commit()
        await db.refresh(chat_message)

        await sio.emit('new_message', {
    'username': username,  # ✅ عدّل من 'sender' إلى 'username'
    'message': message,
    'room_id': room_id,
    'created_at': chat_message.created_at.isoformat()
}, room=str(room_id))

    except Exception as e:
        logger.error(f"Error saving message: {e}")
        await db.rollback()
        await sio.emit('error', {'message': 'Failed to send message'}, to=sid)
    finally:
        await db.close()


@sio.event
async def check_player(sid, data):
    room_id = data.get('room_id')
    username = data.get('username')
    logger.info(f"[check_player] called for username={username}, room_id={room_id}")
    if not all([room_id, username]):
        return {'exists': False}
    try:
        room_id = int(room_id)
        db = await create_session()
        try:
            query = select(RoomPlayer).filter(
                RoomPlayer.room_id == room_id,
                RoomPlayer.player_username == username
            )
            result = await db.execute(query)
            player = result.scalars().first()
            exists = player is not None
            logger.info(f"[check_player] DB result: player={player}, exists={exists}")
            return {'exists': exists}
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Error checking player existence: {e}")
        return {'exists': False}

@sio.event
async def start_game(sid, data):
    """Start game in the room"""
    room_id = data.get('room_id')
    
    if not room_id:
        return
    
    try:
        room_id = int(room_id)  # Convert room_id to integer
    except (ValueError, TypeError):
        logger.error(f"Invalid room_id format: {room_id}")
        await sio.emit('error', {'message': 'Invalid room ID format'}, to=sid)
        return
    
    # Update heartbeat
    last_heartbeat[sid] = time.time()
    
    # Broadcast game start event to room
    await sio.emit('game_started', {
        'room_id': room_id,
        'started_at': datetime.now().isoformat()
    }, room=str(room_id))

# Create socketio app
socket_app = socketio.ASGIApp(sio, app)

# Run with: uvicorn main:socket_app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:socket_app", 
        host="0.0.0.0", 
        port=5000, 
        reload=True
    ) 