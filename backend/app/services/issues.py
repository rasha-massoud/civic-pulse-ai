from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.issue import Issue, IssueStatus


def list_issues(
    db: Session,
    category: str | None = None,
    status: IssueStatus | None = None,
    severity: str | None = None,
) -> list[Issue]:
    stmt = select(Issue).options(selectinload(Issue.reports), selectinload(Issue.tasks))
    if category:
        stmt = stmt.where(Issue.category == category)
    if status:
        stmt = stmt.where(Issue.status == status)
    if severity:
        stmt = stmt.where(Issue.severity == severity)
    stmt = stmt.order_by(Issue.created_at.desc())
    return list(db.scalars(stmt).unique())


def get_issue(db: Session, issue_id: int) -> Issue | None:
    stmt = (
        select(Issue)
        .options(selectinload(Issue.reports), selectinload(Issue.tasks))
        .where(Issue.id == issue_id)
    )
    return db.scalars(stmt).unique().one_or_none()


def update_issue_status(db: Session, issue: Issue, status: IssueStatus) -> Issue:
    issue.status = status
    db.commit()
    db.refresh(issue)
    return issue
