#!/usr/bin/env python
"""
سكريبت لتهيئة قاعدة البيانات وإنشاء الجداول الأولية
"""
import asyncio
import logging
import sys
import os
from sqlalchemy import text

# إضافة المسار الرئيسي للمشروع إلى path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import Base, User
from backend.database.database import engine, async_session_factory
from backend.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    logger.info("بدء تهيئة قاعدة البيانات...")
    
    async with engine.begin() as conn:
        # التحقق مما إذا كانت الجداول موجودة بالفعل
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("تم إنشاء الجداول بنجاح")
    
    # إنشاء مستخدم افتراضي إذا لم يكن هناك مستخدمين
    async with async_session_factory() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM "user"'))
        count = result.scalar()
        
        if count == 0:
            logger.info("إنشاء مستخدم افتراضي...")
            admin_user = User(
                username="admin",
                email="admin@example.com"
            )
            admin_user.set_password("admin123")
            
            session.add(admin_user)
            await session.commit()
            logger.info("تم إنشاء المستخدم الافتراضي بنجاح")
        else:
            logger.info(f"المستخدمون موجودون بالفعل في قاعدة البيانات: {count}")
    
    logger.info("اكتملت تهيئة قاعدة البيانات بنجاح!")

async def run_migrations():
    """تنفيذ ملفات الهجرة باستخدام Alembic (إذا لزم الأمر)"""
    try:
        import alembic.config
        logger.info("تنفيذ ملفات الهجرة...")
        
        alembic_args = [
            '--raiseerr',
            'upgrade', 'head',
        ]
        alembic.config.main(argv=alembic_args)
        
        logger.info("تم تنفيذ ملفات الهجرة بنجاح")
    except Exception as e:
        logger.error(f"حدث خطأ أثناء تنفيذ ملفات الهجرة: {e}")

if __name__ == "__main__":
    logger.info("بدء تشغيل سكريبت تهيئة قاعدة البيانات")
    
    # تنفيذ الوظائف بالترتيب
    asyncio.run(run_migrations())
    asyncio.run(init_db())
    
    logger.info("اكتمل سكريبت تهيئة قاعدة البيانات") 