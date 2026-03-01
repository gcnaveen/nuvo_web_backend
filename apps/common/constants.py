from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    CLIENT = "CLIENT"
    STAFF = "STAFF"
    MAKEUP_ARTIST = "MAKEUP_ARTIST"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"


class SubscriptionPlan(str, Enum):
    SILVER = "SILVER"
    BRONZE = "BRONZE"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"
    DIAMOND = "DIAMOND"