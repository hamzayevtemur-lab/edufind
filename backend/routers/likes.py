from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models.center import LearningCenter, CenterLike, ApprovalStatus

router = APIRouter(prefix="/public", tags=["Likes"])


class LikeBody(BaseModel):
    user_token: str   # anonymous UUID generated in the browser and stored in localStorage


@router.post("/centers/{center_id}/like")
def toggle_like(center_id: int, body: LikeBody, db: Session = Depends(get_db)):
    """
    Toggle like for a center.
    Returns: { liked: bool, likes_count: int }
    - If user hasn't liked yet  → adds like,    increments likes_count
    - If user already liked     → removes like, decrements likes_count
    """
    center = db.query(LearningCenter).filter(
        LearningCenter.id     == center_id,
        LearningCenter.status == ApprovalStatus.approved,
    ).first()

    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    token = body.user_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="user_token is required")

    existing = db.query(CenterLike).filter(
        CenterLike.center_id  == center_id,
        CenterLike.user_token == token,
    ).first()

    if existing:
        # Already liked → unlike
        db.delete(existing)
        center.likes_count = max(0, (center.likes_count or 0) - 1)
        db.commit()
        return {"liked": False, "likes_count": center.likes_count}
    else:
        # Not liked yet → like
        db.add(CenterLike(center_id=center_id, user_token=token))
        center.likes_count = (center.likes_count or 0) + 1
        db.commit()
        return {"liked": True, "likes_count": center.likes_count}


@router.get("/centers/{center_id}/like-status")
def like_status(center_id: int, user_token: str, db: Session = Depends(get_db)):
    """Check if this user has already liked this center."""
    existing = db.query(CenterLike).filter(
        CenterLike.center_id  == center_id,
        CenterLike.user_token == user_token,
    ).first()
    center = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    return {
        "liked":       existing is not None,
        "likes_count": center.likes_count if center else 0,
    }