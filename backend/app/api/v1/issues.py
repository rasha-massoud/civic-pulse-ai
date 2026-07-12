from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.issue import IssueStatus
from app.schemas.issue import IssueOut, IssueStatusUpdate
from app.services import issues as issues_service

router = APIRouter(prefix="/issues", tags=["issues"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[IssueOut])
def list_issues(
    category: str | None = None,
    status: IssueStatus | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
):
    return issues_service.list_issues(db, category=category, status=status, severity=severity)


@router.get("/{issue_id}", response_model=IssueOut)
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = issues_service.get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


@router.patch("/{issue_id}", response_model=IssueOut)
def update_issue_status(issue_id: int, payload: IssueStatusUpdate, db: Session = Depends(get_db)):
    issue = issues_service.get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issues_service.update_issue_status(db, issue, payload.status)
