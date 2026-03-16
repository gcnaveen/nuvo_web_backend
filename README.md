# NUVÓ Web Backend

Django + MongoEngine REST API backend for the NUVÓ Hosting Agency admin panel and public landing page.

---

## 📦 Project Structure

```
backend_code/
├── manage.py
├── requirements.txt
├── config/
│   ├── urls.py               ← Root URL config
│   └── settings/
│       ├── base.py           ← Shared settings
│       ├── dev.py            ← Local dev overrides
│       └── prod.py           ← Production overrides
└── apps/
    ├── accounts/             → Auth: OTP, JWT, middleware, decorators
    ├── users/                → User & profile management + self-registration
    ├── common/               → S3, PhonePe, location server, validators
    ├── master/               → Event themes, uniforms, inventory, plans, payment terms
    └── events/               → Event booking, crew allocation, payments, live tracking
```

---

## 🚀 Local Setup

```bash
cd backend_code
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

---

## ⚙️ Required Settings

Add these to `config/settings/base.py` or as environment variables in `.env`:

```python
# MongoDB
MONGODB_URI = "mongodb://localhost:27017/nuvo"

# AWS S3  (used for profile pictures, gallery images, uniform/theme images)
AWS_ACCESS_KEY_ID        = "..."
AWS_SECRET_ACCESS_KEY    = "..."
AWS_STORAGE_BUCKET_NAME  = "..."
AWS_S3_REGION_NAME       = "ap-south-1"

# PhonePe Payment Gateway (sandbox)
PHONEPE_MERCHANT_ID  = "PGTESTPAYUAT"
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

## 🌍 Base URL

```
http://127.0.0.1:8000/api/
```

All protected endpoints require:

```
Authorization: Bearer <ACCESS_TOKEN>
```

---

## 🔐 Authentication Flow

### Client (Mobile App)

```
POST /auth/send-otp/        → email required, phone optional
POST /auth/verify-otp/      → account auto-created + auto-approved on first login
                              → if profile incomplete, complete it next
POST /users/complete/client/
```

### Staff (Public Self-Registration via Landing Page)

```
POST /users/register/staff/ → multipart/form-data, no auth required
                              → status set to INACTIVE, pending admin review
                              → stage name auto-generated and returned
Admin approves via /auth/admin/approve-user/
POST /auth/send-otp/  →  POST /auth/verify-otp/  →  tokens issued
```

### Staff / Makeup Artist (Admin-Created)

```
POST /auth/register/staff-makeup/  → status PENDING
Admin approves via /auth/admin/approve-user/
POST /auth/send-otp/  →  POST /auth/verify-otp/  →  tokens issued
```

### Admin

```
POST /auth/register/admin/          → status PENDING, password required
Existing admin approves via /auth/admin/approve-user/
POST /auth/send-otp/  →  POST /auth/verify-otp/  →  tokens issued
```

---

## 🔑 AUTH APIs (`/api/auth/`)

### Send OTP

`POST /auth/send-otp/`

> **CLIENT:** Email required, account need not exist yet.
> **STAFF / MAKEUP_ARTIST / ADMIN:** Account must exist and not be blocked.

```json
{ "email": "user@gmail.com" }
```

---

### Verify OTP (Login)

`POST /auth/verify-otp/`

> Returns `403` if account is `PENDING` or blocked.

```json
{ "email": "user@gmail.com", "otp": "123456" }
```

**Response**

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "...",
    "refresh_token": "...",
    "user": {
      "id": "uuid",
      "email": "user@gmail.com",
      "phone_number": "9999999999",
      "full_name": "Riya Sharma",
      "role": "CLIENT",
      "status": "ACTIVE",
      "is_approved": true,
      "profile_completed": false
    }
  }
}
```

---

### Refresh Token

`POST /auth/refresh-token/`

```json
{ "refresh_token": "..." }
```

---

### Logout

`POST /auth/logout/`

Blacklists the refresh token.

```json
{ "refresh_token": "..." }
```

---

### Resend OTP

`POST /auth/resend-otp/`

60-second cooldown, 5-minute OTP expiry.

```json
{ "email": "user@gmail.com" }
```

---

### Get Logged-In User

`GET /auth/me/`

Returns the authenticated user's core account fields.

---

### Register — Staff / Makeup Artist (Admin-created)

`POST /auth/register/staff-makeup/`

Creates account with `status: PENDING`. Admin must approve.

```json
{
  "email": "jane@example.com",
  "phone_number": "9999999999",
  "role": "STAFF"
}
```

> `role` must be `STAFF` or `MAKEUP_ARTIST`.

---

### Register — Admin

`POST /auth/register/admin/`

Account starts as `PENDING`. Another approved admin must approve.

```json
{
  "full_name": "Super Admin",
  "email": "admin@example.com",
  "phone_number": "9999999999",
  "password": "SecurePass123"
}
```

---

### Approve User _(Admin only)_

`POST /auth/admin/approve-user/`

Sets `status → ACTIVE`, `is_approved → true`. Clients are auto-approved and cannot be approved here.

```json
{ "user_id": "uuid" }
```

---

### List Pending Users _(Admin only)_

`GET /auth/admin/pending-users/?role=STAFF`

| Param  | Type   | Description                                      |
| ------ | ------ | ------------------------------------------------ |
| `role` | string | _(optional)_ `STAFF` · `MAKEUP_ARTIST` · `ADMIN` |

---

---

## 👤 USER & PROFILE APIs (`/api/users/`)

### Staff Public Self-Registration _(No auth — public)_

`POST /users/register/staff/`

**Content-Type:** `multipart/form-data`

Called directly from the NUVÓ landing page `/joinourteam`. Creates a `User` (role=`STAFF`, status=`INACTIVE`) and a full `StaffProfile` from the submitted form. Auto-generates a unique stage name. Uploads up to 4 images to S3.

| Field                   | Required | Description                                          |
| ----------------------- | -------- | ---------------------------------------------------- |
| `email`                 | ✅       | Applicant's email                                    |
| `firstName`             | ✅       | First name                                           |
| `lastName`              | ✅       | Last name                                            |
| `telephone`             | ✅\*     | At least one phone required                          |
| `cellPhone`             | ✅\*     | At least one phone required                          |
| `address`               |          | Full address                                         |
| `city`                  |          | City                                                 |
| `country`               |          | Country                                              |
| `placeOfBirth`          |          | Place of birth                                       |
| `dob`                   |          | Date of birth `YYYY-MM-DD`                           |
| `status`                |          | Marital status: `single` \| `married`                |
| `weight`                |          | Weight in kg                                         |
| `height`                |          | Height in cm                                         |
| `shoeSize`              |          | Shoe size                                            |
| `blazerSize`            |          | Blazer size (e.g. `M`, `L`)                          |
| `trouserSize`           |          | Trouser size                                         |
| `student`               |          | `yes` \| `no`                                        |
| `school`                |          | School / university name                             |
| `degree`                |          | Degree / qualification                               |
| `language1`–`language4` |          | Language names (language1 required)                  |
| `rate1`–`rate4`         |          | Proficiency per language if language is set          |
| `hostessExperience`     |          | `yes` \| `no`                                        |
| `groupResponsible`      |          | `yes` \| `no`                                        |
| `agency`                |          | Agency name                                          |
| `experienceAreas`       |          | Multiple values (e.g. `modeling`, `sales/marketing`) |
| `workType`              |          | `full-time` \| `part-time` \| `both`                 |
| `holidayWork`           |          | `yes` \| `no`                                        |
| `images`                |          | Up to 4 image files (2 MB each max)                  |

**Response (201)**

```json
{
  "success": true,
  "message": "Registration submitted successfully! Your application is under review.",
  "data": {
    "id": "profile_uuid",
    "full_name": "Tom Cruise",
    "email": "tom@example.com",
    "stage_name": "Cobalt Raven",
    "status": "PENDING_REVIEW"
  }
}
```

> The `stage_name` is auto-generated (e.g. "Velvet Storm", "Cobalt Raven") and returned to display to the applicant. Admin will use this name to identify the person.

**Error (409)** — duplicate email or phone:

```json
{ "success": false, "message": "An account with this email already exists" }
```

---

### Complete Client Profile

`POST /users/complete/client/`

```json
{
  "full_name": "Riya Sharma",
  "phone_number": "9999999999",
  "city": "Bangalore",
  "state": "Karnataka",
  "country": "India",
  "subscription_plan": "SILVER"
}
```

---

### Complete Staff Profile

`POST /users/complete/staff/`

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

### Complete Makeup Artist Profile

`POST /users/complete/makeup/`

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

### Get My Profile

`GET /users/my-profile/`

Returns profile fields based on the authenticated user's role.

---

### Update My Profile

`PUT /users/update-profile/`

Body fields depend on role (same structure as Complete Profile).

---

### Upload Staff Images (Self)

`POST /users/staff/upload-images/`

**Content-Type:** `multipart/form-data`

| Field             | Type   | Description                          |
| ----------------- | ------ | ------------------------------------ |
| `profile_picture` | file   | _(optional)_ Replaces existing in S3 |
| `gallery_images`  | file[] | _(optional)_ Replaces gallery in S3  |

At least one field required.

---

### List Staff _(Admin only)_

`GET /users/api/staff/`

| Param        | Type   | Description                                           |
| ------------ | ------ | ----------------------------------------------------- |
| `search`     | string | Full name or stage name (case-insensitive)            |
| `city`       | string | Exact city match (case-insensitive)                   |
| `package`    | string | `platinum` · `diamond` · `gold` · `silver` · `bronze` |
| `status`     | string | `assigned` · `unassigned`                             |
| `start_date` | date   | Joined date from `YYYY-MM-DD`                         |
| `end_date`   | date   | Joined date to `YYYY-MM-DD`                           |
| `page`       | int    | Default: `1`                                          |
| `page_size`  | int    | Default: `15`, max: `100`                             |

---

### Get Staff Detail _(Admin only)_

`GET /users/api/staff/<staff_id>/`

Returns full profile including all registration fields, gallery images, and current user status.

---

### Create Staff _(Admin only)_

`POST /users/admin/staff/create/`

**Content-Type:** `multipart/form-data`

Creates a `User` + `StaffProfile` directly. Auto-generates stage name. Supports all profile fields + image uploads.

---

### Update Staff _(Admin only)_

`PUT /users/admin/staff/<staff_id>/update/`

**Content-Type:** `multipart/form-data`

All fields optional. Updates both `User` and `StaffProfile`.

---

### Delete Staff _(Admin only)_

`DELETE /users/admin/staff/<staff_id>/delete/`

Deletes the `StaffProfile`, `User`, and all S3 assets.

---

### Upload Staff Images _(Admin only)_

`POST /users/admin/staff/<staff_id>/upload-images/`

**Content-Type:** `multipart/form-data`

| Field             | Type   | Description                                 |
| ----------------- | ------ | ------------------------------------------- |
| `profile_picture` | file   | _(optional)_ Replaces profile picture in S3 |
| `gallery_images`  | file[] | _(optional)_ Appends to gallery in S3       |

---

### Delete Staff Gallery Image _(Admin only)_

`DELETE /users/admin/staff/<staff_id>/delete-gallery/`

```json
{ "image_url": "https://s3.amazonaws.com/.../image.jpg" }
```

---

### List Clients _(Admin only)_

`GET /users/api/clients/`

| Param        | Type   | Description                                           |
| ------------ | ------ | ----------------------------------------------------- |
| `search`     | string | Full name or email (case-insensitive)                 |
| `city`       | string | Exact city match                                      |
| `plan_type`  | string | `SILVER` · `BRONZE` · `GOLD` · `PLATINUM` · `DIAMOND` |
| `status`     | string | `active` · `inactive` · `blocked`                     |
| `start_date` | date   | Joined date from `YYYY-MM-DD`                         |
| `end_date`   | date   | Joined date to `YYYY-MM-DD`                           |
| `page`       | int    | Default: `1`                                          |
| `page_size`  | int    | Default: `15`, max: `100`                             |

---

### Get Client Detail _(Admin only)_

`GET /users/api/clients/<client_id>/`

---

### Create Client _(Admin only)_

`POST /users/admin/create-client/`

---

### Delete Client _(Admin only)_

`DELETE /users/admin/clients/<client_id>/delete/`

---

### Update Client Subscription _(Admin only)_

`PUT /users/admin/update-subscription/`

```json
{ "user_id": "uuid", "subscription_plan": "GOLD" }
```

Plans: `SILVER` · `BRONZE` · `GOLD` · `PLATINUM` · `DIAMOND`

---

### List Makeup Artists _(Admin only)_

`GET /users/api/makeup-artists/`

| Param        | Type   | Description                       |
| ------------ | ------ | --------------------------------- |
| `search`     | string | Full name (case-insensitive)      |
| `city`       | string | Exact city match                  |
| `experience` | int    | Minimum years of experience       |
| `status`     | string | `active` · `inactive` · `blocked` |
| `page`       | int    | Default: `1`                      |
| `page_size`  | int    | Default: `15`, max: `100`         |

---

### Get / Create / Update / Delete MUA _(Admin only)_

| Method   | Endpoint                                               | Description            |
| -------- | ------------------------------------------------------ | ---------------------- |
| `GET`    | `/users/api/makeup-artists/<mua_id>/`                  | Full profile detail    |
| `POST`   | `/users/admin/makeup-artists/create/`                  | Create MUA + profile   |
| `PUT`    | `/users/admin/makeup-artists/<mua_id>/update/`         | Update profile         |
| `DELETE` | `/users/admin/makeup-artists/<mua_id>/delete/`         | Delete + S3 cleanup    |
| `POST`   | `/users/admin/makeup-artists/<mua_id>/upload-images/`  | Upload profile/gallery |
| `DELETE` | `/users/admin/makeup-artists/<mua_id>/delete-gallery/` | Remove gallery image   |

---

---

## 🗂️ MASTER DATA APIs (`/api/master/`)

> All write endpoints require `ADMIN` role. Read endpoints require auth unless noted.

---

### 🎨 Event Themes

| Method   | Endpoint                            | Description              |
| -------- | ----------------------------------- | ------------------------ |
| `POST`   | `/master/themes/create/`            | Create theme (multipart) |
| `GET`    | `/master/themes/`                   | List all themes          |
| `PUT`    | `/master/themes/<theme_id>/update/` | Update theme (multipart) |
| `DELETE` | `/master/themes/<theme_id>/delete/` | Delete theme + S3 assets |

**Create / Update fields** (`multipart/form-data`):

| Field                 | Type   | Description                                                  |
| --------------------- | ------ | ------------------------------------------------------------ |
| `theme_name`          | string | Required on create                                           |
| `description`         | string |                                                              |
| `status`              | string | `ACTIVE` \| `INACTIVE`                                       |
| `cover_image`         | file   | Replaces existing cover in S3                                |
| `gallery_images`      | file[] | New images to add to gallery                                 |
| `delete_gallery_urls` | string | _(Update only)_ JSON array of S3 URLs to delete from gallery |

---

### 👔 Uniform Categories

| Method   | Endpoint                                | Description                      |
| -------- | --------------------------------------- | -------------------------------- |
| `POST`   | `/master/uniform/create/`               | Create category (multipart)      |
| `GET`    | `/master/uniform/`                      | List all categories (admin)      |
| `GET`    | `/master/uniform/filter/`               | Public filter (no auth required) |
| `PUT`    | `/master/uniform/<category_id>/update/` | Update category (multipart)      |
| `DELETE` | `/master/uniform/<category_id>/delete/` | Delete category + S3 assets      |

**Create / Update fields** (`multipart/form-data`):

| Field               | Type   | Description                                                    |
| ------------------- | ------ | -------------------------------------------------------------- |
| `category_name`     | string | Required on create                                             |
| `unique_key`        | string | Required on create, read-only after (e.g. `royal_traditional`) |
| `description`       | string |                                                                |
| `gender`            | string | `Male` \| `Female` \| `Unisex`                                 |
| `price`             | number | Price per unit in ₹                                            |
| `is_active`         | string | `"true"` \| `"false"`                                          |
| `images`            | file[] | New images to upload                                           |
| `delete_image_urls` | string | _(Update only)_ JSON array of S3 URLs to remove                |

**Public filter** `GET /master/uniform/filter/` — no auth required, used by landing page:

| Param                     | Type   | Description                               |
| ------------------------- | ------ | ----------------------------------------- |
| `gender`                  | string | `Male` \| `Female` \| `Unisex`            |
| `min_price` / `max_price` | number | Price range filter                        |
| `search`                  | string | Category name contains (case-insensitive) |

---

### 📦 Inventory _(Admin only)_

Inventory is built on top of `UniformCategory` — each uniform category has a `stock` dict tracking quantity by size.

| Method | Endpoint                                  | Description                         |
| ------ | ----------------------------------------- | ----------------------------------- |
| `GET`  | `/master/inventory/summary/`              | Dashboard summary stats             |
| `GET`  | `/master/inventory/`                      | List all with stock data            |
| `GET`  | `/master/inventory/<category_id>/`        | Single item with full stock detail  |
| `PUT`  | `/master/inventory/<category_id>/stock/`  | Set stock quantities per size       |
| `POST` | `/master/inventory/<category_id>/adjust/` | Increment/decrement in-use (events) |

**Inventory summary response:**

```json
{
  "total_categories": 12,
  "total_items": 450,
  "total_in_use": 280,
  "total_available": 170,
  "low_stock_count": 3
}
```

**List inventory query params:**

| Param       | Type   | Description                              |
| ----------- | ------ | ---------------------------------------- |
| `search`    | string | Category name contains                   |
| `category`  | string | Exact `unique_key` match                 |
| `is_active` | string | `true` \| `false`                        |
| `low_stock` | string | `true` → only items with < 20% available |

**Update stock body:**

```json
{
  "has_sizes": true,
  "stock": {
    "S": { "total": 20 },
    "M": { "total": 40, "in_use": 12 },
    "L": { "total": 30 },
    "XL": { "total": 10 }
  }
}
```

> `in_use` is optional — omit to keep existing value. `total` cannot be less than `in_use`.

For free-size items (`has_sizes: false`), use key `"OS"` (One Size).

**Adjust in-use body** (called by events system):

```json
{ "size": "M", "delta": 3 }
```

> Positive delta = assign. Negative = return. Returns `400` if stock would go negative.

---

### 💳 Subscription Plans

| Method | Endpoint                                   | Description            |
| ------ | ------------------------------------------ | ---------------------- |
| `GET`  | `/master/subscription/`                    | List all plan settings |
| `PUT`  | `/master/subscription/<plan_name>/update/` | Upsert plan pricing    |

Plan names (fixed): `Diamond` · `Platinum` · `Gold` · `Silver` · `Bronze`

```json
{
  "monthlyPrice": 9999,
  "yearlyPrice": 99999,
  "prioritySupport": true,
  "isFree": false
}
```

---

### 💰 Payment Terms

| Method | Endpoint                  | Description                       |
| ------ | ------------------------- | --------------------------------- |
| `GET`  | `/master/payment/`        | Get current advance percentage    |
| `PUT`  | `/master/payment/update/` | Update advance percentage (0–100) |

```json
{ "advancePercentage": 30 }
```

> This value is read by the admin panel when initiating event payments to auto-calculate the advance amount.

---

---

## 📅 EVENTS APIs (`/api/events/`)

> Event status: `created` · `planning_started` · `staff_allocated` · `completed` · `cancelled`
> Payment status: `unpaid` · `advance` · `paid_fully` · `refund_pending`

---

### Create Event _(Admin only)_

`POST /events/create/`

Required: `event_name`, `city`, `state`, `client_id`, `venue.venue_name`, `event_start_datetime`, `event_end_datetime`

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
    "place_id": "ChIJ...",
    "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ..."
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

---

### List Events _(Admin only)_

`GET /events/`

| Param        | Type   | Description                    |
| ------------ | ------ | ------------------------------ |
| `search`     | string | Event name or client full name |
| `city`       | string | Exact city (case-insensitive)  |
| `status`     | string | Any event status value         |
| `client_id`  | string | ClientProfile ID               |
| `start_date` | date   | Event start >= `YYYY-MM-DD`    |
| `end_date`   | date   | Event start <= `YYYY-MM-DD`    |
| `page`       | int    | Default: `1`                   |
| `page_size`  | int    | Default: `15`, max: `100`      |

---

### Get Event Details

`GET /events/<event_id>/`

Returns fully enriched event: expanded theme, uniform, package, client (with email/phone), crew members with profile pictures.

---

### Update Event _(Admin only)_

`PUT /events/<event_id>/update/`

All fields optional. Same body shape as Create Event. Pass `crew_member_ids` to replace the full crew list.

---

### Update Event Status _(Admin only)_

`PUT /events/<event_id>/status/`

```json
{
  "status": "planning_started",
  "cancelled_reason": ""
}
```

> `cancelled_reason` is required when `status` is `cancelled`.

---

### Delete Event _(Admin only)_

`DELETE /events/<event_id>/delete/`

---

### Available Staff for Event _(Admin only)_

`GET /events/<event_id>/available-staff/`

Returns staff with no scheduling conflicts during the event's time window. Staff already on this event are included with `"already_assigned": true`.

**Conflict rule:** `other.start < this.end AND other.end > this.start`. Cancelled events excluded.

| Param       | Type   | Description               |
| ----------- | ------ | ------------------------- |
| `search`    | string | Full name or stage name   |
| `city`      | string | Exact city                |
| `package`   | string | Package tier filter       |
| `page`      | int    | Default: `1`              |
| `page_size` | int    | Default: `20`, max: `100` |

---

### Assign Crew _(Admin only)_

`PUT /events/<event_id>/assign-crew/`

Replaces the full crew list. Validates no scheduling conflicts before saving. Returns `409` on conflict.

```json
{ "crew_member_ids": ["profile_id_1", "profile_id_2"] }
```

**Conflict response (409):**

```json
{
  "success": false,
  "message": "Scheduling conflict: Rahul (busy on 'Tech Corp Annual Meet') ...",
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

### My Events _(Client / Mobile App)_

`GET /events/my-events/`

Returns all events for the logged-in client, ordered by most recent.

---

---

## 💳 PAYMENT APIs

### Initiate Payment

`POST /events/<event_id>/payment/initiate/`

```json
{ "amount": 25000 }
```

> Amount in ₹. Returns `400` if event is already `paid_fully`.

**Response:**

```json
{
  "success": true,
  "data": {
    "payment_url": "https://mercury-uat.phonepe.com/transact/simulator?token=...",
    "merchant_txn_id": "TXN-ABCD1234-XY789Z"
  }
}
```

Redirect the user to `payment_url` to complete payment on PhonePe's hosted page.

---

### Payment Callback _(Public — PhonePe redirect)_

`GET /events/payment/callback/?txn=<merchant_txn_id>`

Verifies payment with PhonePe and updates `paid_amount` + `payment_status` on the event.

---

### Payment Webhook _(Public — PhonePe server-to-server)_

`POST /events/payment/webhook/`

Handles server-to-server notification from PhonePe. Always returns `200` to acknowledge.

---

---

## 🛰️ LIVE TRACKING API

### Track Event — Live Crew Locations

`GET /events/<event_id>/track/`

Fetches last known location of every assigned crew member from the C++ tracking server. A failure for one member returns `status: "offline"` without aborting the response.

**Response:**

```json
{
  "success": true,
  "data": {
    "event": {
      "id": "uuid",
      "event_name": "Sharma Wedding",
      "status": "staff_allocated",
      "venue_name": "Royal Orchid Palace",
      "venue_lat": 12.9716,
      "venue_lng": 77.5946,
      "city": "Bangalore",
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

### Location Update _(Mobile App → C++ Server directly)_

`POST http://<LOCATION_SERVER_URL>:9090/api/location/update`

> Called **directly by the mobile app**. Django is not involved.

```json
{
  "Employee": "staff_profile_uuid",
  "lat": 12.9715987,
  "lng": 77.5945627
}
```

---

## 📋 Standard Response Shape

All endpoints return:

```json
{
  "success": true | false,
  "message": "Human-readable message",
  "data": { }
}
```

Common HTTP status codes:

| Code | Meaning                                      |
| ---- | -------------------------------------------- |
| 200  | Success                                      |
| 201  | Created                                      |
| 400  | Bad request / validation error               |
| 401  | Missing or invalid token                     |
| 403  | Forbidden (wrong role or pending approval)   |
| 404  | Resource not found                           |
| 405  | Wrong HTTP method                            |
| 409  | Conflict (duplicate email/phone, crew clash) |
| 500  | Internal server error                        |
