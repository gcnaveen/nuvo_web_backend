import jwt
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist
import json

from apps.users.models import User
from apps.accounts.models import OTP
from apps.common.constants import UserRole
from apps.common.email_utils import send_otp_email

from apps.accounts.jwt_utils import generate_access_token, generate_refresh_token
from apps.common.validators import validate_required_fields, validate_email, validate_phone
from apps.accounts.decorators import require_auth, require_role

def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


@csrf_exempt
def send_otp(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)

        email = body.get("email")
        phone = body.get("phone_number")
        role = body.get("role")

        # ---- Required Field Validation ----
        if not email or not phone or not role:
            return api_response(
                False,
                "Email, phone_number and role are required",
                status=400
            )

        # ---- Email Validation ----
        from apps.common.validators import validate_email
        if not validate_email(email):
            return api_response(False, "Invalid email format", status=400)

        # ---- Phone Validation ----
        from apps.common.validators import validate_phone
        if not validate_phone(phone):
            return api_response(False, "Invalid phone number", status=400)

        # ---- Role Validation ----
        if role not in [r.value for r in UserRole]:
            return api_response(False, "Invalid role", status=400)

        # ---- Delete Old OTP if Exists ----
        OTP.objects(email=email).delete()

        # ---- Generate OTP ----
        otp_code = OTP.generate_otp()
        # otp_code = "123456"  # For testing purposes, replace with above line in production

        otp = OTP(
            email=email,
            otp_code=otp_code,
            expires_at=OTP.expiry_time()
        )
        otp.save()

        # ---- Send Email ----
        send_otp_email(email, otp_code)

        return api_response(True, "OTP sent successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
def verify_otp(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)
        email = body.get("email")
        phone = body.get("phone_number")
        role = body.get("role")
        otp_input = body.get("otp")

        if not email or not phone or not role or not otp_input:
            return api_response(False, "All fields are required", status=400)

        otp_obj = OTP.objects.get(email=email)

        if otp_obj.is_verified:
            return api_response(False, "OTP already used", status=400)

        if datetime.utcnow() > otp_obj.expires_at:
            return api_response(False, "OTP expired", status=400)

        if otp_obj.otp_code != otp_input:
            otp_obj.attempt_count += 1
            otp_obj.save()

            if otp_obj.attempt_count >= 5:
                otp_obj.delete()
                return api_response(False, "Too many attempts. OTP deleted.", status=400)

            return api_response(False, "Invalid OTP", status=400)

        otp_obj.is_verified = True
        otp_obj.save()

        # Create user if not exists
        try:
            user = User.objects.get(email=email)
        except DoesNotExist:
            user = User(
                email=email,
                phone_number=phone,
                role=role,
            )
            user.save()

        # Generate JWT
        payload = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "exp": datetime.utcnow().timestamp() + 3600
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user)

        return api_response(True, "Login successful", {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": build_user_response(user)
        })

    except DoesNotExist:
        return api_response(False, "OTP not found. Please request again.", status=400)

    except Exception as e:
        return api_response(False, str(e), status=500)
    

@csrf_exempt
def refresh_token(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)
        token = body.get("refresh_token")

        if not token:
            return api_response(False, "Refresh token required", status=400)

        # Import here to avoid circular imports
        from apps.accounts.jwt_utils import decode_token, generate_access_token
        from apps.accounts.models import BlacklistedToken
        from apps.users.models import User
        import jwt

        # ✅ Check if token is blacklisted
        if BlacklistedToken.objects(token=token).first():
            return api_response(False, "Token is blacklisted", status=401)

        # ✅ Decode token
        payload = decode_token(token)

        # ✅ Ensure it is refresh token
        if payload.get("type") != "refresh":
            return api_response(False, "Invalid token type", status=401)

        user_id = payload.get("user_id")

        if not user_id:
            return api_response(False, "Invalid token payload", status=401)

        # ✅ Get user
        user = User.objects.get(id=user_id)

        # ✅ Blocked user protection
        if user.status == "BLOCKED":
            return api_response(False, "User is blocked", status=403)

        # ✅ Generate new access token
        new_access_token = generate_access_token(user)

        return api_response(True, "Token refreshed successfully", {
            "access_token": new_access_token
        })

    except jwt.ExpiredSignatureError:
        return api_response(False, "Refresh token expired", status=401)

    except jwt.InvalidTokenError:
        return api_response(False, "Invalid refresh token", status=401)

    except User.DoesNotExist:
        return api_response(False, "User not found", status=404)

    except Exception as e:
        return api_response(False, str(e), status=500)
    

@csrf_exempt
def resend_otp(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)
        email = body.get("email")

        if not email:
            return api_response(False, "Email is required", status=400)

        otp_obj = OTP.objects(email=email).first()

        if not otp_obj:
            return api_response(False, "No OTP request found", status=400)

        # Cooldown check (60 seconds)
        time_difference = (datetime.utcnow() - otp_obj.created_at).total_seconds()
        if time_difference < 60:
            return api_response(
                False,
                "Please wait before requesting a new OTP",
                status=400
            )

        # Delete old OTP
        OTP.objects(email=email).delete()

        # new_otp = OTP.generate_otp()
        new_otp = "123456"  # For testing purposes, replace with above line in production


        otp = OTP(
            email=email,
            otp_code=new_otp,
            expires_at=OTP.expiry_time()
        )
        otp.save()

        # send_otp_email(email, new_otp)

        return api_response(True, "OTP resent successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)
    

@csrf_exempt
@require_auth
def logout(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)
        refresh_token = body.get("refresh_token")

        if not refresh_token:
            return api_response(False, "Refresh token required", status=400)

        from apps.accounts.models import BlacklistedToken

        BlacklistedToken(token=refresh_token).save()

        return api_response(True, "Logged out successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)
    

@csrf_exempt
@require_auth
def me(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import (
        ClientProfile,
        StaffProfile,
        MakeupArtistProfile
    )

    user = request.user
    profile_completed = False

    if user.role == "CLIENT":
        profile_completed = ClientProfile.objects(user=user).first() is not None

    elif user.role == "STAFF":
        profile_completed = StaffProfile.objects(user=user).first() is not None

    elif user.role == "MAKEUP_ARTIST":
        profile_completed = MakeupArtistProfile.objects(user=user).first() is not None

    return api_response(True, "User fetched", {
        "id": user.id,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "status": user.status,
        "profile_completed": profile_completed
    })


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def change_user_status(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)
        user_id = body.get("user_id")
        new_status = body.get("status")

        if not user_id or not new_status:
            return api_response(False, "user_id and status required", status=400)

        if new_status not in ["ACTIVE", "INACTIVE", "BLOCKED"]:
            return api_response(False, "Invalid status value", status=400)

        user = User.objects.get(id=user_id)
        user.status = new_status
        user.save()

        return api_response(True, "User status updated")

    except Exception as e:
        return api_response(False, str(e), status=500)
    

def build_user_response(user):
    from apps.users.models import (
        ClientProfile,
        StaffProfile,
        MakeupArtistProfile
    )

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
        "role": user.role,
        "status": user.status,
        "profile_completed": profile_completed
    }