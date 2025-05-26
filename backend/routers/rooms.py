from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database import get_session
from models import Room, RoomPlayer, ChatMessage, User
from config import settings
from services.softether import SoftEtherVPN
import random
import logging
from routers.friends import get_current_user
from shared import sio, NAMESPACE

router = APIRouter()
logger = logging.getLogger(__name__)

# إعداد VPN
vpn = SoftEtherVPN(
    admin_password=settings.SOFTETHER_ADMIN_PASSWORD,
    server_ip=settings.SOFTETHER_SERVER_IP,
    server_port=settings.SOFTETHER_SERVER_PORT
)

@router.get("/")
async def root_get_rooms(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    try:
        result = await db.execute(select(Room))
        rooms_query = result.scalars().all()
        rooms_list = []
        for room in rooms_query:
            rooms_list.append({
                "id": room.id,
                "room_id": room.id,
                "room_name": room.name,
                "owner_username": room.owner_username,
                "description": room.description,
                "is_private": room.is_private,
                "max_players": room.max_players,
                "current_players": room.current_players
            })
        return {"rooms": rooms_list}
    except Exception as e:
        logger.error(f"Error fetching rooms: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rooms")

@router.get("/get_rooms")
async def get_rooms(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    try:
        result = await db.execute(select(Room))
        rooms_query = result.scalars().all()
        rooms_list = []
        for room in rooms_query:
            rooms_list.append({
                "id": room.id,
                "room_id": room.id,
                "room_name": room.name,
                "owner_username": room.owner_username,
                "description": room.description,
                "is_private": room.is_private,
                "max_players": room.max_players,
                "current_players": room.current_players
            })
        return {"rooms": rooms_list}
    except Exception as e:
        logger.error(f"Error fetching rooms: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rooms")

@router.post("/create_room")
async def create_room(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    data = await request.json()
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="Room name is required")
    
    # Check if user is already in a room
    existing_player = await db.execute(
        select(RoomPlayer).filter_by(player_username=current_user.email)
    )
    existing_player = existing_player.scalars().first()
    
    if existing_player:
        # User is already in a room, return that room's information
        room = await db.get(Room, existing_player.room_id)
        if not room:
            # If room doesn't exist, remove the player entry and continue with room creation
            await db.delete(existing_player)
            await db.commit()
        else:
            return {
                "id": room.id,
                "room_id": room.id,
                "vpn_hub": room.vpn_hub,
                "vpn_username": existing_player.username,
                "vpn_password": "REUSEDPASSWORD",  # We don't store the original password
                "server_ip": settings.SOFTETHER_SERVER_IP,
                "port": settings.SOFTETHER_SERVER_PORT,
                "message": "You are already in a room. Using existing connection."
            }
    
    existing = await db.execute(select(Room).filter_by(name=data["name"]))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Room name already exists")
    
    room = Room(
        name=data["name"],
        owner_username=current_user.email,
        description=data.get("description", ""),
        is_private=data.get("is_private", False),
        password=data.get("password", ""),
        max_players=data.get("max_players", 8),
        current_players=1
    )
    db.add(room)
    await db.flush()
    hub_name = f"room_{room.id}"
    room.vpn_hub = hub_name

    logger.info(f"Creating VPN hub: {hub_name}")
    try:
        if not await vpn.create_hub(hub_name):
            logger.error(f"Failed to create VPN hub: {hub_name}")
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create VPN hub")
        username = current_user.email.split('@')[0]
        vpn_password = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
        if not await vpn.create_user(hub_name, username, vpn_password):
            logger.error(f"Failed to create VPN user: {username} in hub: {hub_name}")
            await vpn.delete_hub(hub_name)
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create VPN user")
        rp = RoomPlayer(room_id=room.id, player_username=current_user.email, username=username, is_host=True)
        db.add(rp)
        await db.commit()
        await sio.emit('update_rooms', {}, namespace=NAMESPACE)
        return {
            "id": room.id,
            "room_id": room.id,
            "vpn_hub": hub_name,
            "vpn_username": username,
            "vpn_password": vpn_password,
            "server_ip": settings.SOFTETHER_SERVER_IP,
            "port": settings.SOFTETHER_SERVER_PORT
        }
    except Exception as e:
        logger.error(f"Exception during room creation: {str(e)}")
        try:
            await vpn.delete_hub(hub_name)
        except:
            pass
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating room: {str(e)}")

@router.post("/join_room")
async def join_room(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    data = await request.json()
    if not data.get("room_id"):
        raise HTTPException(status_code=400, detail="Room ID is required")

    # ✅ التحقق من وجود الغرفة
    room_result = await db.execute(select(Room).filter_by(id=data["room_id"]))
    room = room_result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # ✅ التحقق من كلمة المرور إذا كانت الغرفة خاصة
    if room.is_private and room.password:
        if not data.get("password") or data["password"] != room.password:
            raise HTTPException(status_code=401, detail="Invalid room password")

    # ✅ التحقق من وجود اللاعب في الغرفة
    existing_player = await db.execute(
        select(RoomPlayer).filter_by(room_id=room.id, player_username=current_user.email)
    )
    existing_player = existing_player.scalars().first()

    if existing_player:
        hub_name = f"room_{room.id}"
        return {
            "room_id": room.id,
            "vpn_hub": hub_name,
            "vpn_username": existing_player.username,
            "vpn_password": "REUSEDPASSWORD",
            "server_ip": settings.SOFTETHER_SERVER_IP,
            "port": settings.SOFTETHER_SERVER_PORT,
            "message": "You are already in this room. Using existing connection."
        }

    # ✅ التحقق من السعة
    players_count = (await db.execute(
        select(RoomPlayer).filter_by(room_id=room.id)
    )).scalars().all()

    if len(players_count) >= room.max_players:
        raise HTTPException(status_code=400, detail="Room is full")

    # ✅ إنشاء مستخدم جديد في VPN
    hub_name = f"room_{room.id}"
    vpn_username = current_user.email.split('@')[0]
    vpn_password = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))

    if not await vpn.create_user(hub_name, vpn_username, vpn_password):
        logger.error(f"Failed to create VPN user: {vpn_username} in hub: {hub_name}")
        raise HTTPException(status_code=500, detail="Failed to create VPN user")

    # ✅ إضافة اللاعب للغرفة
    rp = RoomPlayer(
        room_id=room.id,
        player_username=current_user.email,
        username=vpn_username,
        is_host=(room.current_players == 0)
    )
    db.add(rp)
    room.current_players += 1
    if room.current_players == 1:
        room.owner_username = current_user.email

    await db.commit()
    await db.refresh(room)
    await sio.emit('update_rooms', {}, namespace=NAMESPACE)
    return {
        "room_id": room.id,
        "vpn_hub": hub_name,
        "vpn_username": vpn_username,
        "vpn_password": vpn_password,
        "server_ip": settings.SOFTETHER_SERVER_IP,
        "port": settings.SOFTETHER_SERVER_PORT,
        "message": "Joined room successfully"
    }

@router.post("/leave_room")
async def leave_room(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    data = await request.json()
    if not data.get("room_id"):
        raise HTTPException(status_code=400, detail="Room ID is required")
    
    try:
        room_id = int(data["room_id"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid room ID format")
    
    rp = await db.execute(select(RoomPlayer).filter_by(room_id=room_id, player_username=current_user.email))
    rp = rp.scalars().first()
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    hub_name = f"room_{room.id}"
    if rp:
        try:
            await vpn.delete_user(hub_name, rp.username)
        except Exception as e:
            logger.warning(f"Error deleting VPN user: {e}")
        await db.delete(rp)
        await db.flush()
    
    # تحقق من عدد اللاعبين بعد الحذف
    players_left = (await db.execute(select(RoomPlayer).filter_by(room_id=room.id))).scalars().all()
    room.current_players = len(players_left)

    if room.current_players == 0:
        # حذف الهب وحذف الغرفة والمحادثات
        try:
            await vpn.delete_hub(hub_name)
        except Exception as e:
            logger.warning(f"Error deleting VPN hub: {e}")
        await db.execute(ChatMessage.__table__.delete().where(ChatMessage.room_id == room.id))
        await db.delete(room)
        logger.info(f"Room {room.id} deleted after last player left.")
    else:
        # إعادة تعيين المضيف إذا خرج المضيف الحالي
        if rp and rp.is_host:
            new_host = (await db.execute(select(RoomPlayer).filter_by(room_id=room.id))).scalars().first()
            if new_host:
                new_host.is_host = True
                room.owner_username = new_host.player_username
                logger.info(f"New host assigned: {new_host.player_username}")
    
    await db.commit()
    await sio.emit('update_rooms', {}, namespace=NAMESPACE)
    return {"message": "left"}

@router.get("/vpn_status")
async def vpn_status(current_user: User = Depends(get_current_user)):
    try:
        result = await vpn.diagnose()
        return result
    except Exception as e:
        logger.error(f"Error diagnosing VPN server: {e}")
        raise HTTPException(status_code=500, detail="Failed to diagnose VPN server")

@router.get("/status")
async def rooms_status():
    return {"status": "ok",
            "socket_url":"http://31.220.80.192:5000"} 