from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CenterListItem(BaseModel):
    id:           int
    name:         str
    description:  Optional[str]   = None
    logo_url:     Optional[str]   = None
    city:         Optional[str]   = None
    phone:        Optional[str]   = None
    email:        Optional[str]   = None
    website:      Optional[str]   = None
    status:       str
    avg_rating:   Optional[float] = None
    review_count: int             = 0
    course_count: int             = 0
    likes_count:  int             = 0
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    created_at:   Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedCenters(BaseModel):
    items:    List[CenterListItem]
    total:    int
    page:     int
    per_page: int
    pages:    int


class PublicStats(BaseModel):
    centers: int
    courses: int
    teachers: int = 0