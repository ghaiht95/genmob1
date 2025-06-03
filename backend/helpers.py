# helpers.py
import asyncio
import time
from sqlalchemy.future import select

# Local imports from this new structure
from shared import logger, sio, client_rooms, last_heartbeat, NAMESPACE
from database.database import create_session, get_session # Added get_session as it might be used by helpers indirectly or directly
from models import Room, RoomPlayer, ChatMessage
from services.Wiregruad import WiregruadVPN

async def get_players_for_room(db, room_id):
    """Get all players in a room as a list of dicts with player_username and is_host"""
    query = select(RoomPlayer).filter(RoomPlayer.room_id == room_id)
    result = await db.execute(query)
    players = result.scalars().all()
    return [
        {
            'username': player.player_username,
            'is_host': player.is_host
        }
        for player in players
    ]

async def handle_player_leave(username, room_id, db, sid=None):
    logger.info(f"[LEAVE] Handling player leave: {username} from room {room_id}")
    
    try:
        # جلب الغرفة
        room_result = await db.execute(select(Room).filter(Room.id == room_id))
        room = room_result.scalars().first()
        if not room:
            logger.warning(f"Room {room_id} not found.")
            return

        # جلب اللاعب
        player_result = await db.execute(
            select(RoomPlayer).filter_by(room_id=room_id, player_username=username)
        )
        player = player_result.scalars().first()
        if not player:
            logger.warning(f"Player {username} not found in room {room_id}")
            return

        is_host_leaving = player.is_host  # حفظ حالة المضيف قبل الحذف

        # حذف اللاعب من VPN
        if room.network_name:
            try:
                vpn = WiregruadVPN()
                await vpn.check_user_in_network_config(db, room.network_name, player.player_username)
                logger.info(f"✅ VPN user {player.player_username} removed from network")
            except Exception:
                logger.exception("❌ Error removing VPN user")

        # حذف اللاعب من قاعدة البيانات
        await db.delete(player)
        logger.info("✅ Player removed from DB")

        # جلب اللاعبين المتبقين من القاعدة بعد الحذف
        remaining_players_result = await db.execute(
            select(RoomPlayer).filter(RoomPlayer.room_id == room_id)
        )
        remaining_players = remaining_players_result.scalars().all()

        room.current_players = len(remaining_players)
        logger.info(f"🧮 Remaining players count: {room.current_players}")

        if room.current_players == 0:
            logger.info("🗑 No players left. Deleting room and shutting down VPN network")
            try:
                if room.network_name:
                    vpn = WiregruadVPN()
                    await vpn.down_network_config(db, room.network_name)
                    logger.info("✅ VPN network shut down")
            except Exception:
                logger.exception("❌ Error shutting down VPN network")
            
            await db.execute(ChatMessage.__table__.delete().where(ChatMessage.room_id == room.id))
            await db.delete(room)
            logger.info("✅ Room and chat deleted")
            await sio.emit('room_closed', {'room_id': room_id}, room=str(room_id))
            await sio.emit('update_rooms', {}, namespace=NAMESPACE)
        else:
            # إعادة تعيين الهوست إذا كان المضيف هو من خرج
            if is_host_leaving:
                new_host = remaining_players[0]
                new_host.is_host = True
                room.owner_username = new_host.player_username
                logger.info(f"👑 New host assigned: {new_host.player_username}")
                await sio.emit('host_changed', {
                    'new_host': new_host.player_username,
                    'room_id': room_id
                }, room=str(room_id))

            # إرسال التحديثات
            players = await get_players_for_room(db, room_id)
            await sio.emit('update_players', {
                'players': players
            }, room=str(room_id))
            await sio.emit('user_left', {
                'username': username,
                'room_id': room_id
            }, room=str(room_id))
            await sio.emit('update_rooms', {}, namespace=NAMESPACE)
            logger.info("✅ Updates emitted")

        await db.commit()
        logger.info("✅ DB committed")

        # تنظيف بيانات العميل إذا تم تمرير sid
        if sid:
            client_rooms.pop(sid, None)
            last_heartbeat.pop(sid, None)

    except Exception:
        logger.exception("❌ Exception in handle_player_leave")
        await db.rollback()
        raise

async def check_heartbeats():
    """Background task to check for stale connections"""
    while True:
        try:
            current_time = time.time()
            stale_clients = []
            
            for sid, last_time in list(last_heartbeat.items()):
                if current_time - last_time > 40:  # 40 seconds timeout
                    stale_clients.append(sid)
            
            for sid in stale_clients:
                logger.warning(f"Client {sid} detected as stale (no heartbeat)")
                
                if sid in client_rooms:
                    client_data = client_rooms[sid]
                    db = await create_session()
                    try:
                        await handle_player_leave(
                            client_data['username'], 
                            client_data['room_id'],
                            db,
                            sid
                        )
                    except Exception as e:
                        logger.error(f"Error handling stale client leave: {e}")
                    finally:
                        await db.close()
                    
                    del client_rooms[sid]
                
                if sid in last_heartbeat:
                    del last_heartbeat[sid]
                    
        except Exception as e:
            logger.error(f"Error in heartbeat monitor: {str(e)}")
            
        await asyncio.sleep(20) 