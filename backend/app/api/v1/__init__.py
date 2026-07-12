from fastapi import APIRouter

from app.api.v1 import auth, issues, reports, tasks

router = APIRouter()
router.include_router(issues.router)
router.include_router(tasks.router)
router.include_router(reports.router)
router.include_router(auth.router)
