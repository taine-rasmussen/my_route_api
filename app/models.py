from sqlalchemy import Column, Integer, String, Text, DateTime, func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    location = Column(String(50), nullable=False)
    home_gym = Column(String(50), nullable=True)
    grade_style = Column(String(50), nullable=False)
