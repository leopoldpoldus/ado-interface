# app/main.py
import sys

from fastapi import FastAPI, HTTPException, Depends, Body, Header, Path, Query
from sqlalchemy.orm import Session
import requests

from app.config import AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT, \
    API_VERSION
from app.database import engine, Base, get_db
from app.models import UserConfig
from app.schemas import User, UserCreate, WorkItemCreate, WorkItemUpdate, ConfigUpdate, Config
from app.crud import get_user_by_username, create_user
from app.auth import get_api_key
from app.azure_devops import get_auth_headers, get_base_url
import logging

from app.utils import transform_work_item

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create a file handler (optional)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)

# Define a log format
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)



# Create tables (for demonstration; in production use Alembic migrations)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Azure DevOps Work Items API with Persistent User Management")



# Helper function to retrieve user-level configuration from the database
def get_user_config(current_user, db: Session):
    config_record = db.query(UserConfig).filter(UserConfig.user_id == current_user.id).first()
    if not config_record:
        raise HTTPException(status_code=404, detail="No configuration found for the user.")
    return {
        "azure_devops_org": config_record.azure_devops_org,
        "azure_devops_project": config_record.azure_devops_project,
        "api_version": config_record.api_version
    }


# ---------------------------
# User Management Endpoints
# ---------------------------
@app.post("/register", response_model=User, summary="Register a New User")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    return create_user(db, user)


# ---------------------------
# Configuration Endpoints (User-Level)
# ---------------------------
@app.get("/config", summary="Get Current Azure DevOps Configuration", response_model=Config)
def get_config(
        current_user=Depends(get_api_key),
        db: Session = Depends(get_db)
):
    """
    Retrieve the current Azure DevOps configuration for the logged-in user.
    If no configuration exists for the user, a default config is created.
    """
    config_record = db.query(UserConfig).filter(UserConfig.user_id == current_user.id).first()
    if not config_record:
        # Create a default configuration record for the user.
        config_record = UserConfig(
            user_id=current_user.id,
            azure_devops_org=AZURE_DEVOPS_ORG,
            azure_devops_project=AZURE_DEVOPS_PROJECT,
            azure_devops_pat=AZURE_DEVOPS_PAT,
            api_version=API_VERSION
        )
        db.add(config_record)
        db.commit()
        db.refresh(config_record)

    return {
        "azure_devops_org": config_record.azure_devops_org,
        "azure_devops_project": config_record.azure_devops_project,
        "api_version": config_record.api_version
    }


@app.put("/config", summary="Update Azure DevOps Configuration", response_model=Config)
def update_config(
        update: ConfigUpdate = Body(...),
        current_user=Depends(get_api_key),
        db: Session = Depends(get_db)
):
    """
    Update the Azure DevOps configuration for the logged-in user.
    Only the provided fields will be updated.
    If no configuration exists, it will only be created if all required fields are provided.
    """
    config_record = db.query(UserConfig).filter(UserConfig.user_id == current_user.id).first()

    if not config_record:
        # Check if all required fields are provided for a new configuration.
        if None in [
            update.azure_devops_org,
            update.azure_devops_project,
            update.azure_devops_pat,
            update.api_version
        ]:
            raise HTTPException(
                status_code=400,
                detail="All required fields must be provided to create a new configuration."
            )
        config_record = UserConfig(
            user_id=current_user.id,
            azure_devops_org=update.azure_devops_org,
            azure_devops_project=update.azure_devops_project,
            azure_devops_pat=update.azure_devops_pat,
            api_version=update.api_version
        )
        db.add(config_record)
        db.commit()
        db.refresh(config_record)
    else:
        if update.azure_devops_org is not None:
            config_record.azure_devops_org = update.azure_devops_org
        if update.azure_devops_project is not None:
            config_record.azure_devops_project = update.azure_devops_project
        if update.azure_devops_pat is not None:
            config_record.azure_devops_pat = update.azure_devops_pat
        if update.api_version is not None:
            config_record.api_version = update.api_version

        db.commit()
        db.refresh(config_record)

    return {
        "azure_devops_org": config_record.azure_devops_org,
        "azure_devops_project": config_record.azure_devops_project,
        "api_version": config_record.api_version
    }


# ---------------------------
# Azure DevOps Work Items Endpoints (Protected)
# ---------------------------
@app.get("/workitems", summary="List Work Items")
def list_work_items(
    state: str = Query(None, description="Filter by work item state (e.g., 'Active', 'Closed')"),
    title: str = Query(None, description="Keyword to search in the work item title"),
    limit: int = Query(200, ge=1, description="Maximum number of work items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    x_pat: str = Header(None, alias="X-Azure-DevOps-PAT"),
    current_user = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    # Retrieve the user-level configuration
    user_config = get_user_config(current_user, db)
    org = user_config["azure_devops_org"]
    project = user_config["azure_devops_project"]
    api_version = user_config["api_version"]

    # Build the WIQL query dynamically.
    # Base query:
    wiql_query = (
        "SELECT [System.Id], [System.Title], [System.State] "
        "FROM WorkItems "
        "WHERE [System.TeamProject] = @project"
    )
    # Append filtering conditions if provided.
    if state:
        # WIQL expects a literal string value enclosed in single quotes.
        wiql_query += f" AND [System.State] = '{state}'"
    if title:
        # Use the CONTAINS operator for a keyword search.
        wiql_query += f" AND [System.Title] CONTAINS '{title}'"
    # Add the ordering clause.
    wiql_query += " ORDER BY [System.ChangedDate] DESC"
    # Use TOP clause to limit the number of rows.
    wiql_query = f"SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = @project"
    if state:
        wiql_query += f" AND [System.State] = '{state}'"
    if title:
        wiql_query += f" AND [System.Title] CONTAINS '{title}'"
    wiql_query += " ORDER BY [System.ChangedDate] DESC"

    # Log the final WIQL query for debugging.
    logger.info(f"WIQL Query: {wiql_query}")

    # WIQL endpoint URL is project-scoped.
    wiql_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/wiql?$top={limit}&api-version={api_version}"
    payload = {"query": wiql_query}
    headers = get_auth_headers(x_pat)
    response = requests.post(wiql_url, json=payload, headers=headers)
    logger.info(f"Request to WIQL endpoint: {response.request.url}")

    if response.status_code != 200:
        logger.error(f"Error retrieving work items: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)

    wiql_result = response.json()
    work_item_ids = [item["id"] for item in wiql_result.get("workItems", [])]
    # Apply offset manually if needed:
    work_item_ids = work_item_ids[offset:offset+limit]

    if work_item_ids:
        ids = ",".join(map(str, work_item_ids))
        # Use the details endpoint including project in URL.
        details_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems?ids={ids}&api-version={api_version}"
        details_response = requests.get(details_url, headers=headers)
        if details_response.status_code != 200:
            logger.error(f"Error retrieving work item details: {details_response.status_code}: {details_response.text}")
            raise HTTPException(status_code=details_response.status_code, detail=details_response.text)
        details = details_response.json()  # assuming details contains a "value" key with list of items.
        transformed = [transform_work_item(item) for item in details.get("value", [])]
        return {"workItems": transformed}

    return {"workItems": []}

# @app.get("/workitems/{work_item_id}", summary="Get Work Item by ID")
# def get_work_item(
#         work_item_id: int = Path(..., description="The ID of the work item to retrieve"),
#         x_pat: str = Header(None, alias="X-Azure-DevOps-PAT"),
#         current_user=Depends(get_api_key),
#         db: Session = Depends(get_db)
# ):
#     user_config = get_user_config(current_user, db)
#     AZURE_DEVOPS_ORG = user_config["azure_devops_org"]
#     API_VERSION = user_config["api_version"]
#     url = f"https://dev.azure.com/{AZURE_DEVOPS_ORG}/_apis/wit/workitems/{work_item_id}?api-version={API_VERSION}"
#     headers = get_auth_headers(x_pat)
#     response = requests.get(url, headers=headers)
#     if response.status_code != 200:
#         raise HTTPException(status_code=response.status_code, detail=response.text)
#     return response.json()

@app.get("/workitems/{work_item_id}", summary="Get Work Item by ID with Web URL")
def get_work_item_info(
    work_item_id: int = Path(..., description="The ID of the work item to retrieve"),
    x_pat: str = Header(None, alias="X-Azure-DevOps-PAT"),
    current_user=Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Retrieve a single work item information along with its web URL."""
    # Retrieve user configuration values
    user_config = get_user_config(current_user, db)
    org = user_config["azure_devops_org"]
    project = user_config["azure_devops_project"]
    api_version = user_config["api_version"]
    headers = get_auth_headers(x_pat)

    # Handle single work item using path parameter
    url = f"https://dev.azure.com/{org}/_apis/wit/workitems/{work_item_id}?api-version={api_version}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    work_item = response.json()

    # Add the web URL for the client
    work_item["webUrl"] = f"https://dev.azure.com/{org}/{project}/_workitems/edit/{work_item_id}"
    return work_item

@app.get("/workitems/batch", summary="Get Multiple Work Items by IDs")
def get_work_items_batch(
    ids: str = Query(..., description="Comma-separated list of work item IDs to retrieve"),
    x_pat: str = Header(None, alias="X-Azure-DevOps-PAT"),
    current_user=Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """Retrieve multiple work items by their IDs along with web URLs."""
    # Retrieve user configuration values
    user_config = get_user_config(current_user, db)
    org = user_config["azure_devops_org"]
    project = user_config["azure_devops_project"]
    api_version = user_config["api_version"]
    headers = get_auth_headers(x_pat)

    # Process work item IDs
    work_item_ids = [id.strip() for id in ids.split(",")]
    batch_url = f"https://dev.azure.com/{org}/_apis/wit/workitems?ids={','.join(work_item_ids)}&api-version={api_version}"
    response = requests.get(batch_url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    result = response.json()
    work_items = result.get("value", [])

    # Add web URLs to each work item
    for work_item in work_items:
        item_id = work_item.get("id")
        work_item["webUrl"] = f"https://dev.azure.com/{org}/{project}/_workitems/edit/{item_id}"

    return {"workItems": work_items}

@app.post("/workitems", summary="Create a Work Item")
def create_work_item(
        item: WorkItemCreate = Body(...),
        x_pat: str = Header(None, alias="X-Azure-DevOps-PAT"),
        current_user=Depends(get_api_key),
        db: Session = Depends(get_db)
):
    user_config = get_user_config(current_user, db)
    API_VERSION = user_config["api_version"]
    base_url = get_base_url(user_config)
    url = f"{base_url}/_apis/wit/workitems/$Task?api-version={API_VERSION}"
    payload = [
        {"op": "add", "path": "/fields/System.Title", "value": item.title},
        {"op": "add", "path": "/fields/System.Description", "value": item.description}
    ]
    headers = get_auth_headers(x_pat)
    headers["Content-Type"] = "application/json-patch+json"
    logger.info(f"Creating work item with payload: {payload} and url: {url}")
    response = requests.patch(url, json=payload, headers=headers)
    if response.status_code not in (200, 201):
        logger.error(f"Error creating work item: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.patch("/workitems/{work_item_id}", summary="Update a Work Item")
def update_work_item(
    work_item_id: int = Path(..., description="The ID of the work item to update"),
    update: WorkItemUpdate = Body(...),
    x_pat: str = Header(None, alias="X-Azure-DevOps-PAT"),
    current_user=Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Update only the specified fields of a work item. This endpoint verifies that
    the work item exists and then builds a JSON Patch payload that uses "replace"
    if a field already exists or "add" if it doesn't. Additionally, it ensures the
    work item gets tagged as "enhanced".
    """
    # Retrieve user configuration values.
    user_config = get_user_config(current_user, db)
    org = user_config["azure_devops_org"]
    API_VERSION = user_config["api_version"]

    # Step 1: Verify the work item exists.
    get_url = f"https://dev.azure.com/{org}/_apis/wit/workitems/{work_item_id}?api-version={API_VERSION}"
    headers = get_auth_headers(x_pat)
    get_response = requests.get(get_url, headers=headers)
    if get_response.status_code != 200:
        raise HTTPException(
            status_code=get_response.status_code,
            detail="Work item not found or unavailable"
        )
    current_work_item = get_response.json()
    fields = current_work_item.get("fields", {})

    # Step 2: Build the patch payload dynamically.
    patch_payload = []

    # Update the title field.
    if update.title:
        op = "replace" if "System.Title" in fields else "add"
        patch_payload.append({
            "op": op,
            "path": "/fields/System.Title",
            "value": update.title
        })

    # Update the description field.
    if update.description:
        op = "replace" if "System.Description" in fields else "add"
        patch_payload.append({
            "op": op,
            "path": "/fields/System.Description",
            "value": update.description
        })

    # Add the "enhanced" tag.
    # System.Tags is stored as a semicolon-separated string.
    existing_tags = fields.get("System.Tags", "")
    # Split existing tags and remove any extra whitespace.
    tags_list = [tag.strip() for tag in existing_tags.split(";") if tag.strip()] if existing_tags else []
    # Check case-insensitively if the "enhanced" tag is already present.
    if "enhanced" not in [tag.lower() for tag in tags_list]:
        tags_list.append("enhanced")
        new_tags_value = "; ".join(tags_list)
        op = "replace" if existing_tags else "add"
        patch_payload.append({
            "op": op,
            "path": "/fields/System.Tags",
            "value": new_tags_value
        })

    if not patch_payload:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    # Step 3: Send the PATCH request using the organization-level URL.
    update_url = f"https://dev.azure.com/{org}/_apis/wit/workitems/{work_item_id}?api-version={API_VERSION}"
    headers["Content-Type"] = "application/json-patch+json"
    patch_response = requests.patch(update_url, json=patch_payload, headers=headers)
    if patch_response.status_code != 200:
        raise HTTPException(status_code=patch_response.status_code, detail=patch_response.text)

    return patch_response.json()