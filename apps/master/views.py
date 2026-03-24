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
        _s3_delete(theme.cover_image or "")
        for u in (theme.gallery_images or []): _s3_delete(u)
        theme.delete()
        return api_response(True, "Theme deleted", {})
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
        for u in (cat.images or []): _s3_delete(u)
        cat.delete()
        return api_response(True, "Uniform category deleted", {})
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




