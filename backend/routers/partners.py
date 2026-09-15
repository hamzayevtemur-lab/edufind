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

PLAN_PRICES = {"free_1month": 0, "1month": 49,  "3months": 129, "6months": 239, "1year": 449}
PLAN_DAYS   = {"free_1month": 30, "1month": 30,  "3months": 90,  "6months": 180, "1year": 365}
PLAN_LABELS = {"free_1month": "1 Month FREE (Launch)", "1month": "1 Month", "3months": "3 Months", "6months": "6 Months", "1year": "1 Year"}
VALID_PLANS = set(PLAN_PRICES.keys())

BACKEND_URL   = os.getenv("BACKEND_URL",   "http://localhost:8000")
SMTP_EMAIL    = os.getenv("SMTP_EMAIL",    "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def tpl_email_verification(req) -> str:
    verify_url = f"{BACKEND_URL}/api/verify-email/{req.approve_token}"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px"><tr><td align="center">
<table width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1)">
<tr><td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 40px;text-align:center">
  <div style="font-size:26px;font-weight:900;color:#fff;letter-spacing:3px">EDUMARKAZ</div>
  <div style="color:rgba(255,255,255,.8);font-size:15px;margin-top:6px">Verify Your Partner Account ✉️</div>
</td></tr>
<tr><td style="padding:36px 40px">
  <h2 style="margin:0 0 8px;font-size:20px;color:#1e293b">Hi {req.contact_person.strip().split()[0]}! One click to activate your account</h2>
  <p style="color:#64748b;margin:0 0 24px;font-size:14px;line-height:1.7">
    Thank you for registering <strong>{req.business_name}</strong> on EduMarkaz. To complete your registration and activate your <strong>1-Month Free Partner Plan</strong>, please confirm your email address.
  </p>
  <div style="text-align:center;margin:32px 0">
    <a href="{verify_url}" style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;text-decoration:none;padding:16px 44px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 16px rgba(79,70,229,.4)">
      ✅ Confirm Email &amp; Activate Account
    </a>
  </div>
  <p style="text-align:center;color:#94a3b8;font-size:12px;margin:0">If you did not request this, you can safely ignore this email.</p>
</td></tr>
<tr><td style="background:#f8fafc;padding:20px 40px;text-align:center;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0">EduMarkaz Partner Program</td></tr>
</table></td></tr></table>
</body></html>"""


def make_password(contact_person: str, email: str) -> str:
    first = contact_person.strip().split()[0].capitalize()
    suffix = str(abs(hash(email)) % 9000 + 1000)
    return f"{first}#{suffix}"


def hash_pw(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def send_email(to: str, subject: str, html: str) -> bool:
    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    if not smtp_email or not smtp_password:
        print(f"⚠️  SMTP not configured — add SMTP_EMAIL and SMTP_PASSWORD to .env")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"EduMarkaz <{smtp_email}>"
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        # Try STARTTLS on port 587 (works with Gmail App Passwords)
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(smtp_email, smtp_password)
                s.sendmail(smtp_email, to, msg.as_string())
        except Exception:
            # Fallback: SSL on port 465
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
                s.login(smtp_email, smtp_password)
                s.sendmail(smtp_email, to, msg.as_string())
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
  <div style="font-size:26px;font-weight:900;color:#fff;letter-spacing:3px">EDUMARKAZ</div>
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
<tr><td style="background:#f8fafc;padding:20px 40px;text-align:center;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0">EduMarkaz Admin · Do not share this link</td></tr>
</table></td></tr></table>
</body></html>"""


def tpl_credentials(partner, pwd: str) -> str:
    ps = partner.plan if isinstance(partner.plan, str) else partner.plan.value
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px"><tr><td align="center">
<table width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1)">
<tr><td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 40px;text-align:center">
  <div style="font-size:26px;font-weight:900;color:#fff;letter-spacing:3px">EDUMARKAZ</div>
  <div style="color:rgba(255,255,255,.8);font-size:15px;margin-top:6px">Welcome to the Partner Program 🎉</div>
</td></tr>
<tr><td style="padding:36px 40px">
  <h2 style="margin:0 0 8px;font-size:20px;color:#1e293b">Hi {partner.contact_person.strip().split()[0]}! Your account is ready.</h2>
  <p style="color:#64748b;margin:0 0 28px;font-size:14px;line-height:1.8"><strong>{partner.business_name}</strong> has been approved on EduMarkaz. Use the credentials below to log in.</p>
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
      <li>Students will start finding you on EduMarkaz!</li>
    </ul>
  </td></tr></table>
</td></tr>
<tr><td style="background:#f8fafc;padding:20px 40px;text-align:center;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0">EduMarkaz Partner Program</td></tr>
</table></td></tr></table>
</body></html>"""


def _page(title: str, body_html: str, accent: str) -> str:
    return f"""<!DOCTYPE html><html>
<head><meta charset="UTF-8"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;700;800&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'DM Sans',sans-serif;background:#07070c;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}.box{{background:#13131f;border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:52px 60px;text-align:center;max-width:560px;box-shadow:0 20px 60px rgba(0,0,0,.6)}}.lbl{{font-size:12px;font-weight:900;letter-spacing:.2em;color:{accent};margin-bottom:28px;opacity:.8}}h1{{color:#fff;font-size:1.75rem;font-weight:800;margin-bottom:18px}}p{{color:rgba(255,255,255,.65);font-size:1rem;line-height:1.9}}code{{color:{accent};background:rgba(255,255,255,.08);padding:3px 10px;border-radius:6px;font-size:17px;font-weight:900}}strong{{color:rgba(255,255,255,.9)}}.btn{{display:inline-block;margin-top:32px;padding:12px 28px;background:{accent}22;border:1px solid {accent}55;color:{accent};border-radius:10px;text-decoration:none;font-weight:700;font-size:14px}}</style>
</head><body>
  <div class="box">
    <div class="lbl">EDUMARKAZ ADMIN</div>
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

    # If an existing pending signup request is UNVERIFIED, remove it so user can re-apply cleanly
    existing_req = db.query(PartnerSignupRequest).filter(
        PartnerSignupRequest.email  == email,
        PartnerSignupRequest.status == PartnerRequestStatus.pending,
    ).first()

    if existing_req:
        if getattr(existing_req, "is_email_verified", 0) == 0:
            db.delete(existing_req)
            db.flush()
        else:
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
        is_email_verified = 0,
        approve_token  = token,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # 1. Send Email Verification link to the registrant
    sent = send_email(
        to        = email,
        subject   = "✉️ Verify Your EduMarkaz Partner Email",
        html      = tpl_email_verification(req),
    )

    # 2. Send notification to admin as well
    smtp_admin = os.getenv("SMTP_EMAIL", "").strip()
    if smtp_admin:
        send_email(
            to        = smtp_admin,
            subject   = f"[EduMarkaz] New Application: {body.business_name}",
            html      = tpl_confirmation(req),
        )

    return {
        "message": "Verification link sent! Please check your email inbox to confirm and activate your account.",
        "request_id": req.id,
        "email_sent": sent
    }


@router.get("/verify-email/{token}", response_class=HTMLResponse)
def verify_email_link(token: str, db: Session = Depends(get_db)):
    req = db.query(PartnerSignupRequest).filter(
        PartnerSignupRequest.approve_token == token
    ).first()

    if not req:
        return _page("❌ Invalid Link", "This verification link is invalid or has already been used.", "#ef4444")
    if req.status != PartnerRequestStatus.pending:
        return _page("⚠️ Already Activated", f"This application was already <strong>{req.status}</strong>.", "#f59e0b")

    # 15-minute expiration check
    if req.created_at:
        created = req.created_at.replace(tzinfo=None) if hasattr(req.created_at, "tzinfo") else req.created_at
        if (datetime.utcnow() - created) > timedelta(minutes=15):
            db.delete(req)
            db.commit()
            return _page(
                "⌛ Verification Link Expired",
                "This verification link has expired (links are valid for 15 minutes).<br><br>"
                "Please <a href='/partner-signup.html' style='color:#a5b4fc;font-weight:700'>click here to re-apply</a> and receive a fresh verification link.",
                "#f59e0b"
            )

    # Mark email as verified and keep status pending for Admin approval
    req.is_email_verified = 1
    req.approve_token     = None   # one-time use
    db.commit()

    # Notify admin that registrant verified email and is ready for review
    smtp_admin = os.getenv("SMTP_EMAIL", "").strip()
    if smtp_admin:
        try:
            send_email(
                to=smtp_admin,
                subject=f"✅ Email Verified: {req.business_name} (Ready for Admin Approval)",
                html=f"""
                <div style="font-family:sans-serif;background:#07070c;padding:36px;color:#fff;border-radius:16px">
                  <h2 style="color:#10b981">✅ Applicant Email Verified!</h2>
                  <p style="color:rgba(255,255,255,.8);line-height:1.7">
                    <strong>{req.contact_person}</strong> ({req.email}) has verified their email address for <strong>{req.business_name}</strong>.<br><br>
                    This application is now ready for your review and approval in the Admin Panel.
                  </p>
                  <a href="{BACKEND_URL}/admin.html" style="display:inline-block;background:#4f46e5;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:700;margin-top:12px">Open Admin Panel →</a>
                </div>
                """
            )
        except Exception as e:
            print(f"⚠️ Could not notify admin of email verification: {e}")

    return _page(
        "🎉 Email Verified Successfully!",
        f"Thank you, <strong>{req.contact_person}</strong>! Your email address (<code>{req.email}</code>) has been verified.<br><br>"
        f"Your application for <strong>{req.business_name}</strong> is now in the queue for Admin review.<br>"
        f"Once our team approves your application, your login credentials will be sent directly to your email inbox!",
        "#10b981"
    )


@router.get("/admin/approve-extension/{partner_id}", response_class=HTMLResponse)
def approve_extension_via_link(partner_id: int, admin_token: str = "", db: Session = Depends(get_db)):
    if admin_token != os.getenv("ADMIN_TOKEN", "edumarkaz-admin-2026") and admin_token != "edufind-admin-2026":
        return _page("❌ Unauthorized", "Invalid or missing admin token.", "#ef4444")
    p = db.query(Partner).filter(Partner.id == partner_id).first()
    if not p:
        return _page("❌ Partner Not Found", f"No partner found with ID #{partner_id}.", "#ef4444")

    now = datetime.utcnow()
    current_exp = p.plan_expires_at or now
    base_date = max(now, current_exp)
    p.plan_expires_at = base_date + timedelta(days=30)
    p.extension_requested = 0
    db.commit()

    try:
        send_email(
            to=p.email,
            subject="🎉 Your EduMarkaz 1-Month Free Plan Extension is Approved!",
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
    except Exception:
        pass

    return _page(
        "✅ Extension Approved!",
        f"<strong>{p.business_name}</strong>'s plan has been extended by +30 days.<br><br>"
        f"<strong>New Expiration:</strong> {p.plan_expires_at.strftime('%Y-%m-%d')}",
        "#10b981",
    )


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