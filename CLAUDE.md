# CLAUDE.md — Nuvo Hosting Engineering Knowledge Base

> **Living document.** Update this file every time architecture changes, a new pattern is introduced, a bug is fixed, or a decision is made. This is the single source of truth for Claude and any developer who picks up this project.

---

## 1. Project Overview

**Nuvo Hosting** is an event hosting management platform that connects clients with professional hostesses/models for events (weddings, corporate, birthdays, etc.).

### Platforms
| Platform | Tech | Owner |
|---|---|---|
| Mobile App | React Native | External mobile developer |
| Admin Panel | React JS (Vite + Bootstrap Icons) | Rakesh (this repo's frontend) |
| Backend API | Python Django | Rakesh (this repo) |
| Location Tracker | C++ server | Separate repo |

### Repos on this machine
```
/Users/rudreshac/Desktop/rakesh/Nuvo/
├── nuvo_web_backend/         ← Django backend (primary)
├── nuvo_web_frountend/       ← React JS admin panel (primary)
├── Nuvo_hosting_c_backend/   ← C++ location tracking server
├── backendENV/               ← Python virtualenv
└── frontencENV/              ← Frontend node env
```

---

## 2. Current Status (as of 2026-06-07)

### Completed Features
- [x] OTP-based login for mobile clients
- [x] Admin password login (JWT)
- [x] Staff/MakeupArtist self-registration + admin approval flow
- [x] User management (CRUD for staff, clients, makeup artists)
- [x] Event CRUD + status lifecycle
- [x] Staff assignment to events
- [x] Payment integration (PhonePe — sandbox, not yet live)
- [x] Live location tracking (hooks into C++ server)
- [x] Master Data module: Themes, Uniforms, Subscription Plans, Payment Terms, Inventory
- [x] **Crew Gallery** — crew member images for mobile "Our Crew" section
- [x] **Extended Payment Terms** — per-tier staff pricing, default hours, overtime rate
- [x] **Coupon Codes** — CRUD, validate API, discount calculation

### Pending / In Progress
- [ ] `used_count` increment on event booking confirmation (coupon integration in events API)
- [ ] PhonePe payment flow — live environment not configured
- [ ] Public landing pages and recruitment form (commented out in App.jsx)
- [ ] Mobile app deployment (dev gives 404 because code hasn't been deployed to AWS Lambda)
- [ ] Diamond-tier event pricing — handled manually, no automated calculation

### Known Issues
- S3 image permissions: only folders with bucket-level public policy are readable publicly. Currently public: `staff/` prefix. Crew images stored at `staff/crew/` to inherit this permission.
- `drf_yasg` is excluded when running on AWS Lambda (stripped metadata causes errors). Swagger UI only available in local dev.

---

## 3. Architecture

```
Mobile App (React Native)
        │
        ▼ HTTPS
Admin Panel (React JS)  ──────►  Django Backend (Python)
                                        │
                                        ├── MongoDB (MongoEngine)
                                        ├── AWS S3 (image storage)
                                        ├── AWS SES / SMTP (OTP emails)
                                        └── C++ Location Server (via HTTP)

Deployment: AWS Lambda + Mangum adapter (WSGI → Lambda handler)
```

### Request Flow
1. All requests hit `https://<domain>/api/<module>/`
2. `GlobalExceptionMiddleware` catches unhandled exceptions
3. `JWTAuthenticationMiddleware` validates Bearer tokens (sets `request.user_payload`)
4. View decorator `@require_auth` checks `request.user_payload`
5. `@require_role(["ADMIN"])` checks role against payload
6. View returns via `api_response(success, message, data, status_code)`

---

## 4. Folder Structure

### Backend (`nuvo_web_backend/`)
```
nuvo_web_backend/
├── config/
│   ├── settings/
│   │   ├── base.py          ← All settings (single file, no split env yet)
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py              ← Root URL conf
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── accounts/            ← Auth: OTP, JWT, login, registration, approval
│   │   ├── models.py        ← OTP, BlacklistedToken
│   │   ├── views.py         ← send_otp, verify_otp, admin_login, logout, etc.
│   │   ├── urls.py
│   │   └── middleware.py    ← JWTAuthenticationMiddleware
│   ├── users/               ← User profiles
│   │   ├── models.py        ← User, ClientProfile, StaffProfile, MakeupArtistProfile
│   │   ├── views.py         ← Admin CRUD for users, profile management
│   │   ├── staff_registration.py  ← Public staff self-registration endpoint
│   │   └── urls.py
│   ├── master/              ← Master data (lookup tables, config)
│   │   ├── models.py        ← EventTheme, UniformCategory, SubscriptionPlanSettings,
│   │   │                       PaymentTerms, CrewMember, Coupon
│   │   ├── views.py         ← All master data CRUD + public mobile endpoints
│   │   └── urls.py
│   ├── events/              ← Event booking and lifecycle
│   │   ├── models.py        ← Event, Venue, GSTDetails, PaymentInfo (embedded)
│   │   ├── views.py         ← Event CRUD, staff assignment, payment, tracking
│   │   ├── dashboard_views.py  ← Dashboard stats, on-duty staff
│   │   └── urls.py
│   └── common/              ← Shared utilities
│       ├── constants.py     ← UserRole, UserStatus, SubscriptionPlan enums
│       ├── s3_utils.py      ← upload_file_to_s3(), delete_file_from_s3()
│       ├── email_utils.py   ← send_otp_email()
│       ├── phonepay_utils.py ← PhonePe payment gateway helpers
│       ├── location_utils.py ← HTTP calls to C++ location server
│       ├── error_middleware.py ← GlobalExceptionMiddleware
│       ├── safe_deref.py    ← Safe MongoEngine reference dereferencing helper
│       └── validators.py
├── requirements.txt
├── new_apis.md              ← Public API docs for mobile developer
└── CLAUDE.md                ← This file
```

### Frontend (`nuvo_web_frountend/`)
```
nuvo_web_frountend/src/
├── App.jsx                  ← Route definitions
├── main.jsx                 ← Vite entry
├── api/
│   ├── axiosInstance.js     ← Axios + JWT interceptor + auto-refresh
│   ├── AuthApi.js           ← login, logout, OTP calls
│   ├── masterApi.js         ← All master data API calls
│   ├── userApi.js           ← User management API calls
│   └── eventApi.js          ← Event API calls
├── auth/
│   ├── AuthContext.jsx      ← JWT context (login, logout, user state)
│   └── ProtectedRoute.jsx   ← Redirect unauthenticated users
├── layouts/
│   ├── MainLayout.jsx       ← Sidebar + header layout for admin pages
│   └── AuthLayout.jsx       ← Bare layout for login/register
├── pages/
│   ├── auth/                ← Login.jsx, Register.jsx, VerifyOtp.jsx
│   ├── user_management/     ← Staff.jsx, StaffDetails.jsx, Clients.jsx,
│   │                           ClientDetails.jsx, MakeupArtist.jsx, MakeupArtistDetails.jsx
│   ├── Dashboard.jsx        ← Stats overview
│   ├── Events.jsx           ← Event list
│   ├── EventDetails.jsx     ← Single event view + status management
│   ├── TrackEvent.jsx       ← Live staff location tracking
│   ├── MasterData.jsx       ← Tabbed master data panel (Themes, Uniforms, Crew,
│   │                           Subscription, Payment Terms, Coupons, Inventory)
│   ├── Uniforms.jsx         ← Uniform gallery/management
│   └── Reports.jsx
└── components/              ← Shared UI components
```

---

## 5. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Backend Framework | Django | 6.0.2 |
| REST API | Django REST Framework | 3.16.1 |
| Database ODM | MongoEngine | 0.29.1 |
| Database | MongoDB | (cloud — URI via env) |
| Auth | djangorestframework_simplejwt | 5.5.1 |
| File Storage | AWS S3 (boto3) | 1.42.61 |
| Email | SMTP (django email backend) | — |
| Payment | PhonePe gateway | sandbox |
| Lambda Adapter | Mangum | 0.17.0 |
| Server | Gunicorn (local), Lambda (prod) | — |
| Image Processing | Pillow | 12.1.1 |
| API Docs | drf-yasg (local only) | 1.21.15 |
| Frontend | React + Vite | — |
| HTTP Client | Axios | — |
| Styling | Bootstrap Icons + custom CSS | — |

---

## 6. Environment Setup

### Backend

```bash
# 1. Activate virtualenv
source /Users/rudreshac/Desktop/rakesh/Nuvo/backendENV/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env in nuvo_web_backend/ with:
SECRET_KEY=<django-secret-key>
MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<dbname>
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<your-gmail>
EMAIL_HOST_PASSWORD=<app-password>
EMAIL_USE_TLS=True
AWS_STORAGE_BUCKET_NAME=nuvohosting
AWS_S3_REGION_NAME=ap-south-1
S3_ACCESS_KEY_ID=<aws-access-key>
S3_SECRET_ACCESS_KEY=<aws-secret-key>
PHONEPE_MERCHANT_ID=PGTESTPAYUAT
PHONEPE_SALT_KEY=<phonepe-salt>
PHONEPE_SALT_INDEX=1
PHONEPE_BASE_URL=https://api-preprod.phonepe.com/apis/pg-sandbox
PHONEPE_REDIRECT_URL=https://yourdomain.com/api/events/payment/callback/
PHONEPE_CALLBACK_URL=https://yourdomain.com/api/events/payment/webhook/
LOCATION_SERVER_URL=http://localhost:9090

# 4. Run development server
python manage.py runserver
```

### Frontend

```bash
# 1. Install dependencies
cd nuvo_web_frountend
npm install

# 2. Create .env in nuvo_web_frountend/ with:
VITE_API_BASE_URL=http://127.0.0.1:8000/api

# 3. Run dev server
npm run dev
```

---

## 7. Important Commands

```bash
# Run backend (from nuvo_web_backend/)
python manage.py runserver

# Run frontend (from nuvo_web_frountend/)
npm run dev

# Test a public endpoint (no auth)
curl http://127.0.0.1:8000/api/master/crew/public/
curl http://127.0.0.1:8000/api/master/payment/config/

# Test coupon validate
curl -X POST http://127.0.0.1:8000/api/master/coupons/validate/ \
  -H "Content-Type: application/json" \
  -d '{"code": "SAVE20"}'

# ngrok for mobile developer to test local backend
ngrok http 8000
# Share the https://xxxx.ngrok.io URL — mobile dev uses it as base URL

# Swagger UI (local only — not available on Lambda)
http://127.0.0.1:8000/swagger/
```

---

## 8. Backend Overview

### Auth & Authorization Decorators

All auth logic lives in `apps/accounts/`. Two custom decorators are used across all protected views:

```python
from apps.accounts.decorators import require_auth, require_role

@csrf_exempt
@require_auth                          # Validates Bearer JWT → sets request.user_payload
@require_role(["ADMIN"])              # Checks role in payload
def my_admin_view(request):
    user_id = request.user_payload["user_id"]
    role    = request.user_payload["role"]
```

Public (no-auth) views use only `@csrf_exempt` with no other decorators.

### API Response Helper

Every view returns via the common helper:

```python
from apps.common.views import api_response

return api_response(True,  "Success message", data_dict)        # 200
return api_response(False, "Error message",   {},   400)        # 4xx
return api_response(False, "Server error",    {},   500)        # 5xx
```

Response shape is always:
```json
{ "success": true|false, "message": "...", "data": {...} }
```

### S3 File Upload Pattern

**Always use the common utility** — never use local/inline S3 code:

```python
from apps.common.s3_utils import upload_file_to_s3, delete_file_from_s3

# Upload
img_file = request.FILES.get("image")
url = upload_file_to_s3(img_file, "staff/crew")   # returns public URL

# Delete (on update/delete)
delete_file_from_s3(old_url)
```

**S3 folder permissions:** Only the `staff/` prefix has bucket-level public read access.
- ✅ `staff/crew/` — crew member images
- ✅ `staff/gallery/` — staff profile gallery
- ❌ `crew/` — NOT publicly accessible (don't use this)

### MongoDB / MongoEngine Patterns

No Django ORM — no migrations. All models use MongoEngine `Document`.

```python
# Primary key pattern (UUID string)
id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))

# Auto-update timestamps
def save(self, *args, **kwargs):
    self.updated_at = datetime.utcnow()
    return super().save(*args, **kwargs)

# Query examples
User.objects(email=email).first()
Event.objects(client=client_profile, status__ne="cancelled")
CrewMember.objects(is_active=True).order_by("name")
```

---

## 9. Frontend Overview

### Axios Instance & JWT Flow

`src/api/axiosInstance.js` handles all HTTP:
- Attaches `Authorization: Bearer <token>` from `localStorage` on every request
- On `401` response: automatically calls `POST /api/auth/refresh-token/` to get a new access token
- If refresh fails: clears localStorage and redirects to `/admin/login`
- All API files import from this instance: `import api from './axiosInstance'`

### Auth Context

`src/auth/AuthContext.jsx` provides:
- `user` — parsed user object from localStorage
- `isAuthenticated` — boolean
- `isLoading` — true while rehydrating from localStorage (prevents flash redirect)
- `login(tokens, userData)` — stores tokens + user in localStorage
- `logout()` — calls blacklist API then clears localStorage

### Admin Panel Routes

| Path | Component | Auth |
|---|---|---|
| `/admin/login` | Login.jsx | Public |
| `/admin/register` | Register.jsx | Public |
| `/admin/verify-otp` | VerifyOtp.jsx | Public |
| `/admin` | Dashboard.jsx | Protected |
| `/admin/events` | Events.jsx | Protected |
| `/admin/events/:id` | EventDetails.jsx | Protected |
| `/admin/events/:id/track` | TrackEvent.jsx | Protected |
| `/admin/staff` | Staff.jsx | Protected |
| `/admin/staff/:id` | StaffDetails.jsx | Protected |
| `/admin/makeup-artist` | MakeupArtist.jsx | Protected |
| `/admin/clients` | Clients.jsx | Protected |
| `/admin/master-data` | MasterData.jsx | Protected |
| `/admin/uniforms` | Uniforms.jsx | Protected |
| `/admin/reports` | Reports.jsx | Protected |

---

## 10. API Reference (Full)

### Auth — `/api/auth/`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/send-otp/` | ❌ | Send OTP to email (mobile login) |
| POST | `/auth/verify-otp/` | ❌ | Verify OTP → returns JWT tokens |
| POST | `/auth/resend-otp/` | ❌ | Resend OTP |
| POST | `/auth/refresh-token/` | ❌ | Refresh access token using refresh token |
| POST | `/auth/logout/` | ✅ | Blacklist refresh token |
| GET  | `/auth/me/` | ✅ | Get current user info |
| POST | `/auth/admin/login/` | ❌ | Admin email+password login |
| POST | `/auth/register/admin/` | ❌ | Register new admin (requires approval) |
| POST | `/auth/register/staff-makeup/` | ❌ | Register staff or makeup artist |
| POST | `/auth/admin/approve-user/` | ✅ ADMIN | Approve pending user |
| GET  | `/auth/admin/pending-users/` | ✅ ADMIN | List users awaiting approval |
| POST | `/auth/admin/change-status/` | ✅ ADMIN | Change user status |

### Users — `/api/users/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET  | `/users/profile/` | ✅ | Get own user record |
| PUT  | `/users/profile/update/` | ✅ | Update own user record |
| POST | `/users/register/staff/` | ❌ | Public staff self-registration (multipart) |
| POST | `/users/complete/client/` | ✅ CLIENT | Complete client profile |
| POST | `/users/complete/staff/` | ✅ STAFF | Complete staff profile |
| POST | `/users/complete/makeup/` | ✅ MAKEUP_ARTIST | Complete makeup artist profile |
| GET  | `/users/my-profile/` | ✅ | Get own full profile |
| PUT  | `/users/update-profile/` | ✅ | Update own full profile |
| POST | `/users/staff/upload-images/` | ✅ STAFF | Upload gallery images |
| GET  | `/users/api/clients/` | ✅ ADMIN | List all clients |
| GET  | `/users/api/clients/:id/` | ✅ ADMIN | Client detail |
| GET  | `/users/api/staff/` | ✅ ADMIN | List all staff |
| GET  | `/users/api/staff/:id/` | ✅ ADMIN | Staff detail |
| GET  | `/users/api/makeup-artists/` | ✅ ADMIN | List makeup artists |
| POST | `/users/admin/create-client/` | ✅ ADMIN | Admin creates client |
| POST | `/users/admin/staff/create/` | ✅ ADMIN | Admin creates staff |
| PUT  | `/users/admin/staff/:id/update/` | ✅ ADMIN | Admin updates staff |
| DELETE | `/users/admin/staff/:id/delete/` | ✅ ADMIN | Admin deletes staff |
| GET  | `/users/mobile/modals_list_filter/` | ✅ | Staff list for assignment modal |

### Master Data — `/api/master/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET  | `/master/themes/` | ✅ ADMIN | List event themes |
| POST | `/master/themes/create/` | ✅ ADMIN | Create theme |
| PUT  | `/master/themes/:id/update/` | ✅ ADMIN | Update theme |
| DELETE | `/master/themes/:id/delete/` | ✅ ADMIN | Delete theme |
| GET  | `/master/uniform/` | ✅ ADMIN | List uniforms |
| GET  | `/master/uniform/filter/` | ❌ | Public uniform filter (mobile) |
| POST | `/master/uniform/create/` | ✅ ADMIN | Create uniform |
| GET  | `/master/inventory/` | ✅ ADMIN | List inventory |
| GET  | `/master/inventory/summary/` | ✅ ADMIN | Inventory summary |
| GET  | `/master/crew/public/` | ❌ | **Public** — crew gallery for mobile |
| POST | `/master/crew/create/` | ✅ ADMIN | Create crew member |
| GET  | `/master/crew/` | ✅ ADMIN | List crew members (admin) |
| PUT  | `/master/crew/:id/update/` | ✅ ADMIN | Update crew member |
| DELETE | `/master/crew/:id/delete/` | ✅ ADMIN | Delete crew member |
| GET  | `/master/subscription/` | ✅ ADMIN | List subscription plans |
| PUT  | `/master/subscription/:name/update/` | ✅ ADMIN | Update subscription plan |
| GET  | `/master/payment/config/` | ❌ | **Public** — payment config for mobile |
| GET  | `/master/payment/` | ✅ ADMIN | Get payment terms (admin) |
| PUT  | `/master/payment/update/` | ✅ ADMIN | Update payment terms |
| POST | `/master/coupons/validate/` | ❌ | **Public** — validate coupon for mobile |
| POST | `/master/coupons/apply/` | ❌ | Apply coupon (server-side calc) |
| GET  | `/master/coupons/` | ✅ ADMIN | List all coupons |
| POST | `/master/coupons/create/` | ✅ ADMIN | Create coupon |
| PUT  | `/master/coupons/:id/update/` | ✅ ADMIN | Update coupon |
| DELETE | `/master/coupons/:id/delete/` | ✅ ADMIN | Delete coupon |

### Events — `/api/events/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET  | `/events/dashboard/stats/` | ✅ ADMIN | Dashboard summary stats |
| GET  | `/events/dashboard/on-duty/` | ✅ ADMIN | Currently on-duty staff |
| GET  | `/events/` | ✅ ADMIN | List all events |
| POST | `/events/create/` | ✅ | Create event |
| GET  | `/events/get-my-events/` | ✅ CLIENT | Client's own events |
| GET  | `/events/:id/` | ✅ | Get event detail |
| PUT  | `/events/:id/update/` | ✅ | Update event |
| DELETE | `/events/:id/delete/` | ✅ | Delete event |
| PUT  | `/events/:id/status/` | ✅ ADMIN | Update event status |
| GET  | `/events/:id/available-staff/` | ✅ ADMIN | List available staff for event |
| POST | `/events/:id/assign-crew/` | ✅ ADMIN | Assign crew to event |
| GET  | `/events/:id/track/` | ✅ | Live location tracking |
| POST | `/events/:id/payment/initiate/` | ✅ | Initiate PhonePe payment |
| POST | `/events/payment/callback/` | ❌ | PhonePe redirect callback |
| POST | `/events/payment/webhook/` | ❌ | PhonePe server webhook |
| GET  | `/events/staff/upcoming-all/` | ✅ STAFF | All upcoming events (staff view) |
| GET  | `/events/staff/assigned/` | ✅ STAFF | Staff's assigned events |
| GET  | `/events/staff/completed/` | ✅ STAFF | Staff's completed events |
| POST | `/events/staff/online-status/` | ✅ STAFF | Update staff online/offline |

---

## 11. Authentication & Authorization

### Roles
```
ADMIN         → Admin panel access, full CRUD on everything
CLIENT        → Mobile app, books events, sees own data
STAFF         → Mobile app, sees assigned events, updates status
MAKEUP_ARTIST → Mobile app, similar to STAFF
```

### Login Flows

**Admin (web panel):**
1. `POST /api/auth/admin/login/` with `{ email, password }`
2. Returns `{ access_token, refresh_token, user }` on success
3. Frontend stores in localStorage via `AuthContext.login()`

**Client/Staff/MakeupArtist (mobile):**
1. `POST /api/auth/send-otp/` with `{ email }` → OTP sent via email
2. `POST /api/auth/verify-otp/` with `{ email, otp }` → returns JWT tokens
3. CLIENT accounts are auto-created on first verify; STAFF/MUA require admin approval

**Google Play Store Verification:**
- Test account `actest967@gmail.com` always receives OTP `1234` (hardcoded in accounts/views.py)

### Token Lifecycle
- Access token: short-lived (used in Authorization header)
- Refresh token: longer-lived, stored in localStorage
- Logout: `POST /api/auth/logout/` blacklists the refresh token
- Auto-refresh: axiosInstance intercepts 401 → calls refresh endpoint → retries original request
- Token blacklist stored in `BlacklistedToken` MongoDB collection

### Approval Gate
| Role | `is_approved` on creation | Who approves |
|---|---|---|
| CLIENT | `True` (auto-approved) | N/A |
| STAFF | `False` | Admin via `approve-user` endpoint |
| MAKEUP_ARTIST | `False` | Admin |
| ADMIN | `False` | Another admin |

---

## 12. Database Structure (MongoDB Collections)

| Collection | Model | Description |
|---|---|---|
| `users` | `User` | Core accounts for all roles |
| `client_profiles` | `ClientProfile` | Extended client data, subscription plan |
| `staff_profiles` | `StaffProfile` | Full staff registration data (physical dims, languages, gallery) |
| `makeup_artist_profiles` | `MakeupArtistProfile` | MUA profile |
| `otps` | `OTP` | OTP codes (expire in 5 min, 4 digits, max 3 attempts) |
| `blacklisted_tokens` | `BlacklistedToken` | Revoked refresh tokens |
| `event_themes` | `EventTheme` | Theme images for events |
| `uniform_categories` | `UniformCategory` | Uniform types with inventory |
| `subscription_plan_settings` | `SubscriptionPlanSettings` | Plan config per tier |
| `payment_terms` | `PaymentTerms` | Advance %, staff pricing, overtime, PhonePe settings |
| `crew_members` | `CrewMember` | Crew gallery images for mobile "Our Crew" section |
| `coupons` | `Coupon` | Discount codes (FLAT or PERCENTAGE) |
| `events` | `Event` | Event bookings (embeds Venue, GSTDetails, PaymentInfo) |

### Key Model Details

**PaymentTerms** (single document, updated in place):
```
advancePercentage       — % of total due at booking (default 30)
staff_pricing           — dict: { BRONZE: 15000, SILVER: 30000, GOLD: 45000, PLATINUM: 65000 }
default_hours_per_day   — standard hours before overtime kicks in (default 5.0)
overtime_rate_per_hour  — INR per hour per staff member above default (default 3000.0)
phonepay_merchant_id, phonepay_salt_key, etc.
```

**Coupon**:
```
code            — unique, uppercase string
discount_type   — "FLAT" or "PERCENTAGE"
discount_value  — INR amount or percentage
usage_limit     — max times the coupon can be used
used_count      — incremented ONLY on event confirmation (not on validate)
is_active       — admin toggle
expiry_date     — nullable DateTimeField
```

**Event statuses**: `created → planning_started → staff_allocated → completed` (or `cancelled`)

---

## 13. Payment Calculation Logic

Documented here for reference (also in `new_apis.md`):

```js
// Staff pricing per tier (per person per day)
// Bronze: ₹15,000 | Silver: ₹30,000 | Gold: ₹45,000 | Platinum: ₹65,000
// Diamond: negotiated directly — NOT included in automated calculation

const base     = staff_pricing[tier] × num_staff × num_days
const extra    = Math.max(0, actual_hours - default_hours_per_day)
const overtime = extra × overtime_rate_per_hour × num_staff
const total    = base + overtime
const advance  = total × (advancePercentage / 100)
const balance  = total - advance
```

**Coupon discount:**
```js
if (coupon.discount_type === 'PERCENTAGE')
  discount = (coupon.discount_value / 100) * total
else  // FLAT
  discount = coupon.discount_value

final = Math.max(0, total - discount)
```

---

## 14. State Management (Frontend)

- **No Redux or Zustand** — all state is local `useState` per page/component
- **Auth state** — managed by `AuthContext` (React Context), persisted in localStorage
- **API calls** — made directly in components via `useEffect` or event handlers
- **Token storage** — `access_token`, `refresh_token`, `user` all in `localStorage`
- **Auto token refresh** — handled transparently by Axios response interceptor

---

## 15. CI/CD & Deployment

- **No CI pipeline** — all changes verified locally by Rakesh before push
- **Git rule:** Claude never pushes to remote or creates PRs. Rakesh handles all git operations.
- **Backend deployment:** AWS Lambda via Mangum adapter. `manage.py runserver` is for local only.
- **Frontend deployment:** Unknown (Vite build → likely S3/CloudFront or similar)
- **`drf_yasg` (Swagger):** Auto-excluded on Lambda via `AWS_LAMBDA_FUNCTION_NAME` env check

---

## 16. Testing

- No automated tests exist yet
- Manual testing via:
  - `python manage.py runserver` + curl or Postman
  - Swagger UI at `http://127.0.0.1:8000/swagger/` (local only)
  - ngrok for exposing local backend to mobile dev during development

---

## 17. Known Issues & Technical Debt

| Issue | Status | Notes |
|---|---|---|
| `used_count` not incremented on booking | Pending | Must be added to event confirmation endpoint |
| PhonePe live credentials not configured | Pending | Only sandbox tested |
| No pagination on any listing endpoint | By design | Admin controls data volume |
| Landing page / recruitment form commented out | Inactive | `App.jsx` has commented routes |
| Diamond tier pricing not automated | By design | Admin adds manually to event |
| No automated tests | Tech debt | All manual currently |
| `CORS_ALLOW_ALL_ORIGINS = True` | Dev setting | Should restrict on prod |
| `DEBUG = False` in base.py | Unusual | Dev runs without DEBUG; no separate dev settings |
| Email port read without `int()` fallback safety | Minor | Would crash if `EMAIL_PORT` not in env |

---

## 18. Architectural Decisions

### Why MongoEngine (not Django ORM)?
MongoDB chosen for flexible schema — staff profiles have many optional fields that vary by individual. No migrations needed when adding fields.

### Why not use Django REST Framework serializers?
Custom `_ser_*()` functions are used throughout instead of DRF serializers. This avoids MongoEngine/DRF compatibility issues and gives full control over response shape.

### Why single `PaymentTerms` document?
Only one set of payment config exists globally. The document is created on first access and updated in place — no multi-tenancy needed.

### Why S3 bucket-level public policy (not per-object ACL)?
AWS has deprecated ACLs for new buckets. Bucket policy granting public read on `staff/*` prefix is the correct approach. New image folders must be under `staff/` to be publicly accessible.

### Why frontend coupon calculation (not server-side)?
Validate endpoint returns coupon details; frontend does the math. This keeps the checkout flow fast (no extra round trip) and allows "Remove Coupon" without any API call.

---

## 19. Dependencies & Integrations

| Service | Purpose | Config location |
|---|---|---|
| MongoDB Atlas | Primary database | `MONGO_URI` env var |
| AWS S3 (`nuvohosting` bucket) | Image storage | `AWS_STORAGE_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, etc. |
| AWS Lambda | Production hosting | `AWS_LAMBDA_FUNCTION_NAME` (set by AWS automatically) |
| SMTP (Gmail) | OTP emails | `EMAIL_HOST_*` env vars |
| PhonePe | Payment gateway | `PHONEPE_*` env vars (sandbox mode) |
| C++ Location Server | Real-time staff tracking | `LOCATION_SERVER_URL` env var |

---

## 20. Mobile Developer API Reference

The file `new_apis.md` in this repo root contains complete documentation for the 3 public APIs the mobile developer consumes:
1. `GET /api/master/crew/public/` — Crew gallery
2. `GET /api/master/payment/config/` — Payment pricing config
3. `POST /api/master/coupons/validate/` — Coupon validation

These 3 endpoints require **no authentication**.

---

## 21. MasterData.jsx Tab Structure

The `MasterData.jsx` page has the following tabs in order:
1. **Themes** — Event theme images
2. **Uniforms** — Uniform categories
3. **Crew Gallery** — Crew member photo management (for mobile "Our Crew" section)
4. **Subscription** — Plan settings per tier
5. **Payment Terms** — Advance %, tier pricing, overtime + Diamond note
6. **Coupons** — Coupon CRUD with usage progress and discount display
7. **Inventory** — Stock management (linked to uniform categories)

---

## 22. Change Log

| Date | Change | Files |
|---|---|---|
| 2026-06-07 | Added Crew Gallery feature (model, CRUD endpoints, admin UI, public mobile API) | `apps/master/models.py`, `apps/master/views.py`, `apps/master/urls.py`, `src/pages/MasterData.jsx`, `src/api/masterApi.js` |
| 2026-06-07 | Extended PaymentTerms with staff_pricing per tier, default_hours_per_day, overtime_rate_per_hour | `apps/master/models.py`, `apps/master/views.py` |
| 2026-06-07 | Added Coupon model + full CRUD + validate/apply public endpoints | `apps/master/models.py`, `apps/master/views.py`, `apps/master/urls.py` |
| 2026-06-07 | Added public mobile API endpoints: crew/public/, payment/config/, coupons/validate/ | `apps/master/urls.py`, `apps/master/views.py` |
| 2026-06-07 | Created new_apis.md — API reference for mobile developer | `new_apis.md` |
| 2026-06-07 | Fixed S3 upload folder for crew images: changed "crew" → "staff/crew" for public access | `apps/master/views.py` |
| 2026-06-07 | Created CLAUDE.md — this engineering knowledge base | `CLAUDE.md` |
