# apps/users/staff_registration.py
#
# Public staff self-registration endpoint — NO auth required.
#
# ADD to apps/users/urls.py:
#   from .staff_registration import staff_self_register
#   path("register/staff/", staff_self_register),
#
import json
import random
import uuid
import os
from datetime import datetime

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from apps.users.models import User, StaffProfile
from apps.common.constants import UserRole, UserStatus


# ── Stage name auto-generator ──────────────────────────────────────────────
#
# Generates a cool, unique stage name like "Velvet Storm" or "Cobalt Raven"
# from curated word banks. Checks DB for uniqueness and retries if taken.

_ADJECTIVES = [
    "Velvet", "Cobalt", "Crimson", "Golden", "Silver", "Onyx", "Ivory",
    "Neon", "Solar", "Lunar", "Arctic", "Ember", "Indigo", "Jade",
    "Scarlet", "Storm", "Phantom", "Mystic", "Regal", "Blazing",
    "Electric", "Crystal", "Shadow", "Noble", "Vivid", "Zenith",
    "Radiant", "Sable", "Azure", "Prism",
]

_NOUNS = [
    "Storm", "Raven", "Phoenix", "Nova", "Echo", "Blaze", "Drift",
    "Apex", "Vex", "Quill", "Titan", "Lynx", "Ember", "Halo",
    "Flare", "Crest", "Pulse", "Vibe", "Sage", "Grove",
    "Reign", "Flint", "Cove", "Glow", "Spark", "Ridge", "Wave",
    "Knight", "Hawk", "Arrow",
]


def _generate_stage_name(max_attempts: int = 20) -> str:
    """
    Returns a unique stage name not already in the DB.
    Falls back to appending a short random suffix on collision.
    """
    for _ in range(max_attempts):
        adj  = random.choice(_ADJECTIVES)
        noun = random.choice(_NOUNS)
        # Avoid same word twice (e.g. "Storm Storm")
        if adj.lower() == noun.lower():
            continue
        candidate = f"{adj} {noun}"
        if not StaffProfile.objects(stage_name=candidate).first():
            return candidate

    # Absolute fallback — very unlikely to be needed
    return f"Star {str(uuid.uuid4())[:6].upper()}"


# ── S3 helpers (same pattern used throughout the project) ────────────────────

def _s3_client():
    import boto3
    from django.conf import settings
    return boto3.client(
        "s3",
        aws_access_key_id     = settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY,
        region_name           = settings.AWS_S3_REGION_NAME,
    )

def _s3_upload(file_obj, folder: str, filename: str = None) -> str:
    from django.conf import settings
    ext    = os.path.splitext(file_obj.name)[-1].lower() or ".jpg"
    key    = f"{folder}/{filename or uuid.uuid4()}{ext}"
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    region = settings.AWS_S3_REGION_NAME
    _s3_client().upload_fileobj(
        file_obj, bucket, key,
        ExtraArgs={"ContentType": file_obj.content_type or "image/jpeg"},
    )
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _api(success, message, data=None, status=200):
    return JsonResponse({"success": success, "message": message, "data": data or {}}, status=status)


# ── Self-registration endpoint ────────────────────────────────────────────────

@csrf_exempt
def staff_self_register(request):
    """
    POST /users/register/staff/
    Content-Type: multipart/form-data   (because images are included)

    Required fields:
      email, first_name, last_name, telephone OR cell_phone

    All other fields from the registration form are optional.
    Images:
      images[]   — up to 4 files (2 MB each enforced client-side)

    On success:
      - Creates User with role=STAFF, status=INACTIVE (pending admin review)
      - Creates StaffProfile with all form data
      - Auto-generates a stage_name
      - Uploads images to S3 as gallery_images
      - Returns the generated stage_name so the frontend can show it

    The admin then reviews pending staff via GET /auth/admin/pending-users/
    and approves via POST /auth/admin/approve-user/
    """
    if request.method != "POST":
        return _api(False, "Invalid method", status=405)

    try:
        # ── Extract form data ──────────────────────────────────────
        email      = request.POST.get("email", "").strip().lower()
        first_name = request.POST.get("firstName", "").strip()
        last_name  = request.POST.get("lastName", "").strip()
        telephone  = request.POST.get("telephone", "").strip()
        cell_phone = request.POST.get("cellPhone", "").strip()

        # ── Validate required fields ───────────────────────────────
        if not email:
            return _api(False, "Email is required", status=400)
        if not first_name:
            return _api(False, "First name is required", status=400)
        if not last_name:
            return _api(False, "Last name is required", status=400)
        if not telephone and not cell_phone:
            return _api(False, "At least one phone number is required", status=400)

        from apps.common.validators import validate_email
        if not validate_email(email):
            return _api(False, "Invalid email format", status=400)

        # ── Duplicate check ────────────────────────────────────────
        if User.objects(email=email).first():
            return _api(False, "An account with this email already exists", status=409)

        phone = cell_phone or telephone
        if phone and User.objects(phone_number=phone).first():
            return _api(False, "An account with this phone number already exists", status=409)

        # ── Parse optional fields ──────────────────────────────────
        full_name      = f"{first_name} {last_name}".strip()
        address        = request.POST.get("address", "").strip()
        city           = request.POST.get("city", "").strip()
        country        = request.POST.get("country", "").strip()
        place_of_birth = request.POST.get("placeOfBirth", "").strip()
        marital_status = request.POST.get("status", "").strip().lower()  # single | married

        # Date of birth
        dob = None
        dob_str = request.POST.get("dob", "").strip()
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, "%Y-%m-%d")
            except ValueError:
                pass

        # Physical dimensions
        weight_raw = request.POST.get("weight", "")
        height_raw = request.POST.get("height", "")
        weight = float(weight_raw) if weight_raw else None
        height = float(height_raw) if height_raw else None
        shoe_size    = request.POST.get("shoeSize", "").strip()
        blazer_size  = request.POST.get("blazerSize", "").strip()
        trouser_size = request.POST.get("trouserSize", "").strip()

        # Education
        is_student  = request.POST.get("student", "no").lower() == "yes"
        school      = request.POST.get("school", "").strip()
        degree      = request.POST.get("degree", "").strip()

        # Languages — up to 4
        languages = []
        for i in range(1, 5):
            lang  = request.POST.get(f"language{i}", "").strip()
            level = request.POST.get(f"rate{i}", "").strip()
            if lang:
                languages.append({"language": lang, "proficiency": level})

        # Work experience
        hostess_experience = request.POST.get("hostessExperience", "no").lower() == "yes"
        group_responsible  = request.POST.get("groupResponsible", "no").lower() == "yes"
        agency             = request.POST.get("agency", "").strip()
        experience_areas   = request.POST.getlist("experienceAreas")
        work_type          = request.POST.get("workType", "").strip()
        holiday_work       = request.POST.get("holidayWork", "no").lower() == "yes"

        # ── Auto-generate stage name ───────────────────────────────
        stage_name = _generate_stage_name()

        # ── Create User (INACTIVE — needs admin approval) ──────────
        user = User(
            email        = email,
            phone_number = phone,
            full_name    = full_name,
            role         = UserRole.STAFF.value,
            status       = UserStatus.INACTIVE.value,  # pending review
            is_approved  = False,
        )
        user.save()

        # ── Create StaffProfile ────────────────────────────────────
        profile = StaffProfile(
            user                  = user,
            full_name             = full_name,
            first_name            = first_name,
            last_name             = last_name,
            stage_name            = stage_name,
            telephone             = telephone,
            cell_phone            = cell_phone,
            address               = address,
            city                  = city,
            country               = country,
            place_of_birth        = place_of_birth,
            marital_status        = marital_status,
            date_of_birth         = dob,
            weight                = weight,
            height                = height,
            shoe_size             = shoe_size,
            blazer_size           = blazer_size,
            trouser_size          = trouser_size,
            is_student            = is_student,
            school                = school,
            degree                = degree,
            languages             = languages,
            hostess_experience    = hostess_experience,
            group_responsible     = group_responsible,
            agency                = agency,
            experience_areas      = experience_areas,
            work_type             = work_type,
            holiday_work          = holiday_work,
            registration_complete = True,
        )
        profile.save()

        # ── Upload images to S3 ────────────────────────────────────
        image_files = request.FILES.getlist("images")
        if image_files:
            # Limit to 4 images
            image_files = image_files[:4]
            gallery_urls = []
            for f in image_files:
                url = _s3_upload(f, folder="staff/registration_gallery")
                gallery_urls.append(url)
            profile.gallery_images = gallery_urls
            profile.save()

        return _api(True, "Registration submitted successfully! Your application is under review.", {
            "id":         str(profile.id),
            "full_name":  full_name,
            "email":      email,
            "stage_name": stage_name,   # show this to the applicant
            "status":     "PENDING_REVIEW",
        }, status=201)

    except Exception as e:
        return _api(False, str(e), status=500)