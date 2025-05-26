#!/usr/bin/env python3
"""
سكريبت لحذف هابات الغرف المحددة من خادم SoftEther VPN
"""
import logging
import sys
import asyncio
import os

# إضافة المسار الرئيسي للمشروع إلى path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.softether import SoftEtherVPN
from config import settings

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# قائمة هابات الغرف المراد حذفها
ROOM_HUBS = ["room_1", "room_12", "room_17", "room_18"]

async def delete_hub(vpn, hub_name):
    """حذف هاب محدد من خادم VPN"""
    logger.info(f"جاري حذف الهاب: {hub_name}")
    
    try:
        result = await vpn.delete_hub(hub_name)
        
        if result:
            logger.info(f"تم حذف الهاب بنجاح: {hub_name}")
            return True
        else:
            logger.error(f"فشل في حذف الهاب: {hub_name}")
            return False
            
    except Exception as e:
        logger.error(f"خطأ في حذف الهاب {hub_name}: {str(e)}")
        return False

async def main():
    """الدالة الرئيسية لحذف جميع هابات الغرف المحددة"""
    logger.info("=== بدء عملية حذف هابات الغرف من VPN ===")
    
    # تهيئة متغير SoftEtherVPN
    vpn = SoftEtherVPN()
    
    success_count = 0
    failure_count = 0
    
    for hub in ROOM_HUBS:
        if await delete_hub(vpn, hub):
            success_count += 1
        else:
            failure_count += 1
        
        # الانتظار قليلاً بين محاولات الحذف
        await asyncio.sleep(1)
    
    logger.info("=== ملخص عملية حذف هابات الغرف ===")
    logger.info(f"إجمالي هابات الغرف التي تمت معالجتها: {len(ROOM_HUBS)}")
    logger.info(f"تم حذفها بنجاح: {success_count}")
    logger.info(f"فشل في الحذف: {failure_count}")
    
    return success_count > 0

if __name__ == "__main__":
    success = asyncio.run(main())
    exit_code = 0 if success else 1
    logger.info(f"=== اكتملت عملية حذف هابات الغرف من VPN بحالة: {'نجاح' if success else 'فشل'} ===")
    sys.exit(exit_code) 