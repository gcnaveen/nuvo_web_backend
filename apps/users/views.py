from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.accounts.decorators import require_auth, require_role
import json


def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


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
    

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_all_users(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    users = User.objects()

    data = []
    for user in users:
        data.append({
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "status": user.status
        })

    return api_response(True, "All users fetched", data)


@csrf_exempt
@require_auth
@require_role(["CLIENT"])
def complete_client_profile(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import ClientProfile
    from apps.common.constants import SubscriptionPlan
    import json

    try:
        body = json.loads(request.body)

        full_name = body.get("full_name")
        city = body.get("city")
        state = body.get("state")
        country = body.get("country")
        subscription_plan = body.get("subscription_plan", "SILVER")

        if not full_name or not city or not state or not country:
            return api_response(False, "All fields are required", status=400)

        if subscription_plan not in [p.value for p in SubscriptionPlan]:
            return api_response(False, "Invalid subscription plan", status=400)

        if ClientProfile.objects(user=request.user).first():
            return api_response(False, "Profile already completed", status=400)

        profile = ClientProfile(
            user=request.user,
            full_name=full_name,
            city=city,
            state=state,
            country=country,
            subscription_plan=subscription_plan
        )
        profile.save()

        return api_response(True, "Client profile completed")

    except Exception as e:
        return api_response(False, str(e), status=500)
    



@csrf_exempt
@require_auth
@require_role(["STAFF"])
def complete_staff_profile(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import StaffProfile
    import json

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

        profile = StaffProfile(
            user=request.user,
            full_name=body.get("full_name"),
            stage_name=body.get("stage_name"),
            gender=body.get("gender"),
            city=body.get("city"),
            state=body.get("state"),
            country=body.get("country"),
            price_of_staff=float(body.get("price_of_staff")),
            experience_in_years=int(body.get("experience_in_years"))
        )
        profile.save()

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
    import json

    try:
        body = json.loads(request.body)

        required_fields = [
            "full_name", "gender",
            "makeup_speciality",
            "city", "state", "country",
            "experience_in_years"
        ]

        for field in required_fields:
            if not body.get(field):
                return api_response(False, f"{field} is required", status=400)

        if MakeupArtistProfile.objects(user=request.user).first():
            return api_response(False, "Profile already completed", status=400)

        profile = MakeupArtistProfile(
            user=request.user,
            full_name=body.get("full_name"),
            gender=body.get("gender"),
            makeup_speciality=body.get("makeup_speciality"),
            city=body.get("city"),
            state=body.get("state"),
            country=body.get("country"),
            experience_in_years=int(body.get("experience_in_years"))
        )
        profile.save()

        return api_response(True, "Makeup artist profile completed")

    except Exception as e:
        return api_response(False, str(e), status=500)
    

@csrf_exempt
@require_auth
def get_my_profile(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import (
        ClientProfile,
        StaffProfile,
        MakeupArtistProfile
    )

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

    from apps.users.models import (
        ClientProfile,
        StaffProfile,
        MakeupArtistProfile
    )

    import json
    body = json.loads(request.body)
    user = request.user

    if user.role == "CLIENT":
        profile = ClientProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)

        profile.full_name = body.get("full_name", profile.full_name)
        profile.city = body.get("city", profile.city)
        profile.state = body.get("state", profile.state)
        profile.country = body.get("country", profile.country)
        profile.save()

    elif user.role == "STAFF":
        profile = StaffProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)

        profile.full_name = body.get("full_name", profile.full_name)
        profile.stage_name = body.get("stage_name", profile.stage_name)
        profile.price_of_staff = float(body.get("price_of_staff", profile.price_of_staff))
        profile.experience_in_years = int(body.get("experience_in_years", profile.experience_in_years))
        profile.save()

    elif user.role == "MAKEUP_ARTIST":
        profile = MakeupArtistProfile.objects(user=user).first()
        if not profile:
            return api_response(False, "Profile not completed", status=404)

        profile.full_name = body.get("full_name", profile.full_name)
        profile.makeup_speciality = body.get("makeup_speciality", profile.makeup_speciality)
        profile.experience_in_years = int(body.get("experience_in_years", profile.experience_in_years))
        profile.save()

    return api_response(True, "Profile updated")


@csrf_exempt
@require_auth
@require_role(["STAFF"])
def upload_staff_images(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    from apps.users.models import StaffProfile
    import os
    from django.conf import settings

    profile = StaffProfile.objects(user=request.user).first()
    if not profile:
        return api_response(False, "Profile not completed", status=404)

    files = request.FILES.getlist("images")

    if not files:
        return api_response(False, "No files uploaded", status=400)

    saved_urls = []

    for file in files:
        file_path = os.path.join(settings.MEDIA_ROOT, file.name)

        with open(file_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        saved_urls.append(settings.MEDIA_URL + file.name)

    profile.gallery_images = saved_urls
    profile.save()

    return api_response(True, "Images uploaded", {
        "gallery_images": saved_urls
    })


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_client_subscription(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    import json
    from apps.users.models import ClientProfile
    from apps.common.constants import SubscriptionPlan

    body = json.loads(request.body)

    user_id = body.get("user_id")
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




