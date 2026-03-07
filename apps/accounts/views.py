# apps/accounts/views.py
import jwt
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist
import json

from apps.users.models import User
from apps.accounts.models import OTP
from apps.common.constants import UserRole, UserStatus
from apps.common.email_utils import send_otp_email

from apps.accounts.jwt_utils import generate_access_token, generate_refresh_token
from apps.accounts.decorators import require_auth, require_role


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


def build_user_response(user):
    """Shared serializer used by verify_otp, me, and register endpoints."""
    from apps.users.models import ClientProfile, StaffProfile, MakeupArtistProfile

    profile_completed = False

    if user.role == "CLIENT":
        profile_completed = ClientProfile.objects(user=user).first() is not None
    elif user.role == "STAFF":
        profile_completed = StaffProfile.objects(user=user).first() is not None
    elif user.role == "MAKEUP_ARTIST":
        profile_completed = MakeupArtistProfile.objects(user=user).first() is not None

    return {
        "id": str(user.id),
        "email": user.email,
        "phone_number": user.phone_number,
        "full_name": user.full_name or "",
        "role": user.role,
        "status": user.status,
        "is_approved": user.is_approved,
        "profile_completed": profile_completed,
    }


# Roles that require explicit admin approval before they can log in
APPROVAL_REQUIRED_ROLES = {UserRole.STAFF.value, UserRole.MAKEUP_ARTIST.value, UserRole.ADMIN.value}


# ─────────────────────────────────────────────────────────────
#  OTP — Send
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def send_otp(request):
    """
    POST /auth/send-otp/

    Body:
    {
        "email": "user@gmail.com"
    }

    - No role, no phone needed from client.
    - If account exists: role is read from DB.
    - If no account: treated as new CLIENT registration.
    - Blocked accounts are rejected.
    - Pending accounts: OTP is sent but verify_otp will gate the token.
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body  = json.loads(request.body)
        email = body.get("email", "").strip()

        if not email:
            return api_response(False, "Email is required", status=400)

        from apps.common.validators import validate_email
        if not validate_email(email):
            return api_response(False, "Invalid email format", status=400)

        # ── Check if account exists ────────────────────────────────
        user = User.objects(email=email).first()

        if user:
            # Blocked accounts — stop here, don't send OTP
            if user.status == UserStatus.BLOCKED.value:
                return api_response(False, "Your account has been blocked.", status=403)
            # Pending accounts — OTP sent, verify_otp will handle the gate

        # ── Generate & store OTP ───────────────────────────────────
        OTP.objects(email=email).delete()

        otp_code = OTP.generate_otp()
        # otp_code = "123456"  # ← uncomment for testing

        OTP(
            email      = email,
            otp_code   = otp_code,
            expires_at = OTP.expiry_time(),
        ).save()

        send_otp_email(email, otp_code)

        return api_response(True, "OTP sent successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  OTP — Verify  (Login)
# ─────────────────────────────────────────────────────────────


@csrf_exempt
def verify_otp(request):
    """
    POST /auth/verify-otp/

    Body:
    {
        "email": "user@gmail.com",
        "otp":   "123456"
    }

    - No role or phone needed.
    - Role is determined from the existing account in DB.
    - New accounts (no existing user) are auto-created as CLIENT.
    - STAFF / MAKEUP_ARTIST / ADMIN pending accounts return 403.
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body      = json.loads(request.body)
        email     = body.get("email", "").strip()
        otp_input = body.get("otp", "").strip()

        if not email or not otp_input:
            return api_response(False, "email and otp are required", status=400)

        # ── OTP lookup & verification ──────────────────────────────
        try:
            otp_obj = OTP.objects.get(email=email)
        except DoesNotExist:
            return api_response(False, "OTP not found. Please request a new one.", status=400)

        if otp_obj.is_verified:
            return api_response(False, "OTP already used", status=400)

        if datetime.utcnow() > otp_obj.expires_at:
            return api_response(False, "OTP has expired", status=400)

        if otp_obj.otp_code != otp_input:
            otp_obj.attempt_count += 1
            otp_obj.save()
            if otp_obj.attempt_count >= 5:
                otp_obj.delete()
                return api_response(False, "Too many failed attempts. OTP deleted.", status=400)
            return api_response(False, "Invalid OTP", status=400)

        otp_obj.is_verified = True
        otp_obj.save()

        # ── Resolve or create user ─────────────────────────────────
        user = User.objects(email=email).first()

        if not user:
            # No account → new CLIENT (phone collected at /users/complete/client/)
            user = User(
                email        = email,
                phone_number = "",
                role         = UserRole.CLIENT.value,
                status       = UserStatus.ACTIVE.value,
                is_approved  = True,
            )
            user.save()

        else:
            # Account exists — apply role-specific gates
            if user.status == UserStatus.BLOCKED.value:
                return api_response(False, "Your account has been blocked.", status=403)

            if user.role in (UserRole.STAFF.value, UserRole.MAKEUP_ARTIST.value, UserRole.ADMIN.value):
                # These roles need explicit admin approval
                if not user.is_approved or user.status == UserStatus.PENDING.value:
                    return api_response(
                        False,
                        "Your account is pending admin approval. "
                        "You will be notified once approved.",
                        status=403
                    )

            elif user.role == UserRole.CLIENT.value:
                # Returning client — ensure approved
                if not user.is_approved:
                    user.is_approved = True
                    user.status      = UserStatus.ACTIVE.value
                    user.save()

        # ── Issue tokens ───────────────────────────────────────────
        access_token  = generate_access_token(user)
        refresh_token = generate_refresh_token(user)

        return api_response(True, "Login successful", {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "user":          build_user_response(user),
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Self-Registration — Staff & Makeup Artist
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def register_staff_or_makeup(request):
    """
    POST /auth/register/staff-makeup/

    Allows STAFF and MAKEUP_ARTIST to self-register.
    Account is created with status=PENDING and is_approved=False.
    An admin must approve before they can log in.

    Body:
    {
        "email":        "jane@example.com",
        "phone_number": "9999999999",
        "role":         "STAFF"          // or "MAKEUP_ARTIST"
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body  = json.loads(request.body)
        email = body.get("email", "").strip()
        phone = body.get("phone_number", "").strip()
        role  = body.get("role", "").strip()

        # ── Validate inputs ────────────────────────────────────────
        if not email or not phone or not role:
            return api_response(
                False, "email, phone_number, and role are required", status=400
            )

        from apps.common.validators import validate_email, validate_phone
        if not validate_email(email):
            return api_response(False, "Invalid email format", status=400)
        if not validate_phone(phone):
            return api_response(False, "Invalid phone number", status=400)

        if role not in (UserRole.STAFF.value, UserRole.MAKEUP_ARTIST.value):
            return api_response(
                False,
                "This endpoint is only for STAFF and MAKEUP_ARTIST registration",
                status=400
            )

        # ── Duplicate checks ───────────────────────────────────────
        if User.objects(email=email).first():
            return api_response(False, "An account with this email already exists", status=409)
        if User.objects(phone_number=phone).first():
            return api_response(
                False, "An account with this phone number already exists", status=409
            )

        # ── Create pending account ─────────────────────────────────
        user = User(
            email=email,
            phone_number=phone,
            role=role,
            status=UserStatus.PENDING.value,
            is_approved=False,
        )
        user.save()

        return api_response(
            True,
            "Registration successful. Your account is under review. "
            "You will be able to log in once an admin approves your account.",
            {
                "id":    str(user.id),
                "email": user.email,
                "role":  user.role,
                "status": user.status,
            },
            status=201,
        )

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Self-Registration — Admin  (replace existing register_admin in views.py)
# ─────────────────────────────────────────────────────────────
#
#  Password is now required again because admin_login validates it.
#  Also add `password = StringField(default="")` back to User model
#  in apps/users/models.py if you removed it.

@csrf_exempt
def register_admin(request):
    """
    POST /auth/register/admin/

    Admin self-registration with email + password.
    Account starts as PENDING / is_approved=False.
    Another existing ADMIN must approve before login is possible.

    Body:
    {
        "full_name":    "Super Admin",
        "email":        "admin@example.com",
        "phone_number": "9999999999",
        "password":     "SecurePass123"
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        from django.contrib.auth.hashers import make_password

        body      = json.loads(request.body)
        full_name = body.get("full_name", "").strip()
        email     = body.get("email", "").strip()
        phone     = body.get("phone_number", "").strip()
        password  = body.get("password", "").strip()

        if not all([full_name, email, phone, password]):
            return api_response(
                False,
                "full_name, email, phone_number, and password are all required",
                status=400
            )

        from apps.common.validators import validate_email, validate_phone
        if not validate_email(email):
            return api_response(False, "Invalid email format", status=400)
        if not validate_phone(phone):
            return api_response(False, "Invalid phone number", status=400)
        if len(password) < 8:
            return api_response(False, "Password must be at least 8 characters", status=400)

        if User.objects(email=email).first():
            return api_response(False, "An account with this email already exists", status=409)
        if User.objects(phone_number=phone).first():
            return api_response(False, "An account with this phone number already exists", status=409)

        user = User(
            full_name    = full_name,
            email        = email,
            phone_number = phone,
            password     = make_password(password),
            role         = UserRole.ADMIN.value,
            status       = UserStatus.PENDING.value,
            is_approved  = False,
        )
        user.save()

        return api_response(
            True,
            "Admin registration successful. "
            "Another admin must approve your account before you can log in.",
            {
                "id":        str(user.id),
                "email":     user.email,
                "full_name": user.full_name,
                "role":      user.role,
                "status":    user.status,
            },
            status=201,
        )

    except Exception as e:
        return api_response(False, str(e), status=500)   


# ─────────────────────────────────────────────────────────────
#  Admin Login — Email + Password  (add to apps/accounts/views.py)
# ─────────────────────────────────────────────────────────────
#
#  POST /auth/admin/login/
#
#  Admin-only endpoint. Validates email + password directly
#  and returns JWT tokens. No OTP involved.
#
#  Add this import at the top of views.py if not already there:
#  from django.contrib.auth.hashers import check_password

@csrf_exempt
def admin_login(request):
    """
    POST /auth/admin/login/

    Direct email + password login for admin web panel.
    No OTP step — credentials are validated and tokens issued immediately.

    Body:
    {
        "email":    "admin@example.com",
        "password": "yourpassword"
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        from django.contrib.auth.hashers import check_password as django_check_password

        body     = json.loads(request.body)
        email    = body.get("email", "").strip()
        password = body.get("password", "").strip()

        if not email or not password:
            return api_response(False, "Email and password are required", status=400)

        # ── Find admin account ─────────────────────────────────────
        user = User.objects(email=email, role=UserRole.ADMIN.value).first()

        if not user:
            # Generic message — don't reveal whether email exists
            return api_response(False, "Invalid email or password", status=401)

        # ── Check account status before checking password ──────────
        if user.status == UserStatus.BLOCKED.value:
            return api_response(False, "Your account has been blocked.", status=403)

        if user.status == UserStatus.PENDING.value or not user.is_approved:
            return api_response(
                False,
                "Your account is pending admin approval. "
                "You will be notified once approved.",
                status=403
            )

        # ── Validate password ──────────────────────────────────────
        if not user.password:
            return api_response(
                False,
                "No password set for this account. "
                "Please contact another admin to reset your credentials.",
                status=401
            )

        if not django_check_password(password, user.password):
            return api_response(False, "Invalid email or password", status=401)

        # ── Issue tokens ───────────────────────────────────────────
        access_token  = generate_access_token(user)
        refresh_token = generate_refresh_token(user)

        return api_response(True, "Login successful", {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "user":          build_user_response(user),
        })

    except Exception as e:
        return api_response(False, str(e), status=500)




# ─────────────────────────────────────────────────────────────
#  Admin — Approve User
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def approve_user(request):
    """
    POST /auth/admin/approve-user/

    Approve a PENDING user (staff, makeup artist, or another admin).
    Only an already-approved ADMIN can call this.

    Body:
    {
        "user_id": "uuid-of-pending-user"
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body    = json.loads(request.body)
        user_id = body.get("user_id", "").strip()

        if not user_id:
            return api_response(False, "user_id is required", status=400)

        # The calling admin must themselves be approved
        if not request.user.is_approved:
            return api_response(
                False,
                "Your admin account is not yet approved and cannot approve others.",
                status=403
            )

        target_user = User.objects(id=user_id).first()
        if not target_user:
            return api_response(False, "User not found", status=404)

        if target_user.role == UserRole.CLIENT.value:
            return api_response(
                False, "Clients do not require approval", status=400
            )

        if target_user.is_approved:
            return api_response(False, "User is already approved", status=400)

        target_user.is_approved = True
        target_user.status      = UserStatus.ACTIVE.value
        target_user.save()

        return api_response(True, "User approved successfully", {
            "id":         str(target_user.id),
            "email":      target_user.email,
            "role":       target_user.role,
            "status":     target_user.status,
            "is_approved": target_user.is_approved,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Admin — List Pending Users  (convenience for approval queue)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_pending_users(request):
    """
    GET /auth/admin/pending-users/

    Returns all users with status=PENDING awaiting approval.
    Optionally filter by role: ?role=STAFF
    """
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        role_filter = request.GET.get("role", "").strip()
        qs = User.objects(status=UserStatus.PENDING.value)

        if role_filter:
            if role_filter not in [r.value for r in UserRole]:
                return api_response(False, "Invalid role filter", status=400)
            qs = qs.filter(role=role_filter)

        data = [
            {
                "id":           str(u.id),
                "email":        u.email,
                "phone_number": u.phone_number,
                "full_name":    u.full_name or "",
                "role":         u.role,
                "status":       u.status,
                "created_at":   str(u.created_at),
            }
            for u in qs
        ]

        return api_response(True, "Pending users fetched", {"results": data, "total": len(data)})

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Token — Refresh
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def refresh_token(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body  = json.loads(request.body)
        token = body.get("refresh_token")

        if not token:
            return api_response(False, "Refresh token required", status=400)

        from apps.accounts.jwt_utils import decode_token, generate_access_token
        from apps.accounts.models import BlacklistedToken

        if BlacklistedToken.objects(token=token).first():
            return api_response(False, "Token is blacklisted", status=401)

        payload = decode_token(token)

        if payload.get("type") != "refresh":
            return api_response(False, "Invalid token type", status=401)

        user_id = payload.get("user_id")
        if not user_id:
            return api_response(False, "Invalid token payload", status=401)

        user = User.objects.get(id=user_id)

        if user.status == UserStatus.BLOCKED.value:
            return api_response(False, "User is blocked", status=403)

        # Also guard pending accounts on token refresh
        if user.status == UserStatus.PENDING.value or not user.is_approved:
            return api_response(False, "Account pending approval", status=403)

        return api_response(True, "Token refreshed successfully", {
            "access_token": generate_access_token(user)
        })

    except jwt.ExpiredSignatureError:
        return api_response(False, "Refresh token expired", status=401)
    except jwt.InvalidTokenError:
        return api_response(False, "Invalid refresh token", status=401)
    except DoesNotExist:
        return api_response(False, "User not found", status=404)
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  OTP — Resend
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def resend_otp(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body  = json.loads(request.body)
        email = body.get("email", "").strip()

        if not email:
            return api_response(False, "Email is required", status=400)

        otp_obj = OTP.objects(email=email).first()
        if not otp_obj:
            return api_response(False, "No OTP request found for this email", status=400)

        elapsed = (datetime.utcnow() - otp_obj.created_at).total_seconds()
        if elapsed < 60:
            return api_response(False, "Please wait 60 seconds before requesting a new OTP", status=429)

        OTP.objects(email=email).delete()

        new_otp = OTP.generate_otp()
        # new_otp = "123456"   # ← replace in production

        OTP(email=email, otp_code=new_otp, expires_at=OTP.expiry_time()).save()

        send_otp_email(email, new_otp)

        return api_response(True, "OTP resent successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Logout
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def logout(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body          = json.loads(request.body)
        refresh_token = body.get("refresh_token")

        if not refresh_token:
            return api_response(False, "Refresh token required", status=400)

        from apps.accounts.models import BlacklistedToken
        BlacklistedToken(token=refresh_token).save()

        return api_response(True, "Logged out successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Me
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def me(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    return api_response(True, "User fetched", build_user_response(request.user))


# ─────────────────────────────────────────────────────────────
#  Admin — Change User Status
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def change_user_status(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    try:
        body       = json.loads(request.body)
        user_id    = body.get("user_id")
        new_status = body.get("status")

        if not user_id or not new_status:
            return api_response(False, "user_id and status are required", status=400)

        valid_statuses = [s.value for s in UserStatus]
        if new_status not in valid_statuses:
            return api_response(
                False,
                f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                status=400
            )

        user = User.objects.get(id=user_id)
        user.status = new_status
        user.save()

        return api_response(True, "User status updated")

    except DoesNotExist:
        return api_response(False, "User not found", status=404)
    except Exception as e:
        return api_response(False, str(e), status=500)
