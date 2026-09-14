from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from typing import Optional, List
from database import get_db
from models.center import LearningCenter, Course, ApprovalStatus, CourseStatus
from schemas.centers import PublicStats, CenterListItem, PaginatedCenters

router = APIRouter(prefix="/public", tags=["Public"])


def serialize(c: LearningCenter) -> CenterListItem:
    return CenterListItem(
        id           = c.id,
        name         = c.name,
        description  = c.description,
        logo_url     = c.logo_url,
        city         = c.city,
        phone        = c.phone,
        email        = c.email,
        website      = c.website,
        status       = c.status,
        avg_rating   = c.avg_rating,
        review_count = c.review_count,
        course_count = c.course_count,
        likes_count  = c.likes_count or 0,
        latitude     = c.latitude,
        longitude    = c.longitude,
        created_at   = c.created_at,
    )


# ═══════════════════════════════════════════════════════
#  STATS
# ═══════════════════════════════════════════════════════

@router.get("/stats", response_model=PublicStats)
def get_stats(db: Session = Depends(get_db)):
    centers = db.query(LearningCenter).filter(LearningCenter.status == ApprovalStatus.approved).count()
    courses = db.query(Course).filter(Course.status == CourseStatus.active).count()

    # Count unique teacher names across all active courses
    teachers = db.query(Course.teacher_name)\
        .filter(Course.status == CourseStatus.active, Course.teacher_name != None, Course.teacher_name != "")\
        .distinct()\
        .count()

    return PublicStats(centers=centers, courses=courses, teachers=teachers)


# ═══════════════════════════════════════════════════════
#  FEATURED
# ═══════════════════════════════════════════════════════

@router.get("/featured", response_model=List[CenterListItem])
def get_featured(db: Session = Depends(get_db)):
    centers = (
        db.query(LearningCenter)
        .filter(LearningCenter.status == ApprovalStatus.approved)
        .options(
            joinedload(LearningCenter.reviews),
            joinedload(LearningCenter.courses),
        )
        .order_by(LearningCenter.created_at.desc())
        .limit(10)
        .all()
    )
    return [serialize(c) for c in centers]


# ═══════════════════════════════════════════════════════
#  BROWSE CENTERS
# ═══════════════════════════════════════════════════════

@router.get("/centers", response_model=PaginatedCenters)
def browse_centers(
    search:   Optional[str] = Query(None),
    city:     Optional[str] = Query(None),
    sort:     Optional[str] = Query("newest"),
    page:     int           = Query(1, ge=1),
    per_page: int           = Query(9, ge=1, le=200),
    db: Session = Depends(get_db),
):
    base_q = db.query(LearningCenter).filter(LearningCenter.status == ApprovalStatus.approved)

    if search:
        term = f"%{search}%"
        base_q = base_q.filter(or_(
            LearningCenter.name.ilike(term),
            LearningCenter.description.ilike(term),
            LearningCenter.city.ilike(term),
        ))

    if city:
        base_q = base_q.filter(LearningCenter.city.ilike(f"%{city}%"))

    total = base_q.count()

    q = base_q.options(
        joinedload(LearningCenter.reviews),
        joinedload(LearningCenter.courses),
    )

    if sort == "az":
        q = q.order_by(LearningCenter.name.asc())
    elif sort == "likes":
        q = q.order_by(LearningCenter.likes_count.desc())
    else:
        q = q.order_by(LearningCenter.created_at.desc())

    centers = q.offset((page - 1) * per_page).limit(per_page).all()
    items   = [serialize(c) for c in centers]

    if sort == "rating":
        items.sort(key=lambda c: c.avg_rating or 0, reverse=True)
    elif sort == "courses":
        items.sort(key=lambda c: c.course_count, reverse=True)

    return PaginatedCenters(
        items    = items,
        total    = total,
        page     = page,
        per_page = per_page,
        pages    = max(1, -(-total // per_page)),
    )


# ═══════════════════════════════════════════════════════
#  PUBLIC COURSES
# ═══════════════════════════════════════════════════════

@router.get("/courses")
def browse_courses(
    search:   Optional[str] = Query(None),
    city:     Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort:     Optional[str] = Query("newest"),
    page:     int           = Query(1, ge=1),
    per_page: int           = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    base_q = (
        db.query(Course)
        .join(LearningCenter, Course.center_id == LearningCenter.id)
        .filter(
            Course.status == CourseStatus.active,
            LearningCenter.status == ApprovalStatus.approved,
        )
    )

    if search:
        term = f"%{search}%"
        base_q = base_q.filter(or_(
            Course.name.ilike(term),
            Course.description.ilike(term),
            Course.teacher_name.ilike(term),
        ))

    if city:
        base_q = base_q.filter(LearningCenter.city.ilike(f"%{city}%"))

    if category:
        base_q = base_q.filter(func.lower(Course.category) == category.lower())

    total = base_q.count()

    q = base_q.options(
        joinedload(Course.center),
        joinedload(Course.campus),
    )

    if sort == "price_asc":
        q = q.order_by(Course.price.asc().nullslast())
    elif sort == "price_desc":
        q = q.order_by(Course.price.desc().nullslast())
    elif sort == "az":
        q = q.order_by(Course.name.asc())
    else:
        q = q.order_by(Course.id.desc())

    courses = q.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for co in courses:
        items.append({
            "id":             co.id,
            "campus_id":      co.campus_id,
            "campus_name":    co.campus.name if co.campus else None,
            "name":           co.name,
            "category":       co.category,
            "description":    co.description,
            "teacher_name":   co.teacher_name,
            "price":          co.price,
            "currency":       co.currency,
            "duration_weeks": co.duration_weeks,
            "schedule":       co.schedule,
            "max_students":   co.max_students,
            "enrolled":       co.enrolled,
            "status":         co.status.value if hasattr(co.status, "value") else co.status,
            "center_id":      co.center_id,
            "center_name":    co.center.name if co.center else None,
            "center_city":    co.center.city if co.center else None,
            "center_phone":   co.center.phone if co.center else None,
            "center_logo":    co.center.logo_url if co.center else None,
        })

    return {
        "items":    items,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    max(1, -(-total // per_page)),
    }