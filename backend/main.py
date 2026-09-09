import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from models.center import LearningCenter, Course, Review, ApprovalStatus, CourseStatus
from routers import centers, center, likes, partners, admin, partner_portal

from database import SessionLocal

app = FastAPI(title="Startup2 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(centers.router)
app.include_router(center.router)
app.include_router(likes.router)
app.include_router(partners.router)
app.include_router(admin.router)
app.include_router(partner_portal.router)

@app.get("/api")
def root():
    return {"message": "FastAPI backend is running 🚀"}

# ── STATIC FILES ──────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")