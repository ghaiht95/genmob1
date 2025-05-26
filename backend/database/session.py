from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings  # استورد الإعدادات التي تحوي رابط DB

DATABASE_URL = settings.DATABASE_URL.replace("asyncpg", "psycopg2")  
# SQLAlchemy العادية تحتاج psycopg2 وليس asyncpg عند الاتصال المتزامن

engine = create_engine(
    DATABASE_URL,
    # لا تحتاج connect_args مع PostgreSQL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)