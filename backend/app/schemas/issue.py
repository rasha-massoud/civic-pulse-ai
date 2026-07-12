from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.issue import IssueStatus
from app.schemas.report import ReportOut
from app.schemas.task import TaskOut


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    severity: str
    status: IssueStatus
    report_count: int
    district: str
    latitude: float
    longitude: float
    created_at: datetime
    updated_at: datetime
    reports: list[ReportOut]
    tasks: list[TaskOut]


class IssueStatusUpdate(BaseModel):
    status: IssueStatus
