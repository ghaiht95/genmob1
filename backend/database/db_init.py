import os
import sys
import asyncio
import logging

# إضافة المسار إلى PYTHONPATH للسماح بالاستيراد
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.schema import DropTable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.ddl import CreateTable
from database.base import Base
# تأكد ما فيه استيراد دائري يرجع لـ models قبل تعريف Base

from config import settings

from database.database import engine, async_session_factory

logger = logging.getLogger(__name__)

async def clear_database():
    """تفريغ قاعدة البيانات وإعادة تهيئتها بجداول فارغة بطريقة غير متزامنة"""
    
    async with engine.begin() as conn:
        try:
            # حذف جميع الجداول
            logger.info("جاري حذف جميع الجداول...")
            await conn.run_sync(Base.metadata.drop_all)
            
            # إعادة إنشاء الجداول
            logger.info("جاري إعادة إنشاء الجداول...")
            await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✅ تم تفريغ قاعدة البيانات بنجاح وإعادة تهيئة الجداول الفارغة!")
            return True
        except Exception as e:
            logger.error(f"❌ حدث خطأ أثناء تهيئة قاعدة البيانات: {e}")
            raise

async def drop_table(table_name):
    """حذف جدول محدد من قاعدة البيانات"""
    if not table_name:
        logger.error("اسم الجدول مطلوب")
        return False
    
    try:
        # الحصول على الجدول المطلوب حذفه
        table = None
        for t in Base.metadata.sorted_tables:
            if t.name == table_name:
                table = t
                break
        
        if not table:
            logger.error(f"الجدول {table_name} غير موجود")
            return False
        
        # حذف الجدول
        async with engine.begin() as conn:
            await conn.execute(DropTable(table))
            
        logger.info(f"✅ تم حذف الجدول {table_name} بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ حدث خطأ أثناء حذف الجدول {table_name}: {e}")
        return False

async def create_table(table_name):
    """إنشاء جدول محدد في قاعدة البيانات"""
    if not table_name:
        logger.error("اسم الجدول مطلوب")
        return False
    
    try:
        # الحصول على الجدول المطلوب إنشاءه
        table = None
        for t in Base.metadata.sorted_tables:
            if t.name == table_name:
                table = t
                break
        
        if not table:
            logger.error(f"الجدول {table_name} غير موجود في الـ metadata")
            return False
        
        # إنشاء الجدول
        async with engine.begin() as conn:
            await conn.execute(CreateTable(table))
            
        logger.info(f"✅ تم إنشاء الجدول {table_name} بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ حدث خطأ أثناء إنشاء الجدول {table_name}: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(clear_database()) 