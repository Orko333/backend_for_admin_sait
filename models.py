from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='client')
    email = Column(String(255), unique=True, index=True, nullable=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Order(Base):
    __tablename__ = 'orders'
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), index=True)
    first_name = Column(String(200))
    username = Column(String(100))
    phone_number = Column(String(50))
    type_label = Column(String(100))
    order_type = Column(String(100))
    topic = Column(Text)
    subject = Column(Text)
    deadline = Column(String(100))
    volume = Column(String(100))
    requirements = Column(Text)
    files = Column(JSON)
    price = Column(Integer)
    status = Column(String(50), default='draft', index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    manager_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    notes = Column(Text, nullable=True)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String(200))
    direction = Column(String(50))
    text = Column(Text)
    chat_id = Column(BigInteger)
    message_type = Column(String(50))
    order_id = Column(BigInteger, ForeignKey('orders.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Feedback(Base):
    __tablename__ = 'feedbacks'
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=True)
    username = Column(String(200))
    text = Column(Text)
    stars = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Promocode(Base):
    __tablename__ = 'promocodes'
    code = Column(String(100), primary_key=True)
    discount_type = Column(String(50))
    discount_value = Column(Integer)
    usage_limit = Column(Integer)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_personal = Column(Boolean, default=False)
    personal_user_id = Column(BigInteger, nullable=True)
    min_order_amount = Column(Integer, default=0)

class PromocodeUsage(Base):
    __tablename__ = 'promocode_usages'
    id = Column(BigInteger, primary_key=True)
    code = Column(String(100), ForeignKey('promocodes.code'))
    user_id = Column(BigInteger)
    order_id = Column(BigInteger)
    discount_amount = Column(Integer)
    used_at = Column(DateTime(timezone=True), server_default=func.now())

class OrderStatusHistory(Base):
    __tablename__ = 'order_status_history'
    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey('orders.id'))
    status = Column(String(50))
    changed_by = Column(BigInteger)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text)

class Referral(Base):
    __tablename__ = 'referrals'
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger)
    referred_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ReferralBonus(Base):
    __tablename__ = 'referral_bonuses'
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger)
    referred_user_id = Column(BigInteger)
    order_id = Column(BigInteger)
    bonus_amount = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

