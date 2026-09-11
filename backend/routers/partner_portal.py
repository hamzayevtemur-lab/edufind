import os, hashlib
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta

from database import get_db
from models.center import (
    Partner, LearningCenter, Campus, Course, Review,
    CourseApplication, ApplicationStatus, ApprovalStatus, CourseStatus,
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
#  SINGLE CENTER PROVISIONING HELPER & SERIALIZERS
# ═══════════════════════════════════════════════════════

def _get_or_create_partner_center(partner: Partner, db: Session) -> LearningCenter:
    center = db.query(LearningCenter).filter(LearningCenter.partner_id == partner.id).first()
    if not center:
        center = LearningCenter(
            name        = partner.business_name,
            phone       = partner.phone,
            email       = partner.email,
            address     = partner.address,
            description = partner.description,
            city        = "Tashkent",
            status      = ApprovalStatus.approved,
            partner_id  = partner.id,
        )
        db.add(center)
        db.commit()
        db.refresh(center)

        main_campus = Campus(
            center_id = center.id,
            name      = f"{center.name} - Main Campus",
            address   = center.address or "Main Location",
            city      = center.city or "Tashkent",
            phone     = center.phone,
            is_main   = 1,
        )
        db.add(main_campus)
        db.commit()
        db.refresh(center)

    return center


def _serialize_campus(c: Campus) -> dict:
    return {
        "id":         c.id,
        "center_id":  c.center_id,
        "name":       c.name,
        "address":    c.address,
        "city":       c.city,
        "phone":      c.phone,
        "latitude":   c.latitude,
        "longitude":  c.longitude,
        "is_main":    c.is_main or 0,
        "created_at": c.created_at,
    }


def _serialize_course(co: Course) -> dict:
    return {
        "id":             co.id,
        "center_id":      co.center_id,
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
    }


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
        "campuses":     [_serialize_campus(cam) for cam in c.campuses],
    }


# ═══════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════

@router.get("/stats")
def partner_stats(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    center = _get_or_create_partner_center(partner, db)

    active_courses = [co for co in center.courses if co.status == CourseStatus.active]
    approved_reviews = [r for r in center.reviews if r.status == ApprovalStatus.approved]
    all_ratings = [r.rating for r in approved_reviews]

    avg_rating = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else 0.0

    return {
        "total_centers":  1,
        "total_campuses": len(center.campuses),
        "total_courses":  len(active_courses),
        "total_reviews":  len(approved_reviews),
        "avg_rating":     avg_rating,
        "plan":           partner.plan.value if hasattr(partner.plan, "value") else partner.plan,
        "expires_at":     partner.plan_expires_at,
        "extension_requested": partner.extension_requested or 0,
    }


# ═══════════════════════════════════════════════════════
#  MY SINGLE LEARNING CENTER
# ═══════════════════════════════════════════════════════

@router.get("/my-center")
def get_my_single_center(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    data = _serialize_center(c)
    data["courses"] = [_serialize_course(co) for co in c.courses]
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


@router.get("/centers")
def list_my_centers(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    return [_serialize_center(c)]


@router.get("/centers/{center_id}")
def get_my_center(
    center_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    if c.id != center_id:
        raise HTTPException(status_code=404, detail="Center not found")

    data = _serialize_center(c)
    data["courses"] = [_serialize_course(co) for co in c.courses]
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


@router.patch("/my-center")
@router.patch("/centers/{center_id}")
def update_my_center(
    body: CenterUpdateBody,
    center_id: Optional[int] = None,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    if center_id and c.id != center_id:
        raise HTTPException(status_code=404, detail="Center not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(c, field, value)

    db.commit()
    db.refresh(c)
    return _serialize_center(c)


# ═══════════════════════════════════════════════════════
#  CAMPUSES / BRANCHES
# ═══════════════════════════════════════════════════════

class CampusBody(BaseModel):
    name:      str
    address:   Optional[str]   = None
    city:      Optional[str]   = None
    phone:     Optional[str]   = None
    latitude:  Optional[float] = None
    longitude: Optional[float] = None
    is_main:   Optional[int]   = 0


@router.get("/campuses")
def list_my_campuses(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    center = _get_or_create_partner_center(partner, db)
    campuses = db.query(Campus).filter(Campus.center_id == center.id).order_by(Campus.is_main.desc(), Campus.id.asc()).all()
    return [_serialize_campus(c) for c in campuses]


@router.post("/campuses", status_code=201)
def create_campus(
    body: CampusBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    center = _get_or_create_partner_center(partner, db)
    if body.is_main:
        db.query(Campus).filter(Campus.center_id == center.id).update({"is_main": 0})

    c = Campus(
        center_id = center.id,
        name      = body.name.strip(),
        address   = body.address.strip() if body.address else None,
        city      = body.city.strip() if body.city else center.city,
        phone     = body.phone.strip() if body.phone else center.phone,
        latitude  = body.latitude,
        longitude = body.longitude,
        is_main   = 1 if body.is_main else 0,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _serialize_campus(c)


@router.patch("/campuses/{campus_id}")
def update_campus(
    campus_id: int,
    body: CampusBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    center = _get_or_create_partner_center(partner, db)
    c = db.query(Campus).filter(Campus.id == campus_id, Campus.center_id == center.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campus not found")

    if body.is_main:
        db.query(Campus).filter(Campus.center_id == center.id).update({"is_main": 0})

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(c, field, value)

    db.commit()
    db.refresh(c)
    return _serialize_campus(c)


@router.delete("/campuses/{campus_id}")
def delete_campus(
    campus_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    center = _get_or_create_partner_center(partner, db)
    c = db.query(Campus).filter(Campus.id == campus_id, Campus.center_id == center.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campus not found")

    count = db.query(Campus).filter(Campus.center_id == center.id).count()
    if count <= 1:
        raise HTTPException(status_code=400, detail="You cannot delete your primary campus. Add another campus first.")

    db.delete(c)
    db.commit()
    return {"message": "Campus deleted"}


# ═══════════════════════════════════════════════════════
#  COURSES
# ═══════════════════════════════════════════════════════

class CourseBody(BaseModel):
    name:           str
    campus_id:      Optional[int]   = None
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
    c = _get_or_create_partner_center(partner, db)
    courses = db.query(Course).filter(Course.center_id == c.id).all()
    return [_serialize_course(co) for co in courses]


@router.post("/centers/{center_id}/courses", status_code=201)
def create_course(
    center_id: int,
    body: CourseBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    try:
        status_val = CourseStatus(body.status or "active")
    except ValueError:
        status_val = CourseStatus.active

    cid = body.campus_id
    if cid:
        cam = db.query(Campus).filter(Campus.id == cid, Campus.center_id == c.id).first()
        if not cam:
            cid = None

    co = Course(
        center_id      = c.id,
        campus_id      = cid,
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
    return _serialize_course(co)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int,
    body: CourseBody,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    co = db.query(Course).filter(Course.id == course_id, Course.center_id == c.id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Course not found")

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "status":
            try:
                value = CourseStatus(value)
            except ValueError:
                continue
        elif field == "campus_id" and value:
            cam = db.query(Campus).filter(Campus.id == value, Campus.center_id == c.id).first()
            if not cam:
                value = None
        setattr(co, field, value)

    db.commit()
    db.refresh(co)
    return _serialize_course(co)


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)
    co = db.query(Course).filter(Course.id == course_id, Course.center_id == c.id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Course not found")
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
    c = _get_or_create_partner_center(partner, db)
    reviews = db.query(Review).filter(
        Review.center_id == c.id,
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

class AppStatusBody(BaseModel):
    status: str


@router.get("/applications")
def list_my_applications(
    partner: Partner = Depends(get_partner),
    db: Session = Depends(get_db),
):
    c = _get_or_create_partner_center(partner, db)

    apps = (
        db.query(CourseApplication)
        .filter(CourseApplication.center_id == c.id)
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
    c = _get_or_create_partner_center(partner, db)
    app = db.query(CourseApplication).filter(CourseApplication.id == app_id, CourseApplication.center_id == c.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        app.status = ApplicationStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    db.commit()
    return {"id": app.id, "status": app.status}