# app/crud.py
from typing import Optional

from sqlalchemy.orm import Session
from app.models import UserModel
from app.schemas import UserCreate
from app.utils import get_password_hash, verify_password, compute_pat_fingerprint  # Import password utility from utils

def get_user_by_username(db: Session, username: str):
    return db.query(UserModel).filter(UserModel.username == username).first()

def get_user_by_pat(db: Session, pat: str) -> Optional[UserModel]:
    """
    Quickly query for a user by computing a fingerprint of the provided PAT.
    Then verify the full (salted) hashed password using the secure verification function.
    """
    fingerprint = compute_pat_fingerprint(pat)
    user = db.query(UserModel).filter(UserModel.pat_fingerprint == fingerprint).first()
    if user and verify_password(pat, user.hashed_password):
        return user
    return None


def create_user(db: Session, user: UserCreate) -> UserModel:
    hashed_password = get_password_hash(user.password)
    fingerprint = compute_pat_fingerprint(user.password)
    db_user = UserModel(
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        pat_fingerprint=fingerprint
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user