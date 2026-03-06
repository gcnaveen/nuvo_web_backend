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
├── common/       → Utilities & Validators
├── master/       → Event Themes, Uniforms, Subscriptions, Payment Terms
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

### 🌍 Base URL

`http://127.0.0.1:8000/api/`

All protected APIs require:

`Authorization: Bearer <ACCESS_TOKEN>`

---

## 🔐 AUTH APIs

### 1️⃣ Send OTP

`POST /auth/send-otp/`

**Roles:** `CLIENT` · `STAFF` · `MAKEUP_ARTIST` · `ADMIN`

> **CLIENT:** Only `email` is required. `phone_number` is optional and only validated for format if supplied. Account does not need to exist yet.
>
> **STAFF / MAKEUP_ARTIST / ADMIN:** Account must already exist (registered via the register endpoints below). The API verifies the email or phone matches a known account before sending the OTP. Blocked accounts are rejected here.

**Body**

```json
{
  "email": "user@gmail.com",
  "phone_number": "9999999999",
  "role": "CLIENT"
}
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

> **CLIENT:** Account is auto-created and auto-approved on first login. `phone_number` is required only on the very first login. Subsequent logins only need `email`, `role`, and `otp`.
>
> **STAFF / MAKEUP_ARTIST / ADMIN:** Returns `403` if the account is still `PENDING`. No tokens are issued until an admin approves the account.

**Body**

```json
{
  "email": "user@gmail.com",
  "phone_number": "9999999999",
  "role": "CLIENT",
  "otp": "123456"
}
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
{
  "refresh_token": "your_refresh_token"
}
```

**Response**

```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "data": {
    "access_token": "......"
  }
}
```

---

### 4️⃣ Logout

`POST /auth/logout/`

**Headers:** `Authorization: Bearer ACCESS_TOKEN`

**Body**

```json
{
  "refresh_token": "your_refresh_token"
}
```

Blacklists the refresh token.

**Response**

```json
{
  "success": true,
  "message": "Logged out successfully",
  "data": {}
}
```

---

### 5️⃣ Resend OTP

`POST /auth/resend-otp/`

60-second cooldown · 5-minute expiry

**Body**

```json
{
  "email": "user@gmail.com"
}
```

**Response**

```json
{
  "success": true,
  "message": "OTP resent successfully",
  "data": {}
}
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
    "id": "0f010853-b7f0-41f1-b2c1-85c257ee3aa0",
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

Self-registration for `STAFF` and `MAKEUP_ARTIST`. Account is created with `status: PENDING` and `is_approved: false`. An admin must approve before the user can log in.

**Body**

```json
{
  "email": "jane@example.com",
  "phone_number": "9999999999",
  "role": "STAFF"
}
```

> `role` must be `STAFF` or `MAKEUP_ARTIST`. Any other value returns a `400`.

**Response (201)**

```json
{
  "success": true,
  "message": "Registration successful. Your account is under review. You will be able to log in once an admin approves your account.",
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

Admin self-registration using password credentials. Account starts as `PENDING`. An existing approved admin must approve before login is possible.

**Body**

```json
{
  "full_name": "Super Admin",
  "email": "admin@example.com",
  "phone_number": "9999999999",
  "password": "SecurePass123"
}
```

> All four fields are required. Password must be at least 8 characters and is stored hashed.

**Response (201)**

```json
{
  "success": true,
  "message": "Admin registration successful. Another admin must approve your account before you can log in.",
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
  "full_name": "Rakesh AC",
  "city": "Bangalore",
  "state": "Karnataka",
  "country": "India",
  "subscription_plan": "SILVER"
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

At least one field is required. Old S3 files are deleted before new ones are uploaded.

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

Approves a `PENDING` account (staff, makeup artist, or another admin). Sets `status → ACTIVE` and `is_approved → true`. The calling admin must themselves be approved. Clients cannot be passed here as they never require approval.

**Body**

```json
{
  "user_id": "uuid-of-pending-user"
}
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

Returns all accounts awaiting approval. Optionally filter by role.

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
    "pagination": {
      "total": 120,
      "page": 1,
      "page_size": 15,
      "total_pages": 8
    }
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
    "pagination": {
      "total": 45,
      "page": 1,
      "page_size": 15,
      "total_pages": 3
    }
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
{
  "user_id": "uuid",
  "status": "BLOCKED"
}
```

**Status options:** `ACTIVE` · `INACTIVE` · `BLOCKED` · `PENDING`

---

### 2️⃣2️⃣ Update Client Subscription

`PUT /users/admin/update-subscription/`

**Body**

```json
{
  "user_id": "uuid",
  "subscription_plan": "GOLD"
}
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

Deletes the theme and removes cover image + all gallery images from S3.

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

Deletes the category and removes all associated images from S3.

---

### 💳 SUBSCRIPTION PLAN SETTINGS

Plan names are fixed: `Diamond` · `Platinum` · `Gold` · `Silver` · `Bronze`

#### Update Subscription Plan

`PUT /master/subscription/<plan_name>/update/`

**Example:** `PUT /master/subscription/Diamond/update/`

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
{
  "advancePercentage": 30
}
```
