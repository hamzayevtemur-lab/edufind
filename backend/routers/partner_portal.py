import os, hashlib
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from pydantic import BaseModel

from database import get_db
from models.center import (
    Partner, LearningCenter, Course, Review,
    ApprovalStatus, CourseStatus,
)

router = APIRouter(prefix="/portal", tags=["Partner Portal"])


# ── Auth helper ────────────────────────────────────────────────────

def get_partner(
    x_partner_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Partner:
    if not x_partner_id:
        raise HTTPException(status_code=401, detail="Missing X-Partner-Id header")
    try:
        pid = int(x_partner_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid partner ID")

    p = db.query(Partner).filter(Partner.id == pid, Partner.is_active == 1).first()
    if not p:
        raise HTTPException(status_code=401, detail="Partner not found or suspended")
    return p


# ═══════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════

class LoginBody(BaseModel):
    email:    str
    password: str


def hash_pw(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


@router.post("/login")
def portal_login(body: LoginBody, db: Session = Depends(get_db)):
    p = db.query(Partner).filter(
        Partner.email == body.email.lower().strip()
    ).first()
    if not p or p.password_hash != hash_pw(body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not p.is_active:
        raise HTTPException(status_code=403, detail="Account is suspended. Contact support.")

    return {
        "partner_id":    p.id,
        "business_name": p.business_name,
        "contact_person": p.contact_person,
        "email":         p.email,
        "phone":         p.phone,
        "plan":          p.plan.value if hasattr(p.plan, "value") else p.plan,
        "expires_at":    p.plan_expires_at,
        "is_active":     p.is_active,
        "extension_requested": p.extension_requested or 0,
    }


# ═══════════════════════════════════════════════════════
#  PLAN EXTENSION REQUEST
# ═══════════════════════════════════════════════════════

from datetime import datetime, timedelta

@router.post("/request-extension")
def request_free_extension(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    """Submits a plan extension request for admin approval."""
    if partner.extension_requested:
        raise HTTPException(status_code=400, detail="Your extension request is already pending admin review.")

    partner.extension_requested = 1
    db.commit()

    # Notify admin via email
    try:
        from routers.partners import send_email, SMTP_EMAIL, BACKEND_URL
        if SMTP_EMAIL:
            admin_token = os.getenv("ADMIN_TOKEN", "edufind-admin-2026")
            approve_url = f"{BACKEND_URL}/api/admin/approve-extension/{partner.id}?admin_token={admin_token}"
            send_email(
                to=SMTP_EMAIL,
                subject=f"[EduFind Extension Request] {partner.business_name}",
                html=f"""
                <div style="font-family:sans-serif;background:#f8fafc;padding:30px">
                  <div style="background:#fff;padding:24px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.08)">
                    <h3 style="color:#4f46e5;margin:0 0 12px">🔄 Plan Extension Request</h3>
                    <p style="color:#334155;line-height:1.6">
                      <strong>{partner.business_name}</strong> ({partner.contact_person}, {partner.email}) has requested a <strong>1-Month Free Plan Extension (+30 days)</strong>.
                    </p>
                    <div style="margin:24px 0">
                      <a href="{approve_url}" style="background:#10b981;color:#fff;text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:700">
                        ✅ Approve Extension (+30 Days)
                      </a>
                    </div>
                  </div>
                </div>
                """
            )
    except Exception as e:
        print(f"⚠️ Extension email notification error: {e}")

    return {
        "message": "⌛ Extension request submitted successfully! Pending admin review.",
        "extension_requested": 1
    }


# ═══════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════

@router.get("/stats")
def partner_stats(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    centers = db.query(LearningCenter).filter(
        LearningCenter.partner_id == partner.id
    ).all()

    center_ids    = [c.id for c in centers]
    total_courses = 0
    total_reviews = 0
    all_ratings   = []

    for c in centers:
        active_courses = [co for co in c.courses if co.status == CourseStatus.active]
        approved_reviews = [r for r in c.reviews if r.status == ApprovalStatus.approved]
        total_courses += len(active_courses)
        total_reviews += len(approved_reviews)
        all_ratings.extend([r.rating for r in approved_reviews])

    avg_rating = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else 0.0

    return {
        "total_centers":  len(centers),
        "total_courses":  total_courses,
        "total_reviews":  total_reviews,
        "avg_rating":     avg_rating,
        "plan":           partner.plan.value if hasattr(partner.plan, "value") else partner.plan,
        "expires_at":     partner.plan_expires_at,
        "extension_requested": partner.extension_requested or 0,
    }


# ═══════════════════════════════════════════════════════
#  CENTERS — list, create, update, delete
# ═══════════════════════════════════════════════════════

def _serialize_center(c: LearningCenter) -> dict:
    return {
        "id":           c.id,
        "name":         c.name,
        "description":  c.description,
        "logo_url":     c.logo_url,
        "city":         c.city,
        "phone":        c.phone,
        "email":        c.email,
        "website":      c.website,
        "address":      c.address,
        "latitude":     c.latitude,
        "longitude":    c.longitude,
        "status":       c.status.value if hasattr(c.status, "value") else c.status,
        "avg_rating":   c.avg_rating,
        "review_count": c.review_count,
        "course_count": c.course_count,
        "likes_count":  c.likes_count,
        "created_at":   c.created_at,
    }


@router.get("/centers")
def list_my_centers(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    centers = db.query(LearningCenter).filter(
        LearningCenter.partner_id == partner.id
    ).options(
        joinedload(LearningCenter.courses),
        joinedload(LearningCenter.reviews),
    ).order_by(LearningCenter.created_at.desc()).all()

    return [_serialize_center(c) for c in centers]


@router.get("/centers/{center_id}")
def get_my_center(
    center_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = db.query(LearningCenter).filter(
        LearningCenter.id == center_id,
        LearningCenter.partner_id == partner.id,
    ).options(
        joinedload(LearningCenter.courses),
        joinedload(LearningCenter.reviews),
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")

    data = _serialize_center(c)
    data["courses"] = [
        {
            "id": co.id, "name": co.name,
            "status": co.status.value if hasattr(co.status, "value") else co.status,
            "description": co.description, "teacher_name": co.teacher_name,
            "price": co.price, "currency": co.currency,
            "duration_weeks": co.duration_weeks, "schedule": co.schedule,
            "max_students": co.max_students, "enrolled": co.enrolled,
        }
        for co in c.courses
    ]
    data["reviews"] = [
        {
            "id": r.id, "student_name": r.student_name, "rating": r.rating,
            "comment": r.comment,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "created_at": r.created_at,
        }
        for r in c.reviews if r.status == ApprovalStatus.approved
    ]
    return data


class CenterCreateBody(BaseModel):
    name:        str
    city:        str
    description: Optional[str] = None
    phone:       Optional[str] = None
    email:       Optional[str] = None
    website:     Optional[str] = None
    address:     Optional[str] = None
    logo_url:    Optional[str] = None
    latitude:    Optional[float] = None
    longitude:   Optional[float] = None


@router.post("/centers", status_code=201)
def create_center(
    body: CenterCreateBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = LearningCenter(
        name        = body.name,
        city        = body.city,
        description = body.description,
        phone       = body.phone,
        email       = body.email,
        website     = body.website,
        address     = body.address,
        logo_url    = body.logo_url,
        latitude    = body.latitude,
        longitude   = body.longitude,
        status      = ApprovalStatus.pending,   # admin must approve
        partner_id  = partner.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _serialize_center(c)


class CenterUpdateBody(BaseModel):
    name:        Optional[str]   = None
    city:        Optional[str]   = None
    description: Optional[str]   = None
    phone:       Optional[str]   = None
    email:       Optional[str]   = None
    website:     Optional[str]   = None
    address:     Optional[str]   = None
    logo_url:    Optional[str]   = None
    latitude:    Optional[float] = None
    longitude:   Optional[float] = None


@router.patch("/centers/{center_id}")
def update_center(
    center_id: int,
    body: CenterUpdateBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = db.query(LearningCenter).filter(
        LearningCenter.id == center_id,
        LearningCenter.partner_id == partner.id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(c, field, value)

    db.commit()
    db.refresh(c)
    return _serialize_center(c)


@router.delete("/centers/{center_id}")
def delete_center(
    center_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = db.query(LearningCenter).filter(
        LearningCenter.id == center_id,
        LearningCenter.partner_id == partner.id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")
    db.delete(c)
    db.commit()
    return {"message": "Center deleted"}


# ═══════════════════════════════════════════════════════
#  COURSES — list, create, update, delete
# ═══════════════════════════════════════════════════════

def _owns_center(partner: Partner, center_id: int, db: Session) -> LearningCenter:
    c = db.query(LearningCenter).filter(
        LearningCenter.id == center_id,
        LearningCenter.partner_id == partner.id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")
    return c


class CourseBody(BaseModel):
    name:           str
    category:       Optional[str]   = "other"
    description:    Optional[str]   = None
    teacher_name:   Optional[str]   = None
    price:          Optional[float] = None
    currency:       Optional[str]   = "UZS"
    duration_weeks: Optional[int]   = None
    schedule:       Optional[str]   = None
    max_students:   Optional[int]   = None
    status:         Optional[str]   = "active"


@router.get("/centers/{center_id}/courses")
def list_courses(
    center_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    _owns_center(partner, center_id, db)
    courses = db.query(Course).filter(Course.center_id == center_id).all()
    return [
        {
            "id": co.id, "name": co.name, "category": co.category, "description": co.description,
            "teacher_name": co.teacher_name, "price": co.price, "currency": co.currency,
            "duration_weeks": co.duration_weeks, "schedule": co.schedule,
            "max_students": co.max_students, "enrolled": co.enrolled,
            "status": co.status.value if hasattr(co.status, "value") else co.status,
        }
        for co in courses
    ]


@router.post("/centers/{center_id}/courses", status_code=201)
def create_course(
    center_id: int,
    body: CourseBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    _owns_center(partner, center_id, db)
    try:
        status_val = CourseStatus(body.status or "active")
    except ValueError:
        status_val = CourseStatus.active

    co = Course(
        center_id      = center_id,
        name           = body.name,
        category       = body.category or "other",
        description    = body.description,
        teacher_name   = body.teacher_name,
        price          = body.price,
        currency       = body.currency or "UZS",
        duration_weeks = body.duration_weeks,
        schedule       = body.schedule,
        max_students   = body.max_students,
        status         = status_val,
    )
    db.add(co)
    db.commit()
    db.refresh(co)
    return {"id": co.id, "name": co.name, "category": co.category, "status": co.status}


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int,
    body: CourseBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    co = db.query(Course).filter(Course.id == course_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Course not found")
    _owns_center(partner, co.center_id, db)

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "status":
            try:
                value = CourseStatus(value)
            except ValueError:
                continue
        setattr(co, field, value)

    db.commit()
    return {"id": co.id, "name": co.name, "category": co.category}


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    co = db.query(Course).filter(Course.id == course_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Course not found")
    _owns_center(partner, co.center_id, db)
    db.delete(co)
    db.commit()
    return {"message": "Course deleted"}


# ═══════════════════════════════════════════════════════
#  REVIEWS — read only for partner
# ═══════════════════════════════════════════════════════

@router.get("/centers/{center_id}/reviews")
def list_reviews(
    center_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    _owns_center(partner, center_id, db)
    reviews = db.query(Review).filter(
        Review.center_id == center_id,
        Review.status == ApprovalStatus.approved,
    ).order_by(Review.created_at.desc()).all()

    return [
        {
            "id": r.id, "student_name": r.student_name, "rating": r.rating,
            "comment": r.comment, "created_at": r.created_at,
        }
        for r in reviews
    ]


# ═══════════════════════════════════════════════════════
#  STUDENT LEADS / APPLICATIONS — partner management
# ═══════════════════════════════════════════════════════

from models.center import CourseApplication, ApplicationStatus

class AppStatusBody(BaseModel):
    status: str


@router.get("/applications")
def list_my_applications(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    """Fetch all student inquiries/applications for centers owned by this partner."""
    my_center_ids = [c.id for c in partner.centers]
    if not my_center_ids:
        return []

    apps = (
        db.query(CourseApplication)
        .filter(CourseApplication.center_id.in_(my_center_ids))
        .order_by(CourseApplication.created_at.desc())
        .all()
    )

    return [
        {
            "id":           a.id,
            "center_id":    a.center_id,
            "center_name":  a.center.name if a.center else None,
            "course_id":    a.course_id,
            "course_name":  a.course.name if a.course else None,
            "student_name": a.student_name,
            "phone":        a.phone,
            "email":        a.email,
            "notes":        a.notes,
            "status":       a.status.value if hasattr(a.status, "value") else a.status,
            "created_at":   a.created_at,
        }
        for a in apps
    ]


@router.patch("/applications/{app_id}/status")
def update_application_status(
    app_id: int,
    body: AppStatusBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    app = db.query(CourseApplication).filter(CourseApplication.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    _owns_center(partner, app.center_id, db)

    try:
        app.status = ApplicationStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    db.commit()
    return {"id": app.id, "status": app.status}