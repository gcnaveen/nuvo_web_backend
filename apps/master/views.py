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
from datetime import datetime
import boto3

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .models import EventTheme, UniformCategory, SubscriptionPlanSettings, PaymentTerms, CrewMember, Coupon
from apps.events.models import Event




# ── S3 Helpers ──────────────────────────────────────────────────────────────
def _s3_client():
    kwargs = {"region_name": settings.AWS_S3_REGION_NAME}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs.update(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    return boto3.client("s3", **kwargs)

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


def _events_using(filter_kwargs: dict, exclude_statuses=("cancelled",)) -> list:
    """
    Returns a list of compact event dicts that match filter_kwargs
    and are NOT in exclude_statuses.
    Used by every delete function below.
    """
    from apps.events.models import Event   # ← add this line

    qs = Event.objects(**filter_kwargs)
    if exclude_statuses:
        qs = qs.filter(status__nin=list(exclude_statuses))
    result = []
    for ev in qs:
        result.append({
            "id":         str(ev.id),
            "event_name": ev.event_name,
            "status":     ev.status,
            "city":       ev.city,
            "event_start_datetime": str(ev.event_start_datetime) if ev.event_start_datetime else None,
        })
    return result




def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data if data is not None else {}
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
@require_role(["ADMIN", "CLIENT"])
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

        # -- Reference check --
        from apps.events.models import Event
        in_use = _events_using({"theme": theme})
        if in_use:
            return api_response(
                False,
                f"Cannot delete '{theme.theme_name}' — it is used by "
                f"{len(in_use)} active event(s). Remove the theme from those "
                f"events first, or wait until they are cancelled/completed.",
                data={"events_using_this": in_use},
                status=409,
            )

        # Safe to delete — clean up S3 assets too
        _s3_delete(theme.cover_image or "")
        for url in (theme.gallery_images or []):
            _s3_delete(url)
        theme.delete()
        return api_response(True, "Theme deleted successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)




# ══════════════════════════════════════════════════════════════════════════════
# 2. UNIFORM CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════

VALID_GENDERS = ["male", "female", "unisex"]
 
 
def _ser_uniform(u):
    return {
        "id":            str(u.id),
        "category_name": u.category_name,
        "unique_key":    u.unique_key,
        "description":   u.description or "",
        "images":        u.images or [],
        "is_active":     u.is_active,
        "gender":        u.gender or "unisex",
        "price":         u.price if u.price is not None else 0.0,
        "created_at":    str(u.created_at) if u.created_at else None,
        "updated_at":    str(u.updated_at) if u.updated_at else None,
    }

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_uniform_category(request):
    """
    POST /master/uniform/create/
    Content-Type: multipart/form-data
 
    Fields:
      category_name *  — required
      unique_key    *  — required, auto-slugified
      description      — optional
      is_active        — true | false  (default true)
      gender           — male | female | unisex  (default unisex)
      price            — number  (default 0)
      images           — file[]
    """
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        name   = request.POST.get("category_name", "").strip()
        key    = request.POST.get("unique_key", "").strip().lower().replace(" ", "_")
        gender = request.POST.get("gender", "unisex").strip().lower()
        price  = request.POST.get("price", "0").strip()
 
        if not name:
            return api_response(False, "category_name is required", status=400)
        if not key:
            return api_response(False, "unique_key is required", status=400)
        if gender not in VALID_GENDERS:
            return api_response(False, f"gender must be one of: {', '.join(VALID_GENDERS)}", status=400)
        if UniformCategory.objects(unique_key=key).first():
            return api_response(False, f"unique_key '{key}' already exists", status=400)
 
        try:
            price_val = float(price) if price else 0.0
        except ValueError:
            return api_response(False, "price must be a number", status=400)
 
        cat = UniformCategory(
            category_name = name,
            unique_key    = key,
            description   = request.POST.get("description", "").strip(),
            is_active     = request.POST.get("is_active", "true").lower() != "false",
            gender        = gender,
            price         = price_val,
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
    """
    GET /master/uniform/
 
    Admin list — returns all categories (active + inactive).
    Supports the same filter params as filter_uniform_categories
    so the admin panel can also filter if needed.
    """
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        qs = UniformCategory.objects()
 
        # Optional admin-side filters
        if gender := request.GET.get("gender", "").strip().lower():
            if gender in VALID_GENDERS:
                qs = qs.filter(gender=gender)
 
        if active := request.GET.get("is_active", "").strip().lower():
            qs = qs.filter(is_active=(active != "false"))
 
        qs = qs.order_by("-created_at")
        return api_response(True, "Uniform categories fetched", [_ser_uniform(c) for c in qs])
    except Exception as e:
        return api_response(False, str(e), status=500)
 
 
@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_uniform_category(request, category_id):
    """
    PUT /master/uniform/<category_id>/update/
    Content-Type: multipart/form-data
 
    Fields (all optional):
      category_name, description, is_active, gender, price
      images            — file[] (appended)
      delete_image_urls — JSON array string of URLs to remove
    """
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        cat = UniformCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Uniform category not found", status=404)
 
        if v := request.POST.get("category_name", "").strip():
            cat.category_name = v
        if "description" in request.POST:
            cat.description = request.POST["description"].strip()
        if "is_active" in request.POST:
            cat.is_active = request.POST["is_active"].lower() != "false"
 
        # gender
        if "gender" in request.POST:
            g = request.POST["gender"].strip().lower()
            if g not in VALID_GENDERS:
                return api_response(False, f"gender must be one of: {', '.join(VALID_GENDERS)}", status=400)
            cat.gender = g
 
        # price
        if "price" in request.POST:
            try:
                cat.price = float(request.POST["price"] or 0)
            except ValueError:
                return api_response(False, "price must be a number", status=400)
 
        # delete individual images
        if raw := request.POST.get("delete_image_urls", ""):
            try:
                imgs = list(cat.images or [])
                for url in json.loads(raw):
                    if url in imgs:
                        imgs.remove(url)
                        _s3_delete(url)
                cat.images = imgs
            except Exception:
                pass
 
        # append new images
        if nf := request.FILES.getlist("images"):
            cat.images = (cat.images or []) + [_s3_upload(f, "uniforms") for f in nf]
 
        cat.save()
        return api_response(True, "Uniform category updated", _ser_uniform(cat))
    except Exception as e:
        return api_response(False, str(e), status=500)
 
 
@csrf_exempt
def filter_uniform_categories(request):
    """
    GET /master/uniform/filter/
 
    Public endpoint — NO auth required (used by the mobile app).
 
    Query params (all optional):
      gender       — male | female | unisex
      min_price    — minimum price (inclusive)
      max_price    — maximum price (inclusive)
      search       — partial match on category_name (case-insensitive)
      is_active    — true | false  (default: only active)
 
    Response:
    {
        "success": true,
        "data": [
            {
                "id": "...",
                "category_name": "Royal Traditional",
                "unique_key": "royal_traditional",
                "description": "...",
                "images": [...],
                "gender": "unisex",
                "price": 2500.0,
                "is_active": true
            }
        ]
    }
    """
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        gender    = request.GET.get("gender", "").strip().lower()
        min_price = request.GET.get("min_price", "").strip()
        max_price = request.GET.get("max_price", "").strip()
        search    = request.GET.get("search", "").strip()
        is_active = request.GET.get("is_active", "true").strip().lower()
 
        # Default: only return active categories for mobile
        qs = UniformCategory.objects(is_active=(is_active != "false"))
 
        if gender and gender in VALID_GENDERS:
            # Return exact gender match OR unisex
            from mongoengine.queryset.visitor import Q
            qs = qs.filter(Q(gender=gender) | Q(gender="unisex"))
 
        if min_price:
            try:
                qs = qs.filter(price__gte=float(min_price))
            except ValueError:
                return api_response(False, "min_price must be a number", status=400)
 
        if max_price:
            try:
                qs = qs.filter(price__lte=float(max_price))
            except ValueError:
                return api_response(False, "max_price must be a number", status=400)
 
        if search:
            qs = qs.filter(category_name__icontains=search)
 
        qs = qs.order_by("price")  # cheapest first — makes sense for mobile browse
 
        return api_response(True, "Uniform categories fetched", [_ser_uniform(c) for c in qs])
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

        # -- Reference check --
        from apps.events.models import Event
        in_use = _events_using({"uniform": cat})
        if in_use:
            return api_response(
                False,
                f"Cannot delete '{cat.category_name}' — it is assigned to "
                f"{len(in_use)} active event(s). Reassign the uniform on those "
                f"events first.",
                data={"events_using_this": in_use},
                status=409,
            )

        for url in (cat.images or []):
            _s3_delete(url)
        cat.delete()
        return api_response(True, "Uniform category deleted successfully")

    except Exception as e:
        return api_response(False, str(e), status=500)

# apps/master/views.py — INVENTORY SECTION
#
# Add these views to apps/master/views.py (below the existing uniform views).
# Also add to urls.py (see bottom of this file).
#
# These endpoints let the admin:
#   1. List all uniform categories as inventory items (with stock)
#   2. Get a single inventory item detail
#   3. Update stock quantities for a uniform category
#   4. (Create new uniform category from inventory page — reuse existing create_uniform_category)
#
# Stock shape:  { "S": {"total": 20, "in_use": 5}, "M": {...}, "OS": {...} }
# has_sizes=True  → multiple sizes (S/M/L/XL/XXL or custom)
# has_sizes=False → single "OS" entry (free/one size)


VALID_SIZES = ["XS", "S", "M", "L", "XL", "XXL", "OS"]  # OS = one size / free size
 
 
def _calc_stock_totals(stock: dict) -> dict:
    """Aggregate total, in_use, available across all sizes."""
    total  = sum(v.get("total",  0) for v in stock.values())
    in_use = sum(v.get("in_use", 0) for v in stock.values())
    return {"total": total, "in_use": in_use, "available": total - in_use}
 
 
def _ser_inventory(cat) -> dict:
    """Full serializer for a uniform category used as inventory item."""
    totals = _calc_stock_totals(cat.stock or {})
    return {
        # ── Identity ──────────────────────────────────────────────
        "id":            str(cat.id),
        "category_name": cat.category_name,
        "unique_key":    cat.unique_key,
        "description":   cat.description   or "",
        "images":        cat.images        or [],
        "is_active":     cat.is_active,
        "gender":        cat.gender        or "unisex",
        "price":         cat.price         if cat.price is not None else 0.0,
 
        # ── Inventory ─────────────────────────────────────────────
        "has_sizes":     cat.has_sizes if cat.has_sizes is not None else True,
        "stock":         cat.stock     or {},
 
        # ── Aggregates (computed, not stored) ─────────────────────
        "total_stock":      totals["total"],
        "total_in_use":     totals["in_use"],
        "total_available":  totals["available"],
 
        # ── Meta ──────────────────────────────────────────────────
        "created_at": str(cat.created_at) if cat.created_at else None,
        "updated_at": str(cat.updated_at) if cat.updated_at else None,
    }
 
 
# ── 1. List Inventory ─────────────────────────────────────────────────────────
 
@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_inventory(request):
    """
    GET /master/inventory/
 
    Returns all uniform categories enriched with stock data.
 
    Query params (all optional):
      search      — category_name contains (case-insensitive)
      category    — exact unique_key match
      is_active   — true | false  (default: all)
      low_stock   — true → only items where available < 20% of total
    """
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        qs = UniformCategory.objects()
 
        if s := request.GET.get("search", "").strip():
            qs = qs.filter(category_name__icontains=s)
 
        if cat := request.GET.get("category", "").strip():
            qs = qs.filter(unique_key=cat)
 
        if active := request.GET.get("is_active", "").strip().lower():
            qs = qs.filter(is_active=(active != "false"))
 
        qs = qs.order_by("category_name")
        items = [_ser_inventory(c) for c in qs]
 
        # low_stock filter (post-query since it's computed)
        if request.GET.get("low_stock", "").lower() == "true":
            items = [
                i for i in items
                if i["total_stock"] > 0
                and (i["total_available"] / i["total_stock"]) < 0.2
            ]
 
        return api_response(True, "Inventory fetched", items)
    except Exception as e:
        return api_response(False, str(e), status=500)
 
 
# ── 2. Get Single Inventory Item ──────────────────────────────────────────────
 
@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def get_inventory_item(request, category_id):
    """GET /master/inventory/<category_id>/"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        cat = UniformCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Uniform category not found", status=404)
        return api_response(True, "Inventory item fetched", _ser_inventory(cat))
    except Exception as e:
        return api_response(False, str(e), status=500)
 
 
# ── 3. Update Stock ───────────────────────────────────────────────────────────
 
@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_stock(request, category_id):
    """
    PUT /master/inventory/<category_id>/stock/
 
    Updates stock quantities. Admin can only change "total" (owned quantity).
    "in_use" is managed by the events system — sending it is ignored.
 
    Body:
    {
        "has_sizes": true,
        "stock": {
            "S":  {"total": 20},
            "M":  {"total": 40},
            "L":  {"total": 30},
            "XL": {"total": 10}
        }
    }
 
    For free-size items (has_sizes=false):
    {
        "has_sizes": false,
        "stock": {
            "OS": {"total": 50}
        }
    }
 
    Rules:
    - total cannot be less than in_use (would make available negative)
    - Admin can now also supply in_use to manually correct assignments
    - If in_use is omitted, existing value is preserved
    - Size keys are preserved as provided (allows custom sizes beyond standard set)
    - Removing a size key removes it from stock (use with care)
    """
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        cat = UniformCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Uniform category not found", status=404)
 
        body = json.loads(request.body)
        new_stock  = body.get("stock", {})
        has_sizes  = body.get("has_sizes")
 
        if not isinstance(new_stock, dict):
            return api_response(False, "stock must be an object", status=400)
 
        # Validate each size entry
        existing_stock = cat.stock or {}
        validated_stock = {}
 
        for size_key, size_data in new_stock.items():
            if not isinstance(size_data, dict):
                return api_response(False, f"stock.{size_key} must be an object", status=400)
 
            new_total  = int(size_data.get("total", 0))
            new_in_use = int(size_data.get("in_use", existing_stock.get(size_key, {}).get("in_use", 0)))
 
            if new_total < 0:
                return api_response(False, f"stock.{size_key}.total cannot be negative", status=400)
            if new_in_use < 0:
                return api_response(False, f"stock.{size_key}.in_use cannot be negative", status=400)
            if new_total < new_in_use:
                return api_response(
                    False,
                    f"stock.{size_key}.total ({new_total}) cannot be less than in_use ({new_in_use})",
                    status=400
                )
 
            validated_stock[size_key] = {
                "total":  new_total,
                "in_use": new_in_use,
            }
 
        cat.stock = validated_stock
 
        if has_sizes is not None:
            cat.has_sizes = bool(has_sizes)
 
        cat.save()
        return api_response(True, "Stock updated successfully", _ser_inventory(cat))
 
    except (json.JSONDecodeError, ValueError) as e:
        return api_response(False, f"Invalid request body: {e}", status=400)
    except Exception as e:
        return api_response(False, str(e), status=500)
 
 
# ── 4. Increment / Decrement in_use (called by events system) ────────────────
 
@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def adjust_in_use(request, category_id):
    """
    POST /master/inventory/<category_id>/adjust/
 
    Called when assigning/returning uniforms to events.
    Increments or decrements in_use for a specific size.
 
    Body:
    {
        "size":   "M",
        "delta":  3      ← positive = assign, negative = return
    }
 
    Returns 400 if assignment would exceed available stock.
    """
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        cat = UniformCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Uniform category not found", status=404)
 
        body  = json.loads(request.body)
        size  = body.get("size", "").strip()
        delta = int(body.get("delta", 0))
 
        if not size:
            return api_response(False, "size is required", status=400)
        if delta == 0:
            return api_response(False, "delta cannot be 0", status=400)
 
        stock = cat.stock or {}
        if size not in stock:
            return api_response(False, f"Size '{size}' not found in stock", status=404)
 
        entry = stock[size]
        new_in_use = entry.get("in_use", 0) + delta
 
        if new_in_use < 0:
            return api_response(False, f"Cannot return more than currently in use for size {size}", status=400)
        if new_in_use > entry.get("total", 0):
            available = entry.get("total", 0) - entry.get("in_use", 0)
            return api_response(
                False,
                f"Not enough stock for size {size}. Available: {available}, Requested: {delta}",
                status=400
            )
 
        stock[size]["in_use"] = new_in_use
        cat.stock = stock
        cat.save()
 
        return api_response(True, "Stock adjusted", _ser_inventory(cat))
 
    except (json.JSONDecodeError, ValueError) as e:
        return api_response(False, f"Invalid request body: {e}", status=400)
    except Exception as e:
        return api_response(False, str(e), status=500)
 
 
# ── 5. Get Inventory Summary (dashboard widget) ───────────────────────────────
 
@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def inventory_summary(request):
    """
    GET /master/inventory/summary/
 
    Returns high-level stats for a dashboard widget.
    {
        "total_categories": 12,
        "total_items":      450,
        "total_in_use":     280,
        "total_available":  170,
        "low_stock_count":  3
    }
    """
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        cats = UniformCategory.objects(is_active=True)
 
        total_categories = 0
        total_items      = 0
        total_in_use     = 0
        low_stock_count  = 0
 
        for cat in cats:
            total_categories += 1
            t = _calc_stock_totals(cat.stock or {})
            total_items   += t["total"]
            total_in_use  += t["in_use"]
            if t["total"] > 0 and (t["available"] / t["total"]) < 0.2:
                low_stock_count += 1
 
        return api_response(True, "Inventory summary", {
            "total_categories": total_categories,
            "total_items":      total_items,
            "total_in_use":     total_in_use,
            "total_available":  total_items - total_in_use,
            "low_stock_count":  low_stock_count,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)




# ══════════════════════════════════════════════════════════════════════════════
# CREW MEMBERS
# ══════════════════════════════════════════════════════════════════════════════

def _ser_crew(m):
    return {
        "id":         str(m.id),
        "name":       m.name,
        "image":      m.image or "",
        "is_active":  m.is_active,
        "created_at": str(m.created_at) if m.created_at else None,
        "updated_at": str(m.updated_at) if m.updated_at else None,
    }


@csrf_exempt
def list_crew_members_public(request):
    """GET /master/crew/public/ — no auth, used by mobile app"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        qs = CrewMember.objects(is_active=True).order_by("name")
        return api_response(True, "Crew members fetched", [_ser_crew(m) for m in qs])
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_crew_members(request):
    """GET /master/crew/ — admin, returns all (active + inactive)"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        qs = CrewMember.objects().order_by("name")
        return api_response(True, "Crew members fetched", [_ser_crew(m) for m in qs])
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_crew_member(request):
    """POST /master/crew/create/ — multipart/form-data
    Fields: name*(req), image*(file, req), tier, order, is_active"""
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        name = request.POST.get("name", "").strip()
        if not name:
            return api_response(False, "name is required", status=400)

        img_file = request.FILES.get("image")
        if not img_file:
            return api_response(False, "image file is required", status=400)

        is_active = request.POST.get("is_active", "true").lower() != "false"

        image_url = upload_file_to_s3(img_file, "staff/crew")
        member = CrewMember(name=name, is_active=is_active, image=image_url)
        member.save()
        return api_response(True, "Crew member created", _ser_crew(member), status=201)
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_crew_member(request, member_id):
    """PUT /master/crew/<member_id>/update/ — multipart/form-data
    Fields (all optional): name, image(file), tier, order, is_active"""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        member = CrewMember.objects(id=member_id).first()
        if not member:
            return api_response(False, "Crew member not found", status=404)

        if v := request.POST.get("name", "").strip():
            member.name = v

        if img_file := request.FILES.get("image"):
            delete_file_from_s3(member.image or "")
            member.image = upload_file_to_s3(img_file, "staff/crew")

        if "is_active" in request.POST:
            member.is_active = request.POST["is_active"].lower() != "false"

        member.save()
        return api_response(True, "Crew member updated", _ser_crew(member))
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_crew_member(request, member_id):
    """DELETE /master/crew/<member_id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Invalid method", status=405)
    try:
        member = CrewMember.objects(id=member_id).first()
        if not member:
            return api_response(False, "Crew member not found", status=404)
        delete_file_from_s3(member.image or "")
        member.delete()
        return api_response(True, "Crew member deleted")
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
# 3b. CREW PACKAGES  (Luxury / Premium)
# ══════════════════════════════════════════════════════════════════════════════

from .models import CrewPackage

_PACKAGE_TYPES = {"LUXURY", "PREMIUM"}


def _ser_crew_package(p) -> dict:
    return {
        "id":               str(p.id),
        "type":             p.type,
        "price_per_person": p.price_per_person,
        "standard_hours":   p.standard_hours,
        "extra_hour_rate":  p.extra_hour_rate,
        "last_updated":     str(p.last_updated),
    }


@csrf_exempt
def list_crew_packages(request):
    """
    GET /api/master/packages/
    Returns both crew packages (LUXURY + PREMIUM).
    No auth — mobile uses this to display pricing.
    """
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    try:
        packages = CrewPackage.objects().order_by("type")
        return api_response(True, "Crew packages fetched", [_ser_crew_package(p) for p in packages])
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def upsert_crew_package(request, package_type):
    """
    PUT /api/master/packages/<package_type>/
    Body: { "price_per_person": 20000, "standard_hours": 8 }
    Creates LUXURY or PREMIUM document if it doesn't exist yet.
    """
    if request.method != "PUT":
        return api_response(False, "Method not allowed", status=405)
    package_type = package_type.upper()
    if package_type not in _PACKAGE_TYPES:
        return api_response(False, f"package_type must be one of {_PACKAGE_TYPES}", status=400)
    try:
        body = json.loads(request.body)
        pkg  = CrewPackage.objects(type=package_type).first()
        if not pkg:
            pkg = CrewPackage(type=package_type)
        if "price_per_person" in body:
            pkg.price_per_person = float(body["price_per_person"])
        if "standard_hours" in body:
            pkg.standard_hours = int(body["standard_hours"])
        pkg.save()
        return api_response(True, f"{package_type} package updated", _ser_crew_package(pkg))
    except Exception as e:
        return api_response(False, str(e), status=500)


# ══════════════════════════════════════════════════════════════════════════════
# 4. PAYMENT TERMS
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_STAFF_PRICING = {"LUXURY": 20000, "PREMIUM": 10000}
STAFF_PACKAGE_TYPES = ["LUXURY", "PREMIUM"]


def _ser_payment_terms(terms):
    return {
        "advancePercentage":      terms.advancePercentage,
        "staff_pricing":          terms.staff_pricing or DEFAULT_STAFF_PRICING,
        "default_hours_per_day":  terms.default_hours_per_day if terms.default_hours_per_day is not None else 5.0,
        "overtime_rate_per_hour": terms.overtime_rate_per_hour if terms.overtime_rate_per_hour is not None else 3000.0,
        "lastUpdatedAt":          str(terms.lastUpdatedAt),
    }


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
            return api_response(True, "No payment terms set", {
                "advancePercentage": None,
                "staff_pricing": DEFAULT_STAFF_PRICING,
                "default_hours_per_day": 5.0,
                "overtime_rate_per_hour": 3000.0,
            })
        return api_response(True, "Payment terms fetched", _ser_payment_terms(terms))
    except Exception as e:
        return api_response(False, str(e), status=500)

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_payment_terms(request):
    """PUT /master/payment/update/
    Body: {
        "advancePercentage": 30,
        "staff_pricing": {"LUXURY": 20000, "PREMIUM": 10000},
        "default_hours_per_day": 5,
        "overtime_rate_per_hour": 3000
    }"""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        body = json.loads(request.body)

        terms = PaymentTerms.objects().first()
        if not terms:
            terms = PaymentTerms(advancePercentage=0)

        if "advancePercentage" in body:
            pct = float(body["advancePercentage"])
            if not (0 <= pct <= 100):
                return api_response(False, "advancePercentage must be 0-100", status=400)
            terms.advancePercentage = pct

        if "staff_pricing" in body:
            pricing = body["staff_pricing"]
            if not isinstance(pricing, dict):
                return api_response(False, "staff_pricing must be an object", status=400)
            validated = {}
            for pkg_type in STAFF_PACKAGE_TYPES:
                if pkg_type in pricing:
                    try:
                        validated[pkg_type] = float(pricing[pkg_type])
                    except (ValueError, TypeError):
                        return api_response(False, f"staff_pricing.{pkg_type} must be a number", status=400)
            terms.staff_pricing = {**(terms.staff_pricing or DEFAULT_STAFF_PRICING), **validated}

        if "default_hours_per_day" in body:
            h = float(body["default_hours_per_day"])
            if h <= 0:
                return api_response(False, "default_hours_per_day must be greater than 0", status=400)
            terms.default_hours_per_day = h

        if "overtime_rate_per_hour" in body:
            terms.overtime_rate_per_hour = float(body["overtime_rate_per_hour"])

        terms.save()
        return api_response(True, "Payment terms updated", _ser_payment_terms(terms))
    except Exception as e:
        return api_response(False, str(e), status=500)


# ══════════════════════════════════════════════════════════════════════════════
# COUPONS
# ══════════════════════════════════════════════════════════════════════════════

from datetime import timezone as tz


def _ser_coupon(c):
    return {
        "id":             str(c.id),
        "code":           c.code,
        "description":    c.description or "",
        "discount_type":  c.discount_type,
        "discount_value": c.discount_value,
        "usage_limit":    c.usage_limit,
        "used_count":     c.used_count,
        "is_active":      c.is_active,
        "expiry_date":    str(c.expiry_date) if c.expiry_date else None,
        "created_at":     str(c.created_at) if c.created_at else None,
        "updated_at":     str(c.updated_at) if c.updated_at else None,
    }


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_coupons(request):
    """GET /master/coupons/"""
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        qs = Coupon.objects().order_by("-created_at")
        return api_response(True, "Coupons fetched", [_ser_coupon(c) for c in qs])
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_coupon(request):
    """POST /master/coupons/create/
    Body: { code, description, discount_type, discount_value, usage_limit, is_active, expiry_date }"""
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        body = json.loads(request.body)

        code = body.get("code", "").strip().upper()
        if not code:
            return api_response(False, "code is required", status=400)
        if Coupon.objects(code=code).first():
            return api_response(False, f"Coupon code '{code}' already exists", status=400)

        discount_type = body.get("discount_type", "FLAT").strip().upper()
        if discount_type not in ("FLAT", "PERCENTAGE"):
            return api_response(False, "discount_type must be FLAT or PERCENTAGE", status=400)

        discount_value = body.get("discount_value")
        if discount_value is None:
            return api_response(False, "discount_value is required", status=400)
        discount_value = float(discount_value)
        if discount_type == "PERCENTAGE" and not (0 < discount_value <= 100):
            return api_response(False, "Percentage discount must be between 1 and 100", status=400)

        expiry_date = None
        if body.get("expiry_date"):
            from dateutil import parser as dateparser
            expiry_date = dateparser.parse(body["expiry_date"])

        coupon = Coupon(
            code=code,
            description=body.get("description", "").strip(),
            discount_type=discount_type,
            discount_value=discount_value,
            usage_limit=int(body.get("usage_limit", 1)),
            is_active=bool(body.get("is_active", True)),
            expiry_date=expiry_date,
        )
        coupon.save()
        return api_response(True, "Coupon created", _ser_coupon(coupon), status=201)
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_coupon(request, coupon_id):
    """PUT /master/coupons/<coupon_id>/update/"""
    if request.method != "PUT":
        return api_response(False, "Invalid method", status=405)
    try:
        coupon = Coupon.objects(id=coupon_id).first()
        if not coupon:
            return api_response(False, "Coupon not found", status=404)

        body = json.loads(request.body)

        if "description" in body:
            coupon.description = body["description"].strip()

        if "discount_type" in body:
            dt = body["discount_type"].strip().upper()
            if dt not in ("FLAT", "PERCENTAGE"):
                return api_response(False, "discount_type must be FLAT or PERCENTAGE", status=400)
            coupon.discount_type = dt

        if "discount_value" in body:
            coupon.discount_value = float(body["discount_value"])

        if "usage_limit" in body:
            coupon.usage_limit = int(body["usage_limit"])

        if "is_active" in body:
            coupon.is_active = bool(body["is_active"])

        if "expiry_date" in body:
            if body["expiry_date"]:
                from dateutil import parser as dateparser
                coupon.expiry_date = dateparser.parse(body["expiry_date"])
            else:
                coupon.expiry_date = None

        coupon.save()
        return api_response(True, "Coupon updated", _ser_coupon(coupon))
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_coupon(request, coupon_id):
    """DELETE /master/coupons/<coupon_id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Invalid method", status=405)
    try:
        coupon = Coupon.objects(id=coupon_id).first()
        if not coupon:
            return api_response(False, "Coupon not found", status=404)
        coupon.delete()
        return api_response(True, "Coupon deleted")
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
def get_payment_config_public(request):
    """GET /master/payment/config/ — NO auth, public endpoint for mobile app.

    Returns all pricing config the mobile app needs to calculate event costs:
      - packages: LUXURY and PREMIUM crew package pricing
      - default_hours_per_day
      - overtime_rate_per_hour
      - advancePercentage

    Response:
    {
        "success": true,
        "data": {
            "advancePercentage": 30,
            "packages": [
                {"type": "LUXURY", "price_per_person": 20000, "standard_hours": 8, "extra_hour_rate": 2500},
                {"type": "PREMIUM", "price_per_person": 10000, "standard_hours": 8, "extra_hour_rate": 1250}
            ],
            "default_hours_per_day": 5.0,
            "overtime_rate_per_hour": 3000.0
        }
    }
    """
    if request.method != "GET":
        return api_response(False, "Invalid method", status=405)
    try:
        terms = PaymentTerms.objects().first()
        packages = CrewPackage.objects().order_by("type")
        packages_data = [
            {
                "type": p.type,
                "price_per_person": p.price_per_person,
                "standard_hours": p.standard_hours,
                "extra_hour_rate": round(p.price_per_person / p.standard_hours, 2) if p.standard_hours else 0,
            }
            for p in packages
        ]
        if not terms:
            return api_response(True, "Payment config fetched", {
                "advancePercentage":      0,
                "packages":               packages_data,
                "staff_pricing":          DEFAULT_STAFF_PRICING,
                "default_hours_per_day":  5.0,
                "overtime_rate_per_hour": 3000.0,
            })
        return api_response(True, "Payment config fetched", {
            "advancePercentage":      terms.advancePercentage,
            "packages":               packages_data,
            "staff_pricing":          terms.staff_pricing or DEFAULT_STAFF_PRICING,
            "default_hours_per_day":  terms.default_hours_per_day  if terms.default_hours_per_day  is not None else 5.0,
            "overtime_rate_per_hour": terms.overtime_rate_per_hour if terms.overtime_rate_per_hour is not None else 3000.0,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
def validate_coupon(request):
    """POST /master/coupons/validate/ — no auth, called from mobile during checkout.

    Validates the coupon and returns its details so the frontend can
    calculate the discount and show a remove option.
    The actual used_count is only incremented when the event is confirmed.

    Request body:  { "code": "SAVE20" }

    Response:
    {
        "success": true,
        "data": {
            "code": "SAVE20",
            "description": "20% off for new clients",
            "discount_type": "PERCENTAGE",   // FLAT | PERCENTAGE
            "discount_value": 20,
            "usage_limit": 2,
            "is_active": true
        }
    }

    Frontend calculation:
      PERCENTAGE → discount = (discount_value / 100) × total_amount
      FLAT       → discount = discount_value  (fixed rupee deduction)
      final_amount = total_amount - discount  (never below 0)

    To remove the coupon: no API call needed — just clear it from frontend state.
    """
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        body = json.loads(request.body)
        code = body.get("code", "").strip().upper()
        if not code:
            return api_response(False, "code is required", status=400)

        coupon = Coupon.objects(code=code).first()
        if not coupon:
            return api_response(False, "Invalid coupon code", status=404)
        if not coupon.is_active:
            return api_response(False, "This coupon is no longer active", status=400)
        if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
            return api_response(False, "This coupon has reached its usage limit", status=400)
        if coupon.expiry_date and coupon.expiry_date < datetime.utcnow():
            return api_response(False, "This coupon has expired", status=400)

        return api_response(True, "Coupon is valid", {
            "code":           coupon.code,
            "description":    coupon.description or "",
            "discount_type":  coupon.discount_type,
            "discount_value": coupon.discount_value,
            "usage_limit":    coupon.usage_limit,
            "is_active":      coupon.is_active,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
def apply_coupon(request):
    """POST /master/coupons/apply/ — NO auth, called from mobile at checkout.

    Validates the coupon AND calculates the exact discount for the given total.

    Request body:
    {
        "code": "SAVE20",
        "total_amount": 75000
    }

    Response (success):
    {
        "success": true,
        "data": {
            "code": "SAVE20",
            "discount_type": "PERCENTAGE",   // FLAT | PERCENTAGE
            "discount_value": 20,
            "discount_amount": 15000,         // actual rupees deducted
            "original_amount": 75000,
            "final_amount": 60000,
            "description": "20% off for new clients"
        }
    }

    How discount is calculated:
      FLAT       → discount_amount = discount_value  (e.g. ₹5000 flat off)
      PERCENTAGE → discount_amount = (discount_value / 100) * total_amount
                   capped so final_amount never goes below 0
    """
    if request.method != "POST":
        return api_response(False, "Invalid method", status=405)
    try:
        body = json.loads(request.body)
        code         = body.get("code", "").strip().upper()
        total_amount = body.get("total_amount")

        if not code:
            return api_response(False, "code is required", status=400)
        if total_amount is None:
            return api_response(False, "total_amount is required", status=400)

        total_amount = float(total_amount)
        if total_amount < 0:
            return api_response(False, "total_amount must be >= 0", status=400)

        # ── Validate coupon ────────────────────────────────────────
        coupon = Coupon.objects(code=code).first()
        if not coupon:
            return api_response(False, "Invalid coupon code", status=404)
        if not coupon.is_active:
            return api_response(False, "This coupon is no longer active", status=400)
        if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
            return api_response(False, "This coupon has reached its usage limit", status=400)
        if coupon.expiry_date and coupon.expiry_date < datetime.utcnow():
            return api_response(False, "This coupon has expired", status=400)

        # ── Calculate discount ─────────────────────────────────────
        if coupon.discount_type == "PERCENTAGE":
            discount_amount = round((coupon.discount_value / 100) * total_amount, 2)
        else:  # FLAT
            discount_amount = round(coupon.discount_value, 2)

        # Ensure discount never exceeds the total
        discount_amount = min(discount_amount, total_amount)
        final_amount    = round(total_amount - discount_amount, 2)

        return api_response(True, "Coupon applied successfully", {
            "code":            coupon.code,
            "description":     coupon.description or "",
            "discount_type":   coupon.discount_type,
            "discount_value":  coupon.discount_value,
            "discount_amount": discount_amount,
            "original_amount": total_amount,
            "final_amount":    final_amount,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)




