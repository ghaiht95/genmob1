import sys
import os

# ????? ???? backend ??? sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from sqlalchemy import select
from database.database import get_session
from models import Room, RoomPlayer, ChatMessage
from services.softether import SoftEtherVPN
from config import settings

vpn = SoftEtherVPN(
    admin_password=settings.SOFTETHER_ADMIN_PASSWORD,
    server_ip=settings.SOFTETHER_SERVER_IP,
    server_port=settings.SOFTETHER_SERVER_PORT
)

async def clean_all():
    async for db in get_session():
        rooms = (await db.execute(select(Room))).scalars().all()
        print("?? Deleting VPN hubs...")
        for room in rooms:
            hub_name = f"room_{room.id}"
            try:
                deleted = await vpn.delete_hub(hub_name)
                print(f"? Deleted VPN hub: {hub_name}" if deleted else f"?? Failed to delete hub: {hub_name}")
            except Exception as e:
                print(f"? Error deleting hub {hub_name}: {e}")

        print("?? Deleting RoomPlayer...")
        await db
