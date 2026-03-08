# apps/master/views.py
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

import json, uuid, os
import boto3

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .models import EventTheme, UniformCategory, SubscriptionPlanSettings, PaymentTerms



# ── S3 Helpers ──────────────────────────────────────────────────────────────
def _s3_client():
    return boto3.client("s3",
        aws_access_key_id     = settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY,
        region_name           = settings.AWS_S3_REGION_NAME,
    )

def _s3_delete(url: str):
    try:
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        _s3_client().delete_object(Bucket=bucket, Key=url.split(f"{bucket}/")[-1])
    except Exception:
        pass

def _s3_upload(file_obj, folder: str, filename: str = None) -> str:
    ext    = os.path.splitext(file_obj.name)[-1].lower() or ".jpg"
    key    = f"{folder}/{filename or uuid.uuid4()}{ext}"
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    region = settings.AWS_S3_REGION_NAME
    _s3_client().upload_fileobj(file_obj, bucket, key,
        ExtraArgs={"ContentType": file_obj.content_type or "image/jpeg"})
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"




def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)

# 1. EVENT THEMES
# ══════════════════════════════════════════════════════════════════════════════

def _ser_theme(t):
    return {
        "id": str(t.id), "theme_name": t.theme_name,
        "status": t.status or "ACTIVE", "description": t.description or "",
        "cover_image": t.cover_image or "", "gallery_images": t.gallery_images or [],
        "created_at": str(t.created_at) if t.created_at else None,
        "updated_at": str(t.updated_at) if t.updated_at else None,
    }

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_event_theme(request):
    """POST /master/themes/create/ — multipart/form-data
    Fields: theme_name*(req), description, status, cover_image(file), gallery_images(files)"""
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        name = request.POST.get("theme_name", "").strip()
        if not name:
            return api_response(False, "theme_name is required", status=400)
        theme = EventTheme(
            theme_name  = name,
            description = request.POST.get("description", "").strip(),
            status      = request.POST.get("status", "ACTIVE").strip().upper(),
        )
        if cf := request.FILES.get("cover_image"):
            theme.cover_image = _s3_upload(cf, "themes/covers", str(theme.id or uuid.uuid4()))
        if gf := request.FILES.getlist("gallery_images"):
            theme.gallery_images = [_s3_upload(f, "themes/gallery") for f in gf]
        theme.save()
        return api_response(True, "Event theme created", _ser_theme(theme), status=201)
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_event_themes(request):
    """GET /master/themes/"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        return api_response(True, "Themes fetched",
            [_ser_theme(t) for t in EventTheme.objects().order_by("-created_at")])
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_event_theme(request, theme_id):
    """PUT /master/themes/<theme_id>/update/ — multipart/form-data
    Fields (all opt): theme_name, description, status,
                      cover_image(file), gallery_images(files),
                      delete_gallery_urls (JSON array string)"""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        theme = EventTheme.objects(id=theme_id).first()
        if not theme:
            return api_response(False, "Theme not found", status=404)
        if v := request.POST.get("theme_name", "").strip(): theme.theme_name = v
        if "description" in request.POST: theme.description = request.POST["description"].strip()
        if "status" in request.POST: theme.status = request.POST["status"].strip().upper()
        if cf := request.FILES.get("cover_image"):
            _s3_delete(theme.cover_image or "")
            theme.cover_image = _s3_upload(cf, "themes/covers", str(theme.id))
        if raw := request.POST.get("delete_gallery_urls", ""):
            try:
                gallery = list(theme.gallery_images or [])
                for url in json.loads(raw):
                    if url in gallery:
                        gallery.remove(url); _s3_delete(url)
                theme.gallery_images = gallery
            except Exception: pass
        if gf := request.FILES.getlist("gallery_images"):
            theme.gallery_images = (theme.gallery_images or []) + [_s3_upload(f, "themes/gallery") for f in gf]
        theme.save()
        return api_response(True, "Theme updated", _ser_theme(theme))
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_event_theme(request, theme_id):
    """DELETE /master/themes/<theme_id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Invalid method", status=405)
    try:
        theme = EventTheme.objects(id=theme_id).first()
        if not theme:
            return api_response(False, "Theme not found", status=404)
        _s3_delete(theme.cover_image or "")
        for u in (theme.gallery_images or []): _s3_delete(u)
        theme.delete()
        return api_response(True, "Theme deleted", {})
    except Exception as e:
        return api_response(False, str(e), status=500)




# ══════════════════════════════════════════════════════════════════════════════
# 2. UNIFORM CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════

def _ser_uniform(u):
    return {
        "id": str(u.id), "category_name": u.category_name,
        "unique_key": u.unique_key, "description": u.description or "",
        "images": u.images or [], "is_active": u.is_active,
        "created_at": str(u.created_at) if u.created_at else None,
        "updated_at": str(u.updated_at) if u.updated_at else None,
    }

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_uniform_category(request):
    """POST /master/uniform/create/ — multipart/form-data
    Fields: category_name*(req), unique_key*(req), description, is_active, images(files)"""
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        name = request.POST.get("category_name", "").strip()
        key  = request.POST.get("unique_key", "").strip().lower().replace(" ", "_")
        if not name: return api_response(False, "category_name is required", status=400)
        if not key:  return api_response(False, "unique_key is required", status=400)
        if UniformCategory.objects(unique_key=key).first():
            return api_response(False, f"unique_key '{key}' already exists", status=400)
        cat = UniformCategory(
            category_name = name, unique_key = key,
            description   = request.POST.get("description", "").strip(),
            is_active     = request.POST.get("is_active", "true").lower() != "false",
        )
        if imgs := request.FILES.getlist("images"):
            cat.images = [_s3_upload(f, "uniforms") for f in imgs]
        cat.save()
        return api_response(True, "Uniform category created", _ser_uniform(cat), status=201)
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_uniform_categories(request):
    """GET /master/uniform/"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        return api_response(True, "Uniform categories fetched",
            [_ser_uniform(c) for c in UniformCategory.objects().order_by("-created_at")])
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_uniform_category(request, category_id):
    """PUT /master/uniform/<category_id>/update/ — multipart/form-data
    Fields (all opt): category_name, description, is_active,
                      images(files), delete_image_urls(JSON array string)"""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        cat = UniformCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Uniform category not found", status=404)
        if v := request.POST.get("category_name", "").strip(): cat.category_name = v
        if "description" in request.POST: cat.description = request.POST["description"].strip()
        if "is_active" in request.POST: cat.is_active = request.POST["is_active"].lower() != "false"
        if raw := request.POST.get("delete_image_urls", ""):
            try:
                imgs = list(cat.images or [])
                for url in json.loads(raw):
                    if url in imgs:
                        imgs.remove(url); _s3_delete(url)
                cat.images = imgs
            except Exception: pass
        if nf := request.FILES.getlist("images"):
            cat.images = (cat.images or []) + [_s3_upload(f, "uniforms") for f in nf]
        cat.save()
        return api_response(True, "Uniform category updated", _ser_uniform(cat))
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_uniform_category(request, category_id):
    """DELETE /master/uniform/<category_id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Invalid method", status=405)
    try:
        cat = UniformCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Uniform category not found", status=404)
        for u in (cat.images or []): _s3_delete(u)
        cat.delete()
        return api_response(True, "Uniform category deleted", {})
    except Exception as e:
        return api_response(False, str(e), status=500)




# ══════════════════════════════════════════════════════════════════════════════
# 3. SUBSCRIPTION PLAN SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

def _ser_plan(p):
    return {
        "id": str(p.id), "name": p.name,
        "monthlyPrice": p.monthlyPrice, "yearlyPrice": p.yearlyPrice,
        "prioritySupport": p.prioritySupport, "isFree": p.isFree,
        "last_updated": str(p.last_updated) if p.last_updated else None,
    }

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_subscription_plans(request):
    """GET /master/subscription/"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        return api_response(True, "Plans fetched",
            [_ser_plan(p) for p in SubscriptionPlanSettings.objects().order_by("name")])
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_subscription_plan(request, plan_name):
    """PUT /master/subscription/<plan_name>/update/
    Body: { monthlyPrice, yearlyPrice, prioritySupport, isFree }
    Upserts — creates the document if it doesn't exist."""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        body = json.loads(request.body)
        plan = SubscriptionPlanSettings.objects(name=plan_name.upper()).first()
        if not plan:
            plan = SubscriptionPlanSettings(name=plan_name.upper())
        if "monthlyPrice"    in body: plan.monthlyPrice    = float(body["monthlyPrice"])
        if "yearlyPrice"     in body: plan.yearlyPrice     = float(body["yearlyPrice"])
        if "prioritySupport" in body: plan.prioritySupport = bool(body["prioritySupport"])
        if "isFree"          in body: plan.isFree          = bool(body["isFree"])
        plan.save()
        return api_response(True, f"{plan.name} plan updated", _ser_plan(plan))
    except Exception as e:
        return api_response(False, str(e), status=500)


# ══════════════════════════════════════════════════════════════════════════════
# 4. PAYMENT TERMS
# ══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def get_payment_terms(request):
    """GET /master/payment/"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        terms = PaymentTerms.objects().first()
        if not terms:
            return api_response(True, "No payment terms set", {"advancePercentage": None})
        return api_response(True, "Payment terms fetched", {
            "advancePercentage": terms.advancePercentage,
            "lastUpdatedAt": str(terms.lastUpdatedAt),
        })
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_payment_terms(request):
    """PUT /master/payment/update/
    Body: { "advancePercentage": 30 }  — 0-100"""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        body = json.loads(request.body)
        pct  = body.get("advancePercentage")
        if pct is None:
            return api_response(False, "advancePercentage is required", status=400)
        pct = float(pct)
        if not (0 <= pct <= 100):
            return api_response(False, "Must be 0-100", status=400)
        terms = PaymentTerms.objects().first() or PaymentTerms(advancePercentage=pct)
        terms.advancePercentage = pct
        terms.save()
        return api_response(True, "Payment terms updated", {
            "advancePercentage": terms.advancePercentage,
            "lastUpdatedAt": str(terms.lastUpdatedAt),
        })
    except Exception as e:
        return api_response(False, str(e), status=500)




