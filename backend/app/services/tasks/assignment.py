from sqlalchemy.orm import Session

from app.models.issue import Issue, IssueStatus
from app.models.task import Task


def create_task(db: Session, issue: Issue, assigned_to: str) -> Task:
    task = Task(issue_id=issue.id, assigned_to=assigned_to)
    db.add(task)

    # Assigning a crew means work has started.
    if issue.status == IssueStatus.OPEN:
        issue.status = IssueStatus.IN_PROGRESS

    db.commit()
    db.refresh(task)
    return task


def update_task_status(db: Session, task: Task, status: str) -> Task:
    task.status = status
    db.commit()
    db.refresh(task)
    return task
