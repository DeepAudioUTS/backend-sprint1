from fastapi import APIRouter

from app.api.v1 import auth, children, stories

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(children.router, prefix="/children", tags=["children"])
router.include_router(stories.router, prefix="/stories", tags=["stories"])
