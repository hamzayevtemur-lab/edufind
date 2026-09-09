from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models.center import LearningCenter, Review, ApprovalStatus, CourseStatus
from schemas.center import CenterDetail, ReviewCreate

router = APIRouter(prefix="/public", tags=["Center Detail"])


@router.get("/centers/{center_id}", response_model=CenterDetail)
def get_center_detail(center_id: int, db: Session = Depends(get_db)):
    center = (
        db.query(LearningCenter)
        .filter(
            LearningCenter.id     == center_id,
            LearningCenter.status == ApprovalStatus.approved,
        )
        .options(
            joinedload(LearningCenter.courses),
            joinedload(LearningCenter.reviews),
        )
        .first()
    )

    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    # active + coming_soon courses are shown, closed ones are hidden
    visible_courses = [
        c for c in center.courses
        if c.status in (CourseStatus.active, CourseStatus.coming_soon)
    ]
    approved_reviews = [r for r in center.reviews if r.status == ApprovalStatus.approved]

    return CenterDetail(
        id           = center.id,
        name         = center.name,
        description  = center.description,
        logo_url     = center.logo_url,
        city         = center.city,
        phone        = center.phone,
        email        = center.email,
        website      = center.website,
        address      = center.address,
        status       = center.status,
        avg_rating   = center.avg_rating,
        review_count = center.review_count,
        course_count = center.course_count,
        latitude     = center.latitude,
        longitude    = center.longitude,
        created_at   = center.created_at,
        courses      = visible_courses,
        reviews      = approved_reviews,
    )


@router.post("/reviews", status_code=201)
def submit_review(body: ReviewCreate, db: Session = Depends(get_db)):
    center = db.query(LearningCenter).filter(
        LearningCenter.id     == body.center_id,
        LearningCenter.status == ApprovalStatus.approved,
    ).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    db.add(Review(
        center_id    = body.center_id,
        student_name = body.student_name,
        rating       = body.rating,
        comment      = body.comment,
        status       = ApprovalStatus.pending,
    ))
    db.commit()
    return {"message": "Review submitted — pending approval"}