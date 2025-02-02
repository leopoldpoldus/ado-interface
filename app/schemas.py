# app/schemas.py
from pydantic import BaseModel
from typing import Optional

# User schemas
class User(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    password: str


# Configuration schemas
class Config(BaseModel):
    azure_devops_org: str
    azure_devops_project: str
    api_version: str
    # Note: For security, we do not return the PAT.

    class Config:
        from_attributes = True  # or use orm_mode = True if you are on pydantic v1

class ConfigUpdate(BaseModel):
    azure_devops_org: Optional[str] = None
    azure_devops_project: Optional[str] = None
    azure_devops_pat: Optional[str] = None
    api_version: Optional[str] = None

# Token schema
class Token(BaseModel):
    access_token: str
    token_type: str

# Azure DevOps Work Item schemas
class WorkItemCreate(BaseModel):
    title: str
    description: str

class WorkItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None