import uuid
from datetime import datetime
from mongoengine import (
    Document, StringField, DateTimeField,
)


class ContactCategory(Document):
    meta = {"collection": "contact_categories"}

    id         = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    name       = StringField(required=True, unique=True)
    created_at = DateTimeField(default=datetime.utcnow)


class Contact(Document):
    meta = {"collection": "contacts"}

    TITLE_CHOICES = ("Mr", "Ms", "Mrs", "Dr")

    id                = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    category          = StringField()          # category name string for easy filtering
    title             = StringField()          # Mr / Ms / Mrs / Dr
    full_name         = StringField(required=True)
    contact_number_1  = StringField(required=True)
    contact_number_2  = StringField()
    email             = StringField()
    address           = StringField()
    company_name      = StringField()
    department_name   = StringField()
    designation       = StringField()
    referred_by       = StringField()
    created_at        = DateTimeField(default=datetime.utcnow)
    updated_at        = DateTimeField(default=datetime.utcnow)
