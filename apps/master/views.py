import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.accounts.decorators import require_auth, require_role
from .models import (
    EventTheme,
    UniformCategory,
    SubscriptionPlanSettings,
    PaymentTerms
)

from apps.common.s3_utils import upload_file_to_s3, delete_file_from_s3


def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


# -------------------------------
# EVENT THEMES CRUD
# -------------------------------
# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def create_event_theme(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    print("POST:", request.POST)
    print("FILES:", request.FILES)

    theme_name = request.POST.get("theme_name")
    description = request.POST.get("description")
    cover_image_file = request.FILES.get("cover_image")
    gallery_files = request.FILES.getlist("gallery_images")
    
    print(cover_image_file)
    print(gallery_files)

    cover_url = None
    gallery_urls = []

    if cover_image_file:
        cover_url = upload_file_to_s3(cover_image_file, "event_themes")

    for file in gallery_files:
        url = upload_file_to_s3(file, "event_themes/gallery")
        gallery_urls.append(url)

    theme = EventTheme(
        theme_name=theme_name,
        description=description,
        cover_image=cover_url,
        gallery_images=gallery_urls
    )
    theme.save()
    return api_response(True, "Theme created")


# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def list_event_themes(request):
    themes = EventTheme.objects()
    data = []

    for t in themes:
        data.append({
            "id": t.id,
            "theme_name": t.theme_name,
            "status": t.status,
            "description": t.description,
            "cover_image": t.cover_image,
            "gallery_images": t.gallery_images
        })

    return api_response(True, "Themes fetched", data)


# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def update_event_theme(request, theme_id):

    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    theme = EventTheme.objects.get(id=theme_id)

    theme_name = request.POST.get("theme_name")
    description = request.POST.get("description")
    status = request.POST.get("status")

    new_cover = request.FILES.get("cover_image")
    new_gallery_files = request.FILES.getlist("gallery_images")

    existing_gallery = request.POST.getlist("existing_gallery")

    # update fields
    if theme_name:
        theme.theme_name = theme_name

    if description:
        theme.description = description

    if status:
        theme.status = status

    # --------------------
    # COVER IMAGE UPDATE
    # --------------------

    if new_cover:

        # delete old cover
        delete_file_from_s3(theme.cover_image)

        cover_url = upload_file_to_s3(new_cover, "event_themes/cover")
        theme.cover_image = cover_url

    # --------------------
    # GALLERY IMAGE UPDATE
    # --------------------

    current_gallery = theme.gallery_images or []

    # delete removed images
    removed_images = set(current_gallery) - set(existing_gallery)

    for img in removed_images:
        delete_file_from_s3(img)

    updated_gallery = list(existing_gallery)

    # upload new gallery images
    for file in new_gallery_files:
        url = upload_file_to_s3(file, "event_themes/gallery")
        updated_gallery.append(url)

    theme.gallery_images = updated_gallery

    theme.save()

    return api_response(True, "Theme updated")


# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def delete_event_theme(request, theme_id):

    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    theme = EventTheme.objects.get(id=theme_id)

    # delete cover
    delete_file_from_s3(theme.cover_image)

    # delete gallery
    for img in theme.gallery_images:
        delete_file_from_s3(img)

    theme.delete()

    return api_response(True, "Theme deleted")


# -------------------------------
# UNIFORM CATEGORY CRUD
# -------------------------------

# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def create_uniform_category(request):

    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    category_name = request.POST.get("category_name")
    unique_key = request.POST.get("unique_key")
    description = request.POST.get("description")

    image_files = request.FILES.getlist("images")

    image_urls = []

    for file in image_files:
        url = upload_file_to_s3(file, "uniform_categories")
        image_urls.append(url)

    category = UniformCategory(
        category_name=category_name,
        unique_key=unique_key,
        description=description,
        images=image_urls
    )

    category.save()

    return api_response(True, "Uniform category created")


# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def list_uniform_categories(request):

    categories = UniformCategory.objects()

    data = [{
        "id": c.id,
        "category_name": c.category_name,
        "unique_key": c.unique_key,
        "description": c.description,
        "images": c.images,
        "is_active": c.is_active
    } for c in categories]

    return api_response(True, "Uniform categories fetched", data)


# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def update_uniform_category(request, category_id):

    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    category = UniformCategory.objects.get(id=category_id)

    category_name = request.POST.get("category_name")
    description = request.POST.get("description")
    is_active = request.POST.get("is_active")

    new_images = request.FILES.getlist("images")
    existing_images = request.POST.getlist("existing_images")

    if category_name:
        category.category_name = category_name

    if description:
        category.description = description

    if is_active is not None:
        category.is_active = is_active.lower() == "true"

    current_images = category.images or []

    # -----------------------
    # delete removed images
    # -----------------------

    removed_images = set(current_images) - set(existing_images)

    for img in removed_images:
        delete_file_from_s3(img)

    updated_images = list(existing_images)

    # -----------------------
    # upload new images
    # -----------------------

    for file in new_images:
        url = upload_file_to_s3(file, "uniform_categories")
        updated_images.append(url)

    category.images = updated_images

    category.save()

    return api_response(True, "Uniform category updated")


# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def delete_uniform_category(request, category_id):

    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    category = UniformCategory.objects.get(id=category_id)

    for img in category.images:
        delete_file_from_s3(img)

    category.delete()

    return api_response(True, "Uniform category deleted")




# -------------------------------
# SUBSCRIPTION PLAN SETTINGS
# -------------------------------

# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def update_subscription_plan(request, plan_name):
    body = json.loads(request.body)

    plan = SubscriptionPlanSettings.objects.get(name=plan_name)

    plan.monthlyPrice = body.get("monthlyPrice", plan.monthlyPrice)
    plan.yearlyPrice = body.get("yearlyPrice", plan.yearlyPrice)
    plan.prioritySupport = body.get("prioritySupport", plan.prioritySupport)
    plan.isFree = body.get("isFree", plan.isFree)
    plan.save()

    return api_response(True, "Subscription plan updated")



# -------------------------------
# PAYMENT TERMS
# -------------------------------

# @require_auth
# @require_role(["ADMIN"])
@csrf_exempt
def update_payment_terms(request):
    body = json.loads(request.body)

    advance = body.get("advancePercentage")

    terms = PaymentTerms.objects.first()
    if not terms:
        terms = PaymentTerms(advancePercentage=advance)
    else:
        terms.advancePercentage = advance

    terms.save()

    return api_response(True, "Payment terms updated")