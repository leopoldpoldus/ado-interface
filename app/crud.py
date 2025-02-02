# app/crud.py
from sqlalchemy.orm import Session
from app.models import UserModel
from app.schemas import UserCreate
from app.utils import get_password_hash  # Import password utility from utils

def get_user_by_username(db: Session, username: str):
    return db.query(UserModel).filter(UserModel.username == username).first()

def create_user(db: Session, user: UserCreate) -> UserModel:
    hashed_password = get_password_hash(user.password)
    db_user = UserModel(username=user.username, full_name=user.full_name, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user