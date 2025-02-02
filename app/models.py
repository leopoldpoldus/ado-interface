# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # One-to-one relationship with UserConfig
    config = relationship("UserConfig", back_populates="user", uselist=False)


class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    azure_devops_org = Column(String, default="your-org")
    azure_devops_project = Column(String, default="your-project")
    azure_devops_pat = Column(String, default="your-pat")
    api_version = Column(String, default="7.1-preview.7")

    user = relationship("UserModel", back_populates="config")