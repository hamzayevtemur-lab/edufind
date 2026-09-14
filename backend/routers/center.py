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
            joinedload(LearningCenter.campuses),
        )
        .first()
    )

    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    visible_courses = []
    for c in center.courses:
        if c.status in (CourseStatus.active, CourseStatus.coming_soon):
            visible_courses.append({
                "id":             c.id,
                "campus_id":      c.campus_id,
                "campus_name":    c.campus.name if c.campus else None,
                "name":           c.name,
                "description":    c.description,
                "teacher_name":   c.teacher_name,
                "price":          c.price,
                "currency":       c.currency,
                "duration_weeks": c.duration_weeks,
                "schedule":       c.schedule,
                "max_students":   c.max_students,
                "enrolled":       c.enrolled,
                "starts_at":      c.starts_at,
                "status":         c.status.value if hasattr(c.status, "value") else c.status,
            })

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
        campuses     = center.campuses or [],
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


from pydantic import BaseModel
from models.center import Course, CourseApplication, ApplicationStatus, CourseRequest, CourseRequestStatus, CourseRequestVote
from typing import Optional, List

class CourseApplyBody(BaseModel):
    student_name:       str
    phone:              str
    email:              Optional[str] = None
    preferred_schedule: Optional[str] = None
    notes:              Optional[str] = None


@router.post("/courses/{course_id}/apply", status_code=201)
def apply_for_course(course_id: int, body: CourseApplyBody, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    app = CourseApplication(
        center_id          = course.center_id,
        course_id          = course_id,
        student_name       = body.student_name.strip(),
        phone              = body.phone.strip(),
        email              = body.email.strip() if body.email else None,
        preferred_schedule = body.preferred_schedule.strip() if body.preferred_schedule else None,
        notes              = body.notes.strip() if body.notes else None,
        status             = ApplicationStatus.pending
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return {"message": "Application submitted successfully!", "application_id": app.id}


class CourseRequestBody(BaseModel):
    title:              str
    category:           Optional[str] = "other"
    preferred_schedule: Optional[str] = None
    student_name:       str
    phone:              str
    email:              Optional[str] = None
    notes:              Optional[str] = None
    user_token:         Optional[str] = None


@router.post("/centers/{center_id}/course-requests", status_code=201)
def create_course_request(center_id: int, body: CourseRequestBody, db: Session = Depends(get_db)):
    center = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    
    req = CourseRequest(
        center_id          = center_id,
        title              = body.title.strip(),
        category           = body.category.strip() if body.category else "other",
        preferred_schedule = body.preferred_schedule.strip() if body.preferred_schedule else None,
        student_name       = body.student_name.strip(),
        phone              = body.phone.strip(),
        email              = body.email.strip() if body.email else None,
        notes              = body.notes.strip() if body.notes else None,
        status             = CourseRequestStatus.pending,
        votes_count        = 1,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    if body.user_token:
        vote = CourseRequestVote(request_id=req.id, user_token=body.user_token.strip())
        db.add(vote)
        db.commit()

    return {"message": "Course request submitted successfully!", "request": {
        "id": req.id, "title": req.title, "category": req.category, "votes_count": req.votes_count
    }}


@router.get("/centers/{center_id}/course-requests")
def list_center_course_requests(
    center_id: int,
    user_token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    reqs = (
        db.query(CourseRequest)
        .filter(CourseRequest.center_id == center_id)
        .order_by(CourseRequest.votes_count.desc(), CourseRequest.id.desc())
        .all()
    )

    voted_req_ids = set()
    if user_token:
        votes = db.query(CourseRequestVote.request_id).filter(
            CourseRequestVote.user_token == user_token
        ).all()
        voted_req_ids = {v[0] for v in votes}

    return [
        {
            "id":                 r.id,
            "title":              r.title,
            "category":           r.category,
            "preferred_schedule": r.preferred_schedule,
            "student_name":       r.student_name,
            "votes_count":        r.votes_count,
            "status":             r.status.value if hasattr(r.status, "value") else r.status,
            "created_at":         r.created_at,
            "user_voted":         r.id in voted_req_ids,
        }
        for r in reqs
    ]


class VoteBody(BaseModel):
    user_token: str


@router.post("/course-requests/{request_id}/vote")
def vote_course_request(request_id: int, body: VoteBody, db: Session = Depends(get_db)):
    req = db.query(CourseRequest).filter(CourseRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Course request not found")

    utoken = body.user_token.strip()
    existing_vote = db.query(CourseRequestVote).filter(
        CourseRequestVote.request_id == request_id,
        CourseRequestVote.user_token == utoken
    ).first()

    if existing_vote:
        # User already voted -> Toggle off (unvote)
        db.delete(existing_vote)
        req.votes_count = max(0, req.votes_count - 1)
        voted = False
    else:
        # User has not voted -> Add vote
        vote = CourseRequestVote(request_id=request_id, user_token=utoken)
        db.add(vote)
        req.votes_count += 1
        voted = True

    db.commit()
    db.refresh(req)
    return {"message": "Vote updated", "votes_count": req.votes_count, "voted": voted}