from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database import get_session
from models import Room, RoomPlayer, ChatMessage, User
from config import settings
from services.Wiregruad import WiregruadVPN 
import random
import logging
from routers.friends import get_current_user
from shared import sio, NAMESPACE

router = APIRouter()
logger = logging.getLogger(__name__)

# إعداد VPN
vpn = WiregruadVPN()

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
                "network_name": room.network_name,	
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
    network_name = f"room_{room.id}"
    room.network_name = network_name

    logger.info(f"Creating VPN hub: {network_name}")
    try:
        if not await vpn.create_network_config(db):
            logger.error(f"Failed to create VPN hub: {network_name}")
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create VPN hub")
        
        rp = RoomPlayer(room_id=room.id, player_username=current_user.email, username=username, is_host=True)
        db.add(rp)
        await db.commit()
        await sio.emit('update_rooms', {}, namespace=NAMESPACE)
        return {
            "id": room.id,
            "room_id": room.id,
            "network_name": network_name,
        }
    except Exception as e:
        logger.error(f"Exception during room creation: {str(e)}")
        try:
            await db.delete(rp)
            await db.delete(room)
            await vpn.delete_network_config(db, network_name)
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
        return {
            "room_id": room.id,
            "network_name": room.network_name,
            "message": "You are already in this room. Using existing connection."
        }

    # ✅ التحقق من السعة
    players_count = (await db.execute(
        select(RoomPlayer).filter_by(room_id=room.id)
    )).scalars().all()

    if len(players_count) >= room.max_players:
        raise HTTPException(status_code=400, detail="Room is full")

    # ✅ إنشاء مستخدم جديد في VPN
    if not await vpn.push_user_to_network_config(db, room.network_name, username=current_user.email):
        logger.error(f"Failed to create VPN user: {current_user.email} in hub: {room.network_name}")
        raise HTTPException(status_code=500, detail="Failed to create VPN user")

    # ✅ إضافة اللاعب للغرفة
    rp = RoomPlayer(
        room_id=room.id,
        player_username=current_user.email,
        username=current_user.email,
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
        "private_key": current_user.private_key,
        "public_key": current_user.public_key,  
        "server_ip": room.network_name.server_ip,
        "port": room.network_name.port,
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


    if rp:
        try:
            await vpn.check_user_in_network_config(db, room.network_name, username=current_user.email)
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
            await vpn.down_network_config(db, room.network_name)
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