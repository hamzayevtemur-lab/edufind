from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Dashboard Stats ──────────────────────────────

class AdminStats(BaseModel):
    total_centers:      int
    approved_centers:   int
    pending_centers:    int
    total_courses:      int
    total_reviews:      int
    pending_reviews:    int
    total_partners:     int
    pending_requests:   int


# ── Center (Admin) ───────────────────────────────

class AdminCenterCreate(BaseModel):
    name:        str
    city:        str
    description: Optional[str]   = None
    phone:       Optional[str]   = None
    email:       Optional[str]   = None
    website:     Optional[str]   = None
    address:     Optional[str]   = None
    logo_url:    Optional[str]   = None
    latitude:    Optional[float] = None
    longitude:   Optional[float] = None
    status:      Optional[str]   = "approved"   # admin creates already-approved


class AdminCenterUpdate(BaseModel):
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
    status:      Optional[str]   = None


class AdminCenterOut(BaseModel):
    id:           int
    name:         str
    city:         Optional[str]   = None
    description:  Optional[str]   = None
    phone:        Optional[str]   = None
    email:        Optional[str]   = None
    website:      Optional[str]   = None
    address:      Optional[str]   = None
    logo_url:     Optional[str]   = None
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    status:       str
    avg_rating:   Optional[float] = None
    review_count: int             = 0
    course_count: int             = 0
    likes_count:  int             = 0
    partner_id:   Optional[int]   = None
    created_at:   Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Course (Admin) ───────────────────────────────

class AdminCourseCreate(BaseModel):
    center_id:      int
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


class AdminCourseOut(BaseModel):
    id:             int
    center_id:      int
    center_name:    Optional[str]   = None
    name:           str
    category:       Optional[str]   = "other"
    status:         str
    description:    Optional[str]   = None
    teacher_name:   Optional[str]   = None
    price:          Optional[float] = None
    currency:       str             = "UZS"
    duration_weeks: Optional[int]   = None
    schedule:       Optional[str]   = None
    max_students:   Optional[int]   = None
    enrolled:       int             = 0

    model_config = {"from_attributes": True}


# ── Review (Admin) ───────────────────────────────

class AdminReviewStatusUpdate(BaseModel):
    status: str    # "approved" | "rejected"


class AdminReviewOut(BaseModel):
    id:           int
    center_id:    int
    center_name:  Optional[str]   = None
    student_name: str
    rating:       int
    comment:      Optional[str]   = None
    status:       str
    created_at:   Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Partner Request (Admin) ──────────────────────

class AdminPartnerRequestOut(BaseModel):
    id:             int
    business_name:  str
    contact_person: str
    email:          str
    phone:          str
    business_type:  str
    plan:           str
    amount:         float
    status:         str
    description:    Optional[str]   = None
    created_at:     Optional[datetime] = None
    reviewed_at:    Optional[datetime] = None

    model_config = {"from_attributes": True}