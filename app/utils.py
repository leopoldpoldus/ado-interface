# app/utils.py
import hashlib

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def compute_pat_fingerprint(pat: str) -> str:
    return hashlib.sha256(pat.encode("utf-8")).hexdigest()


def transform_work_item(raw_item: dict) -> dict:
    fields = raw_item.get("fields", {})
    assigned_to = fields.get("System.AssignedTo", {})
    return {
        "id": raw_item.get("id"),
        "title": fields.get("System.Title"),
        "description": fields.get("System.Description"),
        "state": fields.get("System.State"),
        "createdDate": fields.get("System.CreatedDate"),
        "assignedTo": {
            "displayName": assigned_to.get("displayName"),
            "uniqueName": assigned_to.get("uniqueName"),
            "avatarUrl": assigned_to.get("_links", {}).get("avatar", {}).get("href")
        },
        "url": raw_item.get("url")
    }