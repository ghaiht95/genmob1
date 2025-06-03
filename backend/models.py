from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from database.base import Base
import re
from passlib.context import CryptContext
from typing import Optional, Tuple, Union

# سياق تشفير كلمات المرور
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(100), nullable=False)
    verification_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    private_key = Column(LargeBinary, nullable=True)  # WireGuard keys are 44 chars
    public_key = Column(LargeBinary, nullable=True)   # WireGuard keys are 44 chars

    # علاقات ORM
    messages = relationship("ChatMessage", back_populates="sender", cascade="all, delete-orphan")
    owned_rooms = relationship('Room', back_populates='owner', foreign_keys='Room.owner_username')
    rooms = relationship('RoomPlayer', back_populates='player')
    network_config_user = relationship('network_config_user', back_populates='user')

    def set_password(self, password: str):
        self.password_hash = pwd_context.hash(password)

    def check_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.password_hash)

    @staticmethod
    def validate_username(username: str) -> bool:
        return bool(username and len(username) >= 3 and re.match(r'^[a-zA-Z0-9_]+$', username))

    @staticmethod
    def validate_email(email: str) -> bool:
        return bool(email and re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


class Friendship(Base):
    __tablename__ = "friendship"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    friend_id = Column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    status = Column(String(20), default='pending')  # values: pending, accepted, declined
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # علاقات ORM
    user = relationship('User', foreign_keys=[user_id], backref='sent_requests')
    friend = relationship('User', foreign_keys=[friend_id], backref='received_requests')

    __table_args__ = (
        UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),
    )


class Room(Base):
    __tablename__ = 'room'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    owner_username = Column(String(100), ForeignKey('user.username'), nullable=False, index=True)
    description = Column(Text)
    is_private = Column(Boolean, default=False)
    password = Column(String(100))
    max_players = Column(Integer, default=8)
    current_players = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    network_name = Column(String(100), ForeignKey('network_config.network_name', ondelete='CASCADE'), nullable=True, index=True)

    # علاقات ORM
    players = relationship("RoomPlayer", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")
    owner = relationship("User", back_populates="owned_rooms")
    network_configs = relationship("network_config", back_populates="room")

    @staticmethod
    def validate_name(name: str) -> bool:
        return bool(name and len(name) >= 3 and re.match(r'^[a-zA-Z0-9_\s-]+$', name))


class RoomPlayer(Base):
    __tablename__ = 'room_player'

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='CASCADE'), nullable=False, index=True)
    player_username = Column(String(100), ForeignKey('user.username'), nullable=False, index=True)
    username = Column(String(100), nullable=False)
    is_host = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    # علاقات ORM
    room = relationship('Room', back_populates='players')
    player = relationship('User', back_populates='rooms')

    __table_args__ = (
        UniqueConstraint('room_id', 'player_username', name='unique_player_in_room'),
    )


class ChatMessage(Base):
    __tablename__ = 'chat_message'

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='CASCADE'), nullable=False, index=True)
    username = Column(String(100), ForeignKey('user.username'), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # علاقات ORM
    room = relationship('Room', back_populates='messages', passive_deletes=True)
    sender = relationship('User', back_populates='messages')

    @staticmethod
    def validate_message(message: str) -> bool:
        return bool(message and 0 < len(message.strip()) <= 1000)


class network_config(Base):
    __tablename__ = 'network_config'
    id = Column(Integer, primary_key=True)
    private_key = Column(LargeBinary, nullable=True)  # WireGuard keys are 44 chars
    public_key = Column(LargeBinary, nullable=True)   # WireGuard keys are 44 chars
    server_ip = Column(String(100), nullable=True)
    port = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=False)
    network_name = Column(String(100), nullable=True, unique=True)

    # علاقات ORM
    room = relationship('Room', back_populates='network_configs')
    network_config_user = relationship('network_config_user', back_populates='network_config', cascade="all, delete-orphan")


class network_config_user(Base):
    __tablename__ = 'network_config_user'
    id = Column(Integer, primary_key=True)
    network_config_id = Column(Integer, ForeignKey('network_config.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    allowed_ips = Column(String(100), nullable=True)
    
    # علاقات ORM
    network_config = relationship('network_config', back_populates='network_config_user')
    user = relationship('User', back_populates='network_config_user')