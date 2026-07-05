import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.report import Report
    from app.models.task import Task


class IssueStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class Issue(Base):
    """The deduped/clustered real-world problem one or more Reports point to."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IssueStatus.OPEN,
        server_default=IssueStatus.OPEN.value,
        index=True,
    )
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    district: Mapped[str] = mapped_column(String(150), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="issue")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="issue")
