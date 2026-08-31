from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalars(select(User).where(User.username == username)).one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
