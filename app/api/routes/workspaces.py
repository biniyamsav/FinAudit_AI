import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Workspace
from app.db.session import get_db

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime
    expires_at: datetime


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(db: Annotated[Session, Depends(get_db)]) -> Workspace:
    ttl = timedelta(hours=get_settings().workspace_ttl_hours)
    workspace = Workspace(expires_at=datetime.now(timezone.utc) + ttl)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace