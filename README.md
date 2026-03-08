# nuvo_web_backend

## Local Setup (macOS / Linux)

```bash
# From repo root (Nuvo_backend)
cd nuvo_web_backend
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

---

## 📦 Project Architecture

```
apps/
│
├── accounts/     → Auth, OTP, JWT, Middleware
├── users/        → Profile & Business Logic
├── common/       → Utilities (S3, PhonePe, Location server)
├── master/       → Event Themes, Uniforms, Subscriptions, Payment Terms
└── events/       → Event booking, crew allocation, payments, live tracking
```

---

## ⚙️ Required Settings

Add these to your `config/settings/base.py` (or use environment variables):

```python
# AWS S3
AWS_ACCESS_KEY_ID     = "..."
AWS_SECRET_ACCESS_KEY = "..."
AWS_STORAGE_BUCKET_NAME = "..."
AWS_S3_REGION_NAME    = "ap-south-1"

# PhonePe Payment Gateway
PHONEPE_MERCHANT_ID  = "PGTESTPAYUAT"          # sandbox merchant ID
PHONEPE_SALT_KEY     = "your-salt-key"
PHONEPE_SALT_INDEX   = 1
PHONEPE_BASE_URL     = "https://api-preprod.phonepe.com/apis/pg-sandbox"
PHONEPE_REDIRECT_URL = "https://yourdomain.com/api/events/payment/callback/"
PHONEPE_CALLBACK_URL = "https://yourdomain.com/api/events/payment/webhook/"

# C++ Location Tracking Server
LOCATION_SERVER_URL     = "http://<SERVER_HOST>:9090"
LOCATION_SERVER_TIMEOUT = 5   # seconds
```

---

## 🔐 Authentication Flow

### Client (Mobile App)

```
send-otp  (email required, phone optional)
    ↓
verify-otp → account auto-created + auto-approved on first login
    ↓
If profile not completed → complete-profile
    ↓
Normal app usage
```

### Staff / Makeup Artist

```
register/staff-makeup  → account created with status PENDING
    ↓
Admin approves via admin/approve-user
    ↓
send-otp → verify-otp → tokens issued
    ↓
Normal app usage
```

### Admin

```
register/admin  (full_name, email, phone, password)
    ↓
Existing approved admin approves via admin/approve-user
    ↓
send-otp → verify-otp → tokens issued
    ↓
Full admin access
```

---

## 🌍 Base URL

`http://127.0.0.1:8000/api/`

All protected APIs require:

`Authorization: Bearer <ACCESS_TOKEN>`

---

## 🔐 AUTH APIs

### 1️⃣ Send OTP

`POST /auth/send-otp/`

**Roles:** `CLIENT` · `STAFF` · `MAKEUP_ARTIST` · `ADMIN`

> **CLIENT:** Only `email` is required. `phone_number` is optional. Account does not need to exist yet.
>
> **STAFF / MAKEUP_ARTIST / ADMIN:** Account must already exist. The API verifies the email or phone matches a known account before sending the OTP. Blocked accounts are rejected here.

**Body**

```json
{ "email": "user@gmail.com" }
```

**Response**

```json
{
  "success": true,
  "message": "OTP sent successfully",
  "data": {}
}
```

---

### 2️⃣ Verify OTP (Login)

`POST /auth/verify-otp/`

> **CLIENT:** Account is auto-created and auto-approved on first login. `phone_number` required only on first login.
>
> **STAFF / MAKEUP_ARTIST / ADMIN:** Returns `403` if account is still `PENDING`.

**Body**

```json
{ "email": "user@gmail.com", "otp": "123456" }
```

**Response**

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": ".........",
    "refresh_token": ".........",
    "user": {
      "id": "ee7c55fc-4d49-4aff-b22a-a9df6937a178",
      "email": "user@gmail.com",
      "phone_number": "9999999999",
      "full_name": "",
      "role": "CLIENT",
      "status": "ACTIVE",
      "is_approved": true,
      "profile_completed": false
    }
  }
}
```

**Error — Pending Approval (403)**

```json
{
  "success": false,
  "message": "Your account is pending admin approval. You will be notified once approved.",
  "data": {}
}
```

---

### 3️⃣ Refresh Token

`POST /auth/refresh-token/`

**Body**

```json
{ "refresh_token": "your_refresh_token" }
```

**Response**

```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "data": { "access_token": "......" }
}
```

---

### 4️⃣ Logout

`POST /auth/logout/`

**Body**

```json
{ "refresh_token": "your_refresh_token" }
```

Blacklists the refresh token.

**Response**

```json
{ "success": true, "message": "Logged out successfully", "data": {} }
```

---

### 5️⃣ Resend OTP

`POST /auth/resend-otp/`

60-second cooldown · 5-minute expiry

**Body**

```json
{ "email": "user@gmail.com" }
```

---

### 6️⃣ Get Logged-in User

`GET /auth/me/`

**Response**

```json
{
  "success": true,
  "message": "User fetched",
  "data": {
    "id": "uuid",
    "email": "user@gmail.com",
    "phone_number": "9999999999",
    "full_name": "",
    "role": "CLIENT",
    "status": "ACTIVE",
    "is_approved": true,
    "profile_completed": false
  }
}
```

---

### 7️⃣ Register — Staff / Makeup Artist

`POST /auth/register/staff-makeup/`

Account is created with `status: PENDING`. Admin must approve before login is possible.

**Body**

```json
{
  "email": "jane@example.com",
  "phone_number": "9999999999",
  "role": "STAFF"
}
```

> `role` must be `STAFF` or `MAKEUP_ARTIST`.

**Response (201)**

```json
{
  "success": true,
  "message": "Registration successful. Your account is under review.",
  "data": {
    "id": "uuid",
    "email": "jane@example.com",
    "role": "STAFF",
    "status": "PENDING"
  }
}
```

---

### 8️⃣ Register — Admin

`POST /auth/register/admin/`

Account starts as `PENDING`. An existing approved admin must approve before login.

**Body**

```json
{
  "full_name": "Super Admin",
  "email": "admin@example.com",
  "phone_number": "9999999999",
  "password": "SecurePass123"
}
```

> All four fields required. Password min 8 characters, stored hashed.

**Response (201)**

```json
{
  "success": true,
  "message": "Admin registration successful. Another admin must approve your account.",
  "data": {
    "id": "uuid",
    "email": "admin@example.com",
    "full_name": "Super Admin",
    "role": "ADMIN",
    "status": "PENDING"
  }
}
```

---

## 👤 PROFILE APIs

### 9️⃣ Complete Client Profile

`POST /users/complete/client/`

**Body**

```json
    {
        "full_name":         "Riya Sharma",  ← required
        "phone_number":      "9999999999",   ← required
        "city":              "Bangalore",    ← required
        "state":             "Karnataka",    ← required
        "country":           "India",        ← required
        "subscription_plan": "SILVER"        ← optional, default SILVER
    }
```

---

### 🔟 Complete Staff Profile

`POST /users/complete/staff/`

**Body**

```json
{
  "full_name": "Rahul",
  "stage_name": "Rocky",
  "gender": "Male",
  "city": "Chennai",
  "state": "Tamil Nadu",
  "country": "India",
  "price_of_staff": 5000,
  "experience_in_years": 3
}
```

---

### 1️⃣1️⃣ Complete Makeup Artist Profile

`POST /users/complete/makeup/`

**Body**

```json
{
  "full_name": "Anita",
  "gender": "Female",
  "makeup_speciality": "Bridal",
  "city": "Mumbai",
  "state": "Maharashtra",
  "country": "India",
  "experience_in_years": 5
}
```

---

### 1️⃣2️⃣ Get My Profile (Role-Based)

`GET /users/my-profile/`

Returns profile fields based on the authenticated user's role.

---

### 1️⃣3️⃣ Update My Profile

`PUT /users/update-profile/`

Body fields depend on role (see Complete Profile bodies above).

---

### 1️⃣4️⃣ Upload Staff Images (S3)

`POST /users/staff/upload-images/`

**Content-Type:** `multipart/form-data`

| Field             | Type   | Description                                          |
| ----------------- | ------ | ---------------------------------------------------- |
| `profile_picture` | file   | _(optional)_ Replaces existing profile picture in S3 |
| `gallery_images`  | file[] | _(optional)_ Replaces entire gallery in S3           |

At least one field required. Old S3 files are deleted before uploading.

**Response**

```json
{
  "success": true,
  "message": "Images uploaded successfully",
  "data": {
    "profile_picture": "https://s3.amazonaws.com/bucket/staff/profile_pictures/uuid.jpg",
    "gallery_images": ["https://s3.amazonaws.com/bucket/staff/gallery/uuid.jpg"]
  }
}
```

---

## 👑 ADMIN APIs

### 1️⃣5️⃣ Approve User

`POST /auth/admin/approve-user/`

Approves a `PENDING` account. Sets `status → ACTIVE` and `is_approved → true`. Calling admin must themselves be approved. Clients cannot be approved here (they are auto-approved on first OTP login).

**Body**

```json
{ "user_id": "uuid-of-pending-user" }
```

**Response**

```json
{
  "success": true,
  "message": "User approved successfully",
  "data": {
    "id": "uuid",
    "email": "jane@example.com",
    "role": "STAFF",
    "status": "ACTIVE",
    "is_approved": true
  }
}
```

---

### 1️⃣6️⃣ List Pending Users

`GET /auth/admin/pending-users/`

**Query Parameters**

| Param  | Type   | Description                                      |
| ------ | ------ | ------------------------------------------------ |
| `role` | string | _(optional)_ `STAFF` · `MAKEUP_ARTIST` · `ADMIN` |

**Response**

```json
{
  "success": true,
  "message": "Pending users fetched",
  "data": {
    "total": 3,
    "results": [
      {
        "id": "uuid",
        "email": "jane@example.com",
        "phone_number": "9999999999",
        "full_name": "",
        "role": "STAFF",
        "status": "PENDING",
        "created_at": "2024-06-01 10:00:00"
      }
    ]
  }
}
```

---

### 1️⃣7️⃣ List Staff

`GET /users/admin/staff/`

**Query Parameters**

| Param        | Type   | Description                                           |
| ------------ | ------ | ----------------------------------------------------- |
| `search`     | string | Search by full name or stage name (case-insensitive)  |
| `city`       | string | Filter by city (exact, case-insensitive)              |
| `package`    | string | `platinum` · `diamond` · `gold` · `silver` · `bronze` |
| `status`     | string | `assigned` (on event) or `unassigned` (available)     |
| `start_date` | date   | Joined date from `YYYY-MM-DD`                         |
| `end_date`   | date   | Joined date to `YYYY-MM-DD`                           |
| `page`       | int    | Page number (default: `1`)                            |
| `page_size`  | int    | Results per page (default: `15`, max: `100`)          |

**Response**

```json
{
  "success": true,
  "message": "Staff list fetched",
  "data": {
    "results": [
      {
        "id": "uuid",
        "user_id": "uuid",
        "full_name": "Rahul",
        "stage_name": "Rocky",
        "gender": "Male",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "country": "India",
        "package": "gold",
        "status": "active",
        "price_of_staff": 5000,
        "experience_in_years": 3,
        "profile_picture": "https://s3.amazonaws.com/...",
        "joined_date": "2024-01-15"
      }
    ],
    "pagination": { "total": 120, "page": 1, "page_size": 15, "total_pages": 8 }
  }
}
```

---

### 1️⃣8️⃣ List Makeup Artists

`GET /users/admin/makeup-artists/`

**Query Parameters**

| Param        | Type   | Description                                  |
| ------------ | ------ | -------------------------------------------- |
| `search`     | string | Search by full name (case-insensitive)       |
| `city`       | string | Filter by city (exact, case-insensitive)     |
| `experience` | int    | Minimum years of experience                  |
| `status`     | string | `active` · `inactive` · `blocked`            |
| `page`       | int    | Page number (default: `1`)                   |
| `page_size`  | int    | Results per page (default: `15`, max: `100`) |

**Response**

```json
{
  "success": true,
  "message": "Makeup artists list fetched",
  "data": {
    "results": [
      {
        "id": "uuid",
        "user_id": "uuid",
        "full_name": "Anita",
        "gender": "Female",
        "makeup_speciality": "Bridal",
        "city": "Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "experience_in_years": 5,
        "status": "active",
        "profile_picture": "https://s3.amazonaws.com/...",
        "joined_date": "2024-03-10"
      }
    ],
    "pagination": { "total": 45, "page": 1, "page_size": 15, "total_pages": 3 }
  }
}
```

---

### 1️⃣9️⃣ List Clients

`GET /users/admin/clients/`

**Query Parameters**

| Param        | Type   | Description                                           |
| ------------ | ------ | ----------------------------------------------------- |
| `search`     | string | Search by full name **or** email (case-insensitive)   |
| `city`       | string | Filter by city (exact, case-insensitive)              |
| `plan_type`  | string | `SILVER` · `BRONZE` · `GOLD` · `PLATINUM` · `DIAMOND` |
| `status`     | string | `active` · `inactive` · `blocked`                     |
| `start_date` | date   | Joined date from `YYYY-MM-DD`                         |
| `end_date`   | date   | Joined date to `YYYY-MM-DD`                           |
| `page`       | int    | Page number (default: `1`)                            |
| `page_size`  | int    | Results per page (default: `15`, max: `100`)          |

**Response**

```json
{
  "success": true,
  "message": "Clients list fetched",
  "data": {
    "results": [
      {
        "id": "uuid",
        "user_id": "uuid",
        "full_name": "Rakesh AC",
        "email": "rakesh@gmail.com",
        "city": "Bangalore",
        "state": "Karnataka",
        "country": "India",
        "subscription_plan": "SILVER",
        "status": "active",
        "joined_date": "2024-06-01"
      }
    ],
    "pagination": {
      "total": 200,
      "page": 1,
      "page_size": 15,
      "total_pages": 14
    }
  }
}
```

---

### 2️⃣0️⃣ List All Users (Raw)

`GET /users/admin/all-users/`

Returns basic user records without profile data.

---

### 2️⃣1️⃣ Change User Status

`PUT /users/admin/change-status/`

**Body**

```json
{ "user_id": "uuid", "status": "BLOCKED" }
```

**Status options:** `ACTIVE` · `INACTIVE` · `BLOCKED` · `PENDING`

---

### 2️⃣2️⃣ Update Client Subscription

`PUT /users/admin/update-subscription/`

**Body**

```json
{ "user_id": "uuid", "subscription_plan": "GOLD" }
```

**Plans:** `SILVER` · `BRONZE` · `GOLD` · `PLATINUM` · `DIAMOND`

---

## 🗂️ Master Data APIs

> All master APIs require `Authorization: Bearer <ACCESS_TOKEN>` and role = `ADMIN`

---




### 🎨 EVENT THEMES

#### Create Event Theme

`POST /master/themes/create/`

**Content-Type:** `multipart/form-data`

| Field            | Type   | Description             |
| ---------------- | ------ | ----------------------- |
| `theme_name`     | string | Name of the theme       |
| `description`    | string | Theme description       |
| `cover_image`    | file   | Cover image file        |
| `gallery_images` | file[] | Multiple gallery images |

---

#### List Event Themes

`GET /master/themes/`

**Response**

```json
{
  "success": true,
  "message": "Themes fetched",
  "data": [
    {
      "id": "uuid",
      "theme_name": "Royal Wedding",
      "status": "ACTIVE",
      "description": "Classic royal wedding setup",
      "cover_image": "https://s3.amazonaws.com/bucket/event_themes/cover.jpg",
      "gallery_images": [
        "https://s3.amazonaws.com/bucket/event_themes/gallery/img1.jpg"
      ]
    }
  ]
}
```

---

#### Update Event Theme

`PUT /master/themes/<theme_id>/update/`

**Content-Type:** `multipart/form-data`

| Field              | Type     | Description                                                       |
| ------------------ | -------- | ----------------------------------------------------------------- |
| `theme_name`       | string   | _(optional)_ Updated name                                         |
| `description`      | string   | _(optional)_ Updated description                                  |
| `status`           | string   | _(optional)_ `ACTIVE` / `INACTIVE`                                |
| `cover_image`      | file     | _(optional)_ New cover image — replaces old one in S3             |
| `gallery_images`   | file[]   | _(optional)_ New gallery images to add                            |
| `existing_gallery` | string[] | URLs of gallery images to keep — omitted URLs are deleted from S3 |

---

#### Delete Event Theme

`DELETE /master/themes/<theme_id>/delete/`

Deletes the theme and removes all S3 assets.

---

### 👔 UNIFORM CATEGORIES

#### Create Uniform Category

`POST /master/uniform/create/`

**Content-Type:** `multipart/form-data`

| Field           | Type   | Description                            |
| --------------- | ------ | -------------------------------------- |
| `category_name` | string | Name of the uniform category           |
| `unique_key`    | string | Unique slug (e.g. `royal_traditional`) |
| `description`   | string | Category description                   |
| `images`        | file[] | One or more uniform image files        |

---

#### List Uniform Categories

`GET /master/uniform/`

**Response**

```json
{
  "success": true,
  "message": "Uniform categories fetched",
  "data": [
    {
      "id": "uuid",
      "category_name": "Royal Traditional",
      "unique_key": "royal_traditional",
      "description": "Traditional royal uniforms",
      "images": ["https://s3.amazonaws.com/bucket/uniform_categories/u1.jpg"],
      "is_active": true
    }
  ]
}
```

---

#### Update Uniform Category

`PUT /master/uniform/<category_id>/update/`

**Content-Type:** `multipart/form-data`

| Field             | Type     | Description                                               |
| ----------------- | -------- | --------------------------------------------------------- |
| `category_name`   | string   | _(optional)_ Updated name                                 |
| `description`     | string   | _(optional)_ Updated description                          |
| `is_active`       | string   | _(optional)_ `"true"` or `"false"`                        |
| `images`          | file[]   | _(optional)_ New images to upload                         |
| `existing_images` | string[] | URLs of images to keep — omitted URLs are deleted from S3 |

---

#### Delete Uniform Category

`DELETE /master/uniform/<category_id>/delete/`

Deletes the category and removes all S3 assets.

---

### 💳 SUBSCRIPTION PLAN SETTINGS

Plan names are fixed: `Diamond` · `Platinum` · `Gold` · `Silver` · `Bronze`

#### Update Subscription Plan

`PUT /master/subscription/<plan_name>/update/`

**Body**

```json
{
  "monthlyPrice": 9999,
  "yearlyPrice": 99999,
  "prioritySupport": true,
  "isFree": false
}
```

---

### 💰 PAYMENT TERMS

#### Update Payment Terms

`PUT /master/payment/update/`

**Body**

```json
{ "advancePercentage": 30 }
```

---



## 📅 EVENTS APIs

> Event status choices: `created` · `planning_started` · `staff_allocated` · `completed` · `cancelled`
>
> Payment status choices: `unpaid` · `advance` · `paid_fully` · `refund_pending`

---

### 2️⃣3️⃣ Create Event

`POST /events/create/`

**Role:** `ADMIN`

**Body**

```json
{
  "event_name": "Sharma Wedding",
  "event_type": "Wedding",
  "city": "Bangalore",
  "state": "Karnataka",
  "venue": {
    "venue_name": "Royal Orchid Palace",
    "formatted_address": "MG Road, Bangalore, Karnataka 560001",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "place_id": "ChIJx9Lr6t4WrjsR0p0Gg1bH9lU",
    "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJx9Lr6t4WrjsR0p0Gg1bH9lU"
  },
  "event_start_datetime": "2026-04-10T18:00:00",
  "event_end_datetime": "2026-04-10T23:00:00",
  "no_of_days": 1,
  "working_hours": 5,
  "crew_count": 5,
  "client_id": "uuid",
  "theme_id": "uuid",
  "uniform_id": "uuid",
  "package_id": "uuid",
  "crew_member_ids": ["profile_id_1", "profile_id_2"],
  "gst_details": {
    "company_name": "Sharma Enterprises",
    "address": "123 MG Road, Bangalore",
    "gst_number": "29ABCDE1234F1Z5"
  },
  "payment": {
    "total_amount": 125000,
    "gst_amount": 22500,
    "tax_amount": 0
  }
}
```

> `event_name`, `city`, `state`, `client_id`, `venue.venue_name`, `event_start_datetime`, `event_end_datetime` are required. All other fields are optional. `gst_details` is only needed for corporate events.

**Response (201)**

```json
{
  "success": true,
  "message": "Event created successfully",
  "data": { "...full event object (see Get Event response)..." }
}
```

---

### 2️⃣4️⃣ List Events

`GET /events/`

**Role:** `ADMIN`

**Query Parameters**

| Param        | Type   | Description                                                                    |
| ------------ | ------ | ------------------------------------------------------------------------------ |
| `search`     | string | Search by event name **or** client full name (case-insensitive)                |
| `city`       | string | Filter by city (exact, case-insensitive)                                       |
| `status`     | string | `created` · `planning_started` · `staff_allocated` · `completed` · `cancelled` |
| `client_id`  | string | Filter by ClientProfile ID                                                     |
| `start_date` | date   | `event_start_datetime` >= `YYYY-MM-DD`                                         |
| `end_date`   | date   | `event_start_datetime` <= `YYYY-MM-DD`                                         |
| `page`       | int    | Page number (default: `1`)                                                     |
| `page_size`  | int    | Results per page (default: `15`, max: `100`)                                   |

**Response**

```json
{
  "success": true,
  "message": "Events fetched",
  "data": {
    "results": [
      {
        "id": "uuid",
        "event_name": "Sharma Wedding",
        "event_type": "Wedding",
        "city": "Bangalore",
        "state": "Karnataka",
        "venue": {
          "venue_name": "Royal Orchid Palace",
          "formatted_address": "MG Road, Bangalore",
          "latitude": 12.9716,
          "longitude": 77.5946,
          "place_id": "ChIJ...",
          "google_maps_url": "https://www.google.com/maps/..."
        },
        "event_start_datetime": "2026-04-10 18:00:00",
        "event_end_datetime": "2026-04-10 23:00:00",
        "no_of_days": 1,
        "working_hours": 5.0,
        "crew_count": 5,
        "client": {
          "profile_id": "uuid",
          "full_name": "Riya Sharma",
          "city": "Bangalore"
        },
        "payment": {
          "total_amount": 125000,
          "gst_amount": 22500,
          "tax_amount": 0,
          "paid_amount": 25000,
          "balance_due": 100000,
          "payment_status": "advance",
          "phonepay_transaction_id": "",
          "phonepay_order_id": "",
          "last_updated": "2026-01-15 12:00:00"
        },
        "status": "staff_allocated",
        "cancelled_reason": null,
        "theme_id": "uuid",
        "uniform_id": "uuid",
        "package_id": "uuid",
        "created_at": "2026-01-10 10:00:00",
        "updated_at": "2026-01-15 12:00:00"
      }
    ],
    "pagination": {
      "total": 50,
      "page": 1,
      "page_size": 15,
      "total_pages": 4
    }
  }
}
```

---

### 2️⃣5️⃣ Get Event Details

`GET /events/<event_id>/`

**Role:** Any authenticated user

Returns a fully enriched event object. Theme, uniform, and package are expanded to full objects. Client includes email and phone. Crew members include profile pictures.

**Response**

```json
{
  "success": true,
  "message": "Event fetched",
  "data": {
    "id": "uuid",
    "event_name": "Sharma Wedding",
    "event_type": "Wedding",
    "city": "Bangalore",
    "state": "Karnataka",
    "venue": {
      "venue_name": "Royal Orchid Palace",
      "formatted_address": "MG Road, Bangalore",
      "latitude": 12.9716,
      "longitude": 77.5946,
      "place_id": "ChIJ...",
      "google_maps_url": "https://www.google.com/maps/..."
    },
    "event_start_datetime": "2026-04-10 18:00:00",
    "event_end_datetime": "2026-04-10 23:00:00",
    "no_of_days": 1,
    "working_hours": 5.0,
    "crew_count": 5,
    "client": {
      "profile_id": "uuid",
      "full_name": "Riya Sharma",
      "city": "Bangalore",
      "email": "riya@example.com",
      "phone_number": "9999999999",
      "user_id": "uuid"
    },
    "theme": {
      "id": "uuid",
      "theme_name": "Royal Wedding",
      "cover_image": "https://s3.amazonaws.com/...",
      "status": "ACTIVE"
    },
    "uniform": {
      "id": "uuid",
      "category_name": "Royal Traditional",
      "unique_key": "royal_traditional",
      "images": ["https://s3.amazonaws.com/..."]
    },
    "package": {
      "id": "uuid",
      "name": "Gold",
      "monthly_price": 4999,
      "yearly_price": 49999,
      "priority_support": true,
      "is_free": false
    },
    "crew_members": [
      {
        "profile_id": "uuid",
        "full_name": "Rahul",
        "stage_name": "Rocky",
        "gender": "Male",
        "city": "Chennai",
        "profile_picture": "https://s3.amazonaws.com/...",
        "package": "gold"
      }
    ],
    "gst_details": {
      "company_name": "Sharma Enterprises",
      "address": "123 MG Road, Bangalore",
      "gst_number": "29ABCDE1234F1Z5"
    },
    "payment": {
      "total_amount": 125000,
      "gst_amount": 22500,
      "tax_amount": 0,
      "paid_amount": 25000,
      "balance_due": 100000,
      "payment_status": "advance",
      "phonepay_transaction_id": "",
      "phonepay_order_id": "TXN-ABCD1234-XY789Z",
      "last_updated": "2026-01-15 12:00:00"
    },
    "status": "staff_allocated",
    "cancelled_reason": null,
    "created_at": "2026-01-10 10:00:00",
    "updated_at": "2026-01-15 12:00:00"
  }
}
```

---

### 2️⃣6️⃣ Update Event

`PUT /events/<event_id>/update/`

**Role:** `ADMIN`

All fields are optional. Only supplied fields are updated. To update crew members, pass `crew_member_ids` (replaces the full list).

**Body**

```json
{
  "event_name": "Sharma Grand Wedding",
  "event_type": "Wedding",
  "city": "Bangalore",
  "state": "Karnataka",
  "venue": {
    "venue_name": "The Leela Palace",
    "formatted_address": "Old Airport Road, Bangalore",
    "latitude": 12.9607,
    "longitude": 77.6483,
    "place_id": "ChIJ...",
    "google_maps_url": "https://www.google.com/maps/..."
  },
  "event_start_datetime": "2026-04-10T18:00:00",
  "event_end_datetime": "2026-04-11T01:00:00",
  "no_of_days": 1,
  "working_hours": 7,
  "crew_count": 6,
  "theme_id": "uuid",
  "uniform_id": "uuid",
  "package_id": "uuid",
  "crew_member_ids": ["profile_id_1", "profile_id_2"],
  "gst_details": {
    "company_name": "Sharma Enterprises",
    "address": "123 MG Road, Bangalore",
    "gst_number": "29ABCDE1234F1Z5"
  },
  "payment": {
    "total_amount": 150000,
    "gst_amount": 27000,
    "tax_amount": 0,
    "paid_amount": 50000,
    "payment_status": "advance"
  }
}
```

**Response** — same shape as Get Event Details.

---

### 2️⃣7️⃣ Update Event Status

`PUT /events/<event_id>/status/`

**Role:** `ADMIN`

**Body**

```json
{
  "status": "planning_started",
  "cancelled_reason": ""
}
```

> `cancelled_reason` is required when `status` is `cancelled`.

**Response**

```json
{
  "success": true,
  "message": "Event status updated to 'planning_started'",
  "data": { "id": "uuid", "status": "planning_started" }
}
```

---

### 2️⃣8️⃣ Available Staff for Event

`GET /events/<event_id>/available-staff/`

**Role:** `ADMIN`

Returns staff who are **not** already assigned to another overlapping event in the same time window. Staff already on this event are included with `already_assigned: true` so the UI can pre-check them.

Overlap rule: `other.start < this.end AND other.end > this.start`. Cancelled events are excluded from the conflict check.

**Query Parameters**

| Param       | Type   | Description                                           |
| ----------- | ------ | ----------------------------------------------------- |
| `search`    | string | Search by full name or stage name (case-insensitive)  |
| `city`      | string | Filter by city (exact, case-insensitive)              |
| `package`   | string | `platinum` · `diamond` · `gold` · `silver` · `bronze` |
| `page`      | int    | Page number (default: `1`)                            |
| `page_size` | int    | Results per page (default: `20`, max: `100`)          |

**Response**

```json
{
  "success": true,
  "message": "Available staff fetched",
  "data": {
    "event_window": {
      "start": "2026-04-10 18:00:00",
      "end": "2026-04-10 23:00:00"
    },
    "results": [
      {
        "profile_id": "uuid",
        "full_name": "Rahul",
        "stage_name": "Rocky",
        "gender": "Male",
        "city": "Chennai",
        "package": "gold",
        "profile_picture": "https://s3.amazonaws.com/...",
        "experience_in_years": 3,
        "price_of_staff": 5000,
        "already_assigned": true
      }
    ],
    "busy_count": 12,
    "pagination": {
      "total": 35,
      "page": 1,
      "page_size": 20,
      "total_pages": 2
    }
  }
}
```

---

### 2️⃣9️⃣ Assign Crew to Event

`PUT /events/<event_id>/assign-crew/`

**Role:** `ADMIN`

Replaces the entire crew list. Before saving, validates that none of the submitted staff are already assigned to a conflicting event in the same time slot. Returns `409` with conflict details if any clash is found.

**Body**

```json
{
  "crew_member_ids": ["profile_id_1", "profile_id_2", "profile_id_3"]
}
```

**Response (200)**

```json
{
  "success": true,
  "message": "Crew assigned successfully",
  "data": {
    "crew_count": 3,
    "status": "staff_allocated",
    "crew_members": ["profile_id_1", "profile_id_2", "profile_id_3"]
  }
}
```

**Error — Scheduling Conflict (409)**

```json
{
  "success": false,
  "message": "Scheduling conflict: Rahul (busy on 'Tech Corp Annual Meet'), Anita (busy on 'Mumbai Fashion Show') are already assigned to another event during this time slot.",
  "data": {
    "conflicts": {
      "profile_id_1": {
        "conflict_event_id": "uuid",
        "conflict_event_name": "Tech Corp Annual Meet",
        "conflict_start": "2026-04-10 10:00:00",
        "conflict_end": "2026-04-10 22:00:00"
      }
    }
  }
}
```

---

### 3️⃣0️⃣ Delete Event

`DELETE /events/<event_id>/delete/`

**Role:** `ADMIN`

**Response**

```json
{ "success": true, "message": "Event deleted successfully", "data": {} }
```

---

### 3️⃣1️⃣ My Events (Client — Mobile App)

`GET /events/my-events/`

**Role:** `CLIENT`

Returns all events belonging to the logged-in client, ordered by most recent.

**Response**

```json
{
  "success": true,
  "message": "Events fetched",
  "data": {
    "results": ["...compact event objects..."],
    "total": 4
  }
}
```

---

## 💳 PAYMENT APIs

### 3️⃣2️⃣ Initiate Payment

`POST /events/<event_id>/payment/initiate/`

**Role:** Any authenticated user

Triggers PhonePe payment initiation. Stores the `merchant_txn_id` on the event for callback lookup.

**Body**

```json
{ "amount": 25000 }
```

> `amount` is in ₹ (Indian Rupees). Must be greater than 0. Returns `400` if event is already `paid_fully`.

**Response**

```json
{
  "success": true,
  "message": "STUB: Payment initiation ready. Wire up real API call to go live.",
  "data": {
    "payment_url": "https://mercury-uat.phonepe.com/transact/simulator?token=...",
    "merchant_txn_id": "TXN-ABCD1234-XY789Z"
  }
}
```

> Redirect the user to `payment_url` to complete payment on PhonePe's hosted page.

---

### 3️⃣3️⃣ Payment Callback

`GET /events/payment/callback/?txn=<merchant_txn_id>`

**Role:** Public (called by PhonePe redirect after user completes payment)

Verifies payment status with PhonePe and updates `paid_amount` and `payment_status` on the event.

**Query Parameters**

| Param | Type   | Description                          |
| ----- | ------ | ------------------------------------ |
| `txn` | string | `merchant_txn_id` from initiate step |

**Response**

```json
{
  "success": true,
  "message": "Payment status updated",
  "data": {
    "phonepay_status": "PAYMENT_SUCCESS",
    "event_id": "uuid",
    "payment_status": "paid_fully",
    "paid_amount": 125000
  }
}
```

---

### 3️⃣4️⃣ Payment Webhook

`POST /events/payment/webhook/`

**Role:** Public (server-to-server call from PhonePe)

Handles PhonePe's server-to-server notification. Updates payment status independently of the user redirect. Always returns `200` to acknowledge receipt.

---

## 🛰️ LIVE TRACKING API

> The C++ tracking server (`LOCATION_SERVER_URL`) stores location data sent directly from the mobile app. Django fetches from it server-side to avoid CORS issues.

---

### 3️⃣5️⃣ Track Event — Live Crew Locations

`GET /events/<event_id>/track/`

**Role:** Any authenticated user

Fetches the last known location of every crew member assigned to the event from the C++ tracking server. A failure for one member does not abort the response — that member gets `status: "offline"` with a `location_error` message.

**Response**

```json
{
  "success": true,
  "message": "Tracking data fetched",
  "data": {
    "event": {
      "id": "uuid",
      "event_name": "Sharma Wedding",
      "event_type": "Wedding",
      "status": "staff_allocated",
      "event_start_datetime": "2026-04-10 18:00:00",
      "event_end_datetime": "2026-04-10 23:00:00",
      "venue_name": "Royal Orchid Palace",
      "city": "Bangalore",
      "state": "Karnataka",
      "client_name": "Riya Sharma",
      "crew_count": 5
    },
    "crew": [
      {
        "id": "profile_uuid",
        "name": "Rahul",
        "stage_name": "Rocky",
        "role": "Staff",
        "image_url": "https://s3.amazonaws.com/...",
        "lat": 12.9716,
        "lng": 77.5946,
        "timestamp": "2026-04-10T19:45:00Z",
        "status": "on_event",
        "location_error": null
      },
      {
        "id": "profile_uuid_2",
        "name": "Anita",
        "stage_name": "",
        "role": "Staff",
        "image_url": "https://s3.amazonaws.com/...",
        "lat": null,
        "lng": null,
        "timestamp": null,
        "status": "offline",
        "location_error": "Cannot reach location server (connection refused)"
      }
    ],
    "total_crew": 5,
    "online": 4
  }
}
```

**Crew `status` values:**

| Value      | Meaning                                           |
| ---------- | ------------------------------------------------- |
| `on_event` | C++ server returned valid lat/lng                 |
| `away`     | C++ server responded but returned no coordinates  |
| `offline`  | C++ server unreachable or no data for this member |

---

### Location Update (Mobile App → C++ Server directly)

`POST http://<LOCATION_SERVER_URL>:9090/api/location/update`

> This is called **directly by the mobile app**. The Django backend is not involved.

**Body**

```json
{
  "Employee": "staff_profile_uuid",
  "lat": 12.9715987,
  "lng": 77.5945627
}
```

**Response**

```json
{ "status": "ok" }
```
