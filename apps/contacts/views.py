import json
from datetime import datetime

from django.views.decorators.csrf import csrf_exempt
from apps.accounts.decorators import require_auth, require_role
from .models import Contact, ContactCategory


def api_response(success, message, data=None, status=200):
    import json as _json
    from django.http import JsonResponse
    return JsonResponse(
        {"success": success, "message": message, "data": data if data is not None else {}},
        status=status,
    )


def _ser_category(cat):
    return {
        "id":         cat.id,
        "name":       cat.name,
        "created_at": str(cat.created_at),
    }


def _ser_contact(c):
    return {
        "id":               c.id,
        "category":         c.category or "",
        "title":            c.title or "",
        "full_name":        c.full_name,
        "contact_number_1": c.contact_number_1,
        "contact_number_2": c.contact_number_2 or "",
        "email":            c.email or "",
        "address":          c.address or "",
        "company_name":     c.company_name or "",
        "department_name":  c.department_name or "",
        "designation":      c.designation or "",
        "referred_by":      c.referred_by or "",
        "created_at":       str(c.created_at),
        "updated_at":       str(c.updated_at),
    }


# ══════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_categories(request):
    """GET /api/contacts/categories/"""
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    cats = ContactCategory.objects().order_by("name")
    return api_response(True, "Categories fetched", [_ser_category(c) for c in cats])


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_category(request):
    """POST /api/contacts/categories/create/"""
    if request.method != "POST":
        return api_response(False, "Method not allowed", status=405)
    try:
        body = json.loads(request.body)
        name = (body.get("name") or "").strip()
        if not name:
            return api_response(False, "name is required", status=400)
        if ContactCategory.objects(name__iexact=name).first():
            return api_response(False, "Category already exists", status=400)
        cat = ContactCategory(name=name)
        cat.save()
        return api_response(True, "Category created", _ser_category(cat), status=201)
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_category(request, category_id):
    """DELETE /api/contacts/categories/<id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Method not allowed", status=405)
    try:
        cat = ContactCategory.objects(id=category_id).first()
        if not cat:
            return api_response(False, "Category not found", status=404)
        cat.delete()
        return api_response(True, "Category deleted")
    except Exception as e:
        return api_response(False, str(e), status=500)


# ══════════════════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_contacts(request):
    """
    GET /api/contacts/
    Query params:
      ?category=<name>   — filter by category (optional)
      ?search=<text>     — search by name / phone / email (optional)
    """
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    try:
        qs = Contact.objects()
        category = request.GET.get("category", "").strip()
        if category:
            qs = qs.filter(category__iexact=category)
        search = request.GET.get("search", "").strip()
        if search:
            import re
            pattern = re.compile(search, re.IGNORECASE)
            # MongoEngine doesn't support OR on multiple fields in one filter call;
            # fetch then filter in Python for simplicity.
            qs = [c for c in qs if (
                pattern.search(c.full_name or "") or
                pattern.search(c.contact_number_1 or "") or
                pattern.search(c.email or "") or
                pattern.search(c.company_name or "")
            )]
            return api_response(True, "Contacts fetched", [_ser_contact(c) for c in qs])
        return api_response(True, "Contacts fetched", [_ser_contact(c) for c in qs.order_by("full_name")])
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_contact(request):
    """POST /api/contacts/create/"""
    if request.method != "POST":
        return api_response(False, "Method not allowed", status=405)
    try:
        body = json.loads(request.body)
        full_name        = (body.get("full_name") or "").strip()
        contact_number_1 = (body.get("contact_number_1") or "").strip()
        if not full_name:
            return api_response(False, "full_name is required", status=400)
        if not contact_number_1:
            return api_response(False, "contact_number_1 is required", status=400)

        contact = Contact(
            category         = (body.get("category") or "").strip() or None,
            title            = (body.get("title") or "").strip() or None,
            full_name        = full_name,
            contact_number_1 = contact_number_1,
            contact_number_2 = (body.get("contact_number_2") or "").strip() or None,
            email            = (body.get("email") or "").strip() or None,
            address          = (body.get("address") or "").strip() or None,
            company_name     = (body.get("company_name") or "").strip() or None,
            department_name  = (body.get("department_name") or "").strip() or None,
            designation      = (body.get("designation") or "").strip() or None,
            referred_by      = (body.get("referred_by") or "").strip() or None,
        )
        contact.save()
        return api_response(True, "Contact created", _ser_contact(contact), status=201)
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def get_contact(request, contact_id):
    """GET /api/contacts/<id>/"""
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    c = Contact.objects(id=contact_id).first()
    if not c:
        return api_response(False, "Contact not found", status=404)
    return api_response(True, "Contact fetched", _ser_contact(c))


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_contact(request, contact_id):
    """PUT /api/contacts/<id>/update/"""
    if request.method != "PUT":
        return api_response(False, "Method not allowed", status=405)
    try:
        c = Contact.objects(id=contact_id).first()
        if not c:
            return api_response(False, "Contact not found", status=404)
        body = json.loads(request.body)

        FIELDS = [
            "category", "title", "full_name", "contact_number_1",
            "contact_number_2", "email", "address", "company_name",
            "department_name", "designation", "referred_by",
        ]
        for field in FIELDS:
            if field in body:
                setattr(c, field, (body[field] or "").strip() or None)

        if not c.full_name:
            return api_response(False, "full_name cannot be empty", status=400)
        if not c.contact_number_1:
            return api_response(False, "contact_number_1 cannot be empty", status=400)

        c.updated_at = datetime.utcnow()
        c.save()
        return api_response(True, "Contact updated", _ser_contact(c))
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_contact(request, contact_id):
    """DELETE /api/contacts/<id>/delete/"""
    if request.method != "DELETE":
        return api_response(False, "Method not allowed", status=405)
    try:
        c = Contact.objects(id=contact_id).first()
        if not c:
            return api_response(False, "Contact not found", status=404)
        c.delete()
        return api_response(True, "Contact deleted")
    except Exception as e:
        return api_response(False, str(e), status=500)
