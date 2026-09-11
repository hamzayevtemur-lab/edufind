import os, hashlib, secrets, string
from datetime import datetime, timedelta
from pydantic import BaseModel as PydanticBase
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime

from database import get_db
from models.center import (
    LearningCenter, Campus, Course, Review, CenterLike,
    ApprovalStatus, CourseStatus,
    Partner, PartnerSignupRequest, PartnerRequestStatus, PartnerPlan
)
from schemas.admin import (
    AdminStats,
    AdminCenterCreate, AdminCenterUpdate, AdminCenterOut,
    AdminCourseCreate, AdminCourseOut,
    AdminReviewStatusUpdate, AdminReviewOut,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "Ironman3106)")


# ── Auth helper ────────────────────────────────────────────────────

def require_admin(
    x_admin_token: Optional[str] = Header(None),
    admin_token:   Optional[str] = Query(None),
):
    token = x_admin_token or admin_token
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")


# ═══════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════

@router.get("/stats", response_model=AdminStats, dependencies=[Depends(require_admin)])
def admin_stats(db: Session = Depends(get_db)):
    total_centers    = db.query(LearningCenter).count()
    approved_centers = db.query(LearningCenter).filter(LearningCenter.status == ApprovalStatus.approved).count()
    pending_centers  = db.query(LearningCenter).filter(LearningCenter.status == ApprovalStatus.pending).count()
    total_courses    = db.query(Course).count()
    total_reviews    = db.query(Review).count()
    pending_reviews  = db.query(Review).filter(Review.status == ApprovalStatus.pending).count()
    total_partners   = db.query(Partner).count()
    pending_requests = db.query(PartnerSignupRequest).filter(
        PartnerSignupRequest.status == PartnerRequestStatus.pending
    ).count()

    return AdminStats(
        total_centers    = total_centers,
        approved_centers = approved_centers,
        pending_centers  = pending_centers,
        total_courses    = total_courses,
        total_reviews    = total_reviews,
        pending_reviews  = pending_reviews,
        total_partners   = total_partners,
        pending_requests = pending_requests,
    )


# ═══════════════════════════════════════════════════════
#  CENTERS
# ═══════════════════════════════════════════════════════

def _serialize_center(c: LearningCenter) -> dict:
    return {
        "id":           c.id,
        "name":         c.name,
        "city":         c.city,
        "description":  c.description,
        "phone":        c.phone,
        "email":        c.email,
        "website":      c.website,
        "address":      c.address,
        "logo_url":     c.logo_url,
        "latitude":     c.latitude,
        "longitude":    c.longitude,
        "status":       c.status.value if hasattr(c.status, "value") else c.status,
        "avg_rating":   c.avg_rating,
        "review_count": c.review_count,
        "course_count": c.course_count,
        "likes_count":  c.likes_count,
        "partner_id":   c.partner_id,
        "created_at":   c.created_at,
    }


@router.get("/centers", dependencies=[Depends(require_admin)])
def list_centers(
    status: Optional[str] = None,
    city:   Optional[str] = None,
    page:   int = 1,
    limit:  int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(LearningCenter)
    if status and status != "all":
        try:
            q = q.filter(LearningCenter.status == ApprovalStatus(status))
        except ValueError:
            pass
    if city:
        q = q.filter(LearningCenter.city.ilike(f"%{city}%"))

    total   = q.count()
    centers = q.order_by(LearningCenter.created_at.desc()) \
               .offset((page - 1) * limit).limit(limit).all()

    return {
        "total":   total,
        "page":    page,
        "limit":   limit,
        "centers": [_serialize_center(c) for c in centers],
    }


@router.post("/centers", status_code=201, dependencies=[Depends(require_admin)])
def create_center(body: AdminCenterCreate, db: Session = Depends(get_db)):
    try:
        status_val = ApprovalStatus(body.status or "approved")
    except ValueError:
        status_val = ApprovalStatus.approved

    center = LearningCenter(
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
        status      = status_val,
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    return _serialize_center(center)


@router.get("/centers/{center_id}", dependencies=[Depends(require_admin)])
def get_center(center_id: int, db: Session = Depends(get_db)):
    c = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")
    data = _serialize_center(c)
    data["courses"] = [
        {
            "id": co.id, "name": co.name, "status": co.status.value if hasattr(co.status,"value") else co.status,
            "teacher_name": co.teacher_name, "price": co.price, "currency": co.currency,
            "schedule": co.schedule, "enrolled": co.enrolled, "max_students": co.max_students,
        }
        for co in c.courses
    ]
    data["reviews"] = [
        {
            "id": r.id, "student_name": r.student_name, "rating": r.rating,
            "comment": r.comment, "status": r.status.value if hasattr(r.status,"value") else r.status,
            "created_at": r.created_at,
        }
        for r in c.reviews
    ]
    return data


@router.patch("/centers/{center_id}", dependencies=[Depends(require_admin)])
def update_center(center_id: int, body: AdminCenterUpdate, db: Session = Depends(get_db)):
    c = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "status":
            try:
                value = ApprovalStatus(value)
            except ValueError:
                continue
        setattr(c, field, value)

    db.commit()
    db.refresh(c)
    return _serialize_center(c)


@router.delete("/centers/{center_id}", dependencies=[Depends(require_admin)])
def delete_center(center_id: int, db: Session = Depends(get_db)):
    c = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Center not found")
    db.delete(c)
    db.commit()
    return {"message": f"Center #{center_id} deleted"}


# ═══════════════════════════════════════════════════════
#  COURSES
# ═══════════════════════════════════════════════════════

@router.get("/courses", dependencies=[Depends(require_admin)])
def list_courses(
    center_id: Optional[int] = None,
    status:    Optional[str] = None,
    category:  Optional[str] = None,  # ✅ Make sure this line exists
    db: Session = Depends(get_db),
):
    print(f"📊 Courses API called - category: {category}, status: {status}")
    
    q = db.query(Course)
    
    # Filter by center
    if center_id:
        q = q.filter(Course.center_id == center_id)
    
    # Filter by status
    if status and status != "all":
        try:
            q = q.filter(Course.status == CourseStatus(status))
        except ValueError:
            pass
    
    # ✅ CRITICAL: Filter by category
    if category and category != "all":
        q = q.filter(Course.category == category)
        print(f"✅ Filtering by category: {category}")
    
    courses = q.order_by(Course.id.desc()).all()
    print(f"📚 Found {len(courses)} courses")
    
    result = []
    for co in courses:
        result.append({
            "id":             co.id,
            "center_id":      co.center_id,
            "center_name":    co.center.name if co.center else None,
            "name":           co.name,
            "category":       co.category,  # ✅ Make sure this is included
            "status":         co.status.value if hasattr(co.status, "value") else co.status,
            "description":    co.description,
            "teacher_name":   co.teacher_name,
            "price":          co.price,
            "currency":       co.currency,
            "duration_weeks": co.duration_weeks,
            "schedule":       co.schedule,
            "max_students":   co.max_students,
            "enrolled":       co.enrolled,
        })
    
    return result

@router.post("/courses", status_code=201, dependencies=[Depends(require_admin)])
def create_course(body: AdminCourseCreate, db: Session = Depends(get_db)):
    center = db.query(LearningCenter).filter(LearningCenter.id == body.center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    try:
        status_val = CourseStatus(body.status or "active")
    except ValueError:
        status_val = CourseStatus.active

    course = Course(
        center_id      = body.center_id,
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
    db.add(course)
    db.commit()
    db.refresh(course)
    return {"id": course.id, "name": course.name, "category": course.category, "center_id": course.center_id}


@router.patch("/courses/{course_id}/status", dependencies=[Depends(require_admin)])
def update_course_status(course_id: int, status: str, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        course.status = CourseStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    db.commit()
    return {"id": course.id, "status": course.status}


@router.delete("/courses/{course_id}", dependencies=[Depends(require_admin)])
def delete_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return {"message": f"Course #{course_id} deleted"}


# ═══════════════════════════════════════════════════════
#  REVIEWS
# ═══════════════════════════════════════════════════════

@router.get("/reviews", dependencies=[Depends(require_admin)])
def list_reviews(
    status:    Optional[str] = "pending",
    center_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Review)
    if center_id:
        q = q.filter(Review.center_id == center_id)
    if status and status != "all":
        try:
            q = q.filter(Review.status == ApprovalStatus(status))
        except ValueError:
            pass

    reviews = q.order_by(Review.created_at.desc()).all()
    return [
        {
            "id":           r.id,
            "center_id":    r.center_id,
            "center_name":  r.center.name if r.center else None,
            "student_name": r.student_name,
            "rating":       r.rating,
            "comment":      r.comment,
            "status":       r.status.value if hasattr(r.status,"value") else r.status,
            "created_at":   r.created_at,
        }
        for r in reviews
    ]


@router.patch("/reviews/{review_id}", dependencies=[Depends(require_admin)])
def update_review_status(
    review_id: int,
    body: AdminReviewStatusUpdate,
    db: Session = Depends(get_db),
):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    try:
        review.status = ApprovalStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    db.commit()
    return {"id": review.id, "status": review.status}


@router.delete("/reviews/{review_id}", dependencies=[Depends(require_admin)])
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()
    return {"message": f"Review #{review_id} deleted"}


# ═══════════════════════════════════════════════════════
#  PARTNERS (read-only summary — approve/reject is in partner.py)
# ═══════════════════════════════════════════════════════

@router.get("/partners", dependencies=[Depends(require_admin)])
def list_partners(
    is_active: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Partner)
    if is_active is not None:
        q = q.filter(Partner.is_active == is_active)

    partners = q.order_by(Partner.created_at.desc()).all()
    return [
        {
            "id":              p.id,
            "business_name":   p.business_name,
            "contact_person":  p.contact_person,
            "email":           p.email,
            "phone":           p.phone,
            "business_type":   p.business_type,
            "plan":            p.plan.value if hasattr(p.plan,"value") else p.plan,
            "amount_paid":     p.amount_paid,
            "is_active":       p.is_active,
            "plan_expires_at": p.plan_expires_at,
            "created_at":      p.created_at,
        }
        for p in partners
    ]


@router.patch("/partners/{partner_id}/toggle-active", dependencies=[Depends(require_admin)])
def toggle_partner_active(partner_id: int, db: Session = Depends(get_db)):
    """Suspend or re-activate a partner account."""
    p = db.query(Partner).filter(Partner.id == partner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")
    p.is_active = 0 if p.is_active else 1
    db.commit()
    return {"id": p.id, "is_active": p.is_active}


# ═══════════════════════════════════════════════════════
#  PARTNER SIGNUP REQUESTS — approve / reject
# ═══════════════════════════════════════════════════════



class ApproveBody(PydanticBase):
    admin_token: Optional[str] = None


def _hash_pw(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _gen_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def _plan_days(plan_val: str) -> int:
    return {"1month": 30, "3months": 90, "6months": 180, "1year": 365}.get(plan_val, 30)


@router.get("/partner-requests", dependencies=[Depends(require_admin)])
def list_partner_requests(
    status: Optional[str] = "pending",
    db: Session = Depends(get_db)
):
    q = db.query(PartnerSignupRequest)
    if status and status != "all":
        try:
            q = q.filter(PartnerSignupRequest.status == PartnerRequestStatus(status))
        except ValueError:
            pass
    reqs = q.order_by(PartnerSignupRequest.id.desc()).all()
    return [
        {
            "id": r.id,
            "business_name": r.business_name,
            "contact_person": r.contact_person,
            "email": r.email,
            "phone": r.phone,
            "address": r.address,
            "description": r.description,
            "business_type": r.business_type,
            "plan": r.plan.value if hasattr(r.plan, "value") else r.plan,
            "amount": r.amount,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "is_email_verified": getattr(r, "is_email_verified", 0),
            "created_at": r.created_at,
        }
        for r in reqs
    ]


@router.post("/partner-requests/{request_id}/approve", dependencies=[Depends(require_admin)])
def approve_partner_request(
    request_id: int,
    db: Session = Depends(get_db),
):
    req = db.query(PartnerSignupRequest).filter(PartnerSignupRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != PartnerRequestStatus.pending:
        raise HTTPException(status_code=400, detail=f"Request is already {req.status.value}")
    if getattr(req, "is_email_verified", 0) == 0:
        raise HTTPException(status_code=400, detail="Cannot approve: Waiting for applicant to verify email address first.")

    # Check not already approved
    existing = db.query(Partner).filter(Partner.email == req.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Partner with this email already exists")

    pwd = _gen_password()
    plan_val = req.plan.value if hasattr(req.plan, "value") else req.plan
    expires  = datetime.utcnow() + timedelta(days=_plan_days(plan_val))

    partner = Partner(
        business_name   = req.business_name,
        contact_person  = req.contact_person,
        email           = req.email.lower(),
        phone           = req.phone,
        address         = req.address,
        description     = req.description,
        business_type   = req.business_type,
        plan            = req.plan,
        amount_paid     = req.amount,
        password_hash   = _hash_pw(pwd),
        is_active       = 1,
        plan_expires_at = expires,
    )
    db.add(partner)
    db.flush()

    # Create Learning Center for this partner
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
    db.flush()

    # Create Main Campus
    main_campus = Campus(
        center_id = center.id,
        name      = f"{center.name} - Main Campus",
        address   = center.address or "Main Location",
        city      = center.city or "Tashkent",
        phone     = center.phone,
        is_main   = 1,
    )
    db.add(main_campus)

    req.status      = PartnerRequestStatus.approved
    req.reviewed_at = datetime.utcnow()
    req.partner_id  = partner.id
    db.commit()

    # Send credentials email using the full branded template from partner.py
    try:
        from routers.partners import send_email, tpl_credentials
        send_email(
            to        = req.email,
            subject   = "🎉 EduFind Partner Account Ready — Your Login Details",
            html      = tpl_credentials(partner, pwd),
        )
    except Exception as e:
        print(f"⚠️  Could not send credentials email: {e}")
        # Password is returned in the response so admin can share it manually

    return {
        "message":   f"{req.business_name} approved successfully",
        "email":     req.email,
        "password":  pwd,           # shown in admin panel credential modal
        "plan":      req.plan,
        "expires_at": expires,
    }


@router.post("/partner-requests/{request_id}/reject", dependencies=[Depends(require_admin)])
def reject_partner_request(
    request_id: int,
    db: Session = Depends(get_db),
):
    req = db.query(PartnerSignupRequest).filter(PartnerSignupRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != PartnerRequestStatus.pending:
        raise HTTPException(status_code=400, detail=f"Request is already {req.status.value}")

    req.status      = PartnerRequestStatus.rejected
    req.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": f"{req.business_name} rejected"}


# ─── QUICK TEST: create a partner account directly ────────────────

class CreatePartnerBody(PydanticBase):
    business_name:  str
    contact_person: str
    email:          str
    phone:          Optional[str] = "+998 90 000 0000"
    plan:           Optional[str] = "1month"
    password:       Optional[str] = None   # if None, auto-generate


@router.post("/create-partner", dependencies=[Depends(require_admin)])
def create_partner_directly(
    body: CreatePartnerBody,
    db: Session = Depends(get_db),
):
    """Directly create a partner account without a signup request — useful for testing."""
    existing = db.query(Partner).filter(Partner.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Partner with this email already exists")

    try:
        plan_enum = PartnerPlan(body.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {body.plan}")

    pwd      = body.password or _gen_password()
    plan_val = plan_enum.value
    expires  = datetime.utcnow() + timedelta(days=_plan_days(plan_val))

    partner = Partner(
        business_name   = body.business_name,
        contact_person  = body.contact_person,
        email           = body.email.lower(),
        phone           = body.phone,
        plan            = plan_enum,
        amount_paid     = 0,
        password_hash   = _hash_pw(pwd),
        is_active       = 1,
        plan_expires_at = expires,
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)

    return {
        "message":    "Partner created successfully",
        "partner_id": partner.id,
        "email":      partner.email,
        "password":   pwd,
        "plan":       plan_val,
        "expires_at": expires,
    }


# ─── TEST EMAIL ───────────────────────────────────────────────────

@router.post("/test-email", dependencies=[Depends(require_admin)])
def test_email(to: str, db: Session = Depends(get_db)):
    """Send a test email to verify SMTP is working."""
    from .partners import send_email, SMTP_EMAIL
    if not SMTP_EMAIL:
        raise HTTPException(400, "SMTP_EMAIL is not set in .env")
    html = """
    <div style="font-family:sans-serif;background:#07070c;padding:40px;color:#fff;border-radius:16px">
      <h2 style="color:#4f46e5">✅ EduFind Email Test</h2>
      <p style="color:rgba(255,255,255,.7);margin-top:12px">
        If you received this, your Gmail SMTP is working correctly.<br>
        The full email system is ready to go!
      </p>
    </div>
    """
    sent = send_email(to=to, subject="✅ EduFind — Email Test", html=html)
    if sent:
        return {"message": f"Test email sent to {to}. Check your inbox!"}
    else:
        raise HTTPException(500, "Email failed — check uvicorn logs for details. Make sure SMTP_EMAIL and SMTP_PASSWORD are set in .env and that you are using a Gmail App Password.")


# ═══════════════════════════════════════════════════════
#  PLAN EXTENSION REQUESTS MODERATION
# ═══════════════════════════════════════════════════════

@router.get("/extension-requests", dependencies=[Depends(require_admin)])
def list_extension_requests(db: Session = Depends(get_db)):
    partners = db.query(Partner).filter(Partner.extension_requested == 1).order_by(Partner.id.desc()).all()
    return [
        {
            "id":              p.id,
            "business_name":   p.business_name,
            "contact_person":  p.contact_person,
            "email":           p.email,
            "phone":           p.phone,
            "plan":            p.plan.value if hasattr(p.plan, "value") else p.plan,
            "plan_expires_at": p.plan_expires_at,
            "created_at":      p.created_at,
        }
        for p in partners
    ]


@router.post("/extension-requests/{partner_id}/approve", dependencies=[Depends(require_admin)])
def approve_partner_extension(partner_id: int, db: Session = Depends(get_db)):
    p = db.query(Partner).filter(Partner.id == partner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")

    now = datetime.utcnow()
    current_exp = p.plan_expires_at or now
    base_date = max(now, current_exp)
    p.plan_expires_at = base_date + timedelta(days=30)
    p.extension_requested = 0
    db.commit()

    # Notify partner via email
    try:
        from .partners import send_email
        send_email(
            to=p.email,
            subject="🎉 Your EduFind 1-Month Free Plan Extension is Approved!",
            html=f"""
            <div style="font-family:sans-serif;background:#07070c;padding:40px;color:#fff;border-radius:16px">
              <h2 style="color:#10b981">🎉 Plan Extension Approved!</h2>
              <p style="color:rgba(255,255,255,.8);line-height:1.7">
                Hi <strong>{p.contact_person}</strong>,<br>
                Your request to extend <strong>{p.business_name}</strong>'s free plan by another 30 days has been approved!
              </p>
            </div>
            """
        )
    except Exception as e:
        print(f"⚠️ Extension approval email error: {e}")

    return {
        "message": f"Extension approved for {p.business_name}",
        "partner_id": p.id,
        "expires_at": p.plan_expires_at,
    }


@router.post("/extension-requests/{partner_id}/reject", dependencies=[Depends(require_admin)])
def reject_partner_extension(partner_id: int, db: Session = Depends(get_db)):
    p = db.query(Partner).filter(Partner.id == partner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Partner not found")

    p.extension_requested = 0
    db.commit()
    return {"message": f"Extension request rejected for {p.business_name}"}