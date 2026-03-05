# nuvo_web_backend

## Local setup (macOS / Linux)

Use a virtual environment so `pip install` doesn’t touch system Python:

```bash
# From repo root (Nuvo_backend)
cd nuvo_web_backend
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then run the app:

```bash
python manage.py runserver
```

---

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

```
send-otp
    ↓
verify-otp → returns access + refresh
    ↓
Frontend checks /auth/me
    ↓
If profile not completed → call complete-profile
    ↓
Normal app usage
```

### 🌍 Base URL

`http://127.0.0.1:8000/api/`

All protected APIs require:

`Authorization: Bearer <ACCESS_TOKEN>`

---

## 🔐 AUTH APIs

### 1️⃣ Send OTP

`POST /auth/send-otp/`

**Body**

```json
{
  "email": "user@gmail.com",
  "phone_number": "9999999999",
  "role": "CLIENT"
}
```

**Roles:** `CLIENT` · `STAFF` · `MAKEUP_ARTIST` · `ADMIN`

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
      "role": "CLIENT",
      "status": "ACTIVE",
      "profile_completed": false
    }
  }
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
    "role": "CLIENT",
    "status": "ACTIVE",
    "profile_completed": false
  }
}
```

---

## 👤 PROFILE APIs

### 7️⃣ Complete Client Profile

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

### 8️⃣ Complete Staff Profile

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

### 9️⃣ Complete Makeup Artist Profile

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

### 🔟 Get My Profile (Role-Based)

`GET /users/my-profile/`

Returns profile fields based on the authenticated user's role.

---

### 1️⃣1️⃣ Update My Profile

`PUT /users/update-profile/`

Body fields depend on role (see Complete Profile bodies above for available fields).

---

### 1️⃣2️⃣ Upload Staff Images (S3)

`POST /users/staff/upload-images/`

**Content-Type:** `multipart/form-data`

| Field             | Type   | Description                                          |
| ----------------- | ------ | ---------------------------------------------------- |
| `profile_picture` | file   | _(optional)_ Replaces existing profile picture in S3 |
| `gallery_images`  | file[] | _(optional)_ Replaces entire gallery in S3           |

At least one of the two fields is required. Old S3 files are deleted before new ones are uploaded.

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

### 1️⃣3️⃣ List Staff

`GET /users/admin/staff/`

Requires role = `ADMIN`

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

### 1️⃣4️⃣ List Makeup Artists

`GET /users/admin/makeup-artists/`

Requires role = `ADMIN`

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

### 1️⃣5️⃣ List Clients

`GET /users/admin/clients/`

Requires role = `ADMIN`

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

### 1️⃣6️⃣ List All Users (Raw)

`GET /users/admin/all-users/`

Requires role = `ADMIN`. Returns basic user records without profile data.

---

### 1️⃣7️⃣ Change User Status

`PUT /users/admin/change-status/`

**Body**

```json
{
  "user_id": "uuid",
  "status": "BLOCKED"
}
```

**Status options:** `ACTIVE` · `INACTIVE` · `BLOCKED`

---

### 1️⃣8️⃣ Update Client Subscription

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

Single document — stores the global advance payment percentage.

#### Update Payment Terms

`PUT /master/payment/update/`

**Body**

```json
{
  "advancePercentage": 30
}
```
