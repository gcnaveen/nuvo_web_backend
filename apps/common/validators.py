import re


def validate_email(email):
    pattern = r"[^@]+@[^@]+\.[^@]+"
    return re.match(pattern, email)


def validate_phone(phone):
    return phone.isdigit() and len(phone) >= 10


def validate_required_fields(data, fields):
    for field in fields:
        if not data.get(field):
            return False, f"{field} is required"
    return True, None