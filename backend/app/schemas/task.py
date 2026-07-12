from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    assigned_to: str
    status: str
    created_at: datetime


class TaskCreate(BaseModel):
    issue_id: int
    assigned_to: str


class TaskStatusUpdate(BaseModel):
    status: str
