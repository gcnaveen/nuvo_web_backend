# apps/users/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.accounts.decorators import require_auth, require_role
import json
from apps.users.models import User, ClientProfile, StaffProfile, MakeupArtistProfile

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
            data.append({
                "id":                  str(profile.id),
                "user_id":             str(profile.user.id) if profile.user else None,
                "full_name":           profile.full_name,
                "stage_name":          profile.stage_name,
                "gender":              profile.gender,
                "city":                profile.city,
                "state":               profile.state,
                "country":             profile.country,
                "package":             profile.package,
                "status":              profile.status,
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
#  ADMIN — LIST MAKEUP ARTISTS  (search + filter + pagination)
# ─────────────────────────────────────────────
#
#  Query params:
#    search        – name (case-insensitive contains)
#    city          – exact city match
#    experience    – minimum years of experience  (int)
#    status        – active | inactive | blocked
#    page          – page number  (default: 1)
#    page_size     – rows per page (default: 15, max: 100)
#
# ─────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_makeup_artists(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import MakeupArtistProfile

    try:
        # ── Read query params ────────────────────────────────────────
        search     = request.GET.get("search", "").strip()
        city       = request.GET.get("city", "").strip()
        experience = request.GET.get("experience", "").strip()   # min experience
        status     = request.GET.get("status", "").strip()

        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)

        # ── Build queryset ───────────────────────────────────────────
        qs = MakeupArtistProfile.objects()

        # Search by name
        if search:
            qs = qs.filter(full_name__icontains=search)

        # City filter
        if city:
            qs = qs.filter(city__iexact=city)

        # Minimum experience
        if experience:
            try:
                qs = qs.filter(experience_in_years__gte=int(experience))
            except ValueError:
                return api_response(False, "experience must be an integer", status=400)

        # Status filter
        if status:
            qs = qs.filter(status__iexact=status)

        # ── Pagination ───────────────────────────────────────────────
        total  = qs.count()
        offset = (page - 1) * page_size
        artist_list = qs.skip(offset).limit(page_size)

        # ── Serialize ────────────────────────────────────────────────
        data = []
        for profile in artist_list:
            data.append({
                "id":                  str(profile.id),
                "user_id":             str(profile.user.id) if profile.user else None,
                "full_name":           profile.full_name,
                "gender":              profile.gender,
                "makeup_speciality":   profile.makeup_speciality,
                "city":                profile.city,
                "state":               profile.state,
                "country":             profile.country,
                "experience_in_years": profile.experience_in_years,
                "status":              profile.status,
                "profile_picture":     getattr(profile, "profile_picture", None),
                "joined_date":         str(profile.joined_date) if profile.joined_date else None,
            })

        return api_response(True, "Makeup artists list fetched", {
            "results":    data,
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": -(-total // page_size),
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
        # ── Read query params ────────────────────────────────────────
        search     = request.GET.get("search", "").strip()
        city       = request.GET.get("city", "").strip()
        plan_type  = request.GET.get("plan_type", "").strip()
        status     = request.GET.get("status", "").strip()   # ACTIVE | INACTIVE | BLOCKED
        start_date = request.GET.get("start_date", "").strip()
        end_date   = request.GET.get("end_date", "").strip()

        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)

        # ── Build queryset on ClientProfile ──────────────────────────
        qs = ClientProfile.objects()

        # Search: match name on profile OR email on the related User
        if search:
            matched_user_ids = list(
                User.objects(email__icontains=search).scalar("id")
            )
            qs = qs.filter(
                Q(full_name__icontains=search) | Q(user__in=matched_user_ids)
            )

        # City filter (on profile)
        if city:
            qs = qs.filter(city__iexact=city)

        # Subscription plan filter (on profile)
        if plan_type:
            qs = qs.filter(subscription_plan__iexact=plan_type)

        # Status filter — status lives on User, so filter via the reference
        # MongoEngine supports filtering on ReferenceField using user__status
        if status:
            matched_user_ids = list(
                User.objects(status__iexact=status).scalar("id")
            )
            qs = qs.filter(user__in=matched_user_ids)

        # Joined date range (on profile)
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
        total       = qs.count()
        offset      = (page - 1) * page_size
        client_list = qs.skip(offset).limit(page_size)

        # ── Serialize — pull email, phone, status from related User ──
        data = []
        for profile in client_list:
            user = profile.user  # dereferences the ReferenceField
            data.append({
                "id":                str(profile.id),
                "user_id":           str(user.id) if user else None,
                "full_name":         profile.full_name or "",
                "email":             user.email        if user else None,
                "phone_number":      user.phone_number if user else None,
                "city":              profile.city      or "",
                "state":             profile.state     or "",
                "country":           profile.country   or "",
                "subscription_plan": profile.subscription_plan,
                "status":            user.status       if user else None,  # ← from User
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


