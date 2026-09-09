import secrets
import hashlib
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models.center import PartnerSignupRequest, Partner, PartnerRequestStatus

router = APIRouter(prefix="/api", tags=["Partner"])

PLAN_PRICES = {"1month": 49,  "3months": 129, "6months": 239, "1year": 449}
PLAN_DAYS   = {"1month": 30,  "3months": 90,  "6months": 180, "1year": 365}
PLAN_LABELS = {"1month": "1 Month", "3months": "3 Months", "6months": "6 Months", "1year": "1 Year"}
VALID_PLANS = set(PLAN_PRICES.keys())

BACKEND_URL   = os.getenv("BACKEND_URL",   "http://localhost:8000")
SMTP_EMAIL    = os.getenv("SMTP_EMAIL",    "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def make_password(contact_person: str, email: str) -> str:
    first = contact_person.strip().split()[0].capitalize()
    suffix = str(abs(hash(email)) % 9000 + 1000)
    return f"{first}#{suffix}"


def hash_pw(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def send_email(to: str, subject: str, html: str) -> bool:
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print(f"⚠️  SMTP not configured — add SMTP_EMAIL and SMTP_PASSWORD to .env")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"EduFind <{SMTP_EMAIL}>"
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        # Try STARTTLS on port 587 (works with Gmail App Passwords)
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(SMTP_EMAIL, SMTP_PASSWORD)
                s.sendmail(SMTP_EMAIL, to, msg.as_string())
        except Exception:
            # Fallback: SSL on port 465
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
                s.login(SMTP_EMAIL, SMTP_PASSWORD)
                s.sendmail(SMTP_EMAIL, to, msg.as_string())
        print(f"✅ Email sent → {to}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail auth failed — make sure you are using an App Password, not your regular Gmail password")
        print("   Guide: myaccount.google.com → Security → 2-Step Verification → App passwords")
        return False
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def tpl_confirmation(req) -> str:
    url = f"{BACKEND_URL}/api/partner-approve/{req.approve_token}"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px"><tr><td align="center">
<table width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1)">
<tr><td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 40px;text-align:center">
  <div style="font-size:26px;font-weight:900;color:#fff;letter-spacing:3px">EDUFIND</div>
  <div style="color:rgba(255,255,255,.8);font-size:14px;margin-top:6px">New Partner Application</div>
</td></tr>
<tr><td style="padding:36px 40px">
  <h2 style="margin:0 0 8px;font-size:20px;color:#1e293b">New application received 📬</h2>
  <p style="color:#64748b;margin:0 0 24px;font-size:14px">Review the details and click Approve to create their account and send credentials automatically.</p>
  <table width="100%" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;margin-bottom:28px">
    <tr style="background:#f8fafc"><td style="padding:12px 18px;color:#64748b;font-size:13px;font-weight:700;width:38%;border-bottom:1px solid #e2e8f0">Center Name</td><td style="padding:12px 18px;font-size:14px;font-weight:700;color:#1e293b;border-bottom:1px solid #e2e8f0">{req.business_name}</td></tr>
    <tr><td style="padding:12px 18px;color:#64748b;font-size:13px;font-weight:700;border-bottom:1px solid #e2e8f0">Contact</td><td style="padding:12px 18px;font-size:14px;color:#1e293b;border-bottom:1px solid #e2e8f0">{req.contact_person}</td></tr>
    <tr style="background:#f8fafc"><td style="padding:12px 18px;color:#64748b;font-size:13px;font-weight:700;border-bottom:1px solid #e2e8f0">Email</td><td style="padding:12px 18px;font-size:14px;color:#1e293b;border-bottom:1px solid #e2e8f0">{req.email}</td></tr>
    <tr><td style="padding:12px 18px;color:#64748b;font-size:13px;font-weight:700;border-bottom:1px solid #e2e8f0">Phone</td><td style="padding:12px 18px;font-size:14px;color:#1e293b;border-bottom:1px solid #e2e8f0">{req.phone}</td></tr>
    <tr style="background:#f8fafc"><td style="padding:12px 18px;color:#64748b;font-size:13px;font-weight:700">Plan</td><td style="padding:12px 18px;font-size:14px;font-weight:700;color:#4f46e5">{PLAN_LABELS.get(req.plan, req.plan)} — ${int(req.amount)}</td></tr>
  </table>
  <div style="text-align:center;margin-bottom:20px">
    <a href="{url}" style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;text-decoration:none;padding:16px 48px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 16px rgba(79,70,229,.4)">
      ✅ Approve &amp; Send Credentials
    </a>
  </div>
  <p style="text-align:center;color:#94a3b8;font-size:12px;margin:0">One click → account created + credentials sent to <strong>{req.email}</strong></p>
</td></tr>
<tr><td style="background:#f8fafc;padding:20px 40px;text-align:center;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0">EduFind Admin · Do not share this link</td></tr>
</table></td></tr></table>
</body></html>"""


def tpl_credentials(partner, pwd: str) -> str:
    ps = partner.plan if isinstance(partner.plan, str) else partner.plan.value
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px"><tr><td align="center">
<table width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1)">
<tr><td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 40px;text-align:center">
  <div style="font-size:26px;font-weight:900;color:#fff;letter-spacing:3px">EDUFIND</div>
  <div style="color:rgba(255,255,255,.8);font-size:15px;margin-top:6px">Welcome to the Partner Program 🎉</div>
</td></tr>
<tr><td style="padding:36px 40px">
  <h2 style="margin:0 0 8px;font-size:20px;color:#1e293b">Hi {partner.contact_person.strip().split()[0]}! Your account is ready.</h2>
  <p style="color:#64748b;margin:0 0 28px;font-size:14px;line-height:1.8"><strong>{partner.business_name}</strong> has been approved on EduFind. Use the credentials below to log in.</p>
  <table width="100%" style="background:linear-gradient(135deg,rgba(79,70,229,.07),rgba(124,58,237,.07));border:2px dashed #6366f1;border-radius:14px;margin-bottom:28px">
    <tr><td style="padding:24px 28px">
      <div style="font-weight:800;font-size:11px;color:#4f46e5;margin-bottom:16px;letter-spacing:.1em;text-transform:uppercase">🔑 Your Login Credentials</div>
      <table width="100%">
        <tr><td style="padding:8px 0;color:#64748b;font-size:13px;font-weight:700;width:28%">Email</td><td style="padding:8px 0;font-family:monospace;font-size:14px;font-weight:700;color:#1e293b">{partner.email}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-size:13px;font-weight:700">Password</td><td style="padding:8px 0;font-family:monospace;font-size:22px;font-weight:900;color:#4f46e5;letter-spacing:.05em">{pwd}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b;font-size:13px;font-weight:700">Plan</td><td style="padding:8px 0;color:#10b981;font-size:14px;font-weight:700">{PLAN_LABELS.get(ps, ps)} ✓</td></tr>
      </table>
    </td></tr>
  </table>
  <div style="text-align:center;margin-bottom:28px">
    <a href="http://localhost/partner-portal.html" style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;text-decoration:none;padding:14px 44px;border-radius:12px;font-weight:700;font-size:15px;box-shadow:0 4px 14px rgba(79,70,229,.4)">→ Open Partner Dashboard</a>
  </div>
  <table width="100%" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px"><tr><td style="padding:18px 22px">
    <div style="font-weight:700;color:#15803d;margin-bottom:8px;font-size:13px">📌 Quick Start</div>
    <ul style="margin:0;padding-left:18px;color:#166534;font-size:13px;line-height:2.1">
      <li>Log in with the credentials above</li>
      <li>Add your center's photo and description</li>
      <li>Create your first course listing</li>
      <li>Students will start finding you on EduFind!</li>
    </ul>
  </td></tr></table>
</td></tr>
<tr><td style="background:#f8fafc;padding:20px 40px;text-align:center;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0">EduFind Partner Program</td></tr>
</table></td></tr></table>
</body></html>"""


def _page(title: str, body_html: str, accent: str) -> str:
    return f"""<!DOCTYPE html><html>
<head><meta charset="UTF-8"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;700;800&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'DM Sans',sans-serif;background:#07070c;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}.box{{background:#13131f;border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:52px 60px;text-align:center;max-width:560px;box-shadow:0 20px 60px rgba(0,0,0,.6)}}.lbl{{font-size:12px;font-weight:900;letter-spacing:.2em;color:{accent};margin-bottom:28px;opacity:.8}}h1{{color:#fff;font-size:1.75rem;font-weight:800;margin-bottom:18px}}p{{color:rgba(255,255,255,.65);font-size:1rem;line-height:1.9}}code{{color:{accent};background:rgba(255,255,255,.08);padding:3px 10px;border-radius:6px;font-size:17px;font-weight:900}}strong{{color:rgba(255,255,255,.9)}}.btn{{display:inline-block;margin-top:32px;padding:12px 28px;background:{accent}22;border:1px solid {accent}55;color:{accent};border-radius:10px;text-decoration:none;font-weight:700;font-size:14px}}</style>
</head><body>
  <div class="box">
    <div class="lbl">EDUFIND ADMIN</div>
    <h1>{title}</h1>
    <p>{body_html}</p>
    <a class="btn" href="javascript:window.close()">Close Window</a>
  </div>
</body></html>"""


# ── SCHEMAS ─────────────────────────────────────────

class SignupBody(BaseModel):
    business_type:  str
    business_name:  str
    contact_person: str
    email:          str
    phone:          str
    address:        Optional[str] = None
    description:    Optional[str] = None
    plan:           str
    amount:         float


# ── ROUTES ──────────────────────────────────────────

@router.post("/partner-signup", status_code=201)
def partner_signup(body: SignupBody, db: Session = Depends(get_db)):
    if body.plan not in VALID_PLANS:
        raise HTTPException(400, f"Invalid plan: {body.plan}")

    email = body.email.lower().strip()

    if db.query(PartnerSignupRequest).filter(
        PartnerSignupRequest.email  == email,
        PartnerSignupRequest.status == PartnerRequestStatus.pending,
    ).first():
        raise HTTPException(409, "A pending application already exists for this email.")

    if db.query(Partner).filter(Partner.email == email).first():
        raise HTTPException(409, "This email is already a registered partner.")

    token = secrets.token_urlsafe(32)

    req = PartnerSignupRequest(
        business_type  = body.business_type,
        business_name  = body.business_name,
        contact_person = body.contact_person,
        email          = email,
        phone          = body.phone,
        address        = body.address,
        description    = body.description,
        plan           = body.plan,
        amount         = body.amount,
        status         = PartnerRequestStatus.pending,
        approve_token  = token,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # Email sent to YOU (admin) with the approve button
    send_email(
        to        = SMTP_EMAIL,
        subject   = f"[EduFind] New Application: {body.business_name}",
        html = tpl_confirmation(req),
    )

    return {"message": "Application submitted! We'll be in touch within 24 hours.", "request_id": req.id}


@router.get("/partner-approve/{token}", response_class=HTMLResponse)
def approve_via_link(token: str, db: Session = Depends(get_db)):
    req = db.query(PartnerSignupRequest).filter(
        PartnerSignupRequest.approve_token == token
    ).first()

    if not req:
        return _page("❌ Invalid Link", "This approval link is invalid or has already been used.", "#ef4444")
    if req.status != PartnerRequestStatus.pending:
        return _page("⚠️ Already Processed", f"This application was already <strong>{req.status}</strong>.", "#f59e0b")

    pwd      = make_password(req.contact_person, req.email)
    plan_str = req.plan if isinstance(req.plan, str) else req.plan.value
    expires  = datetime.utcnow() + timedelta(days=PLAN_DAYS.get(plan_str, 30))

    partner = Partner(
        business_name   = req.business_name,
        contact_person  = req.contact_person,
        email           = req.email,
        phone           = req.phone,
        address         = req.address,
        description     = req.description,
        business_type   = req.business_type,
        plan            = req.plan,
        amount_paid     = req.amount,
        password_hash   = hash_pw(pwd),
        plan_expires_at = expires,
    )
    db.add(partner)
    db.flush()

    req.status        = PartnerRequestStatus.approved
    req.reviewed_at   = datetime.utcnow()
    req.partner_id    = partner.id
    req.approve_token = None   # one-time use
    db.commit()

    sent = send_email(
        to        = req.email,
        subject   = "🎉 Welcome to EduFind — Your Login Details",
        html = tpl_credentials(partner, pwd),
    )

    note = f"Credentials emailed to <strong>{req.email}</strong> ✓" if sent \
           else f"⚠️ SMTP not configured. Save this password: <code>{pwd}</code>"

    return _page(
        "✅ Partner Approved!",
        f"<strong>{req.business_name}</strong> is now active.<br><br>"
        f"<strong>Login:</strong> {req.email}<br>"
        f"<strong>Password:</strong> <code>{pwd}</code><br><br>{note}",
        "#10b981",
    )


@router.get("/admin/partner-requests")
def list_requests(status: Optional[str] = "pending", admin_token: str = "", db: Session = Depends(get_db)):
    if admin_token != os.getenv("ADMIN_TOKEN", "edufind-admin-2026"):
        raise HTTPException(403, "Invalid admin token")
    q = db.query(PartnerSignupRequest)
    if status and status != "all":
        try:
            q = q.filter(PartnerSignupRequest.status == PartnerRequestStatus(status))
        except ValueError:
            pass
    rows = q.order_by(PartnerSignupRequest.created_at.desc()).all()
    return [{"id":r.id,"business_name":r.business_name,"contact_person":r.contact_person,
             "email":r.email,"phone":r.phone,"plan":r.plan,"amount":r.amount,
             "status":r.status,"created_at":r.created_at} for r in rows]


class PartnerLoginBody(BaseModel):
    email:    str
    password: str


@router.post("/partner/login")
def partner_login(body: PartnerLoginBody, db: Session = Depends(get_db)):
    p = db.query(Partner).filter(Partner.email == body.email.lower().strip()).first()
    if not p or p.password_hash != hash_pw(body.password):
        raise HTTPException(401, "Invalid email or password")
    if not p.is_active:
        raise HTTPException(403, "Account suspended")
    return {"partner_id":p.id,"business_name":p.business_name,
            "email":p.email,"plan":p.plan.value if hasattr(p.plan, "value") else p.plan,"expires_at":p.plan_expires_at}