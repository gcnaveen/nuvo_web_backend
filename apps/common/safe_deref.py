# apps/common/safe_deref.py
#
# Safe MongoEngine dereference helpers.
#
# Problem:
#   When a referenced document is deleted (e.g. a UniformCategory that an
#   Event points to), MongoEngine raises:
#       OperationError: Trying to dereference unknown document
#       DBRef('uniform_categories', '<id>')
#   This crashes the entire API response even though the event itself is fine.
#
# Solution:
#   Wrap every .field access on a ReferenceField in safe_ref() or safe_attr().
#   On any error (deleted doc, network hiccup, etc.) these return None / default.
#
# Usage:
#   from apps.common.safe_deref import safe_ref, safe_attr, safe_id
#
#   # Instead of:    event.uniform.category_name   (crashes if uniform deleted)
#   # Use:           safe_attr(event.uniform, "category_name")  -> None on error
#
#   # Instead of:    str(event.uniform.id)
#   # Use:           safe_id(event.uniform)  -> None on error


def safe_ref(ref_field):
    """
    Safely dereference a MongoEngine ReferenceField.
    Returns the dereferenced document, or None if it no longer exists.

    Usage:
        doc = safe_ref(event.uniform)
        if doc:
            name = doc.category_name
    """
    if ref_field is None:
        return None
    try:
        # Accessing any attribute forces MongoEngine to actually dereference.
        # We use 'id' because it's always present and cheapest.
        _ = ref_field.id
        return ref_field
    except Exception:
        return None


def safe_attr(ref_field, attr: str, default=None):
    """
    Safely read a single attribute from a ReferenceField.
    Returns default (None) if the document was deleted or can't be loaded.

    Usage:
        name = safe_attr(event.uniform, "category_name", "Unknown")
    """
    doc = safe_ref(ref_field)
    if doc is None:
        return default
    try:
        return getattr(doc, attr, default)
    except Exception:
        return default


def safe_id(ref_field) -> str | None:
    """
    Safely get the string ID of a ReferenceField without dereferencing.
    MongoEngine stores the raw DBRef even for deleted documents, so we can
    often still read the id from it without a DB round-trip.

    Returns the id string, or None if unavailable.

    Usage:
        uid = safe_id(event.uniform)   # "4ac3d0fc-..." or None
    """
    if ref_field is None:
        return None
    try:
        # Fast path: already loaded — use .id directly
        return str(ref_field.id)
    except Exception:
        pass
    try:
        # Fallback: read from the raw DBRef without triggering a dereference
        from mongoengine.base.datastructures import BaseDict
        dbref = ref_field._data if hasattr(ref_field, "_data") else None
        if dbref and hasattr(dbref, "id"):
            return str(dbref.id)
    except Exception:
        pass
    return None


def safe_list_refs(ref_list: list) -> list:
    """
    Filter a ListField(ReferenceField) to only valid (non-deleted) documents.
    Silently drops any entry whose referenced document no longer exists.

    Usage:
        valid_crew = safe_list_refs(event.crew_members)
        for member in valid_crew:
            print(member.full_name)
    """
    result = []
    for ref in (ref_list or []):
        doc = safe_ref(ref)
        if doc is not None:
            result.append(doc)
    return result