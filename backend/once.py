import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, SessionLocal
from models.center import (
    LearningCenter, Course, Review, Partner,
    ApprovalStatus, CourseStatus
)

# 1. Create tables using SQLAlchemy models
Base.metadata.create_all(bind=engine)
print("✅ Database tables initialized successfully!")

db = SessionLocal()

# 2. Check if data exists
if db.query(LearningCenter).count() > 0:
    print("ℹ️ Data already exists — skipping seeding.")
    db.close()
    sys.exit()

# 3. Seed Learning Centers
centers_data = [
    {
        "name": "Bright Future Language Center",
        "description": "Toshkentning yetakchi ingliz tili markazi. IELTS, TOEFL va umumiy ingliz tili kurslari.",
        "phone": "+998 71 234-56-78", "email": "info@brightfuture.uz", "website": "https://brightfuture.uz",
        "address": "Amir Temur ko'chasi 108", "city": "Tashkent", "status": ApprovalStatus.approved,
        "latitude": 41.311081, "longitude": 69.279651, "likes_count": 24
    },
    {
        "name": "MathPro Academy",
        "description": "SAT, DBA va maktab matematikasiga ixtisoslashgan markaz. Kichik guruhlar, tajribali o'qituvchilar.",
        "phone": "+998 71 345-67-89", "email": "info@mathpro.uz", "website": "https://mathpro.uz",
        "address": "Chilonzor tumani, 7-mavze, 12-uy", "city": "Tashkent", "status": ApprovalStatus.approved,
        "latitude": 41.285830, "longitude": 69.203510, "likes_count": 18
    },
    {
        "name": "CodeCraft IT Academy",
        "description": "Python, Web dasturlash va Data Science bo'yicha zamonaviy IT kurslari. Amaliy loyihalar.",
        "phone": "+998 66 234-56-78", "email": "hello@codecraft.uz", "website": "https://codecraft.uz",
        "address": "Registon ko'chasi 15", "city": "Samarkand", "status": ApprovalStatus.approved,
        "latitude": 39.654700, "longitude": 66.975800, "likes_count": 35
    },
    {
        "name": "Oxford English School",
        "description": "Barcha yoshlar uchun ingliz tili kurslari. Sertifikatlangan o'qituvchilar jamoasi.",
        "phone": "+998 73 234-56-78", "email": "info@oxford-fergana.uz", "website": "https://oxford-fergana.uz",
        "address": "Al-Farg'oniy ko'chasi 44", "city": "Fergana", "status": ApprovalStatus.approved,
        "latitude": 40.384200, "longitude": 71.784300, "likes_count": 12
    },
    {
        "name": "Smart Kids Academy",
        "description": "Bolalar uchun matematika, ingliz tili va dasturlash kurslari. 6 yoshdan 16 yoshgacha.",
        "phone": "+998 69 234-56-78", "email": "info@smartkids.uz", "website": None,
        "address": "Mustaqillik ko'chasi 22", "city": "Namangan", "status": ApprovalStatus.approved,
        "latitude": 40.998300, "longitude": 71.672600, "likes_count": 9
    },
    {
        "name": "Star IELTS Center",
        "description": "IELTS va TOEFL tayyorlov kurslari. Band 7+ kafolatlangan natijalar.",
        "phone": "+998 71 567-89-01", "email": "info@starielts.uz", "website": None,
        "address": "Shayxontohur tumani, Navruz ko'chasi 5", "city": "Tashkent", "status": ApprovalStatus.approved,
        "latitude": 41.326500, "longitude": 69.241100, "likes_count": 42
    }
]

created_centers = []
for c_data in centers_data:
    c = LearningCenter(**c_data)
    db.add(c)
    created_centers.append(c)

db.commit()
for c in created_centers:
    db.refresh(c)

print(f"✅ Created {len(created_centers)} Learning Centers.")

# 4. Seed Courses with categories & pricing
courses_data = [
    # Bright Future
    {"center_id": created_centers[0].id, "name": "General English (Beginner-Advanced)", "category": "english", "teacher_name": "Mr. Jasur", "price": 450000, "duration_weeks": 12, "schedule": "Mon/Wed/Fri 09:00-11:00", "max_students": 15, "status": CourseStatus.active},
    {"center_id": created_centers[0].id, "name": "IELTS Intensive Prep (Band 7+)", "category": "ielts", "teacher_name": "Ms. Laylo", "price": 750000, "duration_weeks": 8, "schedule": "Tue/Thu/Sat 14:00-16:00", "max_students": 12, "status": CourseStatus.active},
    
    # MathPro
    {"center_id": created_centers[1].id, "name": "SAT Math Preparation", "category": "sat", "teacher_name": "Dr. Rustam", "price": 850000, "duration_weeks": 10, "schedule": "Mon/Wed/Fri 16:00-18:00", "max_students": 10, "status": CourseStatus.active},
    {"center_id": created_centers[1].id, "name": "School Mathematics (Grades 5-11)", "category": "math", "teacher_name": "Mr. Bekzod", "price": 400000, "duration_weeks": 16, "schedule": "Tue/Thu/Sat 10:00-12:00", "max_students": 15, "status": CourseStatus.active},

    # CodeCraft
    {"center_id": created_centers[2].id, "name": "Python for Beginners & Automation", "category": "programming", "teacher_name": "Sardor Developer", "price": 900000, "duration_weeks": 12, "schedule": "Mon/Wed/Fri 18:30-20:30", "max_students": 20, "status": CourseStatus.active},
    {"center_id": created_centers[2].id, "name": "Full-Stack Web Development (React & FastAPI)", "category": "programming", "teacher_name": "Timur Lead", "price": 1200000, "duration_weeks": 24, "schedule": "Tue/Thu/Sat 18:30-20:30", "max_students": 15, "status": CourseStatus.active},

    # Oxford English School
    {"center_id": created_centers[3].id, "name": "Spoken English Conversation", "category": "english", "teacher_name": "Mr. David", "price": 500000, "duration_weeks": 8, "schedule": "Mon/Wed/Fri 15:00-17:00", "max_students": 14, "status": CourseStatus.active},

    # Smart Kids
    {"center_id": created_centers[4].id, "name": "Kids Math & Logic (Ages 6-10)", "category": "kids", "teacher_name": "Ms. Gulnora", "price": 350000, "duration_weeks": 12, "schedule": "Sat/Sun 11:00-13:00", "max_students": 10, "status": CourseStatus.active},

    # Star IELTS
    {"center_id": created_centers[5].id, "name": "IELTS Academic Masterclass", "category": "ielts", "teacher_name": "Mr. Alex (Band 8.5)", "price": 950000, "duration_weeks": 8, "schedule": "Mon/Wed/Fri 14:00-16:00", "max_students": 12, "status": CourseStatus.active},
]

for co_data in courses_data:
    db.add(Course(**co_data))

db.commit()
print(f"✅ Created {len(courses_data)} Courses across categories.")

# 5. Seed Reviews
reviews_data = [
    {"center_id": created_centers[0].id, "student_name": "Sardor Aliyev", "rating": 5, "comment": "Juda zo'r markaz! O'qituvchilar professional va samimiy.", "status": ApprovalStatus.approved},
    {"center_id": created_centers[0].id, "student_name": "Malika Yusupova", "rating": 5, "comment": "IELTS da 7.5 oldim. Rahmat Bright Future!", "status": ApprovalStatus.approved},
    {"center_id": created_centers[2].id, "student_name": "Jasur Toshmatov", "rating": 5, "comment": "CodeCraft IT kurslari juda amaliy va sifatli!", "status": ApprovalStatus.approved},
    {"center_id": created_centers[1].id, "student_name": "Dilnoza Karimova", "rating": 5, "comment": "Farzandim SAT matematikasidan baland ball oldi.", "status": ApprovalStatus.approved},
]

for r_data in reviews_data:
    db.add(Review(**r_data))

db.commit()
print(f"✅ Created {len(reviews_data)} Approved Reviews.")

db.close()
print()
print("🎉 Database seeded cleanly with SQLAlchemy models!")