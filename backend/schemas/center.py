from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


class CampusOut(BaseModel):
    id:        int
    center_id: int
    name:      str
    address:   Optional[str]   = None
    city:      Optional[str]   = None
    phone:     Optional[str]   = None
    latitude:  Optional[float] = None
    longitude: Optional[float] = None
    is_main:   int             = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CourseOut(BaseModel):
    id:             int
    campus_id:      Optional[int]   = None
    campus_name:    Optional[str]   = None
    name:           str
    description:    Optional[str]   = None
    teacher_name:   Optional[str]   = None
    price:          Optional[float] = None
    currency:       str             = "UZS"
    duration_weeks: Optional[int]   = None
    schedule:       Optional[str]   = None
    max_students:   Optional[int]   = None
    enrolled:       int             = 0
    starts_at:      Optional[datetime] = None
    status:         str             = "active"

    model_config = {"from_attributes": True}


class ReviewOut(BaseModel):
    id:           int
    student_name: str
    rating:       int
    comment:      Optional[str]      = None
    created_at:   Optional[datetime] = None

    model_config = {"from_attributes": True}


class CenterDetail(BaseModel):
    id:           int
    name:         str
    description:  Optional[str]   = None
    logo_url:     Optional[str]   = None
    city:         Optional[str]   = None
    phone:        Optional[str]   = None
    email:        Optional[str]   = None
    website:      Optional[str]   = None
    address:      Optional[str]   = None
    status:       str
    avg_rating:   Optional[float] = None
    review_count: int             = 0
    course_count: int             = 0
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    created_at:   Optional[datetime] = None
    campuses:     List[CampusOut]  = []
    courses:      List[CourseOut]  = []
    reviews:      List[ReviewOut]  = []

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    center_id:    int
    student_name: str
    rating:       int
    comment:      Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_must_be_valid(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("Rating must be between 1 and 5")
        return v