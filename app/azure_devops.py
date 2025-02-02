# app/azure_devops.py
import base64
from app.config import AZURE_DEVOPS_PAT, AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, API_VERSION

def get_auth_headers(pat: str = None) -> dict:
    """
    Create the basic authentication header.
    If a PAT is provided, use it; otherwise, use the default from configuration.
    """
    token = f":{pat or AZURE_DEVOPS_PAT}"
    encoded_token = base64.b64encode(token.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {encoded_token}"}

def get_base_url(config) -> str:
    """
    Construct the base URL for Azure DevOps API calls.
    """
    return f"https://dev.azure.com/{config['azure_devops_org']}/{config['azure_devops_project']}"