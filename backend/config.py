import os
from dotenv import load_dotenv
from typing import Optional
from pydantic import BaseSettings
from pydantic import PostgresDsn
import logging

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # API Settings
    API_BASE_URL: str = "http://localhost:5000"
    FLASK_DEBUG: bool = True
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Database Settings
    POSTGRES_USER: str = "ghaith"
    POSTGRES_PASSWORD: str = "O3gel6!Q3G8ODcBluHdBZr"
    POSTGRES_DB: str = "test_game_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    DATABASE_PATH: str = "dbdata/app.db"

    # VPN Settings
    SOFTETHER_ADMIN_PASSWORD: str = "IDucIsWea45RcQUEijpPih"
    SOFTETHER_SERVER_IP: str = "31.220.80.192"  # تحديث عنوان IP السيرفر
    SOFTETHER_SERVER_PORT: int = 5555  # تحديث المنفذ
    VPNCMD_PATH: str = "/root/vpnserver/vpncmd"
    CONFIG_DIR: str = "/projckt/APP_CLEN/backend/ROOM_CONFIG"
    
    # VPN Network Settings
    VPN_NETWORK: str = "10.0.0.0"  # شبكة VPN الأساسية
    VPN_NETMASK: str = "255.255.255.0"  # قناع الشبكة
    VPN_START_IP: str = "10.0.0.1"  # أول عنوان IP متاح
    VPN_END_IP: str = "10.0.0.254"  # آخر عنوان IP متاح
    VPN_MAC_PREFIX: str = "02:"  # بادئة عنوان MAC
    
    # Other Settings
    NM_API_URL: str = "https://api.example.com"
    MASTER_KEY: str = "your-master-key"
    
    DEBUG: bool = True
    
    CORS_ORIGINS: list = ["http://localhost:5000"]
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    SECRET_KEY: str = "yhbM8^I!76IL2Cx@3vxXG9qSk1r8T"
    ALGORITHM: str = "HS256"
    
    @property
    def DATABASE_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from environment variables

# Create settings instance
settings = Settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
