from fastapi import APIRouter, Depends

from ..auth import require_admin

router = APIRouter(prefix="/api/admin")


@router.post("/verify")
def verify_admin(_: None = Depends(require_admin)):
    return {"ok": True}
