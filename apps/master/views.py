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


def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


# -------------------------------
# EVENT THEMES CRUD
# -------------------------------

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_event_theme(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    body = json.loads(request.body)

    theme = EventTheme(
        theme_name=body.get("theme_name"),
        description=body.get("description"),
        cover_image=body.get("cover_image"),
        gallery_images=body.get("gallery_images", [])
    )
    theme.save()

    return api_response(True, "Theme created")


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
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


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_event_theme(request, theme_id):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)

    body = json.loads(request.body)
    theme = EventTheme.objects.get(id=theme_id)

    theme.theme_name = body.get("theme_name", theme.theme_name)
    theme.description = body.get("description", theme.description)
    theme.status = body.get("status", theme.status)
    theme.cover_image = body.get("cover_image", theme.cover_image)
    theme.gallery_images = body.get("gallery_images", theme.gallery_images)
    theme.save()

    return api_response(True, "Theme updated")


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_event_theme(request, theme_id):
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)

    EventTheme.objects.get(id=theme_id).delete()
    return api_response(True, "Theme deleted")


# -------------------------------
# UNIFORM CATEGORY CRUD
# -------------------------------

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_uniform_category(request):
    body = json.loads(request.body)

    category = UniformCategory(
        category_name=body.get("category_name"),
        unique_key=body.get("unique_key"),
        description=body.get("description"),
        images=body.get("images", [])
    )
    category.save()

    return api_response(True, "Uniform category created")


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
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


# -------------------------------
# SUBSCRIPTION PLAN SETTINGS
# -------------------------------

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
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

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
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