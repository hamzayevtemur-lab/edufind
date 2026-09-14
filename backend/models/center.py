from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# ═══════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════

class ApprovalStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class CourseStatus(str, enum.Enum):
    active      = "active"
    coming_soon = "coming_soon"
    closed      = "closed"
    
class CourseCategory(str, enum.Enum):
    math = "math"
    english = "english"
    ielts = "ielts"
    programming = "programming"
    sat = "sat"
    kids = "kids"
    art = "art"
    other = "other"


class PartnerPlan(str, enum.Enum):
    free_1month = "free_1month"
    month_1 = "1month"
    month_3 = "3months"
    month_6 = "6months"
    year_1  = "1year"


class PartnerRequestStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


# ═══════════════════════════════════════════════
#  PARTNER  (must come before LearningCenter — FK direction)
# ═══════════════════════════════════════════════

class Partner(Base):
    """Created when admin approves a PartnerSignupRequest."""
    __tablename__ = "partners"

    id              = Column(Integer, primary_key=True, index=True)
    business_name   = Column(String(255), nullable=False)
    contact_person  = Column(String(255), nullable=False)
    email           = Column(String(255), nullable=False, unique=True, index=True)
    phone           = Column(String(50),  nullable=True)
    address         = Column(Text,        nullable=True)
    description     = Column(Text,        nullable=True)
    business_type   = Column(String(50),  nullable=True)
    plan = Column(SAEnum(PartnerPlan,name="partner_plan",values_callable=lambda x: [e.value for e in x]),
    nullable=False
)
    amount_paid     = Column(Float,       nullable=False)
    password_hash   = Column(String(255), nullable=False)
    is_active       = Column(Integer,     server_default="1")
    extension_requested = Column(Integer, server_default="0")
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    centers        = relationship("LearningCenter",      back_populates="partner")
    signup_request = relationship("PartnerSignupRequest", back_populates="partner", uselist=False,cascade="all, delete-orphan")



# ═══════════════════════════════════════════════
#  LEARNING CENTER
# ═══════════════════════════════════════════════

class LearningCenter(Base):
    __tablename__ = "learning_centers"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    logo_url    = Column(String(500))
    phone       = Column(String(50))
    email       = Column(String(255))
    website     = Column(String(500))
    address     = Column(Text)
    city        = Column(String(100), index=True)
    status      = Column(SAEnum(ApprovalStatus, name="center_status"),
                         nullable=False, server_default="pending", index=True)
    likes_count = Column(Integer, server_default="0", nullable=False)
    latitude    = Column(Float, nullable=True)
    longitude   = Column(Float, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # which partner owns this center (NULL = admin-seeded)
    partner_id  = Column(Integer, ForeignKey("partners.id"), nullable=True)

    partner = relationship("Partner",    back_populates="centers")
    courses = relationship("Course",     back_populates="center", cascade="all, delete-orphan")
    campuses = relationship("Campus",    back_populates="center", cascade="all, delete-orphan")
    reviews = relationship("Review",     back_populates="center", cascade="all, delete-orphan")
    likes   = relationship("CenterLike", back_populates="center", cascade="all, delete-orphan")
    applications = relationship("CourseApplication", back_populates="center", cascade="all, delete-orphan")
    course_requests = relationship("CourseRequest", back_populates="center", cascade="all, delete-orphan")

    @property
    def avg_rating(self):
        approved = [r.rating for r in self.reviews if r.status == ApprovalStatus.approved]
        return round(sum(approved) / len(approved), 1) if approved else None

    @property
    def review_count(self):
        return sum(1 for r in self.reviews if r.status == ApprovalStatus.approved)

    @property
    def course_count(self):
        return sum(1 for c in self.courses if c.status == CourseStatus.active)


# ═══════════════════════════════════════════════
#  CAMPUS / BRANCH
# ═══════════════════════════════════════════════

class Campus(Base):
    __tablename__ = "campuses"

    id         = Column(Integer, primary_key=True, index=True)
    center_id  = Column(Integer, ForeignKey("learning_centers.id", ondelete="CASCADE"), nullable=False)
    name       = Column(String(255), nullable=False)
    address    = Column(Text, nullable=True)
    city       = Column(String(100), nullable=True)
    phone      = Column(String(50), nullable=True)
    latitude   = Column(Float, nullable=True)
    longitude  = Column(Float, nullable=True)
    is_main    = Column(Integer, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    center  = relationship("LearningCenter", back_populates="campuses")
    courses = relationship("Course", back_populates="campus")


# ═══════════════════════════════════════════════
#  CENTER LIKE
# ═══════════════════════════════════════════════

class CenterLike(Base):
    """One row per (center, user_token) — prevents duplicate likes."""
    __tablename__ = "center_likes"

    id         = Column(Integer, primary_key=True, index=True)
    center_id  = Column(Integer, ForeignKey("learning_centers.id"), nullable=False)
    user_token = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    center = relationship("LearningCenter", back_populates="likes")

    __table_args__ = (
        UniqueConstraint("center_id", "user_token", name="uq_center_user_like"),
    )


# ═══════════════════════════════════════════════
#  COURSE
# ═══════════════════════════════════════════════

class Course(Base):
    __tablename__ = "courses"

    id             = Column(Integer, primary_key=True, index=True)
    center_id      = Column(Integer, ForeignKey("learning_centers.id"), nullable=False)
    campus_id      = Column(Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True)
    name           = Column(String(255), nullable=False)
    status         = Column(SAEnum(CourseStatus, name="course_status"),
                            nullable=False, server_default="active")
    description    = Column(Text)
    teacher_name   = Column(String(255))
    price          = Column(Float)
    currency       = Column(String(10), server_default="UZS")
    duration_weeks = Column(Integer)
    schedule       = Column(String(255))
    max_students   = Column(Integer)
    enrolled       = Column(Integer, server_default="0")
    starts_at      = Column(DateTime)
    category       = Column(String(50), default="other") 

    center   = relationship("LearningCenter", back_populates="courses")
    campus   = relationship("Campus", back_populates="courses")
    applications = relationship("CourseApplication", back_populates="course", cascade="all, delete-orphan")


# ═══════════════════════════════════════════════
#  REVIEW
# ═══════════════════════════════════════════════

class Review(Base):
    __tablename__ = "reviews"

    id           = Column(Integer, primary_key=True, index=True)
    center_id    = Column(Integer, ForeignKey("learning_centers.id"), nullable=False)
    student_name = Column(String(255), nullable=False)
    rating       = Column(Integer, nullable=False)
    status       = Column(SAEnum(ApprovalStatus, name="review_status"),
                          nullable=False, server_default="pending")
    comment      = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    center = relationship("LearningCenter", back_populates="reviews")


# ═══════════════════════════════════════════════
#  APPLICATION STATUS
# ═══════════════════════════════════════════════

class ApplicationStatus(str, enum.Enum):
    pending   = "pending"
    contacted = "contacted"
    enrolled  = "enrolled"
    cancelled = "cancelled"


# ═══════════════════════════════════════════════
#  PARTNER SIGNUP REQUEST
# ═══════════════════════════════════════════════

class PartnerSignupRequest(Base):
    """Submitted on partner-signup.html — pending until admin approves."""
    __tablename__ = "partner_signup_requests"

    id             = Column(Integer, primary_key=True, index=True)
    business_type  = Column(String(50),  nullable=False)
    business_name  = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=False)
    email          = Column(String(255), nullable=False, index=True)
    phone          = Column(String(50),  nullable=False)
    address        = Column(Text,        nullable=True)
    description    = Column(Text,        nullable=True)
    plan = Column(SAEnum(PartnerPlan,name="partner_plan_req",
        values_callable=lambda x: [e.value for e in x]
    ),
    nullable=False
)
    amount         = Column(Float,       nullable=False)
    status         = Column(SAEnum(PartnerRequestStatus, name="partner_request_status"),
                            nullable=False, server_default="pending", index=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at    = Column(DateTime(timezone=True), nullable=True)
    is_email_verified = Column(Integer, server_default="0")
    
    approve_token  = Column(String(128), unique=True, nullable=True)  

    # FK set when admin approves → links to the created Partner
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True)
    partner = relationship("Partner", back_populates="signup_request")


# ═══════════════════════════════════════════════
#  COURSE APPLICATION (STUDENT LEADS)
# ═══════════════════════════════════════════════

class CourseApplication(Base):
    """Submitted by students on center.html or courses.html when applying for a course."""
    __tablename__ = "course_applications"

    id           = Column(Integer, primary_key=True, index=True)
    center_id    = Column(Integer, ForeignKey("learning_centers.id"), nullable=False)
    course_id    = Column(Integer, ForeignKey("courses.id"), nullable=False)
    student_name = Column(String(255), nullable=False)
    phone        = Column(String(50),  nullable=False)
    email              = Column(String(255), nullable=True)
    preferred_schedule = Column(String(255), nullable=True)
    notes              = Column(Text,        nullable=True)
    status       = Column(SAEnum(ApplicationStatus, name="app_status"), nullable=False, server_default="pending", index=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    center = relationship("LearningCenter", back_populates="applications")
    course = relationship("Course", back_populates="applications")


# ═══════════════════════════════════════════════
#  COURSE REQUEST STATUS & MODEL
# ═══════════════════════════════════════════════

class CourseRequestStatus(str, enum.Enum):
    pending  = "pending"
    reviewed = "reviewed"
    accepted = "accepted"
    rejected = "rejected"


class CourseRequest(Base):
    """Submitted by students requesting new/custom courses at a Learning Center."""
    __tablename__ = "course_requests"

    id                 = Column(Integer, primary_key=True, index=True)
    center_id          = Column(Integer, ForeignKey("learning_centers.id", ondelete="CASCADE"), nullable=False)
    title              = Column(String(255), nullable=False)
    category           = Column(String(50), default="other")
    preferred_schedule = Column(String(255), nullable=True)
    student_name       = Column(String(255), nullable=False)
    phone              = Column(String(50),  nullable=False)
    email              = Column(String(255), nullable=True)
    notes              = Column(Text,        nullable=True)
    votes_count        = Column(Integer,     server_default="1", nullable=False)
    status             = Column(SAEnum(CourseRequestStatus, name="course_req_status"), nullable=False, server_default="pending", index=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())

    center = relationship("LearningCenter", back_populates="course_requests")
    votes  = relationship("CourseRequestVote", back_populates="request", cascade="all, delete-orphan")


class CourseRequestVote(Base):
    """One row per (request_id, user_token) — prevents duplicate votes on course requests."""
    __tablename__ = "course_request_votes"

    id         = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("course_requests.id", ondelete="CASCADE"), nullable=False)
    user_token = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    request = relationship("CourseRequest", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("request_id", "user_token", name="uq_request_user_vote"),
    )


    