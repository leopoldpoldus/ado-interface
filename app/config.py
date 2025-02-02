# app/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Azure DevOps configuration
AZURE_DEVOPS_ORG = os.getenv("AZURE_DEVOPS_ORG", "your-org")
AZURE_DEVOPS_PROJECT = os.getenv("AZURE_DEVOPS_PROJECT", "your-project")
AZURE_DEVOPS_PAT = os.getenv("AZURE_DEVOPS_PAT", "your-pat")
API_VERSION = os.getenv("API_VERSION", "7.1-preview.7")

# Application secrets and database URL
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db:5432/users_db")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Add ALGORITHM so it can be imported by other modules
ALGORITHM = os.getenv("ALGORITHM", "HS256")