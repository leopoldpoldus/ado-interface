# app/auth.py
from fastapi import HTTPException, Depends, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import get_user_by_pat  # Still import from crud, which is OK now.

def get_api_key(x_pat: str = Header(..., alias="X-Azure-DevOps-PAT"), db: Session = Depends(get_db)):
    # Implement your logic to look up the user by the provided PAT.
    # For example, you might have a function get_user_by_pat(x_pat)
    user = get_user_by_pat(db, x_pat)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user