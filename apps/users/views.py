# apps/users/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.accounts.decorators import require_auth, require_role
import json
from apps.users.models import User, ClientProfile, StaffProfile, MakeupArtistProfile

import boto3
import uuid
import os
from django.conf import settings


def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


# ─────────────────────────────────────────────
#  PROFILE (Auth User)
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
def get_profile(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    user = request.user
    return api_response(True, "Profile fetched", {
        "id": user.id,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "full_name": user.full_name,
        "city": user.city,
        "state": user.state,
        "country": user.country,
        "status": user.status
    })


@csrf_exempt
@require_auth
def update_profile(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)
        user = request.user

        user.full_name = body.get("full_name", user.full_name)
        user.city = body.get("city", user.city)
        user.state = body.get("state", user.state)
        user.country = body.get("country", user.country)
        user.save()

        return api_response(True, "Profile updated")

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────
#  COMPLETE PROFILE (Role-based)
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["CLIENT"])
def complete_client_profile(request):
    """
    POST /users/complete/client/

    Body:
    {
        "full_name":         "Riya Sharma",  ← required
        "phone_number":      "9999999999",   ← required
        "city":              "Bangalore",    ← required
        "state":             "Karnataka",    ← required
        "country":           "India",        ← required
        "subscription_plan": "SILVER"        ← optional, default SILVER
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.common.constants import SubscriptionPlan
    from apps.common.validators import validate_phone

    try:
        body    = json.loads(request.body)
        user    = request.user

        full_name = body.get("full_name", "").strip()
        phone     = body.get("phone_number", "").strip()
        city      = body.get("city", "").strip()
        state     = body.get("state", "").strip()
        country   = body.get("country", "").strip()
        plan      = body.get("subscription_plan", SubscriptionPlan.SILVER.value).strip().upper()

        # ── Validate required fields ───────────────────────────────
        if not full_name:
            return api_response(False, "full_name is required", status=400)
        if not phone:
            return api_response(False, "phone_number is required", status=400)
        if not validate_phone(phone):
            return api_response(False, "Phone number must be 10 digits", status=400)
        if not city:
            return api_response(False, "city is required", status=400)
        if not state:
            return api_response(False, "state is required", status=400)
        if not country:
            return api_response(False, "country is required", status=400)
        if plan not in [p.value for p in SubscriptionPlan]:
            return api_response(False, "Invalid subscription plan", status=400)

        # ── Check phone not already taken by another user ──────────
        existing = User.objects(phone_number=phone).first()
        if existing and str(existing.id) != str(user.id):
            return api_response(
                False, "This phone number is already registered to another account", status=409
            )

        # ── Check profile not already completed ────────────────────
        if ClientProfile.objects(user=user).first():
            return api_response(False, "Profile already completed", status=400)

        # ── Save full_name + phone back to User ────────────────────
        user.full_name    = full_name
        user.phone_number = phone
        user.save()

        # ── Create ClientProfile ───────────────────────────────────
        ClientProfile(
            user              = user,
            full_name         = full_name,
            city              = city,
            state             = state,
            country           = country,
            subscription_plan = plan,
        ).save()

        return api_response(True, "Profile completed successfully", {
            "full_name":         full_name,
            "email":             user.email,
            "phone_number":      phone,
            "city":              city,
            "state":             state,
            "country":           country,
            "subscription_plan": plan,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["STAFF"])
def complete_staff_profile(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import StaffProfile

    try:
        body = json.loads(request.body)

        required_fields = [
            "full_name", "stage_name", "gender",
            "city", "state", "country",
            "price_of_staff", "experience_in_years"
        ]

        for field in required_fields:
            if not body.get(field):
                return api_response(False, f"{field} is required", status=400)

        if StaffProfile.objects(user=request.user).first():
            return api_response(False, "Profile already completed", status=400)

        StaffProfile(
            user=request.user,
            full_name=body["full_name"],
            stage_name=body["stage_name"],
            gender=body["gender"],
            city=body["city"],
            state=body["state"],
            country=body["country"],
            price_of_staff=float(body["price_of_staff"]),
            experience_in_years=int(body["experience_in_years"])
        ).save()

        return api_response(True, "Staff profile completed")

    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["MAKEUP_ARTIST"])
def complete_makeup_profile(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import MakeupArtistProfile

    try:
        body = json.loads(request.body)

        required_fields = [
            "full_name", "gender", "makeup_speciality",
            "city", "state", "country", "experience_in_years"
        ]

        for field in required_fields:
            if not body.get(field):
                return api_response(False, f"{field} is required", status=400)

        if MakeupArtistProfile.objects(user=request.user).first():
            return api_response(False, "Profile already completed", status=400)

        MakeupArtistProfile(
            user=request.user,
            full_name=body["full_name"],
            gender=body["gender"],
            makeup_speciality=body["makeup_speciality"],
            city=body["city"],
            state=body["state"],
            country=body["country"],
            experience_in_years=int(body["experience_in_years"])
        ).save()

        return api_response(True, "Makeup artist profile completed")

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────
#  MY PROFILE (GET / UPDATE)
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
def get_my_profile(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import ClientProfile, StaffProfile, MakeupArtistProfile

    user = request.user

    if user.role == "CLIENT":
        profile = ClientProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)
        return api_response(True, "Client profile", {
            "full_name": profile.full_name,
            "city": profile.city,
            "state": profile.state,
            "country": profile.country,
            "subscription_plan": profile.subscription_plan,
            "joined_date": profile.joined_date
        })

    elif user.role == "STAFF":
        profile = StaffProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)
        return api_response(True, "Staff profile", {
            "full_name": profile.full_name,
            "stage_name": profile.stage_name,
            "gender": profile.gender,
            "city": profile.city,
            "state": profile.state,
            "country": profile.country,
            "price_of_staff": profile.price_of_staff,
            "experience_in_years": profile.experience_in_years,
            "profile_picture": profile.profile_picture,
            "gallery_images": profile.gallery_images
        })

    elif user.role == "MAKEUP_ARTIST":
        profile = MakeupArtistProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)
        return api_response(True, "Makeup artist profile", {
            "full_name": profile.full_name,
            "gender": profile.gender,
            "makeup_speciality": profile.makeup_speciality,
            "city": profile.city,
            "state": profile.state,
            "country": profile.country,
            "experience_in_years": profile.experience_in_years
        })

    return api_response(False, "Invalid role", status=400)


@csrf_exempt
@require_auth
def update_my_profile(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import ClientProfile, StaffProfile, MakeupArtistProfile

    body = json.loads(request.body)
    user = request.user

    if user.role == "CLIENT":
        profile = ClientProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)
        profile.full_name = body.get("full_name", profile.full_name)
        profile.city      = body.get("city", profile.city)
        profile.state     = body.get("state", profile.state)
        profile.country   = body.get("country", profile.country)
        profile.save()

    elif user.role == "STAFF":
        profile = StaffProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)
        profile.full_name          = body.get("full_name", profile.full_name)
        profile.stage_name         = body.get("stage_name", profile.stage_name)
        profile.price_of_staff     = float(body.get("price_of_staff", profile.price_of_staff))
        profile.experience_in_years = int(body.get("experience_in_years", profile.experience_in_years))
        profile.save()

    elif user.role == "MAKEUP_ARTIST":
        profile = MakeupArtistProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)
        profile.full_name           = body.get("full_name", profile.full_name)
        profile.makeup_speciality   = body.get("makeup_speciality", profile.makeup_speciality)
        profile.experience_in_years = int(body.get("experience_in_years", profile.experience_in_years))
        profile.save()

    return api_response(True, "Profile updated")


# ─────────────────────────────────────────────
#  IMAGE UPLOADS  (S3)
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["STAFF"])
def upload_staff_images(request):
    """Upload profile picture + gallery images to S3."""
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import StaffProfile
    from apps.common.s3_utils import upload_file_to_s3, delete_file_from_s3

    profile = StaffProfile.objects(user=request.user).first()
    if not profile:
        return api_response(False, "Profile not completed", status=404)

    profile_pic_file = request.FILES.get("profile_picture")
    gallery_files    = request.FILES.getlist("gallery_images")

    if not profile_pic_file and not gallery_files:
        return api_response(False, "No files uploaded", status=400)

    try:
        # ── Profile Picture ──────────────────────────────────────────
        if profile_pic_file:
            # Delete old one from S3 if it exists
            if profile.profile_picture:
                delete_file_from_s3(profile.profile_picture)

            profile.profile_picture = upload_file_to_s3(
                profile_pic_file, folder="staff/profile_pictures"
            )

        # ── Gallery Images ───────────────────────────────────────────
        if gallery_files:
            # Delete previous gallery images from S3
            for old_url in (profile.gallery_images or []):
                delete_file_from_s3(old_url)

            profile.gallery_images = [
                upload_file_to_s3(f, folder="staff/gallery") for f in gallery_files
            ]

        profile.save()

        return api_response(True, "Images uploaded successfully", {
            "profile_picture": profile.profile_picture,
            "gallery_images":  profile.gallery_images
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────
#  ADMIN — LIST STAFF  (search + filter + pagination)
# ─────────────────────────────────────────────
#
#  Query params:
#    search        – name or stage_name (case-insensitive contains)
#    city          – exact city match
#    package       – platinum | diamond | gold | silver | bronze
#    status        – assigned | unassigned   (maps to onevent / everything else)
#    start_date    – joined_date >= YYYY-MM-DD
#    end_date      – joined_date <= YYYY-MM-DD
#    page          – page number  (default: 1)
#    page_size     – rows per page (default: 15, max: 100)
#
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_staff(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import StaffProfile
    import mongoengine.queryset.visitor as qv
    from mongoengine.queryset.visitor import Q
    from datetime import datetime

    try:
        # ── Read query params ────────────────────────────────────────
        search     = request.GET.get("search", "").strip()
        city       = request.GET.get("city", "").strip()
        package    = request.GET.get("package", "").strip()
        status     = request.GET.get("status", "").strip()   # assigned | unassigned
        start_date = request.GET.get("start_date", "").strip()
        end_date   = request.GET.get("end_date", "").strip()

        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)

        # ── Build MongoEngine queryset ───────────────────────────────
        qs = StaffProfile.objects()

        # Search: full_name or stage_name
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) | Q(stage_name__icontains=search)
            )

        # City filter
        if city:
            qs = qs.filter(city__iexact=city)

        # Package / membership tier
        if package:
            qs = qs.filter(package__iexact=package)

        # Status: maps "assigned" → onevent, "unassigned" → everything else
        if status == "assigned":
            qs = qs.filter(status="onevent")
        elif status == "unassigned":
            qs = qs.filter(status__ne="onevent")

        # Joined date range
        if start_date:
            try:
                qs = qs.filter(joined_date__gte=datetime.strptime(start_date, "%Y-%m-%d"))
            except ValueError:
                return api_response(False, "start_date must be YYYY-MM-DD", status=400)

        if end_date:
            try:
                qs = qs.filter(joined_date__lte=datetime.strptime(end_date, "%Y-%m-%d"))
            except ValueError:
                return api_response(False, "end_date must be YYYY-MM-DD", status=400)

        # ── Pagination ───────────────────────────────────────────────
        total  = qs.count()
        offset = (page - 1) * page_size
        staff_list = qs.skip(offset).limit(page_size)

        # ── Serialize ────────────────────────────────────────────────
        data = []
        for profile in staff_list:
            user = profile.user          # dereference ReferenceField
            data.append({
                "id":                  str(profile.id),
                "user_id":             str(user.id) if user else None,
                "full_name":           profile.full_name,
                "stage_name":          profile.stage_name,
                "gender":              profile.gender,
                "city":                profile.city,
                "state":               profile.state,
                "country":             profile.country,
                "package":             profile.package,
                "status":              user.status if user else None,   # ← from User
                "price_of_staff":      profile.price_of_staff,
                "experience_in_years": profile.experience_in_years,
                "profile_picture":     profile.profile_picture,
                "joined_date":         str(profile.joined_date) if profile.joined_date else None,
            })

        return api_response(True, "Staff list fetched", {
            "results":    data,
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": -(-total // page_size),   # ceiling division
            }
        })

    except Exception as e:
        return api_response(False, str(e), status=500)




# ─────────────────────────────────────────────
#  ADMIN — LIST CLIENTS  (search + filter + pagination)
# ─────────────────────────────────────────────
#
#  Query params:
#    search        – name or email (case-insensitive contains)
#    city          – exact city match
#    plan_type     – SILVER | GOLD | PLATINUM | DIAMOND | BRONZE
#    status        – active | inactive | blocked
#    start_date    – joined_date >= YYYY-MM-DD
#    end_date      – joined_date <= YYYY-MM-DD
#    page          – page number  (default: 1)
#    page_size     – rows per page (default: 15, max: 100)
#
# ─────────────────────────────────────────────



@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_clients(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import ClientProfile, User
    from mongoengine.queryset.visitor import Q
    from datetime import datetime

    try:
        search     = request.GET.get("search", "").strip()
        city       = request.GET.get("city", "").strip()
        plan_type  = request.GET.get("plan_type", "").strip()
        status     = request.GET.get("status", "").strip()
        start_date = request.GET.get("start_date", "").strip()
        end_date   = request.GET.get("end_date", "").strip()

        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)

        qs = ClientProfile.objects()

        if search:
            matched_user_ids = list(User.objects(email__icontains=search).scalar("id"))
            qs = qs.filter(Q(full_name__icontains=search) | Q(user__in=matched_user_ids))

        if city:
            qs = qs.filter(city__iexact=city)

        if plan_type:
            qs = qs.filter(subscription_plan__iexact=plan_type)

        if status:
            matched_user_ids = list(User.objects(status__iexact=status).scalar("id"))
            qs = qs.filter(user__in=matched_user_ids)

        if start_date:
            try:
                qs = qs.filter(joined_date__gte=datetime.strptime(start_date, "%Y-%m-%d"))
            except ValueError:
                return api_response(False, "start_date must be YYYY-MM-DD", status=400)

        if end_date:
            try:
                qs = qs.filter(joined_date__lte=datetime.strptime(end_date, "%Y-%m-%d"))
            except ValueError:
                return api_response(False, "end_date must be YYYY-MM-DD", status=400)

        total       = qs.count()
        offset      = (page - 1) * page_size
        client_list = qs.skip(offset).limit(page_size)

        data = []
        for profile in client_list:
            # ── Safely dereference User — skip orphaned profiles ──────
            try:
                user = profile.user
                # Force actual dereference by accessing an attribute
                _ = user.id
            except Exception:
                # Orphaned profile — referenced user no longer exists
                continue

            data.append({
                "id":                str(profile.id),
                "user_id":           str(user.id),
                "full_name":         profile.full_name or "",
                "email":             user.email        or "",
                "phone_number":      user.phone_number or "",
                "city":              profile.city      or "",
                "state":             profile.state     or "",
                "country":           profile.country   or "",
                "subscription_plan": profile.subscription_plan or "",
                "status":            user.status       or "",
                "joined_date":       str(profile.joined_date) if profile.joined_date else None,
            })

        return api_response(True, "Clients list fetched", {
            "results": data,
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": max(1, -(-total // page_size)),
            }
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────
#  ADMIN — MISC
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_client_subscription(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import ClientProfile
    from apps.common.constants import SubscriptionPlan

    body     = json.loads(request.body)
    user_id  = body.get("user_id")
    new_plan = body.get("subscription_plan")

    if not user_id or not new_plan:
        return api_response(False, "user_id and subscription_plan required", status=400)

    if new_plan not in [p.value for p in SubscriptionPlan]:
        return api_response(False, "Invalid subscription plan", status=400)

    profile = ClientProfile.objects(user=user_id).first()
    if not profile:
        return api_response(False, "Client profile not found", status=404)

    profile.subscription_plan = new_plan
    profile.save()

    return api_response(True, "Subscription updated")


#  POST /users/admin/clients/create/
#
#  Admin directly creates a client account. No OTP needed.
#  Account is created ACTIVE + approved immediately.
#
#  Body:
#  {
#      "full_name":         "Riya Sharma",
#      "email":             "riya@example.com",
#      "phone_number":      "9999999999",
#      "city":              "Bangalore",      (optional)
#      "state":             "Karnataka",      (optional)
#      "country":           "India",          (optional)
#      "subscription_plan": "SILVER"          (optional, default SILVER)
#  }

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_create_client(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        from django.contrib.auth.hashers import make_password
        from apps.common.constants import UserRole, UserStatus, SubscriptionPlan

        body  = json.loads(request.body)

        full_name = body.get("full_name", "").strip()
        email     = body.get("email", "").strip()
        phone     = body.get("phone_number", "").strip()
        city      = body.get("city", "").strip()
        state     = body.get("state", "").strip()
        country   = body.get("country", "India").strip()
        plan      = body.get("subscription_plan", SubscriptionPlan.SILVER.value).strip().upper()

        # ── Validate required fields ───────────────────────────────
        if not full_name or not email or not phone:
            return api_response(
                False, "full_name, email, and phone_number are required", status=400
            )

        from apps.common.validators import validate_email, validate_phone
        if not validate_email(email):
            return api_response(False, "Invalid email format", status=400)
        if not validate_phone(phone):
            return api_response(False, "Invalid phone number (must be 10 digits)", status=400)

        valid_plans = [p.value for p in SubscriptionPlan]
        if plan not in valid_plans:
            return api_response(
                False,
                f"Invalid subscription_plan. Must be one of: {', '.join(valid_plans)}",
                status=400
            )

        # ── Duplicate checks ───────────────────────────────────────
        if User.objects(email=email).first():
            return api_response(False, "An account with this email already exists", status=409)
        if User.objects(phone_number=phone).first():
            return api_response(False, "An account with this phone number already exists", status=409)

        # ── Create User ────────────────────────────────────────────
        user = User(
            full_name    = full_name,
            email        = email,
            phone_number = phone,
            role         = UserRole.CLIENT.value,
            status       = UserStatus.ACTIVE.value,
            is_approved  = True,
        )
        user.save()

        # ── Create ClientProfile ───────────────────────────────────
        profile = ClientProfile(
            user              = user,
            full_name         = full_name,
            city              = city,
            state             = state,
            country           = country,
            subscription_plan = plan,
        )
        profile.save()

        return api_response(True, "Client created successfully", {
            "id":                str(profile.id),
            "user_id":           str(user.id),
            "full_name":         profile.full_name,
            "email":             user.email,
            "phone_number":      user.phone_number,
            "city":              profile.city or "",
            "state":             profile.state or "",
            "country":           profile.country or "",
            "subscription_plan": profile.subscription_plan,
            "status":            user.status,
            "joined_date":       str(profile.joined_date),
        }, status=201)

    except Exception as e:
        return api_response(False, str(e), status=500)



@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def get_client_detail(request, client_id):
    """
    GET /users/api/clients/<client_id>/

    Returns full detail of a single client by their ClientProfile ID.
    """
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        from apps.users.models import ClientProfile

        profile = ClientProfile.objects(id=client_id).first()
        if not profile:
            return api_response(False, "Client not found", status=404)

        user = profile.user
        if not user:
            return api_response(False, "Associated user account not found", status=404)

        return api_response(True, "Client fetched", {
            "id":                str(profile.id),
            "user_id":           str(user.id),
            "full_name":         profile.full_name or "",
            "email":             user.email,
            "phone_number":      user.phone_number or "",
            "city":              profile.city     or "",
            "state":             profile.state    or "",
            "country":           profile.country  or "",
            "subscription_plan": profile.subscription_plan,
            "status":            user.status,
            "is_approved":       user.is_approved,
            "joined_date":       str(profile.joined_date) if profile.joined_date else None,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────────────────
# ADD THIS TO apps/users/urls.py
# ─────────────────────────────────────────────────────────────────────────
#
#   from django.urls import path
#   from . import views
#
#   urlpatterns = [
#       ...existing urls...
#       path("api/clients/<str:client_id>/", views.get_client_detail),   # ← ADD
#   ]
#
# Make sure this line appears BEFORE any catch-all patterns.




@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def get_staff_detail(request, staff_id):
    """
    GET /users/api/staff/<staff_id>/

    Returns full detail of a single staff member by their StaffProfile ID.
    """
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = StaffProfile.objects(id=staff_id).first()
        if not profile:
            return api_response(False, "Staff member not found", status=404)

        user = profile.user
        if not user:
            return api_response(False, "Associated user account not found", status=404)

        return api_response(True, "Staff fetched", {
            "id":                  str(profile.id),
            "user_id":             str(user.id),
            "full_name":           profile.full_name or "",
            "stage_name":          profile.stage_name or "",
            "gender":              profile.gender or "",
            "city":                profile.city or "",
            "state":               profile.state or "",
            "country":             profile.country or "",
            "package":             profile.package or "",
            "price_of_staff":      profile.price_of_staff,
            "experience_in_years": profile.experience_in_years,
            "profile_picture":     profile.profile_picture or "",
            "gallery_images":      profile.gallery_images or [],
            "status":              user.status,
            "is_approved":         user.is_approved,
            "joined_date":         str(profile.joined_date) if profile.joined_date else None,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)




@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_create_staff(request):
    """
    POST /users/admin/staff/create/

    Admin directly creates a staff member with full details.
    Account is created ACTIVE + approved immediately. No OTP needed.

    Body:
    {
        "full_name":           "Rahul Sharma",   ← required
        "email":               "r@ex.com",       ← required
        "phone_number":        "9999999999",      ← required
        "stage_name":          "DJ Rahul",        ← optional
        "gender":              "Male",            ← required
        "city":                "Bangalore",       ← required
        "state":               "Karnataka",       ← optional
        "country":             "India",           ← optional
        "package":             "SILVER",          ← optional, default SILVER
        "experience_in_years": 3,                 ← optional, default 0
        "price_of_staff":      5000               ← optional, default 0
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        from apps.common.constants import UserRole, UserStatus
        from apps.common.validators import validate_email, validate_phone

        body = json.loads(request.body)

        full_name   = body.get("full_name", "").strip()
        email       = body.get("email", "").strip()
        phone       = body.get("phone_number", "").strip()
        stage_name  = body.get("stage_name", "").strip()
        gender      = body.get("gender", "").strip()
        city        = body.get("city", "").strip()
        state       = body.get("state", "").strip()
        country     = body.get("country", "India").strip()
        package     = body.get("package", "SILVER").strip().upper()
        experience  = int(body.get("experience_in_years", 0) or 0)
        price       = float(body.get("price_of_staff", 0) or 0)

        # ── Validate required fields ───────────────────────────
        if not full_name:
            return api_response(False, "full_name is required", status=400)
        if not email:
            return api_response(False, "email is required", status=400)
        if not validate_email(email):
            return api_response(False, "Invalid email format", status=400)
        if not phone:
            return api_response(False, "phone_number is required", status=400)
        if not validate_phone(phone):
            return api_response(False, "Phone number must be 10 digits", status=400)
        if not gender:
            return api_response(False, "gender is required", status=400)
        if not city:
            return api_response(False, "city is required", status=400)

        valid_packages = ["PLATINUM", "DIAMOND", "GOLD", "SILVER", "BRONZE"]
        if package not in valid_packages:
            return api_response(
                False,
                f"Invalid package. Must be one of: {', '.join(valid_packages)}",
                status=400
            )

        # ── Duplicate checks ───────────────────────────────────
        if User.objects(email=email).first():
            return api_response(False, "An account with this email already exists", status=409)
        if User.objects(phone_number=phone).first():
            return api_response(False, "An account with this phone number already exists", status=409)

        # ── Create User ────────────────────────────────────────
        user = User(
            full_name    = full_name,
            email        = email,
            phone_number = phone,
            role         = UserRole.STAFF.value,
            status       = UserStatus.ACTIVE.value,
            is_approved  = True,
        )
        user.save()

        # ── Create StaffProfile ────────────────────────────────
        profile = StaffProfile(
            user                = user,
            full_name           = full_name,
            stage_name          = stage_name,
            gender              = gender,
            city                = city,
            state               = state,
            country             = country,
            package             = package,
            experience_in_years = experience,
            price_of_staff      = price,
        )
        profile.save()

        return api_response(True, "Staff created successfully", {
            "id":                  str(profile.id),
            "user_id":             str(user.id),
            "full_name":           profile.full_name,
            "stage_name":          profile.stage_name or "",
            "email":               user.email,
            "phone_number":        user.phone_number,
            "gender":              profile.gender,
            "city":                profile.city or "",
            "state":               profile.state or "",
            "country":             profile.country or "",
            "package":             profile.package,
            "experience_in_years": profile.experience_in_years,
            "price_of_staff":      profile.price_of_staff,
            "status":              user.status,
        }, status=201)

    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_delete_staff(request, staff_id):
    """
    DELETE /users/admin/staff/<staff_id>/delete/

    Hard deletes a staff member — removes both StaffProfile and User from DB.
    This is irreversible.
    """
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = StaffProfile.objects(id=staff_id).first()
        if not profile:
            return api_response(False, "Staff member not found", status=404)

        user = profile.user

        # Delete profile first (has reference to user)
        profile.delete()

        # Delete user account
        if user:
            user.delete()

        return api_response(True, "Staff member deleted successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)



# Add to apps/users/views.py

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_delete_client(request, client_id):
    """
    DELETE /users/admin/clients/<client_id>/delete/

    Hard deletes a client — removes both ClientProfile and User from DB.
    This is irreversible.
    """
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = ClientProfile.objects(id=client_id).first()
        if not profile:
            return api_response(False, "Client not found", status=404)

        user = profile.user

        # Delete profile first (has reference to user)
        profile.delete()

        # Delete user account
        if user:
            user.delete()

        return api_response(True, "Client deleted successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)




def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id     = settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY,
        region_name           = settings.AWS_S3_REGION_NAME,
    )


def _s3_delete(url: str):
    """Delete a file from S3 given its full URL. Silently ignores errors."""
    try:
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        # URL looks like: https://<bucket>.s3.<region>.amazonaws.com/<key>
        # OR:              https://s3.<region>.amazonaws.com/<bucket>/<key>
        key = url.split(f"{bucket}/")[-1]
        _s3_client().delete_object(Bucket=bucket, Key=key)
    except Exception:
        pass


def _s3_upload(file_obj, folder: str, filename: str = None) -> str:
    """Upload a file to S3 and return its public URL."""
    ext      = os.path.splitext(file_obj.name)[-1].lower() or ".jpg"
    key      = f"{folder}/{filename or uuid.uuid4()}{ext}"
    bucket   = settings.AWS_STORAGE_BUCKET_NAME
    region   = settings.AWS_S3_REGION_NAME

    _s3_client().upload_fileobj(
        file_obj,
        bucket,
        key,
        ExtraArgs={"ContentType": file_obj.content_type or "image/jpeg"},
    )
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


# ── 1. Admin Upload Staff Images ─────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_upload_staff_images(request, staff_id):
    """
    POST /users/admin/staff/<staff_id>/upload-images/
    Content-Type: multipart/form-data

    Fields (at least one required):
      profile_picture  — file   → replaces existing profile picture in S3
      gallery_images   — file[] → ADDS to existing gallery (does not replace)

    Response:
    {
        "profile_picture": "https://...",   // only present if uploaded
        "gallery_images":  ["https://...", ...]   // full updated gallery list
    }
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)
 
    try:
        profile = StaffProfile.objects(id=staff_id).first()
        if not profile:
            return api_response(False, "Staff member not found", status=404)

        profile_pic_file   = request.FILES.get("profile_picture")
        gallery_files      = request.FILES.getlist("gallery_images")

        if not profile_pic_file and not gallery_files:
            return api_response(False, "At least one of profile_picture or gallery_images is required", status=400)

        result = {}

        # ── Profile picture ───────────────────────────────────────────────
        if profile_pic_file:
            # Delete old picture from S3 if exists
            if profile.profile_picture:
                _s3_delete(profile.profile_picture)

            url = _s3_upload(
                profile_pic_file,
                folder   = f"staff/profile_pictures",
                filename = str(profile.id),
            )
            profile.profile_picture = url
            result["profile_picture"] = url

        # ── Gallery images — APPEND mode ──────────────────────────────────
        if gallery_files:
            new_urls = []
            for f in gallery_files:
                url = _s3_upload(f, folder="staff/gallery")
                new_urls.append(url)

            existing = profile.gallery_images or []
            profile.gallery_images = existing + new_urls
            result["gallery_images"] = profile.gallery_images

        profile.save()

        return api_response(True, "Images uploaded successfully", result)

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 2. Admin Delete Single Gallery Image ─────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_delete_gallery_image(request, staff_id):
    """
    DELETE /users/admin/staff/<staff_id>/delete-gallery/

    Body:
    { "image_url": "https://s3.amazonaws.com/..." }

    Removes the URL from gallery_images list and deletes the file from S3.
    """
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = StaffProfile.objects(id=staff_id).first()
        if not profile:
            return api_response(False, "Staff member not found", status=404)

        body      = json.loads(request.body)
        image_url = body.get("image_url", "").strip()

        if not image_url:
            return api_response(False, "image_url is required", status=400)

        gallery = profile.gallery_images or []
        if image_url not in gallery:
            return api_response(False, "Image not found in gallery", status=404)

        # Remove from list and delete from S3
        gallery.remove(image_url)
        profile.gallery_images = gallery
        profile.save()

        _s3_delete(image_url)

        return api_response(True, "Image deleted successfully", {
            "gallery_images": profile.gallery_images
        })

    except Exception as e:
        return api_response(False, str(e), status=500)




@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_update_staff(request, staff_id):
    """
    PUT /users/admin/staff/<staff_id>/update/

    Admin can update any field on a staff member's profile + account status.

    Body (all optional — only supplied fields are updated):
    {
        "full_name":           "Rahul Sharma",
        "stage_name":          "DJ Rahul",
        "gender":              "Male",
        "city":                "Bangalore",
        "state":               "Karnataka",
        "country":             "India",
        "package":             "GOLD",
        "experience_in_years": 4,
        "price_of_staff":      6000,
        "status":              "ACTIVE"   ← updates User.status
    }
    """
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = StaffProfile.objects(id=staff_id).first()
        if not profile:
            return api_response(False, "Staff member not found", status=404)

        user = profile.user
        if not user:
            return api_response(False, "Associated user not found", status=404)

        body = json.loads(request.body)

        # ── Profile fields ─────────────────────────────────────────
        PROFILE_FIELDS = [
            "full_name", "stage_name", "gender",
            "city", "state", "country", "stage_name",
        ]
        for field in PROFILE_FIELDS:
            if field in body:
                val = body[field].strip() if isinstance(body[field], str) else body[field]
                setattr(profile, field, val)

        if "experience_in_years" in body:
            profile.experience_in_years = int(body["experience_in_years"] or 0)

        if "price_of_staff" in body:
            profile.price_of_staff = float(body["price_of_staff"] or 0)

        if "package" in body:
            pkg = body["package"].strip().upper()
            valid = ["PLATINUM", "DIAMOND", "GOLD", "SILVER", "BRONZE"]
            if pkg not in valid:
                return api_response(False, f"Invalid package. Must be one of: {', '.join(valid)}", status=400)
            profile.package = pkg

        # Sync full_name to User as well
        if "full_name" in body:
            user.full_name = body["full_name"].strip()

        # ── Status (lives on User) ─────────────────────────────────
        if "status" in body:
            new_status = body["status"].strip().upper()
            valid_statuses = ["ACTIVE", "INACTIVE", "BLOCKED"]
            if new_status not in valid_statuses:
                return api_response(False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}", status=400)
            user.status = new_status

        profile.save()
        user.save()

        return api_response(True, "Staff updated successfully", {
            "id":                  str(profile.id),
            "user_id":             str(user.id),
            "full_name":           profile.full_name,
            "stage_name":          profile.stage_name or "",
            "gender":              profile.gender or "",
            "city":                profile.city or "",
            "state":               profile.state or "",
            "country":             profile.country or "",
            "package":             profile.package or "",
            "experience_in_years": profile.experience_in_years,
            "price_of_staff":      profile.price_of_staff,
            "status":              user.status,
            "profile_picture":     profile.profile_picture or "",
            "gallery_images":      profile.gallery_images or [],
            "joined_date":         str(profile.joined_date) if profile.joined_date else None,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)




# ─────────────────────────────────────────────────────────────────────────────
# Add ALL of these views to apps/users/views.py
#
# ADD TO apps/users/urls.py:
#   path("api/makeup-artists/",                              views.list_makeup_artists),
#   path("api/makeup-artists/<str:mua_id>/",                 views.get_mua_detail),
#   path("admin/makeup-artists/create/",                     views.admin_create_mua),
#   path("admin/makeup-artists/<str:mua_id>/update/",        views.admin_update_mua),
#   path("admin/makeup-artists/<str:mua_id>/delete/",        views.admin_delete_mua),
#   path("admin/makeup-artists/<str:mua_id>/upload-images/", views.admin_upload_mua_images),
#   path("admin/makeup-artists/<str:mua_id>/delete-gallery/",views.admin_delete_mua_gallery_image),
# ─────────────────────────────────────────────────────────────────────────────

import math


def _serialize_mua(profile):
    """Shared serializer for MakeupArtistProfile — always dereferences user for status."""
    user = profile.user
    return {
        "id":                   str(profile.id),
        "user_id":              str(user.id),
        "full_name":            profile.full_name or "",
        "gender":               profile.gender or "",
        "makeup_speciality":    profile.makeup_speciality or "",
        "city":                 profile.city or "",
        "state":                profile.state or "",
        "country":              profile.country or "",
        "experience_in_years":  profile.experience_in_years,
        "profile_picture":      profile.profile_picture or "",
        "gallery_images":       profile.gallery_images or [],
        "status":               user.status,          # ← lives on User, NOT on profile
        "email":                user.email,
        "phone_number":         user.phone_number or "",
        "joined_date":          str(profile.joined_date) if profile.joined_date else None,
    }


# ── 1. List Makeup Artists ────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_makeup_artists(request):
    """
    GET /users/api/makeup-artists/

    Query params:
      search      — full name (case-insensitive)
      city        — exact city (case-insensitive)
      experience  — minimum years (int)
      status      — ACTIVE | INACTIVE | BLOCKED
      start_date  — joined_date >= YYYY-MM-DD
      end_date    — joined_date <= YYYY-MM-DD
      page        — default 1
      page_size   — default 15, max 100
    """
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        search     = request.GET.get("search", "").strip()
        city       = request.GET.get("city", "").strip()
        experience = request.GET.get("experience", "").strip()
        status     = request.GET.get("status", "").strip().upper()
        start_date = request.GET.get("start_date", "").strip()
        end_date   = request.GET.get("end_date", "").strip()
        page       = max(int(request.GET.get("page", 1)), 1)
        page_size  = min(int(request.GET.get("page_size", 15)), 100)

        # ── Profile-level filters ──────────────────────────────────
        profile_q = {}
        if search:
            import re
            profile_q["full_name__iregex"] = re.escape(search)
        if city:
            profile_q["city__iexact"] = city
        if experience:
            profile_q["experience_in_years__gte"] = int(experience)
        if start_date:
            from datetime import datetime
            profile_q["joined_date__gte"] = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            from datetime import datetime
            profile_q["joined_date__lte"] = datetime.strptime(end_date, "%Y-%m-%d")

        profiles = MakeupArtistProfile.objects(**profile_q).order_by("-joined_date")

        # ── Status filter (on User) ────────────────────────────────
        if status:
            profiles = [p for p in profiles if p.user and p.user.status == status]
        else:
            profiles = list(profiles)

        total      = len(profiles)
        start      = (page - 1) * page_size
        page_profs = profiles[start: start + page_size]

        return api_response(True, "Makeup artists fetched", {
            "results":    [_serialize_mua(p) for p in page_profs],
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": math.ceil(total / page_size) if total else 1,
            },
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 2. Get MUA Detail ─────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def get_mua_detail(request, mua_id):
    """GET /users/api/makeup-artists/<mua_id>/"""
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = MakeupArtistProfile.objects(id=mua_id).first()
        if not profile:
            return api_response(False, "Makeup artist not found", status=404)
        return api_response(True, "Makeup artist fetched", _serialize_mua(profile))
    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 3. Admin Create MUA ───────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_create_mua(request):
    """
    POST /users/admin/makeup-artists/create/

    Body:
    {
        "full_name":           "Anita Singh",      ← required
        "email":               "anita@example.com", ← required
        "phone_number":        "9999999999",        ← required
        "gender":              "Female",
        "makeup_speciality":   "Bridal",
        "city":                "Mumbai",
        "state":               "Maharashtra",
        "country":             "India",
        "experience_in_years": 4
    }
    Account is created ACTIVE + approved immediately (admin-direct, no OTP).
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body         = json.loads(request.body)
        full_name    = body.get("full_name", "").strip()
        email        = body.get("email", "").strip().lower()
        phone_number = body.get("phone_number", "").strip()

        if not full_name:
            return api_response(False, "full_name is required", status=400)
        if not email:
            return api_response(False, "email is required", status=400)
        if not phone_number:
            return api_response(False, "phone_number is required", status=400)

        if User.objects(email=email).first():
            return api_response(False, "A user with this email already exists", status=400)
        if phone_number and User.objects(phone_number=phone_number).first():
            return api_response(False, "A user with this phone number already exists", status=400)

        user = User(
            email        = email,
            phone_number = phone_number,
            full_name    = full_name,
            role         = "MAKEUP_ARTIST",
            status       = "ACTIVE",
            is_approved  = True,
        )
        user.save()

        profile = MakeupArtistProfile(
            user               = user,
            full_name          = full_name,
            gender             = body.get("gender", "").strip(),
            makeup_speciality  = body.get("makeup_speciality", "").strip(),
            city               = body.get("city", "").strip(),
            state              = body.get("state", "").strip(),
            country            = body.get("country", "").strip(),
            experience_in_years= int(body.get("experience_in_years") or 0),
        )
        profile.save()

        return api_response(True, "Makeup artist created successfully", _serialize_mua(profile), status=201)

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 4. Admin Update MUA ───────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_update_mua(request, mua_id):
    """
    PUT /users/admin/makeup-artists/<mua_id>/update/

    Body (all optional):
    {
        "full_name":           "Anita Singh",
        "gender":              "Female",
        "makeup_speciality":   "Bridal",
        "city":                "Mumbai",
        "state":               "Maharashtra",
        "country":             "India",
        "experience_in_years": 5,
        "status":              "ACTIVE"
    }
    """
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = MakeupArtistProfile.objects(id=mua_id).first()
        if not profile:
            return api_response(False, "Makeup artist not found", status=404)

        user = profile.user
        if not user:
            return api_response(False, "Associated user not found", status=404)

        body = json.loads(request.body)

        STRING_FIELDS = ["full_name", "gender", "makeup_speciality", "city", "state", "country"]
        for field in STRING_FIELDS:
            if field in body:
                val = body[field].strip() if isinstance(body[field], str) else body[field]
                setattr(profile, field, val)

        if "experience_in_years" in body:
            profile.experience_in_years = int(body["experience_in_years"] or 0)

        if "full_name" in body:
            user.full_name = body["full_name"].strip()

        if "status" in body:
            new_status = body["status"].strip().upper()
            if new_status not in ["ACTIVE", "INACTIVE", "BLOCKED"]:
                return api_response(False, "Invalid status", status=400)
            user.status = new_status

        profile.save()
        user.save()

        return api_response(True, "Makeup artist updated successfully", _serialize_mua(profile))

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 5. Admin Delete MUA ───────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_delete_mua(request, mua_id):
    """DELETE /users/admin/makeup-artists/<mua_id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = MakeupArtistProfile.objects(id=mua_id).first()
        if not profile:
            return api_response(False, "Makeup artist not found", status=404)

        user = profile.user

        # Delete all S3 images
        if profile.profile_picture:
            _s3_delete(profile.profile_picture)
        for img_url in (profile.gallery_images or []):
            _s3_delete(img_url)

        profile.delete()
        if user:
            user.delete()

        return api_response(True, "Makeup artist deleted successfully", {})

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 6. Admin Upload MUA Images ────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_upload_mua_images(request, mua_id):
    """
    POST /users/admin/makeup-artists/<mua_id>/upload-images/
    Content-Type: multipart/form-data

    Fields (at least one required):
      profile_picture  — replaces existing
      gallery_images   — appends to gallery
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = MakeupArtistProfile.objects(id=mua_id).first()
        if not profile:
            return api_response(False, "Makeup artist not found", status=404)

        profile_pic_file = request.FILES.get("profile_picture")
        gallery_files    = request.FILES.getlist("gallery_images")

        if not profile_pic_file and not gallery_files:
            return api_response(False, "At least one of profile_picture or gallery_images is required", status=400)

        result = {}

        if profile_pic_file:
            if profile.profile_picture:
                _s3_delete(profile.profile_picture)
            url = _s3_upload(profile_pic_file, folder="mua/profile_pictures", filename=str(profile.id))
            profile.profile_picture = url
            result["profile_picture"] = url

        if gallery_files:
            new_urls = [_s3_upload(f, folder="mua/gallery") for f in gallery_files]
            profile.gallery_images = (profile.gallery_images or []) + new_urls
            result["gallery_images"] = profile.gallery_images

        profile.save()
        return api_response(True, "Images uploaded successfully", result)

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 7. Admin Delete MUA Gallery Image ─────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_delete_mua_gallery_image(request, mua_id):
    """
    DELETE /users/admin/makeup-artists/<mua_id>/delete-gallery/
    Body: { "image_url": "https://..." }
    """
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    try:
        profile = MakeupArtistProfile.objects(id=mua_id).first()
        if not profile:
            return api_response(False, "Makeup artist not found", status=404)

        body      = json.loads(request.body)
        image_url = body.get("image_url", "").strip()

        if not image_url:
            return api_response(False, "image_url is required", status=400)

        gallery = profile.gallery_images or []
        if image_url not in gallery:
            return api_response(False, "Image not found in gallery", status=404)

        gallery.remove(image_url)
        profile.gallery_images = gallery
        profile.save()
        _s3_delete(image_url)

        return api_response(True, "Image deleted successfully", {"gallery_images": profile.gallery_images})

    except Exception as e:
        return api_response(False, str(e), status=500)
