from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.issue import Issue


class Task(Base):
    """Field work assigned by an admin against an Issue.

    `assigned_to` is a plain string naming the responsible municipal
    department (e.g. "Roads & Maintenance Department"), not a FK —
    departments have no accounts or logins in this MVP.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), nullable=False, index=True)
    assigned_to: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="assigned", server_default="assigned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    issue: Mapped["Issue"] = relationship("Issue", back_populates="tasks")
