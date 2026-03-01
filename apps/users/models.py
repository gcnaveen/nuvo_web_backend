import uuid
from datetime import datetime
from mongoengine import (
    Document,
    StringField,
    EmailField,
    DateTimeField
)
from mongoengine import FloatField, IntField, ListField, URLField
from apps.common.constants import UserRole, UserStatus
from mongoengine import ReferenceField
from apps.common.constants import SubscriptionPlan


class User(Document):
    meta = {"collection": "users"}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))

    email = EmailField(required=True, unique=True)
    phone_number = StringField(required=True, unique=True)

    role = StringField(
        choices=[r.value for r in UserRole],
        required=True
    )

    status = StringField(
        choices=[s.value for s in UserStatus],
        default=UserStatus.ACTIVE.value
    )

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    


class ClientProfile(Document):
    meta = {"collection": "client_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    city = StringField()
    state = StringField()
    country = StringField()

    subscription_plan = StringField(
        choices=[p.value for p in SubscriptionPlan],
        default=SubscriptionPlan.SILVER.value
    )

    joined_date = DateTimeField(default=datetime.utcnow)




class StaffProfile(Document):
    meta = {"collection": "staff_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    stage_name = StringField()
    gender = StringField()
    date_of_birth = DateTimeField()

    city = StringField()
    state = StringField()
    country = StringField()

    profile_picture = URLField()
    gallery_images = ListField(URLField())

    height = FloatField()
    weight = FloatField()

    package = StringField()
    price_of_staff = FloatField()
    experience_in_years = IntField()

    joined_date = DateTimeField(default=datetime.utcnow)


class MakeupArtistProfile(Document):
    meta = {"collection": "makeup_artist_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    gender = StringField()
    makeup_speciality = StringField()

    city = StringField()
    state = StringField()
    country = StringField()

    experience_in_years = IntField()

    joined_date = DateTimeField(default=datetime.utcnow)